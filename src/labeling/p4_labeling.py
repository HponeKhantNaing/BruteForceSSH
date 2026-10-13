"""P4 ground-truth labeling: contextual run targets + atomic event roles."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

from collection.p2_normal import iso_now, sha256_file, write_json

POLICY_DEFAULT = "config/p4_labeling_policy.yaml"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_policy(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid labeling policy: {path}")
    return data


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=False) + "\n")


def append_reason(
    exclusions: list[dict[str, Any]],
    *,
    run_id: str | None,
    scenario_id: str | None,
    source_index: str,
    reason_code: str,
    details: str,
    review_required: bool = False,
    extra: dict[str, Any] | None = None,
) -> None:
    rec = {
        "run_id": run_id,
        "scenario_id": scenario_id,
        "source_index": source_index,
        "reason_code": reason_code,
        "details": details,
        "review_required": review_required,
        "timestamp": utc_now_iso(),
    }
    if extra:
        rec.update(extra)
    exclusions.append(rec)


def classify_collection_role(batch_id: str | None, rules: list[dict[str, Any]]) -> str:
    if not batch_id:
        return "unknown"
    for rule in rules:
        sub = str(rule.get("match_substring", ""))
        if sub and sub in batch_id:
            return str(rule.get("role", "unknown"))
    return "unknown"


def intent_for_scenario(policy: dict[str, Any], scenario_id: str) -> str | None:
    known = policy.get("known_scenarios") or {}
    for intent, ids in known.items():
        if scenario_id in (ids or []):
            return intent
    return None


def map_target(policy: dict[str, Any], intent: str) -> str | None:
    mapping = (policy.get("scenario_mapping") or {}).get(intent)
    if not mapping:
        return None
    return mapping.get("target")


def annotate_line(line: str, patterns: list[dict[str, Any]]) -> tuple[str, str, str]:
    """Return (event_role, parser_rule, parse_status)."""
    for rule in patterns:
        for sub in rule.get("substrings") or []:
            if sub.lower() in line.lower():
                return str(rule["role"]), str(rule.get("parser_rule", "pattern")), "matched"
    return "UNCLASSIFIED", "none", "unmatched"


def failed_password_count_in_text(text: str) -> int:
    return text.lower().count("failed password")


def accepted_password_count_in_text(text: str) -> int:
    return text.lower().count("accepted password")


@dataclass
class LabelBuildResult:
    run_labels: list[dict[str, Any]] = field(default_factory=list)
    event_annotations: list[dict[str, Any]] = field(default_factory=list)
    exclusions: list[dict[str, Any]] = field(default_factory=list)
    audits: list[dict[str, Any]] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)


def discover_index_entries(root: Path, policy: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Return list of (source_name, index_entry)."""
    out: list[tuple[str, dict[str, Any]]] = []
    for source_name, cfg in (policy.get("sources") or {}).items():
        index_path = root / cfg["index"]
        for entry in load_jsonl(index_path):
            out.append((source_name, entry))
    return out


def resolve_paths(root: Path, entry: dict[str, Any]) -> tuple[Path | None, Path | None]:
    raw = entry.get("raw_log_path")
    man = entry.get("manifest_path")
    raw_path = (root / raw) if raw else None
    man_path = (root / man) if man else None
    return raw_path, man_path


def validate_ground_truth(
    policy: dict[str, Any],
    scenario_id: str,
    manifest: dict[str, Any],
    raw_text: str,
) -> str | None:
    checks = (policy.get("ground_truth_checks") or {}).get(scenario_id)
    if not checks:
        return None
    # Prefer event_summary from manifest when present; fall back to raw text.
    summary = manifest.get("event_summary") or {}
    failed = summary.get("failed_password_count")
    if failed is None:
        failed = failed_password_count_in_text(raw_text)
    accepted = summary.get("accepted_password_count")
    if accepted is None:
        accepted = accepted_password_count_in_text(raw_text)

    if "require_failed_password_count_eq" in checks:
        if int(failed) != int(checks["require_failed_password_count_eq"]):
            return (
                f"expected failed_password_count="
                f"{checks['require_failed_password_count_eq']} got {failed}"
            )
    if "require_failed_password_min" in checks:
        if int(failed) < int(checks["require_failed_password_min"]):
            return f"failed_password_count {failed} < min {checks['require_failed_password_min']}"
    if "require_accepted_password_min" in checks:
        if int(accepted) < int(checks["require_accepted_password_min"]):
            return f"accepted_password_count {accepted} < min {checks['require_accepted_password_min']}"
    return None


def build_labels(
    root: Path,
    policy: dict[str, Any],
    *,
    include_smoke: bool = False,
) -> LabelBuildResult:
    result = LabelBuildResult()
    eligibility = policy.get("eligibility") or {}
    role_rules = policy.get("collection_role_rules") or []
    patterns = (policy.get("event_roles") or {}).get("patterns") or []
    store_raw = bool(policy.get("store_raw_line_in_annotations", False))
    policy_version = policy.get("label_policy_version", "p4-label-policy-v1")

    allowed_roles = set(eligibility.get("allowed_collection_roles") or ["baseline"])
    if include_smoke:
        allowed_roles.add("smoke")

    entries = discover_index_entries(root, policy)
    result.stats["p2_runs_discovered"] = sum(1 for s, _ in entries if s == "p2")
    result.stats["p3_runs_discovered"] = sum(1 for s, _ in entries if s == "p3")

    # Duplicate tracking
    seen_run_ids: dict[str, str] = {}
    checksum_map: dict[str, list[str]] = defaultdict(list)

    # Sort for determinism
    entries_sorted = sorted(
        entries,
        key=lambda t: (
            t[0],
            t[1].get("collection_batch_id") or "",
            t[1].get("scenario_id") or "",
            t[1].get("run_id") or "",
        ),
    )

    for source_name, entry in entries_sorted:
        source_index = str((policy.get("sources") or {}).get(source_name, {}).get("index", source_name))
        run_id = entry.get("run_id")
        scenario_id = entry.get("scenario_id")
        batch_id = entry.get("collection_batch_id")
        index_result = entry.get("result")

        if not run_id:
            append_reason(
                result.exclusions,
                run_id=None,
                scenario_id=scenario_id,
                source_index=source_index,
                reason_code="missing_manifest",
                details="index entry missing run_id",
            )
            continue

        if run_id in seen_run_ids:
            append_reason(
                result.exclusions,
                run_id=run_id,
                scenario_id=scenario_id,
                source_index=source_index,
                reason_code="duplicate_run_id",
                details=f"duplicate of first seen from {seen_run_ids[run_id]}",
            )
            continue
        seen_run_ids[run_id] = source_index

        raw_path, man_path = resolve_paths(root, entry)
        if not man_path or not man_path.is_file():
            append_reason(
                result.exclusions,
                run_id=run_id,
                scenario_id=scenario_id,
                source_index=source_index,
                reason_code="missing_manifest",
                details=f"manifest missing: {entry.get('manifest_path')}",
            )
            continue
        if not raw_path or not raw_path.is_file():
            append_reason(
                result.exclusions,
                run_id=run_id,
                scenario_id=scenario_id,
                source_index=source_index,
                reason_code="missing_raw_log",
                details=f"raw log missing: {entry.get('raw_log_path')}",
            )
            continue

        try:
            manifest = json.loads(man_path.read_text(encoding="utf-8"))
        except Exception as exc:
            append_reason(
                result.exclusions,
                run_id=run_id,
                scenario_id=scenario_id,
                source_index=source_index,
                reason_code="missing_manifest",
                details=f"manifest unreadable: {exc}",
            )
            continue

        # Index/manifest consistency
        conflicts = []
        for key in ("run_id", "scenario_id", "collection_batch_id", "result", "raw_log_sha256"):
            iv = entry.get(key)
            mv = manifest.get(key)
            if iv is not None and mv is not None and iv != mv:
                conflicts.append(f"{key}: index={iv!r} manifest={mv!r}")
        if conflicts:
            append_reason(
                result.exclusions,
                run_id=run_id,
                scenario_id=scenario_id,
                source_index=source_index,
                reason_code="index_manifest_conflict",
                details="; ".join(conflicts),
            )
            continue

        run_result = manifest.get("result", index_result)
        if eligibility.get("require_run_result_success", True) and run_result != "success":
            code = "interrupted_run" if run_result == "interrupted" else "failed_run"
            if run_result == "interrupted" and not eligibility.get("include_interrupted_runs", False):
                append_reason(
                    result.exclusions,
                    run_id=run_id,
                    scenario_id=scenario_id,
                    source_index=source_index,
                    reason_code=code,
                    details=f"result={run_result}",
                )
                continue
            if run_result != "success" and not eligibility.get("include_failed_runs", False):
                append_reason(
                    result.exclusions,
                    run_id=run_id,
                    scenario_id=scenario_id,
                    source_index=source_index,
                    reason_code=code,
                    details=f"result={run_result}",
                )
                continue

        # Checksum
        digest = sha256_file(raw_path)
        expected = manifest.get("raw_log_sha256") or entry.get("raw_log_sha256")
        if eligibility.get("require_valid_sha256", True):
            if not expected:
                append_reason(
                    result.exclusions,
                    run_id=run_id,
                    scenario_id=scenario_id,
                    source_index=source_index,
                    reason_code="checksum_mismatch",
                    details="missing expected sha256",
                )
                continue
            if digest != expected:
                append_reason(
                    result.exclusions,
                    run_id=run_id,
                    scenario_id=scenario_id,
                    source_index=source_index,
                    reason_code="checksum_mismatch",
                    details=f"expected {expected} got {digest}",
                )
                continue

        checksum_map[digest].append(run_id)

        collection_role = classify_collection_role(batch_id, role_rules)
        if collection_role == "smoke" and not (
            include_smoke or eligibility.get("include_smoke_runs", False)
        ):
            append_reason(
                result.exclusions,
                run_id=run_id,
                scenario_id=scenario_id,
                source_index=source_index,
                reason_code="smoke_excluded",
                details=f"batch_id={batch_id}",
            )
            continue
        if collection_role == "verification" and not eligibility.get(
            "include_verification_runs", False
        ):
            append_reason(
                result.exclusions,
                run_id=run_id,
                scenario_id=scenario_id,
                source_index=source_index,
                reason_code="unknown_collection_role",
                details=(
                    f"collection_role=verification excluded from primary set "
                    f"(batch={batch_id})"
                ),
            )
            continue
        if collection_role == "unknown" or collection_role not in allowed_roles:
            append_reason(
                result.exclusions,
                run_id=run_id,
                scenario_id=scenario_id,
                source_index=source_index,
                reason_code="unknown_collection_role",
                details=f"collection_role={collection_role} batch={batch_id}",
            )
            continue

        if not scenario_id:
            append_reason(
                result.exclusions,
                run_id=run_id,
                scenario_id=None,
                source_index=source_index,
                reason_code="unknown_scenario",
                details="missing scenario_id",
            )
            continue

        known_intent = intent_for_scenario(policy, scenario_id)
        if known_intent is None:
            append_reason(
                result.exclusions,
                run_id=run_id,
                scenario_id=scenario_id,
                source_index=source_index,
                reason_code="unknown_scenario",
                details="scenario_id not in known_scenarios allow-list",
            )
            continue

        scenario_intent = manifest.get("scenario_intent") or entry.get("scenario_intent")
        if not scenario_intent:
            append_reason(
                result.exclusions,
                run_id=run_id,
                scenario_id=scenario_id,
                source_index=source_index,
                reason_code="unknown_intent",
                details="missing scenario_intent",
            )
            continue
        if scenario_intent != known_intent:
            append_reason(
                result.exclusions,
                run_id=run_id,
                scenario_id=scenario_id,
                source_index=source_index,
                reason_code="unknown_intent",
                details=f"manifest intent {scenario_intent!r} != known {known_intent!r}",
                review_required=True,
            )
            continue

        target = map_target(policy, scenario_intent)
        if not target:
            append_reason(
                result.exclusions,
                run_id=run_id,
                scenario_id=scenario_id,
                source_index=source_index,
                reason_code="unknown_intent",
                details=f"no target mapping for intent={scenario_intent}",
            )
            continue

        raw_text = raw_path.read_text(encoding="utf-8", errors="replace")
        gt_err = validate_ground_truth(policy, scenario_id, manifest, raw_text)
        if gt_err:
            append_reason(
                result.exclusions,
                run_id=run_id,
                scenario_id=scenario_id,
                source_index=source_index,
                reason_code="invalid_ground_truth",
                details=gt_err,
                review_required=True,
            )
            continue

        # Duplicate evidence: same checksum already accepted for another run
        prior = [rid for rid in checksum_map[digest] if rid != run_id]
        # Only exclude if another run with same checksum was already accepted
        already_accepted = [r for r in result.run_labels if r.get("raw_log_sha256") == digest]
        if already_accepted:
            append_reason(
                result.exclusions,
                run_id=run_id,
                scenario_id=scenario_id,
                source_index=source_index,
                reason_code="duplicate_evidence",
                details=f"same sha256 as accepted run {already_accepted[0]['run_id']}",
            )
            continue

        sample_id = f"P4_{run_id}"
        phase = manifest.get("collection_phase") or entry.get("collection_phase") or (
            "P2" if source_name == "p2" else "P3"
        )
        family = scenario_intent  # normal / suspicious / brute_force

        run_label = {
            "schema_version": "1.0",
            "sample_id": sample_id,
            "run_id": run_id,
            "scenario_id": scenario_id,
            "scenario_intent": scenario_intent,
            "scenario_family": family,
            "target_label": target,
            "collection_phase": phase,
            "collection_batch_id": batch_id,
            "collection_role": collection_role,
            "data_source": manifest.get("data_source") or entry.get("data_source") or "local_lab",
            "raw_log_path": entry.get("raw_log_path"),
            "manifest_path": entry.get("manifest_path"),
            "raw_log_sha256": digest,
            "raw_log_line_count": manifest.get("raw_log_line_count")
            or entry.get("raw_log_line_count"),
            "started_at": manifest.get("started_at"),
            "ended_at": manifest.get("ended_at"),
            "observed_duration_seconds": manifest.get("observed_duration_seconds"),
            "planned_failed_attempts": manifest.get("planned_failed_attempts"),
            "actual_failed_attempts": manifest.get("actual_failed_attempts"),
            "planned_successes": manifest.get("planned_successes"),
            "actual_successes": manifest.get("actual_successes"),
            "configured_username_count": manifest.get("configured_user_count"),
            "label_source": "controlled_scenario_ground_truth",
            "label_status": "accepted",
            "label_policy_version": policy_version,
            "review_status": "automatic_verified",
            "primary_candidate": True,
            "split_group_run": run_id,
            "split_group_batch": batch_id,
            "split_group_scenario": scenario_id,
            "manifest_schema_version": manifest.get("schema_version"),
            "notes": "",
        }
        result.run_labels.append(run_label)

        # Event annotations (atomic roles only — no target_label)
        lines = raw_text.splitlines()
        for i, line in enumerate(lines, start=1):
            role, parser_rule, parse_status = annotate_line(line, patterns)
            ann = {
                "schema_version": "1.0",
                "event_annotation_id": f"{run_id}:{i}",
                "sample_id": sample_id,
                "run_id": run_id,
                "scenario_id": scenario_id,
                "collection_phase": phase,
                "raw_log_path": entry.get("raw_log_path"),
                "line_number": i,
                "event_role": role,
                "parser_rule": parser_rule,
                "parse_status": parse_status,
            }
            if store_raw:
                ann["raw_line"] = line
            result.event_annotations.append(ann)

        mapping_rule = f"scenario_intent:{scenario_intent} -> {target}"
        result.audits.append(
            {
                "run_id": run_id,
                "sample_id": sample_id,
                "scenario_id": scenario_id,
                "scenario_intent": scenario_intent,
                "target_label": target,
                "mapping_rule": mapping_rule,
                "checksum_verified": True,
                "manifest_verified": True,
                "collection_role": collection_role,
                "collection_batch_id": batch_id,
                "accepted": True,
                "label_policy_version": policy_version,
                "raw_log_path": entry.get("raw_log_path"),
                "manifest_path": entry.get("manifest_path"),
                "raw_log_sha256": digest,
            }
        )

    # Stats
    label_counts = Counter(r["target_label"] for r in result.run_labels)
    role_counts = Counter(a["event_role"] for a in result.event_annotations)
    excl_counts = Counter(e["reason_code"] for e in result.exclusions)
    result.stats.update(
        {
            "eligible_primary_runs": len(result.run_labels),
            "event_annotation_count": len(result.event_annotations),
            "excluded_count": len(result.exclusions),
            "target_counts": dict(label_counts),
            "event_role_counts": dict(role_counts),
            "exclusion_reason_counts": dict(excl_counts),
            "scenario_coverage": dict(
                Counter(r["scenario_id"] for r in result.run_labels)
            ),
        }
    )
    return result


def write_outputs(root: Path, policy: dict[str, Any], built: LabelBuildResult) -> dict[str, Path]:
    out_cfg = policy.get("output") or {}
    out_root = root / out_cfg.get("root", "data/interim/p4")
    audit_dir = out_root / out_cfg.get("audit_dir", "audit")
    audit_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "run_labels": out_root / out_cfg.get("run_labels", "run_labels.jsonl"),
        "event_annotations": out_root
        / out_cfg.get("event_annotations", "event_annotations.jsonl"),
        "excluded_runs": out_root / out_cfg.get("excluded_runs", "excluded_runs.jsonl"),
        "class_distribution": out_root
        / out_cfg.get("class_distribution", "class_distribution.json"),
        "labeling_report": out_root / out_cfg.get("labeling_report", "labeling_report.json"),
        "audit": audit_dir / "label_audit.jsonl",
    }

    # Deterministic ordering
    run_labels = sorted(built.run_labels, key=lambda r: r["sample_id"])
    events = sorted(
        built.event_annotations, key=lambda e: (e["run_id"], e["line_number"])
    )
    exclusions = sorted(
        built.exclusions,
        key=lambda e: (e.get("reason_code") or "", e.get("run_id") or ""),
    )
    audits = sorted(built.audits, key=lambda a: a["run_id"])

    write_jsonl(paths["run_labels"], run_labels)
    write_jsonl(paths["event_annotations"], events)
    write_jsonl(paths["excluded_runs"], exclusions)
    write_jsonl(paths["audit"], audits)

    total = len(run_labels) or 1
    dist = {
        "schema_version": "1.0",
        "unit": "contextual_run",
        "label_policy_version": policy.get("label_policy_version"),
        "counts": {
            "NORMAL": built.stats.get("target_counts", {}).get("NORMAL", 0),
            "SUSPICIOUS": built.stats.get("target_counts", {}).get("SUSPICIOUS", 0),
            "BRUTE_FORCE": built.stats.get("target_counts", {}).get("BRUTE_FORCE", 0),
        },
        "shares": {
            "NORMAL": round(
                built.stats.get("target_counts", {}).get("NORMAL", 0) / total, 4
            ),
            "SUSPICIOUS": round(
                built.stats.get("target_counts", {}).get("SUSPICIOUS", 0) / total, 4
            ),
            "BRUTE_FORCE": round(
                built.stats.get("target_counts", {}).get("BRUTE_FORCE", 0) / total, 4
            ),
        },
        "exclusions": built.stats.get("exclusion_reason_counts", {}),
        "event_role_counts": built.stats.get("event_role_counts", {}),
        "note": "Counts are contextual run samples, not raw log line samples.",
    }
    write_json(paths["class_distribution"], dist)

    report = {
        "generated_at": utc_now_iso(),
        "policy_version": policy.get("label_policy_version"),
        "schema_version": policy.get("schema_version"),
        "p2_runs_discovered": built.stats.get("p2_runs_discovered"),
        "p3_runs_discovered": built.stats.get("p3_runs_discovered"),
        "eligible_primary_runs": built.stats.get("eligible_primary_runs"),
        "smoke_runs_excluded": built.stats.get("exclusion_reason_counts", {}).get(
            "smoke_excluded", 0
        ),
        "failed_runs_excluded": built.stats.get("exclusion_reason_counts", {}).get(
            "failed_run", 0
        ),
        "integrity_failures": built.stats.get("exclusion_reason_counts", {}).get(
            "checksum_mismatch", 0
        )
        + built.stats.get("exclusion_reason_counts", {}).get("index_manifest_conflict", 0),
        "duplicate_issues": built.stats.get("exclusion_reason_counts", {}).get(
            "duplicate_run_id", 0
        )
        + built.stats.get("exclusion_reason_counts", {}).get("duplicate_evidence", 0),
        "exclusion_reason_counts": built.stats.get("exclusion_reason_counts", {}),
        "NORMAL_run_samples": built.stats.get("target_counts", {}).get("NORMAL", 0),
        "SUSPICIOUS_run_samples": built.stats.get("target_counts", {}).get(
            "SUSPICIOUS", 0
        ),
        "BRUTE_FORCE_run_samples": built.stats.get("target_counts", {}).get(
            "BRUTE_FORCE", 0
        ),
        "event_annotation_count": built.stats.get("event_annotation_count"),
        "unclassified_event_count": built.stats.get("event_role_counts", {}).get(
            "UNCLASSIFIED", 0
        ),
        "scenario_coverage": built.stats.get("scenario_coverage", {}),
        "outputs": {k: str(v.relative_to(root)) for k, v in paths.items()},
    }
    write_json(paths["labeling_report"], report)
    return paths
