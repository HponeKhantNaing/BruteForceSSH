"""SQLite durable state for P12 predictions, alerts, and checkpoints."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "p12-db-v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def event_key_for(pred: dict[str, Any]) -> str:
    payload = {
        "release_id": pred.get("release_id"),
        "episode_id": pred.get("episode_id"),
        "snapshot_type": pred.get("snapshot_type"),
        "attempt_count": pred.get("attempt_count"),
        "event_timestamp": pred.get("event_timestamp"),
        "predicted_label": pred.get("predicted_label"),
    }
    return sha256_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def alert_key_for(policy_version: str, event_key: str, alert_phase: str) -> str:
    payload = {
        "alert_policy_version": policy_version,
        "event_key": event_key,
        "alert_phase": alert_phase,
    }
    return sha256_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))


class StateStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=30.0)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA busy_timeout=5000;")
        self._init_schema()

    def close(self) -> None:
        self._conn.close()

    def _init_schema(self) -> None:
        c = self._conn
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS predictions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              event_key TEXT NOT NULL UNIQUE,
              release_id TEXT,
              episode_id TEXT,
              source_id TEXT,
              snapshot_type TEXT,
              provisional INTEGER,
              final INTEGER,
              attempt_count INTEGER,
              event_timestamp TEXT,
              predicted_label TEXT,
              score_normal REAL,
              score_suspicious REAL,
              score_brute_force REAL,
              probability_type TEXT,
              historical_backfill INTEGER,
              alert_eligible INTEGER,
              ingested_at TEXT,
              raw_record_hash TEXT
            );
            CREATE TABLE IF NOT EXISTS alerts (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              alert_key TEXT NOT NULL UNIQUE,
              event_key TEXT NOT NULL,
              policy_version TEXT,
              episode_id TEXT,
              source_id TEXT,
              predicted_label TEXT,
              severity TEXT,
              alert_phase TEXT,
              decision TEXT,
              delivery_state TEXT,
              created_at TEXT,
              queued_at TEXT,
              sent_at TEXT,
              sent_at_epoch REAL,
              retry_count INTEGER DEFAULT 0,
              last_http_status INTEGER,
              last_error TEXT,
              suppressed_reason TEXT,
              discord_message_id TEXT
            );
            CREATE TABLE IF NOT EXISTS runtime_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              event_key TEXT UNIQUE,
              event_type TEXT,
              timestamp TEXT,
              payload_json TEXT,
              ingested_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_pred_label ON predictions(predicted_label);
            CREATE INDEX IF NOT EXISTS idx_pred_snap ON predictions(snapshot_type);
            CREATE INDEX IF NOT EXISTS idx_alert_state ON alerts(delivery_state);
            """
        )
        if self.get_meta("schema_version") is None:
            self.set_meta("schema_version", SCHEMA_VERSION)
            self.set_meta("first_start_completed", "0")
            self.set_meta("prediction_file_offset", "0")
            self.set_meta("prediction_file_inode", "")
        c.commit()

    def get_meta(self, key: str) -> str | None:
        row = self._conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return None if row is None else str(row["value"])

    def set_meta(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    def ingest_prediction(
        self,
        pred: dict[str, Any],
        *,
        historical_backfill: bool,
        alert_eligible: bool,
        policy_version: str,
        alert_decision: dict[str, Any],
        file_offset: int,
        file_inode: str,
    ) -> dict[str, Any]:
        """Atomic: insert prediction (if new) + alert decision + checkpoint."""
        ek = event_key_for(pred)
        probs = pred.get("class_probabilities") or {}
        raw_hash = sha256_text(json.dumps(pred, sort_keys=True, separators=(",", ":")))
        now = utc_now()
        cur = self._conn.cursor()
        try:
            cur.execute("BEGIN")
            cur.execute(
                """
                INSERT OR IGNORE INTO predictions(
                  event_key, release_id, episode_id, source_id, snapshot_type,
                  provisional, final, attempt_count, event_timestamp, predicted_label,
                  score_normal, score_suspicious, score_brute_force, probability_type,
                  historical_backfill, alert_eligible, ingested_at, raw_record_hash
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    ek,
                    pred.get("release_id"),
                    pred.get("episode_id"),
                    pred.get("source_id"),
                    pred.get("snapshot_type"),
                    1 if pred.get("provisional") else 0,
                    1 if pred.get("final") else 0,
                    int(pred.get("attempt_count") or 0),
                    pred.get("event_timestamp"),
                    pred.get("predicted_label"),
                    float(probs.get("NORMAL") or 0.0),
                    float(probs.get("SUSPICIOUS") or 0.0),
                    float(probs.get("BRUTE_FORCE") or 0.0),
                    pred.get("probability_type") or "uncalibrated",
                    1 if historical_backfill else 0,
                    1 if alert_eligible else 0,
                    now,
                    raw_hash,
                ),
            )
            inserted = cur.rowcount == 1
            alert_row = None
            if inserted:
                ak = alert_key_for(policy_version, ek, alert_decision["alert_phase"])
                cur.execute(
                    """
                    INSERT OR IGNORE INTO alerts(
                      alert_key, event_key, policy_version, episode_id, source_id,
                      predicted_label, severity, alert_phase, decision, delivery_state,
                      created_at, queued_at, suppressed_reason, retry_count
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,0)
                    """,
                    (
                        ak,
                        ek,
                        policy_version,
                        pred.get("episode_id"),
                        pred.get("source_id"),
                        pred.get("predicted_label"),
                        alert_decision["severity"],
                        alert_decision["alert_phase"],
                        alert_decision["decision"],
                        alert_decision["delivery_state"],
                        now,
                        now if alert_decision.get("send_discord") else None,
                        alert_decision.get("suppressed_reason"),
                    ),
                )
                alert_row = {
                    "alert_key": ak,
                    "delivery_state": alert_decision["delivery_state"],
                    "send_discord": bool(alert_decision.get("send_discord")),
                }
            self.set_meta("prediction_file_offset", str(file_offset))
            self.set_meta("prediction_file_inode", file_inode)
            cur.execute("COMMIT")
            return {"inserted": inserted, "event_key": ek, "alert": alert_row}
        except Exception:
            cur.execute("ROLLBACK")
            raise

    def last_sent_for_source_label(self, source_id: str, label: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT severity, sent_at_epoch, predicted_label, source_id
            FROM alerts
            WHERE source_id=? AND predicted_label=? AND delivery_state='SENT'
            ORDER BY sent_at_epoch DESC LIMIT 1
            """,
            (source_id, label),
        ).fetchone()
        # For cooldown we also need last sent for same source across labels for escalation —
        # policy compares last sent for same source+label; escalation uses last any for source.
        return dict(row) if row else None

    def last_sent_for_source(self, source_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT severity, sent_at_epoch, predicted_label, source_id
            FROM alerts
            WHERE source_id=? AND delivery_state='SENT'
            ORDER BY sent_at_epoch DESC LIMIT 1
            """,
            (source_id,),
        ).fetchone()
        return dict(row) if row else None

    def consecutive_prefix_brute(self, episode_id: str) -> int:
        rows = self._conn.execute(
            """
            SELECT predicted_label, snapshot_type FROM predictions
            WHERE episode_id=? ORDER BY id DESC LIMIT 20
            """,
            (episode_id,),
        ).fetchall()
        n = 0
        for r in rows:
            if r["snapshot_type"] == "ACTIVE_PREFIX" and r["predicted_label"] == "BRUTE_FORCE":
                n += 1
            else:
                break
        return n

    def pending_alerts(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT a.*, p.score_normal, p.score_suspicious, p.score_brute_force,
                   p.attempt_count, p.event_timestamp, p.release_id, p.snapshot_type,
                   p.provisional, p.final, p.probability_type
            FROM alerts a
            JOIN predictions p ON p.event_key = a.event_key
            WHERE a.delivery_state IN ('PENDING','RETRY_WAIT')
            ORDER BY a.id ASC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_alert_sending(self, alert_key: str) -> None:
        self._conn.execute(
            "UPDATE alerts SET delivery_state='SENDING' WHERE alert_key=?",
            (alert_key,),
        )
        self._conn.commit()

    def mark_alert_sent(self, alert_key: str, *, http_status: int | None, message_id: str | None) -> None:
        now = utc_now()
        self._conn.execute(
            """
            UPDATE alerts SET delivery_state='SENT', sent_at=?, sent_at_epoch=?,
              last_http_status=?, discord_message_id=?, last_error=NULL
            WHERE alert_key=?
            """,
            (now, time.time(), http_status, message_id, alert_key),
        )
        self._conn.commit()

    def mark_alert_retry(self, alert_key: str, *, http_status: int | None, error: str) -> None:
        self._conn.execute(
            """
            UPDATE alerts SET delivery_state='RETRY_WAIT', retry_count=retry_count+1,
              last_http_status=?, last_error=?
            WHERE alert_key=?
            """,
            (http_status, error[:500], alert_key),
        )
        self._conn.commit()

    def mark_alert_failed(self, alert_key: str, *, http_status: int | None, error: str) -> None:
        self._conn.execute(
            """
            UPDATE alerts SET delivery_state='FAILED_PERMANENT', retry_count=retry_count+1,
              last_http_status=?, last_error=?
            WHERE alert_key=?
            """,
            (http_status, error[:500], alert_key),
        )
        self._conn.commit()

    def _count(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        row = self._conn.execute(sql, params).fetchone()
        if row is None:
            return 0
        try:
            return int(row["n"])
        except (KeyError, IndexError, TypeError):
            return int(row[0]) if len(row) else 0

    def counts(self) -> dict[str, Any]:
        pred_n = self._count("SELECT COUNT(*) AS n FROM predictions")
        by_label = {
            r["predicted_label"]: r["n"]
            for r in self._conn.execute(
                "SELECT predicted_label, COUNT(*) AS n FROM predictions GROUP BY predicted_label"
            )
            if r["predicted_label"] is not None
        }
        alert_n = self._count("SELECT COUNT(*) AS n FROM alerts")
        sent = self._count("SELECT COUNT(*) AS n FROM alerts WHERE delivery_state='SENT'")
        pending = self._count(
            "SELECT COUNT(*) AS n FROM alerts WHERE delivery_state IN ('PENDING','RETRY_WAIT','SENDING')"
        )
        failed = self._count(
            "SELECT COUNT(*) AS n FROM alerts WHERE delivery_state='FAILED_PERMANENT'"
        )
        return {
            "predictions": pred_n,
            "by_label": by_label,
            "alerts": alert_n,
            "alerts_sent": sent,
            "alerts_pending": pending,
            "alerts_failed": failed,
        }

    def list_predictions(
        self,
        *,
        label: str | None = None,
        snapshot_type: str | None = None,
        alerts_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))
        q = """
          SELECT p.*, a.delivery_state AS alert_status, a.decision AS alert_decision, a.severity
          FROM predictions p
          LEFT JOIN alerts a ON a.event_key = p.event_key
          WHERE 1=1
        """
        args: list[Any] = []
        if label:
            q += " AND p.predicted_label=?"
            args.append(label)
        if snapshot_type:
            q += " AND p.snapshot_type=?"
            args.append(snapshot_type)
        if alerts_only:
            q += " AND a.delivery_state IN ('SENT','PENDING','RETRY_WAIT','SENDING','SUPPRESSED_COOLDOWN')"
        q += " ORDER BY p.id DESC LIMIT ? OFFSET ?"
        args.extend([limit, offset])
        return [dict(r) for r in self._conn.execute(q, args).fetchall()]

    def list_alerts(self, *, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))
        rows = self._conn.execute(
            "SELECT * FROM alerts ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]

    def recent_activity_buckets(self, minutes: int = 30) -> list[dict[str, Any]]:
        # Simple per-minute bucket from event_timestamp prefix
        rows = self._conn.execute(
            """
            SELECT substr(event_timestamp, 1, 16) AS bucket, predicted_label, COUNT(*) AS n
            FROM predictions
            WHERE event_timestamp IS NOT NULL
            GROUP BY bucket, predicted_label
            ORDER BY bucket DESC
            LIMIT ?
            """,
            (minutes * 3,),
        ).fetchall()
        return [dict(r) for r in rows]

    def insert_runtime_event(self, event: dict[str, Any]) -> bool:
        ek = sha256_text(json.dumps(event, sort_keys=True, separators=(",", ":")))
        cur = self._conn.execute(
            """
            INSERT OR IGNORE INTO runtime_events(event_key, event_type, timestamp, payload_json, ingested_at)
            VALUES (?,?,?,?,?)
            """,
            (
                ek,
                event.get("event"),
                event.get("timestamp"),
                json.dumps(event, sort_keys=True),
                utc_now(),
            ),
        )
        self._conn.commit()
        return cur.rowcount == 1
