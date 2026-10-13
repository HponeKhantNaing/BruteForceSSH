#!/usr/bin/env python3
"""P11 historical logical-attempt reconstruction parity vs P6."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from realtime.p11_monitor import load_yaml, verify_attempt_parity  # noqa: E402


def main() -> int:
    cfg = load_yaml(ROOT / "config" / "p11_realtime.yaml")
    report = verify_attempt_parity(ROOT, cfg)
    print(json.dumps(report, indent=2))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
