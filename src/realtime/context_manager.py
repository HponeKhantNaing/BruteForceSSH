"""Per-source activity episode state machine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from features.window_features import parse_ts
from realtime.attempt_stream import sanitize_attempt_for_features
from realtime.feature_state import compute_episode_features


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Episode:
    episode_id: str
    source_token: str
    state: str = "ACTIVE"  # ACTIVE | CLOSING | CLOSED
    attempts: list[dict[str, Any]] = field(default_factory=list)
    started_at: str | None = None
    last_attempt_at: str | None = None
    user_map: dict[str, str] = field(default_factory=dict)
    _user_seq: int = 0
    close_reason: str | None = None

    def map_user(self, username: str | None) -> str | None:
        if not username:
            return None
        if username not in self.user_map:
            self._user_seq += 1
            self.user_map[username] = f"USR_RUNTIME_{self._user_seq:03d}"
        return self.user_map[username]


@dataclass
class ContextManager:
    idle_timeout_seconds: float
    max_episode_duration_seconds: float
    source_prefix: str = "SRC_RUNTIME_"

    _sources: dict[str, str] = field(default_factory=dict)
    _source_seq: int = 0
    _episode_seq: dict[str, int] = field(default_factory=dict)
    episodes: dict[str, Episode] = field(default_factory=dict)  # source_token -> active
    closed: list[Episode] = field(default_factory=list)

    def source_token(self, raw_source: str | None) -> str:
        key = raw_source or "UNKNOWN_SOURCE"
        if key not in self._sources:
            self._source_seq += 1
            self._sources[key] = f"{self.source_prefix}{self._source_seq:03d}"
        return self._sources[key]

    def active_count(self) -> int:
        return len(self.episodes)

    def on_attempt(
        self,
        attempt: dict[str, Any],
        *,
        as_of: datetime | None = None,
    ) -> tuple[Episode, list[Episode]]:
        """
        Add logical attempt to the correct per-source episode.
        Returns (current_episode, newly_closed_episodes).
        """
        as_of = as_of or _utc_now()
        closed_now = self.check_timeouts(as_of=as_of)

        raw_source = attempt.get("source_ip") or attempt.get("source_id")
        token = self.source_token(str(raw_source) if raw_source else None)
        ep = self.episodes.get(token)

        ts = attempt.get("started_at")
        if ep is None:
            ep = self._start_episode(token, ts)
        else:
            # Max duration relative to first attempt timestamp
            if ep.started_at and ts:
                t0 = parse_ts(ep.started_at)
                t1 = parse_ts(ts)
                if t0 and t1 and (t1 - t0).total_seconds() > self.max_episode_duration_seconds:
                    ep.close_reason = "MAX_DURATION"
                    ep.state = "CLOSED"
                    closed_now.append(ep)
                    self.closed.append(ep)
                    del self.episodes[token]
                    ep = self._start_episode(token, ts)

        raw_user = attempt.get("username_raw") or attempt.get("user_id")
        user_tok = ep.map_user(str(raw_user) if raw_user else None)
        clean = sanitize_attempt_for_features(attempt, user_id=user_tok or "USR_RUNTIME_000", source_token=token)
        clean["attempt_order"] = len(ep.attempts) + 1
        ep.attempts.append(clean)
        if ep.started_at is None:
            ep.started_at = ts
        ep.last_attempt_at = ts
        self.episodes[token] = ep
        return ep, closed_now

    def _start_episode(self, source_token: str, ts: str | None) -> Episode:
        seq = self._episode_seq.get(source_token, 0) + 1
        self._episode_seq[source_token] = seq
        return Episode(
            episode_id=f"EP_{source_token}_{seq:03d}",
            source_token=source_token,
            started_at=ts,
            last_attempt_at=ts,
        )

    def check_timeouts(self, *, as_of: datetime | None = None) -> list[Episode]:
        as_of = as_of or _utc_now()
        closed_now: list[Episode] = []
        for token, ep in list(self.episodes.items()):
            last = parse_ts(ep.last_attempt_at)
            if last is None:
                continue
            idle = (as_of - last).total_seconds()
            # Use event-time idle when as_of is log-derived; wall clock for live monitor.
            if idle >= self.idle_timeout_seconds:
                ep.close_reason = "IDLE_TIMEOUT"
                ep.state = "CLOSED"
                closed_now.append(ep)
                self.closed.append(ep)
                del self.episodes[token]
                continue
            start = parse_ts(ep.started_at)
            if start and (as_of - start).total_seconds() >= self.max_episode_duration_seconds:
                ep.close_reason = "MAX_DURATION"
                ep.state = "CLOSED"
                closed_now.append(ep)
                self.closed.append(ep)
                del self.episodes[token]
        return closed_now

    def close_all(self, reason: str) -> list[Episode]:
        closed_now: list[Episode] = []
        for token, ep in list(self.episodes.items()):
            ep.close_reason = reason
            ep.state = "CLOSED"
            closed_now.append(ep)
            self.closed.append(ep)
            del self.episodes[token]
        return closed_now

    def reset_all(self, reason: str = "LOG_RESET") -> list[Episode]:
        return self.close_all(reason)

    def features_for(
        self,
        episode: Episode,
        *,
        run: dict[str, Any] | None = None,
        sequence: dict[str, Any] | None = None,
        ordered_features: list[str],
    ) -> dict[str, float]:
        return compute_episode_features(
            episode.attempts,
            run=run,
            sequence=sequence,
            ordered_features=ordered_features,
        )
