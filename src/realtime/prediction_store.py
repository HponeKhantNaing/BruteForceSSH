"""Append-only runtime prediction / event / status stores (no raw identities)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _assert_no_secrets(obj: Any) -> None:
    text = json.dumps(obj, default=str)
    if IPV4.search(text):
        raise RuntimeError("refusing to persist raw IPv4 in runtime output")
    lowered = text.lower()
    if "password" in lowered and "auth_method" not in text:
        # allow auth_method":"password" only — block password values
        if re.search(r'"password"\s*:\s*"[^"]+"', text, re.I):
            raise RuntimeError("refusing to persist password field")


class PredictionStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def append(self, event: dict[str, Any]) -> None:
        _assert_no_secrets(event)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, sort_keys=False) + "\n")


class RuntimeEventStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def emit(self, kind: str, **payload: Any) -> None:
        row = {"timestamp": utc_now(), "event": kind, **payload}
        _assert_no_secrets(row)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=False) + "\n")


class StatusWriter:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.state: dict[str, Any] = {
            "running": False,
            "release_id": None,
            "log_source": None,
            "started_at": None,
            "last_log_timestamp": None,
            "last_prediction_timestamp": None,
            "active_episode_count": 0,
            "logical_attempts_processed": 0,
            "predictions_emitted": 0,
            "errors": 0,
        }

    def update(self, **kwargs: Any) -> None:
        self.state.update(kwargs)
        _assert_no_secrets(self.state)
        self.path.write_text(json.dumps(self.state, indent=2) + "\n", encoding="utf-8")
