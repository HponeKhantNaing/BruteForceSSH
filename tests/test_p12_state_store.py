"""SQLite state store uniqueness and transactions."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from presentation.state_store import StateStore, alert_key_for, event_key_for  # noqa: E402


def _pred(i=1):
    return {
        "release_id": "rf-behavior-lab-v1.0.0",
        "episode_id": "EP_X",
        "source_id": "SRC_RUNTIME_001",
        "snapshot_type": "EPISODE_FINAL",
        "provisional": False,
        "final": True,
        "attempt_count": i,
        "event_timestamp": f"2026-09-27T10:00:0{i}+00:00",
        "predicted_label": "BRUTE_FORCE",
        "class_probabilities": {"NORMAL": 0.1, "SUSPICIOUS": 0.2, "BRUTE_FORCE": 0.7},
        "probability_type": "uncalibrated",
    }


def test_unique_event_and_alert_keys(tmp_path):
    store = StateStore(tmp_path / "t.sqlite3")
    pred = _pred()
    decision = {
        "decision": "SEND_FINAL_BRUTE_FORCE",
        "delivery_state": "PENDING",
        "severity": "CRITICAL",
        "alert_phase": "FINAL",
        "send_discord": True,
        "suppressed_reason": None,
    }
    r1 = store.ingest_prediction(
        pred,
        historical_backfill=False,
        alert_eligible=True,
        policy_version="p12-alert-v1",
        alert_decision=decision,
        file_offset=10,
        file_inode="1",
    )
    r2 = store.ingest_prediction(
        pred,
        historical_backfill=False,
        alert_eligible=True,
        policy_version="p12-alert-v1",
        alert_decision=decision,
        file_offset=20,
        file_inode="1",
    )
    assert r1["inserted"] is True
    assert r2["inserted"] is False
    assert store.counts()["predictions"] == 1
    assert store.counts()["alerts"] == 1
    ek = event_key_for(pred)
    assert alert_key_for("p12-alert-v1", ek, "FINAL") == r1["alert"]["alert_key"]
    store.close()
