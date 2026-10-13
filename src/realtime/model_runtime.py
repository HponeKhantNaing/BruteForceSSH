"""Load and run frozen P10 RF behavior bundle (no fit / no scaler / no TF-IDF)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from export.bundle_validator import BundleValidator, load_estimator, sha256_file
from export.schema_validator import SchemaValidationError, validate_feature_dict


class ModelRuntime:
    def __init__(self, release_root: Path, *, expected_sha256: str | None = None):
        self.release_root = release_root
        self.expected_sha256 = expected_sha256
        self.fit_calls = 0
        self.tfidf_used = False
        self.scaler_used = False
        self.model = None
        self.payload: dict[str, Any] = {}
        self.manifest: dict[str, Any] = {}
        self.contract: dict[str, Any] = {}
        self.ordered_features: list[str] = []
        self.class_labels: list[str] = []
        self.model_class_order: list[str] = []
        self.release_id = ""
        self.model_sha256 = ""

    def _block_fit(self, obj: Any, name: str) -> None:
        if not hasattr(obj, "fit"):
            return
        original = obj.fit

        def blocked(*_a, **_k):
            self.fit_calls += 1
            raise RuntimeError(f"P11 forbid fit() on {name}")

        obj.fit = blocked  # type: ignore[method-assign]
        obj._p11_original_fit = original
        if hasattr(obj, "partial_fit"):
            def blocked_partial(*_a, **_k):
                self.fit_calls += 1
                raise RuntimeError(f"P11 forbid partial_fit() on {name}")

            obj.partial_fit = blocked_partial  # type: ignore[method-assign]

    def verify_and_load(self) -> dict[str, Any]:
        if not self.release_root.is_dir():
            return {"ok": False, "error": f"release missing: {self.release_root}"}

        validator = BundleValidator(
            self.release_root,
            expected_source_sha256=self.expected_sha256,
        )
        verification = validator.validate()
        if not verification.get("ok"):
            return {
                "ok": False,
                "error": "P10 bundle verification failed",
                "verification": verification,
            }

        self.manifest = json.loads((self.release_root / "MANIFEST.json").read_text(encoding="utf-8"))
        self.contract = json.loads(
            (self.release_root / "schema/feature_contract.json").read_text(encoding="utf-8")
        )
        self.ordered_features = list(self.contract["ordered_features"])
        self.class_labels = list(self.manifest["class_labels"])
        self.model_class_order = list(self.manifest["model_class_order"])
        self.release_id = self.manifest["release_id"]

        model_path = self.release_root / "model" / "random_forest_behavior.joblib"
        self.model_sha256 = sha256_file(model_path)
        if self.expected_sha256 and self.model_sha256 != self.expected_sha256:
            return {"ok": False, "error": "model SHA mismatch vs expected"}

        # Refuse scaler/tfidf deps
        if self.contract.get("scaling_required") or self.manifest.get("scaler_required"):
            return {"ok": False, "error": "scaler required by contract — unexpected for RF"}
        if self.contract.get("tfidf_required") or self.manifest.get("tfidf_required"):
            return {"ok": False, "error": "tfidf required by contract — unexpected for RF"}

        self.model, self.payload = load_estimator(model_path)
        self._block_fit(self.model, "random_forest_behavior")
        classes = [str(c) for c in self.model.classes_]
        if classes != self.model_class_order:
            return {"ok": False, "error": f"classes_ mismatch {classes}"}
        if set(classes) != set(self.class_labels):
            return {"ok": False, "error": "class set mismatch"}

        return {
            "ok": True,
            "release_id": self.release_id,
            "model_sha256": self.model_sha256,
            "feature_count": len(self.ordered_features),
            "model_class_order": self.model_class_order,
            "representation": self.contract.get("representation"),
            "verification": verification,
        }

    def predict_features(self, features: dict[str, float]) -> dict[str, Any]:
        if self.model is None:
            raise RuntimeError("model not loaded")
        t0 = time.perf_counter()
        try:
            vector = validate_feature_dict(features, self.ordered_features)
        except SchemaValidationError as exc:
            return {
                "ok": False,
                "error": "feature_validation_failed",
                "detail": str(exc),
                "latency_ms": (time.perf_counter() - t0) * 1000.0,
            }

        x = np.asarray([vector], dtype=float)
        pred = self.model.predict(x)[0]
        probs = self.model.predict_proba(x)[0]
        by_model_order = {str(cls): float(probs[i]) for i, cls in enumerate(self.model.classes_)}
        class_probabilities = {label: by_model_order.get(label, 0.0) for label in self.class_labels}
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "ok": True,
            "release_id": self.release_id,
            "predicted_label": str(pred),
            "class_probabilities": class_probabilities,
            "probability_type": "uncalibrated",
            "model_class_order": list(self.model.classes_),
            "latency_ms": latency_ms,
            "tfidf_used": self.tfidf_used,
            "scaler_used": self.scaler_used,
            "fit_calls": self.fit_calls,
        }
