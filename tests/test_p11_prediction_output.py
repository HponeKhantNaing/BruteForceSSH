"""Prediction output mapping uses model.classes_; release_id stamped."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from realtime.model_runtime import ModelRuntime  # noqa: E402
from realtime.p11_monitor import load_yaml  # noqa: E402


def test_probability_mapping_and_uncalibrated():
    cfg = load_yaml(ROOT / "config" / "p11_realtime.yaml")
    release = ROOT / cfg["release"]["root"]
    smoke = json.loads((release / "verification/smoke_test_input.json").read_text())
    rt = ModelRuntime(release, expected_sha256=cfg["release"]["expected_model_sha256"])
    assert rt.verify_and_load()["ok"]
    pred = rt.predict_features(smoke["features"])
    assert pred["ok"]
    assert pred["release_id"] == "rf-behavior-lab-v1.0.0"
    assert pred["probability_type"] == "uncalibrated"
    assert set(pred["class_probabilities"]) == {"NORMAL", "SUSPICIOUS", "BRUTE_FORCE"}
    assert abs(sum(pred["class_probabilities"].values()) - 1.0) < 1e-6
    assert pred["predicted_label"] in pred["class_probabilities"]
