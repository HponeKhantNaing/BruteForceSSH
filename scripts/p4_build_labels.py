#!/usr/bin/env python3
"""
P4 — Build ground-truth labels from verified P2/P3 controlled scenarios.

Does not modify data/raw/*. Does not train models or engineer ML features.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from labeling.p4_labeling import (  # noqa: E402
    build_labels,
    load_policy,
    write_outputs,
)

DEFAULT_POLICY = ROOT / "config" / "p4_labeling_policy.yaml"


def print_summary(built, title: str = "P4 summary") -> None:
    s = built.stats
    print(f"=== {title} ===")
    print(f"P2 runs discovered: {s.get('p2_runs_discovered')}")
    print(f"P3 runs discovered: {s.get('p3_runs_discovered')}")
    print(f"Primary eligible runs: {s.get('eligible_primary_runs')}")
    print(f"Excluded: {s.get('excluded_count')}")
    print(f"Targets: {s.get('target_counts')}")
    print(f"Exclusion reasons: {s.get('exclusion_reason_counts')}")
    print(f"Event roles: {s.get('event_role_counts')}")
    print(f"Scenario coverage: {s.get('scenario_coverage')}")


def cmd_dry_run(policy, include_smoke: bool) -> int:
    built = build_labels(ROOT, policy, include_smoke=include_smoke)
    print_summary(built, "P4 dry-run (no outputs written)")
    return 0


def cmd_validate(policy, include_smoke: bool) -> int:
    built = build_labels(ROOT, policy, include_smoke=include_smoke)
    print_summary(built, "P4 validate-only")
    integrity = (built.stats.get("exclusion_reason_counts") or {}).get(
        "checksum_mismatch", 0
    ) + (built.stats.get("exclusion_reason_counts") or {}).get(
        "index_manifest_conflict", 0
    )
    if built.stats.get("eligible_primary_runs", 0) == 0:
        print("ERROR: no eligible primary runs", file=sys.stderr)
        return 2
    if integrity:
        print(f"ERROR: integrity failures={integrity}", file=sys.stderr)
        return 2
    print("Validation OK")
    return 0


def cmd_build(policy, include_smoke: bool) -> int:
    built = build_labels(ROOT, policy, include_smoke=include_smoke)
    if built.stats.get("eligible_primary_runs", 0) == 0:
        print("ERROR: no eligible primary runs; refusing to build", file=sys.stderr)
        return 2
    paths = write_outputs(ROOT, policy, built)
    print_summary(built, "P4 build")
    print("Wrote:")
    for k, p in paths.items():
        print(f"  {k}: {p.relative_to(ROOT)}")
    return 0


def cmd_report(policy) -> int:
    out_root = ROOT / (policy.get("output") or {}).get("root", "data/interim/p4")
    report_path = out_root / (policy.get("output") or {}).get(
        "labeling_report", "labeling_report.json"
    )
    dist_path = out_root / (policy.get("output") or {}).get(
        "class_distribution", "class_distribution.json"
    )
    if not report_path.is_file():
        print(f"ERROR: report missing: {report_path}", file=sys.stderr)
        return 2
    report = json.loads(report_path.read_text(encoding="utf-8"))
    print(json.dumps(report, indent=2))
    if dist_path.is_file():
        print("--- class_distribution ---")
        print(dist_path.read_text(encoding="utf-8"))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P4 ground-truth labeling pipeline")
    parser.add_argument("--config", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--report", action="store_true")
    parser.add_argument(
        "--include-smoke",
        action="store_true",
        help="Optionally include smoke runs (default excludes them)",
    )
    args = parser.parse_args(argv)

    modes = [args.dry_run, args.validate_only, args.build, args.report]
    if sum(1 for m in modes if m) != 1:
        parser.error("Choose exactly one of --dry-run | --validate-only | --build | --report")

    policy = load_policy(args.config)

    if args.dry_run:
        return cmd_dry_run(policy, args.include_smoke)
    if args.validate_only:
        return cmd_validate(policy, args.include_smoke)
    if args.build:
        return cmd_build(policy, args.include_smoke)
    if args.report:
        return cmd_report(policy)
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
