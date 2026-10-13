"""Rolling window helpers for behavioral features (train-serving parity).

Window policy: inclusive closed interval [anchor - W, anchor].
Only attempts with timestamp <= anchor are considered (no future leakage).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _as_seconds(dt: datetime) -> float:
    return dt.timestamp()


def rolling_count(
    attempts: list[dict[str, Any]],
    *,
    window_seconds: float,
    predicate: Callable[[dict[str, Any]], bool] | None = None,
    timestamp_key: str = "started_at",
) -> float:
    """
    Maximum count of matching attempts in any historical window ending at an attempt.

    For each attempt i as anchor at time t_i, count attempts j with:
      t_i - W <= t_j <= t_i
    and predicate(j) True.
    """
    timed: list[tuple[float, dict[str, Any]]] = []
    for a in attempts:
        dt = parse_ts(a.get(timestamp_key))
        if dt is None:
            continue
        timed.append((_as_seconds(dt), a))
    timed.sort(key=lambda x: x[0])
    if not timed:
        return 0.0

    max_count = 0
    left = 0
    for right, (t_r, a_r) in enumerate(timed):
        # advance left to keep window [t_r - W, t_r]
        while left <= right and timed[left][0] < t_r - window_seconds:
            left += 1
        count = 0
        for k in range(left, right + 1):
            if predicate is None or predicate(timed[k][1]):
                count += 1
        if count > max_count:
            max_count = count
    return float(max_count)


def rolling_unique_count(
    attempts: list[dict[str, Any]],
    *,
    window_seconds: float,
    id_key: str = "user_id",
    timestamp_key: str = "started_at",
) -> float:
    """Maximum unique id_key values in any inclusive historical window."""
    timed: list[tuple[float, str | None]] = []
    for a in attempts:
        dt = parse_ts(a.get(timestamp_key))
        if dt is None:
            continue
        timed.append((_as_seconds(dt), a.get(id_key)))
    timed.sort(key=lambda x: x[0])
    if not timed:
        return 0.0

    max_unique = 0
    left = 0
    for right, (t_r, _) in enumerate(timed):
        while left <= right and timed[left][0] < t_r - window_seconds:
            left += 1
        ids = {timed[k][1] for k in range(left, right + 1) if timed[k][1]}
        max_unique = max(max_unique, len(ids))
    return float(max_unique)


def rolling_count_at_anchor(
    history: list[dict[str, Any]],
    *,
    anchor_ts: str | datetime,
    window_seconds: float,
    predicate: Callable[[dict[str, Any]], bool] | None = None,
    timestamp_key: str = "started_at",
) -> float:
    """Count matching attempts in [anchor-W, anchor] — for online/P11 reuse."""
    if isinstance(anchor_ts, str):
        anchor = parse_ts(anchor_ts)
    else:
        anchor = anchor_ts
    if anchor is None:
        return 0.0
    t_a = _as_seconds(anchor)
    count = 0
    for a in history:
        dt = parse_ts(a.get(timestamp_key))
        if dt is None:
            continue
        t = _as_seconds(dt)
        if t_a - window_seconds <= t <= t_a:
            if predicate is None or predicate(a):
                count += 1
    return float(count)
