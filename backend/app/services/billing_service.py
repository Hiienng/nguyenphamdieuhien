import uuid
import stripe
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..core.config import get_settings
from ..models.subscription import Subscription
from ..models.credit import CreditAccount, CreditTransaction
from ..models.payment import PaymentRecord


def _stripe():
    stripe.api_key = get_settings().STRIPE_SECRET_KEY
    return stripe


async def create_subscription_checkout(user_id: str, success_url: str, cancel_url: str) -> str:
    s = get_settings()
    _stripe()
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": s.STRIPE_PRICE_SUBSCRIPTION, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"user_id": user_id, "type": "subscription"},
    )
    return session.url


async def create_deposit_checkout(user_id: str, success_url: str, cancel_url: str) -> str:
    s = get_settings()
    _stripe()
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{"price": s.STRIPE_PRICE_CREDIT_DEPOSIT, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"user_id": user_id, "type": "credit_deposit"},
    )
    return session.url


async def handle_webhook_event(payload: bytes, sig_header: str, db: AsyncSession) -> dict:
    s = get_settings()
    _stripe()
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, s.STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        return {"error": "invalid_signature"}

    # Idempotency: skip if already processed
    existing = await db.scalar(select(PaymentRecord).where(PaymentRecord.stripe_event_id == event["id"]))
    if existing:
        return {"status": "already_processed"}

    event_type = event["type"]
    user_id = None
    amount_cents = None
    currency = None

    if event_type == "checkout.session.completed":
        session_obj = event["data"]["object"]
        user_id = session_obj.get("metadata", {}).get("user_id")
        tx_type = session_obj.get("metadata", {}).get("type")
        amount_cents = session_obj.get("amount_total")
        currency = session_obj.get("currency")

        if tx_type == "subscription":
            await _activate_subscription(user_id, session_obj, db)
        elif tx_type == "credit_deposit":
            await _add_credits(user_id, 10, session_obj.get("payment_intent"), db)

    elif event_type == "customer.subscription.deleted":
        sub_obj = event["data"]["object"]
        await _expire_subscription(sub_obj.get("id"), db)

    record = PaymentRecord(
        id=str(uuid.uuid4()),
        user_id=user_id,
        stripe_event_id=event["id"],
        event_type=event_type,
        amount_cents=amount_cents,
        currency=currency,
        payload=dict(event),
    )
    db.add(record)
    await db.commit()
    return {"status": "processed"}


async def _activate_subscription(user_id: str, session_obj: dict, db: AsyncSession):
    from datetime import timedelta
    stripe_sub_id = session_obj.get("subscription")
    now = datetime.now(timezone.utc)

    existing = await db.scalar(
        select(Subscription).where(Subscription.user_id == user_id, Subscription.status == "active")
    )
    if existing:
        existing.stripe_sub_id = stripe_sub_id
        existing.period_start = now
        existing.period_end = now + timedelta(days=31)
        existing.status = "active"
    else:
        sub = Subscription(
            id=str(uuid.uuid4()),
            user_id=user_id,
            plan="monthly",
            status="active",
            period_start=now,
            period_end=now + timedelta(days=31),
            stripe_sub_id=stripe_sub_id,
        )
        db.add(sub)


async def _add_credits(user_id: str, amount: int, stripe_pi_id: str | None, db: AsyncSession):
    acct = await db.scalar(select(CreditAccount).where(CreditAccount.user_id == user_id))
    if acct:
        acct.balance += amount
    else:
        acct = CreditAccount(id=str(uuid.uuid4()), user_id=user_id, balance=amount)
        db.add(acct)

    tx = CreditTransaction(
        id=str(uuid.uuid4()),
        user_id=user_id,
        amount=amount,
        tx_type="deposit",
        description=f"Deposit {amount} credits via Stripe",
        stripe_pi_id=stripe_pi_id,
    )
    db.add(tx)


async def _expire_subscription(stripe_sub_id: str, db: AsyncSession):
    sub = await db.scalar(select(Subscription).where(Subscription.stripe_sub_id == stripe_sub_id))
    if sub:
        sub.status = "expired"


async def deduct_credit(user_id: str, db: AsyncSession, amount: int = 1) -> None:
    acct = await db.scalar(select(CreditAccount).where(CreditAccount.user_id == user_id))
    if not acct or acct.balance < amount:
        from fastapi import HTTPException
        raise HTTPException(status_code=402, detail="Insufficient credits")
    acct.balance -= amount
    tx = CreditTransaction(
        id=str(uuid.uuid4()),
        user_id=user_id,
        amount=-amount,
        tx_type="debit",
        description="Thumbnail evaluation",
    )
    db.add(tx)
    await db.commit()
