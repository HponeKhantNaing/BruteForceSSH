"""P3 controlled suspicious / brute-force-like collection (localhost lab only)."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from typing import Any

from collection.p2_normal import (
    ALLOWED_HOSTS,
    LabCredentials,
    assert_localhost,
    iso_now,
    make_ssh_client,
    summarize_auth_text,
)
from paramiko.ssh_exception import AuthenticationException, SSHException

# ---------------------------------------------------------------------------
# Hard safety ceilings — YAML may only use values at or below these.
# ---------------------------------------------------------------------------
MAX_AUTH_ATTEMPTS_PER_RUN = 30
MAX_USERNAMES_PER_RUN = 6
MAX_INTENTIONAL_PASSWORDS_PER_RUN = 3
MAX_SCENARIO_SECONDS = 120
MIN_INTER_ATTEMPT_DELAY = 0.25

# Internal wrong-password templates (never written to manifests).
_WRONG_PASSWORD_TEMPLATES = (
    "incorrect_p3_password_a",
    "incorrect_p3_password_b",
    "incorrect_p3_password_c",
)


@dataclass
class AttemptPlan:
    username: str
    use_valid_password: bool
    wrong_password_index: int = 0


def wrong_password_for_index(index: int) -> str:
    if index < 0 or index >= len(_WRONG_PASSWORD_TEMPLATES):
        raise RuntimeError("wrong password index exceeds MAX_INTENTIONAL_PASSWORDS_PER_RUN")
    return _WRONG_PASSWORD_TEMPLATES[index]


def resolve_usernames(names: list[str], primary_user: str) -> list[str]:
    resolved = []
    for n in names:
        if n == "primary":
            resolved.append(primary_user)
        else:
            resolved.append(n)
    # Deduplicate while preserving order
    out: list[str] = []
    seen: set[str] = set()
    for u in resolved:
        if u not in seen:
            out.append(u)
            seen.add(u)
    return out


def assert_p3_localhost(host: str) -> None:
    normalized = host.strip().lower()
    if normalized not in ALLOWED_HOSTS:
        raise RuntimeError(
            f"Refusing P3 security scenario execution against a non-local target: {host!r}. "
            "Only 127.0.0.1 / localhost are allowed."
        )


def validate_scenario_safety(
    scenario_id: str,
    sc: dict[str, Any],
    *,
    primary_user: str,
) -> dict[str, Any]:
    """Validate one scenario against hard ceilings. Returns computed plan metadata."""
    users = resolve_usernames(list(sc.get("usernames") or ["primary"]), primary_user)
    if not users:
        raise RuntimeError(f"{scenario_id}: at least one username required")
    if len(users) > MAX_USERNAMES_PER_RUN:
        raise RuntimeError(
            f"{scenario_id}: username count {len(users)} exceeds hard cap {MAX_USERNAMES_PER_RUN}"
        )

    gap = float(sc.get("gap_seconds", sc.get("burst_gap_seconds", MIN_INTER_ATTEMPT_DELAY)))
    if gap < MIN_INTER_ATTEMPT_DELAY:
        raise RuntimeError(
            f"{scenario_id}: gap_seconds={gap} below minimum {MIN_INTER_ATTEMPT_DELAY}"
        )

    # Estimate attempts
    if "burst_attempts" in sc:
        attempts = int(sc["burst_attempts"]) * 2
        between = float(sc.get("between_bursts_seconds", 10))
        if between < MIN_INTER_ATTEMPT_DELAY:
            raise RuntimeError(f"{scenario_id}: between_bursts_seconds too small")
        burst_gap = float(sc.get("burst_gap_seconds", gap))
        if burst_gap < MIN_INTER_ATTEMPT_DELAY:
            raise RuntimeError(f"{scenario_id}: burst_gap_seconds below minimum")
    elif "failed_attempts_per_user" in sc:
        per = int(sc["failed_attempts_per_user"])
        attempts = per * len(users)
    else:
        attempts = int(sc.get("failed_attempts", 0))

    if sc.get("expect_success"):
        attempts += 1  # recovery success counts toward auth activity ceiling

    if attempts > MAX_AUTH_ATTEMPTS_PER_RUN:
        raise RuntimeError(
            f"{scenario_id}: planned auth attempts {attempts} exceed hard cap {MAX_AUTH_ATTEMPTS_PER_RUN}"
        )
    if attempts < 1:
        raise RuntimeError(f"{scenario_id}: planned attempts must be >= 1")

    # Rough duration estimate
    if "burst_attempts" in sc:
        est = (
            int(sc["burst_attempts"]) * 2 * (float(sc.get("burst_gap_seconds", gap)) + 0.5)
            + float(sc.get("between_bursts_seconds", 10))
        )
    else:
        fail_count = attempts - (1 if sc.get("expect_success") else 0)
        est = fail_count * (gap + 0.5) + float(sc.get("recovery_delay_seconds", 0))
    if est > MAX_SCENARIO_SECONDS:
        raise RuntimeError(
            f"{scenario_id}: estimated duration {est:.1f}s exceeds hard cap {MAX_SCENARIO_SECONDS}s"
        )

    return {
        "usernames": users,
        "planned_auth_attempts": attempts,
        "gap_seconds": gap,
        "estimated_duration_seconds": est,
    }


def ensure_p3_lab_users(container_name: str, usernames: list[str], password: str) -> None:
    """Create disposable lab users inside the project container if missing."""
    for user in usernames:
        if user in {"root", "primary"}:
            continue
        check = subprocess.run(
            ["docker", "exec", container_name, "id", user],
            capture_output=True,
            text=True,
        )
        if check.returncode != 0:
            subprocess.check_call(
                [
                    "docker",
                    "exec",
                    container_name,
                    "useradd",
                    "-m",
                    "-s",
                    "/bin/bash",
                    user,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        # Set/refresh disposable lab password without embedding it in a shell string.
        proc = subprocess.run(
            ["docker", "exec", "-i", container_name, "chpasswd"],
            input=f"{user}:{password}\n",
            text=True,
            capture_output=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"Failed to set password for lab user {user!r} inside {container_name}"
            )


def ssh_auth_once(
    creds: LabCredentials,
    *,
    username: str,
    password: str,
    timeout: float,
) -> str:
    """
    Single password authentication attempt. Returns 'accepted' or 'failed'.
    Does not retry automatically.
    """
    client = make_ssh_client()
    try:
        client.connect(
            hostname=creds.host,
            port=creds.port,
            username=username,
            password=password,
            look_for_keys=False,
            allow_agent=False,
            timeout=timeout,
            auth_timeout=timeout,
            banner_timeout=timeout,
        )
        client.close()
        return "accepted"
    except AuthenticationException:
        return "failed"
    except SSHException as exc:
        msg = str(exc).lower()
        if "auth" in msg or "permission" in msg or "not open" in msg:
            return "failed"
        raise
    finally:
        try:
            client.close()
        except Exception:
            pass


def count_auth_failure_events(text: str) -> int:
    """Count semantic failure events (not raw line count)."""
    lower = text.lower()
    # Prefer Failed password lines; also count Invalid user when present without Failed password on same semantic event.
    failed_pw = lower.count("failed password")
    invalid_user = lower.count("invalid user")
    # When both appear for same attempt, Failed password usually accompanies invalid user — prefer failed_pw.
    if failed_pw > 0:
        return failed_pw
    return invalid_user


def count_accepted_events(text: str) -> int:
    return text.lower().count("accepted password")


def build_attempt_sequence(
    scenario_id: str,
    sc: dict[str, Any],
    primary_user: str,
) -> list[AttemptPlan]:
    users = resolve_usernames(list(sc.get("usernames") or ["primary"]), primary_user)
    plans: list[AttemptPlan] = []

    if scenario_id.startswith("B05") or "burst_attempts" in sc:
        n = int(sc["burst_attempts"])
        user = users[0]
        for _ in range(n):
            plans.append(AttemptPlan(username=user, use_valid_password=False, wrong_password_index=0))
        # marker handled by executor for between-bursts pause
        for _ in range(n):
            plans.append(AttemptPlan(username=user, use_valid_password=False, wrong_password_index=1))
        return plans

    if "failed_attempts_per_user" in sc:
        per = int(sc["failed_attempts_per_user"])
        for u in users:
            for i in range(per):
                plans.append(
                    AttemptPlan(
                        username=u,
                        use_valid_password=False,
                        wrong_password_index=min(i, MAX_INTENTIONAL_PASSWORDS_PER_RUN - 1),
                    )
                )
    else:
        fails = int(sc.get("failed_attempts", 0))
        user = users[0]
        for i in range(fails):
            plans.append(
                AttemptPlan(
                    username=user,
                    use_valid_password=False,
                    wrong_password_index=min(i % MAX_INTENTIONAL_PASSWORDS_PER_RUN, 2),
                )
            )

    if sc.get("expect_success"):
        plans.append(AttemptPlan(username=users[0], use_valid_password=True, wrong_password_index=0))

    if len(plans) > MAX_AUTH_ATTEMPTS_PER_RUN:
        raise RuntimeError(f"{scenario_id}: attempt sequence exceeds hard cap")
    return plans


def execute_attempt_sequence(
    scenario_id: str,
    sc: dict[str, Any],
    creds: LabCredentials,
    plans: list[AttemptPlan],
    *,
    ssh_timeout: float,
) -> tuple[list[dict[str, Any]], int, int, float]:
    """
    Sequentially execute attempts. Returns (actions, executed_failures, executed_successes, duration_s).
    """
    actions: list[dict[str, Any]] = []
    started = time.monotonic()
    deadline = started + MAX_SCENARIO_SECONDS
    executed_fail = 0
    executed_ok = 0

    gap = float(sc.get("gap_seconds", sc.get("burst_gap_seconds", MIN_INTER_ATTEMPT_DELAY)))
    gap = max(gap, MIN_INTER_ATTEMPT_DELAY)
    recovery_delay = float(sc.get("recovery_delay_seconds", 0))
    between_bursts = float(sc.get("between_bursts_seconds", 0))
    burst_n = int(sc.get("burst_attempts", 0)) if "burst_attempts" in sc else 0

    for idx, plan in enumerate(plans):
        if time.monotonic() > deadline:
            raise TimeoutError(f"{scenario_id}: exceeded MAX_SCENARIO_SECONDS={MAX_SCENARIO_SECONDS}")

        # B05 pause between bursts (after first burst_n attempts)
        if burst_n and idx == burst_n and between_bursts > 0:
            time.sleep(between_bursts)
            actions.append({"type": "between_bursts_pause", "seconds": between_bursts, "at": iso_now()})

        # Recovery delay before successful attempt when previous were failures
        if plan.use_valid_password and recovery_delay > 0 and idx > 0:
            time.sleep(recovery_delay)
            actions.append({"type": "recovery_delay", "seconds": recovery_delay, "at": iso_now()})

        password = creds.password if plan.use_valid_password else wrong_password_for_index(plan.wrong_password_index)
        outcome = ssh_auth_once(
            creds,
            username=plan.username,
            password=password,
            timeout=ssh_timeout,
        )
        if outcome == "accepted":
            executed_ok += 1
            if not plan.use_valid_password:
                raise RuntimeError(
                    f"{scenario_id}: unexpected acceptance with intentional wrong password for {plan.username}"
                )
        else:
            executed_fail += 1
            if plan.use_valid_password:
                raise RuntimeError(
                    f"{scenario_id}: expected successful recovery login failed for {plan.username}"
                )

        actions.append(
            {
                "type": "ssh_auth_attempt",
                "username_alias": plan.username,
                "intended": "success" if plan.use_valid_password else "failure",
                "outcome": outcome,
                "wrong_password_index": None if plan.use_valid_password else plan.wrong_password_index,
                "at": iso_now(),
            }
        )

        # Inter-attempt delay (skip after last)
        if idx < len(plans) - 1:
            # Don't double-sleep when next iteration will apply recovery/between-burst delay at boundary
            next_is_recovery = plans[idx + 1].use_valid_password and recovery_delay > 0
            next_is_burst_boundary = bool(burst_n and (idx + 1) == burst_n and between_bursts > 0)
            if not next_is_recovery and not next_is_burst_boundary:
                time.sleep(gap)

    duration = time.monotonic() - started
    if duration > MAX_SCENARIO_SECONDS:
        raise TimeoutError(f"{scenario_id}: runtime {duration:.1f}s exceeded cap")
    return actions, executed_fail, executed_ok, duration


def evaluate_security_run(
    sc: dict[str, Any],
    text: str,
    *,
    executed_fail: int,
    executed_ok: int,
) -> tuple[str, str, dict[str, Any]]:
    summary = summarize_auth_text(text)
    fail_events = count_auth_failure_events(text)
    accepted = count_accepted_events(text)
    summary["auth_failure_event_count"] = fail_events
    summary["accepted_event_count"] = accepted
    summary["executed_failed_attempts"] = executed_fail
    summary["executed_success_attempts"] = executed_ok

    if not text.strip():
        return "failed", "Captured auth log slice is empty", summary

    min_f = int(sc.get("min_failed_events", 0))
    max_f = int(sc.get("max_failed_events", 10**9))
    if fail_events < min_f or fail_events > max_f:
        return (
            "failed",
            f"Failed-auth event count {fail_events} outside expected [{min_f}, {max_f}]",
            summary,
        )

    if sc.get("expect_success"):
        min_a = int(sc.get("min_accepted_events", 1))
        if accepted < min_a:
            return "failed", f"Expected >= {min_a} Accepted password, found {accepted}", summary
    else:
        if accepted > 0:
            return "failed", f"Unexpected Accepted password count={accepted} in failure-only scenario", summary

    # Soft check: executed failures should roughly match configured intent
    if executed_fail < 1 and min_f > 0:
        return "failed", "No failed attempts were executed", summary

    return "success", "", summary
