"""P8 leakage guards."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def test_real_split_no_scenario_overlap():
    path = ROOT / "data/modeling/p8/split_manifest.json"
    if not path.is_file():
        pytest.skip("split not created")
    split = json.loads(path.read_text())
    for a, b in (("train", "validation"), ("train", "test"), ("validation", "test")):
        assert set(split[a]["scenario_ids"]).isdisjoint(set(split[b]["scenario_ids"]))
        assert set(split[a]["sample_ids"]).isdisjoint(set(split[b]["sample_ids"]))


def test_leakage_audit_pass():
    path = ROOT / "data/modeling/p8/leakage_audit.json"
    if not path.is_file():
        pytest.skip("training not done")
    audit = json.loads(path.read_text())
    assert audit["pass"] is True
    assert audit["sample_overlap"] == 0
    assert audit["scenario_overlap"] == 0
    assert audit["test_used_for_fit"] is False
    assert audit["test_metrics_computed"] is False


def test_no_target_keys_in_features():
    from training.p8_training import load_aligned_p7, load_yaml

    cfg = load_yaml(ROOT / "config" / "p8_training.yaml")
    data = load_aligned_p7(ROOT, cfg)
    for sid, row in data["behavioral"].items():
        keys = set(row["features"])
        assert "target_label" not in keys
        assert "scenario_id" not in keys
        assert "collection_phase" not in keys
