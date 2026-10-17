"""Ephemeral TEST_ONLY RSA-3072 certificates for localhost CloudSync tests."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import os

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


@dataclass(frozen=True)
class TestCertificate:
    pem: bytes
    key_pem: bytes
    der: bytes

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.der).hexdigest()

    def write(self, directory: Path, label: str) -> tuple[Path, Path]:
        cert_path, key_path = directory / (label + ".crt"), directory / (label + ".key")
        for path, data in ((cert_path, self.pem), (key_path, self.key_pem)):
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
        return cert_path, key_path


def make_test_ca(name: str = "Ghar Sajag TEST ONLY CA"):
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=2)).not_valid_after(now + timedelta(days=2))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .sign(key, hashes.SHA256()))
    return key, cert


def issue_test_cert(ca_key, ca_cert, name: str, *, server: bool = False,
                    key_bits: int = 3072, expired: bool = False,
                    not_yet_valid: bool = False,
                    client_purpose: bool = True) -> TestCertificate:
    key = rsa.generate_private_key(public_exponent=65537, key_size=key_bits)
    now = datetime.now(timezone.utc)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    builder = (x509.CertificateBuilder().subject_name(subject).issuer_name(ca_cert.subject)
               .public_key(key.public_key()).serial_number(x509.random_serial_number())
               .not_valid_before(now - timedelta(days=3) if expired else
                                 now + timedelta(days=1) if not_yet_valid else
                                 now - timedelta(hours=1))
               .not_valid_after(now - timedelta(days=1) if expired else
                                now + timedelta(days=2) if not_yet_valid else
                                now + timedelta(days=1))
               .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
               .add_extension(x509.ExtendedKeyUsage([
                   ExtendedKeyUsageOID.SERVER_AUTH if server or not client_purpose
                   else ExtendedKeyUsageOID.CLIENT_AUTH]), critical=True))
    if server:
        builder = builder.add_extension(x509.SubjectAlternativeName([
            x509.DNSName("localhost")]), critical=False)
    cert = builder.sign(ca_key, hashes.SHA256())
    return TestCertificate(cert.public_bytes(serialization.Encoding.PEM),
                           key.private_bytes(serialization.Encoding.PEM,
                                             serialization.PrivateFormat.PKCS8,
                                             serialization.NoEncryption()),
                           cert.public_bytes(serialization.Encoding.DER))
