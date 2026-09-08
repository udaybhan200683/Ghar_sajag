#!/usr/bin/env python3
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
