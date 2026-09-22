#!/usr/bin/env python3
"""Fail-fast, hardware-free-by-default master nightly validation runner."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parents[1]
EVIDENCE = ROOT / "evidence/validation_nightly"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, check=True, text=True,
                          stdout=subprocess.PIPE).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hil", action="store_true")
    parser.add_argument("--hil-soak-minutes", type=int, default=0)
    parser.add_argument("--continue-on-failure", action="store_true")
    args = parser.parse_args()
    if args.hil_soak_minutes < 0:
        parser.error("--hil-soak-minutes must be non-negative")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    commit = git("rev-parse", "HEAD")
    branch = git("branch", "--show-current")
    dirty = bool(git("status", "--porcelain"))
    # Expensive suites have one owner. The parent runs master/FOTA/MEDIUM, so
    # release-gate-final records those as already passed and does not repeat
    # them; its SMALL stress is superseded by MEDIUM here.
    stages = [
        ("master-production-runtime", ["make", "master-validation"], 900),
        ("fota-host-state-machine", ["make", "fota-host-test"], 300),
        ("master-negative-self-test", ["make", "master-validation-self-test"], 300),
        ("deterministic-stress-medium", ["make", "stress-test", "STRESS_PROFILE=MEDIUM"], 1200),
        ("concurrency-household-isolation", ["make", "concurrency-test"], 1200),
        ("authoritative-release-gate-final",
         ["make", "release-gate-final", "GS_RELEASE_GATE_SKIP_MASTER=1",
          "GS_RELEASE_GATE_SKIP_FOTA_HOST=1", "RELEASE_GATE_FINAL_SKIP_PERFORMANCE=1"],
         3600),
        ("extended-100000-event-endurance", ["make", "endurance-test"], 7200),
        ("host-line-branch-coverage", ["make", "validation-coverage"], 1800),
    ]
    if args.hil:
        stages.append(("connected-target-hil", [sys.executable, "tools/hil/nightly.py",
                                        "--soak-minutes", str(args.hil_soak_minutes)],
                       max(1800, args.hil_soak_minutes * 60 + 900)))
    results: list[dict[str, object]] = []
    overall_start = time.monotonic()
    for index, (name, command, timeout) in enumerate(stages, 1):
        started = time.monotonic()
        try:
            cp = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=timeout,
                                env={**os.environ, "PYTHONUNBUFFERED": "1"})
            status = ("PASS" if cp.returncode == 0 else
                      "BLOCKED" if name == "connected-target-hil" and cp.returncode == 2
                      else "FAIL")
            output = cp.stdout or ""
            reason = "" if cp.returncode == 0 else f"exit {cp.returncode}"
        except subprocess.TimeoutExpired as exc:
            status, reason = "FAIL", f"timeout after {timeout}s"
            output = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        log = EVIDENCE / f"{index:02d}_{name}.log"
        log.write_text(output)
        row = {"suite": name, "status": status, "duration": round(time.monotonic()-started, 3),
               "failure_reason": reason, "command": command, "log": str(log.relative_to(ROOT)),
               "commit": commit, "seed": 23063}
        results.append(row)
        print(f"{status} {name} ({row['duration']}s)", flush=True)
        write_report(results, branch, commit, dirty, args.hil, overall_start)
        if status != "PASS" and not args.continue_on_failure:
            print("Fail-fast: later expensive stages were not run.", flush=True)
            return 2 if status == "BLOCKED" else 1
    final_status = write_report(results, branch, commit, dirty, args.hil, overall_start)["status"]
    return 0 if final_status == "PASS" else (2 if final_status == "BLOCKED" else 1)


def write_report(results: list[dict[str, object]], branch: str, commit: str, dirty: bool,
                 hil: bool, started: float) -> dict[str, object]:
    failed = sum(r["status"] == "FAIL" for r in results)
    blocked = sum(r["status"] == "BLOCKED" for r in results)
    status = "FAIL" if failed else "BLOCKED" if blocked else "PASS"
    report = {"schema": 1, "mode": "HIL_NIGHTLY" if hil else "SIMULATION_NIGHTLY",
              "status": status, "branch": branch,
              "commit": commit, "source_dirty_at_start": dirty, "hil_enabled": hil,
              "total": len(results), "passed": len(results)-failed, "failed": failed,
              "skipped": 0, "blocked": blocked, "duration": round(time.monotonic()-started, 3),
              "suites": results}
    (EVIDENCE / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = ["# Validation nightly", "", f"Result: **{report['status']}**", "",
             f"Commit: `{commit}`", f"Seed: `23063`", "", "| Suite | Status | Seconds | Log |",
             "|---|---:|---:|---|"]
    for row in results:
        lines.append(f"| {row['suite']} | {row['status']} | {row['duration']} | `{row['log']}` |")
    (EVIDENCE / "summary.md").write_text("\n".join(lines) + "\n")
    return report


if __name__ == "__main__":
    raise SystemExit(main())
