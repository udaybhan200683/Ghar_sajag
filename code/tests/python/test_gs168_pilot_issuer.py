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
                                TestIssuerUnavailable, new_test_csr, GS117_FIXTURE_HUB)


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

    def test_physical_fixture_authority_persists_and_is_namespace_isolated(self):
        bundle = Path(self.tmp.name) / "physical-ca.pem"
        authority = TestOnlyAuthority.for_gs117_fixture(bundle, initialize=True, now=self.now)
        key, csr = new_test_csr(GS117_FIXTURE_HUB, gs117_fixture=True)
        store = Path(self.tmp.name) / "physical.sqlite3"
        issuer = TestOnlyIssuer(store, authority=authority, clock=lambda: self.now)
        try:
            issued = issuer.issue(GS117_FIXTURE_HUB, csr)
            self.assertEqual(issuer.verify(issued.certificate_pem, GS117_FIXTURE_HUB,
                                          expected_csr=csr), issued)
            _, synthetic = new_test_csr("test-hub-001")
            with self.assertRaises(TestIssuerRejected):
                issuer.issue("test-hub-001", synthetic)
            with self.assertRaises(TestIssuerRejected):
                self.issuer.issue(GS117_FIXTURE_HUB, csr)
            with self.assertRaises(TestIssuerRejected):
                self.issuer.verify(issued.certificate_pem, GS117_FIXTURE_HUB)
        finally:
            issuer.close()
        reloaded = TestOnlyAuthority.for_gs117_fixture(bundle, now=self.now)
        self.assertEqual(reloaded.fingerprint, authority.fingerprint)
        reopened = TestOnlyIssuer(store, authority=reloaded, clock=lambda: self.now)
        try:
            self.assertEqual(reopened.verify(issued.certificate_pem, GS117_FIXTURE_HUB), issued)
            self.assertEqual(reopened.by_fingerprint(issued.fingerprint).permanent_hub_id,
                             GS117_FIXTURE_HUB)
        finally:
            reopened.close()
        self.assertEqual(bundle.stat().st_mode & 0o777, 0o600)
        for wrong in ("hub-001122334455", "test-hub-001", "hub-e072a1d38d34 "):
            with self.subTest(wrong=wrong), self.assertRaises(TestIssuerRejected):
                new_test_csr(wrong, gs117_fixture=True)
        self.assertEqual(key.key_size, 3072)

    def test_fixture_authority_rejects_partial_symlink_and_public_files(self):
        bundle = Path(self.tmp.name) / "fixture-ca.pem"
        authority = TestOnlyAuthority.for_gs117_fixture(bundle, initialize=True, now=self.now)
        before = bundle.read_bytes()
        self.assertEqual(TestOnlyAuthority.for_gs117_fixture(
            bundle, initialize=True, now=self.now).fingerprint, authority.fingerprint)
        self.assertEqual(bundle.read_bytes(), before)
        bundle.chmod(0o644)
        with self.assertRaises(TestIssuerRejected):
            TestOnlyAuthority.for_gs117_fixture(bundle, now=self.now)
        bundle.chmod(0o600)
        link = Path(self.tmp.name) / "linked-ca.pem"
        link.symlink_to(bundle)
        with self.assertRaises(TestIssuerRejected):
            TestOnlyAuthority.for_gs117_fixture(link, initialize=True, now=self.now)
        bundle.write_bytes(b"interrupted private fixture authority")
        with self.assertRaises(TestIssuerRejected):
            TestOnlyAuthority.for_gs117_fixture(bundle, initialize=True, now=self.now)
        self.assertEqual(bundle.read_bytes(), b"interrupted private fixture authority")

    def test_fixture_authority_rejects_changed_certificate_key_and_expiry(self):
        bundle = Path(self.tmp.name) / "fixture-ca.pem"
        TestOnlyAuthority.for_gs117_fixture(bundle, initialize=True, now=self.now)
        original = bundle.read_bytes()
        with self.assertRaises(TestIssuerRejected):
            TestOnlyAuthority.for_gs117_fixture(bundle, now=self.now + timedelta(days=366))
        marker = b"-----BEGIN CERTIFICATE-----"
        original_key = original[:original.index(marker)]
        bundle.write_bytes(original_key + self.authority.public_ca_pem())
        with self.assertRaises(TestIssuerRejected):
            TestOnlyAuthority.for_gs117_fixture(bundle, now=self.now)

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

    def test_backend_registry_adapter_tracks_active_revoked_and_unknown_rows(self):
        _, csr = self.pair()
        issued = self.issuer.issue("test-hub-001", csr)
        active = self.issuer.by_fingerprint(issued.fingerprint)
        self.assertEqual((active.permanent_hub_id, active.state,
                          active.purpose, active.algorithm),
                         ("test-hub-001", "ACTIVE", "CLOUD_TLS_CLIENT", "RSA_3072"))
        self.assertIsNone(self.issuer.by_fingerprint("f" * 64))
        self.assertTrue(self.issuer.revoke(issued.fingerprint))
        self.assertEqual(self.issuer.by_fingerprint(issued.fingerprint).state, "REVOKED")
        with self.assertRaisesRegex(TestIssuerRejected, "invalid_test_fingerprint"):
            self.issuer.by_fingerprint("not-a-fingerprint")

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
