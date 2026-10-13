"""P5 public dataset evaluation helpers (metadata-first; no forced downloads)."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

DECISIONS = {
    "DIRECT_INTEGRATION_CANDIDATE",
    "EXTERNAL_LABELED_EVALUATION",
    "EXTERNAL_UNLABELED_CORPUS",
    "REJECT",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid YAML: {path}")
    return data


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def disk_free_bytes(path: Path) -> int:
    return shutil.disk_usage(path).free


def verify_p4_hashes(root: Path, snapshot_path: Path) -> dict[str, Any]:
    snap = load_json(snapshot_path)
    results = {}
    ok = True
    for rel, expected in snap.items():
        p = root / rel
        if not p.is_file():
            results[rel] = {"status": "MISSING", "expected": expected}
            ok = False
            continue
        actual = sha256_file(p)
        match = actual == expected
        results[rel] = {
            "status": "MATCH" if match else "CHANGED",
            "expected": expected,
            "actual": actual,
        }
        if not match:
            ok = False
    return {"ok": ok, "files": results}


def validate_registry_entry(entry: dict[str, Any]) -> list[str]:
    errors = []
    required = [
        "dataset_id",
        "name",
        "official_source",
        "publisher",
        "data_domain",
        "labeled",
        "decision",
        "decision_reason",
    ]
    for k in required:
        if k not in entry or entry[k] in (None, ""):
            errors.append(f"missing required field: {k}")
    if entry.get("decision") not in DECISIONS:
        errors.append(f"invalid decision: {entry.get('decision')}")
    return errors


def summarize_registry(registry: dict[str, Any]) -> dict[str, Any]:
    datasets = registry.get("datasets") or []
    by_decision: dict[str, list[str]] = {d: [] for d in DECISIONS}
    for d in datasets:
        by_decision.setdefault(d.get("decision", "REJECT"), []).append(d["dataset_id"])
    return {
        "dataset_count": len(datasets),
        "by_decision": {k: v for k, v in by_decision.items() if v},
        "direct_integration": by_decision.get("DIRECT_INTEGRATION_CANDIDATE", []),
        "external_only": by_decision.get("EXTERNAL_LABELED_EVALUATION", [])
        + by_decision.get("EXTERNAL_UNLABELED_CORPUS", []),
        "rejected": by_decision.get("REJECT", []),
    }
