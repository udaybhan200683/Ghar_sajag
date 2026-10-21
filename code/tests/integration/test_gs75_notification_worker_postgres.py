"""Opt-in disposable PostgreSQL concurrency/restart test for GS-75."""
import json
import os
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from ghar_sajag.durable_commit import DurableEventCommit
from ghar_sajag.notification_worker import NotificationWorker, ProviderResult
from ghar_sajag.postgres_database import connect_postgres, initialize_postgres
from psycopg.conninfo import conninfo_to_dict


DSN = os.environ.get("GS75_ISOLATED_TEST_DSN")


class RecordingProvider:
    max_send_seconds = 10

    def __init__(self):
        self.calls = []
        self.lock = threading.Lock()

    def ready(self):
        return True

    def send(self, delivery, *, idempotency_key):
        with self.lock:
            self.calls.append(idempotency_key)
        return ProviderResult(False, retryable=True)


@unittest.skipUnless(DSN, "set GS75_ISOLATED_TEST_DSN to a disposable local gs75 database")
class NotificationWorkerPostgresTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fields = conninfo_to_dict(DSN)
        if fields.get("host") not in ("localhost", "127.0.0.1", "::1"):
            raise RuntimeError("GS75_TEST_DSN_MUST_BE_LOCAL_DISPOSABLE")
        if not str(fields.get("dbname", "")).startswith("gs75"):
            raise RuntimeError("GS75_TEST_DATABASE_NAME_MUST_START_GS75")

    def setUp(self):
        self.db = connect_postgres(DSN, allow_local_unencrypted=True)
        initialize_postgres(self.db)
        self.db.execute("DELETE FROM durable_notification_outbox")
        self.db.execute("DELETE FROM notification_jobs")
        self.db.execute("DELETE FROM alerts")
        self.db.execute("DELETE FROM durable_event_commits")
        self.db.execute("DELETE FROM events")
        self.db.execute("DELETE FROM household_caregivers")
        self.db.execute("DELETE FROM caregivers")
        self.db.execute("DELETE FROM notification_preferences")
        self.db.execute("DELETE FROM households")
        self.db.execute("INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) VALUES('gs75-home','Home','UTC',1,1)")
        self.db.execute("INSERT INTO caregivers(caregiver_id,display_name,created_at) VALUES('gs75-primary','Primary',1)")
        self.db.execute("INSERT INTO household_caregivers(home_id,caregiver_id,role) VALUES('gs75-home','gs75-primary','PRIMARY')")
        self.db.execute("INSERT INTO notification_preferences(home_id,preferences_json,updated_at) VALUES('gs75-home',?,1)",
                        (json.dumps({"safety_alerts": True}),))
        self.committer = DurableEventCommit(self.db)
        self.committer.commit("gs75-home", {
            "event_key": {"physical_device_id":"gs75-node","logical_node_id":"room-1",
                          "origin_session_id":1,"event_sequence":1},
            "event_type":"CALL_FAMILY","occurred_at":101,"hub_received_at":102,
            "location":"private","payload":{},
        }, 110)

    def tearDown(self):
        self.db.close()

    def test_two_workers_skip_locked_and_persist_retry_across_reopen(self):
        providers = [RecordingProvider(), RecordingProvider()]
        results, errors = [], []
        def run(index):
            db = connect_postgres(DSN, allow_local_unencrypted=True)
            try:
                results.append(NotificationWorker(db, providers[index], now=lambda: 110,
                                                  random_value=lambda: 0.5).run_once())
            except Exception as exc:
                errors.append(exc)
            finally:
                db.close()
        threads = [threading.Thread(target=run, args=(i,)) for i in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(10)
        self.assertFalse(errors)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(sum(len(provider.calls) for provider in providers), 1)
        row = self.db.execute("SELECT outbox_id,state,attempts,due_at,last_error_class FROM durable_notification_outbox WHERE stage=1").fetchone()
        self.assertEqual((row[1],row[2],row[3],row[4]), ("PENDING",1,120,"PROVIDER_REJECTED"))
        self.db.close()
        self.db = connect_postgres(DSN, allow_local_unencrypted=True)
        resumed = self.db.execute("SELECT outbox_id,state,attempts,due_at FROM durable_notification_outbox WHERE stage=1").fetchone()
        self.assertEqual(tuple(resumed), (row[0],"PENDING",1,120))


if __name__ == "__main__":
    unittest.main()
