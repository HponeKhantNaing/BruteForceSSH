"""P7 leakage guards."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from features.p7_feature_engineering import FORBIDDEN_FEATURE_KEYS, build_features, load_yaml  # noqa: E402


def test_text_and_numeric_leakage():
    cfg = load_yaml(ROOT / "config" / "p7_features.yaml")
    result = build_features(ROOT, cfg, write=False)
    assert result["leakage_audit"]["pass"] is True
    for row in result["behavioral_rows"]:
        keys = set(row["features"])
        assert keys.isdisjoint(FORBIDDEN_FEATURE_KEYS)
        assert "target_label" not in keys
        assert "scenario_id" not in keys
    for row in result["text_rows"]:
        text = row["canonical_text"]
        assert "BRUTE_FORCE" not in text
        assert "testuser" not in text
        assert "172.18.0.1" not in text
        assert "data/raw/" not in text


def test_n06_target_not_feature():
    cfg = load_yaml(ROOT / "config" / "p7_features.yaml")
    result = build_features(ROOT, cfg, write=False)
    n06_targets = [t for t in result["target_rows"] if t["scenario_id"] == "N06_ISOLATED_PASSWORD_MISTAKE"]
    assert n06_targets
    for t in n06_targets:
        assert t["target_label"] == "NORMAL"
        feat_row = next(r for r in result["behavioral_rows"] if r["sample_id"] == t["sample_id"])
        assert "target_label" not in feat_row["features"]
        assert feat_row["features"]["failed_attempts"] == 1
        assert feat_row["features"]["successful_attempts"] == 1
        assert feat_row["features"]["success_after_failure"] == 1
