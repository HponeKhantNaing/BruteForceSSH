"""Ingestion: backfill, live append, dedup, malformed lines."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from presentation.p11_ingestor import P11Ingestor  # noqa: E402
from presentation.p12_service import load_yaml  # noqa: E402
from presentation.state_store import StateStore  # noqa: E402


def _cfg(tmp_path: Path, pred_file: Path):
    cfg = load_yaml(ROOT / "config" / "p12_dashboard_alerts.yaml")
    cfg = json.loads(json.dumps(cfg))  # deep copy
    cfg["p11"]["predictions_path"] = str(pred_file.relative_to(tmp_path)) if False else str(pred_file)
    # Use absolute via monkey by setting root=tmp_path and paths relative
    return cfg


def test_backfill_no_alerts_then_live_alert(tmp_path):
    root = tmp_path
    p11 = root / "data/runtime/p11"
    p11.mkdir(parents=True)
    pred_path = p11 / "predictions.jsonl"
    hist = {
        "schema_version": "1.0",
        "release_id": "rf-behavior-lab-v1.0.0",
        "episode_id": "EP_OLD",
        "source_id": "SRC_RUNTIME_001",
        "snapshot_type": "EPISODE_FINAL",
        "provisional": False,
        "final": True,
        "attempt_count": 3,
        "event_timestamp": "2026-09-27T09:00:00+00:00",
        "predicted_label": "BRUTE_FORCE",
        "class_probabilities": {"NORMAL": 0.1, "SUSPICIOUS": 0.1, "BRUTE_FORCE": 0.8},
        "probability_type": "uncalibrated",
    }
    pred_path.write_text(json.dumps(hist) + "\n", encoding="utf-8")
    (p11 / "runtime_events.jsonl").write_text("", encoding="utf-8")
    (p11 / "status.json").write_text("{}", encoding="utf-8")

    cfg = load_yaml(ROOT / "config" / "p12_dashboard_alerts.yaml")
    cfg = json.loads(json.dumps(cfg))
    cfg["p11"]["predictions_path"] = "data/runtime/p11/predictions.jsonl"
    cfg["storage"]["sqlite_path"] = "data/runtime/p12/p12_state.sqlite3"

    store = StateStore(root / cfg["storage"]["sqlite_path"])
    ing = P11Ingestor(root, cfg, store)
    bf = ing.first_start_backfill()
    assert bf["historical_found"] == 1
    assert bf["discord_alerts_from_backfill"] == 0
    assert store.counts()["alerts_sent"] == 0
    # backfill creates NOT_REQUIRED alert row possibly
    pending = store.pending_alerts()
    assert pending == []

    live = dict(hist)
    live["episode_id"] = "EP_NEW"
    live["event_timestamp"] = "2026-09-27T11:00:00+00:00"
    live["attempt_count"] = 4
    with pred_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(live) + "\n")
    out = ing.poll_once()
    assert out["inserted"] == 1
    pending = store.pending_alerts()
    assert len(pending) == 1
    assert pending[0]["predicted_label"] == "BRUTE_FORCE"
    store.close()


def test_malformed_json_skipped(tmp_path):
    root = tmp_path
    p11 = root / "data/runtime/p11"
    p11.mkdir(parents=True)
    pred_path = p11 / "predictions.jsonl"
    pred_path.write_text("{not-json\n", encoding="utf-8")
    cfg = load_yaml(ROOT / "config" / "p12_dashboard_alerts.yaml")
    cfg = json.loads(json.dumps(cfg))
    cfg["p11"]["predictions_path"] = "data/runtime/p11/predictions.jsonl"
    cfg["storage"]["sqlite_path"] = "data/runtime/p12/t.sqlite3"
    store = StateStore(root / cfg["storage"]["sqlite_path"])
    store.set_meta("first_start_completed", "1")
    store.set_meta("prediction_file_offset", "0")
    store._conn.commit()
    ing = P11Ingestor(root, cfg, store)
    out = ing.poll_once()
    assert out["inserted"] == 0
    assert ing.errors >= 1
    store.close()
