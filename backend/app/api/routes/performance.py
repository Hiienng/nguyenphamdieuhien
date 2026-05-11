import traceback
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.database import get_db, MarketSessionLocal
from ...schemas.performance import ListingDashboardItem
from ...services import performance_service, reporting_etl

router = APIRouter(prefix="/performance", tags=["performance"])


@router.get("/listings", response_model=list[ListingDashboardItem])
async def get_listings_dashboard(db: AsyncSession = Depends(get_db)):
    try:
        async with MarketSessionLocal() as market_db:
            return await performance_service.get_dashboard_listings(db, market_db)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e), "trace": traceback.format_exc()})


@router.post("/refresh")
async def refresh_dashboard(force: bool = False, db: AsyncSession = Depends(get_db)):
    """Trigger ETL rebuild of reporting tables from raw ingestion data.

    Behaviour:
        - Computes a signature over raw `import_time`s. If unchanged since last
          refresh and `force` is false, returns `{status: 'cached'}` without
          rebuilding.
        - Otherwise truncates and rebuilds `listings_int_ext`, `listings_int_hist`,
          and `keywords`, then upserts `refresh_state`.
        - If another rebuild is in flight (advisory lock held), returns
          `{status: 'in_progress'}`.
    """
    try:
        return await reporting_etl.refresh_if_stale(db, force=force)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e), "trace": traceback.format_exc()})
