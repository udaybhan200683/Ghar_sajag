#!/usr/bin/env python3
"""Bounded Phase 3B concurrent API and household-isolation qualification."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
import json
from pathlib import Path
import random
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from ghar_sajag.foundation import FoundationService  # noqa: E402
from ghar_sajag.model import CloudEvent  # noqa: E402
from tools.sim.local_lab import (  # noqa: E402
    DEFAULT_HOUSEHOLD_SETTINGS,
    HOME,
    OWNER,
    Lab,
    WebLab,
)

HOME_B = "concurrent-home-b"
OWNER_B = "concurrent-owner-b"
WORKERS = 6
EVENTS_PER_HOME = 12
DUPLICATES_PER_HOME = 6
REJECTIONS_PER_HOME = 2


def _call(web, method, path, body=None, actor=OWNER):
    parsed = urlsplit(path)
    raw = json.dumps(body or {}, separators=(",", ":")).encode("utf-8")
    statuses = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": parsed.path,
        "QUERY_STRING": parsed.query,
        "HTTP_HOST": "127.0.0.1:8766",
        "HTTP_X_ACTOR_ID": actor,
        "CONTENT_TYPE": "application/json",
        "CONTENT_LENGTH": str(len(raw)),
        "wsgi.input": BytesIO(raw),
    }
    payload = json.loads(b"".join(web(environ, lambda status, headers: statuses.append(status))))
    return int(statuses[0][:3]), payload


def _event(home_id, index, at):
    kinds = ("MOTION", "DOOR_OPEN", "OK_PRESSED", "CALL_FAMILY")
    return {
        "event_id": f"shared-event-{index:02d}",
        "kind": kinds[index % len(kinds)],
        "location": f"{home_id}-room",
        "occurred_at": at + index,
        "hub_received_at": at + index,
        "payload": {},
    }


def _config(home_id):
    return {
        "schema": 1,
        "home_id": home_id,
        "timezone": "Asia/Kolkata",
        "mode": "HOME",
        "morning": {
            "enabled": True,
            "start_minute": 360,
            "end_minute": 660,
            "grace_minutes": 60,
        },
        "activity_rules": {
            "quiet_start_minute": 1320,
            "quiet_end_minute": 360,
            "door_open_timeout_seconds": 300,
            "daytime_start_minute": 480,
            "daytime_end_minute": 1260,
            "daytime_inactivity_seconds": 10800,
        },
    }


def run(seed=30401, workers=WORKERS):
    if not 2 <= workers <= 8:
        raise ValueError("workers must be between 2 and 8")
    started = time.perf_counter()
    rng = random.Random(seed)
    before_threads = {thread.ident for thread in threading.enumerate()}
    operation_counts = {}
    failures = []
    sqlite_busy = []
    durations_ms = []
    result = None

    with tempfile.TemporaryDirectory(prefix="ghar-sajag-concurrency-") as directory:
        db_path = Path(directory) / "concurrency.sqlite"
        lab = Lab(db_path)
        foundation_b = None
        simulator_pid = lab.proc.pid
        try:
            web = WebLab(lab, 8766)
            foundation_b = FoundationService(
                db_path, HOME_B, OWNER_B, clock=lambda: int(lab.state["now"])
            )
            foundation_b.seed(DEFAULT_HOUSEHOLD_SETTINGS, [])
            code, _ = _call(web, "POST", "/v1/homes", {
                "home_id": HOME_B,
                "display_name": "Concurrent household B",
                "timezone": "Asia/Kolkata",
                "language": "en-IN",
                "residents": [{
                    "resident_id": "resident-b",
                    "display_name": "Resident B",
                    "consent_active": True,
                }],
            }, OWNER_B)
            if code != 201:
                raise AssertionError(f"second household creation failed: {code}")
            with lab.service.lock:
                lab.service.homes.set_caregivers(HOME_B, OWNER_B, "care-b", "backup-b", lab.state["now"])
            _call(web, "POST", f"/v1/homes/{HOME_B}/config", _config(HOME_B), OWNER_B)

            lab.foundation.register_device(OWNER, {
                "device_id": "isolation-a-node",
                "display_name": "Shared Hall Sensor",
                "kind": "NODE",
                "capability": "MOTION",
                "room": "Common room",
            })
            foundation_b.register_device(OWNER_B, {
                "device_id": "isolation-b-node",
                "display_name": "Shared Hall Sensor",
                "kind": "NODE",
                "capability": "MOTION",
                "room": "Common room",
            })
            prefs_b = foundation_b.notification_preferences(OWNER_B)["preferences"]
            foundation_b.update_notification_preferences(
                OWNER_B, {**prefs_b, "safety_alerts": False, "browser_alerts_enabled": True}
            )

            # Device/hub timestamps must not be ahead of the API receive clock.
            at = int(lab.state["now"]) - 100
            events = {
                home_id: [_event(home_id, index, at) for index in range(EVENTS_PER_HOME)]
                for home_id in (HOME, HOME_B)
            }
            foundations = {HOME: lab.foundation, HOME_B: foundation_b}
            owners = {HOME: OWNER, HOME_B: OWNER_B}
            tasks = []

            def add(name, fn):
                tasks.append((name, fn))

            for home_id in (HOME, HOME_B):
                owner = owners[home_id]
                foundation = foundations[home_id]
                for event in events[home_id]:
                    def write_event(home_id=home_id, owner=owner, foundation=foundation, event=event):
                        code, payload = _call(web, "POST", f"/v1/homes/{home_id}/events", event, owner)
                        cloud_event = CloudEvent(
                            home_id, event["event_id"], event["kind"], event["location"],
                            event["occurred_at"], event["hub_received_at"], event["hub_received_at"],
                        )
                        foundation.apply_notification_event(cloud_event)
                        return {"status": code, "duplicate": bool(payload.get("duplicate")), "home": home_id}
                    add("event_write", write_event)
                for index in range(DUPLICATES_PER_HOME):
                    event = events[home_id][index]
                    def replay(home_id=home_id, owner=owner, foundation=foundation, event=event):
                        code, payload = _call(web, "POST", f"/v1/homes/{home_id}/events", event, owner)
                        cloud_event = CloudEvent(
                            home_id, event["event_id"], event["kind"], event["location"],
                            event["occurred_at"], event["hub_received_at"], event["hub_received_at"],
                        )
                        foundation.apply_notification_event(cloud_event)
                        return {"status": code, "duplicate": bool(payload.get("duplicate")), "home": home_id}
                    add("duplicate_replay", replay)
                for index in range(REJECTIONS_PER_HOME):
                    bad = {
                        "event_id": f"bad-{home_id}-{index}", "kind": "UNKNOWN_EVENT",
                        "location": f"{home_id}-room", "occurred_at": at,
                        "hub_received_at": at, "payload": {},
                    }
                    add("malformed_rejection", lambda home_id=home_id, owner=owner, bad=bad:
                        {"status": _call(web, "POST", f"/v1/homes/{home_id}/events", bad, owner)[0], "home": home_id})
                add("device_health", lambda foundation=foundation, did=("isolation-a-node" if home_id == HOME else "isolation-b-node"):
                    foundation.record_health(did, True, "ACTIVE", 3900, 61, "NORMAL", heartbeat=True))
                add("device_read", lambda foundation=foundation, owner=owner: foundation.devices(owner))
                add("notification_read", lambda foundation=foundation, owner=owner: foundation.notification_records(owner))
                add("preference_read", lambda foundation=foundation, owner=owner: foundation.notification_preferences(owner))
                for period in ("TODAY", "WEEK", "MONTH"):
                    add("report_read", lambda home_id=home_id, owner=owner, period=period:
                        _call(web, "GET", f"/v1/homes/{home_id}/reports?period={period}", actor=owner))
                add("snapshot_read", lambda home_id=home_id, owner=owner:
                    _call(web, "GET", f"/v1/homes/{home_id}/snapshot", actor=owner))
            for scope in ("home", "full", "home", "full"):
                add("pwa_read", lambda scope=scope: _call(web, "GET", f"/pwa/state?scope={scope}", actor=OWNER))

            rng.shuffle(tasks)
            release = threading.Event()

            def execute(name, fn):
                release.wait()
                task_started = time.perf_counter()
                try:
                    value = fn()
                    return name, value, None, (time.perf_counter() - task_started) * 1000
                except Exception as error:  # diagnostic capture; asserted below
                    return name, None, f"{type(error).__name__}: {error}", (time.perf_counter() - task_started) * 1000

            responses = []
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="phase3b-concurrency") as pool:
                futures = [pool.submit(execute, name, fn) for name, fn in tasks]
                release.set()
                for future in as_completed(futures):
                    name, value, error, duration = future.result()
                    operation_counts[name] = operation_counts.get(name, 0) + 1
                    durations_ms.append(duration)
                    if error:
                        failures.append({"operation": name, "error": error})
                        if "locked" in error.lower() or "busy" in error.lower():
                            sqlite_busy.append(error)
                    else:
                        responses.append((name, value))

            event_responses = [value for name, value in responses if name in {"event_write", "duplicate_replay"}]
            accepted_by_home = {
                home_id: sum(value["status"] == 202 and not value["duplicate"] for value in event_responses if value["home"] == home_id)
                for home_id in (HOME, HOME_B)
            }
            duplicates_by_home = {
                home_id: sum(value["status"] == 200 and value["duplicate"] for value in event_responses if value["home"] == home_id)
                for home_id in (HOME, HOME_B)
            }
            rejected_by_home = {
                home_id: sum(value["status"] == 400 and value["home"] == home_id for name, value in responses if name == "malformed_rejection")
                for home_id in (HOME, HOME_B)
            }

            incidents_by_home = {
                home_id: sorted(
                    (incident for incident in lab.service.store.incidents.values() if incident.home_id == home_id),
                    key=lambda incident: incident.stable_key,
                )
                for home_id in (HOME, HOME_B)
            }
            for home_id, actor in ((HOME, "primary"), (HOME_B, "care-b")):
                if not incidents_by_home[home_id]:
                    failures.append({"operation": "acknowledgement", "error": f"no incident for {home_id}"})
                    continue
                incident = incidents_by_home[home_id][0]
                code, _ = _call(
                    web, "POST", f"/v1/homes/{home_id}/incidents/{incident.incident_id}/acknowledge",
                    {}, actor,
                )
                if code != 200:
                    failures.append({"operation": "acknowledgement", "error": f"HTTP {code}"})

            snapshots = {
                home_id: _call(web, "GET", f"/v1/homes/{home_id}/snapshot", actor=owners[home_id])[1]
                for home_id in (HOME, HOME_B)
            }
            reports = {
                home_id: {
                    period: _call(web, "GET", f"/v1/homes/{home_id}/reports?period={period}", actor=owners[home_id])[1]
                    for period in ("TODAY", "WEEK", "MONTH")
                }
                for home_id in (HOME, HOME_B)
            }
            timelines = {
                home_id: lab.service.queries.timeline(home_id, owners[home_id], lab.state["now"], limit=100)
                for home_id in (HOME, HOME_B)
            }
            notifications = {
                HOME: lab.foundation.notification_records(OWNER),
                HOME_B: foundation_b.notification_records(OWNER_B),
            }
            devices = {
                HOME: lab.foundation.devices(OWNER),
                HOME_B: foundation_b.devices(OWNER_B),
            }
            preferences = {
                HOME: lab.foundation.notification_preferences(OWNER)["preferences"],
                HOME_B: foundation_b.notification_preferences(OWNER_B)["preferences"],
            }
            pwa_home = _call(web, "GET", "/pwa/state?scope=home", actor=OWNER)[1]
            pwa_full = _call(web, "GET", "/pwa/state?scope=full", actor=OWNER)[1]
            cross_snapshot_statuses = (
                _call(web, "GET", f"/v1/homes/{HOME_B}/snapshot", actor=OWNER)[0],
                _call(web, "GET", f"/v1/homes/{HOME}/snapshot", actor=OWNER_B)[0],
            )
            cross_incident_statuses = (
                _call(
                    web, "POST",
                    f"/v1/homes/{HOME_B}/incidents/{incidents_by_home[HOME_B][0].incident_id}/acknowledge",
                    {}, "primary",
                )[0]
                if incidents_by_home[HOME_B] else None,
                _call(
                    web, "POST",
                    f"/v1/homes/{HOME}/incidents/{incidents_by_home[HOME][0].incident_id}/acknowledge",
                    {}, "care-b",
                )[0]
                if incidents_by_home[HOME] else None,
            )
            cross_foundation_denied = []
            for foundation, actor in ((lab.foundation, OWNER_B), (foundation_b, OWNER)):
                try:
                    foundation.notification_records(actor)
                except PermissionError:
                    cross_foundation_denied.append(True)
                else:
                    cross_foundation_denied.append(False)

            event_rows = lab.foundation.db.execute(
                "SELECT home_id,canonical_event_id,location FROM events WHERE canonical_event_id LIKE 'shared-event-%' ORDER BY home_id,canonical_event_id"
            ).fetchall()
            database_home_ids = {}
            for table in ("events", "device_registry", "device_health_history", "notification_preferences", "notification_records", "application_policy"):
                database_home_ids[table] = sorted(
                    row[0] for row in lab.foundation.db.execute(f"SELECT DISTINCT home_id FROM {table}")
                )

            checks = {
                "no_unexpected_failures": not failures,
                "no_sqlite_busy_or_lock_failures": not sqlite_busy,
                "accepted_counts_deterministic": all(value == EVENTS_PER_HOME for value in accepted_by_home.values()),
                "duplicate_counts_deterministic": all(value == DUPLICATES_PER_HOME for value in duplicates_by_home.values()),
                "rejected_counts_deterministic": all(value == REJECTIONS_PER_HOME for value in rejected_by_home.values()),
                "same_event_ids_are_household_local": len(event_rows) == EVENTS_PER_HOME * 2 and all(
                    row["location"] == f"{row['home_id']}-room" for row in event_rows
                ),
                "snapshot_isolation": all(
                    snapshot["home_id"] == home_id
                    and snapshot["event_counts"].get("CALL_FAMILY") == 3
                    for home_id, snapshot in snapshots.items()
                ),
                "timeline_isolation": all(
                    all(item["location"] != f"{other}-room" for item in timelines[home_id])
                    for home_id, other in ((HOME, HOME_B), (HOME_B, HOME))
                ),
                "timeline_order_deterministic": all(
                    [(item["occurred_at"], item["event_id"]) for item in timelines[home_id]]
                    == sorted(
                        [(item["occurred_at"], item["event_id"]) for item in timelines[home_id]], reverse=True
                    )
                    for home_id in (HOME, HOME_B)
                ),
                "report_isolation": all(
                    report["home_id"] == home_id
                    and report["summary"]["event_count"] == EVENTS_PER_HOME
                    and report["summary"]["call_family"] == 3
                    and all(f"{other}-room" not in json.dumps(report) for other in ({HOME, HOME_B} - {home_id}))
                    and len(report["highlights"]) <= 6
                    and len(report["room_activity"]) <= 5
                    for home_id, periods in reports.items() for report in periods.values()
                ),
                "incident_isolation": all(len(items) == 3 and all(item.home_id == home_id for item in items)
                                          for home_id, items in incidents_by_home.items()),
                "notification_isolation": len(notifications[HOME]) == 3 and len(notifications[HOME_B]) == 3
                    and all(item["state"] == "DELIVERED" for item in notifications[HOME])
                    and all(item["state"] == "SUPPRESSED" for item in notifications[HOME_B]),
                "notification_history_bounded": all(len(items) <= 20 for items in notifications.values()),
                "device_isolation": {item["device_id"] for item in devices[HOME]}.isdisjoint(
                    {item["device_id"] for item in devices[HOME_B]}
                ) and any(item["display_name"] == "Shared Hall Sensor" for item in devices[HOME])
                    and any(item["display_name"] == "Shared Hall Sensor" for item in devices[HOME_B]),
                "preference_isolation": preferences[HOME]["safety_alerts"] is True
                    and preferences[HOME_B]["safety_alerts"] is False,
                "cross_household_access_denied": all(status == 403 for status in cross_snapshot_statuses)
                    and all(status == 403 for status in cross_incident_statuses)
                    and all(cross_foundation_denied),
                "pwa_collections_bounded": len(pwa_home["events"]) <= 20 and len(pwa_full["events"]) <= 20,
                "database_rows_household_scoped": all(
                    set(home_ids) == {HOME, HOME_B} for home_ids in database_home_ids.values()
                ),
            }
            result = {
                "schema_version": 1,
                "seed": seed,
                "workers": workers,
                "operation_counts": operation_counts,
                "counts": {
                    "accepted_by_home": accepted_by_home,
                    "duplicates_by_home": duplicates_by_home,
                    "rejected_by_home": rejected_by_home,
                    "incidents_by_home": {key: len(value) for key, value in incidents_by_home.items()},
                    "notifications_by_home": {key: len(value) for key, value in notifications.items()},
                },
                "database_home_ids": database_home_ids,
                "failures": failures,
                "sqlite_busy_or_lock_failures": sqlite_busy,
                "correctness_gate": {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks},
                "diagnostics": {
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                    "max_operation_duration_ms": round(max(durations_ms, default=0), 3),
                    "sum_operation_duration_ms": round(sum(durations_ms), 3),
                    "simulator_pid": simulator_pid,
                },
            }
        finally:
            if foundation_b is not None:
                foundation_b.close()
            lab.close()

    leaked_threads = [
        thread.name for thread in threading.enumerate()
        if thread.ident not in before_threads and thread.name.startswith("phase3b-concurrency")
    ]
    result["diagnostics"]["worker_threads_after_cleanup"] = leaked_threads
    result["diagnostics"]["simulator_exited"] = lab.proc.poll() is not None
    result["correctness_gate"]["checks"]["no_worker_thread_leaks"] = not leaked_threads
    result["correctness_gate"]["checks"]["simulator_process_cleaned_up"] = lab.proc.poll() is not None
    result["correctness_gate"]["status"] = (
        "PASS" if all(result["correctness_gate"]["checks"].values()) else "FAIL"
    )
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=30401)
    parser.add_argument("--workers", type=int, default=WORKERS)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(args.seed, args.workers)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["correctness_gate"]["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
