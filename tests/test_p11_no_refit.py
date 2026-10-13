"""P11 must never fit / partial_fit the frozen model."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from realtime.model_runtime import ModelRuntime  # noqa: E402
from realtime.p11_monitor import load_yaml  # noqa: E402


def test_no_refit_on_predict():
    cfg = load_yaml(ROOT / "config" / "p11_realtime.yaml")
    release = ROOT / cfg["release"]["root"]
    smoke = json.loads((release / "verification/smoke_test_input.json").read_text())
    rt = ModelRuntime(release, expected_sha256=cfg["release"]["expected_model_sha256"])
    assert rt.verify_and_load()["ok"]
    with pytest.raises(RuntimeError, match="forbid fit"):
        rt.model.fit([[0.0] * 22], ["NORMAL"])
    pred = rt.predict_features(smoke["features"])
    assert pred["ok"]
    assert rt.fit_calls == 1  # the blocked fit attempt counted
    assert rt.tfidf_used is False
    assert rt.scaler_used is False
