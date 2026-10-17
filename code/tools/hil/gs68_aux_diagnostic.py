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
import base64
from pathlib import Path

import gs68_capture as capture
import gs68_build_provenance as provenance

MAX_COMMAND_BYTES = 1024
MAX_RUN_SECONDS = 900
MAX_BYTES = 8 * 1024 * 1024
MAX_CAPTURE_LINES = 8192
MAX_LINE_BYTES = capture.MAX_FRAME_BYTES
CASE_FILE = Path(__file__).with_name("gs68_auxiliary_cases.json")
AUX_CASES = {row["case_id"] for row in json.loads(CASE_FILE.read_text())["cases"]}
HOST_ONLY_SOURCE_DELTA = {
    "code/tools/hil/gs68_aux_diagnostic.py",
    "code/tools/hil/gs68_capture.py",
    "code/tools/hil/gs68_build_provenance.py",
    "code/tools/hil/test_gs68_aux_runners.py",
    "code/scripts/build_gs68_cloudsync_diagnostic.py",
}


def source_delta_is_host_only(paths: set[str]) -> bool:
    return bool(paths) and paths.issubset(HOST_ONLY_SOURCE_DELTA)


class AuxiliaryDiagnosticError(RuntimeError):
    pass


def expected_running_image_digest(image_bytes: bytes, build_report: dict,
                                  image_metadata: dict) -> str:
    """Return the runtime-comparable ESP image hash after provenance checks."""
    try:
        derived = provenance.esp_image_validation_sha256(image_bytes)
    except (TypeError, ValueError) as error:
        raise AuxiliaryDiagnosticError(f"candidate ESP image metadata is invalid: {error}") from error
    for label, value in (("build report", build_report.get("image_validation_sha256")),
                         ("fixture", image_metadata.get("image_validation_sha256"))):
        if value is not None and value != derived:
            raise AuxiliaryDiagnosticError(f"{label} image validation digest mismatch")
    return derived


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
    if not formal._code_worktree_clean():
        errors.append("uncommitted or unknown code inputs make candidate provenance unverifiable")
    fixture_id = fixture.get("fixture_id")
    if not isinstance(fixture_id, str) or not re.fullmatch(r"GS68-SPARE-[A-Z0-9-]+", fixture_id):
        errors.append("fixture ID must identify a separate GS68 spare")
    protected, protected_errors = formal._read_json(formal.PROTECTED_FIXTURE)
    if protected_errors:
        errors.append("protected C8 inventory is unavailable")
    else:
        protected_values = formal._protected_values(protected)
        if fixture_id in protected_values["fixture_ids"]:
            errors.append("fixture aliases the protected C8")
        identity = fixture.get("identity", {})
        if not isinstance(identity, dict):
            identity = {}
        for field in ("mac_address", "usb_serial_short", "port_by_id"):
            if not isinstance(identity.get(field), str) or not identity[field].strip():
                errors.append(f"fixture identity {field} is missing")
        if identity.get("mac_address") and formal._normalize_mac(identity["mac_address"]) in protected_values["macs"]:
            errors.append("fixture MAC aliases protected C8")
        if identity.get("usb_serial_short") and identity["usb_serial_short"].strip().lower() in protected_values["serials"]:
            errors.append("fixture USB serial aliases protected C8")
        if identity.get("port_by_id") and identity["port_by_id"].strip() in protected_values["ports"]:
            errors.append("fixture port aliases protected C8")
    source = fixture.get("source_commit")
    if not re.fullmatch(r"[0-9a-f]{40}", str(source or "")):
        errors.append("fixture source commit is invalid")
    elif not formal._is_reachable_commit(source):
        errors.append("fixture source commit is not reachable from canonical HEAD")
    elif formal._commit_code_tree_oid(source) != formal._current_code_tree_oid():
        # Runner-only changes after an immutable firmware build do not alter its
        # bytes. Permit only this explicit host tooling allowlist; any firmware,
        # build input or unreviewed source delta still blocks the candidate.
        changed = formal.subprocess.run(["git", "diff", "--name-only", f"{source}..HEAD", "--", "code"],
            cwd=formal.REPO, check=False, capture_output=True, text=True)
        paths = {line.strip() for line in changed.stdout.splitlines() if line.strip()}
        if changed.returncode != 0 or not source_delta_is_host_only(paths):
            errors.append("candidate code tree differs outside the approved host-only observer delta")
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
        image_bytes = image_path.read_bytes()
        digest = hashlib.sha256(image_bytes).hexdigest()
        if digest != str(image.get("sha256", "")).lower():
            errors.append("candidate image SHA-256 does not match fixture")
        if digest != build_report.get("image_sha256"):
            errors.append("candidate image SHA-256 does not match build report")
        try:
            validation_digest = expected_running_image_digest(image_bytes, build_report, image)
            declared_validation_digest = build_report.get("image_validation_sha256")
            if declared_validation_digest is not None and declared_validation_digest != validation_digest:
                errors.append("candidate image validation digest differs from build metadata")
        except (AuxiliaryDiagnosticError, TypeError, ValueError) as error:
            validation_digest = None
            errors.append(f"candidate image format or validation digest is unsupported: {error}")
        if isinstance(image, dict) and image.get("image_validation_sha256") not in (None, validation_digest):
            errors.append("candidate image validation digest differs from fixture metadata")
    if build_report.get("target") != "ESP32-S3" or build_report.get("idf_version") != "v6.0.3":
        errors.append("candidate target or pinned ESP-IDF version is invalid")
    if fixture.get("target") != "ESP32-S3" or fixture.get("flash_mb") != 16 or fixture.get("psram_mb") != 8:
        errors.append("fixture target/flash/PSRAM profile does not match S3 N16R8")
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
                 max_bytes: int = MAX_BYTES, max_lines: int = MAX_CAPTURE_LINES):
        if (not 1 <= timeout_seconds <= MAX_RUN_SECONDS or not 1 <= max_bytes <= MAX_BYTES or
                not 1 <= max_lines <= MAX_CAPTURE_LINES):
            raise ValueError("auxiliary bounds are invalid")
        self.transport, self.timeout_seconds, self.max_bytes = transport, timeout_seconds, max_bytes
        self.max_lines = max_lines
        self.started = None
        self.bytes_read = 0
        self.lines_read = 0
        self.console_records: list[dict] = []
        self.startup_log_lines: list[bytes] = []
        self.startup_log_fingerprint = None
        self.ready_frame = None
        self.ready_reobserved = False
        self.startup_replay_suspected = False
        self._post_ready_log_window: list[bytes] = []

    def open(self):
        self.transport.open()
        self.started = time.monotonic()

    def write(self, payload: bytes):
        if self.started is None or time.monotonic() - self.started > self.timeout_seconds:
            raise AuxiliaryDiagnosticError("auxiliary session is closed or expired")
        if not isinstance(payload, bytes) or len(payload) > (3 * MAX_COMMAND_BYTES + 8):
            raise AuxiliaryDiagnosticError("raw command exceeds bounded input size")
        self.transport.write(payload)

    def _read_line(self, deadline: float) -> bytes:
        if self.started is None:
            raise AuxiliaryDiagnosticError("auxiliary session is closed")
        if time.monotonic() - self.started >= self.timeout_seconds:
            raise AuxiliaryDiagnosticError("auxiliary session time bound exceeded")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return b""
        raw = self.transport.read_line(min(remaining, 30.0))
        if not raw:
            return b""
        self.lines_read += 1
        self.bytes_read += len(raw)
        if self.lines_read > self.max_lines:
            raise AuxiliaryDiagnosticError("auxiliary capture line-count limit exceeded")
        if self.bytes_read > self.max_bytes:
            raise AuxiliaryDiagnosticError("auxiliary capture byte limit exceeded")
        self.console_records.append({"sequence": self.lines_read,
            "host_monotonic_ns": time.monotonic_ns(),
            "kind": "unclassified", "raw_base64": base64.b64encode(raw).decode("ascii")})
        if len(raw) > MAX_LINE_BYTES:
            self.console_records[-1]["kind"] = "oversized_line"
            raise AuxiliaryDiagnosticError("console line exceeds size limit")
        if not raw.endswith(b"\n"):
            self.console_records[-1]["kind"] = "truncated_line"
            raise AuxiliaryDiagnosticError("truncated console line")
        return raw

    def wait_ready(self, timeout: float = 30.0, *, max_startup_lines: int = 256) -> dict:
        if self.started is None:
            raise AuxiliaryDiagnosticError("auxiliary session is closed")
        if not 1 <= max_startup_lines <= 1024:
            raise ValueError("startup drain line bound is invalid")
        deadline = time.monotonic() + min(max(timeout, 0.1), 60.0)
        start_lines = self.lines_read
        while time.monotonic() < deadline:
            raw = self._read_line(deadline)
            if not raw:
                break
            frame = self._decode_or_record_console_line(raw, startup=True)
            if frame is None:
                if self.lines_read - start_lines >= max_startup_lines:
                    raise AuxiliaryDiagnosticError("startup console line limit exceeded before READY")
                continue
            if frame.get("event") == "ready":
                self.startup_log_fingerprint = hashlib.sha256(b"".join(self.startup_log_lines)).hexdigest()
                return frame
            raise AuxiliaryDiagnosticError("unexpected structured diagnostic frame before READY")
        raise AuxiliaryDiagnosticError("READY response missing before startup deadline")

    def _decode_or_record_console_line(self, raw: bytes, *, startup: bool = False) -> dict | None:
        body = raw[:-1].rstrip(b"\r")
        record = self.console_records[-1]
        if not body.startswith(capture.FRAME_PREFIX):
            record["kind"] = "console_log"
            if startup:
                self.startup_log_lines.append(raw)
            elif self.startup_log_lines:
                self._post_ready_log_window.append(raw)
                del self._post_ready_log_window[:-len(self.startup_log_lines)]
                prefix = self.startup_log_lines[:min(3, len(self.startup_log_lines))]
                if len(prefix) == 3 and self._post_ready_log_window[-3:] == prefix:
                    self.startup_replay_suspected = True
                    record["kind"] = "startup_replay_suspected"
                    raise AuxiliaryDiagnosticError("startup transcript replay suspected; reset/replay cause is unknown")
            return None
        try:
            frame = capture.parse_device_frame(raw[:-1].rstrip(b"\r"))
        except Exception as error:
            record["kind"] = "malformed_structured_frame"
            raise AuxiliaryDiagnosticError(f"malformed GS68/1 frame: {error}") from error
        record["kind"] = "structured_frame"
        record["event"] = frame.get("event")
        if frame.get("event") == "ready":
            if self.ready_frame is not None:
                self.ready_reobserved = True
                record["kind"] = "unexpected_ready"
                raise AuxiliaryDiagnosticError("unexpected READY while session is active; reboot/replay must be investigated")
            self.ready_frame = frame
        if self.startup_replay_suspected:
            raise AuxiliaryDiagnosticError("startup transcript replay suspected; qualification stopped")
        return frame

    def read_frame(self, timeout: float = 10.0) -> dict:
        if self.started is None or time.monotonic() - self.started > self.timeout_seconds:
            raise AuxiliaryDiagnosticError("auxiliary session is closed or expired")
        deadline = time.monotonic() + min(max(timeout, 0.1), 30.0)
        while time.monotonic() < deadline:
            raw = self._read_line(deadline)
            if not raw:
                time.sleep(min(max(0.0, deadline - time.monotonic()), 0.01))
                continue
            frame = self._decode_or_record_console_line(raw)
            if frame is not None:
                return frame
        raise AuxiliaryDiagnosticError("structured response missing before timeout/disconnect")

    def read_correlated_response(self, *, case_id: str, nonce: str, operation: str,
                                 timeout: float = 10.0) -> dict:
        frame = self.read_frame(timeout)
        if frame.get("event") == "ready":
            raise AuxiliaryDiagnosticError("unexpected READY while command response was outstanding")
        if frame.get("event") == "capture_error":
            raise AuxiliaryDiagnosticError(f"malformed/unrelated framing response: {frame.get('reason', 'unspecified')}")
        expected = {"case_id": case_id, "challenge_nonce": nonce, "operation": operation}
        mismatches = [key for key, value in expected.items() if frame.get(key) != value]
        if mismatches:
            raise AuxiliaryDiagnosticError("uncorrelated command response fields: " + ",".join(mismatches))
        return frame

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
    try:
        frame = session.read_correlated_response(case_id="GS68-AUX-USB-001", nonce=nonce,
                                                 operation="OBSERVE")
    except AuxiliaryDiagnosticError as error:
        return [classify("FAIL", f"fragmented OBSERVE response missing, malformed or uncorrelated: {error}")]
    if frame.get("event") != "command_result" or frame.get("result") != "OBSERVED_NO_ACTION":
        return [classify("FAIL", "fragmented command response did not match OBSERVE")]
    results.append(classify("PASS", "delayed fragmented command received a correlated response"))

    nonce2 = secrets.token_hex(32)
    next_valid = command_frame("GS68-AUX-USB-002", nonce=nonce2)
    session.write(b"not-json\n" + next_valid)
    malformed = session.read_frame()
    recovered = session.read_frame()
    if (malformed.get("event") != "case_result" or malformed.get("case_id") != "GS68-PHY-001" or
            malformed.get("challenge_nonce") != "0" * 64 or malformed.get("case_outcome") != "FAIL" or
            malformed.get("reason") != "INVALID_OR_OVERSIZED_COMMAND"):
        return results + [classify("FAIL", "malformed command was not explicitly rejected")]
    if (recovered.get("event") != "command_result" or recovered.get("result") != "OBSERVED_NO_ACTION" or
            recovered.get("case_id") != "GS68-AUX-USB-002" or recovered.get("challenge_nonce") != nonce2 or
            recovered.get("operation") != "OBSERVE"):
        return results + [classify("FAIL", "valid command after malformed input was not served")]

    nonce3 = secrets.token_hex(32)
    session.write(b"x" * (MAX_COMMAND_BYTES + 1) + b"\n" +
                  command_frame("GS68-AUX-USB-002", nonce=nonce3))
    oversized = session.read_frame()
    recovered = session.read_frame()
    if (oversized.get("event") != "capture_error" or oversized.get("reason") != "oversized_command"):
        return results + [classify("FAIL", "oversized input was not explicitly rejected")]
    if (recovered.get("event") != "command_result" or recovered.get("result") != "OBSERVED_NO_ACTION" or
            recovered.get("case_id") != "GS68-AUX-USB-002" or recovered.get("challenge_nonce") != nonce3 or
            recovered.get("operation") != "OBSERVE"):
        return results + [classify("FAIL", "valid command after oversized input was not served")]
    results.append(classify("PASS", "malformed and oversized lines were rejected and receiver recovered"))

    nonce4, nonce5 = secrets.token_hex(32), secrets.token_hex(32)
    cmds = (command_frame("GS68-AUX-USB-003", nonce=nonce4) +
            command_frame("GS68-AUX-USB-003", nonce=nonce5))
    session.write(cmds)
    first = session.read_correlated_response(case_id="GS68-AUX-USB-003", nonce=nonce4,
                                             operation="OBSERVE")
    second = session.read_correlated_response(case_id="GS68-AUX-USB-003", nonce=nonce5,
                                              operation="OBSERVE")
    if any(f.get("event") != "command_result" or f.get("result") != "OBSERVED_NO_ACTION"
           for f in (first, second)):
        return results + [classify("FAIL", "sequential command response missing or unexpected")]
    results.append(classify("PASS", "sequential commands received two ordered responses"))
    return results


def _send_command(session: BoundedAuxiliarySession, command: dict) -> dict:
    payload = capture.canonical_json(command) + b"\n"
    if len(payload) > MAX_COMMAND_BYTES:
        raise AuxiliaryDiagnosticError("signed-time command exceeds target command bound")
    session.write(payload)
    return session.read_frame()


def _time_challenge(session: BoundedAuxiliarySession, case_id: str) -> dict:
    request_nonce = secrets.token_hex(32)
    frame = _send_command(session, {"schema": "gs68.target.command.v1", "case_id": case_id,
        "challenge_nonce": request_nonce, "operation": "TIME_CHALLENGE"})
    nonce = frame.get("challenge_nonce")
    generation = frame.get("boot_generation")
    if (frame.get("event") != "time_challenge" or frame.get("case_id") != case_id or
            not isinstance(nonce, str) or not capture.HEX64.fullmatch(nonce) or
            not isinstance(generation, int) or isinstance(generation, bool) or generation <= 0 or
            frame.get("random_source") != "ESP32_S3_PSA"):
        raise AuxiliaryDiagnosticError("target did not provide a valid PSA challenge and boot generation")
    return frame


def _load_test_time_authority(session, fixture):
    result = _send_command(session, fixture.load_key_command())
    if (result.get("event") != "time_key_result" or
            result.get("case_id") != "GS68-AUX-TIME-001" or
            result.get("result") != "TEST_ONLY_PUBLIC_KEY_LOADED" or
            result.get("private_key_loaded") is not False or
            result.get("production_anchor") is not False):
        raise AuxiliaryDiagnosticError("target rejected or misreported TEST_ONLY public verification key")


def run_signed_time_valid_and_replay(session: BoundedAuxiliarySession, fixture) -> list[dict]:
    """Exercise target PSA challenge, RSA proof acceptance, then replay rejection."""
    from gs68_signed_time_fixture import TestOnlySignedTimeFixture
    if not isinstance(fixture, TestOnlySignedTimeFixture):
        raise TypeError("a process-local TEST_ONLY signing fixture is required")
    _load_test_time_authority(session, fixture)
    challenge = _time_challenge(session, "GS68-AUX-TIME-001")
    proof = fixture.proof_command(challenge)
    accepted = _send_command(session, proof)
    if (accepted.get("event") != "time_proof_result" or
            accepted.get("case_id") != "GS68-AUX-TIME-001" or
            accepted.get("challenge_nonce") != challenge["challenge_nonce"] or
            accepted.get("result") != "PASS" or
            accepted.get("signature") != "RSA3072_SHA256_VERIFIED" or
            accepted.get("time_authority") != "TEST_ONLY" or
            accepted.get("boot_generation") != challenge["boot_generation"] or
            accepted.get("private_key_exported") is not False):
        return [classify("FAIL", "target did not verify exact nonce/generation TEST_ONLY signed time")]
    replay = _send_command(session, proof)
    if (replay.get("event") != "case_result" or replay.get("case_outcome") != "FAIL" or
            replay.get("reason") != "NO_MATCHING_CURRENT_CHALLENGE"):
        return [classify("FAIL", "replayed signed-time proof was not rejected")]
    return [classify("PASS", "silicon PSA challenge, RSA-3072 proof, nonce/generation binding and replay rejection observed")]


def run_signed_time_negative_proofs(session: BoundedAuxiliarySession, fixture) -> list[dict]:
    """Continue an already-keyed TEST_ONLY session through negative proof cases."""
    from gs68_signed_time_fixture import TestOnlySignedTimeFixture
    if not isinstance(fixture, TestOnlySignedTimeFixture):
        raise TypeError("a process-local TEST_ONLY signing fixture is required")
    rows = []
    challenge = _time_challenge(session, "GS68-AUX-TIME-002")
    wrong_nonce = ("b" if challenge["challenge_nonce"][0] != "b" else "c") + challenge["challenge_nonce"][1:]
    wrong_frame = dict(challenge, challenge_nonce=wrong_nonce)
    wrong_proof = fixture.proof_command(wrong_frame)
    wrong_result = _send_command(session, wrong_proof)
    if (wrong_result.get("event") == "case_result" and wrong_result.get("case_outcome") == "FAIL" and
            wrong_result.get("reason") == "NO_MATCHING_CURRENT_CHALLENGE"):
        correct_result = _send_command(session, fixture.proof_command(challenge))
        if (correct_result.get("event") == "time_proof_result" and correct_result.get("result") == "PASS" and
                correct_result.get("challenge_nonce") == challenge["challenge_nonce"]):
            rows.append(classify("PASS", "mismatched nonce rejected and current challenge remained usable"))
        else:
            rows.append(classify("FAIL", "current challenge was not usable after wrong nonce rejection"))
    else:
        rows.append(classify("FAIL", "mismatched nonce proof was accepted or failure was unclassified"))

    challenge = _time_challenge(session, "GS68-AUX-TIME-002")
    invalid = fixture.proof_command(challenge)
    proof_bytes = bytearray(base64.b64decode(invalid["payload_b64"], validate=True))
    proof_bytes[-1] ^= 0x01
    invalid["payload_b64"] = base64.b64encode(proof_bytes).decode("ascii")
    result = _send_command(session, invalid)
    if (result.get("event") == "case_result" and result.get("case_outcome") == "FAIL" and
            result.get("reason") == "SIGNED_TIME_PROOF_REJECTED_OR_ROLLBACK_DETECTED"):
        rows.append(classify("PASS", "invalid RSA signature rejected"))
    else:
        rows.append(classify("FAIL", "invalid RSA signature was accepted or failure was unclassified"))

    expired_challenge = _time_challenge(session, "GS68-AUX-TIME-002")
    now = int(time.time())
    issued = now - 130
    proof_variant = {"issued_at_utc": issued, "valid_from_utc": issued - 20,
                     "valid_until_utc": issued + 120,
                     "boot_generation": expired_challenge["boot_generation"]}
    expired_challenge = dict(expired_challenge, proof_variant=proof_variant)
    expired = fixture.proof_command(expired_challenge)
    result = _send_command(session, expired)
    if (result.get("event") == "case_result" and result.get("case_outcome") == "FAIL" and
            result.get("reason") == "SIGNED_TIME_PROOF_REJECTED_OR_ROLLBACK_DETECTED"):
        rows.append(classify("PASS", "expired signed-time statement rejected"))
    else:
        rows.append(classify("FAIL", "expired signed-time statement was accepted or failure was unclassified"))

    stale_challenge = _time_challenge(session, "GS68-AUX-TIME-002")
    stale_generation = max(0, stale_challenge["boot_generation"] - 1)
    stale_frame = dict(stale_challenge, proof_variant={
        "issued_at_utc": now, "valid_from_utc": now,
        "valid_until_utc": now + 120, "boot_generation": stale_generation})
    stale = fixture.proof_command(stale_frame)
    result = _send_command(session, stale)
    if (result.get("event") == "case_result" and result.get("case_outcome") == "FAIL" and
            result.get("reason") == "SIGNED_TIME_PROOF_REJECTED_OR_ROLLBACK_DETECTED"):
        rows.append(classify("PASS", "stale boot-generation signed proof rejected"))
    else:
        rows.append(classify("FAIL", "stale boot-generation proof was accepted or failure was unclassified"))
    return rows


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
    from gs68_capture import PySerialTransport, WindowsNativeSerialTransport
    import gs68_cloudsync_hil as formal
    identity = fixture["identity"]
    transport_kind = fixture.get("transport", {}).get("kind") if isinstance(fixture.get("transport"), dict) else None
    if transport_factory is None and transport_kind == "windows-native":
        pnp = identity.get("pnp")
        if not isinstance(pnp, dict):
            return evidence_bundle(fixture_id=fixture["fixture_id"], source_commit=fixture["source_commit"],
                image_sha256=fixture["image"]["sha256"], records=[classify("BLOCKED",
                    "verified Windows spare PnP identity is missing")])
        transport = WindowsNativeSerialTransport(identity.get("com_port", ""),
            expected_port=identity.get("approved_com_port", ""), expected_pnp=pnp)
    else:
        try:
            observed = formal._inspect_by_id_port(identity["port_by_id"], identity["usb_serial_short"])
        except Exception as error:
            return evidence_bundle(fixture_id=fixture["fixture_id"], source_commit=fixture["source_commit"],
                image_sha256=fixture["image"]["sha256"], records=[classify("BLOCKED",
                    f"stable USB fixture identity unavailable: {type(error).__name__}")])
        if observed.get("usb_serial_short") != identity["usb_serial_short"]:
            return evidence_bundle(fixture_id=fixture["fixture_id"], source_commit=fixture["source_commit"],
                image_sha256=fixture["image"]["sha256"], records=[classify("FAIL", "live USB identity changed")])
        transport = (transport_factory or PySerialTransport)(identity["port_by_id"])
    session = BoundedAuxiliarySession(transport)
    rows = []
    try:
        session.open()
        ready = session.wait_ready(timeout=30)
        image_path = Path(fixture["image"].get("path", ""))
        if not image_path.is_absolute():
            image_path = Path(repo) / image_path
        expected_runtime_digest = expected_running_image_digest(
            image_path.read_bytes(), build_report, fixture["image"])
        if (ready.get("event") != "ready" or
                ready.get("running_image_sha256") != expected_runtime_digest or
                ready.get("source_commit") != fixture["source_commit"] or
                ready.get("profile_sha256") != fixture["profile"]["profile_sha256"] or
                formal._normalize_mac(str(ready.get("mac_address", ""))) !=
                    formal._normalize_mac(identity["mac_address"]) or
                ready.get("flash_bytes") != 16 * 1024 * 1024 or
                ready.get("psram_bytes") != 8 * 1024 * 1024 or
                ready.get("chip_model") != "ESP32-S3"):
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
    bundle = evidence_bundle(fixture_id=fixture["fixture_id"], source_commit=fixture["source_commit"],
        image_sha256=fixture["image"]["sha256"], records=rows)
    bundle["console_capture_records"] = session.console_records
    bundle["console_capture_sha256"] = hashlib.sha256(
        capture.canonical_json(session.console_records)).hexdigest()
    bundle["transport_control_events"] = getattr(transport, "control_events", [])
    return bundle


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
