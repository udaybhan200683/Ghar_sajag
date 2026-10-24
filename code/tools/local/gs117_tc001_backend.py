"""Read-only PostgreSQL and authorized caregiver projection for physical TC-001."""
from __future__ import annotations

import http.cookiejar
import json
import os
from pathlib import Path
import ssl
import sys
import urllib.request

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from ghar_sajag.identity_namespaces import is_gs179_test_node_id
from gs179_verified_endpoint import (
    VerifiedAddressHTTPSHandler,
    wsl_ipv4,
    wsl_local_backend_origin,
)

HOME = "gs177-test-product"


def run(request: dict) -> dict:
    dsn = os.environ["GS179_LOCAL_SERVER_DSN"]
    origin = os.environ["PUBLIC_ORIGIN"]
    ca = Path(os.environ["GS179_ANDROID_CA"])
    credentials_path = Path.home() / ".local/state/ghar-sajag/gs179-laptop/caregiver-login.json"
    if (not ca.is_file() or not credentials_path.is_file() or
            credentials_path.stat().st_mode & 0o777 != 0o600):
        raise ValueError("GS179_owner_only_trust_or_login_unavailable")
    credentials = json.loads(credentials_path.read_text())
    if credentials.get("profile") != "GS179_TEST_ONLY" or credentials.get("home_id") != HOME:
        raise ValueError("GS179_TEST_ONLY_Home_binding_missing")
    action = request.get("action")
    if request.get("home_id") != HOME or (action != "readiness" and
                                           request.get("logical_node_id") != "bedroom"):
        raise ValueError("TC001_wrong_Home_or_room")
    device = request.get("physical_device_id")
    if action != "readiness" and not is_gs179_test_node_id(device):
        raise ValueError("TC001_unapproved_test_device_id")
    with psycopg.connect(dsn, connect_timeout=5) as db:
        if action == "readiness":
            db.execute("SELECT 1").fetchone()
            rows = []
        elif action == "baseline":
            rows = db.execute(
                """SELECT origin_session_id,event_sequence FROM durable_event_commits
                   WHERE home_id=%s AND physical_device_id=%s AND logical_node_id=%s""",
                (HOME, device, "bedroom"),
            ).fetchall()
            owner = db.execute(
                """SELECT home_id,installation_epoch,state FROM hub_ownership_registry
                   WHERE hub_device_id=%s""", (request["hub_id"],),
            ).fetchone()
            enrollment = db.execute(
                """SELECT enrollment_generation FROM node_enrollment_history
                   WHERE hub_device_id=%s AND home_id=%s AND physical_node_id=%s
                     AND logical_node_id=%s AND state='ACTIVE'""",
                (request["hub_id"], HOME, device, "bedroom"),
            ).fetchall()
            return {"count": len(rows), "keys": [[int(a), int(b)] for a, b in rows],
                    "authority_ready": bool(owner and owner == (
                        HOME, request["installation_epoch"], "ACTIVE") and len(enrollment) == 1),
                    "enrollment_generation": int(enrollment[0][0]) if len(enrollment) == 1 else None}
        elif action != "event":
            raise ValueError("TC001_unknown_read_action")
        else:
            session = int(request["origin_session_id"])
            sequence = int(request["event_sequence"])
            rows = db.execute(
                """SELECT event_id,committed_at,hub_device_id,ownership_epoch,
                          node_enrollment_generation FROM durable_event_commits
                   WHERE home_id=%s AND physical_device_id=%s AND logical_node_id=%s
                     AND origin_session_id=%s AND event_sequence=%s""",
                (HOME, device, "bedroom", session, sequence),
            ).fetchall()
    if action == "event" and len(rows) != 1:
        return {"durable_count": len(rows), "caregiver_count": 0}

    # This helper runs inside WSL, where the current Windows Wi-Fi address and
    # its phone-facing portproxy are not a reliable route to the local API.
    # Connect to the existing local listener, but keep the configured .local
    # hostname in the URL so CA, SNI, and certificate hostname verification
    # remain unchanged. 8444 is the existing GS-179 APP_PORT.
    local_origin = wsl_local_backend_origin(origin, 8444)
    route = wsl_ipv4()
    context = ssl.create_default_context(cafile=str(ca))
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        VerifiedAddressHTTPSHandler(context, route), urllib.request.HTTPCookieProcessor(jar))

    def call(path: str, method="GET", body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(local_origin + path, data=data, method=method,
                                     headers={"Origin": origin, "Content-Type": "application/json"})
        with opener.open(req, timeout=8) as response:
            return response.status, json.loads(response.read(1_000_000))

    status, profile = call("/lite/v1/auth/login", "POST", {
        "email": credentials["email"], "password": credentials["password"]})
    if status != 200 or profile.get("home_id") != HOME or profile.get("test_only") is not True:
        raise ValueError("TC001_caregiver_login_or_Home_rejected")
    try:
        status, overview = call(f"/lite/v1/homes/{HOME}/overview")
    finally:
        call("/lite/v1/auth/logout", "POST", {})
    if status != 200 or overview.get("source") != "AUTHENTICATED_GS148_TEST_ONLY":
        raise ValueError("TC001_wrong_caregiver_projection_source")
    if action == "readiness":
        return {"home_id": HOME, "caregiver_home_ready": True,
                "source": overview["source"], "backend_origin": origin,
                "source_freshness": overview.get("source_freshness"),
                "monitoring": overview.get("monitoring")}
    key = {"physical_device_id": device, "logical_node_id": "bedroom",
           "origin_session_id": session, "event_sequence": sequence}
    matches = [event for event in overview.get("recent_events", [])
               if event.get("event_key") == key]
    return {"durable_count": 1, "caregiver_count": len(matches),
            "event_key": key, "event_kind": matches[0].get("kind") if matches else None,
            "caregiver_event_id": matches[0].get("event_id") if matches else None,
            "event_location": matches[0].get("location") if matches else None,
            "occurred_at": matches[0].get("occurred_at") if matches else None,
            "received_at": matches[0].get("received_at") if matches else None,
            "event_id": rows[0][0], "committed_at": rows[0][1],
            "committing_hub_id": rows[0][2], "ownership_epoch": rows[0][3],
            "node_enrollment_generation": rows[0][4],
            "source_freshness": overview.get("source_freshness"),
            "monitoring": overview.get("monitoring")}


if __name__ == "__main__":
    try:
        print(json.dumps(run(json.load(sys.stdin)), sort_keys=True))
    except Exception as error:
        # Private connection strings, credentials and peer metadata stay local.
        print(json.dumps({"error": type(error).__name__, "reason":
                          str(error) if isinstance(error, ValueError) else "backend_read_failed"}))
        raise SystemExit(2)
