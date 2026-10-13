"""P10 source integrity against frozen P9/P8 selection."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from export.p10_export import load_yaml, validate_source  # noqa: E402


def test_p9_selected_model_is_rf_behavior():
    cfg = load_yaml(ROOT / "config" / "p10_export.yaml")
    result = validate_source(ROOT, cfg)
    assert result["ok"] is True
    assert result["selected_model_id"] == "random_forest_behavior"
    assert result["selected_representation"] == "behavior_raw"
    assert result["source_artifact_sha256"] == result["p9_selected_sha256"]
    assert result["source_artifact_sha256"] == result["p8_checksum_sha256"]
    assert result["checks"]["test_models_count_1"] is True
    assert result["checks"]["p9_fit_calls_0"] is True
    assert result["checks"]["lock_before_test"] is True
