"""Ingest P11 prediction JSONL into P12 SQLite + alert decisions."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from presentation.alert_policy import evaluate_alert
from presentation.state_store import StateStore, event_key_for


REQUIRED_FIELDS = [
    "release_id",
    "episode_id",
    "source_id",
    "snapshot_type",
    "predicted_label",
    "class_probabilities",
    "probability_type",
    "event_timestamp",
    "attempt_count",
]


class P11Ingestor:
    def __init__(self, root: Path, cfg: dict[str, Any], store: StateStore):
        self.root = root
        self.cfg = cfg
        self.store = store
        self.pred_path = root / cfg["p11"]["predictions_path"]
        self.events_path = root / cfg["p11"]["runtime_events_path"]
        self.policy = cfg["alert_policy"]
        self.errors = 0
        self.ingested = 0
        self.alerts_created = 0

    def _inode(self) -> str:
        try:
            return str(self.pred_path.stat().st_ino)
        except FileNotFoundError:
            return ""

    def first_start_backfill(self) -> dict[str, Any]:
        """Ingest all existing predictions with alert_eligible=False."""
        if self.store.get_meta("first_start_completed") == "1":
            return {"skipped": True, "reason": "already_initialized"}
        if not self.pred_path.is_file():
            self.store.set_meta("first_start_completed", "1")
            self.store.set_meta("prediction_file_offset", "0")
            self.store._conn.commit()
            return {"historical_found": 0, "ingested": 0, "alerts": 0}

        text = self.pred_path.read_text(encoding="utf-8")
        offset = 0
        found = 0
        ingested = 0
        for line in text.splitlines(keepends=True):
            offset += len(line.encode("utf-8"))
            raw = line.strip()
            if not raw:
                continue
            found += 1
            try:
                pred = json.loads(raw)
            except json.JSONDecodeError:
                self.errors += 1
                continue
            ok = self._ingest_one(
                pred,
                historical_backfill=True,
                alert_eligible=False,
                file_offset=offset,
                file_inode=self._inode(),
            )
            if ok.get("inserted"):
                ingested += 1
        self.store.set_meta("first_start_completed", "1")
        self.store.set_meta("prediction_file_offset", str(offset))
        self.store.set_meta("prediction_file_inode", self._inode())
        self.store._conn.commit()
        return {
            "historical_found": found,
            "ingested": ingested,
            "discord_alerts_from_backfill": 0,
        }

    def poll_once(self) -> dict[str, Any]:
        if not self.pred_path.is_file():
            return {"read": 0, "inserted": 0}
        st = self.pred_path.stat()
        inode = str(st.st_ino)
        saved_inode = self.store.get_meta("prediction_file_inode") or ""
        offset = int(self.store.get_meta("prediction_file_offset") or "0")
        if saved_inode and saved_inode != inode:
            offset = 0
            self.store.set_meta("prediction_file_inode", inode)
        if st.st_size < offset:
            offset = 0
        inserted = 0
        read = 0
        with self.pred_path.open("rb") as f:
            f.seek(offset)
            while True:
                line = f.readline()
                if not line:
                    break
                offset = f.tell()
                raw = line.decode("utf-8", errors="replace").strip()
                if not raw:
                    self.store.set_meta("prediction_file_offset", str(offset))
                    self.store._conn.commit()
                    continue
                read += 1
                try:
                    pred = json.loads(raw)
                except json.JSONDecodeError:
                    self.errors += 1
                    self.store.set_meta("prediction_file_offset", str(offset))
                    self.store._conn.commit()
                    continue
                result = self._ingest_one(
                    pred,
                    historical_backfill=False,
                    alert_eligible=True,
                    file_offset=offset,
                    file_inode=inode,
                )
                if result.get("inserted"):
                    inserted += 1
                    if result.get("alert") and result["alert"].get("send_discord"):
                        self.alerts_created += 1
        return {"read": read, "inserted": inserted, "errors": self.errors}

    def _ingest_one(
        self,
        pred: dict[str, Any],
        *,
        historical_backfill: bool,
        alert_eligible: bool,
        file_offset: int,
        file_inode: str,
    ) -> dict[str, Any]:
        missing = [k for k in REQUIRED_FIELDS if k not in pred]
        if missing:
            self.errors += 1
            return {"inserted": False, "error": "SCHEMA_MISMATCH", "missing": missing}
        # Privacy: reject if source_id looks like raw IPv4
        src = str(pred.get("source_id") or "")
        if src.count(".") == 3 and all(p.isdigit() for p in src.split(".")):
            self.errors += 1
            return {"inserted": False, "error": "raw_ip_rejected"}

        last_sent = self.store.last_sent_for_source(str(pred.get("source_id")))
        # For same-label cooldown, prefer last sent same label; escalation uses any last for source
        last_same = self.store.last_sent_for_source_label(
            str(pred.get("source_id")), str(pred.get("predicted_label"))
        )
        # Policy uses last_sent for cooldown/escalation — use most recent sent for source
        consecutive = self.store.consecutive_prefix_brute(str(pred.get("episode_id")))
        # Include current if it's BRUTE_FORCE prefix (not yet stored)
        if (
            pred.get("snapshot_type") == "ACTIVE_PREFIX"
            and pred.get("predicted_label") == "BRUTE_FORCE"
        ):
            consecutive += 1

        decision = evaluate_alert(
            pred,
            policy_cfg=self.policy,
            alert_eligible=alert_eligible,
            last_sent=last_sent,
            now_epoch=time.time(),
            consecutive_prefix_brute=consecutive,
        )
        # If Discord disabled globally, convert PENDING to NOT_REQUIRED for send,
        # but still record decision. Actual env checked by service layer —
        # here we keep PENDING so outbox can send when enabled.
        result = self.store.ingest_prediction(
            pred,
            historical_backfill=historical_backfill,
            alert_eligible=alert_eligible,
            policy_version=str(self.policy.get("version", "p12-alert-v1")),
            alert_decision={
                "decision": decision.decision,
                "delivery_state": decision.delivery_state,
                "severity": decision.severity,
                "alert_phase": decision.alert_phase,
                "send_discord": decision.send_discord,
                "suppressed_reason": decision.suppressed_reason,
            },
            file_offset=file_offset,
            file_inode=file_inode,
        )
        if result.get("inserted"):
            self.ingested += 1
        return result
