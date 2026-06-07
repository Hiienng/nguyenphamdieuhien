"""
Internal Ads Data Pipeline — API routes.

Prefix: /api/v1/internal

Only the browser-extension ingest endpoints remain. The screenshot/image-OCR
import workflow (upload → extract → preview → confirm → history) was removed.
"""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from ...core.auth_middleware import get_current_active_user, get_tenant_db_for_user
from ...models.user import User
from ...schemas.internal import (
    IngestListingRequest,
    IngestKeywordRequest,
    IngestResponse,
)

router = APIRouter(prefix="/internal", tags=["internal"])


# ── POST /ingest/listing — extension pushes listing_report rows ──────────────

@router.post("/ingest/listing", response_model=IngestResponse)
async def ingest_listing(
    req: IngestListingRequest,
    db: AsyncSession = Depends(get_tenant_db_for_user),
    user: User = Depends(get_current_active_user),
):
    """Endpoint for browser extension to push listing_report rows.
    tenant_id is injected from the auth token — extension never touches DB directly.
    """
    from ...models.listing_report import ListingReport

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
            period=row.period,
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
    return IngestResponse(inserted=count)


# ── POST /ingest/keyword — extension pushes keyword_report rows ──────────────

@router.post("/ingest/keyword", response_model=IngestResponse)
async def ingest_keyword(
    req: IngestKeywordRequest,
    db: AsyncSession = Depends(get_tenant_db_for_user),
    user: User = Depends(get_current_active_user),
):
    """Endpoint for browser extension to push keyword_report rows."""
    from ...models.keyword_report import KeywordReport

    now = datetime.now(timezone.utc)
    importer = req.importer or "extension"
    count = 0
    for row in req.rows:
        db.add(KeywordReport(
            listing_id=row.listing_id,
            keyword=row.keyword,
            no_vm=row.no_vm,
            relevant=row.relevant,
            period=row.period,
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
