"""Isolated real TLS/SQLite/caregiver stack for the Node-originated vertical."""
import io
import json
import mimetypes
import os
from pathlib import Path
import secrets
import select
import ssl
import struct
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from cryptography.hazmat.primitives import serialization

from gs40_test_bootstrap import AuthorityService, SignedTimeService, encode_config, public_der, rsa3072
from cloudsync_mtls_certs import make_test_ca, issue_test_cert
from pilot_test_issuer import TestOnlyIssuer, new_test_csr
from ghar_sajag.cloud_client_identity import authorize_cloud_tls_context, TimeReadiness
from ghar_sajag.durable_api import open_durable_event_api
from ghar_sajag.durable_commit import EventCommitConflict
from ghar_sajag.hub_rule_decisions import HubDecisionConflict
from ghar_sajag.caregiver_product import CaregiverProductView
from ghar_sajag.model import Resident
from ghar_sajag.service import GharSajagService
from ghar_sajag.ownership_registry import (VerifiedHubIdentity, AuthorizedHomeOperation,
                                         VerifiedNodeEnrollment)
from ghar_sajag.node_health_policy import DeploymentPolicy, NodeHealthPolicy
from ghar_sajag.node_health_status import NodeHealthStatusStore
from connected_lite import Store, LiteApi, bootstrap_admin

CODE = Path(__file__).resolve().parents[2]
HOME = "gs177-test-product"
HUB = "test-hub-product"


class ProductStack:
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory(prefix="GS178_TEST_ONLY_")
        self.path = Path(self.temp.name)
        self._env = {k: os.environ.get(k) for k in ("GS177_LOCAL_TEST", "GS178_LOCAL_TEST", "PUBLIC_ORIGIN")}
        os.environ.update(GS177_LOCAL_TEST="1", GS178_LOCAL_TEST="1", PUBLIC_ORIGIN="https://caregiver.gs178.dev")
        self.now = int(time.time())
        self.domain_now = self.now
        self.wan_up = True
        self.drop_receipt = False
        self.drop_rule_receipt = False
        self.receipts = []
        self.issuer = TestOnlyIssuer(self.path / "issuer.sqlite")
        key, csr = new_test_csr(HUB)
        self.credential = self.issuer.issue(HUB, csr)
        self.key_pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption())
        server_key, server_ca = make_test_ca("GS178 TEST_ONLY HTTPS")
        self.server_cert = issue_test_cert(server_key, server_ca, "localhost", server=True)
        self.cert_path, self.key_path = self.server_cert.write(self.path, "server")
        self.ca_path = self.path / "server-ca.pem"
        self.ca_path.write_bytes(server_ca.public_bytes(serialization.Encoding.PEM))
        self.client_ca = self.path / "client-ca.pem"
        self.client_ca.write_bytes(self.issuer.authority.public_ca_pem())
        self.service = GharSajagService()
        self.lite_store = Store("sqlite:///" + str(self.path / "caregiver.sqlite"))
        self.lite_store.migrate()
        self.password = secrets.token_urlsafe(32)
        self.actor = bootstrap_admin(self.lite_store, "owner@gs178.dev", self.password, HOME)
        self.service.homes.create(HOME, "Isolated Node-origin Home", "Etc/UTC", "en-IN", self.actor,
            [Resident("test-resident", "TEST_ONLY", True, self.now)], self.now)
        self.durable = open_durable_event_api(self.service, self.path / "product.sqlite",
            now=lambda: self.domain_now, require_registered_ownership=True,
            enable_test_hub_rule_decisions=True)
        db = self.durable.db
        db.execute("INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) VALUES(?,?,?,?,?)",
                   (HOME, "GS178 TEST_ONLY", "UTC", self.now, self.now))
        db.execute("INSERT INTO caregivers(caregiver_id,display_name,created_at) VALUES(?,?,?)", (self.actor, "Test owner", self.now))
        db.execute("INSERT INTO household_caregivers(home_id,caregiver_id,role) VALUES(?,?,'PRIMARY')", (HOME, self.actor))
        owner = self.durable.api.hub_ownership_registry
        self.identity = VerifiedHubIdentity(HUB, "a" * 64, "TEST_ONLY-verified-identity")
        owner.register_unclaimed_identity(self.identity, self.now)
        owner.claim_home(self.identity, AuthorizedHomeOperation("test-installer", HOME, "CLAIM_HUB", "test-claim"), self.now)
        self.profiles = {}
        for room in ("bedroom", "bathroom", "kitchen", "door"):
            physical = "test-c3-" + room
            owner.enroll_node(self.identity, AuthorizedHomeOperation("test-installer", HOME, "ENROLL_NODE", "test-enroll-" + room),
                VerifiedNodeEnrollment(physical, room, 1, "b" * 64, "TEST_ONLY-node-proof"), self.now)
            self.profiles[physical] = "configured"
        self._health()
        self.authority = AuthorityService(self.issuer, db, self.service.lock, enabled=True)
        self.time = SignedTimeService().start()
        self.config_signer = rsa3072()
        self.root_path = self.path / "config-root.der"
        self.root_path.write_bytes(public_der(self.config_signer))
        self.lite = LiteApi(self.lite_store, clock=lambda: self.domain_now,
            product_view=CaregiverProductView(self.service, source="NODE_ORIGIN_HOST_SIM",
                decision_reader=self.durable.api.hub_rule_decisions))
        self.servers = []
        self.hub_origin = self._server(True)
        self.human_origin = self._server(False)
        self.process = None
        self.trace = []

    def _health(self):
        health = NodeHealthStatusStore(self.durable.db, DeploymentPolicy(NodeHealthPolicy(300), self.profiles))
        self.durable.api.node_health_status = health
        self.service.queries.node_health_status = health

    def _server(self, mtls):
        stack = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass
            def do_GET(self): self.handle_request()
            def do_POST(self): self.handle_request()
            def handle_request(self):
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    if size < 0 or size > 16384: raise ValueError("request_too_large")
                    raw = self.rfile.read(size)
                    if mtls:
                        if not stack.wan_up:
                            status, body = 503, {"error": "test_wan_unavailable"}
                        elif self.path == "/v1/test/authority/refresh":
                            status, body = 200, stack.authority.refresh(self.connection, json.loads(raw))
                        else:
                            context = authorize_cloud_tls_context(self.connection,
                                trusted_now=datetime.now(timezone.utc), time_readiness=TimeReadiness.TRUSTED,
                                credentials=stack.issuer, ownership_db=stack.durable.db)
                            status_line, body = stack.durable.api.dispatch(self.command, self.path, "", json.loads(raw), request_context=context)
                            status = int(status_line[:3])
                            stack.receipts.append({"path": self.path, "request": json.loads(raw), "status": status, "response": body})
                            if (stack.drop_rule_receipt and self.path.endswith("/hub-rule-decisions")
                                    and body.get("status") == "COMMITTED"):
                                stack.drop_rule_receipt = False
                                self.close_connection = True
                                return
                            if stack.drop_receipt and body.get("status") == "COMMITTED":
                                stack.drop_receipt = False
                                self.close_connection = True
                                return
                    elif self.path.startswith("/lite/"):
                        env = {"REQUEST_METHOD": self.command, "PATH_INFO": urlsplit(self.path).path,
                               "QUERY_STRING": urlsplit(self.path).query, "CONTENT_LENGTH": str(size),
                               "wsgi.input": io.BytesIO(raw), "HTTP_COOKIE": self.headers.get("Cookie", ""),
                               "HTTP_ORIGIN": self.headers.get("Origin", "")}
                        response = []
                        body = b"".join(stack.lite(env, lambda status, headers: response.append((status, headers))))
                        status_line, headers = response[0]
                        self.send_response(int(status_line[:3]))
                        for name, value in headers: self.send_header(name, value)
                        self.end_headers(); self.wfile.write(body); return
                    else:
                        route = urlsplit(self.path).path
                        if route == "/runtime-config.js":
                            body = b'window.PARIVAR_SAATHI_RUNTIME={mode:"caregiver",backendOrigin:"https://caregiver.gs178.dev",appVersion:"GS178_TEST_ONLY"};'
                        else:
                            root = CODE / "tools/sim/pwa"
                            target = (root / ("index.html" if route == "/" else route.lstrip("/"))).resolve()
                            if not target.is_relative_to(root) or not target.is_file():
                                self.send_error(404); return
                            body = target.read_bytes()
                        status = 200
                    if not isinstance(body, bytes): body = json.dumps(body, separators=(",", ":")).encode()
                    self.send_response(status)
                    content_type = mimetypes.guess_type(self.path)[0] if not mtls and not self.path.startswith("/lite/") else "application/json"
                    self.send_header("Content-Type", content_type or "text/html")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers(); self.wfile.write(body)
                except (PermissionError, ValueError, KeyError, EventCommitConflict, HubDecisionConflict) as error:
                    status = 409 if isinstance(error, (EventCommitConflict, HubDecisionConflict)) else 403 if isinstance(error, PermissionError) else 400
                    if mtls:
                        stack.receipts.append({"path": self.path, "status": status, "error": str(error)})
                    payload = json.dumps({"error": str(error)}, separators=(",", ":")).encode()
                    self.send_response(status); self.send_header("Content-Length", str(len(payload))); self.end_headers(); self.wfile.write(payload)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = context.maximum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(self.cert_path, self.key_path)
        if mtls:
            context.verify_mode = ssl.CERT_REQUIRED
            context.load_verify_locations(cafile=str(self.client_ca))
        server.socket = context.wrap_socket(server.socket, server_side=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start(); self.servers.append((server, thread))
        return f"https://localhost:{server.server_port}"

    def start_node(self, *, transform=None, config_fields=None):
        self.process = subprocess.Popen([str(CODE / "build/gs178_product_host"), str(self.root_path)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        challenge = self.read()
        fields = {1:b"GS178-isolated", 2:secrets.token_urlsafe(16).encode(),
            3:self.hub_origin.encode(), 4:b"localhost", 5:self.ca_path.read_bytes(), 6:b"127.0.0.1",
            7:struct.pack(">H",self.time.port), 8:self.time.public_key_der, 9:HUB.encode(),
            10:self.credential.certificate_pem, 11:self.key_pem, 12:self.credential.fingerprint.encode(),
            13:struct.pack(">Q", self.credential.generation), 14:struct.pack(">Q",1),
            15:struct.pack(">Q",self.now+3600), 16:self.authority.public_key_der}
        fields.update(config_fields or {})
        frame = encode_config(bytes.fromhex(challenge["nonce"]), bytes.fromhex(challenge["public"]), fields, self.config_signer)
        if transform is not None:
            frame = transform(frame)
        self.process.stdin.write(frame.hex()+"\n");self.process.stdin.flush()
        ready = self.read()
        if ready.get("stage") != "CLOUDSYNC_READY": raise AssertionError(ready)
        self.domain_anchor = ready["utc"]
        self.domain_now = ready["utc"]
        return ready

    def read(self):
        if not select.select([self.process.stdout], [], [], 15)[0]:
            raise TimeoutError("bounded Node host response")
        line = self.process.stdout.readline()
        if not line:
            raise AssertionError("Node host exited: " + self.process.stderr.read(4096))
        result = json.loads(line)
        self.trace.append({"host_monotonic_ns":time.monotonic_ns(),"response":result})
        return result

    def command(self, command):
        self.trace.append({"host_monotonic_ns":time.monotonic_ns(),"command":command})
        self.process.stdin.write(command+"\n");self.process.stdin.flush()
        return self.read()

    def human(self, method, path, body=None, cookie=""):
        data = None if body is None else json.dumps(body).encode()
        request = Request(self.human_origin + path, data=data, method=method,
            headers={"Origin": "https://caregiver.gs178.dev", "Content-Type":"application/json", "Cookie":cookie})
        context = ssl.create_default_context(cafile=str(self.ca_path))
        try:
            with urlopen(request, context=context, timeout=5) as response:
                return response.status, json.loads(response.read()), response.headers
        except HTTPError as error:
            try:
                return error.code, json.loads(error.read()), error.headers
            finally:
                error.close()

    def hub_request(self, path, body):
        cert_path, key_path = self.path / "client.pem", self.path / "client.key"
        for path_, data in ((cert_path, self.credential.certificate_pem), (key_path, self.key_pem)):
            fd = os.open(path_, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "wb") as stream: stream.write(data)
        context = ssl.create_default_context(cafile=str(self.ca_path))
        context.minimum_version = context.maximum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(cert_path, key_path)
        request = Request(self.hub_origin + path, data=json.dumps(body).encode(), method="POST")
        try:
            with urlopen(request, context=context, timeout=5) as response:
                return response.status, response.read()
        except HTTPError as error:
            try: return error.code, error.read()
            finally: error.close()

    def login(self):
        status, _, headers = self.human("POST", "/lite/v1/auth/login", {"email":"owner@gs178.dev", "password":self.password})
        if status != 200: raise AssertionError("login failed")
        return headers["Set-Cookie"].split(";", 1)[0]

    def restart_backend(self):
        self.durable.close()
        self.durable = open_durable_event_api(self.service, self.path / "product.sqlite",
            now=lambda: self.domain_now, require_registered_ownership=True,
            enable_test_hub_rule_decisions=True)
        self.authority.db = self.durable.db
        self.lite.product_view.decision_reader = self.durable.api.hub_rule_decisions
        self._health()

    def close(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.stdin.write("quit\n");self.process.stdin.flush()
                try: self.process.wait(timeout=5)
                except subprocess.TimeoutExpired: self.process.kill();self.process.wait()
            for stream in (self.process.stdin,self.process.stdout,self.process.stderr): stream.close()
        for server, thread in self.servers:
            server.shutdown();server.server_close();thread.join(timeout=2)
        self.time.close(); self.durable.close(); self.issuer.close(); self.temp.cleanup()
        for key, value in self._env.items():
            if value is None: os.environ.pop(key,None)
            else: os.environ[key]=value
