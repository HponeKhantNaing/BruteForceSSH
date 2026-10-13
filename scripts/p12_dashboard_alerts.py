#!/usr/bin/env python3
"""P12 — dashboard + Discord alerts over P11 structured predictions."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from presentation.discord_client import DiscordClient  # noqa: E402
from presentation.p12_service import (  # noqa: E402
    P12Service,
    discord_config_status,
    dry_run,
    init_state,
    load_yaml,
    report,
    validate,
    write_json,
)


def _cfg():
    return load_yaml(ROOT / "config" / "p12_dashboard_alerts.yaml")


def main() -> int:
    parser = argparse.ArgumentParser(description="P12 dashboard + Discord alerts")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--validate", action="store_true")
    g.add_argument("--init", action="store_true")
    g.add_argument("--run", action="store_true")
    g.add_argument("--report", action="store_true")
    g.add_argument("--discord-smoke-test", action="store_true")
    g.add_argument("--database-status", action="store_true")
    args = parser.parse_args()
    cfg = _cfg()

    if args.dry_run:
        print(json.dumps(dry_run(ROOT, cfg), indent=2))
        return 0
    if args.validate:
        out = validate(ROOT, cfg)
        print(json.dumps(out, indent=2))
        return 0 if out.get("ok") else 2
    if args.init:
        out = init_state(ROOT, cfg)
        print(json.dumps(out, indent=2))
        return 0 if out.get("ok") else 2
    if args.run:
        out = validate(ROOT, cfg)
        if not out.get("ok"):
            print(json.dumps(out, indent=2))
            return 2
        # Ensure DB initialized
        init_state(ROOT, cfg)
        svc = P12Service(ROOT, cfg)
        print(
            json.dumps(
                {
                    "starting": True,
                    "dashboard": f"http://{cfg['dashboard']['host']}:{cfg['dashboard']['port']}/",
                    "discord": discord_config_status(cfg),
                },
                indent=2,
            ),
            flush=True,
        )
        svc.run_blocking()
        return 0
    if args.report:
        print(json.dumps(report(ROOT, cfg), indent=2))
        return 0
    if args.discord_smoke_test:
        dstat = discord_config_status(cfg)
        if not dstat["enabled"]:
            print(json.dumps({"ok": False, "status": "NOT APPLICABLE", "reason": "Discord disabled"}, indent=2))
            return 0
        if not dstat["webhook_present"]:
            print(json.dumps({"ok": False, "status": "FAIL", "reason": "webhook missing"}, indent=2))
            return 2
        client = DiscordClient.from_env(cfg["discord"])
        result = client.send_smoke_test()
        out_path = ROOT / "data/runtime/p12/discord_smoke_report.json"
        write_json(out_path, {"result": result, "webhook_exposed": False})
        print(json.dumps({"ok": result.get("ok"), "status": "PASS" if result.get("ok") else "FAIL", "http": result.get("status_code")}, indent=2))
        return 0 if result.get("ok") else 2
    if args.database_status:
        db = ROOT / cfg["storage"]["sqlite_path"]
        size = db.stat().st_size if db.is_file() else 0
        print(json.dumps(report(ROOT, cfg) | {"db_bytes": size, "db_path": str(db)}, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
