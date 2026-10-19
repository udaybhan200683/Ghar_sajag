"""Permanent complete-bootstrap negatives; all connections are loopback TLS."""
import copy
import json
import secrets
import socket
import ssl
import unittest
from datetime import datetime, timezone
from cryptography.hazmat.primitives import serialization

from gs178_stack import ProductStack, HOME, HUB, product_stack_for_test
from pilot_test_issuer import new_test_csr, TestOnlyIssuer


class BootstrapSecurity(unittest.TestCase):
    def fixture(self):
        fixture = product_stack_for_test()
        self.addCleanup(fixture.close)
        return fixture

    def test_configuration_signature_failure_prevents_time_and_tls(self):
        s = self.fixture()
        def corrupt(frame): return frame[:-1] + bytes([frame[-1] ^ 1])
        with self.assertRaisesRegex(AssertionError, "authenticated config"):
            s.start_node(transform=corrupt)
        self.assertEqual((s.time.requests, s.receipts), (0, []))

    def test_wrong_recipient_and_unknown_fields_fail_before_network(self):
        s = self.fixture()
        def wrong_nonce(frame): return frame[:9] + bytes([frame[9] ^ 1]) + frame[10:]
        with self.assertRaisesRegex(AssertionError, "authenticated config"):
            s.start_node(transform=wrong_nonce)
        self.assertEqual(s.time.requests, 0)

    def test_invalid_time_signature_prevents_tls(self):
        s = self.fixture()
        s.time.response_transform = lambda proof: proof[:-1] + bytes([proof[-1] ^ 1])
        with self.assertRaisesRegex(AssertionError, "real signed-time accepted"):
            s.start_node()
        self.assertEqual((s.time.requests, s.receipts), (1, []))

    def test_stale_boot_generation_prevents_tls(self):
        s = self.fixture()
        s.time.proof_variant = {"boot_generation": 99}
        with self.assertRaisesRegex(AssertionError, "real signed-time accepted"):
            s.start_node()
        self.assertEqual(s.receipts, [])

    def test_signed_excessive_lifetime_prevents_tls(self):
        s = self.fixture()
        s.time.proof_variant = {"valid_until_utc": s.now + 3600}
        with self.assertRaisesRegex(AssertionError, "real signed-time accepted"):
            s.start_node()
        self.assertEqual(s.receipts, [])

    def test_future_authority_lease_is_rejected_without_tolerance(self):
        s=self.fixture()
        s.authority.clock=lambda:s.now+100
        with self.assertRaisesRegex(AssertionError,"mTLS current authority bootstrap"):
            s.start_node()
        self.assertFalse(any(r.get("path","").endswith("/events") for r in s.receipts))

    def test_expired_registered_credential_fails_before_authority(self):
        s=self.fixture()
        key,csr=new_test_csr(HUB)
        s.issuer.clock=lambda:datetime.fromtimestamp(s.now-2*86400,timezone.utc)
        s.credential=s.issuer.issue(HUB,csr,renew=True,valid_days=1)
        s.key_pem=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
        with self.assertRaisesRegex(AssertionError,"mTLS current authority bootstrap"):
            s.start_node()
        self.assertEqual(s.receipts,[])

    def test_registry_generation_survives_reopen_and_replacement(self):
        s=self.fixture()
        _,csr=new_test_csr(HUB)
        self.assertEqual(s.issuer.issue(HUB,csr,renew=True).generation,2)
        authority=s.issuer.authority
        s.issuer.close()
        s.issuer=TestOnlyIssuer(s.path/"issuer.sqlite",authority=authority)
        _,csr=new_test_csr(HUB)
        self.assertEqual(s.issuer.issue(HUB,csr,renew=True).generation,3)
        self.assertEqual(s.issuer.by_fingerprint(s.credential.fingerprint).state,"SUPERSEDED")

    def test_authority_nonce_generation_replay_and_registry_replacement(self):
        s = self.fixture()
        body = {"protocol":"GS40T/1", "hub_id":HUB, "credential_generation":1,
                "certificate_fingerprint_sha256":s.credential.fingerprint,
                "boot_generation":1, "nonce":secrets.token_hex(32)}
        path = "/v1/test/authority/refresh"
        status, response = s.hub_request(path,body)
        self.assertEqual((status,response[:5]),(200,b"G40A\x01"))
        self.assertEqual(s.hub_request(path,body)[0],403)
        bad = {**body,"nonce":secrets.token_hex(32),"credential_generation":2}
        self.assertEqual(s.hub_request(path,bad)[0],403)
        key, csr = new_test_csr(HUB)
        replacement = s.issuer.issue(HUB, csr, renew=True)
        self.assertEqual(replacement.generation,2)
        self.assertEqual(s.issuer.by_fingerprint(s.credential.fingerprint).state,"SUPERSEDED")
        self.assertEqual(s.hub_request(path,{**body,"nonce":secrets.token_hex(32)})[0],403)
        self.assertEqual(key.key_size,3072)

    def test_wrong_home_stale_enrollment_conflict_and_headers_cannot_authorize(self):
        s = self.fixture()
        ready = s.start_node(); at = ready["utc"]+1
        s.domain_now = at+1
        s.command(f"input 0 motion {at} {at} 1000 420 0")
        self.assertEqual(s.command("sync 2000 1")["completed"],1)
        request = next(r["request"] for r in s.receipts if "request" in r and r["path"].endswith("/events"))
        path=f"/v1/homes/{HOME}/events"
        self.assertEqual(s.hub_request(path,request)[0],200)
        conflict=copy.deepcopy(request);conflict["location"]="wrong-room"
        self.assertEqual(s.hub_request(path,conflict)[0],409)
        old=copy.deepcopy(request);old["node_enrollment_generation"]=99
        self.assertEqual(s.hub_request(path,old)[0],403)
        self.assertEqual(s.hub_request("/v1/homes/gs177-test-other/events",request)[0],403)
        self.assertEqual(s.durable.db.execute("SELECT COUNT(*) FROM events").fetchone()[0],1)

    def test_spoofed_certificate_headers_cannot_replace_tls_client_certificate(self):
        s = self.fixture()
        ready = s.start_node()
        del ready
        body = json.dumps({"event_key": {"physical_device_id": "test-c3-bedroom"}}).encode()
        context = ssl.create_default_context(cafile=str(s.ca_path))
        context.minimum_version = context.maximum_version = ssl.TLSVersion.TLSv1_2
        with socket.create_connection(("127.0.0.1", int(s.hub_origin.rsplit(":", 1)[1])), timeout=3) as raw:
            with self.assertRaises((ssl.SSLError, OSError)):
                with context.wrap_socket(raw, server_hostname="localhost") as peer:
                    peer.sendall((f"POST /v1/homes/{HOME}/events HTTP/1.1\r\n"
                                  "Host: localhost\r\n"
                                  "X-Forwarded-Client-Cert: forged\r\n"
                                  "X-Client-Cert: forged\r\n"
                                  f"Content-Length: {len(body)}\r\n"
                                  "Content-Type: application/json\r\n\r\n").encode() + body)
                    peer.recv(512)
        self.assertEqual(s.durable.db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 0)
        self.assertEqual(s.receipts, [])


if __name__ == "__main__": unittest.main()
