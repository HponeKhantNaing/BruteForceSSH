"""P9 leakage / no-fit guards."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evaluation.model_evaluator import FitCallError, FrozenArtifactBundle  # noqa: E402
from evaluation.p9_evaluation import load_yaml  # noqa: E402


def test_fit_blocked_on_vectorizer():
    cfg = load_yaml(ROOT / "config" / "p9_evaluation.yaml")
    bundle = FrozenArtifactBundle(ROOT, cfg)
    with pytest.raises(FitCallError):
        bundle.vectorizer.fit(["dummy text"])
    assert bundle.fit_calls >= 1


def test_no_forbidden_feature_keys():
    cfg = load_yaml(ROOT / "config" / "p9_evaluation.yaml")
    bundle = FrozenArtifactBundle(ROOT, cfg)
    for row in bundle.behavioral.values():
        keys = set(row["features"])
        assert "target_label" not in keys
        assert "scenario_id" not in keys
        assert "raw_log_path" not in keys
