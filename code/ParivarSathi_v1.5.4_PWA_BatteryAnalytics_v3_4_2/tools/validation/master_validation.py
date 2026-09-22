#!/usr/bin/env python3
"""Run ID-addressable production-runtime validation and emit JSON/JUnit evidence."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BINARY = ROOT / "build/master_validation"
EVIDENCE = ROOT / "evidence/master_validation"
SEED = 23063


def parse_rows(output: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in output.splitlines():
        fields = line.split("\t")
        if len(fields) < 5 or fields[0] not in {"PASS", "FAIL"}:
            continue
        rows.append({"status": fields[0], "id": fields[1], "suite": fields[2],
                     "duration_ms": int(fields[3]), "feature_mapping": fields[4],
                     "failure_reason": "\t".join(fields[5:]),
                     "layer": "L2", "seed": SEED})
    return rows


def git_value(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, text=True,
                          stdout=subprocess.PIPE).stdout.strip()


def write_reports(rows: list[dict[str, object]], output: str, command: list[str]) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    failures = [row for row in rows if row["status"] == "FAIL"]
    suites: dict[str, dict[str, int]] = {}
    for row in rows:
        bucket = suites.setdefault(str(row["suite"]), {"total": 0, "passed": 0, "failed": 0})
        bucket["total"] += 1
        bucket["passed" if row["status"] == "PASS" else "failed"] += 1
    report = {
        "schema": 1, "status": "FAIL" if failures else "PASS", "seed": SEED,
        "commit": git_value("rev-parse", "HEAD"), "command": command,
        "total": len(rows), "passed": len(rows) - len(failures), "failed": len(failures),
        "skipped": 0, "blocked": 0, "duration_ms": sum(int(r["duration_ms"]) for r in rows),
        "suites": suites, "tests": rows,
    }
    (EVIDENCE / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    (EVIDENCE / "runner.log").write_text(output)
    root = ET.Element("testsuite", name="master-validation", tests=str(len(rows)),
                      failures=str(len(failures)), time=str(report["duration_ms"] / 1000))
    for row in rows:
        case = ET.SubElement(root, "testcase", classname=str(row["suite"]),
                             name=str(row["id"]), time=str(int(row["duration_ms"]) / 1000))
        if row["status"] == "FAIL":
            ET.SubElement(case, "failure", message=str(row["failure_reason"])).text = str(row["failure_reason"])
    ET.ElementTree(root).write(EVIDENCE / "junit.xml", encoding="utf-8", xml_declaration=True)


def controlled_self_test() -> int:
    target = "OR-001"
    env = {**os.environ, "GS_VALIDATION_INJECT_FAILURE": target}
    cp = subprocess.run([str(BINARY), "--id", target], cwd=ROOT, env=env, text=True,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    passed = cp.returncode != 0 and f"FAIL\t{target}\t" in cp.stdout
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    record = {"status": "PASS" if passed else "FAIL", "injected_tc": target,
              "child_returncode": cp.returncode, "detected_specific_tc": f"FAIL\t{target}\t" in cp.stdout,
              "parent_failed": cp.returncode != 0}
    (EVIDENCE / "negative_self_test.json").write_text(json.dumps(record, indent=2) + "\n")
    (EVIDENCE / "negative_self_test.log").write_text(cp.stdout)
    print(f"VALIDATION NEGATIVE SELF-TEST: {record['status']} ({target})")
    return 0 if passed else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--id")
    group.add_argument("--suite")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if not BINARY.is_file():
        print(f"missing validation binary: {BINARY}; run make master-validation", file=sys.stderr)
        return 2
    if args.self_test:
        return controlled_self_test()
    command = [str(BINARY)]
    if args.id: command += ["--id", args.id]
    if args.suite: command += ["--suite", args.suite]
    started = time.monotonic()
    cp = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT)
    rows = parse_rows(cp.stdout)
    if not rows:
        print(cp.stdout, end="")
        print("master validation produced no test records", file=sys.stderr)
        return 2
    write_reports(rows, cp.stdout, command)
    print(cp.stdout, end="")
    print(f"MASTER VALIDATION: {'PASS' if cp.returncode == 0 else 'FAIL'}; "
          f"tests={len(rows)} seed={SEED} wall_seconds={time.monotonic()-started:.2f}")
    return cp.returncode


if __name__ == "__main__":
    raise SystemExit(main())
