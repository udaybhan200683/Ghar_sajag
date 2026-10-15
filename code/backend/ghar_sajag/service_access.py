"""Inactive service desk domain over host SQLite.

The injected authority must verify the session and current role from a trusted
server context. This module accepts no HTTP identity headers and installs no
routes. A production issuer, staff directory and PostgreSQL adapter are absent.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from typing import Protocol
from uuid import uuid4

from .diagnostic_authorization import (ActorSession, DiagnosticDenied, DiagnosticGrant, EventAccess,
                                       ServiceMembership, TrustedAccessSnapshot)


class ServiceDenied(PermissionError):
    pass


class ServiceConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class ServiceAccessConfig:
    default_access_seconds: int

    def __post_init__(self):
        if (type(self.default_access_seconds) is not int or
                not 60 <= self.default_access_seconds <= 3600):
            raise ValueError("invalid_service_access_config")

    @classmethod
    def load(cls, path: str | Path) -> "ServiceAccessConfig":
        settings = json.loads(Path(path).read_text(encoding="utf-8"))
        if (type(settings) is not dict or set(settings) !=
                {"schema_version", "default_access_seconds"} or
                type(settings["schema_version"]) is not int or settings["schema_version"] != 1 or
                type(settings["default_access_seconds"]) is not int or
                not 60 <= settings["default_access_seconds"] <= 3600):
            raise ValueError("invalid_service_access_config")
        return cls(settings["default_access_seconds"])


@dataclass(frozen=True)
class TrustedPrincipal:
    actor_id: str
    session_id: str
    issuer_reference: str
    role: str  # CAREGIVER, ADMIN, or TECHNICIAN, from verified authority only
    company_id: str | None
    active: bool
    expires_at: int


class ServiceAuthority(Protocol):
    def principal(self, server_context: object) -> TrustedPrincipal | None:
        """Verify live issuer/session/staff status; never parse caller claims."""

    def caregiver_home(self, server_context: object, home_id: str, epoch: int) -> bool:
        """Check current approved household role and membership/owner epoch."""

    def active_staff(self, company_id: str) -> tuple[str, ...]:
        """Return current eligible technician IDs from trusted company directory."""

    def active_employee(self, company_id: str, actor_id: str, role: str) -> bool:
        """Check an employee's current company role, including admins."""

    def company_for_home(self, home_id: str) -> str | None:
        """Resolve the support company from trusted Home configuration."""


def _ref(value: object, maximum: int = 160) -> bool:
    return type(value) is str and 0 < len(value) <= maximum and value.strip() == value


class ServiceDesk:
    """Single-connection SQLite transaction boundary for isolated host operation."""

    def __init__(self, db: sqlite3.Connection, *, authority: ServiceAuthority | None,
                 config: ServiceAccessConfig, clock):
        if type(config) is not ServiceAccessConfig or not callable(clock):
            raise ValueError("invalid_service_desk_dependencies")
        self.db, self.authority, self.config, self.clock = db, authority, config, clock
        self.db.execute("PRAGMA foreign_keys=ON")

    @contextmanager
    def _tx(self):
        if self.db.in_transaction:
            raise RuntimeError("service_desk_requires_outermost_transaction")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def _now(self):
        at = self.clock()
        if type(at) is not int or at < 0:
            raise RuntimeError("invalid_service_clock")
        return at

    def _principal(self, context, at, *roles):
        actor = self.authority.principal(context) if self.authority is not None else None
        if (type(actor) is not TrustedPrincipal or actor.role not in roles or
                not all(_ref(x) for x in (actor.actor_id, actor.session_id,
                                           actor.issuer_reference)) or
                type(actor.active) is not bool or not actor.active or
                type(actor.expires_at) is not int or at >= actor.expires_at or
                (actor.role in ("ADMIN", "TECHNICIAN") and not _ref(actor.company_id))):
            raise ServiceDenied("trusted_active_principal_required")
        return actor

    def _caregiver(self, context, actor, home, epoch):
        if actor.role != "CAREGIVER" or not self.authority.caregiver_home(context, home, epoch):
            raise ServiceDenied("current_home_caregiver_required")

    def _hub(self, home):
        rows = self.db.execute(
            "SELECT hub_device_id,installation_epoch FROM hub_ownership_registry "
            "WHERE home_id=? AND state='ACTIVE'", (home,)).fetchall()
        if len(rows) != 1:
            raise ServiceConflict("exactly_one_active_home_hub_required")
        return rows[0][0], rows[0][1]

    def _nodes(self, home, hub):
        return tuple(tuple(row) for row in self.db.execute(
            "SELECT physical_node_id,logical_node_id,enrollment_generation "
            "FROM node_enrollment_history WHERE home_id=? "
            "AND hub_device_id=? AND state='ACTIVE' ORDER BY physical_node_id", (home, hub)))

    @staticmethod
    def _saved_nodes(raw):
        # Consent binds enrollment identity, including re-enrollment of the same
        # physical device. Old/invalid host snapshots fail closed.
        try:
            nodes = json.loads(raw)
        except (TypeError, ValueError) as error:
            raise ServiceDenied("invalid_saved_node_scope") from error
        if (type(nodes) is not list or any(
                type(node) is not list or len(node) != 3 or
                not _ref(node[0]) or not _ref(node[1]) or
                type(node[2]) is not int or node[2] <= 0 for node in nodes)):
            raise ServiceDenied("invalid_saved_node_scope")
        return tuple(tuple(node) for node in nodes)

    def _ticket(self, ticket_id):
        row = self.db.execute(
            "SELECT ticket_id,home_id,hub_device_id,ownership_epoch,company_id,status,"
            "assignee_id,assignment_version FROM service_tickets WHERE ticket_id=?",
            (ticket_id,)).fetchone()
        if row is None:
            raise ServiceDenied("ticket_unavailable")
        return dict(zip(("ticket_id", "home_id", "hub_id", "epoch", "company_id",
                         "status", "assignee_id", "version"), row))

    def _current_ticket(self, ticket):
        hub, epoch = self._hub(ticket["home_id"])
        if (hub != ticket["hub_id"] or epoch != ticket["epoch"] or
                self.authority.company_for_home(ticket["home_id"]) != ticket["company_id"]):
            raise ServiceDenied("ownership_changed")

    def _staff(self, company):
        if self.authority is None:
            raise ServiceDenied("staff_authority_required")
        staff = self.authority.active_staff(company)
        if (type(staff) is not tuple or any(not _ref(x) for x in staff) or
                len(set(staff)) != len(staff)):
            raise ServiceDenied("invalid_staff_snapshot")
        return tuple(sorted(staff))

    def _audit(self, ticket, request, actor, action, at):
        self.db.execute(
            "INSERT INTO service_access_audit(ticket_id,request_id,actor_id,action,occurred_at) "
            "VALUES(?,?,?,?,?)", (ticket, request, actor, action, at))

    def _cancel_live(self, ticket, actor, at):
        ids = [row[0] for row in self.db.execute(
            "SELECT request_id FROM service_access_requests WHERE ticket_id=? "
            "AND state IN ('PENDING','APPROVED')", (ticket,))]
        self.db.execute(
            "UPDATE service_access_requests SET state='CANCELLED',decided_at=? "
            "WHERE ticket_id=? AND state IN ('PENDING','APPROVED')", (at, ticket))
        for request in ids:
            self._audit(ticket, request, actor, "ACCESS_CANCELLED", at)

    def _expire(self, ticket, at):
        ids = [row[0] for row in self.db.execute(
            "SELECT request_id FROM service_access_requests WHERE ticket_id=? "
            "AND state='APPROVED' AND expires_at<=?", (ticket, at))]
        self.db.execute(
            "UPDATE service_access_requests SET state='EXPIRED',decided_at=? "
            "WHERE ticket_id=? AND state='APPROVED' AND expires_at<=?", (at, ticket, at))
        for request in ids:
            self._audit(ticket, request, "service-system", "ACCESS_EXPIRED", at)

    def create_ticket(self, context, home_id, reason):
        if not _ref(home_id) or not _ref(reason, 500):
            raise ValueError("invalid_ticket")
        with self._tx():
            at = self._now()
            actor = self._principal(context, at, "CAREGIVER")
            hub, epoch = self._hub(home_id)
            self._caregiver(context, actor, home_id, epoch)
            company_id = self.authority.company_for_home(home_id)
            if not _ref(company_id):
                raise ServiceDenied("trusted_home_company_required")
            ticket = uuid4().hex
            self.db.execute(
                "INSERT INTO service_tickets VALUES(?,?,?,?,?,?,?,'OPEN',NULL,0,?,?)",
                (ticket, home_id, hub, epoch, company_id, actor.actor_id, reason, at, at))
            self._audit(ticket, None, actor.actor_id, "TICKET_CREATED", at)
            return ticket

    def list_tickets(self, context, *, home_id=None, limit=100, offset=0):
        if (type(limit) is not int or not 1 <= limit <= 100 or
                type(offset) is not int or not 0 <= offset <= 10000):
            raise ValueError("invalid_ticket_page")
        with self._tx():
            at = self._now()
            actor = self._principal(context, at, "CAREGIVER", "ADMIN", "TECHNICIAN")
            if actor.role == "CAREGIVER":
                if not _ref(home_id):
                    raise ServiceDenied("home_required")
                _, epoch = self._hub(home_id)
                self._caregiver(context, actor, home_id, epoch)
                where, args = "home_id=?", (home_id,)
            elif actor.role == "ADMIN":
                if not self.authority.active_employee(actor.company_id, actor.actor_id, "ADMIN"):
                    raise ServiceDenied("inactive_admin")
                where, args = "company_id=?", (actor.company_id,)
            else:
                if actor.actor_id not in self._staff(actor.company_id):
                    raise ServiceDenied("inactive_staff")
                where, args = "company_id=? AND assignee_id=? AND status<>'CLOSED'", (
                    actor.company_id, actor.actor_id)
            rows = self.db.execute(
                "SELECT ticket_id,home_id,status,assignee_id FROM service_tickets WHERE " + where +
                " ORDER BY created_at,ticket_id LIMIT ? OFFSET ?", (*args, limit, offset)).fetchall()
            if actor.role == "CAREGIVER":
                return tuple({"ticket_id": x[0], "home_id": x[1], "status": x[2]} for x in rows)
            visible = []
            for row in rows:
                try:
                    self._current_ticket(self._ticket(row[0]))
                except (ServiceDenied, ServiceConflict):
                    continue
                visible.append(row)
            return tuple({"ticket_id": x[0], "home_id": x[1], "status": x[2],
                          "assignee_id": x[3]} for x in visible)

    def ticket_detail(self, context, ticket_id):
        if not _ref(ticket_id):
            raise ValueError("invalid_ticket_id")
        with self._tx():
            at = self._now()
            actor = self._principal(context, at, "CAREGIVER", "ADMIN", "TECHNICIAN")
            ticket = self._ticket(ticket_id)
            self._current_ticket(ticket)
            if actor.role == "CAREGIVER":
                self._caregiver(context, actor, ticket["home_id"], ticket["epoch"])
            elif (ticket["company_id"] != actor.company_id or
                  not self.authority.active_employee(actor.company_id, actor.actor_id, actor.role) or
                  (actor.role == "TECHNICIAN" and
                   (ticket["assignee_id"] != actor.actor_id or ticket["status"] == "CLOSED"))):
                raise ServiceDenied("ticket_unavailable")
            row = self.db.execute("SELECT reason,created_at,updated_at FROM service_tickets "
                                  "WHERE ticket_id=?", (ticket_id,)).fetchone()
            result = {"ticket_id": ticket_id, "home_id": ticket["home_id"],
                      "hub_device_id": ticket["hub_id"], "status": ticket["status"],
                      "reason": row[0], "created_at": row[1], "updated_at": row[2]}
            if actor.role != "CAREGIVER":
                result["assignee_id"] = ticket["assignee_id"]
            return result

    def home_requests(self, context, home_id):
        """Caregiver card data, including exact request scope and backend expiry."""
        with self._tx():
            at = self._now()
            actor = self._principal(context, at, "CAREGIVER")
            hub, epoch = self._hub(home_id)
            self._caregiver(context, actor, home_id, epoch)
            rows = self.db.execute(
                "SELECT r.request_id,r.ticket_id,r.employee_id,r.state,r.expires_at,r.node_scope_json,"
                "r.employee_role "
                "FROM service_access_requests r JOIN service_tickets t ON t.ticket_id=r.ticket_id "
                "WHERE t.home_id=? AND t.hub_device_id=? AND t.ownership_epoch=? "
                "AND t.status<>'CLOSED' AND r.state IN ('PENDING','APPROVED') "
                "ORDER BY r.requested_at,r.request_id LIMIT 100", (home_id, hub, epoch)).fetchall()
            current_nodes = self._nodes(home_id, hub)
            stale = set()
            for row in rows:
                self._expire(row[1], at)
                try:
                    self._current_ticket(self._ticket(row[1]))
                except (ServiceDenied, ServiceConflict):
                    self._cancel_live(row[1], "service-system", at)
                    stale.add(row[0])
                    continue
                if (self._saved_nodes(row[5]) != current_nodes or
                        not self.authority.active_employee(
                            self._ticket(row[1])["company_id"], row[2], row[6])):
                    self._cancel_live(row[1], "service-system", at)
                    stale.add(row[0])
            return tuple({"request_id": row[0], "ticket_id": row[1],
                          "employee_id": row[2], "state": row[3],
                          "expires_at": row[4], "home_id": home_id,
                          "hub_device_id": hub,
                          "node_ids": tuple(node[0] for node in self._saved_nodes(row[5])),
                          "node_scope": self._saved_nodes(row[5]),
                          "access_seconds": self.config.default_access_seconds}
                         for row in rows if row[0] not in stale and
                         (row[3] != "APPROVED" or at < row[4]))

    def unassign(self, context, ticket_id):
        with self._tx():
            at = self._now()
            actor = self._principal(context, at, "ADMIN")
            if not self.authority.active_employee(actor.company_id, actor.actor_id, "ADMIN"):
                raise ServiceDenied("inactive_admin")
            ticket = self._ticket(ticket_id)
            if ticket["company_id"] != actor.company_id or ticket["status"] == "CLOSED":
                raise ServiceDenied("admin_company_ticket_required")
            self._current_ticket(ticket)
            self._cancel_live(ticket_id, actor.actor_id, at)
            self.db.execute("UPDATE service_tickets SET assignee_id=NULL,"
                            "assignment_version=assignment_version+1,status='OPEN',updated_at=? "
                            "WHERE ticket_id=?", (at, ticket_id))
            self._audit(ticket_id, None, actor.actor_id, "TICKET_UNASSIGNED", at)

    def assign(self, context, ticket_id, *, employee_id=None, round_robin=False):
        if not _ref(ticket_id) or type(round_robin) is not bool or (round_robin == (employee_id is not None)):
            raise ValueError("select_manual_or_round_robin")
        with self._tx():
            at = self._now()
            actor = self._principal(context, at, "ADMIN")
            if not self.authority.active_employee(actor.company_id, actor.actor_id, "ADMIN"):
                raise ServiceDenied("inactive_admin")
            ticket = self._ticket(ticket_id)
            if ticket["company_id"] != actor.company_id or ticket["status"] == "CLOSED":
                raise ServiceDenied("admin_company_ticket_required")
            self._current_ticket(ticket)
            staff = self._staff(actor.company_id)
            if round_robin:
                if not staff:
                    raise ServiceConflict("no_eligible_staff")
                prior = self.db.execute(
                    "SELECT last_employee_id FROM service_assignment_cursor WHERE company_id=?",
                    (actor.company_id,)).fetchone()
                employee_id = next((x for x in staff if prior is None or x > prior[0]), staff[0])
            elif employee_id not in staff and employee_id != actor.actor_id:
                raise ServiceDenied("active_technician_required")
            if employee_id == ticket["assignee_id"]:
                if round_robin:
                    self.db.execute("INSERT INTO service_assignment_cursor VALUES(?,?) "
                                    "ON CONFLICT(company_id) DO UPDATE SET last_employee_id=excluded.last_employee_id",
                                    (actor.company_id, employee_id))
                return employee_id
            self._cancel_live(ticket_id, actor.actor_id, at)
            self.db.execute(
                "UPDATE service_tickets SET assignee_id=?,assignment_version=assignment_version+1,"
                "status='OPEN',updated_at=? WHERE ticket_id=?", (employee_id, at, ticket_id))
            if round_robin:
                self.db.execute("INSERT INTO service_assignment_cursor VALUES(?,?) "
                                "ON CONFLICT(company_id) DO UPDATE SET last_employee_id=excluded.last_employee_id",
                                (actor.company_id, employee_id))
            self._audit(ticket_id, None, actor.actor_id, "TICKET_ASSIGNED", at)
            return employee_id

    def start(self, context, ticket_id):
        if not _ref(ticket_id):
            raise ValueError("invalid_ticket_id")
        with self._tx():
            at = self._now()
            actor = self._principal(context, at, "TECHNICIAN", "ADMIN")
            ticket = self._ticket(ticket_id)
            if (ticket["company_id"] != actor.company_id or ticket["status"] == "CLOSED" or
                    (actor.role == "TECHNICIAN" and ticket["assignee_id"] != actor.actor_id)):
                raise ServiceDenied("assigned_active_ticket_required")
            if not self.authority.active_employee(actor.company_id, actor.actor_id, actor.role):
                raise ServiceDenied("inactive_staff")
            self._current_ticket(ticket)
            self._expire(ticket_id, at)
            live = self.db.execute("SELECT request_id,employee_id,employee_role FROM service_access_requests "
                                   "WHERE ticket_id=? AND state IN ('PENDING','APPROVED')", (ticket_id,)).fetchone()
            if live is not None:
                current_nodes = json.dumps(self._nodes(ticket["home_id"], ticket["hub_id"]), separators=(",", ":"))
                saved_nodes = self.db.execute("SELECT node_scope_json FROM service_access_requests "
                                              "WHERE request_id=?", (live[0],)).fetchone()[0]
                if (saved_nodes != current_nodes or
                        (live[1] == actor.actor_id and live[2] != actor.role) or
                        not self.authority.active_employee(ticket["company_id"], live[1], live[2])):
                    self._cancel_live(ticket_id, actor.actor_id, at)
                elif live[1] == actor.actor_id:
                    return live[0]
                else:
                    raise ServiceConflict("another_employee_request_active")
            request = uuid4().hex
            nodes = json.dumps(self._nodes(ticket["home_id"], ticket["hub_id"]), separators=(",", ":"))
            self.db.execute(
                "INSERT INTO service_access_requests(request_id,ticket_id,employee_id,employee_role,assignment_version,"
                "home_id,hub_device_id,ownership_epoch,node_scope_json,state,requested_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,'PENDING',?)",
                (request, ticket_id, actor.actor_id, actor.role, ticket["version"], ticket["home_id"],
                 ticket["hub_id"], ticket["epoch"], nodes, at))
            self._audit(ticket_id, request, actor.actor_id, "ACCESS_REQUESTED", at)
            return request

    def decide(self, context, request_id, *, approve):
        if not _ref(request_id) or type(approve) is not bool:
            raise ValueError("invalid_service_decision")
        with self._tx():
            at = self._now()
            actor = self._principal(context, at, "CAREGIVER")
            row = self.db.execute("SELECT ticket_id,employee_id,employee_role,assignment_version,home_id,"
                                  "hub_device_id,ownership_epoch,node_scope_json,state FROM "
                                  "service_access_requests WHERE request_id=?", (request_id,)).fetchone()
            if row is None or row[8] != "PENDING":
                raise ServiceDenied("pending_request_required")
            ticket = self._ticket(row[0])
            self._caregiver(context, actor, row[4], row[6])
            self._current_ticket(ticket)
            if (ticket["status"] == "CLOSED" or ticket["home_id"] != row[4] or
                    ticket["hub_id"] != row[5] or ticket["epoch"] != row[6] or
                    ticket["version"] != row[3] or
                    (row[2] == "TECHNICIAN" and ticket["assignee_id"] != row[1])):
                raise ServiceDenied("stale_service_request")
            if not self.authority.active_employee(ticket["company_id"], row[1], row[2]):
                raise ServiceDenied("inactive_employee")
            if self._saved_nodes(row[7]) != self._nodes(row[4], row[5]):
                raise ServiceDenied("node_scope_changed")
            expires = at + self.config.default_access_seconds if approve else None
            grant = uuid4().hex if approve else None
            self.db.execute(
                "UPDATE service_access_requests SET state=?,approved_by=?,decided_at=?,"
                "expires_at=?,grant_id=? WHERE request_id=? AND state='PENDING'",
                ("APPROVED" if approve else "DENIED", actor.actor_id, at, expires, grant, request_id))
            self._audit(row[0], request_id, actor.actor_id,
                        "ACCESS_APPROVED" if approve else "ACCESS_DENIED", at)
            return {"approved": approve, "grant_id": grant, "expires_at": expires}

    def revoke(self, context, request_id):
        if not _ref(request_id):
            raise ValueError("invalid_request_id")
        with self._tx():
            at = self._now()
            actor = self._principal(context, at, "CAREGIVER")
            row = self.db.execute("SELECT ticket_id,home_id,ownership_epoch,state FROM "
                                  "service_access_requests WHERE request_id=?", (request_id,)).fetchone()
            if row is None or row[3] != "APPROVED":
                raise ServiceDenied("active_request_required")
            self._current_ticket(self._ticket(row[0]))
            self._caregiver(context, actor, row[1], row[2])
            self.db.execute("UPDATE service_access_requests SET state='REVOKED',decided_at=? "
                            "WHERE request_id=?", (at, request_id))
            self._audit(row[0], request_id, actor.actor_id, "ACCESS_REVOKED", at)

    def close(self, context, ticket_id):
        with self._tx():
            at = self._now()
            actor = self._principal(context, at, "ADMIN")
            if not self.authority.active_employee(actor.company_id, actor.actor_id, "ADMIN"):
                raise ServiceDenied("inactive_admin")
            ticket = self._ticket(ticket_id)
            if ticket["company_id"] != actor.company_id:
                raise ServiceDenied("admin_company_ticket_required")
            self._current_ticket(ticket)
            self._cancel_live(ticket_id, actor.actor_id, at)
            self.db.execute("UPDATE service_tickets SET status='CLOSED',updated_at=? WHERE ticket_id=?",
                            (at, ticket_id))
            self._audit(ticket_id, None, actor.actor_id, "TICKET_CLOSED", at)

    def require_access(self, context, ticket_id, *, node_id=None):
        """Recheck live consent, staff, assignment, ownership and Nodes per request."""
        return self._authorized_access(context, ticket_id, node_id=node_id)[0]

    def _authorized_access(self, context, ticket_id, *, node_id=None):
        """Return scope and its verified principal from ONE transaction."""
        if not _ref(ticket_id) or (node_id is not None and not _ref(node_id)):
            raise ServiceDenied("invalid_access_scope")
        result = None
        with self._tx():
            at = self._now()
            actor = self._principal(context, at, "TECHNICIAN", "ADMIN")
            ticket = self._ticket(ticket_id)
            if (ticket["company_id"] != actor.company_id or ticket["status"] == "CLOSED" or
                    (actor.role == "TECHNICIAN" and ticket["assignee_id"] != actor.actor_id) or
                    not self.authority.active_employee(actor.company_id, actor.actor_id, actor.role)):
                raise ServiceDenied("active_assigned_employee_required")
            self._current_ticket(ticket)
            self._expire(ticket_id, at)
            row = self.db.execute(
                "SELECT request_id,home_id,hub_device_id,ownership_epoch,node_scope_json,"
                "assignment_version,expires_at,rowid,decided_at FROM service_access_requests WHERE ticket_id=? "
                "AND employee_id=? AND employee_role=? AND state='APPROVED'",
                (ticket_id, actor.actor_id, actor.role)).fetchone()
            if (row is not None and row[1:4] ==
                    (ticket["home_id"], ticket["hub_id"], ticket["epoch"]) and
                    row[5] == ticket["version"] and type(row[6]) is int and
                    type(row[8]) is int and row[6] - row[8] == self.config.default_access_seconds and
                    row[8] <= at < row[6]):
                nodes = self._nodes(ticket["home_id"], ticket["hub_id"])
                node_ids = tuple(node[0] for node in nodes)
                if self._saved_nodes(row[4]) == nodes and (node_id is None or node_id in node_ids):
                    result = {"ticket_id": ticket_id, "home_id": ticket["home_id"],
                              "hub_device_id": ticket["hub_id"], "ownership_epoch": ticket["epoch"],
                              "node_ids": node_ids, "node_scope": nodes,
                              "request_id": row[0], "expires_at": row[6]}
        if result is None:
            raise ServiceDenied("current_consent_and_node_scope_required")
        return result, actor, row[5] + 1, row[7]


@dataclass(frozen=True)
class ServiceDiagnosticContext:
    """Internal composition input; the principal is still independently verified."""
    server_context: object
    ticket_id: str


class ServiceDiagnosticAuthority:
    """Compose ticket consent with the existing ED-D02 read policy in-process."""

    def __init__(self, desk: ServiceDesk):
        self.desk = desk

    def resolve(self, context, home_id):
        if type(context) is not ServiceDiagnosticContext:
            return None
        try:
            scope, actor, version, grant_version = self.desk._authorized_access(
                context.server_context, context.ticket_id)
        except (ServiceDenied, ServiceConflict) as error:
            raise DiagnosticDenied() from error
        if scope["home_id"] != home_id:
            raise DiagnosticDenied()
        return TrustedAccessSnapshot(
            ActorSession(actor.actor_id, actor.session_id, actor.issuer_reference, actor.expires_at),
            ServiceMembership(home_id, actor.actor_id, actor.role, version, True,
                              context.ticket_id, scope["hub_device_id"], scope["node_scope"]),
            DiagnosticGrant(home_id, actor.actor_id, scope["ownership_epoch"], version,
                            grant_version, scope["expires_at"], False), scope["ownership_epoch"])

    def event_access(self, context, home_id, canonical_event_id) -> EventAccess | None:
        # An actual event-to-current-Node resolver requires a qualified source.
        # No Class B trace is exposed until that source is supplied.
        return None
