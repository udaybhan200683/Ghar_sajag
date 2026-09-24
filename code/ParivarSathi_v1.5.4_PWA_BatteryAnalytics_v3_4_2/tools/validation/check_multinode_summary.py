#!/usr/bin/env python3
"""Fail-closed shape and per-Node evidence check for the scheduled host campaign."""
from __future__ import annotations

import json
import sys
from pathlib import Path

EXPECTED = {
    "P2-MN01": 1,
    "P2-MN04": 4,
    "P2-MN10": 10,
    "P2-MN25": 25,
    "P2-MN04-RETRY": 4,
    "P2-MN04-ACK-ISOLATION": 4,
    "P2-MN10-OUTAGE": 10,
    "P2-MN10-REMOVE": 10,
    "P2-MN10-REJOIN": 10,
    "P2-MN10-INFLIGHT-REJOIN": 10,
    "P2-MN10-INGRESS-FULL": 10,
    "P2-MN10-JOURNAL-FULL": 10,
    "P2-MN10-FAIRNESS": 10,
}
NODE_NUMBERS = (
    "session", "next_sequence", "retained", "pending", "uplink_attempts",
    "hub_admissions", "matching_acks", "ack_mismatches", "stale_acks",
    "registry_rejections", "ingress_rejections", "application_rejections",
    "volatile_receipts", "maximum_ack_latency_ms",
)


def check(path: Path) -> None:
    report = json.loads(path.read_text())
    if report.get("classification") != "HOST/SIMULATED":
        raise ValueError("physical/simulated classification missing or incorrect")
    count = len(EXPECTED)
    if any(report.get(field) != count for field in
           ("expected_cases", "executed_cases", "passed_cases")):
        raise ValueError("case accounting mismatch")
    cases = report.get("cases")
    if not isinstance(cases, list) or len(cases) != count:
        raise ValueError("mandatory case evidence missing")
    ids = [case.get("id") for case in cases]
    if len(set(ids)) != count or set(ids) != set(EXPECTED):
        raise ValueError("case IDs duplicated or missing")
    for case in cases:
        expected = EXPECTED[case["id"]]
        nodes = case.get("nodes")
        if case.get("status") != "PASS" or not isinstance(nodes, list) or \
                len(nodes) != expected or any(case.get(field) != expected for field in
                                           ("expected_nodes", "executed_nodes", "passed_nodes")):
            raise ValueError(f"{case['id']}: per-Node accounting mismatch")
        for field in ("journal", "ingress_high_water", "ingress_rejected"):
            if type(case.get(field)) is not int or case[field] < 0:
                raise ValueError(f"{case['id']}: invalid aggregate {field}")
        for field in ("physical_id", "logical_id", "room"):
            values = [node.get(field) for node in nodes]
            if any(not isinstance(value, str) or not value for value in values) or \
                    len(set(values)) != expected:
                raise ValueError(f"{case['id']}: missing or duplicate {field}")
        for node in nodes:
            if node.get("status") != "PASS" or node.get("commissioned") is not True:
                raise ValueError(f"{case['id']}: Node status or commissioning missing")
            if any(type(node.get(field)) is not int or node[field] < 0
                   for field in NODE_NUMBERS):
                raise ValueError(f"{case['id']}: per-Node metrics missing")
    by_id = {case["id"]: case for case in cases}
    if by_id["P2-MN10-INGRESS-FULL"]["ingress_high_water"] != 32 or \
            by_id["P2-MN10-INGRESS-FULL"]["ingress_rejected"] <= 0 or \
            by_id["P2-MN10-JOURNAL-FULL"]["journal"] != 8:
        raise ValueError("bounded pressure metrics missing")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_multinode_summary.py <summary.json>")
    try:
        check(Path(sys.argv[1]))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise SystemExit(f"P2-MULTINODE EVIDENCE FAIL: {exc}") from exc
    print("P2-MULTINODE EVIDENCE PASS 13 cases with per-Node metrics")
