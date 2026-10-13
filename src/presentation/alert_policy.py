"""Deterministic P12 alert policy (no probability thresholds)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SEVERITY = {
    "NORMAL": "INFO",
    "SUSPICIOUS": "WARNING",
    "BRUTE_FORCE": "CRITICAL",
}

SEVERITY_RANK = {"INFO": 0, "WARNING": 1, "CRITICAL": 2}


@dataclass
class AlertDecision:
    decision: str
    delivery_state: str
    severity: str
    alert_phase: str
    send_discord: bool
    suppressed_reason: str | None = None


def evaluate_alert(
    prediction: dict[str, Any],
    *,
    policy_cfg: dict[str, Any],
    alert_eligible: bool,
    last_sent: dict[str, Any] | None = None,
    now_epoch: float | None = None,
    consecutive_prefix_brute: int = 0,
) -> AlertDecision:
    """
    Pure policy: prediction + config + recent alert state → decision.

    Never reinterpret predicted_label using class probabilities.
    """
    label = str(prediction.get("predicted_label") or "")
    snapshot = str(prediction.get("snapshot_type") or "")
    provisional = bool(prediction.get("provisional"))
    final = bool(prediction.get("final")) or snapshot == "EPISODE_FINAL"
    severity = SEVERITY.get(label, "INFO")
    cooldown = float(policy_cfg.get("cooldown_seconds", 60))
    early_cfg = policy_cfg.get("early_brute_force") or {}
    early_enabled = bool(early_cfg.get("enabled", False))
    early_need = int(early_cfg.get("consecutive_prefix_required", 2))

    if not alert_eligible:
        return AlertDecision(
            decision="NO_ALERT_HISTORICAL_BACKFILL",
            delivery_state="NOT_REQUIRED",
            severity=severity,
            alert_phase="BACKFILL",
            send_discord=False,
            suppressed_reason="historical_backfill",
        )

    if label == "NORMAL":
        return AlertDecision(
            decision="NO_ALERT_NORMAL",
            delivery_state="NOT_REQUIRED",
            severity=severity,
            alert_phase="NORMAL",
            send_discord=False,
        )

    # Optional early BRUTE_FORCE on ACTIVE_PREFIX
    if (
        early_enabled
        and snapshot == "ACTIVE_PREFIX"
        and label == "BRUTE_FORCE"
        and consecutive_prefix_brute >= early_need
    ):
        decision = _apply_cooldown(
            AlertDecision(
                decision="SEND_EARLY_BRUTE_FORCE",
                delivery_state="PENDING",
                severity="CRITICAL",
                alert_phase="PROVISIONAL_EARLY",
                send_discord=True,
            ),
            last_sent=last_sent,
            severity="CRITICAL",
            cooldown=cooldown,
            now_epoch=now_epoch,
        )
        return decision

    if snapshot == "ACTIVE_PREFIX" or provisional:
        return AlertDecision(
            decision="NO_ALERT_PROVISIONAL",
            delivery_state="NOT_REQUIRED",
            severity=severity,
            alert_phase="PROVISIONAL",
            send_discord=False,
            suppressed_reason="active_prefix_dashboard_only",
        )

    if not final:
        return AlertDecision(
            decision="NO_ALERT_PROVISIONAL",
            delivery_state="NOT_REQUIRED",
            severity=severity,
            alert_phase="PROVISIONAL",
            send_discord=False,
            suppressed_reason="non_final",
        )

    if label == "SUSPICIOUS":
        base = AlertDecision(
            decision="SEND_FINAL_SUSPICIOUS",
            delivery_state="PENDING",
            severity="WARNING",
            alert_phase="FINAL",
            send_discord=True,
        )
        return _apply_cooldown(base, last_sent=last_sent, severity="WARNING", cooldown=cooldown, now_epoch=now_epoch)

    if label == "BRUTE_FORCE":
        base = AlertDecision(
            decision="SEND_FINAL_BRUTE_FORCE",
            delivery_state="PENDING",
            severity="CRITICAL",
            alert_phase="FINAL",
            send_discord=True,
        )
        return _apply_cooldown(base, last_sent=last_sent, severity="CRITICAL", cooldown=cooldown, now_epoch=now_epoch)

    return AlertDecision(
        decision="NO_ALERT_UNKNOWN_LABEL",
        delivery_state="NOT_REQUIRED",
        severity="INFO",
        alert_phase="UNKNOWN",
        send_discord=False,
        suppressed_reason="unknown_label",
    )


def _apply_cooldown(
    decision: AlertDecision,
    *,
    last_sent: dict[str, Any] | None,
    severity: str,
    cooldown: float,
    now_epoch: float | None,
) -> AlertDecision:
    if not last_sent or now_epoch is None:
        return decision
    last_sev = str(last_sent.get("severity") or "INFO")
    last_ts = float(last_sent.get("sent_at_epoch") or 0.0)
    age = now_epoch - last_ts
    if age < 0:
        age = 0
    if age >= cooldown:
        return decision
    # Higher severity bypasses cooldown
    if SEVERITY_RANK.get(severity, 0) > SEVERITY_RANK.get(last_sev, 0):
        decision.decision = "SEND_ESCALATION"
        return decision
    decision.send_discord = False
    decision.delivery_state = "SUPPRESSED_COOLDOWN"
    decision.suppressed_reason = "cooldown"
    decision.decision = "SUPPRESS_COOLDOWN"
    return decision
