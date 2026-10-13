"""Byte-for-byte identity of P8 source vs P10 release model."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from export.p10_export import load_yaml  # noqa: E402


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_source_release_byte_identity():
    cfg = load_yaml(ROOT / "config" / "p10_export.yaml")
    release_id = cfg["release"]["release_id"]
    release_model = ROOT / cfg["paths"]["releases_root"] / release_id / "model" / "random_forest_behavior.joblib"
    source_model = ROOT / "artifacts/p8/models/random_forest_behavior.joblib"
    assert release_model.is_file()
    assert _sha(source_model) == _sha(release_model)
    manifest = json.loads(
        (ROOT / cfg["paths"]["releases_root"] / release_id / "MANIFEST.json").read_text(encoding="utf-8")
    )
    assert manifest["model_sha256"] == _sha(release_model)
    assert manifest["byte_identity"] is True
