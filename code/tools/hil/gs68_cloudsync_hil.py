#!/usr/bin/env python3
"""Fail-closed GS-68 CloudSync physical qualification runner.

Default mode is local, read-only planning. It never imports serial, scans USB,
opens a socket, invokes a build/flash tool, or contacts a backend. Physical
execution is opt-in and gated by exact fixture, approval, and operator inputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import gs130_hil_common as common
import gs68_capture as capture

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parents[1]
REPO = PRODUCT.parent
CASE_PLAN = HERE / "gs68_cloudsync_cases.json"
FIXTURE_TEMPLATE = HERE / "gs68_spare_fixture.template.json"
BACKEND_TEMPLATE = HERE / "gs68_test_backend.template.json"
PROTECTED_FIXTURE = HERE / "gs130_fixture.json"
PROFILE = PRODUCT / "firmware/hub/target/esp32s3/idf/sdkconfig.gs68_cloudsync_hil.defaults"
RUNNER_EXECUTION_ENABLED = True
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except (OSError, json.JSONDecodeError) as error:
        return {}, [f"cannot read valid JSON from {path}: {error.__class__.__name__}"]


def _sha256(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _current_code_tree_oid():
    """Return the committed code subtree identity, excluding later docs-only commits."""
    result = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD:code"],
        check=True, capture_output=True, text=True, timeout=5)
    value = result.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError("current code tree identity is invalid")
    return value


def _is_reachable_commit(commit):
    if not COMMIT_RE.fullmatch(str(commit)):
        return False
    result = subprocess.run(["git", "-C", str(REPO), "merge-base", "--is-ancestor", commit, "HEAD"],
        capture_output=True, text=True, timeout=5)
    return result.returncode == 0


def _resolve_repo_file(value, base=REPO):
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def _normalize_mac(value):
    return re.sub(r"[^0-9a-f]", "", str(value).lower())


def _protected_values(protected):
    values = {"fixture_ids": set(), "macs": set(), "serials": set(), "ports": set()}
    values["fixture_ids"].add(protected.get("fixture_id"))
    for board in protected.get("boards", {}).values():
        values["macs"].add(_normalize_mac(board.get("mac", "")))
        values["serials"].add(str(board.get("usb_serial_short", "")).strip().lower())
        values["ports"].add(str(board.get("by_id", "")).strip())
    for key in values:
        values[key].discard("")
        values[key].discard(None)
    return values


def validate_observed_identity(board_name, expected, observed):
    """Compare a future read-only identity receipt without touching a port."""
    errors = []
    if not isinstance(expected, dict):
        return [f"{board_name}: expected identity must be a JSON object"]
    if not isinstance(observed, dict):
        return [f"{board_name}: observed identity receipt is missing"]
    for key in ("mac_address", "usb_serial_short", "port_by_id"):
        expected_value = expected.get(key)
        observed_value = observed.get(key)
        if not expected_value or not observed_value:
            errors.append(f"{board_name}: identity field {key} is incomplete")
        elif key == "mac_address":
            if _normalize_mac(expected_value) != _normalize_mac(observed_value):
                errors.append(f"{board_name}: observed MAC does not match manifest")
        elif str(expected_value).strip().lower() != str(observed_value).strip().lower():
            errors.append(f"{board_name}: observed {key} does not match manifest")
    return errors


def validate_identity_receipt(fixture, base=REPO):
    """Validate a saved, read-only identity observation; never performs discovery."""
    observation = fixture.get("identity_receipt", {})
    if not isinstance(observation, dict):
        return ["identity_receipt must be a JSON object"]
    path = _resolve_repo_file(observation.get("path"), base)
    expected_hash = observation.get("sha256")
    if path is None or not path.is_file():
        return ["read-only spare-fixture identity receipt is missing"]
    if not SHA256_RE.fullmatch(str(expected_hash or "")) or _sha256(path) != expected_hash.lower():
        return ["read-only spare-fixture identity receipt checksum mismatch"]
    receipt, errors = _read_json(path)
    if errors:
        return errors
    if not isinstance(receipt, dict):
        return ["identity receipt must be a JSON object"]
    failures = []
    if receipt.get("fixture_id") != fixture.get("fixture_id"):
        failures.append("identity receipt fixture_id does not match manifest")
    if receipt.get("method") != "READ_ONLY_DEVICE_IDENTITY":
        failures.append("identity receipt method is not a read-only identity observation")
    try:
        observed_at = datetime.fromisoformat(str(receipt.get("observed_at_utc", "")).replace("Z", "+00:00"))
        if observed_at.tzinfo is None:
            failures.append("identity receipt timestamp lacks an explicit UTC offset")
    except ValueError:
        failures.append("identity receipt timestamp is invalid")
    fixture_boards = fixture.get("boards", {})
    if not isinstance(fixture_boards, dict):
        fixture_boards = {}
    observed_boards = receipt.get("boards", {})
    if not isinstance(observed_boards, dict):
        observed_boards = {}
    for name, expected_target in (("s3", "ESP32-S3"), ("c3", "ESP32-C3")):
        expected = fixture_boards.get(name, {})
        observed = observed_boards.get(name, {})
        if not isinstance(expected, dict):
            expected = {}
        if not isinstance(observed, dict):
            observed = {}
        if observed.get("target") != expected_target or observed.get("flash_mb") != expected.get("flash_mb"):
            failures.append(f"{name}: observed target or flash profile does not match manifest")
        if observed.get("psram_mb") != expected.get("psram_mb"):
            failures.append(f"{name}: observed PSRAM profile does not match manifest")
        expected_identity = expected.get("identity", {})
        if not isinstance(expected_identity, dict):
            expected_identity = {}
        failures.extend(validate_observed_identity(name, expected_identity, observed.get("identity")))
    return failures


def validate_fixture(fixture, source_head, case_plan, profile_path=PROFILE,
                     protected=None, base=REPO, observed_identities=None):
    """Validate fixture identity, source/image/profile provenance, and safety."""
    if not isinstance(fixture, dict):
        return ["fixture manifest must be a JSON object"]
    protected = protected if protected is not None else _read_json(PROTECTED_FIXTURE)[0]
    errors = []
    fixture_id = fixture.get("fixture_id")
    if not isinstance(fixture_id, str) or not re.fullmatch(r"GS68-SPARE-[A-Z0-9-]+", fixture_id):
        errors.append("fixture_id must identify a separate GS68-SPARE fixture")
    if fixture_id in _protected_values(protected)["fixture_ids"]:
        errors.append("fixture_id aliases the protected GS-114 C8 fixture")
    if fixture.get("fixture_class") != "DISPOSABLE_RND_ONLY":
        errors.append("fixture_class must be DISPOSABLE_RND_ONLY")
    errors.extend(validate_identity_receipt(fixture, base))

    if fixture.get("source_commit") != source_head or not COMMIT_RE.fullmatch(str(fixture.get("source_commit", ""))):
        errors.append("source_commit must equal the current isolated source HEAD")

    profile = fixture.get("profile", {})
    if not isinstance(profile, dict):
        profile = {}
        errors.append("profile must be a JSON object")
    if profile.get("profile_id") != "GS68_CLOUDSYNC_DS_MTLS_HIL":
        errors.append("profile_id is not the GS-68 test-only profile")
    declared_profile = _resolve_repo_file(profile.get("config_path"), base)
    if declared_profile is None or declared_profile.resolve() != profile_path.resolve():
        errors.append("profile config_path must reference the checked-in GS-68 DS/TLS overlay")
    if not SHA256_RE.fullmatch(str(profile.get("profile_sha256", ""))):
        errors.append("profile_sha256 is missing or malformed")
    elif not profile_path.is_file() or _sha256(profile_path) != profile["profile_sha256"].lower():
        errors.append("profile_sha256 does not match the checked-in DS/TLS test overlay")
    build_report = _resolve_repo_file(profile.get("build_report"), base)
    if build_report is None or not build_report.is_file():
        errors.append("profile build_report is missing")
    else:
        report, report_errors = _read_json(build_report)
        if report_errors:
            errors.extend(report_errors)
        elif not isinstance(report, dict):
            errors.append("profile build report must be a JSON object")
        else:
            if not _is_reachable_commit(report.get("source_commit")):
                errors.append("profile build report source commit is not reachable from current HEAD")
            if report.get("source_code_tree_oid") != _current_code_tree_oid():
                errors.append("profile build report code tree does not match current source")
            if report.get("profile_sha256") != profile.get("profile_sha256"):
                errors.append("profile build report does not match profile hash")
            if report.get("target") not in (None, "ESP32-S3"):
                errors.append("profile build report target is not ESP32-S3")

    boards = fixture.get("boards", {})
    if not isinstance(boards, dict):
        boards = {}
        errors.append("boards must be a JSON object")
    required_boards = {"s3": ("ESP32-S3", 16, 8), "c3": ("ESP32-C3", None, 0)}
    protected_values = _protected_values(protected)
    for name, (target, flash_mb, psram_mb) in required_boards.items():
        board = boards.get(name, {})
        if not isinstance(board, dict):
            board = {}
            errors.append(f"{name}: board entry must be a JSON object")
        if board.get("target") != target:
            errors.append(f"{name}: unexpected target")
        if not isinstance(board.get("flash_mb"), int) or board["flash_mb"] <= 0:
            errors.append(f"{name}: actual flash_mb must be recorded")
        elif flash_mb is not None and board["flash_mb"] != flash_mb:
            errors.append(f"{name}: S3 must be the selected 16 MiB profile")
        if board.get("psram_mb") != psram_mb:
            errors.append(f"{name}: unexpected PSRAM profile")

        identity = board.get("identity", {})
        if not isinstance(identity, dict):
            identity = {}
            errors.append(f"{name}: identity must be a JSON object")
        for key in ("mac_address", "usb_serial_short", "port_by_id"):
            if not isinstance(identity.get(key), str) or not identity[key].strip():
                errors.append(f"{name}: {key} must be recorded from the spare fixture")
        if identity.get("mac_address") and _normalize_mac(identity["mac_address"]) in protected_values["macs"]:
            errors.append(f"{name}: MAC aliases protected C8 hardware")
        if identity.get("usb_serial_short") and identity["usb_serial_short"].strip().lower() in protected_values["serials"]:
            errors.append(f"{name}: USB serial aliases protected C8 hardware")
        if identity.get("port_by_id") and identity["port_by_id"].strip() in protected_values["ports"]:
            errors.append(f"{name}: port aliases protected C8 hardware")
        if observed_identities is not None:
            errors.extend(validate_observed_identity(name, identity, observed_identities.get(name)))

        image = board.get("image", {})
        if not isinstance(image, dict):
            image = {}
            errors.append(f"{name}: image must be a JSON object")
        image_path = _resolve_repo_file(image.get("path"), base)
        if image_path is None or not image_path.is_file():
            errors.append(f"{name}: source-matched image file is missing")
        elif not SHA256_RE.fullmatch(str(image.get("sha256", ""))) or _sha256(image_path) != image["sha256"].lower():
            errors.append(f"{name}: image SHA-256 does not match image file")
    if build_report is not None and build_report.is_file():
        report, report_errors = _read_json(build_report)
        if not report_errors and isinstance(report, dict):
            s3_entry = boards.get("s3", {})
            s3_image_entry = s3_entry.get("image", {}) if isinstance(s3_entry, dict) else {}
            expected_s3_image = s3_image_entry.get("sha256") if isinstance(s3_image_entry, dict) else None
            if report.get("s3_image_sha256", report.get("image_sha256")) != expected_s3_image:
                errors.append("profile build report S3 image hash does not match spare fixture manifest")
    if not isinstance(case_plan, dict) or not isinstance(case_plan.get("cases"), list) or not case_plan.get("cases"):
        errors.append("physical case plan is missing or empty")
    return errors


def validate_authorization(authorization, fixture_id, case_ids, plan_sha256, now=None):
    """Validate an exact future physical authorization; never grants execution."""
    errors = []
    if not isinstance(authorization, dict) or authorization.get("status") != "APPROVED":
        return ["fixture-specific physical authorization is not APPROVED"]
    if not re.fullmatch(r"\d+", str(authorization.get("jira_comment", ""))):
        errors.append("authorization must reference a specific Jira approval comment")
    if authorization.get("fixture_id") != fixture_id:
        errors.append("authorization fixture_id does not match the separate spare fixture")
    approved_cases = authorization.get("authorized_case_ids")
    valid_case_ids = isinstance(case_ids, list) and all(isinstance(case_id, str) and case_id for case_id in case_ids)
    valid_approved_cases = isinstance(approved_cases, list) and all(isinstance(case_id, str) and case_id for case_id in approved_cases)
    if not valid_case_ids or not valid_approved_cases or not approved_cases or not set(approved_cases).issubset(set(case_ids)):
        errors.append("authorization must enumerate approved physical case IDs")
    elif not set(case_ids).issubset(set(approved_cases)):
        # Cases omitted by approval remain disallowed; callers can adjudicate only approved cases.
        pass
    if authorization.get("plan_sha256") != plan_sha256:
        errors.append("authorization does not bind the current physical plan hash")
    if not isinstance(authorization.get("approved_by"), str) or not authorization["approved_by"].strip():
        errors.append("authorization approver is missing")
    try:
        expiry = datetime.fromisoformat(str(authorization.get("expires_utc", "")).replace("Z", "+00:00"))
        current = now or datetime.now(timezone.utc)
        if expiry.tzinfo is None or expiry <= current:
            errors.append("authorization is expired or lacks an explicit UTC offset")
    except ValueError:
        errors.append("authorization expiry is invalid")
    return errors


def validate_backend_descriptor(descriptor):
    """Offline-only checks; deliberately makes no request to the test service."""
    if not isinstance(descriptor, dict):
        return ["backend descriptor must be a JSON object"]
    errors = []
    if descriptor.get("environment") != "TEST_ONLY":
        errors.append("backend environment must be TEST_ONLY")
    if not isinstance(descriptor.get("backend_id"), str) or not descriptor["backend_id"].strip():
        errors.append("backend_id is missing")
    try:
        parsed = urlparse(str(descriptor.get("base_url") or ""))
        hostname = parsed.hostname
    except ValueError:
        parsed, hostname = urlparse(""), None
    if parsed.scheme != "https" or not hostname or not hostname.endswith(".test"):
        errors.append("backend base_url must be an HTTPS .test host")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        errors.append("backend URL must not embed credentials or query data")
    if descriptor.get("server_name") != hostname:
        errors.append("backend server_name must match the test endpoint hostname")
    if descriptor.get("tls_version") != "TLS1.2":
        errors.append("backend TLS profile must be TLS1.2")
    for key in ("trusted_ca_sha256", "server_certificate_sha256", "client_certificate_sha256"):
        if not SHA256_RE.fullmatch(str(descriptor.get(key, ""))):
            errors.append(f"{key} must be a SHA-256 fingerprint")
    credential_ref = descriptor.get("credential_reference")
    if not isinstance(credential_ref, str) or not re.match(r"^(vault|secret|test-secret)://[^\s]+$", credential_ref):
        errors.append("credential_reference must be a secret-store reference, not credential material")
    for key in ("trusted_time_evidence_reference", "ownership_fixture_reference", "readiness_receipt"):
        if not isinstance(descriptor.get(key), str) or not descriptor[key].strip():
            errors.append(f"{key} is missing")
    for key in ("hub_id", "home_id"):
        if not isinstance(descriptor.get(key), str) or not descriptor[key].strip():
            errors.append(f"expected authenticated {key} is missing")
    epoch = descriptor.get("installation_epoch")
    if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 1:
        errors.append("expected authenticated installation_epoch must be a positive integer")
    if not isinstance(descriptor.get("evidence_signing_public_key_path"), str) or not descriptor["evidence_signing_public_key_path"].strip():
        errors.append("TEST_ONLY evidence signing public key path is missing")
    if not SHA256_RE.fullmatch(str(descriptor.get("evidence_signing_public_key_sha256", ""))):
        errors.append("TEST_ONLY evidence signing public key fingerprint is missing or invalid")
    if descriptor.get("commercial_sending_enabled") is not False:
        errors.append("commercial sending must remain disabled")
    if descriptor.get("production_credentials_used") is not False:
        errors.append("production credentials must not be used")
    return errors


def verify_evidence_artifacts(evidence_root, artifacts, capture_complete):
    """Check a captured evidence bundle without trusting filenames alone."""
    if capture_complete is not True:
        return ["capture is interrupted or incomplete"]
    if not isinstance(artifacts, list) or not artifacts:
        return ["evidence artifact list is missing"]
    root = Path(evidence_root).resolve()
    errors = []
    for artifact in artifacts:
        relative = artifact.get("path") if isinstance(artifact, dict) else None
        if not isinstance(relative, str) or not relative:
            errors.append("artifact path is missing")
            continue
        path = (root / relative).resolve()
        if root not in path.parents or not path.is_file():
            errors.append(f"evidence artifact is missing or escapes the evidence directory: {relative}")
        elif not SHA256_RE.fullmatch(str(artifact.get("sha256", ""))) or _sha256(path) != artifact["sha256"].lower():
            errors.append(f"evidence artifact checksum mismatch: {relative}")
    return errors


def adjudicate_case(case, evidence, fixture, authorization, plan_sha256, case_plan,
                    backend_descriptor, source_head, evidence_root=None):
    """Fail closed until a reviewed physical capture adapter is available.

    A JSON field claiming ``evidence_origin=PHYSICAL`` is not proof of origin.
    This software-only revision has no trusted capture/attestation path, so no
    submitted bundle can be promoted to a physical PASS or FAIL.
    """
    if not isinstance(case, dict) or not isinstance(evidence, dict):
        return "BLOCKED", "case or evidence record is not a JSON object"
    if not isinstance(fixture, dict) or not isinstance(case_plan, dict):
        return "BLOCKED", "fixture or case plan is not a JSON object"
    if evidence.get("evidence_origin") != "PHYSICAL":
        return "BLOCKED", "physical cases cannot pass from host or simulated evidence"
    if evidence.get("capture_adapter") != "gs68-authenticated-serial-v1":
        return "BLOCKED", "evidence was not produced by the bounded GS-68 capture adapter"
    if evidence.get("case_id") != case.get("case_id"):
        return "BLOCKED", "evidence case ID does not match the requested case"
    if evidence.get("case_id") not in authorization.get("authorized_case_ids", []):
        return "BLOCKED", "case is outside the fixture-specific authorization"
    if evidence.get("fixture_id") != fixture.get("fixture_id"):
        return "BLOCKED", "evidence fixture identity does not match the approved fixture"
    expected_fields = {
        "source_commit": source_head,
        "case_plan_sha256": plan_sha256,
        "profile_sha256": fixture.get("profile", {}).get("profile_sha256"),
        "backend_id": backend_descriptor.get("backend_id"),
        "client_certificate_sha256": backend_descriptor.get("client_certificate_sha256"),
        "server_certificate_sha256": backend_descriptor.get("server_certificate_sha256"),
        "hub_id": backend_descriptor.get("hub_id"),
        "home_id": backend_descriptor.get("home_id"),
        "installation_epoch": str(backend_descriptor.get("installation_epoch", "")),
    }
    for key, expected in expected_fields.items():
        if evidence.get(key) != expected:
            return "BLOCKED", f"evidence {key} does not match the approved run"
    if evidence.get("capture_complete") is not True:
        return "BLOCKED", "capture is interrupted or incomplete"
    verifier_path = _resolve_repo_file(backend_descriptor.get("evidence_signing_public_key_path"))
    try:
        verifier_pem = verifier_path.read_bytes() if verifier_path and verifier_path.is_file() else b""
    except OSError:
        verifier_pem = b""
    if not verifier_pem:
        return "BLOCKED", "pinned TEST_ONLY backend evidence verifier is missing"
    binding = {key: str(evidence.get(key, "")) for key in
        ("fixture_id", "source_commit", "image_sha256", "profile_sha256", "case_plan_sha256", "backend_id",
         "client_certificate_sha256", "server_certificate_sha256", "hub_id", "home_id", "installation_epoch")}
    frame = evidence.get("device_frame")
    if not isinstance(frame, dict):
        return "BLOCKED", "authenticated target case frame is missing"
    errors = capture.verify_case_frame(frame, case_id=case["case_id"],
        nonce=str(evidence.get("challenge_nonce", "")), binding=binding,
        verifier_pem=verifier_pem)
    if evidence_root is not None:
        errors.extend(verify_evidence_artifacts(evidence_root, evidence.get("artifacts"), True))
    if errors:
        return "BLOCKED", "; ".join(errors)
    outcome = frame.get("case_outcome")
    if outcome == "PASS":
        return "PASS", "target observation and TEST_ONLY mTLS backend receipt are authenticated and bound"
    if outcome == "FAIL":
        return "FAIL", "authenticated target observation reports the case failed"
    return "BLOCKED", "authenticated target evidence reports an incomplete prerequisite"


def build_dry_run_report(fixture, backend, case_plan, source_head, fixture_errors, backend_errors, plan_sha256):
    cases = []
    raw_cases = case_plan.get("cases", []) if isinstance(case_plan, dict) else []
    if not isinstance(raw_cases, list):
        raw_cases = []
    case_ids = [item.get("case_id") for item in raw_cases if isinstance(item, dict)]
    authorization_errors = validate_authorization(
        fixture.get("physical_authorization"), fixture.get("fixture_id"),
        case_ids, plan_sha256,
    )
    readiness_errors = fixture_errors + backend_errors + authorization_errors
    for case in raw_cases:
        if not isinstance(case, dict):
            continue
        cases.append({
            "case_id": case.get("case_id"),
            "name": case.get("name"),
            "status": "BLOCKED" if readiness_errors else "NOT_RUN",
            "reason": "physical execution is disabled in the software-only phase" if not readiness_errors else "fixture/backend readiness prerequisite is incomplete",
            "prerequisites": case.get("prerequisites", []),
            "expected": case.get("expected"),
            "evidence_required": case.get("evidence_required", []),
            "blocked_when": case.get("blocked_when", []),
            "separate_approval": case.get("separate_approval", []),
            "physical": "NOT_RUN",
        })
    return {
        "schema_version": 1,
        "campaign_id": case_plan.get("campaign_id") if isinstance(case_plan, dict) else None,
        "created_utc": common.utc_now(),
        "mode": "SAFE_DRY_RUN",
        "overall": "NOT_RUN",
        "physical": "NOT_RUN",
        "physical_execution": "BLOCKED",
        "source_commit": source_head,
        "case_plan_sha256": plan_sha256,
        "fixture_id": fixture.get("fixture_id"),
        "profile_sha256": _sha256(PROFILE) if PROFILE.is_file() else None,
        "fixture_errors": fixture_errors,
        "authorization_errors": authorization_errors,
        "backend_id": backend.get("backend_id"),
        "backend_ready": not backend_errors,
        "backend_errors": backend_errors,
        "physical_execution_enabled": RUNNER_EXECUTION_ENABLED,
        "hardware_actions": [],
        "cases": cases,
        "limitations": [
            "No USB/serial discovery, network request, flash, reset, provisioning, or eFuse operation occurred.",
            "All physical qualification remains NOT_RUN; host/simulated evidence cannot satisfy this catalogue row.",
            "A fixture-specific approval and separately authorized DS identity provisioning are required before physical execution.",
        ],
    }


def _load_inputs(fixture_path, backend_path, cases_path):
    fixture, fixture_read_errors = _read_json(fixture_path)
    backend, backend_read_errors = _read_json(backend_path)
    case_plan, case_read_errors = _read_json(cases_path)
    errors = fixture_read_errors + backend_read_errors + case_read_errors
    for label, value in (("fixture", fixture), ("backend descriptor", backend), ("case plan", case_plan)):
        if not isinstance(value, dict):
            errors.append(f"{label} must be a JSON object")
    if not isinstance(fixture, dict):
        fixture = {}
    if not isinstance(backend, dict):
        backend = {}
    if not isinstance(case_plan, dict):
        case_plan = {}
    return fixture, backend, case_plan, errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=FIXTURE_TEMPLATE)
    parser.add_argument("--backend", type=Path, default=BACKEND_TEMPLATE)
    parser.add_argument("--cases", type=Path, default=CASE_PLAN)
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--run-physical", action="store_true", help="execute only specifically authorized cases on the manifest fixture")
    parser.add_argument("--case", action="append", dest="case_ids", help="authorized case ID; repeat to select multiple cases")
    parser.add_argument("--operator-confirmation", help="exact fixture-and-case-bound confirmation string")
    args = parser.parse_args(argv)

    fixture, backend, case_plan, input_errors = _load_inputs(args.fixture, args.backend, args.cases)
    source_head = common.current_source_head()
    fixture_errors = input_errors + validate_fixture(fixture, source_head, case_plan)
    backend_errors = validate_backend_descriptor(backend)
    plan_sha256 = _sha256(args.cases) if args.cases.is_file() else ""
    report = build_dry_run_report(fixture, backend, case_plan, source_head, fixture_errors, backend_errors, plan_sha256)
    evidence_dir = common.create_evidence_dir(args.evidence_dir, "GS68_CLOUDSYNC_HIL")
    if args.run_physical:
        errors = _physical_preflight(fixture, backend, case_plan, source_head,
            fixture_errors, backend_errors, plan_sha256, args.case_ids,
            args.operator_confirmation)
        if errors:
            report.update(mode="PHYSICAL_REQUEST_BLOCKED", overall="BLOCKED",
                          physical="NOT_RUN", physical_blocker=errors,
                          hardware_actions=[])
            for case in report["cases"]:
                case["status"] = "BLOCKED"
                case["reason"] = "; ".join(errors)
            common.write_report(evidence_dir / "gs68_cloudsync_hil_results.json", report)
            print(f"GS68 CLOUDSYNC HIL BLOCKED cases={len(report['cases'])} physical=NOT_RUN hardware_actions=0")
            return 3
        try:
            execution = _execute_physical(fixture, backend, case_plan,
                source_head, plan_sha256, args.case_ids, evidence_dir)
        except Exception as error:
            execution = {"mode": "PHYSICAL_CAPTURE", "overall": "BLOCKED",
                "physical": "NOT_RUN", "physical_execution": "NOT_STARTED",
                "hardware_actions": [], "selected_case_ids": args.case_ids or [],
                "capture_complete": False,
                "physical_blocker": [f"{type(error).__name__}: {str(error)[:240]}"]}
        report.update(execution)
        common.write_report(evidence_dir / "gs68_cloudsync_hil_results.json", report)
        status = report.get("overall", "BLOCKED")
        print(f"GS68 CLOUDSYNC HIL {status} cases={len(args.case_ids)} physical={report.get('physical')} hardware_actions={len(report.get('hardware_actions', []))}")
        return 0 if status == "CAPTURED_REVIEW_REQUIRED" else 1
    common.write_report(evidence_dir / "gs68_cloudsync_hil_results.json", report)
    print(f"GS68 CLOUDSYNC HIL DRY-RUN PASS cases={len(report['cases'])} physical=NOT_RUN execution=BLOCKED")
    return 0


def _physical_preflight(fixture, backend, case_plan, source_head, fixture_errors,
                        backend_errors, plan_sha256, case_ids, confirmation):
    errors = list(fixture_errors) + list(backend_errors)
    all_ids = {case.get("case_id") for case in case_plan.get("cases", []) if isinstance(case, dict)}
    if not case_ids or any(case_id not in all_ids for case_id in (case_ids or [])):
        errors.append("physical execution requires known explicit --case values")
    if len(case_ids or []) != len(set(case_ids or [])):
        errors.append("duplicate --case selection is not allowed")
    authorization = fixture.get("physical_authorization", {})
    errors.extend(validate_authorization(authorization, fixture.get("fixture_id"),
                                         case_ids or [], plan_sha256))
    fixture_id = fixture.get("fixture_id", "UNASSIGNED")
    case_hash = hashlib.sha256("\n".join(sorted(case_ids or [])).encode()).hexdigest()
    expected_confirmation = f"RUN GS68 PHYSICAL {fixture_id} {case_hash}"
    if confirmation != expected_confirmation:
        errors.append("operator confirmation does not match fixture and selected case IDs")
    if backend.get("environment") != "TEST_ONLY" or backend.get("commercial_sending_enabled") is not False:
        errors.append("adapter requires TEST_ONLY backend with commercial sending disabled")
    verifier_path = _resolve_repo_file(backend.get("evidence_signing_public_key_path"))
    if verifier_path is None or not verifier_path.is_file():
        errors.append("pinned TEST_ONLY backend receipt verifier is missing")
    elif (not SHA256_RE.fullmatch(str(backend.get("evidence_signing_public_key_sha256", ""))) or
          _sha256(verifier_path) != backend["evidence_signing_public_key_sha256"].lower()):
        errors.append("TEST_ONLY backend receipt verifier fingerprint mismatch")
    if fixture.get("source_commit") != source_head:
        errors.append("fixture source commit does not match current checkout")
    return errors


def _inspect_by_id_port(port, expected_serial_short, run=subprocess.run):
    """Read udev identity for an exact fixture path without opening the tty."""
    path = Path(port)
    if not str(path).startswith("/dev/serial/by-id/") or not path.is_symlink():
        raise capture.CaptureError("fixture port must be an existing /dev/serial/by-id symlink")
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise capture.CaptureError("fixture by-id port does not resolve") from error
    if resolved.parent != Path("/dev") or not resolved.name.startswith(("ttyUSB", "ttyACM")):
        raise capture.CaptureError("fixture by-id port does not resolve to a supported USB serial node")
    try:
        result = run(["udevadm", "info", "--query=property", "--name", str(path)],
                     check=True, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError) as error:
        raise capture.CaptureError("cannot verify fixture USB serial identity with udev") from error
    properties = {}
    for line in result.stdout.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            properties[key] = value
    if properties.get("ID_SERIAL_SHORT") != expected_serial_short:
        raise capture.CaptureError("USB serial identity does not match the spare-fixture manifest")
    return {"resolved_device": str(resolved), "usb_serial_short": properties["ID_SERIAL_SHORT"],
            "id_path": properties.get("ID_PATH", "")}


def _execute_physical(fixture, backend, case_plan, source_head, plan_sha256,
                      case_ids, evidence_dir, transport_factory=None, udev_run=subprocess.run):
    # Only this function imports/constructs the serial adapter, and only after
    # all fixture, auth, case, and trust checks have passed.
    from gs68_capture import BoundedCapture, PySerialTransport, make_hash_chain
    port = fixture["boards"]["s3"]["identity"]["port_by_id"]
    identity = _inspect_by_id_port(port, fixture["boards"]["s3"]["identity"]["usb_serial_short"], udev_run)
    hardware_actions = [{"action": "READ_UDEV_IDENTITY", "board": "s3", **identity}]
    transport = (transport_factory or PySerialTransport)(port)
    session = BoundedCapture(transport)
    records = []
    opened = False
    ready = None
    try:
        session.open()
        opened = True
        hardware_actions.append({"action": "OPEN_EXACT_MANIFEST_PORT", "board": "s3", "port": port})
        ready = session.wait_ready()
        expected = {
            "source_commit": source_head,
            "profile_sha256": fixture["profile"]["profile_sha256"],
            "running_image_sha256": fixture["boards"]["s3"]["image"]["sha256"].lower(),
            "mac_address": _normalize_mac(fixture["boards"]["s3"]["identity"]["mac_address"]),
            "flash_bytes": fixture["boards"]["s3"]["flash_mb"] * 1024 * 1024,
            "flash_status": 0,
            "psram_bytes": fixture["boards"]["s3"]["psram_mb"] * 1024 * 1024,
            "chip_model": "ESP32-S3",
        }
        observed = dict(ready)
        observed["mac_address"] = _normalize_mac(str(observed.get("mac_address", "")))
        mismatches = [key for key, value in expected.items() if observed.get(key) != value]
        if mismatches:
            raise capture.CaptureError("running target provenance mismatch: " + ",".join(mismatches))
        verifier = _resolve_repo_file(backend["evidence_signing_public_key_path"]).read_bytes()
        for case_id in case_ids:
            nonce = secrets.token_hex(32)
            frame = session.request_case(case_id, nonce, {"operation": "RUN_CASE"})
            binding = {"fixture_id": fixture["fixture_id"], "source_commit": source_head,
                "image_sha256": expected["running_image_sha256"],
                "profile_sha256": expected["profile_sha256"], "case_plan_sha256": plan_sha256,
                "backend_id": backend["backend_id"],
                "client_certificate_sha256": backend["client_certificate_sha256"],
                "server_certificate_sha256": backend["server_certificate_sha256"],
                "hub_id": backend["hub_id"], "home_id": backend["home_id"],
                "installation_epoch": str(backend["installation_epoch"])}
            verification_errors = capture.verify_case_frame(frame, case_id=case_id,
                nonce=nonce, binding=binding, verifier_pem=verifier)
            records.append({"case_id": case_id, "challenge_nonce": nonce,
                            "device_frame": frame, "verification_errors": verification_errors,
                            "adjudication": "BLOCKED" if verification_errors or frame.get("case_outcome") == "BLOCKED"
                                else "CAPTURED_REVIEW_REQUIRED"})
    except Exception as error:
        records.append({"capture_error": type(error).__name__ + ":" + str(error),
                        "capture_complete": False})
    finally:
        try:
            session.close()
        except Exception as error:
            records.append({"capture_error": "transport_close:" + type(error).__name__,
                            "capture_complete": False})
    chain = make_hash_chain(records) if records else []
    complete = (len(records) == len(case_ids) and all(
        "capture_error" not in row and isinstance(row.get("device_frame"), dict) and
        not row.get("verification_errors") for row in records))
    adjudicable = complete and all(
        row["device_frame"].get("case_outcome") in {"PASS", "FAIL"} for row in records)
    bundle_physical = "CAPTURED_UNADJUDICATED" if opened else "NOT_RUN"
    bundle = {"schema": "gs68.physical.capture.v1", "physical": bundle_physical,
        "fixture_id": fixture["fixture_id"], "source_commit": source_head,
        "case_plan_sha256": plan_sha256, "profile_sha256": fixture["profile"]["profile_sha256"],
        "image_sha256": fixture["boards"]["s3"]["image"]["sha256"],
        "backend_id": backend["backend_id"],
        "client_certificate_sha256": backend["client_certificate_sha256"],
        "server_certificate_sha256": backend["server_certificate_sha256"],
        "hub_id": backend["hub_id"], "home_id": backend["home_id"],
        "installation_epoch": str(backend["installation_epoch"]),
        "binding": {"fixture_id": fixture["fixture_id"], "source_commit": source_head,
            "image_sha256": fixture["boards"]["s3"]["image"]["sha256"],
            "profile_sha256": fixture["profile"]["profile_sha256"], "case_plan_sha256": plan_sha256,
            "backend_id": backend["backend_id"],
            "client_certificate_sha256": backend["client_certificate_sha256"],
            "server_certificate_sha256": backend["server_certificate_sha256"],
            "hub_id": backend["hub_id"], "home_id": backend["home_id"],
            "installation_epoch": str(backend["installation_epoch"])},
        "records": chain,
        "target_ready_observation": ready,
        "capture_complete": complete, "hardware_actions": hardware_actions,
        "adapter_id": "gs68-authenticated-serial-v1", "capture_started": opened}
    bundle_path = evidence_dir / "gs68_physical_capture_bundle.json"
    try:
        capture.write_evidence_bundle(bundle_path, bundle)
    except Exception as error:
        return {"mode": "PHYSICAL_CAPTURE", "overall": "BLOCKED",
            "physical": bundle_physical, "physical_execution": "CAPTURED" if opened else "NOT_STARTED",
            "hardware_actions": hardware_actions, "selected_case_ids": case_ids,
            "capture_complete": False, "capture_bundle": None,
            "physical_blocker": [f"evidence persistence failed: {type(error).__name__}: {str(error)[:200]}"]}
    return {"mode": "PHYSICAL_CAPTURE", "overall": "CAPTURED_REVIEW_REQUIRED" if adjudicable else "BLOCKED",
        "physical": bundle_physical, "physical_execution": "CAPTURED" if opened else "NOT_STARTED",
        "hardware_actions": hardware_actions, "selected_case_ids": case_ids,
        "captured_case_count": sum(1 for item in records if "device_frame" in item),
        "capture_complete": complete, "capture_bundle": str(bundle_path),
        "limitation": "Physical qualification remains unadjudicated; only a complete authenticated capture is eligible for owner review."}


if __name__ == "__main__":
    raise SystemExit(main())
