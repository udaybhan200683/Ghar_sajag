"""Feed the Hub's canonical request into the real durable SQLite backend."""
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from ghar_sajag.database import initialize_sqlite
from ghar_sajag.durable_commit import DurableEventCommit


class HubBackendCommitIntegrationTest(unittest.TestCase):
    def test_lost_response_then_duplicate_commit_and_restart(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "backend.sqlite"
            db = sqlite3.connect(path)
            initialize_sqlite(db)
            with db:
                db.execute("INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) VALUES('home-1','Home','UTC',1,1)")
                db.execute("INSERT INTO caregivers(caregiver_id,display_name,created_at) VALUES('care-1','Caregiver',1)")
                db.execute("INSERT INTO household_caregivers(home_id,caregiver_id,role) VALUES('home-1','care-1','PRIMARY')")
            backend = DurableEventCommit(db)
            bridge = subprocess.Popen(
                [str(ROOT / "build/hub_backend_commit_validation"), "--bridge"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, bufsize=1,
            )
            try:
                body = json.loads(bridge.stdout.readline())
                self.assertEqual(body["event_key"], {
                    "physical_device_id": "device-A", "logical_node_id": "room-1",
                    "origin_session_id": 17, "event_sequence": 1,
                })
                first = backend.commit("home-1", body, 110)
                self.assertEqual(first["status"], "COMMITTED")
                # Drop the response; the Hub then restarts with X still pending.
                bridge.stdin.write("LOST\n")
                bridge.stdin.flush()
                retried_body = json.loads(bridge.stdout.readline())
                self.assertEqual(retried_body, body)
                db.close()
                db = sqlite3.connect(path)
                initialize_sqlite(db)
                backend = DurableEventCommit(db)
                duplicate = backend.commit("home-1", retried_body, 120)
                self.assertEqual(duplicate["status"], "COMMITTED")
                self.assertTrue(duplicate["duplicate"])
                bridge.stdin.write("AUTHENTICATED_COMMITTED_DUPLICATE\n")
                bridge.stdin.flush()
                self.assertEqual(bridge.stdout.readline().strip(), "COMPLETED_AFTER_RESTART")
                self.assertEqual(bridge.wait(timeout=5), 0, bridge.stderr.read())
            finally:
                if bridge.poll() is None:
                    bridge.kill()
                    bridge.wait(timeout=5)
                bridge.stdin.close()
                bridge.stdout.close()
                bridge.stderr.close()
            for table, expected in (("events", 1), ("durable_event_commits", 1),
                                    ("alerts", 1), ("notification_jobs", 1),
                                    ("durable_notification_outbox", 1)):
                self.assertEqual(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], expected)
            db.close()


if __name__ == "__main__":
    unittest.main()
