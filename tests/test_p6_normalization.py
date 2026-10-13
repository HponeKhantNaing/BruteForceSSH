"""P6 normalization unit tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from preprocessing.normalizer import normalize_message  # noqa: E402


def test_ip_user_port_pid_replaced_semantics_preserved():
    raw = (
        "2026-09-27T07:18:38.354077+00:00 dd9a612cdd6b sshd[3761]: "
        "Failed password for testuser from 172.18.0.1 port 61010 ssh2"
    )
    text, counts = normalize_message(raw, username="testuser", hostname="dd9a612cdd6b")
    assert "172.18.0.1" not in text
    assert "testuser" not in text
    assert "61010" not in text
    assert "3761" not in text
    assert "failed password" in text
    assert "<ip>" in text
    assert "<user>" in text
    assert "port <port>" in text
    assert counts["ips"] >= 1
    assert counts["usernames"] >= 1


def test_accepted_password_preserved():
    raw = (
        "2026-09-27T06:57:43.269965+00:00 host sshd[809]: "
        "Accepted password for labuser1 from 172.18.0.1 port 64054 ssh2"
    )
    text, _ = normalize_message(raw, username="labuser1", hostname="host")
    assert "accepted password" in text
    assert "labuser1" not in text


def test_authentication_failure_preserved():
    raw = (
        "2026-09-27T07:00:37.842759+00:00 host sshd[1592]: "
        "pam_unix(sshd:auth): authentication failure; logname= uid=0 euid=0 "
        "tty=ssh ruser= rhost=172.18.0.1  user=testuser"
    )
    text, _ = normalize_message(raw, username="testuser", hostname="host")
    assert "authentication failure" in text
    assert "172.18.0.1" not in text
    assert "testuser" not in text
