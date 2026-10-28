"""Runtime-owned TEST_ONLY mTLS -> PostgreSQL -> caregiver process E2E."""
from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import replace
import json
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import unittest
from cryptography.hazmat.primitives import serialization
from psycopg import OperationalError
from psycopg.conninfo import make_conninfo

from ghar_sajag.cloud_client_identity import TimeReadiness
from ghar_sajag.configuration_repository import PostgresConfigurationRepository
from ghar_sajag.diagnostic_authorization import ActorSession
from ghar_sajag.gs179_hub_ingress_runtime import (
    Gs179TestOnlyHubIngressRuntime,
    HubIngressRuntimeConfig,
    _validate_runtime_bind,
    start_gs179_test_only_hub_ingress,
)
from ghar_sajag.identity_namespaces import is_gs179_test_hub_home
from gs178_stack import ProductStack, HOME


CODE_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_PROCESS = CODE_ROOT / "tests" / "support" / "gs179_hub_ingress_process.py"


class _FixtureTrustedTime:
    def __init__(self, current: datetime, ready=True):
        self.value = current
        self.ready = ready

    def readiness(self):
        return TimeReadiness.TRUSTED if self.ready else TimeReadiness.UNTRUSTED

    def current_utc(self):
        return self.value


def _unused_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _readline(process: subprocess.Popen, timeout=15) -> dict:
    if process.stdout is None:
        raise AssertionError("runtime_stdout_unavailable")
    if not select.select([process.stdout], [], [], timeout)[0]:
        raise TimeoutError("runtime_process_output_timeout")
    line = process.stdout.readline()
    if not line:
        error = process.stderr.read(4096) if process.stderr else ""
        raise AssertionError(f"runtime_process_exited:{process.poll()}:{error}")
    return json.loads(line)


class RuntimeDefaultDisabledTests(unittest.TestCase):
    def test_only_exact_owner_approved_physical_hub_home_pair_is_admissible(self):
        self.assertTrue(is_gs179_test_hub_home(
            "hub-e072a1d38d34", "gs177-test-product"))
        self.assertFalse(is_gs179_test_hub_home(
            "hub-001122334455", "gs177-test-product"))
        self.assertFalse(is_gs179_test_hub_home(
            "hub-e072a1d38d34", "gs177-test-other"))
        self.assertFalse(is_gs179_test_hub_home(
            "test-hub-product", "production-home"))

    def test_default_environment_is_disabled_and_does_not_require_dependencies(self):
        config = HubIngressRuntimeConfig.from_environment({})
        runtime = Gs179TestOnlyHubIngressRuntime(config)
        self.assertIsNone(runtime.start())
        self.assertEqual(runtime.status()["runtime_enabled"], "NO")
        self.assertEqual(runtime.status()["listener_started"], "NO")
        self.assertEqual(runtime.status()["real_hub_authenticated"], "NO")
        self.assertEqual(runtime.status()["monitoring_freshness"], "UNKNOWN")
        runtime.close()
        entrypoint = start_gs179_test_only_hub_ingress(HubIngressRuntimeConfig.disabled())
        self.assertIsNone(entrypoint.origin)
        self.assertEqual(entrypoint.status()["listener_started"], "NO")
        entrypoint.close()

    def test_explicit_enable_requires_all_configuration_before_resources(self):
        with self.assertRaisesRegex(ValueError, "hub_ingress_configuration_incomplete"):
            HubIngressRuntimeConfig.from_environment({"GS179_TEST_ONLY_HUB_INGRESS": "1"})

    def test_private_bind_requires_explicit_rfc1918_and_fixed_port_opt_in(self):
        _validate_runtime_bind("127.0.0.1", 0, False)
        _validate_runtime_bind("192.168.1.10", 8444, True)
        with self.assertRaisesRegex(ValueError, "private_bind_requires_explicit_opt_in"):
            _validate_runtime_bind("192.168.1.10", 8444, False)
        with self.assertRaisesRegex(ValueError, "fixed_port_required"):
            _validate_runtime_bind("192.168.1.10", 0, True)
        for address in ("0.0.0.0", "8.8.8.8", "172.15.0.10", "2001:db8::1"):
            with self.subTest(address=address), self.assertRaises(ValueError):
                _validate_runtime_bind(address, 8444, True)

        env = {
            "GS179_TEST_ONLY_HUB_INGRESS": "1",
            "GS179_TEST_ONLY_HUB_PROFILE": "GS179_TEST_ONLY",
            "GS179_TEST_ONLY_HUB_DSN": "postgresql://test@127.0.0.1/gs179_monitoring?sslmode=verify-full",
            "GS179_TEST_ONLY_HUB_SERVER_CERT": "/tmp/server.pem",
            "GS179_TEST_ONLY_HUB_SERVER_KEY": "/tmp/server.key",
            "GS179_TEST_ONLY_HUB_CLIENT_CA": "/tmp/client-ca.pem",
            "GS179_TEST_ONLY_HUB_ID": "test-hub-private-bind",
            "GS179_TEST_ONLY_HUB_HOME_ID": "gs177-test-private-bind",
            "GS179_TEST_ONLY_HUB_INSTALLATION_EPOCH": "1",
            "GS179_TEST_ONLY_HUB_BIND_HOST": "192.168.1.10",
            "GS179_TEST_ONLY_HUB_PORT": "8444",
            "GS179_TEST_ONLY_HUB_ALLOW_PRIVATE_BIND": "1",
        }
        config = HubIngressRuntimeConfig.from_environment(env)
        self.assertTrue(config.allow_private_bind)
        with self.assertRaisesRegex(ValueError, "private_bind_flag_invalid"):
            HubIngressRuntimeConfig.from_environment({
                **env, "GS179_TEST_ONLY_HUB_ALLOW_PRIVATE_BIND": "yes"
            })


@unittest.skipUnless(os.environ.get("GS179_TEST_POSTGRES_DSN"),
                     "requires the registered isolated GS-179 PostgreSQL test environment")
class RuntimeOwnedPostgresCaregiverE2E(unittest.TestCase):
    def setUp(self):
        self.stack = ProductStack(
            postgres_dsn=os.environ["GS179_TEST_POSTGRES_DSN"],
            start_hub_listener=False,
        )
        self.addCleanup(self.stack.close)
        self.process: subprocess.Popen | None = None
        self.addCleanup(self._stop_runtime_process)
        self.trace_path = self.stack.path / "runtime-trace.jsonl"
        self.port = _unused_loopback_port()
        self.epoch = self.stack.durable.db.execute(
            "SELECT installation_epoch FROM hub_ownership_registry "
            "WHERE hub_device_id=? AND state='ACTIVE'", (self.stack.hub_id,)
        ).fetchone()[0]
        self.trusted = _FixtureTrustedTime(
            datetime.fromtimestamp(self.stack.time.clock(), timezone.utc)
        )
        # All material is freshly generated under ProductStack's mode-0700 temp
        # directory; tighten the ephemeral private key before runtime checks.
        self.stack.key_path.chmod(0o600)
        self.stack.path.joinpath("issuer.sqlite").chmod(0o600)
        self.authority_signer_path = self.stack.path / "test-authority-signer.pem"
        signer_pem = self.stack.authority.signer.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        fd = os.open(self.authority_signer_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as signer_file:
            signer_file.write(signer_pem)

    def _config(self, *, epoch=None, port=None):
        return HubIngressRuntimeConfig(
            enabled=True,
            profile="GS179_TEST_ONLY",
            dsn=self.stack.postgres_dsn,
            server_cert=self.stack.cert_path,
            server_key=self.stack.key_path,
            client_ca=self.stack.client_ca,
            hub_id=self.stack.hub_id,
            home_id=self.stack.home_id,
            installation_epoch=self.epoch if epoch is None else epoch,
            bind_host="127.0.0.1",
            port=self.port if port is None else port,
        )

    def _process_environment(self):
        env = os.environ.copy()
        paths = [
            str(CODE_ROOT / "backend"),
            str(CODE_ROOT / "tools" / "hil"),
            str(CODE_ROOT / "tools" / "factory"),
            str(CODE_ROOT / "tests" / "support"),
            str(CODE_ROOT / "parivar_saathi_android_app" / "server"),
        ]
        if env.get("PYTHONPATH"):
            paths.append(env["PYTHONPATH"])
        env["PYTHONPATH"] = os.pathsep.join(paths)
        env.update({
            "GS179_TEST_ONLY_HUB_INGRESS": "1",
            "GS179_TEST_ONLY_HUB_PROFILE": "GS179_TEST_ONLY",
            "GS179_TEST_ONLY_HUB_DSN": self.stack.postgres_dsn,
            "GS179_TEST_ONLY_HUB_SERVER_CERT": str(self.stack.cert_path),
            "GS179_TEST_ONLY_HUB_SERVER_KEY": str(self.stack.key_path),
            "GS179_TEST_ONLY_HUB_CLIENT_CA": str(self.stack.client_ca),
            "GS179_TEST_ONLY_HUB_ID": self.stack.hub_id,
            "GS179_TEST_ONLY_HUB_HOME_ID": self.stack.home_id,
            "GS179_TEST_ONLY_HUB_INSTALLATION_EPOCH": str(self.epoch),
            "GS179_TEST_ONLY_HUB_BIND_HOST": "127.0.0.1",
            "GS179_TEST_ONLY_HUB_PORT": str(self.port),
            "GS179_TEST_ONLY_HUB_REGISTRY": str(self.stack.path / "issuer.sqlite"),
            "GS179_TEST_ONLY_HUB_AUTHORITY_SIGNER": str(self.authority_signer_path),
            "GS179_TEST_ONLY_HUB_TIME_SOURCE": "GS40_TEST_SIGNED_TIME_FIXTURE",
            "GS179_TEST_ONLY_HUB_TIME_UTC": self.trusted.value.isoformat(),
            "GS179_TEST_ONLY_HUB_TRACE": str(self.trace_path),
        })
        return env

    def _start_runtime_process(self):
        self.process = subprocess.Popen(
            [sys.executable, "-u", str(RUNTIME_PROCESS)],
            cwd=CODE_ROOT,
            env=self._process_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        ready = _readline(self.process)
        self.assertEqual(ready.get("event"), "READY", ready)
        self.assertEqual(ready["status"]["listener_ready"], "YES", ready)
        self.assertEqual(ready["status"]["postgres_ready"], "YES", ready)
        self.assertEqual(ready["status"]["trusted_time_ready"], "YES", ready)
        self.assertEqual(ready["status"]["real_hub_authenticated"], "NO", ready)
        self.assertEqual(ready["status"]["hub_connected"], "NO", ready)
        self.assertEqual(ready["status"]["monitoring_freshness"], "UNKNOWN", ready)
        self.stack.hub_origin = ready["origin"]
        return ready

    def _stop_runtime_process(self):
        if self.process is None:
            return
        process, self.process = self.process, None
        if process.poll() is None:
            process.terminate()
            stopped = _readline(process, timeout=10)
            self.assertEqual(stopped.get("event"), "STOPPED", stopped)
        self.assertEqual(process.wait(timeout=5), 0)
        if process.stdin:
            process.stdin.close()
        if process.stdout:
            process.stdout.close()
        if process.stderr:
            process.stderr.close()

    def test_actual_runtime_process_commits_source_event_and_retries_after_restart(self):
        # The entry point is truly default-disabled and rejects missing trusted
        # time before connecting to PostgreSQL or opening a listening socket.
        disabled = Gs179TestOnlyHubIngressRuntime(HubIngressRuntimeConfig.disabled())
        self.assertIsNone(disabled.start())
        self.assertEqual(disabled.status()["persistent_hub_ingress"], "NOT_CONFIGURED")

        no_authority = Gs179TestOnlyHubIngressRuntime(
            self._config(), credentials=self.stack.issuer, trusted_time=self.trusted
        )
        with self.assertRaisesRegex(ValueError, "test_only_authority_refresh_provider_required"):
            no_authority.start()
        self.assertIsNone(no_authority.origin)

        # A MAC-shaped ID passes only the TEST_ONLY namespace check. Without
        # an exact active ownership/epoch row the existing durable registry
        # still refuses it before the listener binds.
        unregistered_physical = Gs179TestOnlyHubIngressRuntime(
            replace(self._config(), hub_id="hub-e072a1d38d34",
                    home_id="gs177-test-product"),
            credentials=self.stack.issuer, trusted_time=self.trusted,
            authority_refresh=lambda *_args: b"",
        )
        with self.assertRaisesRegex(ValueError, "current_hub_home_epoch_binding_required"):
            unregistered_physical.start()
        self.assertIsNone(unregistered_physical.origin)

        untrusted = _FixtureTrustedTime(self.trusted.value, ready=False)
        no_time = Gs179TestOnlyHubIngressRuntime(
            self._config(), credentials=self.stack.issuer, trusted_time=untrusted,
            authority_refresh=lambda *_args: b"",
        )
        with self.assertRaisesRegex(ValueError, "hub_ingress_trusted_time_not_ready"):
            no_time.start()
        self.assertIsNone(no_time.origin)

        for missing_field in ("server_cert", "server_key", "client_ca"):
            with self.subTest(missing_tls_material=missing_field):
                missing_material = Gs179TestOnlyHubIngressRuntime(
                    replace(self._config(), **{
                        missing_field: self.stack.path / f"missing-{missing_field}.pem"
                    }),
                    credentials=self.stack.issuer, trusted_time=self.trusted,
                    authority_refresh=lambda *_args: b"",
                )
                with self.assertRaisesRegex(
                        ValueError, "hub_ingress_tls_material_missing_or_unsafe"):
                    missing_material.start()
                self.assertIsNone(missing_material.origin)

        world_readable_key = self.stack.path / "world-readable-server.key"
        world_readable_key.write_bytes(self.stack.key_path.read_bytes())
        world_readable_key.chmod(0o644)
        unsafe_key = Gs179TestOnlyHubIngressRuntime(
            replace(self._config(), server_key=world_readable_key),
            credentials=self.stack.issuer, trusted_time=self.trusted,
            authority_refresh=lambda *_args: b"",
        )
        with self.assertRaisesRegex(
                ValueError, "hub_ingress_server_key_permissions_must_be_owner_only"):
            unsafe_key.start()
        self.assertIsNone(unsafe_key.origin)

        wrong_registry = type("WrongTestRegistry", (), {
            "environment": "TEST_ONLY",
            "ca_fingerprint": "0" * 64,
            "by_fingerprint": staticmethod(self.stack.issuer.by_fingerprint),
        })()
        wrong_ca = Gs179TestOnlyHubIngressRuntime(
            self._config(), credentials=wrong_registry, trusted_time=self.trusted,
            authority_refresh=lambda *_args: b"",
        )
        with self.assertRaisesRegex(ValueError, "test_only_client_ca_registry_mismatch"):
            wrong_ca.start()
        self.assertIsNone(wrong_ca.origin)

        stale_epoch = Gs179TestOnlyHubIngressRuntime(
            self._config(epoch=self.epoch + 1), credentials=self.stack.issuer,
            trusted_time=self.trusted, authority_refresh=lambda *_args: b"",
        )
        with self.assertRaisesRegex(ValueError, "current_hub_home_epoch_binding_required"):
            stale_epoch.start()
        self.assertIsNone(stale_epoch.origin)

        offline_dsn = make_conninfo(self.stack.postgres_dsn, port=1)
        unavailable = Gs179TestOnlyHubIngressRuntime(
            replace(self._config(), dsn=offline_dsn), credentials=self.stack.issuer,
            trusted_time=self.trusted, authority_refresh=lambda *_args: b"",
        )
        with self.assertRaises(OperationalError):
            unavailable.start()
        self.assertIsNone(unavailable.origin)

        # Same port is used for orderly listener restart so the already
        # configured HOST_SIM Hub runtime can reconnect without a new identity.
        self._start_runtime_process()

        # Exercise the real TEST_ONLY caregiver repository and mTLS Hub routes
        # against this isolated PostgreSQL schema. The callback models the
        # already-verified test session; it does not create a production issuer.
        repository = PostgresConfigurationRepository(
            self.stack.durable.db,
            authorize_caregiver_settings=lambda actor, home_id, at: (
                actor.actor_id == self.stack.actor and home_id == HOME and
                actor.issuer_reference == "GS179_TEST_ONLY_LITE" and at < actor.expires_at
            ),
            lock=self.stack.service.lock,
        )
        self.stack.lite.product_view.configuration_repository = repository
        policy = {
            "schema": 1, "home_id": HOME, "timezone": "Etc/UTC", "mode": "HOME",
            "morning": {"enabled": True, "start_minute": 360,
                        "end_minute": 660, "grace_minutes": 20},
            "activity_rules": {
                "quiet_hours_enabled": True, "quiet_start_minute": 60,
                "quiet_end_minute": 300, "door_open_timeout_seconds": 300,
                "daytime_inactivity_enabled": True, "daytime_start_minute": 480,
                "daytime_end_minute": 1260, "daytime_inactivity_seconds": 10800,
                "morning_steps": [
                    {"location": "bedroom", "enabled": True, "required": True},
                ],
                "morning_sequence_strict_order": True,
            },
        }
        cookie = self.stack.login()
        publish_status, desired, _ = self.stack.human(
            "POST", f"/lite/v1/homes/{HOME}/routine-config",
            {"expected_version": 0, "config": policy}, cookie=cookie,
        )
        self.assertEqual((publish_status, desired["desired_version"], desired["desired_status"]),
                         (202, 1, "DESIRED"), desired)
        canonical_policy = {key: value for key, value in policy.items()
                            if key not in {"schema", "home_id"}}
        hub_get_status, fetched = self.stack.hub_get(f"/v1/homes/{HOME}/config/desired")
        self.assertEqual((hub_get_status, fetched["version"], fetched["config"]),
                         (200, 1, canonical_policy), fetched)
        unrelated_get_status, _ = self.stack.hub_get(f"/v1/homes/{HOME}/events")
        self.assertEqual(unrelated_get_status, 404)
        applied_status, applied_raw = self.stack.hub_request(
            f"/v1/homes/{HOME}/config/applied", {"version": 1}
        )
        applied = json.loads(applied_raw)
        self.assertEqual((applied_status, applied["desired_version"],
                          applied["applied_version"]), (200, 1, 1), applied)
        stale_status, stale_raw = self.stack.hub_request(
            f"/v1/homes/{HOME}/config/applied", {"version": 2}
        )
        self.assertEqual(stale_status, 409, stale_raw)
        self.assertEqual(json.loads(stale_raw), {"error": "configuration_conflict"})
        caregiver_status, caregiver_snapshot, _ = self.stack.human(
            "GET", f"/lite/v1/homes/{HOME}/routine-config", cookie=cookie
        )
        self.assertEqual((caregiver_status, caregiver_snapshot["desired_status"],
                          caregiver_snapshot["applied_version"]), (200, "APPLIED", 1),
                         caregiver_snapshot)

        ready = self.stack.start_node()
        self.assertEqual(ready["stage"], "CLOUDSYNC_READY")
        initial_status, initial_view, _ = self.stack.human(
            "GET", f"/lite/v1/homes/{HOME}/overview", cookie=cookie
        )
        self.assertEqual(initial_status, 200, initial_view)
        self.assertEqual(initial_view["monitoring"], "UNKNOWN", initial_view)

        now = ready["utc"]
        self.stack.domain_now = now + 1
        node_result = self.stack.command(f"input 0 motion {now} {now + 1} 1000 420 0")
        node_event_key = node_result["event_key"]
        first_sync = self.stack.command("sync 3000 1")
        self.assertEqual(first_sync["completed"], 0, first_sync)
        first_trace = [json.loads(line) for line in self.trace_path.read_text().splitlines()]
        first_event_receipt = next(
            row for row in first_trace if row["route"].endswith("/events") and
            row["receipt_status"] == "COMMITTED"
        )
        original_key = first_event_receipt["event_key"]
        self.assertEqual(original_key, {
            "physical_device_id": "test-c3-bedroom",
            "logical_node_id": "bedroom",
            "origin_session_id": 10,
            "event_sequence": 1,
        })
        expected_node_key = (
            f"p{len(original_key['physical_device_id'])}:{original_key['physical_device_id']}"
            f"n{len(original_key['logical_node_id'])}:{original_key['logical_node_id']}"
            f"s{original_key['origin_session_id']}q{original_key['event_sequence']}"
        )
        self.assertEqual(node_event_key, expected_node_key)
        committed = self.stack.durable.db.execute(
            "SELECT e.canonical_event_id,c.hub_device_id,c.ownership_epoch "
            "FROM events e JOIN durable_event_commits c ON c.event_id=e.event_id "
            "WHERE c.home_id=? AND c.physical_device_id=? AND c.logical_node_id=? "
            "AND c.origin_session_id=? AND c.event_sequence=?",
            (HOME, original_key["physical_device_id"], original_key["logical_node_id"],
             original_key["origin_session_id"], original_key["event_sequence"]),
        ).fetchall()
        self.assertEqual(len(committed), 1, original_key)
        self.assertEqual((committed[0][1], committed[0][2]), (self.stack.hub_id, self.epoch))
        provenance = self.stack.service.store.events.event_provenance(
            HOME, committed[0][0]
        )
        self.assertEqual(provenance["event_key"], original_key)
        event_row = self.stack.durable.db.execute(
            "SELECT occurred_at,event_type,location FROM events "
            "WHERE home_id=? AND canonical_event_id=?", (HOME, committed[0][0])
        ).fetchone()
        self.assertEqual((event_row[0], event_row[1], event_row[2]),
                         (now, "MOTION", "bedroom"))

        # A valid TLS client bound to another Home cannot use this listener.
        wrong_home_status, _ = self.stack.hub_request(
            "/v1/homes/gs177-test-other/events", {"event_key": original_key}
        )
        self.assertEqual(wrong_home_status, 403)

        status, caregiver_view, _ = self.stack.human(
            "GET", f"/lite/v1/homes/{HOME}/overview", cookie=cookie
        )
        self.assertEqual(status, 200, caregiver_view)
        visible = [event for event in caregiver_view["recent_events"]
                   if event.get("event_key") == original_key]
        self.assertEqual(len(visible), 1, caregiver_view)
        self.assertEqual(visible[0]["kind"], "MOTION")
        self.assertEqual(visible[0]["occurred_at"], now)
        self.assertEqual(visible[0]["event_key"]["logical_node_id"], "bedroom")

        # The first COMMITTED response was lost after durable commit. Restart
        # the listener process and let the production Node retry its journal.
        self._stop_runtime_process()
        self._start_runtime_process()
        self.stack.command("restart")
        retry_sync = self.stack.command("sync 5000 1")
        self.assertEqual(retry_sync["completed"], 1, retry_sync)
        self.assertEqual(self.stack.durable.db.execute(
            "SELECT COUNT(*) FROM durable_event_commits WHERE home_id=? "
            "AND physical_device_id=? AND logical_node_id=? AND origin_session_id=? "
            "AND event_sequence=?",
            (HOME, original_key["physical_device_id"], original_key["logical_node_id"],
             original_key["origin_session_id"], original_key["event_sequence"]),
        ).fetchone()[0], 1)
        self.assertEqual(self.stack.durable.db.execute(
            "SELECT COUNT(*) FROM events e JOIN durable_event_commits c ON c.event_id=e.event_id "
            "WHERE c.home_id=? AND c.physical_device_id=? AND c.logical_node_id=? "
            "AND c.origin_session_id=? AND c.event_sequence=?",
            (HOME, original_key["physical_device_id"], original_key["logical_node_id"],
             original_key["origin_session_id"], original_key["event_sequence"]),
        ).fetchone()[0], 1)
        self.stack.restart_backend()
        status, caregiver_after_restart, _ = self.stack.human(
            "GET", f"/lite/v1/homes/{HOME}/overview", cookie=cookie
        )
        self.assertEqual(status, 200, caregiver_after_restart)
        self.assertEqual(sum(event.get("event_key") == original_key
                             for event in caregiver_after_restart["recent_events"]), 1)
        self._stop_runtime_process()

        trace = [json.loads(line) for line in self.trace_path.read_text().splitlines()]
        event_receipts = [row for row in trace if row["route"].endswith("/events")
                          and row["receipt_status"] == "COMMITTED"]
        self.assertEqual(len(event_receipts), 2, trace)
        self.assertEqual([row["receipt_status"] for row in event_receipts],
                         ["COMMITTED", "COMMITTED"])
        self.assertEqual([row["duplicate"] for row in event_receipts], [False, True])
        self.assertTrue(all(row["event_key"] == original_key == row["receipt_event_key"]
                            for row in event_receipts))
        self.assertTrue(any(row["http_status"] == 403 and row["route"].endswith("/events")
                            for row in trace), trace)


if __name__ == "__main__":
    unittest.main()
