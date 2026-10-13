#!/usr/bin/env python3
"""P10 — export / version / validate selected model bundle (no retrain)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from export.p10_export import (  # noqa: E402
    dry_run,
    export_release,
    load_yaml,
    report_release,
    smoke_test_release,
    validate_release,
    validate_source,
)


def _cfg() -> dict:
    return load_yaml(ROOT / "config" / "p10_export.yaml")


def main() -> int:
    parser = argparse.ArgumentParser(description="P10 model export / versioning")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--validate-source", action="store_true")
    g.add_argument("--export", action="store_true")
    g.add_argument("--validate-release", action="store_true")
    g.add_argument("--smoke-test", action="store_true")
    g.add_argument("--report", action="store_true")
    args = parser.parse_args()
    cfg = _cfg()

    if args.dry_run:
        out = dry_run(ROOT, cfg)
        print(json.dumps(out, indent=2, default=str))
        return 0 if out.get("p9_status") == "PASS" else 2
    if args.validate_source:
        out = validate_source(ROOT, cfg)
        print(json.dumps(out, indent=2, default=str))
        if out.get("blocked"):
            return 3
        return 0 if out.get("ok") else 2
    if args.export:
        out = export_release(ROOT, cfg)
        print(json.dumps(out, indent=2, default=str))
        if out.get("status") == "REFUSED":
            return 3
        if out.get("blocked"):
            return 3
        return 0 if out.get("ok") else 2
    if args.validate_release:
        out = validate_release(ROOT, cfg)
        print(json.dumps(out, indent=2, default=str))
        return 0 if out.get("ok") else 2
    if args.smoke_test:
        out = smoke_test_release(ROOT, cfg)
        print(json.dumps(out, indent=2, default=str))
        return 0 if out.get("ok") else 2
    if args.report:
        out = report_release(ROOT, cfg)
        print(json.dumps(out, indent=2, default=str))
        return 0 if out.get("ok") else 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
