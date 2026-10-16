"""One-request localhost TLS 1.2 transport for TEST_ONLY CloudSync evidence."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import ssl
import threading

from ghar_sajag.cloud_client_identity import (
    TimeReadiness, authorize_cloud_tls_context,
)


_NOT_GIVEN = object()


def tls_post(*, api, database, credentials, ca_file: Path,
             server_cert: Path, server_key: Path, client_cert: Path | None,
             client_key: Path | None, body: dict, path: str,
             trusted_now: datetime | None = _NOT_GIVEN, hostname: str = "localhost",
             client_ca: Path | None = None, tls13: bool = False,
             before_dispatch=None):
    """Return (HTTP status, JSON body, server error) after a real TLS handshake."""
    result: dict = {}
    if trusted_now is _NOT_GIVEN:
        trusted_now = datetime.now(timezone.utc)
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.minimum_version = server.maximum_version = ssl.TLSVersion.TLSv1_2
    server.verify_mode = ssl.CERT_REQUIRED
    server.load_verify_locations(cafile=str(ca_file))
    server.load_cert_chain(str(server_cert), str(server_key))
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(4)
    port = listener.getsockname()[1]

    def serve():
        try:
            raw, _ = listener.accept()
            with raw, server.wrap_socket(raw, server_side=True) as peer:
                peer.settimeout(4)
                time_readiness = (TimeReadiness.TRUSTED if trusted_now is not None
                                  else TimeReadiness.UNTRUSTED)
                context = authorize_cloud_tls_context(peer, trusted_now=trusted_now,
                    time_readiness=time_readiness, credentials=credentials,
                    ownership_db=database)
                data = b""
                while b"\r\n\r\n" not in data and len(data) <= 4096:
                    chunk = peer.recv(4096)
                    if not chunk: break
                    data += chunk
                header, _, payload = data.partition(b"\r\n\r\n")
                length = None
                for line in header.split(b"\r\n"):
                    if line.lower().startswith(b"content-length:"):
                        length = int(line.split(b":", 1)[1].strip())
                if length is None or length > 2048 or length < 0:
                    raise ValueError("invalid_http_length")
                while len(payload) < length:
                    payload += peer.recv(length - len(payload))
                method, route, _ = header.split(b"\r\n", 1)[0].decode().split(" ", 2)
                if before_dispatch is not None:
                    before_dispatch(context)
                try:
                    status, response = api.dispatch(method, route, "",
                        json.loads(payload[:length]), request_context=context)
                    number = int(status.split(" ", 1)[0])
                except (PermissionError, ValueError, KeyError) as error:
                    number, response = 403, {"error": type(error).__name__}
                encoded = json.dumps(response, separators=(",", ":")).encode()
                peer.sendall(f"HTTP/1.1 {number} RESULT\r\nContent-Length: {len(encoded)}\r\nConnection: close\r\n\r\n".encode() + encoded)
                result.update(status=number, body=response)
        except Exception as error:
            result["server_error"] = type(error).__name__ + ":" + str(error)
        finally:
            listener.close()

    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    client = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    client.minimum_version = client.maximum_version = (
        ssl.TLSVersion.TLSv1_3 if tls13 else ssl.TLSVersion.TLSv1_2)
    client.load_verify_locations(cafile=str(client_ca or ca_file))
    if client_cert is not None and client_key is not None:
        client.load_cert_chain(str(client_cert), str(client_key))
    encoded = json.dumps(body, separators=(",", ":")).encode()
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=4) as raw:
            with client.wrap_socket(raw, server_hostname=hostname) as peer:
                peer.sendall(f"POST {path} HTTP/1.1\r\nHost: localhost\r\nContent-Length: {len(encoded)}\r\n\r\n".encode() + encoded)
                while peer.recv(4096):
                    pass
    except (ssl.SSLError, OSError) as error:
        result["client_error"] = type(error).__name__ + ":" + str(error)
    worker.join(timeout=5)
    if worker.is_alive():
        raise TimeoutError("localhost_TLS_worker_did_not_finish")
    return result
