"""
credit_service.py — Two-bucket credit system (subscription + topup).

Buckets:
- subscription_credits: refilled with the user's plan (e.g. Basic = 5/mo).
  Unused credits are RESET (not carried) at each cycle.
- topup_credits:        one-time purchases. Never expire.

Deduction order: subscription bucket first (use-it-or-lose-it), then topup.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.credit import CreditAccount, CreditTransaction


# ---------------------------------------------------------------------------
# Plan catalog (single source of truth for credit allowances)
# ---------------------------------------------------------------------------
PLAN_CREDIT_ALLOWANCE = {
    "trial_7_days": 3,
    "basic_monthly": 5,
}

TOPUP_PACK_CREDITS = {
    "topup_5": 15,
    "topup_10": 40,
}


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------
async def get_balance(user_id: str, db: AsyncSession) -> dict:
    """Returns {subscription, topup, total, reset_at}."""
    acct = await db.scalar(select(CreditAccount).where(CreditAccount.user_id == user_id))
    if not acct:
        return {"subscription": 0, "topup": 0, "total": 0, "reset_at": None}
    sub = int(acct.subscription_credits or 0)
    topup = int(acct.topup_credits or 0)
    return {
        "subscription": sub,
        "topup": topup,
        "total": sub + topup,
        "reset_at": acct.subscription_credits_reset_at.isoformat() if acct.subscription_credits_reset_at else None,
    }


# ---------------------------------------------------------------------------
# Grant (positive amount → add to a bucket)
# ---------------------------------------------------------------------------
async def grant_credits(
    user_id: str,
    amount: int,
    bucket: str,
    reason: str,
    db: AsyncSession,
    tx_type: str = "grant",
    stripe_pi_id: Optional[str] = None,
    reset_at: Optional[datetime] = None,
) -> None:
    """Add `amount` credits to `bucket` ("subscription" or "topup") and log a transaction.

    Commits within the caller's session — does NOT call db.commit() so it can be
    composed inside a larger transaction.
    """
    if amount <= 0:
        return
    if bucket not in ("subscription", "topup"):
        raise ValueError(f"invalid bucket: {bucket}")

    acct = await db.scalar(select(CreditAccount).where(CreditAccount.user_id == user_id))
    if not acct:
        acct = CreditAccount(
            id=str(uuid.uuid4()),
            user_id=user_id,
            balance=0,
            subscription_credits=0,
            topup_credits=0,
        )
        db.add(acct)
        await db.flush()

    if bucket == "subscription":
        acct.subscription_credits = (acct.subscription_credits or 0) + amount
        if reset_at is not None:
            acct.subscription_credits_reset_at = reset_at
    else:
        acct.topup_credits = (acct.topup_credits or 0) + amount

    acct.balance = (acct.subscription_credits or 0) + (acct.topup_credits or 0)

    tx = CreditTransaction(
        id=str(uuid.uuid4()),
        user_id=user_id,
        amount=amount,
        tx_type=tx_type,
        bucket=bucket,
        description=reason,
        stripe_pi_id=stripe_pi_id,
    )
    db.add(tx)


# ---------------------------------------------------------------------------
# Consume (atomic deduct subscription-first, then topup)
# ---------------------------------------------------------------------------
async def consume_credits(
    user_id: str,
    amount: int,
    feature: str,
    db: AsyncSession,
) -> bool:
    """Atomically deduct `amount` credits. Subscription bucket first, then topup.

    Returns True on success, False if insufficient.
    Records a single credit_transactions row with bucket="subscription"|"topup"|"mixed".
    Commits the change to ensure atomicity even if caller forgets.
    """
    if amount <= 0:
        return True

    # Single SQL UPDATE with WHERE guard — atomic
    sql = text(
        """
        UPDATE credit_accounts
        SET subscription_credits = GREATEST(subscription_credits - LEAST(subscription_credits, :amt), 0),
            topup_credits = topup_credits - GREATEST(:amt - LEAST(subscription_credits, :amt), 0),
            balance = (
                GREATEST(subscription_credits - LEAST(subscription_credits, :amt), 0)
                + topup_credits - GREATEST(:amt - LEAST(subscription_credits, :amt), 0)
            ),
            updated_at = NOW()
        WHERE user_id = :uid
          AND (subscription_credits + topup_credits) >= :amt
        RETURNING
            LEAST(:amt, subscription_credits + GREATEST(:amt - LEAST(subscription_credits + 0, :amt), 0)) AS _placeholder,
            subscription_credits AS new_sub,
            topup_credits AS new_topup
        """
    )

    # We need to know how much came from each bucket BEFORE the deduct.
    # Easier: fetch the current row first then do the atomic update guarded by current totals.
    # Use SELECT FOR UPDATE for row lock + compute split.
    select_sql = text(
        "SELECT subscription_credits, topup_credits FROM credit_accounts "
        "WHERE user_id = :uid FOR UPDATE"
    )
    row = (await db.execute(select_sql, {"uid": user_id})).first()
    if not row:
        return False

    cur_sub = int(row[0] or 0)
    cur_topup = int(row[1] or 0)
    if cur_sub + cur_topup < amount:
        return False

    from_sub = min(cur_sub, amount)
    from_topup = amount - from_sub

    new_sub = cur_sub - from_sub
    new_topup = cur_topup - from_topup

    upd = text(
        """
        UPDATE credit_accounts
        SET subscription_credits = :ns,
            topup_credits = :nt,
            balance = :nb,
            updated_at = NOW()
        WHERE user_id = :uid
          AND subscription_credits = :cs
          AND topup_credits = :ct
        """
    )
    result = await db.execute(
        upd,
        {
            "uid": user_id,
            "ns": new_sub,
            "nt": new_topup,
            "nb": new_sub + new_topup,
            "cs": cur_sub,
            "ct": cur_topup,
        },
    )
    if result.rowcount == 0:
        # Concurrent modification — retry once
        return await consume_credits(user_id, amount, feature, db)

    # Record transaction(s)
    if from_sub > 0:
        db.add(CreditTransaction(
            id=str(uuid.uuid4()),
            user_id=user_id,
            amount=-from_sub,
            tx_type="feature_debit",
            bucket="subscription",
            description=feature,
        ))
    if from_topup > 0:
        db.add(CreditTransaction(
            id=str(uuid.uuid4()),
            user_id=user_id,
            amount=-from_topup,
            tx_type="feature_debit",
            bucket="topup",
            description=feature,
        ))

    await db.commit()
    return True


# ---------------------------------------------------------------------------
# Refund (reverse a consume; e.g. when the downstream API call failed)
# ---------------------------------------------------------------------------
async def refund_credits(
    user_id: str,
    amount: int,
    feature: str,
    db: AsyncSession,
    bucket: str = "auto",
) -> None:
    """Refund credits. bucket="auto" → put back into topup (safe default,
    since subscription credits may have expired by retry time).
    """
    if amount <= 0:
        return
    target_bucket = "topup" if bucket == "auto" else bucket
    await grant_credits(
        user_id=user_id,
        amount=amount,
        bucket=target_bucket,
        reason=f"refund: {feature}",
        db=db,
        tx_type="refund",
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Subscription cycle refill
# ---------------------------------------------------------------------------
async def refill_subscription_credits(
    user_id: str,
    plan: str,
    db: AsyncSession,
    reset_at: Optional[datetime] = None,
) -> int:
    """Reset subscription_credits to plan's allowance (does NOT carry over).
    Returns the new subscription_credits value. Records a transaction.
    """
    allowance = PLAN_CREDIT_ALLOWANCE.get(plan, 0)
    acct = await db.scalar(select(CreditAccount).where(CreditAccount.user_id == user_id))
    if not acct:
        acct = CreditAccount(
            id=str(uuid.uuid4()),
            user_id=user_id,
            balance=0,
            subscription_credits=0,
            topup_credits=0,
        )
        db.add(acct)
        await db.flush()

    previous = int(acct.subscription_credits or 0)
    acct.subscription_credits = allowance
    if reset_at is not None:
        acct.subscription_credits_reset_at = reset_at
    acct.balance = (acct.subscription_credits or 0) + (acct.topup_credits or 0)

    # Net delta for the transaction log
    delta = allowance - previous
    db.add(CreditTransaction(
        id=str(uuid.uuid4()),
        user_id=user_id,
        amount=delta,
        tx_type="subscription_refill",
        bucket="subscription",
        description=f"Refill {plan}: previous={previous} → new={allowance} (unused={previous} lost)",
    ))
    await db.commit()
    return allowance
