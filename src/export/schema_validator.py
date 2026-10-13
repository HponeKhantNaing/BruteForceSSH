"""Strict input/output schema validation for the P10 RF behavior bundle."""

from __future__ import annotations

import math
from typing import Any


class SchemaValidationError(ValueError):
    """Raised when an inference payload violates the feature contract."""


BOOLEAN_FEATURES = frozenset(
    {
        "has_multiple_attempts",
        "success_after_failure",
        "first_attempt_failed",
        "last_attempt_success",
    }
)

NON_NEGATIVE_FEATURES = frozenset(
    {
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
)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_feature_dict(
    features: dict[str, Any],
    ordered_features: list[str],
    *,
    reject_unknown: bool = True,
    reject_non_finite: bool = True,
) -> list[float]:
    """Validate named features and return ordered raw vector for prediction."""
    if not isinstance(features, dict):
        raise SchemaValidationError("features must be an object/dict")

    missing = [f for f in ordered_features if f not in features]
    if missing:
        raise SchemaValidationError(f"missing required features: {missing}")

    extras = [k for k in features if k not in ordered_features]
    if extras and reject_unknown:
        raise SchemaValidationError(f"unknown feature fields rejected: {extras}")

    vector: list[float] = []
    for name in ordered_features:
        value = features[name]
        if not _is_number(value):
            raise SchemaValidationError(f"{name} must be numeric, got {type(value).__name__}")
        num = float(value)
        if reject_non_finite and not math.isfinite(num):
            raise SchemaValidationError(f"{name} must be finite (no NaN/Inf)")
        if name in BOOLEAN_FEATURES and num not in (0.0, 1.0):
            raise SchemaValidationError(f"{name} must be 0 or 1")
        if name in NON_NEGATIVE_FEATURES and num < 0:
            raise SchemaValidationError(f"{name} must be >= 0")
        if name == "failure_ratio" and not (0.0 <= num <= 1.0):
            raise SchemaValidationError("failure_ratio must be in [0, 1]")
        vector.append(num)

    _validate_relational(features)
    return vector


def _validate_relational(features: dict[str, Any]) -> None:
    total = float(features["total_attempts"])
    failed = float(features["failed_attempts"])
    success = float(features["successful_attempts"])
    if failed > total:
        raise SchemaValidationError("failed_attempts must be <= total_attempts")
    if success > total:
        raise SchemaValidationError("successful_attempts must be <= total_attempts")

    f30 = float(features["failed_count_30s_max"])
    f60 = float(features["failed_count_60s_max"])
    f5m = float(features["failed_count_5m_max"])
    if not (f30 <= f60 <= f5m <= failed):
        raise SchemaValidationError(
            "failed_count windows must satisfy 30s_max <= 60s_max <= 5m_max <= failed_attempts"
        )

    u60 = float(features["unique_users_60s_max"])
    ut = float(features["unique_users_total"])
    if u60 > ut:
        raise SchemaValidationError("unique_users_60s_max must be <= unique_users_total")

    streak = float(features["max_failure_streak"])
    if streak > failed:
        raise SchemaValidationError("max_failure_streak must be <= failed_attempts")


def validate_prediction_output(
    payload: dict[str, Any],
    *,
    expected_labels: set[str],
    model_version: str,
) -> None:
    if not isinstance(payload, dict):
        raise SchemaValidationError("prediction output must be an object")
    for key in ("model_version", "predicted_label", "class_probabilities", "probability_type"):
        if key not in payload:
            raise SchemaValidationError(f"output missing field: {key}")
    if payload["model_version"] != model_version:
        raise SchemaValidationError(
            f"model_version mismatch: {payload['model_version']} != {model_version}"
        )
    if payload["predicted_label"] not in expected_labels:
        raise SchemaValidationError(f"unexpected predicted_label: {payload['predicted_label']}")
    if payload["probability_type"] != "uncalibrated":
        raise SchemaValidationError("probability_type must be 'uncalibrated'")
    probs = payload["class_probabilities"]
    if not isinstance(probs, dict):
        raise SchemaValidationError("class_probabilities must be an object")
    if set(probs.keys()) != expected_labels:
        raise SchemaValidationError(
            f"class_probabilities keys {set(probs.keys())} != {expected_labels}"
        )
    for label, value in probs.items():
        if not _is_number(value) or not math.isfinite(float(value)):
            raise SchemaValidationError(f"probability for {label} must be finite numeric")
