"""Behavioral numeric features from P6 logical authentication attempts."""

from __future__ import annotations

import math
import statistics
from datetime import datetime
from typing import Any

from features.window_features import parse_ts, rolling_count, rolling_unique_count

DEFAULT_FEATURE_NAMES = [
    "total_attempts",
    "failed_attempts",
    "successful_attempts",
    "failure_ratio",
    "duration_seconds",
    "attempt_rate_per_second",
    "failed_count_30s_max",
    "failed_count_60s_max",
    "failed_count_5m_max",
    "success_count_5m_max",
    "unique_users_total",
    "unique_users_60s_max",
    "has_multiple_attempts",
    "min_inter_attempt_gap_seconds",
    "mean_inter_attempt_gap_seconds",
    "median_inter_attempt_gap_seconds",
    "std_inter_attempt_gap_seconds",
    "max_failure_streak",
    "success_after_failure",
    "failures_before_first_success",
    "first_attempt_failed",
    "last_attempt_success",
]


def _duration_seconds(
    attempts: list[dict[str, Any]],
    run: dict[str, Any] | None = None,
    sequence: dict[str, Any] | None = None,
    min_duration: float = 1e-3,
) -> float:
    if run and run.get("duration_seconds") is not None:
        try:
            d = float(run["duration_seconds"])
            if d >= 0:
                return max(d, 0.0)
        except (TypeError, ValueError):
            pass
    if sequence and sequence.get("duration_seconds") is not None:
        try:
            d = float(sequence["duration_seconds"])
            if d >= 0:
                return max(d, 0.0)
        except (TypeError, ValueError):
            pass

    start = None
    end = None
    if run:
        start = parse_ts(run.get("started_at"))
        end = parse_ts(run.get("ended_at"))
    if (start is None or end is None) and sequence:
        start = start or parse_ts(sequence.get("sequence_start"))
        end = end or parse_ts(sequence.get("sequence_end"))
    if (start is None or end is None) and attempts:
        times = [parse_ts(a.get("started_at")) for a in attempts]
        times = [t for t in times if t is not None]
        if times:
            start = start or min(times)
            end = end or max(times)
    if start is not None and end is not None:
        d = (end - start).total_seconds()
        return max(d, 0.0)
    return 0.0


def _inter_attempt_gaps(attempts: list[dict[str, Any]]) -> list[float]:
    timed: list[datetime] = []
    for a in sorted(attempts, key=lambda x: (x.get("attempt_order") or 0, x.get("started_at") or "")):
        dt = parse_ts(a.get("started_at"))
        if dt is not None:
            timed.append(dt)
    gaps = []
    for i in range(1, len(timed)):
        gaps.append(max((timed[i] - timed[i - 1]).total_seconds(), 0.0))
    return gaps


def _max_failure_streak(attempts: list[dict[str, Any]]) -> int:
    ordered = sorted(attempts, key=lambda x: (x.get("attempt_order") or 0, x.get("started_at") or ""))
    best = 0
    cur = 0
    for a in ordered:
        if a.get("outcome") == "FAILURE":
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def _success_after_failure(attempts: list[dict[str, Any]]) -> int:
    ordered = sorted(attempts, key=lambda x: (x.get("attempt_order") or 0, x.get("started_at") or ""))
    seen_fail = False
    for a in ordered:
        if a.get("outcome") == "FAILURE":
            seen_fail = True
        elif a.get("outcome") == "SUCCESS" and seen_fail:
            return 1
    return 0


def _failures_before_first_success(attempts: list[dict[str, Any]]) -> int:
    ordered = sorted(attempts, key=lambda x: (x.get("attempt_order") or 0, x.get("started_at") or ""))
    fails = 0
    for a in ordered:
        if a.get("outcome") == "FAILURE":
            fails += 1
        elif a.get("outcome") == "SUCCESS":
            return fails
    # No success: use all failed attempts (documented convention)
    return sum(1 for a in ordered if a.get("outcome") == "FAILURE")


def compute_behavior_features(
    attempt_history: list[dict[str, Any]],
    *,
    run: dict[str, Any] | None = None,
    sequence: dict[str, Any] | None = None,
    min_duration: float = 1e-3,
) -> dict[str, float]:
    """
    Compute deterministic behavioral features from ordered attempt history.

    Train-serving parity: P11 can call this with historical attempts up to now.
    Must NOT use target_label, scenario_id, planned counts, or future attempts.
    """
    attempts = list(attempt_history)
    total = len(attempts)
    failed = sum(1 for a in attempts if a.get("outcome") == "FAILURE")
    success = sum(1 for a in attempts if a.get("outcome") == "SUCCESS")
    unknown = sum(1 for a in attempts if a.get("outcome") == "UNKNOWN")
    # consistency: total should equal failed+success+unknown (+ other outcomes ignored as 0 contribution)

    failure_ratio = (failed / total) if total > 0 else 0.0
    duration = _duration_seconds(attempts, run=run, sequence=sequence, min_duration=min_duration)
    denom = max(duration, min_duration) if total > 0 else min_duration
    attempt_rate = (total / denom) if total > 0 else 0.0
    if not math.isfinite(attempt_rate):
        attempt_rate = 0.0

    is_fail = lambda a: a.get("outcome") == "FAILURE"
    is_succ = lambda a: a.get("outcome") == "SUCCESS"

    users = {a.get("user_id") for a in attempts if a.get("user_id")}
    gaps = _inter_attempt_gaps(attempts)
    multi = 1 if total > 1 else 0

    if gaps:
        min_gap = min(gaps)
        mean_gap = statistics.fmean(gaps)
        median_gap = statistics.median(gaps)
        std_gap = statistics.pstdev(gaps) if len(gaps) > 1 else 0.0
    else:
        min_gap = mean_gap = median_gap = std_gap = 0.0

    ordered = sorted(attempts, key=lambda x: (x.get("attempt_order") or 0, x.get("started_at") or ""))
    first_failed = 1 if ordered and ordered[0].get("outcome") == "FAILURE" else 0
    last_success = 1 if ordered and ordered[-1].get("outcome") == "SUCCESS" else 0

    features = {
        "total_attempts": float(total),
        "failed_attempts": float(failed),
        "successful_attempts": float(success),
        "unknown_attempts": float(unknown),
        "failure_ratio": float(failure_ratio),
        "duration_seconds": float(duration),
        "attempt_rate_per_second": float(attempt_rate),
        "failed_count_30s_max": rolling_count(attempts, window_seconds=30.0, predicate=is_fail),
        "failed_count_60s_max": rolling_count(attempts, window_seconds=60.0, predicate=is_fail),
        "failed_count_5m_max": rolling_count(attempts, window_seconds=300.0, predicate=is_fail),
        "success_count_5m_max": rolling_count(attempts, window_seconds=300.0, predicate=is_succ),
        "unique_users_total": float(len(users)),
        "unique_users_60s_max": rolling_unique_count(attempts, window_seconds=60.0, id_key="user_id"),
        "unique_sources_total": float(len({a.get("source_id") for a in attempts if a.get("source_id")})),
        "has_multiple_attempts": float(multi),
        "min_inter_attempt_gap_seconds": float(min_gap),
        "mean_inter_attempt_gap_seconds": float(mean_gap),
        "median_inter_attempt_gap_seconds": float(median_gap),
        "max_inter_attempt_gap_seconds": float(max(gaps) if gaps else 0.0),
        "std_inter_attempt_gap_seconds": float(std_gap),
        "max_failure_streak": float(_max_failure_streak(attempts)),
        "success_after_failure": float(_success_after_failure(attempts)),
        "failures_before_first_success": float(_failures_before_first_success(attempts)),
        "first_attempt_failed": float(first_failed),
        "last_attempt_success": float(last_success),
    }
    return features


FEATURE_DEFINITIONS = {
    "total_attempts": "Logical authentication attempts in the run",
    "failed_attempts": "Logical attempts with outcome=FAILURE",
    "successful_attempts": "Logical attempts with outcome=SUCCESS",
    "failure_ratio": "failed_attempts / total_attempts (0 if none)",
    "duration_seconds": "Run/sequence duration in seconds",
    "attempt_rate_per_second": "total_attempts / max(duration, eps)",
    "failed_count_30s_max": "Max FAILURE attempts in any inclusive 30s historical window",
    "failed_count_60s_max": "Max FAILURE attempts in any inclusive 60s historical window",
    "failed_count_5m_max": "Max FAILURE attempts in any inclusive 5m historical window",
    "success_count_5m_max": "Max SUCCESS attempts in any inclusive 5m historical window",
    "unique_users_total": "Unique user_id values in the run",
    "unique_users_60s_max": "Max unique user_id in any inclusive 60s window",
    "has_multiple_attempts": "1 if total_attempts > 1 else 0",
    "min_inter_attempt_gap_seconds": "Minimum gap between consecutive attempts (0 if single)",
    "mean_inter_attempt_gap_seconds": "Mean inter-attempt gap (0 if single)",
    "median_inter_attempt_gap_seconds": "Median inter-attempt gap (0 if single)",
    "std_inter_attempt_gap_seconds": "Population stdev of gaps (0 if <2 gaps)",
    "max_failure_streak": "Longest consecutive FAILURE streak",
    "success_after_failure": "1 if a SUCCESS occurs after at least one FAILURE",
    "failures_before_first_success": "FAILURE count before first SUCCESS; else all failures",
    "first_attempt_failed": "1 if first attempt outcome is FAILURE",
    "last_attempt_success": "1 if last attempt outcome is SUCCESS",
    "unique_sources_total": "Diagnostic: unique source_id (often constant in lab)",
    "unknown_attempts": "Logical attempts with outcome=UNKNOWN",
    "max_inter_attempt_gap_seconds": "Maximum inter-attempt gap",
}
