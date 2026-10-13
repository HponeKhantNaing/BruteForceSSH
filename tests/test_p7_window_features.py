"""Rolling window feature tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from features.behavioral_features import compute_behavior_features  # noqa: E402
from features.window_features import rolling_count, rolling_count_at_anchor  # noqa: E402


def _a(order, outcome, ts, user="USR_001"):
    return {
        "attempt_order": order,
        "outcome": outcome,
        "started_at": ts,
        "user_id": user,
    }


def test_burst_10_failures_within_30s():
    attempts = [
        _a(i, "FAILURE", f"2026-09-27T07:00:{i:02d}+00:00") for i in range(10)
    ]
    feats = compute_behavior_features(attempts)
    assert feats["failed_count_30s_max"] == 10
    assert feats["failed_count_60s_max"] == 10
    assert feats["failed_count_5m_max"] == 10


def test_window_boundary_inclusive():
    # Two failures 30s apart: at second anchor, first is exactly at t-30 → included
    attempts = [
        {"outcome": "FAILURE", "started_at": "2026-09-27T07:00:00+00:00"},
        {"outcome": "FAILURE", "started_at": "2026-09-27T07:00:30+00:00"},
    ]
    c = rolling_count(attempts, window_seconds=30.0, predicate=lambda a: a["outcome"] == "FAILURE")
    assert c == 2.0


def test_no_future_information():
    history = [
        {"outcome": "FAILURE", "started_at": "2026-09-27T07:00:00+00:00"},
        {"outcome": "FAILURE", "started_at": "2026-09-27T07:00:10+00:00"},
        {"outcome": "FAILURE", "started_at": "2026-09-27T07:01:00+00:00"},  # future vs anchor
    ]
    # At t=10s, must not count the t=60s attempt
    c = rolling_count_at_anchor(
        history,
        anchor_ts="2026-09-27T07:00:10+00:00",
        window_seconds=60.0,
        predicate=lambda a: a["outcome"] == "FAILURE",
    )
    assert c == 2.0
