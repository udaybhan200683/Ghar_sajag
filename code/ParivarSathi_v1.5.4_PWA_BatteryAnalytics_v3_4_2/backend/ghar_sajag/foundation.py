"""SQLite-backed application domain for Phase 1 household, family, device and policy state."""
from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
import hashlib
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .database import initialize_sqlite

ID = re.compile(r"[a-z][a-z0-9-]{1,31}\Z")
LOCALE = re.compile(r"[a-z]{2}(?:-[A-Z]{2})?\Z")
CONTACT = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+\Z")
ROOMS = {"Bedroom / Room 1", "Kitchen", "Main door", "Pooja room", "Bathroom", "Common room", "Central hub"}
CAPABILITIES = {"HUB": {"HUB"}, "NODE": {"MOTION", "DOOR", "MOTION_BUTTON"}}
NOTIFICATION_PREF_DEFAULTS = {
    "safety_alerts": True,
    "routine_alerts": True,
    "check_in_alerts": True,
    "monitoring_alerts": True,
    "device_maintenance_alerts": False,
    "browser_alerts_enabled": False,
}


class ProvisioningAdapter:
    """Future hardware adapters must attest real pairing before returning PHYSICAL."""
    source = "SIMULATOR"

    def registration_source(self, device_id, kind, capability):
        return self.source


class FoundationError(ValueError):
    pass


def clean_text(value, field, minimum=1, maximum=80):
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum or any(ord(c) < 32 for c in value):
        raise FoundationError(f"invalid_{field}")
    return value.strip()


def synchronized(method):
    @wraps(method)
    def run(self, *args, **kwargs):
        with self.lock:
            return method(self, *args, **kwargs)
    return run


class FoundationService:
    """One transactional SQLite store. Device registry is shared by Devices and Manage Devices."""

    def __init__(self, path: str | Path = ":memory:", home_id="simulation-home", owner_id="simulation-owner", clock=None, provisioning=None):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        initialize_sqlite(self.db)
        self.home_id, self.owner_id = home_id, owner_id
        self.clock = clock or (lambda: int(time.time()))
        self.provisioning = provisioning or ProvisioningAdapter()

    @synchronized
    def close(self):
        self.db.close()

    @synchronized
    def _authorize(self, actor, write=False):
        row = self.db.execute("SELECT role,active FROM family_members WHERE home_id=? AND member_id=?", (self.home_id, actor)).fetchone()
        if row is None or not row["active"] or (write and row["role"] != "OWNER"):
            raise PermissionError("not_authorized")

    def _row(self, table, key, value):
        row = self.db.execute(f"SELECT * FROM {table} WHERE {key}=? AND home_id=?", (value, self.home_id)).fetchone()
        if row is None:
            raise KeyError("not_found")
        return dict(row)

    @synchronized
    def seed(self, defaults, devices):
        """Idempotent bootstrap. Never overwrite a previously saved field or unregistration."""
        at = self.clock()
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO households(home_id,display_name,timezone,language,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                            (self.home_id, "Synthetic demo home", "Asia/Kolkata", "en-IN", at, at))
            self.db.execute("INSERT OR IGNORE INTO family_members(member_id,home_id,display_name,relationship,role,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                            (self.owner_id, self.home_id, "Household admin", "Admin", "OWNER", at, at))
            self.db.execute("INSERT OR IGNORE INTO application_policy(home_id,version,policy_json,updated_at) VALUES(?,?,?,?)",
                            (self.home_id, 1, json.dumps(defaults), at))
            self.db.execute("INSERT OR IGNORE INTO notification_preferences(home_id,preferences_json,updated_at) VALUES(?,?,?)",
                            (self.home_id, json.dumps(NOTIFICATION_PREF_DEFAULTS, sort_keys=True), at))
            for d in devices:
                self.db.execute("INSERT OR IGNORE INTO device_registry(device_id,home_id,display_name,kind,capability,room,firmware_version,registration_source,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                                (d["id"], self.home_id, d["name"], d["kind"], d["capability"], d["room"], "1.5.4", "SIMULATOR", at, at))

    @synchronized
    def reset_test_fixture(self, defaults, devices):
        """Reset simulator-owned application fixtures without affecting normal restart persistence."""
        at = self.clock()
        baseline = {d["id"] for d in devices}
        with self.db:
            self.db.execute("UPDATE households SET display_name='Synthetic demo home',timezone='Asia/Kolkata',language='en-IN',updated_at=? WHERE home_id=?", (at, self.home_id))
            self.db.execute("DELETE FROM device_health_history WHERE home_id=?", (self.home_id,))
            self.db.execute("DELETE FROM family_members WHERE home_id=? AND member_id<>?", (self.home_id, self.owner_id))
            self.db.execute("UPDATE family_members SET display_name='Household admin',relationship='Admin',role='OWNER',contact=NULL,active=1,updated_at=? WHERE home_id=? AND member_id=?", (at, self.home_id, self.owner_id))
            placeholders = ",".join("?" for _ in baseline)
            self.db.execute(f"DELETE FROM device_registry WHERE home_id=? AND device_id NOT IN ({placeholders})", (self.home_id, *baseline))
            for d in devices:
                self.db.execute("INSERT OR IGNORE INTO device_registry(device_id,home_id,display_name,kind,capability,room,firmware_version,registration_source,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (d["id"], self.home_id, d["name"], d["kind"], d["capability"], d["room"], "1.5.4", "SIMULATOR", at, at))
                self.db.execute("UPDATE device_registry SET display_name=?,kind=?,capability=?,room=?,registered=1,enabled=1,online=0,health='UNKNOWN',communication='UNKNOWN',last_seen_at=NULL,battery_mv=NULL,battery_percent=NULL,drain_status='LEARNING',updated_at=? WHERE home_id=? AND device_id=?", (d["name"], d["kind"], d["capability"], d["room"], at, self.home_id, d["id"]))
            self.db.execute("UPDATE application_policy SET version=1,policy_json=?,updated_at=? WHERE home_id=?", (json.dumps(defaults), at, self.home_id))
            self.db.execute("UPDATE notification_preferences SET preferences_json=?,updated_at=? WHERE home_id=?", (json.dumps(NOTIFICATION_PREF_DEFAULTS, sort_keys=True), at, self.home_id))
            self.db.execute("DELETE FROM notification_records WHERE home_id=?", (self.home_id,))

    @synchronized
    def home(self, actor):
        self._authorize(actor)
        r = self.db.execute("SELECT home_id,display_name,timezone,language,updated_at FROM households WHERE home_id=?", (self.home_id,)).fetchone()
        return dict(r)

    @synchronized
    def update_home(self, actor, body):
        self._authorize(actor, True)
        if set(body) != {"display_name", "timezone", "language"}:
            raise FoundationError("home_fields_mismatch")
        name = clean_text(body["display_name"], "display_name", 1, 80)
        timezone = clean_text(body["timezone"], "timezone", 3, 64)
        try: ZoneInfo(timezone)
        except ZoneInfoNotFoundError: raise FoundationError("invalid_timezone") from None
        language = clean_text(body["language"], "language", 2, 5)
        if not LOCALE.fullmatch(language): raise FoundationError("invalid_language")
        with self.db:
            self.db.execute("UPDATE households SET display_name=?,timezone=?,language=?,updated_at=? WHERE home_id=?",
                            (name, timezone, language, self.clock(), self.home_id))
        return self.home(actor)

    @synchronized
    def members(self, actor):
        self._authorize(actor)
        return [dict(r) for r in self.db.execute("SELECT member_id,display_name,relationship,role,contact,active,updated_at FROM family_members WHERE home_id=? ORDER BY created_at,member_id", (self.home_id,))]

    def _member_fields(self, body):
        if set(body) != {"member_id", "display_name", "relationship", "role", "contact"}:
            raise FoundationError("member_fields_mismatch")
        member_id = body["member_id"]
        if not isinstance(member_id, str) or not ID.fullmatch(member_id): raise FoundationError("invalid_member_id")
        name = clean_text(body["display_name"], "display_name")
        relationship = clean_text(body["relationship"], "relationship", 0, 40)
        role = body["role"]
        if role not in {"OWNER", "FAMILY", "CAREGIVER"}: raise FoundationError("invalid_role")
        contact = body["contact"]
        if contact is not None and (not isinstance(contact, str) or not CONTACT.fullmatch(contact) or len(contact) > 120):
            raise FoundationError("invalid_contact")
        return member_id, name, relationship, role, contact

    @synchronized
    def add_member(self, actor, body):
        self._authorize(actor, True)
        mid, name, relation, role, contact = self._member_fields(body)
        at = self.clock()
        try:
            with self.db:
                self.db.execute("INSERT INTO family_members(member_id,home_id,display_name,relationship,role,contact,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                                (mid, self.home_id, name, relation, role, contact, at, at))
        except sqlite3.IntegrityError as exc: raise FoundationError("duplicate_member_or_contact") from exc
        return self._row("family_members", "member_id", mid)

    @synchronized
    def update_member(self, actor, mid, body):
        self._authorize(actor, True)
        old = self._row("family_members", "member_id", mid)
        if not old["active"]: raise FoundationError("member_inactive")
        _, name, relation, role, contact = self._member_fields({**body, "member_id": mid})
        if mid == self.owner_id and role != "OWNER": raise FoundationError("last_owner_required")
        if old["role"] == "OWNER" and role != "OWNER" and self._owner_count() <= 1: raise FoundationError("last_owner_required")
        try:
            with self.db:
                self.db.execute("UPDATE family_members SET display_name=?,relationship=?,role=?,contact=?,updated_at=? WHERE member_id=? AND home_id=? AND active=1",
                                (name, relation, role, contact, self.clock(), mid, self.home_id))
        except sqlite3.IntegrityError as exc: raise FoundationError("duplicate_member_or_contact") from exc
        return self._row("family_members", "member_id", mid)

    def _owner_count(self):
        return self.db.execute("SELECT count(*) FROM family_members WHERE home_id=? AND role='OWNER' AND active=1", (self.home_id,)).fetchone()[0]

    @synchronized
    def deactivate_member(self, actor, mid):
        self._authorize(actor, True)
        old = self._row("family_members", "member_id", mid)
        if not old["active"]: raise FoundationError("member_inactive")
        if old["role"] == "OWNER" and self._owner_count() <= 1: raise FoundationError("last_owner_required")
        with self.db:
            self.db.execute("UPDATE family_members SET active=0,updated_at=? WHERE member_id=? AND home_id=?", (self.clock(), mid, self.home_id))
        return self._row("family_members", "member_id", mid)

    @synchronized
    def devices(self, actor, registered_only=True):
        self._authorize(actor)
        sql = "SELECT * FROM device_registry WHERE home_id=?" + (" AND registered=1" if registered_only else "") + " ORDER BY kind,created_at,device_id"
        return [dict(r) for r in self.db.execute(sql, (self.home_id,))]

    @synchronized
    def device(self, actor, did):
        self._authorize(actor)
        return self._row("device_registry", "device_id", did)

    @synchronized
    def register_device(self, actor, body):
        self._authorize(actor, True)
        if set(body) != {"device_id", "display_name", "kind", "capability", "room"}: raise FoundationError("device_fields_mismatch")
        did = body["device_id"]
        if not isinstance(did, str) or not ID.fullmatch(did): raise FoundationError("invalid_device_id")
        name = clean_text(body["display_name"], "display_name")
        kind, capability, room = body["kind"], body["capability"], body["room"]
        if kind not in CAPABILITIES or capability not in CAPABILITIES[kind]: raise FoundationError("invalid_capability")
        if room not in ROOMS or (kind == "HUB" and room != "Central hub"): raise FoundationError("invalid_room")
        at = self.clock()
        try:
            with self.db:
                self.db.execute("INSERT INTO device_registry(device_id,home_id,display_name,kind,capability,room,registration_source,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                                (did, self.home_id, name, kind, capability, room, self.provisioning.registration_source(did, kind, capability), at, at))
        except sqlite3.IntegrityError as exc: raise FoundationError("duplicate_device_id") from exc
        return self.device(actor, did)

    @synchronized
    def update_device(self, actor, did, body):
        self._authorize(actor, True)
        old = self._row("device_registry", "device_id", did)
        if not old["registered"]: raise FoundationError("device_unregistered")
        if set(body) != {"display_name", "room", "enabled"}: raise FoundationError("device_edit_fields_mismatch")
        name = clean_text(body["display_name"], "display_name")
        room, enabled = body["room"], body["enabled"]
        if room not in ROOMS or (old["kind"] == "HUB" and room != "Central hub"): raise FoundationError("invalid_room")
        if type(enabled) is not bool: raise FoundationError("invalid_enabled")
        with self.db:
            self.db.execute("UPDATE device_registry SET display_name=?,room=?,enabled=?,updated_at=? WHERE device_id=? AND home_id=?",
                            (name, room, int(enabled), self.clock(), did, self.home_id))
        return self.device(actor, did)

    @synchronized
    def unregister_device(self, actor, did):
        self._authorize(actor, True)
        old = self._row("device_registry", "device_id", did)
        if not old["registered"]: raise FoundationError("device_unregistered")
        if old["kind"] == "HUB" and self.db.execute("SELECT count(*) FROM device_registry WHERE home_id=? AND kind='HUB' AND registered=1", (self.home_id,)).fetchone()[0] <= 1:
            raise FoundationError("last_hub_required")
        with self.db:
            self.db.execute("UPDATE device_registry SET registered=0,online=0,communication='OFFLINE',updated_at=? WHERE device_id=? AND home_id=?",
                            (self.clock(), did, self.home_id))
        return self.device(actor, did)

    @staticmethod
    def validate_health(online, health, battery_mv=None, battery_percent=None, drain_status="LEARNING"):
        if type(online) is not bool or health not in {"ACTIVE", "DEGRADED", "OFFLINE", "UNKNOWN"} or drain_status not in {"NORMAL", "HIGH", "LEARNING"}:
            raise FoundationError("invalid_health")
        if (not online and health != "OFFLINE") or (online and health == "OFFLINE"):
            raise FoundationError("inconsistent_health")
        if battery_mv is not None and (type(battery_mv) is not int or not 0 <= battery_mv <= 6000): raise FoundationError("invalid_battery_mv")
        if battery_percent is not None and (type(battery_percent) is not int or not 0 <= battery_percent <= 100): raise FoundationError("invalid_battery_percent")

    @synchronized
    def record_health(self, did, online, health, battery_mv=None, battery_percent=None, drain_status="LEARNING", heartbeat=False):
        self.validate_health(online, health, battery_mv, battery_percent, drain_status)
        old = self._row("device_registry", "device_id", did)
        if not old["registered"]: raise FoundationError("device_unregistered")
        if (old["online"], old["health"], old["battery_mv"], old["battery_percent"], old["drain_status"]) == (int(online), health, battery_mv, battery_percent, drain_status):
            if online and heartbeat and old["last_seen_at"] != self.clock():
                with self.db:
                    self.db.execute("UPDATE device_registry SET last_seen_at=?,updated_at=? WHERE device_id=? AND home_id=?", (self.clock(), self.clock(), did, self.home_id))
            return
        at = self.clock()
        with self.db:
            self.db.execute("UPDATE device_registry SET online=?,health=?,communication=?,last_seen_at=CASE WHEN ? THEN ? ELSE last_seen_at END,battery_mv=?,battery_percent=?,drain_status=?,updated_at=? WHERE device_id=? AND home_id=? AND registered=1",
                            (int(online), health, "ONLINE" if online else "OFFLINE", int(online), at, battery_mv, battery_percent, drain_status, at, did, self.home_id))
            self.db.execute("INSERT INTO device_health_history(home_id,device_type,device_id,sampled_at,status,battery_mv,details_json) SELECT home_id,kind,device_id,?,?,?,? FROM device_registry WHERE device_id=? AND registered=1",
                            (at, health, battery_mv, json.dumps({"online": online, "battery_percent": battery_percent, "drain_status": drain_status}), did))

    @synchronized
    def expire_stale(self, now, exclude=(), stale_seconds=190):
        """Expire simulated devices without a heartbeat; baseline nodes use the C++ freshness path."""
        excluded = set(exclude)
        rows = self.db.execute("SELECT device_id,battery_mv,battery_percent,drain_status FROM device_registry WHERE home_id=? AND registered=1 AND online=1 AND last_seen_at IS NOT NULL AND last_seen_at<?", (self.home_id, now-stale_seconds)).fetchall()
        for row in rows:
            if row["device_id"] not in excluded:
                self.record_health(row["device_id"], False, "OFFLINE", row["battery_mv"], row["battery_percent"], row["drain_status"])

    @synchronized
    def policy(self, actor):
        self._authorize(actor)
        row = self.db.execute("SELECT version,policy_json FROM application_policy WHERE home_id=?", (self.home_id,)).fetchone()
        return {"version": row["version"], "settings": json.loads(row["policy_json"])}

    @synchronized
    def save_policy(self, actor, settings, validator):
        self._authorize(actor, True)
        validator(settings)
        with self.db:
            self.db.execute("UPDATE application_policy SET version=version+1,policy_json=?,updated_at=? WHERE home_id=?",
                            (json.dumps(settings), self.clock(), self.home_id))
        return self.policy(actor)

    @synchronized
    def notification_preferences(self, actor):
        self._authorize(actor)
        row = self.db.execute("SELECT preferences_json,updated_at FROM notification_preferences WHERE home_id=?", (self.home_id,)).fetchone()
        prefs = dict(NOTIFICATION_PREF_DEFAULTS)
        if row:
            prefs.update(json.loads(row["preferences_json"]))
        return {"home_id": self.home_id, "preferences": prefs, "updated_at": row["updated_at"] if row else None}

    @synchronized
    def update_notification_preferences(self, actor, body):
        self._authorize(actor, True)
        if set(body) != set(NOTIFICATION_PREF_DEFAULTS):
            raise FoundationError("notification_preference_fields_mismatch")
        if any(type(value) is not bool for value in body.values()):
            raise FoundationError("invalid_notification_preference")
        at = self.clock()
        with self.db:
            self.db.execute("UPDATE notification_preferences SET preferences_json=?,updated_at=? WHERE home_id=?",
                            (json.dumps(body, sort_keys=True), at, self.home_id))
        return self.notification_preferences(actor)

    @synchronized
    def notification_records(self, actor, limit=20):
        self._authorize(actor)
        rows = self.db.execute(
            "SELECT record_id,category,severity,state,title,message,created_at,delivered_at,failed_at,resolved_at,suppressed_reason "
            "FROM notification_records WHERE home_id=? ORDER BY created_at DESC,record_id DESC LIMIT ?",
            (self.home_id, max(1, min(int(limit), 100))),
        ).fetchall()
        return [dict(row) for row in rows]

    @synchronized
    def apply_notification_event(self, event, delivery_available=True):
        decision = self._notification_decision(event)
        if decision is None:
            return None
        prefs = self.notification_preferences(self.owner_id)["preferences"]
        enabled = prefs[decision["preference"]]
        state = "DELIVERED" if enabled and delivery_available else "SUPPRESSED" if not enabled else "FAILED"
        reason = None if state == "DELIVERED" else "preference_disabled" if state == "SUPPRESSED" else "delivery_unavailable"
        record_id = "notif_" + hashlib.sha256(f"{self.home_id}:{decision['correlation_key']}".encode()).hexdigest()[:16]
        with self.db:
            self.db.execute(
                """
                INSERT OR IGNORE INTO notification_records(
                    record_id,home_id,source_event_id,category,severity,state,title,message,correlation_key,
                    created_at,delivered_at,failed_at,suppressed_reason
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    record_id, self.home_id, event.event_id, decision["category"], decision["severity"],
                    state, decision["title"], decision["message"], decision["correlation_key"], event.server_received_at,
                    event.server_received_at if state == "DELIVERED" else None,
                    event.server_received_at if state == "FAILED" else None,
                    reason,
                ),
            )
        return self.notification_record_by_id(record_id)

    @synchronized
    def create_check_in_overdue_notification(self, at, delivery_available=True):
        class Event:
            event_id = "check-in-overdue"
            kind = "CHECK_IN_OVERDUE"
            server_received_at = at
            payload = {}
        return self.apply_notification_event(Event(), delivery_available)

    @synchronized
    def resolve_notification(self, correlation_key, at):
        with self.db:
            self.db.execute("UPDATE notification_records SET state='RESOLVED',resolved_at=? WHERE home_id=? AND correlation_key=? AND state IN ('DELIVERED','FAILED')",
                            (at, self.home_id, correlation_key))

    def notification_record_by_id(self, record_id):
        row = self.db.execute("SELECT record_id,category,severity,state,title,message,created_at,delivered_at,failed_at,resolved_at,suppressed_reason FROM notification_records WHERE home_id=? AND record_id=?",
                              (self.home_id, record_id)).fetchone()
        return None if row is None else dict(row)

    def _notification_decision(self, event):
        kind = event.kind
        reason = event.payload.get("reason")
        if kind == "CHECK_IN_OVERDUE":
            return {"preference": "check_in_alerts", "category": "CHECK_IN", "severity": "CONCERN", "title": "I am OK check-in overdue", "message": "The expected I am OK check-in has not arrived.", "correlation_key": "check-in:overdue"}
        if kind == "CALL_FAMILY":
            return {"preference": "safety_alerts", "category": "SAFETY", "severity": "URGENT", "title": "Call Family requested", "message": "Family assistance was requested.", "correlation_key": f"event:{event.event_id}"}
        if kind == "MISSING_MORNING_ACTIVITY":
            window = event.payload.get("window_id", event.event_id)
            return {"preference": "routine_alerts", "category": "ROUTINE", "severity": "CONCERN", "title": "Morning routine concern", "message": "Expected morning activity was not completed.", "correlation_key": f"morning:{window}"}
        if kind == "DAYTIME_INACTIVITY":
            return {"preference": "routine_alerts", "category": "ROUTINE", "severity": "CONCERN", "title": "Daytime inactivity concern", "message": "Expected daytime activity was not observed.", "correlation_key": f"event:{event.event_id}"}
        if kind == "DOOR_LEFT_OPEN":
            return {"preference": "safety_alerts", "category": "SAFETY", "severity": "CONCERN", "title": "Main door left open", "message": "Main door stayed open longer than configured.", "correlation_key": f"event:{event.event_id}"}
        if kind == "POST_DOOR_INACTIVITY":
            return {"preference": "safety_alerts", "category": "SAFETY", "severity": "CONCERN", "title": "No indoor activity after door closed", "message": "Indoor activity did not follow the door event.", "correlation_key": f"event:{event.event_id}"}
        if kind in {"UNUSUAL_NIGHT_BATHROOM_ACTIVITY", "UNUSUAL_NIGHT_COMMON_ACTIVITY"}:
            return {"preference": "safety_alerts", "category": "SAFETY", "severity": "CONCERN", "title": "Unusual night activity", "message": "Night activity was outside configured household limits.", "correlation_key": f"event:{event.event_id}"}
        if kind == "COVERAGE_CHANGED" and reason == "coverage_lost":
            return {"preference": "monitoring_alerts", "category": "MONITORING", "severity": "CONCERN", "title": "Monitoring coverage lost", "message": "A monitoring device was unavailable.", "correlation_key": "coverage:monitoring"}
        if kind == "COVERAGE_CHANGED" and reason == "coverage_restored":
            self.resolve_notification("coverage:monitoring", event.server_received_at)
            return None
        if kind == "OK_PRESSED":
            self.resolve_notification("check-in:overdue", event.server_received_at)
            return None
        return None
