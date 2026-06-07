"""
Optimization action log — Phase 1.

Lets the user record what they optimized on a listing/keyword (turned off,
changed title/tag/price/image, …) and list that history per listing, so they can
review whether an action helped when re-checking metrics after ~7 days.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.auth_middleware import get_current_active_user, get_tenant_db_for_user
from ...models.user import User
from ...models.optimization_log import OptimizationLog

router = APIRouter(prefix="/optimization-log", tags=["optimization-log"])

ALLOWED_ACTIONS = {
    "listing_off", "listing_on",
    "keyword_off", "keyword_on",
    "edit_title", "edit_tags", "edit_price", "edit_image", "edit_other",
}


class LogCreate(BaseModel):
    listing_id: str
    keyword: str | None = None
    action: str
    note: str | None = None


@router.get("")
async def list_logs(
    listing_id: str | None = None,
    limit: int = 200,
    db: AsyncSession = Depends(get_tenant_db_for_user),
    user: User = Depends(get_current_active_user),
):
    q = select(OptimizationLog).where(OptimizationLog.tenant_id == user.id)
    if listing_id:
        q = q.where(OptimizationLog.listing_id == listing_id)
    q = q.order_by(OptimizationLog.created_at.desc()).limit(min(limit, 500))
    rows = (await db.execute(q)).scalars().all()
    return [
        {
            "id": r.id,
            "listing_id": r.listing_id,
            "keyword": r.keyword,
            "action": r.action,
            "note": r.note,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.post("")
async def create_log(
    body: LogCreate,
    db: AsyncSession = Depends(get_tenant_db_for_user),
    user: User = Depends(get_current_active_user),
):
    if body.action not in ALLOWED_ACTIONS:
        raise HTTPException(400, f"Hành động không hợp lệ: {body.action}")
    if not body.listing_id.strip():
        raise HTTPException(400, "Thiếu listing_id")
    row = OptimizationLog(
        tenant_id=user.id,
        listing_id=body.listing_id.strip(),
        keyword=(body.keyword or None),
        action=body.action,
        note=(body.note or None),
    )
    db.add(row)
    await db.commit()
    return {"ok": True, "id": row.id}


@router.delete("/{log_id}")
async def delete_log(
    log_id: int,
    db: AsyncSession = Depends(get_tenant_db_for_user),
    user: User = Depends(get_current_active_user),
):
    row = await db.get(OptimizationLog, log_id)
    if not row or row.tenant_id != user.id:
        raise HTTPException(404, "Not found")
    await db.delete(row)
    await db.commit()
    return {"ok": True}
