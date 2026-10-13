#!/usr/bin/env python3
"""P9 — validation evaluation, selection lock, selected-only TEST."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evaluation.p9_evaluation import (  # noqa: E402
    dry_run,
    evaluate_test_selected,
    evaluate_validation,
    load_yaml,
    out_root,
    select_and_lock,
)
from evaluation.model_evaluator import FrozenArtifactBundle  # noqa: E402


def _cfg():
    return load_yaml(ROOT / "config" / "p9_evaluation.yaml")


def cmd_dry_run(_: argparse.Namespace) -> int:
    print(json.dumps(dry_run(ROOT, _cfg()), indent=2))
    return 0


def cmd_validate(_: argparse.Namespace) -> int:
    cfg = _cfg()
    bundle = FrozenArtifactBundle(ROOT, cfg)
    integrity = bundle.verify_integrity()
    out = out_root(ROOT, cfg)
    print(
        json.dumps(
            {
                "ok": integrity["ok"],
                "integrity": integrity,
                "test_receipt_exists": (out / "test_evaluation_receipt.json").is_file(),
                "selection_lock_exists": (out / "model_selection.lock.json").is_file(),
            },
            indent=2,
        )
    )
    return 0 if integrity["ok"] else 2


def cmd_eval_val(_: argparse.Namespace) -> int:
    result = evaluate_validation(ROOT, _cfg())
    summary = {
        "ok": result.get("ok"),
        "validation_samples": result.get("validation_samples"),
        "validation_scenarios": result.get("validation_scenarios"),
        "fit_calls": result.get("fit_calls"),
        "macro_f1": {
            mid: result["metrics_by_model"][mid]["macro_f1"]
            for mid in result.get("metrics_by_model", {})
        }
        if result.get("ok")
        else None,
    }
    print(json.dumps(summary, indent=2))
    return 0 if result.get("ok") else 2


def cmd_select(_: argparse.Namespace) -> int:
    result = select_and_lock(ROOT, _cfg())
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 2


def cmd_test(_: argparse.Namespace) -> int:
    result = evaluate_test_selected(ROOT, _cfg())
    print(json.dumps(result, indent=2, default=str))
    if result.get("refused"):
        return 3
    return 0 if result.get("ok") else 2


def cmd_report(_: argparse.Namespace) -> int:
    out = out_root(ROOT, _cfg())
    report = out / "evaluation_report.json"
    if not report.is_file():
        print("No evaluation_report.json — run validation/select/test first.", file=sys.stderr)
        return 1
    print(report.read_text())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="P9 model evaluation")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--validate-only", action="store_true")
    g.add_argument("--evaluate-validation", action="store_true")
    g.add_argument("--select-model", action="store_true")
    g.add_argument("--evaluate-test-selected", action="store_true")
    g.add_argument("--report", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        return cmd_dry_run(args)
    if args.validate_only:
        return cmd_validate(args)
    if args.evaluate_validation:
        return cmd_eval_val(args)
    if args.select_model:
        return cmd_select(args)
    if args.evaluate_test_selected:
        return cmd_test(args)
    return cmd_report(args)


if __name__ == "__main__":
    raise SystemExit(main())
