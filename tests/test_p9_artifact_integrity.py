"""P8 artifact integrity for P9."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evaluation.model_evaluator import FrozenArtifactBundle, canonical_json_sha256  # noqa: E402
from evaluation.p9_evaluation import load_yaml  # noqa: E402


def test_artifact_integrity_pass():
    cfg = load_yaml(ROOT / "config" / "p9_evaluation.yaml")
    bundle = FrozenArtifactBundle(ROOT, cfg)
    integrity = bundle.verify_integrity()
    assert integrity["ok"] is True
    assert integrity["split_canonical_match"] is True
    assert integrity["split_canonical_sha256"] == cfg["expected_split_sha256_canonical"]


def test_split_hash_mismatch_detected(tmp_path):
    cfg = load_yaml(ROOT / "config" / "p9_evaluation.yaml")
    # Corrupt expected hash in config copy
    cfg = dict(cfg)
    cfg["expected_split_sha256_canonical"] = "0" * 64
    bundle = FrozenArtifactBundle(ROOT, cfg)
    integrity = bundle.verify_integrity()
    assert integrity["ok"] is False
    assert integrity["split_canonical_match"] is False
