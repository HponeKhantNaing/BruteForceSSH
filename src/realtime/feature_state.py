"""Episode feature snapshots via P7 compute_behavior_features (train-serving parity)."""

from __future__ import annotations

from typing import Any

from features.behavioral_features import DEFAULT_FEATURE_NAMES, compute_behavior_features


def compute_episode_features(
    attempts: list[dict[str, Any]],
    *,
    ordered_features: list[str] | None = None,
    run: dict[str, Any] | None = None,
    sequence: dict[str, Any] | None = None,
    min_duration: float = 1e-3,
) -> dict[str, float]:
    """
    Build the exact model feature dict by reusing P7 formulas.

    Historical parity: pass P6 run + sequence so duration_seconds matches training.
    Live episodes: omit run/sequence; duration uses attempt timestamp span
    (last relevant attempt time — never idle-timeout wall time).
    """
    names = list(ordered_features or DEFAULT_FEATURE_NAMES)
    # Live: synthesize a minimal run envelope from attempts so duration uses
    # first→last attempt times without inventing idle wait.
    live_run = run
    if live_run is None and attempts:
        started = attempts[0].get("started_at")
        ended = attempts[-1].get("ended_at") or attempts[-1].get("started_at")
        live_run = {"started_at": started, "ended_at": ended}

    full = compute_behavior_features(
        attempts,
        run=live_run,
        sequence=sequence,
        min_duration=min_duration,
    )
    return {k: float(full[k]) for k in names if k in full}
