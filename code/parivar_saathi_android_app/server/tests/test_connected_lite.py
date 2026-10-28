import json
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from io import BytesIO
from uuid import uuid4
import stat
import secrets
import threading
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools" / "local"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tests" / "support"))
from connected_lite import (HOME_ID, Denied, LiteApi, Store, bootstrap_admin, bootstrap_caregiver,
                            build_app, rotate_password, run_scenario, validate_public_origin,
                            token_digest, password_hash, password_valid)
from gs179_change_login import (DuplicateEmail, LoginChangeError, _atomic_write,
                                _encode_json, update_existing_login,
                                main as change_login_main)


class CaregiverLoginChangeTests(unittest.TestCase):
    """Existing-account-only login update, using SQLite by default or isolated PG on demand."""

    HOME = "gs177-test-login-change"
    OLD_EMAIL = "owner-before@example.org"
    NEW_EMAIL = "owner-after@example.org"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gs179-login-change-")
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.postgres_schema = None
        self.addCleanup(self._cleanup_test_resources)
        os.environ["GS177_LOCAL_TEST"] = "1"
        os.environ["PUBLIC_ORIGIN"] = "https://care.gharsajag.in"
        base_dsn = os.environ.get("GS179_CHANGE_LOGIN_TEST_DSN")
        if base_dsn:
            from gs179_postgres_test_db import IsolatedPostgresSchema
            self.postgres_schema = IsolatedPostgresSchema(base_dsn)
            url = self.postgres_schema.url
        else:
            url = "sqlite:///" + str(self.root / "test.db")
            os.environ["GS177_LOCAL_TEST"] = "1"
        self.store = Store(url)
        self.store.migrate()
        self.old_password = secrets.token_urlsafe(24)
        self.new_password = secrets.token_urlsafe(24)
        self.other_password = secrets.token_urlsafe(24)
        self.second_password = secrets.token_urlsafe(24)
        self.account_id = bootstrap_admin(self.store, self.OLD_EMAIL,
                                          self.old_password, self.HOME)
        self.credentials_path = self.root / "caregiver-login.json"
        self.credentials = {"created_by": "GS179_TEST_ONLY", "profile": "GS179_TEST_ONLY",
                            "email": self.OLD_EMAIL, "password": self.old_password,
                            "home_id": self.HOME}
        self._write_credentials(self.credentials)
        with self.store.connect() as db:
            self.store.sql(db,
                "INSERT INTO lite_runs(run_id,home_id,account_id,scenario_id,status,"
                "simulation_generation,created_at,result_json) VALUES(?,?,?,?,?,?,?,?)",
                ("preserved-run", self.HOME, self.account_id, "motion-room1-visible",
                 "PASS", 1, 1000, '{"timeline":["preserve"]}'))
            self.store.sql(db,
                "INSERT INTO lite_api_limits(account_id,window_start,request_count) VALUES(?,?,?)",
                (self.account_id, 1000, 7))
            # A minimal isolated fixture matching the durable GS-148 event-key table.
            db.execute("CREATE TABLE IF NOT EXISTS households(home_id TEXT PRIMARY KEY)")
            db.execute("CREATE TABLE IF NOT EXISTS events(event_id TEXT PRIMARY KEY,home_id TEXT,payload_json TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS durable_event_commits(home_id TEXT,physical_device_id TEXT,"
                       "logical_node_id TEXT,origin_session_id INTEGER,event_sequence INTEGER,event_id TEXT,"
                       "payload_sha256 TEXT,committed_at INTEGER,PRIMARY KEY(home_id,physical_device_id,"
                       "logical_node_id,origin_session_id,event_sequence))")
            self.store.sql(db, "INSERT INTO households(home_id) VALUES(?)", (self.HOME,))
            self.store.sql(db, "INSERT INTO events(event_id,home_id,payload_json) VALUES(?,?,?)",
                           ("preserved-event", self.HOME, '{"kind":"MOTION"}'))
            self.store.sql(db, "INSERT INTO durable_event_commits(home_id,physical_device_id,logical_node_id,"
                       "origin_session_id,event_sequence,event_id,payload_sha256,committed_at) "
                       "VALUES(?,?,?,?,?,?,?,?)",
                           (self.HOME, "test-node", "bedroom", 1, 1, "preserved-event", "a" * 64, 1001))

    def _cleanup_test_resources(self):
        if self.postgres_schema is not None:
            self.postgres_schema.close()
            self.postgres_schema = None
        self.temp.cleanup()

    def _write_credentials(self, value):
        self.credentials_path.write_text(json.dumps(value), encoding="utf-8")
        self.credentials_path.chmod(0o600)

    def _credentials(self):
        return json.loads(self.credentials_path.read_text(encoding="utf-8"))

    def _add_session(self):
        token = secrets.token_urlsafe(24)
        with self.store.connect() as db:
            self.store.sql(db,
                "INSERT INTO lite_sessions(session_id,account_id,token_hash,issued_at,expires_at,revoked_at) "
                "VALUES(?,?,?,?,?,?)",
                ("session-1", self.account_id, token_digest(token), 1000, 5000, None))
        return token

    def test_changes_existing_account_revokes_sessions_and_preserves_home_and_data(self):
        old_session = self._add_session()
        update_existing_login(self.store, self.credentials_path, self.NEW_EMAIL.upper(),
                              self.new_password, self.new_password)
        updated = self._credentials()
        self.assertEqual(updated["email"], self.NEW_EMAIL)
        self.assertEqual(updated["account_id"], self.account_id)
        self.assertEqual(updated["home_id"], self.HOME)
        self.assertEqual(updated["created_by"], "GS179_TEST_ONLY")
        self.assertEqual(stat.S_IMODE(self.credentials_path.stat().st_mode), 0o600)
        self.assertFalse(self.credentials_path.with_name("caregiver-login.json.pending").exists())
        with self.store.connect() as db:
            account = self.store.sql(db, "SELECT account_id,email,password_hash FROM lite_accounts").fetchall()
            memberships = self.store.sql(db, "SELECT account_id,home_id,role,active,ownership_epoch FROM lite_memberships").fetchall()
            session = self.store.sql(db, "SELECT revoked_at FROM lite_sessions WHERE session_id=?", ("session-1",)).fetchone()
            run = self.store.sql(db, "SELECT run_id,result_json FROM lite_runs WHERE run_id=?", ("preserved-run",)).fetchone()
            committed = self.store.sql(db, "SELECT event_id,payload_sha256 FROM durable_event_commits").fetchall()
        self.assertEqual(account[0]["account_id"], self.account_id)
        self.assertEqual(account[0]["email"], self.NEW_EMAIL)
        self.assertTrue(password_valid(updated["password"], account[0]["password_hash"]))
        self.assertEqual(len(account), 1)
        self.assertEqual(dict(memberships[0]), {"account_id": self.account_id, "home_id": self.HOME,
                                               "role": "ADMIN", "active": True, "ownership_epoch": 1})
        self.assertIsNotNone(session["revoked_at"])
        self.assertEqual(dict(run), {"run_id": "preserved-run", "result_json": '{"timeline":["preserve"]}'})
        self.assertEqual([dict(row) for row in committed], [{"event_id": "preserved-event", "payload_sha256": "a" * 64}])

        api = LiteApi(self.store, clock=lambda: 2000)
        session_env = {"REQUEST_METHOD": "GET", "PATH_INFO": "/lite/v1/me",
                       "CONTENT_LENGTH": "0", "wsgi.input": BytesIO(b""),
                       "HTTP_ORIGIN": "https://care.gharsajag.in",
                       "HTTP_COOKIE": "ps_session=" + old_session,
                       "REMOTE_ADDR": "192.0.2.9"}
        session_status = []
        api(session_env, lambda status, headers: session_status.append(status))
        self.assertEqual(session_status[0], "403 Forbidden")
        def login(email, password):
            body = json.dumps({"email": email, "password": password}).encode()
            env = {"REQUEST_METHOD": "POST", "PATH_INFO": "/lite/v1/auth/login",
                   "CONTENT_LENGTH": str(len(body)), "wsgi.input": BytesIO(body),
                   "HTTP_ORIGIN": "https://care.gharsajag.in", "REMOTE_ADDR": "192.0.2.9"}
            response = []
            api(env, lambda status, headers: response.append(status))
            return response[0]
        os.environ["GS177_LOCAL_TEST"] = "1"
        self.assertEqual(login(self.OLD_EMAIL, self.old_password), "401 Unauthorized")
        self.assertEqual(login(self.NEW_EMAIL, self.new_password), "200 OK")

    def test_invalid_email_short_password_and_confirmation_leave_state_unchanged(self):
        before_digest = hashlib.sha256(self.credentials_path.read_bytes()).hexdigest()
        for email, password, confirmation, error in (
            ("bad-email", self.new_password, self.new_password, "invalid_email"),
            (self.NEW_EMAIL, "x" * 15, "x" * 15, "password_must_be_16_to_256_characters"),
            (self.NEW_EMAIL, self.new_password, self.new_password + "x", "password_confirmation_mismatch"),
        ):
            with self.subTest(error=error), self.assertRaisesRegex(LoginChangeError, error):
                update_existing_login(self.store, self.credentials_path, email, password, confirmation)
        self.assertEqual(hashlib.sha256(self.credentials_path.read_bytes()).hexdigest(), before_digest)
        with self.store.connect() as db:
            row = self.store.sql(db, "SELECT account_id,email FROM lite_accounts").fetchone()
            self.assertEqual(dict(row), {"account_id": self.account_id, "email": self.OLD_EMAIL})
        self.assertFalse(self.credentials_path.with_name("caregiver-login.json.pending").exists())

    def test_duplicate_email_does_not_change_existing_account(self):
        other = bootstrap_caregiver(self.store, "already-used@example.org",
                                    self.other_password, self.HOME)
        before_digest = hashlib.sha256(self.credentials_path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(DuplicateEmail, "email_already_in_use"):
            update_existing_login(self.store, self.credentials_path, "already-used@example.org",
                                  self.new_password, self.new_password)
        self.assertEqual(hashlib.sha256(self.credentials_path.read_bytes()).hexdigest(), before_digest)
        with self.store.connect() as db:
            row = self.store.sql(db, "SELECT account_id,email FROM lite_accounts WHERE account_id=?",
                                 (self.account_id,)).fetchone()
            self.assertEqual(dict(row), {"account_id": self.account_id, "email": self.OLD_EMAIL})
            self.assertTrue(self.store.sql(db, "SELECT 1 FROM lite_accounts WHERE account_id=?", (other,)).fetchone())

    def test_restart_recovers_commit_before_credential_file_promotion(self):
        new_email = self.NEW_EMAIL
        new_password = self.new_password
        target = dict(self.credentials, email=new_email, password=new_password, account_id=self.account_id)
        target_hash = password_hash(new_password)
        pending = {"version": 1, "target": target, "target_password_hash": target_hash,
                   "previous_email": self.OLD_EMAIL, "account_id": self.account_id, "home_id": self.HOME}
        pending_path = self.credentials_path.with_name("caregiver-login.json.pending")
        _atomic_write(pending_path, _encode_json(pending))
        with self.store.connect() as db:
            self.store.sql(db, "UPDATE lite_accounts SET email=?,password_hash=? WHERE account_id=?",
                           (new_email, target_hash, self.account_id))
            recovery_token = secrets.token_urlsafe(24)
            self.store.sql(db, "INSERT INTO lite_sessions(session_id,account_id,token_hash,issued_at,expires_at) "
                           "VALUES(?,?,?,?,?)", ("session-recovery", self.account_id,
                                                 token_digest(recovery_token), 1000, 5000))
            self.store.sql(db, "UPDATE lite_sessions SET revoked_at=? WHERE account_id=? AND revoked_at IS NULL",
                           (2000, self.account_id))
        reopened = Store(self.store.url)
        second_email = "second-change@example.org"
        with self.assertRaisesRegex(LoginChangeError, "previous_login_change_recovered_retry_with_new_values"):
            update_existing_login(reopened, self.credentials_path, second_email,
                                  self.second_password, self.second_password)
        self.assertEqual(self._credentials()["email"], new_email)
        self.assertFalse(pending_path.exists())
        update_existing_login(reopened, self.credentials_path, second_email,
                              self.second_password, self.second_password)
        state = self._credentials()
        self.assertEqual(state["email"], second_email)
        self.assertEqual(state["account_id"], self.account_id)
        self.assertFalse(pending_path.exists())
        with reopened.connect() as db:
            row = self.store.sql(db, "SELECT email FROM lite_accounts WHERE account_id=?", (self.account_id,)).fetchone()
            self.assertEqual(row["email"], second_email)
            self.assertTrue(self.store.sql(db, "SELECT revoked_at FROM lite_sessions WHERE session_id=?",
                                           ("session-recovery",)).fetchone()["revoked_at"])

    def test_interactive_command_uses_hidden_password_prompts(self):
        class Tty:
            @staticmethod
            def isatty():
                return True
        env = {"GS179_LOCAL_SERVER_DSN": self.store.url,
               "GS179_CAREGIVER_CREDENTIALS": str(self.credentials_path),
               "GS177_LOCAL_TEST": "1", "PUBLIC_ORIGIN": "https://care.gharsajag.in"}
        with patch.dict(os.environ, env, clear=False), \
             patch("sys.stdin", Tty()), patch("sys.stderr", Tty()), \
             patch("builtins.input", return_value=self.NEW_EMAIL), \
             patch("getpass.getpass", side_effect=(self.new_password, self.new_password)):
            self.assertEqual(change_login_main(), 0)
        credential = self._credentials()
        self.assertEqual(credential["email"], self.NEW_EMAIL)
        with self.store.connect() as db:
            stored = self.store.sql(db, "SELECT password_hash FROM lite_accounts WHERE account_id=?",
                                    (self.account_id,)).fetchone()
        self.assertTrue(password_valid(credential["password"], stored["password_hash"]))


class PublicOriginPolicyTests(unittest.TestCase):
    def test_private_ipv4_is_only_accepted_by_explicit_gs179_test_profile(self):
        self.assertEqual(
            validate_public_origin("https://192.168.1.6", test_only_lan=True,
                                   monitoring_enabled=True),
            "https://192.168.1.6",
        )
        self.assertEqual(
            validate_public_origin("https://desktop-r1.local", test_only_lan=True,
                                   monitoring_enabled=True),
            "https://desktop-r1.local",
        )
        for origin in (
            "http://192.168.1.6", "https://8.8.8.8", "https://172.15.1.2",
            "https://172.32.1.2", "https://127.0.0.1", "https://192.168.1.6/",
            "https://user@192.168.1.6", "https://192.168.1.6:8443",
            "https://care.gharsajag.in",
            "https://host.other.local", "https://desktop-r1.local:443",
            "https://desktop_r1.local", "https://user@desktop-r1.local",
        ):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                validate_public_origin(origin, test_only_lan=True, monitoring_enabled=True)
        with self.assertRaisesRegex(ValueError, "requires_gs179_test_only_monitoring"):
            validate_public_origin("https://192.168.1.6", test_only_lan=True,
                                   monitoring_enabled=False)

    def test_GS177_API_LAN_ORIGIN_001_ip_pairing_is_an_explicit_test_only_origin_alias(self):
        api = object.__new__(LiteApi)
        api.allowed_origins = frozenset(("https://desktop-r1.local", "https://192.168.1.10"))
        with patch.dict(os.environ, {
            "PUBLIC_ORIGIN": "https://desktop-r1.local",
            "GS179_LOCAL_LAN_TEST_ONLY": "1",
            "GS179_TEST_ONLY_MONITORING": "1",
        }, clear=False):
            api._csrf({"HTTP_ORIGIN": "https://desktop-r1.local"})
            api._csrf({"HTTP_ORIGIN": "https://192.168.1.10"})
            with self.assertRaises(Denied):
                api._csrf({"HTTP_ORIGIN": "https://192.168.1.11"})
        with patch.dict(os.environ, {
            "PUBLIC_ORIGIN": "https://care.gharsajag.in",
            "GS179_LOCAL_LAN_TEST_ONLY": "0",
            "GS179_TEST_ONLY_MONITORING": "0",
            "GS179_TEST_ONLY_ALLOWED_ORIGINS": "https://192.168.1.10",
        }, clear=False):
            api.allowed_origins = frozenset(("https://care.gharsajag.in",))
            with self.assertRaises(Denied):
                api._csrf({"HTTP_ORIGIN": "https://192.168.1.10"})

    def test_GS177_API_LAN_ORIGIN_002_alias_configuration_is_rejected_outside_lan_test_only_mode(self):
        with patch.dict(os.environ, {
            "PUBLIC_ORIGIN": "https://care.gharsajag.in",
            "GS179_LOCAL_LAN_TEST_ONLY": "0",
            "GS179_TEST_ONLY_MONITORING": "0",
            "GS179_TEST_ONLY_ALLOWED_ORIGINS": "https://192.168.1.10",
        }, clear=False):
            with self.assertRaisesRegex(
                    ValueError, "test_only_origin_aliases_require_isolated_gs179_lan_profile"):
                build_app()

    def test_commercial_profile_still_requires_existing_exact_https_dns_origin(self):
        self.assertEqual(validate_public_origin("https://care.gharsajag.in"),
                         "https://care.gharsajag.in")
        for origin in ("https://192.168.1.6", "https://8.8.8.8", "https://127.0.0.1",
                       "https://[::1]"):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                validate_public_origin(origin)


class ConnectedLiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        os.environ['GS177_LOCAL_TEST'] = '1'
        os.environ['PUBLIC_ORIGIN'] = 'https://care.gharsajag.in'
        cls.store = Store('sqlite:///' + cls.temp.name + '/lite.db')
        os.environ['DATABASE_URL'] = 'sqlite:///' + cls.temp.name + '/lite.db'
        cls.api = LiteApi(cls.store, runner=lambda scenario: {
            'status': 'PASS', 'scenario': {'id': scenario}, 'state': {'timeline': [{'kind': 'MOTION', 'event_key': 'synthetic-only'}]},
            'checks': [{'pass': True, 'detail': 'observed'}], 'hardware_evidence': 'NOT_RUN',
            'provenance': 'HOST_SIMULATION_TEST_ONLY',
        }, clock=lambda: 1000)
        bootstrap_admin(cls.store, 'admin@example.org', 'correct-horse-battery-test-177', HOME_ID)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def request(self, method, path, body=None, cookie='', origin='https://care.gharsajag.in'):
        raw = json.dumps(body or {}).encode()
        env = {'REQUEST_METHOD': method, 'PATH_INFO': path, 'CONTENT_LENGTH': str(len(raw)),
               'wsgi.input': BytesIO(raw), 'HTTP_ORIGIN': origin, 'HTTP_COOKIE': cookie,
               'REMOTE_ADDR': '192.0.2.2'}
        headers=[]
        response=json.loads(b''.join(self.api(env, lambda status, h: headers.extend([status,h]))))
        return headers[0], response, dict(headers[1])

    def login(self):
        status, body, headers = self.request('POST','/lite/v1/auth/login',
            {'email':'admin@example.org','password':'correct-horse-battery-test-177'})
        self.assertEqual(status, '200 OK')
        return headers['Set-Cookie'].split(';',1)[0]

    def test_valid_login_session_restore_and_logout(self):
        cookie=self.login()
        self.assertEqual(self.request('GET','/lite/v1/me',cookie=cookie)[1]['role'],'ADMIN')
        overview=self.request('GET',f'/lite/v1/homes/{HOME_ID}/overview',cookie=cookie)[1]
        self.assertIn('TEST_ONLY', str(overview))
        self.assertEqual(overview['physical_status'],'UNAVAILABLE')
        self.assertEqual(overview['physical_status_reason'],'NO_HUB_CLOUDSYNC')
        self.assertEqual(overview['physical_data_contract'],'GS-148_CLOUDSYNC')
        self.assertEqual(overview['source_freshness'],'UNKNOWN')
        self.assertEqual(overview['backend_data_retrieved_at'],1000)
        self.assertNotIn('last_successful_sync',overview)
        devices=self.request('GET',f'/lite/v1/homes/{HOME_ID}/devices',cookie=cookie)[1]
        self.assertEqual(devices['physical_status'],'UNAVAILABLE')
        self.assertEqual(devices['physical_status_reason'],'NO_HUB_CLOUDSYNC')
        routines=self.request('GET',f'/lite/v1/homes/{HOME_ID}/routines',cookie=cookie)[1]
        self.assertEqual(routines['learning_status'],'UNSUPPORTED_MULTI_DAY')
        self.assertEqual(self.request('POST','/lite/v1/auth/logout',cookie=cookie)[0],'200 OK')
        self.assertEqual(self.request('GET','/lite/v1/me',cookie=cookie)[0],'403 Forbidden')

    def test_invalid_credentials_and_csrf(self):
        self.assertEqual(self.request('POST','/lite/v1/auth/login',{'email':'admin@example.org','password':'wrong'})[0],'401 Unauthorized')
        self.assertEqual(self.request('POST','/lite/v1/auth/login',{'email':'admin@example.org','password':'wrong'},origin='https://evil.example.org')[0],'403 Forbidden')
        cloud_event={'event_key':{'home_id':'real-home','device_id':'node-1','boot_id':'boot-1','sequence':1}}
        self.assertEqual(self.request('POST','/v1/homes/real-home/events',cloud_event)[0],'404 Not Found')

    def test_product_permission_denial_is_forbidden_not_service_unavailable(self):
        cookie = self.login()

        class DeniedProductView:
            service = type("Service", (), {"lock": threading.RLock()})()

            @staticmethod
            def dispatch(*_args):
                raise PermissionError("current_home_settings_membership_required")

        with patch.dict(os.environ, {"GS178_LOCAL_TEST": "1"}, clear=False):
            previous = self.api
            self.api = LiteApi(self.store, clock=lambda: 1000,
                               product_view=DeniedProductView())
            try:
                status, payload, _ = self.request(
                    "GET", f"/lite/v1/homes/{HOME_ID}/routine-config", cookie=cookie
                )
            finally:
                self.api = previous
        self.assertEqual(status, "403 Forbidden")
        self.assertEqual(payload, {"error": "not_authorized"})

    def test_authenticated_api_rate_limit_is_bounded_and_recovers_next_window(self):
        home='gs177-test-rate-limit'
        bootstrap_admin(self.store,'rate-limit@example.org','rate-limit-password-177',home)
        status,_,headers=self.request('POST','/lite/v1/auth/login',
            {'email':'rate-limit@example.org','password':'rate-limit-password-177'})
        self.assertEqual(status,'200 OK')
        cookie=headers['Set-Cookie'].split(';',1)[0]
        for _ in range(239):
            status,_,_=self.request('GET',f'/lite/v1/homes/{home}/overview',cookie=cookie)
            self.assertEqual(status,'200 OK')
        status,body,headers=self.request('GET',f'/lite/v1/homes/{home}/overview',cookie=cookie)
        self.assertEqual(status,'429 Too Many Requests')
        self.assertEqual(body['error'],'rate_limited')
        self.assertGreaterEqual(int(headers['Retry-After']),1)
        self.api.clock=lambda:1060
        self.assertEqual(self.request('GET',f'/lite/v1/homes/{home}/overview',cookie=cookie)[0],'200 OK')
        with self.store.connect() as db:
            self.store.sql(db,'DELETE FROM lite_api_limits WHERE account_id=(SELECT account_id FROM lite_accounts WHERE email=?)',
                           ('rate-limit@example.org',))
        self.api.clock=lambda:1000

    def test_simulation_hourly_rate_limit(self):
        cookie=self.login()
        account=self.request('GET','/lite/v1/me',cookie=cookie)[1]['account_id']
        inserted=[]
        try:
            with self.store.connect() as db:
                for _ in range(120):
                    run_id=str(uuid4());inserted.append(run_id)
                    self.store.sql(db,'INSERT INTO lite_runs(run_id,home_id,account_id,scenario_id,status,simulation_generation,created_at,result_json) VALUES(?,?,?,?,?,?,?,?)',
                                   (run_id,HOME_ID,account,'motion-room1-visible','PASS',1,1000,'{}'))
            status,body,headers=self.request('POST',f'/lite/v1/homes/{HOME_ID}/sim/runs',{'scenario_id':'motion-room1-visible'},cookie)
            self.assertEqual(status,'429 Too Many Requests')
            self.assertEqual(body['error'],'simulation_hourly_limit')
            self.assertEqual(headers['Retry-After'],'3600')
        finally:
            with self.store.connect() as db:
                for run_id in inserted:
                    self.store.sql(db,'DELETE FROM lite_runs WHERE run_id=?',(run_id,))

    def test_home_role_epoch_and_frontend_tampering_denied(self):
        cookie=self.login()
        engineering=self.request('GET',f'/lite/v1/homes/{HOME_ID}/engineering',cookie=cookie)
        self.assertEqual(engineering[0],'200 OK')
        self.assertEqual(engineering[1]['gs124_health']['status'],'UNSUPPORTED')
        self.assertEqual(engineering[1]['physical_status'],'UNAVAILABLE')
        self.assertEqual(engineering[1]['physical_status_reason'],'NO_HUB_CLOUDSYNC')
        self.assertEqual(engineering[1]['physical_data_contract'],'GS-148_CLOUDSYNC')
        self.assertEqual(self.request('GET','/lite/v1/homes/other-home/overview',cookie=cookie)[0],'403 Forbidden')
        with self.store.connect() as db:
            self.store.sql(db,"UPDATE lite_memberships SET role='CAREGIVER' WHERE home_id=?",(HOME_ID,))
        self.assertEqual(self.request('GET',f'/lite/v1/homes/{HOME_ID}/sim/catalog',cookie=cookie)[0],'403 Forbidden')
        self.assertEqual(self.request('GET',f'/lite/v1/homes/{HOME_ID}/engineering',cookie=cookie)[0],'403 Forbidden')
        self.assertEqual(self.request('GET',f'/lite/v1/homes/{HOME_ID}/overview',cookie=cookie)[0],'200 OK')
        with self.store.connect() as db:
            self.store.sql(db,"UPDATE lite_memberships SET role='ADMIN',ownership_epoch=2 WHERE home_id=?",(HOME_ID,))
        self.assertEqual(self.request('GET',f'/lite/v1/homes/{HOME_ID}/overview',cookie=cookie)[0],'403 Forbidden')
        with self.store.connect() as db:
            self.store.sql(db,"UPDATE lite_memberships SET ownership_epoch=1 WHERE home_id=?",(HOME_ID,))

    def test_run_persists_after_api_restart_and_input_is_bounded(self):
        cookie=self.login()
        url=f'/lite/v1/homes/{HOME_ID}/sim/runs'
        self.assertEqual(self.request('POST',url,{'scenario_id':'unknown'},cookie)[0],'400 Bad Request')
        status, created, _=self.request('POST',url,{'scenario_id':'motion-room1-visible'},cookie)
        self.assertEqual(status,'201 Created')
        restarted=LiteApi(self.store,runner=self.api.runner,clock=lambda:1000)
        self.api=restarted
        status, loaded, _=self.request('GET',url+'/'+created['run_id'],cookie=cookie)
        self.assertEqual(status,'200 OK')
        self.assertEqual(loaded['result']['provenance'],'HOST_SIMULATION_TEST_ONLY')
        self.assertEqual(loaded['result']['hardware_evidence'],'NOT_RUN')
        self.assertEqual(self.request('POST',url,{'scenario_id':'motion-room1-visible','seed':7},cookie)[0],'400 Bad Request')
        self.assertEqual(self.request('POST',url,{'scenario_id':'x'*17000},cookie)[0],'400 Bad Request')

    def test_saved_run_exposes_test_only_event_and_routine_trace_projections(self):
        cookie=self.login()
        root=f'/lite/v1/homes/{HOME_ID}'
        status,created,_=self.request('POST',root+'/sim/runs',{'scenario_id':'motion-room1-visible'},cookie)
        self.assertEqual(status,'201 Created')
        self.assertEqual(created['trace_id'],f"sim:{created['run_id']}")
        trace=created['result']['trace']
        self.assertFalse(trace['original_event_key_available'])
        self.assertEqual(trace['event_count'],1)
        overview=self.request('GET',root+'/overview',cookie=cookie)[1]
        event=next(item for item in overview['recent_events'] if item['run_id']==created['run_id'])
        self.assertIsNone(event['event_key'])
        self.assertFalse(event['original_event_key_available'])
        self.assertEqual(event['source'],'HOST_SIMULATION_TEST_ONLY')
        self.assertEqual(event['trace_id'],f"sim:{created['run_id']}:1")

        # This catalogue scenario is category=routine even though its ID does not contain
        # "routine", "morning", "inactivity" or "night"; the catalogue is authoritative.
        status,catalogue_routine,_=self.request('POST',root+'/sim/runs',
            {'scenario_id':'door-left-open-two-hour-config-default'},cookie)
        self.assertEqual(status,'201 Created')
        routine_view=self.request('GET',root+'/routines',cookie=cookie)[1]
        self.assertIn(catalogue_routine['run_id'],[item['run_id'] for item in routine_view['runs']])

        saved_runner=self.api.runner
        try:
            self.api.runner=lambda scenario: {
                'status':'PASS','scenario':{'id':scenario,'title':'Missing morning activity','category':'morning'},
                'state':{'timeline':[],'simulation':{'reason':'no_qualifying_evidence'},
                         'incidents':[{'incident_id':'incident-1','kind':'MISSING_MORNING_ACTIVITY',
                                       'home_id':'simulation-home','is_test':False,'state':'OPEN'}]},
                'step_results':[{'index':1,'passed':True,'detail':'scenario rule evaluated'}],
                'checks':[{'pass':True,'detail':'expected missing-activity decision'}],
                'provenance':'HOST_SIMULATION_TEST_ONLY','hardware_evidence':'NOT_RUN'}
            status,morning,_=self.request('POST',root+'/sim/runs',{'scenario_id':'morning-missing-covered'},cookie)
            self.assertEqual(status,'201 Created')
            routines=self.request('GET',root+'/routines',cookie=cookie)[1]
            decision=next(item for item in routines['decisions'] if item['run_id']==morning['run_id'])
            self.assertEqual(decision['decision_reason'],'no_qualifying_evidence')
            self.assertEqual(decision['learning_status'],'UNSUPPORTED_MULTI_DAY')
            self.assertEqual(decision['incident_count'],1)
            self.assertEqual(decision['provenance'],'HOST_SIMULATION_TEST_ONLY')
            incidents=self.request('GET',root+'/incidents',cookie=cookie)[1]['incidents']
            projected=next(item for item in incidents if item['run_id']==morning['run_id'])
            self.assertNotIn('home_id',projected)
            self.assertNotIn('is_test',projected)
            self.assertEqual(projected['provenance'],'HOST_SIMULATION_TEST_ONLY')
        finally:
            self.api.runner=saved_runner

    def test_initial_schema_migration_is_recorded_once_across_restart(self):
        with self.store.connect() as db:
            versions=[row['version'] for row in self.store.sql(db,'SELECT version FROM lite_schema_migrations ORDER BY version').fetchall()]
        self.assertEqual(versions,[1])
        LiteApi(self.store,runner=self.api.runner,clock=lambda:1000)
        with self.store.connect() as db:
            versions=[row['version'] for row in self.store.sql(db,'SELECT version FROM lite_schema_migrations ORDER BY version').fetchall()]
        self.assertEqual(versions,[1])

    def test_wsgi_entrypoint_health_and_database_readiness(self):
        import wsgi
        previous = self.api
        try:
            self.api = wsgi.application
            self.assertEqual(self.request('GET', '/healthz')[0], '200 OK')
            ready = self.request('GET', '/readyz')
            self.assertEqual(ready[0], '200 OK')
            self.assertEqual(ready[1], {'status': 'ready', 'database': 'reachable'})
        finally:
            self.api = previous

    def test_reset_preserves_history_and_increments_fixture_generation(self):
        cookie=self.login()
        root=f'/lite/v1/homes/{HOME_ID}/sim'
        first=self.request('POST',root+'/runs',{'scenario_id':'motion-room1-visible'},cookie)[1]
        reset=self.request('POST',root+'/reset',{},cookie)
        self.assertEqual(reset[0],'200 OK')
        self.assertGreater(reset[1]['simulation_generation'],first['simulation_generation'])
        self.assertEqual(self.request('GET',root+'/runs/'+first['run_id'],cookie=cookie)[0],'200 OK')

    def test_real_existing_lab_executes_through_authenticated_api(self):
        cookie=self.login()
        saved=self.api
        try:
            self.api=LiteApi(self.store,runner=run_scenario,clock=lambda:1000)
            status,created,_=self.request('POST',f'/lite/v1/homes/{HOME_ID}/sim/runs',
                {'scenario_id':'motion-room1-visible'},cookie)
            self.assertEqual(status,'201 Created')
            self.assertEqual(created['status'],'PASS')
            self.assertGreater(len(created['result']['state']['timeline']),0)
            self.assertEqual(created['result']['hardware_evidence'],'NOT_RUN')
            loaded=self.request('GET',f'/lite/v1/homes/{HOME_ID}/sim/runs/{created["run_id"]}',cookie=cookie)[1]
            self.assertEqual(loaded['result']['checks'],created['result']['checks'])
        finally:
            self.api=saved

    def test_session_expiry_and_other_admin_home_isolation(self):
        cookie=self.login()
        second='gs177-test-other-admin'
        bootstrap_admin(self.store,'another-admin@example.org','another-correct-password-177',second)
        self.assertEqual(self.request('GET',f'/lite/v1/homes/{second}/engineering',cookie=cookie)[0],'403 Forbidden')
        saved=self.api
        try:
            self.api=LiteApi(self.store,runner=saved.runner,clock=lambda:50000)
            self.assertEqual(self.request('GET','/lite/v1/me',cookie=cookie)[0],'403 Forbidden')
        finally:
            self.api=saved

    def test_caregiver_login_denied_engineering_and_rotation_revokes(self):
        bootstrap_caregiver(self.store,'caregiver@example.org','caregiver-secret-password-177',HOME_ID)
        status,profile,headers=self.request('POST','/lite/v1/auth/login',
            {'email':'caregiver@example.org','password':'caregiver-secret-password-177'})
        self.assertEqual(status,'200 OK')
        self.assertEqual(profile['role'],'CAREGIVER')
        cookie=headers['Set-Cookie'].split(';',1)[0]
        self.assertEqual(self.request('GET',f'/lite/v1/homes/{HOME_ID}/overview',cookie=cookie)[0],'200 OK')
        self.assertEqual(self.request('GET',f'/lite/v1/homes/{HOME_ID}/engineering',cookie=cookie)[0],'403 Forbidden')
        self.assertEqual(self.request('GET',f'/lite/v1/homes/{HOME_ID}/sim/runs',cookie=cookie)[0],'403 Forbidden')
        rotate_password(self.store,'caregiver@example.org','new-caregiver-password-177')
        self.assertEqual(self.request('GET','/lite/v1/me',cookie=cookie)[0],'403 Forbidden')
        self.assertEqual(self.request('POST','/lite/v1/auth/login',
            {'email':'caregiver@example.org','password':'new-caregiver-password-177'})[0],'200 OK')


if __name__ == '__main__':
    unittest.main()
