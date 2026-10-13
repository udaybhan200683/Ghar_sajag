"""GS-124/125 host SQLite service desk; all principals here are fixtures."""
import json
import io
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from ghar_sajag.database import initialize_sqlite
from ghar_sajag.ownership_registry import (HubOwnershipRegistry, VerifiedHubIdentity,
                                            AuthorizedHomeOperation, VerifiedNodeEnrollment)
from ghar_sajag.service_access import (ServiceAccessConfig, ServiceConflict, ServiceDenied,
                                       ServiceDesk, ServiceDiagnosticAuthority,
                                       ServiceDiagnosticContext, TrustedPrincipal)
from ghar_sajag.diagnostic_authorization import DiagnosticAction, DiagnosticAuthorizer, DiagnosticDenied
from ghar_sajag.diagnostics import DiagnosticReadService, DiagnosticLimits, TechnicalPage, TechnicalRecord
from ghar_sajag.http_api import JsonApi


class FixtureAuthority:
    def __init__(self):
        self.capabilities = {}
        self.staff = {"tech-a", "tech-b"}
        self.admins = {"admin"}
        self.homes = {"care-a": "home-a", "care-b": "home-b"}
        self.company = {"home-a": "company", "home-b": "company"}
        for name, role in (("care-a", "CAREGIVER"), ("care-b", "CAREGIVER"),
                           ("admin", "ADMIN"), ("tech-a", "TECHNICIAN"),
                           ("tech-b", "TECHNICIAN")):
            self.capabilities[name] = object()
        self.principals = {cap: TrustedPrincipal(name, "session-"+name, "fixture-issuer",
                                                role, None if role == "CAREGIVER" else "company",
                                                True, 100000)
                           for (name, role), cap in zip(
                               (("care-a", "CAREGIVER"), ("care-b", "CAREGIVER"),
                                ("admin", "ADMIN"), ("tech-a", "TECHNICIAN"),
                                ("tech-b", "TECHNICIAN")), self.capabilities.values())}

    def principal(self, context):
        try:
            return self.principals.get(context)
        except TypeError:
            return None

    def caregiver_home(self, context, home_id, epoch):
        actor = self.principal(context)
        return actor is not None and self.homes.get(actor.actor_id) == home_id and epoch == 1

    def active_staff(self, company_id):
        return tuple(sorted(self.staff)) if company_id == "company" else ()

    def active_employee(self, company_id, actor_id, role):
        return company_id == "company" and ((role == "TECHNICIAN" and actor_id in self.staff)
                                             or (role == "ADMIN" and actor_id in self.admins))

    def company_for_home(self, home_id):
        return self.company.get(home_id)

    def context(self, name):
        return self.capabilities[name]


class ServiceAccessTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "service.sqlite"
        self.db = self.connect()
        self.now = 100
        self.authority = FixtureAuthority()
        with self.db:
            for home in ("home-a", "home-b"):
                self.db.execute("INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) "
                                "VALUES(?,?, 'UTC',1,1)", (home, home))
        registry = HubOwnershipRegistry(self.db)
        for home, hub, fingerprint in (("home-a", "hub-a", "a"*64),
                                        ("home-b", "hub-b", "b"*64)):
            identity = VerifiedHubIdentity(hub, fingerprint, "fixture-proof")
            registry.register_unclaimed_identity(identity, 1)
            registry.claim_home(identity, AuthorizedHomeOperation("fixture", home,
                                "CLAIM_HUB", "fixture-authorization"), 2)
        registry.enroll_node(VerifiedHubIdentity("hub-a", "a"*64, "fixture-proof"),
                             AuthorizedHomeOperation("fixture", "home-a", "ENROLL_NODE", "fixture-auth"),
                             VerifiedNodeEnrollment("node-a", "room-a", 1, "c"*64, "fixture-proof"), 3)
        self.config = ServiceAccessConfig.load(Path(__file__).resolve().parents[2] /
                                               "config/service_access.json")
        self.desk = self.service()

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def connect(self):
        db = sqlite3.connect(self.path, isolation_level=None, timeout=10)
        initialize_sqlite(db)
        db.execute("PRAGMA synchronous=FULL")
        return db

    def service(self, db=None):
        return ServiceDesk(db or self.db, authority=self.authority, config=self.config,
                           clock=lambda: self.now)

    def ctx(self, name):
        return self.authority.context(name)

    def ticket(self):
        return self.desk.create_ticket(self.ctx("care-a"), "home-a", "Hub not responding")

    def assigned(self):
        ticket = self.ticket()
        self.desk.assign(self.ctx("admin"), ticket, employee_id="tech-a")
        return ticket

    def approved(self):
        ticket = self.assigned()
        request = self.desk.start(self.ctx("tech-a"), ticket)
        return ticket, request, self.desk.decide(self.ctx("care-a"), request, approve=True)

    def test_S01_config_requires_version_and_bounded_integer(self):
        self.assertEqual(self.config.default_access_seconds, 1800)
        with self.assertRaises(ValueError):
            ServiceAccessConfig(True)
        for value in (True, 0, 59, 3601, "1800"):
            path = Path(self.temp.name) / "config.json"
            path.write_text(json.dumps({"schema_version":1,"default_access_seconds":value}))
            with self.assertRaises(ValueError):
                ServiceAccessConfig.load(path)

    def test_S02_no_authority_or_forged_claim_can_create(self):
        for forged in ({"actor_id":"care-a", "verified":True}, "care-a", None):
            with self.assertRaises(ServiceDenied):
                self.desk.create_ticket(forged, "home-a", "reason")
        with self.assertRaises(ServiceDenied):
            ServiceDesk(self.db, authority=None, config=self.config,
                        clock=lambda:100).create_ticket(self.ctx("care-a"), "home-a", "reason")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM service_tickets").fetchone()[0], 0)

    def test_S03_caregiver_home_and_company_are_server_derived(self):
        with self.assertRaises(ServiceDenied):
            self.desk.create_ticket(self.ctx("care-b"), "home-a", "reason")
        ticket = self.ticket()
        self.assertEqual(self.db.execute("SELECT company_id,hub_device_id,ownership_epoch "
                                         "FROM service_tickets WHERE ticket_id=?", (ticket,)).fetchone(),
                         ("company", "hub-a", 1))
        self.assertEqual(len(self.desk.list_tickets(self.ctx("care-a"), home_id="home-a")), 1)
        self.assertEqual(self.desk.list_tickets(self.ctx("care-b"), home_id="home-b"), ())

    def test_S04_unassigned_admin_only_manual_and_tech_isolation(self):
        ticket = self.ticket()
        self.assertEqual(len(self.desk.list_tickets(self.ctx("admin"))), 1)
        self.assertEqual(self.desk.list_tickets(self.ctx("tech-a")), ())
        with self.assertRaises(ServiceDenied):
            self.desk.start(self.ctx("tech-a"), ticket)
        self.desk.assign(self.ctx("admin"), ticket, employee_id="tech-a")
        self.assertEqual(len(self.desk.list_tickets(self.ctx("tech-a"))), 1)
        self.assertEqual(self.desk.list_tickets(self.ctx("tech-b")), ())

    def test_S05_round_robin_and_no_eligible_staff(self):
        tickets = [self.ticket() for _ in range(4)]
        self.assertEqual([self.desk.assign(self.ctx("admin"), ticket, round_robin=True)
                          for ticket in tickets], ["tech-a", "tech-b", "tech-a", "tech-b"])
        self.authority.staff.clear()
        pending = self.ticket()
        with self.assertRaises(ServiceConflict):
            self.desk.assign(self.ctx("admin"), pending, round_robin=True)
        self.assertIsNone(self.db.execute("SELECT assignee_id FROM service_tickets WHERE ticket_id=?",
                                          (pending,)).fetchone()[0])

    def test_S06_start_does_not_grant_and_approval_is_one_time(self):
        ticket = self.assigned()
        request = self.desk.start(self.ctx("tech-a"), ticket)
        self.assertEqual(self.desk.start(self.ctx("tech-a"), ticket), request)
        self.assertEqual(self.desk.home_requests(self.ctx("care-a"), "home-a")[0]["state"], "PENDING")
        with self.assertRaises(ServiceDenied):
            self.desk.require_access(self.ctx("tech-a"), ticket)
        with self.assertRaises(ServiceDenied):
            self.desk.decide(self.ctx("care-b"), request, approve=True)
        result = self.desk.decide(self.ctx("care-a"), request, approve=True)
        self.assertEqual(result["expires_at"], 1900)
        self.assertEqual(self.desk.require_access(self.ctx("tech-a"), ticket, node_id="node-a")
                         ["node_ids"], ("node-a",))
        with self.assertRaises(ServiceDenied):
            self.desk.decide(self.ctx("care-a"), request, approve=True)

    def test_S07_deny_requires_new_start_and_grant_never_created(self):
        ticket = self.assigned()
        request = self.desk.start(self.ctx("tech-a"), ticket)
        self.assertFalse(self.desk.decide(self.ctx("care-a"), request, approve=False)["approved"])
        with self.assertRaises(ServiceDenied):
            self.desk.require_access(self.ctx("tech-a"), ticket)
        self.assertNotEqual(self.desk.start(self.ctx("tech-a"), ticket), request)

    def test_S08_fixed_expiry_reapproval_and_restart(self):
        ticket, request, result = self.approved()
        self.db.close()
        self.db = self.connect()
        self.desk = self.service()
        self.now = 1899
        self.assertEqual(self.desk.require_access(self.ctx("tech-a"), ticket)["expires_at"], 1900)
        self.now = 1900
        with self.assertRaises(ServiceDenied):
            self.desk.require_access(self.ctx("tech-a"), ticket)
        self.assertEqual(self.db.execute("SELECT state FROM service_access_requests WHERE request_id=?",
                                         (request,)).fetchone()[0], "EXPIRED")
        fresh = self.desk.start(self.ctx("tech-a"), ticket)
        self.assertNotEqual(fresh, request)
        with self.assertRaises(ServiceDenied):
            self.desk.require_access(self.ctx("tech-a"), ticket)
        self.assertEqual(self.desk.decide(self.ctx("care-a"), fresh, approve=True)["expires_at"], 3700)

    def test_S09_revoke_and_reassignment_immediately_deny(self):
        ticket, request, _ = self.approved()
        self.desk.revoke(self.ctx("care-a"), request)
        with self.assertRaises(ServiceDenied):
            self.desk.require_access(self.ctx("tech-a"), ticket)
        new = self.desk.start(self.ctx("tech-a"), ticket)
        self.desk.decide(self.ctx("care-a"), new, approve=True)
        self.desk.assign(self.ctx("admin"), ticket, employee_id="tech-b")
        with self.assertRaises(ServiceDenied):
            self.desk.require_access(self.ctx("tech-a"), ticket)
        self.assertEqual(self.desk.list_tickets(self.ctx("tech-a")), ())

    def test_S10_unassign_close_and_offboard_deny(self):
        ticket, _, _ = self.approved()
        self.authority.staff.remove("tech-a")
        with self.assertRaises(ServiceDenied):
            self.desk.require_access(self.ctx("tech-a"), ticket)
        self.authority.staff.add("tech-a")
        self.desk.unassign(self.ctx("admin"), ticket)
        with self.assertRaises(ServiceDenied):
            self.desk.require_access(self.ctx("tech-a"), ticket)
        self.desk.close(self.ctx("admin"), ticket)
        with self.assertRaises(ServiceDenied):
            self.desk.start(self.ctx("tech-a"), ticket)

    def test_S11_ownership_and_current_node_fence(self):
        ticket, _, _ = self.approved()
        with self.assertRaises(ServiceDenied):
            self.desk.require_access(self.ctx("tech-a"), ticket, node_id="node-b")
        self.db.execute("UPDATE node_enrollment_history SET state='REVOKED',ended_at=101 "
                        "WHERE physical_node_id='node-a'")
        with self.assertRaises(ServiceDenied):
            self.desk.require_access(self.ctx("tech-a"), ticket)
        self.db.execute("UPDATE hub_ownership_registry SET installation_epoch=2 "
                        "WHERE hub_device_id='hub-a'")
        with self.assertRaises(ServiceDenied):
            self.desk.require_access(self.ctx("tech-a"), ticket)

    def test_S12_company_role_and_session_expiry(self):
        ticket = self.assigned()
        self.authority.principals[self.ctx("tech-a")] = TrustedPrincipal(
            "tech-a", "session", "fixture-issuer", "TECHNICIAN", "other-company", True, 1000)
        with self.assertRaises(ServiceDenied):
            self.desk.start(self.ctx("tech-a"), ticket)
        self.authority.principals[self.ctx("admin")] = TrustedPrincipal(
            "admin", "session", "fixture-issuer", "ADMIN", "company", True, 100)
        with self.assertRaises(ServiceDenied):
            self.desk.assign(self.ctx("admin"), ticket, employee_id="tech-b")

    def test_S13_concurrent_approval_has_single_winner(self):
        ticket = self.assigned()
        request = self.desk.start(self.ctx("tech-a"), ticket)
        outcomes = []
        barrier = threading.Barrier(2)
        def approve():
            db = self.connect()
            try:
                barrier.wait()
                outcomes.append(self.service(db).decide(self.ctx("care-a"), request, approve=True))
            except ServiceDenied:
                outcomes.append("DENIED")
            finally:
                db.close()
        threads = [threading.Thread(target=approve) for _ in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertEqual(sum(isinstance(x, dict) for x in outcomes), 1)
        self.assertEqual(outcomes.count("DENIED"), 1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM service_access_requests "
                                         "WHERE state='APPROVED'").fetchone()[0], 1)

    def test_S14_admin_real_home_requires_caregiver_approval(self):
        ticket = self.ticket()
        request = self.desk.start(self.ctx("admin"), ticket)
        with self.assertRaises(ServiceDenied):
            self.desk.require_access(self.ctx("admin"), ticket)
        self.desk.decide(self.ctx("care-a"), request, approve=True)
        self.assertEqual(self.desk.require_access(self.ctx("admin"), ticket)["home_id"], "home-a")

    def test_S15_existing_diagnostic_policy_composes_with_ticket_consent(self):
        ticket = self.assigned()
        context = ServiceDiagnosticContext(self.ctx("tech-a"), ticket)
        guard = DiagnosticAuthorizer(ServiceDiagnosticAuthority(self.desk))
        with self.assertRaises(DiagnosticDenied):
            guard.require(context, "home-a", DiagnosticAction.READ_DIAGNOSTICS, 100)
        request = self.desk.start(self.ctx("tech-a"), ticket)
        self.desk.decide(self.ctx("care-a"), request, approve=True)
        self.assertEqual(guard.require(context, "home-a", DiagnosticAction.READ_DIAGNOSTICS, 100)
                         .membership.actor_id, "tech-a")
        with self.assertRaises(DiagnosticDenied):
            guard.require(context, "home-b", DiagnosticAction.READ_DIAGNOSTICS, 100)
        self.desk.revoke(self.ctx("care-a"), request)
        with self.assertRaises(DiagnosticDenied):
            guard.require(context, "home-a", DiagnosticAction.READ_DIAGNOSTICS, 100)

    def test_S16_concurrent_round_robin_serializes_cursor_and_assignments(self):
        tickets = [self.ticket(), self.ticket()]
        barrier = threading.Barrier(2)
        assigned = []
        def dispatch(ticket):
            db = self.connect()
            try:
                barrier.wait()
                assigned.append(self.service(db).assign(self.ctx("admin"), ticket,
                                                       round_robin=True))
            finally:
                db.close()
        threads = [threading.Thread(target=dispatch, args=(ticket,)) for ticket in tickets]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertEqual(sorted(assigned), ["tech-a", "tech-b"])

    def test_S17_concurrent_close_and_approval_never_leave_live_access(self):
        ticket = self.assigned()
        request = self.desk.start(self.ctx("tech-a"), ticket)
        barrier = threading.Barrier(2)
        outcomes = []
        def operate(action):
            db = self.connect()
            try:
                barrier.wait()
                desk = self.service(db)
                if action == "close":
                    desk.close(self.ctx("admin"), ticket)
                else:
                    desk.decide(self.ctx("care-a"), request, approve=True)
                outcomes.append("OK")
            except ServiceDenied:
                outcomes.append("DENIED")
            finally:
                db.close()
        threads = [threading.Thread(target=operate, args=(action,))
                   for action in ("close", "approve")]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertEqual(len(outcomes), 2)
        self.assertEqual(self.db.execute("SELECT status FROM service_tickets WHERE ticket_id=?",
                                         (ticket,)).fetchone()[0], "CLOSED")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM service_access_requests "
                                         "WHERE ticket_id=? AND state='APPROVED'", (ticket,)).fetchone()[0], 0)
        with self.assertRaises(ServiceDenied):
            self.desk.require_access(self.ctx("tech-a"), ticket)

    def test_S18_company_rebinding_fences_old_staff_queue_and_grant(self):
        ticket, _, _ = self.approved()
        self.authority.company["home-a"] = "another-company"
        self.assertEqual(self.desk.list_tickets(self.ctx("admin")), ())
        self.assertEqual(self.desk.list_tickets(self.ctx("tech-a")), ())
        with self.assertRaises(ServiceDenied):
            self.desk.require_access(self.ctx("tech-a"), ticket)
        with self.assertRaises(ServiceDenied):
            self.desk.assign(self.ctx("admin"), ticket, employee_id="tech-b")

    def test_S19_bounded_queue_paging_and_ticket_detail_role_scope(self):
        first, second = self.ticket(), self.ticket()
        self.assertEqual(len(self.desk.list_tickets(self.ctx("admin"), limit=1, offset=0)), 1)
        self.assertEqual(len(self.desk.list_tickets(self.ctx("admin"), limit=1, offset=1)), 1)
        for invalid in (0, 101, True):
            with self.assertRaises(ValueError):
                self.desk.list_tickets(self.ctx("admin"), limit=invalid)
        with self.assertRaises(ServiceDenied):
            self.desk.ticket_detail(self.ctx("tech-a"), first)
        self.desk.assign(self.ctx("admin"), first, employee_id="tech-a")
        self.assertEqual(self.desk.ticket_detail(self.ctx("tech-a"), first)["reason"],
                         "Hub not responding")
        with self.assertRaises(ServiceDenied):
            self.desk.ticket_detail(self.ctx("tech-b"), first)
        with self.assertRaises(ServiceDenied):
            self.desk.ticket_detail(self.ctx("care-b"), first)
        self.assertNotIn("assignee_id", self.desk.ticket_detail(self.ctx("care-a"), first))

    def test_S20_same_physical_node_reenrollment_requires_fresh_consent(self):
        ticket, old, _ = self.approved()
        HubOwnershipRegistry(self.db).enroll_node(
            VerifiedHubIdentity("hub-a", "a"*64, "fixture-proof"),
            AuthorizedHomeOperation("fixture", "home-a", "ENROLL_NODE", "fixture-auth"),
            VerifiedNodeEnrollment("node-a", "room-new", 2, "d"*64, "fixture-proof"), 101)
        with self.assertRaises(ServiceDenied):
            self.desk.require_access(self.ctx("tech-a"), ticket, node_id="node-a")
        fresh = self.desk.start(self.ctx("tech-a"), ticket)
        self.assertNotEqual(old, fresh)
        self.assertEqual(self.desk.home_requests(self.ctx("care-a"), "home-a")[0]
                         ["node_scope"], (("node-a", "room-new", 2),))
        self.desk.decide(self.ctx("care-a"), fresh, approve=True)
        self.assertEqual(self.desk.require_access(self.ctx("tech-a"), ticket)
                         ["node_scope"], (("node-a", "room-new", 2),))

    def test_S21_staff_role_change_cannot_reuse_consent(self):
        ticket, old, _ = self.approved()
        self.authority.staff.remove("tech-a")
        self.authority.admins.add("tech-a")
        self.authority.principals[self.ctx("tech-a")] = TrustedPrincipal(
            "tech-a", "new-session", "fixture-issuer", "ADMIN", "company", True, 100000)
        with self.assertRaises(ServiceDenied):
            self.desk.require_access(self.ctx("tech-a"), ticket)
        fresh = self.desk.start(self.ctx("tech-a"), ticket)
        self.assertNotEqual(fresh, old)
        with self.assertRaises(ServiceDenied):
            self.desk.require_access(self.ctx("tech-a"), ticket)
        self.desk.decide(self.ctx("care-a"), fresh, approve=True)
        self.desk.require_access(self.ctx("tech-a"), ticket)

    def test_S22_diagnostic_snapshot_never_substitutes_a_second_principal(self):
        ticket, _, _ = self.approved()
        original = self.authority.principal
        calls = []
        def changing(context):
            calls.append(context)
            return original(context if len(calls) == 1 else self.ctx("tech-b"))
        with patch.object(self.authority, "principal", side_effect=changing):
            result = ServiceDiagnosticAuthority(self.desk).resolve(
                ServiceDiagnosticContext(self.ctx("tech-a"), ticket), "home-a")
        self.assertEqual(result.actor.actor_id, "tech-a")
        self.assertEqual(result.grant.actor_id, "tech-a")
        self.assertEqual(len(calls), 1)

    def blocked_operation(self, operation, new_time):
        """Hold a real SQLite writer until the worker reaches BEGIN IMMEDIATE."""
        ready, go, attempted = (threading.Event() for _ in range(3))
        outcomes = []
        def worker():
            db = self.connect()
            db.set_trace_callback(lambda sql: attempted.set() if sql == "BEGIN IMMEDIATE" else None)
            ready.set()
            try:
                if not go.wait(10):
                    raise TimeoutError("worker not released")
                outcomes.append(operation(self.service(db)))
            except BaseException as error:
                outcomes.append(error)
            finally:
                db.close()
        thread = threading.Thread(target=worker)
        thread.start()
        self.assertTrue(ready.wait(10))
        self.db.execute("BEGIN IMMEDIATE")
        try:
            go.set()
            self.assertTrue(attempted.wait(10))
            self.now = new_time
        finally:
            self.db.commit()
            thread.join(10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(outcomes), 1)
        return outcomes[0]

    def test_S23_approval_and_expiry_use_time_after_writer_lock(self):
        ticket = self.assigned()
        request = self.desk.start(self.ctx("tech-a"), ticket)
        result = self.blocked_operation(
            lambda desk: desk.decide(self.ctx("care-a"), request, approve=True), 200)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["expires_at"], 2000)
        result = self.blocked_operation(
            lambda desk: desk.require_access(self.ctx("tech-a"), ticket), 2000)
        self.assertIsInstance(result, ServiceDenied)
        self.assertEqual(self.db.execute("SELECT state FROM service_access_requests WHERE request_id=?",
                                         (request,)).fetchone()[0], "EXPIRED")

    def test_S24_audit_failure_rolls_back_approval_and_dispatch_cursor(self):
        ticket = self.ticket()
        with patch.object(self.desk, "_audit", side_effect=sqlite3.OperationalError("fixture write failure")):
            with self.assertRaises(sqlite3.OperationalError):
                self.desk.assign(self.ctx("admin"), ticket, round_robin=True)
        self.assertIsNone(self.db.execute("SELECT assignee_id FROM service_tickets WHERE ticket_id=?",
                                          (ticket,)).fetchone()[0])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM service_assignment_cursor").fetchone()[0], 0)
        self.assertEqual(self.desk.assign(self.ctx("admin"), ticket, round_robin=True), "tech-a")
        request = self.desk.start(self.ctx("tech-a"), ticket)
        with patch.object(self.desk, "_audit", side_effect=sqlite3.OperationalError("fixture write failure")):
            with self.assertRaises(sqlite3.OperationalError):
                self.desk.decide(self.ctx("care-a"), request, approve=True)
        self.assertEqual(self.db.execute("SELECT state,grant_id FROM service_access_requests WHERE request_id=?",
                                         (request,)).fetchone(), ("PENDING", None))
        self.assertFalse(self.db.in_transaction)
        self.desk.decide(self.ctx("care-a"), request, approve=True)

    def test_S25_restart_preserves_pending_revoke_and_dispatch_cursor(self):
        ticket = self.ticket()
        self.desk.assign(self.ctx("admin"), ticket, round_robin=True)
        request = self.desk.start(self.ctx("tech-a"), ticket)
        self.db.close()
        self.db = self.connect()
        self.desk = self.service()
        self.assertEqual(self.desk.start(self.ctx("tech-a"), ticket), request)
        self.desk.decide(self.ctx("care-a"), request, approve=True)
        self.desk.revoke(self.ctx("care-a"), request)
        self.db.close()
        self.db = self.connect()
        self.desk = self.service()
        with self.assertRaises(ServiceDenied):
            self.desk.require_access(self.ctx("tech-a"), ticket)
        self.assertEqual(self.desk.assign(self.ctx("admin"), self.ticket(), round_robin=True), "tech-b")

    def test_S26_concurrent_revoke_and_read_deny_every_subsequent_read(self):
        ticket, request, _ = self.approved()
        barrier, outcomes = threading.Barrier(2), []
        def worker(revoke):
            db = self.connect()
            try:
                barrier.wait()
                desk = self.service(db)
                if revoke:
                    desk.revoke(self.ctx("care-a"), request)
                else:
                    desk.require_access(self.ctx("tech-a"), ticket)
                outcomes.append("OK")
            except ServiceDenied:
                outcomes.append("DENIED")
            finally:
                db.close()
        threads = [threading.Thread(target=worker, args=(flag,)) for flag in (True, False)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(10)
        self.assertEqual(len(outcomes), 2)
        self.assertIn("OK", outcomes)
        with self.assertRaises(ServiceDenied):
            self.desk.require_access(self.ctx("tech-a"), ticket)

    def test_S27_invalid_persisted_node_scope_fails_closed(self):
        ticket, request, _ = self.approved()
        self.db.execute("UPDATE service_access_requests SET node_scope_json=? WHERE request_id=?",
                        ('["node-a"]', request))
        with self.assertRaises(ServiceDenied):
            self.desk.require_access(self.ctx("tech-a"), ticket)

    def test_S28_production_service_routes_remain_absent_with_actor_header(self):
        api = JsonApi()
        for method, path in (("POST", "/v1/homes/home-a/service-tickets"),
                             ("GET", "/v1/service-tickets"),
                             ("POST", "/v1/service-tickets/ticket/start"),
                             ("POST", "/v1/service-access/request/approve"),
                             ("POST", "/v1/service-access/request/revoke")):
            status = []
            body = b"{}"
            result = b"".join(api({"REQUEST_METHOD": method, "PATH_INFO": path,
                                   "HTTP_X_ACTOR_ID": "admin", "HTTP_VERIFIED": "true",
                                   "CONTENT_LENGTH": str(len(body)), "wsgi.input": io.BytesIO(body)},
                                  lambda s, h: status.append(s)))
            self.assertEqual(status, ["404 Not Found"])
            self.assertEqual(json.loads(result), {"error": "route_not_found"})

    def test_S29_consent_to_read_outcome_fences_device_generation_and_inflight_revoke(self):
        ticket = self.assigned()
        request = self.desk.start(self.ctx("tech-a"), ticket)
        context = ServiceDiagnosticContext(self.ctx("tech-a"), ticket)
        records = [TechnicalRecord("home-a", 1, "node-a", "a"*64, 95,
                                   {"connectivity": "HEALTHY", "resident_name": "private"}, 1)]
        class Source:
            after_read = None
            def page(self, home, epoch, offset, limit):
                if self.after_read:
                    self.after_read()
                return TechnicalPage("fixture-revision", tuple(records))
        source = Source()
        view = DiagnosticReadService(DiagnosticAuthorizer(ServiceDiagnosticAuthority(self.desk)),
                                     clock=lambda: self.now, limits=DiagnosticLimits(2, 10000, 2, 80, 20),
                                     technical_source=source)
        self.assertEqual(view.read(context, "home-a", "health").status, 403)
        self.desk.decide(self.ctx("care-a"), request, approve=True)
        result = view.read(context, "home-a", "health")
        self.assertEqual(result.status, 200)
        self.assertEqual(result.body["devices"][0]["device_id"], "node-a")
        self.assertNotIn("private", json.dumps(result.body))
        self.assertIn(("Cache-Control", "no-store"), result.headers)
        for device, generation in (("node-foreign", 1), ("node-a", 2), ("node-a", None)):
            records[:] = [TechnicalRecord("home-a", 1, device, "a"*64, 95, {}, generation)]
            self.assertEqual(view.read(context, "home-a", "health").status, 403)
        records[:] = [TechnicalRecord("home-a", 1, "hub-a", "a"*64, 95, {})]
        self.assertEqual(view.read(context, "home-a", "health").status, 200)
        source.after_read = lambda: self.desk.revoke(self.ctx("care-a"), request)
        result = view.read(context, "home-a", "health")
        self.assertEqual(result.status, 403)
        self.assertEqual(result.body, {"error": "diagnostic_not_authorized"})

    def test_S30_persisted_expiry_cannot_extend_the_configured_fixed_grant(self):
        ticket, request, _ = self.approved()
        self.db.execute("UPDATE service_access_requests SET expires_at=100000 WHERE request_id=?",
                        (request,))
        with self.assertRaises(ServiceDenied):
            self.desk.require_access(self.ctx("tech-a"), ticket)


if __name__ == "__main__":
    unittest.main()
