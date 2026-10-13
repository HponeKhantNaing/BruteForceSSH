"""Release directories are immutable once created."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from export.p10_export import export_release, load_yaml  # noqa: E402


def test_second_export_refused():
    cfg = load_yaml(ROOT / "config" / "p10_export.yaml")
    release_dir = ROOT / cfg["paths"]["releases_root"] / cfg["release"]["release_id"]
    assert release_dir.is_dir()
    result = export_release(ROOT, cfg)
    assert result.get("status") == "REFUSED"
    assert "already exists" in result.get("error", "")
