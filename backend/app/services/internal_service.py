from __future__ import annotations

"""
Internal Ads Data Pipeline — business logic.

Handles: upload → extract → confirm → discard → rollback → history → snapshot.
"""
import asyncio
import json
import logging
import os
import struct
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm.attributes import flag_modified

logger = logging.getLogger(__name__)

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import AsyncSessionLocal

from ..models.import_batch import ImportBatch
from ..models.listing_report import ListingReport
from ..models.keyword_report import KeywordReport
from ..models.manual_listing_report import ManualListingReport
from ..models.manual_keyword_report import ManualKeywordReport

# ── Image validation constants ──────────────────────────────────────────────
MIN_IMAGE_SIZE = 10 * 1024       # 10 KB — smaller is likely corrupt or icon
MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20 MB
MIN_DIMENSION = 200              # px — screenshots should be at least 200×200

# Temp storage path for uploaded files (instead of ImageKit during upload)
_TEMP_UPLOAD_DIR = Path("/tmp/etsy_uploads")

# Magic bytes for supported formats
_MAGIC = {
    b"\x89PNG\r\n\x1a\n": "png",
    b"\xff\xd8\xff": "jpeg",
    b"RIFF": "webp",  # WebP starts with RIFF....WEBP
}

# All persistent data lives in DB / ImageKit. No filesystem dependency.

VISION_QUOTA_MESSAGE = (
    "He thong da het quota Vision API. Vui long doi Gemini key hoac nap them credit Hugging Face roi thu lai."
)


def _now_batch_id() -> str:
    """Generate batch_id as YYYYMMDD_HHMM."""
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _is_quota_message(message: str | None) -> bool:
    msg = (message or "").lower()
    return "het quota vision api" in msg or ("quota" in msg and "huggingface" in msg and "gemini" in msg)


def _summarize_error_message(message: str | None) -> str | None:
    if not message:
        return message
    compact = " ".join(str(message).split())
    if _is_quota_message(compact):
        return VISION_QUOTA_MESSAGE
    return compact[:240]


# ── Image validation ─────────────────────────────────────────────────────────

def _detect_format(header: bytes) -> str | None:
    """Detect image format from first bytes (magic bytes)."""
    if header[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if header[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "webp"
    return None


def _read_dimensions(data: bytes, fmt: str) -> tuple[int, int] | None:
    """Extract (width, height) from image bytes without PIL."""
    try:
        if fmt == "png":
            # IHDR chunk starts at byte 16: width(4B) + height(4B)
            if len(data) < 24:
                return None
            w = struct.unpack(">I", data[16:20])[0]
            h = struct.unpack(">I", data[20:24])[0]
            return w, h
        if fmt == "jpeg":
            # Scan for SOF0/SOF2 marker (0xFF 0xC0 or 0xFF 0xC2)
            i = 2
            while i < len(data) - 9:
                if data[i] != 0xFF:
                    break
                marker = data[i + 1]
                if marker in (0xC0, 0xC2):
                    h = struct.unpack(">H", data[i + 5 : i + 7])[0]
                    w = struct.unpack(">H", data[i + 7 : i + 9])[0]
                    return w, h
                # Skip to next marker
                seg_len = struct.unpack(">H", data[i + 2 : i + 4])[0]
                i += 2 + seg_len
            return None
        if fmt == "webp":
            # VP8 lossy: width/height at bytes 26-29
            if len(data) >= 30 and data[12:16] == b"VP8 ":
                w = struct.unpack("<H", data[26:28])[0] & 0x3FFF
                h = struct.unpack("<H", data[28:30])[0] & 0x3FFF
                return w, h
            # VP8L lossless: width/height packed in bytes 21-24
            if len(data) >= 25 and data[12:16] == b"VP8L":
                bits = struct.unpack("<I", data[21:25])[0]
                w = (bits & 0x3FFF) + 1
                h = ((bits >> 14) & 0x3FFF) + 1
                return w, h
            return None
    except Exception:
        return None
    return None


async def validate_image(filename: str, content: bytes) -> str | None:
    """
    Validate image content. Returns error message string, or None if valid.

    Checks:
    1. File size (10 KB – 20 MB)
    2. Magic bytes match actual image format (not just extension)
    3. Minimum dimensions (200×200) — screenshot should be readable
    """
    size = len(content)
    if size < MIN_IMAGE_SIZE:
        return f"{filename}: quá nhỏ ({size:,} bytes < {MIN_IMAGE_SIZE:,}). Có thể file bị lỗi."
    if size > MAX_IMAGE_SIZE:
        mb = size / (1024 * 1024)
        return f"{filename}: quá lớn ({mb:.1f} MB > 20 MB)."

    fmt = _detect_format(content[:12])
    if fmt is None:
        return f"{filename}: không phải ảnh hợp lệ (PNG/JPEG/WebP). File có thể bị đổi extension."

    dims = _read_dimensions(content, fmt)
    if dims is not None:
        w, h = dims
        if w < MIN_DIMENSION or h < MIN_DIMENSION:
            return (
                f"{filename}: ảnh quá nhỏ ({w}×{h}px). "
                f"Screenshot cần ít nhất {MIN_DIMENSION}×{MIN_DIMENSION}px."
            )

    return None


# ── Save uploaded files to temp storage (fast, returns immediately) ─────────

async def save_uploaded_files(
    file_contents: list[tuple],
    db: AsyncSession,
) -> tuple[str, int, list[dict]]:
    """
    Save uploaded images to a local temp directory and record in DB.
    Returns (batch_id, file_count, image_files_placeholder).
    ImageKit upload happens later during extraction.
    """
    batch_id = _now_batch_id()

    # 1. Create batch record (status=uploading)
    batch = ImportBatch(
        batch_id=batch_id,
        status="uploading",
        file_count=len(file_contents),
        total_files=len(file_contents),
    )
    db.add(batch)
    await db.commit()

    # 2. Save files to temp directory
    batch_dir = _TEMP_UPLOAD_DIR / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)

    image_files_meta = []
    for f, content in file_contents:
        safe_name = f.filename.replace("/", "_").replace("..", "_")
        file_path = batch_dir / safe_name
        file_path.write_bytes(content)
        image_files_meta.append({
            "name": f.filename,
            "temp_path": str(file_path),
        })

    # 3. Update batch: store file metadata, mark as uploaded
    batch.image_files = image_files_meta
    batch.status = "uploaded"
    await db.commit()

    logger.info("Uploaded %d files to temp dir %s (batch=%s)", len(file_contents), batch_dir, batch_id)
    return batch_id, len(image_files_meta), image_files_meta


# ── Extract ──────────────────────────────────────────────────────────────────

async def run_extraction(batch_id: str, db: AsyncSession = None) -> dict:
    print(f"!!! BACKGROUND EXTRACTION TRIGGERED FOR BATCH: {batch_id} !!!")
    """
    Run extraction for all images in the batch.
    1. Upload temp files to ImageKit (if still pending)
    2. Extract data using Claude Vision
    3. Update DB status and progress
    Returns preview JSON.
    """
    if db is None:
        async with AsyncSessionLocal() as session:
            return await _run_extraction_impl(batch_id, session)
    else:
        return await _run_extraction_impl(batch_id, db)


async def _run_extraction_impl(batch_id: str, db: AsyncSession) -> dict:
    from .internal_extractor import extract_batch_streaming, _merge_results
    from . import imagekit_service

    result = await db.execute(
        select(ImportBatch).where(ImportBatch.batch_id == batch_id)
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise ValueError(f"Batch {batch_id} not found")

    file_metas = batch.image_files or []
    if not file_metas:
        raise ValueError(f"Batch {batch_id} has no images")

    # Step 1: Upload temp files to ImageKit (with error handling)
    batch.status = "to_imagekit"  # keep under 16 chars — DB column is VARCHAR(16)
    await db.commit()

    uploaded_to_ik = []
    try:
        for meta in file_metas:
            temp_path = meta.get("temp_path")
            if temp_path and os.path.exists(temp_path):
                with open(temp_path, "rb") as fh:
                    content = fh.read()
                ik_result = await imagekit_service.upload_image(meta["name"], content, batch_id)
                uploaded_to_ik.append(ik_result)
            else:
                # Fallback: try to read from DB (legacy flow)
                uploaded_to_ik.append(meta)

        # Store ImageKit URLs
        batch.image_files = uploaded_to_ik
        batch.status = "extracting"
        batch.progress = 0
        batch.total_files = len(uploaded_to_ik)
        await db.commit()
    except Exception as e:
        logger.error("ImageKit upload failed for batch %s: %s", batch_id, e)
        batch.status = "failed"
        batch.error_message = f"ImageKit upload failed: {e}"
        await db.commit()
        return {"batch_id": batch_id, "listing_report": [], "keyword_report": [], "failed_files": [m.get("name","") for m in file_metas], "successful_files": [], "streaming": False}

    # Step 2: Fetch images from ImageKit for extraction
    images: list[tuple[str, bytes]] = []
    for info in uploaded_to_ik:
        url = info.get("url")
        if url:
            try:
                content = await imagekit_service.fetch_image_bytes(url)
                images.append((info["name"], content))
            except Exception as e:
                logger.warning("Failed to fetch image bytes for %s: %s", info.get("name", "unknown"), e)
        else:
            logger.warning("Skipping file without URL: %s", info.get("name", "unknown"))
    
    if not images:
        logger.error("No images could be fetched for extraction (batch=%s)", batch_id)
        batch.status = "failed"
        batch.error_message = "All images failed to fetch from storage"
        await db.commit()
        return {"batch_id": batch_id, "listing_report": [], "keyword_report": [], "failed_files": [m.get("name","") for m in file_metas], "successful_files": [], "streaming": False}

    results: list[dict | None] = [None] * len(images)
    extraction_errors: dict[str, str] = {}
    logger.info("Starting extraction for batch %s (%d images)", batch_id, len(images))

    def _build_preview(streaming: bool, upto_idx: int | None = None) -> dict:
        current_lr, current_kr = _merge_results(results)
        if streaming and upto_idx is not None:
            processed = [i for i in range(len(images)) if i <= upto_idx]
        else:
            processed = list(range(len(images)))
        failed = [images[i][0] for i in processed if results[i] is None]
        successful = [images[i][0] for i in processed if results[i] is not None]
        errors = {
            images[i][0]: _summarize_error_message(
                extraction_errors.get(images[i][0], "Extraction returned no data")
            )
            for i in processed
            if results[i] is None
        }
        quota_exhausted = bool(failed) and all(_is_quota_message(errors.get(name)) for name in failed)
        return {
            "batch_id": batch_id,
            "listing_report": current_lr,
            "keyword_report": current_kr,
            "failed_files": failed,
            "successful_files": successful,
            "extraction_errors": errors,
            "quota_exhausted": quota_exhausted,
            "streaming": streaming,
        }

    async def on_result(idx: int, result: dict | None, error_message: str | None = None):
        results[idx] = result
        filename = images[idx][0]
        if result is None:
            extraction_errors[filename] = _summarize_error_message(
                error_message or "Extraction returned no data"
            )
        else:
            extraction_errors.pop(filename, None)
        try:
            partial = _build_preview(streaming=True, upto_idx=idx)
            batch.preview_data = partial
            flag_modified(batch, "preview_data")
            batch.progress = sum(
                1 for i, r in enumerate(results) if r is not None or (i <= idx and r is None)
            )
            batch.listing_count = len(partial["listing_report"])
            batch.keyword_count = len(partial["keyword_report"])
            await db.commit()
        except Exception as e:
            logger.error("Partial merge failed: %s", e)

    try:
        await extract_batch_streaming(images, on_result=on_result)
    except Exception as e:
        logger.error("CRITICAL EXTRACTION ERROR: %s", e)
        batch.status = "failed"
        batch.error_message = f"Streaming Extraction failed: {e}"
        await db.commit()
        raise

    final_preview = _build_preview(streaming=False)
    batch.preview_data = final_preview
    flag_modified(batch, "preview_data")
    batch.status = "extracted" if final_preview["successful_files"] else "failed"
    if not final_preview["successful_files"]:
        first_error = next(iter(final_preview.get("extraction_errors", {}).values()), "All images failed extraction")
        batch.error_message = _summarize_error_message(first_error)
    batch.progress = len(images)
    batch.listing_count = len(final_preview["listing_report"])
    batch.keyword_count = len(final_preview["keyword_report"])
    await db.commit()

    # Cleanup temp files (best-effort)
    try:
        batch_dir = _TEMP_UPLOAD_DIR / batch_id
        if batch_dir.exists():
            import shutil
            shutil.rmtree(batch_dir, ignore_errors=True)
    except Exception:
        pass

    return final_preview


async def get_batch_preview(batch_id: str) -> dict:
    """Return preview JSON stored on the batch row."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ImportBatch).where(ImportBatch.batch_id == batch_id)
        )
        batch = result.scalar_one_or_none()
        if not batch or not batch.preview_data:
            raise FileNotFoundError(f"Preview not found for batch: {batch_id}")
        return batch.preview_data


# ── Confirm ──────────────────────────────────────────────────────────────────

async def confirm_import(
    batch_id: str,
    listing_report: list[dict],
    keyword_report: list[dict],
    no_vm: str | None,
    db: AsyncSession,
    tenant_id: str,
) -> dict:
    """
    Import user-reviewed data into DB.
    1. Dedup: delete old records with same listing_id + period
    2. Insert new records with import_time + importer + no_vm
    3. Save snapshot JSON
    4. Delete raw images
    5. Update batch status
    """
    result = await db.execute(
        select(ImportBatch).where(ImportBatch.batch_id == batch_id)
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise ValueError(f"Batch {batch_id} not found")
    if batch.status not in ("extracted", "uploaded"):
        raise ValueError(f"Batch {batch_id} status is {batch.status}, expected extracted")

    now = datetime.now(timezone.utc)
    importer = batch_id

    # Deduplication logic removed: Data will always be recorded and distinguished by import_time.
    # User requested to never automatically delete data from the tables.


    # 2. Insert new records — apply no_vm + importer + import_time to all rows
    vm = no_vm.strip() if no_vm else None

    lr_count = 0
    for row in listing_report:
        db.add(ManualListingReport(
            listing_id=row["listing_id"],
            title=row.get("title"),
            no_vm=vm or row.get("no_vm"),
            price=row.get("price"),
            stock=row.get("stock"),
            category=row.get("category"),
            lifetime_orders=row.get("lifetime_orders"),
            lifetime_revenue=row.get("lifetime_revenue"),
            period=row["period"],
            views=row.get("views", 0),
            clicks=row.get("clicks", 0),
            orders=row.get("orders", 0),
            revenue=row.get("revenue", 0),
            spend=row.get("spend", 0),
            roas=row.get("roas", 0),
            import_time=now,
            importer=importer,
            batch_id=batch_id,
            tenant_id=tenant_id,
        ))
        lr_count += 1

    kw_count = 0
    for row in keyword_report:
        db.add(ManualKeywordReport(
            listing_id=row["listing_id"],
            keyword=row["keyword"],
            no_vm=vm or row.get("no_vm"),
            relevant=row.get("relevant"),
            period=row.get("period", ""),
            roas=row.get("roas", 0),
            orders=row.get("orders", 0),
            spend=row.get("spend", 0),
            revenue=row.get("revenue", 0),
            clicks=row.get("clicks", 0),
            click_rate=row.get("click_rate"),
            views=row.get("views", 0),
            import_time=now,
            importer=importer,
            batch_id=batch_id,
            tenant_id=tenant_id,
        ))
        kw_count += 1

    await db.commit()

    # 3. Persist snapshot in DB column
    prev = batch.preview_data or {}
    snapshot = {
        "batch_id": batch_id,
        "confirmed_at": now.isoformat(),
        "no_vm": vm,
        "importer": importer,
        "successful_files": prev.get("successful_files", []),
        "failed_files": prev.get("failed_files", []),
        "listing_report": listing_report,
        "keyword_report": keyword_report,
    }
    batch.snapshot_data = snapshot

    # 4. Delete uploaded images from ImageKit (best-effort, never block confirm)
    from . import imagekit_service
    file_ids = [info.get("fileId") for info in (batch.image_files or []) if info.get("fileId")]
    await imagekit_service.delete_files(file_ids)
    batch.image_files = []
    batch.preview_data = None

    # 5. Update batch
    batch.status = "confirmed"
    batch.listing_count = lr_count
    batch.keyword_count = kw_count
    batch.confirmed_at = now
    await db.commit()

    return {"imported": True, "rows": {"listing": lr_count, "keyword": kw_count}}


# ── Discard ──────────────────────────────────────────────────────────────────

async def discard_batch(batch_id: str, db: AsyncSession) -> None:
    """Cancel a pending batch: delete ImageKit assets + preview, mark discarded."""
    result = await db.execute(
        select(ImportBatch).where(ImportBatch.batch_id == batch_id)
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise ValueError(f"Batch {batch_id} not found")

    # Delete ImageKit files
    from . import imagekit_service
    file_ids = [info.get("fileId") for info in (batch.image_files or []) if info.get("fileId")]
    await imagekit_service.delete_files(file_ids)

    # Cleanup temp files
    try:
        batch_dir = _TEMP_UPLOAD_DIR / batch_id
        if batch_dir.exists():
            import shutil
            shutil.rmtree(batch_dir, ignore_errors=True)
    except Exception:
        pass

    batch.image_files = []
    batch.preview_data = None
    batch.status = "discarded"
    await db.commit()


# ── Rollback ─────────────────────────────────────────────────────────────────

async def rollback_batch(batch_id: str, db: AsyncSession) -> None:
    """Revert a confirmed batch: delete DB rows by import_time, keep snapshot."""
    result = await db.execute(
        select(ImportBatch).where(ImportBatch.batch_id == batch_id)
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise ValueError(f"Batch {batch_id} not found")
    if batch.status != "confirmed":
        raise ValueError(f"Batch {batch_id} status is {batch.status}, expected confirmed")
    if not batch.confirmed_at:
        raise ValueError(f"Batch {batch_id} has no confirmed_at timestamp")

    # Delete rows matching the exact import_time (= batch.confirmed_at)
    await db.execute(
        delete(ManualListingReport).where(ManualListingReport.import_time == batch.confirmed_at)
    )
    await db.execute(
        delete(ManualKeywordReport).where(ManualKeywordReport.import_time == batch.confirmed_at)
    )

    batch.status = "rolled_back"
    await db.commit()


# ── History ──────────────────────────────────────────────────────────────────

async def get_history(db: AsyncSession, limit: int = 20) -> list[dict]:
    """Return recent import batches."""
    result = await db.execute(
        select(ImportBatch)
        .order_by(ImportBatch.created_at.desc())
        .limit(limit)
    )
    batches = result.scalars().all()
    items = []
    for b in batches:
        failed_files: list[str] = []
        successful_files: list[str] = []
        if b.preview_data:
            failed_files = b.preview_data.get("failed_files", []) or []
            successful_files = b.preview_data.get("successful_files", []) or []
        elif b.snapshot_data:
            successful_files = b.snapshot_data.get("successful_files", []) or []
        items.append({
            "batch_id": b.batch_id,
            "status": b.status,
            "file_count": b.file_count or 0,
            "listing_count": b.listing_count or 0,
            "keyword_count": b.keyword_count or 0,
            "created_at": b.created_at,
            "confirmed_at": b.confirmed_at,
            "note": b.note,
            "error_message": b.error_message,
            "failed_files": failed_files,
            "successful_files": successful_files,
        })
    return items


# ── Snapshot ─────────────────────────────────────────────────────────────────

async def get_snapshot(batch_id: str) -> dict | None:
    """Read the snapshot for a confirmed/rolled_back batch from DB."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ImportBatch).where(ImportBatch.batch_id == batch_id)
        )
        batch = result.scalar_one_or_none()
        if not batch:
            return None
        return batch.snapshot_data
