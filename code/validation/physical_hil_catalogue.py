#!/usr/bin/env python3
"""Validate physical-HIL traceability and block release on missing evidence."""
from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path

PRODUCT = Path(__file__).resolve().parents[1]
REPO = PRODUCT.parent
CATALOGUE = REPO / "docs/validation/PHYSICAL_HIL_CATALOGUE.csv"
TRACEABILITY = REPO / "docs/validation/MASTER_TRACEABILITY.csv"
ALLOWED_STATUS = {"PASS", "PARTIAL", "FAIL", "BLOCKED", "NOT_RUN", "HISTORICAL_EVIDENCE_ONLY"}
REQUIRED_FIELDS = {
    "TEST_ID", "FEATURE_IDS", "REQUIREMENT_IDS", "JIRA_OWNER", "HARDWARE_PROFILE",
    "DESCRIPTION", "EXECUTION_CLASS", "PREREQUISITES", "SAFETY_CLASS",
    "COMMAND_OR_PROCEDURE", "EXPECTED_OBSERVABLE", "FAILURE_CONDITIONS",
    "LAST_EXECUTION_UTC", "SOURCE_HEAD", "IMAGE_SHA256", "FIXTURE_ID", "STATUS",
    "EVIDENCE", "RELEASE_BLOCKING", "LIMITATIONS",
}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def validate(catalogue_path: Path = CATALOGUE, traceability_path: Path = TRACEABILITY,
             require_release: bool = False) -> tuple[list[str], int, int, int]:
    errors: list[str] = []
    rows = read_rows(catalogue_path)
    trace = read_rows(traceability_path)
    if not rows:
        return ["empty physical HIL catalogue"], 0, 0
    missing = REQUIRED_FIELDS - set(rows[0])
    if missing:
        errors.append("catalogue missing columns: " + ",".join(sorted(missing)))
    ids = [r.get("TEST_ID", "").strip() for r in rows]
    if not all(ids) or len(ids) != len(set(ids)):
        errors.append("test IDs must be nonempty and unique")
    by_id = set(ids)
    for row in rows:
        if row.get("STATUS") not in ALLOWED_STATUS:
            errors.append(f"{row.get('TEST_ID')}: invalid status {row.get('STATUS')!r}")
        if row.get("RELEASE_BLOCKING") not in {"YES", "NO"}:
            errors.append(f"{row.get('TEST_ID')}: RELEASE_BLOCKING must be YES or NO")
        evidence = row.get("EVIDENCE", "")
        if evidence and not evidence.startswith(("http://", "https://")):
            if not (catalogue_path.parent / evidence).resolve().exists():
                errors.append(f"{row.get('TEST_ID')}: evidence path does not exist: {evidence}")
        if row.get("STATUS") == "PASS":
            if not re.fullmatch(r"[0-9a-f]{40}", row.get("SOURCE_HEAD", "")):
                errors.append(f"{row.get('TEST_ID')}: PASS lacks exact source HEAD")
            hashes = re.findall(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])", row.get("IMAGE_SHA256", ""))
            if not hashes:
                errors.append(f"{row.get('TEST_ID')}: PASS lacks image SHA-256")
            if evidence and not evidence.startswith(("http://", "https://")) and not (catalogue_path.parent / evidence).resolve().is_file():
                errors.append(f"{row.get('TEST_ID')}: PASS lacks evidence file")
    required_features = 0
    conditional_features = 0
    for row in trace:
        if row.get("IMPLEMENTATION_STATUS") not in {"IMPLEMENTED", "PARTIALLY_IMPLEMENTED"}:
            continue
        physical_class = row.get("PHYSICAL_CLASS")
        if physical_class not in {"PHYSICAL_REQUIRED", "PHYSICAL_CONDITIONAL"}:
            continue
        if physical_class == "PHYSICAL_REQUIRED":
            required_features += 1
        else:
            conditional_features += 1
        refs = [x.strip() for x in row.get("PHYSICAL_TEST_ID", "").split(";") if x.strip()]
        if not refs or any(ref not in by_id for ref in refs):
            errors.append(f"{row.get('FEATURE_ID')}: {physical_class} row has unresolved HIL test ID {refs}")
    blockers = [r for r in rows if r.get("RELEASE_BLOCKING") == "YES"]
    if require_release:
        for row in blockers:
            if row.get("STATUS") != "PASS":
                errors.append(f"release evidence incomplete: {row['TEST_ID']}={row.get('STATUS')}")
            if row.get("SOURCE_HEAD") in {"", "NOT_RUN", "HISTORICAL", "UNVERIFIED_CLASSIC_IMAGE"}:
                errors.append(f"release evidence has no current-source provenance: {row['TEST_ID']}")
            if not re.search(r"[0-9a-f]{64}", row.get("IMAGE_SHA256", "")):
                errors.append(f"release evidence has no image hash: {row['TEST_ID']}")
    return errors, len(rows), required_features, conditional_features


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="check case catalogue and feature traceability; no device access")
    mode.add_argument("--release", action="store_true", help="require every release-blocking physical case to have PASS evidence")
    args = parser.parse_args()
    errors, cases, features, conditional = validate(require_release=args.release)
    if errors:
        for error in errors:
            print("PHYSICAL HIL ERROR: " + error)
        if args.release:
            print(f"PHYSICAL HIL RELEASE EVIDENCE: FAIL cases={cases} required_features={features} conditional_features={conditional}")
        return 1
    if args.release:
        count = sum(r.get("RELEASE_BLOCKING") == "YES" for r in read_rows(CATALOGUE))
        print(f"PHYSICAL HIL RELEASE EVIDENCE: PASS mandatory={count}")
    else:
        print(f"PHYSICAL HIL CATALOGUE: PASS cases={cases} physical_required_features={features} physical_conditional_features={conditional} device_access=NONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
