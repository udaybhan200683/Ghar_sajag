#!/usr/bin/env python3
"""Deterministic Phase 3 stress foundation using real local domain/API paths."""
from __future__ import annotations

import argparse
import json
import random
import resource
import sys
import tempfile
import time
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.sim.local_lab import HOME, OWNER, Lab  # noqa: E402

PROFILE_PATH = ROOT / "tools/stress/profiles.json"
PERFORMANCE_BUDGET_PATH = ROOT / "tests/validation/phase3a_performance_budget.json"
EVENT_TYPES = (
    ("MOTION", "room1"),
    ("DOOR_OPEN", "entry"),
    ("DOOR_CLOSED", "entry"),
    ("OK_PRESSED", "room1"),
    ("CALL_FAMILY", "room1"),
)


def _rss_bytes(who=resource.RUSAGE_SELF):
    value = resource.getrusage(who).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def _proc_rss(pid):
    try:
        for line in Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None
    return None


def _event(index, at, rng):
    kind, location = EVENT_TYPES[index % len(EVENT_TYPES)]
    return {
        "event_id": f"stress-{index:08d}-{rng.randrange(1_000_000):06d}",
        "kind": kind,
        "location": location,
        "occurred_at": at,
        "hub_received_at": at,
        "payload": {},
    }


def _report_api(lab, period):
    captured = []
    chunks = lab.api({
        "REQUEST_METHOD": "GET",
        "PATH_INFO": f"/v1/homes/{HOME}/reports",
        "QUERY_STRING": f"period={period}",
        "HTTP_X_ACTOR_ID": OWNER,
        "CONTENT_LENGTH": "0",
        "wsgi.input": BytesIO(b""),
    }, lambda status, headers: captured.append(status))
    payload = json.loads(b"".join(chunks))
    if not captured[0].startswith("2"):
        raise ValueError(payload.get("error", captured[0]))
    return payload


def _stderr_progress(message):
    print(f"[stress] {message}", file=sys.stderr, flush=True)


def _milestones(total):
    if total <= 0:
        return {}
    return {
        max(1, (total * step + 3) // 4): min(100, step * 25)
        for step in range(1, 5)
    }


def _loop_progress(progress, label, completed, total, milestones):
    if progress is not None and completed in milestones:
        progress(f"{label}: {completed}/{total} ({milestones[completed]}%)")


def run(profile_name="SMALL", seed=30401, allow_large=False, progress=None):
    profiles = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))["profiles"]
    name = profile_name.upper()
    if name not in profiles:
        raise ValueError(f"unknown profile: {profile_name}")
    profile = profiles[name]
    payload_limits = json.loads(PERFORMANCE_BUDGET_PATH.read_text(encoding="utf-8"))["limits"]
    if profile["manual_only"] and not allow_large:
        raise ValueError(f"{name} is manual-only; pass --allow-large explicitly")
    rng = random.Random(seed)
    started = time.perf_counter()
    rss_before = _rss_bytes()
    stage_duration_ms = {}

    @contextmanager
    def stage(key, label):
        if progress is not None:
            progress(f"{label}: start")
        stage_started = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = round((time.perf_counter() - stage_started) * 1000, 3)
            stage_duration_ms[key] = elapsed_ms
            if progress is not None:
                progress(f"{label}: complete ({elapsed_ms:.1f} ms)")

    with tempfile.TemporaryDirectory(prefix=f"ghar-sajag-stress-{name.lower()}-") as directory:
        db_path = Path(directory) / "stress.sqlite"
        lab = None
        accepted = duplicate_responses = rejected = 0
        request_failures = 0
        generated = []
        max_home_bytes = max_full_bytes = max_report_bytes = 0
        try:
            with stage("setup_devices", "setup/devices"):
                lab = Lab(db_path)
                child_rss_before = _proc_rss(lab.proc.pid)
                for index in range(profile["extra_devices"]):
                    lab.foundation.register_device(OWNER, {
                        "device_id": f"stress-node-{index:02d}",
                        "display_name": f"Stress Node {index:02d}",
                        "kind": "NODE",
                        "capability": "MOTION",
                        "room": "Common room",
                    })
            at = int(lab.state["now"])
            with stage("accepted_event_ingestion", "accepted event ingestion"):
                milestones = _milestones(profile["events"])
                for index in range(profile["events"]):
                    event = _event(index, at, rng)
                    result = lab.api_call("POST", f"/v1/homes/{HOME}/events", event)
                    if result.get("duplicate"):
                        duplicate_responses += 1
                    else:
                        accepted += 1
                    generated.append(event)
                    _loop_progress(progress, "accepted event ingestion", index + 1, profile["events"], milestones)
            with stage("duplicate_replay", "duplicate replay"):
                milestones = _milestones(profile["duplicates"])
                for index in range(profile["duplicates"]):
                    result = lab.api_call("POST", f"/v1/homes/{HOME}/events", generated[index % len(generated)])
                    duplicate_responses += int(bool(result.get("duplicate")))
                    _loop_progress(progress, "duplicate replay", index + 1, profile["duplicates"], milestones)
            with stage("malformed_rejection", "malformed rejection"):
                milestones = _milestones(profile["malformed"])
                for index in range(profile["malformed"]):
                    try:
                        lab.api_call("POST", f"/v1/homes/{HOME}/events", {
                            "event_id": f"malformed-{index}", "kind": "UNKNOWN_EVENT",
                        })
                        request_failures += 1
                    except (ValueError, TypeError, KeyError):
                        rejected += 1
                    _loop_progress(progress, "malformed rejection", index + 1, profile["malformed"], milestones)
            with stage("api_pwa_reads", "API/PWA reads"):
                milestones = _milestones(profile["api_reads"])
                for index in range(profile["api_reads"]):
                    try:
                        scope = "full" if index % 20 == 0 else "home"
                        payload = json.dumps(lab.pwa_view(scope), separators=(",", ":")).encode()
                        if scope == "home":
                            max_home_bytes = max(max_home_bytes, len(payload))
                        else:
                            max_full_bytes = max(max_full_bytes, len(payload))
                    except Exception:
                        request_failures += 1
                    _loop_progress(progress, "API/PWA reads", index + 1, profile["api_reads"], milestones)
            reports = {}
            with stage("report_cycles", "report cycles"):
                milestones = _milestones(profile["report_cycles"])
                for index in range(profile["report_cycles"]):
                    period = ("TODAY", "WEEK", "MONTH")[index % 3]
                    try:
                        report = _report_api(lab, period)
                        reports[period] = report
                        max_report_bytes = max(max_report_bytes, len(json.dumps(report, separators=(",", ":")).encode()))
                    except Exception:
                        request_failures += 1
                    _loop_progress(progress, "report cycles", index + 1, profile["report_cycles"], milestones)
            with stage("final_verification", "final verification"):
                home = lab.pwa_view("home")
                history = lab.foundation.notification_records(OWNER)
                event_count = lab.foundation.db.execute("SELECT COUNT(*) FROM events WHERE home_id=?", (HOME,)).fetchone()[0]
                notification_count = lab.foundation.db.execute("SELECT COUNT(*) FROM notification_records WHERE home_id=?", (HOME,)).fetchone()[0]
                lab.foundation.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                database_bytes = db_path.stat().st_size
                correctness = {
                    "accepted_matches": accepted == profile["events"],
                    "duplicates_match": duplicate_responses == profile["duplicates"],
                    "rejections_match": rejected == profile["malformed"],
                    "no_unexpected_request_failures": request_failures == 0,
                    "home_events_bounded": len(home["events"]) <= 20,
                    "notification_history_bounded": len(history) <= 20,
                    "report_highlights_bounded": all(len(item["highlights"]) <= 6 for item in reports.values()),
                    "report_rooms_bounded": all(len(item["room_activity"]) <= 5 for item in reports.values()),
                    "home_payload_bounded": max_home_bytes <= payload_limits["payloads.home_compact_bytes"],
                    "full_payload_bounded": max_full_bytes <= payload_limits["payloads.full_state_bytes"],
                    "report_payload_bounded": max_report_bytes <= payload_limits["payloads.report_month_bytes"],
                    "database_growth_bounded": database_bytes <= profile["max_database_bytes"],
                }
            result = {
                "schema_version": 1,
                "profile": name,
                "seed": seed,
                "configuration": profile,
                "counts": {
                    "generated": profile["events"] + profile["duplicates"] + profile["malformed"],
                    "accepted": accepted,
                    "rejected": rejected,
                    "duplicates": duplicate_responses,
                    "request_failures": request_failures,
                    "event_history": int(event_count),
                    "notifications": int(notification_count),
                    "notification_history_returned": len(history),
                    "home_recent_events": len(home["events"]),
                },
                "payload_max_bytes": {
                    "home": max_home_bytes,
                    "full": max_full_bytes,
                    "report": max_report_bytes,
                },
                "storage": {"database_bytes": database_bytes},
                "correctness_gate": {
                    "status": "PASS" if all(correctness.values()) else "FAIL",
                    "checks": correctness,
                },
                "diagnostics": {
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                    "process_max_rss_before_bytes": rss_before,
                    "process_max_rss_after_bytes": _rss_bytes(),
                    "simulator_rss_before_bytes": child_rss_before,
                    "simulator_rss_after_bytes": _proc_rss(lab.proc.pid),
                    "stage_duration_ms": stage_duration_ms,
                },
            }
        finally:
            if lab is not None:
                lab.close()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="SMALL")
    parser.add_argument("--seed", type=int, default=30401)
    parser.add_argument("--allow-large", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = run(args.profile, args.seed, args.allow_large, progress=_stderr_progress)
    except ValueError as error:
        parser.error(str(error))
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["correctness_gate"]["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
