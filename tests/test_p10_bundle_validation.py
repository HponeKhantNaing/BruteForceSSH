"""Bundle validation and checksum failure detection."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from export.bundle_validator import BundleValidator  # noqa: E402
from export.p10_export import load_yaml, validate_release  # noqa: E402


def test_validate_release_pass():
    cfg = load_yaml(ROOT / "config" / "p10_export.yaml")
    result = validate_release(ROOT, cfg)
    assert result["ok"] is True
    assert result["checks"]["checksums"] == "PASS"
    assert result["checks"]["tfidf_required"] == "PASS"
    assert result["checks"]["scaler_required"] == "PASS"
    assert result["fit_calls"] == 0


def test_checksum_tamper_detected(tmp_path):
    cfg = load_yaml(ROOT / "config" / "p10_export.yaml")
    release_id = cfg["release"]["release_id"]
    src = ROOT / cfg["paths"]["releases_root"] / release_id
    dst = tmp_path / release_id
    shutil.copytree(src, dst)
    readme = dst / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "\n# tampered\n", encoding="utf-8")
    result = BundleValidator(dst).validate()
    assert result["ok"] is False
    assert result["checks"]["checksums"] == "FAIL"
