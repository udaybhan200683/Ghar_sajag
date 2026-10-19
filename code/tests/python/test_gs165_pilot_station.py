"""GS-165 host-only station, registry, recovery and report boundaries."""
from datetime import datetime, timezone
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TEST_CASE_ID = "GS165-PILOT-001"
sys.path.insert(0, str(ROOT / "tools" / "factory"))
from pilot_station import (  # noqa: E402
    ManufacturingRegistry, PilotStation, Provenance, StationError, main,
)
from pilot_test_issuer import (  # noqa: E402
    TestIssuerUnavailable, TestOnlyAuthority, TestOnlyIssuer,
)


class PilotStationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.authority = TestOnlyAuthority(datetime(2026, 10, 19, tzinfo=timezone.utc))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="GS165_TEST_ONLY_")
        root = Path(self.tmp.name)
        self.registry_path = root / "station.sqlite3"
        self.issuer_path = root / "issuer.sqlite3"
        self.issuer = TestOnlyIssuer(self.issuer_path, authority=self.authority)
        self.registry = ManufacturingRegistry(self.registry_path, self.authority.fingerprint)
        self.station = PilotStation(self.registry, self.issuer)
        self.provenance = Provenance(
            "source-v1", "synthetic-fw-v1", hashlib.sha256(b"synthetic-fw").hexdigest(),
            "source-head-test", hashlib.sha256(b"synthetic-artifact").hexdigest(),
        )

    def tearDown(self):
        self.registry.close()
        self.issuer.close()
        self.tmp.cleanup()

    def test_100_device_sequential_simulation(self):
        reports = self.station.simulate_batch(100, self.provenance)
        self.assertEqual(len(reports), 100)
        self.assertEqual({r["provisioning_state"] for r in reports}, {"SIMULATED_QA_PASS"})
        self.assertEqual({r["qa_result"] for r in reports}, {"SIMULATED_PASS"})
        self.assertEqual(len({r["permanent_hub_id"] for r in reports}), 100)
        self.assertEqual(len({r["certificate_fingerprint_sha256"] for r in reports}), 100)
        self.assertEqual(len({r["public_qr"] for r in reports}), 100)
        self.assertTrue(all(r["label"] == "SIMULATED" for r in reports))
        self.assertTrue(all(r["delivery_readiness"] == "NOT_READY_SIMULATION_ONLY" for r in reports))

    def test_duplicate_hub_identity_with_conflicting_provenance_is_quarantined(self):
        self.station.simulate_one("test-hub-001", self.provenance)
        changed = Provenance(**{**self.provenance.__dict__, "firmware_version": "different"})
        with self.assertRaisesRegex(StationError, "identity_or_provenance_conflict_quarantined"):
            self.station.simulate_one("test-hub-001", changed)
        self.assertEqual(self.registry.get("test-hub-001")["provisioning_state"], "QUARANTINED")
        with self.assertRaisesRegex(StationError, "quarantine_reason_is_immutable"):
            self.registry.quarantine("test-hub-001", "operator_review_retryable")
        with self.assertRaisesRegex(StationError, "conflicting_identity_requires_new_hub_id"):
            self.registry.recover("test-hub-001", "RECOVER test-hub-001")
        unsafe = Provenance("operator@example.com", "synthetic-fw-v1", self.provenance.firmware_sha256,
                            "source-head-test", self.provenance.artifact_sha256)
        with self.assertRaisesRegex(StationError, "safe_provenance_token_required"):
            unsafe.validate()

    def test_credential_or_issuer_mismatch_quarantines(self):
        self.station.simulate_one("test-hub-002", self.provenance)
        self.registry.db.execute("UPDATE devices SET issuer_reference=? WHERE hub_id=?", ("0" * 64, "test-hub-002"))
        with self.assertRaisesRegex(StationError, "credential_issuer_mismatch_quarantined"):
            self.station.verify("test-hub-002")
        self.assertEqual(self.registry.get("test-hub-002")["provisioning_state"], "QUARANTINED")

    def test_revoked_credential_is_quarantined(self):
        report = self.station.simulate_one("test-hub-revoked", self.provenance)
        self.assertTrue(self.issuer.revoke(report["certificate_fingerprint_sha256"]))
        with self.assertRaisesRegex(StationError, "credential_issuer_mismatch_quarantined"):
            self.station.verify("test-hub-revoked")
        self.assertEqual(self.registry.get("test-hub-revoked")["provisioning_state"], "QUARANTINED")

    def test_duplicate_fingerprint_and_qr_are_rejected(self):
        first = self.station.simulate_one("test-hub-public-1", self.provenance)
        self.registry.reserve("test-hub-public-2", self.provenance)
        with self.assertRaises(sqlite3.IntegrityError):
            with self.registry.transaction():
                self.registry.db.execute("UPDATE devices SET certificate_fingerprint=? WHERE hub_id=?",
                                         (first["certificate_fingerprint_sha256"], "test-hub-public-2"))
        with self.assertRaises(sqlite3.IntegrityError):
            with self.registry.transaction():
                self.registry.db.execute("UPDATE devices SET qr_handle=? WHERE hub_id=?",
                                         (first["public_qr"], "test-hub-public-2"))

    def test_corrupted_registry_authority_metadata_fails_closed(self):
        copy_path = Path(self.tmp.name) / "corrupt-registry.sqlite3"
        copied = sqlite3.connect(copy_path)
        self.registry.db.backup(copied)
        copied.execute("PRAGMA ignore_check_constraints=ON")
        copied.execute("UPDATE station_meta SET environment='PRODUCTION' WHERE singleton=1")
        copied.commit(); copied.close()
        with self.assertRaisesRegex(StationError, "NOT_READY_TEST_ISSUER_MISMATCH"):
            ManufacturingRegistry(copy_path, self.authority.fingerprint)

    def test_interrupted_registry_transaction_rolls_back_and_retry_is_idempotent(self):
        with self.assertRaisesRegex(InterruptedError, "simulated_interruption_during_registry_transaction"):
            self.station.simulate_one("test-hub-003", self.provenance, interrupt_at="before_qa_commit")
        before = self.registry.get("test-hub-003")
        self.assertEqual(before["provisioning_state"], "TEST_CREDENTIAL_ISSUED")
        fingerprint = before["certificate_fingerprint"]
        report = self.station.resume("test-hub-003", self.provenance)
        self.assertEqual(report["provisioning_state"], "SIMULATED_QA_PASS")
        self.assertEqual(report["certificate_fingerprint_sha256"], fingerprint)

    def test_registry_restart_with_same_test_authority_and_retry(self):
        with self.assertRaisesRegex(InterruptedError, "simulated_interruption_after_credential"):
            self.station.simulate_one("test-hub-004", self.provenance, interrupt_at="after_credential")
        fingerprint = self.registry.get("test-hub-004")["certificate_fingerprint"]
        self.registry.close(); self.issuer.close()
        self.issuer = TestOnlyIssuer(self.issuer_path, authority=self.authority)
        self.registry = ManufacturingRegistry(self.registry_path, self.authority.fingerprint)
        self.station = PilotStation(self.registry, self.issuer)
        resumed = self.station.resume("test-hub-004", self.provenance)
        self.assertEqual(resumed["certificate_fingerprint_sha256"], fingerprint)
        self.assertEqual(resumed["provisioning_state"], "SIMULATED_QA_PASS")

    def test_quarantine_and_explicit_recovery(self):
        self.station.simulate_one("test-hub-005", self.provenance)
        self.registry.quarantine("test-hub-005", "operator_review_retryable")
        with self.assertRaisesRegex(StationError, "recovery_confirmation_mismatch"):
            self.registry.recover("test-hub-005", "yes")
        self.registry.recover("test-hub-005", "RECOVER test-hub-005")
        report = self.station.resume("test-hub-005", self.provenance)
        self.assertEqual(report["qa_result"], "SIMULATED_PASS")
        self.assertEqual(self.registry.get("test-hub-005")["provisioning_state"], "SIMULATED_QA_PASS")

    def test_test_issuer_outage_keeps_reservation_and_retry_recovers(self):
        self.issuer.set_test_available(False)
        with self.assertRaises(TestIssuerUnavailable):
            self.station.simulate_one("test-hub-009", self.provenance)
        self.assertEqual(self.registry.get("test-hub-009")["provisioning_state"], "RESERVED")
        self.issuer.set_test_available(True)
        report = self.station.resume("test-hub-009", self.provenance)
        self.assertEqual(report["provisioning_state"], "SIMULATED_QA_PASS")

    def test_mock_to_production_boundary_fails_closed(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["--registry", str(self.registry_path), "--environment", "production", "export-public"])
        self.assertEqual(code, 2)
        self.assertIn("NOT_READY_SECURITY_APPROVAL", output.getvalue())

    def test_no_state_or_report_can_claim_physical_or_delivery_ready(self):
        report = self.station.simulate_one("test-hub-006", self.provenance)
        self.assertNotIn("READY", report["provisioning_state"])
        self.assertEqual(report["physical_qa"], "NOT_RUN")
        self.assertEqual(report["delivery_readiness"], "NOT_READY_SIMULATION_ONLY")
        self.assertNotIn("home_id", report)
        self.assertNotIn("home_epoch", report)

    def test_reports_exclude_sensitive_values_and_qr_is_non_authorizing(self):
        self.station.simulate_one("test-hub-007", self.provenance)
        self.registry.db.execute("UPDATE devices SET qa_report_json=? WHERE hub_id=?",
                                 (json.dumps({"private_key": "PRIVATE", "token": "BEARER", "safe": "PASS"}), "test-hub-007"))
        exported = json.dumps(self.station.export())
        self.assertNotIn("PRIVATE", exported)
        self.assertNotIn("BEARER", exported)
        self.assertNotIn("private_key", exported)
        report = self.station.verify("test-hub-007")
        self.assertTrue(report["public_qr"].startswith("gs://hub/v1/"))
        self.assertNotIn("token", report["public_qr"].lower())
        self.assertNotIn("home", report["public_qr"].lower())
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["--registry", str(self.registry_path), "verify", "test-hub-007"])
        self.assertEqual(code, 0)
        self.assertIn("NOT_REPEATED_AUTHORITY_KEY_EPHEMERAL", output.getvalue())

    def test_batch_limit_and_invalid_state_transition(self):
        with self.assertRaisesRegex(StationError, "batch_size_must_be_1_to_100"):
            self.station.simulate_batch(101, self.provenance)
        self.registry.reserve("test-hub-008", self.provenance)
        with self.assertRaisesRegex(StationError, "invalid_state_transition"):
            self.registry.transition("test-hub-008", "DELIVERY_READY")


if __name__ == "__main__":
    unittest.main()
