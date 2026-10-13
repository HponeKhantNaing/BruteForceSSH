#!/usr/bin/env python3
"""P5 — public dataset evaluation CLI (metadata-first; no automatic downloads)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from external_data.p5_evaluator import (  # noqa: E402
    disk_free_bytes,
    load_json,
    load_yaml,
    sha256_file,
    summarize_registry,
    utc_now,
    validate_registry_entry,
    verify_p4_hashes,
    write_json,
)


def _paths():
    cfg = load_yaml(ROOT / "config" / "p5_dataset_evaluation.yaml")
    paths = cfg["paths"]
    return cfg, {k: ROOT / v for k, v in paths.items()}


def cmd_list(args: argparse.Namespace) -> int:
    _, paths = _paths()
    reg = load_json(paths["registry"])
    for d in reg["datasets"]:
        print(
            f"{d['dataset_id']:20}  {d['decision']:30}  "
            f"domain={d['data_domain']}  labeled={d['labeled']}  "
            f"download_approved={d.get('download_approved', False)}"
        )
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    _, paths = _paths()
    reg = load_json(paths["registry"])
    ids = [args.dataset_id] if args.dataset_id else [d["dataset_id"] for d in reg["datasets"]]
    for did in ids:
        entry = next((d for d in reg["datasets"] if d["dataset_id"] == did), None)
        if entry is None:
            print(f"ERROR: unknown dataset_id={did}", file=sys.stderr)
            return 1
        errs = validate_registry_entry(entry)
        eval_path = ROOT / entry["evaluation_file"]
        if not eval_path.is_file():
            errs.append(f"missing evaluation file: {eval_path}")
        else:
            ev = load_json(eval_path)
            if ev.get("decision") != entry.get("decision"):
                errs.append("registry/evaluation decision mismatch")
        status = "PASS" if not errs else "FAIL"
        print(f"[{status}] {did}: decision={entry['decision']}")
        for e in errs:
            print(f"  - {e}")
        if args.dry_run:
            print("  (dry-run: no downloads attempted)")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    cfg, paths = _paths()
    reg = load_json(paths["registry"])
    summary = summarize_registry(reg)
    free = disk_free_bytes(ROOT)
    p4 = verify_p4_hashes(ROOT, paths["p4_hash_snapshot"]) if paths["p4_hash_snapshot"].is_file() else {
        "ok": False,
        "files": {},
    }
    report = {
        "generated_at": utc_now(),
        "policy_version": cfg.get("evaluation_policy_version"),
        "summary": summary,
        "disk_free_bytes": free,
        "disk_free_gb": round(free / (1024**3), 2),
        "p4_regression": p4,
        "integration_candidates_exist": (ROOT / "data/external/p5/integration_candidates.jsonl").is_file(),
        "external_files_manifest_exists": paths["external_files"].is_file(),
        "downloads_present": any(
            p for p in paths["downloads_dir"].rglob("*")
            if p.is_file() and p.name != ".gitkeep"
        )
        if paths["downloads_dir"].is_dir()
        else False,
    }
    out = ROOT / "data/external/p5/audit/p5_evaluation_report.json"
    write_json(out, report)
    print(json.dumps(report, indent=2))
    print(f"\nWrote {out}")
    return 0 if p4.get("ok") else 2


def cmd_download_approved(args: argparse.Namespace) -> int:
    """Only download when registry marks download_approved=true (none in P5 Case B)."""
    _, paths = _paths()
    reg = load_json(paths["registry"])
    entry = next((d for d in reg["datasets"] if d["dataset_id"] == args.dataset_id), None)
    if entry is None:
        print(f"ERROR: unknown dataset_id={args.dataset_id}", file=sys.stderr)
        return 1
    if not entry.get("download_approved"):
        print(
            f"REFUSED: {args.dataset_id} download_approved=false "
            f"(decision={entry['decision']}, status={entry.get('download_status')})"
        )
        return 1
    print("ERROR: download path not implemented for approved datasets in this P5 Case B build.")
    return 1


def cmd_hash_file(args: argparse.Namespace) -> int:
    p = Path(args.path)
    if not p.is_file():
        print(f"ERROR: not a file: {p}", file=sys.stderr)
        return 1
    print(sha256_file(p))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="P5 public dataset evaluation")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List registry datasets")
    p_list.set_defaults(func=cmd_list)

    p_eval = sub.add_parser("evaluate", help="Validate registry + evaluation metadata")
    p_eval.add_argument("--dataset-id", dest="dataset_id", default=None)
    p_eval.add_argument("--evaluate-all", action="store_true")
    p_eval.add_argument("--dry-run", action="store_true")
    p_eval.set_defaults(func=cmd_evaluate)

    p_report = sub.add_parser("report", help="Write evaluation summary + P4 regression")
    p_report.set_defaults(func=cmd_report)

    p_dl = sub.add_parser("download-approved", help="Download only if download_approved=true")
    p_dl.add_argument("dataset_id")
    p_dl.set_defaults(func=cmd_download_approved)

    p_hash = sub.add_parser("sha256", help="Hash a local file")
    p_hash.add_argument("path")
    p_hash.set_defaults(func=cmd_hash_file)

    # Convenience flags matching the brief
    parser_top = argparse.ArgumentParser(add_help=False)
    parser_top.add_argument("--list", action="store_true")
    parser_top.add_argument("--evaluate", metavar="DATASET_ID")
    parser_top.add_argument("--evaluate-all", action="store_true")
    parser_top.add_argument("--report", action="store_true")
    parser_top.add_argument("--dry-run", action="store_true")
    parser_top.add_argument("--download-approved", metavar="DATASET_ID")
    known, _ = parser_top.parse_known_args()

    if known.list or known.evaluate or known.evaluate_all or known.report or known.download_approved:
        if known.list:
            return cmd_list(argparse.Namespace())
        if known.report:
            return cmd_report(argparse.Namespace())
        if known.download_approved:
            return cmd_download_approved(argparse.Namespace(dataset_id=known.download_approved))
        ns = argparse.Namespace(
            dataset_id=None if known.evaluate_all else known.evaluate,
            dry_run=known.dry_run,
        )
        return cmd_evaluate(ns)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
