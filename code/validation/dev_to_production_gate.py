#!/usr/bin/env python3
"""Validate the GS-173 DEV-to-production register for RC NO-GO conditions."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

PRODUCT = Path(__file__).resolve().parents[1]
REPOSITORY = PRODUCT.parent
REGISTER = REPOSITORY / "docs/product/DEV_TO_PRODUCTION_REGISTER.json"
MARKDOWN = REPOSITORY / "docs/product/DEV_TO_PRODUCTION_REGISTER.md"
SHA = re.compile(r"^[0-9a-f]{40}$")
IMPLEMENTATION_STATES = {"IMPLEMENTED_DISABLED", "PARTIAL", "MISSING", "BLOCKED"}
DEV_STATES = {"ACTIVE_ISOLATED", "PARTIAL", "BLOCKED", "NOT_VERIFIED", "DISABLED"}
PROD_STATES = {"QUALIFIED", "PARTIAL", "MISSING", "BLOCKED", "NOT_VERIFIED", "NOT_RUN"}
GATE_STATES = {"PASS", "FAIL", "BLOCKED", "PARTIAL", "NOT_RUN"}
REQUIRED = {
    "gate_id", "component_requirement", "owning_jira", "scope", "source_paths",
    "dev_effective_config", "implementation_state", "dev_effective_state", "dev_state_detail",
    "prod_readiness", "deferred_or_missing", "test_identity_termination",
    "production_switch_over", "dependencies_and_approvals", "security_rollback",
    "required_tests", "acceptance", "evidence", "release_blocking", "gate_status",
    "accountable_reviewer", "owner_security_approval", "last_verified_commit"
}


def audit_register(path: Path = REGISTER, markdown_path: Path = MARKDOWN
                   ) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [], [f"register unreadable/invalid JSON: {error}"]
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        return [], ["schema_version must be 1"]
    if data.get("register_owner") != "GS-173" or data.get("validation_owner") != "GS-116":
        errors.append("register ownership must be GS-173 with GS-116 gate enforcement")
    if SHA.fullmatch(str(data.get("source_commit", ""))) is None:
        errors.append("source_commit must be a full commit SHA")
    rows = data.get("items")
    if not isinstance(rows, list) or not rows:
        return [], errors + ["items must be a nonempty array"]
    ids: list[str] = []
    for item in rows:
        if not isinstance(item, dict):
            errors.append("each item must be an object")
            continue
        gate = str(item.get("gate_id", "")).strip() or "UNKNOWN"
        ids.append(gate)
        empty = [field for field in REQUIRED if field not in item or item[field] in (None, "", [])]
        if empty:
            errors.append(f"{gate}: missing fields {','.join(sorted(empty))}")
        if item.get("implementation_state") not in IMPLEMENTATION_STATES:
            errors.append(f"{gate}: invalid implementation_state")
        if item.get("dev_effective_state") not in DEV_STATES:
            errors.append(f"{gate}: invalid dev_effective_state")
        if item.get("prod_readiness") not in PROD_STATES:
            errors.append(f"{gate}: invalid prod_readiness")
        if item.get("gate_status") not in GATE_STATES:
            errors.append(f"{gate}: invalid gate_status")
        if item.get("scope") not in {"MANDATORY_R1", "APPROVED_POST_R1", "CONDITIONAL", "SCOPE_PENDING"}:
            errors.append(f"{gate}: invalid scope")
        if not isinstance(item.get("release_blocking"), bool):
            errors.append(f"{gate}: release_blocking must be boolean")
        if SHA.fullmatch(str(item.get("last_verified_commit", ""))) is None:
            errors.append(f"{gate}: last_verified_commit must be a full commit SHA")
        for field in ("owning_jira", "source_paths", "dependencies_and_approvals", "required_tests"):
            if not isinstance(item.get(field), list) or not item[field]:
                errors.append(f"{gate}: {field} must be a nonempty array")
        for source in item.get("source_paths", []):
            source = str(source)
            if source.startswith("NO_SWITCH_EXISTS:"):
                continue
            if not (REPOSITORY / source).is_file():
                errors.append(f"{gate}: source path missing: {source}")
    if len(set(ids)) != len(ids) or any(re.fullmatch(r"DTP-\d{3}", value) is None for value in ids):
        errors.append("gate IDs must be unique DTP-NNN values")
    try:
        markdown = markdown_path.read_text(encoding="utf-8")
    except OSError as error:
        return rows, errors + [f"human-readable register unavailable: {error}"]
    table_ids = re.findall(r"^\| (DTP-\d{3}) \|", markdown, re.M)
    if table_ids != ids:
        errors.append("Markdown gate IDs/order do not match JSON items")
    return rows, errors


def release_blockers(rows: list[dict[str, Any]]) -> list[str]:
    blockers = []
    for item in rows:
        pending_scope = item.get("scope") == "SCOPE_PENDING"
        incomplete = (item.get("gate_status") != "PASS" or
                      item.get("prod_readiness") != "QUALIFIED")
        if pending_scope or (item.get("release_blocking") is True and incomplete):
            blockers.append(str(item.get("gate_id", "UNKNOWN")))
    return blockers


def main() -> int:
    rows, errors = audit_register()
    if errors:
        print("DEV TO PRODUCTION RELEASE GATE FAIL " + "; ".join(errors))
        return 1
    blockers = release_blockers(rows)
    if blockers:
        print("DEV TO PRODUCTION RELEASE GATE BLOCKED "
              f"open={len(blockers)} gates={','.join(blockers)}")
        return 1
    print(f"DEV TO PRODUCTION RELEASE GATE PASS gates={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
