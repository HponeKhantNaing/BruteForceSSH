"""Tests for P4 atomic event role annotation."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from labeling.p4_labeling import annotate_line, load_policy  # noqa: E402


def patterns():
    policy = load_policy(ROOT / "config" / "p4_labeling_policy.yaml")
    return (policy.get("event_roles") or {}).get("patterns") or []


def test_accepted_password():
    role, rule, status = annotate_line(
        "Accepted password for testuser from 172.18.0.1 port 1 ssh2", patterns()
    )
    assert role == "AUTH_SUCCESS"
    assert status == "matched"


def test_failed_password():
    role, _, status = annotate_line(
        "Failed password for testuser from 172.18.0.1 port 1 ssh2", patterns()
    )
    assert role == "AUTH_FAILURE"
    assert status == "matched"


def test_session_open_close():
    assert annotate_line("pam_unix(sshd:session): session opened for user testuser", patterns())[0] == "SESSION_OPEN"
    assert annotate_line("pam_unix(sshd:session): session closed for user testuser", patterns())[0] == "SESSION_CLOSE"


def test_unknown_line():
    role, _, status = annotate_line("completely unrelated noise xyz", patterns())
    assert role == "UNCLASSIFIED"
    assert status == "unmatched"
