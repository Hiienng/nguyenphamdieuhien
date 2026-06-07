from typing import AsyncGenerator
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from .database import AsyncSessionLocal
from .config import get_settings
from ..models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

# Single-user app: all data is keyed to this fixed tenant id. Login is a shared
# secret (SECRET_KEY) — no email/password accounts.
SINGLE_USER_ID = "b7b81ef3-8a1a-42ca-8a56-efb40358ff91"
SINGLE_USER_EMAIL = "owner@local"


def _single_user() -> User:
    """Return the in-memory owner identity (not persisted; no DB row needed)."""
    return User(
        id=SINGLE_USER_ID,
        email=SINGLE_USER_EMAIL,
        password_hash="",
        is_active=True,
        is_admin=True,
    )


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    secret = get_settings().SECRET_KEY
    if not token or not secret or token != secret:
        raise HTTPException(status_code=401, detail="Invalid or missing access token")
    return _single_user()


async def get_current_active_user(user: User = Depends(get_current_user)) -> User:
    return user


def get_tenant_id(user: User = Depends(get_current_active_user)) -> str:
    return user.id


async def get_tenant_db_for_user(
    user: User = Depends(get_current_active_user),
) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: session with RLS app.tenant_id set to the single user."""
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(
                text("SELECT set_config('app.tenant_id', :tid, true)"),
                {"tid": user.id},
            )
            yield session
        finally:
            await session.close()
