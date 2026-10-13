"""Feature contract matches P8 authority; raw representation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from export.p10_export import load_yaml  # noqa: E402
from export.schema_validator import SchemaValidationError, validate_feature_dict  # noqa: E402


def test_feature_order_matches_p8():
    cfg = load_yaml(ROOT / "config" / "p10_export.yaml")
    release_id = cfg["release"]["release_id"]
    contract = json.loads(
        (
            ROOT / cfg["paths"]["releases_root"] / release_id / "schema" / "feature_contract.json"
        ).read_text(encoding="utf-8")
    )
    authority = json.loads(
        (ROOT / "artifacts/p8/preprocessing/behavior_feature_order.json").read_text(encoding="utf-8")
    )["feature_order"]
    assert contract["ordered_features"] == authority
    assert contract["feature_count"] == 22
    assert contract["scaling_required"] is False
    assert contract["tfidf_required"] is False
    assert contract["representation"] == "behavior_raw"


def test_reject_missing_and_bad_ranges():
    cfg = load_yaml(ROOT / "config" / "p10_export.yaml")
    release_id = cfg["release"]["release_id"]
    release = ROOT / cfg["paths"]["releases_root"] / release_id
    ordered = json.loads((release / "schema/feature_contract.json").read_text())["ordered_features"]
    feats = json.loads((release / "verification/smoke_test_input.json").read_text())["features"]

    bad = dict(feats)
    del bad["failed_attempts"]
    try:
        validate_feature_dict(bad, ordered)
        assert False, "expected missing feature error"
    except SchemaValidationError:
        pass

    bad = dict(feats)
    bad["failed_attempts"] = -1
    try:
        validate_feature_dict(bad, ordered)
        assert False, "expected range error"
    except SchemaValidationError:
        pass

    bad = dict(feats)
    bad["failed_attempts"] = 10
    bad["total_attempts"] = 3
    try:
        validate_feature_dict(bad, ordered)
        assert False, "expected relational error"
    except SchemaValidationError:
        pass
