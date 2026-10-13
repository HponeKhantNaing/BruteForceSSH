"""Offline smoke inference + source/release parity."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from export.bundle_validator import load_estimator, predict_from_features  # noqa: E402
from export.p10_export import load_yaml, smoke_test_release  # noqa: E402


def test_smoke_inference_and_parity():
    cfg = load_yaml(ROOT / "config" / "p10_export.yaml")
    out = smoke_test_release(ROOT, cfg)
    assert out["ok"] is True
    assert out["live_logs"] is False
    assert out["discord"] is False

    release_id = cfg["release"]["release_id"]
    release = ROOT / cfg["paths"]["releases_root"] / release_id
    manifest = json.loads((release / "MANIFEST.json").read_text())
    contract = json.loads((release / "schema/feature_contract.json").read_text())
    smoke = json.loads((release / "verification/smoke_test_input.json").read_text())
    expected = json.loads((release / "verification/smoke_test_expected.json").read_text())

    source_model = joblib.load(ROOT / "artifacts/p8/models/random_forest_behavior.joblib")["model"]
    release_model, _ = load_estimator(release / "model" / "random_forest_behavior.joblib")

    # Instrument fit
    for model in (source_model, release_model):
        def blocked(*_a, **_k):
            raise AssertionError("fit called")

        model.fit = blocked

    src_pred = predict_from_features(
        source_model,
        smoke["features"],
        contract["ordered_features"],
        model_version=manifest["release_id"],
        class_order=manifest["class_labels"],
    )
    rel_pred = predict_from_features(
        release_model,
        smoke["features"],
        contract["ordered_features"],
        model_version=manifest["release_id"],
        class_order=manifest["class_labels"],
    )
    assert src_pred["predicted_label"] == rel_pred["predicted_label"] == expected["predicted_label"]
    assert np.allclose(
        src_pred["probability_vector_in_model_class_order"],
        rel_pred["probability_vector_in_model_class_order"],
    )
    assert rel_pred["probability_type"] == "uncalibrated"
