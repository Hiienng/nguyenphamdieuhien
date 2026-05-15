"""
intelligence.py — Routes for Thumbnail Knowledge & Evaluation

Prefix: /api/v1/intelligence  (mounted in main.py)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db, MarketSessionLocal
from ...core.auth_middleware import get_current_active_user, require_credit
from ...models.user import User
from ...schemas.vision_schema import (
    KnowledgeGenerateRequest,
    KnowledgeRecord,
    KnowledgeListResponse,
    ThumbnailEvalResponse,
)
from ...services import vision_service
from ...services.billing_service import deduct_credit

router = APIRouter(tags=["intelligence"])

# ---------------------------------------------------------------------------
# POST /thumbnail-knowledge/generate
# ---------------------------------------------------------------------------

@router.post("/thumbnail-knowledge/generate")
async def generate_thumbnail_knowledge(
    body: KnowledgeGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Query top trending market listings for a product type, extract visual patterns
    via Claude Vision, and upsert results into the thumbnail_knowledge table.
    """
    async with MarketSessionLocal() as market_db:
        result = await vision_service.generate_knowledge(
            product_type=body.product_type,
            top_n=body.top_n,
            internal_db=db,
            market_db=market_db,
        )
    return result


# ---------------------------------------------------------------------------
# GET /thumbnail-knowledge
# ---------------------------------------------------------------------------

@router.get("/thumbnail-knowledge", response_model=KnowledgeListResponse)
async def list_thumbnail_knowledge(
    product_type: str | None = Query(None, description="Filter by product type"),
    db: AsyncSession = Depends(get_db),
):
    """
    Return all thumbnail_knowledge records, optionally filtered by product_type.
    """
    if product_type:
        result = await db.execute(
            text(
                "SELECT id, product_type, target_audience, patterns, sample_urls, sample_count, generated_at "
                "FROM thumbnail_knowledge WHERE product_type = :pt ORDER BY generated_at DESC"
            ),
            {"pt": product_type},
        )
    else:
        result = await db.execute(
            text(
                "SELECT id, product_type, target_audience, patterns, sample_urls, sample_count, generated_at "
                "FROM thumbnail_knowledge ORDER BY generated_at DESC"
            )
        )

    rows = result.mappings().fetchall()
    items = [KnowledgeRecord.model_validate(dict(row)) for row in rows]
    return KnowledgeListResponse(items=items, total=len(items))


# ---------------------------------------------------------------------------
# POST /thumbnail-eval
# ---------------------------------------------------------------------------

@router.post("/thumbnail-eval", response_model=ThumbnailEvalResponse)
async def evaluate_thumbnail(
    image: UploadFile = File(..., description="Thumbnail image to evaluate"),
    product_type: str = Form(..., description="Product type (e.g. 'onesie', 'mug')"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_credit),
):
    """
    Upload a thumbnail image and receive an AI evaluation scored against
    the knowledge base for the given product_type.
    """
    # Validate content type
    allowed_types = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    content_type = image.content_type or "image/jpeg"
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported image type '{content_type}'. Use JPEG, PNG, WEBP, or GIF.",
        )

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=422, detail="Uploaded image is empty.")

    result = await vision_service.evaluate_thumbnail(
        image_bytes=image_bytes,
        image_media_type=content_type,
        product_type=product_type,
        internal_db=db,
    )
    await deduct_credit(user.id, db)
    return result
