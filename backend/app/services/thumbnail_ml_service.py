"""
thumbnail_ml_service.py — Bridge between backend and the LightGBM scorer in model/.

Loads scorer lazily; returns None if model file not yet trained.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Add model/ root to path so scorer can import feature_extractor
_MODEL_ROOT = Path(__file__).resolve().parents[4] / "model"
if str(_MODEL_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODEL_ROOT))


def _get_scorer():
    try:
        from src.thumbnail_scorer.scorer import predict_score, reload_model, get_model_meta
        return predict_score, reload_model, get_model_meta
    except ImportError as e:
        logger.warning("thumbnail_scorer not importable: %s", e)
        return None, None, None


def score_features(feature_dict: dict) -> float | None:
    """
    Convert a ThumbnailFeatures Pydantic model (or dict) to ML score 0–1.
    Returns None if model not yet trained or import fails.
    """
    predict_score, _, _ = _get_scorer()
    if predict_score is None:
        return None
    try:
        return predict_score(feature_dict)
    except Exception as exc:
        logger.warning("ML scoring failed: %s", exc)
        return None


def reload_model() -> None:
    _, reload, _ = _get_scorer()
    if reload:
        reload()


def get_model_meta() -> dict:
    _, _, meta_fn = _get_scorer()
    if meta_fn:
        return meta_fn()
    return {}
