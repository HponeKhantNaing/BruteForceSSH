"""P6 end-to-end dataset build tests."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from preprocessing.p6_preprocessing import build_dataset, load_yaml, sha256_file  # noqa: E402


def _p4_counts():
    runs = [
        json.loads(l)
        for l in (ROOT / "data/interim/p4/run_labels.jsonl").read_text().splitlines()
        if l.strip()
    ]
    primary = [r for r in runs if r.get("primary_candidate") is True]
    from collections import Counter

    return len(primary), Counter(r["target_label"] for r in primary)


def test_sample_counts_match_p4():
    n, dist = _p4_counts()
    cfg = load_yaml(ROOT / "config" / "p6_preprocessing.yaml")
    built = build_dataset(ROOT, cfg, write=False)
    assert built["quality"]["runs_accepted"] == n
    assert built["class_distribution"]["counts"]["NORMAL"] == dist["NORMAL"]
    assert built["class_distribution"]["counts"]["SUSPICIOUS"] == dist["SUSPICIOUS"]
    assert built["class_distribution"]["counts"]["BRUTE_FORCE"] == dist["BRUTE_FORCE"]


def test_no_double_count_failures():
    cfg = load_yaml(ROOT / "config" / "p6_preprocessing.yaml")
    built = build_dataset(ROOT, cfg, write=False)
    q = built["quality"]
    assert q["auth_failure_events"] == q["pam_auth_failure_events"]
    # Logical failures must equal AUTH_FAILURE anchors, not sum of PAM+AUTH
    assert q["logical_failed_attempts"] == q["auth_failure_events"]
    assert q["logical_failed_attempts"] != (
        q["auth_failure_events"] + q["pam_auth_failure_events"]
    )


def test_determinism():
    cfg = load_yaml(ROOT / "config" / "p6_preprocessing.yaml")
    a = build_dataset(ROOT, cfg, write=False)
    b = build_dataset(ROOT, cfg, write=False)
    assert a["canonical_runs"] == b["canonical_runs"]
    assert a["canonical_events"] == b["canonical_events"]
    assert a["canonical_attempts"] == b["canonical_attempts"]
    assert a["canonical_sequences"] == b["canonical_sequences"]


def test_raw_immutability_hashes_stable():
    paths = [
        ROOT / "data/interim/p4/run_labels.jsonl",
        ROOT / "data/interim/p4/event_annotations.jsonl",
        ROOT / "data/interim/p4/class_distribution.json",
    ]
    before = {str(p): sha256_file(p) for p in paths}
    cfg = load_yaml(ROOT / "config" / "p6_preprocessing.yaml")
    build_dataset(ROOT, cfg, write=False)
    after = {str(p): sha256_file(p) for p in paths}
    assert before == after
