from typing import AsyncGenerator
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

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
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
    now = datetime.now(timezone.utc)
    sub = await db.scalar(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status == "active",
            Subscription.period_end > now,
        )
    )
    if not sub and not user.is_admin:
        raise HTTPException(status_code=403, detail="Active subscription required")
    return user


async def require_credit(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    acct = await db.scalar(select(CreditAccount).where(CreditAccount.user_id == user.id))
    if not acct or acct.balance < 1:
        raise HTTPException(status_code=402, detail="Insufficient credits")
    return user


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
