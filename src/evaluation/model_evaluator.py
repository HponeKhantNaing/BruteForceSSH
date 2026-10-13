"""Load frozen P8 artifacts and build evaluation representations (no fit)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from scipy import sparse

from training.preprocessing import build_behavior_matrix, build_hybrid, transform_behavior, transform_text

# Representation map matching P8 training
MODEL_REPRESENTATION = {
    "logistic_regression_hybrid": "hybrid",
    "logistic_regression_text": "text",
    "logistic_regression_behavior": "behavior_scaled",
    "linear_svm_hybrid": "hybrid",
    "multinomial_nb_text": "text",
    "random_forest_behavior": "behavior_raw",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json_sha256(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


class FitCallError(RuntimeError):
    pass


class FrozenArtifactBundle:
    """Frozen P8 preprocessors + models. Any .fit() raises."""

    def __init__(self, root: Path, cfg: dict[str, Any]):
        self.root = root
        self.cfg = cfg
        self.fit_calls = 0
        self._load()

    def _load(self) -> None:
        inputs = self.cfg["inputs"]
        self.split = json.loads((self.root / inputs["split_manifest"]).read_text(encoding="utf-8"))
        self.training_manifest = json.loads((self.root / inputs["training_manifest"]).read_text(encoding="utf-8"))
        self.checksums = json.loads((self.root / inputs["artifact_checksums"]).read_text(encoding="utf-8"))

        tf_payload = joblib.load(self.root / inputs["tfidf"])
        sc_payload = joblib.load(self.root / inputs["scaler"])
        self.vectorizer = tf_payload["vectorizer"]
        self.scaler = sc_payload["scaler"]
        self.feature_order = json.loads((self.root / inputs["feature_order"]).read_text(encoding="utf-8"))[
            "feature_order"
        ]

        # Patch fit to detect accidental refits
        self._patch_no_fit(self.vectorizer, "TfidfVectorizer")
        self._patch_no_fit(self.scaler, "StandardScaler")

        self.models: dict[str, Any] = {}
        models_dir = self.root / inputs["models_dir"]
        for mid in self.cfg["candidates"]:
            payload = joblib.load(models_dir / f"{mid}.joblib")
            model = payload["model"]
            self._patch_no_fit(model, mid)
            self.models[mid] = {
                "payload": payload,
                "model": model,
                "representation": MODEL_REPRESENTATION[mid],
                "path": str((models_dir / f"{mid}.joblib").relative_to(self.root)),
                "sha256": sha256_file(models_dir / f"{mid}.joblib"),
            }

        beh = load_jsonl(self.root / inputs["behavioral_features"])
        txt = load_jsonl(self.root / inputs["text_samples"])
        tgt = load_jsonl(self.root / inputs["targets"])
        self.behavioral = {r["sample_id"]: r for r in beh}
        self.text = {r["sample_id"]: r for r in txt}
        self.targets = {t["sample_id"]: t for t in tgt}

    def _patch_no_fit(self, obj: Any, name: str) -> None:
        if not hasattr(obj, "fit"):
            return
        original = obj.fit

        def blocked(*args, **kwargs):
            self.fit_calls += 1
            raise FitCallError(f"P9 forbid fit() on {name}")

        obj.fit = blocked  # type: ignore[method-assign]
        obj._p9_original_fit = original  # keep reference unused

    def verify_integrity(self) -> dict[str, Any]:
        inputs = self.cfg["inputs"]
        expected_canon = self.cfg.get("expected_split_sha256_canonical")
        actual_canon = canonical_json_sha256(self.split)
        file_checks = {}
        mapping = {
            "split_manifest": inputs["split_manifest"],
            "tfidf_vectorizer": inputs["tfidf"],
            "behavior_scaler": inputs["scaler"],
            "behavior_feature_order": inputs["feature_order"],
        }
        for mid in self.cfg["candidates"]:
            mapping[mid] = f"{inputs['models_dir']}/{mid}.joblib"

        ok = True
        for key, rel in mapping.items():
            path = self.root / rel
            actual = sha256_file(path)
            expected = self.checksums.get(key)
            match = actual == expected
            file_checks[key] = {"expected": expected, "actual": actual, "match": match}
            if not match:
                ok = False

        # P7 source hashes from training manifest
        p7_ok = True
        p7_checks = {}
        src_map = {
            "behavioral_features": inputs["behavioral_features"],
            "text_samples": inputs["text_samples"],
            "targets": inputs["targets"],
            "feature_manifest": "data/features/p7/feature_manifest.json",
            "feature_schema": "data/features/p7/feature_schema.json",
        }
        for k, rel in src_map.items():
            expected = self.training_manifest.get("p7_source_hashes", {}).get(k)
            if expected is None:
                continue
            actual = sha256_file(self.root / rel)
            match = actual == expected
            p7_checks[k] = {"match": match, "actual": actual, "expected": expected}
            if not match:
                p7_ok = False
                ok = False

        split_ok = actual_canon == expected_canon
        if not split_ok:
            ok = False

        # scenario overlap
        tr, va, te = (
            set(self.split["train"]["scenario_ids"]),
            set(self.split["validation"]["scenario_ids"]),
            set(self.split["test"]["scenario_ids"]),
        )
        overlap = len(tr & va) + len(tr & te) + len(va & te)

        return {
            "ok": ok and p7_ok and overlap == 0,
            "split_canonical_sha256": actual_canon,
            "split_canonical_match": split_ok,
            "artifact_checks": file_checks,
            "p7_checks": p7_checks,
            "scenario_overlap": overlap,
            "p8_test_metrics_computed": self.training_manifest.get("test_metrics_computed"),
            "fit_calls": self.fit_calls,
        }

    def sample_ids(self, partition: str) -> list[str]:
        return list(self.split[partition]["sample_ids"])

    def labels(self, sample_ids: list[str]) -> list[str]:
        return [self.targets[s]["target_label"] for s in sample_ids]

    def build_matrices(self, sample_ids: list[str]) -> dict[str, Any]:
        texts = [self.text[s]["canonical_text"] for s in sample_ids]
        X_text = transform_text(self.vectorizer, texts)
        X_raw = build_behavior_matrix(self.behavioral, sample_ids, self.feature_order)
        X_scaled = transform_behavior(self.scaler, X_raw)
        X_hybrid = build_hybrid(X_text, X_scaled)
        return {
            "text": X_text,
            "behavior_raw": X_raw,
            "behavior_scaled": X_scaled,
            "hybrid": X_hybrid,
        }

    def matrix_for_model(self, model_id: str, matrices: dict[str, Any]):
        rep = MODEL_REPRESENTATION[model_id]
        return matrices[rep]

    def predict(self, model_id: str, X) -> np.ndarray:
        model = self.models[model_id]["model"]
        return model.predict(X)

    def predict_details(self, model_id: str, X) -> dict[str, Any]:
        model = self.models[model_id]["model"]
        pred = model.predict(X)
        out: dict[str, Any] = {"predicted_label": pred}
        if hasattr(model, "predict_proba"):
            out["uncalibrated_probabilities"] = model.predict_proba(X)
            out["probability_classes"] = list(model.classes_)
        if hasattr(model, "decision_function"):
            out["decision_scores"] = model.decision_function(X)
        return out
