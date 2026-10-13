"""P12 service orchestration: ingest + alert worker + dashboard."""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from presentation.alert_worker import AlertWorker
from presentation.dashboard_app import create_app
from presentation.discord_client import DiscordClient
from presentation.p11_ingestor import P11Ingestor
from presentation.state_store import StateStore


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def discord_config_status(cfg: dict[str, Any]) -> dict[str, Any]:
    enabled_raw = os.environ.get(cfg["discord"]["enabled_env_var"], "false")
    enabled = str(enabled_raw).strip().lower() in {"1", "true", "yes", "on"}
    url = os.environ.get(cfg["discord"]["webhook_env_var"], "").strip()
    if not enabled:
        return {"ok": True, "enabled": False, "status": "DISABLED", "webhook_present": bool(url)}
    if not url:
        return {
            "ok": False,
            "enabled": True,
            "status": "MISCONFIGURED",
            "error": "P12_DISCORD_ENABLED=true but DISCORD_WEBHOOK_URL missing",
            "webhook_present": False,
        }
    return {"ok": True, "enabled": True, "status": "ENABLED", "webhook_present": True}


def dry_run(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    pred_path = root / cfg["p11"]["predictions_path"]
    schema = None
    if pred_path.is_file():
        for line in pred_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                schema = sorted(json.loads(line).keys())
                break
    dstat = discord_config_status(cfg)
    host = cfg["dashboard"]["host"]
    port = cfg["dashboard"]["port"]
    return {
        "p11_predictions": str(pred_path),
        "p11_events": str(root / cfg["p11"]["runtime_events_path"]),
        "p11_status": str(root / cfg["p11"]["status_path"]),
        "prediction_schema_keys": schema,
        "database": str(root / cfg["storage"]["sqlite_path"]),
        "dashboard_url": f"http://{host}:{port}/",
        "alert_policy": cfg["alert_policy"]["version"],
        "discord_mode": cfg["alert_policy"]["discord_mode"],
        "cooldown_seconds": cfg["alert_policy"]["cooldown_seconds"],
        "discord_enabled": dstat["enabled"],
        "discord_status": dstat["status"],
        "early_brute_force_enabled": bool(cfg["alert_policy"]["early_brute_force"]["enabled"]),
        "sends_discord": False,
    }


def validate(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    checks = {}
    for key, rel in [
        ("predictions", cfg["p11"]["predictions_path"]),
        ("events", cfg["p11"]["runtime_events_path"]),
        ("status", cfg["p11"]["status_path"]),
    ]:
        checks[key] = (root / rel).exists()
    dstat = discord_config_status(cfg)
    checks["discord_config"] = dstat["ok"]
    checks["dashboard_bind_localhost"] = cfg["dashboard"]["host"] in {"127.0.0.1", "localhost"}
    checks["privacy_no_raw_ip"] = cfg["privacy"]["allow_raw_ip"] is False
    # Ensure presentation does not import ML for normal path — structural check in tests
    ok = all(checks.values()) and dstat["ok"]
    return {"ok": ok, "checks": checks, "discord": dstat}


def init_state(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    store = StateStore(root / cfg["storage"]["sqlite_path"])
    ingestor = P11Ingestor(root, cfg, store)
    backfill = ingestor.first_start_backfill()
    # optionally ingest runtime events (sanitized already)
    events_path = root / cfg["p11"]["runtime_events_path"]
    ev_n = 0
    if events_path.is_file():
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if store.insert_runtime_event(ev):
                ev_n += 1
    counts = store.counts()
    store.close()
    return {
        "ok": True,
        "backfill": backfill,
        "runtime_events_ingested": ev_n,
        "counts": counts,
    }


class P12Service:
    def __init__(self, root: Path, cfg: dict[str, Any]):
        self.root = root
        self.cfg = cfg
        self.store = StateStore(root / cfg["storage"]["sqlite_path"])
        self.ingestor = P11Ingestor(root, cfg, self.store)
        self.discord = DiscordClient.from_env(cfg["discord"])
        self.worker = AlertWorker(
            self.store,
            self.discord,
            max_attempts=int(cfg["discord"].get("max_attempts", 3)),
            backoff_seconds=list(cfg["discord"].get("retry_backoff_seconds") or [1, 2, 4]),
        )
        self.service_state: dict[str, Any] = {
            "running": False,
            "started_at": None,
            "health": "HEALTHY",
            "discord_status": "ENABLED" if self.discord.enabled else "DISABLED",
            "predictions_ingested": 0,
            "alerts_created": 0,
            "alerts_sent": 0,
            "errors": 0,
        }
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

    def start_background(self) -> None:
        if self.store.get_meta("first_start_completed") != "1":
            self.ingestor.first_start_backfill()
        self.service_state["running"] = True
        self.service_state["started_at"] = utc_now()
        t1 = threading.Thread(target=self._ingest_loop, name="p12-ingest", daemon=True)
        t2 = threading.Thread(target=self._alert_loop, name="p12-alerts", daemon=True)
        self._threads = [t1, t2]
        t1.start()
        t2.start()

    def _ingest_loop(self) -> None:
        interval = float(self.cfg["ingestion"].get("poll_interval_ms", 250)) / 1000.0
        while not self._stop.is_set():
            try:
                result = self.ingestor.poll_once()
                self.service_state["predictions_ingested"] = self.ingestor.ingested
                self.service_state["alerts_created"] = self.ingestor.alerts_created
                self.service_state["errors"] = self.ingestor.errors
                self.service_state["last_ingest"] = result
                if self.service_state.get("health") == "DEGRADED_INGESTION":
                    self.service_state["health"] = "HEALTHY"
                    self.service_state.pop("last_error", None)
                self._write_status()
            except Exception as exc:  # noqa: BLE001
                self.service_state["health"] = "DEGRADED_INGESTION"
                self.service_state["last_error"] = f"{type(exc).__name__}: {exc}"
                self._write_status()
            self._stop.wait(interval)

    def _alert_loop(self) -> None:
        while not self._stop.is_set():
            try:
                if self.discord.enabled:
                    out = self.worker.process_once()
                    self.service_state["alerts_sent"] = self.store.counts()["alerts_sent"]
                    if out.get("failed"):
                        self.service_state["discord_status"] = "DEGRADED"
                        self.service_state["health"] = "DEGRADED_DISCORD"
                    else:
                        self.service_state["discord_status"] = "ENABLED"
                        if self.service_state.get("health") == "DEGRADED_DISCORD":
                            self.service_state["health"] = "HEALTHY"
                            self.service_state.pop("last_error", None)
                self._write_status()
            except Exception as exc:  # noqa: BLE001
                self.service_state["discord_status"] = "DEGRADED"
                self.service_state["health"] = "DEGRADED_DISCORD"
                self.service_state["last_error"] = f"{type(exc).__name__}: {exc}"
                self._write_status()
            self._stop.wait(0.5)

    def _write_status(self) -> None:
        path = self.root / self.cfg["storage"]["service_status_path"]
        payload = {
            **self.service_state,
            "counts": self.store.counts(),
            "updated_at": utc_now(),
        }
        write_json(path, payload)

    def stop(self) -> None:
        self._stop.set()
        self.service_state["running"] = False
        self._write_status()

    def run_blocking(self) -> None:
        self.start_background()
        app = create_app(
            root=self.root,
            cfg=self.cfg,
            store=self.store,
            service_state=self.service_state,
        )
        host = self.cfg["dashboard"]["host"]
        port = int(self.cfg["dashboard"]["port"])
        try:
            app.run(host=host, port=port, threaded=True, use_reloader=False)
        finally:
            self.stop()
            self.store.close()


def report(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    store = StateStore(root / cfg["storage"]["sqlite_path"])
    status_path = root / cfg["storage"]["service_status_path"]
    status = json.loads(status_path.read_text()) if status_path.is_file() else {}
    out = {
        "counts": store.counts(),
        "meta": {
            "first_start_completed": store.get_meta("first_start_completed"),
            "prediction_file_offset": store.get_meta("prediction_file_offset"),
            "schema_version": store.get_meta("schema_version"),
        },
        "service_status": status,
        "discord": discord_config_status(cfg),
    }
    store.close()
    return out
