"""Discord webhook client — never logs or returns the webhook URL."""

from __future__ import annotations

import os
from typing import Any

import requests


class DiscordClient:
    def __init__(
        self,
        *,
        webhook_url: str | None,
        timeout_seconds: float = 5.0,
        enabled: bool = False,
    ):
        self._url = webhook_url or ""
        self.timeout = float(timeout_seconds)
        self.enabled = bool(enabled) and bool(self._url)

    @classmethod
    def from_env(cls, cfg: dict[str, Any]) -> "DiscordClient":
        enabled_raw = os.environ.get(cfg.get("enabled_env_var", "P12_DISCORD_ENABLED"), "false")
        enabled = str(enabled_raw).strip().lower() in {"1", "true", "yes", "on"}
        url = os.environ.get(cfg.get("webhook_env_var", "DISCORD_WEBHOOK_URL"), "").strip()
        return cls(
            webhook_url=url or None,
            timeout_seconds=float(cfg.get("timeout_seconds", 5)),
            enabled=enabled,
        )

    def build_payload(self, alert: dict[str, Any]) -> dict[str, Any]:
        label = alert.get("predicted_label")
        severity = alert.get("severity")
        phase = alert.get("alert_phase")
        if phase == "PROVISIONAL_EARLY":
            title = "PROVISIONAL EARLY WARNING — Brute-Force Behavior"
        elif label == "BRUTE_FORCE":
            title = "🚨 Brute-Force Behavior Detected"
        elif label == "SUSPICIOUS":
            title = "⚠️ Suspicious SSH Activity"
        else:
            title = f"Alert — {label}"

        alert_id = str(alert.get("alert_key") or "")[:12]
        scores = (
            f"NORMAL: {float(alert.get('score_normal') or 0):.3f}\n"
            f"SUSPICIOUS: {float(alert.get('score_suspicious') or 0):.3f}\n"
            f"BRUTE_FORCE: {float(alert.get('score_brute_force') or 0):.3f}"
        )
        email = alert.get("lab_email") or alert.get("email")
        location = alert.get("lab_location") or alert.get("location")
        wrong = alert.get("lab_wrong_attempts")
        login_block = ""
        if email or location:
            login_block = (
                f"Login email: `{email or 'unknown'}`\n"
                f"Login location: `{location or 'unknown'}`\n"
            )
            if wrong is not None:
                login_block += f"Wrong password attempts: `{wrong}`\n"
        content = (
            f"**{title}**\n"
            f"Severity: `{severity}`\n"
            f"Predicted class: `{label}`\n"
            f"{login_block}"
            f"Runtime source ID: `{alert.get('source_id')}`\n"
            f"Episode ID: `{alert.get('episode_id')}`\n"
            f"Snapshot: `{alert.get('snapshot_type')}` ({phase})\n"
            f"Attempt count: `{alert.get('attempt_count')}`\n"
            f"Event timestamp: `{alert.get('event_timestamp')}`\n"
            f"Release ID: `{alert.get('release_id')}`\n"
            f"Model scores — uncalibrated:\n```\n{scores}\n```\n"
            f"Alert ID: `{alert_id}`"
        )
        return {
            "content": content,
            "allowed_mentions": {"parse": []},
        }

    def send(self, alert: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            return {
                "ok": False,
                "status_code": None,
                "error": "discord_disabled",
                "retryable": False,
            }
        payload = self.build_payload(alert)
        try:
            resp = requests.post(
                self._url,
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
        except requests.RequestException as exc:
            return {
                "ok": False,
                "status_code": None,
                "error": type(exc).__name__,
                "retryable": True,
                "retry_after": None,
            }
        status = resp.status_code
        retry_after = None
        if status == 429:
            try:
                retry_after = float(resp.headers.get("Retry-After") or 1)
            except ValueError:
                retry_after = 1.0
        ok = 200 <= status < 300
        permanent = status in {400, 401, 403, 404}
        return {
            "ok": ok,
            "status_code": status,
            "error": None if ok else f"http_{status}",
            "retryable": (not ok) and (not permanent),
            "retry_after": retry_after,
            "message_id": None,
        }

    def send_smoke_test(self) -> dict[str, Any]:
        alert = {
            "predicted_label": "SUSPICIOUS",
            "severity": "WARNING",
            "alert_phase": "TEST",
            "alert_key": "smoke-test-0000",
            "source_id": "SRC_RUNTIME_TEST",
            "episode_id": "EP_TEST_000",
            "snapshot_type": "EPISODE_FINAL",
            "attempt_count": 0,
            "event_timestamp": "n/a",
            "release_id": "rf-behavior-lab-v1.1.0",
            "score_normal": 0.0,
            "score_suspicious": 0.0,
            "score_brute_force": 0.0,
            "lab_email": "testuser2222@gmail.com",
            "lab_location": "Yangon, Myanmar",
            "lab_wrong_attempts": 0,
        }
        # Override content for smoke clarity
        if not self.enabled:
            return {"ok": False, "error": "discord_disabled_or_missing_webhook"}
        payload = {
            "content": (
                "**TEST ALERT — P12 Discord Integration**\n"
                "This is a non-threat connectivity check.\n"
                "Alert ID: `smoke-test`"
            ),
            "allowed_mentions": {"parse": []},
        }
        try:
            resp = requests.post(self._url, json=payload, timeout=self.timeout)
            return {"ok": 200 <= resp.status_code < 300, "status_code": resp.status_code}
        except requests.RequestException as exc:
            return {"ok": False, "error": type(exc).__name__}
