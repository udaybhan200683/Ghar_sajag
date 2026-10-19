#!/usr/bin/env python3
"""Create one source-linked TEST_ONLY Node event in the persistent local R1 DB.

This runs the existing GS-178 Node host binary, GS-40 configuration/time path,
HubRuntime, GS-179 verified mTLS listener and GS-148 PostgreSQL COMMITTED API.
It refuses a non-loopback or non-verify-full database and never clears data.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
CODE = ROOT / "code"
sys.path[:0] = [str(CODE / "tests" / "support"), str(CODE / "tests" / "integration"),
               str(CODE / "backend"), str(CODE / "validation"), str(CODE / "tools" / "sim"),
               str(CODE / "tools" / "hil"), str(CODE / "tools" / "factory"),
               str(CODE / "parivar_saathi_android_app" / "server")]

from gs179_postgres_test_db import local_verified_postgres_url  # noqa: E402
from gs178_stack import HOME, HUB, ProductStack  # noqa: E402


def _write_credentials(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    temp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)
    path.chmod(0o600)


def run_health_refresh(dsn: str, credential_path: Path) -> int:
    if not credential_path.is_file():
        print("BLOCKED local_caregiver_credentials_missing_run_node_event_once")
        return 2
    credentials = json.loads(credential_path.read_text(encoding="utf-8"))
    if credentials.get("profile") != "GS179_TEST_ONLY" or credentials.get("home_id") != HOME:
        print("BLOCKED local_caregiver_credentials_not_bound_to_expected_test_home")
        return 2
    import psycopg
    with psycopg.connect(dsn, connect_timeout=5) as db:
        committed = db.execute(
            "SELECT COUNT(*) FROM durable_event_commits WHERE home_id=%s", (HOME,)
        ).fetchone()[0]
        if committed != 1:
            print("BLOCKED expected_single_source_event_commit_not_present")
            return 2

    stack = None
    try:
        stack = ProductStack(
            postgres_dsn=dsn, persistent_postgres=True,
            home_id=HOME, hub_id=HUB,
            caregiver_email=credentials["email"],
            caregiver_password=credentials["password"],
            reuse_existing_test_home=True, reuse_existing_caregiver=True,
        )
        ready = stack.start_node()
        if ready.get("stage") != "CLOUDSYNC_READY":
            raise RuntimeError("node_cloudsync_startup_not_ready")
        stack.command("health 0 1000")
        attempts = []
        accepted = False
        for attempt in range(8):
            # Keep the host domain clock deterministic and accelerated, as in
            # the registered GS-178 E2E. The bounded retries let this new host
            # simulator boot advance source_revision past the last persisted
            # report without changing trusted-time validation.
            time.sleep(5 if attempt == 0 else 2)
            domain_ms = (attempt + 2) * 1000
            stack.domain_now = ready["utc"] + domain_ms // 1000
            result = stack.command(f"sync {domain_ms} 1")
            attempts.append({"domain_ms": domain_ms, "health_accepted": result.get("health_accepted"),
                             "health_submitted": result.get("health_submitted")})
            if result.get("health_accepted", 0) >= 1:
                accepted = True
                break
        if not accepted:
            raise RuntimeError("node_health_not_accepted:" + json.dumps(
                {"attempts": attempts, "receipts": stack.receipts}, sort_keys=True))
        cookie = stack.login()
        status, overview, _ = stack.human(
            "GET", f"/lite/v1/homes/{HOME}/overview", cookie=cookie)
        if status != 200:
            raise RuntimeError("caregiver_overview_not_authorized")
        status, devices, _ = stack.human(
            "GET", f"/lite/v1/homes/{HOME}/devices", cookie=cookie)
        if status != 200:
            raise RuntimeError("caregiver_devices_not_authorized")
        matching_event = next((event for event in overview.get("recent_events", [])
                               if event.get("event_key", {}).get("physical_device_id") == "test-c3-bedroom"), None)
        statuses = [{"node_id": item.get("logical_node_id"), "status": item.get("status"),
                     "coverage": item.get("coverage")} for item in devices.get("devices", [])]
        if matching_event is None or not any(
                item["node_id"] == "bedroom" and item["status"] == "ONLINE" and
                item["coverage"] == "COVERED" for item in statuses):
            raise RuntimeError("committed_event_or_online_node_missing_from_caregiver_projection:" +
                               json.dumps({"attempts": attempts, "statuses": statuses,
                                           "monitoring": overview.get("monitoring"),
                                           "source_freshness": overview.get("source_freshness"),
                                           "receipts": stack.receipts}, sort_keys=True))
        report = {
            "result": "HOST_SIM_PASS",
            "source": "GS178_NODE_HOST_TO_GS148_POSTGRES_TO_CAREGIVER",
            "home_id": HOME,
            "node_event_key": matching_event.get("event_key"),
            "postgres_committed_event_count": committed,
            "health_attempts": attempts,
            "backend_receipts": [
                {"path": item["path"], "status": item["status"],
                 "response": item["response"]} for item in stack.receipts
            ],
            "caregiver_monitoring": overview.get("monitoring"),
            "caregiver_source_freshness": overview.get("source_freshness"),
            "caregiver_device_statuses": statuses,
            "physical_status": "NOT_RUN",
        }
        print(json.dumps(report, sort_keys=True))
        return 0
    except Exception as error:
        print(f"FAIL {type(error).__name__}: {error}")
        return 1
    finally:
        if stack is not None:
            stack.close()


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--health-only", action="store_true")
    args = parser.parse_args(argv)
    if os.environ.get("GS179_LOCAL_PERSISTENT_POSTGRES") != "1":
        print("BLOCKED explicit_local_persistent_test_profile_required")
        return 2
    dsn = os.environ.get("GS179_LOCAL_SERVER_DSN", "")
    credential_path = Path(os.environ.get(
        "GS179_CAREGIVER_CREDENTIALS",
        str(Path.home() / ".local/state/ghar-sajag/gs179-laptop/caregiver-login.json"),
    )).expanduser()
    if not dsn:
        print("BLOCKED GS179_LOCAL_SERVER_DSN_missing")
        return 2
    try:
        app_url = local_verified_postgres_url(dsn)
    except ValueError as error:
        print(f"BLOCKED database_policy={error}")
        return 2
    if credential_path.exists():
        if args.health_only:
            return run_health_refresh(dsn, credential_path)
        print("BLOCKED caregiver_credentials_already_exist_preserve_existing_data")
        return 2
    if args.health_only:
        print("BLOCKED local_caregiver_credentials_missing_run_node_event_once")
        return 2

    run_id = secrets.token_hex(6)
    home_id, hub_id = HOME, HUB
    caregiver_email = "owner-laptop-" + run_id + "@gs178.dev"
    import psycopg
    with psycopg.connect(dsn, connect_timeout=5) as db:
        row = db.execute("SELECT 1 FROM lite_homes WHERE home_id=%s", (home_id,)).fetchone()
        reuse_existing = row is not None
        if db.execute("SELECT to_regclass('public.durable_event_commits') IS NOT NULL").fetchone()[0]:
            committed = db.execute(
                "SELECT COUNT(*) FROM durable_event_commits WHERE home_id=%s", (home_id,)
            ).fetchone()[0]
            if committed:
                print("BLOCKED local_GS178_Home_already_has_committed_events_preserve_existing_data")
                return 2

    os.environ["GS179_LOCAL_PERSISTENT_POSTGRES"] = "1"
    stack = None
    credential_written = False
    try:
        stack = ProductStack(postgres_dsn=dsn, persistent_postgres=True,
                             home_id=home_id, hub_id=hub_id,
                             caregiver_email=caregiver_email,
                             reuse_existing_test_home=reuse_existing)
        ready = stack.start_node()
        if ready.get("stage") != "CLOUDSYNC_READY":
            raise RuntimeError("node_cloudsync_startup_not_ready")
        credential_payload = {
            "profile": "GS179_TEST_ONLY",
            "email": caregiver_email,
            "password": stack.password,
            "home_id": home_id,
            "created_by": "gs178_node_host_simulation",
        }
        _write_credentials(credential_path, credential_payload)
        credential_written = True
        stack.command("health 0 1000")
        timestamp = stack.now + 1
        motion = stack.command(
            f"input 0 motion {timestamp} {timestamp} 3000 420 0"
        )
        if motion.get("ack") != "DURABLE" or not motion.get("event_key"):
            raise RuntimeError("node_motion_not_durably_admitted")
        # The Hub's test clock advances by 5 seconds during this sync. Keep
        # the backend receive-time callback on that same deterministic clock
        # before invoking CloudSync, as the registered GS-178 E2E does.
        stack.domain_now = ready["utc"] + 5
        sync = stack.command("sync 5000 1")
        if sync.get("completed") != 1 or sync.get("health_accepted", 0) < 1:
            raise RuntimeError("hub_cloudsync_commit_or_health_missing:" +
                               json.dumps({"ready": ready, "motion": motion,
                                            "sync": sync, "receipts": stack.receipts},
                                           sort_keys=True))
        receipt = next((item for item in stack.receipts
                        if item["path"] == f"/v1/homes/{home_id}/events" and
                        item["response"].get("status") == "COMMITTED"), None)
        if receipt is None or receipt["response"].get("event_key") != motion["event_key"]:
            raise RuntimeError("committed_receipt_eventkey_mismatch")
        caregiver_cookie = stack.login()
        status, view, _ = stack.human(
            "GET", f"/lite/v1/homes/{home_id}/overview", cookie=caregiver_cookie
        )
        if status != 200 or not any(
            event.get("event_key") == motion["event_key"]
            for event in view.get("recent_events", [])
        ):
            raise RuntimeError("caregiver_projection_missing_committed_event")
        status, devices, _ = stack.human(
            "GET", f"/lite/v1/homes/{home_id}/devices", cookie=caregiver_cookie
        )
        if status != 200 or not devices.get("devices"):
            raise RuntimeError("caregiver_nodehealth_projection_missing")
        event_count = stack.durable.db.execute(
            "SELECT COUNT(*) FROM durable_event_commits WHERE home_id=?", (home_id,)
        ).fetchone()[0]
        if event_count != 1:
            raise RuntimeError("unexpected_persistent_event_count")
        report = {
            "result": "HOST_SIM_PASS",
            "source": "GS178_NODE_HOST_TO_GS148_POSTGRES_TO_CAREGIVER",
            "home_id": home_id,
            "node_event_key": motion["event_key"],
            "node_ack": motion["ack"],
            "hub_sync": sync,
            "backend_receipt_status": receipt["status"],
            "backend_receipt": receipt["response"],
            "postgres_committed_event_count": event_count,
            "caregiver_event_count": len(view.get("recent_events", [])),
            "caregiver_monitoring": view.get("monitoring"),
            "caregiver_source_freshness": view.get("source_freshness"),
            "caregiver_device_statuses": [
                {"node_id": item.get("node_id"), "status": item.get("status"),
                 "coverage": item.get("coverage")}
                for item in devices.get("devices", [])
            ],
            "credentials_file": str(credential_path),
            "physical_status": "NOT_RUN",
        }
        print(json.dumps(report, sort_keys=True))
        return 0
    except Exception as error:
        if credential_written:
            try:
                import psycopg
                with psycopg.connect(dsn, connect_timeout=5) as db:
                    count = db.execute(
                        "SELECT COUNT(*) FROM durable_event_commits WHERE home_id=%s",
                        (home_id,),
                    ).fetchone()[0]
                if not count:
                    credential_path.unlink(missing_ok=True)
                else:
                    print("PRESERVED caregiver login for an already durable local TEST_ONLY event")
            except Exception:
                print("PRESERVED caregiver login; unable to determine durable commit state")
        print(f"FAIL {type(error).__name__}: {error}")
        return 1
    finally:
        if stack is not None:
            stack.close()


if __name__ == "__main__":
    raise SystemExit(main())
