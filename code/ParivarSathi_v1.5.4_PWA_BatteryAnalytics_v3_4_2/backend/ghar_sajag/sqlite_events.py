"""SQLite-backed mapping for canonical CloudEvent history."""
from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterable, Iterator, MutableMapping

from .model import CloudEvent


class SQLiteEventMap(MutableMapping[tuple[str, str], CloudEvent]):
    """Persist CloudEvents while preserving the InMemoryStore.events mapping API."""

    def __init__(self, connection: sqlite3.Connection, lock: threading.RLock | None = None) -> None:
        self.db = connection
        self.lock = lock or threading.RLock()

    def __getitem__(self, key: tuple[str, str]) -> CloudEvent:
        home_id, event_id = key
        with self.lock:
            row = self.db.execute(
                "SELECT * FROM events WHERE home_id=? AND event_id=?",
                (home_id, event_id),
            ).fetchone()
        if row is None:
            raise KeyError(key)
        return self._row_to_event(row)

    def __setitem__(self, key: tuple[str, str], event: CloudEvent) -> None:
        home_id, event_id = key
        if home_id != event.home_id or event_id != event.event_id:
            raise KeyError("event_key_mismatch")
        payload_json = json.dumps(event.payload, sort_keys=True, separators=(",", ":"))
        source_type = self._source_type(event.kind)
        with self.lock, self.db:
            self.db.execute(
                """
                INSERT OR REPLACE INTO events(
                    event_id,home_id,source_id,source_type,node_id,room_id,session_id,sequence_number,
                    sensor_type,event_type,location,occurred_at,received_at,hub_received_at,
                    uncertainty_ms,is_test,payload_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    event.event_id,
                    event.home_id,
                    f"{event.home_id}:{event.event_id}",
                    source_type,
                    None,
                    None,
                    0,
                    0,
                    event.kind,
                    event.kind,
                    event.location,
                    event.occurred_at,
                    event.server_received_at,
                    event.hub_received_at,
                    event.uncertainty_s * 1000,
                    1 if event.is_test else 0,
                    payload_json,
                ),
            )

    def __delitem__(self, key: tuple[str, str]) -> None:
        home_id, event_id = key
        with self.lock, self.db:
            deleted = self.db.execute("DELETE FROM events WHERE home_id=? AND event_id=?", (home_id, event_id)).rowcount
        if deleted == 0:
            raise KeyError(key)

    def __iter__(self) -> Iterator[tuple[str, str]]:
        with self.lock:
            rows = self.db.execute("SELECT home_id,event_id FROM events ORDER BY home_id,event_id").fetchall()
        return iter((row["home_id"], row["event_id"]) for row in rows)

    def __len__(self) -> int:
        with self.lock:
            return int(self.db.execute("SELECT COUNT(*) FROM events").fetchone()[0])

    def items(self) -> Iterable[tuple[tuple[str, str], CloudEvent]]:  # type: ignore[override]
        with self.lock:
            rows = self.db.execute("SELECT * FROM events ORDER BY occurred_at,event_id").fetchall()
        return [((row["home_id"], row["event_id"]), self._row_to_event(row)) for row in rows]

    def home_events(self, home_id: str, *, kinds=None, start=None, end=None,
                    include_test=True, newest_first=False, limit=None, payload_reasons=None) -> list[CloudEvent]:
        """Use the durable history index instead of materializing every home's events."""
        clauses, values = ["home_id=?"], [home_id]
        if not include_test:
            clauses.append("is_test=0")
        if start is not None:
            clauses.append("occurred_at>=?")
            values.append(int(start))
        if end is not None:
            clauses.append("occurred_at<?")
            values.append(int(end))
        if kinds:
            ordered = sorted(set(kinds))
            clauses.append("event_type IN (" + ",".join("?" for _ in ordered) + ")")
            values.extend(ordered)
        if payload_reasons:
            reasons = sorted(set(payload_reasons))
            clauses.append("json_extract(payload_json,'$.reason') IN (" + ",".join("?" for _ in reasons) + ")")
            values.extend(reasons)
        direction = "DESC" if newest_first else "ASC"
        sql = "SELECT * FROM events WHERE " + " AND ".join(clauses) + f" ORDER BY occurred_at {direction},event_id {direction}"
        if limit is not None:
            sql += " LIMIT ?"
            values.append(max(0, int(limit)))
        with self.lock:
            rows = self.db.execute(sql, values).fetchall()
        return [self._row_to_event(row) for row in rows]

    def latest_home_received(self, home_id: str, kind: str) -> CloudEvent | None:
        with self.lock:
            row = self.db.execute(
                "SELECT * FROM events WHERE home_id=? AND event_type=? ORDER BY received_at DESC,event_id DESC LIMIT 1",
                (home_id, kind),
            ).fetchone()
        return None if row is None else self._row_to_event(row)

    def home_event_counts(self, home_id: str) -> dict[str, int]:
        with self.lock:
            rows = self.db.execute(
                "SELECT event_type,COUNT(*) AS count FROM events WHERE home_id=? GROUP BY event_type",
                (home_id,),
            ).fetchall()
        return {row["event_type"]: int(row["count"]) for row in rows}

    def get(self, key: tuple[str, str], default=None):  # type: ignore[override]
        try:
            return self[key]
        except KeyError:
            return default

    def clear_home(self, home_id: str) -> None:
        with self.lock, self.db:
            self.db.execute("DELETE FROM events WHERE home_id=?", (home_id,))

    @staticmethod
    def _source_type(kind: str) -> str:
        if kind in {"HUB_HEARTBEAT", "COVERAGE_CHANGED"}:
            return "HUB"
        if kind in {"OK_PRESSED", "CALL_FAMILY"}:
            return "RESIDENT_CONTROL"
        if kind.startswith("MISSING_") or kind in {"DAYTIME_INACTIVITY", "DOOR_LEFT_OPEN", "POST_DOOR_INACTIVITY", "MORNING_ROUTINE_COMPLETED", "UNUSUAL_NIGHT_BATHROOM_ACTIVITY", "UNUSUAL_NIGHT_COMMON_ACTIVITY"}:
            return "SYSTEM"
        return "NODE"

    @staticmethod
    def _row_to_event(row) -> CloudEvent:
        payload = json.loads(row["payload_json"] or "{}")
        hub_received_at = row["hub_received_at"] if "hub_received_at" in row.keys() and row["hub_received_at"] is not None else row["received_at"]
        return CloudEvent(
            row["home_id"],
            row["event_id"],
            row["event_type"],
            row["location"],
            int(row["occurred_at"] or row["received_at"]),
            int(hub_received_at),
            int(row["received_at"]),
            int(row["uncertainty_ms"] or 0) // 1000,
            bool(row["is_test"]),
            payload,
        )
