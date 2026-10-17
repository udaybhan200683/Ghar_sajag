from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import socket
import ssl
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

import gs68_capture as capture
import gs68_cloudsync_hil as runner
from gs68_signed_time_fixture import SignedTimeFixtureError, TestOnlySignedTimeFixture
from gs68_test_backend import GS68TestBackend


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FakeTransport:
    def __init__(self, response=b""):
        self.response = response
        self.opened = False
        self.closed = False
        self.writes = []

    def open(self):
        self.opened = True

    def write(self, payload):
        self.writes.append(payload)

    def read_line(self, timeout):
        return self.response

    def close(self):
        self.closed = True


class QueueTransport(FakeTransport):
    def __init__(self, responses):
        super().__init__()
        self.responses = list(responses)

    def read_line(self, timeout):
        return self.responses.pop(0) if self.responses else b""


class GS68PhysicalCaptureTests(unittest.TestCase):
    def test_dry_import_and_fixture_template_do_not_open_serial(self):
        with patch.object(capture.PySerialTransport, "open", side_effect=AssertionError("serial opened")):
            transport = FakeTransport()
            self.assertFalse(transport.opened)
            self.assertEqual(capture.parse_device_frame, capture.parse_device_frame)

    def test_only_explicit_by_id_path_can_construct_serial_transport(self):
        with self.assertRaises(capture.CaptureError):
            capture.PySerialTransport("/dev/ttyUSB0")
        adapter = capture.PySerialTransport("/dev/serial/by-id/usb-GS68-SPARE")
        self.assertIsNone(adapter.device)

    def test_protocol_frame_and_bounded_response(self):
        valid = b'GS68/1 {"schema":"gs68.target.event.v1","event":"ready"}\n'
        transport = FakeTransport(valid)
        session = capture.BoundedCapture(transport, timeout_seconds=5)
        session.open()
        result = session.request_case("GS68-PHY-001", "a" * 64, {"operation": "PROBE"})
        self.assertEqual(result["event"], "ready")
        self.assertIn(b"GS68-PHY-001", transport.writes[0])
        session.close()
        self.assertTrue(transport.closed)

    def test_c3_observation_command_is_read_only_and_source_image_bound(self):
        case_id, nonce = "GS68-PHY-006", "a" * 64
        binding = {"source_commit": "b" * 40, "profile_sha256": "c" * 64,
                   "running_image_sha256": "d" * 64}
        frame = {"schema": "gs68.target.event.v1", "event": "node_observation",
            "role": "c3", "case_id": case_id, "challenge_nonce": nonce,
            **binding, "physical": "NOT_RUN"}
        transport = FakeTransport(b"GS68/1 " + capture.canonical_json(frame) + b"\n")
        session = capture.BoundedCapture(transport, timeout_seconds=5)
        session.open()
        self.assertEqual(session.request_node_observation(case_id, nonce, binding), frame)
        self.assertIn(b'"operation":"OBSERVE"', transport.writes[0])
        self.assertNotIn(b'"operation":"RUN_CASE"', transport.writes[0])
        session.close()

        wrong_image = dict(frame, running_image_sha256="e" * 64)
        bad = capture.BoundedCapture(FakeTransport(
            b"GS68/1 " + capture.canonical_json(wrong_image) + b"\n"), timeout_seconds=5)
        bad.open()
        with self.assertRaisesRegex(capture.CaptureError, "running_image_sha256"):
            bad.request_node_observation(case_id, nonce, binding)
        bad.close()


    def test_truncated_oversized_and_invalid_frames_fail_closed(self):
        transport = FakeTransport(b"GS68/1 {\"schema\":\"gs68.target.event.v1\"}")
        session = capture.BoundedCapture(transport, timeout_seconds=5)
        session.open()
        with self.assertRaisesRegex(capture.CaptureError, "truncated"):
            session.request_case("GS68-PHY-001", "b" * 64, {"operation": "PROBE"})
        with self.assertRaises(capture.CaptureError):
            capture.parse_device_frame(b"GS68/1 " + b"x" * (capture.MAX_FRAME_BYTES + 1))
        with self.assertRaisesRegex(capture.CaptureError, "schema"):
            capture.parse_device_frame(b"GS68/1 {}")
        session.close()

    def test_case_identifier_nonce_and_observation_limits_are_enforced(self):
        session = capture.BoundedCapture(FakeTransport(b""), timeout_seconds=1)
        session.open()
        with self.assertRaisesRegex(capture.CaptureError, "unknown physical case"):
            session.request_case("GS68-PHY-099", "c" * 64, {})
        with self.assertRaisesRegex(capture.CaptureError, "nonce"):
            session.request_case("GS68-PHY-001", "not-a-nonce", {})
        session.close()
        with self.assertRaises(ValueError):
            capture.BoundedCapture(FakeTransport(), timeout_seconds=901)

    def test_hash_chain_detects_tampering_and_reordering(self):
        chain = capture.make_hash_chain([{"case_id": "GS68-PHY-001", "observation": "ok"},
                                        {"case_id": "GS68-PHY-002", "observation": "ok"}])
        self.assertEqual(capture.verify_hash_chain(chain), [])
        changed = json.loads(json.dumps(chain))
        changed[0]["observation"] = "altered"
        self.assertTrue(capture.verify_hash_chain(changed))
        self.assertTrue(capture.verify_hash_chain(list(reversed(chain))))

    def test_case_receipt_must_bind_schema_outcome_and_durable_commit(self):
        signer = Ed25519PrivateKey.generate()
        public = signer.public_key().public_bytes(serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo)
        binding = {"fixture_id": "GS68-SPARE-UNIT-001", "source_commit": "a" * 40,
            "image_sha256": "b" * 64, "profile_sha256": "c" * 64,
            "backend_id": "gs68-test-backend", "client_certificate_sha256": "e" * 64,
            "server_certificate_sha256": "f" * 64, "case_plan_sha256": "e" * 64,
            "hub_id": "hub-001",
            "home_id": "home-001", "installation_epoch": "7"}
        nonce = "d" * 64
        observation = {"case_id": "GS68-PHY-001", "signing": "verified", "rsa_bits": 3072}
        receipt = {"schema": "gs68.backend.receipt.v1", "environment": "TEST_ONLY",
            "tls_version": "TLSv1.2", **binding,
            "case_id": "GS68-PHY-001", "challenge_nonce": nonce,
            "event_body_sha256": _sha(capture.canonical_json(observation)),
            "case_outcome": "PASS", "status": "COMMITTED", "durable": True}
        signed = {**receipt, "signature_b64": base64.b64encode(
            signer.sign(capture.canonical_json(receipt))).decode("ascii")}
        frame = {"schema": "gs68.target.event.v1", "event": "case_result",
            "case_id": "GS68-PHY-001", "challenge_nonce": nonce,
            "case_outcome": "PASS", "observation": observation, "backend_receipt": signed}
        self.assertEqual(capture.verify_case_frame(frame, case_id="GS68-PHY-001",
            nonce=nonce, binding=binding, verifier_pem=public), [])
        tampered_observation = dict(frame, observation={"case_id": "GS68-PHY-001", "signing": "failed"})
        self.assertTrue(any("exact target observation" in item for item in
            capture.verify_case_frame(tampered_observation, case_id="GS68-PHY-001",
                nonce=nonce, binding=binding, verifier_pem=public)))
        blocked = dict(frame, case_outcome="BLOCKED")
        self.assertTrue(capture.verify_case_frame(blocked, case_id="GS68-PHY-001",
            nonce=nonce, binding=binding, verifier_pem=public))
        forged = dict(frame, case_outcome="PASS", backend_receipt={**signed, "durable": False})
        self.assertTrue(capture.verify_case_frame(forged, case_id="GS68-PHY-001",
            nonce=nonce, binding=binding, verifier_pem=public))

    def test_integrated_adapter_capture_cannot_promote_blocked_or_fake_to_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            signer = Ed25519PrivateKey.generate()
            public = signer.public_key().public_bytes(serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo)
            verifier_path = root / "backend-verifier.pem"
            verifier_path.write_bytes(public)
            fixture = {"fixture_id": "GS68-SPARE-UNIT-001", "source_commit": "a" * 40,
                "profile": {"profile_sha256": "b" * 64},
                "boards": {"s3": {"flash_mb": 16, "psram_mb": 8,
                    "identity": {"mac_address": "02:00:00:00:68:01",
                        "usb_serial_short": "UNIT-S3", "port_by_id": "/dev/serial/by-id/unit-s3"},
                    "image": {"sha256": "c" * 64}}}}
            backend = {"backend_id": "gs68-test-backend",
                "client_certificate_sha256": "d" * 64,
                "server_certificate_sha256": "e" * 64,
                "hub_id": "hub-001", "home_id": "home-001", "installation_epoch": 7,
                "evidence_signing_public_key_path": str(verifier_path)}
            case_id, nonce = "GS68-PHY-001", "d" * 64
            ready = {"schema": "gs68.target.event.v1", "event": "ready",
                "source_commit": "a" * 40, "profile_sha256": "b" * 64,
                "running_image_sha256": "c" * 64, "mac_address": "020000006801",
                "flash_bytes": 16 * 1024 * 1024, "flash_status": 0,
                "psram_bytes": 8 * 1024 * 1024,
                "chip_model": "ESP32-S3"}
            result = {"schema": "gs68.target.event.v1", "event": "case_result",
                "case_id": case_id, "challenge_nonce": nonce, "case_outcome": "BLOCKED",
                "reason": "DS_TEST_IDENTITY_NOT_PROVISIONED",
                "observation": {"signing": "BLOCKED_NO_DS_CONTEXT"}}
            transport = QueueTransport([
                b"GS68/1 " + capture.canonical_json(ready) + b"\n",
                b"GS68/1 " + capture.canonical_json(result) + b"\n"])
            with patch.object(runner, "_inspect_by_id_port", return_value={
                    "resolved_device": "/dev/ttyACM-unit", "usb_serial_short": "UNIT-S3", "id_path": "unit"}), \
                 patch.object(runner.secrets, "token_hex", return_value=nonce):
                report = runner._execute_physical(fixture, backend,
                    {"cases": [{"case_id": case_id}]}, "a" * 40, "e" * 64,
                    [case_id], root / "capture", transport_factory=lambda _port: transport)
            self.assertEqual(report["overall"], "BLOCKED")
            self.assertEqual(report["physical"], "CAPTURED_UNADJUDICATED")
            self.assertEqual(report["physical_execution"], "CAPTURED")
            self.assertEqual(report["captured_case_count"], 1)
            self.assertFalse(report["capture_complete"])
            bundle = json.loads(Path(report["capture_bundle"]).read_text())
            self.assertEqual(bundle["records"][0]["adjudication"], "BLOCKED")

    def test_atomic_evidence_write_is_restricted_and_verifiable(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "capture.json"
            capture.write_evidence_bundle(path, {"physical": "NOT_RUN", "records": []})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertTrue(path.read_bytes().endswith(b"\n"))

    def _backend(self, temp, client_key_size=3072, *, revoked=False,
                 trusted_time_delta=timedelta(0)):
        root = Path(temp)
        ca_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "GS68 TEST ONLY CA")])
        now = datetime.now(timezone.utc)
        ca_cert = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
            .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                key_encipherment=False, data_encipherment=False, key_agreement=False,
                key_cert_sign=True, crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
            .sign(ca_key, hashes.SHA256()))

        def issue(name, server=False, key_size=3072):
            key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
            subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
            builder = (x509.CertificateBuilder().subject_name(subject).issuer_name(ca_cert.subject)
                .public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(hours=12))
                .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                    key_encipherment=True, data_encipherment=False, key_agreement=False,
                    key_cert_sign=False, crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
                .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
                .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
                .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH if server else ExtendedKeyUsageOID.CLIENT_AUTH]), critical=True))
            if server:
                builder = builder.add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
            cert = builder.sign(ca_key, hashes.SHA256())
            key_pem = key.private_bytes(serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
            from types import SimpleNamespace
            return SimpleNamespace(cert=cert, key_pem=key_pem,
                pem=cert.public_bytes(serialization.Encoding.PEM),
                fingerprint=hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest(),
                write=lambda directory, label: _write_pair(directory, label, cert, key_pem))

        def _write_pair(directory, label, cert, key_pem):
            cert_path, key_path = root / (label + ".crt"), root / (label + ".key")
            cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(key_pem)
            return cert_path, key_path

        server = issue("localhost", server=True)
        client = issue("gs68-spare-hub", key_size=client_key_size)
        ca_path = root / "ca.pem"
        ca_path.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
        server_cert, server_key = server.write(root, "server")
        client_cert, client_key = client.write(root, "client")
        signer = Ed25519PrivateKey.generate()
        backend = GS68TestBackend(server_cert=server_cert, server_key=server_key,
            client_ca=ca_path, signer=signer, sqlite_path=root / "commits.sqlite",
            allowed_clients={client.fingerprint: {"hub_id": "hub-001", "home_id": "home-001", "installation_epoch": 7}},
            trusted_time_utc=now + trusted_time_delta,
            revoked_client_fingerprints={client.fingerprint} if revoked else set())
        address = backend.start()
        return backend, address, ca_path, client_cert, client_key, client.fingerprint

    def _exchange(self, address, ca_path, client_cert, client_key, payload, method="POST", route="/v1/gs68/case", headers=None):
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=str(ca_path))
        context.minimum_version = context.maximum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(str(client_cert), str(client_key))
        with socket.create_connection(address, timeout=3) as raw:
            with context.wrap_socket(raw, server_hostname="localhost") as connection:
                body = capture.canonical_json(payload) if payload is not None else b""
                extra = "".join(f"{name}: {value}\r\n" for name, value in (headers or {}).items())
                request = (f"{method} {route} HTTP/1.1\r\nHost: localhost\r\n{extra}"
                           f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n").encode() + body
                connection.sendall(request)
                response = bytearray()
                while True:
                    data = connection.recv(4096)
                    if not data:
                        break
                    response.extend(data)
        header, _, content = bytes(response).partition(b"\r\n\r\n")
        status = int(header.split(b" ", 2)[1])
        return status, json.loads(content) if content else {}

    def _request(self):
        observation = {"case_id": "GS68-PHY-008", "assertion": "durable_duplicate_safe"}
        return {"fixture_id": "GS68-SPARE-001", "source_commit": "a" * 40,
            "image_sha256": "b" * 64, "profile_sha256": "c" * 64,
            "case_plan_sha256": "e" * 64,
            "hub_id": "hub-001", "home_id": "home-001", "installation_epoch": 7,
            "event_key": "node-01:7:123", "event_body_sha256": _sha(capture.canonical_json(observation)),
            "observation": observation,
            "case_id": "GS68-PHY-008", "challenge_nonce": "e" * 64}

    def test_test_only_backend_requires_mtls_and_signs_exact_durable_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            backend, address, ca, cert, key, client_fingerprint = self._backend(temp)
            try:
                status, health = self._exchange(address, ca, cert, key, None, "GET", "/healthz",
                                                {"X-GS68-Nonce": "e" * 64})
                self.assertEqual(status, 200)
                self.assertEqual(health["tls_version"], "TLSv1.2")
                status, first = self._exchange(address, ca, cert, key, self._request())
                status2, second = self._exchange(address, ca, cert, key, self._request())
                self.assertEqual((status, status2), (200, 200))
                self.assertFalse(first["duplicate"])
                self.assertTrue(second["duplicate"])
                self.assertEqual(first["client_certificate_sha256"], client_fingerprint)
                public = backend.public_signing_key_pem
                binding = {key: self._request()[key] for key in (
                    "fixture_id", "source_commit", "image_sha256", "profile_sha256", "case_plan_sha256",
                    "hub_id", "home_id", "installation_epoch", "case_id", "challenge_nonce",
                    "event_key", "event_body_sha256")}
                binding["installation_epoch"] = str(binding["installation_epoch"])
                self.assertEqual(capture.verify_backend_receipt(first, public, binding), [])
                altered = dict(first, event_body_sha256="f" * 64)
                self.assertTrue(capture.verify_backend_receipt(altered, public, binding))
            finally:
                backend.close()

    def test_backend_readiness_is_nonce_bound_and_signed(self):
        with tempfile.TemporaryDirectory() as temp:
            backend, address, ca, cert, key, fingerprint = self._backend(temp)
            try:
                nonce = "9" * 64
                status, health = self._exchange(address, ca, cert, key, None, "GET", "/healthz",
                                                {"X-GS68-Nonce": nonce})
                self.assertEqual(status, 200)
                self.assertEqual(health["schema"], "gs68.backend.health.v1")
                request = self._request()
                readiness_request = {field: request[field] for field in (
                    "fixture_id", "source_commit", "image_sha256", "profile_sha256",
                    "case_plan_sha256", "hub_id", "home_id", "installation_epoch", "case_id")}
                readiness_request.update(c3_image_sha256="1" * 64, c3_profile_sha256="2" * 64)
                readiness_request["challenge_nonce"] = nonce
                status, receipt = self._exchange(address, ca, cert, key, readiness_request,
                                                 "POST", "/v1/gs68/readiness")
                self.assertEqual(status, 200)
                binding = dict(readiness_request, installation_epoch="7")
                self.assertEqual(capture.verify_backend_receipt(receipt,
                    backend.public_signing_key_pem, binding), [])
                self.assertEqual(receipt["client_certificate_sha256"], fingerprint)
                self.assertEqual(receipt["status"], "READY")
                self.assertEqual(receipt["physical"], "NOT_RUN")
            finally:
                backend.close()

    def test_backend_rejects_non_rsa3072_client_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            backend, address, ca, cert, key, _ = self._backend(temp, client_key_size=2048)
            try:
                status, response = self._exchange(address, ca, cert, key, None, "GET", "/healthz",
                                                  {"X-GS68-Nonce": "8" * 64})
                self.assertEqual(status, 403)
                self.assertEqual(response["error"], "client_certificate_must_use_rsa3072")
            finally:
                backend.close()

    def test_backend_tls_rejects_client_certificate_from_untrusted_ca(self):
        with tempfile.TemporaryDirectory() as temp:
            backend, address, ca, _, _, _ = self._backend(temp)
            try:
                now = datetime.now(timezone.utc)
                foreign_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
                foreign_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "untrusted GS68 client")])
                foreign_cert = (x509.CertificateBuilder().subject_name(foreign_name).issuer_name(foreign_name)
                    .public_key(foreign_key.public_key()).serial_number(x509.random_serial_number())
                    .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(hours=1))
                    .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
                    .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                        key_encipherment=False, data_encipherment=False, key_agreement=False,
                        key_cert_sign=True, crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
                    .add_extension(x509.SubjectKeyIdentifier.from_public_key(foreign_key.public_key()), critical=False)
                    .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(foreign_key.public_key()), critical=False)
                    .sign(foreign_key, hashes.SHA256()))
                client_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
                client_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "foreign-hub")])
                client_cert = (x509.CertificateBuilder().subject_name(client_name).issuer_name(foreign_name)
                    .public_key(client_key.public_key()).serial_number(x509.random_serial_number())
                    .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(hours=1))
                    .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                    .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                        key_encipherment=True, data_encipherment=False, key_agreement=False,
                        key_cert_sign=False, crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
                    .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=True)
                    .add_extension(x509.SubjectKeyIdentifier.from_public_key(client_key.public_key()), critical=False)
                    .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(foreign_key.public_key()), critical=False)
                    .sign(foreign_key, hashes.SHA256()))
                cert_path, key_path = Path(temp) / "foreign-client.pem", Path(temp) / "foreign-client.key"
                cert_path.write_bytes(client_cert.public_bytes(serialization.Encoding.PEM))
                fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(client_key.private_bytes(serialization.Encoding.PEM,
                        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
                with self.assertRaises(ssl.SSLError):
                    self._exchange(address, ca, cert_path, key_path, None, "GET", "/healthz",
                                   {"X-GS68-Nonce": "a" * 64})
            finally:
                backend.close()

    def test_backend_wrong_home_and_event_key_body_conflict_reject(self):
        with tempfile.TemporaryDirectory() as temp:
            backend, address, ca, cert, key, _ = self._backend(temp)
            try:
                wrong_home = self._request()
                wrong_home["home_id"] = "home-other"
                status, response = self._exchange(address, ca, cert, key, wrong_home)
                self.assertEqual(status, 403)
                self.assertEqual(response["error"], "ownership_epoch_mismatch")
                self.assertEqual(self._exchange(address, ca, cert, key, self._request())[0], 200)
                conflict = self._request()
                conflict["observation"] = {"case_id": "GS68-PHY-008", "assertion": "different_payload"}
                conflict["event_body_sha256"] = _sha(capture.canonical_json(conflict["observation"]))
                status, response = self._exchange(address, ca, cert, key, conflict)
                self.assertEqual(status, 409)
                self.assertEqual(response["error"], "event_key_binding_conflict")
                wrong_epoch = self._request()
                wrong_epoch["installation_epoch"] = 8
                status, response = self._exchange(address, ca, cert, key, wrong_epoch)
                self.assertEqual(status, 403)
                self.assertEqual(response["error"], "ownership_epoch_mismatch")
            finally:
                backend.close()

    def test_backend_requires_observation_digest_to_match_submitted_measurement(self):
        with tempfile.TemporaryDirectory() as temp:
            backend, address, ca, cert, key, _ = self._backend(temp)
            try:
                request = self._request()
                request["event_body_sha256"] = "0" * 64
                status, response = self._exchange(address, ca, cert, key, request)
                self.assertEqual(status, 400)
                self.assertEqual(response["error"], "observation_digest_mismatch")
            finally:
                backend.close()

    def test_control_interface_is_restricted_to_known_test_cases(self):
        with tempfile.TemporaryDirectory() as temp:
            backend, *_ = self._backend(temp)
            try:
                backend.set_case_control("GS68-PHY-004", "REJECT", "revoked")
                with self.assertRaisesRegex(Exception, "unsupported"):
                    backend.set_case_control("GS68-PHY-999", "ACCEPT")
                with self.assertRaisesRegex(Exception, "loopback"):
                    GS68TestBackend(server_cert=Path("missing"), server_key=Path("missing"),
                        client_ca=Path("missing"), signer=Ed25519PrivateKey.generate(),
                        sqlite_path=Path("/tmp/missing.sqlite"), allowed_clients={}, bind="0.0.0.0")
            finally:
                backend.close()

    def test_backend_rejects_revoked_and_synthetic_time_expired_client_certificates(self):
        for options, expected in (({"revoked": True}, "client_certificate_revoked"),
                                  ({"trusted_time_delta": timedelta(hours=13)},
                                   "client_certificate_outside_synthetic_trusted_time")):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as temp:
                backend, address, ca, cert, key, _ = self._backend(temp, **options)
                try:
                    status, response = self._exchange(address, ca, cert, key, None,
                        "GET", "/healthz", {"X-GS68-Nonce": "f" * 64})
                    self.assertEqual(status, 403)
                    self.assertEqual(response["error"], expected)
                finally:
                    backend.close()

    def test_test_only_backend_lost_response_retry_is_durable_and_duplicate_safe(self):
        with tempfile.TemporaryDirectory() as temp:
            backend, address, ca, cert, key, _ = self._backend(temp)
            try:
                backend.set_case_control("GS68-PHY-008", "DROP_ONCE")
                request = self._request()
                with self.assertRaises((IndexError, ValueError)):
                    self._exchange(address, ca, cert, key, request)
                status, first_receipt = self._exchange(address, ca, cert, key, request)
                self.assertEqual(status, 200)
                self.assertFalse(first_receipt["duplicate"])
                status, retry_receipt = self._exchange(address, ca, cert, key, request)
                self.assertEqual(status, 200)
                self.assertTrue(retry_receipt["duplicate"])
                self.assertTrue(retry_receipt["durable"])
                backend.close()
                self.assertIsNone(backend._http)
                self.assertIsNone(backend._thread)
            finally:
                backend.close()

    def test_node_hub_exact_event_key_requires_authenticated_durable_ack(self):
        key = {"physical_device_id": "node-01", "source_id": "node-logical-01",
               "session_id": "7", "sequence": "19"}
        observation = {"last_ack_event_key": dict(key), "last_ack_authenticated": True,
            "last_ack_matched_pending": True, "last_ack_retired": True, "last_ack_durable": True}
        self.assertEqual(capture.verify_node_hub_event_key(observation, key), [])
        wrong = dict(key, sequence="20")
        self.assertTrue(capture.verify_node_hub_event_key(observation, wrong))
        unauthenticated = dict(observation, last_ack_authenticated=False)
        self.assertTrue(capture.verify_node_hub_event_key(unauthenticated, key))

    def test_backend_paired_commit_binds_exact_node_ack_event_key(self):
        with tempfile.TemporaryDirectory() as temp:
            backend, address, ca, cert, key, _ = self._backend(temp)
            try:
                event_key = {"physical_device_id": "node-01", "source_id": "node-logical-01",
                    "session_id": "7", "sequence": "19"}
                observation = {"case_id": "GS68-PHY-006", "last_ack_event_key": dict(event_key),
                    "last_ack_authenticated": True, "last_ack_matched_pending": True,
                    "last_ack_retired": True, "last_ack_durable": True}
                request = dict(self._request(), case_id="GS68-PHY-006", event_key=event_key,
                    observation=observation, event_body_sha256=_sha(capture.canonical_json(observation)))
                status, receipt = self._exchange(address, ca, cert, key, request)
                self.assertEqual(status, 200)
                self.assertEqual(receipt["event_key"], event_key)
                self.assertTrue(receipt["durable"])
                forged = dict(request, event_key=dict(event_key, sequence="20"))
                forged["event_body_sha256"] = _sha(capture.canonical_json(observation))
                status, response = self._exchange(address, ca, cert, key, forged)
                self.assertEqual(status, 400)
                self.assertEqual(response["error"], "node_event_key_ack_mismatch")
            finally:
                backend.close()


class GS68SignedTimeFixtureTests(unittest.TestCase):
    def test_ephemeral_public_key_and_current_challenge_proof(self):
        fixture = TestOnlySignedTimeFixture()
        key_command = fixture.load_key_command()
        self.assertEqual(key_command["operation"], "LOAD_TIME_KEY")
        self.assertEqual(key_command["case_id"], "GS68-AUX-TIME-001")
        public_der = base64.b64decode(key_command["payload_b64"], validate=True)
        public_key = serialization.load_der_public_key(public_der)
        self.assertEqual(public_key.key_size, 3072)
        self.assertNotIn("private", key_command)

        challenge = {"schema": "gs68.target.event.v1", "event": "time_challenge",
                     "case_id": "GS68-AUX-TIME-001", "challenge_nonce": "a" * 64,
                     "boot_generation": 7, "created_monotonic_ms": 1234}
        command = fixture.proof_command(challenge, issued_at_utc=1_900_000_000)
        proof = base64.b64decode(command["payload_b64"], validate=True)
        self.assertEqual(len(proof), 456)
        self.assertEqual(proof[:4], b"GSTP")
        self.assertEqual(int.from_bytes(proof[8:16], "big"), 7)
        self.assertEqual(proof[16:48], b"\xaa" * 32)
        public_key.verify(proof[72:], proof[:72], padding.PKCS1v15(), hashes.SHA256())
        self.assertEqual(command["challenge_nonce"], challenge["challenge_nonce"])
        next_challenge = dict(challenge, challenge_nonce="b" * 64,
                              case_id="GS68-AUX-TIME-002")
        variant = dict(next_challenge, proof_variant={
            "issued_at_utc": 1_900_000_001, "valid_from_utc": 1_900_000_001,
            "valid_until_utc": 1_900_000_000, "boot_generation": 8})
        with self.assertRaisesRegex(SignedTimeFixtureError, "interval"):
            fixture.proof_command(variant)
        stale_generation = dict(next_challenge, proof_variant={
            "issued_at_utc": 1_900_000_001, "valid_from_utc": 1_900_000_001,
            "valid_until_utc": 1_900_000_121, "boot_generation": 6})
        stale = fixture.proof_command(stale_generation)
        stale_proof = base64.b64decode(stale["payload_b64"], validate=True)
        self.assertEqual(int.from_bytes(stale_proof[8:16], "big"), 6)
        generation_zero = dict(next_challenge, proof_variant={
            "issued_at_utc": 1_900_000_001, "valid_from_utc": 1_900_000_001,
            "valid_until_utc": 1_900_000_121, "boot_generation": 0})
        zero = fixture.proof_command(generation_zero)
        zero_proof = base64.b64decode(zero["payload_b64"], validate=True)
        self.assertEqual(int.from_bytes(zero_proof[8:16], "big"), 0)

    def test_invalid_challenge_and_generation_fail_closed(self):
        fixture = TestOnlySignedTimeFixture()
        invalid_frames = [
            {},
            {"schema": "gs68.target.event.v1", "event": "ready",
             "case_id": "GS68-AUX-TIME-001", "challenge_nonce": "a" * 64,
             "boot_generation": 1},
            {"schema": "gs68.target.event.v1", "event": "time_challenge",
             "case_id": "GS68-AUX-TIME-001", "challenge_nonce": "A" * 64,
             "boot_generation": 1},
            {"schema": "gs68.target.event.v1", "event": "time_challenge",
             "case_id": "GS68-AUX-TIME-001", "challenge_nonce": "a" * 64,
             "boot_generation": True},
            {"schema": "gs68.target.event.v1", "event": "time_challenge",
             "case_id": "GS68-AUX-TIME-001", "challenge_nonce": "a" * 64,
             "boot_generation": 0},
        ]
        for frame in invalid_frames:
            with self.subTest(frame=frame), self.assertRaises(SignedTimeFixtureError):
                fixture.proof_command(frame, issued_at_utc=1_900_000_000)


if __name__ == "__main__":
    unittest.main()
