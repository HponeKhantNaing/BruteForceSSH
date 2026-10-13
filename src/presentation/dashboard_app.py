"""Flask dashboard API + SPA shell for P12 (localhost only by default)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory

from presentation.lab_api import register_lab_routes
from presentation.state_store import StateStore


def create_app(
    *,
    root: Path,
    cfg: dict[str, Any],
    store: StateStore,
    service_state: dict[str, Any],
) -> Flask:
    spa_dir = root / "web" / "dist"
    app = Flask(
        __name__,
        static_folder=None,
    )
    app.config["MAX_CONTENT_LENGTH"] = 1_000_000
    app.config["SPA_DIR"] = spa_dir

    @app.after_request
    def security_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "img-src 'self' data:; "
            "font-src 'self' data: https://fonts.gstatic.com; "
            "connect-src 'self'; object-src 'none'; base-uri 'self'"
        )
        return resp

    def p11_health() -> dict[str, Any]:
        status_path = root / cfg["p11"]["status_path"]
        stale_after = float(cfg["p11"].get("stale_after_seconds", 10))
        if not status_path.is_file():
            return {"state": "OFFLINE", "raw": None}
        try:
            raw = json.loads(status_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"state": "OFFLINE", "raw": None}
        # Idle monitors still have running=true; do not treat old started_at as STALE.
        ts = raw.get("last_prediction_timestamp") or raw.get("last_log_timestamp")
        age = None
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                age = (datetime.now(timezone.utc) - dt).total_seconds()
            except ValueError:
                age = None
        if raw.get("running"):
            state = "ONLINE"
        elif age is not None and age <= stale_after:
            state = "STALE"
        else:
            state = "OFFLINE"
        return {"state": state, "age_seconds": age, "raw": raw}

    def discord_status() -> str:
        return str(service_state.get("discord_status") or "DISABLED")

    def spa_index():
        index = spa_dir / "index.html"
        if index.is_file():
            return send_from_directory(spa_dir, "index.html")
        return (
            "<!doctype html><html><body style='font-family:system-ui;padding:2rem'>"
            "<h1>BruteWatch</h1>"
            "<p>TypeScript UI not built. Run <code>cd web && npm install && npm run build</code>.</p>"
            "</body></html>"
        ), 200, {"Content-Type": "text/html; charset=utf-8"}

    @app.get("/")
    def index():
        return spa_index()

    @app.get("/monitor")
    @app.get("/alerts")
    @app.get("/lab")
    def spa_routes():
        return spa_index()

    @app.get("/assets/<path:asset_path>")
    def spa_assets(asset_path: str):
        assets = spa_dir / "assets"
        if not assets.is_dir():
            return jsonify({"error": "assets_missing"}), 404
        return send_from_directory(assets, asset_path)

    @app.get("/api/health")
    def api_health():
        p11 = p11_health()
        counts = store.counts()
        return jsonify(
            {
                "p12_status": service_state.get("health", "HEALTHY"),
                "p11_status": p11["state"],
                "discord_status": discord_status(),
                "database_status": "OK" if store.db_path.is_file() else "MISSING",
                "release_id": cfg["model_info"]["release_id"],
                "predictions": counts["predictions"],
                "alerts_sent": counts["alerts_sent"],
            }
        )

    @app.get("/api/status")
    def api_status():
        return jsonify(
            {
                "service": service_state,
                "p11": p11_health(),
                "counts": store.counts(),
                "discord_status": discord_status(),
            }
        )

    @app.get("/api/summary")
    def api_summary():
        c = store.counts()
        return jsonify(
            {
                "predictions_ingested": c["predictions"],
                "normal": c["by_label"].get("NORMAL", 0),
                "suspicious": c["by_label"].get("SUSPICIOUS", 0),
                "brute_force": c["by_label"].get("BRUTE_FORCE", 0),
                "alerts_sent": c["alerts_sent"],
                "alerts_pending": c["alerts_pending"],
                "alerts_failed": c["alerts_failed"],
                "activity": store.recent_activity_buckets(),
            }
        )

    @app.get("/api/predictions")
    def api_predictions():
        label = request.args.get("label")
        snapshot = request.args.get("snapshot_type")
        alerts_only = request.args.get("alerts_only", "false").lower() == "true"
        limit = min(int(request.args.get("limit", 100)), int(cfg["dashboard"].get("max_api_limit", 500)))
        offset = max(0, int(request.args.get("offset", 0)))
        if label and label not in {"NORMAL", "SUSPICIOUS", "BRUTE_FORCE"}:
            return jsonify({"error": "invalid label"}), 400
        if snapshot and snapshot not in {"ACTIVE_PREFIX", "EPISODE_FINAL"}:
            return jsonify({"error": "invalid snapshot_type"}), 400
        rows = store.list_predictions(
            label=label,
            snapshot_type=snapshot,
            alerts_only=alerts_only,
            limit=limit,
            offset=offset,
        )
        return jsonify({"items": rows, "limit": limit, "offset": offset})

    @app.get("/api/alerts")
    def api_alerts():
        limit = min(int(request.args.get("limit", 100)), 500)
        offset = max(0, int(request.args.get("offset", 0)))
        return jsonify({"items": store.list_alerts(limit=limit, offset=offset)})

    @app.get("/api/events")
    def api_events():
        rows = store._conn.execute(
            "SELECT event_type, timestamp, payload_json FROM runtime_events ORDER BY id DESC LIMIT 100"
        ).fetchall()
        items = []
        for r in rows:
            items.append(
                {
                    "event_type": r["event_type"],
                    "timestamp": r["timestamp"],
                    "payload": json.loads(r["payload_json"]) if r["payload_json"] else {},
                }
            )
        return jsonify({"items": items})

    @app.get("/api/model")
    def api_model():
        return jsonify(
            {
                **cfg["model_info"],
                "note": "Probabilities are uncalibrated model scores, not confidence.",
                "limitation": (
                    "Controlled-lab model. Results are monitoring signals, "
                    "not a production security guarantee."
                ),
            }
        )

    register_lab_routes(app)
    return app
