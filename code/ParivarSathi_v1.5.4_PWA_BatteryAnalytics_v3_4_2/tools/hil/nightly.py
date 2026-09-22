#!/usr/bin/env python3
"""Fail-closed entry point for unattended connected-target validation.

The current target firmware exposes serial evidence but no safe remote GPIO/power
controller. This runner therefore validates explicit board/port configuration and
runs a configured repository-local adapter. Absence of hardware or an adapter is
BLOCKED and non-zero; it can never become a false PASS.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence/hil_nightly"
ADAPTER_REPORT = EVIDENCE / "adapter_result.json"


def validate_adapter_report(path: Path, commit: str, hub_id: str, c3_id: str) -> list[str]:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return [f"invalid or missing adapter report {path}: {exc}"]
    errors = []
    if data.get("status") != "PASS": errors.append("adapter report status is not PASS")
    if data.get("commit") != commit: errors.append("adapter report commit does not match requested commit")
    required_suites = {"HIL-SMOKE", "HIL-OFFLINE", "HIL-FOTA", "HIL-RESTART", "HIL-STRESS", "HIL-SOAK"}
    passed_suites = {row.get("id") for row in data.get("suites", []) if row.get("status") == "PASS"}
    missing_suites = sorted(required_suites - passed_suites)
    if missing_suites: errors.append("mandatory HIL suites not PASS: " + ", ".join(missing_suites))
    for label, expected in (("hub", hub_id), ("c3", c3_id)):
        target = data.get(label, {})
        if target.get("identity") != expected: errors.append(f"{label} identity mismatch")
        version = str(target.get("version", ""))
        if not version or "-dirty" in version: errors.append(f"{label} version missing or dirty")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", str(target.get("sha256", ""))):
            errors.append(f"{label} SHA256 missing or invalid")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--soak-minutes", type=int, default=0)
    args = parser.parse_args()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    hub_port = os.environ.get("HIL_HUB_PORT", "")
    c3_port = os.environ.get("HIL_C3_PORT", "")
    hub_id = os.environ.get("HIL_EXPECTED_HUB_ID", "")
    c3_id = os.environ.get("HIL_EXPECTED_C3_ID", "")
    adapter = os.environ.get(
        "HIL_ADAPTER_COMMAND", f"{os.fspath(Path(os.sys.executable))} tools/hil/esp_idf_adapter.py")
    auto_discover = os.environ.get("HIL_AUTO_DISCOVER") == "1"
    missing = []
    for label, value in (("HIL_HUB_PORT", hub_port), ("HIL_C3_PORT", c3_port)):
        if not value and not auto_discover: missing.append(f"{label} is not configured (or set HIL_AUTO_DISCOVER=1)")
        elif value and value.lower() != "auto" and os.name != "nt" and not Path(value).exists(): missing.append(f"{label} does not exist: {value}")
    if not hub_id: missing.append("HIL_EXPECTED_HUB_ID is not configured")
    if not c3_id: missing.append("HIL_EXPECTED_C3_ID is not configured")
    commit = subprocess.run(["git","rev-parse","HEAD"], cwd=ROOT, check=True,
                            text=True,stdout=subprocess.PIPE).stdout.strip()
    report: dict[str, object] = {"schema": 1, "status": "BLOCKED", "hub_port": hub_port,
                                 "c3_port": c3_port, "soak_minutes": args.soak_minutes,
                                 "expected_hub_identity": hub_id, "expected_c3_identity": c3_id,
                                 "commit": commit,
                                 "reasons": missing}
    if missing:
        (EVIDENCE / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
        print("HIL NIGHTLY: BLOCKED — " + "; ".join(missing))
        return 2
    command = shlex.split(adapter) + ["--hub-port", hub_port or "auto", "--c3-port", c3_port or "auto",
                                      "--expected-hub-id", hub_id, "--expected-c3-id", c3_id,
                                      "--commit", commit, "--report", str(ADAPTER_REPORT),
                                      "--soak-minutes", str(args.soak_minutes)]
    started = time.monotonic()
    cp = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT)
    (EVIDENCE / "adapter.log").write_text(cp.stdout or "")
    validation_errors = validate_adapter_report(ADAPTER_REPORT, commit, hub_id, c3_id)
    status = "PASS" if cp.returncode == 0 and not validation_errors else "FAIL"
    report.update({"status": status,
                   "duration": round(time.monotonic()-started, 3), "command": command,
                   "returncode": cp.returncode, "adapter_report": str(ADAPTER_REPORT.relative_to(ROOT)),
                   "validation_errors": validation_errors})
    (EVIDENCE / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"HIL NIGHTLY: {report['status']}")
    return 0 if status == "PASS" else (cp.returncode or 1)


if __name__ == "__main__":
    raise SystemExit(main())
