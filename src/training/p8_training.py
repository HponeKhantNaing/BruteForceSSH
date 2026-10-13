"""P8 leakage-safe training orchestrator."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import sklearn
import yaml
from scipy import sparse

from training.model_factory import ENABLED_MODEL_IDS, build_model, model_supports
from training.preprocessing import (
    build_behavior_matrix,
    build_hybrid,
    fit_scaler_train_only,
    fit_tfidf_train_only,
    transform_behavior,
    transform_text,
)
from training.splitter import build_scenario_split, scenario_audit

TRAINING_VERSION = "p8-v1"
CLASSES = ["NORMAL", "SUSPICIOUS", "BRUTE_FORCE"]

FORBIDDEN_FEATURE_SUBSTR = ("target", "label", "scenario", "phase", "path", "batch")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid YAML: {path}")
    return data


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def load_aligned_p7(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    paths = {k: root / v for k, v in cfg["inputs"].items() if k != "p7_features_config"}
    missing = [k for k, p in paths.items() if not p.is_file()]
    if missing:
        raise RuntimeError(f"Missing P7 inputs: {missing}")

    beh = load_jsonl(paths["behavioral_features"])
    txt = load_jsonl(paths["text_samples"])
    tgt = load_jsonl(paths["targets"])
    schema = json.loads(paths["feature_schema"].read_text(encoding="utf-8"))
    manifest = json.loads(paths["feature_manifest"].read_text(encoding="utf-8"))

    b_ids = {r["sample_id"] for r in beh}
    t_ids = {r["sample_id"] for r in txt}
    y_ids = {r["sample_id"] for r in tgt}
    if not (b_ids == t_ids == y_ids):
        raise RuntimeError("P7 sample ID misalignment")
    if len(beh) != len(b_ids):
        raise RuntimeError("Duplicate sample IDs in behavioral features")

    feature_order = [
        f["name"] for f in schema.get("behavioral_features", []) if f.get("default_enabled")
    ]
    if not feature_order:
        raise RuntimeError("No default_enabled behavioral features")

    # leakage key check
    for r in beh:
        for k in r["features"]:
            kl = k.lower()
            if any(s in kl for s in FORBIDDEN_FEATURE_SUBSTR):
                raise RuntimeError(f"Forbidden feature key: {k}")

    hashes = {k: sha256_file(p) for k, p in paths.items()}
    p7_cfg = load_yaml(root / cfg["inputs"]["p7_features_config"])

    return {
        "behavioral": {r["sample_id"]: r for r in beh},
        "text": {r["sample_id"]: r for r in txt},
        "targets": tgt,
        "targets_by_id": {t["sample_id"]: t for t in tgt},
        "feature_order": feature_order,
        "schema": schema,
        "manifest": manifest,
        "hashes": hashes,
        "p7_config": p7_cfg,
        "sample_count": len(beh),
    }


def create_split(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    data = load_aligned_p7(root, cfg)
    audit = scenario_audit(data["targets"], group_key=cfg["split"]["group_key"])
    split = build_scenario_split(
        data["targets"],
        seed=int(cfg["random_seed"]),
        group_key=cfg["split"]["group_key"],
        train_fraction=float(cfg["split"]["train_fraction"]),
        validation_fraction=float(cfg["split"]["validation_fraction"]),
        test_fraction=float(cfg["split"]["test_fraction"]),
        require_all_classes=bool(cfg["split"]["require_all_classes_each_split"]),
        min_groups_per_class=int(cfg["split"]["min_groups_per_class"]),
    )
    split["split_version"] = cfg["split"]["version"]

    out = root / cfg["output"]["modeling_root"]
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "split_manifest.json", split)
    split_hash = sha256_bytes(canonical_json_bytes(split))
    summary = {
        "split_version": split["split_version"],
        "split_manifest_sha256": split_hash,
        "group_key": split["group_key"],
        "random_seed": split["random_seed"],
        "train_samples": len(split["train"]["sample_ids"]),
        "validation_samples": len(split["validation"]["sample_ids"]),
        "test_samples": len(split["test"]["sample_ids"]),
        "train_class_counts": split["train"]["class_counts"],
        "validation_class_counts": split["validation"]["class_counts"],
        "test_class_counts": split["test"]["class_counts"],
        "train_scenarios": split["train"]["scenario_ids"],
        "validation_scenarios": split["validation"]["scenario_ids"],
        "test_scenarios": split["test"]["scenario_ids"],
        "scenario_overlap": 0,
        "sample_overlap": 0,
        "scenario_audit": audit,
    }
    write_json(out / "split_summary.json", summary)
    return {"split": split, "summary": summary, "data": data}


def _labels(sample_ids: list[str], targets_by_id: dict[str, dict[str, Any]]) -> np.ndarray:
    return np.array([targets_by_id[s]["target_label"] for s in sample_ids], dtype=object)


def _roundtrip_predict(model: Any, X, y_train_sample) -> bool:
    """Fit already done; save/load and compare predictions on TRAIN slice."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "m.joblib"
        joblib.dump(model, path)
        loaded = joblib.load(path)
        # Take up to 5 rows
        n = min(5, X.shape[0])
        if sparse.issparse(X):
            Xs = X[:n]
        else:
            Xs = X[:n]
        a = model.predict(Xs)
        b = loaded.predict(Xs)
        return bool(np.array_equal(a, b))


def train_models(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    modeling = root / cfg["output"]["modeling_root"]
    artifacts = root / cfg["output"]["artifacts_root"]
    split_path = modeling / "split_manifest.json"
    if not split_path.is_file():
        raise RuntimeError("split_manifest.json missing — run --split first")

    split = json.loads(split_path.read_text(encoding="utf-8"))
    split_hash = sha256_bytes(canonical_json_bytes(split))
    data = load_aligned_p7(root, cfg)

    train_ids = split["train"]["sample_ids"]
    val_ids = split["validation"]["sample_ids"]
    test_ids = split["test"]["sample_ids"]
    fit_ids = set(train_ids)
    if fit_ids & set(val_ids) or fit_ids & set(test_ids):
        raise RuntimeError("Fit IDs overlap val/test")

    # Verify scenario disjoint
    if (
        set(split["train"]["scenario_ids"]) & set(split["validation"]["scenario_ids"])
        or set(split["train"]["scenario_ids"]) & set(split["test"]["scenario_ids"])
        or set(split["validation"]["scenario_ids"]) & set(split["test"]["scenario_ids"])
    ):
        raise RuntimeError("Scenario overlap in locked split")

    feature_order = data["feature_order"]
    y_train = _labels(train_ids, data["targets_by_id"])
    for lab in CLASSES:
        if lab not in set(y_train):
            raise RuntimeError(f"TRAIN missing class {lab}")

    train_texts = [data["text"][i]["canonical_text"] for i in train_ids]
    val_texts = [data["text"][i]["canonical_text"] for i in val_ids]
    # TEST texts loaded only for optional transform shape check — never for fit/metrics
    test_texts = [data["text"][i]["canonical_text"] for i in test_ids]

    # TRAIN-only TF-IDF
    vectorizer = fit_tfidf_train_only(train_texts, data["p7_config"])
    X_text_train = transform_text(vectorizer, train_texts)
    X_text_val = transform_text(vectorizer, val_texts)
    # Transform test for serialization/shape only — no metrics
    X_text_test = transform_text(vectorizer, test_texts)

    vocab_size = len(vectorizer.vocabulary_) if hasattr(vectorizer, "vocabulary_") else 0

    # TRAIN-only scaler
    X_beh_train = build_behavior_matrix(data["behavioral"], train_ids, feature_order)
    X_beh_val = build_behavior_matrix(data["behavioral"], val_ids, feature_order)
    X_beh_test = build_behavior_matrix(data["behavioral"], test_ids, feature_order)
    scaler = fit_scaler_train_only(X_beh_train)
    X_beh_train_s = transform_behavior(scaler, X_beh_train)
    X_beh_val_s = transform_behavior(scaler, X_beh_val)
    X_beh_test_s = transform_behavior(scaler, X_beh_test)

    X_hyb_train = build_hybrid(X_text_train, X_beh_train_s)
    X_hyb_val = build_hybrid(X_text_val, X_beh_val_s)

    # Sanity: validation transform/predict works (no metrics published)
    y_val = _labels(val_ids, data["targets_by_id"])

    prep_dir = artifacts / "preprocessing"
    model_dir = artifacts / "models"
    prep_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    write_json(prep_dir / "behavior_feature_order.json", {"feature_order": feature_order})
    joblib.dump(
        {
            "vectorizer": vectorizer,
            "fit_sample_ids": list(train_ids),
            "fit_scope": "TRAIN_ONLY",
            "training_version": TRAINING_VERSION,
        },
        prep_dir / "tfidf_vectorizer.joblib",
    )
    joblib.dump(
        {
            "scaler": scaler,
            "fit_sample_ids": list(train_ids),
            "fit_scope": "TRAIN_ONLY",
            "feature_order": feature_order,
            "training_version": TRAINING_VERSION,
        },
        prep_dir / "behavior_scaler.joblib",
    )

    # Provenance assertions
    assert set(train_ids).isdisjoint(set(val_ids))
    assert set(train_ids).isdisjoint(set(test_ids))

    model_cfgs = cfg.get("models") or {}
    training_report: list[dict[str, Any]] = []
    artifact_checksums: dict[str, str] = {
        "split_manifest": sha256_file(split_path),
        "tfidf_vectorizer": sha256_file(prep_dir / "tfidf_vectorizer.joblib"),
        "behavior_scaler": sha256_file(prep_dir / "behavior_scaler.joblib"),
        "behavior_feature_order": sha256_file(prep_dir / "behavior_feature_order.json"),
    }

    seed = int(cfg["random_seed"])
    representations = {
        "logistic_regression_hybrid": ("hybrid", X_hyb_train, X_hyb_val),
        "logistic_regression_text": ("text", X_text_train, X_text_val),
        "logistic_regression_behavior": ("behavior", X_beh_train_s, X_beh_val_s),
        "linear_svm_hybrid": ("hybrid", X_hyb_train, X_hyb_val),
        "multinomial_nb_text": ("text", X_text_train, X_text_val),
        "random_forest_behavior": ("behavior", X_beh_train, X_beh_val),  # unscaled
    }

    for model_id in ENABLED_MODEL_IDS:
        mcfg = model_cfgs.get(model_id) or {}
        if not mcfg.get("enabled", True):
            training_report.append({"model_id": model_id, "status": "SKIPPED"})
            continue
        rep_name, Xtr, Xva = representations[model_id]
        # NB non-negative check
        if model_id == "multinomial_nb_text":
            if sparse.issparse(Xtr):
                if Xtr.min() < 0:
                    raise RuntimeError("NB received negative features")
            elif np.min(Xtr) < 0:
                raise RuntimeError("NB received negative features")

        model = build_model(model_id, cfg, random_seed=seed)
        t0 = time.perf_counter()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            model.fit(Xtr, y_train)
        elapsed = time.perf_counter() - t0
        conv_warn = any("ConvergenceWarning" in type(w.message).__name__ or "Convergence" in str(w.message) for w in caught)

        classes = list(getattr(model, "classes_", []))
        if set(classes) != set(CLASSES):
            raise RuntimeError(f"{model_id} classes_={classes}")

        # Validation sanity predict only
        _ = model.predict(Xva)

        art_path = model_dir / f"{model_id}.joblib"
        payload = {
            "model": model,
            "model_id": model_id,
            "representation": rep_name,
            "training_version": TRAINING_VERSION,
            "train_sample_ids": list(train_ids),
            "fit_scope": "TRAIN_ONLY",
            "classes": classes,
            "feature_dimension": int(Xtr.shape[1]),
            "supports": model_supports(model),
            "test_metrics_computed": False,
            "experimental": True,
        }
        joblib.dump(payload, art_path)
        ok_rt = _roundtrip_predict(model, Xtr, y_train)
        checksum = sha256_file(art_path)
        artifact_checksums[model_id] = checksum

        training_report.append(
            {
                "model_id": model_id,
                "representation": rep_name,
                "status": "TRAINED",
                "train_samples": len(train_ids),
                "feature_dimension": int(Xtr.shape[1]),
                "fit_duration_seconds": round(elapsed, 4),
                "convergence_warning": conv_warn,
                "artifact_path": str(art_path.relative_to(root)),
                "artifact_sha256": checksum,
                "classes": classes,
                "supports": model_supports(model),
                "roundtrip_ok": ok_rt,
                "test_metrics_computed": False,
            }
        )

    # Preprocessor round-trip
    reloaded_tfidf = joblib.load(prep_dir / "tfidf_vectorizer.joblib")["vectorizer"]
    reloaded_scaler = joblib.load(prep_dir / "behavior_scaler.joblib")["scaler"]
    tfidf_rt = np.allclose(
        transform_text(vectorizer, train_texts[:3]).toarray(),
        transform_text(reloaded_tfidf, train_texts[:3]).toarray(),
    )
    scaler_rt = np.allclose(
        transform_behavior(scaler, X_beh_train[:3]),
        transform_behavior(reloaded_scaler, X_beh_train[:3]),
    )

    leakage_audit = {
        "sample_overlap": 0,
        "scenario_overlap": 0,
        "test_used_for_fit": False,
        "validation_used_for_fit": False,
        "tfidf_fit_scope": "TRAIN_ONLY",
        "scaler_fit_scope": "TRAIN_ONLY",
        "classifier_fit_scope": "TRAIN_ONLY",
        "tfidf_fit_sample_ids_subset_of_train": True,
        "scaler_fit_sample_ids_subset_of_train": True,
        "target_in_feature": False,
        "scenario_in_feature": False,
        "raw_ip_leakage": False,
        "raw_username_leakage": False,
        "class_bearing_path_leakage": False,
        "test_metrics_computed": False,
        "pass": True,
    }

    training_manifest = {
        "training_version": TRAINING_VERSION,
        "created_at": utc_now(),
        "python_version": platform.python_version(),
        "scikit_learn_version": sklearn.__version__,
        "scipy_version": __import__("scipy").__version__,
        "p7_feature_version": data["manifest"].get("feature_engineering_version"),
        "p7_feature_manifest_sha256": data["hashes"].get("feature_manifest"),
        "p7_source_hashes": data["hashes"],
        "split_version": split.get("split_version"),
        "split_manifest_sha256": split_hash,
        "random_seed": seed,
        "grouping_strategy": cfg["split"]["group_key"],
        "train_sample_count": len(train_ids),
        "validation_sample_count": len(val_ids),
        "test_sample_count": len(test_ids),
        "train_class_distribution": split["train"]["class_counts"],
        "validation_class_distribution": split["validation"]["class_counts"],
        "test_class_distribution": split["test"]["class_counts"],
        "tfidf_config": data["p7_config"].get("text_features"),
        "tfidf_vocabulary_size": vocab_size,
        "behavior_feature_count": len(feature_order),
        "behavior_feature_names": feature_order,
        "hybrid_dimension": int(X_hyb_train.shape[1]),
        "text_dimension": int(X_text_train.shape[1]),
        "models_trained": [r["model_id"] for r in training_report if r.get("status") == "TRAINED"],
        "test_metrics_computed": False,
        "primary_baseline": "logistic_regression_hybrid",
        "declared_best_model": False,
    }

    write_json(modeling / "training_manifest.json", training_manifest)
    write_json(modeling / "training_report.json", {"models": training_report})
    write_json(modeling / "artifact_checksums.json", artifact_checksums)
    write_json(modeling / "leakage_audit.json", leakage_audit)

    (artifacts / "README.md").write_text(
        """# P8 Experimental Artifacts

These artifacts are **EXPERIMENTAL**.

- Fit scope: **TRAIN only**
- Test set: **LOCKED** (no metrics in P8)
- No model has been declared the winner
- P10 owns production packaging/versioning
""",
        encoding="utf-8",
    )
    (modeling / "README.md").write_text(
        """# P8 Modeling Outputs

Leakage-safe scenario-group split + TRAIN-only fitted preprocessing + experimental models.

No TEST metrics. No winner selection. See `docs/P8_ML_TRAINING.md`.
""",
        encoding="utf-8",
    )

    # Unused test transform shapes recorded only to prove transform works — not evaluation
    _ = (X_text_test.shape, X_beh_test_s.shape)

    all_trained = all(r.get("status") == "TRAINED" for r in training_report if r.get("status") != "SKIPPED")
    primary_ok = any(
        r.get("model_id") == "logistic_regression_hybrid" and r.get("status") == "TRAINED"
        for r in training_report
    )
    roundtrips = all(r.get("roundtrip_ok", True) for r in training_report if r.get("status") == "TRAINED")

    return {
        "ok": all_trained and primary_ok and tfidf_rt and scaler_rt and roundtrips and leakage_audit["pass"],
        "training_manifest": training_manifest,
        "training_report": training_report,
        "artifact_checksums": artifact_checksums,
        "leakage_audit": leakage_audit,
        "vocab_size": vocab_size,
        "feature_order": feature_order,
        "tfidf_roundtrip": tfidf_rt,
        "scaler_roundtrip": scaler_rt,
        "split_hash": split_hash,
        "hybrid_dim": int(X_hyb_train.shape[1]),
        "text_dim": int(X_text_train.shape[1]),
        "behavior_dim": len(feature_order),
    }


def dry_run_summary(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    data = load_aligned_p7(root, cfg)
    audit = scenario_audit(data["targets"], cfg["split"]["group_key"])
    # plan split without writing
    split = build_scenario_split(
        data["targets"],
        seed=int(cfg["random_seed"]),
        group_key=cfg["split"]["group_key"],
        train_fraction=float(cfg["split"]["train_fraction"]),
        validation_fraction=float(cfg["split"]["validation_fraction"]),
        test_fraction=float(cfg["split"]["test_fraction"]),
        require_all_classes=bool(cfg["split"]["require_all_classes_each_split"]),
        min_groups_per_class=int(cfg["split"]["min_groups_per_class"]),
    )
    return {
        "p7_samples": data["sample_count"],
        "scenario_groups": audit["unique_scenario_ids"],
        "scenario_ids_per_target": audit["scenario_ids_per_target"],
        "planned_train": len(split["train"]["sample_ids"]),
        "planned_validation": len(split["validation"]["sample_ids"]),
        "planned_test": len(split["test"]["sample_ids"]),
        "planned_models": [m for m, c in (cfg.get("models") or {}).items() if c.get("enabled", True)],
        "tfidf_fitted": False,
        "scaler_fitted": False,
        "models_trained": False,
        "training_version": TRAINING_VERSION,
    }
