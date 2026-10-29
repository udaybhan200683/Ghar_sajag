"""Focused failure-closed PostgreSQL boundary tests for GS-179 TEST_ONLY."""
import os
from io import BytesIO
import json
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest
import psycopg

from ghar_sajag.cloud_client_identity import TimeReadiness, VerifiedHubContext
from ghar_sajag.configuration_repository import (
    ConfigurationConflict, PostgresConfigurationRepository,
)
from ghar_sajag.diagnostic_authorization import ActorSession
from ghar_sajag.human_authentication import (
    CurrentSession, HumanAuthenticationBoundary, IssuerPolicy, VerifiedAssertion,
)
from ghar_sajag.http_api import JsonApi
from ghar_sajag.postgres_database import connect_postgres, initialize_postgres
from gs179_postgres_test_db import IsolatedPostgresSchema, local_verified_postgres_url

CODE_ROOT = Path(__file__).resolve().parents[2]
LAPTOP_SERVER = CODE_ROOT / "tools" / "local" / "gs179-laptop-server.sh"
WINDOWS_PROXY = CODE_ROOT / "tools" / "local" / "gs179-windows-lan-proxy.ps1"


class MorningRoutineConfigurationPostgres(unittest.TestCase):
    """Exercise desired/applied policy on real PG in the existing isolated schema."""

    @classmethod
    def setUpClass(cls):
        base_dsn = os.environ.get("GS179_TEST_POSTGRES_DSN")
        if not base_dsn:
            raise RuntimeError("GS179_TEST_POSTGRES_DSN_required_for_isolated_config_test")
        cls.isolated = IsolatedPostgresSchema(base_dsn)
        try:
            cls.db = connect_postgres(cls.isolated.dsn, allow_local_unencrypted=True)
            initialize_postgres(cls.db)
        except BaseException:
            cls.isolated.close()
            raise

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "db"):
            cls.db.close()
        if hasattr(cls, "isolated"):
            cls.isolated.close()

    def test_bedroom_only_policy_persists_and_requires_exact_hub_apply_ack(self):
        suffix = os.urandom(8).hex()
        home_id = "gs117-bedroom-only-" + suffix
        hub_id = "gs117-test-hub-" + suffix
        ownership_fingerprint = "a" * 64
        self.db.execute(
            "INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) "
            "VALUES(?,?,?,?,?)",
            (home_id, "GS-117 isolated Morning Routine", "Etc/UTC", 1, 1),
        )
        self.db.execute(
            """INSERT INTO hub_ownership_registry
               (hub_device_id,identity_key_fingerprint,state,home_id,installation_epoch,created_at,updated_at)
               VALUES(?,?,'ACTIVE',?,1,1,1)""",
            (hub_id, ownership_fingerprint, home_id),
        )
        actor = ActorSession("test-owner-" + suffix, "test-session-" + suffix,
                             "approved-test-adapter", 1000)
        hub = VerifiedHubContext(
            hub_id, home_id, 1, "b" * 64, ownership_fingerprint, True,
            TimeReadiness.TRUSTED,
        )
        policy = {
            "morning": {"enabled": True, "start_minute": 420,
                        "end_minute": 600, "grace_minutes": 30},
            "activity_rules": {
                "quiet_hours_enabled": True, "quiet_start_minute": 60,
                "quiet_end_minute": 300, "door_open_timeout_seconds": 300,
                "daytime_inactivity_enabled": True, "daytime_start_minute": 480,
                "daytime_end_minute": 1260, "daytime_inactivity_seconds": 10800,
                "morning_steps": [
                    {"location": "bedroom", "enabled": True, "required": True},
                ],
            },
        }
        repository = PostgresConfigurationRepository(
            self.db,
            authorize_caregiver_settings=lambda _actor, _home, at: at < _actor.expires_at,
            authorize_hub_configuration=lambda context, home, _at: (
                context.permanent_hub_id == hub_id and context.home_id == home),
        )
        self.assertTrue(self.db.durable_commit_ready)

        desired = repository.publish_desired(
            actor=actor, home_id=home_id, config=policy, expected_version=0, at=10)
        self.assertEqual((desired.desired_version, desired.desired_status), (1, "DESIRED"))
        self.assertIsNone(desired.applied_version)
        fetched = repository.get_for_hub(context=hub, home_id=home_id, at=11)
        self.assertEqual(fetched.desired_config, policy)
        self.assertIsNone(fetched.applied_config)

        applied = repository.record_applied(context=hub, home_id=home_id,
                                            version=desired.desired_version, at=12)
        self.assertEqual(applied.applied_version, 1)
        self.assertEqual(applied.applied_config["activity_rules"]["morning_steps"],
                         [{"location": "bedroom", "enabled": True, "required": True}])
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM configurations WHERE home_id=?", (home_id,)
        ).fetchone()[0], 1)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM audit_log WHERE home_id=?", (home_id,)
        ).fetchone()[0], 2)
        with self.assertRaisesRegex(ConfigurationConflict, "stale_desired"):
            repository.publish_desired(actor=actor, home_id=home_id, config=policy,
                                       expected_version=0, at=13)

    def test_authorized_settings_to_hub_fetch_and_applied_status_api_on_isolated_postgres(self):
        suffix = os.urandom(8).hex()
        home_id = "gs117-config-api-" + suffix
        hub_id = "gs117-config-hub-" + suffix
        owner_id = "gs117-config-owner-" + suffix
        session_id = "gs117-config-session-" + suffix
        fingerprint = "c" * 64
        self.db.execute(
            "INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) "
            "VALUES(?,?,?,?,?)", (home_id, "Isolated config API", "Etc/UTC", 1, 1))
        self.db.execute(
            """INSERT INTO hub_ownership_registry
               (hub_device_id,identity_key_fingerprint,state,home_id,installation_epoch,created_at,updated_at)
               VALUES(?,?,'ACTIVE',?,3,1,1)""", (hub_id, fingerprint, home_id))
        actor = ActorSession(owner_id, session_id, "fixture-issuer-reference", 200)
        hub = VerifiedHubContext(hub_id, home_id, 3, "d" * 64, fingerprint, True,
                                 TimeReadiness.TRUSTED)
        policy = {
            "morning": {"enabled": True, "start_minute": 420,
                        "end_minute": 600, "grace_minutes": 30},
            "activity_rules": {
                "quiet_hours_enabled": True, "quiet_start_minute": 60,
                "quiet_end_minute": 300, "door_open_timeout_seconds": 300,
                "daytime_inactivity_enabled": True, "daytime_start_minute": 480,
                "daytime_end_minute": 1260, "daytime_inactivity_seconds": 10800,
                "morning_steps": [{"location": "bedroom", "enabled": True, "required": True}],
            },
        }

        class Verifier:
            def verify(self, credential):
                if credential != "fixture-credential":
                    return None
                return VerifiedAssertion("https://fixture.invalid", owner_id,
                    ("ghar-sajag-api",), session_id, "access", 90, 90, 200)

        class Directory:
            def current(self, issuer, subject, session):
                if (issuer, subject, session) != (
                        "https://fixture.invalid", owner_id, session_id):
                    return None
                return CurrentSession(issuer, subject, session, owner_id, True, True)

        boundary = HumanAuthenticationBoundary(
            IssuerPolicy("https://fixture.invalid", "ghar-sajag-api", "access"),
            Verifier(), Directory(), lambda: 100)
        repository = PostgresConfigurationRepository(
            self.db,
            authorize_caregiver_settings=lambda current, requested_home, at:
                current.actor_id == owner_id and requested_home == home_id and at < current.expires_at,
            authorize_hub_configuration=lambda context, requested_home, _at:
                context.permanent_hub_id == hub_id and requested_home == home_id)
        api = JsonApi(now=lambda: 100, configuration_repository=repository,
            human_authentication=boundary,
            caregiver_credential_from_request=lambda env: env.get("HTTP_AUTHORIZATION"),
            verified_hub_context_from_request=lambda env: env.get("gs.fixture_hub"))

        def request(method, path, body=None, **server_context):
            raw = b"" if body is None else json.dumps(body).encode()
            statuses = []
            response = b"".join(api({"REQUEST_METHOD": method, "PATH_INFO": path,
                "CONTENT_LENGTH": str(len(raw)), "wsgi.input": BytesIO(raw), **server_context},
                lambda status, _headers: statuses.append(status)))
            return int(statuses[0][:3]), json.loads(response)

        path = f"/v1/homes/{home_id}/config"
        status, desired = request("POST", path,
            {"expected_version": 0, "config": policy},
            HTTP_AUTHORIZATION="fixture-credential", HTTP_X_ACTOR_ID="wrong-actor")
        self.assertEqual((status, desired["desired_version"], desired["applied_version"]),
                         (202, 1, None))
        status, fetched = request("GET", f"{path}/desired", **{"gs.fixture_hub": hub})
        self.assertEqual((status, fetched["version"], fetched["config"]), (200, 1, policy))
        status, applied = request("POST", f"{path}/applied", {"version": 1},
                                  **{"gs.fixture_hub": hub})
        self.assertEqual((status, applied["desired_version"], applied["applied_version"]),
                         (200, 1, 1))
        status, caregiver = request("GET", path, HTTP_AUTHORIZATION="fixture-credential")
        self.assertEqual((status, caregiver["desired_status"], caregiver["applied_config"]),
                         (200, "APPLIED", policy))
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM configurations WHERE home_id=?", (home_id,)
        ).fetchone()[0], 1)


class PostgresSecurityBoundary(unittest.TestCase):
    def test_remote_database_requires_hostname_verified_tls(self):
        for dsn in (
            "host=db.example.invalid dbname=ghar user=hub sslmode=require",
            "host=db.example.invalid dbname=ghar user=hub sslmode=prefer",
        ):
            with self.subTest(dsn=dsn), self.assertRaisesRegex(
                    ValueError, "remote_postgres_requires_sslmode_verify_full"):
                connect_postgres(dsn)

    def test_local_plaintext_requires_explicit_test_mode(self):
        dsn = "host=/tmp/no-postgres-here dbname=ghar user=hub"
        with self.assertRaisesRegex(ValueError, "local_postgres_requires_explicit_test_mode_or_tls"):
            connect_postgres(dsn)

    def test_local_test_override_does_not_allow_remote_unverified_tls(self):
        dsn = "host=db.example.invalid dbname=ghar user=hub sslmode=require"
        with self.assertRaisesRegex(ValueError, "remote_postgres_requires_sslmode_verify_full"):
            connect_postgres(dsn, allow_local_unencrypted=True)

    def test_migration_fails_before_queries_without_durable_server_settings(self):
        class UnsafeDatabase:
            dialect = "postgres"
            durable_commit_ready = False
            in_transaction = False

            def execute(self, *_args, **_kwargs):
                raise AssertionError("migration must reject before executing SQL")

        with self.assertRaisesRegex(ValueError, "postgres_durable_settings_required"):
            initialize_postgres(UnsafeDatabase())

    def test_isolated_schema_refuses_nonlocal_database_before_connecting(self):
        with self.assertRaisesRegex(ValueError, "accepts local database hosts only"):
            IsolatedPostgresSchema("host=database.example.invalid dbname=ghar user=hub")

    def test_persistent_local_server_dsn_requires_local_hostname_verified_tls(self):
        with self.assertRaisesRegex(ValueError, "loopback hosts only"):
            local_verified_postgres_url(
                "host=database.example.invalid dbname=ghar user=hub sslmode=verify-full"
            )
        with self.assertRaisesRegex(ValueError, "requires hostname-verified TLS"):
            local_verified_postgres_url("host=127.0.0.1 dbname=ghar user=hub sslmode=require")
        url = local_verified_postgres_url(
            "host=127.0.0.1 port=55432 dbname=gs179_monitoring user=gs179_app "
            "password=private sslmode=verify-full sslrootcert=/private/pg-ca.pem"
        )
        self.assertTrue(url.startswith("postgresql://gs179_app:private@127.0.0.1:55432/"))
        self.assertIn("sslmode=verify-full", url)

    def test_postgres_adapter_preserves_tls_query_when_adding_connect_timeout(self):
        dsn = ("postgresql://gs179_app:private@127.0.0.1:1/gs179_monitoring"
               "?sslmode=verify-full&sslrootcert=%2Fprivate%2Fpostgres-ca.pem")
        with self.assertRaises(psycopg.OperationalError):
            connect_postgres(dsn)


class LaptopServiceLifecycleBoundary(unittest.TestCase):
    """Exercise generated lifecycle commands only in a throwaway HOME."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gs179-laptop-lifecycle-")
        self.home = Path(self.temp.name)
        self.bin = self.home / "bin"
        self.bin.mkdir()
        self.pg_data = self.home / ".local/share/ghar-sajag/gs179-laptop/postgres"
        self.pg_root = self.home / ".local/share/ghar-sajag/gs179-laptop/postgres-root"
        self.pg_bin = self.pg_root / "usr/lib/postgresql/18/bin"
        self.pg_bin.mkdir(parents=True)
        self.pg_data.mkdir(parents=True)
        self.pg_log = self.home / "pgctl.log"
        self.gunicorn_log = self.home / "gunicorn.log"
        self.systemctl_log = self.home / "systemctl.log"
        self.pg_state = self.home / "pg-running"
        self._write_executable(self.pg_bin / "pg_ctl", """
            #!/usr/bin/env bash
            printf '%s\\n' "$*" >> "$FAKE_PG_LOG"
            case " $* " in
              *" status "*) test -f "$FAKE_PG_STATE"; exit $? ;;
              *" start "*) touch "$FAKE_PG_STATE"; exit 0 ;;
              *" stop "*) rm -f "$FAKE_PG_STATE"; exit 0 ;;
            esac
            exit 0
        """)
        self._write_executable(self.bin / "systemctl", """
            #!/usr/bin/env bash
            printf '%s\\n' "$*" >> "$FAKE_SYSTEMCTL_LOG"
        """)
        self._write_executable(self.bin / "python3", """
            #!/usr/bin/env bash
            if [[ "${1:-}" == "-" ]]; then cat >/dev/null; exit 0; fi
            printf '%s\\n' "$*" >> "$FAKE_GUNICORN_LOG"
            exit 0
        """)
        self._write_executable(self.bin / "ip", """
            #!/usr/bin/env bash
            printf '2: eth0 inet 172.17.152.10/20 brd 172.17.159.255 scope global eth0\\n'
        """)
        self.env = os.environ.copy()
        self.env.update({
            "HOME": str(self.home),
            "PATH": str(self.bin) + os.pathsep + os.environ.get("PATH", ""),
            "FAKE_PG_LOG": str(self.pg_log),
            "FAKE_PG_STATE": str(self.pg_state),
            "FAKE_GUNICORN_LOG": str(self.gunicorn_log),
            "FAKE_SYSTEMCTL_LOG": str(self.systemctl_log),
        })

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def _write_executable(path: Path, body: str):
        path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
        path.chmod(0o700)

    def _run_script(self, command: str, *arguments: str, extra_env=None):
        env = self.env.copy()
        env.update(extra_env or {})
        return subprocess.run(
            ["bash", str(LAPTOP_SERVER), command, *arguments], env=env,
            text=True, capture_output=True, timeout=15, check=False)

    def _write_private_server_env(self):
        config = self.home / ".config/ghar-sajag/gs179-laptop/server.env"
        config.parent.mkdir(parents=True)
        config.write_text(textwrap.dedent("""
            export DATABASE_URL='postgresql://gs179_app@127.0.0.1:55432/gs179_monitoring'
            export GS179_LOCAL_SERVER_DSN='postgresql://gs179_app@127.0.0.1:55432/gs179_monitoring'
            export PUBLIC_ORIGIN='https://192.168.1.6'
            export GS179_WINDOWS_WIFI_IPV4='192.168.1.6'
            export GS179_WIFI_NAME='test-wifi'
            export GS179_TEST_ONLY_MONITORING='1'
            export GS179_LOCAL_LAN_TEST_ONLY='1'
            export GS179_TEST_ONLY_HOME_PREFIX='gs177-test-'
        """).lstrip(), encoding="utf-8")
        config.chmod(0o600)

    def test_generated_unit_keeps_windows_forwarding_out_of_service_lifecycle(self):
        result = self._run_script("install-unit")
        self.assertEqual(result.returncode, 0, result.stderr)
        unit = (self.home / ".config/systemd/user/gs179-laptop.service").read_text()
        self.assertIn("ExecStart=/bin/bash", unit)
        self.assertIn(" run\n", unit)
        self.assertNotIn("ExecStartPost", unit)
        self.assertNotIn("proxy-start", unit)
        self.assertIn("ExecStopPost=/bin/bash", unit)
        self.assertIn(" stop-post\n", unit)
        systemctl_calls = self.systemctl_log.read_text()
        self.assertIn("--user daemon-reload", systemctl_calls)
        self.assertIn("--user enable gs179-laptop.service", systemctl_calls)

    def test_failed_service_result_preserves_running_postgres_for_recovery(self):
        self.pg_state.touch()
        result = self._run_script("stop-post", extra_env={"SERVICE_RESULT": "exit-code"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PostgreSQL left running for local recovery", result.stdout)
        self.assertTrue(self.pg_state.exists())
        self.assertFalse(self.pg_log.exists() and " stop" in self.pg_log.read_text())

    def test_clean_stop_stops_only_postgres_without_windows_network_calls(self):
        self.pg_state.touch()
        result = self._run_script("stop-post", extra_env={"SERVICE_RESULT": "success"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.pg_state.exists())
        self.assertIn("-m fast -w stop", self.pg_log.read_text())
        self.assertNotIn("powershell", self.pg_log.read_text().lower())

    def test_service_recovery_starts_postgres_once_and_never_runs_proxy_hooks(self):
        self._write_private_server_env()
        first = self._run_script("run")
        second = self._run_script("run")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        pg_calls = self.pg_log.read_text().splitlines()
        self.assertEqual(sum(" start" in f" {line}" for line in pg_calls), 1)
        self.assertEqual(len(self.gunicorn_log.read_text().splitlines()), 2)
        self.assertTrue(all("--bind 172.17.152.10:8444" in line
                            for line in self.gunicorn_log.read_text().splitlines()))
        self.assertNotIn("proxy-start", (self.home / ".config/systemd/user/gs179-laptop.service").read_text()
                         if (self.home / ".config/systemd/user/gs179-laptop.service").exists() else "")

    def test_GS117_HUB_ROUTE_001_explicit_fixed_port_reuses_scoped_proxy_guards(self):
        source = WINDOWS_PROXY.read_text(encoding="utf-8")
        self.assertIn('[string]$EndpointKind = "Caregiver"', source)
        self.assertIn('[ValidateSet("Caregiver", "PhysicalHubIngress")]', source)
        physical = source[source.index('if ($EndpointKind -eq "PhysicalHubIngress")'):
                          source.index('function Stop-WithError')]
        for required in ('$ListenPort = 8445', '$TargetPort = 8445',
                         '$RuleName = "GS117-Physical-Hub-mTLS"',
                         '$Action -notin @("Audit", "Start", "Stop")'):
            self.assertIn(required, physical)
        self.assertNotIn("18791", source)
        self.assertIn('if ($Action -in @("Start", "Stop", "Watch")) { Assert-Administrator }', source)
        self.assertIn('Test-TrustedWifiProfile', source)
        self.assertIn('-LocalAddress $actualAddress -LocalPort $ListenPort', source)
        print("CASE GS117-HUB-ROUTE-001 PASS")

    def test_read_only_audit_precedes_mutation_admin_gate(self):
        source = WINDOWS_PROXY.read_text(encoding="utf-8")
        self.assertIn("function Get-NetstatListenerCount([string]$Address, [int]$Port)", source)
        self.assertIn('if ($listenerReadStatus -ne "READABLE")', source)
        self.assertIn('ListenerReadStatus = $listenerReadStatus', source)
        self.assertIn('ListenerCount = $listenerCount', source)
        audit = source.index('if ($Action -eq "Audit")')
        audit_exit = source.index("exit 0", audit)
        admin_gate = source.index('if ($Action -in @("Start", "Stop", "Watch")) { Assert-Administrator }')
        self.assertLess(audit, audit_exit)
        self.assertLess(audit_exit, admin_gate)
        stop = source[source.index('if ($Action -eq "Stop")'):source.index('$wifiState = Get-ActiveWifiState')]
        self.assertLess(stop.index("Assert-Administrator"), stop.index("portproxy delete"))
        self.assertLess(stop.index("Assert-Administrator"), stop.index("Remove-NetFirewallRule"))
        start = source[source.index('if ($Action -eq "Start")', admin_gate):]
        for mutation in ("New-NetFirewallRule -Name", "Set-NetFirewallAddressFilter",
                         "portproxy add", "portproxy delete"):
            self.assertGreater(start.index(mutation), 0)
        self.assertIn("if ($needsFirewallScopeUpdate)", start)
        self.assertLess(source.index('if ($Action -eq "UnregisterWatch")'),
                        source.index("Unregister-ScheduledTask"))
        self.assertLess(source.index('if ($Action -eq "RegisterWatch")'),
                        source.index("Register-ScheduledTask"))

    def test_proxy_start_repairs_dormant_mapping_and_fails_closed_without_listener(self):
        source = WINDOWS_PROXY.read_text(encoding="utf-8")
        start = source[source.index('if ($Action -eq "Start")', source.index('$existingRule = Get-ExactFirewallRule')):]
        self.assertIn("elseif ($occupied.Count -eq 0)", start)
        self.assertIn("Wait-PortProxyListener $actualAddress $ListenPort", start)
        self.assertIn("portproxy_listener_not_active", start)
        self.assertIn("$originalMappingRemoved -and $mapRows.Count -eq 1", start)
        self.assertIn('if ($createdFirewall) { Remove-NetFirewallRule', start)

    def test_health_states_do_not_promote_host_or_wifi_to_hub_health(self):
        source = LAPTOP_SERVER.read_text(encoding="utf-8")
        self.assertIn("LOCAL_BACKEND_READY=PASS", source)
        self.assertIn("LAPTOP_LAN_ENDPOINT_TLS_READY=PASS tls=ca_and_dns_san_verified", source)
        self.assertIn("LAN_FORWARDING_READY=FAIL", source)
        self.assertIn("DEVELOPMENT_ENDPOINT_READY=FAIL local_backend=%s lan_forwarding=%s", source)
        self.assertIn("(( local_ready == 0 && lan_ready == 0 ))", source)
        self.assertIn("PHONE_LAN_REACHABLE=NOT_VERIFIED", source)
        self.assertIn("HUB_INGRESS_RUNTIME_IMPLEMENTED=YES", source)
        self.assertIn("HUB_INGRESS_AUTOSTART=DISABLED", source)
        self.assertIn("HUB_IDENTITY_AUTHENTICATED=NO", source)
        self.assertIn("HUB_MONITORING_FRESHNESS=UNKNOWN", source)
        self.assertIn("PERSISTENT_HUB_INGRESS=NOT_CONFIGURED", source)
        self.assertIn("HUB_INGRESS_READY=NOT_CONFIGURED", source)
        self.assertNotIn("192.168.1.6", source)
        self.assertNotIn("GS179_WIFI_NAME=", source)
        self.assertIn('--resolve "$GS179_LAN_HOSTNAME:443:$observed_ip"', source)
        self.assertIn('"https://$GS179_LAN_HOSTNAME/readyz"', source)
        self.assertIn('network-refresh)', source)
        self.assertIn('"PUBLIC_ORIGIN": "https://" + host + ".local"', source)

    def test_GS179_LAN_AUTO_001_network_refresh_and_watcher_retarget_only_owned_service(self):
        source = LAPTOP_SERVER.read_text(encoding="utf-8")
        proxy = WINDOWS_PROXY.read_text(encoding="utf-8")
        self.assertIn("network-refresh-config)", source)
        self.assertIn("record-proxy-target)", source)
        self.assertIn("start-mdns-advertiser)", source)
        self.assertIn("proxy-watch-register)", source)
        self.assertIn("-Action RegisterWatch -LinuxScriptPath", source)
        self.assertIn("NetworkProfile/Operational", proxy)
        self.assertIn("EventID=10000", proxy)
        self.assertIn("Get-ActiveWifiState ($Action -eq \"Watch\")", proxy)
        self.assertIn("-RemoteAddress $scope", proxy)
        self.assertIn('-InterfaceAlias "Wi-Fi"', proxy)
        self.assertIn("-Profile $firewallProfile", proxy)
        self.assertLess(proxy.index("record-proxy-target '$WslAddress'"),
                        proxy.index("start-mdns-advertiser"))
        self.assertIn('function Test-TrustedWifiProfile($Category)', proxy)
        register = proxy[proxy.index('if ($Action -eq "RegisterWatch")'):proxy.index('# Rollback must remain available')]
        self.assertIn('Get-ActiveWifiState $false', register)
        self.assertIn('watch_registration_requires_trusted_private_or_domain_rfc1918_wifi', register)
        self.assertLess(register.index('Test-TrustedWifiProfile'), register.index('Register-ScheduledTask'))
        trusted_start = proxy.index('if ($Action -in @("Start", "Watch") -and -not (Test-TrustedWifiProfile')
        self.assertLess(trusted_start, proxy.index('$existingRule = Get-ExactFirewallRule', trusted_start))
        self.assertNotIn("ExpectedWifiName", proxy)
        self.assertNotIn("WifiAddress = \"192.168.", proxy)

    def test_existing_watcher_reconciles_wsl_only_ip_changes_without_restarting_healthy_backend(self):
        proxy = WINDOWS_PROXY.read_text(encoding="utf-8")
        source = LAPTOP_SERVER.read_text(encoding="utf-8")
        self.assertIn("<CalendarTrigger>", proxy)
        self.assertIn("<Interval>PT1M</Interval><Duration>P1D</Duration>", proxy)
        self.assertIn("<ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>", proxy)
        self.assertIn("logon,Wi-Fi profile connected,daily WSL address reconciliation every minute", proxy)
        self.assertIn("-Action Watch", proxy)
        self.assertIn("network-refresh-config", proxy)
        self.assertIn("NETWORK_CONFIGURATION_CHANGED=0", source)
        self.assertIn("ensure_local_service ||", source)
        self.assertIn("elif (( NETWORK_CONFIGURATION_CHANGED != 0 )); then", source)
        self.assertIn("elif ! wait_for_local_backend; then", source)
        self.assertIn("LAN_FORWARDING_READY=FAIL", source)

    def test_watch_revalidates_discovered_wsl_ip_before_start_guard(self):
        proxy = WINDOWS_PROXY.read_text(encoding="utf-8")
        discovery = proxy.index('$WslAddress = $wslMatch.Groups["address"].Value')
        watch_start = proxy.index('$Action = "Start"', discovery)
        revalidation = proxy.index('$wslPrivate = Is-Rfc1918 $WslAddress', watch_start)
        start_guard = proxy.index(
            'if (-not $wslPrivate -or $WslAddress -notmatch', revalidation)
        self.assertLess(discovery, watch_start)
        self.assertLess(watch_start, revalidation)
        self.assertLess(revalidation, start_guard)

    def test_gs117_entrypoint_starts_local_service_and_waits_for_controller_page(self):
        launcher = (CODE_ROOT / "tools" / "local" / "gs117-tc001-launch.sh").read_text(encoding="utf-8")
        windows_launcher = (CODE_ROOT / "tools" / "local" / "GS117-TC001-Console.cmd").read_text(encoding="utf-8")
        self.assertIn('"$GS179" dev-start', launcher)
        self.assertIn('"$GS179" proxy-audit', launcher)
        self.assertIn("GS117_WEB_UTILITY_READY=ALREADY_RUNNING", launcher)
        self.assertIn("http://127.0.0.1:18791/", launcher)
        self.assertIn("exec python3 code/tools/local/gs117_tc001_console.py", launcher)
        self.assertIn("http://127.0.0.1:18791/", windows_launcher)
        self.assertIn("AddSeconds(30)", windows_launcher)
        self.assertIn("GS-117 utility did not become reachable", windows_launcher)
        print("CASE GS179-LAN-AUTO-001 PASS")

    def test_GS179_LAN_RECOVERY_001_proxy_stop_rollback_needs_no_active_wifi(self):
        source = WINDOWS_PROXY.read_text(encoding="utf-8")
        stop_branch = source.index('if ($Action -eq "Stop")')
        wifi_probe = source.index('$wifiState = Get-ActiveWifiState')
        stop = source[stop_branch:wifi_probe]
        self.assertLess(stop_branch, wifi_probe)
        self.assertIn("Assert-Administrator", stop)
        self.assertIn("Get-PortProxyRows", stop)
        self.assertIn("Get-ExactFirewallRule", stop)
        self.assertNotIn("Get-ActiveWifiState", stop)
        print("CASE GS179-LAN-RECOVERY-001 PASS")

    def test_proxy_target_recorder_accepts_only_wsl_nat_addresses(self):
        accepted = self._run_script("record-proxy-target", "172.17.152.10")
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        target = self.home / ".local/state/ghar-sajag/gs179-laptop/windows-wsl-target"
        self.assertEqual(target.read_text().strip(), "172.17.152.10")
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)

        for invalid in ("192.168.1.10", "172.15.0.1", "172.32.0.1", "not-an-ip"):
            with self.subTest(invalid=invalid):
                rejected = self._run_script("record-proxy-target", invalid)
                self.assertEqual(rejected.returncode, 2)
                self.assertIn("refusing_to_record_non_wsl_nat_address", rejected.stderr)
        self.assertEqual(target.read_text().strip(), "172.17.152.10")

    def test_start_and_restart_wait_for_bounded_verified_local_readiness(self):
        source = LAPTOP_SERVER.read_text(encoding="utf-8")
        wait = source.index("wait_for_local_backend()")
        next_function = source.index("start_service()", wait)
        wait_body = source[wait:next_function]
        self.assertIn("$(seq 1 30)", wait_body)
        self.assertIn("postgres_health_check", wait_body)
        self.assertIn("local_https_health_check", wait_body)
        self.assertIn("start) start_service ;;", source)
        self.assertIn("restart) restart_service ;;", source)
        start = source[source.index("start_service()") : source.index("restart_service()")]
        restart = source[source.index("restart_service()") : source.index("run_event()")]
        self.assertIn("load_config", start)
        self.assertIn("load_config", restart)
        self.assertIn("ensure_local_service ||", start)
        self.assertIn("wait_for_local_backend ||", restart)


if __name__ == "__main__":
    unittest.main()
