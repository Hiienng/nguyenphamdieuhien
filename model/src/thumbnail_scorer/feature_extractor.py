"""
feature_extractor.py — Convert raw ThumbnailFeatures DB rows into a numpy feature matrix.

All categoricals are label-encoded with a fixed vocabulary so the mapping is stable
across training and inference. Unknown values map to 0.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Fixed vocabularies — ORDER MATTERS (determines column indices)
# ---------------------------------------------------------------------------

BACKGROUND_TYPE = ["white_studio", "lifestyle", "gradient", "texture", "outdoor", "flat_lay", "other"]
COMPOSITION     = ["centered", "flat_lay", "close_up", "editorial", "angled", "hanging"]
DECORATION_TECH = ["embroidery", "print", "heat_transfer", "applique", "none"]
SEASONAL_TYPE   = ["christmas", "halloween", "easter", "valentines", "non_seasonal"]
OVERALL_MOOD    = ["warm", "minimal", "playful", "elegant", "rustic", "vibrant", "whimsical", "neutral", "other"]
FABRIC_MATERIAL = ["cotton", "fleece", "knit", "polyester", "waffle", "linen", "velvet", "none", "other"]
IMAGE_BRIGHTNESS   = ["dark", "medium", "bright"]
IMAGE_CONTRAST     = ["low", "medium", "high"]
COLOR_HARMONY      = ["monochromatic", "analogous", "complementary", "triadic", "neutral"]
BACKGROUND_CLUTTER = ["clean", "minimal", "moderate", "busy"]
PRODUCT_VISIBILITY = ["full", "partial", "close_up", "multiple_angles"]
PRODUCT_SIZE       = ["small", "medium", "large", "fills_frame"]
GENDER_SIGNAL      = ["neutral", "feminine", "masculine"]
AGE_TARGET         = ["newborn", "infant", "toddler", "adult", "unknown"]
OCCASION_SIGNAL    = ["everyday", "gift", "seasonal", "hospital", "announcement"]
STYLE_AESTHETIC    = ["modern", "rustic", "boho", "classic", "whimsical", "minimal"]
PRODUCT_TYPE       = ["onesie", "crown", "blanket", "sweater", "other"]

VOCAB = {
    "background_type":       BACKGROUND_TYPE,
    "composition":           COMPOSITION,
    "decoration_technique":  DECORATION_TECH,
    "seasonal_type":         SEASONAL_TYPE,
    "overall_mood":          OVERALL_MOOD,
    "fabric_material":       FABRIC_MATERIAL,
    "image_brightness":      IMAGE_BRIGHTNESS,
    "image_contrast":        IMAGE_CONTRAST,
    "color_harmony":         COLOR_HARMONY,
    "background_clutter":    BACKGROUND_CLUTTER,
    "product_visibility":    PRODUCT_VISIBILITY,
    "product_size_in_frame": PRODUCT_SIZE,
    "gender_signal":         GENDER_SIGNAL,
    "age_target":            AGE_TARGET,
    "occasion_signal":       OCCASION_SIGNAL,
    "style_aesthetic":       STYLE_AESTHETIC,
    "product_type":          PRODUCT_TYPE,
}

BOOLEAN_COLS = [
    "text_overlay",
    "personalization_visible",
    "gift_cue_visible",
    "size_reference",
]

NUMERIC_COLS = [
    "color_count",          # 1-6
]

# Derived features computed from list columns
# (lifestyle_props, subject_colors, decoration_colors)
DERIVED_COLS = [
    "lifestyle_prop_count",   # len(lifestyle_props)
    "subject_color_count",    # len(subject_colors)
    "decoration_color_count", # len(decoration_colors)
    "has_lifestyle_props",    # lifestyle_prop_count > 0
    "is_seasonal",            # seasonal_type != 'non_seasonal'
    "has_decoration",         # decoration_technique not in (none, null)
    "has_personalization",    # personalization_visible OR 'name' in decoration_object
]

# Final feature names in order (used to build FEATURE_NAMES constant)
def build_feature_names() -> list[str]:
    names = []
    for col, vocab in VOCAB.items():
        names.append(col + "_enc")
    names.extend(BOOLEAN_COLS)
    names.extend(NUMERIC_COLS)
    names.extend(DERIVED_COLS)
    return names

FEATURE_NAMES = build_feature_names()
N_FEATURES = len(FEATURE_NAMES)


def _label_encode(value: str | None, vocab: list[str]) -> int:
    if value is None:
        return 0
    v = str(value).lower().strip()
    for i, w in enumerate(vocab):
        if w in v or v in w:
            return i + 1  # 1-indexed; 0 = unknown
    return 0


def row_to_vector(row: dict) -> np.ndarray:
    """Convert a single feature dict (from DB row or Pydantic model) to a 1D float32 array."""
    vec = []

    # Categorical label encodings
    for col, vocab in VOCAB.items():
        vec.append(_label_encode(row.get(col), vocab))

    # Booleans
    for col in BOOLEAN_COLS:
        vec.append(int(bool(row.get(col, False))))

    # Numerics
    for col in NUMERIC_COLS:
        v = row.get(col)
        vec.append(float(v) if v is not None else 2.0)  # median fallback

    # Derived
    lifestyle_props = row.get("lifestyle_props") or []
    subject_colors  = row.get("subject_colors") or []
    deco_colors     = row.get("decoration_colors") or []
    deco_object     = str(row.get("decoration_object") or "").lower()
    deco_tech       = str(row.get("decoration_technique") or "none").lower()
    seasonal        = str(row.get("seasonal_type") or "non_seasonal").lower()
    personalization = bool(row.get("personalization_visible", False))

    lp_count = len(lifestyle_props) if isinstance(lifestyle_props, list) else 0
    sc_count = len(subject_colors) if isinstance(subject_colors, list) else 0
    dc_count = len(deco_colors) if isinstance(deco_colors, list) else 0

    vec.append(lp_count)
    vec.append(sc_count)
    vec.append(dc_count)
    vec.append(int(lp_count > 0))
    vec.append(int(seasonal != "non_seasonal"))
    vec.append(int(deco_tech not in ("none", "")))
    vec.append(int(personalization or "name" in deco_object or "custom" in deco_object))

    return np.array(vec, dtype=np.float32)


def rows_to_matrix(rows: list[dict]) -> np.ndarray:
    """Convert a list of feature dicts to a 2D matrix (n_samples, N_FEATURES)."""
    return np.vstack([row_to_vector(r) for r in rows])
