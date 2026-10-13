#!/usr/bin/env python3
"""P6 — build canonical supervised dataset from local P4 only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from preprocessing.p6_preprocessing import (  # noqa: E402
    PREPROCESSING_VERSION,
    build_dataset,
    dry_run_summary,
    load_yaml,
    sha256_file,
    validate_sources,
)


def _cfg() -> dict:
    return load_yaml(ROOT / "config" / "p6_preprocessing.yaml")


def cmd_dry_run(_: argparse.Namespace) -> int:
    cfg = _cfg()
    summary = dry_run_summary(ROOT, cfg)
    print(json.dumps(summary, indent=2))
    if not summary["source_check"]["ok"]:
        print("SOURCE CHECK FAILED", file=sys.stderr)
        return 1
    print(
        f"\nDry-run OK: primary_runs={summary['p4_primary_runs']} "
        f"public_records_expected={summary['expected_public_records_included']} "
        f"version={PREPROCESSING_VERSION}"
    )
    return 0


def cmd_validate(_: argparse.Namespace) -> int:
    cfg = _cfg()
    check = validate_sources(ROOT, cfg)
    print(json.dumps(check, indent=2))
    if not check["ok"]:
        return 1
    # Build without write to validate joins/reconstruction
    result = build_dataset(ROOT, cfg, write=False)
    print(
        json.dumps(
            {
                "ok": result["ok"],
                "quality": result["quality"],
                "leakage_hits": result["dataset_manifest"].get("leakage_guard_hits"),
                "external_policy": result["source_check"]["external_policy"],
            },
            indent=2,
        )
    )
    return 0 if result["ok"] else 2


def cmd_build(_: argparse.Namespace) -> int:
    cfg = _cfg()
    result = build_dataset(ROOT, cfg, write=True)
    print(
        json.dumps(
            {
                "ok": result["ok"],
                "output_root": result["output_root"],
                "quality": result["quality"],
                "class_distribution": result["class_distribution"],
                "normalization_report": result["normalization_report"],
            },
            indent=2,
        )
    )
    return 0 if result["ok"] else 2


def cmd_report(_: argparse.Namespace) -> int:
    out = ROOT / "data/processed/p6"
    manifest = out / "dataset_manifest.json"
    quality = out / "quality_report.json"
    if not manifest.is_file():
        print("No P6 dataset found. Run --build first.", file=sys.stderr)
        return 1
    print(json.dumps(json.loads(manifest.read_text()), indent=2))
    print("---")
    print(json.dumps(json.loads(quality.read_text()), indent=2))
    # Immutability spot-check against recorded hashes
    hashes = json.loads(manifest.read_text())["source_hashes"]
    ok = True
    for key, expected in hashes.items():
        if key == "p5_registry":
            path = ROOT / "data/external/p5/registry.json"
        elif key == "run_labels":
            path = ROOT / "data/interim/p4/run_labels.jsonl"
        elif key == "event_annotations":
            path = ROOT / "data/interim/p4/event_annotations.jsonl"
        elif key == "excluded_runs":
            path = ROOT / "data/interim/p4/excluded_runs.jsonl"
        elif key == "class_distribution":
            path = ROOT / "data/interim/p4/class_distribution.json"
        else:
            continue
        actual = sha256_file(path)
        match = actual == expected
        ok = ok and match
        print(f"hash {key}: {'MATCH' if match else 'CHANGED'}")
    return 0 if ok else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="P6 canonical dataset builder")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--validate-only", action="store_true")
    g.add_argument("--build", action="store_true")
    g.add_argument("--report", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        return cmd_dry_run(args)
    if args.validate_only:
        return cmd_validate(args)
    if args.build:
        return cmd_build(args)
    return cmd_report(args)


if __name__ == "__main__":
    raise SystemExit(main())
