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
sys.path.insert(0,str(ROOT))
from tools.validation.component_gate import run_process, source_fingerprint
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
    # Final release owns complete software validation. Extended diagnostics
    # remain separate; no environment-only claim of already-passed stages.
    fingerprint = source_fingerprint()
    stages = [
        ("hil-tooling", ["make", "hil-tooling-test"], 300),
        ("hil-host-isolation", ["make", "hil-host-check"], 300),
        ("production-target-build", [sys.executable, "scripts/build_validation_targets.py"], 3600),
        ("master-production-runtime", ["make", "master-validation"], 900),
        ("fota-host-state-machine", ["make", "fota-host-test"], 300),
        ("master-negative-self-test", ["make", "master-validation-self-test"], 300),
        ("deterministic-stress-medium", ["make", "stress-test", "STRESS_PROFILE=MEDIUM"], 1200),
        ("concurrency-household-isolation", ["make", "concurrency-test"], 1200),
        ("authoritative-release-gate-final",
         ["make", "release-gate-final"],
         3600),
        ("extended-100000-event-endurance", ["make", "endurance-test"], 7200),
        ("host-line-branch-coverage", ["make", "validation-coverage"], 1800),
    ]
    if args.hil:
        # Phase 1 has one WSL-first qualification path. The nested target owns
        # software gates, fixture readiness and the authoritative regression.
        stages.append(("connected-target-hil-phase1", ["make", "hil-qualify"], 7200))
    results: list[dict[str, object]] = []
    overall_start = time.monotonic()
    for index, (name, command, timeout) in enumerate(stages, 1):
        started = time.monotonic()
        executed = run_process(command, ROOT, {**os.environ, "PYTHONUNBUFFERED": "1"}, timeout)
        cp = argparse.Namespace(returncode=executed["exit_code"])
        status = ("PASS" if cp.returncode == 0 else
                  "BLOCKED" if name == "connected-target-hil-phase1" and cp.returncode == 2
                  else "FAIL")
        output = executed["output"]
        reason = "" if cp.returncode == 0 else f"exit {cp.returncode}"
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
    if source_fingerprint() != fingerprint:
        results.append({"suite":"source-integrity", "status":"FAIL", "duration":0,
                        "failure_reason":"source changed during campaign", "log":""})
    final_status = write_report(results, branch, commit, dirty, args.hil, overall_start, complete=True)["status"]
    return 0 if final_status == "PASS" else (2 if final_status == "BLOCKED" else 1)


def write_report(results: list[dict[str, object]], branch: str, commit: str, dirty: bool,
                 hil: bool, started: float, complete: bool = False) -> dict[str, object]:
    failed = sum(r["status"] == "FAIL" for r in results)
    blocked = sum(r["status"] == "BLOCKED" for r in results)
    status = "FAIL" if failed or not results else "BLOCKED" if blocked else "PASS" if complete else "RUNNING"
    report = {"schema": 1, "mode": "HIL_NIGHTLY" if hil else "SIMULATION_NIGHTLY",
              "status": status, "branch": branch,
              "commit": commit, "source_dirty_at_start": dirty, "hil_enabled": hil,
              "total": len(results), "passed": len(results)-failed-blocked, "failed": failed,
              "complete":complete,"physical_status":"NOT_RUN" if not hil else "SEPARATE_HIL_EVIDENCE_REQUIRED",
              "physically_qualified":False,"release_approved":False,
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
