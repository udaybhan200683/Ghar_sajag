"""Production ownership policy and event commit guard on an isolated SQLite file.

The test capability records stand in only for trusted GS-109 verifier outputs.
These tests exercise the real registry/transaction code, not certificate proof.
"""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from ghar_sajag.database import initialize_sqlite
from ghar_sajag.durable_commit import DurableEventCommit
from ghar_sajag.http_api import JsonApi
from ghar_sajag.ownership_registry import (
    AuthorizedHomeOperation,
    HubOwnershipRegistry,
    OwnershipConflict,
    TransferBlocked,
    VerifiedHubIdentity,
    VerifiedNodeEnrollment,
)


class HubOwnershipRegistryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "ownership.sqlite"
        self.db = self.connect()
        with self.db:
            for home in ("home-a", "home-b", "home-other"):
                self.db.execute(
                    "INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) VALUES(?,?, 'UTC',1,1)",
                    (home, home),
                )
        self.registry = HubOwnershipRegistry(self.db)
        self.identity = VerifiedHubIdentity("hub-permanent-1", "a" * 64, "proof-hub-1")
        self.claim = AuthorizedHomeOperation("installer-1", "home-a", "CLAIM_HUB", "auth-claim-1")
        self.registry.register_unclaimed_identity(self.identity, 10)
        self.registry.claim_home(self.identity, self.claim, 11)
        self.enroll_node("node-physical-1", "room-bathroom", 1, "b" * 64)
        self.api = JsonApi(durable_events=DurableEventCommit(self.db),
                           hub_ownership_registry=self.registry, now=lambda: 100)

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def connect(self):
        db = sqlite3.connect(self.path, isolation_level=None)
        initialize_sqlite(db)
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def enroll_node(self, physical, logical, generation, fingerprint):
        operation = AuthorizedHomeOperation("installer-1", "home-a", "ENROLL_NODE", f"auth-enroll-{generation}")
        self.registry.enroll_node(self.identity, operation, VerifiedNodeEnrollment(
            physical, logical, generation, fingerprint, f"node-proof-{generation}"), 20 + generation)

    @staticmethod
    def body(sequence=1, generation=1, event_type="MOTION"):
        return {
            "cloudsync_version": 2,
            "node_enrollment_generation": generation,
            "event_key": {"physical_device_id": "node-physical-1",
                          "logical_node_id": "room-bathroom",
                          "origin_session_id": 77, "event_sequence": sequence},
            "event_type": event_type, "occurred_at": 50 + sequence,
            "hub_received_at": 60 + sequence, "location": "bathroom",
            "payload": {},
        }

    @staticmethod
    def context(epoch=1, hub="hub-permanent-1", fingerprint="a" * 64):
        # This internal context is populated only by an eventual trusted device
        # authenticator. HTTP headers are not promoted to these fields.
        return {"gs.verified_hub": hub, "gs.hub_key_fingerprint": fingerprint,
                "gs.installation_epoch": epoch}

    def submit(self, home, body, context=None):
        return self.api.dispatch("POST", f"/v1/homes/{home}/events", "", body,
                                 request_context=context or self.context())

    def test_registered_home_node_commit_retry_and_restart(self):
        body = self.body(event_type="CALL_FAMILY")
        status, receipt = self.submit("home-a", body)
        self.assertTrue(status.startswith("201"))
        self.assertEqual(receipt["status"], "COMMITTED")
        self.assertFalse(receipt["duplicate"])
        self.assertEqual(tuple(self.db.execute(
            "SELECT hub_device_id,ownership_epoch,node_enrollment_generation FROM durable_event_commits"
        ).fetchone()), ("hub-permanent-1", 1, 1))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM alerts").fetchone()[0], 1)
        self.assertEqual(self.submit("home-a", body)[1]["duplicate"], True)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 1)
        self.db.close()

        self.db = self.connect()
        self.registry = HubOwnershipRegistry(self.db)
        self.api = JsonApi(durable_events=DurableEventCommit(self.db),
                           hub_ownership_registry=self.registry, now=lambda: 101)
        status, receipt = self.submit("home-a", body)
        self.assertTrue(status.startswith("200"))
        self.assertTrue(receipt["duplicate"])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM alerts").fetchone()[0], 1)

    def test_identity_and_authorization_fail_closed(self):
        with self.assertRaisesRegex(OwnershipConflict, "already_registered"):
            self.registry.register_unclaimed_identity(self.identity, 12)
        with self.assertRaisesRegex(OwnershipConflict, "permanent_hub_identity_key_changed"):
            self.registry.register_unclaimed_identity(
                VerifiedHubIdentity(self.identity.hub_device_id, "c" * 64, "proof-replaced"), 12)
        with self.assertRaisesRegex(OwnershipConflict, "hub_not_claimable"):
            self.registry.claim_home(
                self.identity,
                AuthorizedHomeOperation("installer-2", "home-b", "CLAIM_HUB", "auth-conflicting-claim"),
                13,
            )
        self.assertEqual(tuple(self.db.execute(
            "SELECT state,home_id,installation_epoch FROM hub_ownership_registry WHERE hub_device_id=?",
            (self.identity.hub_device_id,),
        ).fetchone()), ("ACTIVE", "home-a", 1))
        for context in (
            {"HTTP_X_ACTOR_ID": "hub-permanent-1"},
            self.context(epoch=2),
            self.context(hub="other-hub"),
            self.context(fingerprint="c" * 64),
        ):
            with self.assertRaises(PermissionError):
                self.submit("home-a", self.body(sequence=2), context)
        with self.assertRaises(PermissionError):
            self.submit("home-other", self.body(sequence=3))
        legacy = self.body(sequence=4)
        legacy.pop("cloudsync_version")
        legacy.pop("node_enrollment_generation")
        with self.assertRaises(PermissionError):
            self.submit("home-a", legacy)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM durable_event_commits").fetchone()[0], 0)
        print("P0-P2D-010 PASS permanent identity, exact Home ownership and unverified claims fail closed")

    def test_generation_replacement_revocation_and_old_event_replay(self):
        first = self.body(sequence=1, generation=1)
        self.assertTrue(self.submit("home-a", first)[0].startswith("201"))
        self.enroll_node("node-physical-1", "room-bathroom", 2, "d" * 64)
        # A lost COMMITTED response for work already durably accepted under
        # generation 1 remains safely retryable after generation 2 replaces it.
        old_duplicate = self.submit("home-a", first)
        self.assertTrue(old_duplicate[0].startswith("200"))
        self.assertTrue(old_duplicate[1]["duplicate"])
        conflicting_retry = self.body(sequence=1, generation=1, event_type="DOOR_OPEN")
        with self.assertRaisesRegex(ValueError, "event_key_payload_conflict"):
            self.submit("home-a", conflicting_retry)
        stale = self.body(sequence=2, generation=1)
        with self.assertRaises(PermissionError):
            self.submit("home-a", stale)
        with self.assertRaisesRegex(OwnershipConflict, "node_enrollment_generation_not_globally_monotonic"):
            self.enroll_node("node-physical-1", "room-bathroom", 2, "d" * 64)
        current = self.body(sequence=2, generation=2)
        self.assertTrue(self.submit("home-a", current)[0].startswith("201"))
        self.registry.revoke_node(self.identity,
            AuthorizedHomeOperation("installer-1", "home-a", "REVOKE_NODE", "auth-revoke-node"),
            "node-physical-1", 2, 30)
        with self.assertRaises(PermissionError):
            self.submit("home-a", self.body(sequence=3, generation=2))
        current_duplicate = self.submit("home-a", current)
        self.assertTrue(current_duplicate[1]["duplicate"])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 2)
        print("P0-P2D-011 PASS Node generation fencing preserves only exact committed retries")

    def test_transfer_epoch_fences_old_home_and_preserves_old_data(self):
        pending = self.body(sequence=1)
        self.assertTrue(self.submit("home-a", pending)[0].startswith("201"))
        operation = AuthorizedHomeOperation("owner-a", "home-a", "TRANSFER_HUB", "auth-transfer-1")
        self.assertEqual(self.registry.begin_transfer(self.identity, operation, "home-b", 40), 2)
        with self.assertRaises(PermissionError):
            self.submit("home-a", self.body(sequence=2), self.context(epoch=1))
        with self.assertRaises(PermissionError):
            self.submit("home-b", self.body(sequence=3), self.context(epoch=2))
        with self.assertRaisesRegex(TransferBlocked, "disposition_and_local_rebind_unapproved"):
            self.registry.complete_transfer(self.identity, "home-b", 41)
        row = self.db.execute(
            "SELECT state,home_id,pending_home_id,installation_epoch FROM hub_ownership_registry WHERE hub_device_id=?",
            (self.identity.hub_device_id,),
        ).fetchone()
        self.assertEqual(tuple(row), ("TRANSFER_PENDING", "home-a", "home-b", 2))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM events WHERE home_id='home-a'").fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM events WHERE home_id='home-b'").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM hub_ownership_history WHERE hub_device_id=?",
                                         (self.identity.hub_device_id,)).fetchone()[0], 3)
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("DELETE FROM households WHERE home_id='home-a'")
        print("P0-P2D-012 PASS transfer epoch blocks both Homes and preserves old-Home data")

    def test_node_identity_cannot_be_active_under_two_homes(self):
        second_hub = VerifiedHubIdentity("hub-permanent-2", "c" * 64, "proof-hub-2")
        self.registry.register_unclaimed_identity(second_hub, 31)
        self.registry.claim_home(second_hub,
            AuthorizedHomeOperation("installer-2", "home-b", "CLAIM_HUB", "auth-claim-2"), 32)
        old_home_event = self.body(sequence=18, generation=1)
        self.assertTrue(self.submit("home-a", old_home_event)[0].startswith("201"))
        with self.assertRaisesRegex(OwnershipConflict, "node_identity_already_active"):
            self.registry.enroll_node(second_hub,
                AuthorizedHomeOperation("installer-2", "home-b", "ENROLL_NODE", "auth-node-home-b"),
                VerifiedNodeEnrollment("node-physical-1", "room-bathroom", 2,
                                       "d" * 64, "node-proof-home-b"), 33)
        self.assertEqual(tuple(self.db.execute(
            "SELECT hub_device_id,home_id,state FROM node_enrollment_history WHERE physical_node_id=? AND state='ACTIVE'",
            ("node-physical-1",),
        ).fetchone()), ("hub-permanent-1", "home-a", "ACTIVE"))
        self.registry.revoke_node(self.identity,
            AuthorizedHomeOperation("installer-1", "home-a", "REVOKE_NODE", "auth-revoke-for-rehome"),
            "node-physical-1", 1, 34)
        with self.assertRaisesRegex(OwnershipConflict, "node_enrollment_generation_not_globally_monotonic"):
            self.registry.enroll_node(second_hub,
                AuthorizedHomeOperation("installer-2", "home-b", "ENROLL_NODE", "auth-stale-generation"),
                VerifiedNodeEnrollment("node-physical-1", "room-bathroom", 1,
                                       "d" * 64, "node-proof-stale-generation"), 35)
        self.registry.enroll_node(second_hub,
            AuthorizedHomeOperation("installer-2", "home-b", "ENROLL_NODE", "auth-node-home-b"),
            VerifiedNodeEnrollment("node-physical-1", "room-bathroom", 2,
                                   "d" * 64, "node-proof-home-b"), 36)
        with self.assertRaises(PermissionError):
            self.submit("home-b", self.body(sequence=19, generation=1), self.context(epoch=1, hub="hub-permanent-2", fingerprint="c" * 64))
        current_home_event = self.body(sequence=20, generation=2)
        self.assertTrue(self.submit("home-b", current_home_event,
            self.context(epoch=1, hub="hub-permanent-2", fingerprint="c" * 64))[0].startswith("201"))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM events WHERE home_id='home-a'").fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM events WHERE home_id='home-b'").fetchone()[0], 1)
        print("P0-P2D-013 PASS Node re-home uses one active binding and globally monotonic generation")

    def test_commit_guard_runs_inside_write_transaction(self):
        observed = []
        def guard(db, home_id, body):
            observed.append(db.in_transaction)
            return HubOwnershipRegistry.authorize_cloud_event(
                db, self.context(), home_id, body)
        result = DurableEventCommit(self.db).commit(
            "home-a", self.body(sequence=9), 70, authorization_guard=guard)
        self.assertEqual(result["status"], "COMMITTED")
        self.assertEqual(observed, [True])


if __name__ == "__main__":
    unittest.main()
