"""P9 evaluation orchestrator: validation → lock selection → selected-only TEST."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from evaluation.error_analysis import build_error_records, disagreement_analysis
from evaluation.metrics import compute_classification_metrics
from evaluation.model_evaluator import (
    FitCallError,
    FrozenArtifactBundle,
    MODEL_REPRESENTATION,
    canonical_json_sha256,
    sha256_file,
)
from evaluation.model_selector import select_model

EVALUATION_VERSION = "p9-v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid YAML: {path}")
    return data


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def out_root(root: Path, cfg: dict[str, Any]) -> Path:
    return root / cfg["output"]["root"]


def scenario_for_class(split_part: dict[str, Any], targets: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Map class → scenario_id for a partition (one scenario per class expected)."""
    mapping: dict[str, set[str]] = defaultdict(set)
    for sid in split_part["sample_ids"]:
        t = targets[sid]
        mapping[t["target_label"]].add(t["scenario_id"])
    return {lab: sorted(scs)[0] if len(scs) == 1 else ",".join(sorted(scs)) for lab, scs in mapping.items()}


def evaluate_validation(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    bundle = FrozenArtifactBundle(root, cfg)
    integrity = bundle.verify_integrity()
    if not integrity["ok"]:
        return {"ok": False, "stage": "integrity", "integrity": integrity}
    if integrity.get("p8_test_metrics_computed"):
        return {"ok": False, "stage": "test_contamination", "integrity": integrity}

    class_order = list(cfg["class_order"])
    val_ids = bundle.sample_ids("validation")
    y_true = bundle.labels(val_ids)
    matrices = bundle.build_matrices(val_ids)

    metrics_by_model: dict[str, Any] = {}
    cms: dict[str, Any] = {}
    preds_by_model: dict[str, list[str]] = {}
    comparison_rows = []

    for mid in cfg["candidates"]:
        X = bundle.matrix_for_model(mid, matrices)
        y_pred = list(bundle.predict(mid, X))
        preds_by_model[mid] = y_pred
        metrics = compute_classification_metrics(y_true, y_pred, class_order=class_order)
        metrics["model_id"] = mid
        metrics["representation"] = MODEL_REPRESENTATION[mid]
        metrics_by_model[mid] = metrics
        cms[mid] = metrics["confusion_matrix"]
        comparison_rows.append(
            {
                "model_id": mid,
                "representation": MODEL_REPRESENTATION[mid],
                "accuracy": metrics["accuracy"],
                "balanced_accuracy": metrics["balanced_accuracy"],
                "macro_precision": metrics["macro_precision"],
                "macro_recall": metrics["macro_recall"],
                "macro_f1": metrics["macro_f1"],
                "weighted_f1": metrics["weighted_f1"],
                "minimum_class_recall": metrics["minimum_class_recall"],
                "normal_recall": metrics["normal_recall"],
                "suspicious_recall": metrics["suspicious_recall"],
                "brute_force_recall": metrics["brute_force_recall"],
            }
        )

    # predictions jsonl
    pred_rows = []
    for i, sid in enumerate(val_ids):
        pred_rows.append(
            {
                "sample_id": sid,
                "scenario_id": bundle.targets[sid]["scenario_id"],
                "true_label": y_true[i],
                "predictions": {mid: preds_by_model[mid][i] for mid in cfg["candidates"]},
            }
        )

    # errors across all models on validation
    all_errors = []
    for mid in cfg["candidates"]:
        all_errors.extend(
            build_error_records(
                val_ids,
                y_true,
                preds_by_model[mid],
                bundle.targets,
                bundle.behavioral,
                model_id=mid,
            )
        )
    disagreements = disagreement_analysis(val_ids, y_true, preds_by_model, bundle.targets)

    ablation = {
        "partition": "validation",
        "models": {
            mid: {
                "macro_f1": metrics_by_model[mid]["macro_f1"],
                "accuracy": metrics_by_model[mid]["accuracy"],
                "balanced_accuracy": metrics_by_model[mid]["balanced_accuracy"],
                "minimum_class_recall": metrics_by_model[mid]["minimum_class_recall"],
                "per_class": metrics_by_model[mid]["per_class"],
            }
            for mid in (
                "logistic_regression_text",
                "logistic_regression_behavior",
                "logistic_regression_hybrid",
            )
        },
        "notes": [
            "VALIDATION-only ablation; same Logistic Regression family",
            "Do not interpret as causal proof",
        ],
    }

    # scenario breakdown for each model
    scen_map = scenario_for_class(bundle.split["validation"], bundle.targets)
    scenario_breakdown = {"validation": {}, "test": None}
    for mid in cfg["candidates"]:
        by_sc: dict[str, dict[str, Any]] = {}
        for i, sid in enumerate(val_ids):
            sc = bundle.targets[sid]["scenario_id"]
            if sc not in by_sc:
                by_sc[sc] = {
                    "scenario_id": sc,
                    "true_class": bundle.targets[sid]["target_label"],
                    "correct": 0,
                    "total": 0,
                    "predicted_labels": Counter(),
                }
            by_sc[sc]["total"] += 1
            pred = preds_by_model[mid][i]
            by_sc[sc]["predicted_labels"][pred] += 1
            if pred == y_true[i]:
                by_sc[sc]["correct"] += 1
        scenario_breakdown["validation"][mid] = {
            sc: {
                **v,
                "predicted_labels": dict(v["predicted_labels"]),
                "accuracy": v["correct"] / v["total"] if v["total"] else 0.0,
            }
            for sc, v in by_sc.items()
        }

    out = out_root(root, cfg)
    write_json(out / "validation_metrics.json", metrics_by_model)
    write_jsonl(out / "validation_predictions.jsonl", pred_rows)
    write_json(out / "validation_confusion_matrices.json", cms)
    write_json(
        out / "validation_model_comparison.json",
        {
            "partition": "validation",
            "primary_metric": cfg["selection"]["primary_metric"],
            "rows": comparison_rows,
        },
    )
    write_json(out / "ablation_analysis.json", ablation)
    write_json(
        out / "error_analysis.json",
        {
            "validation_errors": all_errors,
            "validation_disagreements_text_behavior_hybrid": disagreements,
            "test_errors_selected": None,
        },
    )
    write_json(out / "scenario_breakdown.json", scenario_breakdown)

    leakage_audit = {
        "scenario_overlap": integrity["scenario_overlap"],
        "target_leakage": False,
        "raw_ip_leakage": False,
        "raw_username_leakage": False,
        "fit_calls": bundle.fit_calls,
        "tfidf_refitted": False,
        "scaler_refitted": False,
        "classifier_refitted": False,
        "test_used_for_selection": False,
        "pass": integrity["ok"] and bundle.fit_calls == 0,
    }
    write_json(out / "leakage_audit.json", leakage_audit)

    return {
        "ok": True,
        "integrity": integrity,
        "validation_samples": len(val_ids),
        "validation_scenarios": scen_map,
        "metrics_by_model": metrics_by_model,
        "comparison_rows": comparison_rows,
        "fit_calls": bundle.fit_calls,
        "disagreements": disagreements,
    }


def select_and_lock(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    out = out_root(root, cfg)
    metrics_path = out / "validation_metrics.json"
    if not metrics_path.is_file():
        raise RuntimeError("validation_metrics.json missing — run --evaluate-validation first")

    metrics_by_model = json.loads(metrics_path.read_text(encoding="utf-8"))
    selection = select_model(
        metrics_by_model,
        primary_metric=cfg["selection"]["primary_metric"],
        tie_breakers=cfg["selection"]["tie_breakers"],
        exact_tie_preference=cfg["selection"]["exact_tie_preference"],
    )

    bundle = FrozenArtifactBundle(root, cfg)
    integrity = bundle.verify_integrity()
    if not integrity["ok"]:
        return {"ok": False, "integrity": integrity}

    mid = selection["selected_model_id"]
    model_info = bundle.models[mid]
    split_sha = integrity["split_canonical_sha256"]

    selection_manifest = {
        "selected_model_id": mid,
        "selected_artifact_path": model_info["path"],
        "selected_artifact_sha256": model_info["sha256"],
        "selected_representation": MODEL_REPRESENTATION[mid],
        "primary_metric": selection["primary_metric"],
        "primary_metric_value": selection["primary_metric_value"],
        "minimum_class_recall": selection["minimum_class_recall"],
        "tie_break_values": selection["tie_break_values"],
        "tie_break_used": selection["tie_break_used"],
        "selection_reason": selection["selection_reason"],
        "selection_rule_version": selection["selection_rule_version"],
        "ranked_model_ids": selection["ranked_model_ids"],
        "validation_scenarios": scenario_for_class(bundle.split["validation"], bundle.targets),
        "selected_at": utc_now(),
        "test_evaluated": False,
        "split_manifest_sha256": split_sha,
        "evaluation_version": EVALUATION_VERSION,
    }
    write_json(out / "model_selection.json", selection_manifest)
    sel_sha = sha256_file(out / "model_selection.json")

    lock = {
        "selection_manifest_sha256": sel_sha,
        "selected_model_id": mid,
        "selected_model_sha256": model_info["sha256"],
        "split_manifest_sha256": split_sha,
        "locked_at": utc_now(),
        "test_evaluated": False,
    }
    write_json(out / "model_selection.lock.json", lock)

    return {"ok": True, "selection": selection_manifest, "lock": lock, "selection_sha256": sel_sha}


def evaluate_test_selected(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    out = out_root(root, cfg)
    receipt_path = out / "test_evaluation_receipt.json"
    if receipt_path.is_file() and not cfg["test"].get("allow_repeat_test_evaluation"):
        return {
            "ok": False,
            "refused": True,
            "reason": "test_evaluation_receipt.json already exists — TEST is locked",
            "receipt": json.loads(receipt_path.read_text(encoding="utf-8")),
        }

    lock_path = out / "model_selection.lock.json"
    sel_path = out / "model_selection.json"
    if not lock_path.is_file() or not sel_path.is_file():
        raise RuntimeError("Selection lock missing — run --select-model first")

    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    selection = json.loads(sel_path.read_text(encoding="utf-8"))

    # verify selection file hash matches lock
    if sha256_file(sel_path) != lock["selection_manifest_sha256"]:
        raise RuntimeError("model_selection.json hash mismatch vs lock")

    bundle = FrozenArtifactBundle(root, cfg)
    integrity = bundle.verify_integrity()
    if not integrity["ok"]:
        return {"ok": False, "integrity": integrity}
    if integrity["split_canonical_sha256"] != lock["split_manifest_sha256"]:
        raise RuntimeError("Split hash mismatch vs selection lock")

    mid = selection["selected_model_id"]
    if bundle.models[mid]["sha256"] != lock["selected_model_sha256"]:
        raise RuntimeError("Selected model artifact hash mismatch")

    # Structural guard: only selected model may be used on TEST
    test_ids = bundle.sample_ids("test")
    y_true = bundle.labels(test_ids)
    matrices = bundle.build_matrices(test_ids)
    X = bundle.matrix_for_model(mid, matrices)
    details = bundle.predict_details(mid, X)
    y_pred = list(details["predicted_label"])

    # Ensure we did not iterate all models — only mid predicted
    class_order = list(cfg["class_order"])
    metrics = compute_classification_metrics(y_true, y_pred, class_order=class_order)
    metrics["model_id"] = mid
    metrics["representation"] = MODEL_REPRESENTATION[mid]
    metrics["correct_over_total"] = f"{metrics['correct_count']}/{metrics['total_count']}"

    # predictions
    pred_rows = []
    for i, sid in enumerate(test_ids):
        row: dict[str, Any] = {
            "sample_id": sid,
            "scenario_id": bundle.targets[sid]["scenario_id"],
            "true_label": y_true[i],
            "predicted_label": y_pred[i],
            "correct": y_true[i] == y_pred[i],
        }
        if "uncalibrated_probabilities" in details:
            probs = details["uncalibrated_probabilities"][i]
            classes = details["probability_classes"]
            row["uncalibrated_probabilities"] = {
                str(c): float(probs[j]) for j, c in enumerate(classes)
            }
        if "decision_scores" in details:
            scores = details["decision_scores"][i]
            if hasattr(scores, "__iter__") and not isinstance(scores, (str, bytes)):
                row["decision_scores"] = {
                    class_order[j] if j < len(class_order) else str(j): float(s)
                    for j, s in enumerate(list(scores))
                }
            else:
                row["decision_scores"] = float(scores)
        pred_rows.append(row)

    # scenario breakdown for selected only
    by_sc: dict[str, dict[str, Any]] = {}
    for i, sid in enumerate(test_ids):
        sc = bundle.targets[sid]["scenario_id"]
        if sc not in by_sc:
            by_sc[sc] = {
                "scenario_id": sc,
                "true_class": bundle.targets[sid]["target_label"],
                "correct": 0,
                "total": 0,
                "predicted_labels": Counter(),
                "misclassifications": [],
            }
        by_sc[sc]["total"] += 1
        by_sc[sc]["predicted_labels"][y_pred[i]] += 1
        if y_pred[i] == y_true[i]:
            by_sc[sc]["correct"] += 1
        else:
            by_sc[sc]["misclassifications"].append(
                {"sample_id": sid, "true": y_true[i], "pred": y_pred[i]}
            )
    test_scen = {
        sc: {
            **v,
            "predicted_labels": dict(v["predicted_labels"]),
            "accuracy": v["correct"] / v["total"] if v["total"] else 0.0,
        }
        for sc, v in by_sc.items()
    }

    test_errors = build_error_records(
        test_ids, y_true, y_pred, bundle.targets, bundle.behavioral, model_id=mid
    )

    write_json(out / "test_metrics_selected.json", metrics)
    write_jsonl(out / "test_predictions_selected.jsonl", pred_rows)
    write_json(out / "test_confusion_matrix_selected.json", metrics["confusion_matrix"])

    # update scenario breakdown / error analysis
    scen_path = out / "scenario_breakdown.json"
    scen = json.loads(scen_path.read_text(encoding="utf-8")) if scen_path.is_file() else {}
    scen["test"] = {"selected_model_id": mid, "scenarios": test_scen}
    write_json(scen_path, scen)

    err_path = out / "error_analysis.json"
    err = json.loads(err_path.read_text(encoding="utf-8")) if err_path.is_file() else {}
    err["test_errors_selected"] = test_errors
    write_json(err_path, err)

    metrics_sha = sha256_file(out / "test_metrics_selected.json")
    receipt = {
        "selected_model_id": mid,
        "selected_model_sha256": lock["selected_model_sha256"],
        "selection_lock_sha256": sha256_file(lock_path),
        "split_manifest_sha256": lock["split_manifest_sha256"],
        "test_sample_count": len(test_ids),
        "evaluated_at": utc_now(),
        "metrics_sha256": metrics_sha,
        "evaluation_version": EVALUATION_VERSION,
        "models_evaluated_on_test": 1,
    }
    # Receipt first — hashes lock state from selection stage (before any post-test edits).
    write_json(receipt_path, receipt)

    # Do NOT rewrite model_selection.json after lock (would break selection_manifest_sha256).
    lock["test_evaluated"] = True
    lock["test_receipt_path"] = str(receipt_path.relative_to(root))
    write_json(lock_path, lock)

    # evaluation manifest + report
    _write_final_manifests(root, cfg, bundle, integrity, selection, lock, metrics, receipt)

    quality = _quality_assessment(metrics)
    return {
        "ok": True,
        "metrics": metrics,
        "receipt": receipt,
        "scenario_breakdown": test_scen,
        "fit_calls": bundle.fit_calls,
        "quality_assessment": quality,
        "test_models_evaluated": 1,
    }


def _quality_assessment(metrics: dict[str, Any]) -> str:
    # descriptive only; small-n aware
    mf1 = metrics["macro_f1"]
    min_r = metrics["minimum_class_recall"]
    if mf1 >= 0.8 and min_r >= 0.6:
        return "PROMISING_IN_LAB"
    if mf1 >= 0.5:
        return "MIXED"
    return "WEAK"


def _write_final_manifests(
    root: Path,
    cfg: dict[str, Any],
    bundle: FrozenArtifactBundle,
    integrity: dict[str, Any],
    selection: dict[str, Any],
    lock: dict[str, Any],
    test_metrics: dict[str, Any],
    receipt: dict[str, Any],
) -> None:
    out = out_root(root, cfg)
    val_metrics = json.loads((out / "validation_metrics.json").read_text(encoding="utf-8"))
    model_hashes = {mid: bundle.models[mid]["sha256"] for mid in cfg["candidates"]}

    evaluation_manifest = {
        "evaluation_version": EVALUATION_VERSION,
        "created_at": utc_now(),
        "p8_training_version": bundle.training_manifest.get("training_version"),
        "p8_split_version": bundle.split.get("split_version"),
        "split_manifest_sha256": integrity["split_canonical_sha256"],
        "training_manifest_sha256": sha256_file(root / cfg["inputs"]["training_manifest"]),
        "tfidf_sha256": integrity["artifact_checks"]["tfidf_vectorizer"]["actual"],
        "scaler_sha256": integrity["artifact_checks"]["behavior_scaler"]["actual"],
        "p8_model_sha256": model_hashes,
        "selected_model_id": selection["selected_model_id"],
        "selected_model_sha256": selection["selected_artifact_sha256"],
        "validation_sample_count": len(bundle.sample_ids("validation")),
        "test_sample_count": len(bundle.sample_ids("test")),
        "validation_scenarios": scenario_for_class(bundle.split["validation"], bundle.targets),
        "test_scenarios": scenario_for_class(bundle.split["test"], bundle.targets),
        "selection_policy": cfg["selection"],
        "test_evaluated_once": True,
        "known_limitations": [
            "Validation/test each have only 15 samples (5 per class)",
            "Each class represented by one held-out scenario group",
            "Controlled lab scenario bias",
            "Single source environment / limited user diversity",
            "Results do not establish real-world production accuracy",
        ],
    }
    write_json(out / "evaluation_manifest.json", evaluation_manifest)

    report = {
        "evaluation_version": EVALUATION_VERSION,
        "validation": {
            "sample_count": evaluation_manifest["validation_sample_count"],
            "scenarios": evaluation_manifest["validation_scenarios"],
            "all_model_metrics": {
                mid: {
                    "accuracy": val_metrics[mid]["accuracy"],
                    "balanced_accuracy": val_metrics[mid]["balanced_accuracy"],
                    "macro_f1": val_metrics[mid]["macro_f1"],
                    "minimum_class_recall": val_metrics[mid]["minimum_class_recall"],
                }
                for mid in cfg["candidates"]
            },
        },
        "selection": {
            "selected_model": selection["selected_model_id"],
            "selection_reason": selection["selection_reason"],
            "selected_model_sha256": selection["selected_artifact_sha256"],
            "primary_metric": selection["primary_metric"],
            "primary_metric_value": selection["primary_metric_value"],
        },
        "test": {
            "selected_model_only": True,
            "sample_count": evaluation_manifest["test_sample_count"],
            "scenarios": evaluation_manifest["test_scenarios"],
            "metrics": test_metrics,
            "confusion_matrix": test_metrics["confusion_matrix"],
        },
        "limitations": {
            "small_dataset": True,
            "scenario_holdout": True,
            "lab_bias": True,
            "single_source": True,
            "limited_user_diversity": True,
            "one_error_accuracy_delta": round(1 / 15, 4),
            "one_class_error_recall_delta": 0.2,
        },
        "receipt": receipt,
        "fit_calls": bundle.fit_calls,
    }
    write_json(out / "evaluation_report.json", report)

    (out / "README.md").write_text(
        """# P9 Evaluation

Validation-based model selection + one-time locked TEST on the selected model only.

- No TF-IDF / scaler / classifier refit
- No TEST-based model selection
- See `docs/P9_MODEL_EVALUATION.md`
""",
        encoding="utf-8",
    )


def dry_run(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    bundle = FrozenArtifactBundle(root, cfg)
    integrity = bundle.verify_integrity()
    out = out_root(root, cfg)
    selected = None
    if (out / "model_selection.json").is_file():
        selected = json.loads((out / "model_selection.json").read_text())["selected_model_id"]
    test_eval = (out / "test_evaluation_receipt.json").is_file()
    return {
        "p8_artifact_integrity": "PASS" if integrity["ok"] else "FAIL",
        "split_sha256": integrity["split_canonical_sha256"],
        "validation_samples": len(bundle.sample_ids("validation")),
        "test_samples": len(bundle.sample_ids("test")),
        "candidate_models": cfg["candidates"],
        "selection_policy": cfg["selection"],
        "selected_model": selected or "NOT YET SELECTED",
        "test_evaluated": test_eval,
        "evaluation_version": EVALUATION_VERSION,
    }
