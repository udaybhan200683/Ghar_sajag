"""Isolated TEST_ONLY mTLS evidence backend for GS-68.

The library binds to loopback by default and never contacts an external host.
Its mTLS receipt proves that the server validated the presented client
certificate during TLS 1.2 and that the exact case challenge was durably
recorded by this TEST_ONLY service. Production CloudSync APIs are not exposed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import base64
import hashlib
import ipaddress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
import json
from pathlib import Path
import re
import sqlite3
import ssl
import socket
import stat
import threading
import tempfile

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography import x509
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from gs68_capture import canonical_json, verify_node_hub_event_key

CASE_IDS = {f"GS68-PHY-{number:03d}" for number in range(1, 11)}
MAX_REQUEST = 32 * 1024
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class BackendError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_receipt(signer: Ed25519PrivateKey, payload: dict) -> dict:
    receipt = dict(payload)
    receipt["signature_b64"] = base64.b64encode(signer.sign(canonical_json(payload))).decode("ascii")
    return receipt


class GS68TestBackend:
    """mTLS-only test receiver with transactional duplicate suppression."""
    def __init__(self, *, server_cert: Path, server_key: Path, client_ca: Path,
                 signer: Ed25519PrivateKey, sqlite_path: Path,
                 allowed_clients: dict[str, dict], bind: str = "127.0.0.1",
                 isolated_network_confirmed: bool = False,
                 trusted_time_utc: datetime | None = None,
                 revoked_client_fingerprints: set[str] | None = None):
        self.server_cert = Path(server_cert)
        self.server_key = Path(server_key)
        self.client_ca = Path(client_ca)
        self.signer = signer
        self.sqlite_path = Path(sqlite_path)
        self.allowed_clients = {key.lower(): dict(value) for key, value in allowed_clients.items()}
        self.trusted_time_utc = trusted_time_utc
        self.revoked_client_fingerprints = {
            value.lower() for value in (revoked_client_fingerprints or set())
        }
        try:
            address = ipaddress.ip_address(bind)
        except ValueError as exc:
            raise BackendError("backend bind must be a numeric IP address") from exc
        if not address.is_loopback and (not address.is_private or not isolated_network_confirmed):
            raise BackendError("non-loopback TEST_ONLY bind requires an explicitly confirmed private test network")
        self.bind = str(address)
        self._scenarios = {}
        self._scenario_lock = threading.Lock()
        self._http = None
        self._thread = None

    def validate_startup(self) -> None:
        """Validate all TEST_ONLY startup inputs before opening the listener."""
        if (not isinstance(self.trusted_time_utc, datetime) or self.trusted_time_utc.tzinfo is None or
                self.trusted_time_utc.utcoffset() is None):
            raise BackendError("synthetic trusted time must include an explicit UTC offset")
        if not isinstance(self.signer, Ed25519PrivateKey):
            raise BackendError("TEST_ONLY evidence signer must be Ed25519")
        if not self.allowed_clients:
            raise BackendError("TEST_ONLY Hub identity allowlist must not be empty")
        for fingerprint, identity in self.allowed_clients.items():
            if not HEX64.fullmatch(fingerprint):
                raise BackendError("Hub identity certificate fingerprint is invalid")
            if not isinstance(identity, dict):
                raise BackendError("Hub identity mapping must be an object")
            for field in ("hub_id", "home_id"):
                if not isinstance(identity.get(field), str) or not IDENTIFIER.fullmatch(identity[field]):
                    raise BackendError(f"Hub identity mapping has invalid {field}")
            epoch = identity.get("installation_epoch")
            if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 1:
                raise BackendError("Hub identity mapping has invalid installation_epoch")
        if any(not HEX64.fullmatch(value) for value in self.revoked_client_fingerprints):
            raise BackendError("revoked certificate fingerprint is invalid")
        for path in (self.server_cert, self.server_key, self.client_ca):
            if not path.is_file():
                raise BackendError(f"TEST_ONLY startup file is missing: {path.name}")
        if not self.sqlite_path.parent.is_dir():
            raise BackendError("TEST_ONLY SQLite parent directory must already exist")
        if self.sqlite_path.exists() and self.sqlite_path.is_symlink():
            raise BackendError("TEST_ONLY SQLite path must not be a symbolic link")
        for path in (self.server_key,):
            if stat.S_IMODE(path.stat().st_mode) & 0o077:
                raise BackendError(f"TEST_ONLY private key must be owner-only: {path.name}")
        try:
            server_cert = x509.load_pem_x509_certificate(self.server_cert.read_bytes())
            server_key = serialization.load_pem_private_key(self.server_key.read_bytes(), password=None)
            ca_cert = x509.load_pem_x509_certificate(self.client_ca.read_bytes())
            if (not isinstance(server_cert.public_key(), rsa.RSAPublicKey) or
                    not isinstance(server_key, rsa.RSAPrivateKey) or
                    server_cert.public_key().public_numbers() != server_key.public_key().public_numbers()):
                raise BackendError("TEST_ONLY server certificate and private key do not match")
            if not isinstance(ca_cert.public_key(), rsa.RSAPublicKey):
                raise BackendError("TEST_ONLY client CA must be RSA for this harness")
            constraints = ca_cert.extensions.get_extension_for_class(x509.BasicConstraints).value
            if not constraints.ca:
                raise BackendError("TEST_ONLY client trust certificate is not a CA")
            server_usage = server_cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
            if ExtendedKeyUsageOID.SERVER_AUTH not in server_usage:
                raise BackendError("TEST_ONLY server certificate lacks serverAuth EKU")
        except BackendError:
            raise
        except Exception as exc:
            raise BackendError(f"TEST_ONLY startup material is invalid: {type(exc).__name__}") from exc

    def _certificate_error(self, peer_der: bytes) -> tuple[str | None, str]:
        try:
            certificate = x509.load_der_x509_certificate(peer_der)
            public_key = certificate.public_key()
            usage = certificate.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
            key_usage = certificate.extensions.get_extension_for_class(x509.KeyUsage).value
        except Exception:
            return "invalid_client_certificate_profile", ""
        if not isinstance(public_key, rsa.RSAPublicKey) or public_key.key_size != 3072:
            return "client_certificate_must_use_rsa3072", ""
        if ExtendedKeyUsageOID.CLIENT_AUTH not in usage:
            return "client_certificate_missing_client_auth_eku", ""
        if not key_usage.digital_signature:
            return "client_certificate_missing_digital_signature_usage", ""
        trusted_time = self.trusted_time_utc.astimezone(timezone.utc)
        not_before = (certificate.not_valid_before_utc if hasattr(certificate, "not_valid_before_utc")
                      else certificate.not_valid_before.replace(tzinfo=timezone.utc))
        not_after = (certificate.not_valid_after_utc if hasattr(certificate, "not_valid_after_utc")
                     else certificate.not_valid_after.replace(tzinfo=timezone.utc))
        if trusted_time < not_before or trusted_time > not_after:
            return "client_certificate_outside_synthetic_trusted_time", ""
        fingerprint = sha256(peer_der)
        if fingerprint in self.revoked_client_fingerprints:
            return "client_certificate_revoked", fingerprint
        return None, fingerprint

    @property
    def public_signing_key_pem(self) -> bytes:
        return self.signer.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)

    @property
    def public_signing_key_sha256(self) -> str:
        return sha256(self.public_signing_key_pem)

    def set_case_control(self, case_id: str, outcome: str, detail: str = ""):
        """In-process automated test control; never exposed on the TLS API."""
        if case_id not in CASE_IDS or outcome not in {"ACCEPT", "REJECT", "DROP_ONCE", "MALFORMED_RECEIPT"}:
            raise BackendError("unsupported test control scenario")
        with self._scenario_lock:
            self._scenarios[case_id] = (outcome, detail[:256])

    def start(self):
        if self._http is not None:
            raise BackendError("TEST_ONLY backend already started")
        self.validate_startup()
        if not self.sqlite_path.exists():
            fd = os.open(self.sqlite_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)
        elif stat.S_IMODE(self.sqlite_path.stat().st_mode) & 0o077:
            raise BackendError("TEST_ONLY SQLite database must be owner-only mode 0600")
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, fmt, *args):
                # Never log request bodies, certificate contents, or credentials.
                return

            def _send(self, code: int, value: dict):
                body = canonical_json(value)
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path != "/healthz":
                    self._send(404, {"error": "not_found", "environment": "TEST_ONLY"})
                    return
                peer = self.connection.getpeercert(binary_form=True)
                if not peer:
                    self._send(401, {"error": "client_certificate_required"})
                    return
                profile_error, cert_fp = owner._certificate_error(peer)
                if profile_error:
                    self._send(403, {"error": profile_error})
                    return
                if cert_fp not in owner.allowed_clients:
                    self._send(403, {"error": "unknown_client"})
                    return
                challenge = self.headers.get("X-GS68-Nonce", "")
                if len(challenge) != 64 or any(c not in "0123456789abcdef" for c in challenge):
                    self._send(400, {"error": "invalid_nonce", "environment": "TEST_ONLY"})
                    return
                server_cert = x509.load_pem_x509_certificate(owner.server_cert.read_bytes())
                receipt = make_receipt(owner.signer, {
                    "schema": "gs68.backend.health.v1", "backend_id": "gs68-test-backend",
                    "environment": "TEST_ONLY", "status": "HEALTHY",
                    "tls_version": self.connection.version(),
                    "client_certificate_sha256": cert_fp,
                    "server_certificate_sha256": server_cert.fingerprint(hashes.SHA256()).hex(),
                    "challenge_nonce": challenge,
                })
                self._send(200, receipt)

            def do_POST(self):
                if self.path == "/v1/gs68/readiness":
                    self._readiness()
                    return
                if self.path != "/v1/gs68/case":
                    self._send(404, {"error": "not_found", "environment": "TEST_ONLY"})
                    return
                peer = self.connection.getpeercert(binary_form=True)
                if not peer:
                    self._send(401, {"error": "client_certificate_required"})
                    return
                profile_error, cert_fp = owner._certificate_error(peer)
                if profile_error:
                    self._send(403, {"error": profile_error})
                    return
                identity = owner.allowed_clients.get(cert_fp)
                if identity is None:
                    self._send(403, {"error": "unknown_client"})
                    return
                try:
                    length = int(self.headers.get("Content-Length", "-1"))
                except ValueError:
                    length = -1
                if length <= 0 or length > MAX_REQUEST:
                    self._send(413, {"error": "invalid_length"})
                    return
                try:
                    request = json.loads(self.rfile.read(length))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self._send(400, {"error": "invalid_json"})
                    return
                if not isinstance(request, dict):
                    self._send(400, {"error": "invalid_request"})
                    return
                case_id = request.get("case_id")
                if case_id not in CASE_IDS:
                    self._send(400, {"error": "unknown_case"})
                    return
                nonce = request.get("challenge_nonce")
                if not isinstance(nonce, str) or len(nonce) != 64 or any(c not in "0123456789abcdef" for c in nonce):
                    self._send(400, {"error": "invalid_nonce"})
                    return
                required = ("fixture_id", "source_commit", "image_sha256", "profile_sha256", "case_plan_sha256",
                            "hub_id", "home_id", "installation_epoch", "event_body_sha256")
                if any(not isinstance(request.get(field), (str, int)) or not str(request[field]) for field in required):
                    self._send(400, {"error": "missing_binding"})
                    return
                event_key = request.get("event_key")
                if isinstance(event_key, dict):
                    fields = ("physical_device_id", "source_id", "session_id", "sequence")
                    if set(event_key) != set(fields) or any(not str(event_key.get(key, "")) for key in fields):
                        self._send(400, {"error": "invalid_node_event_key"})
                        return
                    if any(not isinstance(event_key[key], str) or not IDENTIFIER.fullmatch(event_key[key])
                           for key in ("physical_device_id", "source_id")):
                        self._send(400, {"error": "invalid_node_event_key"})
                        return
                    for key in ("session_id", "sequence"):
                        value = event_key[key]
                        if (not isinstance(value, str) or not value.isdigit() or int(value) < 1 or
                                str(int(value)) != value):
                            self._send(400, {"error": "invalid_node_event_key"})
                            return
                elif not isinstance(event_key, str) or not event_key:
                    self._send(400, {"error": "invalid_event_key"})
                    return
                observation = request.get("observation")
                if not isinstance(observation, dict):
                    self._send(400, {"error": "missing_observation"})
                    return
                optional_hashes = ("c3_image_sha256", "c3_profile_sha256")
                if any(field in request and (not isinstance(request[field], str) or
                       not HEX64.fullmatch(request[field])) for field in optional_hashes):
                    self._send(400, {"error": "invalid_c3_event_binding"})
                    return
                if any(field in request for field in optional_hashes) and not all(field in request for field in optional_hashes):
                    self._send(400, {"error": "incomplete_c3_event_binding"})
                    return
                observation_digest = sha256(canonical_json(observation))
                if request["event_body_sha256"] != observation_digest:
                    self._send(400, {"error": "observation_digest_mismatch"})
                    return
                if isinstance(event_key, dict) and verify_node_hub_event_key(observation, event_key):
                    self._send(400, {"error": "node_event_key_ack_mismatch"})
                    return
                if request["hub_id"] != identity.get("hub_id"):
                    self._send(403, {"error": "hub_identity_mismatch"})
                    return
                if request["home_id"] != identity.get("home_id") or request["installation_epoch"] != identity.get("installation_epoch"):
                    self._send(403, {"error": "ownership_epoch_mismatch"})
                    return
                with owner._scenario_lock:
                    scenario, detail = owner._scenarios.get(case_id, ("ACCEPT", ""))
                if scenario == "REJECT":
                    payload = {"status": "REJECTED", "case_outcome": "FAIL", "durable": False,
                               "detail": detail or "injected_test_rejection"}
                    self._send(403, make_receipt(owner.signer, owner._receipt_base(
                        self, request, cert_fp, identity, payload)))
                    return
                if scenario == "DROP_ONCE":
                    with owner._scenario_lock:
                        owner._scenarios[case_id] = ("ACCEPT", detail)
                    self.close_connection = True
                    return
                if scenario == "MALFORMED_RECEIPT":
                    self._send(200, {"environment": "TEST_ONLY", "signature_b64": "bad"})
                    return
                body_sha = request["event_body_sha256"]
                if not isinstance(body_sha, str) or not HEX64.fullmatch(body_sha):
                    self._send(400, {"error": "invalid_body_digest"})
                    return
                commit_binding = {key: request[key] for key in (
                    "fixture_id", "source_commit", "image_sha256", "profile_sha256",
                    "case_plan_sha256", "hub_id", "home_id", "installation_epoch",
                    "case_id", "event_key", "event_body_sha256", "observation")}
                for optional_binding in ("c3_image_sha256", "c3_profile_sha256"):
                    if optional_binding in request:
                        commit_binding[optional_binding] = request[optional_binding]
                commit_sha = sha256(canonical_json(commit_binding))
                event_key_storage = (canonical_json(event_key).decode("ascii")
                                     if isinstance(event_key, dict) else event_key)
                duplicate = False
                try:
                    with sqlite3.connect(owner.sqlite_path, timeout=2, isolation_level=None) as db:
                        db.execute("PRAGMA journal_mode=WAL")
                        db.execute("PRAGMA synchronous=FULL")
                        db.execute("CREATE TABLE IF NOT EXISTS gs68_commits_v2 (fixture TEXT NOT NULL, event_key TEXT NOT NULL, commit_sha TEXT NOT NULL, receipt TEXT NOT NULL, PRIMARY KEY(fixture,event_key))")
                        db.execute("BEGIN IMMEDIATE")
                        row = db.execute("SELECT commit_sha,receipt FROM gs68_commits_v2 WHERE fixture=? AND event_key=?",
                                         (request["fixture_id"], event_key_storage)).fetchone()
                        if row is not None:
                            if row[0] != commit_sha:
                                db.execute("ROLLBACK")
                                self._send(409, {"error": "event_key_binding_conflict"})
                                return
                            duplicate = True
                        payload = {"status": "COMMITTED", "case_outcome": "PASS", "duplicate": duplicate,
                                   "durable": True, "detail": "TEST_ONLY_sqlite_commit"}
                        receipt = owner._receipt_base(self, request, cert_fp, identity, payload)
                        signed = make_receipt(owner.signer, receipt)
                        if row is None:
                            db.execute("INSERT INTO gs68_commits_v2 VALUES (?,?,?,?)",
                                (request["fixture_id"], event_key_storage, commit_sha,
                                 canonical_json(signed).decode("ascii")))
                        db.execute("COMMIT")
                except sqlite3.Error:
                    self._send(503, {"error": "test_backend_storage_fault"})
                    return
                self._send(200, signed)

            def _readiness(self):
                peer = self.connection.getpeercert(binary_form=True)
                if not peer:
                    self._send(401, {"error": "client_certificate_required"})
                    return
                profile_error, cert_fp = owner._certificate_error(peer)
                if profile_error:
                    self._send(403, {"error": profile_error})
                    return
                identity = owner.allowed_clients.get(cert_fp)
                if identity is None:
                    self._send(403, {"error": "unknown_client"})
                    return
                try:
                    length = int(self.headers.get("Content-Length", "-1"))
                except ValueError:
                    length = -1
                if length <= 0 or length > MAX_REQUEST:
                    self._send(413, {"error": "invalid_length"})
                    return
                try:
                    request = json.loads(self.rfile.read(length))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self._send(400, {"error": "invalid_json"})
                    return
                if not isinstance(request, dict):
                    self._send(400, {"error": "invalid_request"})
                    return
                nonce = request.get("challenge_nonce")
                if not isinstance(nonce, str) or not HEX64.fullmatch(nonce):
                    self._send(400, {"error": "invalid_nonce"})
                    return
                required = ("fixture_id", "source_commit", "image_sha256", "profile_sha256",
                    "case_plan_sha256", "hub_id", "home_id", "installation_epoch", "case_id")
                if any(field not in request for field in required):
                    self._send(400, {"error": "missing_binding"})
                    return
                if not isinstance(request["fixture_id"], str) or not IDENTIFIER.fullmatch(request["fixture_id"]):
                    self._send(400, {"error": "invalid_fixture_id"})
                    return
                if not isinstance(request["source_commit"], str) or not HEX40.fullmatch(request["source_commit"]):
                    self._send(400, {"error": "invalid_source_commit"})
                    return
                if any(not isinstance(request[field], str) or not HEX64.fullmatch(request[field])
                       for field in ("image_sha256", "profile_sha256", "case_plan_sha256")):
                    self._send(400, {"error": "invalid_readiness_hash"})
                    return
                optional_hashes = ("c3_image_sha256", "c3_profile_sha256")
                if any(field in request and (not isinstance(request[field], str) or
                       not HEX64.fullmatch(request[field])) for field in optional_hashes):
                    self._send(400, {"error": "invalid_c3_readiness_hash"})
                    return
                if any(field in request for field in optional_hashes) and not all(field in request for field in optional_hashes):
                    self._send(400, {"error": "incomplete_c3_readiness_binding"})
                    return
                if request["case_id"] not in CASE_IDS:
                    self._send(400, {"error": "unknown_case"})
                    return
                epoch = request["installation_epoch"]
                if (request["hub_id"] != identity["hub_id"] or request["home_id"] != identity["home_id"]
                        or isinstance(epoch, bool) or not isinstance(epoch, int)
                        or epoch != identity["installation_epoch"]):
                    self._send(403, {"error": "ownership_epoch_mismatch"})
                    return
                server_cert = x509.load_pem_x509_certificate(owner.server_cert.read_bytes())
                payload = {
                    "schema": "gs68.backend.readiness.v1", "backend_id": "gs68-test-backend",
                    "environment": "TEST_ONLY", "status": "READY",
                    "created_utc": datetime.now(timezone.utc).isoformat(),
                    "tls_version": self.connection.version(),
                    "client_certificate_sha256": cert_fp,
                    "server_certificate_sha256": server_cert.fingerprint(hashes.SHA256()).hex(),
                    "fixture_id": request["fixture_id"], "source_commit": request["source_commit"],
                    "image_sha256": request["image_sha256"], "profile_sha256": request["profile_sha256"],
                    "case_plan_sha256": request["case_plan_sha256"], "case_id": request["case_id"],
                    "challenge_nonce": nonce, "hub_id": identity["hub_id"],
                    "home_id": identity["home_id"], "installation_epoch": str(identity["installation_epoch"]),
                    "trusted_time_utc": owner.trusted_time_utc.astimezone(timezone.utc).isoformat(),
                    "physical": "NOT_RUN",
                }
                for field in optional_hashes:
                    if field in request:
                        payload[field] = request[field]
                self._send(200, make_receipt(owner.signer, payload))

        self._http = ThreadingHTTPServer((self.bind, 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = context.maximum_version = ssl.TLSVersion.TLSv1_2
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(cafile=str(self.client_ca))
        context.load_cert_chain(str(self.server_cert), str(self.server_key))
        self._http.socket = context.wrap_socket(self._http.socket, server_side=True)
        self._thread = threading.Thread(target=self._http.serve_forever, daemon=True)
        self._thread.start()
        return self._http.server_address

    def _receipt_base(self, handler, request, cert_fp, identity, outcome):
        server_cert = x509.load_pem_x509_certificate(self.server_cert.read_bytes())
        receipt = {
            "schema": "gs68.backend.receipt.v1", "environment": "TEST_ONLY",
            "backend_id": "gs68-test-backend", "created_utc": datetime.now(timezone.utc).isoformat(),
            "tls_version": handler.connection.version(),
            "client_certificate_sha256": cert_fp,
            "server_certificate_sha256": server_cert.fingerprint(hashes.SHA256()).hex(),
            "fixture_id": request["fixture_id"], "source_commit": request["source_commit"],
            "image_sha256": request["image_sha256"], "profile_sha256": request["profile_sha256"],
            "case_plan_sha256": request["case_plan_sha256"],
            "case_id": request["case_id"], "challenge_nonce": request["challenge_nonce"],
            "hub_id": identity.get("hub_id"), "home_id": identity.get("home_id"),
            "installation_epoch": str(identity.get("installation_epoch", "")),
            "trusted_time_utc": self.trusted_time_utc.astimezone(timezone.utc).isoformat(),
            "event_key": request["event_key"], "event_body_sha256": request["event_body_sha256"],
            **outcome,
        }
        for optional_binding in ("c3_image_sha256", "c3_profile_sha256"):
            if optional_binding in request:
                receipt[optional_binding] = request[optional_binding]
        return receipt

    def close(self):
        if self._http is not None:
            self._http.shutdown()
            self._http.server_close()
            self._thread.join(timeout=2)
            self._http = None
            self._thread = None


def _synthetic_certificate(ca_key, ca_cert, common_name, key, *, server, now):
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    eku = ExtendedKeyUsageOID.SERVER_AUTH if server else ExtendedKeyUsageOID.CLIENT_AUTH
    builder = (x509.CertificateBuilder().subject_name(subject).issuer_name(ca_cert.subject)
        .public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(hours=12))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
            key_encipherment=True, data_encipherment=False, key_agreement=False,
            key_cert_sign=False, crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
        .add_extension(x509.ExtendedKeyUsage([eku]), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False))
    if server:
        builder = builder.add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
    return builder.sign(ca_key, hashes.SHA256())


def _write_private(path: Path, value: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(value)


def _run_self_test() -> None:
    """Exercise generated credentials, TLS 1.2 readiness and durable retry locally."""
    now = datetime.now(timezone.utc).replace(microsecond=0)
    with tempfile.TemporaryDirectory(prefix="gs68-test-backend-") as name:
        root = Path(name)
        ca_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "GS68 temporary TEST_ONLY CA")])
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
        server_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        client_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        server_cert = _synthetic_certificate(ca_key, ca_cert, "localhost", server_key,
                                             server=True, now=now)
        client_cert = _synthetic_certificate(ca_key, ca_cert, "gs68-temporary-hub", client_key,
                                             server=False, now=now)
        ca_path = root / "client-ca.pem"
        server_cert_path = root / "server.pem"
        server_key_path = root / "server-key.pem"
        client_cert_path = root / "client.pem"
        client_key_path = root / "client-key.pem"
        ca_path.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
        server_cert_path.write_bytes(server_cert.public_bytes(serialization.Encoding.PEM))
        client_cert_path.write_bytes(client_cert.public_bytes(serialization.Encoding.PEM))
        _write_private(server_key_path, server_key.private_bytes(serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        _write_private(client_key_path, client_key.private_bytes(serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        client_fp = client_cert.fingerprint(hashes.SHA256()).hex()
        backend = GS68TestBackend(server_cert=server_cert_path, server_key=server_key_path,
            client_ca=ca_path, signer=Ed25519PrivateKey.generate(), sqlite_path=root / "commits.sqlite",
            allowed_clients={client_fp: {"hub_id": "test-hub-001", "home_id": "test-home-001",
                                         "installation_epoch": 3}}, trusted_time_utc=now)
        address = backend.start()
        try:
            context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=str(ca_path))
            context.minimum_version = context.maximum_version = ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(str(client_cert_path), str(client_key_path))

            def exchange(route: str, payload: dict) -> dict:
                body = canonical_json(payload)
                with socket.create_connection(address, timeout=3) as raw:
                    with context.wrap_socket(raw, server_hostname="localhost") as connection:
                        request = (f"POST {route} HTTP/1.1\r\nHost: localhost\r\n"
                            f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n"
                            "Connection: close\r\n\r\n").encode("ascii") + body
                        connection.sendall(request)
                        response = bytearray()
                        while True:
                            chunk = connection.recv(4096)
                            if not chunk:
                                break
                            response.extend(chunk)
                header, _, content = bytes(response).partition(b"\r\n\r\n")
                status = int(header.split(b" ", 2)[1])
                if status != 200:
                    raise BackendError(f"TEST_ONLY self-test endpoint returned HTTP {status}")
                return json.loads(content)

            common = {"fixture_id": "GS68-SELF-TEST", "source_commit": "a" * 40,
                "image_sha256": "b" * 64, "profile_sha256": "c" * 64,
                "c3_image_sha256": "f" * 64, "c3_profile_sha256": "1" * 64,
                "case_plan_sha256": "d" * 64, "hub_id": "test-hub-001",
                "home_id": "test-home-001", "installation_epoch": 3,
                "case_id": "GS68-PHY-001", "challenge_nonce": "e" * 64}
            readiness = exchange("/v1/gs68/readiness", common)
            from gs68_capture import verify_backend_receipt
            binding = dict(common, installation_epoch="3")
            if verify_backend_receipt(readiness, backend.public_signing_key_pem, binding):
                raise BackendError("TEST_ONLY self-test readiness signature or binding failed")
            observation = {"case_id": "GS68-PHY-001", "result": "synthetic"}
            request = dict(common, event_key="test-node:3:1", observation=observation,
                event_body_sha256=sha256(canonical_json(observation)))
            first = exchange("/v1/gs68/case", request)
            second = exchange("/v1/gs68/case", request)
            if first.get("durable") is not True or first.get("duplicate") is not False or second.get("duplicate") is not True:
                raise BackendError("TEST_ONLY self-test durable duplicate-safe receipt failed")
        finally:
            backend.close()


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--serve", action="store_true", help="start the isolated TEST_ONLY mTLS service")
    parser.add_argument("--server-cert", type=Path)
    parser.add_argument("--server-key", type=Path)
    parser.add_argument("--client-ca", type=Path)
    parser.add_argument("--evidence-signing-key", type=Path)
    parser.add_argument("--allowed-clients", type=Path, help="JSON map of client certificate fingerprints to test identities")
    parser.add_argument("--sqlite", type=Path)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--confirm-isolated-network", action="store_true")
    parser.add_argument("--trusted-time-utc", help="explicit synthetic trust time, ISO-8601 with UTC offset")
    parser.add_argument("--revoked-fingerprints", type=Path, help="TEST_ONLY JSON array of revoked client certificate SHA-256 values")
    args = parser.parse_args(argv)
    if args.self_test:
        try:
            _run_self_test()
        except Exception as exc:
            print(f"GS68 TEST BACKEND SELF-TEST FAIL reason={type(exc).__name__}")
            return 1
        print("GS68 TEST BACKEND SELF-TEST PASS tls=TLS1.2 rsa3072=PASS readiness=SIGNED durable_retry=PASS physical=NOT_RUN external_network=NOT_USED")
        return 0
    if not args.serve:
        parser.error("select --self-test or explicitly configure --serve")
    required = (args.server_cert, args.server_key, args.client_ca,
                args.evidence_signing_key, args.allowed_clients, args.sqlite)
    if any(path is None for path in required):
        parser.error("--serve requires explicit server certificate/key, client CA, evidence signer, allowlist, and SQLite paths")
    if not args.trusted_time_utc:
        parser.error("--serve requires --trusted-time-utc with an explicit UTC offset")
    for private_path in (args.server_key, args.evidence_signing_key):
        mode = stat.S_IMODE(private_path.stat().st_mode)
        if mode & 0o077:
            parser.error(f"TEST_ONLY private key file must be owner-only mode 0600: {private_path.name}")
    try:
        allowed = json.loads(args.allowed_clients.read_text(encoding="utf-8"))
        signing_key = serialization.load_pem_private_key(args.evidence_signing_key.read_bytes(), password=None)
        trusted_time = datetime.fromisoformat(args.trusted_time_utc.replace("Z", "+00:00"))
        revoked = json.loads(args.revoked_fingerprints.read_text(encoding="utf-8")) if args.revoked_fingerprints else []
    except Exception as exc:
        parser.error(f"TEST_ONLY startup material cannot be parsed: {type(exc).__name__}")
    if not isinstance(allowed, dict) or not isinstance(signing_key, Ed25519PrivateKey) or not isinstance(revoked, list):
        parser.error("allowlist must be a JSON object and evidence signer must be Ed25519")
    server = GS68TestBackend(server_cert=args.server_cert, server_key=args.server_key,
        client_ca=args.client_ca, signer=signing_key, sqlite_path=args.sqlite,
        allowed_clients=allowed, bind=args.bind,
        isolated_network_confirmed=args.confirm_isolated_network, trusted_time_utc=trusted_time,
        revoked_client_fingerprints=set(revoked))
    try:
        address = server.start()
    except Exception as exc:
        parser.error(f"TEST_ONLY startup validation failed: {type(exc).__name__}")
    print(json.dumps({"status": "READY", "environment": "TEST_ONLY",
        "bind": address[0], "port": address[1],
        "evidence_signing_public_key_sha256": server.public_signing_key_sha256,
        "commercial_sending_enabled": False, "physical": "NOT_RUN"}, sort_keys=True))
    try:
        server._thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
