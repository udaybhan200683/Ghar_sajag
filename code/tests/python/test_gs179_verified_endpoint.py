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
import subprocess
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


class EngineeringSnapshotTest(unittest.TestCase):
    def test_controller_identity_and_release_isolation(self):
        """GS179-UNATTENDED-003: task environment cannot hide RC caller."""
        from gs179_verified_endpoint import _verify_engineering_controller
        with tempfile.TemporaryDirectory() as temp:
            proc = Path(temp)
            manifest = dict(controller_pid=42, source='GS117_EXISTING_BOUNDED_ENGINEERING_INGRESS')
            for mode in ('', 'ENGINEERING'):
                (proc/'environ').write_bytes(('GHAR_SAJAG_QUALIFICATION_MODE='+mode).encode())
                _verify_engineering_controller(proc, manifest, 42)
            for mode in ('RC', 'PRODUCTION', 'RELEASE_CANDIDATE', 'RELEASE', 'COMMERCIAL'):
                (proc/'environ').write_bytes(('GHAR_SAJAG_QUALIFICATION_MODE='+mode).encode())
                with self.assertRaisesRegex(ValueError, 'release_controller'):
                    _verify_engineering_controller(proc, manifest, 42)
            with self.assertRaisesRegex(ValueError, 'controller_identity_mismatch'):
                _verify_engineering_controller(proc, manifest, 43)

    def test_protected_snapshots_not_caller_source_execute(self):
        """GS179-UNATTENDED-002: protected copies execute; mutable source does not."""
        import gs179_engineering_validator as v
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / 'protected'; base.mkdir()
            source = Path(temp) / 'source'; source.mkdir()
            names = ('gs179-windows-lan-proxy.ps1', 'gs179_engineering_validator.py',
                     'gs179_verified_endpoint.py', 'gs117_hil_authorization.py')
            hashes = {}
            for name in names:
                data = b"# pinned snapshot\n"
                (base / name).write_bytes(data); (source / name).write_bytes(data)
                hashes[name] = hashlib.sha256(data).hexdigest()
            import json
            manifest = dict(schema='GS179_ENGINEERING_EXECUTOR_V1', sources=hashes)
            (base / 'installation.json').write_text(json.dumps(manifest), encoding='utf-8-sig')
            with patch.object(v, 'ROOT', source):
                # Restore modules after exercising real loader on inert test bytes.
                with patch.dict(sys.modules):
                    v.load_snapshot(base)
                # Ordinary application/authorization source edits do not run
                # from the checkout and do not invalidate the fixed executor.
                marker = source / 'must-not-execute'
                (source / names[3]).write_text(
                    f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n",
                    encoding='utf-8')
                with patch.dict(sys.modules):
                    v.load_snapshot(base)
                self.assertFalse(marker.exists())
                (source / names[3]).unlink()
                (source / names[3]).symlink_to(base / names[3])
                with self.assertRaisesRegex(ValueError, 'reviewed_project_source_changed'):
                    with patch.dict(sys.modules):
                        v.load_snapshot(base)
                (source / names[3]).unlink()
                (source / names[3]).write_bytes(b"# pinned snapshot\n")

                # A change to the canonical privileged GS-179 source still
                # fails closed against the reviewed installation manifest.
                (source / names[2]).write_text('unreviewed')
                with self.assertRaisesRegex(ValueError, 'reviewed_project_source_changed'):
                    with patch.dict(sys.modules):
                        v.load_snapshot(base)
                (source / names[2]).write_bytes((base / names[2]).read_bytes())

                # The installed GS-117 authority snapshot remains immutable
                # and must still match its administrator-owned manifest pin.
                (base / names[3]).write_text('unreviewed')
                with self.assertRaisesRegex(ValueError, 'protected_snapshot_changed'):
                    with patch.dict(sys.modules):
                        v.load_snapshot(base)
                (base / names[3]).write_bytes(b"# pinned snapshot\n")

                # Path substitution in the protected manifest remains denied.
                manifest['sources']['../evil.py'] = 'a' * 64
                (base / 'installation.json').write_text(json.dumps(manifest))
                with self.assertRaisesRegex(ValueError, 'protected_manifest_invalid'):
                    with patch.dict(sys.modules):
                        v.load_snapshot(base)


class VerifiedEndpointTest(unittest.TestCase):
    def test_current_private_address_only(self):
        def runner(*args, **kwargs):
            self.assertEqual(kwargs['timeout'], 30)
            self.assertTrue(kwargs['check'])
            return SimpleNamespace(stdout="192.168.1.8\r\n")
        self.assertEqual(windows_wifi_ipv4("https://desktop-3qqu64b.local", runner=runner),
                         "192.168.1.8")
        for output in ("", "192.168.1.8\n192.168.1.9\n", "8.8.8.8\n", "127.0.0.1\n"):
            with self.subTest(output=output), self.assertRaises(ValueError):
                windows_wifi_ipv4("https://desktop-3qqu64b.local",
                                  runner=lambda *a, **kw: SimpleNamespace(stdout=output))
        with self.assertRaises(ValueError):
            windows_wifi_ipv4("https://untrusted.example",
                              runner=runner)

        def expired(*args, **kwargs):
            raise subprocess.TimeoutExpired('bounded_wifi_query', kwargs['timeout'])
        with self.assertRaises(subprocess.TimeoutExpired):
            windows_wifi_ipv4("https://desktop-3qqu64b.local", runner=expired)

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



class StandingEngineeringAuthorityTest(unittest.TestCase):
    """GS179-ENGINEERING-LAB-001: production authority, mocked registered functional lab only."""
    @contextmanager
    def lab(self):
        import gs179_verified_endpoint as e
        import gs117_hil_authorization as a
        with tempfile.TemporaryDirectory() as temp:
            state=Path(temp);state.chmod(0o700)
            audit=state/'audit.jsonl';audit.touch(mode=0o600)
            clock=[datetime(2026,11,10,tzinfo=timezone.utc)]
            from contextlib import ExitStack
            with ExitStack() as stack:
                for obj,name,value in [(a,'DEV_STATE',state),(a,'DEV_MODE_AUDIT',audit)]:
                    stack.enter_context(patch.object(obj,name,value))
                stack.enter_context(patch.object(a,'_environment_is_release_qualified',return_value=False))
                proof=stack.enter_context(patch.object(e,'engineering_functional_admission',return_value={'image_qualification':'NOT_VERIFIED'}))
                stack.enter_context(patch.object(e,'_network_utc',side_effect=lambda now=None:now or clock[0]))
                yield e,a,state,audit,clock,proof

    def test_standing_survives_days_and_service_restart_without_hardware_entitlement(self):
        with self.lab() as (e,a,state,audit,clock,proof):
            grant=e.record_engineering_network_authorization();sha=grant['sha256']
            original=Path(grant['path']).read_bytes()
            for days in (0,1,5,30):
                clock[0]=datetime(2026,11,10,tzinfo=timezone.utc)+timedelta(days=days)
                r=e.development_network_authority(sha)
                self.assertIsNone(r['expires_at']);self.assertFalse(r['hardware_operations_authorized'])
            with patch.object(e,'_physical_service_identity',return_value={'controller_start':'1','service_pid':10}):
                first=e.issue_development_sublease(sha,123,'services')
                clock[0]+=timedelta(seconds=1800)
                with self.assertRaisesRegex(ValueError,'idle'):
                    e.development_sublease_authority(first['lease_id'],sha,123,'services')
            with patch.object(e,'_physical_service_identity',return_value={'controller_start':'2','service_pid':20}):
                second=e.issue_development_sublease(sha,456,'resumed-services')
                self.assertNotEqual(first['lease_id'],second['lease_id'])
                r=e.development_sublease_authority(second['lease_id'],sha,456,'resumed-services')
                self.assertLessEqual((datetime.fromisoformat(r['lease_deadline'])-clock[0]).total_seconds(),3600)
                with self.assertRaisesRegex(ValueError,'duration_invalid'):
                    e.issue_development_sublease(sha,456,'resumed-services',seconds=3601)
            clock[0]+=timedelta(seconds=3600)
            with self.assertRaisesRegex(ValueError,'expired_or_idle'):
                e.development_sublease_authority(second['lease_id'],sha,456,'resumed-services')
            self.assertEqual(Path(grant['path']).read_bytes(),original)
            with self.assertRaisesRegex(ValueError,'already_enrolled'):
                e.record_engineering_network_authorization()

    def test_revocation_clock_and_release_fail_closed(self):
        with self.lab() as (e,a,state,audit,clock,proof):
            grant=e.record_engineering_network_authorization();sha=grant['sha256']
            clock[0]-=timedelta(seconds=1)
            with self.assertRaisesRegex(ValueError,'clock_invalid'):e.development_network_authority(sha)
            clock[0]+=timedelta(seconds=1)
            with patch.object(a,'_environment_is_release_qualified',return_value=True):
                with self.assertRaisesRegex(ValueError,'release_environment'):e.development_network_authority(sha)
                with self.assertRaisesRegex(ValueError,'release_environment'):e.record_engineering_network_authorization()
            proof.side_effect=ValueError('installed_proof_stale')
            with patch.object(a,'_environment_is_release_qualified',return_value=True):
                e.revoke_development_network_authorization(sha,'owner revocation')
            proof.side_effect=None
            with self.assertRaisesRegex(ValueError,'revoked'):e.development_network_authority(sha)

    def test_functional_fixture_guard_and_fixed_intended_image_identity_required(self):
        with self.lab() as (e,a,state,audit,clock,proof):
            proof.side_effect=ValueError('installed_proof_stale')
            with self.assertRaisesRegex(ValueError,'proof_stale'):e.record_engineering_network_authorization()
            self.assertFalse(e._engineering_network_path().exists())
            proof.side_effect=None
            grant=e.record_engineering_network_authorization()
            proof.side_effect=ValueError('installed_proof_stale')
            with self.assertRaisesRegex(ValueError,'proof_stale'):e.development_network_authority(grant['sha256'])
            proof.side_effect=None
            with patch.object(a,'DEV_IMAGES',{'c3':'production','s3':'production'}):
                with self.assertRaisesRegex(ValueError,'allowlist_changed'):e.development_network_authority(grant['sha256'])

    def test_existing_release_build_guard_rejects_engineering_options_and_root(self):
        import importlib.util
        script=Path(__file__).resolve().parents[2]/'scripts/build_validation_targets.py'
        spec=importlib.util.spec_from_file_location('gs179_profile_guard',script)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        flags=['GS40_TEST_ONLY_CLOUDSYNC','GS_HIL_BUILD','GS_HIL_CONTROL','GS_HIL_COMMISSIONING']
        with tempfile.TemporaryDirectory() as temp:
            build=Path(temp);cache=build/'CMakeCache.txt'
            cache.write_text('\n'.join(f'{name}:BOOL=OFF' for name in flags))
            module.verify_s3_production_profile(build)
            for name in flags:
                cache.write_text(f'{name}:BOOL=ON\n')
                with self.assertRaisesRegex(ValueError,'restricted options'):module.verify_s3_production_profile(build)
            cache.write_text('GS40_TEST_ONLY_CONFIG_ROOT_DER:FILEPATH=/test-root.der\n')
            with self.assertRaisesRegex(ValueError,'trust root'):module.verify_s3_production_profile(build)

    def test_unregistered_laptop_or_owner_cannot_enroll(self):
        with self.lab() as (e,a,state,audit,clock,proof):
            with patch('socket.gethostname',return_value='other-laptop'):
                with self.assertRaisesRegex(ValueError,'owner_or_laptop'):e.record_engineering_network_authorization()
            with patch('os.getuid',return_value=999):
                with self.assertRaisesRegex(ValueError,'owner_or_laptop'):e.record_engineering_network_authorization()
            self.assertFalse(e._engineering_network_path().exists())

    def test_registration_tamper_missing_audit_and_interrupted_publication(self):
        import json
        with self.lab() as (e,a,state,audit,clock,proof):
            with patch.object(e,'_network_event',side_effect=OSError('interrupted')):
                with self.assertRaises(OSError):e.record_engineering_network_authorization()
            path=e._engineering_network_path();sha=a.digest(path)
            with self.assertRaisesRegex(ValueError,'audit_invalid'):e.development_network_authority(sha)
            with self.assertRaises(FileExistsError):e.record_engineering_network_authorization()
        with self.lab() as (e,a,state,audit,clock,proof):
            grant=e.record_engineering_network_authorization();path=Path(grant['path'])
            before=audit.read_bytes();audit.write_text('corrupt audit')
            with self.assertRaises(ValueError):e.development_network_authority(grant['sha256'])
            audit.write_bytes(before)
            r=json.loads(path.read_text());r['identity']['home_id']='wrong';path.write_text(json.dumps(r))
            with self.assertRaisesRegex(ValueError,'registration_mismatch'):e.engineering_network_authority(a.digest(path))
            path.chmod(0o644)
            with self.assertRaisesRegex(ValueError,'not_private'):e.engineering_network_authority(a.digest(path))


class ModeReportingTest(unittest.TestCase):
    """GS179-MODE-REPORT-001: source/artifact evidence cannot attest a running target."""
    def test_reporting_unknown_does_not_operate_or_enroll(self):
        import gs179_verified_endpoint as e
        with patch.object(e,'_network_private_json',side_effect=ValueError('missing fixture')), \
             patch.object(e,'_engineering_build_identity',side_effect=ValueError('missing running proof')), \
             patch.object(e,'record_engineering_network_authorization',side_effect=AssertionError('must not enroll')):
            r=e.operating_mode_status()
        self.assertFalse(r['routine_engineering_authorization_eligible'])
        self.assertFalse(r['profile_identity_verified'])
        self.assertEqual(r['running_images']['c3']['profile'],'UNKNOWN')
        self.assertEqual(r['built_images']['s3']['profile'],'UNKNOWN')

    def test_matching_artifact_and_receipt_never_assert_current_running_mode(self):
        import gs179_verified_endpoint as e
        import gs117_hil_authorization as a
        with tempfile.TemporaryDirectory() as temp:
            binary=Path(temp)/'app.bin';binary.write_bytes(b'engineering artifact')
            expected=hashlib.sha256(binary.read_bytes()).hexdigest()
            fixture=dict(home_id=a.IDENTITY['home_id'],hub_id=a.IDENTITY['s3']['device_id'],
                         physical_device_id=a.IDENTITY['c3']['device_id'])
            for role in ('c3','s3'):fixture[role]=dict(image=str(binary),installed_image_receipt='receipt')
            receipt=dict(running_image_sha256=expected,observed_at='2026-10-31T00:00:00Z',profile='PRODUCTION')
            with patch.object(e,'ENGINEERING_IMAGES',dict(c3=expected,s3=expected)), \
                 patch.object(e,'_network_private_json',side_effect=[fixture,receipt,receipt]), \
                 patch.object(e,'_engineering_build_identity',return_value={}):
                r=e.operating_mode_status()
            self.assertEqual(r['built_images']['c3']['profile'],'ENGINEERING')
            self.assertEqual(r['installed_images']['c3']['profile'],'UNKNOWN')
            self.assertEqual(r['running_images']['s3']['profile'],'UNKNOWN')
            self.assertFalse(r['routine_engineering_authorization_eligible'])

    def test_wrong_home_is_not_verified(self):
        import gs179_verified_endpoint as e
        with patch.object(e,'_network_private_json',return_value={'home_id':'other'}), \
             patch.object(e,'_engineering_build_identity',side_effect=ValueError('mismatch')):
            r=e.operating_mode_status()
        self.assertEqual(r['fixture_reason'],'mode_fixture_identity_mismatch')
        self.assertFalse(r['profile_identity_verified'])

    def test_receipt_state_diagnosis_does_not_repair_missing_or_unsafe_paths(self):
        import gs179_verified_endpoint as e
        import gs117_hil_authorization as a
        with tempfile.TemporaryDirectory() as temp:
            state=Path(temp)/'state'
            with patch.object(a,'READBACK_RECEIPT_STATE',state), \
                 patch.object(e,'_network_private_json',side_effect=ValueError('no fixture')), \
                 patch.object(e,'_engineering_build_identity',side_effect=ValueError('no proof')):
                self.assertEqual(e.operating_mode_status()['receipt_state_check'],'MISSING')
                self.assertFalse(state.exists())
                state.mkdir(mode=0o700)
                self.assertEqual(e.operating_mode_status()['receipt_state_check'],'PRIVATE_DIRECTORY')
                state.chmod(0o755)
                self.assertEqual(e.operating_mode_status()['receipt_state_check'],'PERMISSIONS_TOO_BROAD')
                self.assertEqual(state.stat().st_mode & 0o777,0o755)
                state.rmdir();state.symlink_to(Path(temp),target_is_directory=True)
                self.assertEqual(e.operating_mode_status()['receipt_state_check'],'SYMLINK')

    def test_mode_cli_emits_parseable_report_without_device_arguments(self):
        import subprocess, json
        script=Path(__file__).resolve().parents[2]/'tools/local/gs179_verified_endpoint.py'
        result=subprocess.run([sys.executable,str(script),'--mode-status'],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        prefix,payload=result.stdout.strip().split('=',1)
        self.assertEqual(prefix,'GHAR_SAJAG_MODE_STATUS')
        report=json.loads(payload)
        self.assertEqual(report['schema'],'GS179_MODE_STATUS_V1')
        self.assertEqual(set(report['running_images']),{'c3','s3'})
        self.assertFalse(report['routine_engineering_authorization_eligible'])

    def test_actual_cli_standing_handoff_rejects_invalid_authority_without_issuing(self):
        import subprocess,json
        script=Path(__file__).resolve().parents[2]/'tools/local/gs179_verified_endpoint.py'
        args=[sys.executable,str(script),'--physical-ingress-authority','GS-179#11947',
              '--controller-pid','1','--service-directory','not-a-service',
              '--network-window','DEV','--network-approval-sha256','0'*64,
              '--issue-development-sublease']
        result=subprocess.run(args,capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,2)
        body=json.loads(result.stdout)
        self.assertEqual(body,{'error':'ValueError'})  # Existing CLI deliberately redacts details.

    def test_cli_handoff_accepts_only_matching_standing_or_legacy_authority(self):
        import gs179_verified_endpoint as e
        for ref in ('GS-179#11916','GS-179#11947'):
            with patch.object(e,'development_network_authority',return_value={'approval_ref':ref}), \
                 patch.object(e,'issue_development_sublease',return_value={'lease_id':'new'}) as issue:
                self.assertEqual(e.issue_network_sublease_for_reference(ref,'DEV','hash',1,'dir','prior')['lease_id'],'new')
                issue.assert_called_once()
        with patch.object(e,'development_network_authority',return_value={'approval_ref':'GS-179#11916'}), \
             patch.object(e,'issue_development_sublease') as issue:
            with self.assertRaisesRegex(ValueError,'reference_invalid'):
                e.issue_network_sublease_for_reference('GS-179#11947','DEV','hash',1,'dir','prior')
            issue.assert_not_called()


class EngineeringFunctionalAdmissionTest(unittest.TestCase):
    """GS117-USB-FUNCTIONAL-001: no qualification shortcut, no daily ROM gate."""
    @contextmanager
    def fixture(self):
        import copy
        import gs179_verified_endpoint as e
        import gs117_hil_authorization as a
        with tempfile.TemporaryDirectory() as temp:
            binary=Path(temp)/'engineering.bin';binary.write_bytes(b'known engineering build')
            sha=hashlib.sha256(binary.read_bytes()).hexdigest()
            f=dict(profile='GS179_TEST_ONLY',qualification_profile='GS117_DEV_TEST_ONLY',
                   home_id=a.IDENTITY['home_id'],hub_id=a.IDENTITY['s3']['device_id'],
                   physical_device_id=a.IDENTITY['c3']['device_id'],installation_epoch=1)
            for role in ('c3','s3'):
                f[role]=dict(port=a.IDENTITY[role]['port'],serial_number=a.IDENTITY[role]['serial_number'],
                             image=str(binary),image_sha256=sha)
            f['c3'].update(hil_control=True,hil_build=False,physical_wake=False)
            f['s3']['full_product_composition']=True
            from contextlib import ExitStack
            with ExitStack() as stack:
                stack.enter_context(patch.object(e,'ENGINEERING_IMAGES',dict(c3=sha,s3=sha)))
                stack.enter_context(patch.object(e,'_network_private_json',return_value=f))
                stack.enter_context(patch.object(e,'_engineering_network_path',return_value=Path(temp)/'absent-policy'))
                stack.enter_context(patch.object(a,'_environment_is_release_qualified',return_value=False))
                stack.enter_context(patch('socket.gethostname',return_value=e.ENGINEERING_LAPTOP))
                stack.enter_context(patch('os.getuid',return_value=e.ENGINEERING_OWNER_UID))
                stack.enter_context(patch.object(a,'_verify_scope_a_readback_pass',side_effect=AssertionError('no ROM qualification gate')))
                yield e,a,f

    def test_ordinary_functional_admission_without_readback_or_running_hash_claim(self):
        with self.fixture() as (e,a,f):
            for _ in range(2):
                result=e.engineering_functional_admission(f)
                self.assertEqual(result['running_images'],'UNKNOWN')
                self.assertEqual(result['image_qualification'],'NOT_VERIFIED')

    def test_wrong_home_usb_profile_or_build_fails(self):
        import copy
        with self.fixture() as (e,a,f):
            for mutate in [lambda v:v.update(home_id='wrong'),lambda v:v['c3'].update(port='COM99'),
                           lambda v:v['c3'].update(hil_control=False),lambda v:v['s3'].update(image_sha256='0'*64)]:
                value=copy.deepcopy(f);mutate(value)
                with self.assertRaises(ValueError):e.engineering_functional_admission(value)
            with patch.object(a,'_environment_is_release_qualified',return_value=True):
                with self.assertRaisesRegex(ValueError,'release_environment'):e.engineering_functional_admission(f)

    def test_existing_image_qualification_still_requires_real_audited_capture(self):
        import gs117_hil_authorization as a
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'state_not_private'):
                a._verify_scope_a_readback_pass(Path(temp)/'missing')

    def test_functional_session_is_single_operation_and_preserves_legacy_ledger(self):
        import gs117_hil_authorization as a
        import gs179_verified_endpoint as e
        with tempfile.TemporaryDirectory() as temp:
            state=Path(temp)/'hardware';dev=Path(temp)/'dev'
            state.mkdir(mode=0o700);dev.mkdir(mode=0o700)
            old=state/'historical.json';old.write_text('SAFETY_LATCHED 1/1')
            admission=dict(owner_approval_ref='GS-117#11958',identity=a.IDENTITY)
            with patch.object(a,'STATE',state),patch.object(a,'DEV_STATE',dev), \
                 patch.object(e,'engineering_functional_admission',return_value=admission), \
                 patch.object(e,'_network_event') as audit:
                with a.engineering_functional_session('motion_event_once') as (policy,run):
                    self.assertEqual(policy['profile'],'GS117_ENGINEERING_FUNCTIONAL')
                    run['functional_outcome']='BLOCKED'
                self.assertEqual(audit.call_count,2)
                self.assertEqual(old.read_text(),'SAFETY_LATCHED 1/1')
                with self.assertRaisesRegex(ValueError,'not_allowed'):
                    with a.engineering_functional_session('flash'):pass

if __name__ == "__main__":
    unittest.main()
