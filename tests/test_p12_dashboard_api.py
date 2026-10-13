"""Dashboard API tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from presentation.dashboard_app import create_app  # noqa: E402
from presentation.p12_service import load_yaml  # noqa: E402
from presentation.state_store import StateStore  # noqa: E402


def test_dashboard_api_endpoints(tmp_path):
    cfg = load_yaml(ROOT / "config" / "p12_dashboard_alerts.yaml")
    cfg = json.loads(json.dumps(cfg))
    # point p11 status to empty file
    p11 = tmp_path / "data/runtime/p11"
    p11.mkdir(parents=True)
    (p11 / "status.json").write_text(json.dumps({"running": False}), encoding="utf-8")
    cfg["p11"]["status_path"] = "data/runtime/p11/status.json"
    store = StateStore(tmp_path / "db.sqlite3")
    pred = {
        "release_id": "rf-behavior-lab-v1.0.0",
        "episode_id": "EP_1",
        "source_id": "SRC_RUNTIME_001",
        "snapshot_type": "EPISODE_FINAL",
        "provisional": False,
        "final": True,
        "attempt_count": 2,
        "event_timestamp": "2026-09-27T10:00:00+00:00",
        "predicted_label": "SUSPICIOUS",
        "class_probabilities": {"NORMAL": 0.2, "SUSPICIOUS": 0.7, "BRUTE_FORCE": 0.1},
        "probability_type": "uncalibrated",
    }
    store.ingest_prediction(
        pred,
        historical_backfill=False,
        alert_eligible=True,
        policy_version="p12-alert-v1",
        alert_decision={
            "decision": "SEND_FINAL_SUSPICIOUS",
            "delivery_state": "PENDING",
            "severity": "WARNING",
            "alert_phase": "FINAL",
            "send_discord": True,
            "suppressed_reason": None,
        },
        file_offset=1,
        file_inode="1",
    )
    app = create_app(root=tmp_path, cfg=cfg, store=store, service_state={"health": "HEALTHY", "discord_status": "DISABLED"})
    client = app.test_client()
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/status").status_code == 200
    summary = client.get("/api/summary").get_json()
    assert summary["predictions_ingested"] == 1
    preds = client.get("/api/predictions?label=SUSPICIOUS").get_json()
    assert len(preds["items"]) == 1
    assert client.get("/api/alerts").status_code == 200
    model = client.get("/api/model").get_json()
    assert "uncalibrated" in model["note"].lower()
    assert "webhook" not in json.dumps(model).lower()
    html = client.get("/").data.decode("utf-8")
    assert "BruteWatch" in html or "root" in html or "AI Server Threat Monitor" in html
    assert "DISCORD_WEBHOOK" not in html
    assert client.get("/api/lab/status").status_code == 200
    store.close()
