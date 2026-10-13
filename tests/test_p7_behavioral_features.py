"""Behavioral feature unit tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from features.behavioral_features import compute_behavior_features  # noqa: E402


def _a(order, outcome, ts, user="USR_001"):
    return {
        "attempt_id": f"r:ATTEMPT_{order:03d}",
        "attempt_order": order,
        "outcome": outcome,
        "started_at": ts,
        "user_id": user,
        "source_id": "SRC_001",
    }


def test_double_count_uses_logical_attempts_not_events():
    # One logical FAILURE (PAM+AUTH already collapsed in P6)
    attempts = [_a(1, "FAILURE", "2026-09-27T07:00:00+00:00")]
    feats = compute_behavior_features(attempts)
    assert feats["failed_attempts"] == 1
    assert feats["total_attempts"] == 1


def test_suspicious_three_failures():
    attempts = [
        _a(1, "FAILURE", "2026-09-27T07:00:00+00:00"),
        _a(2, "FAILURE", "2026-09-27T07:00:10+00:00"),
        _a(3, "FAILURE", "2026-09-27T07:00:20+00:00"),
    ]
    feats = compute_behavior_features(attempts)
    assert feats["failed_attempts"] == 3
    assert feats["max_failure_streak"] == 3
    assert feats["failure_ratio"] == 1.0
    assert feats["successful_attempts"] == 0


def test_n06_style_success_after_failure():
    attempts = [
        _a(1, "FAILURE", "2026-09-27T07:00:37+00:00"),
        _a(2, "SUCCESS", "2026-09-27T07:00:46+00:00"),
    ]
    feats = compute_behavior_features(attempts)
    assert feats["failed_attempts"] == 1
    assert feats["successful_attempts"] == 1
    assert feats["success_after_failure"] == 1
    assert feats["failures_before_first_success"] == 1


def test_multi_user_60s():
    attempts = [
        _a(1, "FAILURE", "2026-09-27T07:00:00+00:00", "USR_001"),
        _a(2, "FAILURE", "2026-09-27T07:00:10+00:00", "USR_002"),
        _a(3, "FAILURE", "2026-09-27T07:00:20+00:00", "USR_003"),
    ]
    feats = compute_behavior_features(attempts)
    assert feats["unique_users_60s_max"] == 3
    assert feats["unique_users_total"] == 3
