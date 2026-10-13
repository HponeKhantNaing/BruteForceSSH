"""P12 privacy + ML boundary tests."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRES = ROOT / "src" / "presentation"


def test_presentation_code_avoids_raw_log_and_ml_inference():
    forbidden = [
        (re.compile(r"data/raw/auth/auth\.log"), "raw auth.log path"),
        (re.compile(r"joblib\.load"), "joblib.load"),
        (re.compile(r"model\.predict\b"), "model.predict"),
        (re.compile(r"predict_proba\s*\("), "predict_proba"),
    ]
    for path in PRES.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for pat, name in forbidden:
            assert not pat.search(text), f"{path.name} contains {name}"


def test_no_hardcoded_discord_webhook_url():
    for path in list(PRES.rglob("*")) + [ROOT / "config" / "p12_dashboard_alerts.yaml"]:
        if not path.is_file():
            continue
        if path.suffix not in {".py", ".yaml", ".html", ".js", ".css"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert "discord.com/api/webhooks" not in text
