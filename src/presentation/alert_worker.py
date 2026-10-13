"""Discord outbox worker over durable alert rows."""

from __future__ import annotations

import time
from typing import Any

from presentation.discord_client import DiscordClient
from presentation.lab_api import latest_lab_session
from presentation.state_store import StateStore


def _enrich_with_lab_login(alert: dict[str, Any]) -> dict[str, Any]:
    """Attach latest Lab Login email/location onto the Discord alert payload."""
    sess = latest_lab_session()
    if not sess:
        return alert
    out = dict(alert)
    out["lab_email"] = sess.get("email")
    out["lab_location"] = sess.get("location")
    out["lab_wrong_attempts"] = sess.get("wrong_attempts")
    out["lab_session_status"] = sess.get("status")
    return out


class AlertWorker:
    def __init__(
        self,
        store: StateStore,
        client: DiscordClient,
        *,
        max_attempts: int = 3,
        backoff_seconds: list[float] | None = None,
    ):
        self.store = store
        self.client = client
        self.max_attempts = int(max_attempts)
        self.backoff = list(backoff_seconds or [1, 2, 4])

    def process_once(self) -> dict[str, Any]:
        pending = self.store.pending_alerts(limit=10)
        sent = 0
        failed = 0
        retried = 0
        for alert in pending:
            if not self.client.enabled:
                # Keep pending when Discord intentionally disabled after enqueue —
                # for disabled mode, policy should not enqueue PENDING.
                break
            key = alert["alert_key"]
            retries = int(alert.get("retry_count") or 0)
            self.store.mark_alert_sending(key)
            result = self.client.send(_enrich_with_lab_login(alert))
            if result.get("ok"):
                self.store.mark_alert_sent(
                    key,
                    http_status=result.get("status_code"),
                    message_id=result.get("message_id"),
                )
                sent += 1
                continue
            if result.get("retryable") and retries + 1 < self.max_attempts:
                self.store.mark_alert_retry(
                    key,
                    http_status=result.get("status_code"),
                    error=str(result.get("error") or "retryable"),
                )
                wait = result.get("retry_after")
                if wait is None:
                    idx = min(retries, len(self.backoff) - 1)
                    wait = self.backoff[idx]
                time.sleep(float(wait))
                retried += 1
            else:
                self.store.mark_alert_failed(
                    key,
                    http_status=result.get("status_code"),
                    error=str(result.get("error") or "permanent"),
                )
                failed += 1
        return {"sent": sent, "failed": failed, "retried": retried, "seen": len(pending)}
