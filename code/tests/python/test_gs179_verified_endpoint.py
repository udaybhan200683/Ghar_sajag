"""GS-179 Windows route selection preserves the original TLS hostname."""
from __future__ import annotations

import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import ipaddress
from pathlib import Path
import socketserver
import ssl
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "local"))
from gs179_verified_endpoint import (
    VerifiedAddressHTTPSConnection,
    windows_wifi_ipv4,
    wsl_ipv4,
    wsl_local_backend_origin,
    verify_caregiver_origin_alias,
)


class VerifiedEndpointTest(unittest.TestCase):
    def test_current_private_address_only(self):
        runner = lambda *a, **kw: SimpleNamespace(stdout="192.168.1.8\r\n")
        self.assertEqual(windows_wifi_ipv4("https://desktop-3qqu64b.local", runner=runner),
                         "192.168.1.8")
        for output in ("", "192.168.1.8\n192.168.1.9\n", "8.8.8.8\n", "127.0.0.1\n"):
            with self.subTest(output=output), self.assertRaises(ValueError):
                windows_wifi_ipv4("https://desktop-3qqu64b.local",
                                  runner=lambda *a, **kw: SimpleNamespace(stdout=output))
        with self.assertRaises(ValueError):
            windows_wifi_ipv4("https://untrusted.example",
                              runner=runner)

    def test_route_keeps_sni_hostname(self):
        context = __import__("ssl").create_default_context()
        connection = VerifiedAddressHTTPSConnection(
            "desktop-3qqu64b.local", route_ipv4="192.168.1.8", context=context)
        raw = object()
        tls = object()
        with patch("gs179_verified_endpoint.socket.create_connection", return_value=raw) as create:
            with patch.object(context, "wrap_socket", return_value=tls) as wrap:
                connection.connect()
        create.assert_called_once_with(("192.168.1.8", 443), connection.timeout)
        wrap.assert_called_once_with(raw, server_hostname="desktop-3qqu64b.local")

    def test_wsl_local_route_is_dynamic_and_private(self):
        runner = lambda *a, **kw: SimpleNamespace(
            stdout="2: eth0 inet 172.17.152.10/20 brd 172.17.159.255 scope global eth0\n")
        self.assertEqual(wsl_ipv4(runner=runner), "172.17.152.10")
        for output in ("", "2: eth0 inet 172.17.1.2/20 eth0\n3: eth0 inet 172.17.1.3/20 eth0\n",
                       "2: eth0 inet 8.8.8.8/24 scope global eth0\n"):
            with self.subTest(output=output), self.assertRaises(ValueError):
                wsl_ipv4(runner=lambda *a, **kw: SimpleNamespace(stdout=output))

    def test_local_listener_route_preserves_original_https_hostname(self):
        self.assertEqual(
            wsl_local_backend_origin("https://desktop-3qqu64b.local", 8444),
            "https://desktop-3qqu64b.local:8444",
        )
        for origin in ("http://desktop-3qqu64b.local", "https://example.com",
                       "https://desktop-3qqu64b.local:9443"):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                wsl_local_backend_origin(origin, 8444)
        with self.assertRaises(ValueError):
            wsl_local_backend_origin("https://desktop-3qqu64b.local", 70000)


class CaregiverOriginAliasTlsTest(unittest.TestCase):
    """GS117-ORIGIN-ALIAS-001: real TLS identity checks, no hardware access."""
    @classmethod
    def setUpClass(cls):
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        now = datetime.now(timezone.utc)
        ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "GS117 isolated test CA")])
        ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
              .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
              .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(days=1))
              .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
              .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
              .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                  key_encipherment=False, data_encipherment=False, key_agreement=False,
                  key_cert_sign=True, crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
              .sign(ca_key, hashes.SHA256()))
        cls.ca = cls.root / "ca.pem"
        cls.ca.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
        cls.leaves = {}
        for name, include_ip in (("installed", True), ("other", True), ("dns_only", False)):
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            sans = [x509.DNSName("laptop.local")]
            if include_ip:
                sans.append(x509.IPAddress(ipaddress.IPv4Address("192.168.1.10")))
            cert = (x509.CertificateBuilder().subject_name(x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, "laptop.local")]))
                .issuer_name(ca_name).public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(days=1))
                .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
                .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
                .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                    key_encipherment=True, data_encipherment=False, key_agreement=False,
                    key_cert_sign=False, crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
                .add_extension(x509.SubjectAlternativeName(sans), critical=False)
                .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
                .sign(ca_key, hashes.SHA256()))
            cert_path, key_path = cls.root / (name + ".pem"), cls.root / (name + ".key")
            cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
            cls.leaves[name] = (cert_path, key_path)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @contextmanager
    def endpoint(self, leaf="installed"):
        cert, key = self.leaves[leaf]
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)
        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                try: self.request.recv(1)
                except OSError: pass
        class Server(socketserver.ThreadingTCPServer):
            daemon_threads = True
            def get_request(self):
                raw, address = super().get_request()
                try: return context.wrap_socket(raw, server_side=True), address
                except BaseException:
                    raw.close()
                    raise
        server = Server(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
        thread.start()
        hosts = []
        def factory(host, *, route_ipv4, context, timeout):
            self.assertEqual(route_ipv4, "192.168.1.10")
            self.assertTrue(context.check_hostname)
            self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
            hosts.append(host)
            return VerifiedAddressHTTPSConnection(host, port=server.server_address[1],
                route_ipv4="127.0.0.1", context=context, timeout=timeout)
        try: yield factory, hosts
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)

    def verify(self, factory, *, ca=None, installed=None):
        return verify_caregiver_origin_alias("https://laptop.local", "https://192.168.1.10/",
            ca or self.ca, installed or self.leaves["installed"][0],
            wifi_address_reader=lambda _origin: "192.168.1.10", connection_factory=factory)

    def test_actual_dns_and_ip_tls_names_match_same_installed_leaf(self):
        with self.endpoint() as (factory, hosts):
            proof = self.verify(factory)
        self.assertEqual(hosts, ["laptop.local", "192.168.1.10"])
        self.assertEqual(proof["apk_origin"], "https://192.168.1.10")
        der = ssl.PEM_cert_to_DER_cert(self.leaves["installed"][0].read_text())
        self.assertEqual(proof["server_cert_sha256"], hashlib.sha256(der).hexdigest())

    def test_trusted_but_different_leaf_is_not_the_installed_backend(self):
        with self.endpoint("other") as (factory, _hosts):
            with self.assertRaisesRegex(ValueError, "installed_server_certificate_mismatch"):
                self.verify(factory)

    def test_ip_san_and_ca_validation_remain_mandatory(self):
        with self.endpoint("dns_only") as (factory, _hosts):
            with self.assertRaises(ssl.SSLCertVerificationError):
                self.verify(factory, installed=self.leaves["dns_only"][0])
        with self.endpoint() as (factory, _hosts):
            with self.assertRaises(ssl.SSLCertVerificationError):
                self.verify(factory, ca=self.leaves["other"][0])

    def test_wrong_route_public_address_or_url_is_rejected_before_tls(self):
        for origin in ("https://192.168.1.11", "https://8.8.8.8", "https://127.0.0.1",
                       "https://169.254.1.1", "https://other.local", "http://192.168.1.10",
                       "https://192.168.1.10:8445", "https://user:pw@192.168.1.10",
                       "https://192.168.1.10/path", "https://192.168.1.10?q=1"):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                verify_caregiver_origin_alias("https://laptop.local", origin,
                    self.ca, self.leaves["installed"][0],
                    wifi_address_reader=lambda _origin: "192.168.1.10",
                    connection_factory=lambda *_a, **_kw: self.fail("TLS must not start"))


if __name__ == "__main__":
    unittest.main()
