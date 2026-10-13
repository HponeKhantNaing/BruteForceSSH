#!/usr/bin/env python3
"""Expand P7 lab features via controlled synthetic augmentation (lab-only).

Does NOT pull public datasets (P5 Case B). Creates jittered behavioral copies
of existing labeled lab runs so P8/P9 can train/evaluate on a larger set while
preserving scenario_id grouping (leakage-safe split unchanged by group).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
P7 = ROOT / "data" / "features" / "p7"
BASELINE = ROOT / "data" / "features" / "p7_baseline_75"

# Continuous features: multiplicative jitter
JITTER_KEYS = {
    "total_attempts",
    "failed_attempts",
    "successful_attempts",
    "duration_seconds",
    "attempt_rate_per_second",
    "failed_count_30s_max",
    "failed_count_60s_max",
    "failed_count_5m_max",
    "success_count_5m_max",
    "unique_users_total",
    "unique_users_60s_max",
    "min_inter_attempt_gap_seconds",
    "mean_inter_attempt_gap_seconds",
    "median_inter_attempt_gap_seconds",
    "std_inter_attempt_gap_seconds",
    "max_failure_streak",
    "failures_before_first_success",
}

BINARY_KEYS = {
    "has_multiple_attempts",
    "success_after_failure",
    "first_attempt_failed",
    "last_attempt_success",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def backup_baseline() -> None:
    if BASELINE.exists():
        return
    BASELINE.mkdir(parents=True, exist_ok=True)
    for name in (
        "behavioral_features.jsonl",
        "text_samples.jsonl",
        "targets.jsonl",
        "feature_schema.json",
        "feature_manifest.json",
        "exclusions.jsonl",
    ):
        src = P7 / name
        if src.exists():
            shutil.copy2(src, BASELINE / name)
    (BASELINE / "README.md").write_text(
        "# P7 baseline (75 lab runs)\n\nFrozen copy before synthetic augmentation.\n",
        encoding="utf-8",
    )


def _clamp_nonneg(x: float) -> float:
    if not math.isfinite(x):
        return 0.0
    return max(0.0, float(x))


def jitter_features(feat: dict[str, float], rng: random.Random, label: str) -> dict[str, float]:
    out = dict(feat)
    scale = 0.08 + rng.random() * 0.12  # 8–20% relative noise
    for k in JITTER_KEYS:
        if k not in out:
            continue
        v = float(out[k])
        noise = 1.0 + rng.uniform(-scale, scale)
        out[k] = _clamp_nonneg(v * noise)

    # Re-derive failure_ratio consistently
    total = max(out.get("total_attempts", 0.0), 1e-6)
    failed = min(out.get("failed_attempts", 0.0), total)
    success = min(out.get("successful_attempts", 0.0), total)
    # Keep counts roughly consistent with label priors
    if label == "BRUTE_FORCE":
        failed = max(failed, total * 0.7)
        success = min(success, total * 0.3)
    elif label == "NORMAL":
        failed = min(failed, max(2.0, total * 0.35))
    out["failed_attempts"] = _clamp_nonneg(failed)
    out["successful_attempts"] = _clamp_nonneg(success)
    out["total_attempts"] = max(out["failed_attempts"] + out["successful_attempts"], total * 0.5)
    t = out["total_attempts"]
    out["failure_ratio"] = float(out["failed_attempts"] / t) if t > 0 else 0.0

    # Rate from duration
    dur = max(out.get("duration_seconds", 1.0), 1e-3)
    out["duration_seconds"] = dur
    out["attempt_rate_per_second"] = float(out["total_attempts"] / dur)

    # Window maxima consistent-ish with failed_attempts
    f = out["failed_attempts"]
    out["failed_count_30s_max"] = min(out.get("failed_count_30s_max", f), f)
    out["failed_count_60s_max"] = max(out.get("failed_count_60s_max", f), out["failed_count_30s_max"])
    out["failed_count_5m_max"] = max(out.get("failed_count_5m_max", f), out["failed_count_60s_max"])
    out["max_failure_streak"] = min(max(out.get("max_failure_streak", 0.0), 0.0), f)

    for k in BINARY_KEYS:
        if k in out:
            # Rare flip only when still plausible
            if rng.random() < 0.03:
                out[k] = 1.0 - float(out[k] >= 0.5)
            else:
                out[k] = 1.0 if float(out[k]) >= 0.5 else 0.0

    out["has_multiple_attempts"] = 1.0 if out["total_attempts"] >= 2 else 0.0
    return {k: float(v) for k, v in out.items()}


def augment(copies_per_sample: int, seed: int) -> dict[str, Any]:
    backup_baseline()
    src = BASELINE if (BASELINE / "targets.jsonl").is_file() else P7

    beh = {r["sample_id"]: r for r in load_jsonl(src / "behavioral_features.jsonl")}
    txt = {r["sample_id"]: r for r in load_jsonl(src / "text_samples.jsonl")}
    tgt = load_jsonl(src / "targets.jsonl")
    if not tgt:
        raise RuntimeError("No baseline targets")

    rng = random.Random(seed)
    new_beh: list[dict[str, Any]] = []
    new_txt: list[dict[str, Any]] = []
    new_tgt: list[dict[str, Any]] = []

    # Keep originals first
    for t in tgt:
        sid = t["sample_id"]
        new_beh.append(beh[sid])
        new_txt.append(txt[sid])
        new_tgt.append(t)

    for t in tgt:
        sid = t["sample_id"]
        label = t["target_label"]
        base_f = beh[sid]["features"]
        base_text = txt[sid]["canonical_text"]
        for i in range(copies_per_sample):
            new_id = f"{sid}__AUG{i:03d}"
            feats = jitter_features(base_f, rng, label)
            new_beh.append(
                {
                    "sample_id": new_id,
                    "features": feats,
                    "feature_engineering_version": beh[sid].get(
                        "feature_engineering_version", "p7-v1"
                    ),
                    "synthetic_lab_augment": True,
                    "augment_parent_id": sid,
                }
            )
            # Tiny text variation — still anonymized lab style
            suffix = f"\n<host> sshd[<pid>]: pam_unix(sshd:session): session closed for user <user> #aug{i}"
            new_txt.append(
                {
                    "sample_id": new_id,
                    "canonical_text": base_text + suffix,
                    "synthetic_lab_augment": True,
                    "augment_parent_id": sid,
                }
            )
            new_tgt.append(
                {
                    "sample_id": new_id,
                    "target_label": label,
                    "split_group_run": t.get("split_group_run"),
                    "split_group_batch": t.get("split_group_batch"),
                    "scenario_id": t["scenario_id"],
                    "synthetic_lab_augment": True,
                    "augment_parent_id": sid,
                }
            )

    write_jsonl(P7 / "behavioral_features.jsonl", new_beh)
    write_jsonl(P7 / "text_samples.jsonl", new_txt)
    write_jsonl(P7 / "targets.jsonl", new_tgt)

    # Refresh manifest provenance note
    manifest_path = P7 / "feature_manifest.json"
    if manifest_path.is_file():
        man = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        man = {}
    man["augment"] = {
        "synthetic_lab_augment": True,
        "copies_per_sample": copies_per_sample,
        "seed": seed,
        "original_samples": len(tgt),
        "total_samples": len(new_tgt),
        "baseline_dir": str(BASELINE.relative_to(ROOT)),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "note": "Lab-only jittered copies; public datasets not merged (P5 Case B).",
    }
    man["sample_count"] = len(new_tgt)
    manifest_path.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")

    # checksums helper
    def sha(p: Path) -> str:
        h = hashlib.sha256()
        h.update(p.read_bytes())
        return h.hexdigest()

    return {
        "ok": True,
        "original_samples": len(tgt),
        "copies_per_sample": copies_per_sample,
        "total_samples": len(new_tgt),
        "baseline": str(BASELINE.relative_to(ROOT)),
        "hashes": {
            "behavioral_features": sha(P7 / "behavioral_features.jsonl"),
            "text_samples": sha(P7 / "text_samples.jsonl"),
            "targets": sha(P7 / "targets.jsonl"),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Augment P7 lab features")
    ap.add_argument("--copies", type=int, default=39, help="Synthetic copies per original sample")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    if args.copies < 1:
        raise SystemExit("--copies must be >= 1")
    out = augment(args.copies, args.seed)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
