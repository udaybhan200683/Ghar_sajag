"""Failure and authorization tests for the durable notification outbox worker."""
import json
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from ghar_sajag.database import initialize_sqlite
from ghar_sajag.durable_commit import DurableEventCommit
from ghar_sajag.notification_worker import (
    NotificationWorker, NotificationWorkerProcess, ProviderResult, main,
)


class FakeProvider:
    max_send_seconds = 10

    def __init__(self, results=None, on_send=None, ready=True):
        self.results = list(results or [ProviderResult(True, "fake-accepted")])
        self.on_send = on_send
        self.is_ready = ready
        self.calls = []

    def ready(self):
        return self.is_ready

    def send(self, delivery, *, idempotency_key):
        self.calls.append((delivery, idempotency_key))
        if self.on_send:
            self.on_send()
        result = self.results.pop(0) if len(self.results) > 1 else self.results[0]
        if isinstance(result, BaseException):
            raise result
        return result


class NotificationWorkerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "worker.sqlite"
        self.db = self.open_db()
        self.seed()
        self.committer = DurableEventCommit(self.db)
        self.committer.commit("home-1", self.body(), 110)

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def open_db(self):
        db = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False, timeout=5)
        db.row_factory = sqlite3.Row
        initialize_sqlite(db)
        return db

    def seed(self):
        self.db.execute("INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) VALUES('home-1','Home','UTC',1,1)")
        for caregiver, role in (("primary-1", "PRIMARY"), ("backup-1", "BACKUP")):
            self.db.execute("INSERT INTO caregivers(caregiver_id,display_name,created_at) VALUES(?,?,1)", (caregiver, caregiver))
            self.db.execute("INSERT INTO household_caregivers(home_id,caregiver_id,role) VALUES('home-1',?,?)", (caregiver, role))
        self.db.execute("INSERT INTO notification_preferences(home_id,preferences_json,updated_at) VALUES('home-1',?,1)",
                        (json.dumps({"safety_alerts": True}),))

    @staticmethod
    def body(sequence=1, kind="CALL_FAMILY", is_test=False):
        return {"event_key": {"physical_device_id": "hub-node", "logical_node_id": "room-1",
                              "origin_session_id": 1, "event_sequence": sequence},
                "event_type": kind, "occurred_at": 101, "hub_received_at": 102,
                "location": "private", "is_test": is_test, "payload": {}}

    def outbox(self, stage=1):
        return self.db.execute("SELECT outbox_id,state,attempts,due_at,lease_token,lease_generation,provider_reference,terminal_reason FROM durable_notification_outbox WHERE stage=?", (stage,)).fetchone()

    def worker(self, provider, *, clock=lambda: 110, **kwargs):
        return NotificationWorker(self.db, provider, now=clock, random_value=lambda: 0.5, **kwargs)

    def test_commit_duplicate_and_restart_preserve_single_effect_identity(self):
        body = self.body()
        self.assertTrue(self.committer.commit("home-1", body, 111)["duplicate"])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM durable_notification_outbox").fetchone()[0], 2)
        before = self.outbox()[0]
        self.db.close()
        self.db = self.open_db()
        after = self.outbox()[0]
        self.assertEqual(before, after)

    def test_provider_acceptance_is_durable_and_distinct_from_acknowledgement(self):
        provider = FakeProvider()
        metrics = self.worker(provider).run_once()
        row = self.outbox()
        self.assertEqual(metrics["accepted"], 1)
        self.assertEqual(row[1], "DELIVERED")
        self.assertEqual(row[6], "fake-accepted")
        self.assertIsNotNone(self.db.execute("SELECT provider_accepted_at FROM durable_notification_outbox WHERE outbox_id=?", (row[0],)).fetchone()[0])
        self.assertEqual(self.db.execute("SELECT state FROM alerts").fetchone()[0], "OPEN")
        self.assertEqual(self.db.execute("SELECT state FROM notification_jobs WHERE recipient_id='primary-1'").fetchone()[0], "PROVIDER_ACCEPTED")
        self.assertEqual(provider.calls[0][1], row[0])

    def test_temporary_timeout_network_and_bounded_jitter_retry(self):
        provider = FakeProvider([TimeoutError("private timeout details")])
        worker = self.worker(provider, max_attempts=2, base_retry_seconds=10, max_retry_seconds=40)
        metrics = worker.run_once()
        row = self.outbox()
        self.assertEqual(metrics["retry_scheduled"], 1)
        self.assertEqual(row[1:4], ("PENDING", 1, 120))
        self.assertEqual(self.db.execute("SELECT last_error_class FROM durable_notification_outbox WHERE outbox_id=?", (row[0],)).fetchone()[0], "TIMEOUT")
        self.assertEqual(tuple(self.db.execute("SELECT state,attempts FROM notification_jobs WHERE recipient_id='primary-1'").fetchone()), ("CREATED",1))
        self.db.close()
        self.db = self.open_db()
        self.assertEqual(self.outbox()[3], 120)
        metrics = self.worker(FakeProvider([ConnectionError()]), clock=lambda: 120,
                              max_attempts=2).run_once()
        self.assertEqual(metrics["failed"], 1)
        self.assertEqual(self.outbox()[1], "FAILED")
        self.assertEqual(self.outbox()[7], "RETRY_LIMIT")
        self.assertEqual(self.db.execute("SELECT state FROM notification_jobs WHERE recipient_id='primary-1'").fetchone()[0], "FAILED")

    def test_permanent_provider_rejection_is_terminal_without_retry(self):
        metrics = self.worker(FakeProvider([ProviderResult(False, retryable=False)])).run_once()
        self.assertEqual(metrics["failed"], 1)
        self.assertEqual(self.outbox()[1], "FAILED")
        self.assertEqual(self.outbox()[7], "PROVIDER_PERMANENT")

    def test_two_sqlite_workers_racing_claim_one_row_have_one_owner(self):
        providers = [FakeProvider([ProviderResult(False)]), FakeProvider([ProviderResult(False)])]
        results, errors = [], []
        def run(index):
            db = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False, timeout=5)
            db.row_factory = sqlite3.Row
            try:
                results.append(NotificationWorker(db, providers[index], now=lambda: 110).run_once())
            except Exception as error:
                errors.append(error)
            finally:
                db.close()
        threads = [threading.Thread(target=run, args=(i,)) for i in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(5)
        self.assertFalse(errors)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(sum(provider.calls.__len__() for provider in providers), 1)

    def test_expired_claim_recovery_rejects_stale_completion_token(self):
        provider = FakeProvider()
        provider.max_send_seconds = 1
        worker = self.worker(provider, lease_seconds=6)
        rows = worker._claim(110, {"expired_leases": 0})
        claimed = rows[0]
        recovered = worker._claim(116, {"expired_leases": 0})
        self.assertEqual(len(recovered), 1)
        self.assertNotEqual(claimed["lease_token"], recovered[0]["lease_token"])
        self.assertGreater(recovered[0]["lease_generation"], claimed["lease_generation"])
        self.assertFalse(worker._finish(claimed, state="DELIVERED", provider_reference="stale"))
        self.assertTrue(worker._finish(recovered[0], state="DELIVERED", provider_reference="new"))

    def test_crash_on_final_allowed_attempt_expires_to_terminal_without_extra_send(self):
        provider = FakeProvider()
        provider.max_send_seconds = 1
        worker = self.worker(provider, lease_seconds=6, max_attempts=1)
        self.assertEqual(len(worker._claim(110, {"expired_leases": 0})), 1)
        metrics = {"expired_leases": 0, "failed": 0}
        self.assertEqual(worker._claim(116, metrics), [])
        self.assertEqual(metrics, {"expired_leases": 1, "failed": 1})
        self.assertEqual(self.outbox()[1], "FAILED")
        self.assertEqual(self.db.execute("SELECT state FROM notification_jobs WHERE recipient_id='primary-1'").fetchone()[0], "FAILED")

    def test_acknowledged_before_send_cancels_and_during_send_does_not_reopen(self):
        primary = self.db.execute("SELECT alert_id FROM alerts").fetchone()[0]
        self.db.execute("UPDATE alerts SET state='ACKNOWLEDGED',acknowledged_at=111 WHERE alert_id=?", (primary,))
        metrics = self.worker(FakeProvider()).run_once()
        self.assertEqual(metrics["cancelled"], 1)
        self.assertEqual(self.outbox()[1], "FAILED")
        self.assertEqual(self.outbox()[7], "INCIDENT_NOT_ACTIVE")
        # A second incident is acknowledged while an attempt is already running.
        self.committer.commit("home-1", self.body(sequence=2), 120)
        alert = self.db.execute("SELECT alert_id FROM alerts WHERE source_event_id=(SELECT event_id FROM events WHERE sequence_number=2)").fetchone()[0]
        def acknowledge():
            self.db.execute("UPDATE alerts SET state='ACKNOWLEDGED',acknowledged_at=121 WHERE alert_id=?", (alert,))
        provider = FakeProvider(on_send=acknowledge)
        metrics = self.worker(provider, clock=lambda: 120).run_once()
        self.assertEqual(metrics["accepted"], 1)
        self.assertEqual(self.db.execute("SELECT state FROM alerts WHERE alert_id=?", (alert,)).fetchone()[0], "ACKNOWLEDGED")

    def test_removed_wrong_role_missing_consent_preference_and_test_event_fail_closed(self):
        cases = [
            ("UPDATE household_caregivers SET active=0 WHERE caregiver_id='primary-1'", "membership"),
            ("UPDATE household_caregivers SET role='FAMILY' WHERE caregiver_id='primary-1'", "role"),
            ("UPDATE households SET consent_state='WITHDRAWN' WHERE home_id='home-1'", "consent"),
            ("UPDATE notification_preferences SET preferences_json='{}' WHERE home_id='home-1'", "preference"),
            ("DELETE FROM notification_preferences WHERE home_id='home-1'", "missing preference"),
        ]
        for sql, _label in cases:
            # Restore one reusable pending row between each fail-closed case.
            self.db.execute("UPDATE durable_notification_outbox SET state='PENDING',lease_token=NULL,lease_until=NULL,terminal_reason=NULL WHERE stage=1")
            self.db.execute("UPDATE household_caregivers SET active=1,role='PRIMARY' WHERE caregiver_id='primary-1'")
            self.db.execute("UPDATE households SET consent_state='ACTIVE' WHERE home_id='home-1'")
            self.db.execute("INSERT OR REPLACE INTO notification_preferences(home_id,preferences_json,updated_at) VALUES('home-1',?,1)", (json.dumps({"safety_alerts": True}),))
            self.db.execute(sql)
            provider = FakeProvider()
            self.worker(provider).run_once()
            self.assertEqual(provider.calls, [])
        event_id = self.db.execute("SELECT event_id FROM events WHERE sequence_number=1").fetchone()[0]
        self.db.execute("UPDATE notification_preferences SET preferences_json=? WHERE home_id='home-1'",
                        (json.dumps({"safety_alerts": True}),))
        self.db.execute("UPDATE events SET is_test=1 WHERE event_id=?", (event_id,))
        self.db.execute("UPDATE durable_notification_outbox SET state='PENDING',lease_token=NULL,lease_until=NULL,attempts=0 WHERE stage=1")
        provider = FakeProvider()
        self.worker(provider, clock=lambda: 120).run_once()
        self.assertEqual(provider.calls, [])

    def test_wrong_home_recipient_is_never_sent(self):
        self.db.execute("INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) VALUES('home-2','Other','UTC',1,1)")
        self.db.execute("INSERT INTO caregivers(caregiver_id,display_name,created_at) VALUES('other-care','Other',1)")
        self.db.execute("INSERT INTO household_caregivers(home_id,caregiver_id,role) VALUES('home-2','other-care','PRIMARY')")
        self.db.execute("UPDATE durable_notification_outbox SET recipient_id='other-care' WHERE stage=1")
        provider = FakeProvider()
        self.worker(provider).run_once()
        self.assertEqual(provider.calls, [])

    def test_provider_acceptance_then_crash_retries_same_idempotency_key(self):
        class CrashAfterAcceptance(FakeProvider):
            def send(self, delivery, *, idempotency_key):
                self.calls.append((delivery, idempotency_key))
                raise SystemExit("simulated process crash after remote acceptance")
        first = CrashAfterAcceptance()
        first.max_send_seconds = 1
        with self.assertRaises(SystemExit):
            self.worker(first, lease_seconds=6).run_once()
        outbox_id = self.outbox()[0]
        second = FakeProvider()
        self.worker(second, clock=lambda: 116).run_once()
        self.assertEqual(first.calls[0][1], outbox_id)
        self.assertEqual(second.calls[0][1], outbox_id)
        self.assertEqual(self.outbox()[1], "DELIVERED")

    def test_provider_unavailable_database_unavailable_and_worker_loop_bounds(self):
        with self.assertRaisesRegex(RuntimeError, "notification_worker_not_ready"):
            self.worker(FakeProvider(ready=False)).run_once()
        dead = sqlite3.connect(self.path)
        dead.close()
        with self.assertRaises(Exception):
            NotificationWorker(dead, FakeProvider()).run_once()
        provider = FakeProvider([ProviderResult(False)])
        worker = self.worker(provider)
        process = NotificationWorkerProcess(worker, poll_seconds=0.25, stop_event=threading.Event())
        process.run(max_cycles=1)
        self.assertEqual(len(provider.calls), 1)

    def test_autonomous_process_entrypoint_is_disabled_by_default(self):
        with mock.patch.dict(os.environ, {"GS_NOTIFICATION_WORKER_ENABLED": "0"}, clear=True):
            self.assertEqual(main(), 78)

    def test_sanitized_notification_payload_and_no_secret_logging(self):
        provider = FakeProvider()
        self.worker(provider).run_once()
        delivery = provider.calls[0][0]
        self.assertEqual(delivery.event_type, "CALL_FAMILY")
        self.assertEqual(delivery.severity, "URGENT")
        self.assertFalse(hasattr(delivery, "payload"))
        self.assertNotIn("private", repr(delivery))
        self.assertNotIn("contact", repr(delivery))

    def test_backup_escalation_is_delayed_and_not_repeated(self):
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM durable_notification_outbox WHERE stage=2 AND due_at<=110").fetchone()[0], 0)
        backup = self.outbox(stage=2)
        self.assertEqual(backup[3], 410)
        self.assertEqual(self.worker(FakeProvider()).run_once()["claimed"], 1)
        provider = FakeProvider()
        metrics = self.worker(provider, clock=lambda: 410).run_once()
        self.assertEqual(metrics["accepted"], 1)
        self.assertEqual(self.worker(FakeProvider(), clock=lambda: 1000).run_once()["claimed"], 0)

    def test_legacy_backup_outbox_without_stage_uses_current_backup_membership(self):
        self.db.execute("UPDATE durable_notification_outbox SET stage=NULL WHERE stage=2")
        provider = FakeProvider()
        metrics = self.worker(provider, clock=lambda: 410).run_once()
        self.assertEqual(metrics["accepted"], 2)  # due primary plus migrated backup
        self.assertEqual({call[0].recipient_id for call in provider.calls}, {"primary-1", "backup-1"})

    def test_resolved_incident_before_backup_due_cancels_all_unsent_jobs(self):
        alert_id = self.db.execute("SELECT alert_id FROM alerts").fetchone()[0]
        self.db.execute("UPDATE alerts SET state='RESOLVED',resolved_at=111 WHERE alert_id=?", (alert_id,))
        provider = FakeProvider()
        metrics = self.worker(provider, clock=lambda: 410).run_once()
        self.assertEqual(metrics["cancelled"], 2)
        self.assertEqual(provider.calls, [])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM durable_notification_outbox WHERE state='FAILED' AND terminal_reason='INCIDENT_NOT_ACTIVE'").fetchone()[0], 2)

    def test_local_completion_transaction_failure_leaves_recoverable_stable_key(self):
        outbox_id = self.outbox()[0]
        self.db.execute("""CREATE TRIGGER reject_worker_completion BEFORE UPDATE OF state ON durable_notification_outbox
                          WHEN NEW.state='DELIVERED' BEGIN SELECT RAISE(ABORT,'completion fault'); END""")
        provider = FakeProvider()
        provider.max_send_seconds = 1
        with self.assertRaises(sqlite3.IntegrityError):
            self.worker(provider, lease_seconds=6).run_once()
        self.db.execute("DROP TRIGGER reject_worker_completion")
        self.assertEqual(self.outbox()[1], "PENDING")
        retry_provider = FakeProvider()
        self.worker(retry_provider, clock=lambda: 116).run_once()
        self.assertEqual(provider.calls[0][1], outbox_id)
        self.assertEqual(retry_provider.calls[0][1], outbox_id)

    def test_corrupt_outbox_and_metrics_are_fail_closed_and_aggregate_only(self):
        self.db.execute("UPDATE durable_notification_outbox SET payload_json='not-json' WHERE stage=1")
        provider = FakeProvider()
        metrics = self.worker(provider).run_once()
        self.assertEqual(provider.calls, [])
        self.assertEqual(metrics["failed"], 1)
        self.assertEqual(self.outbox()[7], "CORRUPT_OUTBOX")
        self.assertEqual(self.db.execute("SELECT state FROM notification_jobs WHERE recipient_id='primary-1'").fetchone()[0], "FAILED")
        snapshot = self.worker(FakeProvider()).metrics_snapshot()
        self.assertEqual(set(snapshot), {"pending", "retry", "expired_lease", "provider_accepted", "failed"})
        self.assertTrue(all(type(value) is int for value in snapshot.values()))
        self.assertNotIn("out_", repr(snapshot))


if __name__ == "__main__":
    unittest.main()
