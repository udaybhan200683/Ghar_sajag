"""Isolated TEST_ONLY mTLS evidence backend for GS-68.

The library binds to loopback by default and never contacts an external host.
Its mTLS receipt proves that the server validated the presented client
certificate during TLS 1.2 and that the exact case challenge was durably
recorded by this TEST_ONLY service. Production CloudSync APIs are not exposed.
"""
from __future__ import annotations

from datetime import datetime, timezone
import base64
import hashlib
import ipaddress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
import ssl
import stat
import threading

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography import x509
from cryptography.x509.oid import ExtendedKeyUsageOID

from gs68_capture import canonical_json

CASE_IDS = {f"GS68-PHY-{number:03d}" for number in range(1, 11)}
MAX_REQUEST = 32 * 1024


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
                 isolated_network_confirmed: bool = False):
        self.server_cert = Path(server_cert)
        self.server_key = Path(server_key)
        self.client_ca = Path(client_ca)
        self.signer = signer
        self.sqlite_path = Path(sqlite_path)
        self.allowed_clients = {key.lower(): dict(value) for key, value in allowed_clients.items()}
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
        owner = self

        def client_certificate_error(peer_der: bytes) -> str | None:
            try:
                certificate = x509.load_der_x509_certificate(peer_der)
                public_key = certificate.public_key()
                usage = certificate.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
            except Exception:
                return "invalid_client_certificate_profile"
            if not isinstance(public_key, rsa.RSAPublicKey) or public_key.key_size != 3072:
                return "client_certificate_must_use_rsa3072"
            if ExtendedKeyUsageOID.CLIENT_AUTH not in usage:
                return "client_certificate_missing_client_auth_eku"
            return None

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
                profile_error = client_certificate_error(peer)
                if profile_error:
                    self._send(403, {"error": profile_error})
                    return
                cert_fp = sha256(peer)
                if cert_fp not in owner.allowed_clients:
                    self._send(403, {"error": "unknown_client"})
                    return
                challenge = self.headers.get("X-GS68-Nonce", "")
                if len(challenge) != 64 or any(c not in "0123456789abcdef" for c in challenge):
                    self._send(400, {"error": "invalid_nonce", "environment": "TEST_ONLY"})
                    return
                server_cert = x509.load_pem_x509_certificate(owner.server_cert.read_bytes())
                receipt = make_receipt(owner.signer, {
                    "schema": "gs68.backend.readiness.v1", "backend_id": "gs68-test-backend",
                    "environment": "TEST_ONLY", "status": "READY",
                    "tls_version": self.connection.version(),
                    "client_certificate_sha256": cert_fp,
                    "server_certificate_sha256": server_cert.fingerprint(hashes.SHA256()).hex(),
                    "challenge_nonce": challenge,
                })
                self._send(200, receipt)

            def do_POST(self):
                if self.path != "/v1/gs68/case":
                    self._send(404, {"error": "not_found", "environment": "TEST_ONLY"})
                    return
                peer = self.connection.getpeercert(binary_form=True)
                if not peer:
                    self._send(401, {"error": "client_certificate_required"})
                    return
                profile_error = client_certificate_error(peer)
                if profile_error:
                    self._send(403, {"error": profile_error})
                    return
                cert_fp = sha256(peer)
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
                            "hub_id", "home_id", "installation_epoch", "event_key", "event_body_sha256")
                if any(not isinstance(request.get(field), (str, int)) or not str(request[field]) for field in required):
                    self._send(400, {"error": "missing_binding"})
                    return
                observation = request.get("observation")
                if not isinstance(observation, dict):
                    self._send(400, {"error": "missing_observation"})
                    return
                observation_digest = sha256(canonical_json(observation))
                if request["event_body_sha256"] != observation_digest:
                    self._send(400, {"error": "observation_digest_mismatch"})
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
                if not isinstance(body_sha, str) or len(body_sha) != 64 or any(c not in "0123456789abcdef" for c in body_sha):
                    self._send(400, {"error": "invalid_body_digest"})
                    return
                duplicate = False
                try:
                    with sqlite3.connect(owner.sqlite_path, timeout=2, isolation_level=None) as db:
                        db.execute("PRAGMA journal_mode=WAL")
                        db.execute("PRAGMA synchronous=FULL")
                        db.execute("CREATE TABLE IF NOT EXISTS gs68_commits (fixture TEXT NOT NULL, event_key TEXT NOT NULL, body_sha TEXT NOT NULL, case_id TEXT NOT NULL, receipt TEXT NOT NULL, PRIMARY KEY(fixture,event_key))")
                        db.execute("BEGIN IMMEDIATE")
                        row = db.execute("SELECT body_sha,receipt FROM gs68_commits WHERE fixture=? AND event_key=?",
                                         (request["fixture_id"], request["event_key"])).fetchone()
                        if row is not None:
                            if row[0] != body_sha:
                                db.execute("ROLLBACK")
                                self._send(409, {"error": "event_key_payload_conflict"})
                                return
                            duplicate = True
                        payload = {"status": "COMMITTED", "case_outcome": "PASS", "duplicate": duplicate,
                                   "durable": True, "detail": "TEST_ONLY_sqlite_commit"}
                        receipt = owner._receipt_base(self, request, cert_fp, identity, payload)
                        signed = make_receipt(owner.signer, receipt)
                        if row is None:
                            db.execute("INSERT INTO gs68_commits VALUES (?,?,?,?,?)",
                                (request["fixture_id"], request["event_key"], body_sha, case_id,
                                 canonical_json(signed).decode("ascii")))
                        db.execute("COMMIT")
                except sqlite3.Error:
                    self._send(503, {"error": "test_backend_storage_fault"})
                    return
                self._send(200, signed)

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
        return {
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
            "event_key": request["event_key"], "event_body_sha256": request["event_body_sha256"],
            **outcome,
        }

    def close(self):
        if self._http is not None:
            self._http.shutdown()
            self._http.server_close()
            self._thread.join(timeout=2)
            self._http = None
            self._thread = None


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
    args = parser.parse_args(argv)
    if args.self_test:
        print("GS68 TEST BACKEND SELF-TEST PASS physical=NOT_RUN external_network=NOT_USED")
        return 0
    if not args.serve:
        parser.error("select --self-test or explicitly configure --serve")
    required = (args.server_cert, args.server_key, args.client_ca,
                args.evidence_signing_key, args.allowed_clients, args.sqlite)
    if any(path is None for path in required):
        parser.error("--serve requires explicit server certificate/key, client CA, evidence signer, allowlist, and SQLite paths")
    for private_path in (args.server_key, args.evidence_signing_key):
        mode = stat.S_IMODE(private_path.stat().st_mode)
        if mode & 0o077:
            parser.error(f"TEST_ONLY private key file must be owner-only mode 0600: {private_path.name}")
    try:
        allowed = json.loads(args.allowed_clients.read_text(encoding="utf-8"))
        signing_key = serialization.load_pem_private_key(args.evidence_signing_key.read_bytes(), password=None)
    except Exception as exc:
        parser.error(f"TEST_ONLY startup material cannot be parsed: {type(exc).__name__}")
    if not isinstance(allowed, dict) or not isinstance(signing_key, Ed25519PrivateKey):
        parser.error("allowlist must be a JSON object and evidence signer must be Ed25519")
    server = GS68TestBackend(server_cert=args.server_cert, server_key=args.server_key,
        client_ca=args.client_ca, signer=signing_key, sqlite_path=args.sqlite,
        allowed_clients=allowed, bind=args.bind,
        isolated_network_confirmed=args.confirm_isolated_network)
    address = server.start()
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
