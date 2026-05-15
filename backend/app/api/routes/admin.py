from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ...core.database import get_db
from ...core.auth_middleware import require_admin
from ...models.user import User
from ...models.subscription import Subscription
from ...models.credit import CreditAccount

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/tenants")
async def list_tenants(
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [
        {"id": u.id, "email": u.email, "full_name": u.full_name, "is_active": u.is_active, "created_at": u.created_at.isoformat()}
        for u in users
    ]


@router.get("/tenants/{tenant_id}/stats")
async def tenant_stats(
    tenant_id: str,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    tenant = await db.get(User, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    sub = await db.scalar(
        select(Subscription).where(
            Subscription.user_id == tenant_id,
            Subscription.status == "active",
            Subscription.period_end > now,
        )
    )
    credit = await db.scalar(select(CreditAccount).where(CreditAccount.user_id == tenant_id))

    return {
        "id": tenant.id,
        "email": tenant.email,
        "full_name": tenant.full_name,
        "is_active": tenant.is_active,
        "subscription": {"status": sub.status, "period_end": sub.period_end.isoformat()} if sub else None,
        "credit_balance": credit.balance if credit else 0,
    }
