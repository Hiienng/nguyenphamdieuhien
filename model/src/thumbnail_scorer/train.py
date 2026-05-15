"""
train.py — Train LightGBM binary classifier on thumbnail_features.

Label:
  ml_label = 1  → Bestseller / Popular now (market-validated thumbnails)
  ml_label = 0  → unlabelled / other

Usage:
  cd model
  python -m src.thumbnail_scorer.train
  # saves model to checkpoints/thumbnail_scorer.pkl
"""
from __future__ import annotations

import json
import os
import pickle
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import psycopg2
import psycopg2.extras
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import roc_auc_score

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from model.src.thumbnail_scorer.feature_extractor import rows_to_matrix, FEATURE_NAMES

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_AojWpVq4sC9z@ep-crimson-mouse-aoigj44f-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
)
CHECKPOINT_DIR = Path(__file__).resolve().parents[3] / "model" / "checkpoints"
MODEL_PATH = CHECKPOINT_DIR / "thumbnail_scorer.pkl"


def load_training_data() -> tuple[np.ndarray, np.ndarray]:
    """Load thumbnail_features rows with ml_label IS NOT NULL from DB."""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            product_type, background_type, composition, decoration_technique,
            seasonal_type, overall_mood, fabric_material,
            image_brightness, image_contrast, color_harmony, color_count,
            background_clutter, product_visibility, product_size_in_frame,
            gender_signal, age_target, occasion_signal, style_aesthetic,
            text_overlay, personalization_visible, gift_cue_visible, size_reference,
            lifestyle_props, subject_colors, decoration_colors, decoration_object,
            ml_label
        FROM thumbnail_features
        WHERE ml_label IS NOT NULL
        ORDER BY id
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        raise ValueError("No labelled rows found in thumbnail_features (ml_label IS NOT NULL).")

    labels = np.array([int(r["ml_label"]) for r in rows], dtype=np.int32)
    features = rows_to_matrix([dict(r) for r in rows])
    return features, labels


def train(min_samples: int = 30) -> None:
    print("Loading training data...")
    X, y = load_training_data()
    n_pos = int(y.sum())
    n_neg = int((y == 0).sum())
    print(f"  Total: {len(y)} samples  |  pos(1)={n_pos}  neg(0)={n_neg}")

    if len(y) < min_samples:
        print(f"  ⚠ Only {len(y)} samples — need at least {min_samples} to train reliably.")
        print("  Run generate_knowledge for more product types first.")
        sys.exit(1)

    # Class imbalance: weight positives higher
    scale_pos_weight = n_neg / max(n_pos, 1)

    model = lgb.LGBMClassifier(
        objective="binary",
        metric="auc",
        n_estimators=200,
        learning_rate=0.05,
        num_leaves=15,          # small — avoids overfit on small dataset
        min_child_samples=5,
        scale_pos_weight=scale_pos_weight,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbose=-1,
    )

    # Cross-validation
    cv = StratifiedKFold(n_splits=min(5, n_pos), shuffle=True, random_state=42)
    cv_scores = cross_val_score(model, X, y, cv=cv, scoring="roc_auc")
    print(f"  CV AUC: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

    # Final fit on all data
    model.fit(X, y)

    # Feature importance
    importances = sorted(
        zip(FEATURE_NAMES, model.feature_importances_),
        key=lambda x: x[1], reverse=True
    )
    print("\n  Top 10 features:")
    for name, imp in importances[:10]:
        print(f"    {name:<35} {imp:.0f}")

    # Save
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    meta = {
        "n_samples": len(y),
        "n_pos": n_pos,
        "n_neg": n_neg,
        "cv_auc_mean": float(cv_scores.mean()),
        "cv_auc_std": float(cv_scores.std()),
        "feature_names": FEATURE_NAMES,
    }
    with open(MODEL_PATH, "wb") as f:
        pickle.dump({"model": model, "meta": meta}, f)

    meta_path = CHECKPOINT_DIR / "thumbnail_scorer_meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\n  ✓ Model saved to {MODEL_PATH}")
    print(f"  ✓ Meta saved to  {meta_path}")


if __name__ == "__main__":
    train()
