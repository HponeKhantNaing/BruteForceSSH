"""Streaming attempt reconstruction: PAM+AUTH = 1 FAILURE; session ≠ extra SUCCESS."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from realtime.attempt_stream import StreamingAttemptReconstructor  # noqa: E402
from realtime.p11_monitor import load_yaml, verify_attempt_parity  # noqa: E402


def _ev(n, role, pid=10, user="alice", ip="10.0.0.1", ts="2026-09-27T10:00:00+00:00"):
    return {
        "event_id": f"E{n}",
        "line_number": n,
        "event_role": role,
        "pid": pid,
        "user_id": user,
        "username_raw": user,
        "source_id": "SRC_001",
        "source_ip": ip,
        "timestamp_iso": ts,
        "run_id": "TEST",
    }


def test_pam_auth_failure_pairs_to_one_failure():
    s = StreamingAttemptReconstructor()
    out1 = s.push(_ev(1, "PAM_AUTH_FAILURE"))
    assert out1.completed_attempts == []
    out2 = s.push(_ev(2, "AUTH_FAILURE"))
    assert len(out2.completed_attempts) == 1
    assert out2.completed_attempts[0]["outcome"] == "FAILURE"
    assert len(out2.completed_attempts[0]["event_ids"]) == 2


def test_success_session_is_one_success():
    s = StreamingAttemptReconstructor()
    out = s.push(_ev(1, "AUTH_SUCCESS"))
    assert len(out.completed_attempts) == 1
    assert out.completed_attempts[0]["outcome"] == "SUCCESS"
    s.push(_ev(2, "SESSION_OPEN"))
    s.push(_ev(3, "SESSION_CLOSE"))
    # No additional attempts from session lines
    assert s._attempt_order == 1


def test_historical_attempt_parity_395():
    cfg = load_yaml(ROOT / "config" / "p11_realtime.yaml")
    report = verify_attempt_parity(ROOT, cfg)
    assert report["ok"] is True
    assert report["expected_failures"] == 345
    assert report["actual_failures"] == 345
    assert report["expected_successes"] == 50
    assert report["actual_successes"] == 50
    assert report["actual_unknown"] == 0
