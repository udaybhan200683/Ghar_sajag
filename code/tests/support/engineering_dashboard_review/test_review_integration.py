"""Real host-event -> existing durable API/query -> inactive trace review.

Fixture authorization is local test input. No production diagnostic route exists.
"""
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from ghar_sajag.durable_api import open_durable_event_api
from ghar_sajag.durable_commit import EventCommitConflict
from ghar_sajag.model import Resident
from ghar_sajag.service import GharSajagService
from review_model import FixtureGrant, Observation, canonical_key, trace

ROOT = Path(__file__).resolve().parents[3]


class ActualApiFixture:
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gs125-review-api-")
        self.path = Path(self.temp.name) / "events.sqlite"
        self.body = json.loads((ROOT / "build/p0_cloud_sync_request.json").read_text())
        self.event = json.loads((ROOT / "build/p0_product_event.json").read_text())
        self.key = self.body["event_key"]
        self.home = "home"
        self.service = GharSajagService()
        self.service.homes.create(self.home, "Host review fixture", "Asia/Kolkata", "en-IN", "fixture-owner",
                                  [Resident("fixture-resident", "Fixture", True, 1700000000)], 1700000000)
        self.api = self.open()
        self.api.db.execute("INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) VALUES(?,?,?,?,?)",
                            (self.home, "Host review fixture", "UTC", 1700000000, 1700000000))
        self.context = {"gs.verified_hub": "fixture-hub"}

    def open(self):
        return open_durable_event_api(self.service, self.path,
            lambda context, home, key: context.get("gs.verified_hub") == "fixture-hub"
                and home == self.home and key == self.key,
            now=lambda: 1700000100)

    def commit(self, body=None, context=None, home=None):
        return self.api.api.dispatch("POST", f"/v1/homes/{home or self.home}/events", "",
            self.body if body is None else body,
            request_context=self.context if context is None else context)

    def reopen(self):
        self.api.close()
        self.api = self.open()

    def close(self):
        self.api.close()
        self.temp.cleanup()

    def review(self):
        status, receipt = self.commit()
        assert status.startswith("201") and receipt["status"] == "COMMITTED"
        original = self.api.db.execute("SELECT canonical_event_id,location,occurred_at,hub_received_at FROM events").fetchone()
        assert original["canonical_event_id"] == canonical_key(self.key)
        # The Node-local key lacks physical identity. The existing authenticated
        # Hub/CloudSync request supplies the qualified original identity. Preserve
        # both representations and check every origin field, never literal equality.
        assert self.event["event_id"] == (
            f'{self.key["logical_node_id"]}:{self.key["origin_session_id"]}:{self.key["event_sequence"]}')
        assert self.event["location"] == self.body["location"]
        assert self.event["occurred_at"] == self.body["occurred_at"]
        observation = Observation(1, self.home, original["canonical_event_id"], "backend_committed", "PASS",
            "DurableEventCommit.commit", "actual isolated file-SQLite transaction and query",
            "BACKEND_FIXTURE", 1, "fixture-backend", 100, "OBSERVED")
        view = trace(self.home, self.key, [observation],
            FixtureGrant("fixture-technician", self.home, 200, frozenset({"READ_DIAGNOSTICS"})), 100)
        snapshot = self.service.queries.snapshot(self.home, "fixture-owner", 1700000100)
        return {"scope": "INACTIVE_DESIGN_REVIEW", "product_status": "PARTIAL",
                "environment": "HOST_SIMULATION_AND_LOCAL_API", "source_head": "77e29d44c57f0851f78358049c288323c985d2e7",
                "trace": view, "caregiver_snapshot": snapshot,
                "node_local_event_id": self.event["event_id"],
                "original_location": original["location"], "original_occurred_at": original["occurred_at"],
                "original_hub_received_at": original["hub_received_at"],
                "physical_status": "NOT_RUN", "commercial_authentication": "BLOCKED",
                "controls": "UNAVAILABLE", "installation_result": "NOT_TESTED"}


class ActualIntegrationPreparationTest(unittest.TestCase):
    def setUp(self):
        self.f = ActualApiFixture()
        self.addCleanup(self.f.close)

    def test_actual_host_generated_key_and_room_reach_real_api_query(self):
        view = self.f.review()
        latest = view["caregiver_snapshot"]["latest_activity"]
        self.assertEqual(latest["event_id"], canonical_key(self.f.key))
        self.assertEqual(view["node_local_event_id"], self.f.event["event_id"])
        self.assertEqual(latest["location"], self.f.body["location"])
        self.assertEqual(latest["occurred_at"], self.f.body["occurred_at"])
        self.assertEqual(view["trace"]["stages"][8]["result"], "PASS")
        self.assertTrue(all(s["result"] == "UNKNOWN" for s in view["trace"]["stages"][:8]))
        self.assertEqual(view["product_status"], "PARTIAL")

    def test_actual_commit_survives_reopen_and_duplicate_retry_one_row(self):
        self.f.commit()
        self.f.reopen()
        status, reply = self.f.commit()
        self.assertEqual(status, "200 OK")
        self.assertTrue(reply["duplicate"])
        row = self.f.api.db.execute("SELECT canonical_event_id,occurred_at,hub_received_at,location FROM events").fetchone()
        self.assertEqual(row["canonical_event_id"], canonical_key(self.f.key))
        self.assertEqual(row["occurred_at"], self.f.body["occurred_at"])
        self.assertEqual(row["hub_received_at"], self.f.body["hub_received_at"])
        self.assertEqual(row["location"], self.f.body["location"])
        self.assertEqual(self.f.api.db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 1)

    def test_conflicting_same_key_payload_rejected_original_room_preserved(self):
        self.f.commit()
        with self.assertRaises(EventCommitConflict):
            self.f.commit(body={**self.f.body, "location": "wrong-room"})
        self.assertEqual(self.f.api.db.execute("SELECT location FROM events").fetchone()[0], self.f.body["location"])

    def test_missing_or_http_spoofed_trusted_context_denied_before_commit(self):
        for context in ({}, {"HTTP_GS_VERIFIED_HUB": "fixture-hub"}, {"gs.verified_hub": "wrong-hub"}):
            with self.subTest(context=context), self.assertRaises(PermissionError):
                self.f.commit(context=context)
        self.assertEqual(self.f.api.db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 0)

    def test_foreign_home_and_wrong_node_authorization_denied(self):
        with self.assertRaises(PermissionError):
            self.f.commit(home="foreign-home")
        body = copy.deepcopy(self.f.body)
        body["event_key"]["physical_device_id"] = "wrong-node"
        with self.assertRaises(PermissionError):
            self.f.commit(body=body)
        self.assertEqual(self.f.api.db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 0)

    def test_actual_caregiver_query_household_denial(self):
        self.f.commit()
        with self.assertRaises(PermissionError):
            self.f.service.queries.snapshot(self.f.home, "unknown-actor", 1700000100)
        with self.assertRaises(PermissionError):
            self.f.service.queries.snapshot("foreign-home", "fixture-owner", 1700000100)

    def test_closed_storage_never_returns_committed(self):
        self.f.api.close()
        with self.assertRaises(sqlite3.Error):
            self.f.commit()
        self.f.api = self.f.open()
        self.assertEqual(self.f.api.db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 0)

    def test_diagnostic_fixture_grant_not_existing_caregiver_read(self):
        self.f.commit()
        # Existing authorized caregiver query works, but does not authorize the draft diagnostics.
        self.assertIsNotNone(self.f.service.queries.snapshot(self.f.home, "fixture-owner", 1700000100)["latest_activity"])
        with self.assertRaises(PermissionError):
            trace(self.f.home, self.f.key, [], FixtureGrant("fixture-owner", self.f.home, 200, frozenset({"read"})), 100)


if __name__ == "__main__":
    unittest.main()
