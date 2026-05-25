import traceback
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.database import get_db, MarketSessionLocal
from ...services import references_service, onboarding_service

router = APIRouter(prefix="/references", tags=["references"])


@router.post("/refresh")
async def refresh(
    top_n: int = Query(3, ge=1, le=10),
    listing_id: str | None = Query(None, description="Nếu truyền, chỉ refresh 1 listing. Bỏ trống = toàn bộ."),
    db: AsyncSession = Depends(get_db),
):
    try:
        async with MarketSessionLocal() as market_db:
            result = await references_service.refresh_references(db, market_db, top_n=top_n, listing_id=listing_id)
        return {"status": "ok", **result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e), "trace": traceback.format_exc()})


@router.get("")
async def list_all(db: AsyncSession = Depends(get_db)):
    try:
        return await references_service.get_references(db)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e), "trace": traceback.format_exc()})


# IMPORTANT: Static paths MUST be declared BEFORE dynamic /{listing_id} route,
# otherwise FastAPI matches "product-categories" as a listing_id and returns empty list.
@router.get("/product-categories", tags=["references"])
async def get_product_categories():
    """
    Get list of valid product categories for onboarding.
    Public endpoint, no auth required.
    Response: { categories: [{ id, name, label }, ...] }
    """
    try:
        categories = await onboarding_service.get_product_categories_formatted()
        return {"categories": categories}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e), "trace": traceback.format_exc()})


@router.get("/{listing_id}")
async def get_by_listing(listing_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await references_service.get_references(db, listing_id=listing_id)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e), "trace": traceback.format_exc()})
