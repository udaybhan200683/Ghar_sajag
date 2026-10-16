"""Software-only GS-68/109 mTLS peer-to-Hub authorization seam.

An SSL server must authenticate the client chain before calling this adapter.
No route installs this adapter until production issuer, registry and time
contracts are approved. Factory code can implement CloudCredentialRegistry;
synthetic records must never be used by a commercial deployment.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
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


class TimeReadiness(str, Enum):
    """Explicit server time state used by the TLS and credential boundary."""

    TRUSTED = "TRUSTED"
    UNTRUSTED = "UNTRUSTED"


@dataclass(frozen=True)
class VerifiedHubContext:
    """Typed proof result created only after TLS, credential and ownership checks."""

    permanent_hub_id: str
    home_id: str
    installation_epoch: int
    certificate_fingerprint_sha256: str
    ownership_fingerprint_sha256: str
    certificate_chain_verified: bool
    time_readiness: TimeReadiness

    def internal_event_context(self) -> dict[str, object]:
        if not self.certificate_chain_verified or self.time_readiness is not TimeReadiness.TRUSTED:
            raise CloudClientRejected("verified_hub_context_not_ready")
        return {
            "gs.verified_hub": self.permanent_hub_id,
            "gs.hub_key_fingerprint": self.ownership_fingerprint_sha256,
            "gs.installation_epoch": self.installation_epoch,
            "gs.home_id": self.home_id,
            "gs.time_readiness": self.time_readiness.value,
        }


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
        peer.version() != "TLSv1.2" or not peer.getpeercert()):
        raise CloudClientRejected("verified_tls12_client_required")
    if (not isinstance(trusted_now, datetime) or trusted_now.tzinfo is None):
        raise CloudClientRejected("trusted_time_required")
    der = peer.getpeercert(binary_form=True)
    return _authorize_verified_certificate(der, trusted_now=trusted_now,
                                           credentials=credentials,
                                           ownership_db=ownership_db)


def authorize_cloud_tls_context(peer: ssl.SSLSocket, *, trusted_now: datetime | None,
                                time_readiness: TimeReadiness,
                                credentials: CloudCredentialRegistry,
                                ownership_db: sqlite3.Connection) -> VerifiedHubContext:
    """Return a typed current Hub/Home/epoch capability from verified TLS.

    This requires a trusted server clock and the TLS stack's successful chain
    validation. SNTP hints, request fields and headers cannot supply either.
    Commercial routing remains disabled pending approved provisioning and
    deployment decisions.
    """
    if time_readiness is not TimeReadiness.TRUSTED:
        raise CloudClientRejected("trusted_time_required")
    legacy = authorize_cloud_tls_peer(peer, trusted_now=trusted_now,
                                      credentials=credentials,
                                      ownership_db=ownership_db)
    der = peer.getpeercert(binary_form=True)
    if not der:
        raise CloudClientRejected("client_certificate_required")
    home_id = legacy.get("gs.home_id")
    if not isinstance(home_id, str) or not home_id:
        raise CloudClientRejected("current_home_required")
    return VerifiedHubContext(
        permanent_hub_id=str(legacy["gs.verified_hub"]), home_id=home_id,
        installation_epoch=int(legacy["gs.installation_epoch"]),
        certificate_fingerprint_sha256=hashlib.sha256(der).hexdigest(),
        ownership_fingerprint_sha256=str(legacy["gs.hub_key_fingerprint"]),
        certificate_chain_verified=True, time_readiness=time_readiness,
    )


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
            "gs.installation_epoch": row[2],
            "gs.home_id": row[1]}
