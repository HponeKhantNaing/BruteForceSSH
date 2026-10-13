"""Stateful streaming logical-attempt reconstruction (P6 semantics).

PAM_AUTH_FAILURE + AUTH_FAILURE (same pid) → one FAILURE.
AUTH_SUCCESS + SESSION_* → one SUCCESS.
CONNECTION / unclassified → correlation only / ignore for attempts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from features.window_features import parse_ts
from preprocessing.attempt_reconstructor import (
    AUTH_ATTEMPT_ANCHORS,
    PAM_FAILURE,
    SESSION_ROLES,
    reconstruct_attempts,
)


@dataclass
class StreamAttemptResult:
    completed_attempts: list[dict[str, Any]] = field(default_factory=list)
    unresolved_expired: list[dict[str, Any]] = field(default_factory=list)


class StreamingAttemptReconstructor:
    """
    Online reconstructor.

    For complete historical event lists, prefer flush_batch() which delegates to
    P6 reconstruct_attempts for exact parity. Live mode uses incremental emit.
    """

    def __init__(self, *, correlation_timeout_seconds: float = 2.0, run_id_prefix: str = "LIVE"):
        self.correlation_timeout = float(correlation_timeout_seconds)
        self.run_id_prefix = run_id_prefix
        self._events: list[dict[str, Any]] = []
        self._attempt_order = 0
        self._pending_pam: dict[Any, list[dict[str, Any]]] = {}
        self._pending_success: list[dict[str, Any]] = []
        self._assigned: set[str] = set()
        self._emitted_ids: set[str] = set()

    def reset(self) -> None:
        self.__init__(
            correlation_timeout_seconds=self.correlation_timeout,
            run_id_prefix=self.run_id_prefix,
        )

    def flush_batch(self, events: list[dict[str, Any]], run_id: str) -> list[dict[str, Any]]:
        """Exact P6 batch reconstruction (historical parity authority)."""
        return reconstruct_attempts(events, run_id)

    def push(self, event: dict[str, Any], *, now_mono: float | None = None) -> StreamAttemptResult:
        """Push one parsed event; may complete zero or more logical attempts."""
        del now_mono  # reserved for future timeout scheduling
        out = StreamAttemptResult()
        role = event.get("event_role")
        if role in (None, "UNCLASSIFIED", "CONNECTION_EVENT", "OTHER"):
            # Keep connection events only if needed later; do not create attempts
            if role == "CONNECTION_EVENT":
                self._events.append(event)
            return out

        self._events.append(event)
        eid = event["event_id"]

        if role == PAM_FAILURE:
            self._pending_pam.setdefault(event.get("pid"), []).append(event)
            return out

        if role in ("AUTH_FAILURE", "INVALID_USER"):
            attempt = self._emit_failure(event)
            out.completed_attempts.append(attempt)
            return out

        if role == "AUTH_SUCCESS":
            # Create SUCCESS immediately; attach subsequent sessions opportunistically
            attempt = self._emit_success(event)
            self._pending_success.append(
                {
                    "attempt": attempt,
                    "pid": event.get("pid"),
                    "user_id": event.get("user_id") or event.get("username_raw"),
                    "line_number": event.get("line_number") or 0,
                    "opened_at": parse_ts(event.get("timestamp_iso")) or datetime.now(timezone.utc),
                }
            )
            out.completed_attempts.append(attempt)
            return out

        if role in SESSION_ROLES:
            self._attach_session(event)
            return out

        return out

    def expire_pending(self, *, as_of: datetime | None = None) -> StreamAttemptResult:
        """Expire timed-out pending PAM orphans as FAILURE attempts."""
        out = StreamAttemptResult()
        as_of = as_of or datetime.now(timezone.utc)
        # Orphan PAMs older than correlation timeout → FAILURE
        for pid, pams in list(self._pending_pam.items()):
            keep: list[dict[str, Any]] = []
            for pam in pams:
                if pam["event_id"] in self._assigned:
                    continue
                ts = parse_ts(pam.get("timestamp_iso"))
                age = (as_of - ts).total_seconds() if ts else self.correlation_timeout + 1
                if age >= self.correlation_timeout:
                    attempt = self._emit_orphan_pam(pam)
                    out.completed_attempts.append(attempt)
                    out.unresolved_expired.append(pam)
                else:
                    keep.append(pam)
            if keep:
                self._pending_pam[pid] = keep
            else:
                self._pending_pam.pop(pid, None)
        # Pending success buffers only attach sessions; attempts already emitted
        self._pending_success = [
            p
            for p in self._pending_success
            if (as_of - p["opened_at"]).total_seconds() < self.correlation_timeout
        ]
        return out

    def _next_id(self, run_id: str | None = None) -> str:
        self._attempt_order += 1
        rid = run_id or self.run_id_prefix
        return f"{rid}:ATTEMPT_{self._attempt_order:03d}"

    def _emit_failure(self, event: dict[str, Any]) -> dict[str, Any]:
        event_ids = [event["event_id"]]
        self._assigned.add(event["event_id"])
        pid = event.get("pid")
        candidates = self._pending_pam.get(pid, [])
        for pam in candidates:
            if pam["event_id"] in self._assigned:
                continue
            if (pam.get("line_number") or 0) <= (event.get("line_number") or 0):
                event_ids.insert(0, pam["event_id"])
                self._assigned.add(pam["event_id"])
                break
        self._pending_pam[pid] = [
            p for p in candidates if p["event_id"] not in self._assigned
        ]
        attempt_id = self._next_id(event.get("run_id"))
        linked_ts = [event.get("timestamp_iso")]
        for eid in event_ids:
            for e in self._events:
                if e["event_id"] == eid:
                    linked_ts.append(e.get("timestamp_iso"))
        started = next((t for t in linked_ts if t), event.get("timestamp_iso"))
        attempt = {
            "schema_version": "1.0",
            "attempt_id": attempt_id,
            "run_id": event.get("run_id") or self.run_id_prefix,
            "attempt_order": self._attempt_order,
            "started_at": started,
            "ended_at": event.get("timestamp_iso"),
            "source_id": event.get("source_id"),
            "source_ip": event.get("source_ip"),  # in-memory only; stripped before persist
            "user_id": event.get("user_id"),
            "username_raw": event.get("username_raw"),
            "auth_method": "password",
            "outcome": "FAILURE",
            "event_ids": event_ids,
            "reconstruction_method": "sshd_pid_time_event_correlation",
            "reconstruction_status": "verified",
        }
        self._emitted_ids.add(attempt_id)
        return attempt

    def _emit_success(self, event: dict[str, Any]) -> dict[str, Any]:
        self._assigned.add(event["event_id"])
        attempt_id = self._next_id(event.get("run_id"))
        attempt = {
            "schema_version": "1.0",
            "attempt_id": attempt_id,
            "run_id": event.get("run_id") or self.run_id_prefix,
            "attempt_order": self._attempt_order,
            "started_at": event.get("timestamp_iso"),
            "ended_at": event.get("timestamp_iso"),
            "source_id": event.get("source_id"),
            "source_ip": event.get("source_ip"),
            "user_id": event.get("user_id"),
            "username_raw": event.get("username_raw"),
            "auth_method": "password",
            "outcome": "SUCCESS",
            "event_ids": [event["event_id"]],
            "reconstruction_method": "sshd_pid_time_event_correlation",
            "reconstruction_status": "verified",
        }
        self._emitted_ids.add(attempt_id)
        return attempt

    def _attach_session(self, event: dict[str, Any]) -> None:
        if event["event_id"] in self._assigned:
            return
        for pending in self._pending_success:
            pid_ok = event.get("pid") == pending["pid"]
            user_ok = (
                event.get("user_id")
                and event.get("user_id") == pending["user_id"]
                and (event.get("line_number") or 0) > pending["line_number"]
            ) or (
                event.get("username_raw")
                and event.get("username_raw") == pending.get("attempt", {}).get("username_raw")
                and (event.get("line_number") or 0) > pending["line_number"]
            )
            if not (pid_ok or user_ok):
                continue
            if (event.get("line_number") or 0) < pending["line_number"]:
                continue
            attempt = pending["attempt"]
            attempt["event_ids"].append(event["event_id"])
            attempt["ended_at"] = event.get("timestamp_iso") or attempt.get("ended_at")
            self._assigned.add(event["event_id"])
            return

    def _emit_orphan_pam(self, pam: dict[str, Any]) -> dict[str, Any]:
        self._assigned.add(pam["event_id"])
        attempt_id = self._next_id(pam.get("run_id"))
        return {
            "schema_version": "1.0",
            "attempt_id": attempt_id,
            "run_id": pam.get("run_id") or self.run_id_prefix,
            "attempt_order": self._attempt_order,
            "started_at": pam.get("timestamp_iso"),
            "ended_at": pam.get("timestamp_iso"),
            "source_id": pam.get("source_id"),
            "source_ip": pam.get("source_ip"),
            "user_id": pam.get("user_id"),
            "username_raw": pam.get("username_raw"),
            "auth_method": "password",
            "outcome": "FAILURE",
            "event_ids": [pam["event_id"]],
            "reconstruction_method": "sshd_pid_time_event_correlation",
            "reconstruction_status": "orphan_pam_failure",
        }


def sanitize_attempt_for_features(attempt: dict[str, Any], *, user_id: str, source_token: str) -> dict[str, Any]:
    """Feature-facing attempt: runtime tokens only, no raw IP/username."""
    return {
        "attempt_id": attempt["attempt_id"],
        "attempt_order": attempt.get("attempt_order"),
        "started_at": attempt.get("started_at"),
        "ended_at": attempt.get("ended_at"),
        "outcome": attempt.get("outcome"),
        "user_id": user_id,
        "source_id": source_token,
        "auth_method": attempt.get("auth_method", "password"),
    }
