#!/usr/bin/env python3
"""Guided genuine AM312 optical PIR and GPIO4 evidence; never injects motion."""
from __future__ import annotations
import argparse
from pathlib import Path
import re
import sys

from gs130_hil_common import (FIXTURE, ReadOnlyCapture, TOKEN, current_source_head,
                              create_evidence_dir, report_exit_code, utc_now, verify_preflight, write_report)

CASES = (
    ("C8-P2", "Wait for BAT_SLEEP_ENTER. Move once through the installed AM312 field of view. Do not use INJECT_MOTION."),
    ("C8-P3", "After the first event, allow the AM312 output to return LOW; then create one real sustained HIGH episode and allow it to clear."),
    ("C8-P4", "After sleep eligibility is restored, create one real AM312 motion while the Node is asleep and capture wake, restore, EventKey and durable ACK."),
)


def record_pre_run(args, status, detail):
    evidence_dir = create_evidence_dir(args.report, "GS130_MOTION_HIL")
    report = {
        "schema_version": 1, "campaign": "GS-130 guided genuine motion HIL",
        "fixture_id": FIXTURE["fixture_id"], "source_head": current_source_head(),
        "firmware_source_head": FIXTURE["firmware_source_head"],
        "image_sha256_expected": {n: FIXTURE["boards"][n]["image_sha256"] for n in ("c3", "s3")},
        "flash_readback_hash_verified": False,
        "ports": {"c3": args.c3_port, "s3": args.s3_port},
        "cases": [{"test_id": case_id, "status": status, "instruction": instruction, "detail": detail}
                  for case_id, instruction in CASES],
        "overall": status, "motion_source": "operator-confirmed physical AM312 movement; injected motion rejected",
        "hardware_actions": [], "physical_qualification_complete": False, "release_approved": False,
    }
    write_report(evidence_dir / "motion_hil_results.json", report)
    print(f"MANUAL-ASSISTED MOTION HIL RESULT {status} cases={len(CASES)} evidence={evidence_dir}")


def evaluate_motion_evidence(c3: str, s3: str):
    text = c3 + "\n" + s3
    if "INJECT_MOTION" in text:
        return "FAIL", "Injected motion appeared in evidence; it cannot qualify optical PIR."
    required = ("BAT_SLEEP_WAKE", "cause=GPIO", "gpio4=1", "BAT_SLEEP_RESTORE", "PIR -> NodeRuntime", "NodeMessage sent")
    missing = [item for item in required if item not in c3]
    key_match = re.search(r"(?:EventKey|event_key)\s*[:=]\s*([A-Za-z0-9:._-]+)", c3, re.I)
    if key_match is None:
        missing.append("C3 EventKey")
    else:
        key = key_match.group(1)
        c3_lines = c3.splitlines()
        authenticated_ack = any(
            key in line and "authenticated" in line.lower() and
            any(token in line.lower() for token in ("application ack", "durable ack", "durable_ack"))
            for line in s3.splitlines()
        )
        if key not in s3:
            missing.append("same EventKey observed in S3 Hub log")
        retired = any(key in line and ("retired" in line.lower() or "pending=0" in line.lower()) for line in c3_lines)
        if not authenticated_ack:
            missing.append("authenticated application Durable ACK for the same EventKey")
        if not retired:
            missing.append("Node retirement for the same EventKey")
    if missing:
        return "BLOCKED", "Missing independently observable evidence: " + ", ".join(missing)
    return "PASS", "Real GPIO4 wake, one Node event, S3 process and application ACK markers observed; review exact key/counter deltas."


def overall_motion_status(cases):
    statuses = [item["status"] for item in cases]
    if "FAIL" in statuses:
        return "FAIL"
    if len(statuses) == len(CASES) and all(status == "PASS" for status in statuses):
        return "PASS"
    if not statuses or all(status == "NOT_RUN" for status in statuses):
        return "NOT_RUN"
    return "PARTIAL"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="enter operator-assisted serial capture; no stimulus is sent")
    parser.add_argument("--c3-port")
    parser.add_argument("--s3-port")
    parser.add_argument("--c3-image", type=Path)
    parser.add_argument("--s3-image", type=Path)
    parser.add_argument("--capture-seconds", type=int, default=30)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if not args.run:
        print("MANUAL-ASSISTED MOTION HIL NOT_RUN: no port opened and no physical stimulus requested.")
        for case_id, instruction in CASES:
            print(f"{case_id} NOT_RUN: {instruction}")
        record_pre_run(args, "NOT_RUN", "No --run flag; no hardware interface was opened or stimulus requested.")
        return 3
    if not 10 <= args.capture_seconds <= 180:
        print("BLOCKED: each capture must be 10..180 seconds")
        record_pre_run(args, "BLOCKED", "Capture interval is outside the bounded supported range.")
        return 3
    failures = verify_preflight(args.c3_port, args.s3_port, args.c3_image, args.s3_image)
    if failures:
        for failure in failures:
            print("BLOCKED:", failure)
        record_pre_run(args, "BLOCKED", "; ".join(failures))
        return 3
    print("Read-only manual HIL plan (no serial writes, reset, power interruption, erase, enrollment, wiring changes or injection):")
    for case_id, instruction in CASES:
        print(f"  {case_id}: {instruction}")
    print("Serial open can still affect reset lines. Continue only after explicit user approval for this exact plan and a verified non-resetting adapter.")
    if input(f"Type exactly 'OBSERVE {FIXTURE['fixture_id']}' to open the pinned read-only streams: ").strip() != TOKEN:
        print("BLOCKED: fixture observation not authorized")
        record_pre_run(args, "BLOCKED", "Explicit fixture/operator confirmation was not supplied; no UART was opened.")
        return 3
    capture = ReadOnlyCapture({"c3": args.c3_port, "s3": args.s3_port})
    try:
        capture.open()
    except (OSError, ImportError) as error:
        capture.close()
        print("BLOCKED: safe serial observation unavailable:", error)
        record_pre_run(args, "BLOCKED", f"Read-only serial capture could not start safely: {error}")
        return 3
    start = utc_now()
    cases = []
    all_logs = {"c3": [], "s3": []}
    aborted = False
    try:
        for case_id, instruction in CASES:
            print(f"\n{case_id}: {instruction}")
            print("Do not reset, power-cycle, inject, re-enroll, rewire or interrupt storage.")
            answer = input(f"When ready, press Enter; then perform the genuine motion during the next {args.capture_seconds}s capture. Type ABORT to stop: ").strip()
            if answer.upper() == "ABORT":
                cases.append({"test_id": case_id, "status": "NOT_RUN", "detail": "Operator safely aborted before stimulus."})
                aborted = True
                break
            case_start = utc_now()
            window = capture.window(args.capture_seconds)
            for name in all_logs:
                all_logs[name].append(window[name])
            status, detail = evaluate_motion_evidence(window["c3"], window["s3"])
            cases.append({"test_id": case_id, "status": status, "instruction": instruction,
                          "start_utc": case_start, "end_utc": utc_now(), "detail": detail})
            print(f"{case_id} {status}: {detail}")
    finally:
        capture.close()
    end = utc_now()
    evidence_dir = create_evidence_dir(args.report, "GS130_MOTION_HIL")
    for name in all_logs:
        (evidence_dir / f"{name}_serial_redacted.log").write_text("\n".join(all_logs[name]) + "\n")
    source_head = current_source_head()
    overall = overall_motion_status(cases)
    report = {
        "schema_version": 1, "campaign": "GS-130 guided genuine motion HIL",
        "fixture_id": FIXTURE["fixture_id"], "source_head": source_head,
        "firmware_source_head": FIXTURE["firmware_source_head"],
        "image_sha256_expected": {n: FIXTURE["boards"][n]["image_sha256"] for n in ("c3", "s3")},
        "flash_readback_hash_verified": False, "start_utc": start, "end_utc": end,
        "ports": {"c3": args.c3_port, "s3": args.s3_port}, "cases": cases,
        "overall": overall,
        "motion_source": "operator-confirmed physical AM312 movement; injected motion rejected",
        "hardware_actions": ["read-only UART observation", "operator-presented real sensor stimulus"],
        "physical_qualification_complete": False, "release_approved": False,
    }
    write_report(evidence_dir / "motion_hil_results.json", report)
    print(f"MANUAL-ASSISTED MOTION HIL RESULT {report['overall']} cases={len(cases)}/{len(CASES)} evidence={evidence_dir}")
    return report_exit_code(overall)


if __name__ == "__main__":
    raise SystemExit(main())
