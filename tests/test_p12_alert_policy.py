"""Alert policy unit tests — no probability thresholds."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from presentation.alert_policy import evaluate_alert  # noqa: E402

POLICY = {
    "version": "p12-alert-v1",
    "cooldown_seconds": 60,
    "early_brute_force": {"enabled": False, "consecutive_prefix_required": 2},
}


def _pred(label, snapshot, **kw):
    return {
        "predicted_label": label,
        "snapshot_type": snapshot,
        "provisional": snapshot == "ACTIVE_PREFIX",
        "final": snapshot == "EPISODE_FINAL",
        "source_id": "SRC_RUNTIME_001",
        "episode_id": "EP_1",
        "class_probabilities": kw.get("probs", {"NORMAL": 0.1, "SUSPICIOUS": 0.2, "BRUTE_FORCE": 0.7}),
        **{k: v for k, v in kw.items() if k != "probs"},
    }


def test_normal_final_no_discord():
    d = evaluate_alert(_pred("NORMAL", "EPISODE_FINAL"), policy_cfg=POLICY, alert_eligible=True)
    assert d.send_discord is False
    assert d.decision == "NO_ALERT_NORMAL"


def test_provisional_suspicious_no_discord():
    d = evaluate_alert(_pred("SUSPICIOUS", "ACTIVE_PREFIX"), policy_cfg=POLICY, alert_eligible=True)
    assert d.send_discord is False
    assert d.decision == "NO_ALERT_PROVISIONAL"


def test_provisional_brute_default_no_discord():
    d = evaluate_alert(_pred("BRUTE_FORCE", "ACTIVE_PREFIX"), policy_cfg=POLICY, alert_eligible=True)
    assert d.send_discord is False


def test_final_suspicious_warning():
    d = evaluate_alert(_pred("SUSPICIOUS", "EPISODE_FINAL"), policy_cfg=POLICY, alert_eligible=True)
    assert d.send_discord is True
    assert d.severity == "WARNING"
    assert d.decision == "SEND_FINAL_SUSPICIOUS"


def test_final_brute_critical():
    d = evaluate_alert(_pred("BRUTE_FORCE", "EPISODE_FINAL"), policy_cfg=POLICY, alert_eligible=True)
    assert d.send_discord is True
    assert d.severity == "CRITICAL"


def test_no_probability_threshold_reinterpret():
    # Low BF score but label BRUTE_FORCE final → still alert
    d = evaluate_alert(
        _pred("BRUTE_FORCE", "EPISODE_FINAL", probs={"NORMAL": 0.5, "SUSPICIOUS": 0.1, "BRUTE_FORCE": 0.4}),
        policy_cfg=POLICY,
        alert_eligible=True,
    )
    assert d.send_discord is True
    # High BF score but label NORMAL → no alert
    d2 = evaluate_alert(
        _pred("NORMAL", "EPISODE_FINAL", probs={"NORMAL": 0.4, "SUSPICIOUS": 0.21, "BRUTE_FORCE": 0.39}),
        policy_cfg=POLICY,
        alert_eligible=True,
    )
    assert d2.send_discord is False


def test_historical_backfill_no_alert():
    d = evaluate_alert(_pred("BRUTE_FORCE", "EPISODE_FINAL"), policy_cfg=POLICY, alert_eligible=False)
    assert d.send_discord is False
    assert d.suppressed_reason == "historical_backfill"


def test_cooldown_and_escalation():
    now = time.time()
    last = {"severity": "WARNING", "sent_at_epoch": now - 20}
    d = evaluate_alert(
        _pred("SUSPICIOUS", "EPISODE_FINAL"),
        policy_cfg=POLICY,
        alert_eligible=True,
        last_sent=last,
        now_epoch=now,
    )
    assert d.delivery_state == "SUPPRESSED_COOLDOWN"
    d2 = evaluate_alert(
        _pred("BRUTE_FORCE", "EPISODE_FINAL"),
        policy_cfg=POLICY,
        alert_eligible=True,
        last_sent=last,
        now_epoch=now,
    )
    assert d2.send_discord is True
    assert d2.decision == "SEND_ESCALATION"
