"""P6 external supervised data guard."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from preprocessing.p6_preprocessing import (  # noqa: E402
    build_dataset,
    load_yaml,
    validate_p5_external_policy,
)


def test_p5_registry_dispositions():
    reg = json.loads((ROOT / "data/external/p5/registry.json").read_text())
    cfg = load_yaml(ROOT / "config" / "p6_preprocessing.yaml")
    result = validate_p5_external_policy(reg, cfg["external_supervised_data"]["expected_dispositions"])
    assert result["ok"], result["errors"]


def test_zero_public_supervised_records():
    cfg = load_yaml(ROOT / "config" / "p6_preprocessing.yaml")
    assert cfg["external_supervised_data"]["enabled"] is False
    built = build_dataset(ROOT, cfg, write=False)
    assert built["quality"]["public_supervised_records"] == 0
    assert built["dataset_manifest"]["external_supervised_data_included"] is False
    for r in built["canonical_runs"]:
        assert r.get("data_source") == "local_lab"
        assert not str(r.get("run_id", "")).startswith("loghub")
        assert "cicids" not in str(r.get("run_id", "")).lower()
        assert "cam_lds" not in str(r.get("run_id", "")).lower()
