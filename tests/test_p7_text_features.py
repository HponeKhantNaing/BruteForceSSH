"""TF-IDF factory remains unfitted in P7."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from features.p7_feature_engineering import load_yaml  # noqa: E402
from features.text_features import (  # noqa: E402
    build_numeric_scaler,
    build_tfidf_vectorizer,
    is_scaler_fitted,
    is_vectorizer_fitted,
)


def test_tfidf_unfitted():
    cfg = load_yaml(ROOT / "config" / "p7_features.yaml")
    vec = build_tfidf_vectorizer(cfg)
    assert not is_vectorizer_fitted(vec)
    assert not hasattr(vec, "vocabulary_") or vec.vocabulary_ is None
    assert cfg["text_features"]["fitted_in_p7"] is False


def test_scaler_unfitted():
    cfg = load_yaml(ROOT / "config" / "p7_features.yaml")
    scaler = build_numeric_scaler(cfg)
    assert not is_scaler_fitted(scaler)
