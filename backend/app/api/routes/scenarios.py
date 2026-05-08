from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.database import get_db
from ...models.scenario import ScenarioRule
from ...schemas.scenario import ScenarioRuleOut, ScenarioRuleIn

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("/rules", response_model=list[ScenarioRuleOut])
async def list_rules(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ScenarioRule).order_by(ScenarioRule.id))
    return result.scalars().all()


@router.put("/rules/{rule_id}", response_model=ScenarioRuleOut)
async def update_rule(rule_id: int, body: ScenarioRuleIn, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ScenarioRule).where(ScenarioRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    for field, value in body.model_dump().items():
        setattr(rule, field, value)
    rule.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.post("/rules", response_model=ScenarioRuleOut, status_code=201)
async def create_rule(body: ScenarioRuleIn, db: AsyncSession = Depends(get_db)):
    rule = ScenarioRule(**body.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(rule_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ScenarioRule).where(ScenarioRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.delete(rule)
    await db.commit()
