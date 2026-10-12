"""Durable backend receipt and atomic business effects on a real SQLite file."""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from ghar_sajag.database import initialize_sqlite
from ghar_sajag.durable_commit import DurableEventCommit, EventCommitConflict
from ghar_sajag.http_api import JsonApi


class DurableEventCommitTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "events.sqlite"
        self.open_db()
        with self.db:
            self.db.execute("INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) VALUES('home-1','Home','UTC',1,1)")
            for caregiver, role in (("care-1", "PRIMARY"), ("care-2", "BACKUP")):
                self.db.execute("INSERT INTO caregivers(caregiver_id,display_name,created_at) VALUES(?,?,1)", (caregiver, caregiver))
                self.db.execute("INSERT INTO household_caregivers(home_id,caregiver_id,role) VALUES('home-1',?,?)", (caregiver, role))

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def open_db(self):
        self.db = sqlite3.connect(self.path)
        initialize_sqlite(self.db)
        self.committer = DurableEventCommit(self.db)

    @staticmethod
    def body(device="device-1", node="room-1", session=1, sequence=1, kind="CALL_FAMILY"):
        return {"event_key": {"physical_device_id": device, "logical_node_id": node,
                              "origin_session_id": session, "event_sequence": sequence},
                "event_type": kind, "occurred_at": 101, "hub_received_at": 102,
                "location": "kitchen", "payload": {}}

    def counts(self):
        return tuple(self.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                     for table in ("events", "durable_event_commits", "alerts", "notification_jobs",
                                   "durable_notification_outbox"))

    def test_first_duplicate_lost_response_and_restart(self):
        body = self.body()
        self.assertEqual(self.committer.commit("home-1", body, 110)["status"], "COMMITTED")
        self.assertEqual(self.counts(), (1, 1, 1, 2, 2))
        # The caller discards the first response and sends the same bytes again.
        self.assertTrue(self.committer.commit("home-1", body, 111)["duplicate"])
        self.assertEqual(self.counts(), (1, 1, 1, 2, 2))
        self.db.close()
        self.open_db()
        self.assertTrue(self.committer.commit("home-1", body, 112)["duplicate"])
        self.assertEqual(self.counts(), (1, 1, 1, 2, 2))
        self.assertEqual([row[0] for row in self.db.execute("SELECT state FROM durable_notification_outbox")],
                         ["PENDING", "PENDING"])
        self.assertEqual(len(self.committer.due_outbox(110)), 1)
        outbox_id = self.committer.due_outbox(110)[0][0]
        self.assertTrue(self.committer.mark_delivered(outbox_id, "provider-1"))
        self.assertTrue(self.committer.mark_delivered(outbox_id, "provider-1"))
        self.assertEqual(len(self.committer.due_outbox(110)), 0)
        self.assertEqual(len(self.committer.due_outbox(410)), 1)

    def test_conflicting_type_timestamp_payload_and_identity(self):
        original = self.body()
        self.committer.commit("home-1", original, 110)
        for replacement in (
            {**original, "event_type": "MOTION"},
            {**original, "occurred_at": 103},
            {**original, "payload": {"different": True}},
            {**original, "location": "door"},
        ):
            with self.assertRaises(EventCommitConflict):
                self.committer.commit("home-1", replacement, 111)
        self.assertEqual(self.counts(), (1, 1, 1, 2, 2))
        # Logical identity is part of the key; it creates a separate event.
        other = self.body(node="room-2")
        self.assertFalse(self.committer.commit("home-1", other, 112)["duplicate"])
        self.assertEqual(self.counts()[:2], (2, 2))

    def test_faults_rollback_all_effects_then_retry(self):
        points = ("before_event", "after_event", "after_business_effect", "after_outbox")
        for index, point in enumerate(points, start=1):
            body = self.body(sequence=index)
            before = self.counts()
            with self.assertRaisesRegex(RuntimeError, "injected_"):
                self.committer.commit("home-1", body, 110, fail_at=point)
            self.assertEqual(self.counts(), before, point)
            self.assertFalse(self.committer.commit("home-1", body, 111)["duplicate"])
        self.assertEqual(self.counts(), (4, 4, 4, 8, 8))

    def test_sqlite_commit_failure_rolls_back(self):
        # A deferred FK is checked by SQLite at COMMIT, after every INSERT ran.
        self.db.execute("CREATE TABLE parent_guard(id INTEGER PRIMARY KEY)")
        self.db.execute("CREATE TABLE commit_guard(parent INTEGER REFERENCES parent_guard(id) DEFERRABLE INITIALLY DEFERRED)")
        self.db.commit()
        original = self.committer._fault

        def fail_at_commit(selected, point):
            if point == "commit_failure":
                self.db.execute("INSERT INTO commit_guard(parent) VALUES(1)")
            else:
                original(selected, point)

        self.committer._fault = fail_at_commit
        body = self.body()
        with self.assertRaises(sqlite3.Error):
            self.committer.commit("home-1", body, 110)
        self.assertEqual(self.counts(), (0, 0, 0, 0, 0))
        self.committer._fault = original
        self.assertFalse(self.committer.commit("home-1", body, 111)["duplicate"])

    def test_sessions_nodes_high_rate_and_quiet_door(self):
        for device, node, session, sequence in (("device-1", "room-1", 1, 1),
                                                ("device-1", "room-1", 2, 1),
                                                ("device-2", "room-2", 1, 1)):
            body = self.body(device, node, session, sequence, "MOTION")
            self.committer.commit("home-1", body, 110)
            for _ in range(100):
                self.assertTrue(self.committer.commit("home-1", body, 111)["duplicate"])
        self.assertEqual(self.counts(), (3, 3, 0, 0, 0))
        door = self.body(sequence=2, kind="DOOR_OPEN")
        door["payload"] = {"quiet_hours": True}
        self.committer.commit("home-1", door, 120)
        self.assertEqual(self.counts(), (4, 4, 0, 0, 1))

    def test_api_requires_authorized_hub_and_durable_store(self):
        body = self.body()
        api = JsonApi(now=lambda: 110)
        self.assertEqual(api.dispatch("POST", "/v1/homes/home-1/events", "hub-1", body)[0][:3], "503")
        api = JsonApi(now=lambda: 110, durable_events=self.committer,
                      authorize_hub=lambda context, home, key: home == "home-1" and context.get("gs.verified_hub") == "hub-1")
        with self.assertRaises(PermissionError):
            api.dispatch("POST", "/v1/homes/home-1/events", "intruder", body)
        trusted = {"gs.verified_hub": "hub-1"}
        first = api.dispatch("POST", "/v1/homes/home-1/events", "hub-1", body,
                             request_context=trusted)
        self.assertEqual(first[0][:3], "201")
        self.assertEqual(first[1]["status"], "COMMITTED")
        self.assertTrue(api.dispatch("POST", "/v1/homes/home-1/events", "hub-1", body,
                                     request_context=trusted)[1]["duplicate"])


if __name__ == "__main__":
    unittest.main()
