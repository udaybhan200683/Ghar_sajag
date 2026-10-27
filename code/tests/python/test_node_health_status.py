"""Authenticated current-state NodeHealth ingest and expiry tests."""
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from ghar_sajag.cloud_client_identity import TimeReadiness, VerifiedHubContext
from ghar_sajag.database import initialize_sqlite
from ghar_sajag.node_health_policy import DeploymentPolicy, NodeHealthPolicy
from ghar_sajag.node_health_status import NodeHealthRejected, NodeHealthStatusStore
from ghar_sajag.ownership_registry import (
    AuthorizedHomeOperation, HubOwnershipRegistry, VerifiedHubIdentity,
    VerifiedNodeEnrollment,
)
from ghar_sajag.http_api import JsonApi
from ghar_sajag.model import Resident
from ghar_sajag.service import GharSajagService


class NodeHealthStatusTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:", isolation_level=None)
        self.db.row_factory = sqlite3.Row
        initialize_sqlite(self.db)
        self.db.execute("INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) VALUES('home-a','Fixture','UTC',1,1)")
        self.owner = HubOwnershipRegistry(self.db)
        self.identity = VerifiedHubIdentity("hub-a", "a" * 64, "fixture-proof")
        self.owner.register_unclaimed_identity(self.identity, 1)
        self.owner.claim_home(self.identity, AuthorizedHomeOperation(
            "fixture", "home-a", "CLAIM_HUB", "fixture-claim"), 2)
        self.owner.enroll_node(self.identity, AuthorizedHomeOperation(
            "fixture", "home-a", "ENROLL_NODE", "fixture-enroll"),
            VerifiedNodeEnrollment("c3-146393c5d158", "bathroom", 1,
                                   "b" * 64, "fixture-node-proof"), 3)
        self.context = VerifiedHubContext(
            "hub-a", "home-a", 1, "c" * 64, "a" * 64, True,
            TimeReadiness.TRUSTED)
        self.store = NodeHealthStatusStore(
            self.db, DeploymentPolicy(NodeHealthPolicy(300),
                                      {"c3-146393c5d158": "configured"}))
        self.body = {
            "home_id": "home-a", "physical_node_id": "c3-146393c5d158",
            "logical_node_id": "bathroom", "node_enrollment_generation": 1,
            "session_id": 7, "boot_generation": 1, "source_revision": 1,
            "contact_kind": "NODE_HEALTH", "profile_id": "configured",
            "heartbeat_seconds": 300, "offline_seconds": 910,
            "hub_received_at": 1000, "hub_snapshot_at": 1001,
        }

    def tearDown(self):
        self.db.close()

    def test_authenticated_profiled_contact_and_independent_freshness(self):
        self.assertTrue(self.store.ingest(self.context, "home-a", self.body, 1002)["accepted"])
        refreshed = {**self.body, "source_revision": 2, "hub_snapshot_at": 1900}
        self.store.ingest(self.context, "home-a", refreshed, 1901)
        self.assertEqual(self.store.latest("home-a", 1910)[0]["status"], "ONLINE")
        self.assertEqual(self.store.latest("home-a", 1911)[0]["status"], "OFFLINE")
        self.assertEqual(self.store.latest("home-a", 2092)[0]["status"], "UNKNOWN")
        self.assertEqual(self.store.latest("home-a", 2092)[0]["coverage"], "UNKNOWN")

    def test_rejects_untrusted_context_home_epoch_node_profile_and_replay(self):
        with self.assertRaisesRegex(NodeHealthRejected, "trusted_time"):
            untrusted = VerifiedHubContext(
                **{**self.context.__dict__, "time_readiness": TimeReadiness.UNTRUSTED})
            self.store.ingest(untrusted, "home-a", self.body, 1002)
        with self.assertRaisesRegex(NodeHealthRejected, "wrong_home"):
            self.store.ingest(self.context, "home-b", self.body, 1002)
        with self.assertRaisesRegex(NodeHealthRejected, "untrusted_node_profile"):
            self.store.ingest(self.context, "home-a", {**self.body, "offline_seconds": 999}, 1002)
        with self.assertRaisesRegex(NodeHealthRejected, "node_not_currently_enrolled"):
            self.store.ingest(self.context, "home-a", {**self.body, "logical_node_id": "other"}, 1002)
        self.store.ingest(self.context, "home-a", self.body, 1002)
        with self.assertRaisesRegex(NodeHealthRejected, "replayed_or_out_of_order"):
            self.store.ingest(self.context, "home-a", self.body, 1003)

    def test_rechecks_transfer_epoch_and_rejects_boolean_as_integer(self):
        with self.assertRaisesRegex(NodeHealthRejected, "invalid_node_health_number"):
            self.store.ingest(self.context, "home-a", {**self.body, "session_id": True}, 1002)
        self.db.execute("INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) VALUES('home-b','Fixture B','UTC',1,1)")
        self.owner.begin_transfer(self.identity, AuthorizedHomeOperation(
            "fixture", "home-a", "TRANSFER_HUB", "fixture-transfer"), "home-b", 4)
        with self.assertRaisesRegex(NodeHealthRejected, "stale_hub_home_or_epoch"):
            self.store.ingest(self.context, "home-a", self.body, 1002)

    def test_read_model_rejects_replaced_hub_key_fingerprint(self):
        self.store.ingest(self.context, "home-a", self.body, 1002)
        self.db.execute(
            "UPDATE hub_ownership_registry SET identity_key_fingerprint=? WHERE hub_device_id=?",
            ("d" * 64, "hub-a"),
        )
        unknown = self.store.latest("home-a", 1003)
        self.assertEqual(len(unknown), 1)
        self.assertEqual((unknown[0]["status"], unknown[0]["coverage"]), ("UNKNOWN", "UNKNOWN"))
        self.assertIsNone(unknown[0]["hub_received_at"])
        self.assertIsNone(unknown[0]["backend_received_at"])
        self.assertIsNone(self.store.latest_hub_contact("home-a"))
        self.assertIsNone(self.store.latest_hub_backend_contact("home-a"))

    def test_never_seen_active_enrollment_is_unknown_until_authenticated_contact(self):
        unknown = self.store.latest("home-a", 1000)
        self.assertEqual(len(unknown), 1)
        self.assertEqual((unknown[0]["physical_node_id"], unknown[0]["logical_node_id"],
                          unknown[0]["status"], unknown[0]["coverage"]),
                         ("c3-146393c5d158", "bathroom", "UNKNOWN", "UNKNOWN"))
        self.assertIsNone(unknown[0]["node_contact_age_seconds"])
        self.assertFalse(unknown[0]["source_fresh"])
        self.assertEqual(self.store.latest("home-b", 1000), [])
        self.store.ingest(self.context, "home-a", self.body, 1002)
        self.assertEqual(self.store.latest("home-a", 1002)[0]["status"], "ONLINE")
        self.owner.revoke_node(self.identity, AuthorizedHomeOperation(
            "fixture", "home-a", "REVOKE_NODE", "fixture-revoke"),
            "c3-146393c5d158", 1, 1003)
        self.assertEqual(self.store.latest("home-a", 1003), [])

    def test_authenticated_ingest_flows_to_snapshot_with_distinct_times(self):
        clock = [1002]
        service = GharSajagService()
        service.homes.create("home-a", "Fixture", "Asia/Kolkata", "en-IN", "owner-a",
                             [Resident("resident-a", "Resident", True, 1)], 1)
        service.queries.node_health_status = self.store
        api = JsonApi(service=service, now=lambda: clock[0],
                      node_health_status=self.store)
        with self.assertRaisesRegex(PermissionError, "verified_hub_context_required"):
            api.dispatch("POST", "/v1/homes/home-a/node-health", "", self.body,
                         request_context={"gs.verified_hub": "hub-a"})
        status, receipt = api.dispatch("POST", "/v1/homes/home-a/node-health", "",
                                       self.body, request_context=self.context)
        self.assertTrue(status.startswith("200"))
        self.assertEqual(receipt["status"], "ACCEPTED")
        snapshot = service.queries.snapshot("home-a", "owner-a", clock[0])
        node = snapshot["node_health"][0]
        self.assertEqual((node["status"], node["hub_received_at"],
                          node["backend_received_at"], snapshot["fetched_at"]),
                         ("ONLINE", 1000, 1002, 1002))
        self.assertEqual(snapshot["last_node_health_hub_at"], 1001)
        self.assertEqual(snapshot["last_node_health_backend_at"], 1002)
        self.assertFalse(service.queries.snapshot("home-a", "owner-a", 991)["hub_reachable"])
        clock[0] = 1193
        stale = service.queries.snapshot("home-a", "owner-a", clock[0])
        self.assertFalse(stale["hub_reachable"])
        self.assertEqual(stale["node_health"][0]["status"], "UNKNOWN")
