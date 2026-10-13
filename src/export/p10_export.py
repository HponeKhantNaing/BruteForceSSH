"""P10 export builder: package exact P9-selected P8 artifact (no retrain)."""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import yaml

from .bundle_validator import BundleValidator, load_estimator, predict_from_features, sha256_file

EXPECTED_CLASS_SET = {"NORMAL", "SUSPICIOUS", "BRUTE_FORCE"}


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def file_sha(path: Path) -> str:
    return sha256_file(path)


def _load_json(root: Path, rel: str) -> dict[str, Any]:
    return json.loads((root / rel).read_text(encoding="utf-8"))


def _feature_order(root: Path, cfg: dict[str, Any]) -> list[str]:
    order_path = root / cfg["source"]["p8_feature_order"]
    payload = json.loads(order_path.read_text(encoding="utf-8"))
    return list(payload["feature_order"])


def _feature_types(ordered: list[str]) -> dict[str, str]:
    boolean = {
        "has_multiple_attempts",
        "success_after_failure",
        "first_attempt_failed",
        "last_attempt_success",
    }
    ratios = {"failure_ratio"}
    types: dict[str, str] = {}
    for name in ordered:
        if name in boolean:
            types[name] = "boolean_0_1"
        elif name in ratios:
            types[name] = "ratio_0_1"
        elif "gap" in name or name in {"duration_seconds", "attempt_rate_per_second"}:
            types[name] = "non_negative_float"
        else:
            types[name] = "non_negative_numeric"
    return types


def synthetic_smoke_features(ordered: list[str]) -> dict[str, float]:
    """Structurally valid synthetic vector (not a TEST sample)."""
    base = {
        "total_attempts": 4.0,
        "failed_attempts": 3.0,
        "successful_attempts": 1.0,
        "failure_ratio": 0.75,
        "duration_seconds": 18.0,
        "attempt_rate_per_second": 4.0 / 18.0,
        "failed_count_30s_max": 2.0,
        "failed_count_60s_max": 3.0,
        "failed_count_5m_max": 3.0,
        "success_count_5m_max": 1.0,
        "unique_users_total": 1.0,
        "unique_users_60s_max": 1.0,
        "has_multiple_attempts": 1.0,
        "min_inter_attempt_gap_seconds": 2.0,
        "mean_inter_attempt_gap_seconds": 4.5,
        "median_inter_attempt_gap_seconds": 4.0,
        "std_inter_attempt_gap_seconds": 1.2,
        "max_failure_streak": 3.0,
        "success_after_failure": 1.0,
        "failures_before_first_success": 3.0,
        "first_attempt_failed": 1.0,
        "last_attempt_success": 1.0,
    }
    missing = [f for f in ordered if f not in base]
    if missing:
        raise RuntimeError(f"smoke fixture missing features: {missing}")
    return {f: float(base[f]) for f in ordered}


def validate_source(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    src = cfg["source"]
    errors: list[str] = []
    sel = _load_json(root, src["p9_selection"])
    lock = _load_json(root, src["p9_selection_lock"])
    receipt = _load_json(root, src["p9_test_receipt"])
    report = _load_json(root, src["p9_evaluation_report"])
    leak = _load_json(root, src["p9_leakage_audit"])
    checksums = _load_json(root, src["p8_artifact_checksums"])
    ordered = _feature_order(root, cfg)

    model_id = sel.get("selected_model_id")
    expected_id = cfg["release"]["model_id"]
    if model_id != expected_id:
        return {
            "ok": False,
            "blocked": True,
            "status": "BLOCKED",
            "errors": [
                f"P9 selected_model_id={model_id!r} != expected {expected_id!r}; refusing silent package swap"
            ],
        }

    artifact_rel = sel.get("selected_artifact_path")
    artifact_path = root / artifact_rel
    if not artifact_path.is_file():
        errors.append(f"missing selected artifact: {artifact_rel}")

    source_sha = file_sha(artifact_path) if artifact_path.is_file() else None
    p9_sha = sel.get("selected_artifact_sha256")
    lock_sha = lock.get("selected_model_sha256")
    receipt_sha = receipt.get("selected_model_sha256")
    p8_sha = checksums.get("random_forest_behavior")

    expected_rep = cfg["source"].get("expected_representation", "behavior_raw")
    checks = {
        "p9_selected_model_id": model_id == expected_id,
        "representation": sel.get("selected_representation") == expected_rep,
        "selection_lock_exists": (root / src["p9_selection_lock"]).is_file(),
        "test_receipt_exists": (root / src["p9_test_receipt"]).is_file(),
        "test_models_count_1": receipt.get("models_evaluated_on_test") == 1,
        "p9_fit_calls_0": (leak.get("fit_calls") if leak.get("fit_calls") is not None else report.get("fit_calls"))
        == 0,
        "source_sha_eq_p9": source_sha == p9_sha,
        "source_sha_eq_lock": source_sha == lock_sha,
        "source_sha_eq_receipt": source_sha == receipt_sha,
        "source_sha_eq_p8_checksum": source_sha == p8_sha,
        "lock_before_test": lock.get("locked_at", "") < receipt.get("evaluated_at", ""),
        "feature_count": len(ordered) == int(cfg["validation"]["expected_feature_count"]),
    }

    # Load model classes
    payload = joblib.load(artifact_path)
    model = payload["model"]
    classes = [str(c) for c in model.classes_]
    checks["class_set"] = set(classes) == EXPECTED_CLASS_SET
    checks["n_features_in"] = int(getattr(model, "n_features_in_", -1)) == len(ordered)
    # Payload uses "behavior"; P9 semantic label is behavior_raw (unscaled).
    checks["payload_is_behavior"] = payload.get("representation") in {"behavior", "behavior_raw"}

    for key, ok in checks.items():
        if not ok:
            errors.append(f"check failed: {key}")

    return {
        "ok": not errors,
        "blocked": False,
        "status": "PASS" if not errors else "FAIL",
        "checks": checks,
        "errors": errors,
        "selected_model_id": model_id,
        "selected_representation": sel.get("selected_representation"),
        "payload_representation": payload.get("representation"),
        "source_artifact_path": artifact_rel,
        "source_artifact_sha256": source_sha,
        "p9_selected_sha256": p9_sha,
        "p8_checksum_sha256": p8_sha,
        "model_class_order": classes,
        "feature_order": ordered,
        "feature_count": len(ordered),
        "n_features_in_": int(getattr(model, "n_features_in_", -1)),
        "lock": lock,
        "receipt": receipt,
        "selection": sel,
        "validation_metric": {
            "primary_metric": sel.get("primary_metric"),
            "primary_metric_value": sel.get("primary_metric_value"),
        },
        "tfidf_required": False,
        "scaler_required": False,
    }


def dry_run(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    src_info = validate_source(root, cfg)
    release = cfg["release"]
    return {
        "p9_status": "PASS" if src_info.get("ok") else ("BLOCKED" if src_info.get("blocked") else "FAIL"),
        "selected_model_id": src_info.get("selected_model_id"),
        "selected_representation": src_info.get("selected_representation"),
        "source_artifact_path": src_info.get("source_artifact_path"),
        "source_sha256": src_info.get("source_artifact_sha256"),
        "required_runtime_dependencies": {
            "model": "required",
            "feature_order": "required",
            "tfidf": "not required",
            "scaler": "not required",
        },
        "planned_release_id": release["release_id"],
        "tfidf_included": False,
        "scaler_included": False,
        "feature_order_included": True,
        "writes": False,
        "source_validation": src_info,
    }


def _build_schemas(
    release_dir: Path,
    ordered: list[str],
    class_order: list[str],
    release_id: str,
    window_policy: dict[str, Any],
) -> None:
    feature_types = _feature_types(ordered)
    contract = {
        "contract_version": "1.0",
        "representation": "behavior_raw",
        "feature_count": len(ordered),
        "ordered_features": ordered,
        "feature_types": feature_types,
        "feature_order_hash": hashlib.sha256(
            json.dumps(ordered, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "scaling_required": False,
        "behavior_scaler_required": False,
        "text_required": False,
        "tfidf_required": False,
        "missing_values_allowed": False,
        "non_finite_values_allowed": False,
        "unknown_features_policy": "reject",
        "positional_vector_accepted": False,
        "model_class_order": class_order,
        "window_policy": window_policy,
        "training_context": "one contextual run = one sample",
        "realtime_context_policy": "P11_DECISION_REQUIRED",
        "notes": [
            "Features are RAW behavioral values (no StandardScaler).",
            "P11 must reproduce P7 logical-attempt and inclusive [t-W, t] window semantics.",
            "Continuous-stream session policy is a P11 decision; do not redefine feature meanings.",
        ],
    }
    write_json(release_dir / "schema" / "feature_contract.json", contract)

    props = {}
    for name in ordered:
        if feature_types[name] == "boolean_0_1":
            props[name] = {"type": "number", "enum": [0, 1]}
        elif feature_types[name] == "ratio_0_1":
            props[name] = {"type": "number", "minimum": 0, "maximum": 1}
        else:
            props[name] = {"type": "number", "minimum": 0}
    input_schema = {
        "schema_version": "1.0",
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "P10BehaviorRawInput",
        "type": "object",
        "required": ["schema_version", "features"],
        "additionalProperties": False,
        "properties": {
            "schema_version": {"type": "string", "const": "1.0"},
            "features": {
                "type": "object",
                "required": ordered,
                "additionalProperties": False,
                "properties": props,
            },
        },
    }
    write_json(release_dir / "schema" / "input.schema.json", input_schema)

    output_schema = {
        "schema_version": "1.0",
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "P10PredictionOutput",
        "type": "object",
        "required": [
            "model_version",
            "predicted_label",
            "class_probabilities",
            "probability_type",
        ],
        "additionalProperties": True,
        "properties": {
            "model_version": {"type": "string", "const": release_id},
            "predicted_label": {"type": "string", "enum": sorted(EXPECTED_CLASS_SET)},
            "class_probabilities": {
                "type": "object",
                "required": sorted(EXPECTED_CLASS_SET),
                "additionalProperties": False,
                "properties": {
                    "NORMAL": {"type": "number"},
                    "SUSPICIOUS": {"type": "number"},
                    "BRUTE_FORCE": {"type": "number"},
                },
            },
            "probability_type": {"type": "string", "const": "uncalibrated"},
        },
        "example": {
            "model_version": release_id,
            "predicted_label": "NORMAL",
            "class_probabilities": {
                "NORMAL": 0.0,
                "SUSPICIOUS": 0.0,
                "BRUTE_FORCE": 0.0,
            },
            "probability_type": "uncalibrated",
        },
    }
    write_json(release_dir / "schema" / "output.schema.json", output_schema)


def _write_metadata(
    root: Path,
    release_dir: Path,
    cfg: dict[str, Any],
    src_info: dict[str, Any],
    release_model_sha: str,
) -> None:
    src = cfg["source"]
    release = cfg["release"]
    report = _load_json(root, src["p9_evaluation_report"])
    train = _load_json(root, src["p8_training_manifest"])
    sel = src_info["selection"]
    receipt = src_info["receipt"]
    lock = src_info["lock"]

    limitations = [
        "small training set (45 TRAIN samples)",
        "controlled scenario bias",
        "single lab environment / single primary source",
        "limited username diversity",
        "no INVALID_USER examples in training source",
        "behavior features may reflect scenario design",
        "held-out TEST covers only 3 scenario groups (15 runs)",
        "uncalibrated Random Forest probabilities",
        "The model was trained on bounded contextual scenario runs. "
        "Continuous real-time inference requires a defined runtime context/session policy before deployment.",
    ]

    model_card = {
        "model_id": release["model_id"],
        "model_version": release["version"],
        "release_id": release["release_id"],
        "model_family": "RandomForestClassifier",
        "representation": "behavior_raw",
        "training_phase": "P8",
        "selected_in_phase": "P9",
        "packaged_in_phase": "P10",
        "maturity": release["maturity"],
        "release_channel": release["channel"],
        "classes": sorted(EXPECTED_CLASS_SET),
        "model_class_order": src_info["model_class_order"],
        "feature_count": src_info["feature_count"],
        "training_samples": train.get("train_sample_count"),
        "validation_samples": train.get("validation_sample_count"),
        "test_samples": train.get("test_sample_count"),
        "p9_selected_validation_metric": {
            "name": sel.get("primary_metric"),
            "value": sel.get("primary_metric_value"),
        },
        "p9_final_test_result": {
            "correct_over_total": (
                f"{report['test']['metrics']['correct_count']}/"
                f"{report['test']['metrics']['total_count']}"
            ),
            "macro_f1": report["test"]["metrics"]["macro_f1"],
            "note": "Frozen P9 result; not recomputed in P10.",
        },
        "intended_use": (
            "controlled-lab SSH authentication behavior classification "
            "for the project's real-time threat-monitoring prototype"
        ),
        "out_of_scope_use": [
            "universal IDS",
            "internet-wide attack detector",
            "production security guarantee",
            "calibrated risk scoring",
        ],
        "known_limitations": limitations,
        "probability_calibration": "UNCALIBRATED",
        "custom_thresholds": False,
    }
    write_json(release_dir / "metadata" / "model_card.json", model_card)

    eval_summary = {
        "evaluation_recomputed_in_p10": False,
        "selected_model": sel["selected_model_id"],
        "validation_selection_rule": sel.get("selection_reason"),
        "validation_selected_metric": {
            "name": sel.get("primary_metric"),
            "value": sel.get("primary_metric_value"),
        },
        "test_sample_count": report["test"]["sample_count"],
        "test_correct_count": report["test"]["metrics"]["correct_count"],
        "test_macro_f1": report["test"]["metrics"]["macro_f1"],
        "validation_scenarios": report["validation"]["scenarios"],
        "test_scenarios": report["test"]["scenarios"],
        "test_evaluation_receipt_sha256": file_sha(root / src["p9_test_receipt"]),
        "selection_lock_sha256": file_sha(root / src["p9_selection_lock"]),
        "maturity_note": "CONTROLLED_LAB_VALIDATED — not production-proven",
    }
    write_json(release_dir / "metadata" / "evaluation_summary.json", eval_summary)

    provenance = {
        "chain": [
            "P2/P3 raw data",
            "P4 labels",
            "P6 canonical data",
            "P7 features",
            "P8 training",
            "P9 selection/evaluation",
            "P10 release",
        ],
        "hashes": {
            "p7_feature_manifest": file_sha(root / src["p7_feature_manifest"]),
            "p8_split_manifest": file_sha(root / src["p8_split_manifest"]),
            "p8_training_manifest": file_sha(root / src["p8_training_manifest"]),
            "p8_selected_model": src_info["source_artifact_sha256"],
            "p9_model_selection": file_sha(root / src["p9_selection"]),
            "p9_selection_lock": file_sha(root / src["p9_selection_lock"]),
            "p9_test_receipt": file_sha(root / src["p9_test_receipt"]),
            "p10_release_model": release_model_sha,
        },
        "identifiers": {
            "p7_feature_version": train.get("p7_feature_version"),
            "p8_training_version": train.get("training_version"),
            "p8_split_version": train.get("split_version"),
            "p9_evaluation_version": sel.get("evaluation_version"),
            "p10_export_version": cfg.get("export_version"),
            "release_id": release["release_id"],
        },
        "byte_identity": {
            "source_artifact_path": src_info["source_artifact_path"],
            "source_artifact_sha256": src_info["source_artifact_sha256"],
            "release_artifact_path": f"artifacts/p10/releases/{release['release_id']}/model/random_forest_behavior.joblib",
            "release_artifact_sha256": release_model_sha,
            "byte_identity": release_model_sha == src_info["source_artifact_sha256"],
        },
        "selection_lock": {
            "locked_at": lock.get("locked_at"),
            "test_evaluated_at": receipt.get("evaluated_at"),
            "lock_before_test": lock.get("locked_at", "") < receipt.get("evaluated_at", ""),
        },
    }
    write_json(release_dir / "metadata" / "provenance.json", provenance)

    env = {
        "python_version": platform.python_version(),
        "scikit_learn_version": _pkg_version("sklearn"),
        "numpy_version": _pkg_version("numpy"),
        "scipy_version": _pkg_version("scipy"),
        "joblib_version": _pkg_version("joblib"),
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "p8_recorded_scikit_learn_version": train.get("scikit_learn_version"),
        "p8_recorded_python_version": train.get("python_version"),
    }
    write_json(release_dir / "metadata" / "environment.json", env)

    compatibility = {
        "serialization_format": "joblib (sklearn estimator inside dict payload)",
        "tested_python_version": env["python_version"],
        "tested_scikit_learn_version": env["scikit_learn_version"],
        "tested_numpy_version": env["numpy_version"],
        "tested_scipy_version": env["scipy_version"],
        "tested_joblib_version": env["joblib_version"],
        "supported_architecture_assumptions": [
            env["architecture"],
            "Load with matching major sklearn version where possible",
        ],
        "untested_versions_claimed": False,
        "notes": [
            "Do not claim compatibility with untested sklearn/python versions.",
            "joblib/sklearn pickle compatibility can break across major upgrades.",
        ],
    }
    write_json(release_dir / "metadata" / "compatibility.json", compatibility)


def _pkg_version(name: str) -> str:
    if name == "sklearn":
        import sklearn

        return sklearn.__version__
    mod = __import__(name)
    return getattr(mod, "__version__", "unknown")


def _write_checksums(release_dir: Path) -> None:
    lines = [
        "# CHECKSUMS.sha256 — SHA-256 of important release files.",
        "# Policy: this checksum file is excluded from its own checksum list.",
        "",
    ]
    include = [
        "README.md",
        "RELEASE.json",
        "MANIFEST.json",
        "model/random_forest_behavior.joblib",
        "schema/input.schema.json",
        "schema/output.schema.json",
        "schema/feature_contract.json",
        "metadata/model_card.json",
        "metadata/provenance.json",
        "metadata/evaluation_summary.json",
        "metadata/environment.json",
        "metadata/compatibility.json",
        "verification/smoke_test_input.json",
        "verification/smoke_test_expected.json",
    ]
    for rel in include:
        digest = file_sha(release_dir / rel)
        lines.append(f"{digest}  {rel}")
    (release_dir / "CHECKSUMS.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_readme(release_dir: Path, cfg: dict[str, Any], src_info: dict[str, Any]) -> None:
    release = cfg["release"]
    ordered = src_info["feature_order"]
    text = f"""# {release['release_id']}

Packaged Random Forest SSH auth behavior classifier for the lab prototype.

## What this is

- **Model ID:** `{release['model_id']}`
- **Version:** `{release['version']}`
- **Channel:** `{release['channel']}`
- **Maturity:** `{release['maturity']}`
- **Representation:** `behavior_raw` (22 raw behavioral features; no TF-IDF; no StandardScaler)

This is **not** production-proven. P9 TEST was 15 held-out controlled runs / 3 scenario groups.

## Classes

`NORMAL` · `SUSPICIOUS` · `BRUTE_FORCE`

Internal `model.classes_` order is recorded in `MANIFEST.json` / `schema/feature_contract.json`.

## Required input

Provide all 22 features by name (order enforced by contract). Unknown fields are rejected.

```
{chr(10).join(ordered)}
```

## Validate / smoke

From repository root:

```bash
python3 scripts/p10_export_model.py --validate-release
python3 scripts/p10_export_model.py --smoke-test
```

Offline only — no live logs, no Discord, no network.

## Probabilities

`predict_proba` values are **uncalibrated**. Do not treat them as calibrated confidence or true risk.

## Limitations

- Small dataset; controlled lab scenarios; single-source environment
- Limited user diversity; only 3 held-out TEST scenario groups
- Uncalibrated probabilities
- Trained on **bounded contextual runs** (`one run = one sample`). Continuous real-time inference requires a defined runtime context/session policy (P11) without changing feature semantics.

## P11 handoff

Use this release root, `schema/feature_contract.json`, and `MANIFEST.json`. Reproduce P7 logical-attempt + inclusive `[t-W, t]` window semantics exactly.
"""
    (release_dir / "README.md").write_text(text, encoding="utf-8")


def export_release(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    src_info = validate_source(root, cfg)
    if src_info.get("blocked"):
        return src_info
    if not src_info.get("ok"):
        return {"ok": False, "status": "FAIL", "errors": src_info.get("errors", []), "source": src_info}

    release = cfg["release"]
    release_id = release["release_id"]
    releases_root = root / cfg["paths"]["releases_root"]
    release_dir = releases_root / release_id
    if release_dir.exists():
        return {
            "ok": False,
            "status": "REFUSED",
            "error": "release version already exists",
            "release_dir": str(release_dir.relative_to(root)),
        }

    # Snapshot P8/P9 hashes before write
    p8_model = root / src_info["source_artifact_path"]
    p8_before = file_sha(p8_model)
    p9_paths = [
        cfg["source"]["p9_selection"],
        cfg["source"]["p9_selection_lock"],
        cfg["source"]["p9_test_receipt"],
        cfg["source"]["p9_evaluation_report"],
    ]
    p9_before = {rel: file_sha(root / rel) for rel in p9_paths}

    release_dir.mkdir(parents=True, exist_ok=False)
    (release_dir / "model").mkdir()
    (release_dir / "schema").mkdir()
    (release_dir / "metadata").mkdir()
    (release_dir / "verification").mkdir()

    dest_model = release_dir / "model" / "random_forest_behavior.joblib"
    shutil.copy2(p8_model, dest_model)
    release_sha = file_sha(dest_model)
    if release_sha != p8_before:
        shutil.rmtree(release_dir)
        return {"ok": False, "status": "BLOCKED", "error": "byte identity failed after copy"}

    ordered = src_info["feature_order"]
    class_order = src_info["model_class_order"]
    # Canonical label presentation order for outputs (stable project order)
    label_presentation = ["NORMAL", "SUSPICIOUS", "BRUTE_FORCE"]

    _build_schemas(release_dir, ordered, class_order, release_id, cfg.get("window_policy", {}))
    _write_metadata(root, release_dir, cfg, src_info, release_sha)

    # Smoke fixtures + source/release parity
    smoke_features = synthetic_smoke_features(ordered)
    smoke_input = {"schema_version": "1.0", "features": smoke_features}
    write_json(release_dir / "verification" / "smoke_test_input.json", smoke_input)

    source_payload = joblib.load(p8_model)
    source_model = source_payload["model"]
    release_payload = joblib.load(dest_model)
    release_model = release_payload["model"]

    # Patch fit counters for export path
    fit_calls = {"n": 0}

    def _block(obj: Any, name: str) -> None:
        if not hasattr(obj, "fit"):
            return
        original = obj.fit

        def blocked(*_a, **_k):
            fit_calls["n"] += 1
            raise RuntimeError(f"P10 forbid fit on {name}")

        obj.fit = blocked  # type: ignore[method-assign]
        obj._p10_original_fit = original

    _block(source_model, "source")
    _block(release_model, "release")

    src_pred = predict_from_features(
        source_model,
        smoke_features,
        ordered,
        model_version=release_id,
        class_order=label_presentation,
    )
    rel_pred = predict_from_features(
        release_model,
        smoke_features,
        ordered,
        model_version=release_id,
        class_order=label_presentation,
    )
    parity_ok = src_pred["predicted_label"] == rel_pred["predicted_label"] and np.allclose(
        src_pred["probability_vector_in_model_class_order"],
        rel_pred["probability_vector_in_model_class_order"],
    )
    if not parity_ok:
        shutil.rmtree(release_dir)
        return {"ok": False, "status": "BLOCKED", "error": "source/release prediction parity failed"}

    smoke_expected = {
        "purpose": "packaging regression verification (not accuracy evidence)",
        "predicted_label": rel_pred["predicted_label"],
        "probability_vector_shape": [len(class_order)],
        "class_labels": label_presentation,
        "model_class_order": class_order,
        "class_probabilities": rel_pred["class_probabilities"],
        "probability_type": "uncalibrated",
    }
    write_json(release_dir / "verification" / "smoke_test_expected.json", smoke_expected)

    feature_order_hash = hashlib.sha256(
        json.dumps(ordered, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    manifest = {
        "release_id": release_id,
        "model_id": release["model_id"],
        "model_version": release["version"],
        "release_channel": release["channel"],
        "maturity": release["maturity"],
        "model_file": "model/random_forest_behavior.joblib",
        "model_sha256": release_sha,
        "representation": "behavior_raw",
        "feature_contract": "schema/feature_contract.json",
        "feature_count": len(ordered),
        "feature_order_hash": feature_order_hash,
        "class_labels": label_presentation,
        "model_class_order": class_order,
        "tfidf_required": False,
        "scaler_required": False,
        "p8_training_version": _load_json(root, cfg["source"]["p8_training_manifest"]).get(
            "training_version"
        ),
        "p9_evaluation_version": src_info["selection"].get("evaluation_version"),
        "selection_lock_hash": file_sha(root / cfg["source"]["p9_selection_lock"]),
        "test_receipt_hash": file_sha(root / cfg["source"]["p9_test_receipt"]),
        "created_at": utc_now(),
        "byte_identity": True,
        "source_artifact_sha256": p8_before,
    }
    write_json(release_dir / "MANIFEST.json", manifest)

    release_doc = {
        "name": "RF Behavior Lab Release",
        "version": release["version"],
        "release_id": release_id,
        "status": "RELEASED",
        "model": release["model_id"],
        "representation": "behavior_raw",
        "labels": label_presentation,
        "intended_use": (
            "controlled-lab SSH authentication behavior classification "
            "for the project's real-time threat-monitoring prototype"
        ),
        "limitations": [
            "CONTROLLED_LAB_VALIDATED only",
            "small held-out TEST (15 runs / 3 scenarios)",
            "uncalibrated probabilities",
            "run-level training context vs continuous-stream P11 context gap",
        ],
        "channel": release["channel"],
        "maturity": release["maturity"],
    }
    write_json(release_dir / "RELEASE.json", release_doc)
    _write_readme(release_dir, cfg, src_info)
    _write_checksums(release_dir)

    validator = BundleValidator(release_dir, expected_source_sha256=p8_before)
    verification = validator.validate()
    verification["source_release_prediction_parity"] = "PASS" if parity_ok else "FAIL"
    verification["source_release_probability_parity"] = "PASS" if parity_ok else "FAIL"
    verification["fit_calls_during_export"] = fit_calls["n"]
    verification["evaluation_recomputed_in_p10"] = False
    write_json(release_dir / "verification" / "verification_report.json", verification)

    # Refresh checksums to include verification_report? Prompt says at minimum listed files;
    # verification_report is generated after checksums. Keep report out of CHECKSUMS or update.
    # Policy: verification_report may change during validate; exclude from CHECKSUMS list (already excluded).

    archive_info = None
    if cfg.get("bundle", {}).get("create_archive", True):
        dist_root = root / cfg["paths"]["dist_root"]
        dist_root.mkdir(parents=True, exist_ok=True)
        archive_path = dist_root / f"{release_id}.tar.gz"
        if archive_path.exists():
            return {
                "ok": False,
                "status": "REFUSED",
                "error": "archive already exists",
                "release_ok": verification.get("ok"),
            }
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(release_dir, arcname=release_id)
        archive_info = {
            "path": str(archive_path.relative_to(root)),
            "sha256": file_sha(archive_path),
        }

    p8_after = file_sha(p8_model)
    p9_after = {rel: file_sha(root / rel) for rel in p9_paths}

    return {
        "ok": bool(verification.get("ok")) and parity_ok and fit_calls["n"] == 0,
        "status": "PASS" if verification.get("ok") and parity_ok else "FAIL",
        "release_id": release_id,
        "release_dir": str(release_dir.relative_to(root)),
        "source_sha256": p8_before,
        "release_sha256": release_sha,
        "byte_identity": release_sha == p8_before,
        "verification": verification,
        "smoke": rel_pred,
        "archive": archive_info,
        "p8_unchanged": p8_before == p8_after,
        "p9_unchanged": p9_before == p9_after,
        "fit_calls": fit_calls["n"],
        "retraining": False,
        "test_recomputed": False,
    }


def validate_release(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    release_id = cfg["release"]["release_id"]
    release_dir = root / cfg["paths"]["releases_root"] / release_id
    if not release_dir.is_dir():
        return {"ok": False, "error": f"release not found: {release_id}"}
    src_info = validate_source(root, cfg)
    validator = BundleValidator(
        release_dir,
        expected_source_sha256=src_info.get("source_artifact_sha256"),
    )
    result = validator.validate()
    result["release_id"] = release_id
    return result


def smoke_test_release(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    release_id = cfg["release"]["release_id"]
    release_dir = root / cfg["paths"]["releases_root"] / release_id
    if not release_dir.is_dir():
        return {"ok": False, "error": f"release not found: {release_id}"}
    manifest = json.loads((release_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    contract = json.loads((release_dir / "schema/feature_contract.json").read_text(encoding="utf-8"))
    smoke_in = json.loads(
        (release_dir / "verification/smoke_test_input.json").read_text(encoding="utf-8")
    )
    model, _payload = load_estimator(release_dir / "model" / "random_forest_behavior.joblib")
    pred = predict_from_features(
        model,
        smoke_in["features"],
        list(contract["ordered_features"]),
        model_version=manifest["release_id"],
        class_order=list(manifest["class_labels"]),
    )
    return {
        "ok": True,
        "note": "This is a packaging smoke test, not an accuracy evaluation.",
        "prediction": pred,
        "network_calls": 0,
        "live_logs": False,
        "discord": False,
    }


def report_release(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    release_id = cfg["release"]["release_id"]
    release_dir = root / cfg["paths"]["releases_root"] / release_id
    if not release_dir.is_dir():
        return {"ok": False, "error": f"release not found: {release_id}"}
    manifest = json.loads((release_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    release_doc = json.loads((release_dir / "RELEASE.json").read_text(encoding="utf-8"))
    eval_summary = json.loads(
        (release_dir / "metadata/evaluation_summary.json").read_text(encoding="utf-8")
    )
    return {
        "ok": True,
        "manifest": manifest,
        "release": release_doc,
        "evaluation_summary": eval_summary,
        "note": "P9 metrics referenced only; not recomputed.",
    }
