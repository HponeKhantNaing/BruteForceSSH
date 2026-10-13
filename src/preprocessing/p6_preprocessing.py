"""P6 canonical dataset build: local P4 only, no public supervised merge."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from preprocessing.attempt_reconstructor import attempt_id_map, reconstruct_attempts
from preprocessing.auth_parser import parse_auth_line
from preprocessing.normalizer import IdentityMapper, merge_counts, normalize_message

PREPROCESSING_VERSION = "p6-v1"

# Metadata leakage tokens that must not appear in model-eligible text
LEAKAGE_PATTERNS = [
    re.compile(r"\bNORMAL\b"),
    re.compile(r"\bSUSPICIOUS\b"),
    re.compile(r"\bBRUTE_FORCE\b"),
    re.compile(r"\bN0[1-6]\b"),
    re.compile(r"\bS0[1-4]\b"),
    re.compile(r"\bB0[1-5]\b"),
    re.compile(r"\bP[23]\b"),
    re.compile(r"brute_force", re.I),
    re.compile(r"data/raw/"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid YAML: {path}")
    return data


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=False) + "\n")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def validate_p5_external_policy(registry: dict[str, Any], expected: dict[str, str]) -> dict[str, Any]:
    by_id = {d["dataset_id"]: d for d in registry.get("datasets") or []}
    errors = []
    checked = {}
    for did, disp in expected.items():
        entry = by_id.get(did)
        if not entry:
            errors.append(f"missing dataset in registry: {did}")
            continue
        actual = entry.get("p6_disposition")
        checked[did] = {"expected": disp, "actual": actual, "decision": entry.get("decision")}
        if actual != disp:
            errors.append(f"{did}: expected disposition {disp}, got {actual}")
        if actual == "INCLUDE_CANDIDATE" or entry.get("decision") == "DIRECT_INTEGRATION_CANDIDATE":
            errors.append(f"{did}: unexpected direct integration candidate")
    return {"ok": not errors, "errors": errors, "checked": checked}


def read_raw_line(raw_path: Path, line_number: int) -> str | None:
    if not raw_path.is_file():
        return None
    lines = raw_path.read_text(encoding="utf-8", errors="replace").splitlines()
    if line_number < 1 or line_number > len(lines):
        return None
    return lines[line_number - 1]


def validate_sources(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    inputs = cfg["inputs"]
    paths = {k: root / v for k, v in inputs.items()}
    missing = [k for k, p in paths.items() if not p.is_file()]
    hashes = {k: sha256_file(p) for k, p in paths.items() if p.is_file()}
    registry = json.loads(paths["p5_registry"].read_text(encoding="utf-8")) if paths["p5_registry"].is_file() else {}
    ext = validate_p5_external_policy(registry, cfg["external_supervised_data"]["expected_dispositions"])
    if cfg["external_supervised_data"].get("enabled"):
        ext["ok"] = False
        ext["errors"].append("external_supervised_data.enabled must be false for P6")
    return {
        "ok": not missing and ext["ok"],
        "missing": missing,
        "hashes": hashes,
        "external_policy": ext,
        "paths": {k: str(p) for k, p in paths.items()},
    }


def build_dataset(root: Path, cfg: dict[str, Any], *, write: bool = True) -> dict[str, Any]:
    """Full P6 build. Returns summary stats and optionally writes outputs."""
    source_check = validate_sources(root, cfg)
    if not source_check["ok"]:
        return {"ok": False, "stage": "validate_sources", "source_check": source_check}

    runs = load_jsonl(root / cfg["inputs"]["run_labels"])
    events_p4 = load_jsonl(root / cfg["inputs"]["event_annotations"])

    primary_runs = [r for r in runs if r.get("primary_candidate") is True]
    if cfg.get("quality", {}).get("require_primary_candidate", True):
        selected_runs = primary_runs
    else:
        selected_runs = runs

    run_by_id = {r["run_id"]: r for r in selected_runs}
    events_by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unknown_run_events = []
    for e in events_p4:
        rid = e.get("run_id")
        if rid not in run_by_id:
            # Events for non-primary / excluded runs — skip for canonical supervised set
            if rid not in {r["run_id"] for r in runs}:
                unknown_run_events.append(e)
            continue
        events_by_run[rid].append(e)

    # Pass 1: parse all lines, observe identities
    mapper = IdentityMapper(
        user_prefix=cfg["anonymization"]["user_id_prefix"],
        source_prefix=cfg["anonymization"]["source_id_prefix"],
        pad=int(cfg["anonymization"].get("zero_pad", 3)),
    )
    parsed_cache: dict[tuple[str, int], dict[str, Any]] = {}
    raw_missing = []
    for rid, elist in events_by_run.items():
        for e in elist:
            raw_rel = e.get("raw_log_path") or run_by_id[rid].get("raw_log_path")
            raw_path = root / raw_rel
            line = read_raw_line(raw_path, int(e["line_number"]))
            if line is None:
                raw_missing.append({"run_id": rid, "line_number": e["line_number"], "raw_log_path": raw_rel})
                continue
            parsed = parse_auth_line(line)
            parsed_cache[(rid, int(e["line_number"]))] = {"raw": line, "parsed": parsed}
            mapper.observe_user(parsed.get("username_raw"))
            mapper.observe_source(parsed.get("source_ip"))
    mapper.freeze()

    norm_cfg = cfg["normalization"]
    noise_roles = set(cfg["noise_policy"].get("noise_roles") or [])
    auth_roles = set(cfg["noise_policy"].get("auth_relevant_roles") or [])
    text_roles = set(cfg["sequence_policy"].get("include_roles_in_canonical_text") or [])

    norm_counts = Counter()
    canonical_events: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    manual_review: list[dict[str, Any]] = []

    # Build events per run (without attempt_id yet)
    events_for_recon: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for rid in sorted(run_by_id.keys()):
        run = run_by_id[rid]
        elist = sorted(events_by_run.get(rid, []), key=lambda x: int(x["line_number"]))
        # Duplicate line check within run
        seen_raw: dict[str, int] = {}
        for e in elist:
            ln = int(e["line_number"])
            key = (rid, ln)
            if key not in parsed_cache:
                exclusions.append(
                    {
                        "run_id": rid,
                        "reason": "raw_reference_failure",
                        "line_number": ln,
                    }
                )
                continue
            raw = parsed_cache[key]["raw"]
            parsed = parsed_cache[key]["parsed"]
            if raw in seen_raw:
                # record duplicate candidate but keep both (legitimate repeats possible)
                pass
            seen_raw[raw] = seen_raw.get(raw, 0) + 1

            event_id = f"{rid}:{ln}"
            username = parsed.get("username_raw")
            source_ip = parsed.get("source_ip")
            hostname = parsed.get("hostname_raw")
            norm_msg, counts = normalize_message(
                raw,
                username=username,
                hostname=hostname,
                lowercase=bool(norm_cfg.get("lowercase_normalized_message", True)),
            )
            merge_counts(norm_counts, counts)

            role = e.get("event_role")
            is_noise = role in noise_roles
            is_auth = role in auth_roles
            include_seq = role in text_roles

            ce = {
                "schema_version": "1.0",
                "event_id": event_id,
                "run_id": rid,
                "line_number": ln,
                "timestamp_raw": parsed.get("timestamp_raw"),
                "timestamp_iso": parsed.get("timestamp_iso"),
                "timestamp_parse_status": parsed.get("timestamp_parse_status"),
                "process": parsed.get("process"),
                "pid": parsed.get("pid"),
                "process_id_normalized": "<PID>" if parsed.get("pid") is not None else None,
                "event_role": role,
                "source_id": mapper.source_id(source_ip),
                "user_id": mapper.user_id(username),
                "source_ip_present": source_ip is not None,
                "username_present": username is not None,
                "normalized_message": norm_msg,
                "is_auth_relevant": is_auth,
                "is_infrastructure_noise": is_noise,
                "include_in_sequence": include_seq,
                "parse_status": parsed.get("parse_status") or e.get("parse_status"),
                "raw_log_path": e.get("raw_log_path") or run.get("raw_log_path"),
                "attempt_id": None,
            }
            if seen_raw[raw] > 1:
                ce["duplicate_event_candidate"] = True
            events_for_recon[rid].append(ce)

    # Reconstruct attempts
    all_attempts: list[dict[str, Any]] = []
    recon_report_rows: list[dict[str, Any]] = []
    for rid in sorted(run_by_id.keys()):
        run = run_by_id[rid]
        ce_list = events_for_recon[rid]
        attempts = reconstruct_attempts(ce_list, rid)
        idmap = attempt_id_map(attempts)
        for ce in ce_list:
            ce["attempt_id"] = idmap.get(ce["event_id"])
            canonical_events.append(ce)
        all_attempts.extend(attempts)

        fail_n = sum(1 for a in attempts if a["outcome"] == "FAILURE")
        succ_n = sum(1 for a in attempts if a["outcome"] == "SUCCESS")
        # Manifest validation signals
        manifest_fail = run.get("actual_failed_attempts")
        manifest_succ = run.get("actual_successes")
        # Also try event_summary from manifest file if null
        if manifest_fail is None or manifest_succ is None:
            mpath = run.get("manifest_path")
            if mpath and (root / mpath).is_file():
                try:
                    man = json.loads((root / mpath).read_text(encoding="utf-8"))
                    es = man.get("event_summary") or {}
                    if manifest_fail is None:
                        manifest_fail = es.get("failed_password_count")
                    if manifest_succ is None:
                        manifest_succ = es.get("accepted_password_count")
                except (OSError, json.JSONDecodeError):
                    pass

        status = "MATCH"
        notes = ""
        if manifest_fail is not None and fail_n != int(manifest_fail):
            status = "REVIEW_REQUIRED"
            notes = f"fail reconstructed={fail_n} manifest={manifest_fail}"
        if manifest_succ is not None and succ_n != int(manifest_succ):
            status = "REVIEW_REQUIRED"
            notes = (notes + "; " if notes else "") + f"succ reconstructed={succ_n} manifest={manifest_succ}"
        # AUTH_FAILURE count should equal logical failures when PAM pairs cleanly
        auth_fail_events = sum(1 for c in ce_list if c["event_role"] == "AUTH_FAILURE")
        if status == "MATCH" and auth_fail_events != fail_n and manifest_fail is None:
            # Explainable if only AUTH_FAILURE anchors used
            if auth_fail_events == fail_n:
                status = "MATCH"
            else:
                status = "EXPLAINED_DIFFERENCE"
                notes = f"auth_failure_events={auth_fail_events} logical_failures={fail_n}"

        row = {
            "run_id": rid,
            "scenario_id": run.get("scenario_id"),
            "manifest_failures": manifest_fail,
            "reconstructed_failures": fail_n,
            "manifest_successes": manifest_succ,
            "reconstructed_successes": succ_n,
            "auth_failure_events": auth_fail_events,
            "pam_auth_failure_events": sum(1 for c in ce_list if c["event_role"] == "PAM_AUTH_FAILURE"),
            "status": status,
            "notes": notes,
        }
        recon_report_rows.append(row)
        if status == "REVIEW_REQUIRED":
            manual_review.append(
                {
                    "run_id": rid,
                    "reason": "attempt_count_mismatch",
                    "details": row,
                }
            )

    # Sort canonical events deterministically
    canonical_events.sort(key=lambda e: (e["run_id"], e["line_number"]))
    all_attempts.sort(key=lambda a: (a["run_id"], a["attempt_order"]))

    # Build sequences + runs
    events_by_run_c = defaultdict(list)
    for e in canonical_events:
        events_by_run_c[e["run_id"]].append(e)
    attempts_by_run = defaultdict(list)
    for a in all_attempts:
        attempts_by_run[a["run_id"]].append(a)

    canonical_sequences: list[dict[str, Any]] = []
    canonical_runs: list[dict[str, Any]] = []
    leakage_hits = []

    for rid in sorted(run_by_id.keys()):
        run = run_by_id[rid]
        evs = events_by_run_c[rid]
        atts = attempts_by_run[rid]
        text_parts = [
            e["normalized_message"]
            for e in evs
            if e.get("include_in_sequence") and e.get("normalized_message")
        ]
        canonical_text = "\n".join(text_parts)
        for pat in LEAKAGE_PATTERNS:
            if pat.search(canonical_text):
                leakage_hits.append({"run_id": rid, "pattern": pat.pattern})

        # Also check for raw IPs / known lab usernames
        if re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", canonical_text):
            leakage_hits.append({"run_id": rid, "pattern": "raw_ipv4"})
        for u in ("testuser", "labuser1", "labuser2", "labuser3"):
            if re.search(rf"\b{u}\b", canonical_text, re.I):
                leakage_hits.append({"run_id": rid, "pattern": f"raw_username:{u}"})

        seq_start = evs[0]["timestamp_iso"] if evs else None
        seq_end = evs[-1]["timestamp_iso"] if evs else None
        duration = run.get("observed_duration_seconds")
        event_ids = [e["event_id"] for e in evs]
        attempt_ids = [a["attempt_id"] for a in atts]

        canonical_sequences.append(
            {
                "sample_id": f"P6_{rid}",
                "run_id": rid,
                "event_ids": event_ids,
                "attempt_ids": attempt_ids,
                "canonical_text": canonical_text,
                "sequence_start": seq_start,
                "sequence_end": seq_end,
                "duration_seconds": duration,
                "preprocessing_version": PREPROCESSING_VERSION,
            }
        )

        canonical_runs.append(
            {
                "schema_version": "1.0",
                "sample_id": f"P6_{rid}",
                "run_id": rid,
                "scenario_id": run.get("scenario_id"),
                "scenario_family": run.get("scenario_family"),
                "target_label": run.get("target_label"),
                "collection_phase": run.get("collection_phase"),
                "collection_batch_id": run.get("collection_batch_id"),
                "data_source": run.get("data_source"),
                "collection_role": run.get("collection_role"),
                "started_at": run.get("started_at"),
                "ended_at": run.get("ended_at"),
                "duration_seconds": duration,
                "raw_log_path": run.get("raw_log_path"),
                "raw_log_sha256": run.get("raw_log_sha256"),
                "event_count": len(evs),
                "logical_attempt_count": len(atts),
                "event_ids": event_ids,
                "attempt_ids": attempt_ids,
                "canonical_text": canonical_text,
                "split_group_run": run.get("split_group_run"),
                "split_group_batch": run.get("split_group_batch"),
                "preprocessing_version": PREPROCESSING_VERSION,
            }
        )

    class_counts = Counter(r["target_label"] for r in canonical_runs)
    outcome_counts = Counter(a["outcome"] for a in all_attempts)
    role_counts = Counter(e["event_role"] for e in canonical_events)

    quality = {
        "runs_discovered_p4_primary": len(primary_runs),
        "runs_accepted": len(canonical_runs),
        "runs_excluded": len(exclusions),
        "events_discovered_p4": len(events_p4),
        "events_in_primary_joins": sum(len(v) for v in events_by_run.values()),
        "canonical_events": len(canonical_events),
        "auth_relevant_events": sum(1 for e in canonical_events if e["is_auth_relevant"]),
        "noise_marked_events": sum(1 for e in canonical_events if e["is_infrastructure_noise"]),
        "partial_parse_events": sum(1 for e in canonical_events if e.get("parse_status") == "partial"),
        "logical_attempts": len(all_attempts),
        "attempt_outcomes": dict(outcome_counts),
        "timestamp_parse_failures": sum(
            1 for e in canonical_events if e.get("timestamp_parse_status") not in ("ok",)
        ),
        "raw_reference_failures": len(raw_missing),
        "unknown_run_events": len(unknown_run_events),
        "manifest_match_runs": sum(1 for r in recon_report_rows if r["status"] == "MATCH"),
        "manifest_mismatch_runs": sum(1 for r in recon_report_rows if r["status"] == "REVIEW_REQUIRED"),
        "explained_difference_runs": sum(1 for r in recon_report_rows if r["status"] == "EXPLAINED_DIFFERENCE"),
        "manual_review_runs": len({m["run_id"] for m in manual_review}),
        "leakage_hits": len(leakage_hits),
        "public_supervised_records": 0,
        "event_role_counts": dict(role_counts),
        "class_counts": dict(class_counts),
        "auth_failure_events": role_counts.get("AUTH_FAILURE", 0),
        "pam_auth_failure_events": role_counts.get("PAM_AUTH_FAILURE", 0),
        "logical_failed_attempts": outcome_counts.get("FAILURE", 0),
        "logical_success_attempts": outcome_counts.get("SUCCESS", 0),
    }

    normalization_report = {
        "timestamps_normalized": int(norm_counts.get("timestamps", 0)),
        "usernames_replaced": int(norm_counts.get("usernames", 0)),
        "ips_replaced": int(norm_counts.get("ips", 0)),
        "ports_replaced": int(norm_counts.get("ports", 0)),
        "pids_replaced": int(norm_counts.get("pids", 0)),
        "hostnames_normalized": int(norm_counts.get("hostnames", 0)),
        "unique_user_ids": mapper.user_count,
        "unique_source_ids": mapper.source_count,
        "lowercase_normalized_message": bool(norm_cfg.get("lowercase_normalized_message", True)),
    }

    attempt_reconstruction_report = {
        "method": cfg["attempt_reconstruction"].get("method"),
        "runs": recon_report_rows,
        "summary": {
            "match": quality["manifest_match_runs"],
            "review_required": quality["manifest_mismatch_runs"],
            "explained_difference": quality["explained_difference_runs"],
            "total_attempts": len(all_attempts),
            "outcomes": dict(outcome_counts),
        },
    }

    class_distribution = {
        "schema_version": "1.0",
        "unit": "canonical_contextual_run",
        "preprocessing_version": PREPROCESSING_VERSION,
        "counts": {
            "NORMAL": class_counts.get("NORMAL", 0),
            "SUSPICIOUS": class_counts.get("SUSPICIOUS", 0),
            "BRUTE_FORCE": class_counts.get("BRUTE_FORCE", 0),
        },
        "total": len(canonical_runs),
        "external_supervised_data_included": False,
    }

    dataset_manifest = {
        "dataset_name": "p6_canonical_local_lab",
        "schema_version": "1.0",
        "preprocessing_version": PREPROCESSING_VERSION,
        "created_at": utc_now(),
        "source_files": source_check["paths"],
        "source_hashes": source_check["hashes"],
        "p4_primary_sample_count": len(primary_runs),
        "canonical_sample_count": len(canonical_runs),
        "class_distribution": class_distribution["counts"],
        "event_count": len(canonical_events),
        "attempt_count": len(all_attempts),
        "external_supervised_data_included": False,
        "public_dataset_policy": {
            "loghub_openssh": "external_only",
            "cicids2017": "external_only",
            "cam_lds": "external_only",
            "loghub_hdfs": "rejected",
        },
        "normalization_policy": norm_cfg,
        "anonymization_policy": {
            "user_id_prefix": cfg["anonymization"]["user_id_prefix"],
            "source_id_prefix": cfg["anonymization"]["source_id_prefix"],
            "persist_reversible_mapping": False,
        },
        "attempt_reconstruction_method": cfg["attempt_reconstruction"].get("method"),
        "known_limitations": [
            "Single Docker lab source environment",
            "Limited username/source IP diversity",
            "Attempt correlation uses OpenSSH PID pairing",
            "INVALID_USER coverage currently zero in source data",
            "No public supervised data included by P5 policy",
        ],
        "leakage_guard_hits": leakage_hits,
        "external_policy_validation": source_check["external_policy"],
    }

    out_root = root / cfg["output"]["root"]
    result = {
        "ok": quality["leakage_hits"] == 0 and source_check["ok"] and len(raw_missing) == 0,
        "source_check": source_check,
        "quality": quality,
        "normalization_report": normalization_report,
        "attempt_reconstruction_report": attempt_reconstruction_report,
        "class_distribution": class_distribution,
        "dataset_manifest": dataset_manifest,
        "canonical_runs": canonical_runs,
        "canonical_events": canonical_events,
        "canonical_attempts": all_attempts,
        "canonical_sequences": canonical_sequences,
        "exclusions": exclusions,
        "manual_review": manual_review,
        "output_root": str(out_root),
    }

    if write:
        out_root.mkdir(parents=True, exist_ok=True)
        (out_root / "schemas").mkdir(parents=True, exist_ok=True)
        write_jsonl(out_root / "canonical_runs.jsonl", canonical_runs)
        write_jsonl(out_root / "canonical_events.jsonl", canonical_events)
        write_jsonl(out_root / "canonical_attempts.jsonl", all_attempts)
        write_jsonl(out_root / "canonical_sequences.jsonl", canonical_sequences)
        write_jsonl(out_root / "exclusions.jsonl", exclusions)
        write_jsonl(out_root / "manual_review.jsonl", manual_review)
        write_json(out_root / "dataset_manifest.json", dataset_manifest)
        write_json(out_root / "quality_report.json", quality)
        write_json(out_root / "normalization_report.json", normalization_report)
        write_json(out_root / "attempt_reconstruction_report.json", attempt_reconstruction_report)
        write_json(out_root / "class_distribution.json", class_distribution)
        _write_schemas(out_root / "schemas")
        _write_readme(out_root)

    return result


def _write_schemas(schema_dir: Path) -> None:
    write_json(
        schema_dir / "canonical_run.schema.json",
        {
            "title": "CanonicalRun",
            "type": "object",
            "required": ["sample_id", "run_id", "target_label", "preprocessing_version"],
            "properties": {
                "sample_id": {"type": "string"},
                "run_id": {"type": "string"},
                "target_label": {"enum": ["NORMAL", "SUSPICIOUS", "BRUTE_FORCE"]},
                "canonical_text": {"type": "string"},
                "event_ids": {"type": "array", "items": {"type": "string"}},
                "attempt_ids": {"type": "array", "items": {"type": "string"}},
            },
        },
    )
    write_json(
        schema_dir / "canonical_event.schema.json",
        {
            "title": "CanonicalEvent",
            "type": "object",
            "required": ["event_id", "run_id", "line_number", "event_role", "normalized_message"],
            "properties": {
                "event_id": {"type": "string"},
                "run_id": {"type": "string"},
                "line_number": {"type": "integer"},
                "event_role": {"type": "string"},
                "normalized_message": {"type": "string"},
                "attempt_id": {"type": ["string", "null"]},
            },
        },
    )
    write_json(
        schema_dir / "canonical_attempt.schema.json",
        {
            "title": "CanonicalAttempt",
            "type": "object",
            "required": ["attempt_id", "run_id", "outcome", "event_ids"],
            "properties": {
                "attempt_id": {"type": "string"},
                "run_id": {"type": "string"},
                "outcome": {"enum": ["SUCCESS", "FAILURE", "UNKNOWN"]},
                "event_ids": {"type": "array", "items": {"type": "string"}},
            },
        },
    )


def _write_readme(out_root: Path) -> None:
    text = """# P6 Canonical Dataset (local lab only)

This directory holds the **supervised canonical dataset** built from P4 local ground truth.

## Hard policy

- Public supervised data: **disabled**
- Loghub OpenSSH / CIC-IDS2017 / CAM-LDS: **EXTERNAL_ONLY** (not present here)
- Loghub HDFS: **REJECT**

## Semantic levels

1. **Event** — `canonical_events.jsonl`
2. **Logical authentication attempt** — `canonical_attempts.jsonl`
3. **Contextual run** — `canonical_runs.jsonl` + `canonical_sequences.jsonl`

## P7 handoff

Use runs/events/attempts/sequences + `dataset_manifest.json`.

Do **not** expect TF-IDF, behavioral feature columns, or train/test splits here.
"""
    (out_root / "README.md").write_text(text, encoding="utf-8")


def dry_run_summary(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    source_check = validate_sources(root, cfg)
    runs = load_jsonl(root / cfg["inputs"]["run_labels"])
    events = load_jsonl(root / cfg["inputs"]["event_annotations"])
    primary = [r for r in runs if r.get("primary_candidate") is True]
    return {
        "p4_primary_runs": len(primary),
        "class_distribution": dict(Counter(r["target_label"] for r in primary)),
        "events_discovered": len(events),
        "external_supervised_enabled": cfg["external_supervised_data"]["enabled"],
        "expected_public_records_included": 0,
        "source_check": source_check,
    }
