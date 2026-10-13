"""Train-only TF-IDF and scaler tests."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from training.preprocessing import fit_scaler_train_only, fit_tfidf_train_only  # noqa: E402


def test_tfidf_excludes_test_only_token():
    cfg = {
        "text_features": {
            "lowercase": True,
            "ngram_range": {"min": 1, "max": 1},
            "min_df": 1,
            "max_df": 1.0,
            "max_features": 1000,
            "sublinear_tf": True,
            "norm": "l2",
        }
    }
    train = ["failed password for user"]
    test_only = "super_secret_test_token"
    vec = fit_tfidf_train_only(train, cfg)
    assert "super_secret_test_token" not in vec.vocabulary_
    # transform test text must not add token to vocabulary
    _ = vec.transform([f"failed password {test_only}"])
    assert "super_secret_test_token" not in vec.vocabulary_


def test_scaler_uses_train_mean_only():
    X_train = np.array([[1.0], [3.0], [5.0]])
    X_test = np.array([[1000.0]])
    scaler = fit_scaler_train_only(X_train)
    assert np.isclose(scaler.mean_[0], 3.0)
    # Fitting on all would yield different mean
    all_mean = np.mean(np.vstack([X_train, X_test]))
    assert not np.isclose(scaler.mean_[0], all_mean)
