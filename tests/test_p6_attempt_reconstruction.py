"""P6 attempt reconstruction tests (PAM double-count + success/session)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from preprocessing.attempt_reconstructor import reconstruct_attempts  # noqa: E402


def _ev(eid, role, pid, line, user="USR_001", src="SRC_001"):
    return {
        "event_id": eid,
        "event_role": role,
        "pid": pid,
        "line_number": line,
        "timestamp_iso": f"2026-09-27T07:00:{line:02d}+00:00",
        "source_id": src,
        "user_id": user,
    }


def test_pam_plus_auth_failure_one_attempt_two_events():
    events = [
        _ev("r:1", "CONNECTION_EVENT", 100, 1),
        _ev("r:2", "PAM_AUTH_FAILURE", 100, 2),
        _ev("r:3", "AUTH_FAILURE", 100, 3),
    ]
    attempts = reconstruct_attempts(events, "r")
    assert len(attempts) == 1
    assert attempts[0]["outcome"] == "FAILURE"
    assert set(attempts[0]["event_ids"]) == {"r:2", "r:3"}


def test_success_with_session_one_attempt():
    events = [
        _ev("r:1", "AUTH_SUCCESS", 200, 1),
        _ev("r:2", "SESSION_OPEN", 200, 2),
        _ev("r:3", "SESSION_CLOSE", 200, 3),
    ]
    attempts = reconstruct_attempts(events, "r")
    assert len(attempts) == 1
    assert attempts[0]["outcome"] == "SUCCESS"
    assert "r:1" in attempts[0]["event_ids"]
    assert "r:2" in attempts[0]["event_ids"]
    assert "r:3" in attempts[0]["event_ids"]


def test_connection_event_not_an_attempt():
    events = [
        _ev("r:1", "CONNECTION_EVENT", 1, 1),
        _ev("r:2", "CONNECTION_EVENT", 1, 2),
    ]
    attempts = reconstruct_attempts(events, "r")
    assert attempts == []
