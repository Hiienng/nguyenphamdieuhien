"""
bulk_extract_features.py — Extract Gemini features for ALL market_listing rows with images.

Skips rows already in thumbnail_features (by image_url).
Assigns ml_label: 1 for Bestseller/Popular now, 0 for others.

Usage:
  cd nguyenphamdieuhien.online/backend
  python scripts/bulk_extract_features.py [--limit 50] [--product-type onesie]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Add backend root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

EtseeMate_DB = os.environ["DATABASE_URL"].replace("postgresql://", "postgres://")
MARKET_DB   = os.environ["ETSY_MARKET_DB"].replace("postgresql://", "postgres://")
GEMINI_KEY  = os.environ.get("GEMINI_API_KEY_paid_thumbnail")


async def already_extracted(pool: asyncpg.Pool, image_url: str) -> bool:
    row = await pool.fetchrow(
        "SELECT id FROM thumbnail_features WHERE image_url = $1 LIMIT 1", image_url
    )
    return row is not None


async def extract_and_save(pool: asyncpg.Pool, row: dict) -> bool:
    """Extract features via Gemini and insert into thumbnail_features."""
    import google.generativeai as genai

    image_url   = row["image_url"]
    product_type = row["product_type"] or "other"
    badge        = row["badge"] or ""
    ml_label     = 1 if badge and ("bestseller" in badge.lower() or "popular" in badge.lower()) else 0

    # Build prompt
    from app.services.vision_service import _FEATURE_PROMPT, _extract_json

    prompt = f"Product type context: {product_type}\n\n{_FEATURE_PROMPT}"
    contents = [f"{prompt}\n\nImage URL: {image_url}"]

    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash-lite")

    loop = asyncio.get_event_loop()
    try:
        response = await loop.run_in_executor(
            None, lambda: model.generate_content(contents)
        )
        data = _extract_json(response.text)
    except Exception as exc:
        logger.warning("Gemini failed for %s: %s", image_url[:60], exc)
        return False

    def _bool(v, default=False):
        if isinstance(v, bool): return v
        if isinstance(v, str): return v.lower() in ("true", "1", "yes")
        return default

    def _int(v, default=None):
        try: return int(v)
        except: return default

    await pool.execute("""
        INSERT INTO thumbnail_features (
            source, image_url, product_type, badge,
            subject, subject_colors, subject_color_names,
            background_color, background_color_name, background_type, background_description,
            theme, fabric_material,
            decoration_object, decoration_technique, decoration_colors,
            seasonal_type, lifestyle_props,
            text_overlay, text_overlay_content, composition, overall_mood,
            image_brightness, image_contrast, color_harmony, color_count, background_clutter,
            product_visibility, product_size_in_frame,
            personalization_visible, gift_cue_visible, size_reference,
            gender_signal, age_target, occasion_signal, style_aesthetic,
            ml_label, extracted_at
        ) VALUES (
            'market', $1, $2, $3,
            $4, $5::jsonb, $6::jsonb,
            $7, $8, $9, $10,
            $11, $12,
            $13, $14, $15::jsonb,
            $16, $17::jsonb,
            $18, $19, $20, $21,
            $22, $23, $24, $25, $26,
            $27, $28,
            $29, $30, $31,
            $32, $33, $34, $35,
            $36, NOW()
        )
        ON CONFLICT DO NOTHING
    """,
        image_url, product_type, badge,
        data.get("subject"),
        json.dumps(data.get("subject_colors") or []),
        json.dumps(data.get("subject_color_names") or []),
        data.get("background_color"),
        data.get("background_color_name"),
        data.get("background_type"),
        data.get("background_description"),
        data.get("theme"),
        data.get("fabric_material"),
        data.get("decoration_object"),
        data.get("decoration_technique"),
        json.dumps(data.get("decoration_colors") or []),
        data.get("seasonal_type"),
        json.dumps(data.get("lifestyle_props") or []),
        _bool(data.get("text_overlay")),
        data.get("text_overlay_content"),
        data.get("composition"),
        data.get("overall_mood"),
        data.get("image_brightness"),
        data.get("image_contrast"),
        data.get("color_harmony"),
        _int(data.get("color_count")),
        data.get("background_clutter"),
        data.get("product_visibility"),
        data.get("product_size_in_frame"),
        _bool(data.get("personalization_visible")),
        _bool(data.get("gift_cue_visible")),
        _bool(data.get("size_reference")),
        data.get("gender_signal"),
        data.get("age_target"),
        data.get("occasion_signal"),
        data.get("style_aesthetic"),
        ml_label,
    )
    return True


async def main(limit: int | None, product_type: str | None) -> None:
    logger.info("Connecting to DBs...")
    EtseeMate_pool = await asyncpg.create_pool(EtseeMate_DB, ssl="require")
    market_pool   = await asyncpg.create_pool(MARKET_DB,   ssl="require")

    # Fetch market listings
    where = "image_url IS NOT NULL"
    params: list = []
    if product_type:
        where += " AND product_type = $1"
        params.append(product_type)

    query = f"SELECT image_url, product_type, badge FROM market_listing WHERE {where} ORDER BY tag_ranking ASC NULLS LAST"
    if limit:
        query += f" LIMIT {limit}"

    rows = await market_pool.fetch(query, *params)
    logger.info("Found %d market listings to process", len(rows))

    done = skipped = failed = 0
    for i, row in enumerate(rows):
        if await already_extracted(EtseeMate_pool, row["image_url"]):
            skipped += 1
            continue
        ok = await extract_and_save(EtseeMate_pool, dict(row))
        if ok:
            done += 1
            logger.info("[%d/%d] ✓ %s", i+1, len(rows), row["image_url"][:70])
        else:
            failed += 1
            logger.warning("[%d/%d] ✗ failed: %s", i+1, len(rows), row["image_url"][:70])

        # Small delay to avoid Gemini rate limit
        await asyncio.sleep(0.5)

    await EtseeMate_pool.close()
    await market_pool.close()
    logger.info("Done — extracted: %d | skipped: %d | failed: %d", done, skipped, failed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Max rows to process")
    parser.add_argument("--product-type", type=str, default=None)
    args = parser.parse_args()
    asyncio.run(main(args.limit, args.product_type))
