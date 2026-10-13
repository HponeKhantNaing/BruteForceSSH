"""Scenario-group-aware deterministic train/validation/test split."""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from typing import Any


CLASSES = ("NORMAL", "SUSPICIOUS", "BRUTE_FORCE")


def _stable_rank(seed: int, scenario_id: str) -> str:
    """Deterministic sort key from seed + scenario_id."""
    h = hashlib.sha256(f"{seed}:{scenario_id}".encode("utf-8")).hexdigest()
    return h


def allocate_group_counts(n_groups: int, train_f: float, val_f: float, test_f: float) -> tuple[int, int, int]:
    """
    Allocate integer group counts for train/val/test.
    Prefer at least 1 group per split when n_groups >= 3.
    """
    if n_groups < 3:
        raise ValueError(f"Need >=3 scenario groups for 3-way split, got {n_groups}")

    # Start with at least 1 each
    n_test = max(1, round(n_groups * test_f))
    n_val = max(1, round(n_groups * val_f))
    n_train = n_groups - n_test - n_val
    if n_train < 1:
        # shrink test then val
        while n_train < 1 and n_test > 1:
            n_test -= 1
            n_train = n_groups - n_test - n_val
        while n_train < 1 and n_val > 1:
            n_val -= 1
            n_train = n_groups - n_test - n_val
    if n_train < 1 or n_val < 1 or n_test < 1:
        raise ValueError(f"Cannot allocate 3-way split for n_groups={n_groups}")
    assert n_train + n_val + n_test == n_groups
    return n_train, n_val, n_test


def build_scenario_split(
    targets: list[dict[str, Any]],
    *,
    seed: int = 42,
    group_key: str = "scenario_id",
    train_fraction: float = 0.60,
    validation_fraction: float = 0.20,
    test_fraction: float = 0.20,
    require_all_classes: bool = True,
    min_groups_per_class: int = 3,
) -> dict[str, Any]:
    """
    Create a scenario-disjoint train/validation/test split.

    Same scenario_id never appears in more than one split.
    """
    # Validate scenario → single label
    scen_to_label: dict[str, str] = {}
    scen_to_samples: dict[str, list[str]] = defaultdict(list)
    label_to_scenarios: dict[str, list[str]] = defaultdict(list)

    for t in targets:
        sc = t[group_key]
        lab = t["target_label"]
        sid = t["sample_id"]
        if sc in scen_to_label and scen_to_label[sc] != lab:
            raise RuntimeError(f"Scenario {sc} maps to multiple labels: {scen_to_label[sc]} vs {lab}")
        scen_to_label[sc] = lab
        scen_to_samples[sc].append(sid)

    for sc, lab in scen_to_label.items():
        label_to_scenarios[lab].append(sc)

    for lab in CLASSES:
        n = len(label_to_scenarios.get(lab, []))
        if n < min_groups_per_class:
            raise RuntimeError(
                f"Class {lab} has only {n} scenario groups; need >= {min_groups_per_class}"
            )

    train_sc: list[str] = []
    val_sc: list[str] = []
    test_sc: list[str] = []

    for lab in CLASSES:
        scenarios = sorted(label_to_scenarios[lab], key=lambda s: _stable_rank(seed, s))
        n_train, n_val, n_test = allocate_group_counts(
            len(scenarios), train_fraction, validation_fraction, test_fraction
        )
        train_sc.extend(scenarios[:n_train])
        val_sc.extend(scenarios[n_train : n_train + n_val])
        test_sc.extend(scenarios[n_train + n_val :])

    def samples_for(scen_list: list[str]) -> list[str]:
        out: list[str] = []
        for sc in sorted(scen_list):
            out.extend(sorted(scen_to_samples[sc]))
        return out

    train_ids = samples_for(train_sc)
    val_ids = samples_for(val_sc)
    test_ids = samples_for(test_sc)

    id_to_label = {t["sample_id"]: t["target_label"] for t in targets}

    def class_counts(ids: list[str]) -> dict[str, int]:
        return dict(Counter(id_to_label[i] for i in ids))

    # invariants
    s_train, s_val, s_test = set(train_ids), set(val_ids), set(test_ids)
    if s_train & s_val or s_train & s_test or s_val & s_test:
        raise RuntimeError("Sample overlap across splits")
    ss_train, ss_val, ss_test = set(train_sc), set(val_sc), set(test_sc)
    if ss_train & ss_val or ss_train & ss_test or ss_val & ss_test:
        raise RuntimeError("Scenario overlap across splits")
    if len(s_train) + len(s_val) + len(s_test) != len(targets):
        raise RuntimeError("Not all samples assigned")

    if require_all_classes:
        for name, counts in (
            ("train", class_counts(train_ids)),
            ("validation", class_counts(val_ids)),
            ("test", class_counts(test_ids)),
        ):
            for lab in CLASSES:
                if counts.get(lab, 0) < 1:
                    raise RuntimeError(f"{name} missing class {lab}: {counts}")

    return {
        "schema_version": "1.0",
        "split_version": "p8-split-v1",
        "random_seed": seed,
        "group_key": group_key,
        "train": {
            "sample_ids": train_ids,
            "scenario_ids": sorted(train_sc),
            "class_counts": class_counts(train_ids),
        },
        "validation": {
            "sample_ids": val_ids,
            "scenario_ids": sorted(val_sc),
            "class_counts": class_counts(val_ids),
        },
        "test": {
            "sample_ids": test_ids,
            "scenario_ids": sorted(test_sc),
            "class_counts": class_counts(test_ids),
        },
    }


def scenario_audit(targets: list[dict[str, Any]], group_key: str = "scenario_id") -> dict[str, Any]:
    scen_to_label: dict[str, str] = {}
    scen_counts: dict[str, int] = Counter()
    label_scenarios: dict[str, list[str]] = defaultdict(list)
    batches = Counter(t.get("split_group_batch") for t in targets)
    for t in targets:
        sc = t[group_key]
        lab = t["target_label"]
        scen_counts[sc] += 1
        if sc in scen_to_label and scen_to_label[sc] != lab:
            raise RuntimeError(f"Scenario {sc} multi-label")
        if sc not in scen_to_label:
            scen_to_label[sc] = lab
            label_scenarios[lab].append(sc)
    return {
        "unique_scenario_ids": len(scen_to_label),
        "scenario_ids_per_target": {k: sorted(v) for k, v in label_scenarios.items()},
        "runs_per_scenario": dict(sorted(scen_counts.items())),
        "unique_batch_groups": len(batches),
        "batch_counts": dict(batches),
        "scenario_single_label_ok": True,
    }
