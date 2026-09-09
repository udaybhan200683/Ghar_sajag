#!/usr/bin/env python3
# Ghar Sajag traceability edition 2.0 | source release 1.4.2
# @module T01 Simulation/CI
# @requirements E08, E10, V01, AI01, AI03, NFR-08
# Requirement links identify design responsibility, not completed acceptance coverage.
# See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
# The Makefile builds host C++17 and runs Python/JavaScript tests plus simulator fixtures. Tests prove
# their asserted paths, not every SRD criterion. Keep a clean command transcript and attach additional
# scenario tests as requirements are integrated.

"""Compile and execute representative feature-flag simulator variants."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
CASES = {
    "p0_default": "-DGS_FEATURE_MORNING_ROUTINE=1 -DGS_FEATURE_CALL_FAMILY=1 -DGS_FEATURE_LOCAL_OFFLINE=1",
    "routine_disabled": "-DGS_FEATURE_MORNING_ROUTINE=0",
    "call_disabled": "-DGS_FEATURE_CALL_FAMILY=0",
    "offline_disabled": "-DGS_FEATURE_LOCAL_OFFLINE=0",
}

def run_case(name: str, flags: str) -> dict:
    subprocess.run(["make", "clean"], cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    result = subprocess.run(["make", "simulator", f"TRACE_FLAGS={flags}"], cwd=ROOT, check=True, capture_output=True, text=True)
    start = result.stdout.find("{\n")
    decoded, _ = json.JSONDecoder().raw_decode(result.stdout[start:])
    return {"case": name, **decoded}

if __name__ == "__main__":
    results = [run_case(name, flags) for name, flags in CASES.items()]
    for result in results:
        print(json.dumps(result, sort_keys=True))
