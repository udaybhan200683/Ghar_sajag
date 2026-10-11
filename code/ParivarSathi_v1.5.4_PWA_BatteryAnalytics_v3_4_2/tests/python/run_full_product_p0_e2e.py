#!/usr/bin/env python3
"""Deterministic C3/S3 host-stack -> local backend/API -> caregiver PWA E2E.

The production C++ runtime, Hub CloudSync serializer, JsonApi/service, home view
projection and shipped static PWA modules execute. Local GPIO/RF/time and the
test-only local actor binding are explicit boundaries; this is not production
OIDC, the unfinished authenticated Hub commit worker, or physical qualification.
"""
from __future__ import annotations

import argparse
import copy
import io
import json
import mimetypes
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from wsgiref.simple_server import WSGIRequestHandler, make_server

PRODUCT = Path(__file__).resolve().parents[2]
SCENARIO_REGISTRY = PRODUCT.parents[1] / "docs/validation/P0_E2E_SCENARIOS.json"
sys.path.insert(0, str(PRODUCT / "backend"))
from ghar_sajag.http_api import JsonApi  # noqa: E402
from ghar_sajag.service import GharSajagService  # noqa: E402
from ghar_sajag.durable_api import open_durable_event_api  # noqa: E402


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *_args):
        pass


class LocalProductStack:
    """Isolated localhost PWA and real API with durable CloudSync commit.

    Hub auth is represented only by ephemeral local test credentials translated
    by this fixture middleware into an internal trusted context. This does not
    claim the missing production Hub authenticator or OIDC deployment adapter.
    """

    def __init__(self, home_id: str, actor_id: str, cloud_event_key: dict):
        self.home_id = home_id
        self.actor_id = actor_id
        self.now = 1_700_000_100
        self.service = GharSajagService()
        self.dev_api = JsonApi(self.service, now=lambda: self.now)
        self._temp = tempfile.TemporaryDirectory(prefix="ghar-sajag-p0-durable-")
        self.database_path = Path(self._temp.name) / "backend.sqlite"
        self.enrollment = {
            "home_id": home_id, "hub_id": "hub-p0-fixture", "generation": 7,
            "physical_device_id": cloud_event_key["physical_device_id"],
            "logical_node_id": cloud_event_key["logical_node_id"],
        }
        # Fixture-only representation of the trusted enrollment resolver's
        # current revocation state. This exercises JsonApi's production
        # authorize_hub seam; it is not a production registry or issuer.
        self.revoked_nodes: set[tuple[str, str]] = set()
        self.fixture_tokens = {
            secrets.token_urlsafe(32): dict(self.enrollment),
            secrets.token_urlsafe(32): {**self.enrollment, "generation": 6},
            secrets.token_urlsafe(32): {**self.enrollment, "home_id": "another-home"},
            secrets.token_urlsafe(32): {**self.enrollment, "physical_device_id": "wrong-device"},
        }
        self.valid_fixture_token = next(iter(self.fixture_tokens))
        self.durable = self._open_durable_api()
        self.app_root = PRODUCT / "app"

    def _authorize_fixture_hub(self, context: dict, home_id: str, event_key: dict) -> bool:
        claims = context.get("gs.p0_fixture_hub_claims")
        expected = self.enrollment
        return bool(
            isinstance(claims, dict) and isinstance(event_key, dict) and
            context.get("gs.verified_hub") == expected["hub_id"] == claims.get("hub_id") and
            claims.get("home_id") == home_id == expected["home_id"] and
            claims.get("generation") == expected["generation"] and
            claims.get("physical_device_id") == event_key.get("physical_device_id") == expected["physical_device_id"] and
            claims.get("logical_node_id") == event_key.get("logical_node_id") == expected["logical_node_id"] and
            (claims.get("physical_device_id"), claims.get("logical_node_id")) not in self.revoked_nodes
        )

    def _open_durable_api(self):
        return open_durable_event_api(
            self.service, self.database_path, self._authorize_fixture_hub,
            now=lambda: self.now,
        )

    def _provision_test_household(self, home_id: str) -> None:
        """Seed the already-enrolled household row required by the event fixture."""
        with sqlite3.connect(self.database_path) as db:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute(
                "INSERT OR IGNORE INTO households(home_id,display_name,timezone,created_at,updated_at) VALUES(?,?,?,?,?)",
                (home_id, "P0 isolated test household", "Asia/Kolkata", self.now, self.now),
            )
            db.execute(
                "INSERT OR IGNORE INTO caregivers(caregiver_id,display_name,created_at) VALUES(?,?,?)",
                (self.actor_id, "P0 test owner", self.now),
            )
            db.execute(
                "INSERT OR IGNORE INTO household_caregivers(home_id,caregiver_id,role) VALUES(?,?,'OWNER')",
                (home_id, self.actor_id),
            )

    def restart_durable_backend(self) -> None:
        self.durable.close()
        self.durable = self._open_durable_api()

    def close(self) -> None:
        self.durable.close()
        self._temp.cleanup()

    @staticmethod
    def _respond(start_response, status, body, content_type="application/json", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        headers = [("content-type", content_type), ("content-length", str(len(body)))]
        headers.extend(extra or [])
        start_response(status, headers)
        return [body]

    def __call__(self, environ, start_response):
        method = environ.get("REQUEST_METHOD", "GET")
        path = environ.get("PATH_INFO", "/")
        if method == "GET" and path == "/runtime-config.json":
            return self._respond(start_response, "200 OK", json.dumps({
                "home_id": self.home_id,
                "api_base": ".",
            }), extra=[("cache-control", "no-store")])
        if path.startswith("/v1/"):
            # The caregiver adapter is development-only. Hub auth below is a
            # separate fixture credential and never comes from X-Actor-Id.
            environ = dict(environ)
            if not environ.get("HTTP_X_ACTOR_ID"):
                environ["HTTP_X_ACTOR_ID"] = self.actor_id
            body_bytes = b""
            if method == "POST":
                length = int(environ.get("CONTENT_LENGTH") or 0)
                body_bytes = environ.get("wsgi.input", io.BytesIO()).read(length)
                environ["wsgi.input"] = io.BytesIO(body_bytes)
            body = json.loads(body_bytes) if body_bytes else {}
            if method == "POST" and path == "/v1/homes":
                status_line = []
                result = self.dev_api(environ, lambda status, headers: status_line.append(status))
                if status_line and status_line[0].startswith("201"):
                    self._provision_test_household(body["home_id"])
                return self._respond(start_response, status_line[0], b"".join(result))
            if method == "POST" and path.endswith("/events") and "event_key" in body:
                claims = self.fixture_tokens.get(environ.get("HTTP_X_P0_FIXTURE_AUTH", ""))
                if claims is not None:
                    # Only this loopback fixture middleware creates internal
                    # trusted keys; production deployment must supply its own.
                    environ["gs.verified_hub"] = claims["hub_id"]
                    environ["gs.p0_fixture_hub_claims"] = claims
                return self.durable.api(environ, start_response)
            return self.dev_api(environ, start_response)
        if method not in {"GET", "HEAD"}:
            return self._respond(start_response, "405 Method Not Allowed", b"")
        if path in {"/", "/index.html"}:
            candidate = self.app_root / "public" / "index.html"
        elif path.startswith("/src/"):
            candidate = self.app_root / path.lstrip("/")
        else:
            candidate = self.app_root / "public" / path.lstrip("/")
        try:
            resolved = candidate.resolve(strict=True)
            if not resolved.is_file() or not resolved.is_relative_to(self.app_root.resolve()):
                raise FileNotFoundError
            payload = resolved.read_bytes()
        except (OSError, RuntimeError):
            return self._respond(start_response, "404 Not Found", b"not_found", "text/plain")
        content_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
        if resolved.suffix == ".mjs":
            content_type = "text/javascript; charset=utf-8"
        return self._respond(start_response, "200 OK", payload, content_type,
                             [("cache-control", "no-cache")])


def request_json(base: str, method: str, path: str, body=None, actor="owner-p0", hub_token=None):
    headers = {"accept": "application/json", "x-actor-id": actor}
    data = None
    if body is not None:
        data = json.dumps(body, separators=(",", ":")).encode()
        headers["content-type"] = "application/json"
    if hub_token is not None:
        headers["x-p0-fixture-auth"] = hub_token
    req = Request(base + path, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


def check(rows, case_id, condition, detail):
    rows.append({"scenario_id": case_id, "status": "PASS" if condition else "FAIL", "detail": detail})
    if not condition:
        error = AssertionError(f"{case_id}: {detail}")
        error.scenario_results = list(rows)
        raise error


def parse_scenario_selection(value: str | None):
    if value is None:
        return None
    requested = [item.strip() for item in value.split(",")]
    known = {item["scenario_id"] for item in json.loads(SCENARIO_REGISTRY.read_text())["scenarios"]}
    if not requested or any(not item for item in requested) or len(set(requested)) != len(requested):
        raise ValueError("scenario selection must contain unique comma-separated IDs")
    unknown = set(requested) - known
    if unknown:
        raise ValueError("unknown P0 scenarios: " + ",".join(sorted(unknown)))
    return set(requested)


def run(args) -> int:
    event = json.loads(args.event.read_text())
    cloud_request = json.loads(args.cloud_request.read_text())
    if event.get("event_id") != event.get("event_key"):
        raise ValueError("host-stack EventKey identity mismatch")
    if cloud_request.get("event_key", {}).get("event_sequence") is None:
        raise ValueError("production CloudSync request lacks EventKey")
    node_parts = event["event_key"].rsplit(":", 2)
    if len(node_parts) != 3 or node_parts != [
        cloud_request["event_key"]["logical_node_id"],
        str(cloud_request["event_key"]["origin_session_id"]),
        str(cloud_request["event_key"]["event_sequence"]),
    ]:
        raise ValueError("CloudSync request EventKey does not match Node event export")
    if (event.get("kind") != cloud_request.get("event_type") or
        event.get("occurred_at") != cloud_request.get("occurred_at") or
        event.get("hub_received_at") != cloud_request.get("hub_received_at")):
        raise ValueError("CloudSync event meaning/timestamps differ from Node event export")

    stack = LocalProductStack("home-p0-e2e", "owner-p0", cloud_request["event_key"])
    stack.now = event["occurred_at"]
    server = make_server("127.0.0.1", 0, stack, handler_class=QuietHandler)
    base = f"http://127.0.0.1:{server.server_port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    rows = []
    selected = args.selected_scenarios

    def check_selected(case_id, condition, detail):
        if selected is None or case_id in selected:
            check(rows, case_id, condition, detail)

    try:
        status, created = request_json(base, "POST", "/v1/homes", {
            "home_id": stack.home_id, "display_name": "P0 isolated test household",
            "timezone": "Asia/Kolkata", "language": "en-IN",
            "residents": [{"resident_id": "resident-p0", "display_name": "Resident", "consent_active": True}],
        })
        check_selected("P0-E2E-001", status == 201 and created.get("home_id") == stack.home_id,
              "real JsonApi creates isolated household and owner authorization")

        # This is the exact body emitted by production Hub CloudSync. The API runs
        # its real file-backed SQLite transaction. Only the upstream Hub principal
        # is a local ephemeral test credential; no receipt is fabricated.
        event_path = f"/v1/homes/{stack.home_id}/events"
        status, committed = request_json(base, "POST", event_path, cloud_request,
                                         hub_token=stack.valid_fixture_token)
        check_selected("P0-GAP-001", status == 201 and committed.get("status") == "COMMITTED" and
                       committed.get("event_key") == cloud_request["event_key"],
              "production-shaped CloudSync request reaches the real durable API transaction and returns its committed exact EventKey")
        committed_row = stack.durable.db.execute(
            """SELECT e.canonical_event_id FROM events AS e
                 JOIN durable_event_commits AS c ON c.event_id=e.event_id
                WHERE c.home_id=? AND c.physical_device_id=? AND c.logical_node_id=?
                  AND c.origin_session_id=? AND c.event_sequence=?""",
            (stack.home_id, cloud_request["event_key"]["physical_device_id"],
             cloud_request["event_key"]["logical_node_id"], cloud_request["event_key"]["origin_session_id"],
             cloud_request["event_key"]["event_sequence"]),
        ).fetchone()
        if committed_row is None:
            raise AssertionError("durable API returned COMMITTED before exact event row became queryable")
        caregiver_event_id = committed_row[0]
        immutable_row = stack.durable.db.execute(
            "SELECT occurred_at,hub_received_at,event_type,location,payload_json FROM events WHERE home_id=? AND canonical_event_id=?",
            (stack.home_id, caregiver_event_id),
        ).fetchone()
        check_selected("P0-P2D-008", immutable_row is not None and
                       immutable_row[0] == cloud_request["occurred_at"] and
                       immutable_row[1] == cloud_request["hub_received_at"] and
                       immutable_row[2] == cloud_request["event_type"] and
                       immutable_row[3] == cloud_request["location"] and
                       json.loads(immutable_row[4]) == cloud_request["payload"],
              "durable commit preserves the original EventKey payload and Node/Hub timestamps")

        status, unauthorized = request_json(base, "POST", event_path, cloud_request)
        check_selected("P0-P2D-001", status == 403 and unauthorized.get("error") == "hub_not_authorized",
              "client actor identity without trusted Hub context cannot create a durable event")

        wrong_owner_token = next(token for token, claims in stack.fixture_tokens.items()
                                 if claims["home_id"] == "another-home")
        status, wrong_owner = request_json(base, "POST", f"/v1/homes/another-home/events", cloud_request,
                                           hub_token=wrong_owner_token)
        check_selected("P0-P2D-002", status == 403 and wrong_owner.get("error") == "hub_not_authorized",
              "Hub principal cannot commit an event to a different Home")

        stale_token = next(token for token, claims in stack.fixture_tokens.items()
                           if claims["generation"] == stack.enrollment["generation"] - 1)
        status, stale_generation = request_json(base, "POST", event_path, cloud_request,
                                                hub_token=stale_token)
        check_selected("P0-P2D-003", status == 403 and stale_generation.get("error") == "hub_not_authorized",
              "stale Hub enrollment generation cannot write current Home events")

        wrong_identity_token = next(token for token, claims in stack.fixture_tokens.items()
                                    if claims["physical_device_id"] == "wrong-device")
        status, wrong_identity = request_json(base, "POST", event_path, cloud_request,
                                              hub_token=wrong_identity_token)
        check_selected("P0-P2D-004", status == 403 and wrong_identity.get("error") == "hub_not_authorized",
              "Hub authorization is pinned to the enrolled physical and logical Node identity")

        # Model a revocation decision delivered by the trusted authorizer. The
        # API must reject before creating any durable event. The authoritative
        # production revocation registry is not implemented by this fixture.
        revoked_identity = (stack.enrollment["physical_device_id"],
                           stack.enrollment["logical_node_id"])
        stack.revoked_nodes.add(revoked_identity)
        revoked_request = copy.deepcopy(cloud_request)
        revoked_request["event_key"]["event_sequence"] += 1
        status, revoked = request_json(base, "POST", event_path, revoked_request,
                                       hub_token=stack.valid_fixture_token)
        revoked_commit_count = stack.durable.db.execute(
            "SELECT COUNT(*) FROM durable_event_commits WHERE home_id=? AND event_sequence=?",
            (stack.home_id, revoked_request["event_key"]["event_sequence"]),
        ).fetchone()[0]
        check_selected("P0-P2D-009", status == 403 and revoked.get("error") == "hub_not_authorized" and
                       revoked_commit_count == 0,
              "trusted authorizer revocation rejects the Node before durable commit")
        stack.revoked_nodes.remove(revoked_identity)

        # Reopen the same file to model backend restart, then retry the exact
        # request as if the first HTTP response had been lost. COMMITTED comes
        # from the original transaction and the duplicate row is not rewritten.
        stack.restart_durable_backend()
        status, retry = request_json(base, "POST", event_path, cloud_request,
                                     hub_token=stack.valid_fixture_token)
        check_selected("P0-P2D-005", status == 200 and retry.get("status") == "COMMITTED" and
                       retry.get("duplicate") is True,
              "backend restart plus exact retry returns the persisted idempotent COMMITTED receipt")

        conflicting = copy.deepcopy(cloud_request)
        conflicting["location"] = str(conflicting.get("location", "")) + "-conflict"
        status, conflict = request_json(base, "POST", event_path, conflicting,
                                        hub_token=stack.valid_fixture_token)
        committed_count = stack.durable.db.execute(
            "SELECT COUNT(*) FROM durable_event_commits WHERE home_id=?", (stack.home_id,)
        ).fetchone()[0]
        check_selected("P0-P2D-006", status == 409 and conflict.get("error") == "event_key_payload_conflict" and
                       committed_count == 1,
              "conflicting content under the exact EventKey is rejected without replacing durable state")

        # A closed connection simulates unavailable durable storage. It must not
        # generate a successful receipt; then reopen so the remaining scenarios run.
        stack.durable.close()
        status, unavailable = request_json(base, "POST", event_path, cloud_request,
                                           hub_token=stack.valid_fixture_token)
        check_selected("P0-P2D-007", status == 503 and unavailable.get("error") == "event_commit_unavailable",
              "database failure remains fail-closed with no COMMITTED receipt")
        stack.durable = stack._open_durable_api()

        # This explicitly exercised heartbeat is an API freshness input only; it
        # does not claim C3 NodeHealth or ESP-NOW delivery.
        heartbeat_at = event["occurred_at"] + 1
        stack.now = heartbeat_at
        heartbeat = {
            "event_id": "p0-hub-heartbeat-01", "kind": "HUB_HEARTBEAT",
            "location": "hub", "occurred_at": heartbeat_at,
            "hub_received_at": heartbeat_at, "uncertainty_s": 0, "payload": {},
        }
        status, heartbeat_result = request_json(base, "POST", f"/v1/homes/{stack.home_id}/events", heartbeat)
        check_selected("P0-E2E-011", status == 202 and heartbeat_result.get("duplicate") is False,
              "API accepts the implemented Hub heartbeat observation record")

        check_selected("P0-E2E-002", retry.get("event_key") == cloud_request["event_key"] and
                       retry.get("duplicate") is True,
              "Hub retry preserves the structured EventKey and produces an idempotent durable response")
        check_selected("P0-E2E-003", stack.durable.db.execute(
            "SELECT COUNT(*) FROM events WHERE home_id=? AND canonical_event_id=?",
            (stack.home_id, caregiver_event_id),
        ).fetchone()[0] == 1,
              "exact retry yields one durable event visible to caregiver event queries")

        door_at = event["occurred_at"] + 2
        door_event = {
            "event_id": "p0-door-open-01", "kind": "DOOR_OPEN", "location": "main_door",
            "occurred_at": door_at, "hub_received_at": door_at, "uncertainty_s": 0,
            "payload": {"quiet_hours": True, "unexpected": True},
        }
        stack.now = door_at
        status, door_result = request_json(base, "POST", f"/v1/homes/{stack.home_id}/events", door_event)
        check_selected("P0-E2E-004", status == 202 and door_result.get("duplicate") is False,
              "real API stores door event and derives caregiver door status")

        # A concern event exercises actual incident creation; policy scheduling is
        # intentionally outside this test because no production scheduler exists.
        concern_at = event["occurred_at"] + 3
        stack.now = concern_at
        concern = {
            "event_id": "p0-daytime-inactivity-01", "kind": "DAYTIME_INACTIVITY",
            "location": "home", "occurred_at": concern_at, "hub_received_at": concern_at,
            "uncertainty_s": 0, "payload": {"reason": "simulated_covered_window"},
        }
        status, concern_result = request_json(base, "POST", f"/v1/homes/{stack.home_id}/events", concern)
        check_selected("P0-E2E-005", status == 202 and concern_result.get("duplicate") is False,
              "real service evaluates an accepted implemented concern event and creates its effect")

        call_at = event["occurred_at"] + 4
        call_family = {
            "event_id": "p0-call-family-01", "kind": "CALL_FAMILY", "location": "resident",
            "occurred_at": call_at, "hub_received_at": call_at, "uncertainty_s": 0, "payload": {},
        }
        stack.now = call_at
        status, call_result = request_json(base, "POST", f"/v1/homes/{stack.home_id}/events", call_family)
        check_selected("P0-E2E-006", status == 202 and call_result.get("duplicate") is False,
              "resident Call Family event creates implemented caregiver incident state")

        status, snapshot = request_json(base, "GET", f"/v1/homes/{stack.home_id}/snapshot")
        ids = [row["event_id"] for row in snapshot.get("recent_events", [])]
        check_selected("P0-E2E-007", status == 200 and ids.count(caregiver_event_id) == 1 and
              snapshot["latest_activity"]["kind"] == "DOOR_OPEN" and snapshot["door_status"]["unexpected"],
              "caregiver projection includes the durable CloudSync EventKey exactly once alongside door state")
        check_selected("P0-E2E-008", len(snapshot.get("active_incidents", [])) == 2 and
              ids.index("p0-call-family-01") < ids.index("p0-daytime-inactivity-01") <
              ids.index("p0-door-open-01") < ids.index(caregiver_event_id),
              "backend projection preserves resident-action incident state and event chronology")
        check_selected("P0-E2E-012", snapshot.get("hub_reachable") is True and
              snapshot.get("last_hub_at") == heartbeat_at,
              "fresh Hub heartbeat updates Hub liveness independently of resident activity")

        stack.now = heartbeat_at + 191
        status, stale_snapshot = request_json(base, "GET", f"/v1/homes/{stack.home_id}/snapshot")
        check_selected("P0-E2E-013", status == 200 and stale_snapshot["hub_reachable"] is False,
              "Hub freshness expires after the implemented 190-second API lease")
        stack.now = call_at + 10

        status, _ = request_json(base, "GET", f"/v1/homes/{stack.home_id}/snapshot", actor="unrelated-caregiver")
        check_selected("P0-E2E-009", status == 403,
              "real API denies cross-household reads without an authorized role")

        status, second_home = request_json(base, "POST", "/v1/homes", {
            "home_id": "home-p0-isolated-2", "display_name": "Second isolated household",
            "timezone": "Asia/Kolkata", "language": "en-IN",
            "residents": [{"resident_id": "resident-p0-2", "display_name": "Resident 2", "consent_active": True}],
        })
        status, second_snapshot = request_json(base, "GET", f"/v1/homes/{second_home['home_id']}/snapshot")
        check_selected("P0-E2E-014", status == 200 and second_snapshot["recent_events"] == [] and
              second_snapshot["active_incidents"] == [],
              "events and incidents remain isolated between multiple service homes")

        config = {
            "morning": {"start_minute": 360, "end_minute": 660},
            "activity_rules": {
                "quiet_start_minute": 1320, "quiet_end_minute": 360,
                "door_open_timeout_seconds": 300, "daytime_start_minute": 540,
                "daytime_end_minute": 1080, "daytime_inactivity_seconds": 7200,
            },
        }
        status, published = request_json(base, "POST", f"/v1/homes/{stack.home_id}/config", config)
        status2, readback = request_json(base, "GET", f"/v1/homes/{stack.home_id}/config")
        check_selected("P0-E2E-015", status == 202 and status2 == 200 and
              published.get("version") == readback.get("version") == 1 and readback.get("config", {}).get("activity_rules") == config["activity_rules"],
              "implemented desired-policy API validates, versions and returns the same configuration")
        bad_config = {"morning": {}, "activity_rules": {"quiet_start_minute": 1440}}
        status, _ = request_json(base, "POST", f"/v1/homes/{stack.home_id}/config", bad_config)
        check_selected("P0-E2E-016", status == 400,
              "invalid policy is rejected by the real API instead of receiving a false success")

        browser_tests = 0
        if selected is None or "P0-E2E-017" in selected:
            env = os.environ.copy()
            env.update({"P0_E2E_BASE_URL": base, "P0_E2E_EVENT_ID": caregiver_event_id})
            playwright = PRODUCT / "node_modules" / ".bin" / "playwright"
            spec = PRODUCT / "tests" / "playwright" / "p0_full_product.spec.ts"
            completed = subprocess.run(
                [str(playwright), "test", str(spec), "--project=chromium-desktop", "--reporter=line"],
                cwd=PRODUCT, env=env, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=120, check=False,
            )
            args.report.parent.mkdir(parents=True, exist_ok=True)
            (args.report.parent / "p0-playwright.log").write_text(completed.stdout)
            if completed.returncode != 0 or "1 passed" not in completed.stdout or "skipped" in completed.stdout.lower():
                rows.append({"scenario_id": "P0-E2E-017", "status": "FAIL", "detail": "targeted Chromium PWA test did not prove one executed PASS", "exit_code": completed.returncode})
                print(completed.stdout, file=sys.stderr)
                error = AssertionError("targeted Chromium PWA regression failed, skipped or collected zero tests")
                error.scenario_results = list(rows)
                raise error
            rows.append({"scenario_id": "P0-E2E-017", "status": "PASS", "detail": "actual Chromium app reload renders the live API timeline, door state, connectivity and concern", "test_count": 1})
            browser_tests = 1
            print(completed.stdout, end="")

        report = {
            "schema_version": 1, "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PRODUCT.parents[1], text=True).strip(),
            "execution": "PASS" if all(row["status"] == "PASS" for row in rows) else "FAIL",
            "product_vertical_status": "PARTIAL",
            "scenario_results": rows,
            "checks": len(rows), "test_count": browser_tests,
            "selected_scenarios": sorted(selected) if selected is not None else "ALL",
            "product_gaps": ["GS-148: production Hub TLS/credential authenticator and enrollment-generation registry binding are not configured; local test credential only"],
            "auth_boundary": "ephemeral loopback Hub fixture credential is translated by test middleware; production Hub trust and caregiver OIDC are not claimed",
            "physical_qualification": "NOT_RUN",
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        print("\n".join(f"{row['scenario_id']} {row['status']} {row['detail']}" for row in rows))
        if selected is None:
            print(f"P0 E2E EXECUTION PASS scenarios={len(rows)} checks={len(rows)} browser_tests={browser_tests} product_status=PARTIAL physical=NOT_RUN")
        else:
            print(f"P0 E2E SCOPED EXECUTION PASS selected={len(selected)} checks={len(rows)} browser_tests={browser_tests} product_status=PARTIAL physical=NOT_RUN")
        print(f"P0 E2E REPORT {args.report}")
        return 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        stack.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", type=Path, required=True)
    parser.add_argument("--cloud-request", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=Path("build/p0_product_e2e_report.json"))
    parser.add_argument("--scenarios", help="optional comma-separated stable scenario IDs; omitting runs every registered scenario")
    args = parser.parse_args()
    try:
        args.selected_scenarios = parse_scenario_selection(args.scenarios)
        return run(args)
    except (AssertionError, OSError, ValueError, KeyError, json.JSONDecodeError, subprocess.SubprocessError) as error:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({
            "schema_version": 1,
            "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PRODUCT.parents[1], text=True).strip(),
            "execution": "FAIL", "product_vertical_status": "BLOCKED",
            "failure": str(error), "physical_qualification": "NOT_RUN",
            "auth_boundary": "localhost-only X-Actor-Id adapter; production OIDC not claimed",
            "scenario_results": getattr(error, "scenario_results", []),
            "checks": len(getattr(error, "scenario_results", [])),
        }, indent=2) + "\n")
        print(f"P0 E2E FAIL {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
