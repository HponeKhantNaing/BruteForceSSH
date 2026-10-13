"""Model factory / representation tests."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy import sparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from training.model_factory import build_model  # noqa: E402


def test_models_fit_compatible_inputs():
    y = np.array(["NORMAL", "SUSPICIOUS", "BRUTE_FORCE", "NORMAL", "SUSPICIOUS", "BRUTE_FORCE"])
    X_text = sparse.csr_matrix(np.random.RandomState(0).rand(6, 10))
    X_beh = np.random.RandomState(1).rand(6, 5)
    X_beh_s = X_beh - X_beh.mean(axis=0)
    X_hyb = sparse.hstack([X_text, sparse.csr_matrix(X_beh_s)], format="csr")

    cfg = {
        "models": {
            "logistic_regression_hybrid": {"C": 1.0, "max_iter": 500},
            "logistic_regression_text": {"C": 1.0, "max_iter": 500},
            "logistic_regression_behavior": {"C": 1.0, "max_iter": 500},
            "linear_svm_hybrid": {"C": 1.0, "max_iter": 500},
            "multinomial_nb_text": {"alpha": 1.0},
            "random_forest_behavior": {"n_estimators": 10, "max_depth": 3, "min_samples_leaf": 1},
        }
    }
    build_model("logistic_regression_hybrid", cfg).fit(X_hyb, y)
    build_model("logistic_regression_text", cfg).fit(X_text, y)
    build_model("logistic_regression_behavior", cfg).fit(X_beh_s, y)
    build_model("linear_svm_hybrid", cfg).fit(X_hyb, y)
    build_model("multinomial_nb_text", cfg).fit(X_text, y)  # non-negative
    build_model("random_forest_behavior", cfg).fit(X_beh, y)


def test_nb_rejects_concept_of_scaled_negative():
    # Documented: NB uses text TF-IDF only (non-negative)
    X_text = sparse.csr_matrix([[0.1, 0.2], [0.3, 0.0], [0.0, 0.4]])
    y = np.array(["NORMAL", "SUSPICIOUS", "BRUTE_FORCE"])
    model = build_model("multinomial_nb_text", {"models": {"multinomial_nb_text": {"alpha": 1.0}}})
    model.fit(X_text, y)
    assert X_text.min() >= 0
