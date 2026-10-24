#!/usr/bin/env python3
"""Run the bundled caregiver PWA against verified laptop HTTPS/PostgreSQL state."""
from __future__ import annotations

import http.cookiejar
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import urllib.request

from gs179_verified_endpoint import VerifiedAddressHTTPSHandler, windows_wifi_ipv4

ROOT = Path(__file__).resolve().parents[3]


def main() -> int:
    import psycopg

    origin = os.environ.get("PUBLIC_ORIGIN", "")
    dsn = os.environ.get("GS179_LOCAL_SERVER_DSN", "")
    credentials_path = Path(os.environ.get(
        "GS179_CAREGIVER_CREDENTIALS",
        str(Path.home() / ".local/state/ghar-sajag/gs179-laptop/caregiver-login.json"),
    )).expanduser()
    ca = Path(os.environ.get("GS179_ANDROID_CA", "")).expanduser()
    if not origin.startswith("https://") or not dsn or not ca.is_file():
        print("BLOCKED local_https_database_or_ca_configuration_missing")
        return 2
    if not credentials_path.is_file() or credentials_path.stat().st_mode & 0o777 != 0o600:
        print("BLOCKED owner_only_caregiver_credentials_missing_or_permissions_invalid")
        return 2
    credentials = json.loads(credentials_path.read_text(encoding="utf-8"))
    home = credentials.get("home_id")
    if credentials.get("profile") != "GS179_TEST_ONLY" or home != "gs177-test-product":
        print("BLOCKED expected_gs179_test_only_home_required")
        return 2

    with psycopg.connect(dsn, connect_timeout=5) as db:
        rows = db.execute(
            """SELECT physical_device_id,logical_node_id,origin_session_id,event_sequence
                 FROM durable_event_commits WHERE home_id=%s ORDER BY committed_at""",
            (home,),
        ).fetchall()
    if len(rows) != 1:
        print("BLOCKED expected_exactly_one_durable_node_event_for_local_fixture")
        return 2
    event_key = {
        "physical_device_id": rows[0][0],
        "logical_node_id": rows[0][1],
        "origin_session_id": rows[0][2],
        "event_sequence": rows[0][3],
    }
    if event_key["physical_device_id"] != "test-c3-bedroom" or event_key["logical_node_id"] != "bedroom":
        print("BLOCKED durable_event_does_not_match_expected_test_node")
        return 2

    context = ssl.create_default_context(cafile=str(ca))
    # Windows advertises the .local name to the phone, but WSL need not have
    # mDNS. Route to the current Windows Wi-Fi address while preserving the
    # original hostname for SNI and certificate verification.
    try:
        route_ipv4 = windows_wifi_ipv4(origin)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"BLOCKED verified_windows_wifi_route_unavailable: {type(error).__name__}")
        return 2
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(VerifiedAddressHTTPSHandler(context, route_ipv4),
                                         urllib.request.HTTPCookieProcessor(jar))

    def call(path: str, method: str = "GET", body: dict | None = None):
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            origin + path, data=data, method=method,
            headers={"Origin": origin, "Content-Type": "application/json"},
        )
        with opener.open(request, timeout=8) as response:
            return response.status, json.loads(response.read())

    status, profile = call("/lite/v1/auth/login", "POST", {
        "email": credentials["email"], "password": credentials["password"],
    })
    if status != 200 or profile.get("home_id") != home or profile.get("test_only") is not True:
        print("BLOCKED caregiver_login_or_home_binding_failed")
        return 2
    status, overview = call(f"/lite/v1/homes/{home}/overview")
    devices_status, devices = call(f"/lite/v1/homes/{home}/devices")
    if status != 200 or devices_status != 200:
        print("FAIL caregiver_projection_http_failure")
        return 1
    event = next((item for item in overview.get("recent_events", [])
                  if item.get("event_key") == event_key), None)
    node = next((item for item in devices.get("devices", [])
                 if item.get("physical_node_id") == event_key["physical_device_id"]), None)
    if event is None:
        print("FAIL caregiver_timeline_does_not_match_postgres_event_key")
        return 1
    freshness = overview.get("source_freshness")
    monitoring = overview.get("monitoring")
    if (overview.get("source") != "AUTHENTICATED_GS148_TEST_ONLY" or
            freshness not in {"CURRENT", "STALE", "UNKNOWN"} or node is None or
            (freshness == "CURRENT" and
             (monitoring != "COVERED" or node.get("status") != "ONLINE" or
              node.get("coverage") != "COVERED")) or
            (freshness != "CURRENT" and monitoring != "UNKNOWN")):
        print("FAIL caregiver_projection_source_or_freshness_contract_mismatch")
        return 2

    # Revoke this preflight login before the browser creates its own session.
    call("/lite/v1/auth/logout", "POST", {})

    config = {
        "origin": origin,
        "email": credentials["email"],
        "password": credentials["password"],
        "homeId": home,
        "eventKey": event_key,
        "eventKind": event.get("kind"),
        "eventDisplayKind": {
            "MOTION": "Motion recorded",
            "DOOR_OPEN": "Door opened",
            "DOOR_CLOSED": "Door closed",
            "OK_PRESSED": "I Am OK check-in",
            "CALL_FAMILY": "Call Family request",
        }.get(event.get("kind"), event.get("kind") or "Recorded activity"),
        "room": event_key["logical_node_id"],
        "physicalNodeId": event_key["physical_device_id"],
        "eventOrigin": "HOST_SIM · TEST_ONLY",
        "sourceFreshness": freshness,
        "monitoring": monitoring,
        "nodeStatus": node.get("status"),
        "nodeCoverage": node.get("coverage"),
        "role": profile.get("role"),
        "testOnly": profile.get("test_only"),
        "gs179LocalLanTestOnly": True,
        "routeIpv4": route_ipv4,
    }
    env = os.environ.copy()
    env["NODE_EXTRA_CA_CERTS"] = str(ca)
    result = subprocess.run(
        ["node", str(ROOT / "code/tools/local/gs179_laptop_caregiver_browser.cjs")],
        input=json.dumps(config), text=True, capture_output=True, timeout=60, env=env,
        cwd=ROOT / "code",
    )
    if result.returncode != 0:
        print(result.stderr.strip() or "FAIL caregiver_browser_validation_failed")
        return result.returncode or 1
    print(result.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
