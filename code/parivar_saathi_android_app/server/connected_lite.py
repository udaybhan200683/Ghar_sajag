"""GS-177 connected Lite staging API. Synthetic Homes only; never a Hub ingress API.

The public process deliberately does not mount ghar_sajag.http_api.JsonApi or
local_lab.WebLab. Their development actor headers must never become credentials.
"""
from __future__ import annotations

from contextlib import contextmanager
from hashlib import scrypt, sha256
from hmac import compare_digest
from io import BytesIO
import json
import logging
import os
from pathlib import Path
import re
import secrets
import sqlite3
import sys
import time
from urllib.parse import parse_qs
from uuid import uuid4

CODE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE / "tools" / "sim"))
sys.path.insert(0, str(CODE / "validation"))
sys.path.insert(0, str(CODE / "backend"))
from functional_scenarios import _assert_one, load_catalog, DEFAULT_CATALOG
from pwa_frontend_validation import execute_for_frontend, catalog_for_frontend
from ghar_sajag.diagnostic_authorization import (ActorSession, HomeMembership, DiagnosticGrant,
    TrustedAccessSnapshot, DiagnosticAuthorizer)
from ghar_sajag.diagnostics import DiagnosticReadService, DiagnosticLimits
from ghar_sajag.model import Role
from ghar_sajag.human_authentication import (HumanAuthenticationBoundary, IssuerPolicy,
    VerifiedAssertion, CurrentSession, AuthenticationDenied)

SCHEMA = Path(__file__).with_name("connected_lite_schema.sql").read_text()
MIGRATIONS = ((1, SCHEMA),)
COOKIE = "ps_session"
MAX_BODY = 16_384
SESSION_SECONDS = 12 * 3600
API_REQUESTS_PER_MINUTE = 240
HOME_ID = "gs177-test-home"  # Local test fixture only; operator bootstrap allocates unique Homes.
IDENT = re.compile(r"^[a-zA-Z0-9_-]{1,80}$")
ROUTINE_CATEGORIES = frozenset({"routine", "morning", "inactivity"})
logging.basicConfig(level=logging.INFO, format="%(message)s")
LOG = logging.getLogger("parivar_saathi_lite")


def password_hash(password: str, salt: bytes | None = None) -> str:
    if len(password) < 16 or len(password) > 256:
        raise ValueError("password_length_invalid")
    salt = salt or secrets.token_bytes(32)
    return salt.hex() + ":" + scrypt(password.encode(), salt=salt, n=2**15, r=8, p=1, maxmem=128*1024*1024).hex()


def password_valid(password: str, stored: str) -> bool:
    try:
        salt, expected = stored.split(":", 1)
        actual = password_hash(password, bytes.fromhex(salt)).split(":", 1)[1]
        return compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def token_digest(token: str) -> str:
    return sha256(token.encode()).hexdigest()


class Denied(Exception):
    pass


class RateLimited(Exception):
    def __init__(self, retry_after: int):
        super().__init__("rate_limited")
        self.retry_after = retry_after


class Store:
    """One schema for PostgreSQL deployment and explicit local SQLite tests."""
    def __init__(self, url: str):
        self.url = url
        self.local = url.startswith("sqlite:///")
        if not self.local and not url.startswith(("postgres://", "postgresql://")):
            raise ValueError("DATABASE_URL must be PostgreSQL")
        if self.local and os.environ.get("GS177_LOCAL_TEST") != "1":
            raise ValueError("SQLite requires explicit GS177_LOCAL_TEST=1")

    @contextmanager
    def connect(self):
        if self.local:
            db = sqlite3.connect(self.url.removeprefix("sqlite:///"), timeout=10)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
        else:
            import psycopg
            from psycopg.rows import dict_row
            db = psycopg.connect(self.url, row_factory=dict_row)
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def sql(self, db, query: str, args=()):
        return db.execute(query if self.local else query.replace("?", "%s"), args)

    def migrate(self):
        with self.connect() as db:
            if not self.local:
                self.sql(db, "SELECT pg_advisory_xact_lock(?)", (177001,))
            db.execute("CREATE TABLE IF NOT EXISTS lite_schema_migrations (version INTEGER PRIMARY KEY, applied_at BIGINT NOT NULL)")
            applied = self.sql(db, "SELECT COALESCE(MAX(version),0) AS version FROM lite_schema_migrations").fetchone()["version"]
            for version, script in MIGRATIONS:
                if version <= applied:
                    continue
                for statement in script.split(";\n"):
                    if statement.strip():
                        db.execute(statement)
                self.sql(db, "INSERT INTO lite_schema_migrations(version,applied_at) VALUES(?,?)",
                         (version, int(time.time())))


def run_scenario(scenario_id: str):
    """Execute the existing C++/Python lab, never an independently coded engine."""
    from local_lab import Lab
    lab = Lab()
    try:
        payload = execute_for_frontend(lab, scenario_id)
        checks = [_assert_one(payload["state"], a) for a in payload["scenario"]["assertions"]]
        payload["checks"] = [{"pass": ok, "detail": detail} for ok, detail in checks]
        payload["status"] = "PASS" if payload["steps_passed"] and all(ok for ok, _ in checks) else "FAIL"
        payload["provenance"] = "HOST_SIMULATION_TEST_ONLY"
        payload["hardware_evidence"] = "NOT_RUN"
        payload["source_revision"] = os.environ.get("SOURCE_REVISION") or os.environ.get("RENDER_GIT_COMMIT") or "unknown"
        return payload
    finally:
        lab.close()


def _scenario_catalogue():
    return {scenario["id"]: scenario for scenario in load_catalog(DEFAULT_CATALOG)["scenarios"]}


def _run_event_rows(run_id: str, scenario_id: str, created_at: int, result: dict):
    """Project persisted simulator timeline records without claiming product EventKeys."""
    timeline = result.get("state", {}).get("timeline", [])
    provenance = result.get("provenance", "HOST_SIMULATION_TEST_ONLY")
    rows = []
    for index, event in enumerate(timeline):
        if not isinstance(event, dict):
            continue
        rows.append({
            "trace_id": f"sim:{run_id}:{index + 1}",
            "run_id": run_id,
            "scenario_id": scenario_id,
            "event_id": event.get("event_id"),
            "event_key": None,
            "original_event_key_available": False,
            "source": provenance,
            "provenance": provenance,
            "kind": event.get("kind") or event.get("type") or "UNKNOWN",
            "device_id": event.get("device_id"),
            "location": event.get("location"),
            "occurred_at": event.get("occurred_at"),
            "received_at": event.get("received_at"),
            "delayed": bool(event.get("delayed", False)),
            "run_created_at": created_at,
        })
    return rows


def _routine_decision(run_id: str, scenario_id: str, created_at: int, status: str, result: dict,
                      catalogue: dict | None = None):
    """Expose the scenario engine's recorded decision evidence, not a learned baseline."""
    scenario = result.get("scenario") or {}
    scenario_meta = (catalogue or {}).get(scenario_id, {})
    category = scenario.get("category") or scenario_meta.get("category")
    if category not in ROUTINE_CATEGORIES:
        return None
    state = result.get("state", {})
    simulation = state.get("simulation") or {}
    timeline = state.get("timeline", [])
    incidents = state.get("incidents", [])
    return {
        "run_id": run_id,
        "trace_id": f"sim:{run_id}",
        "scenario_id": scenario_id,
        "scenario_title": scenario.get("title") or scenario_meta.get("title") or scenario_id,
        "category": category,
        "evaluated_at": created_at,
        "result": status,
        "decision_reason": simulation.get("reason") or "NOT_EMITTED_BY_SCENARIO",
        "step_results": result.get("step_results", []),
        "checks": result.get("checks", []),
        "event_ids": [event.get("event_id") for event in timeline if isinstance(event, dict) and event.get("event_id")],
        "incident_ids": [incident.get("incident_id") for incident in incidents if isinstance(incident, dict) and incident.get("incident_id")],
        "incident_count": len(incidents),
        "provenance": result.get("provenance", "HOST_SIMULATION_TEST_ONLY"),
        "learning_status": "UNSUPPORTED_MULTI_DAY",
    }


class SyntheticDiagnosticAuthority:
    """Adapter for the existing GS-124 read boundary, only after Lite session lookup.

    The synthetic grant is derived from current ADMIN membership on TEST_ONLY;
    it is never available for real Homes or caller-supplied identity assertions.
    """
    def resolve(self, context, home_id):
        if (not isinstance(context, dict) or not home_id.startswith("gs177-test-") or
                context.get("role") != "ADMIN" or not context.get("test_only") or
                context.get("home_id") != home_id):
            return None
        account_id, epoch = context["account_id"], context["home_epoch"]
        return TrustedAccessSnapshot(
            ActorSession(account_id, context["session_id"], "gs177-test-only-session", context["expires_at"]),
            HomeMembership(home_id, account_id, Role.OWNER, 1, True),
            DiagnosticGrant(home_id, account_id, epoch, 1, 1, context["expires_at"], False), epoch)

    def event_access(self, context, home_id, canonical_event_id):
        return None  # Synthetic lab EventKeys are not product durable-commit rows.


class OpaqueSessionVerifier:
    """Store-backed high-entropy opaque credential verifier for staging sessions."""
    def __init__(self, store, db, issuer):
        self.store, self.db, self.issuer = store, db, issuer

    def verify(self, credential):
        if not isinstance(credential, str) or not re.fullmatch(r"[A-Za-z0-9_-]{40,100}", credential):
            return None
        row = self.store.sql(self.db, """SELECT session_id,account_id,issued_at,expires_at,revoked_at
                               FROM lite_sessions WHERE token_hash=?""", (token_digest(credential),)).fetchone()
        if row is None or row["revoked_at"] is not None:
            return None
        return VerifiedAssertion(self.issuer, row["account_id"], ("parivar-saathi-lite",),
                                 row["session_id"], "session", row["issued_at"],
                                 row["issued_at"], row["expires_at"])


class CurrentSessionDirectory:
    def __init__(self, store, db, issuer):
        self.store, self.db, self.issuer = store, db, issuer

    def current(self, issuer, subject, session_id):
        if issuer != self.issuer:
            return None
        row = self.store.sql(self.db, """SELECT a.active,s.revoked_at FROM lite_sessions s
                               JOIN lite_accounts a ON a.account_id=s.account_id
                               WHERE s.account_id=? AND s.session_id=?""", (subject, session_id)).fetchone()
        if row is None:
            return None
        return CurrentSession(issuer, subject, session_id, subject,
                              bool(row["active"]), row["revoked_at"] is None)


class LiteApi:
    def __init__(self, store: Store, runner=run_scenario, clock=time.time, product_view=None):
        self.store, self.runner, self.clock = store, runner, clock
        if product_view is not None and (not store.local or os.environ.get("GS178_LOCAL_TEST") != "1"):
            raise ValueError("product_composition_requires_explicit_isolated_test")
        self.product_view = product_view
        self.diagnostics = DiagnosticReadService(
            DiagnosticAuthorizer(SyntheticDiagnosticAuthority()), clock=lambda: int(self.clock()),
            limits=DiagnosticLimits(20, 65536, 4, 3600, 60))
        self.store.migrate()

    def __call__(self, env, respond):
        started = time.monotonic()
        headers = [("Content-Type", "application/json; charset=utf-8"), ("Cache-Control", "no-store"),
                   ("X-Content-Type-Options", "nosniff"), ("Referrer-Policy", "no-referrer")]
        try:
            status, payload, extra = self.dispatch(env)
            headers += extra
        except Denied:
            status, payload = "403 Forbidden", {"error": "not_authorized"}
        except RateLimited as error:
            status, payload = "429 Too Many Requests", {"error": "rate_limited"}
            headers.append(("Retry-After", str(error.retry_after)))
        except ValueError as error:
            status, payload = "400 Bad Request", {"error": str(error)}
        except Exception:
            LOG.exception(json.dumps({"event": "request_exception", "path": env.get("PATH_INFO", "")[:120]}))
            status, payload = "503 Service Unavailable", {"error": "service_unavailable"}
        LOG.info(json.dumps({"event": "request", "method": env.get("REQUEST_METHOD", "")[:8],
                             "path": env.get("PATH_INFO", "")[:120], "status": int(status[:3]),
                             "duration_ms": round((time.monotonic()-started)*1000)}))
        encoded = json.dumps(payload, separators=(", ", ":")).encode()
        respond(status, headers + [("Content-Length", str(len(encoded)))])
        return [encoded]

    def _body(self, env):
        length = int(env.get("CONTENT_LENGTH") or 0)
        if length < 0 or length > MAX_BODY:
            raise ValueError("request_too_large")
        if not length:
            return {}
        body = json.loads(env["wsgi.input"].read(length))
        if type(body) is not dict:
            raise ValueError("invalid_json_object")
        return body

    def _csrf(self, env):
        origin = env.get("HTTP_ORIGIN", "")
        expected = os.environ.get("PUBLIC_ORIGIN", "")
        if not expected or origin != expected:
            raise Denied()

    def _session(self, db, env, home_id=None, admin=False):
        cookie = env.get("HTTP_COOKIE", "")
        tokens = [part.strip().split("=", 1)[1] for part in cookie.split(";")
                  if part.strip().startswith(COOKIE + "=") and "=" in part]
        if len(tokens) != 1 or not re.fullmatch(r"[A-Za-z0-9_-]{40,100}", tokens[0]):
            raise Denied()
        issuer = os.environ.get("PUBLIC_ORIGIN", "")
        try:
            boundary = HumanAuthenticationBoundary(
                IssuerPolicy(issuer, "parivar-saathi-lite", "session"),
                OpaqueSessionVerifier(self.store, db, issuer),
                CurrentSessionDirectory(self.store, db, issuer),
                lambda: int(self.clock()))
            actor = boundary.authenticate(tokens[0])
        except (AuthenticationDenied, ValueError) as error:
            raise Denied() from error
        query = """SELECT s.session_id,s.expires_at,s.revoked_at,a.account_id,a.email,a.active,
                   m.home_id,m.role,m.active AS member_active,m.ownership_epoch,h.test_only,h.ownership_epoch AS home_epoch
                   FROM lite_sessions s JOIN lite_accounts a ON a.account_id=s.account_id
                   JOIN lite_memberships m ON m.account_id=a.account_id
                   JOIN lite_homes h ON h.home_id=m.home_id
                   WHERE s.session_id=? AND a.account_id=?"""
        if home_id is not None:
            query += " AND m.home_id=?"
        query += " ORDER BY m.home_id LIMIT 1"
        params = (actor.session_id, actor.actor_id) if home_id is None else (actor.session_id, actor.actor_id, home_id)
        row = self.store.sql(db, query, params).fetchone()
        if not row or not row["active"] or not row["member_active"] or row["revoked_at"] is not None or row["expires_at"] <= int(self.clock()) or row["ownership_epoch"] != row["home_epoch"]:
            raise Denied()
        now = int(self.clock())
        window = now - now % 60
        count = self.store.sql(db, """INSERT INTO lite_api_limits(account_id,window_start,request_count)
                         VALUES(?,?,1) ON CONFLICT(account_id) DO UPDATE SET
                         request_count=CASE WHEN lite_api_limits.window_start=excluded.window_start
                                            THEN lite_api_limits.request_count+1 ELSE 1 END,
                         window_start=excluded.window_start RETURNING request_count""",
                               (row["account_id"], window)).fetchone()["request_count"]
        if count > API_REQUESTS_PER_MINUTE:
            raise RateLimited(max(1, 60 - (now - window)))
        if admin and (row["role"] != "ADMIN" or not row["test_only"]):
            raise Denied()
        return row

    def _login(self, db, env, body):
        email, password = body.get("email"), body.get("password")
        if type(email) is not str or type(password) is not str or len(email) > 254 or len(password) > 256:
            raise Denied()
        email = email.strip().lower()
        now = int(self.clock())
        # Persistent account and source-IP throttles; no user enumeration.
        ip = env.get("REMOTE_ADDR", "unknown")[:100]
        key = token_digest(email + "|" + ip)
        attempts = self.store.sql(db, "SELECT failures,blocked_until FROM lite_login_limits WHERE key_hash=?", (key,)).fetchone()
        if attempts and attempts["blocked_until"] > now:
            raise Denied()
        row = self.store.sql(db, "SELECT account_id,password_hash,active FROM lite_accounts WHERE email=?", (email,)).fetchone()
        valid = password_valid(password, row["password_hash"] if row else DUMMY_HASH)
        if not row or not row["active"] or not valid:
            failures = (attempts["failures"] if attempts else 0) + 1
            self.store.sql(db, """INSERT INTO lite_login_limits(key_hash,failures,blocked_until) VALUES(?,?,?)
                          ON CONFLICT(key_hash) DO UPDATE SET failures=excluded.failures,blocked_until=excluded.blocked_until""",
                           (key, failures, now + 900 if failures >= 5 else 0))
            return "401 Unauthorized", {"error": "invalid_credentials"}, []
        self.store.sql(db, "DELETE FROM lite_login_limits WHERE key_hash=?", (key,))
        token = secrets.token_urlsafe(48)
        session_id = str(uuid4())
        self.store.sql(db, "INSERT INTO lite_sessions(session_id,account_id,token_hash,issued_at,expires_at) VALUES(?,?,?,?,?)",
                       (session_id, row["account_id"], token_digest(token), now, now + SESSION_SECONDS))
        session = self._session(db, {"HTTP_COOKIE": COOKIE + "=" + token})
        return "200 OK", self._profile(session), [("Set-Cookie", f"{COOKIE}={token}; Max-Age={SESSION_SECONDS}; Path=/; Secure; HttpOnly; SameSite=Strict")]

    @staticmethod
    def _profile(row):
        return {"account_id": row["account_id"], "email": row["email"], "home_id": row["home_id"],
                "role": row["role"], "test_only": bool(row["test_only"]), "expires_at": row["expires_at"],
                "backend_revision": os.environ.get("SOURCE_REVISION") or os.environ.get("RENDER_GIT_COMMIT") or "unknown"}

    def dispatch(self, env):
        method, path = env.get("REQUEST_METHOD", "GET"), env.get("PATH_INFO", "/")
        now = int(self.clock())
        if method == "GET" and path == "/healthz":
            return "200 OK", {"status": "ok", "service": "parivar-saathi-lite"}, []
        if method == "GET" and path == "/readyz":
            with self.store.connect() as db:
                self.store.sql(db, "SELECT 1")
            return "200 OK", {"status": "ready", "database": "reachable"}, []
        if method not in {"GET", "POST"}:
            return "405 Method Not Allowed", {"error": "method_not_allowed"}, []
        if method == "POST":
            self._csrf(env)
            body = self._body(env)
        else:
            body = {}
        # Connected Lite mounts only the isolated TEST_ONLY API. The existing
        # GS-148 /v1 durable event contract remains a separate composition that
        # requires its verified Hub identity/epoch middleware; never copy Hub
        # events into lite_runs or accept the development actor-header adapter.
        with self.store.connect() as db:
            if method == "POST" and path == "/lite/v1/auth/login":
                return self._login(db, env, body)
            if method == "POST" and path == "/lite/v1/auth/logout":
                session = self._session(db, env)
                self.store.sql(db, "UPDATE lite_sessions SET revoked_at=? WHERE session_id=?", (now, session["session_id"]))
                return "200 OK", {"status": "logged_out"}, [("Set-Cookie", f"{COOKIE}=; Max-Age=0; Path=/; Secure; HttpOnly; SameSite=Strict")]
            if method == "GET" and path == "/lite/v1/me":
                return "200 OK", self._profile(self._session(db, env)), []
            match = re.fullmatch(r"/lite/v1/homes/([A-Za-z0-9_-]{1,80})(?:/(.*))?", path)
            if not match:
                return "404 Not Found", {"error": "route_not_found"}, []
            home, sub = match.group(1), match.group(2) or ""
            session = self._session(db, env, home, admin=sub.startswith(("sim", "engineering")))
            if not home.startswith("gs177-test-") or not session["test_only"]:
                raise Denied()  # Real Home authority/consent is not yet composed.
            if self.product_view is not None:
                with self.product_view.service.lock:
                    result = self.product_view.dispatch(session, home, sub, method, body, now)
                if result is not None:
                    return "200 OK", result, []
            if method == "GET" and sub == "overview":
                rows = self.store.sql(db, "SELECT run_id,scenario_id,status,created_at FROM lite_runs WHERE home_id=? ORDER BY created_at DESC,run_id DESC LIMIT 20", (home,)).fetchall()
                saved = self.store.sql(db, "SELECT run_id,scenario_id,status,created_at,result_json FROM lite_runs WHERE home_id=? ORDER BY created_at DESC,run_id DESC LIMIT 20", (home,)).fetchall()
                catalogue = _scenario_catalogue()
                decoded = [(row, json.loads(row["result_json"])) for row in saved]
                latest_events = [event for row, result in decoded
                                 for event in _run_event_rows(row["run_id"], row["scenario_id"], row["created_at"], result)]
                # The simulator timeline order is authoritative within a run; run creation time orders runs.
                latest_events.sort(key=lambda event: (event["run_created_at"], str(event.get("occurred_at") or "")), reverse=True)
                decisions = []
                for row, result in decoded:
                    decision = _routine_decision(row["run_id"], row["scenario_id"], row["created_at"], row["status"], result, catalogue)
                    if decision:
                        decisions.append(decision)
                latest = decoded[0][1] if decoded else None
                timeline = latest.get("state", {}).get("timeline", []) if latest else []
                return "200 OK", {"home_id": home, "test_only": True, "source": "HOST_SIMULATION_TEST_ONLY",
                                  "physical_status": "UNAVAILABLE",
                                  "physical_status_reason": "NO_HUB_CLOUDSYNC",
                                  "physical_data_contract": "GS-148_CLOUDSYNC",
                                  "monitoring": "UNKNOWN", "source_freshness": "UNKNOWN",
                                  "backend_data_retrieved_at": now,
                                  "latest_simulated_event": timeline[-1] if timeline else None,
                                  "recent_events": latest_events[:100],
                                  "routine_decisions": decisions[:20],
                                  "runs": [dict(r) for r in rows]}, []
            if method == "GET" and sub == "devices":
                latest = self.store.sql(db, "SELECT result_json FROM lite_runs WHERE home_id=? ORDER BY created_at DESC LIMIT 1", (home,)).fetchone()
                devices = json.loads(latest["result_json"]).get("state", {}).get("devices", []) if latest else []
                return "200 OK", {"home_id": home, "test_only": True, "devices": devices,
                                  "provenance": "HOST_SIMULATION_TEST_ONLY",
                                  "physical_status": "UNAVAILABLE",
                                  "physical_status_reason": "NO_HUB_CLOUDSYNC",
                                  "physical_data_contract": "GS-148_CLOUDSYNC"}, []
            if method == "GET" and sub in {"reports", "routines", "incidents"}:
                periods = {"day": 86400, "week": 7*86400, "month": 31*86400}
                query = parse_qs(env.get("QUERY_STRING", ""))
                period = query.get("period", ["week"])[0]
                if sub == "reports" and (set(query) - {"period"} or period not in periods):
                    raise ValueError("invalid_report_period")
                rows = self.store.sql(db, "SELECT run_id,scenario_id,status,created_at,result_json FROM lite_runs WHERE home_id=? AND created_at>=? ORDER BY created_at DESC LIMIT 100", (home, now-periods.get(period, 31*86400))).fetchall()
                runs = [{"run_id": r["run_id"], "scenario_id": r["scenario_id"], "status": r["status"], "created_at": r["created_at"]} for r in rows]
                if sub == "reports":
                    counts = {status: sum(r["status"] == status for r in runs) for status in ("PASS", "FAIL", "BLOCKED", "NOT_RUN")}
                    event_count = sum(len(json.loads(r["result_json"]).get("state", {}).get("timeline", [])) for r in rows)
                    incident_count = sum(len(json.loads(r["result_json"]).get("state", {}).get("incidents", [])) for r in rows)
                    return "200 OK", {"home_id": home, "test_only": True, "run_count": len(runs), "runs": runs,
                                      "period": period, "outcomes": counts, "event_count": event_count,
                                      "incident_count": incident_count, "source": "SAVED_SIMULATION_RUNS_ONLY"}, []
                if sub == "routines":
                    catalogue = _scenario_catalogue()
                    decisions = []
                    related = []
                    for row in rows:
                        result = json.loads(row["result_json"])
                        decision = _routine_decision(row["run_id"], row["scenario_id"], row["created_at"], row["status"], result, catalogue)
                        if decision:
                            decisions.append(decision)
                            related.append({"run_id": row["run_id"], "scenario_id": row["scenario_id"],
                                            "status": row["status"], "created_at": row["created_at"],
                                            "trace_id": decision["trace_id"], "category": decision["category"]})
                    return "200 OK", {"home_id": home, "test_only": True, "learning_status": "UNSUPPORTED_MULTI_DAY",
                                      "source": "HOST_SIMULATION_TEST_ONLY", "runs": related,
                                      "decisions": decisions}, []
                incidents = []
                for row in rows:
                    for incident in json.loads(row["result_json"]).get("state", {}).get("incidents", []):
                        # The lab fixture's internal home_id/is_test fields are not household authority.
                        incidents.append({"run_id": row["run_id"], "trace_id": f"sim:{row['run_id']}",
                                          "incident_id": incident.get("incident_id"),
                                          "kind": incident.get("kind") or incident.get("type") or "UNKNOWN",
                                          "state": incident.get("state") or incident.get("status") or "SIMULATED",
                                          "created_at": incident.get("created_at") or row["created_at"],
                                          "provenance": "HOST_SIMULATION_TEST_ONLY"})
                return "200 OK", {"home_id": home, "test_only": True, "incidents": incidents[:100]}, []
            if method == "GET" and sub == "sim/catalog":
                return "200 OK", catalog_for_frontend(), []
            if method == "POST" and sub == "sim/reset":
                if body:
                    raise ValueError("reset_accepts_no_parameters")
                self.store.sql(db, "UPDATE lite_homes SET simulation_generation=simulation_generation+1 WHERE home_id=?", (home,))
                generation = self.store.sql(db, "SELECT simulation_generation FROM lite_homes WHERE home_id=?", (home,)).fetchone()["simulation_generation"]
                return "200 OK", {"home_id": home, "simulation_generation": generation,
                                  "state": "FRESH_PER_RUN", "saved_history": "PRESERVED"}, []
            if method == "POST" and sub == "sim/runs":
                scenario_id = body.get("scenario_id")
                catalogue = load_catalog(DEFAULT_CATALOG)["scenarios"]
                if type(scenario_id) is not str or scenario_id not in {s["id"] for s in catalogue}:
                    raise ValueError("unsupported_scenario")
                if body.keys() - {"scenario_id"}:
                    raise ValueError("unsupported_simulation_parameters")
                # The PostgreSQL advisory lock bounds shared lab output and CPU across workers.
                if not self.store.local:
                    self.store.sql(db, "SELECT pg_advisory_xact_lock(177)")
                recent = self.store.sql(db, "SELECT COUNT(*) AS total FROM lite_runs WHERE home_id=? AND created_at>=?",
                                        (home, now-3600)).fetchone()["total"]
                if recent >= 120:
                    return "429 Too Many Requests", {"error": "simulation_hourly_limit"}, [("Retry-After", "3600")]
                result = self.runner(scenario_id)
                run_id = str(uuid4())
                status = result.get("status", "BLOCKED")
                generation = self.store.sql(db, "SELECT simulation_generation FROM lite_homes WHERE home_id=?", (home,)).fetchone()["simulation_generation"]
                result["trace"] = {"trace_id": f"sim:{run_id}", "run_id": run_id,
                                    "created_at": now, "provenance": result.get("provenance", "HOST_SIMULATION_TEST_ONLY"),
                                    "original_event_key_available": False,
                                    "event_count": len(result.get("state", {}).get("timeline", []))}
                self.store.sql(db, "INSERT INTO lite_runs(run_id,home_id,account_id,scenario_id,status,simulation_generation,created_at,result_json) VALUES(?,?,?,?,?,?,?,?)",
                               (run_id, home, session["account_id"], scenario_id, status, generation, now, json.dumps(result)))
                return "201 Created", {"run_id": run_id, "trace_id": result["trace"]["trace_id"], "status": status,
                                        "simulation_generation": generation, "result": result}, []
            if method == "GET" and sub == "sim/runs":
                rows = self.store.sql(db, "SELECT run_id,scenario_id,status,created_at FROM lite_runs WHERE home_id=? ORDER BY created_at DESC LIMIT 100", (home,)).fetchall()
                return "200 OK", {"runs": [dict(r) for r in rows]}, []
            run = re.fullmatch(r"sim/runs/([0-9a-f-]{36})", sub)
            if method == "GET" and run:
                row = self.store.sql(db, "SELECT run_id,scenario_id,status,created_at,result_json FROM lite_runs WHERE home_id=? AND run_id=?", (home, run.group(1))).fetchone()
                if not row:
                    return "404 Not Found", {"error": "run_not_found"}, []
                return "200 OK", {"run_id": row["run_id"], "scenario_id": row["scenario_id"], "status": row["status"],
                                  "created_at": row["created_at"], "result": json.loads(row["result_json"])}, []
            if method == "GET" and sub == "engineering":
                rows = self.store.sql(db, "SELECT run_id,scenario_id,status,created_at FROM lite_runs WHERE home_id=? ORDER BY created_at DESC LIMIT 30", (home,)).fetchall()
                # Reuse GS-124's current authorization and read-only health projection.
                # The absent target technical source correctly reports UNSUPPORTED.
                projection = self.diagnostics.read(dict(session), home, "health")
                if projection.status != 200:
                    raise Denied()
                return "200 OK", {"home_id": home, "test_only": True,
                                  "gs124_health": projection.body, "hardware_evidence": "UNKNOWN",
                                  "physical_status": "UNAVAILABLE",
                                  "physical_status_reason": "NO_HUB_CLOUDSYNC",
                                  "physical_data_contract": "GS-148_CLOUDSYNC",
                                  "source_revision": os.environ.get("SOURCE_REVISION") or os.environ.get("RENDER_GIT_COMMIT") or "unknown",
                                  "runs": [dict(r) for r in rows]}, []
            return "404 Not Found", {"error": "route_not_found"}, []


DUMMY_HASH = password_hash("unused-dummy-password-for-timing")


def bootstrap_admin(store: Store, email: str, password: str, home_id: str | None = None):
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
        raise ValueError("invalid_email")
    digest = password_hash(password)
    home_id = home_id or "gs177-test-" + uuid4().hex[:20]
    if not IDENT.fullmatch(home_id) or not home_id.startswith("gs177-test-"):
        raise ValueError("invalid_test_home")
    with store.connect() as db:
        store.sql(db, "INSERT INTO lite_homes(home_id,test_only,ownership_epoch) VALUES(?,?,?)", (home_id, True, 1))
        account_id = str(uuid4())
        store.sql(db, "INSERT INTO lite_accounts(account_id,email,password_hash,active) VALUES(?,?,?,?)", (account_id, email.lower(), digest, True))
        store.sql(db, "INSERT INTO lite_memberships(account_id,home_id,role,active,ownership_epoch) VALUES(?,?,?,?,?)", (account_id, home_id, "ADMIN", True, 1))
    return account_id


def bootstrap_caregiver(store: Store, email: str, password: str, home_id: str):
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
        raise ValueError("invalid_email")
    digest = password_hash(password)
    with store.connect() as db:
        home = store.sql(db, "SELECT test_only,ownership_epoch FROM lite_homes WHERE home_id=?", (home_id,)).fetchone()
        if not home or not home["test_only"]:
            raise ValueError("test_home_required")
        account_id = str(uuid4())
        store.sql(db, "INSERT INTO lite_accounts(account_id,email,password_hash,active) VALUES(?,?,?,?)",
                  (account_id, email.lower(), digest, True))
        store.sql(db, "INSERT INTO lite_memberships(account_id,home_id,role,active,ownership_epoch) VALUES(?,?,?,?,?)",
                  (account_id, home_id, "CAREGIVER", True, home["ownership_epoch"]))
    return account_id


def rotate_password(store: Store, email: str, password: str):
    digest = password_hash(password)
    with store.connect() as db:
        account = store.sql(db, "SELECT account_id FROM lite_accounts WHERE email=? AND active=?",
                            (email.lower(), True)).fetchone()
        if not account:
            raise ValueError("active_account_required")
        store.sql(db, "UPDATE lite_accounts SET password_hash=? WHERE account_id=?", (digest, account["account_id"]))
        store.sql(db, "UPDATE lite_sessions SET revoked_at=? WHERE account_id=? AND revoked_at IS NULL",
                  (int(time.time()), account["account_id"]))


def build_app():
    origin = os.environ.get("PUBLIC_ORIGIN", "")
    if not re.fullmatch(r"https://[a-z0-9](?:[a-z0-9.-]{1,251}[a-z0-9])", origin) or ".." in origin:
        raise ValueError("PUBLIC_ORIGIN must be the exact approved HTTPS origin")
    return LiteApi(Store(os.environ["DATABASE_URL"]))


if __name__ == "__main__":
    import getpass
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["bootstrap-admin", "bootstrap-caregiver", "rotate-password", "migrate"])
    parser.add_argument("--email")
    parser.add_argument("--home-id")
    args = parser.parse_args()
    store = Store(os.environ["DATABASE_URL"])
    store.migrate()
    if args.command in {"bootstrap-admin", "bootstrap-caregiver", "rotate-password"}:
        if not args.email:
            parser.error("--email required")
        password = getpass.getpass("New account password (min 16 chars): ")
        confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation:
            parser.error("password mismatch")
        if args.command == "bootstrap-admin":
            print("account_id=" + bootstrap_admin(store, args.email, password))
        elif args.command == "bootstrap-caregiver":
            if not args.home_id:
                parser.error("--home-id required")
            print("account_id=" + bootstrap_caregiver(store, args.email, password, args.home_id))
        else:
            rotate_password(store, args.email, password)
            print("password_rotated_sessions_revoked")
    else:
        print("schema_ready")
