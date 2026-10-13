"""Per-source episode idle / max-duration / isolation."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from realtime.context_manager import ContextManager  # noqa: E402


def _attempt(ts: str, ip: str, user: str, outcome: str = "FAILURE", order: int = 1):
    return {
        "attempt_id": f"A{order}",
        "attempt_order": order,
        "started_at": ts,
        "ended_at": ts,
        "outcome": outcome,
        "source_ip": ip,
        "username_raw": user,
    }


def test_source_contexts_isolated():
    cm = ContextManager(idle_timeout_seconds=30, max_episode_duration_seconds=300)
    t0 = "2026-09-27T10:00:00+00:00"
    ep_a, _ = cm.on_attempt(_attempt(t0, "1.1.1.1", "u1"), as_of=datetime.fromisoformat(t0))
    ep_b, _ = cm.on_attempt(_attempt(t0, "2.2.2.2", "u2"), as_of=datetime.fromisoformat(t0))
    assert ep_a.episode_id != ep_b.episode_id
    assert ep_a.source_token != ep_b.source_token
    assert len(ep_a.attempts) == 1
    assert len(ep_b.attempts) == 1


def test_idle_timeout_new_episode():
    cm = ContextManager(idle_timeout_seconds=30, max_episode_duration_seconds=300)
    t0 = datetime(2026, 9, 27, 10, 0, 0, tzinfo=timezone.utc)
    ep1, _ = cm.on_attempt(
        _attempt(t0.isoformat(), "1.1.1.1", "u1"),
        as_of=t0,
    )
    t1 = t0 + timedelta(seconds=10)
    ep2, closed = cm.on_attempt(
        _attempt(t1.isoformat(), "1.1.1.1", "u1", order=2),
        as_of=t1,
    )
    assert ep2.episode_id == ep1.episode_id
    assert closed == []
    t2 = t1 + timedelta(seconds=31)
    # timeout check with wall-clock after idle
    closed2 = cm.check_timeouts(as_of=t2)
    assert len(closed2) == 1
    assert closed2[0].close_reason == "IDLE_TIMEOUT"
    ep3, _ = cm.on_attempt(
        _attempt(t2.isoformat(), "1.1.1.1", "u1", order=3),
        as_of=t2,
    )
    assert ep3.episode_id != ep1.episode_id


def test_max_duration_splits_episode():
    cm = ContextManager(idle_timeout_seconds=600, max_episode_duration_seconds=60)
    t0 = datetime(2026, 9, 27, 10, 0, 0, tzinfo=timezone.utc)
    ep1, _ = cm.on_attempt(_attempt(t0.isoformat(), "1.1.1.1", "u1"), as_of=t0)
    t_late = t0 + timedelta(seconds=61)
    ep2, closed = cm.on_attempt(
        _attempt(t_late.isoformat(), "1.1.1.1", "u1", order=2),
        as_of=t_late,
    )
    assert any(c.close_reason == "MAX_DURATION" for c in closed)
    assert ep2.episode_id != ep1.episode_id
