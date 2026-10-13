"""Logical authentication attempt reconstruction (P6).

Critical rule: PAM_AUTH_FAILURE + AUTH_FAILURE for the same sshd PID
= one FAILURE attempt (not two).
"""

from __future__ import annotations

from typing import Any


AUTH_ATTEMPT_ANCHORS = {"AUTH_FAILURE", "AUTH_SUCCESS", "INVALID_USER"}
SESSION_ROLES = {"SESSION_OPEN", "SESSION_CLOSE"}
PAM_FAILURE = "PAM_AUTH_FAILURE"


def reconstruct_attempts(events: list[dict[str, Any]], run_id: str) -> list[dict[str, Any]]:
    """
    Reconstruct logical attempts from ordered canonical event dicts.

    Each event must include: event_id, event_role, pid, timestamp_iso,
    source_id, user_id, line_number.
    """
    ordered = sorted(events, key=lambda e: (e.get("line_number") or 0, e.get("event_id") or ""))
    attempts: list[dict[str, Any]] = []
    # Track which event_ids already assigned to an attempt
    assigned: set[str] = set()

    # Index PAM failures by pid for pairing with AUTH_FAILURE
    pam_by_pid: dict[int | None, list[dict[str, Any]]] = {}
    for e in ordered:
        if e.get("event_role") == PAM_FAILURE:
            pam_by_pid.setdefault(e.get("pid"), []).append(e)

    pam_used: set[str] = set()

    attempt_order = 0
    for e in ordered:
        role = e.get("event_role")
        if role not in AUTH_ATTEMPT_ANCHORS:
            continue
        if e["event_id"] in assigned:
            continue

        attempt_order += 1
        attempt_id = f"{run_id}:ATTEMPT_{attempt_order:03d}"
        event_ids = [e["event_id"]]
        assigned.add(e["event_id"])

        if role in ("AUTH_FAILURE", "INVALID_USER"):
            outcome = "FAILURE"
            # Attach unpaired PAM failure with same pid appearing before this line
            pid = e.get("pid")
            candidates = pam_by_pid.get(pid, [])
            for pam in candidates:
                if pam["event_id"] in pam_used or pam["event_id"] in assigned:
                    continue
                if (pam.get("line_number") or 0) <= (e.get("line_number") or 0):
                    event_ids.insert(0, pam["event_id"])
                    assigned.add(pam["event_id"])
                    pam_used.add(pam["event_id"])
                    break
        else:
            outcome = "SUCCESS"
            # Attach SESSION_OPEN/CLOSE with same pid (or immediately following session lines)
            pid = e.get("pid")
            for nxt in ordered:
                if nxt["event_id"] in assigned:
                    continue
                if nxt.get("event_role") not in SESSION_ROLES:
                    continue
                # Same sshd pid preferred; session close is often same parent pid
                if nxt.get("pid") == pid or (
                    nxt.get("user_id")
                    and nxt.get("user_id") == e.get("user_id")
                    and (nxt.get("line_number") or 0) > (e.get("line_number") or 0)
                ):
                    # Only attach session events that are near this success (same run, later lines)
                    if (nxt.get("line_number") or 0) < (e.get("line_number") or 0):
                        continue
                    event_ids.append(nxt["event_id"])
                    assigned.add(nxt["event_id"])

        # Timestamps from first/last linked events
        linked = [x for x in ordered if x["event_id"] in event_ids]
        linked_sorted = sorted(linked, key=lambda x: x.get("line_number") or 0)
        started = linked_sorted[0].get("timestamp_iso")
        ended = linked_sorted[-1].get("timestamp_iso")

        attempts.append(
            {
                "schema_version": "1.0",
                "attempt_id": attempt_id,
                "run_id": run_id,
                "attempt_order": attempt_order,
                "started_at": started,
                "ended_at": ended,
                "source_id": e.get("source_id"),
                "user_id": e.get("user_id"),
                "auth_method": "password",
                "outcome": outcome,
                "event_ids": event_ids,
                "reconstruction_method": "sshd_pid_time_event_correlation",
                "reconstruction_status": "verified",
            }
        )

    # Orphan PAM failures (no AUTH_FAILURE) → FAILURE attempts
    for e in ordered:
        if e.get("event_role") != PAM_FAILURE:
            continue
        if e["event_id"] in assigned:
            continue
        attempt_order += 1
        attempt_id = f"{run_id}:ATTEMPT_{attempt_order:03d}"
        assigned.add(e["event_id"])
        attempts.append(
            {
                "schema_version": "1.0",
                "attempt_id": attempt_id,
                "run_id": run_id,
                "attempt_order": attempt_order,
                "started_at": e.get("timestamp_iso"),
                "ended_at": e.get("timestamp_iso"),
                "source_id": e.get("source_id"),
                "user_id": e.get("user_id"),
                "auth_method": "password",
                "outcome": "FAILURE",
                "event_ids": [e["event_id"]],
                "reconstruction_method": "sshd_pid_time_event_correlation",
                "reconstruction_status": "orphan_pam_failure",
            }
        )

    # Fill attempt_id back onto events via caller
    return attempts


def attempt_id_map(attempts: list[dict[str, Any]]) -> dict[str, str]:
    m: dict[str, str] = {}
    for a in attempts:
        for eid in a.get("event_ids") or []:
            m[eid] = a["attempt_id"]
    return m
