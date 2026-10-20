"""Permanent complete-bootstrap negatives; all connections are loopback TLS."""
import copy
from concurrent.futures import ThreadPoolExecutor
import http.client
import json
import secrets
import socket
import ssl
import time
import unittest
from datetime import datetime, timezone
from threading import Event
from urllib.error import URLError
from cryptography.hazmat.primitives import serialization

from gs178_stack import ProductStack, HOME, HUB, product_stack_for_test
from pilot_test_issuer import new_test_csr, TestOnlyIssuer
from ghar_sajag.test_only_mtls_listener import TestOnlyMtlsListener


class BootstrapSecurity(unittest.TestCase):
    def fixture(self):
        fixture = product_stack_for_test()
        self.addCleanup(fixture.close)
        return fixture

    @staticmethod
    def listener(s, **overrides):
        options = {
            "profile": "GS179_TEST_ONLY",
            "api": s.durable.api,
            "credentials": s.issuer,
            "ownership_db": s.durable.db,
            "server_cert": s.cert_path,
            "server_key": s.key_path,
            "client_ca": s.client_ca,
            "trusted_time": lambda: datetime.now(timezone.utc),
            "bind_host": "127.0.0.1",
            "available": lambda: True,
        }
        options.update(overrides)
        return TestOnlyMtlsListener(**options)

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

    def test_listener_requires_readiness_and_rejects_unsafe_or_unbounded_configuration(self):
        s = self.fixture()
        options = {
            "profile": "GS179_TEST_ONLY", "api": s.durable.api,
            "credentials": s.issuer, "ownership_db": s.durable.db,
            "server_cert": s.cert_path, "server_key": s.key_path,
            "client_ca": s.client_ca,
            "trusted_time": lambda: datetime.now(timezone.utc),
        }
        with self.subTest("missing readiness"):
            with self.assertRaisesRegex(ValueError, "readiness_provider_required"):
                TestOnlyMtlsListener(**options)
        with self.subTest("private address requires explicit bind opt-in"):
            with self.assertRaisesRegex(ValueError, "private_bind_requires_explicit_opt_in"):
                TestOnlyMtlsListener(**options, available=lambda: True,
                                     bind_host="192.168.1.6")
        with self.subTest("wildcard is never accepted"):
            with self.assertRaisesRegex(ValueError, "wildcard_or_reserved_bind_forbidden"):
                TestOnlyMtlsListener(**options, available=lambda: True,
                                     bind_host="0.0.0.0", allow_private_bind=True)
        with self.subTest("worker count is bounded"):
            with self.assertRaisesRegex(ValueError, "concurrency_out_of_bounds"):
                TestOnlyMtlsListener(**options, available=lambda: True,
                                     max_concurrent_requests=33)
        with self.subTest("backend readiness is checked before serving"):
            with self.assertRaisesRegex(ValueError, "backend_not_ready"):
                TestOnlyMtlsListener(**options, available=lambda: False)
        with self.subTest("trusted time is checked before serving"):
            no_time_options = {**options, "trusted_time": lambda: None}
            with self.assertRaisesRegex(ValueError, "trusted_time_not_ready"):
                TestOnlyMtlsListener(**no_time_options, available=lambda: True)
        with self.subTest("port is bounded"):
            with self.assertRaisesRegex(ValueError, "port_out_of_bounds"):
                TestOnlyMtlsListener(**options, available=lambda: True, port=65_536)

    def test_runtime_readiness_loss_rejects_backend_and_trusted_time(self):
        s = self.fixture()
        s.mtls_listener.close()
        readiness = [True]
        trusted_time = [datetime.now(timezone.utc)]
        listener = self.listener(
            s, available=lambda: readiness[0],
            trusted_time=lambda: trusted_time[0])
        s.mtls_listener = listener
        s.hub_origin = listener.start()
        path = f"/v1/homes/{HOME}/events"

        readiness[0] = False
        self.assertEqual(s.hub_request(path, {})[0], 503)
        readiness[0] = True
        trusted_time[0] = None
        self.assertEqual(s.hub_request(path, {})[0], 403)
        self.assertEqual(s.durable.db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 0)

    def test_listener_bounds_workers_then_recovers_and_drains_on_close(self):
        s = self.fixture()
        s.mtls_listener.close()
        entered = Event()
        release = Event()
        readiness_calls = 0
        serving = [False]

        def readiness():
            nonlocal readiness_calls
            if not serving[0]:
                return True
            readiness_calls += 1
            if readiness_calls == 1:
                entered.set()
                if not release.wait(5):
                    return False
            return True

        listener = self.listener(s, available=readiness, max_concurrent_requests=1)
        s.mtls_listener = listener
        s.hub_origin = listener.start()
        serving[0] = True
        path = f"/v1/homes/{HOME}/events"
        with ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(s.hub_request, path, {})
            self.assertTrue(entered.wait(3), "first authenticated request did not reach readiness")
            self.assertEqual(listener.server.active_workers, 1)
            with self.assertRaises((URLError, http.client.HTTPException, OSError)):
                s.hub_request(path, {})
            self.assertEqual(listener.server.active_workers, 1)
            self.assertEqual(readiness_calls, 1)
            release.set()
            status, _ = first.result(timeout=5)
            self.assertEqual(status, 400)  # empty event rejected; not misclassified as success

        # The capacity is released after the first request; the still-running
        # service accepts a later authenticated request and returns its actual
        # validation result.
        status, _ = s.hub_request(path, {})
        self.assertEqual(status, 400)
        self.assertEqual(readiness_calls, 2)
        self.assertTrue(listener.server.wait_for_workers(2))
        self.assertEqual(listener.server.active_workers, 0)
        listener.close(timeout_seconds=2)
        with self.assertRaisesRegex(RuntimeError, "test_listener_closed"):
            listener.start()

    def test_listener_bounds_incomplete_tls_handshakes_before_http_dispatch(self):
        s = self.fixture()
        s.mtls_listener.close()
        listener = self.listener(s, max_concurrent_requests=1, timeout_seconds=2)
        s.mtls_listener = listener
        s.hub_origin = listener.start()
        port = int(s.hub_origin.rsplit(":", 1)[1])

        # A TCP client that sends no TLS ClientHello occupies the one allowed
        # worker until the configured handshake timeout. It must not block the
        # accept loop or permit unbounded handshake work.
        stalled = socket.create_connection(("127.0.0.1", port), timeout=2)
        self.addCleanup(stalled.close)
        deadline = time.monotonic() + 2
        while listener.server.active_workers != 1 and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(listener.server.active_workers, 1)

        excess = socket.create_connection(("127.0.0.1", port), timeout=2)
        self.addCleanup(excess.close)
        excess.settimeout(2)
        self.assertEqual(excess.recv(1), b"")
        self.assertEqual(listener.server.active_workers, 1)

        self.assertTrue(listener.server.wait_for_workers(3))
        self.assertEqual(listener.server.active_workers, 0)
        stalled.settimeout(2)
        self.assertEqual(stalled.recv(1), b"")
        # After the stalled peer is gone, the application listener still
        # accepts a correctly authenticated client and applies normal request
        # validation. The empty body is deliberately invalid (400).
        self.assertEqual(s.hub_request(f"/v1/homes/{HOME}/events", {})[0], 400)


if __name__ == "__main__": unittest.main()
