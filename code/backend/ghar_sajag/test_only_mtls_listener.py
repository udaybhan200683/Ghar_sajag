"""Application-terminated mTLS listener for isolated GS-179 TEST_ONLY use.

This is deliberately not a production server or a Render proxy adapter. The
TLS handshake terminates in this process; Hub identity is derived only from the
verified TLS peer certificate and the current credential/ownership registry.
No HTTP header can create or replace a ``VerifiedHubContext``.
"""
from __future__ import annotations

from datetime import datetime
import ipaddress
import json
import logging
from pathlib import Path
import re
import socket
import ssl
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import BoundedSemaphore, Condition, Thread
import time
from typing import Callable
from urllib.parse import urlsplit

from .cloud_client_identity import TimeReadiness, authorize_cloud_tls_context
from .durable_commit import EventCommitConflict
from .hub_rule_decisions import HubDecisionConflict
from .identity_namespaces import is_gs179_test_hub_id


_HOME_ROUTE = re.compile(r"^/v1/homes/([A-Za-z0-9_-]{1,80})/(events|node-health|hub-rule-decisions)$")
_LOG = logging.getLogger("ghar_sajag.test_only_mtls_listener")


class _BoundedThreadingHTTPServer(ThreadingHTTPServer):
    """Bound accepted request workers and expose a bounded shutdown wait."""

    daemon_threads = True
    block_on_close = False

    def __init__(self, address, handler, *, max_workers: int,
                 tls_context: ssl.SSLContext, connection_timeout_seconds: float):
        self.request_queue_size = max_workers
        self._worker_slots = BoundedSemaphore(max_workers)
        self._worker_condition = Condition()
        self._active_workers = 0
        self._tls_context = tls_context
        self._connection_timeout_seconds = connection_timeout_seconds
        super().__init__(address, handler)

    @property
    def active_workers(self) -> int:
        with self._worker_condition:
            return self._active_workers

    def process_request(self, request, client_address):
        # Do not create an unbounded thread backlog under slow or abusive
        # clients. A full listener closes the newly accepted socket before TLS
        # or HTTP work begins; clients must retry through CloudSync's normal
        # bounded retry policy.
        if not self._worker_slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        with self._worker_condition:
            self._active_workers += 1
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._finish_worker()
            raise

    def process_request_thread(self, request, client_address):
        tls_request = None
        try:
            # The listening socket remains plain. TLS handshake work happens
            # only after a bounded worker slot is acquired, and its socket
            # timeout is active before the peer can send its ClientHello.
            request.settimeout(self._connection_timeout_seconds)
            tls_request = self._tls_context.wrap_socket(
                request, server_side=True, do_handshake_on_connect=False)
            tls_request.settimeout(self._connection_timeout_seconds)
            tls_request.do_handshake()
        except (OSError, ssl.SSLError):
            try:
                self.shutdown_request(tls_request if tls_request is not None else request)
            finally:
                self._finish_worker()
            return
        except BaseException:
            try:
                self.shutdown_request(tls_request if tls_request is not None else request)
            finally:
                self._finish_worker()
            raise
        try:
            super().process_request_thread(tls_request, client_address)
        finally:
            self._finish_worker()

    def _finish_worker(self):
        with self._worker_condition:
            self._active_workers -= 1
            self._worker_condition.notify_all()
        self._worker_slots.release()

    def wait_for_workers(self, timeout_seconds: float) -> bool:
        deadline = time.monotonic() + timeout_seconds
        with self._worker_condition:
            while self._active_workers:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._worker_condition.wait(remaining)
            return True


def _validate_bind_host(bind_host: str, allow_private_bind: bool) -> None:
    """Keep accidental wildcard/public listeners out of TEST_ONLY composition."""
    if bind_host == "localhost":
        return
    try:
        address = ipaddress.ip_address(bind_host)
    except ValueError as error:
        raise ValueError("test_listener_bind_must_be_loopback_or_private_ip") from error
    if not isinstance(address, ipaddress.IPv4Address):
        raise ValueError("test_listener_ipv4_bind_required")
    if address.is_loopback:
        return
    if address.is_unspecified or address.is_multicast or address.is_reserved:
        raise ValueError("test_listener_wildcard_or_reserved_bind_forbidden")
    if (not allow_private_bind or not isinstance(address, ipaddress.IPv4Address)
            or not address.is_private):
        raise ValueError("test_listener_private_bind_requires_explicit_opt_in")


def _trusted_time_ready(value) -> bool:
    return (isinstance(value, datetime) and value.tzinfo is not None
            and value.utcoffset() is not None)


class TestOnlyMtlsListener:
    """Bounded HTTP/1.1 adapter that terminates TLS and dispatches GS-148 APIs.

    Callers must explicitly select ``profile='GS179_TEST_ONLY'``. Requests are
    limited to test-only Hub and Home namespaces, TLS 1.2 client certificates
    are mandatory, and trusted-time readiness must be supplied by the caller.
    Loopback is the default binding. A private IPv4 binding requires an
    explicit ``allow_private_bind=True`` at the call site; wildcard and public
    addresses are rejected. This does not configure or attest network
    isolation. Never use this class for commercial service composition.
    """

    def __init__(self, *, profile: str, api, credentials, ownership_db,
                 server_cert: str | Path, server_key: str | Path,
                 client_ca: str | Path, trusted_time: Callable[[], datetime | None],
                 authority_refresh: Callable[[object, dict], bytes] | None = None,
                 bind_host: str = "127.0.0.1", port: int = 0,
                 max_request_bytes: int = 16_384, timeout_seconds: float = 5.0,
                 available: Callable[[], bool] | None = None,
                 max_concurrent_requests: int = 8,
                 allow_private_bind: bool = False,
                 on_result: Callable[[str, dict, int, object], None] | None = None,
                 drop_response: Callable[[str, dict, int, object], bool] | None = None):
        if profile != "GS179_TEST_ONLY":
            raise ValueError("explicit_gs179_test_only_profile_required")
        if not callable(trusted_time) or not (0 < max_request_bytes <= 16_384):
            raise ValueError("invalid_test_listener_configuration")
        if not callable(available):
            raise ValueError("test_listener_readiness_provider_required")
        if type(max_concurrent_requests) is not int or not 1 <= max_concurrent_requests <= 32:
            raise ValueError("test_listener_concurrency_out_of_bounds")
        if type(port) is not int or not 0 <= port <= 65_535:
            raise ValueError("test_listener_port_out_of_bounds")
        try:
            backend_ready = available()
            trusted_now = trusted_time()
        except Exception as error:
            raise ValueError("test_listener_startup_prerequisite_check_failed") from error
        if backend_ready is not True:
            raise ValueError("test_listener_backend_not_ready")
        if not _trusted_time_ready(trusted_now):
            raise ValueError("test_listener_trusted_time_not_ready")
        if not (0 < timeout_seconds <= 15):
            raise ValueError("invalid_test_listener_timeout")
        _validate_bind_host(bind_host, allow_private_bind)
        for path in (server_cert, server_key, client_ca):
            if not Path(path).is_file():
                raise ValueError("test_listener_tls_material_missing")

        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.minimum_version = tls.maximum_version = ssl.TLSVersion.TLSv1_2
        tls.verify_mode = ssl.CERT_REQUIRED
        tls.load_cert_chain(str(server_cert), str(server_key))
        tls.load_verify_locations(cafile=str(client_ca))

        self.api = api
        self.credentials = credentials
        self.ownership_db = ownership_db
        self.trusted_time = trusted_time
        self.authority_refresh = authority_refresh
        self.max_request_bytes = max_request_bytes
        self.timeout_seconds = timeout_seconds
        self.available = available
        self.on_result = on_result
        self.drop_response = drop_response
        self._started = False
        self._closed = False

        listener = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            server_version = "GS179-TestOnly"
            sys_version = ""

            def log_message(self, _format, *_args):
                # Avoid logging request payloads, credentials, or identifiers.
                return

            def do_POST(self):
                self._dispatch_post()

            def do_GET(self):
                self._send(405, {"error": "method_not_allowed"})

            def do_PUT(self):
                self._send(405, {"error": "method_not_allowed"})

            def do_DELETE(self):
                self._send(405, {"error": "method_not_allowed"})

            def _dispatch_post(self):
                self.close_connection = True
                self.connection.settimeout(listener.timeout_seconds)
                request_path = urlsplit(self.path)
                if request_path.query or request_path.fragment or request_path.path != self.path:
                    self._send(400, {"error": "invalid_request_target"})
                    return
                if self.headers.get_all("Transfer-Encoding"):
                    self._send(400, {"error": "transfer_encoding_not_supported"})
                    return
                lengths = self.headers.get_all("Content-Length") or []
                if len(lengths) != 1 or not re.fullmatch(r"[0-9]{1,6}", lengths[0].strip()):
                    self._send(400, {"error": "invalid_content_length"})
                    return
                size = int(lengths[0])
                if size <= 0 or size > listener.max_request_bytes:
                    self._send(413, {"error": "request_size_out_of_bounds"})
                    return
                if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                    self._send(415, {"error": "application_json_required"})
                    return
                raw = self.rfile.read(size)
                if len(raw) != size:
                    self._send(400, {"error": "incomplete_request_body"})
                    return
                try:
                    body = json.loads(raw.decode("utf-8"))
                    if not isinstance(body, dict):
                        raise ValueError("json_object_required")
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
                    self._send(400, {"error": "invalid_json_object"})
                    return
                if not listener.available():
                    self._send(503, {"error": "test_backend_unavailable"})
                    return
                if not request_path.path.startswith("/v1/homes/") and request_path.path != "/v1/test/authority/refresh":
                    self._send(404, {"error": "route_not_found"})
                    return
                try:
                    # Serialize certificate/registry authorization with this
                    # process's ownership writes. DurableEventCommit still
                    # rechecks Home/epoch/enrollment inside its DB transaction.
                    with listener.api.service.lock:
                        now = listener.trusted_time()
                        context = authorize_cloud_tls_context(
                            self.connection, trusted_now=now,
                            time_readiness=(TimeReadiness.TRUSTED if _trusted_time_ready(now)
                                            else TimeReadiness.UNTRUSTED),
                            credentials=listener.credentials,
                            ownership_db=listener.ownership_db,
                        )
                        if (not is_gs179_test_hub_id(context.permanent_hub_id) or
                                not context.home_id.startswith("gs177-test-")):
                            raise PermissionError("test_only_identity_required")
                        if request_path.path == "/v1/test/authority/refresh":
                            if listener.authority_refresh is None:
                                self._send(404, {"error": "route_not_found"})
                                return
                            status, response = 200, listener.authority_refresh(self.connection, body)
                        else:
                            match = _HOME_ROUTE.fullmatch(request_path.path)
                            if match is None:
                                status, response = 404, {"error": "route_not_found"}
                            elif match.group(1) != context.home_id:
                                raise PermissionError("hub_home_binding_mismatch")
                            else:
                                status_line, response = listener.api.dispatch(
                                    "POST", request_path.path, "", body,
                                    request_context=context,
                                )
                                status = int(status_line.split(" ", 1)[0])
                    if listener.on_result is not None:
                        listener.on_result(request_path.path, body, status, response)
                    if listener.drop_response is not None and listener.drop_response(
                            request_path.path, body, status, response):
                        return
                    self._send(status, response)
                except PermissionError as error:
                    response = {"error": str(error)}
                    if listener.on_result is not None:
                        listener.on_result(request_path.path, body, 403, response)
                    self._send(403, response)
                except (EventCommitConflict, HubDecisionConflict):
                    response = {"error": "conflicting_committed_content"}
                    if listener.on_result is not None:
                        listener.on_result(request_path.path, body, 409, response)
                    self._send(409, response)
                except (ValueError, KeyError, json.JSONDecodeError):
                    response = {"error": "invalid_request"}
                    if listener.on_result is not None:
                        listener.on_result(request_path.path, body, 400, response)
                    self._send(400, response)
                except sqlite3.Error:
                    response = {"error": "durable_store_unavailable"}
                    if listener.on_result is not None:
                        listener.on_result(request_path.path, body, 503, response)
                    self._send(503, response)
                except (TimeoutError, socket.timeout):
                    response = {"error": "request_timeout"}
                    if listener.on_result is not None:
                        listener.on_result(request_path.path, body, 503, response)
                    self._send(503, response)
                except Exception as error:
                    _LOG.warning("TEST_ONLY Hub request failed (%s)", type(error).__name__)
                    response = {"error": "test_listener_unavailable"}
                    if listener.on_result is not None:
                        listener.on_result(request_path.path, body, 503, response)
                    self._send(503, response)

            def _send(self, status: int, payload):
                if isinstance(payload, bytes):
                    encoded, content_type = payload, "application/octet-stream"
                else:
                    encoded, content_type = json.dumps(payload, separators=(",", ":")).encode(), "application/json"
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(encoded)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Connection", "close")
                self.end_headers()
                try:
                    self.wfile.write(encoded)
                except (BrokenPipeError, ConnectionResetError):
                    # Client disconnect after commit is a lost receipt; retry
                    # remains safe through the canonical idempotent EventKey.
                    pass

        self.server = _BoundedThreadingHTTPServer(
            (bind_host, int(port)), Handler,
            max_workers=max_concurrent_requests, tls_context=tls,
            connection_timeout_seconds=timeout_seconds)
        self.origin = f"https://localhost:{self.server.server_port}" if bind_host in {"127.0.0.1", "::1", "localhost"} else f"https://{bind_host}:{self.server.server_port}"
        self._thread: Thread | None = None

    def start(self) -> str:
        if self._closed:
            raise RuntimeError("test_listener_closed")
        if self._started:
            raise RuntimeError("test_listener_already_started")
        self._thread = Thread(target=self.server.serve_forever, name="gs179-test-mtls", daemon=True)
        self._thread.start()
        self._started = True
        return self.origin

    def close(self, *, timeout_seconds: float = 5.0) -> None:
        if self._closed:
            return
        if not (0 < timeout_seconds <= 30):
            raise ValueError("test_listener_shutdown_timeout_out_of_bounds")
        if self._started:
            self.server.shutdown()
            self._thread.join(timeout=timeout_seconds)
            if self._thread.is_alive():
                raise TimeoutError("test_listener_shutdown_timeout")
            self._started = False
        self.server.server_close()
        if not self.server.wait_for_workers(timeout_seconds):
            self._closed = True
            raise TimeoutError("test_listener_request_drain_timeout")
        self._closed = True
