"""
payment_service.py — Gateway-agnostic payment abstraction (Polar.sh impl).

Public surface (keep stable so future gateway swaps are localized):
- async create_checkout(product_id, user, type_metadata) -> str   # returns checkout URL
- verify_webhook(headers, body) -> dict | None                     # raises on invalid sig
- parse_event(payload) -> dict                                     # normalized event

Uses `polar-sdk` when installed; otherwise falls back to direct HTTPS calls.
"""
from __future__ import annotations

import hmac
import hashlib
import json
import logging
from typing import Any, Optional

import httpx

from ..core.config import get_settings
from ..models.user import User

logger = logging.getLogger(__name__)


def _polar_base_url() -> str:
    s = get_settings()
    if s.POLAR_ENV == "sandbox":
        return "https://sandbox-api.polar.sh"
    return "https://api.polar.sh"


# ---------------------------------------------------------------------------
# Try import polar-sdk; fallback to httpx
# ---------------------------------------------------------------------------
try:
    from polar_sdk import Polar  # type: ignore

    def _polar_client() -> "Polar":
        s = get_settings()
        return Polar(
            access_token=s.POLAR_ACCESS_TOKEN,
            server="sandbox" if s.POLAR_ENV == "sandbox" else "production",
        )

    _HAS_SDK = True
except Exception:  # pragma: no cover
    _HAS_SDK = False
    Polar = None  # type: ignore


# ---------------------------------------------------------------------------
# Checkout creation
# ---------------------------------------------------------------------------
async def create_checkout(
    product_id: str,
    user: User,
    type_metadata: str,
) -> str:
    """Create a Polar checkout session and return the URL the user should be sent to.

    `type_metadata` is echoed back in the webhook so we know what to grant
    (e.g. "subscription", "topup_5", "topup_10").
    """
    s = get_settings()
    if not product_id:
        raise RuntimeError(
            f"Polar product not configured (type={type_metadata}). "
            "Set POLAR_PRODUCT_* env vars."
        )
    if not s.POLAR_ACCESS_TOKEN:
        raise RuntimeError("POLAR_ACCESS_TOKEN not set")

    metadata = {"user_id": user.id, "type": type_metadata}

    # Prefer SDK if available
    if _HAS_SDK:
        try:
            client = _polar_client()
            checkout = client.checkouts.create(  # type: ignore[attr-defined]
                products=[product_id],
                customer_email=user.email,
                success_url=s.POLAR_SUCCESS_URL,
                metadata=metadata,
            )
            url = getattr(checkout, "url", None) or checkout.get("url")  # type: ignore[union-attr]
            if not url:
                raise RuntimeError("Polar SDK returned no checkout URL")
            return url
        except Exception as e:
            logger.warning("Polar SDK checkout failed (%s); falling back to HTTP", e)

    # HTTP fallback
    async with httpx.AsyncClient(timeout=15) as cx:
        r = await cx.post(
            f"{_polar_base_url()}/v1/checkouts/",
            headers={
                "Authorization": f"Bearer {s.POLAR_ACCESS_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "products": [product_id],
                "customer_email": user.email,
                "success_url": s.POLAR_SUCCESS_URL,
                "metadata": metadata,
            },
        )
        r.raise_for_status()
        data = r.json()
        url = data.get("url")
        if not url:
            raise RuntimeError(f"Polar HTTP returned no checkout URL: {data}")
        return url


# ---------------------------------------------------------------------------
# Webhook signature verification
# ---------------------------------------------------------------------------
def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Polar uses standard webhook signing: HMAC-SHA256 hex of the raw body."""
    if not signature or not secret:
        return False
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    # Polar may prefix with "sha256=" or send multiple comma-separated values
    candidates = [signature.strip()]
    if "," in signature:
        candidates = [v.strip() for v in signature.split(",")]
    for cand in candidates:
        cand = cand.split("=", 1)[-1] if "=" in cand else cand
        if hmac.compare_digest(expected, cand):
            return True
    return False


def parse_event(payload: bytes) -> dict:
    """Parse and lightly normalize a Polar webhook payload."""
    data = json.loads(payload.decode("utf-8"))
    return {
        "type": data.get("type") or data.get("event"),
        "id": data.get("id") or (data.get("data", {}) or {}).get("id"),
        "data": data.get("data", {}),
        "raw": data,
    }
