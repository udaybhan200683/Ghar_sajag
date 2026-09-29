"""Atomic SQLite event, incident and notification-outbox commit contract.

This adapter requires an authenticated Hub boundary before ``commit`` is called.
It never sends a notification while the database transaction is open.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from typing import Callable

from .ingest import IngestService


class EventCommitConflict(ValueError):
    pass


class DurableEventCommit:
    INCIDENT_TYPES = {
        "CALL_FAMILY", "MISSING_MORNING_ACTIVITY", "DAYTIME_INACTIVITY",
        "DOOR_LEFT_OPEN", "UNUSUAL_NIGHT_BATHROOM_ACTIVITY",
        "UNUSUAL_NIGHT_COMMON_ACTIVITY", "POST_DOOR_INACTIVITY",
    }

    def __init__(self, db: sqlite3.Connection, lock: threading.RLock | None = None) -> None:
        if db.in_transaction or db.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise ValueError("durable_store_requires_foreign_keys")
        if db.execute("PRAGMA synchronous").fetchone()[0] < 2:
            raise ValueError("durable_store_requires_full_sync")
        if not db.execute("PRAGMA database_list").fetchone()[2]:
            raise ValueError("durable_store_requires_file_database")
        self.db = db
        self.lock = lock or threading.RLock()

    @staticmethod
    def _identity(body: dict) -> tuple[dict, str]:
        key = body.get("event_key")
        if not isinstance(key, dict) or set(key) != {
            "physical_device_id", "logical_node_id", "origin_session_id", "event_sequence"
        }:
            raise ValueError("invalid_event_key")
        physical, node = key["physical_device_id"], key["logical_node_id"]
        session, sequence = key["origin_session_id"], key["event_sequence"]
        if (not isinstance(physical, str) or not 1 <= len(physical) <= 64 or
            not isinstance(node, str) or not 1 <= len(node) <= 24 or
            type(session) is not int or not 0 < session < 2**63 or
            type(sequence) is not int or not 0 < sequence < 2**63):
            raise ValueError("invalid_event_key")
        canonical = f"p{len(physical)}:{physical}n{len(node)}:{node}s{session}q{sequence}"
        return key, canonical

    @staticmethod
    def _payload(body: dict) -> tuple[dict, str]:
        allowed = {"event_key", "event_type", "occurred_at", "hub_received_at",
                   "location", "uncertainty_s", "is_test", "payload"}
        if set(body) - allowed or not {"event_key", "event_type", "occurred_at", "hub_received_at"} <= set(body):
            raise ValueError("invalid_event_payload")
        kind = body["event_type"]
        if not isinstance(kind, str) or kind not in IngestService.ALLOWED_KINDS:
            raise ValueError("unknown_kind")
        occurred, received = body["occurred_at"], body["hub_received_at"]
        uncertainty = body.get("uncertainty_s", 0)
        location, payload, is_test = body.get("location", ""), body.get("payload", {}), body.get("is_test", False)
        if (type(occurred) is not int or not -(2**63) < occurred < 2**63 or
            type(received) is not int or not -(2**63) < received < 2**63 or
            type(uncertainty) is not int or uncertainty < 0 or
            not isinstance(location, str) or len(location) > 64 or
            not isinstance(payload, dict) or type(is_test) is not bool):
            raise ValueError("invalid_event_payload")
        if kind == "MOTION_SUMMARY":
            count, first, last = payload.get("additional_count"), payload.get("first_ms"), payload.get("last_ms")
            if (type(count) is not int or not 0 < count <= 0xFFFFFFFF or
                type(first) is not int or first < 0 or type(last) is not int or last < first):
                raise ValueError("invalid_motion_summary")
        normalized = {"event_type": kind, "occurred_at": occurred,
                      "hub_received_at": received, "location": location,
                      "uncertainty_s": uncertainty, "is_test": is_test, "payload": payload}
        try:
            canonical_json = json.dumps(normalized, sort_keys=True, separators=(",", ":"),
                                        ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as error:
            raise ValueError("invalid_event_payload") from error
        return normalized, hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    @staticmethod
    def _stable_key(kind: str, event_id: str, payload: dict) -> str:
        if kind == "CALL_FAMILY":
            return f"call-family:{event_id}"
        if kind == "MISSING_MORNING_ACTIVITY":
            return f"missing-morning:{payload.get('window_id', event_id)}"
        if kind == "DAYTIME_INACTIVITY":
            return f"daytime-inactivity:{event_id}"
        return f"routine-concern:{kind}:{event_id}"

    @staticmethod
    def _id(prefix: str, value: str) -> str:
        return prefix + hashlib.sha256(value.encode("utf-8")).hexdigest()

    def commit(self, home_id: str, body: dict, received_at: int,
               fail_at: str | None = None) -> dict:
        """Return COMMITTED only after commit; fail_at is a host fault-injection hook."""
        key, canonical = self._identity(body)
        payload, fingerprint = self._payload(body)
        identity = (home_id, key["physical_device_id"], key["logical_node_id"],
                    key["origin_session_id"], key["event_sequence"])
        event_id = self._id("evt_", home_id + "\0" + canonical)
        with self.lock:
            if self.db.in_transaction:
                raise RuntimeError("event_commit_requires_clean_transaction")
            self.db.execute("BEGIN IMMEDIATE")
            try:
                if not self.db.execute("SELECT 1 FROM households WHERE home_id=?", (home_id,)).fetchone():
                    raise ValueError("unknown_home")
                prior = self.db.execute(
                    "SELECT payload_sha256 FROM durable_event_commits WHERE home_id=? AND physical_device_id=? AND logical_node_id=? AND origin_session_id=? AND event_sequence=?",
                    identity).fetchone()
                if prior is not None:
                    if prior[0] != fingerprint:
                        raise EventCommitConflict("event_key_payload_conflict")
                    self.db.commit()
                    return {"event_key": key, "status": "COMMITTED", "duplicate": True}
                self._fault(fail_at, "before_event")
                self.db.execute(
                    """INSERT INTO events(event_id,canonical_event_id,home_id,source_id,source_type,
                       session_id,sequence_number,sensor_type,event_type,location,occurred_at,
                       received_at,hub_received_at,uncertainty_ms,is_test,payload_json)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (event_id, canonical, home_id, canonical, "NODE", key["origin_session_id"],
                     key["event_sequence"], payload["event_type"], payload["event_type"],
                     payload["location"], payload["occurred_at"], received_at,
                     payload["hub_received_at"], payload["uncertainty_s"] * 1000,
                     int(payload["is_test"]), json.dumps(payload["payload"], sort_keys=True)))
                self.db.execute(
                    "INSERT INTO durable_event_commits VALUES(?,?,?,?,?,?,?,?)",
                    (*identity, event_id, fingerprint, received_at))
                self._fault(fail_at, "after_event")
                kind = payload["event_type"]
                incident_id = None
                stable = None
                if not payload["is_test"] and kind in self.INCIDENT_TYPES:
                    stable = self._stable_key(kind, canonical, payload["payload"])
                    incident_id = self._id("inc_", home_id + "\0" + stable)
                    self.db.execute(
                        """INSERT INTO alerts(alert_id,home_id,stable_key,alert_type,severity,
                           state,source_event_id,created_at,is_test) VALUES(?,?,?,?,?,'OPEN',?,?,0)
                           ON CONFLICT(home_id,stable_key) DO NOTHING""",
                        (incident_id, home_id, stable, kind,
                         "URGENT" if kind == "CALL_FAMILY" else "CONCERN", event_id, received_at))
                    incident_id = self.db.execute(
                        "SELECT alert_id FROM alerts WHERE home_id=? AND stable_key=?",
                        (home_id, stable)).fetchone()[0]
                self._fault(fail_at, "after_business_effect")
                if incident_id is not None or (kind == "DOOR_OPEN" and
                    payload["payload"].get("quiet_hours") is True and not payload["is_test"]):
                    recipients = self.db.execute(
                        """SELECT caregiver_id,role FROM household_caregivers
                           WHERE home_id=? AND active=1 AND role IN ('PRIMARY','BACKUP')
                           ORDER BY CASE role WHEN 'PRIMARY' THEN 0 ELSE 1 END, caregiver_id""",
                        (home_id,)).fetchall()
                    effect_key = stable or f"door-quiet:{canonical}"
                    for recipient, role in recipients:
                        if incident_id is None and role != "PRIMARY":
                            continue
                        stage = 1 if role == "PRIMARY" else 2
                        due = received_at + (300 if stage == 2 else 0)
                        unique = home_id + "\0" + effect_key + "\0" + recipient
                        outbox_id = self._id("out_", unique)
                        if incident_id is not None:
                            self.db.execute(
                                """INSERT INTO notification_jobs(job_id,alert_id,home_id,
                                   recipient_id,stage,due_at,state,idempotency_key)
                                   VALUES(?,?,?,?,?,?,'CREATED',?)
                                   ON CONFLICT(idempotency_key) DO NOTHING""",
                                (self._id("job_", unique), incident_id, home_id, recipient,
                                 stage, due, unique))
                        self.db.execute(
                            """INSERT INTO durable_notification_outbox
                               (outbox_id,home_id,event_id,effect_key,recipient_id,payload_json,due_at)
                               VALUES(?,?,?,?,?,?,?)
                               ON CONFLICT(home_id,effect_key,recipient_id) DO NOTHING""",
                            (outbox_id, home_id, event_id, effect_key, recipient,
                             json.dumps({"kind": kind, "event_key": canonical}, sort_keys=True), due))
                self._fault(fail_at, "after_outbox")
                self._fault(fail_at, "commit_failure")
                self.db.commit()
            except BaseException:
                self.db.rollback()
                raise
        return {"event_key": key, "status": "COMMITTED", "duplicate": False}

    def due_outbox(self, at: int, limit: int = 100) -> list[tuple]:
        """Read committed pending work; pass outbox_id as provider idempotency key."""
        with self.lock:
            return self.db.execute(
                """SELECT outbox_id,recipient_id,payload_json FROM durable_notification_outbox
                   WHERE state='PENDING' AND due_at<=? ORDER BY due_at,outbox_id LIMIT ?""",
                (at, max(0, min(limit, 100))),
            ).fetchall()

    def mark_delivered(self, outbox_id: str, provider_reference: str) -> bool:
        """Idempotent local completion after an idempotent provider accepts delivery."""
        if not provider_reference:
            raise ValueError("provider_reference_required")
        with self.lock, self.db:
            row = self.db.execute(
                "SELECT state FROM durable_notification_outbox WHERE outbox_id=?", (outbox_id,)
            ).fetchone()
            if row is None:
                return False
            if row[0] == "DELIVERED":
                return True
            if row[0] != "PENDING":
                return False
            self.db.execute(
                """UPDATE durable_notification_outbox SET state='DELIVERED',provider_reference=?
                   WHERE outbox_id=? AND state='PENDING'""", (provider_reference, outbox_id))
            return True

    @staticmethod
    def _fault(selected: str | None, point: str) -> None:
        if selected == point:
            raise RuntimeError("injected_" + point)
