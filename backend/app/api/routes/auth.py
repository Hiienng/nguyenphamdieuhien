import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Response, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from ...core.database import get_db, MarketSessionLocal
from ...core.auth_middleware import get_current_active_user, require_subscription
from ...core.config import get_settings
from ...models.user import User
from ...models.credit import CreditAccount
from ...models.subscription import Subscription
from ...services.auth_service import hash_password, verify_password, create_access_token, create_refresh_token, create_extension_token, decode_token
from ...services import onboarding_service, credit_service
from ...schemas.auth import RegisterRequest, LoginRequest, TokenResponse, MeResponse, SubscriptionInfo, UserInfo, OnboardingSetupRequest, OnboardingSetupResponse

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
COOKIE_MAX_AGE = 7 * 24 * 3600  # 7 days in seconds

def _cookie_kwargs() -> dict:
    secure = get_settings().APP_ENV == "production"
    return {"httponly": True, "samesite": "lax", "max_age": COOKIE_MAX_AGE, "secure": secure}


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(User).where(User.email == body.email))
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        id=str(uuid.uuid4()),
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=None,
    )
    db.add(user)
    await db.flush()  # ensure user.id is persisted before FK reference

    credit = CreditAccount(
        id=str(uuid.uuid4()),
        user_id=user.id,
        balance=0,
        subscription_credits=0,
        topup_credits=0,
    )
    db.add(credit)

    # Create 7-day trial subscription
    now = datetime.now(timezone.utc)
    trial_end = now + timedelta(days=7)
    trial_sub = Subscription(
        id=str(uuid.uuid4()),
        user_id=user.id,
        plan="trial_7_days",
        status="trial",
        period_start=now,
        period_end=trial_end,
        stripe_sub_id=None,
    )
    db.add(trial_sub)
    await db.flush()  # ensure credit_account row exists before grant

    # Grant 3 trial credits in the subscription bucket — expire with the trial.
    await credit_service.grant_credits(
        user_id=user.id,
        amount=3,
        bucket="subscription",
        reason="trial_grant: signup +3 credits (expires with 7-day trial)",
        db=db,
        tx_type="trial_grant",
        reset_at=trial_end,
    )

    await db.commit()

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    response.set_cookie(REFRESH_COOKIE, refresh_token, **_cookie_kwargs())

    return TokenResponse(
        access_token=access_token,
        user=UserInfo(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            created_at=user.created_at.isoformat() if user.created_at else None,
            onboarding_completed=user.onboarding_completed,
            product_categories=user.product_categories,
            seller_location=user.seller_location,
        ),
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == body.email))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    response.set_cookie(REFRESH_COOKIE, refresh_token, **_cookie_kwargs())

    return TokenResponse(
        access_token=access_token,
        user=UserInfo(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            created_at=user.created_at.isoformat() if user.created_at else None,
            onboarding_completed=user.onboarding_completed,
            product_categories=user.product_categories,
            seller_location=user.seller_location,
        ),
    )


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
    response.set_cookie(REFRESH_COOKIE, new_refresh, **_cookie_kwargs())

    return TokenResponse(
        access_token=new_access,
        user=UserInfo(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            created_at=user.created_at.isoformat() if user.created_at else None,
            onboarding_completed=user.onboarding_completed,
            product_categories=user.product_categories,
            seller_location=user.seller_location,
        ),
    )


@router.post("/extension-token")
async def issue_extension_token(user: User = Depends(require_subscription)):
    """Issue a long-lived token for the browser extension. Stateless: revoke by rotating JWT_SECRET_KEY.

    Gated by subscription — the ingest endpoints require subscription anyway, so
    free users would get a useless token. Match the gate to avoid confusion.
    """
    return {"token": create_extension_token(user.id)}


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
        onboarding_completed=user.onboarding_completed,
        product_categories=user.product_categories,
        seller_location=user.seller_location,
    )


@router.post("/onboarding/setup", response_model=OnboardingSetupResponse, status_code=201)
async def setup_onboarding(
    request: OnboardingSetupRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Setup onboarding for a user.
    - First-time setup: always allowed
    - Update (after 90 days): only if >= 90 days since last_onboarding_update
    """

    # Check if user can update
    can_update, reason = onboarding_service.can_update_onboarding(current_user)
    if not can_update:
        raise HTTPException(status_code=400, detail=reason)

    # Fetch valid product categories from market_listing
    try:
        async with MarketSessionLocal() as market_db:
            valid_categories = await onboarding_service.get_valid_product_categories(market_db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch valid categories: {str(e)}")

    # Validate product_categories
    for cat in request.product_categories:
        if cat not in valid_categories:
            raise HTTPException(status_code=400, detail=f"Invalid product category: {cat}")

    # Validate seller_location (ISO country code)
    if not onboarding_service.is_valid_country_code(request.seller_location):
        raise HTTPException(status_code=400, detail=f"Invalid country code: {request.seller_location}")

    # Update user
    current_user.onboarding_completed = True
    current_user.product_categories = request.product_categories
    current_user.seller_location = request.seller_location
    current_user.last_onboarding_update = datetime.now(timezone.utc)

    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)

    return OnboardingSetupResponse(
        success=True,
        user=UserInfo(
            id=current_user.id,
            email=current_user.email,
            full_name=current_user.full_name,
            is_active=current_user.is_active,
            created_at=current_user.created_at.isoformat() if current_user.created_at else None,
            onboarding_completed=current_user.onboarding_completed,
            product_categories=current_user.product_categories,
            seller_location=current_user.seller_location,
        ),
    )
