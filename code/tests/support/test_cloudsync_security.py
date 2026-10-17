"""GS-68/109 certificate-to-permanent-Hub unit regressions (TEST_ONLY keys)."""
from dataclasses import replace
from datetime import datetime, timezone
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "tests/support"))
from cloudsync_mtls_certs import issue_test_cert, make_test_ca
from ghar_sajag.cloud_client_identity import (
    CloudClientRejected, CloudCredentialRecord, TimeReadiness, VerifiedHubContext,
    _authorize_verified_certificate,
)
from ghar_sajag.database import initialize_sqlite
from ghar_sajag.ownership_registry import (
    AuthorizedHomeOperation, HubOwnershipRegistry, VerifiedHubIdentity,
)


class MockFactoryRegistry:
    """GS-165/172 interface mock; no production issuer or registry."""
    def __init__(self, record):
        self.records = {record.fingerprint_sha256: record}

    def by_fingerprint(self, fingerprint_sha256):
        return self.records.get(fingerprint_sha256)


class CloudSyncSecurityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ca_key, ca = make_test_ca()
        cls.valid = issue_test_cert(ca_key, ca, "test-hub-cloud")
        cls.other = issue_test_cert(ca_key, ca, "test-clone")
        cls.small = issue_test_cert(ca_key, ca, "test-small", key_bits=2048)
        cls.expired = issue_test_cert(ca_key, ca, "test-expired", expired=True)
        cls.not_yet_valid = issue_test_cert(ca_key, ca, "test-not-yet-valid",
                                            not_yet_valid=True)
        cls.server_only = issue_test_cert(ca_key, ca, "test-wrong-eku", client_purpose=False)

    def setUp(self):
        self.db = sqlite3.connect(":memory:", isolation_level=None)
        initialize_sqlite(self.db)
        self.db.execute("INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) VALUES('home-a','TEST','UTC',1,1)")
        self.owner = HubOwnershipRegistry(self.db)
        self.identity = VerifiedHubIdentity("hub-permanent-1", "a" * 64, "test-proof")
        self.owner.register_unclaimed_identity(self.identity, 1)
        self.owner.claim_home(self.identity, AuthorizedHomeOperation(
            "test-installer", "home-a", "CLAIM_HUB", "test-claim"), 2)
        self.record = CloudCredentialRecord(self.valid.fingerprint, "hub-permanent-1", "ACTIVE")
        self.credentials = MockFactoryRegistry(self.record)

    def tearDown(self):
        self.db.close()

    def authorize(self, cert=None, now=None):
        return _authorize_verified_certificate(
            self.valid.der if cert is None else cert,
            trusted_now=datetime.now(timezone.utc) if now is None else now,
            credentials=self.credentials, ownership_db=self.db)

    def test_001_valid_dedicated_rsa3072_maps_current_owner(self):
        self.assertEqual(self.authorize(), {"gs.verified_hub": "hub-permanent-1",
                                            "gs.hub_key_fingerprint": "a" * 64,
                                            "gs.installation_epoch": 1,
                                            "gs.home_id": "home-a"})

    def test_002_unknown_or_cloned_identity_rejected(self):
        with self.assertRaisesRegex(CloudClientRejected, "unknown_revoked"):
            self.authorize(self.other.der)

    def test_003_revoked_credential_rejected(self):
        self.credentials.records[self.valid.fingerprint] = replace(self.record, state="REVOKED")
        with self.assertRaisesRegex(CloudClientRejected, "unknown_revoked"):
            self.authorize()

    def test_004_wrong_signing_purpose_rejected(self):
        self.credentials.records[self.valid.fingerprint] = replace(self.record, purpose="COMMISSIONING")
        with self.assertRaisesRegex(CloudClientRejected, "unknown_revoked"):
            self.authorize()

    def test_005_unsupported_algorithm_rejected(self):
        self.credentials.records[self.valid.fingerprint] = replace(self.record, algorithm="P256")
        with self.assertRaisesRegex(CloudClientRejected, "unknown_revoked"):
            self.authorize()

    def test_006_wrong_key_size_rejected(self):
        self.credentials.records[self.small.fingerprint] = replace(
            self.record, fingerprint_sha256=self.small.fingerprint)
        with self.assertRaisesRegex(CloudClientRejected, "dedicated_rsa3072"):
            self.authorize(self.small.der)

    def test_007_expired_certificate_rejected(self):
        self.credentials.records[self.expired.fingerprint] = replace(
            self.record, fingerprint_sha256=self.expired.fingerprint)
        with self.assertRaisesRegex(CloudClientRejected, "not_current"):
            self.authorize(self.expired.der)

    def test_008_trusted_time_required(self):
        with self.assertRaisesRegex(CloudClientRejected, "trusted_time_required"):
            _authorize_verified_certificate(self.valid.der, trusted_now=None,
                credentials=self.credentials, ownership_db=self.db)

    def test_009_missing_and_corrupt_certificate_rejected(self):
        for value in (b"", b"not-a-certificate", b"x" * 8193):
            with self.subTest(value=value[:10]), self.assertRaises(CloudClientRejected):
                self.authorize(value)

    def test_010_wrong_eku_rejected(self):
        self.credentials.records[self.server_only.fingerprint] = replace(
            self.record, fingerprint_sha256=self.server_only.fingerprint)
        with self.assertRaisesRegex(CloudClientRejected, "dedicated_rsa3072"):
            self.authorize(self.server_only.der)

    def test_011_missing_ownership_or_transfer_rejected(self):
        self.owner.revoke_hub(self.identity, AuthorizedHomeOperation(
            "test-installer", "home-a", "REVOKE_HUB", "test-revoke"), 3)
        with self.assertRaisesRegex(CloudClientRejected, "current_hub_ownership_required"):
            self.authorize()

    def test_012_repeated_lookup_preserves_state(self):
        for _ in range(3):
            self.assertEqual(self.authorize()["gs.installation_epoch"], 1)

    def test_013_typed_context_binds_current_home_epoch_and_time_readiness(self):
        legacy = self.authorize()
        self.assertEqual(legacy["gs.home_id"], "home-a")
        context = VerifiedHubContext(
            permanent_hub_id=legacy["gs.verified_hub"], home_id=legacy["gs.home_id"],
            installation_epoch=legacy["gs.installation_epoch"],
            certificate_fingerprint_sha256=self.valid.fingerprint,
            ownership_fingerprint_sha256=legacy["gs.hub_key_fingerprint"],
            certificate_chain_verified=True, time_readiness=TimeReadiness.TRUSTED,
        )
        internal = context.internal_event_context()
        self.assertEqual((internal["gs.verified_hub"], internal["gs.home_id"],
                          internal["gs.installation_epoch"], internal["gs.time_readiness"]),
                         ("hub-permanent-1", "home-a", 1, "TRUSTED"))
        with self.assertRaisesRegex(CloudClientRejected, "context_not_ready"):
            VerifiedHubContext(
                **{**context.__dict__, "time_readiness": TimeReadiness.UNTRUSTED}
            ).internal_event_context()

    def test_014_not_yet_valid_certificate_rejected(self):
        self.credentials.records[self.not_yet_valid.fingerprint] = replace(
            self.record, fingerprint_sha256=self.not_yet_valid.fingerprint)
        with self.assertRaisesRegex(CloudClientRejected, "not_current"):
            self.authorize(self.not_yet_valid.der)


if __name__ == "__main__":
    unittest.main()
