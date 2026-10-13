"""Secret / raw-log scan of the P10 release bundle."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from export.p10_export import load_yaml  # noqa: E402

SECRET_PATTERNS = [
    re.compile(r"DISCORD_WEBHOOK", re.I),
    re.compile(r"api[_-]?key\s*[:=]", re.I),
    re.compile(r"password\s*[:=]", re.I),
    re.compile(r"private[_-]?token", re.I),
]


def test_release_secret_scan_clean():
    cfg = load_yaml(ROOT / "config" / "p10_export.yaml")
    release = ROOT / cfg["paths"]["releases_root"] / cfg["release"]["release_id"]
    assert release.is_dir()
    raw_logs = 0
    secrets = 0
    for path in release.rglob("*"):
        if path.is_dir():
            continue
        if path.name == "auth.log":
            raw_logs += 1
        if path.suffix.lower() in {".joblib", ".gz", ".zip"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pat in SECRET_PATTERNS:
            if pat.search(text):
                secrets += 1
                break
    assert raw_logs == 0
    assert secrets == 0
    # No TF-IDF / scaler binaries
    assert not list(release.rglob("*tfidf*"))
    assert not list(release.rglob("*scaler*"))
