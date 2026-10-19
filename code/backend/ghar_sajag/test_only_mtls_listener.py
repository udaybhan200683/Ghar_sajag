"""Application-terminated mTLS listener for isolated GS-179 TEST_ONLY use.

This is deliberately not a production server or a Render proxy adapter. The
TLS handshake terminates in this process; Hub identity is derived only from the
verified TLS peer certificate and the current credential/ownership registry.
No HTTP header can create or replace a ``VerifiedHubContext``.
"""
from __future__ import annotations

from datetime import datetime
import json
import logging
from pathlib import Path
import re
import socket
import ssl
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Callable
from urllib.parse import urlsplit

from .cloud_client_identity import TimeReadiness, authorize_cloud_tls_context
from .durable_commit import EventCommitConflict
from .hub_rule_decisions import HubDecisionConflict


_HOME_ROUTE = re.compile(r"^/v1/homes/([A-Za-z0-9_-]{1,80})/(events|node-health|hub-rule-decisions)$")
_LOG = logging.getLogger("ghar_sajag.test_only_mtls_listener")


class TestOnlyMtlsListener:
    """Bounded HTTP/1.1 adapter that terminates TLS and dispatches GS-148 APIs.

    Callers must explicitly select ``profile='GS179_TEST_ONLY'``. Requests are
    limited to test-only Hub and Home namespaces, TLS 1.2 client certificates
    are mandatory, and trusted-time readiness must be supplied by the caller.
    ``bind_host`` may be a private/public address for an independently isolated
    test deployment; never use this class for commercial service composition.
    """

    def __init__(self, *, profile: str, api, credentials, ownership_db,
                 server_cert: str | Path, server_key: str | Path,
                 client_ca: str | Path, trusted_time: Callable[[], datetime | None],
                 authority_refresh: Callable[[object, dict], bytes] | None = None,
                 bind_host: str = "127.0.0.1", port: int = 0,
                 max_request_bytes: int = 16_384, timeout_seconds: float = 5.0,
                 available: Callable[[], bool] | None = None,
                 on_result: Callable[[str, dict, int, object], None] | None = None,
                 drop_response: Callable[[str, dict, int, object], bool] | None = None):
        if profile != "GS179_TEST_ONLY":
            raise ValueError("explicit_gs179_test_only_profile_required")
        if not callable(trusted_time) or not bind_host or not (0 < max_request_bytes <= 16_384):
            raise ValueError("invalid_test_listener_configuration")
        if not (0 < timeout_seconds <= 15):
            raise ValueError("invalid_test_listener_timeout")
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
        self.available = available or (lambda: True)
        self.on_result = on_result
        self.drop_response = drop_response
        self._started = False

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
                            time_readiness=(TimeReadiness.TRUSTED if isinstance(now, datetime)
                                            and now.tzinfo is not None else TimeReadiness.UNTRUSTED),
                            credentials=listener.credentials,
                            ownership_db=listener.ownership_db,
                        )
                        if (not context.permanent_hub_id.startswith("test-hub-") or
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
                    self._send(403, {"error": str(error)})
                except (EventCommitConflict, HubDecisionConflict):
                    self._send(409, {"error": "conflicting_committed_content"})
                except (ValueError, KeyError, json.JSONDecodeError):
                    self._send(400, {"error": "invalid_request"})
                except sqlite3.Error:
                    self._send(503, {"error": "durable_store_unavailable"})
                except (TimeoutError, socket.timeout):
                    self._send(503, {"error": "request_timeout"})
                except Exception as error:
                    _LOG.warning("TEST_ONLY Hub request failed (%s)", type(error).__name__)
                    self._send(503, {"error": "test_listener_unavailable"})

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

        class Server(ThreadingHTTPServer):
            daemon_threads = True
            block_on_close = False

        self.server = Server((bind_host, int(port)), Handler)
        self.server.socket = tls.wrap_socket(self.server.socket, server_side=True)
        self.origin = f"https://localhost:{self.server.server_port}" if bind_host in {"127.0.0.1", "::1", "localhost"} else f"https://{bind_host}:{self.server.server_port}"
        self._thread: Thread | None = None

    def start(self) -> str:
        if self._started:
            raise RuntimeError("test_listener_already_started")
        self._thread = Thread(target=self.server.serve_forever, name="gs179-test-mtls", daemon=True)
        self._thread.start()
        self._started = True
        return self.origin

    def close(self) -> None:
        if self._started:
            self.server.shutdown()
            self._thread.join(timeout=3)
            if self._thread.is_alive():
                raise TimeoutError("test_listener_shutdown_timeout")
            self._started = False
        self.server.server_close()
