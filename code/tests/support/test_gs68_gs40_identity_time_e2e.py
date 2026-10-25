"""TEST_ONLY GS-168 identity -> mTLS -> GS-40 NodeHealth -> caregiver projection."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from cryptography import x509
from cryptography.hazmat.primitives import serialization

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "tools" / "factory"))
sys.path.insert(0, str(ROOT / "tools" / "hil"))
sys.path.insert(0, str(ROOT / "tests" / "support"))

from cloudsync_mtls_certs import issue_test_cert, make_test_ca
from cloudsync_mtls_local import tls_post
from pilot_test_issuer import TestOnlyIssuer, new_test_csr
from gs40_test_bootstrap import AuthorityService, encode_config, rsa3072
from cryptography.hazmat.primitives.asymmetric import ec


PHYSICAL_GS117_HUB = "hub-e072a1d38d34"
PHYSICAL_GS117_HOME = "gs177-test-product"
from ghar_sajag.cloud_client_identity import (
    CloudClientRejected, _authorize_verified_certificate,
)
from ghar_sajag.database import initialize_sqlite
from ghar_sajag.http_api import JsonApi
from ghar_sajag.model import Resident
from ghar_sajag.node_health_policy import DeploymentPolicy, NodeHealthPolicy
from ghar_sajag.node_health_status import NodeHealthStatusStore
from ghar_sajag.ownership_registry import (
    AuthorizedHomeOperation, HubOwnershipRegistry, VerifiedHubIdentity,
    VerifiedNodeEnrollment,
)
from ghar_sajag.service import GharSajagService


NODE_ID = "c3-gs68-e2e-001"
HUB_ID = "test-hub-001"
OWNERSHIP_FP = "a" * 64


def _write(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


class Gs68Gs40IdentityTimeE2eTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="GS68_GS40_TEST_ONLY_")
        self.paths = Path(self.temp.name)
        self.now = datetime.now(timezone.utc).replace(microsecond=0)
        self.issuer = TestOnlyIssuer(
            self.paths / "issuer.sqlite3", clock=lambda: self.now)
        client_key, client_csr = new_test_csr(HUB_ID)
        self.credential = self.issuer.issue(HUB_ID, client_csr, valid_days=30)
        client_key_pem = client_key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption())
        self.client_cert = _write(self.paths / "hub-client.crt",
                                  self.credential.certificate_pem)
        self.client_key = _write(self.paths / "hub-client.key", client_key_pem)
        self.client_root = _write(self.paths / "hub-test-root.crt",
                                  self.issuer.authority.public_ca_pem())

        server_key, server_ca = make_test_ca("GS-68 localhost TLS server TEST_ONLY")
        server = issue_test_cert(server_key, server_ca, "gs68-localhost-server",
                                 server=True)
        self.server_cert = _write(self.paths / "server.crt", server.pem)
        self.server_key = _write(self.paths / "server.key", server.key_pem)
        self.server_root = _write(
            self.paths / "server-test-root.crt",
            server_ca.public_bytes(serialization.Encoding.PEM))

        self.db = sqlite3.connect(":memory:", isolation_level=None,
                                  check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        initialize_sqlite(self.db)
        self.db.execute(
            "INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) "
            "VALUES('home-a','TEST','UTC',1,1)")
        self.db.execute(
            "INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) "
            "VALUES('home-b','TEST B','UTC',1,1)")
        self.owner = HubOwnershipRegistry(self.db)
        self.identity = VerifiedHubIdentity(HUB_ID, OWNERSHIP_FP, "test-proof-ref")
        self.owner.register_unclaimed_identity(self.identity, 1)
        self.owner.claim_home(self.identity, AuthorizedHomeOperation(
            "test-installer", "home-a", "CLAIM_HUB", "test-claim"), 2)
        self.owner.enroll_node(self.identity, AuthorizedHomeOperation(
            "test-installer", "home-a", "ENROLL_NODE", "test-enroll"),
            VerifiedNodeEnrollment(NODE_ID, "bathroom", 1, "b" * 64,
                                   "test-node-proof"), 3)

        self.health = NodeHealthStatusStore(
            self.db, DeploymentPolicy(NodeHealthPolicy(300), {NODE_ID: "configured"}))
        self.backend_clock = [int(self.now.timestamp()) + 2]
        self.service = GharSajagService()
        self.service.homes.create(
            "home-a", "Fixture", "Etc/UTC", "en-IN", "owner-a",
            [Resident("resident-a", "Resident", True, 1)], 1)
        self.service.queries.node_health_status = self.health
        self.api = JsonApi(service=self.service,
                           now=lambda: self.backend_clock[0],
                           node_health_status=self.health)
        self.body = self._body(self.backend_clock[0] - 2, revision=1)

    def tearDown(self):
        self.issuer.close()
        self.db.close()
        self.temp.cleanup()

    @staticmethod
    def _body(received_at: int, revision: int):
        return {
            "home_id": "home-a", "physical_node_id": NODE_ID,
            "logical_node_id": "bathroom", "node_enrollment_generation": 1,
            "session_id": 77, "boot_generation": 1,
            "source_revision": revision, "contact_kind": "NODE_HEALTH",
            "profile_id": "configured", "heartbeat_seconds": 300,
            "offline_seconds": 910, "hub_received_at": received_at,
            "hub_snapshot_at": received_at + 1,
        }

    def exchange(self, body=None):
        return tls_post(
            api=self.api, database=self.db, credentials=self.issuer,
            ca_file=self.server_root, server_cert=self.server_cert,
            server_key=self.server_key, client_cert=self.client_cert,
            client_key=self.client_key, client_ca=self.server_root,
            server_client_ca=self.client_root, body=self.body if body is None else body,
            path="/v1/homes/home-a/node-health")

    def caregiver_snapshot(self, at: int):
        self.backend_clock[0] = at
        status, snapshot = self.api.dispatch(
            "GET", "/v1/homes/home-a/snapshot", "owner-a", {})
        self.assertTrue(status.startswith("200"))
        return snapshot["node_health"][0]

    def test_001_issued_identity_mtls_nodehealth_and_caregiver_status(self):
        result = self.exchange()
        self.assertEqual((result.get("status"), result.get("body", {}).get("status")),
                         (200, "ACCEPTED"), result)
        online = self.caregiver_snapshot(self.backend_clock[0])
        self.assertEqual((online["status"], online["coverage"],
                          online["contact_kind"], online["profile_id"]),
                         ("ONLINE", "COVERED", "NODE_HEALTH", "configured"))

        # Silent Node expiry is represented by a later Hub snapshot; the latest
        # authenticated Hub contact is fresh, while the Node contact is >910s.
        original_contact = self.body["hub_received_at"]
        expired_at = original_contact + 911
        self.backend_clock[0] = expired_at + 2
        offline_body = self._body(original_contact, revision=2)
        offline_body["hub_snapshot_at"] = expired_at + 1
        offline = self.exchange(offline_body)
        self.assertEqual(offline.get("status"), 200, offline)
        observed = self.caregiver_snapshot(self.backend_clock[0])
        self.assertEqual((observed["status"], observed["coverage"]),
                         ("OFFLINE", "UNKNOWN"))
        stale = self.caregiver_snapshot(self.backend_clock[0] + 191)
        self.assertEqual(stale["status"], "UNKNOWN")

    def test_002_ownership_transfer_and_credential_revocation_fail_closed(self):
        transfer = self.owner.begin_transfer(
            self.identity, AuthorizedHomeOperation(
                "test-installer", "home-a", "TRANSFER_HUB", "test-transfer"),
            "home-b", 4)
        self.assertIsNotNone(transfer)
        rejected_transfer = self.exchange()
        self.assertIn("current_hub_ownership_required",
                      rejected_transfer.get("server_error", ""), rejected_transfer)

    def test_003_credential_revocation_fails_closed_after_tls_chain_validation(self):
        self.assertTrue(self.issuer.revoke(self.credential.fingerprint))
        rejected_revocation = self.exchange()
        self.assertIn("unknown_revoked_or_wrong_purpose_credential",
                      rejected_revocation.get("server_error", ""),
                      rejected_revocation)

    def test_004_expired_and_wrong_source_credentials_rejected(self):
        future = self.now + timedelta(days=31)
        with self.assertRaisesRegex(CloudClientRejected, "not_current"):
            _authorize_verified_certificate(
                x509.load_pem_x509_certificate(
                    self.credential.certificate_pem).public_bytes(
                        serialization.Encoding.DER),
                trusted_now=future, credentials=self.issuer,
                ownership_db=self.db)

        wrong_key, wrong_csr = new_test_csr("test-hub-unenrolled-2")
        wrong_credential = self.issuer.issue("test-hub-unenrolled-2", wrong_csr)
        wrong_der = x509.load_pem_x509_certificate(
            wrong_credential.certificate_pem).public_bytes(serialization.Encoding.DER)
        with self.assertRaisesRegex(CloudClientRejected, "current_hub_ownership"):
            _authorize_verified_certificate(
                wrong_der, trusted_now=self.now + timedelta(minutes=1),
                credentials=self.issuer, ownership_db=self.db)
        self.assertEqual(wrong_key.key_size, 3072)

    def test_005_gs117_physical_config_is_exact_fixture_only(self):
        target = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        signer = rsa3072()
        fields = {index: b"fixture" for index in range(1, 17)}
        fields[3] = b"https://localhost"
        fields[4] = b"localhost"
        fields[6] = b"127.0.0.1"
        fields[9] = PHYSICAL_GS117_HUB.encode("ascii")
        fields[21] = PHYSICAL_GS117_HOME.encode("ascii")
        physical = encode_config(b"n" * 32, target, fields, signer)
        self.assertTrue(physical.startswith(b"\x00\x00"))

        fields[9] = b"hub-e072a1d38d35"
        with self.assertRaisesRegex(ValueError, "test_identity_required"):
            encode_config(b"n" * 32, target, fields, signer)
        fields[9] = PHYSICAL_GS117_HUB.encode("ascii")
        fields[21] = b"another-home"
        with self.assertRaisesRegex(ValueError, "invalid_test_fixture_home_binding"):
            encode_config(b"n" * 32, target, fields, signer)
        fields.pop(21)
        fields[9] = b"test-hub-product"
        synthetic = encode_config(b"n" * 32, target, fields, signer)
        self.assertTrue(synthetic)

    def test_006_gs117_physical_authority_is_bound_to_exact_home(self):
        fingerprint = "c" * 64
        issuer = SimpleNamespace(
            by_fingerprint=lambda value: SimpleNamespace(generation=2)
            if value == fingerprint else None)
        context = SimpleNamespace(
            permanent_hub_id=PHYSICAL_GS117_HUB,
            home_id=PHYSICAL_GS117_HOME,
            certificate_fingerprint_sha256=fingerprint,
            installation_epoch=3,
        )
        service = AuthorityService(issuer, object(), threading.RLock(),
                                   enabled=True, signer=rsa3072())
        body = {
            "protocol": "GS40T/1", "hub_id": PHYSICAL_GS117_HUB,
            "credential_generation": 2,
            "certificate_fingerprint_sha256": fingerprint,
            "boot_generation": 5, "nonce": "d" * 64,
        }
        with patch("gs40_test_bootstrap.authorize_cloud_tls_context",
                   return_value=context):
            lease = service.refresh(object(), body)
        self.assertIn(PHYSICAL_GS117_HUB.encode(), lease)
        self.assertIn(PHYSICAL_GS117_HOME.encode(), lease)
        self.assertEqual(struct.unpack(">Q", lease[61:69])[0], 3)

        for overrides in ({"home_id": "gs177-test-other"},
                          {"permanent_hub_id": "hub-e072a1d38d35"}):
            rejected_context = SimpleNamespace(**{**vars(context), **overrides})
            rejected_service = AuthorityService(
                issuer, object(), threading.RLock(), enabled=True, signer=rsa3072())
            with patch("gs40_test_bootstrap.authorize_cloud_tls_context",
                       return_value=rejected_context):
                with self.assertRaisesRegex(PermissionError, "invalid_authority_challenge"):
                    rejected_service.refresh(object(), body)

if __name__ == "__main__":
    unittest.main()
