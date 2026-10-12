"""Composition tests for the file-backed authenticated Hub commit API."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from ghar_sajag.durable_api import open_durable_event_api
from ghar_sajag.model import Resident
from ghar_sajag.service import GharSajagService


class DurableApiCompositionTest(unittest.TestCase):
    def test_requires_file_store_and_trusted_authorizer(self):
        with tempfile.TemporaryDirectory() as directory:
            service = GharSajagService()
            with self.assertRaisesRegex(ValueError, "trusted_hub_authorizer_required"):
                open_durable_event_api(service, Path(directory) / "missing-auth.sqlite", None)
            with self.assertRaisesRegex(ValueError, "requires_file_database"):
                open_durable_event_api(service, ":memory:", lambda *_: True)

    def test_committed_event_survives_reopen_and_uses_existing_query_projection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "backend.sqlite"
            service = GharSajagService()
            service.homes.create(
                "home-1", "Fixture", "Asia/Kolkata", "en-IN", "owner-1",
                [Resident("resident-1", "Resident", True, 100)], 100,
            )
            api = open_durable_event_api(
                service, path,
                lambda context, home, key: (
                    context.get("gs.verified_hub") == "hub-1" and home == "home-1" and
                    key == {"physical_device_id": "device-1", "logical_node_id": "room-1",
                            "origin_session_id": 4, "event_sequence": 9}
                ),
                now=lambda: 120,
            )
            with sqlite3.connect(path) as db:
                db.execute(
                    "INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) VALUES('home-1','Fixture','UTC',100,100)"
                )
            body = {
                "event_key": {"physical_device_id": "device-1", "logical_node_id": "room-1",
                              "origin_session_id": 4, "event_sequence": 9},
                "event_type": "MOTION", "occurred_at": 110, "hub_received_at": 115,
                "location": "bathroom", "uncertainty_s": 1, "payload": {},
            }
            context = {"gs.verified_hub": "hub-1"}
            status, receipt = api.api.dispatch(
                "POST", "/v1/homes/home-1/events", "", body,
                request_context=context,
            )
            self.assertTrue(status.startswith("201"))
            self.assertEqual(receipt["status"], "COMMITTED")
            verification = sqlite3.connect(path)
            self.assertEqual(verification.execute("SELECT COUNT(*) FROM durable_event_commits").fetchone()[0], 1)
            verification.close()
            event_id = api.db.execute("SELECT canonical_event_id FROM events").fetchone()[0]
            api.close()

            api = open_durable_event_api(service, path,
                lambda context, home, key: context.get("gs.verified_hub") == "hub-1" and home == "home-1",
                now=lambda: 121,
            )
            retry_status, retry = api.api.dispatch(
                "POST", "/v1/homes/home-1/events", "", body,
                request_context=context,
            )
            self.assertTrue(retry_status.startswith("200"))
            self.assertTrue(retry["duplicate"])
            snapshot = service.queries.snapshot("home-1", "owner-1", 121)
            self.assertEqual(snapshot["latest_activity"]["event_id"], event_id)
            self.assertEqual(snapshot["latest_activity"]["occurred_at"], 110)
            self.assertEqual(snapshot["latest_activity"]["location"], "bathroom")
            api.close()


if __name__ == "__main__":
    unittest.main()
