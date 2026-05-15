from __future__ import annotations

"""
Gemini Vision extractor for Etsy Ads dashboard screenshots.

Two screenshot types:
  1. Listing performance (summary header + daily table)
  2. Keyword performance (keyword × metrics table)

Gemini auto-classifies the type and returns structured JSON.
"""
import asyncio
import base64
import json
import logging
import re
from datetime import datetime, date
from pathlib import Path
from typing import Awaitable, Callable

import google.generativeai as genai
import httpx

from ..core.config import get_settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds — exponential backoff: 2s, 4s, 8s
VISION_CALL_TIMEOUT = 90

# ── Unified prompt — Gemini classifies automatically ──────────────────────────

EXTRACTION_PROMPT = """You are an AI that reads Etsy Ads dashboard screenshots and extracts structured data.

Look at this screenshot carefully and determine which type it is:

TYPE A — Listing performance page:
Contains a listing's advertising summary (views, clicks, orders, revenue, spend, ROAS) and a daily breakdown table.

If TYPE A, extract:
- listing_id: the Etsy listing ID. Look for it in the URL bar (e.g. "/listings/4438217152"). If URL bar is not visible, look for it anywhere on the page, in titles, or links. It is a long numeric string.
- title: the listing title shown on the page
- no_vm: if visible, the "vm" code (e.g. "vm08"); otherwise null
- price: listing price (number, no $)
- stock: stock/quantity if visible; otherwise null
- category: product category if visible; otherwise null
- lifetime_orders: total orders if shown; otherwise null
- lifetime_revenue: total revenue if shown (number, no $); otherwise null
- period: the date range from the dropdown filter — extract exactly as shown (e.g. "Mar 19 - Apr 18", "Custom (04/11/2026 - 04/18/2026)")
- summary: {views, clicks, orders, revenue, spend, roas} — numbers from the header
- metric_column: which metric the daily table shows (e.g. "views", "spend", "clicks")
- daily_data: array of {date, value} from the daily table. Date format: "DD/M/YY" (e.g. "19/3/26") or "Mon DD" (e.g. "Apr 18"). Value: integer for views/clicks/orders, float for revenue/spend/roas.

Return JSON:
{
  "type": "listing_daily",
  "listing_id": "4438217152",
  "title": "Applique embroidered baby sweater...",
  "no_vm": "vm08",
  "price": 24.27,
  "stock": 991,
  "category": "Sweater",
  "lifetime_orders": 3,
  "lifetime_revenue": 102.97,
  "period": "Mar 19 - Apr 18",
  "summary": {"views": 2474, "clicks": 33, "orders": 3, "revenue": 102.97, "spend": 27.99, "roas": 3.68},
  "metric_column": "views",
  "daily_data": [
    {"date": "19/3/26", "value": 68},
    {"date": "20/3/26", "value": 26}
  ]
}

TYPE B — Keyword performance table:
Contains a table of keywords with columns: keyword, ROAS, orders, spend, revenue, clicks, click rate, views, and a status toggle (on/off).

If TYPE B, extract:
- listing_id: find the numeric listing ID if possible
- no_vm: if visible; otherwise null
- keywords: array of objects with {keyword, relevant, roas, orders, spend, revenue, clicks, click_rate, views}
  - relevant: the on/off toggle state for the keyword — "on" if active, "off" if paused/disabled; null if not visible
  - click_rate: keep as string with % (e.g. "1.1%")
  - spend/revenue: float, no $
  - roas: float

Return JSON:
{
  "type": "keyword_table",
  "listing_id": "4438225302",
  "no_vm": "vm08",
  "keywords": [
    {"keyword": "custom sweatshirts", "relevant": "on", "roas": 0, "orders": 0, "spend": 0.85, "revenue": 0, "clicks": 2, "click_rate": "1.1%", "views": 181}
  ]
}

IMPORTANT:
- Return ONLY valid JSON, no markdown, no text before or after.
- All numbers should be plain numbers (no commas, no $ signs).
- If you cannot determine a value, use null.
- Be precise with listing_id — it must be the exact numeric ID.

NUMERIC UNITS — CRITICAL:
- revenue, spend, price, lifetime_revenue: always formatted as X.XX (exactly 2 decimal places for cents).
  Read the full digit string, then insert a decimal point before the last 2 digits.
  Example: screen shows "$3399" → full digits are "3399" → insert dot before last 2 → 33.99
  Example: screen shows "$34.99" → full digits are "3499" → insert dot before last 2 → 34.99
  Example: screen shows "$10397" → full digits are "10397" → insert dot before last 2 → 103.97
  The result must always have exactly 2 decimal places: 33.99, 34.99, 103.97, 69.69, 601.99
- roas: always formatted as X.XX (2 decimal places).
  Read the full digit string, then insert a decimal point before the last 2 digits.
  Example: screen shows "149" → full digits "149" → insert dot → 1.49
  Example: screen shows "1.87" → full digits "187" → insert dot → 1.87
  The result must always have exactly 2 decimal places: 1.49, 1.87, 3.68
- views, clicks, orders: plain integers, no decimal point.
- daily_data value: match the metric_column type — integer for views/clicks/orders, decimal float (2dp) for revenue/spend/roas.
"""


_MONTH_ABBR = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_date_part(s: str, year_hint: int | None = None) -> date | None:
    """Parse a single date string in any known format to a date object."""
    s = s.strip()
    # YYYY-MM-DD
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    # YYYY/MM/DD
    m = re.fullmatch(r"(\d{4})/(\d{2})/(\d{2})", s)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    # MM/DD/YYYY
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return date(int(m[3]), int(m[1]), int(m[2]))
    # D/M/YY  (e.g. "19/3/26")
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2})", s)
    if m:
        yy = int(m[3])
        return date(2000 + yy, int(m[2]), int(m[1]))
    # "Mar 19" or "Mar 19 2026"
    m = re.fullmatch(r"([A-Za-z]{3})\s+(\d{1,2})(?:\s+(\d{4}))?", s)
    if m:
        mon = _MONTH_ABBR.get(m[1].lower())
        if mon:
            yr = int(m[3]) if m[3] else (year_hint or datetime.now().year)
            return date(yr, mon, int(m[2]))
    return None


def _normalize_period(raw: str) -> str:
    """Normalise any period string to ISO 8601: YYYY-MM-DD/YYYY-MM-DD or YYYY-MM-DD."""
    raw = raw.strip()
    
    # Handle "Custom (04/11/2026 - 04/18/2026)" format by stripping prefix/suffix
    if raw.lower().startswith("custom"):
        raw = re.sub(r"^[Cc]ustom\s*\(?", "", raw).rstrip(")")
        raw = raw.strip()

    if not raw or raw == "custom_default":
        return raw

    # Already correct ISO range
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}/\d{4}-\d{2}-\d{2}", raw):
        return raw
    # Already correct ISO date
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw

    year_hint = datetime.now().year

    # "M/D/YYYY-YYYY/MM/DD"  e.g. "4/2/2026-2026/05/03"
    m = re.fullmatch(r"(\d{1,2}/\d{1,2}/\d{4})-(\d{4}/\d{2}/\d{2})", raw)
    if m:
        d1 = _parse_date_part(m[1], year_hint)
        d2 = _parse_date_part(m[2], year_hint)
        if d1 and d2:
            return f"{d1.isoformat()}/{d2.isoformat()}"

    # "YYYY/MM/DD-YYYY/MM/DD"  e.g. "2026/04/04-2026/05/04"
    m = re.fullmatch(r"(\d{4}/\d{2}/\d{2})-(\d{4}/\d{2}/\d{2})", raw)
    if m:
        d1 = _parse_date_part(m[1], year_hint)
        d2 = _parse_date_part(m[2], year_hint)
        if d1 and d2:
            return f"{d1.isoformat()}/{d2.isoformat()}"

    # "Mon DD - Mon DD"  e.g. "Mar 19 - Apr 18"
    # "MM/DD/YYYY - MM/DD/YYYY"
    if " - " in raw:
        parts = raw.split(" - ", 1)
        d1 = _parse_date_part(parts[0], year_hint)
        d2 = _parse_date_part(parts[1], year_hint)
        if d1 and d2:
            return f"{d1.isoformat()}/{d2.isoformat()}"

    # Single-date fallback
    d = _parse_date_part(raw, year_hint)
    if d:
        return d.isoformat()

    return raw  # unknown format — pass through unchanged


def _normalize_daily_date(raw: str) -> str:
    """Normalise a daily-row date (any format) to YYYY-MM-DD."""
    d = _parse_date_part(raw.strip())
    return d.isoformat() if d else raw


def _parse_json_response(text: str) -> dict:
    print(f"DEBUG: RAW AI TEXT (first 200 chars): {text[:200]}")
    text = text.strip()
    try:
        # Try finding the first '{' and last '}'
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            json_str = text[start:end+1]
            return json.loads(json_str)
        return json.loads(text)
    except Exception as e:
        print(f"DEBUG: PARSE FAILED: {e}")
        logger.error(f"Failed to parse JSON from AI: {e}. Raw text: {text[:200]}...")
        raise ValueError(f"AI response is not valid JSON: {e}")


MAX_RETRIES = 5  # Allow more retries for 100 images
RETRY_BASE_DELAY = 4  # Start with 4s delay

class GeminiQuotaExceeded(Exception):
    pass


class HuggingFaceQuotaExceeded(Exception):
    pass


VISION_QUOTA_MESSAGE = (
    "He thong da het quota Vision API. Vui long doi Gemini key hoac nap them credit Hugging Face roi thu lai."
)
VISION_NOT_CONFIGURED_MESSAGE = (
    "Chua cau hinh Vision API. Can co GEMINI_API_KEY_paid, GEMINI_API_KEY_free hoac HUGGINGFACE_API_KEY."
)

def _mime_for(name: str) -> str:
    n = name.lower()
    if n.endswith(".png"):
        return "image/png"
    if n.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"


def _is_quota_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        "429" in msg
        or "quota" in msg
        or "resource_exhausted" in msg
    )


def _is_hf_quota_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        "402" in msg
        or "payment required" in msg
        or "depleted your monthly included credits" in msg
        or "billing" in msg
        or "quota" in msg
        or "rate limit" in msg
    )


def _sanitize_provider_error(prefix: str, exc: Exception) -> str:
    raw = re.sub(r"\s+", " ", str(exc)).strip()
    if not raw:
        return prefix
    return f"{prefix}: {raw[:240]}"


async def _call_gemini_with_key(filename: str, image_data: bytes, settings, api_key: str) -> dict:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(settings.GEMINI_MODEL)
    mime_type = _mime_for(filename)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    model.generate_content,
                    [{"mime_type": mime_type, "data": image_data}, EXTRACTION_PROMPT],
                ),
                timeout=VISION_CALL_TIMEOUT,
            )
            logger.info("GEMINI response for %s: %s", filename, response.text[:200])
            return _parse_json_response(response.text)
        except Exception as e:
            if _is_quota_error(e):
                raise GeminiQuotaExceeded(str(e))
            raise
    raise GeminiQuotaExceeded("Max retries exhausted")


async def _call_gemini_vision(filename: str, image_data: bytes, settings) -> dict:
    """Try Gemini keys in order before falling back to other providers."""
    gemini_keys = [
        key.strip()
        for key in (settings.GEMINI_API_KEY_paid, settings.GEMINI_API_KEY_free)
        if key and key.strip()
    ]
    if not gemini_keys:
        raise ValueError("No Gemini API key configured")

    saw_quota_error = False
    last_error: Exception | None = None
    for api_key in gemini_keys:
        try:
            return await _call_gemini_with_key(filename, image_data, settings, api_key)
        except GeminiQuotaExceeded as exc:
            saw_quota_error = True
            last_error = exc
            logger.warning("Gemini quota exhausted for %s on one configured key", filename)
            continue
        except Exception as exc:
            last_error = exc
            break

    if saw_quota_error and (last_error is None or isinstance(last_error, GeminiQuotaExceeded)):
        raise GeminiQuotaExceeded("All configured Gemini keys are out of quota")
    if last_error is not None:
        raise last_error
    raise GeminiQuotaExceeded("All configured Gemini keys are out of quota")


async def _call_huggingface_vision(filename: str, image_data: bytes, settings) -> dict:
    """HF Router fallback (Qwen3-VL etc.)."""
    logger.info("ENTERING HUGGINGFACE EXTRACTION for %s", filename)
    b64 = base64.b64encode(image_data).decode()
    mime_type = _mime_for(filename)

    url = "https://router.huggingface.co/v1/chat/completions"
    headers = {"Authorization": f"Bearer {settings.HUGGINGFACE_API_KEY}"}
    payload = {
        "model": settings.HF_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
                    {"type": "text", "text": EXTRACTION_PROMPT},
                ],
            }
        ],
        "max_tokens": 2048,
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code != 200:
            error = Exception(f"HF error: {resp.status_code} - {resp.text}")
            if _is_hf_quota_error(error):
                raise HuggingFaceQuotaExceeded(str(error))
            raise error
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        return _parse_json_response(text)


async def extract_batch_streaming(
    images: list[tuple[str, bytes]],
    on_result: Callable[[int, dict | None, str | None], Awaitable[None]] | None = None,
):
    """
    Extract images one by one and call on_result(idx, result) after each.

    Args:
        images: list of (filename, image_bytes) tuples.
    """
    settings = get_settings()
    total = len(images)
    gemini_keys = [
        key.strip()
        for key in (settings.GEMINI_API_KEY_paid, settings.GEMINI_API_KEY_free)
        if key and key.strip()
    ]
    has_hf = bool(settings.HUGGINGFACE_API_KEY and settings.HUGGINGFACE_API_KEY.strip())

    for idx, (name, data) in enumerate(images):
        error_message = None
        try:
            result = None
            if not gemini_keys and not has_hf:
                error_message = VISION_NOT_CONFIGURED_MESSAGE

            gemini_quota_exhausted = False
            hf_quota_exhausted = False

            if gemini_keys:
                try:
                    result = await _call_gemini_vision(name, data, settings)
                except GeminiQuotaExceeded as e:
                    gemini_quota_exhausted = True
                    error_message = _sanitize_provider_error("Gemini het quota", e)
                    logger.warning("Gemini quota exhausted for %s: %s", name, e)
                except Exception as e:
                    error_message = _sanitize_provider_error("Gemini failed", e)
                    logger.warning("Gemini failed for %s: %s", name, e)

            if result is None and has_hf:
                try:
                    result = await _call_huggingface_vision(name, data, settings)
                    error_message = None
                except HuggingFaceQuotaExceeded as e:
                    hf_quota_exhausted = True
                    logger.warning("HuggingFace quota exhausted for %s: %s", name, e)
                    if gemini_quota_exhausted:
                        error_message = VISION_QUOTA_MESSAGE
                    else:
                        error_message = _sanitize_provider_error("HuggingFace het quota", e)
                except Exception as e:
                    hf_error = _sanitize_provider_error("HuggingFace failed", e)
                    error_message = f"{error_message}; {hf_error}" if error_message else hf_error
                    logger.error("HuggingFace failed for %s: %s", name, e)

            if result is None and gemini_quota_exhausted and (hf_quota_exhausted or not has_hf):
                error_message = VISION_QUOTA_MESSAGE

            if on_result:
                await on_result(idx, result, None if result is not None else error_message)
        except Exception as e:
            error_message = _sanitize_provider_error("Streaming error", e)
            logger.error("Streaming error for %s: %s", name, e)
            if on_result:
                await on_result(idx, None, error_message)

        if idx < total - 1:
            await asyncio.sleep(5.0)


def _merge_results(
    raw_results: list[dict | None],
) -> tuple[list[dict], list[dict]]:
    logger.error(f"!!! EXECUTING MERGE FROM: {__file__} !!!")
    logger.error(f"!!! RAW RESULTS COUNT: {len(raw_results)} !!!")
    """
    Merge extracted data from multiple screenshots.

    Listing daily screenshots for the same listing_id are merged:
    - Summary row: taken from any screenshot (they share the same summary)
    - Daily rows: merged by date across different metric_columns

    Keyword tables are kept as-is.
    """
    # Group by listing_id for listing_daily type
    listing_groups: dict[str, dict] = {}  # listing_id -> merged data
    keyword_rows: list[dict] = []

    for r in raw_results:
        if r is None:
            print("DEBUG: MERGE - Skipping None result")
            continue

        rtype = str(r.get("type", "")).lower()
        print(f"DEBUG: MERGE - Checking RTYPE: '{rtype}' | LID: {r.get('listing_id')}")
        logger.error(f"CHECKING RTYPE: '{rtype}' | KEYS: {list(r.keys())}")

        if "listing" in rtype or "type a" in rtype:
            print(f"DEBUG: MERGE - MATCHED TYPE A for {r.get('listing_id')}")
            logger.error(f"-> MATCHED LISTING TYPE A for {r.get('listing_id')}")
            lid = r.get("listing_id", "")
            if not lid:
                continue

            if lid not in listing_groups:
                listing_groups[lid] = {
                    "listing_id": lid,
                    "title": r.get("title"),
                    "no_vm": r.get("no_vm"),
                    "price": r.get("price"),
                    "stock": r.get("stock"),
                    "category": r.get("category"),
                    "lifetime_orders": r.get("lifetime_orders"),
                    "lifetime_revenue": r.get("lifetime_revenue"),
                    "period": _normalize_period(r.get("period", "")),
                    "summary": r.get("summary", {}),
                    "daily": {},  # date -> {metric: value}
                }
            else:
                # Update metadata if missing
                grp = listing_groups[lid]
                for key in ("title", "no_vm", "price", "stock", "category",
                            "lifetime_orders", "lifetime_revenue"):
                    if grp.get(key) is None and r.get(key) is not None:
                        grp[key] = r[key]

            # Merge daily data
            metric_col = r.get("metric_column", "views")
            for day in r.get("daily_data", []):
                date_key = _normalize_daily_date(day.get("date", ""))
                if not date_key:
                    continue
                if date_key not in listing_groups[lid]["daily"]:
                    listing_groups[lid]["daily"][date_key] = {}
                listing_groups[lid]["daily"][date_key][metric_col] = day.get("value", 0)

        elif "keyword" in rtype or "type b" in rtype:
            logger.error(f"-> MATCHED KEYWORD TYPE B for {r.get('listing_id')}")
            lid = r.get("listing_id", "")
            vm = r.get("no_vm")
            for kw in r.get("keywords", []):
                keyword_rows.append({
                    "listing_id": lid,
                    "vm": vm,
                    "keyword": kw.get("keyword"),
                    "relevant": kw.get("relevant"),
                    "roas": kw.get("roas"),
                    "orders": kw.get("orders"),
                    "spend": kw.get("spend"),
                    "revenue": kw.get("revenue"),
                    "clicks": kw.get("clicks"),
                    "click_rate": kw.get("click_rate"),
                    "views": kw.get("views"),
                })

    # Build flat listing_report rows
    listing_rows: list[dict] = []
    for lid, grp in listing_groups.items():
        base = {
            "listing_id": grp["listing_id"],
            "title": grp["title"],
            "no_vm": grp["no_vm"],
            "price": grp["price"],
            "stock": grp["stock"],
            "category": grp["category"],
            "lifetime_orders": grp["lifetime_orders"],
            "lifetime_revenue": grp["lifetime_revenue"],
        }

        # Summary row
        s = grp["summary"]
        listing_rows.append({
            **base,
            "period": grp["period"],
            "views": s.get("views", 0),
            "clicks": s.get("clicks", 0),
            "orders": s.get("orders", 0),
            "revenue": s.get("revenue", 0),
            "spend": s.get("spend", 0),
            "roas": s.get("roas", 0),
        })

        # Daily rows
        for date_key, metrics in sorted(grp["daily"].items()):
            listing_rows.append({
                **base,
                "period": date_key,
                "views": metrics.get("views", 0),
                "clicks": metrics.get("clicks", 0),
                "orders": metrics.get("orders", 0),
                "revenue": metrics.get("revenue", 0),
                "spend": metrics.get("spend", 0),
                "roas": metrics.get("roas", 0),
            })

    # Set default period on keyword rows from listing data
    default_period = ""
    if listing_groups:
        first = next(iter(listing_groups.values()))
        default_period = first.get("period", "")  # already normalised above

    for kw in keyword_rows:
        kw["period"] = _normalize_period(kw.get("period", "") or default_period)

    return listing_rows, keyword_rows
