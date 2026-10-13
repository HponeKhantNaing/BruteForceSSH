"""P6 leakage guards for canonical text."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from preprocessing.p6_preprocessing import build_dataset, load_yaml  # noqa: E402


@pytest.fixture(scope="module")
def built():
    cfg = load_yaml(ROOT / "config" / "p6_preprocessing.yaml")
    return build_dataset(ROOT, cfg, write=False)


def test_no_metadata_leakage_in_canonical_text(built):
    assert built["dataset_manifest"]["leakage_guard_hits"] == []
    for seq in built["canonical_sequences"]:
        text = seq["canonical_text"]
        assert "BRUTE_FORCE" not in text
        assert "SUSPICIOUS" not in text
        assert "NORMAL" not in text
        assert "data/raw/" not in text
        assert "brute_force" not in text.lower() or "brute_force" not in text  # path-style
        # collection phase tokens as standalone
        for tok in ("P2", "P3"):
            assert tok not in text.split()
        assert "testuser" not in text
        assert "172.18.0.1" not in text


def test_n06_label_unchanged(built):
    n06 = [r for r in built["canonical_runs"] if r["scenario_id"] == "N06_ISOLATED_PASSWORD_MISTAKE"]
    assert n06
    for r in n06:
        assert r["target_label"] == "NORMAL"
        fails = sum(
            1
            for a in built["canonical_attempts"]
            if a["run_id"] == r["run_id"] and a["outcome"] == "FAILURE"
        )
        succs = sum(
            1
            for a in built["canonical_attempts"]
            if a["run_id"] == r["run_id"] and a["outcome"] == "SUCCESS"
        )
        assert fails == 1
        assert succs == 1
