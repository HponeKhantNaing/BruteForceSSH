"""Runtime outputs must not persist raw IPs/usernames/passwords."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from realtime.prediction_store import PredictionStore  # noqa: E402

IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def test_prediction_store_rejects_raw_ip(tmp_path):
    store = PredictionStore(tmp_path / "predictions.jsonl")
    with pytest.raises(RuntimeError):
        store.append({"source_id": "10.0.0.5", "predicted_label": "NORMAL"})


def test_unique_users_runtime_tokens_not_raw():
    # Feature path uses USR_RUNTIME_* tokens — ensure contract example has no IPv4
    from datetime import datetime, timezone

    from realtime.context_manager import ContextManager

    cm = ContextManager(idle_timeout_seconds=30, max_episode_duration_seconds=300)
    t = datetime(2026, 9, 27, 10, 0, 0, tzinfo=timezone.utc)
    for i, user in enumerate(("alice", "bob", "carol"), start=1):
        cm.on_attempt(
            {
                "attempt_id": user,
                "attempt_order": i,
                "started_at": t.isoformat(),
                "ended_at": t.isoformat(),
                "outcome": "FAILURE",
                "source_ip": "203.0.113.10",
                "username_raw": user,
            },
            as_of=t,
        )
    ep = list(cm.episodes.values())[0]
    users = {a["user_id"] for a in ep.attempts}
    assert users == {"USR_RUNTIME_001", "USR_RUNTIME_002", "USR_RUNTIME_003"}
    assert ep.source_token.startswith("SRC_RUNTIME_")
    from realtime.feature_state import compute_episode_features

    feats = compute_episode_features(
        ep.attempts,
        ordered_features=[
            "unique_users_total",
            "unique_users_60s_max",
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
        ],
    )
    assert feats["unique_users_total"] == 3.0
    assert feats["unique_users_60s_max"] == 3.0
    # persisted-style payload
    payload = {"source_id": ep.source_token, "users": list(users)}
    assert not IPV4.search(json.dumps(payload))
