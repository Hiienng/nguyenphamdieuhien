"""
EtseeMate Ads Data Pipeline — API routes.

Prefix: /api/v1/EtseeMate
"""
import asyncio
import logging
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import NotSupportedError

logger = logging.getLogger(__name__)

from ...core.database import get_db
from ...core.auth_middleware import require_subscription, get_tenant_db_for_user
from ...models.user import User
from ...schemas.internal import (
    UploadResponse,
    ExtractResponse,
    ConfirmRequest,
    ConfirmResponse,
    BatchActionResponse,
    BatchHistoryItem,
    IngestListingRequest,
    IngestKeywordRequest,
    IngestResponse,
)
from ...services import internal_service, reporting_etl, crawler_ops

router = APIRouter(prefix="/EtseeMate", tags=["EtseeMate"])


async def _assert_batch_owner(batch_id: str, user: "User", db: AsyncSession) -> "ImportBatch":
    """Load batch and 404 if it doesn't exist or belong to user (no leak)."""
    from ...models.import_batch import ImportBatch
    from sqlalchemy import select

    batch = (await db.execute(
        select(ImportBatch).where(ImportBatch.batch_id == batch_id)
    )).scalar_one_or_none()
    if not batch or (batch.tenant_id and batch.tenant_id != user.id and not user.is_admin):
        raise HTTPException(404, "Batch not found")
    return batch


@router.get("/status")
async def get_batch_status(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_subscription),
):
    """
    Get current progress of a batch.
    """
    batch = await _assert_batch_owner(batch_id, user, db)
    return {
        "batch_id": batch.batch_id,
        "status": batch.status,
        "progress": batch.progress or 0,
        "total_files": batch.total_files or 0,
        "listing_count": batch.listing_count or 0,
        "keyword_count": batch.keyword_count or 0,
        "error_message": batch.error_message,
        "quota_exhausted": bool((batch.preview_data or {}).get("quota_exhausted")),
    }


@router.get("/preview")
async def get_batch_preview(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_subscription),
):
    """
    Get the preview JSON data for a batch.
    Returns empty streaming preview instead of 404 when data isn't ready yet.
    """
    await _assert_batch_owner(batch_id, user, db)
    try:
        return await internal_service.get_batch_preview(batch_id)
    except FileNotFoundError:
        # Return empty preview instead of 404 to avoid console error spam from polling
        return {
            "batch_id": batch_id,
            "listing_report": [],
            "keyword_report": [],
            "failed_files": [],
            "successful_files": [],
            "extraction_errors": {},
            "quota_exhausted": False,
            "streaming": True,
        }


# ── POST /upload — receive images, create batch ─────────────────────────────

@router.post("/upload", response_model=UploadResponse)
async def upload_screenshots(
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_subscription),
):
    if not files:
        raise HTTPException(400, "No files provided")
    if len(files) > 100:
        raise HTTPException(400, "Tối đa 100 file mỗi lần import để đảm bảo tốc độ trích xuất.")

    allowed = {".png", ".jpg", ".jpeg", ".webp"}
    for f in files:
        ext = "." + f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
        if ext not in allowed:
            raise HTTPException(400, f"File type not allowed: {f.filename}")

    # Validate image content (magic bytes, size, dimensions)
    errors = []
    file_contents: list[tuple] = []  # (UploadFile, bytes)
    for f in files:
        content = await f.read()
        err = await internal_service.validate_image(f.filename, content)
        if err:
            errors.append(err)
        else:
            file_contents.append((f, content))

    if errors:
        raise HTTPException(
            422,
            detail={"message": "Image validation failed", "errors": errors},
        )

    try:
        batch_id, count, _ = await internal_service.save_uploaded_files(
            file_contents, db, tenant_id=user.id,
        )
    except Exception as exc:
        logger.exception("save_uploaded_files failed")
        raise HTTPException(500, f"Lỗi lưu file: {exc}") from exc
    return UploadResponse(batch_id=batch_id, file_count=count)


# ── POST /extract — run Claude Vision on batch images ────────────────────────

@router.post("/extract")
async def extract_batch(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_subscription),
):
    """
    Start extraction in the background using asyncio.create_task.
    (BackgroundTasks closes DB connections after request — create_task avoids that.)
    """
    await _assert_batch_owner(batch_id, user, db)
    asyncio.create_task(internal_service.run_extraction(batch_id))
    return {"message": "Extraction started in background", "batch_id": batch_id, "status": "processing"}


# ── POST /confirm — write reviewed data to DB ───────────────────────────────

@router.post("/confirm", response_model=ConfirmResponse)
async def confirm_import(req: ConfirmRequest, db: AsyncSession = Depends(get_tenant_db_for_user), user: User = Depends(require_subscription)):
    try:
        result = await internal_service.confirm_import(
            batch_id=req.batch_id,
            listing_report=[r.model_dump() for r in req.listing_report],
            keyword_report=[r.model_dump() for r in req.keyword_report],
            no_vm=req.no_vm,
            db=db,
            tenant_id=user.id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as exc:
        logger.exception("confirm_import failed for batch %s", req.batch_id)
        raise HTTPException(500, f"Lỗi confirm: {exc}") from exc

    # New raw rows just landed — rebuild reporting layer so the FE shows them
    # without the user having to click "Tải lại". Failure here must not break
    # the import response.
    try:
        await reporting_etl.refresh_if_stale(db, user.id, force=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Post-import reporting rebuild failed for batch %s: %s", req.batch_id, exc)

    return ConfirmResponse(imported=result["imported"], rows=result["rows"])


# ── POST /discard — cancel pending batch ─────────────────────────────────────

@router.post("/discard", response_model=BatchActionResponse)
async def discard_batch(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_subscription),
):
    await _assert_batch_owner(batch_id, user, db)
    try:
        await internal_service.discard_batch(batch_id, db)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return BatchActionResponse(batch_id=batch_id, status="discarded")


# ── POST /rollback — revert confirmed batch ──────────────────────────────────

@router.post("/rollback", response_model=BatchActionResponse)
async def rollback_batch(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_subscription),
):
    await _assert_batch_owner(batch_id, user, db)
    try:
        await internal_service.rollback_batch(batch_id, db)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return BatchActionResponse(batch_id=batch_id, status="rolled_back")


# ── GET /history — list import batches ───────────────────────────────────────

@router.get("/history", response_model=list[BatchHistoryItem])
async def import_history(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_subscription),
):
    return await internal_service.get_history(db, limit, tenant_id=user.id)


# ── GET /snapshot/{batch_id} — view confirmed data ──────────────────────────

@router.get("/snapshot/{batch_id}")
async def get_snapshot(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_subscription),
):
    await _assert_batch_owner(batch_id, user, db)
    data = await internal_service.get_snapshot(batch_id)
    if data is None:
        raise HTTPException(404, f"Snapshot not found for batch {batch_id}")
    return data


# ── POST /ingest/listing — extension pushes listing_report rows ──────────────

@router.post("/ingest/listing", response_model=IngestResponse)
async def ingest_listing(
    req: IngestListingRequest,
    db: AsyncSession = Depends(get_tenant_db_for_user),
    user: User = Depends(require_subscription),
):
    """Endpoint for browser extension to push listing_report rows.
    tenant_id is injected from JWT — extension never touches DB directly.
    """
    from ...models.listing_report import ListingReport
    from ...services.internal_extractor import _normalize_period
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    importer = req.importer or "extension"
    count = 0
    for row in req.rows:
        db.add(ListingReport(
            listing_id=row.listing_id,
            title=row.title,
            no_vm=row.no_vm,
            price=row.price,
            stock=row.stock,
            category=row.category,
            lifetime_orders=row.lifetime_orders,
            lifetime_revenue=row.lifetime_revenue,
            period=_normalize_period(row.period or ""),
            views=row.views,
            clicks=row.clicks,
            orders=row.orders,
            revenue=row.revenue,
            spend=row.spend,
            roas=row.roas,
            import_time=now,
            importer=importer,
            tenant_id=user.id,
        ))
        count += 1
    await db.commit()

    try:
        new_ids = list({r.listing_id for r in req.rows})
        await crawler_ops.enqueue_listings(db, new_ids, reason="extension_ingest")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Enqueue crawl_queue failed (ingest/listing): %s", exc)

    return IngestResponse(inserted=count)


# ── POST /ingest/keyword — extension pushes keyword_report rows ──────────────

@router.post("/ingest/keyword", response_model=IngestResponse)
async def ingest_keyword(
    req: IngestKeywordRequest,
    db: AsyncSession = Depends(get_tenant_db_for_user),
    user: User = Depends(require_subscription),
):
    """Endpoint for browser extension to push keyword_report rows."""
    from ...models.keyword_report import KeywordReport
    from ...services.internal_extractor import _normalize_period
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    importer = req.importer or "extension"
    count = 0
    for row in req.rows:
        db.add(KeywordReport(
            listing_id=row.listing_id,
            keyword=row.keyword,
            no_vm=row.no_vm,
            relevant=row.relevant,
            period=_normalize_period(row.period or ""),
            roas=row.roas,
            orders=row.orders,
            spend=row.spend,
            revenue=row.revenue,
            clicks=row.clicks,
            click_rate=row.click_rate,
            views=row.views,
            import_time=now,
            importer=importer,
            tenant_id=user.id,
        ))
        count += 1
    await db.commit()
    return IngestResponse(inserted=count)
