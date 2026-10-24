"""GS40T/1 isolated host services. No serial access or production entry point.

Keys exist in host memory. Configuration output is encrypted to a fresh target
challenge. TLS peer validation and the existing GS-168/ownership registry are
the authority; request fields never supply Home ownership.
"""
from __future__ import annotations

import base64
import ipaddress
from datetime import datetime, timezone
import os
import re
import socket
import struct
import threading
import time
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from gs68_signed_time_fixture import TestOnlySignedTimeFixture
from ghar_sajag.cloud_client_identity import authorize_cloud_tls_context, TimeReadiness


# This is an owner-designated development fixture, not a general physical-ID
# enrollment rule. The authenticated certificate registry and current
# ownership/epoch checks remain authoritative for every request.
_GS117_PHYSICAL_HUB_ID = "hub-e072a1d38d34"
_GS117_PHYSICAL_HOME_ID = "gs177-test-product"
_PHYSICAL_HUB_ID = re.compile(r"hub-[0-9a-f]{12}\Z")


def public_der(key):
    return key.public_key().public_bytes(serialization.Encoding.DER,
                                         serialization.PublicFormat.SubjectPublicKeyInfo)


def rsa3072():
    return rsa.generate_private_key(public_exponent=65537, key_size=3072)


def isolated_destination(host):
    if host == "localhost" or (host.endswith(".test") and re.fullmatch(r"[a-z0-9.-]+", host)):
        return True
    try:
        address=ipaddress.IPv4Address(host)
        return any(address in ipaddress.IPv4Network(network) for network in
                   ("127.0.0.0/8","10.0.0.0/8","172.16.0.0/12","192.168.0.0/16"))
    except ipaddress.AddressValueError:
        return False


def encode_config(challenge: bytes, target_public: bytes, fields: dict[int, bytes], signer) -> bytes:
    """Return the exact length-prefixed G40E wire frame; never persist secrets.

    Caller must identify/authorize a fixture before delivering this frame. This
    pure sender neither identifies a board nor opens a port.
    """
    base_fields = set(range(1, 17))
    rule_fields = set(range(17, 21))
    supplied = set(fields)
    if (len(challenge) != 32 or not any(challenge) or
            supplied not in (base_fields, base_fields | rule_fields)):
        raise ValueError("invalid_fixture_challenge_or_fields")
    if not isinstance(signer, rsa.RSAPrivateKey) or signer.key_size != 3072:
        raise ValueError("test_config_rsa3072_signer_required")
    origin = urlsplit(fields[3].decode("ascii"))
    if (origin.scheme != "https" or not isolated_destination(origin.hostname or "")
            or origin.username or origin.password or origin.path or origin.query or origin.fragment
            or fields[4].decode("ascii") != origin.hostname
            or not 0 < (origin.port or 443) <= 65535
            or not isolated_destination(fields[6].decode("ascii"))):
        raise ValueError("isolated_test_origin_required")
    try:
        configured_hub_id = fields[9].decode("ascii")
    except (UnicodeDecodeError, AttributeError):
        raise ValueError("test_identity_required") from None
    if (not configured_hub_id.startswith("test-hub-") and
            not (configured_hub_id == _GS117_PHYSICAL_HUB_ID and
                 _PHYSICAL_HUB_ID.fullmatch(configured_hub_id))):
        raise ValueError("test_identity_required")
    if supplied == base_fields | rule_fields:
        if (not fields[17] or len(fields[17]) > 64 or
                fields[18] != b"Etc/UTC" or len(fields[19]) < 40 or
                len(fields[19]) > 512 or not fields[19].startswith(b"AR1") or
                len(fields[20]) != 1 or fields[20][0] > 4):
            raise ValueError("invalid_signed_home_rule_config")
    plaintext = b"G40P\x01" + b"".join(
        bytes([i]) + struct.pack(">H", len(fields[i])) + fields[i]
        for i in sorted(fields))
    if len(plaintext) > 16384:
        raise ValueError("config_too_large")
    target = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), target_public)
    ephemeral = ec.generate_private_key(ec.SECP256R1())
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=challenge,
               info=b"GS40T/1/CONFIG/AES256GCM\x00").derive(ephemeral.exchange(ec.ECDH(), target))
    public = ephemeral.public_key().public_bytes(serialization.Encoding.X962,
                                                serialization.PublicFormat.UncompressedPoint)
    iv = os.urandom(12)
    header = b"G40E\x01" + challenge + public + iv + struct.pack(">H", len(plaintext))
    unsigned = header + AESGCM(key).encrypt(iv, plaintext, header)
    envelope = unsigned + signer.sign(b"GS40T/1/CONFIG\x00" + unsigned,
                                       padding.PKCS1v15(), hashes.SHA256())
    if len(envelope) > 24576:
        raise ValueError("envelope_too_large")
    return struct.pack(">I", len(envelope)) + envelope


class SignedTimeService:
    """Bounded loopback UDP carrier for the existing GS-68 proof format."""
    def __init__(self, clock=time.time):
        self.fixture, self.clock = TestOnlySignedTimeFixture(), clock
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(("127.0.0.1", 0))
        self.socket.settimeout(.1)
        self.port = self.socket.getsockname()[1]
        self.stop = threading.Event()
        self.requests = 0
        self.proof_variant = None
        self.response_transform = lambda proof: proof
        self.worker = threading.Thread(target=self._serve, daemon=True)

    @property
    def public_key_der(self):
        return base64.b64decode(self.fixture.load_key_command()["payload_b64"])

    def start(self):
        self.worker.start()
        return self

    def _serve(self):
        while not self.stop.is_set() and self.requests < 256:
            try:
                request, address = self.socket.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                break
            self.requests += 1
            if len(request) != 45 or request[:5] != b"GSTQ\x01":
                continue
            generation = int.from_bytes(request[5:13], "big")
            if generation == 0 or not any(request[13:]):
                continue
            frame = {"schema": "gs68.target.event.v1", "event": "time_challenge",
                     "case_id": "GS68-AUX-TIME-001", "boot_generation": generation,
                     "challenge_nonce": request[13:].hex()}
            if self.proof_variant is not None:
                frame["proof_variant"] = self.proof_variant
            proof = self.fixture.proof_command(frame, issued_at_utc=int(self.clock()))
            self.socket.sendto(self.response_transform(base64.b64decode(proof["payload_b64"])), address)

    def close(self):
        self.stop.set()
        self.worker.join(timeout=1)
        self.socket.close()
        if self.worker.is_alive():
            raise TimeoutError("signed_time_service_shutdown")


class AuthorityService:
    """Purpose-separated signer around current verified TLS/registry state.

    The hosting isolated TLS server must require the GS-168 client CA and TLS
    1.2. authorize_cloud_tls_context verifies that precondition and resolves
    active credentials/current ownership. Ingest rechecks independently.
    """
    def __init__(self, issuer, ownership_db, lock, *, clock=time.time, enabled=False,
                 signer=None):
        if enabled is not True:
            raise ValueError("explicit_test_only_composition_required")
        self.issuer, self.db, self.lock, self.clock = issuer, ownership_db, lock, clock
        self.signer = signer if signer is not None else rsa3072()
        self._seen = set()

    @property
    def public_key_der(self):
        return public_der(self.signer)

    def refresh(self, peer, body: dict) -> bytes:
        now = int(self.clock())
        with self.lock:
            context = authorize_cloud_tls_context(peer, trusted_now=datetime.fromtimestamp(now, timezone.utc),
                time_readiness=TimeReadiness.TRUSTED, credentials=self.issuer, ownership_db=self.db)
            expected = {"protocol", "hub_id", "credential_generation", "certificate_fingerprint_sha256",
                        "boot_generation", "nonce"}
            if (not isinstance(body, dict) or set(body) != expected or body["protocol"] != "GS40T/1"
                    or body["hub_id"] != context.permanent_hub_id
                    or not (
                        (context.permanent_hub_id.startswith("test-hub-") and
                         context.home_id.startswith("gs177-test-")) or
                        (context.permanent_hub_id == _GS117_PHYSICAL_HUB_ID and
                         context.home_id == _GS117_PHYSICAL_HOME_ID)
                    )
                    or body["certificate_fingerprint_sha256"] != context.certificate_fingerprint_sha256
                    or type(body["boot_generation"]) is not int or not 0 < body["boot_generation"] < 2**63
                    or not isinstance(body["nonce"], str) or not re.fullmatch(r"[0-9a-f]{64}", body["nonce"])
                    or not any(bytes.fromhex(body["nonce"]))):
                raise PermissionError("invalid_authority_challenge")
            record = self.issuer.by_fingerprint(context.certificate_fingerprint_sha256)
            if (record is None or type(body["credential_generation"]) is not int
                    or body["credential_generation"] != record.generation):
                raise PermissionError("credential_generation_mismatch")
            challenge = (context.certificate_fingerprint_sha256, body["boot_generation"], body["nonce"])
            if challenge in self._seen or len(self._seen) >= 256:
                raise PermissionError("authority_challenge_replay_or_limit")
            hub, home = context.permanent_hub_id.encode(), context.home_id.encode()
            # Current epoch is also the authority revision. Any transfer changes
            # epoch; credential replacement is independently fingerprint-bound.
            # A signed-time snapshot has whole-second precision and anchors at
            # receipt. Begin validity at the preceding completed second so its
            # quantization cannot turn a current lease into a future statement.
            # This SHORTENS remaining lifetime; target future checks stay exact.
            valid_from = now - 1
            unsigned = (b"G40A\x01" + bytes.fromhex(body["nonce"]) + struct.pack(">QQQQQQB",
                body["boot_generation"], valid_from, valid_from + 60, context.installation_epoch,
                record.generation, context.installation_epoch, 1) +
                bytes.fromhex(context.certificate_fingerprint_sha256) + bytes([len(hub)]) + hub +
                bytes([len(home)]) + home)
            signature = self.signer.sign(b"GS40T/1/AUTHORITY\x00" + unsigned,
                                         padding.PKCS1v15(), hashes.SHA256())
            self._seen.add(challenge)
            return unsigned + signature
