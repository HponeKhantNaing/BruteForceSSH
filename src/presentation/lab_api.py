"""Lab-only SSH exercise API (localhost Docker lab). Never persists passwords."""

from __future__ import annotations

import os
import re
import socket
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

from flask import Flask, jsonify, request
from paramiko.ssh_exception import AuthenticationException, SSHException

from collection.p2_normal import (
    LabCredentials,
    assert_localhost,
    docker_container_health,
    make_ssh_client,
    ssh_failed_once,
    ssh_success_session,
)

LAB_CONTAINER = "ai-security-ubuntu-lab"
LAB_HOST = "127.0.0.1"
MAX_ATTEMPTS_PER_MINUTE = 20
BURST_MIN = 3
BURST_MAX = 10
MAX_SESSIONS = 200

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_lock = threading.Lock()
_attempt_times: deque[float] = deque()
_sessions: deque[dict[str, Any]] = deque(maxlen=MAX_SESSIONS)
_pending_fails: dict[str, int] = {}
_session_seq = 0


def _lab_port() -> int:
    raw = os.environ.get("LAB_SSH_PORT", "2222").strip() or "2222"
    port = int(raw)
    if not (1 <= port <= 65535):
        raise ValueError("invalid LAB_SSH_PORT")
    return port


def _lab_ssh_user() -> str:
    user = os.environ.get("LAB_SSH_USER", "testuser").strip() or "testuser"
    return user


def _lab_login_email() -> str:
    return (os.environ.get("LAB_LOGIN_EMAIL", "testuser2222@gmail.com").strip() or "testuser2222@gmail.com").lower()


def _client_is_localhost() -> bool:
    addr = (request.remote_addr or "").strip().lower()
    return addr in {"127.0.0.1", "::1", "localhost"}


def _rate_limit_ok(cost: int = 1) -> bool:
    now = time.monotonic()
    with _lock:
        while _attempt_times and now - _attempt_times[0] > 60.0:
            _attempt_times.popleft()
        if len(_attempt_times) + cost > MAX_ATTEMPTS_PER_MINUTE:
            return False
        for _ in range(cost):
            _attempt_times.append(now)
        return True


def _sanitize_email(email: str) -> str:
    e = (email or "").strip().lower()
    if not e or len(e) > 128 or not _EMAIL_RE.match(e):
        raise ValueError("valid email required")
    return e


def _sanitize_location(location: str) -> str:
    loc = (location or "").strip()
    if not loc:
        return "Unknown (lab)"
    loc = re.sub(r"[\r\n\t]+", " ", loc)[:80]
    return loc or "Unknown (lab)"


def _ssh_user_for_email(email: str) -> str:
    """Any valid UI email maps to the lab SSH user — password is shared for all emails."""
    _ = email  # tracked in sessions; auth uses shared lab credentials
    return _lab_ssh_user()


def _outcome_from_actions(actions: list[dict[str, Any]]) -> str:
    types = {a.get("type") for a in actions}
    if "ssh_auth_failed" in types:
        return "auth_failed"
    if "ssh_connect" in types or "ssh_close" in types:
        return "accepted"
    return "unknown"


def _attempt_once(creds: LabCredentials, password: str, timeout: float = 20.0) -> dict[str, Any]:
    """Single password auth; reports accepted or auth_failed (no password in result)."""
    client = make_ssh_client()
    try:
        client.connect(
            hostname=creds.host,
            port=creds.port,
            username=creds.user,
            password=password,
            look_for_keys=False,
            allow_agent=False,
            timeout=timeout,
            auth_timeout=timeout,
            banner_timeout=timeout,
            disabled_algorithms={"auth": ["keyboard-interactive", "gssapi"]},
        )
        client.close()
        return {"result": "accepted", "attempts": 1}
    except AuthenticationException:
        return {"result": "auth_failed", "attempts": 1}
    except SSHException as exc:
        msg = str(exc).lower()
        if "auth" in msg or "permission" in msg:
            return {"result": "auth_failed", "attempts": 1, "note": type(exc).__name__}
        raise
    finally:
        try:
            client.close()
        except Exception:  # noqa: BLE001
            pass


def _record_session(
    *,
    email: str,
    location: str,
    wrong_attempts: int,
    status: str,
    mode: str,
) -> dict[str, Any]:
    global _session_seq
    with _lock:
        _session_seq += 1
        row = {
            "id": _session_seq,
            "email": email,
            "location": location,
            "wrong_attempts": int(wrong_attempts),
            "status": status,
            "mode": mode,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        _sessions.appendleft(row)
        return dict(row)


def _list_sessions(limit: int = 50) -> list[dict[str, Any]]:
    with _lock:
        return [dict(s) for s in list(_sessions)[:limit]]


def latest_lab_session() -> dict[str, Any] | None:
    """Most recent Lab Login session (email + location) for Discord enrichment."""
    with _lock:
        if not _sessions:
            return None
        return dict(_sessions[0])


def lab_sessions_snapshot(limit: int = 5) -> list[dict[str, Any]]:
    """Recent sessions for alert context (newest first)."""
    return _list_sessions(limit)


def lab_status_payload() -> dict[str, Any]:
    port = _lab_port()
    container = {"status": "unknown", "health": "unknown", "ok": False}
    try:
        status, health = docker_container_health(LAB_CONTAINER)
        container = {
            "status": status,
            "health": health,
            "ok": status == "running" and health in {"healthy", "none"},
        }
    except Exception as exc:  # noqa: BLE001
        container = {"status": "error", "health": "error", "ok": False, "error": type(exc).__name__}

    ssh_ok = False
    try:
        with socket.create_connection((LAB_HOST, port), timeout=2):
            ssh_ok = True
    except OSError:
        ssh_ok = False

    return {
        "ok": True,
        "lab": {
            "host": LAB_HOST,
            "port": port,
            "container": container,
            "ssh_reachable": ssh_ok,
        },
        "limits": {
            "max_attempts_per_minute": MAX_ATTEMPTS_PER_MINUTE,
            "burst_min": BURST_MIN,
            "burst_max": BURST_MAX,
        },
        "login_hint": {
            "email_placeholder": "you@company.com",
            "shared_password": True,
            "note": "Any valid email works; password is the shared lab password.",
        },
        "disclaimer": "Controlled-lab only. Attempts target the project Docker SSH container.",
    }


def register_lab_routes(app: Flask) -> None:
    @app.get("/api/lab/status")
    def api_lab_status():
        if not _client_is_localhost():
            return jsonify({"ok": False, "error": "localhost_only"}), 403
        return jsonify(lab_status_payload())

    @app.get("/api/lab/sessions")
    def api_lab_sessions():
        if not _client_is_localhost():
            return jsonify({"ok": False, "error": "localhost_only"}), 403
        limit = min(int(request.args.get("limit") or 50), MAX_SESSIONS)
        return jsonify({"ok": True, "items": _list_sessions(limit)})

    @app.post("/api/lab/attempt")
    def api_lab_attempt():
        if not _client_is_localhost():
            return jsonify({"ok": False, "error": "localhost_only"}), 403

        body = request.get_json(silent=True) or {}
        mode = str(body.get("mode") or "").strip().lower()
        if mode not in {"once", "success", "burst"}:
            return jsonify({"ok": False, "error": "mode must be once|success|burst"}), 400

        # Prefer email; accept legacy username for older clients.
        raw_email = body.get("email")
        if raw_email is None and body.get("username"):
            # Treat bare username as local-part of lab email for back-compat.
            raw_email = f"{body.get('username')}@lab.local"
        try:
            email = _sanitize_email(str(raw_email or ""))
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

        location = _sanitize_location(str(body.get("location") or ""))
        password = body.get("password")
        if not isinstance(password, str) or not password or len(password) > 256:
            return jsonify({"ok": False, "error": "password required (1-256 chars)"}), 400

        burst_count = int(body.get("burst_count") or BURST_MIN)
        if mode == "burst":
            if burst_count < BURST_MIN or burst_count > BURST_MAX:
                return jsonify(
                    {
                        "ok": False,
                        "error": f"burst_count must be {BURST_MIN}-{BURST_MAX}",
                    }
                ),
                400
            cost = burst_count
        else:
            cost = 1

        if not _rate_limit_ok(cost):
            return jsonify({"ok": False, "error": "rate_limited", "retry_after_seconds": 60}), 429

        try:
            port = _lab_port()
            assert_localhost(LAB_HOST)
        except Exception as exc:  # noqa: BLE001
            return jsonify({"ok": False, "error": str(exc)}), 500

        ssh_user = _ssh_user_for_email(email)
        creds = LabCredentials(user=ssh_user, password=password, host=LAB_HOST, port=port)
        results: list[dict[str, Any]] = []

        try:
            if mode == "once":
                out = _attempt_once(creds, password)
                results.append(out)
            elif mode == "success":
                # Force correct SSH user + password from env for recovery demo.
                ok_user = _lab_ssh_user()
                ok_pw = os.environ.get("LAB_SSH_PASSWORD", "").strip()
                if not ok_pw:
                    return jsonify({"ok": False, "error": "LAB_SSH_PASSWORD not configured"}), 500
                ok_creds = LabCredentials(user=ok_user, password=ok_pw, host=LAB_HOST, port=port)
                actions = ssh_success_session(ok_creds, commands=["whoami"], hold_seconds=0, timeout=20)
                results.append({"result": _outcome_from_actions(actions), "attempts": 1})
            else:  # burst — intentional failures using provided password as wrong auth
                for _ in range(burst_count):
                    actions = ssh_failed_once(creds, password, timeout=20)
                    results.append({"result": _outcome_from_actions(actions), "attempts": 1})
        except Exception as exc:  # noqa: BLE001
            return jsonify(
                {
                    "ok": False,
                    "mode": mode,
                    "email": email,
                    "error": type(exc).__name__,
                    "detail": str(exc)[:200],
                    "results": results,
                }
            ), 502

        last = results[-1]["result"] if results else "unknown"
        fail_n = sum(1 for r in results if r.get("result") == "auth_failed")
        accepted = last == "accepted" or any(r.get("result") == "accepted" for r in results)

        with _lock:
            pending = _pending_fails.get(email, 0)
            if mode == "burst":
                wrong = fail_n
                status = "failed" if fail_n else "unknown"
                _pending_fails.pop(email, None)
            elif accepted:
                wrong = pending  # wrong tries before this success
                status = "success"
                _pending_fails.pop(email, None)
            else:
                wrong = pending + fail_n
                _pending_fails[email] = wrong
                status = "failed"

        session = _record_session(
            email=email,
            location=location,
            wrong_attempts=wrong,
            status=status,
            mode=mode,
        )

        return jsonify(
            {
                "ok": True,
                "mode": mode,
                "attempt_count": len(results),
                "last_result": last,
                "results": results,
                "lab_host": LAB_HOST,
                "lab_port": port,
                "email": email,
                "location": location,
                "session": session,
            }
        )
