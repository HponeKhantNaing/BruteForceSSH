#!/usr/bin/env python3
"""P8 — leakage-safe scenario-group split + TRAIN-only model training."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from training.p8_training import (  # noqa: E402
    TRAINING_VERSION,
    create_split,
    dry_run_summary,
    load_aligned_p7,
    load_yaml,
    train_models,
)


def _cfg():
    return load_yaml(ROOT / "config" / "p8_training.yaml")


def cmd_dry_run(_: argparse.Namespace) -> int:
    cfg = _cfg()
    summary = dry_run_summary(ROOT, cfg)
    print(json.dumps(summary, indent=2))
    return 0


def cmd_validate(_: argparse.Namespace) -> int:
    cfg = _cfg()
    try:
        data = load_aligned_p7(ROOT, cfg)
        summary = dry_run_summary(ROOT, cfg)
        print(
            json.dumps(
                {
                    "ok": True,
                    "sample_count": data["sample_count"],
                    "feature_count": len(data["feature_order"]),
                    "scenario_groups": summary["scenario_groups"],
                    "planned_split": {
                        "train": summary["planned_train"],
                        "validation": summary["planned_validation"],
                        "test": summary["planned_test"],
                    },
                    "three_way_feasible": True,
                },
                indent=2,
            )
        )
        return 0
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, indent=2))
        return 2


def cmd_split(_: argparse.Namespace) -> int:
    cfg = _cfg()
    result = create_split(ROOT, cfg)
    print(json.dumps(result["summary"], indent=2))
    return 0


def cmd_train(_: argparse.Namespace) -> int:
    cfg = _cfg()
    result = train_models(ROOT, cfg)
    print(
        json.dumps(
            {
                "ok": result["ok"],
                "vocab_size": result["vocab_size"],
                "text_dim": result["text_dim"],
                "behavior_dim": result["behavior_dim"],
                "hybrid_dim": result["hybrid_dim"],
                "models": [
                    {"model_id": m["model_id"], "status": m["status"], "dim": m.get("feature_dimension")}
                    for m in result["training_report"]
                ],
                "test_metrics_computed": False,
                "tfidf_roundtrip": result["tfidf_roundtrip"],
                "scaler_roundtrip": result["scaler_roundtrip"],
                "version": TRAINING_VERSION,
            },
            indent=2,
        )
    )
    return 0 if result["ok"] else 2


def cmd_report(_: argparse.Namespace) -> int:
    modeling = ROOT / "data/modeling/p8"
    if not (modeling / "training_manifest.json").is_file():
        print("No P8 training found. Run --split then --train.", file=sys.stderr)
        return 1
    man = json.loads((modeling / "training_manifest.json").read_text())
    report = json.loads((modeling / "training_report.json").read_text())
    leak = json.loads((modeling / "leakage_audit.json").read_text())
    split_sum = json.loads((modeling / "split_summary.json").read_text()) if (modeling / "split_summary.json").is_file() else {}
    print(json.dumps({"split_summary": split_sum, "training_manifest": man, "training_report": report, "leakage_audit": leak}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="P8 leakage-safe ML training")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--validate-only", action="store_true")
    g.add_argument("--split", action="store_true")
    g.add_argument("--train", action="store_true")
    g.add_argument("--report", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        return cmd_dry_run(args)
    if args.validate_only:
        return cmd_validate(args)
    if args.split:
        return cmd_split(args)
    if args.train:
        return cmd_train(args)
    return cmd_report(args)


if __name__ == "__main__":
    raise SystemExit(main())
