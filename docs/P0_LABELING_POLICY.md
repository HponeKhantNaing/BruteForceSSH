# P0 — Labeling Policy & Leakage Prevention

**Phase:** P0 — Project Foundation  
**Status:** Policy design only — no labeled production dataset in P0

---

## 1. Label set

Every supervised row uses exactly one of:

```text
NORMAL
SUSPICIOUS
BRUTE_FORCE
```

Labels describe **behavioral context**, not a single keyword.

---

## 2. Label definitions for annotators / scenario designers

### 2.1 NORMAL

Use when activity is consistent with legitimate use or an isolated mistake.

**Examples:**

- A normal successful login
- Session open / close associated with normal use
- An occasional isolated failed password
- Low-frequency failures without multi-user spraying or burst intensity

**Non-example:** Do not escalate a single mistyped password to `BRUTE_FORCE`.

### 2.2 SUSPICIOUS

Use when behavior exceeds expected normal patterns but evidence is incomplete for confirmed brute-force.

**Examples:**

- Multiple failures beyond ordinary mistype patterns, yet below sustained brute-force intensity
- Short bursts that are unusual but not conclusive
- Attempts against several usernames without extreme rate
- Ambiguous failure→success sequences that warrant review

`SUSPICIOUS` means “operator attention,” not “proven attack.”

### 2.3 BRUTE_FORCE

Use when repeated high-rate authentication failures occur under a controlled attack scenario **and** contextual evidence supports that interpretation.

Evidence may combine:

- elevated `failed_count_30s` / `failed_count_60s` / `failed_count_5m`
- elevated `unique_users_60s`
- elevated `attempt_rate`
- short `time_since_previous_attempt` across many tries
- scenario intent recorded as brute-force simulation against the lab server

**Forbidden labeling rule:**

```text
"Failed password" = BRUTE_FORCE
```

This rule is explicitly banned.

---

## 3. Labeling workflow (future)

1. Design a scenario with intended class (`scenario_id`, intent notes).
2. Collect raw logs only from the project lab (or generate marked synthetic logs).
3. Parse events and compute behavioral features.
4. Assign labels using:
   - scenario intent, plus
   - per-event behavioral evidence, plus
   - the class definitions above
5. Review borderline cases (especially `SUSPICIOUS` vs neighbors).
6. Store `label`, `scenario_id`, and `data_source` on every row.

Scenario intent alone is not enough for every line: early setup lines inside a brute-force scenario may still be `NORMAL` if they precede attack traffic. Document edge-case decisions.

---

## 4. Rules for avoiding incorrect labels

| Bad practice | Correct practice |
|---|---|
| Keyword → class mapping | Use windows + scenario context |
| Labeling without `scenario_id` | Always attach scenario identity |
| Copying public dataset “attack” labels blindly | Map only after class-definition review (P5) |
| Letting dashboard operators silently rewrite historical gold labels during live demos | Keep gold labels immutable; runtime uses `prediction` |
| Using Discord alert state as ground truth | Alerts are outputs, not labels |

---

## 5. Baseline thresholds vs labels

Configurable thresholds in `config/example.yaml` are **helpers** for scenario design and later rule-assisted labeling — not a substitute for the ML model, and not immutable truth.

They are baseline values to be validated experimentally. If thresholds and human/scenario labels disagree systematically, revise thresholds or labeling guidance explicitly in a later phase decision note.

---

## 6. Data leakage prevention

### 6.1 The risk

Authentication attacks are multi-event processes. If events from the **same attack session / scenario** are randomly split so that some lines land in training and others in testing, the model can memorize session-specific artifacts and produce **over-optimistic** metrics that will not hold in real monitoring.

### 6.2 Required split strategy (future)

Prefer scenario-aware partitions:

```text
Training scenarios
Validation scenarios
Independent test scenarios
```

Split keys (in priority order):

```text
scenario_id
session (if defined)
time period
```

Avoid as the primary strategy:

```text
random line-level train_test_split on all rows
```

### 6.3 Practical rules

1. All rows sharing a `scenario_id` belong to exactly one split bucket.
2. Brute-force scenarios used for training must not leak into the independent test set.
3. Normal scenarios for testing should include isolated failures to verify that failures ≠ automatic attack predictions.
4. If public data is added later, evaluate it as a separate domain bucket when possible.
5. Record the split manifest next to processed datasets (P6+).

### 6.4 Why this matters

Leakage hides the real difficulty of detecting unseen attack sessions. Scenario-held-out evaluation better matches the deployment question:

> Given a new sequence of authentication behavior from the lab monitor, can the system classify it usefully?

---

## 7. Quality checks before training (future checklist)

- [ ] No row missing `label` or `scenario_id`
- [ ] No forbidden keyword-only labeling rule used
- [ ] Class counts reviewed; severe imbalance documented
- [ ] Synthetic rows marked `data_source=synthetic`
- [ ] Split manifest is scenario-safe
- [ ] IP memorization mitigations reviewed
