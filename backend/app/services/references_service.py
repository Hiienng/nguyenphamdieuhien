"""
References service — pair internal listings với top-N market listings cùng
category, rank theo tag_ranking ASC.

Schema mapping (market_listing):
  - market_listing.listing_id  → reference_listing_id
  - market_listing.keyword     → search_tag
  - market_listing.tag_ranking → tag_ranking
  - market_listing.title       → derive product_type qua Gemini (1 call/run)

Gọi từ POST /api/v1/references/refresh.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings

logger = logging.getLogger(__name__)


# Map internal category → market product_type keywords to match against
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "onesie":   ["onesie", "bodysuit", "baby bodysuit", "baby shower onesie", "custom baby onesie",
                 "monogram onesie", "custom name onesie", "personalized baby onesie", "baby onesie"],
    "blanket":  ["blanket", "swaddle", "custom baby blanket", "birth stat blanket",
                 "knit baby blanket", "embroidered blanket", "heirloom baby blanket",
                 "monogrammed blanket", "keepsake blanket", "baby name blanket"],
    "blankets": ["blanket", "swaddle", "custom baby blanket", "birth stat blanket",
                 "knit baby blanket", "embroidered blanket", "heirloom baby blanket",
                 "monogrammed blanket", "keepsake blanket", "baby name blanket"],
    "sweater":  ["sweater", "baby zip romper", "romper", "knit", "coming home outfit",
                 "newborn outfit", "baby clothes"],
    "crown":    ["crown", "first birthday", "first birthday gift", "baby milestone",
                 "birthday gift"],
}

# Canonical product_types Gemini có thể trả về (= keys of _CATEGORY_KEYWORDS + "other")
_PRODUCT_TYPES = ["onesie", "blanket", "sweater", "crown", "other"]


_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS references_engine (
    listing_id           VARCHAR(32)  NOT NULL,
    reference_listing_id TEXT         NOT NULL,
    ref_rank             SMALLINT     NOT NULL,
    ref_title            TEXT,
    ref_shop             TEXT,
    ref_url              TEXT,
    ref_price            INTEGER,
    ref_discount         INTEGER,
    ref_rating           REAL,
    ref_review_count     INTEGER,
    ref_tag_ranking      INTEGER,
    ref_badge            TEXT,
    ref_free_shipping    BOOLEAN,
    ref_product_type     TEXT,
    ref_import_date      DATE,
    match_method         VARCHAR(16)  DEFAULT 'category',
    refreshed_at         TIMESTAMPTZ  DEFAULT now(),
    PRIMARY KEY (listing_id, reference_listing_id)
)
"""

_MIGRATE_COLUMNS_SQL = """
ALTER TABLE references_engine
    ADD COLUMN IF NOT EXISTS ref_discount      INTEGER,
    ADD COLUMN IF NOT EXISTS ref_free_shipping BOOLEAN,
    ADD COLUMN IF NOT EXISTS ref_product_type  TEXT,
    ADD COLUMN IF NOT EXISTS ref_import_date   DATE
"""

_UPSERT_SQL = """
INSERT INTO references_engine (
    listing_id, reference_listing_id, ref_rank,
    ref_title, ref_shop, ref_url, ref_price, ref_discount,
    ref_rating, ref_review_count, ref_tag_ranking, ref_badge,
    ref_free_shipping, ref_product_type, ref_import_date,
    match_method, refreshed_at
) VALUES (
    :listing_id, :reference_listing_id, :rnk,
    :ref_title, :ref_shop, :ref_url, :ref_price, :ref_discount,
    :ref_rating, :ref_review_count, :ref_tag_ranking, :ref_badge,
    :ref_free_shipping, :ref_product_type, :ref_import_date,
    'category', now()
)
ON CONFLICT (listing_id, reference_listing_id) DO UPDATE SET
    ref_rank          = EXCLUDED.ref_rank,
    ref_title         = COALESCE(EXCLUDED.ref_title,         references_engine.ref_title),
    ref_shop          = COALESCE(EXCLUDED.ref_shop,          references_engine.ref_shop),
    ref_url           = COALESCE(EXCLUDED.ref_url,           references_engine.ref_url),
    ref_price         = COALESCE(EXCLUDED.ref_price,         references_engine.ref_price),
    ref_discount      = COALESCE(EXCLUDED.ref_discount,      references_engine.ref_discount),
    ref_rating        = COALESCE(EXCLUDED.ref_rating,        references_engine.ref_rating),
    ref_review_count  = COALESCE(EXCLUDED.ref_review_count,  references_engine.ref_review_count),
    ref_tag_ranking   = COALESCE(EXCLUDED.ref_tag_ranking,   references_engine.ref_tag_ranking),
    ref_badge         = COALESCE(EXCLUDED.ref_badge,         references_engine.ref_badge),
    ref_free_shipping = COALESCE(EXCLUDED.ref_free_shipping, references_engine.ref_free_shipping),
    ref_product_type  = COALESCE(EXCLUDED.ref_product_type,  references_engine.ref_product_type),
    ref_import_date   = COALESCE(EXCLUDED.ref_import_date,   references_engine.ref_import_date),
    refreshed_at      = now()
"""


def _classify_titles_with_gemini_sync(titles: list[str]) -> dict[str, str]:
    """Batch-classify titles → product_type. 1 Gemini call cho tất cả."""
    settings = get_settings()
    if not settings.GEMINI_API_KEY_paid_thumbnail or not titles:
        return {}

    try:
        import google.generativeai as genai  # lazy: optional, not bundled in desktop build
    except Exception as e:  # noqa: BLE001
        logger.warning("google.generativeai unavailable; skipping Gemini classification: %s", e)
        return {}

    genai.configure(api_key=settings.GEMINI_API_KEY_paid_thumbnail)
    model = genai.GenerativeModel("gemini-2.5-flash")

    try:
        response = model.generate_content(_build_classify_prompt(titles))
        result = _parse_classify_response(response.text.strip(), titles)
        logger.info("Gemini classified %d/%d titles", sum(1 for v in result.values() if v), len(titles))
        return result
    except Exception as e:
        logger.warning("Gemini classification failed: %s", e)
        return {}


def _build_classify_prompt(titles: list[str]) -> str:
    types_str = ", ".join(_PRODUCT_TYPES)
    numbered = "\n".join(f"{i+1}|{t}" for i, t in enumerate(titles))
    return (
        f"Classify each Etsy listing title by the PHYSICAL PRODUCT being sold. "
        f"Pick exactly ONE product_type from: {types_str}.\n\n"
        f"Definitions (match ONLY when title clearly names the physical item):\n"
        f"- onesie: baby onesie or bodysuit (one-piece infant garment).\n"
        f"- blanket: baby blanket or swaddle.\n"
        f"- sweater: knit/woven sweater, romper, or coming-home outfit.\n"
        f"- crown: a wearable crown (e.g. birthday/cake-smash crown for babies).\n"
        f"- other: anything else (necklaces, jewelry, prints, signs, mugs, decor, "
        f"  digital files, accessories, gift items not in the four categories above).\n\n"
        f"IMPORTANT:\n"
        f"- Words like \"birthday gift\", \"mother's day\", \"personalized\" alone do NOT make it a crown — "
        f"  classify as \"other\" unless title explicitly says \"crown\".\n"
        f"- Necklaces, rings, earrings, bracelets, watches → other.\n"
        f"- Wall art, prints, signs, plaques, frames → other.\n"
        f"- When unsure, choose \"other\".\n\n"
        f"Input: {len(titles)} lines, format `<index>|<title>`.\n"
        f"Output: JSON array of objects, exactly {len(titles)} items, in input order.\n"
        f"Each item: {{\"i\": <index>, \"t\": \"<product_type>\"}}.\n"
        f"Do NOT split titles on commas. Return ONLY the JSON array.\n\n"
        f"INPUT:\n{numbered}"
    )


def _parse_classify_response(raw: str, titles: list[str]) -> dict[str, str]:
    match = re.search(r"\[[\s\S]*\]", raw)
    arr = json.loads(match.group() if match else raw)
    if not isinstance(arr, list):
        return {}
    idx_to_type = {}
    for item in arr:
        if isinstance(item, dict) and "i" in item and "t" in item:
            try:
                idx_to_type[int(item["i"]) - 1] = str(item["t"]).lower().strip()
            except (ValueError, TypeError):
                continue
    out = {}
    for i, t in enumerate(titles):
        ptype = idx_to_type.get(i, "")
        if ptype not in _PRODUCT_TYPES:
            ptype = "other"
        out[t] = ptype
    return out


async def _classify_titles_with_groq(titles: list[str]) -> dict[str, str]:
    settings = get_settings()
    if not settings.GROQ_API_KEY or not titles:
        return {}
    prompt = _build_classify_prompt(titles)
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                json=payload,
            )
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"]
        # Groq with json_object mode returns {"result": [...]} — try both shapes
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                for v in parsed.values():
                    if isinstance(v, list):
                        raw = json.dumps(v)
                        break
        except Exception:
            pass
        result = _parse_classify_response(raw, titles)
        logger.info("Groq classified %d/%d titles", sum(1 for v in result.values() if v), len(titles))
        return result
    except Exception as e:
        logger.warning("Groq classification failed: %s", e)
        return {}


async def _classify_titles(titles: list[str]) -> dict[str, str]:
    # Try Gemini first, fall back to Groq
    result = await asyncio.to_thread(_classify_titles_with_gemini_sync, titles)
    if result:
        return result
    logger.info("Gemini unavailable — falling back to Groq for %d titles", len(titles))
    return await _classify_titles_with_groq(titles)


def _matches_category(text_blob: str, category: str) -> bool:
    """Substring match listing title/keyword against category-specific keywords."""
    blob = (text_blob or "").lower()
    kws = _CATEGORY_KEYWORDS.get(category, [category])
    return any(kw in blob for kw in kws)


async def refresh_references(
    db: AsyncSession,
    market_db: AsyncSession,
    top_n: int = 3,
    listing_id: str | None = None,
) -> dict:
    await db.execute(text(_CREATE_TABLE_SQL))
    await db.execute(text(_MIGRATE_COLUMNS_SQL))

    # Xoá refs cũ của scope đang refresh
    await db.execute(
        text(
            """
            DELETE FROM references_engine
            WHERE (CAST(:listing_id AS VARCHAR) IS NULL OR listing_id = CAST(:listing_id AS VARCHAR))
            """
        ),
        {"listing_id": listing_id},
    )

    listings_result = await db.execute(
        text("SELECT listing_id, category FROM listings WHERE category IS NOT NULL"
             + (" AND listing_id = :lid" if listing_id else "")),
        {"lid": listing_id} if listing_id else {},
    )
    internal_listings = [dict(r._mapping) for r in listings_result]

    if not internal_listings:
        return {"upserted": 0, "listings_with_ref": 0, "total_refs": 0, "top_n": top_n, "scope": listing_id or "all"}

    # Ensure product_type column exists (idempotent — crawler có thể không biết về cột này)
    try:
        await market_db.execute(text("ALTER TABLE market_listing ADD COLUMN IF NOT EXISTS product_type TEXT"))
        await market_db.commit()
    except Exception as e:
        logger.warning("Could not ensure product_type column: %s", e)

    # Pull all market candidates với product_type đã được lưu sẵn
    try:
        mkt_result = await market_db.execute(text("""
            SELECT listing_id::text AS reference_listing_id,
                   title, shop_name, url, price, discount,
                   rating, review_count, tag_ranking, badge, free_shipping,
                   keyword AS search_tag,
                   product_type,
                   crawled_at::date AS import_date
            FROM market_listing
            WHERE tag_ranking IS NOT NULL
        """))
        market_rows = [dict(r._mapping) for r in mkt_result]
    except Exception as e:
        logger.warning("market_listing query failed: %s", e)
        market_rows = []

    if not market_rows:
        return {"upserted": 0, "listings_with_ref": 0, "total_refs": 0, "top_n": top_n, "scope": listing_id or "all"}

    # Lazy backfill: chỉ classify các rows có product_type=NULL, UPDATE ngược về DB
    needs_classify = [m for m in market_rows if not m.get("product_type") and m.get("title")]
    if needs_classify:
        titles = [m["title"] for m in needs_classify]
        title_to_type = await _classify_titles(titles)
        if title_to_type:
            updates = []
            for m in needs_classify:
                ptype = title_to_type.get(m["title"])
                if ptype:
                    m["product_type"] = ptype
                    updates.append({"lid": int(m["reference_listing_id"]), "kw": m["search_tag"], "pt": ptype})
            for u in updates:
                await market_db.execute(
                    text("UPDATE market_listing SET product_type = :pt WHERE listing_id = :lid AND keyword = :kw"),
                    u,
                )
            await market_db.commit()
            logger.info("Backfilled product_type for %d market_listing rows", len(updates))

    # Strict match: market.product_type phải khớp listing.category (canonical form).
    # Listing nào không có market candidate cùng product_type → 0 refs.
    def _canon(cat: str) -> str:
        cat = (cat or "").lower().strip()
        return "blanket" if cat in ("blanket", "blankets") else cat

    rows = []
    for lst in internal_listings:
        target = _canon(lst["category"])
        matches = [m for m in market_rows if (m.get("product_type") or "").lower() == target]
        matches.sort(key=lambda m: (m.get("tag_ranking") or 99999, -(m.get("review_count") or 0)))
        for rnk, m in enumerate(matches[:top_n], start=1):
            rows.append({
                "listing_id": lst["listing_id"],
                "reference_listing_id": m["reference_listing_id"],
                "rnk": rnk,
                "ref_title": m.get("title"),
                "ref_shop": m.get("shop_name"),
                "ref_url": m.get("url"),
                "ref_price": int(m["price"]) if m.get("price") is not None else None,
                "ref_discount": m.get("discount"),
                "ref_rating": float(m["rating"]) if m.get("rating") is not None else None,
                "ref_review_count": m.get("review_count"),
                "ref_tag_ranking": m.get("tag_ranking"),
                "ref_badge": m.get("badge"),
                "ref_free_shipping": m.get("free_shipping"),
                "ref_product_type": m.get("product_type"),
                "ref_import_date": m.get("import_date"),
            })

    for row in rows:
        await db.execute(text(_UPSERT_SQL), row)

    await db.commit()

    scope = await db.execute(
        text(
            """
            SELECT COUNT(DISTINCT listing_id) AS covered, COUNT(*) AS total
            FROM references_engine
            WHERE (CAST(:listing_id AS VARCHAR) IS NULL OR listing_id = CAST(:listing_id AS VARCHAR))
            """
        ),
        {"listing_id": listing_id},
    )
    r = scope.one()._mapping

    return {
        "upserted":          len(rows),
        "listings_with_ref": r["covered"],
        "total_refs":        r["total"],
        "top_n":             top_n,
        "scope":             listing_id or "all",
    }


async def get_references(
    db: AsyncSession,
    listing_id: str | None = None,
) -> list[dict]:
    result = await db.execute(
        text(
            """
            SELECT listing_id, reference_listing_id, ref_rank,
                   ref_title, ref_shop, ref_url, ref_price, ref_discount,
                   ref_rating, ref_review_count, ref_tag_ranking, ref_badge,
                   ref_free_shipping, ref_product_type, ref_import_date,
                   refreshed_at
            FROM references_engine
            WHERE (CAST(:listing_id AS VARCHAR) IS NULL OR listing_id = CAST(:listing_id AS VARCHAR))
            ORDER BY listing_id, ref_rank
            """
        ),
        {"listing_id": listing_id},
    )
    return [dict(r._mapping) for r in result]
