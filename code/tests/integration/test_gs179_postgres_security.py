"""Focused failure-closed PostgreSQL boundary tests for GS-179 TEST_ONLY."""
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest
import psycopg

from ghar_sajag.postgres_database import connect_postgres, initialize_postgres
from gs179_postgres_test_db import IsolatedPostgresSchema, local_verified_postgres_url

CODE_ROOT = Path(__file__).resolve().parents[2]
LAPTOP_SERVER = CODE_ROOT / "tools" / "local" / "gs179-laptop-server.sh"
WINDOWS_PROXY = CODE_ROOT / "tools" / "local" / "gs179-windows-lan-proxy.ps1"


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

    def _run_script(self, command: str, *, extra_env=None):
        env = self.env.copy()
        env.update(extra_env or {})
        return subprocess.run(
            ["bash", str(LAPTOP_SERVER), command], env=env,
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

    def test_read_only_audit_precedes_mutation_admin_gate(self):
        source = WINDOWS_PROXY.read_text(encoding="utf-8")
        audit = source.index('if ($Action -eq "Audit")')
        audit_exit = source.index("exit 0", audit)
        admin_gate = source.index("administrator_token_required_for_scoped_portproxy_and_firewall_rule")
        self.assertLess(audit, audit_exit)
        self.assertLess(audit_exit, admin_gate)
        for mutation in ("New-NetFirewallRule", "Remove-NetFirewallRule", "portproxy add", "portproxy delete"):
            self.assertGreater(source.index(mutation), admin_gate)

    def test_health_states_do_not_promote_host_or_wifi_to_hub_health(self):
        source = LAPTOP_SERVER.read_text(encoding="utf-8")
        self.assertIn("LOCAL_BACKEND_READY=PASS", source)
        self.assertIn("PHONE_LAN_REACHABLE=BLOCKED_CONFIG_MISMATCH", source)
        self.assertIn("HUB_INGRESS_READY=NOT_CONFIGURED", source)
        mismatch = source.index('if [[ "$observed_ip" != "$GS179_WINDOWS_WIFI_IPV4" ]]')
        phone_probe = source.index('"https://$GS179_WINDOWS_WIFI_IPV4/readyz"')
        self.assertLess(mismatch, phone_probe)

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
        self.assertIn("wait_for_local_backend ||", start)
        self.assertIn("wait_for_local_backend ||", restart)


if __name__ == "__main__":
    unittest.main()
