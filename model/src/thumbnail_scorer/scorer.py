"""
scorer.py — Load trained LightGBM model and predict ML score for a feature dict.

Returns proba(label=1) — probability the thumbnail is Bestseller/Popular quality.
Score range: 0.0 – 1.0
"""
from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import numpy as np

from .feature_extractor import row_to_vector

MODEL_PATH = Path(__file__).resolve().parents[3] / "checkpoints" / "thumbnail_scorer.pkl"

_model_cache: dict[str, Any] = {}


def _load_model() -> Any:
    if "model" not in _model_cache:
        if not MODEL_PATH.exists():
            return None
        with open(MODEL_PATH, "rb") as f:
            payload = pickle.load(f)
        _model_cache["model"] = payload["model"]
        _model_cache["meta"] = payload.get("meta", {})
    return _model_cache["model"]


def predict_score(feature_dict: dict) -> float | None:
    """
    Returns ML score 0–1, or None if model not available.
    feature_dict: dict with same keys as ThumbnailFeatures fields.
    """
    model = _load_model()
    if model is None:
        return None
    vec = row_to_vector(feature_dict).reshape(1, -1)
    proba = model.predict_proba(vec)[0][1]
    return round(float(proba), 4)


def get_model_meta() -> dict:
    _load_model()
    return _model_cache.get("meta", {})


def reload_model() -> None:
    """Force reload from disk (call after re-training)."""
    _model_cache.clear()
