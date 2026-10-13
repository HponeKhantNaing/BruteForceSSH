"""Scenario-group splitter tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from training.splitter import build_scenario_split  # noqa: E402


def _targets():
    rows = []
    for sc, lab, n in [
        ("N01", "NORMAL", 2),
        ("N02", "NORMAL", 2),
        ("N03", "NORMAL", 2),
        ("S01", "SUSPICIOUS", 2),
        ("S02", "SUSPICIOUS", 2),
        ("S03", "SUSPICIOUS", 2),
        ("B01", "BRUTE_FORCE", 2),
        ("B02", "BRUTE_FORCE", 2),
        ("B03", "BRUTE_FORCE", 2),
    ]:
        for i in range(n):
            rows.append(
                {
                    "sample_id": f"P6_{sc}_{i}",
                    "scenario_id": sc,
                    "target_label": lab,
                    "split_group_batch": "BATCH",
                }
            )
    return rows


def test_scenario_never_crosses_splits():
    split = build_scenario_split(_targets(), seed=42)
    for a, b in (
        ("train", "validation"),
        ("train", "test"),
        ("validation", "test"),
    ):
        assert set(split[a]["scenario_ids"]).isdisjoint(set(split[b]["scenario_ids"]))
        assert set(split[a]["sample_ids"]).isdisjoint(set(split[b]["sample_ids"]))


def test_deterministic_split():
    a = build_scenario_split(_targets(), seed=42)
    b = build_scenario_split(_targets(), seed=42)
    assert a == b


def test_class_coverage():
    split = build_scenario_split(_targets(), seed=42)
    for part in ("train", "validation", "test"):
        for lab in ("NORMAL", "SUSPICIOUS", "BRUTE_FORCE"):
            assert split[part]["class_counts"].get(lab, 0) >= 1
