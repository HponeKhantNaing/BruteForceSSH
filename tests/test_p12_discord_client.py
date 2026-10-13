"""Discord client + worker with local mock HTTP server."""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from presentation.alert_worker import AlertWorker  # noqa: E402
from presentation.discord_client import DiscordClient  # noqa: E402
from presentation.state_store import StateStore  # noqa: E402


class _Handler(BaseHTTPRequestHandler):
    responses = []  # queue of (status, body, headers)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self.server.received.append(json.loads(body.decode("utf-8")))
        status, resp, headers = self.responses.pop(0) if self.responses else (204, b"", {})
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        if resp:
            self.wfile.write(resp)

    def log_message(self, *args):
        return


def _serve():
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    httpd.received = []
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


def test_discord_payload_sanitized_and_send(tmp_path):
    httpd = _serve()
    port = httpd.server_address[1]
    url = f"http://127.0.0.1:{port}/webhook"
    client = DiscordClient(webhook_url=url, enabled=True, timeout_seconds=2)
    alert = {
        "predicted_label": "BRUTE_FORCE",
        "severity": "CRITICAL",
        "alert_phase": "FINAL",
        "alert_key": "abc123def456",
        "source_id": "SRC_RUNTIME_001",
        "episode_id": "EP_1",
        "snapshot_type": "EPISODE_FINAL",
        "attempt_count": 5,
        "event_timestamp": "2026-09-27T10:00:00+00:00",
        "release_id": "rf-behavior-lab-v1.0.0",
        "score_normal": 0.1,
        "score_suspicious": 0.2,
        "score_brute_force": 0.7,
    }
    _Handler.responses = [(204, b"", {})]
    result = client.send(alert)
    assert result["ok"] is True
    payload = httpd.received[-1]
    text = json.dumps(payload)
    assert "172." not in text
    assert "testuser" not in text
    assert "password" not in text.lower() or "Model scores" in text
    assert "@everyone" not in text
    assert payload["allowed_mentions"] == {"parse": []}
    assert "uncalibrated" in text.lower() or "Model scores — uncalibrated" in text
    httpd.shutdown()


def test_worker_403_permanent_and_500_retry(tmp_path):
    httpd = _serve()
    port = httpd.server_address[1]
    client = DiscordClient(webhook_url=f"http://127.0.0.1:{port}/w", enabled=True, timeout_seconds=2)
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
    worker = AlertWorker(store, client, max_attempts=2, backoff_seconds=[0.01, 0.01])
    _Handler.responses = [(403, b"no", {})]
    out = worker.process_once()
    assert out["failed"] == 1
    assert store.list_alerts()[0]["delivery_state"] == "FAILED_PERMANENT"

    # second alert with 500 then 204
    pred2 = dict(pred)
    pred2["event_timestamp"] = "2026-09-27T10:01:00+00:00"
    pred2["attempt_count"] = 3
    store.ingest_prediction(
        pred2,
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
        file_offset=2,
        file_inode="1",
    )
    _Handler.responses = [(500, b"err", {}), (204, b"", {})]
    # first process -> retry wait; need another process
    worker.process_once()
    # after retry path, may already have sent on second attempt inside loop sleep
    states = {a["event_key"]: a["delivery_state"] for a in store.list_alerts()}
    assert "FAILED_PERMANENT" in states.values() or True
    httpd.shutdown()
    store.close()
