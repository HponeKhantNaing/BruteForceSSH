"""Tests for P4 integrity, exclusions, and determinism."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from labeling.p4_labeling import build_labels, load_policy  # noqa: E402


def test_smoke_excluded_by_default():
    policy = load_policy(ROOT / "config" / "p4_labeling_policy.yaml")
    built = build_labels(ROOT, policy, include_smoke=False)
    assert built.stats.get("exclusion_reason_counts", {}).get("smoke_excluded", 0) >= 1
    for r in built.run_labels:
        assert r["collection_role"] == "baseline"
        assert "SMOKE" not in (r.get("collection_batch_id") or "")


def test_baseline_counts_expected():
    policy = load_policy(ROOT / "config" / "p4_labeling_policy.yaml")
    built = build_labels(ROOT, policy, include_smoke=False)
    counts = built.stats.get("target_counts", {})
    assert counts.get("NORMAL") == 30
    assert counts.get("SUSPICIOUS") == 20
    assert counts.get("BRUTE_FORCE") == 25
    assert built.stats.get("eligible_primary_runs") == 75


def test_deterministic_build():
    policy = load_policy(ROOT / "config" / "p4_labeling_policy.yaml")
    a = build_labels(ROOT, policy, include_smoke=False)
    b = build_labels(ROOT, policy, include_smoke=False)
    ids_a = [r["sample_id"] for r in sorted(a.run_labels, key=lambda x: x["sample_id"])]
    ids_b = [r["sample_id"] for r in sorted(b.run_labels, key=lambda x: x["sample_id"])]
    assert ids_a == ids_b
    assert len(a.event_annotations) == len(b.event_annotations)


def test_checksum_mismatch_exclusion(tmp_path: Path):
    # Create a tiny fake tree with bad checksum
    policy = load_policy(ROOT / "config" / "p4_labeling_policy.yaml")
    # Use real data path but mutate a copy in memory by calling build and checking
    # that checksum mismatches would exclude — covered if we sabotage via fixture.
    normal = tmp_path / "data" / "raw" / "normal"
    run = normal / "N01_SINGLE_SUCCESS" / "N01_FAKE_001"
    run.mkdir(parents=True)
    auth = run / "auth.log"
    auth.write_text("Failed password for testuser from 1.2.3.4 port 1 ssh2\n", encoding="utf-8")
    man = {
        "schema_version": "1.0",
        "run_id": "N01_FAKE_001",
        "scenario_id": "N01_SINGLE_SUCCESS",
        "scenario_intent": "normal",
        "result": "success",
        "collection_batch_id": "P2_BASELINE_FAKE",
        "collection_phase": "P2",
        "raw_log_sha256": "0" * 64,
        "raw_log_line_count": 1,
        "data_source": "local_lab",
    }
    (run / "manifest.json").write_text(json.dumps(man), encoding="utf-8")
    idx = {
        "run_id": "N01_FAKE_001",
        "scenario_id": "N01_SINGLE_SUCCESS",
        "scenario_intent": "normal",
        "collection_batch_id": "P2_BASELINE_FAKE",
        "result": "success",
        "raw_log_path": str(auth.relative_to(tmp_path)),
        "manifest_path": str((run / "manifest.json").relative_to(tmp_path)),
        "raw_log_sha256": "0" * 64,
        "data_source": "local_lab",
    }
    (normal / "index.jsonl").write_text(json.dumps(idx) + "\n", encoding="utf-8")
    sec = tmp_path / "data" / "raw" / "security"
    sec.mkdir(parents=True)
    (sec / "index.jsonl").write_text("", encoding="utf-8")

    # Point policy sources relative to tmp_path
    pol = json.loads(json.dumps(policy))  # deep copy via json
    # policy is yaml dict — copy shallow+nested
    import copy

    pol = copy.deepcopy(policy)
    built = build_labels(tmp_path, pol, include_smoke=False)
    reasons = [e["reason_code"] for e in built.exclusions]
    assert "checksum_mismatch" in reasons
    assert built.stats.get("eligible_primary_runs") == 0
