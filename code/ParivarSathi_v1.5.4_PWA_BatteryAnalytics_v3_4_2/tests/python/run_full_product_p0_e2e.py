#!/usr/bin/env python3
"""Deterministic C3/S3 host-stack -> local backend/API -> caregiver PWA E2E.

The production C++ runtime, Hub CloudSync serializer, JsonApi/service, home view
projection and shipped static PWA modules execute. Local GPIO/RF/time and the
test-only local actor binding are explicit boundaries; this is not production
OIDC, the unfinished authenticated Hub commit worker, or physical qualification.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
from pathlib import Path
import subprocess
import sys
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


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *_args):
        pass


class LocalProductStack:
    """Isolated localhost static PWA + real JsonApi with a local test actor."""

    def __init__(self, home_id: str, actor_id: str):
        self.home_id = home_id
        self.actor_id = actor_id
        self.now = 1_700_000_100
        self.service = GharSajagService()
        self.api = JsonApi(self.service, now=lambda: self.now)
        self.app_root = PRODUCT / "app"

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
            # This localhost-only adapter supplies the identity for the prototype
            # JsonApi. It is not exposed by the PWA and is not a production auth layer.
            if not environ.get("HTTP_X_ACTOR_ID"):
                environ = dict(environ)
                environ["HTTP_X_ACTOR_ID"] = self.actor_id
            return self.api(environ, start_response)
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


def request_json(base: str, method: str, path: str, body=None, actor="owner-p0"):
    headers = {"accept": "application/json", "x-actor-id": actor}
    data = None
    if body is not None:
        data = json.dumps(body, separators=(",", ":")).encode()
        headers["content-type"] = "application/json"
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
    if str(cloud_request["event_key"]["event_sequence"]) not in event["event_key"]:
        raise ValueError("CloudSync request EventKey does not match Node event export")

    stack = LocalProductStack("home-p0-e2e", "owner-p0")
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

        # Exercise the exact production S3 CloudSync body first. The current local
        # API intentionally refuses it because the authenticated durable Hub commit
        # middleware/store is not implemented in the production service composition.
        status, rejected = request_json(base, "POST", f"/v1/homes/{stack.home_id}/events", cloud_request)
        check_selected("P0-GAP-001", status == 503 and rejected.get("error") == "durable_event_store_unavailable",
              "production-shaped CloudSync request is fail-closed at the documented GS-148 API seam")

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

        # Exercise the implemented local development event-ingestion route, preserving
        # the immutable C3 EventKey string and original event time from the real C++ stack.
        app_event = {key: event[key] for key in ("event_id", "kind", "location", "occurred_at", "hub_received_at", "uncertainty_s", "payload")}
        stack.now = event["occurred_at"] + 1
        status, accepted = request_json(base, "POST", f"/v1/homes/{stack.home_id}/events", app_event)
        check_selected("P0-E2E-002", status == 202 and accepted.get("event_id") == event["event_key"],
              "real application service ingests the original EventKey-derived activity")
        status, duplicate = request_json(base, "POST", f"/v1/homes/{stack.home_id}/events", app_event)
        check_selected("P0-E2E-003", status == 200 and duplicate.get("duplicate") is True,
              "real application ingestion deduplicates repeated event identity")

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
        check_selected("P0-E2E-007", status == 200 and ids.count(event["event_key"]) == 1 and
              snapshot["latest_activity"]["kind"] == "DOOR_OPEN" and snapshot["door_status"]["unexpected"],
              "caregiver projection preserves exact motion identity, door meaning and latest activity")
        check_selected("P0-E2E-008", len(snapshot.get("active_incidents", [])) == 2 and
              ids.index("p0-call-family-01") < ids.index("p0-daytime-inactivity-01") <
              ids.index("p0-door-open-01") < ids.index(event["event_key"]),
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
            env.update({"P0_E2E_BASE_URL": base, "P0_E2E_EVENT_ID": event["event_key"]})
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
            "product_gaps": ["P0-GAP-001: authenticated production Hub Durable-Commit API/store unavailable (GS-148)"],
            "auth_boundary": "localhost-only X-Actor-Id adapter; production OIDC not claimed",
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
