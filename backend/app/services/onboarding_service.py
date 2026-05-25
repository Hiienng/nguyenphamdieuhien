"""
Onboarding service — Handle product categories validation and onboarding flow.
"""

import logging
from datetime import datetime, timezone
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession
import pycountry

from ..core.database import MarketSessionLocal
from . import etsy_categories

logger = logging.getLogger(__name__)


async def _fetch_crawled_product_types(market_db: AsyncSession) -> list[str]:
    """Fetch DISTINCT product_type values currently present in market_listing."""
    try:
        result = await market_db.execute(text("""
            SELECT DISTINCT product_type
            FROM market_listing
            WHERE product_type IS NOT NULL AND product_type != ''
        """))
        return [row[0] for row in result.fetchall() if row[0]]
    except Exception as e:
        logger.warning("Failed to fetch crawled product types: %s", e)
        return []


async def get_valid_product_categories(market_db: AsyncSession) -> list[str]:
    """
    Return the union of canonical Etsy catalog ids + any crawled product_types
    not yet in the catalog. Used for validation in /onboarding/setup.
    """
    crawled = await _fetch_crawled_product_types(market_db)
    catalog_ids = etsy_categories.get_catalog_ids()
    return sorted(catalog_ids | {t.lower() for t in crawled})


async def get_product_categories_formatted() -> list[dict]:
    """
    Return the catalog merged with crawled data — each entry has:
    { id, name, label, group, has_data }
    """
    try:
        async with MarketSessionLocal() as market_db:
            crawled = await _fetch_crawled_product_types(market_db)
    except Exception as e:
        logger.warning("Could not query market_listing, returning catalog only: %s", e)
        crawled = []

    formatted = etsy_categories.merge_with_crawled(crawled)
    logger.info("Returning %d product categories (%d crawled)",
                len(formatted), sum(1 for c in formatted if c["has_data"]))
    return formatted


def is_valid_country_code(code: str) -> bool:
    """
    Validate ISO 3166-1 alpha-2 country code using pycountry.
    """
    if not code or not isinstance(code, str):
        return False

    try:
        country = pycountry.countries.get(alpha_2=code.upper())
        return country is not None
    except Exception:
        return False


def can_update_onboarding(user) -> tuple[bool, str]:
    """
    Check if user can update their onboarding settings.
    Returns (can_update: bool, reason: str)

    Rules:
    - If onboarding_completed=false → first-time setup, always allowed
    - If onboarding_completed=true → check if 90+ days since last_onboarding_update
      - If < 90 days → cannot update
      - If >= 90 days → can update
    """
    if not user.onboarding_completed:
        return True, "First-time onboarding setup"

    if user.last_onboarding_update is None:
        # Should not happen, but handle gracefully
        return False, "Onboarding locked. Can update after 90 days."

    now = datetime.now(timezone.utc)
    # Make last_onboarding_update timezone-aware if it isn't
    last_update = user.last_onboarding_update
    if last_update.tzinfo is None:
        last_update = last_update.replace(tzinfo=timezone.utc)

    days_since_update = (now - last_update).days

    if days_since_update >= 90:
        return True, f"Can update (last update: {days_since_update} days ago)"
    else:
        return False, "Onboarding locked. Can update after 90 days."
