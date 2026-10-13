#!/usr/bin/env python3
"""P11 — real-time ML monitoring CLI (no dashboard / Discord / prevention)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from realtime.p11_monitor import (  # noqa: E402
    dry_run,
    load_yaml,
    monitor_loop,
    replay_run,
    validate_runtime,
    verify_parity,
)


def _cfg():
    return load_yaml(ROOT / "config" / "p11_realtime.yaml")


def main() -> int:
    parser = argparse.ArgumentParser(description="P11 real-time monitoring")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--validate", action="store_true")
    g.add_argument("--verify-parity", action="store_true")
    g.add_argument("--monitor", action="store_true")
    g.add_argument("--report", action="store_true")
    g.add_argument("--replay-run", type=str, metavar="RUN_ID")
    parser.add_argument(
        "--duration-seconds",
        type=float,
        default=20.0,
        help="Monitor loop duration (default 20s). Use 0 for until interrupted.",
    )
    parser.add_argument(
        "--skip-parity-gate",
        action="store_true",
        help="Unsafe: start monitor without re-running parity (not for PASS).",
    )
    args = parser.parse_args()
    cfg = _cfg()

    if args.dry_run:
        out = dry_run(ROOT, cfg)
        print(json.dumps(out, indent=2, default=str))
        return 0 if out.get("p10_bundle_verification") == "PASS" else 2
    if args.validate:
        out = validate_runtime(ROOT, cfg)
        print(json.dumps(out, indent=2, default=str))
        return 0 if out.get("ok") else 2
    if args.verify_parity:
        out = verify_parity(ROOT, cfg)
        print(json.dumps(out, indent=2, default=str))
        return 0 if out.get("ok") else 2
    if args.monitor:
        dur = None if args.duration_seconds == 0 else args.duration_seconds
        out = monitor_loop(
            ROOT,
            cfg,
            duration_seconds=dur,
            require_parity=not args.skip_parity_gate,
        )
        print(json.dumps(out, indent=2, default=str))
        if out.get("status") == "BLOCKED":
            return 3
        return 0 if out.get("ok") else 2
    if args.replay_run:
        out = replay_run(ROOT, cfg, args.replay_run)
        print(json.dumps(out, indent=2, default=str))
        return 0 if out.get("ok") else 2
    if args.report:
        paths = {
            "status": ROOT / cfg["outputs"]["status"],
            "feature_parity": ROOT / cfg["outputs"]["feature_parity_report"],
            "attempt_parity": ROOT / cfg["outputs"]["attempt_parity_report"],
            "latency": ROOT / cfg["outputs"]["latency_report"],
            "context_policy": ROOT / cfg["outputs"]["context_policy"],
        }
        report = {}
        for k, p in paths.items():
            report[k] = json.loads(p.read_text()) if p.is_file() else None
        print(json.dumps(report, indent=2, default=str))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
