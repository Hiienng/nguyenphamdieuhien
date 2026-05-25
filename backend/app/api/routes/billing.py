from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from ...core.database import get_db
from ...core.config import get_settings
from ...core.auth_middleware import get_current_active_user
from ...models.user import User
from ...models.subscription import Subscription
from ...models.credit import CreditTransaction
from ...services import billing_service, trial_service, credit_service
from ...schemas.billing import (
    CheckoutResponse,
    SubscriptionStatusResponse,
    TrialStatusResponse,
    CreditsResponse,
    CreditTransaction as CreditTxSchema,
    PlansResponse,
    PlanInfo,
    TopupInfo,
    SubscribeRequest,
    TopupRequest,
)

router = APIRouter(prefix="/billing", tags=["billing"])


# ---------------------------------------------------------------------------
# Plan catalog (B16)
# ---------------------------------------------------------------------------
@router.get("/plans", response_model=PlansResponse)
async def get_plans():
    """Public plan + top-up catalog. No auth required."""
    s = get_settings()
    return PlansResponse(
        plans=[
            PlanInfo(
                id="trial_7_days",
                name="Free Trial",
                price_cents=0,
                is_subscription=False,
                duration_days=7,
                credits=3,
            ),
            PlanInfo(
                id="basic_monthly",
                name="Basic",
                price_cents=900,
                is_subscription=True,
                interval="month",
                credits_per_cycle=5,
                polar_product_id=s.POLAR_PRODUCT_BASIC_MONTHLY or None,
            ),
        ],
        topups=[
            TopupInfo(
                id="topup_5",
                price_cents=500,
                credits=15,
                polar_product_id=s.POLAR_PRODUCT_TOPUP_5 or None,
            ),
            TopupInfo(
                id="topup_10",
                price_cents=1000,
                credits=40,
                polar_product_id=s.POLAR_PRODUCT_TOPUP_10 or None,
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Subscribe (B17) — Polar checkout
# ---------------------------------------------------------------------------
@router.post("/subscribe", response_model=CheckoutResponse)
async def subscribe(
    body: SubscribeRequest | None = None,
    user: User = Depends(get_current_active_user),
):
    plan = (body.plan if body else "basic_monthly") or "basic_monthly"
    try:
        url = await billing_service.create_subscription_checkout(user=user, plan=plan)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Polar checkout failed: {e}")
    return CheckoutResponse(checkout_url=url)


# ---------------------------------------------------------------------------
# Top-up (B17) — Polar checkout
# ---------------------------------------------------------------------------
@router.post("/topup", response_model=CheckoutResponse)
async def topup(
    body: TopupRequest,
    user: User = Depends(get_current_active_user),
):
    try:
        url = await billing_service.create_topup_checkout(user=user, pack=body.pack)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Polar checkout failed: {e}")
    return CheckoutResponse(checkout_url=url)


# ---------------------------------------------------------------------------
# Subscription / Trial status (existing)
# ---------------------------------------------------------------------------
@router.get("/subscription", response_model=SubscriptionStatusResponse)
async def get_subscription(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    sub = await db.scalar(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status.in_(["active", "cancelled"]),
            Subscription.period_end > now,
        )
    )
    if not sub:
        return SubscriptionStatusResponse(status="none")
    return SubscriptionStatusResponse(
        status=sub.status,
        plan=sub.plan,
        period_end=sub.period_end.isoformat() if sub.period_end else None,
        stripe_sub_id=sub.stripe_sub_id,
    )


@router.get("/trial-status", response_model=TrialStatusResponse)
async def get_trial_status(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    status = await trial_service.get_trial_status(user.id, db)
    return TrialStatusResponse(**status)


@router.post("/cancel")
async def cancel_subscription(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark subscription cancelled. Access + subscription_credits persist until period_end."""
    now = datetime.now(timezone.utc)
    sub = await db.scalar(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status == "active",
            Subscription.period_end > now,
        )
    )
    if not sub:
        raise HTTPException(status_code=404, detail="No active subscription")

    sub.status = "cancelled"
    await db.commit()
    # NOTE: actual cancel-at-period-end with Polar must be done via Polar dashboard
    # or future Polar API integration. We just flip our local status.
    return {"ok": True, "message": "Subscription will cancel at period end"}


# ---------------------------------------------------------------------------
# Credit balance + history
# ---------------------------------------------------------------------------
@router.get("/credits", response_model=CreditsResponse)
async def get_credits(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    bal = await credit_service.get_balance(user.id, db)

    result = await db.execute(
        select(CreditTransaction)
        .where(CreditTransaction.user_id == user.id)
        .order_by(CreditTransaction.created_at.desc())
        .limit(20)
    )
    txs = result.scalars().all()

    return CreditsResponse(
        subscription=bal["subscription"],
        topup=bal["topup"],
        total=bal["total"],
        reset_at=bal["reset_at"],
        balance=bal["total"],  # legacy compat
        transactions=[
            CreditTxSchema(
                amount=t.amount,
                tx_type=t.tx_type,
                description=t.description,
                bucket=t.bucket,
                created_at=t.created_at.isoformat(),
            )
            for t in txs
        ],
    )


# ---------------------------------------------------------------------------
# Polar webhook (B18) — no auth, signature-verified
# ---------------------------------------------------------------------------
@router.post("/webhook")
async def polar_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    # Polar uses standard webhooks; the canonical header is "webhook-signature"
    signature = (
        request.headers.get("webhook-signature")
        or request.headers.get("polar-signature")
        or ""
    )
    result = await billing_service.handle_webhook_event(payload, signature, db)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return {"status": result.get("status", "ok")}


# ---------------------------------------------------------------------------
# Deprecated: /deposit (legacy Stripe path) — kept as 410 to surface migration
# ---------------------------------------------------------------------------
@router.post("/deposit")
async def deposit_deprecated():
    raise HTTPException(
        status_code=410,
        detail="Deprecated: use POST /api/v1/billing/topup with pack='topup_5' or 'topup_10'.",
    )
