"""Representation routing tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evaluation.model_evaluator import MODEL_REPRESENTATION  # noqa: E402


def test_representation_map():
    assert MODEL_REPRESENTATION["logistic_regression_hybrid"] == "hybrid"
    assert MODEL_REPRESENTATION["logistic_regression_text"] == "text"
    assert MODEL_REPRESENTATION["logistic_regression_behavior"] == "behavior_scaled"
    assert MODEL_REPRESENTATION["linear_svm_hybrid"] == "hybrid"
    assert MODEL_REPRESENTATION["multinomial_nb_text"] == "text"
    assert MODEL_REPRESENTATION["random_forest_behavior"] == "behavior_raw"
