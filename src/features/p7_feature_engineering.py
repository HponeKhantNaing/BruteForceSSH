"""P7 feature engineering orchestrator — deterministic features, unfitted TF-IDF."""

from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from features.behavioral_features import (
    DEFAULT_FEATURE_NAMES,
    FEATURE_DEFINITIONS,
    compute_behavior_features,
)
from features.text_features import build_numeric_scaler, build_tfidf_vectorizer, is_vectorizer_fitted

FEATURE_ENGINEERING_VERSION = "p7-v1"

LEAKAGE_TEXT_PATTERNS = [
    re.compile(r"\bNORMAL\b"),
    re.compile(r"\bSUSPICIOUS\b"),
    re.compile(r"\bBRUTE_FORCE\b"),
    re.compile(r"\bN0[1-6]\b"),
    re.compile(r"\bS0[1-4]\b"),
    re.compile(r"\bB0[1-5]\b"),
    re.compile(r"\bP[23]\b"),
    re.compile(r"brute_force", re.I),
    re.compile(r"data/raw/"),
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
]
RAW_USERNAMES = ("testuser", "labuser1", "labuser2", "labuser3")

FORBIDDEN_FEATURE_KEYS = {
    "target_label",
    "scenario_id",
    "scenario_intent",
    "scenario_family",
    "collection_phase",
    "collection_batch_id",
    "batch_id",
    "raw_log_path",
    "planned_failed_attempts",
    "configured_attempt_count",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid YAML: {path}")
    return data


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def validate_p6(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    paths = {k: root / v for k, v in cfg["inputs"].items()}
    missing = [k for k, p in paths.items() if not p.is_file()]
    hashes = {k: sha256_file(p) for k, p in paths.items() if p.is_file()}
    if missing:
        return {"ok": False, "missing": missing, "hashes": hashes}

    runs = load_jsonl(paths["canonical_runs"])
    attempts = load_jsonl(paths["canonical_attempts"])
    sequences = load_jsonl(paths["canonical_sequences"])
    manifest = json.loads(paths["dataset_manifest"].read_text(encoding="utf-8"))

    run_ids = {r["sample_id"] for r in runs}
    seq_ids = {s["sample_id"] for s in sequences}
    ok = (
        len(runs) == len(sequences)
        and run_ids == seq_ids
        and manifest.get("external_supervised_data_included") is False
        and not cfg["external_supervised_data"].get("enabled", False)
    )
    return {
        "ok": ok,
        "missing": missing,
        "hashes": hashes,
        "runs": len(runs),
        "attempts": len(attempts),
        "sequences": len(sequences),
        "class_counts": dict(Counter(r["target_label"] for r in runs)),
        "attempt_outcomes": dict(Counter(a["outcome"] for a in attempts)),
        "preprocessing_version": manifest.get("preprocessing_version"),
        "external_supervised_data_included": manifest.get("external_supervised_data_included"),
        "sample_id_alignment": run_ids == seq_ids,
    }


def audit_text_leakage(text: str) -> list[str]:
    findings = []
    for pat in LEAKAGE_TEXT_PATTERNS:
        if pat.search(text):
            findings.append(pat.pattern)
    for u in RAW_USERNAMES:
        if re.search(rf"\b{re.escape(u)}\b", text, re.I):
            findings.append(f"raw_username:{u}")
    return findings


def _stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "min": None,
            "max": None,
            "mean": None,
            "median": None,
            "std": None,
            "unique_value_count": 0,
            "missing_count": 0,
            "variance": None,
        }
    uniq = len(set(values))
    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "std": statistics.pstdev(values) if len(values) > 1 else 0.0,
        "unique_value_count": uniq,
        "missing_count": 0,
        "variance": statistics.pvariance(values) if len(values) > 1 else 0.0,
    }


def validate_feature_row(features: dict[str, float]) -> list[str]:
    errors = []
    for k, v in features.items():
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            errors.append(f"{k}: non-numeric")
            continue
        if not math.isfinite(float(v)):
            errors.append(f"{k}: non-finite")
    checks = [
        ("total_attempts", lambda x: x >= 0),
        ("failed_attempts", lambda x: x >= 0),
        ("successful_attempts", lambda x: x >= 0),
        ("failure_ratio", lambda x: 0 <= x <= 1),
        ("duration_seconds", lambda x: x >= 0),
        ("attempt_rate_per_second", lambda x: x >= 0),
        ("unique_users_total", lambda x: x >= 0),
        ("min_inter_attempt_gap_seconds", lambda x: x >= 0),
        ("mean_inter_attempt_gap_seconds", lambda x: x >= 0),
        ("median_inter_attempt_gap_seconds", lambda x: x >= 0),
        ("std_inter_attempt_gap_seconds", lambda x: x >= 0),
    ]
    for name, pred in checks:
        if name in features and not pred(features[name]):
            errors.append(f"{name}: range violation ({features[name]})")

    total = features.get("total_attempts", 0)
    failed = features.get("failed_attempts", 0)
    success = features.get("successful_attempts", 0)
    unknown = features.get("unknown_attempts", 0)
    if abs((failed + success + unknown) - total) > 1e-9:
        errors.append("attempt sum inconsistency")

    if features.get("failed_count_30s_max", 0) - features.get("failed_count_60s_max", 0) > 1e-9:
        errors.append("window 30>60")
    if features.get("failed_count_60s_max", 0) - features.get("failed_count_5m_max", 0) > 1e-9:
        errors.append("window 60>5m")
    if features.get("failed_count_5m_max", 0) - failed > 1e-9:
        errors.append("window 5m > failed_attempts")
    if features.get("unique_users_60s_max", 0) - features.get("unique_users_total", 0) > 1e-9:
        errors.append("unique_users_60s > total")
    if features.get("max_failure_streak", 0) - failed > 1e-9:
        errors.append("streak > failed")
    return errors


def build_features(root: Path, cfg: dict[str, Any], *, write: bool = True) -> dict[str, Any]:
    p6 = validate_p6(root, cfg)
    if not p6["ok"]:
        return {"ok": False, "stage": "validate_p6", "p6": p6}

    runs = load_jsonl(root / cfg["inputs"]["canonical_runs"])
    attempts = load_jsonl(root / cfg["inputs"]["canonical_attempts"])
    sequences = load_jsonl(root / cfg["inputs"]["canonical_sequences"])
    runs_by_id = {r["run_id"]: r for r in runs}
    seq_by_sample = {s["sample_id"]: s for s in sequences}
    attempts_by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for a in attempts:
        attempts_by_run[a["run_id"]].append(a)

    default_names = list(cfg["behavioral_features"].get("default_enabled") or DEFAULT_FEATURE_NAMES)
    min_duration = float(cfg["behavioral_features"].get("min_duration_seconds", 1e-3))

    behavioral_rows: list[dict[str, Any]] = []
    text_rows: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    leakage_findings: list[dict[str, Any]] = []
    validation_errors: list[dict[str, Any]] = []

    # Ensure TF-IDF stays unfitted
    vectorizer = build_tfidf_vectorizer(cfg)
    scaler = build_numeric_scaler(cfg)
    assert not is_vectorizer_fitted(vectorizer)

    for run in sorted(runs, key=lambda r: r["sample_id"]):
        sample_id = run["sample_id"]
        rid = run["run_id"]
        seq = seq_by_sample.get(sample_id)
        if seq is None:
            exclusions.append({"sample_id": sample_id, "reason": "missing_sequence"})
            continue

        hist = sorted(
            attempts_by_run.get(rid, []),
            key=lambda a: (a.get("attempt_order") or 0, a.get("started_at") or ""),
        )
        feats = compute_behavior_features(hist, run=run, sequence=seq, min_duration=min_duration)

        # Strip forbidden keys if any ever appear
        for bad in list(feats):
            if bad in FORBIDDEN_FEATURE_KEYS:
                del feats[bad]
                leakage_findings.append({"sample_id": sample_id, "type": "numeric_forbidden", "key": bad})

        errs = validate_feature_row(feats)
        if errs:
            validation_errors.append({"sample_id": sample_id, "errors": errs})
            exclusions.append({"sample_id": sample_id, "reason": "non_finite_feature", "errors": errs})
            continue

        # Default feature subset for model-eligible output
        model_feats = {k: float(feats[k]) for k in default_names if k in feats}
        # Keep diagnostic extras outside features object? Store full in diagnostics later.
        behavioral_rows.append(
            {
                "sample_id": sample_id,
                "features": model_feats,
                "diagnostic_features": {
                    "unique_sources_total": feats.get("unique_sources_total", 0.0),
                    "unknown_attempts": feats.get("unknown_attempts", 0.0),
                    "max_inter_attempt_gap_seconds": feats.get("max_inter_attempt_gap_seconds", 0.0),
                },
                "feature_engineering_version": FEATURE_ENGINEERING_VERSION,
            }
        )

        text = seq.get("canonical_text") or ""
        text_findings = audit_text_leakage(text)
        if text_findings:
            leakage_findings.append({"sample_id": sample_id, "type": "text", "findings": text_findings})

        text_rows.append(
            {
                "sample_id": sample_id,
                "canonical_text": text,
                "text_char_count": len(text),
                "text_token_count": len(text.split()) if text else 0,
                "text_line_count": len([ln for ln in text.splitlines() if ln.strip()]),
            }
        )

        target_rows.append(
            {
                "sample_id": sample_id,
                "target_label": run.get("target_label"),
                "split_group_run": run.get("split_group_run"),
                "split_group_batch": run.get("split_group_batch"),
                "scenario_id": run.get("scenario_id"),
            }
        )

    # Alignment
    b_ids = [r["sample_id"] for r in behavioral_rows]
    t_ids = [r["sample_id"] for r in text_rows]
    y_ids = [r["sample_id"] for r in target_rows]
    p6_ids = sorted(r["sample_id"] for r in runs)
    set_b, set_t, set_y, set_p6 = set(b_ids), set(t_ids), set(y_ids), set(p6_ids)
    alignment = {
        "p6_sample_count": len(set_p6),
        "behavior_count": len(b_ids),
        "text_count": len(t_ids),
        "target_count": len(y_ids),
        "aligned": set_b == set_t == set_y == set_p6 and len(b_ids) == len(set_b),
        "missing_from_behavior": sorted(set_p6 - set_b),
        "missing_from_text": sorted(set_p6 - set_t),
        "missing_from_targets": sorted(set_p6 - set_y),
        "duplicates_behavior": len(b_ids) - len(set_b),
        "duplicates_text": len(t_ids) - len(set_t),
        "duplicates_targets": len(y_ids) - len(set_y),
        "extra": sorted((set_b | set_t | set_y) - set_p6),
    }

    # Feature statistics
    feature_values: dict[str, list[float]] = defaultdict(list)
    for row in behavioral_rows:
        for k, v in row["features"].items():
            feature_values[k].append(float(v))
        for k, v in row.get("diagnostic_features", {}).items():
            feature_values[f"diagnostic::{k}"].append(float(v))

    feature_statistics = {k: _stats(vs) for k, vs in sorted(feature_values.items())}

    constant = []
    near_constant = []
    for name in default_names:
        st = feature_statistics.get(name)
        if not st:
            continue
        if st["unique_value_count"] == 1:
            constant.append(name)
        elif st["unique_value_count"] is not None and st["unique_value_count"] <= 2 and st["count"] >= 10:
            # near-constant heuristic: <=2 unique values
            near_constant.append(name)

    # Disable constants in schema default_enabled
    enabled_final = [n for n in default_names if n not in constant]
    disabled = [n for n in default_names if n in constant]

    # Per-class diagnostics (analysis only; does not alter features)
    by_label = defaultdict(list)
    target_map = {t["sample_id"]: t["target_label"] for t in target_rows}
    for row in behavioral_rows:
        by_label[target_map[row["sample_id"]]].append(row["features"])

    per_class = {}
    for label, rows in by_label.items():
        per_class[label] = {}
        keys = rows[0].keys() if rows else []
        for k in keys:
            vals = [float(r[k]) for r in rows]
            per_class[label][k] = _stats(vals)

    # Schema
    schema_features = []
    for name in default_names:
        schema_features.append(
            {
                "name": name,
                "dtype": "float64",
                "description": FEATURE_DEFINITIONS.get(name, ""),
                "source": "canonical_attempts",
                "unit": "count_or_ratio_or_seconds",
                "default_enabled": name not in constant,
                "leakage_risk": "low",
                "online_reproducible": True,
                "known_risk": "scenario_generation_artifact_risk",
            }
        )
    # Diagnostic-only documented
    for name in cfg["behavioral_features"].get("diagnostic_only") or []:
        schema_features.append(
            {
                "name": name,
                "dtype": "float64",
                "description": FEATURE_DEFINITIONS.get(name, "diagnostic"),
                "source": "diagnostic",
                "default_enabled": False,
                "leakage_risk": "medium" if "source" in name else "low",
                "online_reproducible": True,
                "known_risk": "lab_environment_limitation",
            }
        )

    text_lengths = [r["text_char_count"] for r in text_rows]
    text_tokens = [r["text_token_count"] for r in text_rows]

    class_counts = Counter(t["target_label"] for t in target_rows)
    samples_per_feature = (
        len(behavioral_rows) / max(len(enabled_final), 1) if behavioral_rows else 0
    )

    diagnostics = {
        "sample_count": len(behavioral_rows),
        "attempt_count": p6["attempts"],
        "feature_count_defined": len(default_names),
        "default_enabled_feature_count": len(enabled_final),
        "constant_features": constant,
        "near_constant_features": near_constant,
        "text_length_summary": _stats([float(x) for x in text_lengths]),
        "text_token_summary": _stats([float(x) for x in text_tokens]),
        "class_distribution": dict(class_counts),
        "samples_per_numeric_feature": samples_per_feature,
        "small_sample_warning": samples_per_feature < 5,
        "scenario_generation_artifact_warnings": [
            "Features may strongly reflect controlled lab scenario design",
            "Do not claim production traffic distributions",
        ],
        "single_source_warning": True,
        "limited_user_diversity_warning": True,
        "tfidf_fitted": False,
        "scaler_fitted": False,
        "vocabulary_size": "NOT_FITTED",
        "max_features_configured": cfg["text_features"].get("max_features"),
        "validation_error_count": len(validation_errors),
        "exclusion_count": len(exclusions),
        "leakage_finding_count": len(leakage_findings),
    }

    leakage_audit = {
        "text_leakage_findings": [f for f in leakage_findings if f.get("type") == "text"],
        "numeric_leakage_findings": [f for f in leakage_findings if f.get("type") != "text"],
        "pass": len(leakage_findings) == 0,
    }

    feature_manifest = {
        "feature_engineering_version": FEATURE_ENGINEERING_VERSION,
        "created_at": utc_now(),
        "p6_preprocessing_version": p6.get("preprocessing_version"),
        "p6_dataset_manifest_hash": p6["hashes"].get("dataset_manifest"),
        "p6_source_hashes": p6["hashes"],
        "sample_count": len(behavioral_rows),
        "numeric_feature_count": len(default_names),
        "default_numeric_feature_names": enabled_final,
        "disabled_constant_features": disabled,
        "text_method": "tfidf",
        "tfidf_fitted": False,
        "tfidf_config": cfg["text_features"],
        "numeric_scaler_fitted": False,
        "target_classes": dict(class_counts),
        "external_supervised_data_included": False,
        "known_limitations": [
            "Small contextual sample count (~75)",
            "Controlled scenario generation bias",
            "Single source ID in lab (SRC_001)",
            "Limited user diversity",
            "TF-IDF vocabulary unknown until P8 fit on TRAIN",
            "Text length kept diagnostic (not default model feature)",
        ],
        "window_policy": cfg["behavioral_features"].get("window_policy"),
    }

    feature_schema = {
        "schema_version": "1.0",
        "feature_engineering_version": FEATURE_ENGINEERING_VERSION,
        "behavioral_features": schema_features,
        "text_features": {
            "method": "tfidf",
            "fitted_in_p7": False,
            "source_field": "canonical_text",
            "config": cfg["text_features"],
        },
        "targets": {
            "fields": ["sample_id", "target_label", "split_group_run", "split_group_batch", "scenario_id"],
            "scenario_id_is_feature": False,
        },
    }

    ok = (
        alignment["aligned"]
        and leakage_audit["pass"]
        and len(validation_errors) == 0
        and not is_vectorizer_fitted(vectorizer)
        and cfg["text_features"].get("fitted_in_p7") is False
    )

    result = {
        "ok": ok,
        "p6": p6,
        "behavioral_rows": behavioral_rows,
        "text_rows": text_rows,
        "target_rows": target_rows,
        "exclusions": exclusions,
        "alignment": alignment,
        "feature_statistics": feature_statistics,
        "constant_features": {"constant": constant, "near_constant": near_constant},
        "diagnostics": diagnostics,
        "leakage_audit": leakage_audit,
        "feature_manifest": feature_manifest,
        "feature_schema": feature_schema,
        "per_class_diagnostics": per_class,
        "validation_errors": validation_errors,
        "default_enabled": enabled_final,
        "vectorizer_fitted": is_vectorizer_fitted(vectorizer),
    }

    if write:
        out = root / cfg["output"]["root"]
        out.mkdir(parents=True, exist_ok=True)
        # Rewrite behavioral rows with only enabled defaults (constants removed from features dict)
        out_behavior = []
        for row in behavioral_rows:
            feats = {k: v for k, v in row["features"].items() if k in enabled_final}
            out_behavior.append(
                {
                    "sample_id": row["sample_id"],
                    "features": feats,
                    "feature_engineering_version": FEATURE_ENGINEERING_VERSION,
                }
            )
        # text without diagnostic length in model path — keep lengths only in separate diagnostics;
        # spec example has only sample_id + canonical_text
        out_text = [{"sample_id": r["sample_id"], "canonical_text": r["canonical_text"]} for r in text_rows]

        write_jsonl(out / "behavioral_features.jsonl", out_behavior)
        write_jsonl(out / "text_samples.jsonl", out_text)
        write_jsonl(out / "targets.jsonl", target_rows)
        write_jsonl(out / "exclusions.jsonl", exclusions)
        write_json(out / "feature_schema.json", feature_schema)
        write_json(out / "feature_manifest.json", feature_manifest)
        write_json(out / "diagnostics.json", diagnostics)
        write_json(out / "feature_statistics.json", feature_statistics)
        write_json(out / "constant_features.json", {"constant": constant, "near_constant": near_constant})
        write_json(out / "leakage_audit.json", leakage_audit)
        write_json(out / "sample_alignment_report.json", alignment)
        write_json(out / "per_class_diagnostics.json", per_class)
        (out / "README.md").write_text(
            """# P7 Features

Behavioral numeric features + text samples + targets for P8.

- TF-IDF: **unfitted** (fit on TRAIN only in P8)
- No scaler fitted
- No train/test split
- No model training
- Public supervised data: **not included**
""",
            encoding="utf-8",
        )
        result["behavioral_rows"] = out_behavior
        result["text_rows"] = out_text

    return result
