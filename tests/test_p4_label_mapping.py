"""Tests for P4 contextual target mapping and N06/S01/B01 sanity."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from labeling.p4_labeling import (  # noqa: E402
    annotate_line,
    build_labels,
    load_policy,
    map_target,
)


def test_intent_mapping():
    policy = load_policy(ROOT / "config" / "p4_labeling_policy.yaml")
    assert map_target(policy, "normal") == "NORMAL"
    assert map_target(policy, "suspicious") == "SUSPICIOUS"
    assert map_target(policy, "brute_force") == "BRUTE_FORCE"


def test_n06_s01_b01_from_build():
    policy = load_policy(ROOT / "config" / "p4_labeling_policy.yaml")
    built = build_labels(ROOT, policy, include_smoke=False)
    by_scenario = {}
    for r in built.run_labels:
        by_scenario.setdefault(r["scenario_id"], []).append(r)

    assert "N06_ISOLATED_PASSWORD_MISTAKE" in by_scenario
    for r in by_scenario["N06_ISOLATED_PASSWORD_MISTAKE"]:
        assert r["target_label"] == "NORMAL"

    assert "S01_FEW_REPEATED_FAILURES" in by_scenario
    for r in by_scenario["S01_FEW_REPEATED_FAILURES"]:
        assert r["target_label"] == "SUSPICIOUS"

    assert "B01_SHORT_FAILURE_BURST" in by_scenario
    for r in by_scenario["B01_SHORT_FAILURE_BURST"]:
        assert r["target_label"] == "BRUTE_FORCE"

    # Event roles for those runs must include AUTH_FAILURE but not carry target_label
    for sid, expected_target in [
        ("N06_ISOLATED_PASSWORD_MISTAKE", "NORMAL"),
        ("S01_FEW_REPEATED_FAILURES", "SUSPICIOUS"),
        ("B01_SHORT_FAILURE_BURST", "BRUTE_FORCE"),
    ]:
        run_ids = {r["run_id"] for r in by_scenario[sid]}
        anns = [a for a in built.event_annotations if a["run_id"] in run_ids]
        assert any(a["event_role"] == "AUTH_FAILURE" for a in anns)
        assert all("target_label" not in a for a in anns)
        # parent contextual target remains as expected
        assert all(
            r["target_label"] == expected_target for r in by_scenario[sid]
        )


def test_failed_password_is_not_threat_role():
    policy = load_policy(ROOT / "config" / "p4_labeling_policy.yaml")
    patterns = (policy.get("event_roles") or {}).get("patterns") or []
    role, _, _ = annotate_line("Failed password for x", patterns)
    assert role == "AUTH_FAILURE"
    assert role not in {"NORMAL", "SUSPICIOUS", "BRUTE_FORCE"}
