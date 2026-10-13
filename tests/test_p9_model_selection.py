"""Model selection policy tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evaluation.model_selector import select_model  # noqa: E402


def _m(macro_f1, min_r, bal, acc):
    return {
        "macro_f1": macro_f1,
        "minimum_class_recall": min_r,
        "balanced_accuracy": bal,
        "accuracy": acc,
    }


def test_highest_macro_f1_wins():
    metrics = {
        "logistic_regression_text": _m(0.5, 0.4, 0.5, 0.5),
        "logistic_regression_hybrid": _m(0.9, 0.5, 0.6, 0.6),
        "random_forest_behavior": _m(0.7, 0.7, 0.7, 0.7),
    }
    sel = select_model(metrics)
    assert sel["selected_model_id"] == "logistic_regression_hybrid"
    assert sel["tie_break_used"] is False


def test_tie_break_min_class_recall():
    metrics = {
        "logistic_regression_hybrid": _m(0.8, 0.4, 0.9, 0.9),
        "logistic_regression_behavior": _m(0.8, 0.8, 0.5, 0.5),
    }
    sel = select_model(metrics)
    assert sel["selected_model_id"] == "logistic_regression_behavior"
    assert sel["tie_break_used"] is True


def test_exact_tie_preference():
    metrics = {
        "linear_svm_hybrid": _m(0.7, 0.7, 0.7, 0.7),
        "logistic_regression_hybrid": _m(0.7, 0.7, 0.7, 0.7),
    }
    sel = select_model(metrics)
    assert sel["selected_model_id"] == "logistic_regression_hybrid"
