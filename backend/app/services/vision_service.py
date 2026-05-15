"""
vision_service.py — Thumbnail Knowledge Generation & Evaluation

Uses Gemini 2.5 Flash Lite for vision tasks (cheapest available):
  1. _extract_features(): extract rich visual features from a single image
  2. generate_knowledge(): crawl trending market listings → extract features → aggregate patterns
  3. evaluate_thumbnail(): score a thumbnail against knowledge base + return extracted features

Key used: GEMINI_API_KEY_paid_thumbnail (dedicated, no fallback).
"""
from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any

import google.generativeai as genai
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..schemas.vision_schema import CriterionScore, ThumbnailEvalResponse, ThumbnailFeatures
from . import thumbnail_ml_service

logger = logging.getLogger(__name__)

RUBRIC_CRITERIA = [
    "resolution_sharpness",
    "visual_clarity",
    "background_quality",
    "product_focus",
    "text_overlay_readability",
    "theme_mood_consistency",
    "color_palette_fit",
    "target_audience_fit",
    "lifestyle_context",
]


def _get_model() -> genai.GenerativeModel:
    settings = get_settings()
    key = settings.GEMINI_API_KEY_paid_thumbnail
    if not key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY_paid_thumbnail chưa được cấu hình.")
    genai.configure(api_key=key)
    return genai.GenerativeModel(settings.GEMINI_MODEL)


async def _generate(model: genai.GenerativeModel, contents: list) -> str:
    """Sync Gemini call wrapped — google-generativeai is sync, run in thread."""
    import asyncio
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, lambda: model.generate_content(contents))
    return response.text


async def _generate_with_fallback(contents: list) -> str:
    """Call thumbnail Gemini key — no fallback, fail fast on quota."""
    model = _get_model()
    return await _generate(model, contents)


def _extract_json(text_content: str) -> Any:
    """Extract JSON from Gemini response that may have surrounding markdown/text."""
    try:
        return json.loads(text_content.strip())
    except json.JSONDecodeError:
        pass
    # Strip markdown fences
    cleaned = re.sub(r"```(?:json)?", "", text_content).strip().strip("`")
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text_content)
    if match:
        return json.loads(match.group(1))
    raise ValueError(f"No valid JSON found in response: {text_content[:300]}")


_FEATURE_PROMPT = """You are an expert Etsy product image analyst.
Analyze this thumbnail image and extract all visual features.
Return ONLY a valid JSON object with these exact keys (no markdown fences):

{
  "subject": "<what the main product/subject is, e.g. 'personalized baby onesie'>",
  "subject_colors": ["#hex1", "#hex2"],
  "subject_color_names": ["color name1", "color name2"],
  "background_color": "#hex",
  "background_color_name": "<color name>",
  "background_type": "<white_studio|lifestyle|gradient|texture|outdoor|flat_lay|other>",
  "background_description": "<brief description>",
  "theme": "<overall theme, e.g. 'minimalist newborn gift'>",
  "fabric_material": "<material if visible, e.g. 'cotton', 'fleece', 'none'>",
  "decoration_object": "<decoration/text on product, e.g. 'name Jason', 'dinosaur patch', 'none'>",
  "decoration_technique": "<embroidery|print|heat_transfer|applique|none>",
  "decoration_colors": ["#hex1"],
  "seasonal_type": "<christmas|halloween|easter|valentines|non_seasonal>",
  "lifestyle_props": ["prop1", "prop2"],
  "text_overlay": true or false,
  "text_overlay_content": "<text if present, else null>",
  "composition": "<centered|flat_lay|close_up|editorial|angled|hanging>",
  "overall_mood": "<warm|minimal|playful|elegant|rustic|vibrant|etc.>",

  "image_brightness": "<dark|medium|bright>",
  "image_contrast": "<low|medium|high>",
  "color_harmony": "<monochromatic|analogous|complementary|triadic|neutral>",
  "color_count": <integer 1-6, number of visually dominant colors>,
  "background_clutter": "<clean|minimal|moderate|busy>",

  "product_visibility": "<full|partial|close_up|multiple_angles>",
  "product_size_in_frame": "<small|medium|large|fills_frame>",
  "personalization_visible": true or false,
  "gift_cue_visible": true or false,
  "size_reference": true or false,

  "gender_signal": "<neutral|feminine|masculine>",
  "age_target": "<newborn|infant|toddler|adult|unknown>",
  "occasion_signal": "<everyday|gift|seasonal|hospital|announcement>",
  "style_aesthetic": "<modern|rustic|boho|classic|whimsical|minimal>"
}"""


async def _extract_features_from_url(image_url: str, product_type: str | None = None) -> ThumbnailFeatures:
    """Extract rich visual features from an image URL."""
    prompt = _FEATURE_PROMPT
    if product_type:
        prompt = f"Product type context: {product_type}\n\n{prompt}"
    contents = [f"{prompt}\n\nImage URL: {image_url}"]
    try:
        raw = await _generate_with_fallback(contents)
        data = _extract_json(raw)
    except Exception as exc:
        logger.warning("Feature extraction failed for %s: %s", image_url, exc)
        return ThumbnailFeatures(source="market", image_url=image_url, product_type=product_type)
    return _parse_features(data, source="market", image_url=image_url, product_type=product_type)


async def _extract_features_from_bytes(
    image_bytes: bytes,
    image_media_type: str,
    product_type: str | None = None,
) -> ThumbnailFeatures:
    """Extract rich visual features from raw image bytes."""
    prompt = _FEATURE_PROMPT
    if product_type:
        prompt = f"Product type context: {product_type}\n\n{prompt}"
    image_part = {"mime_type": image_media_type, "data": image_bytes}
    try:
        raw = await _generate_with_fallback([prompt, image_part])
        data = _extract_json(raw)
    except Exception as exc:
        logger.warning("Feature extraction from bytes failed: %s", exc)
        return ThumbnailFeatures(source="user", product_type=product_type)
    return _parse_features(data, source="user", product_type=product_type)


def _parse_features(
    data: dict,
    source: str,
    image_url: str | None = None,
    product_type: str | None = None,
    ml_label: int | None = None,
) -> ThumbnailFeatures:
    return ThumbnailFeatures(
        source=source,
        image_url=image_url,
        product_type=product_type,
        subject=data.get("subject"),
        subject_colors=data.get("subject_colors") or [],
        subject_color_names=data.get("subject_color_names") or [],
        background_color=data.get("background_color"),
        background_color_name=data.get("background_color_name"),
        background_type=data.get("background_type"),
        background_description=data.get("background_description"),
        theme=data.get("theme"),
        fabric_material=data.get("fabric_material"),
        decoration_object=data.get("decoration_object"),
        decoration_technique=data.get("decoration_technique"),
        decoration_colors=data.get("decoration_colors") or [],
        seasonal_type=data.get("seasonal_type"),
        lifestyle_props=data.get("lifestyle_props") or [],
        text_overlay=bool(data.get("text_overlay", False)),
        text_overlay_content=data.get("text_overlay_content"),
        composition=data.get("composition"),
        overall_mood=data.get("overall_mood"),
        # new fields
        image_brightness=data.get("image_brightness"),
        image_contrast=data.get("image_contrast"),
        color_harmony=data.get("color_harmony"),
        color_count=data.get("color_count"),
        background_clutter=data.get("background_clutter"),
        product_visibility=data.get("product_visibility"),
        product_size_in_frame=data.get("product_size_in_frame"),
        personalization_visible=bool(data.get("personalization_visible", False)),
        gift_cue_visible=bool(data.get("gift_cue_visible", False)),
        size_reference=bool(data.get("size_reference", False)),
        gender_signal=data.get("gender_signal"),
        age_target=data.get("age_target"),
        occasion_signal=data.get("occasion_signal"),
        style_aesthetic=data.get("style_aesthetic"),
        ml_label=ml_label,
    )


async def _save_features(
    features: ThumbnailFeatures,
    badge: str | None,
    internal_db: AsyncSession,
    ml_label: int | None = None,
) -> None:
    """Persist a ThumbnailFeatures record to the thumbnail_features table."""
    await internal_db.execute(
        text("""
            INSERT INTO thumbnail_features (
                source, listing_id, image_url, product_type, badge,
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
                :source, :listing_id, :image_url, :product_type, :badge,
                :subject, CAST(:subject_colors AS jsonb), CAST(:subject_color_names AS jsonb),
                :background_color, :background_color_name, :background_type, :background_description,
                :theme, :fabric_material,
                :decoration_object, :decoration_technique, CAST(:decoration_colors AS jsonb),
                :seasonal_type, CAST(:lifestyle_props AS jsonb),
                :text_overlay, :text_overlay_content, :composition, :overall_mood,
                :image_brightness, :image_contrast, :color_harmony, :color_count, :background_clutter,
                :product_visibility, :product_size_in_frame,
                :personalization_visible, :gift_cue_visible, :size_reference,
                :gender_signal, :age_target, :occasion_signal, :style_aesthetic,
                :ml_label, NOW()
            )
        """),
        {
            "source": features.source,
            "listing_id": features.listing_id,
            "image_url": features.image_url,
            "product_type": features.product_type,
            "badge": badge,
            "subject": features.subject,
            "subject_colors": json.dumps(features.subject_colors),
            "subject_color_names": json.dumps(features.subject_color_names),
            "background_color": features.background_color,
            "background_color_name": features.background_color_name,
            "background_type": features.background_type,
            "background_description": features.background_description,
            "theme": features.theme,
            "fabric_material": features.fabric_material,
            "decoration_object": features.decoration_object,
            "decoration_technique": features.decoration_technique,
            "decoration_colors": json.dumps(features.decoration_colors),
            "seasonal_type": features.seasonal_type,
            "lifestyle_props": json.dumps(features.lifestyle_props),
            "text_overlay": features.text_overlay,
            "text_overlay_content": features.text_overlay_content,
            "composition": features.composition,
            "overall_mood": features.overall_mood,
            "image_brightness": features.image_brightness,
            "image_contrast": features.image_contrast,
            "color_harmony": features.color_harmony,
            "color_count": features.color_count,
            "background_clutter": features.background_clutter,
            "product_visibility": features.product_visibility,
            "product_size_in_frame": features.product_size_in_frame,
            "personalization_visible": features.personalization_visible,
            "gift_cue_visible": features.gift_cue_visible,
            "size_reference": features.size_reference,
            "gender_signal": features.gender_signal,
            "age_target": features.age_target,
            "occasion_signal": features.occasion_signal,
            "style_aesthetic": features.style_aesthetic,
            "ml_label": ml_label,
        },
    )


# ---------------------------------------------------------------------------
# Function 1: Generate Knowledge
# ---------------------------------------------------------------------------

async def generate_knowledge(
    product_type: str,
    top_n: int,
    internal_db: AsyncSession,
    market_db: AsyncSession,
) -> dict:
    """
    Query trending market listings (badge = Popular now / Best Seller),
    cluster by target audience, extract visual patterns via Gemini Vision,
    and upsert into thumbnail_knowledge.
    """
    # ── Step 1: Query market_listing ────────────────────────────────────────
    # Badge values in DB: 'Popular now', 'Bestseller' (note: no space)
    result = await market_db.execute(
        text("""
            SELECT image_url, title, badge, tag_ranking
            FROM market_listing
            WHERE (badge ILIKE '%popular%' OR badge ILIKE '%bestseller%' OR badge ILIKE '%best seller%')
              AND product_type = :product_type
              AND image_url IS NOT NULL
            ORDER BY tag_ranking ASC
            LIMIT :top_n
        """),
        {"product_type": product_type, "top_n": top_n},
    )
    rows = result.fetchall()

    # Fallback: if product_type has no badge data, use 'other' category
    if len(rows) < 3:
        result = await market_db.execute(
            text("""
                SELECT image_url, title, badge, tag_ranking
                FROM market_listing
                WHERE (badge ILIKE '%popular%' OR badge ILIKE '%bestseller%' OR badge ILIKE '%best seller%')
                  AND image_url IS NOT NULL
                ORDER BY tag_ranking ASC
                LIMIT :top_n
            """),
            {"top_n": top_n},
        )
        rows = result.fetchall()

    if len(rows) < 3:
        raise HTTPException(
            status_code=422,
            detail=f"Không đủ dữ liệu trending trong market_listing (tìm thấy {len(rows)}, cần ít nhất 3 rows). "
                   "Hãy chạy crawler để thu thập thêm data.",
        )

    image_urls = [r.image_url for r in rows]
    badges = [r.badge or "" for r in rows]
    titles = [r.title or "" for r in rows]

    # ── Step 2: Extract rich features per image (Tier 1) ────────────────────
    all_features: list[ThumbnailFeatures] = []
    for url, badge in zip(image_urls, badges):
        feat = await _extract_features_from_url(url, product_type=product_type)
        feat.badge = badge
        # ml_label: 1 for Bestseller/Popular now, 0 for others
        ml_label = 1 if badge and ("bestseller" in badge.lower() or "popular" in badge.lower()) else 0
        feat.ml_label = ml_label
        all_features.append(feat)
        try:
            await _save_features(feat, badge=badge, internal_db=internal_db, ml_label=ml_label)
        except Exception as exc:
            logger.warning("Failed to save features for %s: %s", url, exc)
    if all_features:
        await internal_db.commit()

    # ── Step 3: Detect target_audience segments from titles (text-only) ─────
    titles_formatted = "\n".join(f"- {t}" for t in titles if t)
    segment_prompt = (
        "You are an Etsy market analyst. Given the following product listing titles, "
        "identify 1-3 distinct target audience segments (e.g. 'new moms', 'dog lovers'). "
        "Return ONLY a JSON array of short segment labels (max 4 words each).\n\n"
        f"Product type: {product_type}\n\nTitles:\n{titles_formatted}\n\n"
        "Return JSON array only, e.g.: [\"new moms\", \"pet lovers\"]"
    )

    segments_raw = await _generate_with_fallback([segment_prompt])
    try:
        segments: list[str] = _extract_json(segments_raw)
        if not isinstance(segments, list) or not segments:
            segments = ["general"]
    except Exception:
        segments = ["general"]

    # ── Step 4: Aggregate features per segment → patterns (Tier 2) ──────────
    upserted = []
    for seg_idx, segment in enumerate(segments):
        seg_features = [f for i, f in enumerate(all_features) if i % len(segments) == seg_idx]
        if not seg_features:
            seg_features = all_features
        seg_urls = [f.image_url for f in seg_features if f.image_url]

        # Aggregate patterns from extracted features
        all_colors = [c for f in seg_features for c in (f.subject_colors or [])]
        all_bg_types = [f.background_type for f in seg_features if f.background_type]
        all_themes = [f.theme for f in seg_features if f.theme]
        all_moods = [f.overall_mood for f in seg_features if f.overall_mood]
        all_compositions = [f.composition for f in seg_features if f.composition]
        all_props = [p for f in seg_features for p in (f.lifestyle_props or [])]
        all_seasonal = [f.seasonal_type for f in seg_features if f.seasonal_type and f.seasonal_type != "non_seasonal"]

        def most_common(lst: list, top_n: int = 3) -> list:
            from collections import Counter
            return [v for v, _ in Counter(lst).most_common(top_n)]

        patterns = {
            "dominant_colors": most_common(all_colors, 5),
            "bg_style": most_common(all_bg_types, 1)[0] if all_bg_types else "unknown",
            "text_overlay": sum(1 for f in seg_features if f.text_overlay) > len(seg_features) / 2,
            "composition": most_common(all_compositions, 1)[0] if all_compositions else "unknown",
            "mood": most_common(all_moods, 2),
            "common_props": most_common(all_props, 5),
            "ta_signals": most_common(all_themes, 3),
            "seasonal_types": most_common(all_seasonal, 3),
            "decoration_techniques": most_common(
                [f.decoration_technique for f in seg_features if f.decoration_technique and f.decoration_technique != "none"], 3
            ),
            "fabric_materials": most_common(
                [f.fabric_material for f in seg_features if f.fabric_material and f.fabric_material != "none"], 3
            ),
            "sample_count": len(seg_features),
        }

        # ── Step 5: Upsert into thumbnail_knowledge ──────────────────────────
        await internal_db.execute(
            text("""
                INSERT INTO thumbnail_knowledge
                    (product_type, target_audience, patterns, sample_urls, sample_count, generated_at)
                VALUES
                    (:pt, :ta, CAST(:patterns AS jsonb), CAST(:sample_urls AS jsonb), :sample_count, NOW())
                ON CONFLICT (product_type, target_audience)
                DO UPDATE SET
                    patterns     = EXCLUDED.patterns,
                    sample_urls  = EXCLUDED.sample_urls,
                    sample_count = EXCLUDED.sample_count,
                    generated_at = EXCLUDED.generated_at
            """),
            {
                "pt": product_type,
                "ta": segment,
                "patterns": json.dumps(patterns),
                "sample_urls": json.dumps(seg_urls[:5]),
                "sample_count": len(seg_features),
            },
        )
        await internal_db.commit()
        upserted.append({"target_audience": segment, "patterns": patterns, "sample_count": len(seg_features)})

    return {
        "product_type": product_type,
        "images_processed": len(all_features),
        "segments_processed": len(upserted),
        "segments": [u["target_audience"] for u in upserted],
        "details": upserted,
    }


# ---------------------------------------------------------------------------
# Function 2: Evaluate Thumbnail
# ---------------------------------------------------------------------------

_VALIDATE_PROMPT = """You are an Etsy product image validator.
Look at this image and answer ONE question: is this a legitimate product listing thumbnail for an e-commerce store?

A valid product thumbnail must show:
- A clearly identifiable physical product (clothing, accessory, home item, etc.)
- The product is the main subject, not a person's face, landscape, screenshot, meme, document, or abstract art

Respond ONLY with this exact JSON (no markdown, no extra text):
{"valid": true, "reason": "brief reason"}
OR
{"valid": false, "reason": "brief reason explaining what the image actually shows"}"""


async def _validate_is_product_image(image_bytes: bytes, image_media_type: str) -> tuple[bool, str]:
    """Return (is_valid, reason). Fast single-call check before full evaluation."""
    image_b64 = base64.b64encode(image_bytes).decode()
    contents = [
        _VALIDATE_PROMPT,
        {"mime_type": image_media_type, "data": image_b64},
    ]
    try:
        raw = await _generate_with_fallback(contents)
        data = _extract_json(raw)
        return bool(data.get("valid", False)), str(data.get("reason", ""))
    except Exception as exc:
        logger.warning("Validation call failed (%s) — allowing through", exc)
        return True, "validation skipped"


async def evaluate_thumbnail(
    image_bytes: bytes,
    image_media_type: str,
    product_type: str,
    internal_db: AsyncSession,
) -> ThumbnailEvalResponse:
    """
    Evaluate a seller's thumbnail image against thumbnail_knowledge for the given product_type.
    Returns structured scores across 9 rubric criteria.
    """
    # ── Step 0: Validate image is a product thumbnail ─────────────────────
    is_valid, reason = await _validate_is_product_image(image_bytes, image_media_type)
    if not is_valid:
        raise HTTPException(
            status_code=422,
            detail=f"Image does not appear to be a product listing thumbnail: {reason}",
        )

    # ── Step 1: Load knowledge from DB ────────────────────────────────────
    result = await internal_db.execute(
        text("SELECT target_audience, patterns FROM thumbnail_knowledge WHERE product_type = :pt"),
        {"pt": product_type},
    )
    knowledge_rows = result.fetchall()

    if not knowledge_rows:
        raise HTTPException(
            status_code=404,
            detail=f"Chưa có knowledge cho product_type='{product_type}'. "
                   "Hãy chạy /thumbnail-knowledge/generate trước.",
        )

    knowledge_context = "\n\n".join(
        f"=== Segment: {row.target_audience} ===\n{json.dumps(row.patterns, indent=2)}"
        for row in knowledge_rows
    )
    segments_list = [row.target_audience for row in knowledge_rows]

    # ── Step 2: Extract rich features from image (Tier 1) ─────────────────
    features = await _extract_features_from_bytes(image_bytes, image_media_type, product_type)

    # ── Step 2b: ML score (LightGBM) ──────────────────────────────────────
    ml_score = thumbnail_ml_service.score_features(features.model_dump())

    # ── Step 3: Build Gemini scoring prompt using features + knowledge ─────
    criteria_str = "\n".join(f"- {c}" for c in RUBRIC_CRITERIA)
    features_summary = json.dumps({
        "subject": features.subject,
        "subject_colors": features.subject_colors,
        "background_type": features.background_type,
        "theme": features.theme,
        "composition": features.composition,
        "seasonal_type": features.seasonal_type,
        "text_overlay": features.text_overlay,
        "overall_mood": features.overall_mood,
        "decoration_technique": features.decoration_technique,
        "fabric_material": features.fabric_material,
    }, indent=2)

    eval_prompt = (
        f"You are an expert Etsy thumbnail evaluator for product type: '{product_type}'.\n\n"
        "## Extracted Image Features\n"
        f"{features_summary}\n\n"
        "## Step 1 — Detect Target Audience\n"
        f"Available segments: {segments_list}\n"
        "Pick the closest matching segment, or 'general' if none fit.\n\n"
        "## Step 2 — Score 9 criteria (1-10 each)\n"
        "Use the knowledge base patterns below as benchmark.\n\n"
        f"## Knowledge Base\n{knowledge_context}\n\n"
        f"## Criteria:\n{criteria_str}\n\n"
        "## Output (JSON ONLY, no markdown fences):\n"
        "{\n"
        '  "target_audience": "detected segment",\n'
        '  "overall": <float 1-10>,\n'
        '  "scores": {\n'
        '    "resolution_sharpness": {"score": <float>, "comment": "<string>"},\n'
        '    "visual_clarity": {"score": <float>, "comment": "<string>"},\n'
        '    "background_quality": {"score": <float>, "comment": "<string>"},\n'
        '    "product_focus": {"score": <float>, "comment": "<string>"},\n'
        '    "text_overlay_readability": {"score": <float>, "comment": "<string>"},\n'
        '    "theme_mood_consistency": {"score": <float>, "comment": "<string>"},\n'
        '    "color_palette_fit": {"score": <float>, "comment": "<string>"},\n'
        '    "target_audience_fit": {"score": <float>, "comment": "<string>"},\n'
        '    "lifestyle_context": {"score": <float>, "comment": "<string>"}\n'
        "  },\n"
        '  "strengths": ["strength1", "strength2"],\n'
        '  "suggestions": ["suggestion1", "suggestion2"]\n'
        "}"
    )

    # Send prompt-only (features already extracted above)
    try:
        raw = await _generate_with_fallback([eval_prompt])
    except Exception as exc:
        logger.error("Gemini evaluate call failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Gemini vision call failed: {exc}")

    try:
        data = _extract_json(raw)
    except Exception as exc:
        logger.error("Failed to parse evaluation response: %s | raw: %s", exc, raw[:500])
        raise HTTPException(status_code=502, detail="Gemini returned invalid JSON during evaluation.")

    # ── Step 4: Parse into ThumbnailEvalResponse ──────────────────────────
    scores_raw = data.get("scores", {})
    scores: dict[str, CriterionScore] = {}
    for criterion in RUBRIC_CRITERIA:
        entry = scores_raw.get(criterion, {"score": 5.0, "comment": "N/A"})
        scores[criterion] = CriterionScore(
            score=float(entry.get("score", 5.0)),
            comment=str(entry.get("comment", "")),
        )

    overall = float(data.get("overall", sum(s.score for s in scores.values()) / len(scores)))

    return ThumbnailEvalResponse(
        product_type=product_type,
        target_audience=str(data.get("target_audience", "general")),
        overall=round(overall, 2),
        scores=scores,
        strengths=data.get("strengths", []),
        suggestions=data.get("suggestions", []),
        features=features,
        ml_score=ml_score,
    )
