"""Lab API unit tests (no live SSH required for validation/rate-limit paths)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from presentation.dashboard_app import create_app  # noqa: E402
from presentation.lab_api import lab_status_payload  # noqa: E402
from presentation.p12_service import load_yaml  # noqa: E402
from presentation.state_store import StateStore  # noqa: E402


def test_lab_status_endpoint(tmp_path):
    cfg = load_yaml(ROOT / "config" / "p12_dashboard_alerts.yaml")
    cfg = json.loads(json.dumps(cfg))
    p11 = tmp_path / "data/runtime/p11"
    p11.mkdir(parents=True)
    (p11 / "status.json").write_text(json.dumps({"running": False}), encoding="utf-8")
    cfg["p11"]["status_path"] = "data/runtime/p11/status.json"
    store = StateStore(tmp_path / "db.sqlite3")
    app = create_app(
        root=tmp_path,
        cfg=cfg,
        store=store,
        service_state={"health": "HEALTHY", "discord_status": "DISABLED"},
    )
    client = app.test_client()
    r = client.get("/api/lab/status")
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert body["lab"]["host"] == "127.0.0.1"
    assert "password" not in json.dumps(body).lower()
    store.close()


def test_lab_attempt_validation(tmp_path):
    cfg = load_yaml(ROOT / "config" / "p12_dashboard_alerts.yaml")
    cfg = json.loads(json.dumps(cfg))
    store = StateStore(tmp_path / "db.sqlite3")
    app = create_app(
        root=tmp_path,
        cfg=cfg,
        store=store,
        service_state={"health": "HEALTHY", "discord_status": "DISABLED"},
    )
    client = app.test_client()
    bad = client.post("/api/lab/attempt", json={"mode": "once", "username": "", "password": "x"})
    assert bad.status_code == 400
    bad_mode = client.post(
        "/api/lab/attempt",
        json={"mode": "hack", "username": "testuser", "password": "x"},
    )
    assert bad_mode.status_code == 400
    store.close()


def test_lab_status_payload_shape():
    payload = lab_status_payload()
    assert "lab" in payload
    assert "limits" in payload
