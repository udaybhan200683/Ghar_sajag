"""GS-68/109/148 localhost simulated HIL; no board, USB or real credentials."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import tempfile
import unittest
from cryptography.hazmat.primitives.serialization import Encoding

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "tests/support"))
from cloudsync_mtls_certs import issue_test_cert, make_test_ca
from cloudsync_mtls_local import tls_post
from ghar_sajag.cloud_client_identity import CloudCredentialRecord
from ghar_sajag.durable_api import open_durable_event_api
from ghar_sajag.model import Resident
from ghar_sajag.ownership_registry import (
    AuthorizedHomeOperation, HubOwnershipRegistry, VerifiedHubIdentity,
    VerifiedNodeEnrollment,
)
from ghar_sajag.service import GharSajagService


class MockCredentialRegistry:
    def __init__(self, record):
        self.records = {record.fingerprint_sha256: record}
    def by_fingerprint(self, fingerprint):
        return self.records.get(fingerprint)


class CloudSyncMtlsSimHilTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="gs-cloud-mtls-test-")
        cls.certs = Path(cls.temporary.name)
        ca_key, ca = make_test_ca()
        cls.ca_file = cls.certs / "ca.crt"
        cls.ca_file.write_bytes(ca.public_bytes(Encoding.PEM))
        os.chmod(cls.ca_file, 0o600)
        cls.server = issue_test_cert(ca_key, ca, "localhost", server=True)
        cls.client = issue_test_cert(ca_key, ca, "test-hub")
        cls.clone = issue_test_cert(ca_key, ca, "test-clone")
        cls.expired = issue_test_cert(ca_key, ca, "expired", expired=True)
        cls.server_cert, cls.server_key = cls.server.write(cls.certs, "server")
        cls.client_cert, cls.client_key = cls.client.write(cls.certs, "client")
        cls.clone_cert, cls.clone_key = cls.clone.write(cls.certs, "clone")
        cls.expired_cert, cls.expired_key = cls.expired.write(cls.certs, "expired")
        other_key, other_ca = make_test_ca("WRONG TEST CA")
        cls.wrong_ca = cls.certs / "wrong-ca.crt"
        cls.wrong_ca.write_bytes(other_ca.public_bytes(
            Encoding.PEM))
        os.chmod(cls.wrong_ca, 0o600)
        cls.foreign = issue_test_cert(other_key, other_ca, "foreign-hub")
        cls.foreign_cert, cls.foreign_key = cls.foreign.write(cls.certs, "foreign")

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="gs-cloud-db-")
        self.db_path = Path(self.tmp.name) / "events.sqlite"
        self.service, self.endpoint = self.open_api()
        self.identity = VerifiedHubIdentity("hub-permanent-1", "a" * 64, "test-proof")
        owner = HubOwnershipRegistry(self.endpoint.db)
        owner.register_unclaimed_identity(self.identity, 1)
        owner.claim_home(self.identity, AuthorizedHomeOperation(
            "test-installer", "home-a", "CLAIM_HUB", "test-claim"), 2)
        owner.enroll_node(self.identity, AuthorizedHomeOperation(
            "test-installer", "home-a", "ENROLL_NODE", "test-enroll"),
            VerifiedNodeEnrollment("device-room1", "room1", 3, "b" * 64, "node-proof"), 3)
        self.credentials = MockCredentialRegistry(CloudCredentialRecord(
            self.client.fingerprint, "hub-permanent-1", "ACTIVE"))

    def tearDown(self):
        self.endpoint.close()
        self.tmp.cleanup()

    def open_api(self):
        service = GharSajagService()
        service.homes.create("home-a", "Fixture", "Asia/Kolkata", "en-IN", "care-1",
                             [Resident("resident-1", "Resident", True, 1)], 1)
        service.homes.create("home-b", "Transfer fixture", "Asia/Kolkata", "en-IN", "care-2",
                             [Resident("resident-2", "Resident B", True, 1)], 1)
        endpoint = open_durable_event_api(service, self.db_path,
            require_registered_ownership=True, now=lambda: 1800000999)
        with endpoint.db:
            endpoint.db.execute("INSERT OR IGNORE INTO households(home_id,display_name,timezone,created_at,updated_at) VALUES('home-a','Fixture','UTC',1,1)")
            endpoint.db.execute("INSERT OR IGNORE INTO caregivers(caregiver_id,display_name,created_at) VALUES('care-1','Caregiver',1)")
            endpoint.db.execute("INSERT OR IGNORE INTO households(home_id,display_name,timezone,created_at,updated_at) VALUES('home-b','Transfer fixture','UTC',1,1)")
            endpoint.db.execute("INSERT OR IGNORE INTO caregivers(caregiver_id,display_name,created_at) VALUES('care-2','Caregiver B',1)")
            endpoint.db.execute("INSERT OR IGNORE INTO household_caregivers(home_id,caregiver_id,role) VALUES('home-a','care-1','PRIMARY')")
            endpoint.db.execute("INSERT OR IGNORE INTO household_caregivers(home_id,caregiver_id,role) VALUES('home-b','care-2','PRIMARY')")
        return service, endpoint

    @staticmethod
    def body(sequence=1):
        return {"cloudsync_version": 2, "node_enrollment_generation": 3,
                "event_key": {"physical_device_id": "device-room1",
                              "logical_node_id": "room1", "origin_session_id": 42,
                              "event_sequence": sequence},
                "event_type": "CALL_FAMILY", "occurred_at": 1800000000 + sequence,
                "hub_received_at": 1800000900 + sequence,
                "location": "room1", "payload": {}}

    def exchange(self, **changes):
        options = dict(api=self.endpoint.api, database=self.endpoint.db,
                       credentials=self.credentials, ca_file=self.ca_file,
                       server_cert=self.server_cert, server_key=self.server_key,
                       client_cert=self.client_cert, client_key=self.client_key,
                       body=self.body(), path="/v1/homes/home-a/events")
        options.update(changes)
        return tls_post(**options)

    def effects(self):
        return self.endpoint.db.execute("SELECT COUNT(*) FROM durable_event_commits").fetchone()[0]

    def test_001_valid_mtls_durable_commit(self):
        result = self.exchange()
        self.assertEqual((result.get("status"), result.get("body", {}).get("status")), (201, "COMMITTED"), result)
        self.assertEqual(self.effects(), 1)

    def test_002_wrong_client_ca(self):
        result = self.exchange(client_cert=self.foreign_cert, client_key=self.foreign_key)
        self.assertNotIn("status", result)
        self.assertEqual(self.effects(), 0)

    def test_003_wrong_server_ca(self):
        result = self.exchange(client_ca=self.wrong_ca)
        self.assertNotIn("status", result)
        self.assertEqual(self.effects(), 0)

    def test_004_wrong_server_identity(self):
        result = self.exchange(hostname="wrong-host.invalid")
        self.assertNotIn("status", result)
        self.assertEqual(self.effects(), 0)

    def test_005_revoked_certificate(self):
        self.credentials.records[self.client.fingerprint] = CloudCredentialRecord(
            self.client.fingerprint, "hub-permanent-1", "REVOKED")
        self.assertNotIn("status", self.exchange())
        self.assertEqual(self.effects(), 0)

    def test_006_expired_certificate(self):
        self.assertNotIn("status", self.exchange(client_cert=self.expired_cert,
                                                  client_key=self.expired_key))
        self.assertEqual(self.effects(), 0)

    def test_007_missing_signer_context(self):
        self.assertNotIn("status", self.exchange(client_cert=None, client_key=None))
        self.assertEqual(self.effects(), 0)

    def test_008_wrong_purpose(self):
        self.credentials.records[self.client.fingerprint] = CloudCredentialRecord(
            self.client.fingerprint, "hub-permanent-1", "ACTIVE", purpose="COMMISSIONING")
        self.assertNotIn("status", self.exchange())
        self.assertEqual(self.effects(), 0)

    def test_009_cloned_unknown_identity(self):
        self.assertNotIn("status", self.exchange(client_cert=self.clone_cert,
                                                  client_key=self.clone_key))
        self.assertEqual(self.effects(), 0)

    def test_010_unsupported_tls_profile(self):
        self.assertNotIn("status", self.exchange(tls13=True))
        self.assertEqual(self.effects(), 0)

    def test_011_wrong_home(self):
        self.assertEqual(self.exchange(path="/v1/homes/home-b/events").get("status"), 403)
        self.assertEqual(self.effects(), 0)

    def test_018_home_transfer_during_authenticated_request_fails_closed(self):
        owner = HubOwnershipRegistry(self.endpoint.db)
        def transfer_after_tls(_trusted_context):
            epoch = owner.begin_transfer(self.identity, AuthorizedHomeOperation(
                "test-installer", "home-a", "TRANSFER_HUB", "test-inflight-transfer"),
                "home-b", 4)
            self.assertEqual(epoch, 2)
        result = self.exchange(before_dispatch=transfer_after_tls)
        self.assertEqual(result.get("status"), 403, result)
        self.assertEqual(self.effects(), 0)

    def test_012_stale_epoch_or_transfer(self):
        owner = HubOwnershipRegistry(self.endpoint.db)
        owner.revoke_hub(self.identity, AuthorizedHomeOperation(
            "test-installer", "home-a", "REVOKE_HUB", "test-revoke"), 4)
        self.assertNotIn("status", self.exchange())
        self.assertEqual(self.effects(), 0)

    def test_013_untrusted_time(self):
        self.assertNotIn("status", self.exchange(trusted_now=None))
        self.assertEqual(self.effects(), 0)

    def test_014_exact_retry_no_duplicate_effect(self):
        self.assertEqual(self.exchange().get("status"), 201)
        retry = self.exchange()
        self.assertEqual(retry.get("status"), 200)
        self.assertEqual((retry["body"]["status"], retry["body"]["duplicate"]),
                         ("COMMITTED", True))
        self.assertEqual(self.effects(), 1)

    def test_015_backend_restart_retry(self):
        self.assertEqual(self.exchange().get("status"), 201)
        self.endpoint.close()
        self.service, self.endpoint = self.open_api()
        self.assertEqual(self.exchange().get("status"), 200)
        self.assertEqual(self.effects(), 1)

    def test_016_network_recovery(self):
        self.assertEqual(self.effects(), 0)
        self.assertEqual(self.exchange().get("status"), 201)
        self.assertEqual(self.effects(), 1)

    def test_017_malformed_body_no_commit(self):
        bad = self.body(); bad["event_key"]["event_sequence"] = "bad"
        self.assertNotEqual(self.exchange(body=bad).get("status"), 201)
        self.assertEqual(self.effects(), 0)

    def test_019_production_worker_real_mtls_durable_retry(self):
        """Real Hub worker JSON -> real TLS -> durable API -> exact Hub receipt."""
        binary = ROOT / "build/p2d_cloud_contract_validation"
        self.assertTrue(binary.is_file(), "build p2d-cloud-contract-host-test first")
        process = subprocess.Popen([str(binary), "--worker-api-bridge"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1)
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        try:
            def read_line():
                self.assertTrue(selector.select(timeout=15), "production worker timed out")
                line = process.stdout.readline()
                self.assertTrue(line, "production worker exited early")
                return line.strip()

            first = json.loads(read_line())
            self.assertEqual(first["event_key"], self.body()["event_key"])
            committed = self.exchange(body=first)
            self.assertEqual(committed.get("status"), 201, committed)
            self.assertEqual(self.effects(), 1)
            # Authenticated backend committed, but the response is lost before
            # the Hub sees it. The retained original request must be retried.
            process.stdin.write("0 0 0\n{}\n")
            process.stdin.flush()
            retried = json.loads(read_line())
            self.assertEqual(retried, first)
            duplicate = self.exchange(body=retried)
            self.assertEqual(duplicate.get("status"), 200, duplicate)
            self.assertTrue(duplicate["body"]["duplicate"])
            process.stdin.write("200 1 1\n" +
                json.dumps(duplicate["body"], separators=(",", ":")) + "\n")
            process.stdin.flush()
            worker_result = read_line()
            self.assertIn("RESULT gs148_worker_api_bridge=PASS completed=1 attempts=2", worker_result)
            print(worker_result, flush=True)
            self.assertEqual(process.wait(timeout=10), 0, process.stderr.read())
            self.assertEqual(self.effects(), 1)
            self.assertEqual(self.endpoint.db.execute("SELECT COUNT(*) FROM notification_jobs").fetchone()[0], 1)
            projection = self.service.queries.snapshot("home-a", "care-1", 1800001000)
            self.assertEqual(projection["recent_events"][0]["kind"], "CALL_FAMILY")
        finally:
            selector.close()
            if process.poll() is None:
                process.kill(); process.wait(timeout=5)
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()


if __name__ == "__main__":
    integration_only = "--integration-only" in sys.argv[1:]
    names = [name for name in unittest.defaultTestLoader.getTestCaseNames(CloudSyncMtlsSimHilTest)
             if (name.startswith("test_019_") if integration_only else not name.startswith("test_019_"))]
    suite = unittest.TestSuite(CloudSyncMtlsSimHilTest(name) for name in names)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({"suite": "cloudsync_mtls_integration" if integration_only else "cloudsync_mtls_sim_hil", "cases": result.testsRun,
                      "failures": len(result.failures), "errors": len(result.errors),
                      "physical": "NOT_RUN", "status": "PASS" if result.wasSuccessful() else "FAIL"},
                     sort_keys=True))
    if result.wasSuccessful():
        print(f"CLOUDSYNC MTLS {'INTEGRATION' if integration_only else 'SIM HIL'} PASS cases={result.testsRun} physical=NOT_RUN")
    sys.exit(0 if result.wasSuccessful() and result.testsRun == (1 if integration_only else 18) else 1)
