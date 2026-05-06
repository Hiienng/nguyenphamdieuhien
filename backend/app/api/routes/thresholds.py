from fastapi import APIRouter, Depends
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.database import get_db
from ...models.threshold import ThresholdConfig
from ...schemas.threshold import ThresholdConfigOut, ThresholdConfigIn

router = APIRouter(prefix="/thresholds", tags=["thresholds"])

_DEFAULT = ThresholdConfig(id=0, roas_be=2.5, cr_high=3.0, ctr_high=1.5,
                           note=None, created_by="system")


async def _latest(db: AsyncSession) -> ThresholdConfig:
    result = await db.execute(
        select(ThresholdConfig).order_by(desc(ThresholdConfig.id)).limit(1)
    )
    return result.scalar_one_or_none() or _DEFAULT


@router.get("/current", response_model=ThresholdConfigOut)
async def get_current(db: AsyncSession = Depends(get_db)):
    return await _latest(db)


@router.get("/history", response_model=list[ThresholdConfigOut])
async def get_history(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ThresholdConfig).order_by(desc(ThresholdConfig.id)).limit(20)
    )
    return result.scalars().all()


@router.post("", response_model=ThresholdConfigOut, status_code=201)
async def save_threshold(body: ThresholdConfigIn, db: AsyncSession = Depends(get_db)):
    row = ThresholdConfig(**body.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row
