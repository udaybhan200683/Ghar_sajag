"""Software-only GS-68/109 mTLS peer-to-Hub authorization seam.

An SSL server must authenticate the client chain before calling this adapter.
No route installs this adapter until production issuer, registry and time
contracts are approved. Factory code can implement CloudCredentialRegistry;
synthetic records must never be used by a commercial deployment.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import re
import sqlite3
import ssl
from typing import Protocol

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID


_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")


class CloudClientRejected(PermissionError):
    """Peer cannot be promoted to a permanent Hub identity."""


@dataclass(frozen=True)
class CloudCredentialRecord:
    fingerprint_sha256: str
    permanent_hub_id: str
    state: str
    purpose: str = "CLOUD_TLS_CLIENT"
    algorithm: str = "RSA_3072"


class CloudCredentialRegistry(Protocol):
    """Future GS-165/172 issuer/registry adapter; no provisioning here."""

    def by_fingerprint(self, fingerprint_sha256: str) -> CloudCredentialRecord | None: ...


def authorize_cloud_tls_peer(peer: ssl.SSLSocket, *, trusted_now: datetime | None,
                             credentials: CloudCredentialRegistry,
                             ownership_db: sqlite3.Connection) -> dict:
    """Resolve a verified TLS peer against current backend ownership state.

    The returned context is accepted by the existing durable transaction guard.
    The transaction rechecks current Home/epoch/Node generation before COMMITTED.
    No caller-supplied Home, QR, serial or HTTP header participates in identity.
    """
    if (not isinstance(peer, ssl.SSLSocket) or not peer.server_side or
        peer.context.verify_mode != ssl.CERT_REQUIRED or not peer.cipher() or
        peer.version() != "TLSv1.2"):
        raise CloudClientRejected("verified_tls12_client_required")
    if (not isinstance(trusted_now, datetime) or trusted_now.tzinfo is None):
        raise CloudClientRejected("trusted_time_required")
    der = peer.getpeercert(binary_form=True)
    return _authorize_verified_certificate(der, trusted_now=trusted_now,
                                           credentials=credentials,
                                           ownership_db=ownership_db)


def _authorize_verified_certificate(der: bytes | None, *, trusted_now: datetime | None,
                                    credentials: CloudCredentialRegistry,
                                    ownership_db: sqlite3.Connection) -> dict:
    """Parse/match a certificate already chain-verified by the TLS boundary."""
    if not isinstance(trusted_now, datetime) or trusted_now.tzinfo is None:
        raise CloudClientRejected("trusted_time_required")
    if not der or len(der) > 8192:
        raise CloudClientRejected("client_certificate_required")
    try:
        cert = x509.load_der_x509_certificate(der)
        key = cert.public_key()
        eku = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        if (not isinstance(key, rsa.RSAPublicKey) or key.key_size != 3072 or
            ExtendedKeyUsageOID.CLIENT_AUTH not in eku):
            raise CloudClientRejected("dedicated_rsa3072_client_identity_required")
        now = trusted_now.astimezone(timezone.utc)
        if not cert.not_valid_before_utc <= now <= cert.not_valid_after_utc:
            raise CloudClientRejected("client_certificate_not_current")
    except (ValueError, x509.ExtensionNotFound) as error:
        raise CloudClientRejected("invalid_client_certificate") from error
    fingerprint = hashlib.sha256(der).hexdigest()
    record = credentials.by_fingerprint(fingerprint)
    if (record is None or record.fingerprint_sha256 != fingerprint or
        _FINGERPRINT.fullmatch(fingerprint) is None or record.state != "ACTIVE" or
        record.purpose != "CLOUD_TLS_CLIENT" or record.algorithm != "RSA_3072" or
        not record.permanent_hub_id):
        raise CloudClientRejected("unknown_revoked_or_wrong_purpose_credential")
    row = ownership_db.execute(
        """SELECT identity_key_fingerprint,home_id,installation_epoch
           FROM hub_ownership_registry WHERE hub_device_id=? AND state='ACTIVE'""",
        (record.permanent_hub_id,),
    ).fetchone()
    if (row is None or not row[1] or type(row[2]) is not int or row[2] <= 0 or
        _FINGERPRINT.fullmatch(row[0]) is None):
        raise CloudClientRejected("current_hub_ownership_required")
    return {"gs.verified_hub": record.permanent_hub_id,
            "gs.hub_key_fingerprint": row[0],
            "gs.installation_epoch": row[2]}
