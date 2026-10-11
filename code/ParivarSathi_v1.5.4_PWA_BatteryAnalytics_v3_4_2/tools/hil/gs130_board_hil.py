#!/usr/bin/env python3
"""Opt-in, read-only UART observation for the pinned disposable GS-114 pair."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys

from gs130_hil_common import (FIXTURE, PRODUCT, ReadOnlyCapture, TOKEN, current_source_head,
                              create_evidence_dir, report_exit_code, status_from_logs, utc_now, verify_preflight,
                              write_report)

CASES = ("HIL-A01", "HIL-A02", "HIL-A03", "HIL-A04", "HIL-A05", "HIL-A06", "HIL-A07", "HIL-A08")


def record_pre_run(args, status, detail):
    evidence_dir = create_evidence_dir(args.report, "GS130_BOARD_HIL")
    report = {
        "schema_version": 1, "campaign": "GS-130 automated observational board HIL",
        "fixture_id": FIXTURE["fixture_id"], "source_head": current_source_head(),
        "firmware_source_head": FIXTURE["firmware_source_head"],
        "firmware_version_expected": FIXTURE["firmware_version"],
        "image_sha256_expected": {n: FIXTURE["boards"][n]["image_sha256"] for n in ("c3", "s3")},
        "flash_readback_hash_verified": False, "config_fingerprint_observed": False,
        "ports": {"c3": args.c3_port, "s3": args.s3_port},
        "cases": [{"test_id": case_id, "status": status, "detail": detail} for case_id in CASES],
        "overall": status, "hardware_actions": [], "physical_qualification_complete": False,
        "release_approved": False,
    }
    write_report(evidence_dir / "board_hil_results.json", report)
    print(f"AUTOMATED BOARD HIL RESULT {status} cases={len(CASES)} evidence={evidence_dir}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observe", action="store_true", help="open the two explicit stable by-id UART interfaces read-only after interactive approval")
    parser.add_argument("--c3-port")
    parser.add_argument("--s3-port")
    parser.add_argument("--c3-image", type=Path)
    parser.add_argument("--s3-image", type=Path)
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if not args.observe:
        print("AUTOMATED BOARD HIL NOT_RUN: no UART was opened; explicit user fixture approval is required.")
        print(f"Approved fixture identifier: {FIXTURE['fixture_id']}; required runtime phrase: {TOKEN}")
        record_pre_run(args, "NOT_RUN", "No --observe flag; no hardware interface was opened.")
        return 3
    if args.seconds < 10 or args.seconds > 900:
        print("BLOCKED: observation duration must be 10..900 seconds")
        return 3
    failures = verify_preflight(args.c3_port, args.s3_port, args.c3_image, args.s3_image)
    if failures:
        for failure in failures:
            print("BLOCKED:", failure)
        record_pre_run(args, "BLOCKED", "; ".join(failures))
        return 3
    print("Read-only observation plan for the exact pinned by-id fixture:")
    print("  HIL-A01: collect identity/version banner; remain BLOCKED if running-image hash/config evidence is absent.")
    print("  HIL-A02/A03: mark authenticated link/NodeHealth only from explicit matching UART markers.")
    print("  HIL-A04/A08: NOT_RUN; outage/loss/replay stimuli are outside this passive campaign.")
    print("  HIL-A05: PASS only if one exact EventKey correlates authenticated Durable ACK and Node retirement.")
    print("  HIL-A06/A07: classify only observed runtime errors and target sleep/timer markers.")
    print("No UART writes, flash/reset, enrollment, event injection or fault stimulus; DTR/RTS are set low.")
    print("Serial open can still affect target reset lines on an unverified adapter. Stop if that cannot be excluded.")
    if input(f"Type exactly '{TOKEN}' only after the user-approved fixture and this scope are confirmed: ").strip() != TOKEN:
        print("BLOCKED: fixture observation not authorized")
        record_pre_run(args, "BLOCKED", "Explicit fixture/operator confirmation was not supplied; no UART was opened.")
        return 3
    start = utc_now()
    capture = ReadOnlyCapture({"c3": args.c3_port, "s3": args.s3_port})
    try:
        capture.open()
        print(f"Capturing both existing UART streams for {args.seconds}s; no commands will be sent.")
        logs = capture.window(args.seconds)
    except (OSError, ImportError) as error:
        print("BLOCKED: safe serial observation unavailable:", error)
        record_pre_run(args, "BLOCKED", f"Read-only serial capture could not start safely: {error}")
        return 3
    finally:
        capture.close()
    end = utc_now()
    cases = []
    for case_id in CASES:
        status, detail = status_from_logs(case_id, logs["c3"], logs["s3"])
        cases.append({"test_id": case_id, "status": status, "detail": detail})
    failures = [row for row in cases if row["status"] == "FAIL"]
    runnable = [row for row in cases if row["status"] in {"PASS", "FAIL"}]
    overall = "FAIL" if failures else ("PASS" if runnable and len(runnable) == len(cases) and all(r["status"] == "PASS" for r in cases) else "PARTIAL")
    evidence_dir = create_evidence_dir(args.report, "GS130_BOARD_HIL")
    for name in ("c3", "s3"):
        (evidence_dir / f"{name}_serial_redacted.log").write_text(logs[name] + "\n")
    source_head = current_source_head()
    report = {
        "schema_version": 1, "campaign": "GS-130 automated observational board HIL",
        "fixture_id": FIXTURE["fixture_id"], "source_head": source_head,
        "firmware_source_head": FIXTURE["firmware_source_head"],
        "firmware_version_expected": FIXTURE["firmware_version"],
        "image_sha256_expected": {n: FIXTURE["boards"][n]["image_sha256"] for n in ("c3", "s3")},
        "flash_readback_hash_verified": False, "config_fingerprint_observed": False,
        "start_utc": start, "end_utc": end, "duration_seconds": args.seconds,
        "ports": {"c3": args.c3_port, "s3": args.s3_port},
        "cases": cases, "overall": overall,
        "hardware_actions": ["UART open/read only after typed confirmation"],
        "physical_qualification_complete": False, "release_approved": False,
    }
    write_report(evidence_dir / "board_hil_results.json", report)
    for row in cases:
        print(f"{row['test_id']} {row['status']}: {row['detail']}")
    print(f"AUTOMATED BOARD HIL RESULT {overall} cases={len(cases)} evidence={evidence_dir}")
    return report_exit_code(overall)


if __name__ == "__main__":
    raise SystemExit(main())
