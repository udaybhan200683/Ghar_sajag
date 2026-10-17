"""GS-168: isolated software-only TEST_ONLY X.509 issuer.

Never import into commercial CloudSync or trust a test certificate as a Hub credential.
This module generates synthetic RSA keys in host memory, not on an ESP32-S3.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import sqlite3
import threading
from typing import Callable

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID, ObjectIdentifier

TEST_ONLY = "TEST_ONLY"
_TEST_MARKER = b"GHAR_SAJAG_GS168_TEST_ONLY_V1"
_TEST_OID = ObjectIdentifier("2.25.271828182845904523536028747135266249775")
_HUB_ID = re.compile(r"test-hub-[a-z0-9][a-z0-9-]{0,31}\Z")


class TestIssuerRejected(ValueError):
    """Test-only policy violation; never expose keys in error messages."""


class TestIssuerUnavailable(RuntimeError):
    """Simulated signing service outage."""


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise TestIssuerRejected("aware_utc_time_required")
    return value.astimezone(timezone.utc)


def _fingerprint(cert: x509.Certificate) -> str:
    return cert.fingerprint(hashes.SHA256()).hex()


def new_test_csr(hub_id: str):
    """Host-only fixture helper: returns (private key, CSR); never log the key."""
    if not isinstance(hub_id, str) or not _HUB_ID.fullmatch(hub_id):
        raise TestIssuerRejected("invalid_test_hub_id")
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"TEST_ONLY:{hub_id}")])
    csr = x509.CertificateSigningRequestBuilder().subject_name(subject).sign(key, hashes.SHA256())
    return key, csr


class TestOnlyAuthority:
    """Ephemeral test CA: private material stays in process memory."""

    def __init__(self, now: datetime | None = None):
        at = _utc(now or datetime.now(timezone.utc))
        self._key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "GHAR_SAJAG_TEST_ONLY_ROOT")])
        self.certificate = (
            x509.CertificateBuilder()
            .subject_name(subject).issuer_name(subject).public_key(self._key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(at - timedelta(minutes=5))
            .not_valid_after(at + timedelta(days=365))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=False, content_commitment=False,
                                         key_encipherment=False, data_encipherment=False,
                                         key_agreement=False, key_cert_sign=True, crl_sign=True,
                                         encipher_only=False, decipher_only=False), critical=True)
            # Keep the private TEST_ONLY marker noncritical so ordinary TLS
            # stacks can validate the chain. The issuer/backend still require
            # the exact marker and active registry mapping.
            .add_extension(x509.UnrecognizedExtension(_TEST_OID, _TEST_MARKER), critical=False)
            .sign(self._key, hashes.SHA256())
        )

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.certificate)

    def public_ca_pem(self) -> bytes:
        return self.certificate.public_bytes(serialization.Encoding.PEM)

    def _sign(self, hub_id: str, public_key, at: datetime, days: int) -> x509.Certificate:
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"TEST_ONLY:{hub_id}")])
        return (
            x509.CertificateBuilder()
            .subject_name(subject).issuer_name(self.certificate.subject)
            .public_key(public_key).serial_number(x509.random_serial_number())
            .not_valid_before(at - timedelta(minutes=1))
            .not_valid_after(at + timedelta(days=days))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                                         key_encipherment=False, data_encipherment=False,
                                         key_agreement=False, key_cert_sign=False, crl_sign=False,
                                         encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
            .add_extension(x509.UnrecognizedExtension(_TEST_OID, _TEST_MARKER), critical=False)
            .sign(self._key, hashes.SHA256())
        )


@dataclass(frozen=True)
class TestCredential:
    hub_id: str
    fingerprint: str
    certificate_pem: bytes  # PUBLIC certificate; never private key.
    state: str
    issuer_fingerprint: str


@dataclass(frozen=True)
class RegisteredCloudCredential:
    """Structural adapter for the existing backend CloudCredentialRegistry."""

    fingerprint_sha256: str
    permanent_hub_id: str
    state: str
    purpose: str = "CLOUD_TLS_CLIENT"
    algorithm: str = "RSA_3072"


class TestOnlyIssuer:
    """GS-168 scoped issuer; SQLite persists public metadata, never key material.

    Reopening a metadata DB requires the same in-memory TestOnlyAuthority.
    Durable CA private-key backup/real provisioning is deliberately NOT implemented.
    """

    def __init__(self, store: str | Path = ":memory:", *,
                 authority: TestOnlyAuthority | None = None,
                 environment: str = TEST_ONLY,
                 clock: Callable[[], datetime] | None = None):
        if environment != TEST_ONLY:
            raise TestIssuerRejected("NOT_READY_SECURITY_APPROVAL")
        self.authority = authority or TestOnlyAuthority()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._available = True
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(store), timeout=3, check_same_thread=False)
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS gs168_meta (
                only_row INTEGER PRIMARY KEY CHECK (only_row=1),
                environment TEXT NOT NULL CHECK (environment='TEST_ONLY'),
                ca_fingerprint TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS gs168_credentials (
                fingerprint TEXT PRIMARY KEY,
                hub_id TEXT NOT NULL,
                serial_hex TEXT NOT NULL UNIQUE,
                certificate_pem BLOB NOT NULL,
                state TEXT NOT NULL CHECK (state IN ('ACTIVE','REVOKED','SUPERSEDED')),
                issued_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS gs168_one_active_hub
                ON gs168_credentials(hub_id) WHERE state='ACTIVE';
        """)
        existing = self._db.execute("SELECT environment,ca_fingerprint FROM gs168_meta WHERE only_row=1").fetchone()
        if existing is None:
            with self._db:
                self._db.execute("INSERT INTO gs168_meta VALUES (1,?,?)", (TEST_ONLY, self.authority.fingerprint))
        elif existing != (TEST_ONLY, self.authority.fingerprint):
            self._db.close()
            raise TestIssuerRejected("test_ca_mismatch_or_production_namespace")

    def close(self):
        self._db.close()

    def set_test_available(self, available: bool):
        """Failure-injection toggle, never a production feature flag."""
        if type(available) is not bool:
            raise TestIssuerRejected("boolean_required")
        with self._lock:
            self._available = available

    def _check_ready(self):
        with self._lock:
            if not self._available:
                raise TestIssuerUnavailable("test_issuer_temporarily_unavailable")

    def _validate_csr(self, hub_id: str, csr: x509.CertificateSigningRequest):
        if not isinstance(hub_id, str) or not _HUB_ID.fullmatch(hub_id):
            raise TestIssuerRejected("invalid_test_hub_id")
        if not isinstance(csr, x509.CertificateSigningRequest) or not csr.is_signature_valid:
            raise TestIssuerRejected("invalid_csr_signature")
        if csr.subject != x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"TEST_ONLY:{hub_id}")]):
            raise TestIssuerRejected("csr_hub_identity_mismatch")
        key = csr.public_key()
        if not isinstance(key, rsa.RSAPublicKey) or key.key_size != 3072:
            raise TestIssuerRejected("test_rsa3072_csr_required")
        return key

    def issue(self, hub_id: str, csr: x509.CertificateSigningRequest, *, renew: bool = False,
              valid_days: int = 30) -> TestCredential:
        self._check_ready()
        key = self._validate_csr(hub_id, csr)
        if type(valid_days) is not int or not 1 <= valid_days <= 90 or type(renew) is not bool:
            raise TestIssuerRejected("invalid_test_issuance_policy")
        at = _utc(self.clock())
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                prior = self._db.execute("SELECT fingerprint FROM gs168_credentials WHERE hub_id=? AND state='ACTIVE'", (hub_id,)).fetchone()
                any_old = self._db.execute("SELECT 1 FROM gs168_credentials WHERE hub_id=? LIMIT 1", (hub_id,)).fetchone()
                if renew and prior is None:
                    raise TestIssuerRejected("active_credential_required_for_renewal")
                if not renew and any_old is not None:
                    raise TestIssuerRejected("test_hub_id_already_issued")
                cert = self.authority._sign(hub_id, key, at, valid_days)
                fingerprint = _fingerprint(cert)
                if renew:
                    self._db.execute("UPDATE gs168_credentials SET state='SUPERSEDED' WHERE fingerprint=?", (prior[0],))
                pem = cert.public_bytes(serialization.Encoding.PEM)
                self._db.execute(
                    "INSERT INTO gs168_credentials VALUES (?,?,?,?,?,?)",
                    (fingerprint, hub_id, format(cert.serial_number, "x"), pem, "ACTIVE", at.isoformat()),
                )
                self._db.commit()
            except Exception:
                self._db.rollback()
                raise
        return TestCredential(hub_id, fingerprint, pem, "ACTIVE", self.authority.fingerprint)

    def verify(self, pem: bytes, expected_hub_id: str, *, at: datetime | None = None,
               expected_csr: x509.CertificateSigningRequest | None = None) -> TestCredential:
        self._check_ready()
        now = _utc(at or self.clock())
        if not isinstance(pem, bytes) or len(pem) > 8192:
            raise TestIssuerRejected("invalid_certificate_input")
        if not isinstance(expected_hub_id, str) or not _HUB_ID.fullmatch(expected_hub_id):
            raise TestIssuerRejected("invalid_test_hub_id")
        try:
            cert = x509.load_pem_x509_certificate(pem)
            if cert.issuer != self.authority.certificate.subject:
                raise TestIssuerRejected("test_certificate_wrong_issuer")
            self.authority.certificate.public_key().verify(
                cert.signature, cert.tbs_certificate_bytes,
                padding.PKCS1v15(), cert.signature_hash_algorithm)
            marker = cert.extensions.get_extension_for_oid(_TEST_OID)
            if marker.value.value != _TEST_MARKER:
                raise TestIssuerRejected("test_only_marker_required")
            if cert.subject != x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"TEST_ONLY:{expected_hub_id}")]):
                raise TestIssuerRejected("certificate_hub_identity_mismatch")
            if not isinstance(cert.public_key(), rsa.RSAPublicKey) or cert.public_key().key_size != 3072:
                raise TestIssuerRejected("test_rsa3072_certificate_required")
            if not cert.not_valid_before_utc <= now <= cert.not_valid_after_utc:
                raise TestIssuerRejected("test_certificate_expired_or_not_yet_valid")
            if ExtendedKeyUsageOID.CLIENT_AUTH not in cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value:
                raise TestIssuerRejected("client_auth_required")
            if cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca:
                raise TestIssuerRejected("leaf_certificate_required")
            if expected_csr is not None:
                key = self._validate_csr(expected_hub_id, expected_csr)
                if key.public_numbers() != cert.public_key().public_numbers():
                    raise TestIssuerRejected("csr_certificate_public_key_mismatch")
        except (ValueError, TypeError, x509.ExtensionNotFound, x509.InvalidVersion) as exc:
            if isinstance(exc, TestIssuerRejected):
                raise
            raise TestIssuerRejected("invalid_test_certificate") from exc
        except Exception as exc:
            if isinstance(exc, TestIssuerRejected):
                raise
            raise TestIssuerRejected("test_certificate_signature_invalid") from exc
        fingerprint = _fingerprint(cert)
        with self._lock:
            row = self._db.execute("SELECT hub_id,state,certificate_pem FROM gs168_credentials WHERE fingerprint=?", (fingerprint,)).fetchone()
        if row is None or row[0] != expected_hub_id or row[1] != "ACTIVE" or row[2] != pem:
            raise TestIssuerRejected("unknown_revoked_or_superseded_test_certificate")
        return TestCredential(expected_hub_id, fingerprint, pem, "ACTIVE", self.authority.fingerprint)

    def revoke(self, fingerprint: str) -> bool:
        self._check_ready()
        if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
            raise TestIssuerRejected("invalid_test_fingerprint")
        with self._lock, self._db:
            row = self._db.execute("UPDATE gs168_credentials SET state='REVOKED' WHERE fingerprint=? AND state='ACTIVE'", (fingerprint,))
        return row.rowcount == 1

    def by_fingerprint(self, fingerprint_sha256: str) -> RegisteredCloudCredential | None:
        """Expose public registry metadata through CloudCredentialRegistry."""
        self._check_ready()
        if not isinstance(fingerprint_sha256, str) or not re.fullmatch(
                r"[0-9a-f]{64}", fingerprint_sha256):
            raise TestIssuerRejected("invalid_test_fingerprint")
        with self._lock:
            row = self._db.execute(
                "SELECT hub_id,state FROM gs168_credentials WHERE fingerprint=?",
                (fingerprint_sha256,),
            ).fetchone()
        if row is None:
            return None
        return RegisteredCloudCredential(fingerprint_sha256, row[0], row[1])

    def public_inventory(self) -> list[dict]:
        """Metadata export excludes PEM, CSRs, all private keys and ownership claims."""
        with self._lock:
            rows = self._db.execute("SELECT hub_id,fingerprint,state FROM gs168_credentials ORDER BY hub_id,fingerprint").fetchall()
        return [{"environment": TEST_ONLY, "hub_id": hub_id, "fingerprint": fp,
                 "state": state} for hub_id, fp, state in rows]
