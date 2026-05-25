from typing import AsyncGenerator
from contextlib import asynccontextmanager
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from datetime import datetime, timezone

from .database import get_db, AsyncSessionLocal
from ..models.user import User
from ..models.subscription import Subscription
from ..models.credit import CreditAccount
from ..services.auth_service import decode_token
from ..services import trial_service, credit_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    if not payload or payload.get("type") not in ("access", "extension"):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = await db.get(User, payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def get_current_active_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    return user


async def require_subscription(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Check if user has active trial OR paid subscription.

    Allows admins without subscription.
    """
    if user.is_admin:
        return user

    has_sub = await trial_service.has_active_subscription(user.id, db)
    if not has_sub:
        raise HTTPException(status_code=403, detail="Active subscription required")
    return user


async def require_credit(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Legacy single-credit check. Prefer `require_credits(amount)` factory below."""
    bal = await credit_service.get_balance(user.id, db)
    if bal["total"] < 1:
        raise HTTPException(
            status_code=402,
            detail={
                "type": "insufficient_credits",
                "needed": 1,
                "available": bal["total"],
                "message": "Insufficient credits",
            },
        )
    return user


def require_credits(amount: int = 1):
    """FastAPI dependency factory: ensures user has at least `amount` credits.

    Does NOT deduct — the endpoint must call `credit_service.consume_credits`
    (or use the `consume_or_refund` context manager) AFTER doing the work
    so a failed call is naturally not charged.
    """
    async def _dep(
        user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        bal = await credit_service.get_balance(user.id, db)
        if bal["total"] < amount:
            raise HTTPException(
                status_code=402,
                detail={
                    "type": "insufficient_credits",
                    "needed": amount,
                    "available": bal["total"],
                    "message": "Insufficient credits",
                },
            )
        return user

    return _dep


@asynccontextmanager
async def consume_or_refund(user_id: str, amount: int, feature: str, db: AsyncSession):
    """Deduct `amount` credits, run the protected block, refund on exception.

    Usage:
        async with consume_or_refund(user.id, 1, "thumbnail-eval", db):
            result = await heavy_work()
        return result
    """
    ok = await credit_service.consume_credits(user_id, amount, feature, db)
    if not ok:
        raise HTTPException(
            status_code=402,
            detail={
                "type": "insufficient_credits",
                "needed": amount,
                "message": "Insufficient credits",
            },
        )
    try:
        yield
    except Exception:
        # Refund on any downstream failure so user is not charged for failed work.
        try:
            await credit_service.refund_credits(user_id, amount, feature, db, bucket="auto")
        except Exception:
            pass
        raise


def get_tenant_id(user: User = Depends(get_current_active_user)) -> str:
    return user.id


async def get_tenant_db_for_user(
    user: User = Depends(require_subscription),
) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: session with RLS app.tenant_id set to current user."""
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(
                text("SELECT set_config('app.tenant_id', :tid, true)"),
                {"tid": user.id},
            )
            yield session
        finally:
            await session.close()


async def require_admin(user: User = Depends(get_current_active_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_active_subscription(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Check if user has active subscription (trial or paid).

    If no active subscription, raise 403 with trial_expired error type.
    """
    has_subscription = await trial_service.has_active_subscription(user.id, db)
    if not has_subscription:
        raise HTTPException(
            status_code=403,
            detail="Trial expired. Please upgrade to continue.",
            headers={"X-Error-Type": "trial_expired"}
        )
    return user
