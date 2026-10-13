"""Inclusive [t-W, t] window boundary parity with P7 helpers."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from features.window_features import rolling_count, rolling_count_at_anchor  # noqa: E402


def test_inclusive_window_boundaries():
    # Attempts at t=0, 30, 60, 300
    base = "2026-09-27T10:00:00+00:00"
    from datetime import datetime, timedelta, timezone

    t0 = datetime(2026, 9, 27, 10, 0, 0, tzinfo=timezone.utc)

    def mk(offset_s: float, outcome="FAILURE"):
        ts = (t0 + timedelta(seconds=offset_s)).isoformat()
        return {"started_at": ts, "outcome": outcome, "user_id": "U1"}

    attempts = [mk(0), mk(30), mk(60), mk(300)]
    is_fail = lambda a: a["outcome"] == "FAILURE"
    # At last attempt (300), 30s window includes only itself (boundary at 270)
    assert rolling_count_at_anchor(attempts, anchor_ts=attempts[-1]["started_at"], window_seconds=30, predicate=is_fail) == 1
    # 60s window ending at 300: [240,300] → only t=300
    assert rolling_count_at_anchor(attempts, anchor_ts=attempts[-1]["started_at"], window_seconds=60, predicate=is_fail) == 1
    # Exactly 30s apart: window of 30 from t=30 includes t=0 and t=30
    assert rolling_count_at_anchor(attempts, anchor_ts=attempts[1]["started_at"], window_seconds=30, predicate=is_fail) == 2
    # Max over anchors for 30s should be 2
    assert rolling_count(attempts, window_seconds=30, predicate=is_fail) == 2.0
    assert rolling_count(attempts, window_seconds=300, predicate=is_fail) == 4.0
