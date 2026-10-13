"""Alert worker durability helpers."""

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


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.send_response(204)
        self.end_headers()

    def log_message(self, *a):
        return


def test_outbox_send_marks_sent(tmp_path):
    httpd = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
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
        "predicted_label": "BRUTE_FORCE",
        "class_probabilities": {"NORMAL": 0.05, "SUSPICIOUS": 0.1, "BRUTE_FORCE": 0.85},
        "probability_type": "uncalibrated",
    }
    store.ingest_prediction(
        pred,
        historical_backfill=False,
        alert_eligible=True,
        policy_version="p12-alert-v1",
        alert_decision={
            "decision": "SEND_FINAL_BRUTE_FORCE",
            "delivery_state": "PENDING",
            "severity": "CRITICAL",
            "alert_phase": "FINAL",
            "send_discord": True,
            "suppressed_reason": None,
        },
        file_offset=1,
        file_inode="1",
    )
    client = DiscordClient(
        webhook_url=f"http://127.0.0.1:{httpd.server_address[1]}/hook",
        enabled=True,
    )
    worker = AlertWorker(store, client, max_attempts=3, backoff_seconds=[0.01])
    out = worker.process_once()
    assert out["sent"] == 1
    assert store.counts()["alerts_sent"] == 1
    # restart: same alert not pending
    out2 = worker.process_once()
    assert out2["seen"] == 0
    httpd.shutdown()
    store.close()
