"""
trial_service.py — Trial subscription logic

Functions:
- is_trial_active(user_id, db) → bool
- has_active_subscription(user_id, db) → bool
- get_trial_status(user_id, db) → dict
- get_days_remaining(user_id, db) → int
- get_hours_remaining(user_id, db) → int
"""
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.subscription import Subscription


async def get_trial_subscription(user_id: str, db: AsyncSession) -> Subscription | None:
    """Fetch active trial subscription for user."""
    now = datetime.now(timezone.utc)
    sub = await db.scalar(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status == "trial",
            Subscription.period_end > now,
        )
    )
    return sub


async def is_trial_active(user_id: str, db: AsyncSession) -> bool:
    """Check if trial is active (status=trial and period_end > now)."""
    sub = await get_trial_subscription(user_id, db)
    return sub is not None


async def has_active_subscription(user_id: str, db: AsyncSession) -> bool:
    """Check if user has active trial OR paid subscription."""
    now = datetime.now(timezone.utc)

    # Check for active trial
    trial = await db.scalar(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status == "trial",
            Subscription.period_end > now,
        )
    )
    if trial:
        return True

    # Check for active paid subscription
    paid = await db.scalar(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status == "active",
            Subscription.period_end > now,
        )
    )
    return paid is not None


async def get_trial_status(user_id: str, db: AsyncSession) -> dict:
    """
    Get comprehensive trial status including:
    - trial_active: bool
    - days_remaining: int (0 if expired)
    - hours_remaining: int (0 if expired)
    - trial_ends_at: ISO datetime string or None
    - can_access_features: bool (trial active OR paid subscription active)
    """
    sub = await get_trial_subscription(user_id, db)
    now = datetime.now(timezone.utc)

    if sub:
        delta = sub.period_end - now
        days_remaining = max(0, delta.days)
        hours_remaining = max(0, delta.seconds // 3600)

        return {
            "trial_active": True,
            "days_remaining": days_remaining,
            "hours_remaining": hours_remaining,
            "trial_ends_at": sub.period_end.isoformat() if sub.period_end else None,
            "can_access_features": True,
        }

    # Check for paid subscription
    paid = await db.scalar(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status == "active",
            Subscription.period_end > now,
        )
    )

    if paid:
        return {
            "trial_active": False,
            "days_remaining": 0,
            "hours_remaining": 0,
            "trial_ends_at": None,
            "can_access_features": True,
        }

    # No active subscription
    return {
        "trial_active": False,
        "days_remaining": 0,
        "hours_remaining": 0,
        "trial_ends_at": None,
        "can_access_features": False,
    }


async def get_days_remaining(user_id: str, db: AsyncSession) -> int:
    """Get days remaining in trial (0 if trial not active or expired)."""
    sub = await get_trial_subscription(user_id, db)
    if not sub:
        return 0
    now = datetime.now(timezone.utc)
    delta = sub.period_end - now
    return max(0, delta.days)


async def get_hours_remaining(user_id: str, db: AsyncSession) -> int:
    """Get hours remaining in trial (0 if trial not active or expired)."""
    sub = await get_trial_subscription(user_id, db)
    if not sub:
        return 0
    now = datetime.now(timezone.utc)
    delta = sub.period_end - now
    return max(0, delta.seconds // 3600)
