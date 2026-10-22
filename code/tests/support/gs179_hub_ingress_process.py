"""Disposable subprocess entry point for the GS-179 runtime E2E only.

This helper reads public TEST_ONLY issuer metadata read-only and accepts a
trusted-time fixture explicitly supplied by its parent test. It is not an
operator service and must never be used for real-device credentials.
"""
from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import signal
import sqlite3
import threading

from cryptography.hazmat.primitives import serialization

from pilot_test_issuer import RegisteredCloudCredential
from ghar_sajag.cloud_client_identity import TimeReadiness
from ghar_sajag.gs179_hub_ingress_runtime import (
    HubIngressRuntimeConfig,
    start_gs179_test_only_hub_ingress,
)
from gs40_test_bootstrap import AuthorityService


class _ReadOnlyTestCredentialRegistry:
    """Read existing public credential state without issuer/key operations."""

    def __init__(self, path: str):
        source = Path(path).resolve(strict=True)
        uri = source.as_uri() + "?mode=ro"
        self._db = sqlite3.connect(uri, uri=True, timeout=3, check_same_thread=False)
        self._lock = threading.RLock()
        row = self._db.execute(
            "SELECT environment,ca_fingerprint FROM gs168_meta WHERE only_row=1"
        ).fetchone()
        if row is None or row[0] != "TEST_ONLY":
            self._db.close()
            raise ValueError("test_only_credential_registry_required")
        self.environment, self.ca_fingerprint = row

    def by_fingerprint(self, fingerprint_sha256: str):
        with self._lock:
            row = self._db.execute(
                "SELECT hub_id,state,generation FROM gs168_credentials WHERE fingerprint=?",
                (fingerprint_sha256,),
            ).fetchone()
        if row is None:
            return None
        return RegisteredCloudCredential(
            fingerprint_sha256, row[0], row[1], generation=row[2]
        )

    def close(self):
        self._db.close()


class _ExplicitTestTrustedTime:
    def __init__(self, value: str):
        if os.environ.get("GS179_TEST_ONLY_HUB_TIME_SOURCE") != "GS40_TEST_SIGNED_TIME_FIXTURE":
            raise ValueError("explicit_test_signed_time_fixture_required")
        self._value = datetime.fromisoformat(value)
        if self._value.tzinfo is None or self._value.utcoffset() is None:
            raise ValueError("aware_test_trusted_time_required")

    def readiness(self):
        return TimeReadiness.TRUSTED

    def current_utc(self):
        return self._value


def _record_trace(path: str):
    target = Path(path)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)

    def record(route, request, status, response):
        event_key = request.get("event_key") if isinstance(request, dict) else None
        response_key = response.get("event_key") if isinstance(response, dict) else None
        row = {
            "route": route,
            "http_status": status,
            "receipt_status": response.get("status") if isinstance(response, dict) else None,
            "duplicate": response.get("duplicate") if isinstance(response, dict) else None,
            "event_key": event_key,
            "receipt_event_key": response_key,
        }
        os.write(fd, (json.dumps(row, separators=(",", ":")) + "\n").encode())
        os.fsync(fd)

    return record, lambda: os.close(fd)


def main() -> int:
    registry = None
    close_trace = lambda: None
    runtime = None
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_args: stop.set())
    signal.signal(signal.SIGINT, lambda *_args: stop.set())
    try:
        config = HubIngressRuntimeConfig.from_environment()
        if not config.enabled:
            runtime = start_gs179_test_only_hub_ingress(config)
            print(json.dumps({"event": "DISABLED", "status": runtime.status()},
                             separators=(",", ":")), flush=True)
            runtime.close()
            runtime = None
            return 0
        registry = _ReadOnlyTestCredentialRegistry(os.environ["GS179_TEST_ONLY_HUB_REGISTRY"])
        trusted_time = _ExplicitTestTrustedTime(
            os.environ["GS179_TEST_ONLY_HUB_TIME_UTC"]
        )
        trace_path = os.environ["GS179_TEST_ONLY_HUB_TRACE"]
        on_result, close_trace = _record_trace(trace_path)
        authority_holder = {}

        def authority_refresh(peer, body):
            return authority_holder["service"].refresh(peer, body)

        dropped_marker = Path(trace_path + ".first-commit-dropped")

        def drop_first_committed_event(route, _request, status, response):
            if (not dropped_marker.exists() and route.endswith("/events") and
                    status in (200, 201) and isinstance(response, dict) and
                    response.get("status") == "COMMITTED"):
                try:
                    fd = os.open(dropped_marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                except FileExistsError:
                    return False
                os.close(fd)
                return True
            return False

        runtime = start_gs179_test_only_hub_ingress(
            config,
            credentials=registry,
            trusted_time=trusted_time,
            authority_refresh=authority_refresh,
            on_result=on_result,
            drop_response=drop_first_committed_event,
        )
        authority_signer = serialization.load_pem_private_key(
            Path(os.environ["GS179_TEST_ONLY_HUB_AUTHORITY_SIGNER"]).read_bytes(),
            password=None,
        )
        authority_holder["service"] = AuthorityService(
            registry,
            runtime.durable_api.db,
            runtime.durable_api.api.service.lock,
            clock=lambda: int(trusted_time.current_utc().timestamp()),
            enabled=True,
            signer=authority_signer,
        )
        print(json.dumps({
            "event": "READY",
            "origin": runtime.origin,
            "status": runtime.status(),
        }, separators=(",", ":")), flush=True)
        while not stop.wait(0.2):
            pass
        runtime.close()
        runtime = None
        print(json.dumps({"event": "STOPPED"}, separators=(",", ":")), flush=True)
        return 0
    except BaseException as error:
        print(json.dumps({"event": "FAILED", "error_type": type(error).__name__},
                         separators=(",", ":")), flush=True)
        return 2
    finally:
        if runtime is not None:
            runtime.close()
        close_trace()
        if registry is not None:
            registry.close()


if __name__ == "__main__":
    raise SystemExit(main())
