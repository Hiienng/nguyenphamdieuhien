"""
billing_service.py — Polar.sh checkout + webhook orchestration.

This module owns:
- create_subscription_checkout / create_topup_checkout       (called by routes)
- handle_webhook_event                                       (Polar webhook entrypoint)
- handle_subscription_renewal                                (refill subscription credits)

Persists idempotency in payment_records.stripe_event_id (column kept for back-compat;
now stores Polar event IDs).
"""
from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..core.config import get_settings
from ..models.user import User
from ..models.subscription import Subscription
from ..models.credit import CreditAccount
from ..models.payment import PaymentRecord
from . import payment_service, credit_service

logger = logging.getLogger(__name__)


# Map of public catalog id → Polar product id (resolved at call time)
def _product_id_for(plan_or_pack: str) -> str:
    s = get_settings()
    return {
        "basic_monthly": s.POLAR_PRODUCT_BASIC_MONTHLY,
        "topup_5": s.POLAR_PRODUCT_TOPUP_5,
        "topup_10": s.POLAR_PRODUCT_TOPUP_10,
    }.get(plan_or_pack, "")


# ---------------------------------------------------------------------------
# Checkout creators (called by routes/billing.py)
# ---------------------------------------------------------------------------
async def create_subscription_checkout(user: User, plan: str = "basic_monthly") -> str:
    product_id = _product_id_for(plan)
    return await payment_service.create_checkout(product_id, user, type_metadata="subscription")


async def create_topup_checkout(user: User, pack: str) -> str:
    if pack not in ("topup_5", "topup_10"):
        raise ValueError(f"invalid topup pack: {pack}")
    product_id = _product_id_for(pack)
    return await payment_service.create_checkout(product_id, user, type_metadata=pack)


# ---------------------------------------------------------------------------
# Webhook dispatch
# ---------------------------------------------------------------------------
async def handle_webhook_event(payload: bytes, signature: str, db: AsyncSession) -> dict:
    s = get_settings()
    if not payment_service.verify_webhook_signature(payload, signature, s.POLAR_WEBHOOK_SECRET):
        return {"error": "invalid_signature"}

    event = payment_service.parse_event(payload)
    event_id = event.get("id") or str(uuid.uuid4())
    event_type = event.get("type") or "unknown"

    # Idempotency
    existing = await db.scalar(
        select(PaymentRecord).where(PaymentRecord.stripe_event_id == event_id)
    )
    if existing:
        return {"status": "already_processed"}

    data = event.get("data") or {}
    metadata = data.get("metadata") or {}
    user_id = metadata.get("user_id")
    type_meta = metadata.get("type")
    amount_cents = data.get("amount") or data.get("amount_total")
    currency = data.get("currency")

    try:
        if event_type in ("checkout.updated", "checkout.session.completed"):
            status = data.get("status")
            if status in ("succeeded", "completed", "complete"):
                await _handle_successful_checkout(user_id, type_meta, data, db)

        elif event_type == "order.created":
            # One-time purchase confirmation (top-up)
            if type_meta in ("topup_5", "topup_10") and user_id:
                await _grant_topup(user_id, type_meta, data.get("id"), db)

        elif event_type == "subscription.created":
            if user_id:
                await _activate_or_update_subscription(user_id, "basic_monthly", data, db)
                await handle_subscription_renewal(user_id, "basic_monthly", data, db)

        elif event_type == "subscription.updated":
            # Renewal → refill credits for the new period
            if user_id:
                await handle_subscription_renewal(user_id, "basic_monthly", data, db)

        elif event_type in ("subscription.canceled", "subscription.cancelled"):
            sub_id = data.get("id")
            if sub_id:
                await _mark_subscription_cancelled(sub_id, db)

    except Exception as e:
        logger.exception("Failed handling Polar event %s: %s", event_type, e)
        # Still record the event so we don't reprocess infinitely
        record = PaymentRecord(
            id=str(uuid.uuid4()),
            user_id=user_id,
            stripe_event_id=event_id,
            event_type=f"{event_type}__error",
            amount_cents=amount_cents,
            currency=currency,
            payload=event.get("raw"),
        )
        db.add(record)
        await db.commit()
        return {"error": str(e)}

    record = PaymentRecord(
        id=str(uuid.uuid4()),
        user_id=user_id,
        stripe_event_id=event_id,
        event_type=event_type,
        amount_cents=amount_cents,
        currency=currency,
        payload=event.get("raw"),
    )
    db.add(record)
    await db.commit()
    return {"status": "processed"}


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------
async def _handle_successful_checkout(
    user_id: Optional[str], type_meta: Optional[str], data: dict, db: AsyncSession
) -> None:
    if not user_id or not type_meta:
        return
    if type_meta == "subscription":
        await _activate_or_update_subscription(user_id, "basic_monthly", data, db)
        await handle_subscription_renewal(user_id, "basic_monthly", data, db)
    elif type_meta in ("topup_5", "topup_10"):
        await _grant_topup(user_id, type_meta, data.get("id"), db)


async def _grant_topup(user_id: str, pack: str, polar_order_id: Optional[str], db: AsyncSession) -> None:
    amount = credit_service.TOPUP_PACK_CREDITS.get(pack, 0)
    if amount <= 0:
        return
    await credit_service.grant_credits(
        user_id=user_id,
        amount=amount,
        bucket="topup",
        reason=f"{pack} purchase (Polar order {polar_order_id})",
        db=db,
        tx_type=pack,
        stripe_pi_id=polar_order_id,
    )


async def _activate_or_update_subscription(
    user_id: str, plan: str, data: dict, db: AsyncSession
) -> None:
    polar_sub_id = data.get("id") or data.get("subscription_id")
    now = datetime.now(timezone.utc)
    period_end = _parse_period_end(data, default_days=31)

    existing = await db.scalar(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status.in_(["active", "trial", "cancelled"]),
        )
    )
    if existing:
        existing.plan = plan
        existing.status = "active"
        existing.period_start = now
        existing.period_end = period_end
        existing.stripe_sub_id = polar_sub_id
    else:
        sub = Subscription(
            id=str(uuid.uuid4()),
            user_id=user_id,
            plan=plan,
            status="active",
            period_start=now,
            period_end=period_end,
            stripe_sub_id=polar_sub_id,
        )
        db.add(sub)


async def _mark_subscription_cancelled(polar_sub_id: str, db: AsyncSession) -> None:
    """Mark cancelled but KEEP period_end so user has access until then."""
    sub = await db.scalar(
        select(Subscription).where(Subscription.stripe_sub_id == polar_sub_id)
    )
    if sub:
        sub.status = "cancelled"


async def handle_subscription_renewal(
    user_id: str, plan: str, data: dict, db: AsyncSession
) -> None:
    """Refill subscription credits at the start of a new billing cycle.
    Unused credits from the previous cycle are LOST (reset to plan allowance).
    """
    period_end = _parse_period_end(data, default_days=31)
    await credit_service.refill_subscription_credits(
        user_id=user_id,
        plan=plan,
        db=db,
        reset_at=period_end,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _parse_period_end(data: dict, default_days: int = 31) -> datetime:
    raw = (
        data.get("current_period_end")
        or data.get("period_end")
        or data.get("ends_at")
    )
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            pass
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(raw, tz=timezone.utc)
        except Exception:
            pass
    return datetime.now(timezone.utc) + timedelta(days=default_days)


# ---------------------------------------------------------------------------
# Legacy shim — keep deduct_credit importable but route it through credit_service
# ---------------------------------------------------------------------------
async def deduct_credit(user_id: str, db: AsyncSession, amount: int = 1) -> None:
    """DEPRECATED — use credit_service.consume_credits + consume_or_refund instead."""
    ok = await credit_service.consume_credits(user_id, amount, "legacy", db)
    if not ok:
        from fastapi import HTTPException
        raise HTTPException(status_code=402, detail="Insufficient credits")
