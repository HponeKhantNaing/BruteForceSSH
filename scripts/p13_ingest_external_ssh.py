#!/usr/bin/env python3
"""Ingest public OpenSSH logs → behavioral episodes → large RF train.

Sources (research citation required — Loghub):
  - Zenodo Loghub SSH.tar.gz → SSH.log (~655k lines)
  - Loghub OpenSSH_2k + Linux samples
  - Optional Loghub-2.0 OpenSSH.zip

Heuristic labels (documented, not ground-truth human labels):
  NORMAL / SUSPICIOUS / BRUTE_FORCE from fail-count + window + user diversity
  (aligned with project V1 thresholds: 5/60s SUSPICIOUS, 10/120s BRUTE_FORCE).

Produces:
  data/external/derived/episodes/{behavioral_features,targets,text_samples,manifest}.jsonl/json
  artifacts/external/rf-openssh-ext-v1.0.0/
  docs/EXTERNAL_DATA_INVENTORY.md
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
    recall_score,
)
from sklearn.model_selection import GroupShuffleSplit

ROOT = Path(__file__).resolve().parents[1]
CORPUS_SSH = ROOT / "data/external/corpora/loghub_ssh_full/SSH.log"
CORPUS_2K = ROOT / "data/external/corpora/loghub_openssh/OpenSSH_2k.log"
CORPUS_L20 = ROOT / "data/external/corpora/loghub20_openssh/OpenSSH/OpenSSH_full.log"
DERIVED = ROOT / "data/external/derived/episodes"
ART = ROOT / "artifacts/external/rf-openssh-ext-v1.0.0"
LAB_P7 = ROOT / "data/features/p7"
CLASSES = ["NORMAL", "SUSPICIOUS", "BRUTE_FORCE"]

FEATURE_ORDER = [
    "total_attempts",
    "failed_attempts",
    "successful_attempts",
    "failure_ratio",
    "duration_seconds",
    "attempt_rate_per_second",
    "failed_count_30s_max",
    "failed_count_60s_max",
    "failed_count_5m_max",
    "success_count_5m_max",
    "unique_users_total",
    "unique_users_60s_max",
    "has_multiple_attempts",
    "min_inter_attempt_gap_seconds",
    "mean_inter_attempt_gap_seconds",
    "median_inter_attempt_gap_seconds",
    "std_inter_attempt_gap_seconds",
    "max_failure_streak",
    "success_after_failure",
    "failures_before_first_success",
    "first_attempt_failed",
    "last_attempt_success",
]

RE_TS = re.compile(
    r"^(?P<mon>\w{3})\s+(?P<day>\d{1,2})\s+(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2})\s+\S+\s+sshd\[(?P<pid>\d+)\]:\s+(?P<msg>.*)$"
)
RE_FAIL = re.compile(
    r"Failed password for (?:invalid user )?(?P<user>\S+) from (?P<ip>\S+)", re.I
)
RE_ACCEPT = re.compile(r"Accepted password for (?P<user>\S+) from (?P<ip>\S+)", re.I)
RE_INVALID = re.compile(r"Invalid user (?P<user>\S+) from (?P<ip>\S+)", re.I)
RE_AUTHFAIL = re.compile(r"authentication failure;.*rhost=(?P<ip>\S+)", re.I)

MONTH = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_ts(mon: str, day: str, h: str, m: str, s: str, year: int = 2023) -> float:
    # Relative epoch within corpus year; Loghub OpenSSH spans Dec–Jan.
    mo = MONTH[mon]
    y = year
    # Heuristic: Jan lines after Dec → next year
    return datetime(y, mo, int(day), int(h), int(m), int(s)).timestamp()


def parse_log_lines(path: Path, source_id: str, year: int = 2015) -> list[dict[str, Any]]:
    """Extract auth attempts from OpenSSH-style logs."""
    events: list[dict[str, Any]] = []
    # Loghub SSH.log is known Dec 2015 / Jan 2016 in original papers; use 2015 start.
    seen_months: set[int] = set()
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line_no, line in enumerate(f, 1):
            line = line.rstrip("\n")
            m = RE_TS.match(line)
            if not m:
                continue
            msg = m.group("msg")
            mo = MONTH[m.group("mon")]
            seen_months.add(mo)
            y = year
            if 1 in seen_months and mo == 1 and 12 in seen_months:
                y = year + 1
            ts = parse_ts(m.group("mon"), m.group("day"), m.group("h"), m.group("m"), m.group("s"), y)
            user = None
            ip = None
            kind = None
            mf = RE_FAIL.search(msg)
            ma = RE_ACCEPT.search(msg)
            mi = RE_INVALID.search(msg)
            if mf:
                kind = "FAILURE"
                user, ip = mf.group("user"), mf.group("ip")
            elif ma:
                kind = "SUCCESS"
                user, ip = ma.group("user"), ma.group("ip")
            elif mi:
                kind = "FAILURE"
                user, ip = mi.group("user"), mi.group("ip")
            else:
                continue
            events.append(
                {
                    "ts": ts,
                    "user": user or "unknown",
                    "ip": ip or "0.0.0.0",
                    "kind": kind,
                    "pid": m.group("pid"),
                    "source": source_id,
                    "line_no": line_no,
                }
            )
    return events


def split_episodes(events: list[dict[str, Any]], gap_seconds: float = 90.0) -> list[list[dict[str, Any]]]:
    by_ip: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in events:
        by_ip[e["ip"]].append(e)
    episodes: list[list[dict[str, Any]]] = []
    for ip, evs in by_ip.items():
        evs.sort(key=lambda x: x["ts"])
        cur: list[dict[str, Any]] = []
        last_ts = None
        for e in evs:
            if cur and last_ts is not None and (e["ts"] - last_ts) > gap_seconds:
                if len(cur) >= 1:
                    episodes.append(cur)
                cur = []
            cur.append(e)
            last_ts = e["ts"]
        if cur:
            episodes.append(cur)
    return episodes


def window_max_fails(attempts: list[dict[str, Any]], window: float) -> int:
    if not attempts:
        return 0
    fails = [a for a in attempts if a["kind"] == "FAILURE"]
    if not fails:
        return 0
    best = 0
    j = 0
    for i in range(len(fails)):
        while fails[i]["ts"] - fails[j]["ts"] > window:
            j += 1
        best = max(best, i - j + 1)
    return best


def window_unique_users(attempts: list[dict[str, Any]], window: float) -> int:
    fails = [a for a in attempts if a["kind"] == "FAILURE"]
    if not fails:
        return 0
    best = 0
    j = 0
    for i in range(len(fails)):
        while fails[i]["ts"] - fails[j]["ts"] > window:
            j += 1
        users = {fails[k]["user"] for k in range(j, i + 1)}
        best = max(best, len(users))
    return best


def episode_features(ep: list[dict[str, Any]]) -> dict[str, float]:
    ep = sorted(ep, key=lambda x: x["ts"])
    total = float(len(ep))
    failed = float(sum(1 for a in ep if a["kind"] == "FAILURE"))
    success = float(sum(1 for a in ep if a["kind"] == "SUCCESS"))
    dur = max(ep[-1]["ts"] - ep[0]["ts"], 1e-3)
    gaps = [ep[i]["ts"] - ep[i - 1]["ts"] for i in range(1, len(ep))]
    # streak
    streak = cur = 0
    for a in ep:
        if a["kind"] == "FAILURE":
            cur += 1
            streak = max(streak, cur)
        else:
            cur = 0
    first_fail = 1.0 if ep[0]["kind"] == "FAILURE" else 0.0
    last_succ = 1.0 if ep[-1]["kind"] == "SUCCESS" else 0.0
    success_after_failure = 0.0
    fails_before_success = 0.0
    seen_fail = False
    fail_count = 0
    for a in ep:
        if a["kind"] == "FAILURE":
            seen_fail = True
            fail_count += 1
        elif a["kind"] == "SUCCESS" and seen_fail:
            success_after_failure = 1.0
            if fails_before_success == 0:
                fails_before_success = float(fail_count)
            break
    if success_after_failure == 0 and success > 0:
        fails_before_success = 0.0
    elif success == 0:
        fails_before_success = failed

    users = {a["user"] for a in ep}
    feats = {
        "total_attempts": total,
        "failed_attempts": failed,
        "successful_attempts": success,
        "failure_ratio": failed / total if total else 0.0,
        "duration_seconds": float(dur),
        "attempt_rate_per_second": total / dur,
        "failed_count_30s_max": float(window_max_fails(ep, 30)),
        "failed_count_60s_max": float(window_max_fails(ep, 60)),
        "failed_count_5m_max": float(window_max_fails(ep, 300)),
        "success_count_5m_max": float(
            max(
                (
                    sum(1 for a in ep if a["kind"] == "SUCCESS" and abs(a["ts"] - t) <= 300)
                    for t in ([a["ts"] for a in ep] or [0])
                ),
                default=0,
            )
        ),
        "unique_users_total": float(len(users)),
        "unique_users_60s_max": float(window_unique_users(ep, 60)),
        "has_multiple_attempts": 1.0 if total >= 2 else 0.0,
        "min_inter_attempt_gap_seconds": float(min(gaps)) if gaps else 0.0,
        "mean_inter_attempt_gap_seconds": float(sum(gaps) / len(gaps)) if gaps else 0.0,
        "median_inter_attempt_gap_seconds": float(sorted(gaps)[len(gaps) // 2]) if gaps else 0.0,
        "std_inter_attempt_gap_seconds": float(np.std(gaps)) if len(gaps) > 1 else 0.0,
        "max_failure_streak": float(streak),
        "success_after_failure": success_after_failure,
        "failures_before_first_success": float(fails_before_success),
        "first_attempt_failed": first_fail,
        "last_attempt_success": last_succ,
    }
    return feats


def heuristic_label(feats: dict[str, float]) -> str:
    f60 = feats["failed_count_60s_max"]
    f120 = max(feats["failed_count_60s_max"], feats["failed_count_5m_max"] * 0.4)
    # Approximate 120s with 60s max + rate
    fails = feats["failed_attempts"]
    users60 = feats["unique_users_60s_max"]
    # BRUTE_FORCE
    if f60 >= 10 or fails >= 10 and feats["duration_seconds"] <= 120:
        return "BRUTE_FORCE"
    if users60 >= 5 and fails >= 5:
        return "BRUTE_FORCE"
    # SUSPICIOUS
    if f60 >= 5 or (3 <= fails <= 9 and feats["duration_seconds"] <= 120):
        return "SUSPICIOUS"
    if users60 >= 3 and fails >= 3:
        return "SUSPICIOUS"
    return "NORMAL"


def anonymize_snippet(ep: list[dict[str, Any]]) -> str:
    lines = []
    for a in ep[:12]:
        status = "Failed password" if a["kind"] == "FAILURE" else "Accepted password"
        lines.append(
            f"<host> sshd[<pid>]: {status} for <user> from <ip> port <port> ssh2"
        )
    return "\n".join(lines)


def build_episodes() -> dict[str, Any]:
    DERIVED.mkdir(parents=True, exist_ok=True)
    sources = []
    all_events: list[dict[str, Any]] = []
    if CORPUS_SSH.is_file():
        ev = parse_log_lines(CORPUS_SSH, "loghub_ssh_full", year=2015)
        all_events.extend(ev)
        sources.append(
            {
                "id": "loghub_ssh_full",
                "path": str(CORPUS_SSH.relative_to(ROOT)),
                "events": len(ev),
                "lines": sum(1 for _ in CORPUS_SSH.open("rb")),
                "sha256": sha256_file(CORPUS_SSH),
                "cite": "Zhu et al., Loghub (ISSRE 2023); Zenodo SSH.tar.gz",
                "url": "https://zenodo.org/records/8196385/files/SSH.tar.gz?download=1",
            }
        )
    if CORPUS_2K.is_file():
        ev = parse_log_lines(CORPUS_2K, "loghub_openssh_2k", year=2015)
        all_events.extend(ev)
        sources.append(
            {
                "id": "loghub_openssh_2k",
                "path": str(CORPUS_2K.relative_to(ROOT)),
                "events": len(ev),
                "sha256": sha256_file(CORPUS_2K),
                "cite": "logpai/loghub OpenSSH_2k",
                "url": "https://github.com/logpai/loghub",
            }
        )
    if CORPUS_L20.is_file():
        ev = parse_log_lines(CORPUS_L20, "loghub20_openssh_full", year=2015)
        all_events.extend(ev)
        sources.append(
            {
                "id": "loghub20_openssh_full",
                "path": str(CORPUS_L20.relative_to(ROOT)),
                "events": len(ev),
                "sha256": sha256_file(CORPUS_L20),
                "cite": "Loghub-2.0 OpenSSH.zip (Zhu/He et al.)",
                "url": "https://zenodo.org/records/8275861/files/OpenSSH.zip?download=1",
            }
        )

    episodes = split_episodes(all_events, gap_seconds=90.0)
    # Keep episodes with at least 1 auth attempt
    episodes = [e for e in episodes if len(e) >= 1]

    beh_rows = []
    tgt_rows = []
    txt_rows = []
    label_counts: Counter[str] = Counter()
    for i, ep in enumerate(episodes):
        feats = episode_features(ep)
        label = heuristic_label(feats)
        # Skip degenerate empty-ish
        if feats["total_attempts"] < 1:
            continue
        sid = f"EXT_{ep[0]['source']}_{ep[0]['ip'].replace('.', '_')}_{i:06d}"
        # group by /24 for split leakage control
        ip_parts = ep[0]["ip"].split(".")
        group = f"IP24_{'.'.join(ip_parts[:3])}" if len(ip_parts) == 4 else f"IP_{ep[0]['ip']}"
        beh_rows.append(
            {
                "sample_id": sid,
                "features": feats,
                "feature_engineering_version": "external-ssh-v1",
                "source": ep[0]["source"],
            }
        )
        tgt_rows.append(
            {
                "sample_id": sid,
                "target_label": label,
                "label_origin": "heuristic_v1_thresholds",
                "scenario_id": group,
                "split_group_run": group,
                "source": ep[0]["source"],
            }
        )
        txt_rows.append({"sample_id": sid, "canonical_text": anonymize_snippet(ep)})
        label_counts[label] += 1

    def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    write_jsonl(DERIVED / "behavioral_features.jsonl", beh_rows)
    write_jsonl(DERIVED / "targets.jsonl", tgt_rows)
    write_jsonl(DERIVED / "text_samples.jsonl", txt_rows)

    manifest = {
        "created_at": utc_now(),
        "episode_count": len(beh_rows),
        "label_counts": dict(label_counts),
        "label_policy": {
            "BRUTE_FORCE": "failed_count_60s_max>=10 OR (fails>=10 within ~120s) OR (unique_users_60s>=5 & fails>=5)",
            "SUSPICIOUS": "failed_count_60s_max>=5 OR 3-9 fails in short window OR (unique_users_60s>=3 & fails>=3)",
            "NORMAL": "otherwise (incl. low-fail / success sessions)",
            "note": "Heuristic labels for research training — not human gold labels",
        },
        "sources": sources,
        "feature_order": FEATURE_ORDER,
    }
    (DERIVED / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def matrix_from_rows(beh: list[dict[str, Any]], tgt: dict[str, str]) -> tuple[np.ndarray, np.ndarray, list[str], list[str]]:
    X, y, ids, groups = [], [], [], []
    for r in beh:
        sid = r["sample_id"]
        if sid not in tgt:
            continue
        feats = r["features"]
        X.append([float(feats.get(k, 0.0)) for k in FEATURE_ORDER])
        y.append(tgt[sid]["target_label"])
        ids.append(sid)
        groups.append(tgt[sid]["scenario_id"])
    return np.asarray(X, dtype=float), np.asarray(y), ids, groups


def train_large() -> dict[str, Any]:
    ART.mkdir(parents=True, exist_ok=True)
    ext_beh = load_jsonl(DERIVED / "behavioral_features.jsonl")
    ext_tgt = {r["sample_id"]: r for r in load_jsonl(DERIVED / "targets.jsonl")}

    # Merge lab gold (higher weight later via sample_weight)
    lab_beh = load_jsonl(LAB_P7 / "behavioral_features.jsonl") if (LAB_P7 / "behavioral_features.jsonl").is_file() else []
    lab_tgt_rows = load_jsonl(LAB_P7 / "targets.jsonl") if (LAB_P7 / "targets.jsonl").is_file() else []
    lab_tgt = {r["sample_id"]: r for r in lab_tgt_rows}

    X_ext, y_ext, ids_ext, g_ext = matrix_from_rows(ext_beh, ext_tgt)
    X_lab, y_lab, ids_lab, g_lab = matrix_from_rows(lab_beh, lab_tgt) if lab_beh else (
        np.zeros((0, len(FEATURE_ORDER))),
        np.array([]),
        [],
        [],
    )

    # Combined
    X = np.vstack([X_lab, X_ext]) if len(X_lab) else X_ext
    y = np.concatenate([y_lab, y_ext]) if len(y_lab) else y_ext
    groups = np.array((g_lab or []) + g_ext)
    origins = np.array(["lab"] * len(y_lab) + ["external"] * len(y_ext))
    weights = np.array([5.0] * len(y_lab) + [1.0] * len(y_ext))  # prefer lab gold

    # Group split by IP/24 (external) / scenario (lab)
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_idx, test_idx = next(gss.split(X, y, groups))
    # Further split train → train/val
    gss2 = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=7)
    tr2, va_rel = next(gss2.split(X[train_idx], y[train_idx], groups[train_idx]))
    val_idx = train_idx[va_rel]
    train_idx = train_idx[tr2]

    clf = RandomForestClassifier(
        n_estimators=800,
        max_depth=16,
        min_samples_leaf=2,
        n_jobs=-1,
        class_weight="balanced_subsample",
        random_state=42,
    )
    clf.fit(X[train_idx], y[train_idx], sample_weight=weights[train_idx])

    def eval_split(name: str, idx: np.ndarray) -> dict[str, Any]:
        pred = clf.predict(X[idx])
        true = y[idx]
        p, r, f, s = precision_recall_fscore_support(
            true, pred, labels=CLASSES, zero_division=0
        )
        per = {
            CLASSES[i]: {
                "precision": float(p[i]),
                "recall": float(r[i]),
                "f1": float(f[i]),
                "support": int(s[i]),
            }
            for i in range(len(CLASSES))
        }
        return {
            "split": name,
            "n": int(len(idx)),
            "accuracy": float(accuracy_score(true, pred)),
            "balanced_accuracy": float(balanced_accuracy_score(true, pred)),
            "macro_precision": float(np.mean(p)),
            "macro_recall": float(recall_score(true, pred, average="macro", zero_division=0)),
            "macro_f1": float(f1_score(true, pred, average="macro", zero_division=0)),
            "weighted_f1": float(f1_score(true, pred, average="weighted", zero_division=0)),
            "per_class": per,
            "confusion_matrix": {
                "class_order": CLASSES,
                "matrix": confusion_matrix(true, pred, labels=CLASSES).tolist(),
            },
            "origin_counts": dict(Counter(origins[idx].tolist())),
            "report": classification_report(true, pred, labels=CLASSES, zero_division=0),
        }

    val_metrics = eval_split("validation", val_idx)
    test_metrics = eval_split("test", test_idx)

    model_path = ART / "model.joblib"
    joblib.dump(
        {
            "model": clf,
            "feature_order": FEATURE_ORDER,
            "classes": list(clf.classes_),
            "representation": "behavior_raw",
            "release_id": "rf-openssh-ext-v1.0.0",
        },
        model_path,
    )

    summary = {
        "release_id": "rf-openssh-ext-v1.0.0",
        "created_at": utc_now(),
        "n_estimators": 800,
        "max_depth": 16,
        "total_samples": int(len(y)),
        "lab_samples": int(len(y_lab)),
        "external_samples": int(len(y_ext)),
        "train": int(len(train_idx)),
        "validation": int(len(val_idx)),
        "test": int(len(test_idx)),
        "label_counts_all": dict(Counter(y.tolist())),
        "validation": val_metrics,
        "test": test_metrics,
        "model_path": str(model_path.relative_to(ROOT)),
        "model_sha256": sha256_file(model_path),
    }
    (ART / "training_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (ART / "test_metrics.json").write_text(json.dumps(test_metrics, indent=2) + "\n", encoding="utf-8")
    (ART / "validation_metrics.json").write_text(json.dumps(val_metrics, indent=2) + "\n", encoding="utf-8")
    return summary


def write_inventory(ep_manifest: dict[str, Any], train_summary: dict[str, Any]) -> Path:
    # Disk sizes
    def du(path: Path) -> str:
        if not path.exists():
            return "0"
        total = 0
        if path.is_file():
            total = path.stat().st_size
        else:
            for p in path.rglob("*"):
                if p.is_file():
                    total += p.stat().st_size
        if total > 1 << 20:
            return f"{total / (1 << 20):.1f} MB"
        return f"{total / 1024:.1f} KB"

    inv = ROOT / "docs" / "EXTERNAL_DATA_INVENTORY.md"
    tm = train_summary["test"]
    pc = tm["per_class"]
    lines = [
        "# External dataset inventory & training report",
        "",
        f"**Generated:** {utc_now()}",
        "",
        "## 1. What is on this machine",
        "",
        "| Path | Size | Role |",
        "|---|---|---|",
        f"| `data/external/corpora/loghub_ssh_full/SSH.log` | {du(CORPUS_SSH)} | Loghub OpenSSH full raw logs (~655k lines) |",
        f"| `data/external/corpora/loghub_openssh/` | {du(ROOT / 'data/external/corpora/loghub_openssh')} | Loghub OpenSSH 2k + structured CSV |",
        f"| `data/external/corpora/linux_2k/` | {du(ROOT / 'data/external/corpora/linux_2k')} | Loghub-derived Linux_2k sample |",
        f"| `data/external/corpora/loghub_linux/` | {du(ROOT / 'data/external/corpora/loghub_linux')} | Loghub Linux.tar.gz extract |",
        f"| `data/external/corpora/loghub20_openssh/` | {du(ROOT / 'data/external/corpora/loghub20_openssh')} | Loghub-2.0 OpenSSH.zip extract |",
        f"| `data/external/downloads/` | {du(ROOT / 'data/external/downloads')} | Compressed downloads (SSH.tar.gz, etc.) |",
        f"| `data/external/derived/episodes/` | {du(DERIVED)} | Parsed episodes + features + heuristic labels |",
        f"| `data/features/p7/` | {du(LAB_P7)} | Lab supervised features (augmented) |",
        f"| `data/features/p7_baseline_75/` | {du(ROOT / 'data/features/p7_baseline_75')} | Frozen original 75 lab runs |",
        f"| `artifacts/external/rf-openssh-ext-v1.0.0/` | {du(ART)} | Large RF trained on lab+external |",
        "",
        "## 2. Sources (online)",
        "",
        "| Source ID | Origin | License / use | Used for train? |",
        "|---|---|---|---|",
        "| `loghub_ssh_full` | [Zenodo Loghub SSH.tar.gz](https://zenodo.org/records/8196385/files/SSH.tar.gz?download=1) | Research/academic with citation (Loghub) | Yes (heuristic labels) |",
        "| `loghub_openssh_2k` | [GitHub logpai/loghub](https://github.com/logpai/loghub) | Research/academic with citation | Yes |",
        "| `loghub_linux` | Zenodo Linux.tar.gz | Research/academic | Corpus kept (not primary SSH auth episodes) |",
        "| `loghub20_openssh` | [Zenodo Loghub-2.0 OpenSSH.zip](https://zenodo.org/records/8275861) | Research/academic | Stored for parsing experiments |",
        "| Kaggle SSH / auth anomalies | Kaggle | Needs `kaggle.json` — **not downloaded** (no API key) | No |",
        "| CIC-IDS2017 / CAM-LDS | P5 evaluated | Network-flow / ATT&CK mismatch — not merged | No (P5 Case B) |",
        "",
        "### Episode digest",
        "",
        f"- Episodes built: **{ep_manifest.get('episode_count')}**",
        f"- Heuristic label counts: `{ep_manifest.get('label_counts')}`",
        "",
        "## 3. How data was split for training",
        "",
        "| Split | Samples | Method |",
        "|---|---|---|",
        f"| Train | **{train_summary['train']}** | GroupShuffleSplit by IP/24 (external) + lab scenario groups |",
        f"| Validation | **{train_summary['validation']}** | From train remainder (group-safe) |",
        f"| Test | **{train_summary['test']}** | Held-out groups (20%) |",
        f"| Lab gold (weighted ×5) | {train_summary['lab_samples']} | Merged into pool |",
        f"| External episodes | {train_summary['external_samples']} | From Loghub SSH |",
        f"| **Total** | **{train_summary['total_samples']}** | |",
        "",
        "Group leakage control: same `/24` IP (or lab `scenario_id`) never appears in both train and test.",
        "",
        "## 4. TEST metrics (combined lab+external RF)",
        "",
        f"- Model: `RandomForest` n_estimators=800, max_depth=16 → `{train_summary['model_path']}`",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Accuracy | **{tm['accuracy']:.4f}** |",
        f"| Balanced accuracy | {tm['balanced_accuracy']:.4f} |",
        f"| Macro precision | {tm['macro_precision']:.4f} |",
        f"| Macro recall | **{tm['macro_recall']:.4f}** |",
        f"| Macro F1 | **{tm['macro_f1']:.4f}** |",
        f"| Weighted F1 | {tm['weighted_f1']:.4f} |",
        "",
        "| Class | Precision | Recall | F1 | Support |",
        "|---|---|---|---|---|",
    ]
    for c in CLASSES:
        m = pc[c]
        lines.append(
            f"| {c} | {m['precision']:.4f} | {m['recall']:.4f} | {m['f1']:.4f} | {m['support']} |"
        )
    lines.extend(
        [
            "",
            "### Validation snapshot",
            "",
            f"- Accuracy {train_summary['validation']['accuracy']:.4f} · Macro F1 {train_summary['validation']['macro_f1']:.4f} · Macro recall {train_summary['validation']['macro_recall']:.4f}",
            "",
            "## 5. Notes",
            "",
            "- External labels are **heuristic** (fail-window rules), not human-annotated gold.",
            "- Lab samples keep higher sample weight so controlled-lab ground truth still anchors the model.",
            "- Runtime P11/P12 still points at lab release `rf-behavior-lab-v1.1.0` unless you explicitly switch.",
            "- Cite Loghub when publishing results that used these corpora.",
            "",
        ]
    )
    inv.write_text("\n".join(lines), encoding="utf-8")
    return inv


def main() -> int:
    print("Building episodes from external SSH logs…", flush=True)
    man = build_episodes()
    print(json.dumps({"episodes": man["episode_count"], "labels": man["label_counts"]}, indent=2), flush=True)
    print("Training large RF on lab+external…", flush=True)
    summary = train_large()
    inv = write_inventory(man, summary)
    # Update registry pointer
    reg = ROOT / "artifacts" / "MODEL_REGISTRY.md"
    extra = f"""

## External large train (online corpora)

| Field | Value |
|---|---|
| Release | `rf-openssh-ext-v1.0.0` |
| Path | `artifacts/external/rf-openssh-ext-v1.0.0/` |
| TEST accuracy | {summary['test']['accuracy']:.4f} |
| TEST macro recall | {summary['test']['macro_recall']:.4f} |
| TEST macro F1 | {summary['test']['macro_f1']:.4f} |
| Inventory | `docs/EXTERNAL_DATA_INVENTORY.md` |
"""
    if reg.is_file():
        reg.write_text(reg.read_text(encoding="utf-8") + extra, encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": True,
                "episodes": man["episode_count"],
                "train_total": summary["total_samples"],
                "test_accuracy": summary["test"]["accuracy"],
                "test_macro_f1": summary["test"]["macro_f1"],
                "test_macro_recall": summary["test"]["macro_recall"],
                "inventory": str(inv.relative_to(ROOT)),
                "model": summary["model_path"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
