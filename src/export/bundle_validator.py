"""Validate a packaged P10 release bundle (no retraining)."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from .schema_validator import SchemaValidationError, validate_feature_dict, validate_prediction_output

REQUIRED_FILES = [
    "README.md",
    "RELEASE.json",
    "MANIFEST.json",
    "CHECKSUMS.sha256",
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

SECRET_PATTERNS = [
    re.compile(r"DISCORD_WEBHOOK", re.I),
    re.compile(r"api[_-]?key", re.I),
    re.compile(r"password\s*[:=]", re.I),
    re.compile(r"private[_-]?token", re.I),
    re.compile(r"BEGIN (RSA |OPENSSH )?PRIVATE KEY"),
]

RAW_LOG_NAME = re.compile(r"auth\.log$", re.I)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_checksums(path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        digest, rel = parts[0], parts[-1]
        mapping[rel.lstrip("*")] = digest
    return mapping


def load_estimator(model_path: Path) -> tuple[Any, dict[str, Any]]:
    payload = joblib.load(model_path)
    if not isinstance(payload, dict) or "model" not in payload:
        raise RuntimeError("release model payload must be a dict with key 'model'")
    return payload["model"], payload


def predict_from_features(
    model: Any,
    features: dict[str, Any],
    ordered_features: list[str],
    *,
    model_version: str,
    class_order: list[str],
) -> dict[str, Any]:
    vector = validate_feature_dict(features, ordered_features)
    x = np.asarray([vector], dtype=float)
    pred = model.predict(x)[0]
    probs = model.predict_proba(x)[0]
    class_probabilities = {
        str(cls): float(probs[i]) for i, cls in enumerate(model.classes_)
    }
    # Ensure documented class order keys present
    for cls in class_order:
        class_probabilities.setdefault(cls, 0.0)
    out = {
        "model_version": model_version,
        "predicted_label": str(pred),
        "class_probabilities": {k: class_probabilities[k] for k in class_order},
        "probability_type": "uncalibrated",
        "model_class_order": [str(c) for c in model.classes_],
        "probability_vector_in_model_class_order": [float(p) for p in probs],
    }
    validate_prediction_output(
        out,
        expected_labels=set(class_order),
        model_version=model_version,
    )
    return out


class BundleValidator:
    def __init__(self, release_root: Path, *, expected_source_sha256: str | None = None):
        self.release_root = release_root
        self.expected_source_sha256 = expected_source_sha256
        self.fit_calls = 0

    def _patch_no_fit(self, obj: Any, name: str) -> None:
        if not hasattr(obj, "fit"):
            return
        original = obj.fit

        def blocked(*_a, **_k):
            self.fit_calls += 1
            raise RuntimeError(f"P10 forbid fit() on {name}")

        obj.fit = blocked  # type: ignore[method-assign]
        obj._p10_original_fit = original

    def validate(self) -> dict[str, Any]:
        root = self.release_root
        results: dict[str, Any] = {"ok": True, "checks": {}, "errors": []}

        def fail(key: str, msg: str) -> None:
            results["ok"] = False
            results["checks"][key] = "FAIL"
            results["errors"].append(f"{key}: {msg}")

        def pass_(key: str) -> None:
            results["checks"][key] = "PASS"

        # Required files
        missing = [rel for rel in REQUIRED_FILES if not (root / rel).is_file()]
        if missing:
            fail("required_files", f"missing: {missing}")
        else:
            pass_("required_files")

        if not (root / "MANIFEST.json").is_file():
            return results

        manifest = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))
        contract = json.loads((root / "schema/feature_contract.json").read_text(encoding="utf-8"))
        ordered = list(contract["ordered_features"])
        model_path = root / "model" / "random_forest_behavior.joblib"
        model_sha = sha256_file(model_path)
        results["model_sha256"] = model_sha

        if model_sha != manifest.get("model_sha256"):
            fail("manifest_model_sha", "MANIFEST model_sha256 mismatch")
        else:
            pass_("manifest_model_sha")

        if self.expected_source_sha256 and model_sha != self.expected_source_sha256:
            fail("byte_identity", "release model SHA != source SHA")
        else:
            pass_("byte_identity")

        # Checksums (exclude CHECKSUMS.sha256 itself)
        checksums = parse_checksums(root / "CHECKSUMS.sha256")
        checksum_ok = True
        for rel, expected in checksums.items():
            path = root / rel
            if not path.is_file():
                checksum_ok = False
                results["errors"].append(f"checksum missing file: {rel}")
                continue
            actual = sha256_file(path)
            if actual != expected:
                checksum_ok = False
                results["errors"].append(f"checksum mismatch: {rel}")
        if checksum_ok:
            pass_("checksums")
        else:
            fail("checksums", "one or more checksum mismatches")

        # Representation / deps
        if contract.get("scaling_required") is not False or manifest.get("scaler_required") is not False:
            fail("scaler_required", "RF behavior release must not require scaler")
        else:
            pass_("scaler_required")
        if contract.get("text_required") is not False or manifest.get("tfidf_required") is not False:
            fail("tfidf_required", "RF behavior release must not require TF-IDF")
        else:
            pass_("tfidf_required")

        # No TF-IDF/scaler binaries packaged as runtime deps
        banned = list(root.rglob("*tfidf*")) + list(root.rglob("*scaler*"))
        if banned:
            fail("no_preprocessor_binaries", f"found: {[str(p.relative_to(root)) for p in banned]}")
        else:
            pass_("no_preprocessor_binaries")

        # Load model
        try:
            model, payload = load_estimator(model_path)
            self._patch_no_fit(model, "release_model")
            pass_("model_load")
        except Exception as exc:  # noqa: BLE001
            fail("model_load", str(exc))
            return results

        classes = [str(c) for c in model.classes_]
        expected_set = set(manifest.get("class_labels") or ["NORMAL", "SUSPICIOUS", "BRUTE_FORCE"])
        if set(classes) != expected_set:
            fail("class_set", f"classes_={classes}")
        else:
            pass_("class_set")
        if classes != list(manifest.get("model_class_order") or []):
            fail("class_order", "manifest model_class_order != model.classes_")
        else:
            pass_("class_order")

        n_in = int(getattr(model, "n_features_in_", -1))
        if n_in != len(ordered) or len(ordered) != int(contract.get("feature_count", -1)):
            fail("feature_count", f"n_features_in_={n_in}, ordered={len(ordered)}")
        else:
            pass_("feature_count")

        # Smoke inference
        smoke_in = json.loads((root / "verification/smoke_test_input.json").read_text(encoding="utf-8"))
        smoke_exp = json.loads((root / "verification/smoke_test_expected.json").read_text(encoding="utf-8"))
        try:
            pred1 = predict_from_features(
                model,
                smoke_in["features"],
                ordered,
                model_version=manifest["release_id"],
                class_order=list(manifest["class_labels"]),
            )
            pred2 = predict_from_features(
                model,
                smoke_in["features"],
                ordered,
                model_version=manifest["release_id"],
                class_order=list(manifest["class_labels"]),
            )
            if pred1["predicted_label"] != pred2["predicted_label"]:
                fail("smoke_determinism", "label mismatch across two loads")
            elif not np.allclose(
                pred1["probability_vector_in_model_class_order"],
                pred2["probability_vector_in_model_class_order"],
            ):
                fail("smoke_determinism", "proba mismatch across two loads")
            else:
                pass_("smoke_determinism")

            if pred1["predicted_label"] != smoke_exp.get("predicted_label"):
                fail("smoke_expected_label", "predicted label != smoke expected")
            else:
                pass_("smoke_expected_label")
            pass_("smoke_prediction")
            results["smoke_prediction"] = pred1
        except Exception as exc:  # noqa: BLE001
            fail("smoke_prediction", str(exc))

        # Negative validation cases
        feats = dict(smoke_in["features"])
        try:
            bad = dict(feats)
            del bad["failed_attempts"]
            validate_feature_dict(bad, ordered)
            fail("missing_feature", "missing feature was accepted")
        except SchemaValidationError:
            pass_("missing_feature")

        try:
            bad = dict(feats)
            bad["failure_ratio"] = float("nan")
            validate_feature_dict(bad, ordered)
            fail("non_finite", "NaN accepted")
        except SchemaValidationError:
            pass_("non_finite")

        try:
            bad = dict(feats)
            bad["failure_ratio"] = 1.5
            validate_feature_dict(bad, ordered)
            fail("invalid_range", "out-of-range accepted")
        except SchemaValidationError:
            pass_("invalid_range")

        try:
            bad = dict(feats)
            bad["failed_attempts"] = 10
            bad["total_attempts"] = 3
            validate_feature_dict(bad, ordered)
            fail("relational", "impossible relation accepted")
        except SchemaValidationError:
            pass_("relational")

        # Named features: key order must not matter. Positional bare lists are rejected.
        try:
            shuffled_items = list(feats.items())[::-1]
            reordered_named = dict(shuffled_items)
            vec_a = validate_feature_dict(feats, ordered)
            vec_b = validate_feature_dict(reordered_named, ordered)
            if vec_a != vec_b:
                fail("feature_order_policy", "named feature reorder changed vector")
            else:
                try:
                    validate_feature_dict(list(feats.values())[::-1], ordered)  # type: ignore[arg-type]
                    fail("feature_order_policy", "positional list was accepted")
                except SchemaValidationError:
                    if contract.get("positional_vector_accepted"):
                        fail("feature_order_policy", "positional vectors must not be accepted in V1")
                    else:
                        pass_("feature_order_policy")
        except SchemaValidationError as exc:
            fail("feature_order_policy", str(exc))

        # Secret / privacy scan
        secret_hits = 0
        raw_logs = 0
        for path in root.rglob("*"):
            if path.is_dir():
                continue
            if RAW_LOG_NAME.search(path.name):
                raw_logs += 1
            if path.suffix.lower() in {".joblib", ".tar", ".gz", ".zip"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for pat in SECRET_PATTERNS:
                if pat.search(text):
                    secret_hits += 1
                    break
        results["raw_logs"] = raw_logs
        results["secret_hits"] = secret_hits
        if raw_logs == 0:
            pass_("no_raw_logs")
        else:
            fail("no_raw_logs", f"found {raw_logs}")
        if secret_hits == 0:
            pass_("secret_scan")
        else:
            fail("secret_scan", f"hits={secret_hits}")

        results["fit_calls"] = self.fit_calls
        if self.fit_calls != 0:
            fail("fit_calls", f"fit_calls={self.fit_calls}")
        else:
            pass_("fit_calls")

        results["representation"] = contract.get("representation")
        results["feature_count"] = len(ordered)
        results["model_classes"] = classes
        return results
