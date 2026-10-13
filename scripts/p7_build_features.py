#!/usr/bin/env python3
"""P7 — build behavioral + text feature sources (TF-IDF unfitted)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from features.p7_feature_engineering import (  # noqa: E402
    FEATURE_ENGINEERING_VERSION,
    build_features,
    load_yaml,
    sha256_file,
    validate_p6,
)
from features.text_features import build_tfidf_vectorizer, is_vectorizer_fitted  # noqa: E402


def _cfg():
    return load_yaml(ROOT / "config" / "p7_features.yaml")


def cmd_dry_run(_: argparse.Namespace) -> int:
    cfg = _cfg()
    p6 = validate_p6(ROOT, cfg)
    vec = build_tfidf_vectorizer(cfg)
    report = {
        "p6_samples_discovered": p6.get("runs"),
        "p6_attempts_discovered": p6.get("attempts"),
        "text_samples_expected": p6.get("sequences"),
        "behavior_samples_expected": p6.get("runs"),
        "target_distribution": p6.get("class_counts"),
        "default_behavioral_features": cfg["behavioral_features"]["default_enabled"],
        "tfidf_fitted": is_vectorizer_fitted(vec),
        "tfidf_fitted_in_p7_config": cfg["text_features"].get("fitted_in_p7"),
        "p6_ok": p6.get("ok"),
        "version": FEATURE_ENGINEERING_VERSION,
    }
    print(json.dumps(report, indent=2))
    return 0 if p6.get("ok") else 1


def cmd_validate(_: argparse.Namespace) -> int:
    cfg = _cfg()
    result = build_features(ROOT, cfg, write=False)
    print(
        json.dumps(
            {
                "ok": result["ok"],
                "alignment": result.get("alignment"),
                "leakage_pass": result.get("leakage_audit", {}).get("pass"),
                "constant": result.get("constant_features"),
                "default_enabled_count": len(result.get("default_enabled") or []),
                "vectorizer_fitted": result.get("vectorizer_fitted"),
                "sample_count": len(result.get("behavioral_rows") or []),
                "validation_errors": result.get("validation_errors"),
            },
            indent=2,
        )
    )
    return 0 if result["ok"] else 2


def cmd_build(_: argparse.Namespace) -> int:
    cfg = _cfg()
    result = build_features(ROOT, cfg, write=True)
    print(
        json.dumps(
            {
                "ok": result["ok"],
                "output": str(ROOT / cfg["output"]["root"]),
                "samples": len(result.get("behavioral_rows") or []),
                "default_enabled": result.get("default_enabled"),
                "constant": result.get("constant_features"),
                "class_distribution": result.get("diagnostics", {}).get("class_distribution"),
                "tfidf_fitted": result.get("vectorizer_fitted"),
                "leakage_pass": result.get("leakage_audit", {}).get("pass"),
            },
            indent=2,
        )
    )
    return 0 if result["ok"] else 2


def cmd_report(_: argparse.Namespace) -> int:
    out = ROOT / "data/features/p7"
    if not (out / "feature_manifest.json").is_file():
        print("No P7 features found. Run --build first.", file=sys.stderr)
        return 1
    manifest = json.loads((out / "feature_manifest.json").read_text())
    diag = json.loads((out / "diagnostics.json").read_text())
    align = json.loads((out / "sample_alignment_report.json").read_text())
    leak = json.loads((out / "leakage_audit.json").read_text())
    print(json.dumps({"manifest": manifest, "diagnostics": diag, "alignment": align, "leakage": leak}, indent=2))
    # P6 immutability
    ok = True
    for key, expected in (manifest.get("p6_source_hashes") or {}).items():
        path = ROOT / _cfg()["inputs"][key]
        actual = sha256_file(path)
        match = actual == expected
        ok = ok and match
        print(f"p6_hash {key}: {'MATCH' if match else 'CHANGED'}")
    return 0 if ok else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="P7 feature engineering")
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
