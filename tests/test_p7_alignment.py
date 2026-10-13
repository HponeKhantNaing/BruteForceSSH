"""Sample alignment across behavior/text/targets."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from features.p7_feature_engineering import build_features, load_yaml  # noqa: E402


def test_alignment_equals_p6():
    cfg = load_yaml(ROOT / "config" / "p7_features.yaml")
    result = build_features(ROOT, cfg, write=False)
    assert result["ok"]
    a = result["alignment"]
    assert a["aligned"] is True
    assert a["behavior_count"] == a["text_count"] == a["target_count"] == a["p6_sample_count"]
    assert a["duplicates_behavior"] == 0
    assert not a["missing_from_behavior"]
