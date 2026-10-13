"""ED-D03-MIN non-active read foundation, never composed into JsonApi/main.

No credential issuer, grant mutation, timeline, event writer, firmware observer,
installation certificate or device control. All operational limits are explicit
injected policy, with NO production numeric defaults. Test authority/metadata
adapters qualify only this policy/projection, not deployed identity or telemetry.
"""
from collections import OrderedDict
from dataclasses import dataclass
import json
import re
import secrets
import sqlite3
from typing import Protocol

from .diagnostic_authorization import DiagnosticAction, DiagnosticAuthorizer, DiagnosticDenied, positive
from .durable_commit import DurableEventCommit

STAGES = ("sensor", "node_created", "radio_tx", "hub_rx", "hub_validated",
          "hub_persisted", "rules_processed", "backend_queued", "backend_committed",
          "dashboard_received", "application_ack", "node_retired")
NO_STORE = (("Cache-Control", "no-store"), ("Vary", "Authorization, Cookie"))
HEALTH_FIELDS = {
    "connectivity": {"HEALTHY", "OFFLINE", "WARNING", "ERROR"},
    "wifi_state": {"CONNECTED", "DISCONNECTED"},
    "backend_state": {"CONNECTED", "DISCONNECTED"},
    "contact_age_s": (0, 2**63 - 1), "node_health_age_s": (0, 2**63 - 1),
    "rx_rssi_dbm": (-127, 0), "battery_mv": (0, 10000),
    "queue_depth": (0, 2**63 - 1), "oldest_queued_age_s": (0, 2**63 - 1),
    "last_sync_at": (0, 2**63 - 1),
    "firmware_version": r"[0-9]+(?:\.[0-9]+){1,3}(?:-[A-Za-z0-9_.-]+)?",
    "config_fingerprint": r"[a-f0-9]{64}",
}


@dataclass(frozen=True)
class DiagnosticLimits:
    max_page: int
    max_bytes: int
    max_cursors: int
    recent_seconds: int
    freshness_seconds: int

    def __post_init__(self):
        if not all(positive(v) for v in self.__dict__.values()):
            raise ValueError("diagnostic_policy_invalid")


@dataclass(frozen=True)
class TechnicalRecord:
    home_id: str
    ownership_epoch: int
    device_id: str
    source_fingerprint: str
    observed_at: int | None
    fields: dict


@dataclass(frozen=True)
class TechnicalPage:
    revision: str
    records: tuple[TechnicalRecord, ...]
    has_more: bool = False
    gap: bool = False


class ScopedTechnicalSource(Protocol):
    def page(self, home_id: str, ownership_epoch: int, offset: int, limit: int) -> TechnicalPage:
        """Select ONLY qualified current Home/epoch records; bounded before fetch.

        Source qualification/binding belongs to GS-65/109. No target adapter
        exists here. Arbitrary request telemetry/verified flags are not sources.
        """


@dataclass(frozen=True)
class DiagnosticResponse:
    status: int
    body: dict
    headers: tuple = NO_STORE


class DiagnosticUnavailable(RuntimeError):
    pass


class DiagnosticReadService:
    def __init__(self, authorizer=None, *, clock, limits=None, db=None, technical_source=None):
        self.authorizer = authorizer or DiagnosticAuthorizer()
        self.clock, self.limits, self.db = clock, limits, db
        self.technical_source = technical_source
        self._cursors = OrderedDict()

    def read(self, context, home_id, operation, query=None):
        """In-process boundary only. No deployed or WSGI route activates this."""
        try:
            at = self.clock()
            scope = self.authorizer.require(context, home_id, DiagnosticAction.READ_DIAGNOSTICS, at)
            if type(self.limits) is not DiagnosticLimits:
                raise DiagnosticUnavailable()
            if type(query) is not dict and query is not None:
                raise ValueError()
            query = {} if query is None else query
            pending = None
            if operation == "health":
                body, pending = self._health(scope, query, at)
            elif operation == "trace":
                body = self._trace(context, scope, query, at)
            else:
                raise DiagnosticDenied()
            # Reject in-flight revocation/transfer/logout/expiry before return.
            current = self.authorizer.require(context, home_id, DiagnosticAction.READ_DIAGNOSTICS, self.clock())
            if current != scope:
                raise DiagnosticDenied()
            if len(json.dumps(body, ensure_ascii=False, allow_nan=False).encode()) > self.limits.max_bytes:
                raise DiagnosticUnavailable()
            if pending is not None:
                token, cursor = pending
                self._cursors[token] = cursor
                while len(self._cursors) > self.limits.max_cursors:
                    self._cursors.popitem(last=False)
            return DiagnosticResponse(200, body)
        except DiagnosticDenied as error:
            self._cursors.clear()
            return DiagnosticResponse(401 if error.unauthenticated else 403,
                                      {"error": "diagnostic_not_authorized"})
        except (ValueError, TypeError, KeyError):
            return DiagnosticResponse(400, {"error": "invalid_diagnostic_request"})
        except (sqlite3.Error, RuntimeError, OSError):
            return DiagnosticResponse(503, {"error": "diagnostic_source_unavailable"})

    def _health(self, scope, query, at):
        if set(query) - {"limit", "cursor"}:
            raise ValueError()
        limit = query.get("limit", self.limits.max_page)
        if type(limit) is not int or not 1 <= limit <= self.limits.max_page:
            raise ValueError()
        offset, previous_revision = 0, None
        if "cursor" in query:
            token = query["cursor"]
            if type(token) is not str or len(token) > 256:
                raise DiagnosticDenied()
            cursor = self._cursors.get(token)
            if cursor is None or cursor[0] != scope:
                raise DiagnosticDenied()
            _, previous_revision, offset = cursor
        home = scope.membership.home_id
        body = {"schema_version": 1, "class": "A", "home_id": home,
                "ownership_epoch": str(scope.ownership_epoch), "status": "UNSUPPORTED",
                "devices": [], "gap": False, "next_cursor": None}
        if self.technical_source is None:
            if "cursor" in query:
                raise DiagnosticDenied()
            return body, None
        page = self.technical_source.page(home, scope.ownership_epoch, offset, limit)
        if (type(page) is not TechnicalPage or type(page.revision) is not str or
                not 0 < len(page.revision) <= 128 or type(page.records) is not tuple or
                len(page.records) > limit or type(page.has_more) is not bool or type(page.gap) is not bool or
                (page.has_more and not page.records)):
            raise DiagnosticUnavailable()
        if previous_revision is not None and previous_revision != page.revision:
            raise DiagnosticDenied()
        for record in page.records:
            if (type(record) is not TechnicalRecord or record.home_id != home or
                    not positive(record.ownership_epoch) or record.ownership_epoch != scope.ownership_epoch):
                raise DiagnosticDenied()
            body["devices"].append(self._technical(record, at))
        body.update(status="OBSERVED", gap=page.gap)
        pending = None
        if page.has_more:
            token = secrets.token_urlsafe(32)
            body["next_cursor"] = token
            pending = (token, (scope, page.revision, offset + len(page.records)))
        return body, pending

    def _technical(self, record, at):
        if not self._identifier(record.device_id) or type(record.fields) is not dict:
            raise DiagnosticUnavailable()
        fingerprint = record.source_fingerprint
        qualified = type(fingerprint) is str and re.fullmatch(r"[a-f0-9]{64}", fingerprint)
        age = at - record.observed_at if type(record.observed_at) is int and 0 < record.observed_at <= at else None
        status = "UNKNOWN" if not qualified or age is None else (
            "STALE" if age > self.limits.freshness_seconds else "OBSERVED")
        fields = {}
        for key, rule in HEALTH_FIELDS.items():
            value = record.fields.get(key)
            valid = ((type(value) is int and rule[0] <= value <= rule[1]) if type(rule) is tuple else
                     (type(value) is str and value in rule) if type(rule) is set else
                     (type(value) is str and len(value) <= 80 and re.fullmatch(rule, value)))
            fields[key] = {"status": status if key in record.fields else "UNSUPPORTED",
                           "value": value if status == "OBSERVED" and valid else None}
            if not valid and key in record.fields and status == "OBSERVED":
                fields[key]["status"] = "UNKNOWN"
        return {"device_id": record.device_id, "status": status, "age_s": age,
                "source_fingerprint": fingerprint if qualified else None, "fields": fields}

    def _trace(self, context, scope, query, at):
        if set(query) != {"event_key"}:
            raise ValueError()
        key, canonical = DurableEventCommit._identity({"event_key": query["event_key"]})
        if self.db is None:
            raise DiagnosticUnavailable()
        unavailable = {"schema_version": 1, "class": "B", "home_id": scope.membership.home_id,
                       "status": "UNKNOWN", "reason_code": "SCOPED_EVIDENCE_UNAVAILABLE"}
        binding = self.authorizer.event_access(context, scope, canonical)
        if binding is None:
            return unavailable
        # Exact product-owned join; no items(), timeline or SELECT payload_json.
        row = self.db.execute("""
            SELECT e.canonical_event_id,e.event_type,e.location,e.occurred_at,
                   e.hub_received_at,e.received_at,e.uncertainty_ms,c.committed_at,
                   c.ownership_epoch,c.node_enrollment_generation
              FROM durable_event_commits c JOIN events e
                ON e.event_id=c.event_id AND e.home_id=c.home_id
             WHERE c.home_id=? AND c.physical_device_id=? AND c.logical_node_id=?
               AND c.origin_session_id=? AND c.event_sequence=?
               AND c.ownership_epoch=? AND c.node_enrollment_generation=?
               AND e.canonical_event_id=? AND c.committed_at>=? AND c.committed_at<=?
             LIMIT 1
        """, (scope.membership.home_id, key["physical_device_id"], key["logical_node_id"],
              key["origin_session_id"], key["event_sequence"], scope.ownership_epoch,
              binding.enrollment_generation, canonical, max(0, at - self.limits.recent_seconds), at)).fetchone()
        if self.authorizer.event_access(context, scope, canonical) != binding:
            raise DiagnosticDenied()
        if row is None:
            # Same absent result for wrong key, foreign Home, epoch, stale window
            # or legacy commit without verified enrollment provenance.
            return unavailable
        stages = [{"stage": stage, "result": "UNKNOWN", "reason_code": "EVIDENCE_UNAVAILABLE"}
                  for stage in STAGES]
        stages[8].update(result="PASS", reason_code="DURABLE_BACKEND_ROW",
                         provenance={"producer": "DurableEventCommit",
                                     "observation": "READ_ONLY_SQLITE_JOIN",
                                     "deployment": "UNKNOWN", "source_fingerprint": None})
        # Keep raw original zero time distinct from caregiver fallback occurrence.
        return {"schema_version": 1, "class": "B", "home_id": scope.membership.home_id,
                "status": "OBSERVED", "canonical_event_id": canonical,
                "event_key": {k: str(v) if type(v) is int else v for k, v in key.items()},
                "ownership_epoch": str(row["ownership_epoch"]),
                "enrollment_generation": str(row["node_enrollment_generation"]),
                "category": row["event_type"] if row["event_type"] in {"MOTION", "DOOR_OPEN", "DOOR_CLOSED", "OK_PRESSED", "CALL_FAMILY"} else "UNSUPPORTED",
                "location": self._label(row["location"]),
                "times": {"occurred_at": self._time(row["occurred_at"]),
                          "hub_received_at": self._time(row["hub_received_at"]),
                          "backend_received_at": self._time(row["received_at"]),
                          "committed_at": self._time(row["committed_at"]),
                          "uncertainty_ms": row["uncertainty_ms"] if type(row["uncertainty_ms"]) is int and row["uncertainty_ms"] >= 0 else None}, "stages": stages}

    @staticmethod
    def _identifier(value):
        return type(value) is str and re.fullmatch(r"[A-Za-z0-9:._-]{1,128}", value)

    @staticmethod
    def _label(value):
        return value if type(value) is str and len(value.encode()) <= 128 and all(c.isprintable() and c not in "<>" for c in value) else None

    @staticmethod
    def _time(value):
        return {"value": value if type(value) is int and value > 0 else None,
                "status": "RECORDED" if type(value) is int and value > 0 else "UNKNOWN",
                "clock_trust": "UNKNOWN"}
