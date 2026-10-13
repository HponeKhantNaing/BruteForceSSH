"""P10 bundle load + no scaler/TF-IDF/refit."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from realtime.model_runtime import ModelRuntime  # noqa: E402
from realtime.p11_monitor import load_yaml  # noqa: E402


def test_model_runtime_loads_frozen_rf():
    cfg = load_yaml(ROOT / "config" / "p11_realtime.yaml")
    rt = ModelRuntime(
        ROOT / cfg["release"]["root"],
        expected_sha256=cfg["release"]["expected_model_sha256"],
    )
    loaded = rt.verify_and_load()
    assert loaded["ok"] is True
    assert loaded["release_id"] == "rf-behavior-lab-v1.0.0"
    assert loaded["feature_count"] == 22
    assert list(rt.model.classes_) == ["BRUTE_FORCE", "NORMAL", "SUSPICIOUS"]
    assert rt.contract["scaling_required"] is False
    assert rt.contract["tfidf_required"] is False
