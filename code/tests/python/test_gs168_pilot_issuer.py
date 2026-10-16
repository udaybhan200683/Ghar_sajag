"""Focused GS-168 only; no firmware, customer certificate issuer or hardware."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import tempfile
import unittest
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "factory"))
from pilot_test_issuer import (TestOnlyAuthority, TestOnlyIssuer, TestIssuerRejected,
                                TestIssuerUnavailable, new_test_csr)


class PilotIssuerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.start = datetime.now(timezone.utc)
        cls.authority = TestOnlyAuthority(cls.start)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="GS168_TEST_ONLY_")
        self.path = Path(self.tmp.name) / "test_only.sqlite3"
        self.now = self.start
        self.issuer = TestOnlyIssuer(self.path, authority=self.authority, clock=lambda: self.now)

    def tearDown(self):
        self.issuer.close()
        self.tmp.cleanup()

    def pair(self, identity="test-hub-001"):
        return new_test_csr(identity)

    def test_issue_csr_binding_and_verify(self):
        key, csr = self.pair()
        issued = self.issuer.issue("test-hub-001", csr)
        self.assertEqual(self.issuer.verify(issued.certificate_pem, issued.hub_id, expected_csr=csr), issued)
        self.assertIn(b"BEGIN CERTIFICATE", issued.certificate_pem)
        self.assertEqual(key.key_size, 3072)

    def test_wrong_hub_and_wrong_csr_public_key(self):
        _, csr = self.pair()
        issued = self.issuer.issue("test-hub-001", csr)
        with self.assertRaises(TestIssuerRejected):
            self.issuer.verify(issued.certificate_pem, "test-hub-002")
        _, other = self.pair()
        with self.assertRaises(TestIssuerRejected):
            self.issuer.verify(issued.certificate_pem, "test-hub-001", expected_csr=other)
        with self.assertRaises(TestIssuerRejected):
            self.issuer.issue("test-hub-002", csr)

    def test_no_duplicate_issue_and_clean_renewal(self):
        _, csr = self.pair()
        previous = self.issuer.issue("test-hub-001", csr)
        with self.assertRaises(TestIssuerRejected):
            self.issuer.issue("test-hub-001", csr)
        _, replacement_csr = self.pair()
        current = self.issuer.issue("test-hub-001", replacement_csr, renew=True)
        self.assertNotEqual(current.fingerprint, previous.fingerprint)
        self.issuer.verify(current.certificate_pem, current.hub_id)
        with self.assertRaises(TestIssuerRejected):
            self.issuer.verify(previous.certificate_pem, previous.hub_id)

    def test_revoke_and_no_implicit_reissue(self):
        _, csr = self.pair()
        issued = self.issuer.issue("test-hub-001", csr)
        self.assertTrue(self.issuer.revoke(issued.fingerprint))
        self.assertFalse(self.issuer.revoke(issued.fingerprint))
        with self.assertRaises(TestIssuerRejected):
            self.issuer.verify(issued.certificate_pem, issued.hub_id)
        with self.assertRaises(TestIssuerRejected):
            self.issuer.issue("test-hub-001", csr)

    def test_expiry_and_future_start(self):
        _, csr = self.pair()
        issued = self.issuer.issue("test-hub-001", csr, valid_days=1)
        with self.assertRaises(TestIssuerRejected):
            self.issuer.verify(issued.certificate_pem, issued.hub_id, at=self.start + timedelta(days=2))
        with self.assertRaises(TestIssuerRejected):
            self.issuer.verify(issued.certificate_pem, issued.hub_id, at=self.start - timedelta(days=2))

    def test_outage_recovery_and_metadata_restart(self):
        _, csr = self.pair()
        issued = self.issuer.issue("test-hub-001", csr)
        self.issuer.set_test_available(False)
        with self.assertRaises(TestIssuerUnavailable):
            self.issuer.verify(issued.certificate_pem, issued.hub_id)
        self.issuer.set_test_available(True)
        self.issuer.verify(issued.certificate_pem, issued.hub_id)
        self.issuer.close()
        self.issuer = TestOnlyIssuer(self.path, authority=self.authority, clock=lambda: self.now)
        self.issuer.verify(issued.certificate_pem, issued.hub_id)
        with self.assertRaises(TestIssuerRejected):
            TestOnlyIssuer(self.path, authority=TestOnlyAuthority(self.now))

    def test_production_namespace_and_safe_inventory(self):
        with self.assertRaisesRegex(TestIssuerRejected, "NOT_READY_SECURITY_APPROVAL"):
            TestOnlyIssuer(self.path, environment="production", authority=self.authority)
        _, csr = self.pair()
        issued = self.issuer.issue("test-hub-001", csr)
        self.assertEqual(self.issuer.public_inventory()[0]["environment"], "TEST_ONLY")
        self.assertNotIn("certificate_pem", self.issuer.public_inventory()[0])
        self.assertNotIn("private_key", str(self.issuer.public_inventory()))
        self.assertTrue(issued.issuer_fingerprint)

    def test_invalid_hub_id_and_key_type_rejected(self):
        with self.assertRaises(TestIssuerRejected):
            self.pair("production-hub-001")
        _, csr = self.pair()
        with self.assertRaises(TestIssuerRejected):
            self.issuer.issue("test-hub-001", csr, valid_days=91)
        with self.assertRaises(TestIssuerRejected):
            self.issuer.issue("test-hub-001", csr, renew=True)

    def test_sequential_batch(self):
        count = 100 if os.environ.get("GS168_TEST_100") == "1" else 10
        identifiers = [f"test-hub-{n:03d}" for n in range(count)]
        for hub_id in identifiers:
            _, csr = self.pair(hub_id)
            self.issuer.issue(hub_id, csr)
        inventory = self.issuer.public_inventory()
        self.assertEqual(len(inventory), count)
        self.assertEqual(len({record["fingerprint"] for record in inventory}), count)


if __name__ == "__main__":
    unittest.main()
