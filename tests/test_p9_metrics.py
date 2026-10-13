"""Metric computation unit tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evaluation.metrics import compute_classification_metrics  # noqa: E402


def test_perfect_scores():
    y = ["NORMAL", "SUSPICIOUS", "BRUTE_FORCE"] * 2
    m = compute_classification_metrics(y, y)
    assert m["accuracy"] == 1.0
    assert m["macro_f1"] == 1.0
    assert m["correct_count"] == 6


def test_known_confusion():
    y_true = ["NORMAL", "NORMAL", "SUSPICIOUS", "BRUTE_FORCE"]
    y_pred = ["NORMAL", "SUSPICIOUS", "SUSPICIOUS", "BRUTE_FORCE"]
    m = compute_classification_metrics(y_true, y_pred)
    assert m["correct_count"] == 3
    assert m["total_count"] == 4
    assert m["per_class"]["NORMAL"]["correct"] == 1
    assert m["per_class"]["NORMAL"]["support"] == 2
    assert m["confusion_matrix"]["class_order"] == ["NORMAL", "SUSPICIOUS", "BRUTE_FORCE"]
