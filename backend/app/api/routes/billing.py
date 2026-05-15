from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from ...core.database import get_db
from ...core.auth_middleware import get_current_active_user
from ...models.user import User
from ...models.subscription import Subscription
from ...models.credit import CreditAccount, CreditTransaction
from ...services import billing_service
from ...schemas.billing import CheckoutResponse, SubscriptionStatusResponse, CreditsResponse, CreditTransaction as CreditTxSchema

router = APIRouter(prefix="/billing", tags=["billing"])

_BASE_URL = "https://nguyenphamdieuhien.online"


@router.post("/subscribe", response_model=CheckoutResponse)
async def subscribe(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    url = await billing_service.create_subscription_checkout(
        user_id=user.id,
        success_url=f"{_BASE_URL}/etseemate.html?payment=success",
        cancel_url=f"{_BASE_URL}/etseemate.html?payment=cancel",
    )
    return CheckoutResponse(checkout_url=url)


@router.get("/subscription", response_model=SubscriptionStatusResponse)
async def get_subscription(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    sub = await db.scalar(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status == "active",
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


@router.post("/cancel")
async def cancel_subscription(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
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

    import stripe as stripe_lib
    from ...core.config import get_settings
    stripe_lib.api_key = get_settings().STRIPE_SECRET_KEY

    if sub.stripe_sub_id:
        stripe_lib.Subscription.modify(sub.stripe_sub_id, cancel_at_period_end=True)

    sub.status = "cancelled"
    await db.commit()
    return {"ok": True, "message": "Subscription will cancel at period end"}


@router.post("/deposit", response_model=CheckoutResponse)
async def deposit(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    url = await billing_service.create_deposit_checkout(
        user_id=user.id,
        success_url=f"{_BASE_URL}/etseemate.html?payment=success&type=credits",
        cancel_url=f"{_BASE_URL}/etseemate.html?payment=cancel",
    )
    return CheckoutResponse(checkout_url=url)


@router.get("/credits", response_model=CreditsResponse)
async def get_credits(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    acct = await db.scalar(select(CreditAccount).where(CreditAccount.user_id == user.id))
    balance = acct.balance if acct else 0

    result = await db.execute(
        select(CreditTransaction)
        .where(CreditTransaction.user_id == user.id)
        .order_by(CreditTransaction.created_at.desc())
        .limit(10)
    )
    txs = result.scalars().all()

    return CreditsResponse(
        balance=balance,
        transactions=[
            CreditTxSchema(
                amount=t.amount,
                tx_type=t.tx_type,
                description=t.description,
                created_at=t.created_at.isoformat(),
            )
            for t in txs
        ],
    )


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    result = await billing_service.handle_webhook_event(payload, sig_header, db)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return {"status": "ok"}
