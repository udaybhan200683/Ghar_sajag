#!/usr/bin/env python3
"""Bounded GS-68 auxiliary TEST_ONLY console diagnostics.

This harness is deliberately separate from official GS68-PHY-001..010. Import
and validation are host-only; serial is opened only by an explicit caller after
fixture/image/security/recovery gates have been independently satisfied.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import re
import time
from pathlib import Path

import gs68_capture as capture
import gs68_build_provenance as provenance

MAX_COMMAND_BYTES = 1024
MAX_RUN_SECONDS = 900
MAX_BYTES = 8 * 1024 * 1024
CASE_FILE = Path(__file__).with_name("gs68_auxiliary_cases.json")
AUX_CASES = {row["case_id"] for row in json.loads(CASE_FILE.read_text())["cases"]}


class AuxiliaryDiagnosticError(RuntimeError):
    pass


def classify(status: str, reason: str) -> dict:
    if status not in {"PASS", "FAIL", "BLOCKED", "NOT_RUN"}:
        raise ValueError("unsupported auxiliary status")
    return {"status": status, "reason": str(reason)[:240],
            "qualification_scope": "AUXILIARY_TEST_ONLY_ONLY",
            "official_gs68_physical_acceptance": "NOT_RUN"}


def validate_candidate_binding(fixture: object, build_report: object, *, repo: Path) -> list[str]:
    """Bind the immutable binary to a trusted commit, current code tree and exact report."""
    import gs68_cloudsync_hil as formal

    if not isinstance(fixture, dict) or not isinstance(build_report, dict):
        return ["fixture or build report is not a JSON object"]
    errors = []
    source = fixture.get("source_commit")
    if not re.fullmatch(r"[0-9a-f]{40}", str(source or "")):
        errors.append("fixture source commit is invalid")
    elif not formal._is_reachable_commit(source):
        errors.append("fixture source commit is not reachable from canonical HEAD")
    elif formal._commit_code_tree_oid(source) != formal._current_code_tree_oid():
        errors.append("candidate code tree differs from current committed source")
    if build_report.get("source_commit") != source:
        errors.append("build report source commit differs from fixture")
    if build_report.get("source_code_tree_oid") != formal._commit_code_tree_oid(source):
        errors.append("build report code-tree binding is invalid")
    profile = fixture.get("profile", {})
    if not isinstance(profile, dict):
        profile = {}
    if build_report.get("profile_sha256") != profile.get("profile_sha256"):
        errors.append("candidate profile hash differs from build report")
    image = fixture.get("image", {})
    image_path = Path(image.get("path", "")) if isinstance(image, dict) else Path()
    if not image_path.is_absolute():
        image_path = Path(repo) / image_path
    if not image_path.is_file():
        errors.append("candidate image is missing")
    else:
        digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
        if digest != str(image.get("sha256", "")).lower():
            errors.append("candidate image SHA-256 does not match fixture")
        if digest != build_report.get("image_sha256"):
            errors.append("candidate image SHA-256 does not match build report")
    if build_report.get("target") != "ESP32-S3" or build_report.get("idf_version") != "v6.0.3":
        errors.append("candidate target or pinned ESP-IDF version is invalid")
    errors.extend(provenance.validate_manifest(repo, build_report.get("build_inputs"),
                                               build_report.get("build_inputs_sha256")))
    report_path = Path(profile.get("build_report", ""))
    if not report_path.is_absolute():
        report_path = Path(repo) / report_path
    try:
        actual_report = json.loads(report_path.read_text())
    except (OSError, json.JSONDecodeError):
        actual_report = None
    if (not report_path.is_file() or
            hashlib.sha256(report_path.read_bytes()).hexdigest() != profile.get("build_report_sha256") or
            actual_report != build_report):
        errors.append("build report does not match fixture checksum")
    return errors


def validate_install_gates(fixture: object) -> list[str]:
    """Require explicit verified evidence for every installation safety gate."""
    if not isinstance(fixture, dict):
        return ["fixture manifest is missing"]
    gates = fixture.get("install_gates", {})
    if not isinstance(gates, dict):
        return ["install gate evidence is malformed"]
    required = ("spare_identity_verified", "protected_c8_excluded", "security_status_known",
                "plain_app_update_compatible", "installed_partition_layout_verified",
                "recovery_backup_verified", "recovery_method_validated", "usb_transport_stable",
                "test_only_build_confirmed", "production_endpoints_disabled",
                "fixture_specific_owner_authorization", "application_installation_authorized",
                "installed_application_image_verified")
    return [f"installation gate not proven: {name}" for name in required if gates.get(name) is not True]


def command_frame(case_id: str, operation: str = "OBSERVE", nonce: str | None = None) -> bytes:
    if case_id not in AUX_CASES:
        raise AuxiliaryDiagnosticError("unknown auxiliary case ID")
    if not isinstance(nonce, str) or not capture.HEX64.fullmatch(nonce):
        raise AuxiliaryDiagnosticError("command nonce must be 32 random bytes in lowercase hex")
    payload = capture.canonical_json({"schema": "gs68.target.command.v1", "case_id": case_id,
        "challenge_nonce": nonce, "operation": operation}) + b"\n"
    if len(payload) > MAX_COMMAND_BYTES:
        raise AuxiliaryDiagnosticError("command exceeds target 1024-byte limit")
    return payload


class BoundedAuxiliarySession:
    def __init__(self, transport, *, timeout_seconds: int = MAX_RUN_SECONDS,
                 max_bytes: int = MAX_BYTES):
        if not 1 <= timeout_seconds <= MAX_RUN_SECONDS or not 1 <= max_bytes <= MAX_BYTES:
            raise ValueError("auxiliary bounds are invalid")
        self.transport, self.timeout_seconds, self.max_bytes = transport, timeout_seconds, max_bytes
        self.started = None
        self.bytes_read = 0

    def open(self):
        self.transport.open()
        self.started = time.monotonic()

    def write(self, payload: bytes):
        if self.started is None or time.monotonic() - self.started > self.timeout_seconds:
            raise AuxiliaryDiagnosticError("auxiliary session is closed or expired")
        if not isinstance(payload, bytes) or len(payload) > (3 * MAX_COMMAND_BYTES + 8):
            raise AuxiliaryDiagnosticError("raw command exceeds bounded input size")
        self.transport.write(payload)

    def read_frame(self, timeout: float = 10.0) -> dict:
        if self.started is None or time.monotonic() - self.started > self.timeout_seconds:
            raise AuxiliaryDiagnosticError("auxiliary session is closed or expired")
        raw = self.transport.read_line(min(max(timeout, 0.1), 30.0))
        if not raw:
            raise AuxiliaryDiagnosticError("serial timeout or USB/IP disconnect")
        self.bytes_read += len(raw)
        if self.bytes_read > self.max_bytes:
            raise AuxiliaryDiagnosticError("auxiliary capture byte limit exceeded")
        if len(raw) > capture.MAX_FRAME_BYTES or not raw.endswith(b"\n"):
            raise AuxiliaryDiagnosticError("truncated or oversized target frame")
        if not raw.startswith(capture.FRAME_PREFIX):
            raise AuxiliaryDiagnosticError("target frame prefix is invalid")
        return capture.parse_device_frame(raw[:-1])

    def close(self):
        try:
            self.transport.close()
        finally:
            self.started = None


def run_usb_sequence(session: BoundedAuxiliarySession, *, fragment_delay: float = 0.2) -> list[dict]:
    """Exercise delayed/fragmented, malformed/oversized recovery, and sequential input."""
    if not 0 <= fragment_delay <= 2:
        raise ValueError("fragment delay exceeds bound")
    results = []
    nonce = secrets.token_hex(32)
    valid = command_frame("GS68-AUX-USB-001", nonce=nonce).rstrip(b"\n") + b"\r\n"
    midpoint = max(1, len(valid) // 2)
    session.write(valid[:midpoint])
    time.sleep(fragment_delay)
    session.write(valid[midpoint:])
    frame = session.read_frame()
    if (frame.get("event") != "command_result" or frame.get("result") != "OBSERVED_NO_ACTION" or
            frame.get("case_id") != "GS68-AUX-USB-001" or frame.get("challenge_nonce") != nonce):
        return [classify("FAIL", "fragmented command response did not match OBSERVE")]
    results.append(classify("PASS", "delayed fragmented command received a correlated response"))

    nonce2 = secrets.token_hex(32)
    next_valid = command_frame("GS68-AUX-USB-002", nonce=nonce2)
    session.write(b"not-json\n" + next_valid)
    malformed = session.read_frame()
    recovered = session.read_frame()
    if (malformed.get("event") != "case_result" or malformed.get("case_outcome") != "FAIL" or
            malformed.get("reason") != "INVALID_OR_OVERSIZED_COMMAND"):
        return results + [classify("FAIL", "malformed command was not explicitly rejected")]
    if (recovered.get("event") != "command_result" or recovered.get("result") != "OBSERVED_NO_ACTION" or
            recovered.get("case_id") != "GS68-AUX-USB-002" or recovered.get("challenge_nonce") != nonce2):
        return results + [classify("FAIL", "valid command after malformed input was not served")]

    nonce3 = secrets.token_hex(32)
    session.write(b"x" * (MAX_COMMAND_BYTES + 1) + b"\n" +
                  command_frame("GS68-AUX-USB-002", nonce=nonce3))
    oversized = session.read_frame()
    recovered = session.read_frame()
    if (oversized.get("event") != "case_result" or oversized.get("case_outcome") != "FAIL" or
            oversized.get("reason") != "INVALID_OR_OVERSIZED_COMMAND"):
        return results + [classify("FAIL", "oversized input was not explicitly rejected")]
    if (recovered.get("event") != "command_result" or recovered.get("result") != "OBSERVED_NO_ACTION" or
            recovered.get("case_id") != "GS68-AUX-USB-002" or recovered.get("challenge_nonce") != nonce3):
        return results + [classify("FAIL", "valid command after oversized input was not served")]
    results.append(classify("PASS", "malformed and oversized lines were rejected and receiver recovered"))

    nonce4, nonce5 = secrets.token_hex(32), secrets.token_hex(32)
    cmds = (command_frame("GS68-AUX-USB-003", nonce=nonce4) +
            command_frame("GS68-AUX-USB-003", nonce=nonce5))
    session.write(cmds)
    first, second = session.read_frame(), session.read_frame()
    if any(f.get("event") != "command_result" or f.get("result") != "OBSERVED_NO_ACTION" or
           f.get("case_id") != "GS68-AUX-USB-003" for f in (first, second)) or \
            [first.get("challenge_nonce"), second.get("challenge_nonce")] != [nonce4, nonce5]:
        return results + [classify("FAIL", "sequential command response missing or unexpected")]
    results.append(classify("PASS", "sequential commands received two ordered responses"))
    return results


def execute_usb_if_ready(fixture: object, build_report: object, *, repo: Path,
                         transport_factory=None) -> dict:
    """Open only after exact candidate + fixture/security/recovery gates pass."""
    failures = validate_candidate_binding(fixture, build_report, repo=repo)
    failures.extend(validate_install_gates(fixture))
    if failures:
        rows = [classify("BLOCKED", reason) for reason in failures]
        safe_fixture = fixture if isinstance(fixture, dict) else {}
        safe_image = safe_fixture.get("image", {})
        safe_image = safe_image if isinstance(safe_image, dict) else {}
        safe_source = safe_fixture.get("source_commit")
        safe_source = safe_source if isinstance(safe_source, str) and len(safe_source) == 40 else "0" * 40
        safe_hash = safe_image.get("sha256")
        safe_hash = safe_hash if isinstance(safe_hash, str) and capture.HEX64.fullmatch(safe_hash) else "0" * 64
        return evidence_bundle(fixture_id=str(safe_fixture.get("fixture_id", "UNBOUND")),
            source_commit=safe_source,
            image_sha256=safe_hash,
            records=rows)
    from gs68_capture import PySerialTransport
    identity = fixture["identity"]
    transport = (transport_factory or PySerialTransport)(identity["port_by_id"])
    session = BoundedAuxiliarySession(transport)
    rows = []
    try:
        session.open()
        ready = session.read_frame(timeout=30)
        if (ready.get("event") != "ready" or
                ready.get("running_image_sha256") != fixture["image"]["sha256"] or
                ready.get("source_commit") != fixture["source_commit"] or
                ready.get("profile_sha256") != fixture["profile"]["profile_sha256"]):
            raise AuxiliaryDiagnosticError("READY identity does not match approved candidate")
        rows.extend(run_usb_sequence(session))
    except Exception as error:
        blocked = isinstance(error, (TimeoutError, OSError)) or "timeout" in str(error).lower() or "disconnect" in str(error).lower()
        rows.append(classify("BLOCKED" if blocked else "FAIL",
                             f"{type(error).__name__}: {str(error)}"))
    finally:
        try:
            session.close()
        except Exception as error:
            rows.append(classify("BLOCKED", f"transport close failed: {type(error).__name__}"))
    return evidence_bundle(fixture_id=fixture["fixture_id"], source_commit=fixture["source_commit"],
        image_sha256=fixture["image"]["sha256"], records=rows)


def evidence_bundle(*, fixture_id: str, source_commit: str, image_sha256: str,
                    records: list[dict]) -> dict:
    if not fixture_id or len(source_commit) != 40 or not capture.HEX64.fullmatch(image_sha256):
        raise AuxiliaryDiagnosticError("evidence binding is incomplete")
    # This checksum is an auxiliary bundle integrity aid, never backend attestation.
    records = [dict(row, qualification_scope="AUXILIARY_TEST_ONLY_ONLY",
                    official_gs68_physical_acceptance="NOT_RUN") for row in records]
    serialized = capture.canonical_json(records)
    return {"schema": "gs68.auxiliary.capture.v1", "physical": "AUXILIARY_TEST_ONLY_ONLY",
        "official_gs68_physical_acceptance": "NOT_RUN", "fixture_id": fixture_id,
        "source_commit": source_commit, "image_sha256": image_sha256,
        "capture_complete": all(row.get("status") in {"PASS", "FAIL", "BLOCKED", "NOT_RUN"}
                                 for row in records),
        "records": records, "records_sha256": hashlib.sha256(serialized).hexdigest()}
