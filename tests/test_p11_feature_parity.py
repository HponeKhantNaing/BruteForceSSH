"""Historical P7 feature parity gate: 75/75."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from realtime.p11_monitor import load_yaml, verify_feature_parity  # noqa: E402


def test_feature_parity_75_of_75():
    cfg = load_yaml(ROOT / "config" / "p11_realtime.yaml")
    report = verify_feature_parity(ROOT, cfg)
    assert report["ok"] is True
    assert report["samples_checked"] == 75
    assert report["samples_passed"] == 75
    assert report["samples_failed"] == 0
