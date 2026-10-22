"""Isolated real TLS/relational database/caregiver stack for Node-origin E2E."""
import io
import hashlib
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
from ghar_sajag.durable_api import open_durable_event_api, open_postgres_durable_event_api
from ghar_sajag.test_only_mtls_listener import TestOnlyMtlsListener
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


def _test_activity_rules_ar1():
    def location(value):
        encoded=value.encode("ascii")
        return bytes([len(encoded)])+encoded
    return (b"AR1\x1f" + struct.pack(">HHIHHIHHI",60,300,7200,480,1260,10800,
        360,660,14400) + location("bedroom") + location("bathroom") +
        location("kitchen") + struct.pack(">HH",1320,360) +
        location("bathroom") + struct.pack(">H",4) + location("common") +
        struct.pack(">HII",4,300,7200))


class ProductStack:
    def __init__(self, *, postgres_dsn=None, persistent_postgres=False,
                 home_id=None, hub_id=None, caregiver_email=None,
                 caregiver_password=None, reuse_existing_test_home=False,
                 reuse_existing_caregiver=False, start_hub_listener=True):
        self.postgres_schema = None
        self.postgres_url = None
        if persistent_postgres:
            if os.environ.get("GS179_LOCAL_PERSISTENT_POSTGRES") != "1" or not postgres_dsn:
                raise ValueError("explicit_gs179_local_persistent_postgres_guard_required")
            from gs179_postgres_test_db import local_verified_postgres_url
            self.postgres_dsn = postgres_dsn
            self.postgres_url = local_verified_postgres_url(postgres_dsn)
        elif postgres_dsn is not None:
            from gs179_postgres_test_db import IsolatedPostgresSchema
            self.postgres_schema = IsolatedPostgresSchema(postgres_dsn)
            self.postgres_dsn = self.postgres_schema.dsn
            self.postgres_url = self.postgres_schema.url
        else:
            self.postgres_dsn = None
        self.home_id = home_id or HOME
        self.hub_id = hub_id or HUB
        self.caregiver_email = caregiver_email or "owner@gs178.dev"
        if persistent_postgres and not self.home_id.startswith("gs177-test-"):
            raise ValueError("persistent_local_home_must_use_test_only_prefix")
        if reuse_existing_caregiver and (not reuse_existing_test_home or not caregiver_password):
            raise ValueError("existing_caregiver_reuse_requires_existing_persistent_home_and_password")
        if reuse_existing_test_home and (
                not persistent_postgres or self.home_id != HOME or self.hub_id != HUB):
            raise ValueError("existing_local_fixture_reuse_is_limited_to_the_seeded_gs178_home")
        self.temp = tempfile.TemporaryDirectory(prefix="GS178_TEST_ONLY_")
        self.path = Path(self.temp.name)
        self._env = {k: os.environ.get(k) for k in (
            "GS177_LOCAL_TEST", "GS178_LOCAL_TEST", "GS179_TEST_ONLY_MONITORING",
            "GS179_TEST_ONLY_HOME_PREFIX", "PUBLIC_ORIGIN")}
        os.environ.update(GS177_LOCAL_TEST="1", GS178_LOCAL_TEST="1", PUBLIC_ORIGIN="https://caregiver.gs178.dev")
        if self.postgres_schema is not None or persistent_postgres:
            os.environ.update(GS179_TEST_ONLY_MONITORING="1",
                              GS179_TEST_ONLY_HOME_PREFIX="gs177-test-")
        else:
            os.environ.update(GS179_TEST_ONLY_MONITORING="0",
                              GS179_TEST_ONLY_HOME_PREFIX="gs177-test-")
        self.now = int(time.time())
        self.domain_now = self.now
        self.wan_up = True
        self.drop_receipt = False
        self.drop_rule_receipt = False
        self.receipts = []
        self.issuer = TestOnlyIssuer(self.path / "issuer.sqlite")
        key, csr = new_test_csr(self.hub_id)
        self.credential = self.issuer.issue(self.hub_id, csr)
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
        self.lite_store = Store(
            self.postgres_url if self.postgres_url is not None
            else "sqlite:///" + str(self.path / "caregiver.sqlite"))
        self.lite_store.migrate()
        self.password = caregiver_password or secrets.token_urlsafe(32)
        if reuse_existing_caregiver:
            with self.lite_store.connect() as lite_db:
                account = self.lite_store.sql(
                    lite_db,
                    "SELECT a.account_id,m.active,m.ownership_epoch FROM lite_accounts a "
                    "JOIN lite_memberships m ON m.account_id=a.account_id "
                    "WHERE a.email=? AND a.active=? AND m.home_id=? AND m.role='CAREGIVER'",
                    (self.caregiver_email.lower(), True, self.home_id),
                ).fetchone()
                home = self.lite_store.sql(
                    lite_db, "SELECT ownership_epoch,test_only FROM lite_homes WHERE home_id=?",
                    (self.home_id,),
                ).fetchone()
                if (account is None or home is None or not home["test_only"] or
                        not account["active"] or account["ownership_epoch"] != home["ownership_epoch"]):
                    raise ValueError("existing_test_caregiver_session_scope_not_current")
                self.actor = account["account_id"]
        elif reuse_existing_test_home:
            from connected_lite import bootstrap_caregiver
            self.actor = bootstrap_caregiver(
                self.lite_store, self.caregiver_email, self.password, self.home_id)
        else:
            self.actor = bootstrap_admin(
                self.lite_store, self.caregiver_email, self.password, self.home_id)
        self.service.homes.create(self.home_id, "Isolated Node-origin Home", "Etc/UTC", "en-IN", self.actor,
            [Resident("test-resident", "TEST_ONLY", True, self.now)], self.now)
        self.durable = self._open_durable_api()
        db = self.durable.db
        if reuse_existing_test_home:
            if not reuse_existing_caregiver:
                db.execute("INSERT INTO caregivers(caregiver_id,display_name,created_at) VALUES(?,?,?)",
                           (self.actor, "GS-179 local test caregiver", self.now))
                db.execute("INSERT INTO household_caregivers(home_id,caregiver_id,role) VALUES(?,?,'FAMILY')",
                           (self.home_id, self.actor))
            else:
                roster = db.execute(
                    "SELECT 1 FROM household_caregivers WHERE home_id=? AND caregiver_id=? AND active=1",
                    (self.home_id, self.actor),
                ).fetchone()
                if roster is None:
                    raise ValueError("existing_test_caregiver_not_in_current_durable_roster")
            binding = db.execute(
                "SELECT identity_key_fingerprint,state,home_id,installation_epoch "
                "FROM hub_ownership_registry WHERE hub_device_id=?", (self.hub_id,)
            ).fetchone()
            if (binding is None or binding[1] != "ACTIVE" or binding[2] != self.home_id or
                    type(binding[3]) is not int or binding[3] <= 0 or
                    not isinstance(binding[0], str) or len(binding[0]) != 64):
                raise ValueError("seeded_test_hub_current_ownership_not_verified")
            expected_nodes = {"test-c3-" + room: room
                              for room in ("bedroom", "bathroom", "kitchen", "door")}
            enrolled = db.execute(
                "SELECT physical_node_id,logical_node_id,enrollment_generation "
                "FROM node_enrollment_history WHERE hub_device_id=? AND home_id=? AND state='ACTIVE'",
                (self.hub_id, self.home_id),
            ).fetchall()
            observed_nodes = {row[0]: (row[1], row[2]) for row in enrolled}
            if observed_nodes != {node: (room, 1) for node, room in expected_nodes.items()}:
                raise ValueError("seeded_test_node_enrollment_set_mismatch")
            self.identity = VerifiedHubIdentity(
                self.hub_id, binding[0], "TEST_ONLY-existing-local-fixture")
            self.profiles = {node: "configured" for node in expected_nodes}
            operation_prefix = "existing-" + self.home_id
        else:
            db.execute("INSERT INTO households(home_id,display_name,timezone,created_at,updated_at) VALUES(?,?,?,?,?)",
                       (self.home_id, "GS178 TEST_ONLY", "UTC", self.now, self.now))
            db.execute("INSERT INTO caregivers(caregiver_id,display_name,created_at) VALUES(?,?,?)",
                       (self.actor, "Test owner", self.now))
            db.execute("INSERT INTO household_caregivers(home_id,caregiver_id,role) VALUES(?,?,'PRIMARY')",
                       (self.home_id, self.actor))
            owner = self.durable.api.hub_ownership_registry
            if persistent_postgres:
                identity_fingerprint = hashlib.sha256(("GS179_TEST_ONLY:" + self.hub_id).encode()).hexdigest()
                identity_proof = "TEST_ONLY-verified-identity:" + self.hub_id
                operation_prefix = "test-" + self.home_id
            else:
                identity_fingerprint = "a" * 64
                identity_proof = "TEST_ONLY-verified-identity"
                operation_prefix = "test"
            self.identity = VerifiedHubIdentity(self.hub_id, identity_fingerprint, identity_proof)
            owner.register_unclaimed_identity(self.identity, self.now)
            owner.claim_home(self.identity, AuthorizedHomeOperation(
                "test-installer", self.home_id, "CLAIM_HUB", operation_prefix + "-claim"), self.now)
            self.profiles = {}
            for room in ("bedroom", "bathroom", "kitchen", "door"):
                physical = "test-c3-" + room
                node_fingerprint = (hashlib.sha256(("GS179_TEST_ONLY_NODE:" + physical).encode()).hexdigest()
                                    if persistent_postgres else "b" * 64)
                owner.enroll_node(self.identity, AuthorizedHomeOperation(
                    "test-installer", self.home_id, "ENROLL_NODE", operation_prefix + "-enroll-" + room),
                    VerifiedNodeEnrollment(physical, room, 1, node_fingerprint,
                                           "TEST_ONLY-node-proof:" + self.home_id), self.now)
                self.profiles[physical] = "configured"
        if persistent_postgres and not reuse_existing_test_home:
            self.profiles = {"test-c3-" + room: "configured"
                             for room in ("bedroom", "bathroom", "kitchen", "door")}
        self._health()
        self.authority = AuthorityService(self.issuer, db, self.service.lock, enabled=True)
        self.time = SignedTimeService().start()
        self.config_signer = rsa3072()
        self.root_path = self.path / "config-root.der"
        self.root_path.write_bytes(public_der(self.config_signer))
        self.lite = LiteApi(self.lite_store, clock=lambda: self.domain_now,
            product_view=CaregiverProductView(self.service, source="NODE_ORIGIN_HOST_SIM",
                decision_reader=self.durable.api.hub_rule_decisions,
                session_authority_db=(self.durable.db if self.postgres_dsn else None),
                bind_test_only_session=bool(self.postgres_dsn)))
        self.servers = []
        self.mtls_listener = None
        self.hub_origin = self._server(True) if start_hub_listener else None
        self.human_origin = self._server(False)
        self.process = None
        self.trace = []

    def _health(self):
        health = NodeHealthStatusStore(self.durable.db, DeploymentPolicy(NodeHealthPolicy(300), self.profiles))
        self.durable.api.node_health_status = health
        self.service.queries.node_health_status = health

    def _open_durable_api(self):
        if self.postgres_dsn is not None:
            return open_postgres_durable_event_api(
                self.service, self.postgres_dsn, now=lambda: self.domain_now,
                require_registered_ownership=True, enable_test_hub_rule_decisions=True,
                allow_local_unencrypted=True)
        return open_durable_event_api(self.service, self.path / "product.sqlite",
            now=lambda: self.domain_now, require_registered_ownership=True,
            enable_test_hub_rule_decisions=True)

    def _server(self, mtls):
        stack = self
        if mtls:
            def record_result(path, request, status, response):
                if path != "/v1/test/authority/refresh":
                    stack.receipts.append({"path": path, "request": request,
                                           "status": status, "response": response})

            def drop_receipt(path, _request, status, response):
                if (stack.drop_rule_receipt and path.endswith("/hub-rule-decisions")
                        and isinstance(response, dict) and response.get("status") == "COMMITTED"):
                    stack.drop_rule_receipt = False
                    return True
                if (stack.drop_receipt and isinstance(response, dict)
                        and response.get("status") == "COMMITTED"):
                    stack.drop_receipt = False
                    return True
                return False

            self.mtls_listener = TestOnlyMtlsListener(
                profile="GS179_TEST_ONLY", api=self.durable.api,
                credentials=self.issuer, ownership_db=self.durable.db,
                server_cert=self.cert_path, server_key=self.key_path,
                client_ca=self.client_ca,
                trusted_time=lambda: datetime.now(timezone.utc),
                authority_refresh=self.authority.refresh,
                bind_host="127.0.0.1", port=0, max_request_bytes=16_384,
                timeout_seconds=5, available=lambda: stack.wan_up,
                on_result=record_result, drop_response=drop_receipt)
            return self.mtls_listener.start()

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
                    if self.path.startswith("/lite/"):
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
                except (PermissionError, ValueError, KeyError) as error:
                    status = 403 if isinstance(error, PermissionError) else 400
                    payload = json.dumps({"error": str(error)}, separators=(",", ":")).encode()
                    self.send_response(status); self.send_header("Content-Length", str(len(payload))); self.end_headers(); self.wfile.write(payload)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = context.maximum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(self.cert_path, self.key_path)
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
            7:struct.pack(">H",self.time.port), 8:self.time.public_key_der, 9:self.hub_id.encode(),
            10:self.credential.certificate_pem, 11:self.key_pem, 12:self.credential.fingerprint.encode(),
            13:struct.pack(">Q", self.credential.generation), 14:struct.pack(">Q",1),
            15:struct.pack(">Q",self.now+3600), 16:self.authority.public_key_der,
            17:self.home_id.encode(), 18:b"Etc/UTC", 19:_test_activity_rules_ar1(), 20:b"\x00"}
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
        request = Request(self.hub_origin + path, data=json.dumps(body).encode(), method="POST",
                          headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, context=context, timeout=5) as response:
                return response.status, response.read()
        except HTTPError as error:
            try: return error.code, error.read()
            finally: error.close()

    def login(self):
        status, _, headers = self.human("POST", "/lite/v1/auth/login", {"email":self.caregiver_email, "password":self.password})
        if status != 200: raise AssertionError("login failed")
        return headers["Set-Cookie"].split(";", 1)[0]

    def restart_backend(self):
        self.durable.close()
        self.durable = self._open_durable_api()
        self.authority.db = self.durable.db
        self.lite.product_view.decision_reader = self.durable.api.hub_rule_decisions
        self.lite.product_view.session_authority_db = (
            self.durable.db if self.postgres_dsn else None)
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
        if self.mtls_listener is not None:
            self.mtls_listener.close()
        self.time.close(); self.durable.close(); self.issuer.close(); self.temp.cleanup()
        if self.postgres_schema is not None:
            self.postgres_schema.close()
        for key, value in self._env.items():
            if value is None: os.environ.pop(key,None)
            else: os.environ[key]=value


def product_stack_for_test():
    """Select PostgreSQL only for the explicit GS-179 local integration run."""
    if os.environ.get("GS179_TEST_POSTGRES_ONLY") != "1":
        return ProductStack()
    dsn = os.environ.get("GS179_TEST_POSTGRES_DSN")
    if not dsn:
        raise RuntimeError("GS179_TEST_POSTGRES_DSN_required_for_postgres_only_run")
    return ProductStack(postgres_dsn=dsn)
