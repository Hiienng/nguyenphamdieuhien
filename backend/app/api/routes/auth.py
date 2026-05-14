import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Response, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from ...core.database import get_db
from ...core.auth_middleware import get_current_active_user
from ...models.user import User
from ...models.credit import CreditAccount
from ...models.subscription import Subscription
from ...services.auth_service import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from ...schemas.auth import RegisterRequest, LoginRequest, TokenResponse, MeResponse, SubscriptionInfo

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
COOKIE_MAX_AGE = 7 * 24 * 3600  # 7 days in seconds


@router.post("/register", response_model=TokenResponse)
async def register(body: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(User).where(User.email == body.email))
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        id=str(uuid.uuid4()),
        email=body.email,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    await db.flush()  # ensure user.id is persisted before FK reference

    credit = CreditAccount(id=str(uuid.uuid4()), user_id=user.id, balance=0)
    db.add(credit)

    await db.commit()

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    response.set_cookie(REFRESH_COOKIE, refresh_token, httponly=True, samesite="lax", max_age=COOKIE_MAX_AGE)
    return TokenResponse(access_token=access_token)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == body.email))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    response.set_cookie(REFRESH_COOKIE, refresh_token, httponly=True, samesite="lax", max_age=COOKIE_MAX_AGE)
    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    refresh_token: Optional[str] = Cookie(default=None, alias=REFRESH_COOKIE),
    db: AsyncSession = Depends(get_db),
):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = await db.get(User, payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or disabled")

    new_access = create_access_token(user.id)
    new_refresh = create_refresh_token(user.id)
    response.set_cookie(REFRESH_COOKIE, new_refresh, httponly=True, samesite="lax", max_age=COOKIE_MAX_AGE)
    return TokenResponse(access_token=new_access)


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(REFRESH_COOKIE)
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
async def me(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    credit = await db.scalar(select(CreditAccount).where(CreditAccount.user_id == user.id))
    balance = credit.balance if credit else 0

    now = datetime.now(timezone.utc)
    sub = await db.scalar(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status == "active",
            Subscription.period_end > now,
        )
    )

    sub_info = None
    if sub:
        sub_info = SubscriptionInfo(
            status=sub.status,
            period_end=sub.period_end.isoformat() if sub.period_end else None,
        )

    return MeResponse(
        id=user.id,
        email=user.email,
        is_admin=user.is_admin,
        subscription=sub_info,
        credit_balance=balance,
    )
