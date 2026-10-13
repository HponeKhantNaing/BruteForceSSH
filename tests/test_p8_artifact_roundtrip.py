"""Artifact round-trip tests against real P8 outputs (after --train)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

MODELS = [
    "logistic_regression_hybrid",
    "logistic_regression_text",
    "logistic_regression_behavior",
    "linear_svm_hybrid",
    "multinomial_nb_text",
    "random_forest_behavior",
]


@pytest.fixture(scope="module")
def trained():
    prep = ROOT / "artifacts/p8/preprocessing"
    models = ROOT / "artifacts/p8/models"
    if not (prep / "tfidf_vectorizer.joblib").is_file():
        pytest.skip("P8 artifacts not trained yet")
    return prep, models


def test_tfidf_reload(trained):
    prep, _ = trained
    payload = joblib.load(prep / "tfidf_vectorizer.joblib")
    assert payload["fit_scope"] == "TRAIN_ONLY"
    vec = payload["vectorizer"]
    X = vec.transform(["failed password for <USER> from <IP> port <PORT> ssh2"])
    assert X.shape[1] == len(vec.vocabulary_)


def test_scaler_reload(trained):
    prep, _ = trained
    payload = joblib.load(prep / "behavior_scaler.joblib")
    assert payload["fit_scope"] == "TRAIN_ONLY"
    order = json.loads((prep / "behavior_feature_order.json").read_text())["feature_order"]
    X = np.zeros((1, len(order)))
    _ = payload["scaler"].transform(X)


def test_models_reload(trained):
    _, models = trained
    for mid in MODELS:
        path = models / f"{mid}.joblib"
        assert path.is_file()
        payload = joblib.load(path)
        assert payload["test_metrics_computed"] is False
        assert payload["fit_scope"] == "TRAIN_ONLY"
        assert set(payload["classes"]) == {"NORMAL", "SUSPICIOUS", "BRUTE_FORCE"}
