from __future__ import annotations

import hashlib
import json
import struct
import time
import unittest
from unittest.mock import patch

import gs68_aux_diagnostic as aux
import gs68_build_provenance as provenance
import gs68_capture as capture
from gs68_signed_time_fixture import TestOnlySignedTimeFixture


def response(event="command_result", **extra):
    body = {"schema": "gs68.target.event.v1", "event": event, **extra}
    return capture.FRAME_PREFIX + capture.canonical_json(body) + b"\n"


def ready(**extra):
    fields = {"source_commit": "a" * 40, "profile_sha256": "b" * 64,
        "running_image_sha256": "c" * 64, "reset_reason": 1, "physical": "NOT_RUN"}
    fields.update(extra)
    return response("ready", **fields)


def valid_esp_image(chip_id=9):
    header = bytearray(24)
    header[0:4] = bytes((0xE9, 1, 0, 0x40))
    header[12:14] = chip_id.to_bytes(2, "little")
    header[23] = 1
    segment = b"diagnostic-segment"
    body = bytes(header) + struct.pack("<II", 0x3C030020, len(segment)) + segment
    checksum = 0xEF
    for value in segment:
        checksum ^= value
    checksum_offset = ((len(body) + 15) // 16) * 16 - 1
    body += bytes(checksum_offset - len(body)) + bytes((checksum,))
    return body + hashlib.sha256(body).digest()


class FakeTransport:
    def __init__(self, lines):
        self.lines = list(lines)
        self.writes = []
        self.opened = self.closed = False

    def open(self): self.opened = True
    def write(self, payload): self.writes.append(payload)
    def read_line(self, timeout): return self.lines.pop(0) if self.lines else b""
    def close(self): self.closed = True


class SignedTimeTarget(FakeTransport):
    def __init__(self):
        super().__init__([ready()])
        self.accepted = False

    def write(self, payload):
        super().write(payload)
        command = json.loads(payload)
        operation = command["operation"]
        if operation == "LOAD_TIME_KEY":
            self.lines.append(response("time_key_result", case_id=command["case_id"],
                result="TEST_ONLY_PUBLIC_KEY_LOADED", private_key_loaded=False, production_anchor=False))
        elif operation == "TIME_CHALLENGE":
            self.lines.append(response("time_challenge", case_id=command["case_id"],
                challenge_nonce="a" * 64, boot_generation=3, random_source="ESP32_S3_PSA"))
        elif operation == "TIME_PROOF" and not self.accepted:
            self.accepted = True
            self.lines.append(response("time_proof_result", case_id=command["case_id"],
                challenge_nonce=command["challenge_nonce"], result="PASS",
                signature="RSA3072_SHA256_VERIFIED", time_authority="TEST_ONLY",
                boot_generation=3, private_key_exported=False))
        else:
            self.lines.append(response("case_result", case_id=command["case_id"],
                challenge_nonce=command["challenge_nonce"], case_outcome="FAIL",
                reason="NO_MATCHING_CURRENT_CHALLENGE"))


class FakeDevice:
    def __init__(self, data=b""):
        self.data = bytearray(data)
        self.writes = []
        self.flush_count = 0
        self.close_count = 0

    def read(self, count):
        if not self.data:
            return b""
        value = bytes(self.data[:count])
        del self.data[:count]
        return value

    def write(self, value):
        self.writes.append(value)
        return len(value)

    def flush(self): self.flush_count += 1
    def close(self): self.close_count += 1


class FakeWindowsPlatform:
    def __init__(self, *, identity=None, owner=0, safe=True, data=b""):
        self.identity = identity or {"instance_id": "USB\\VID_303A&PID_1001\\SPARE",
            "vid": "303a", "pid": "1001", "serial": "SPARE-TEST"}
        self.owner = owner
        self.safe = safe
        self.device = FakeDevice(data)
        self.open_calls = []
        self.control_events = []
        self.port_events = []

    def inspect_pnp_identity(self, port): return self.identity
    def port_owner(self, port): return self.owner
    def reset_safe_open_policy(self, port):
        return {"verified": self.safe, "description": "mock-qualified no-toggle policy" if self.safe else "unqualified"}
    def open_serial(self, port, **kwargs):
        self.open_calls.append((port, kwargs))
        return self.device
    def take_control_line_events(self, port):
        events, self.control_events = self.control_events, []
        return events
    def take_port_events(self, port):
        events, self.port_events = self.port_events, []
        return events


class FakeWindowsNativeApi:
    def __init__(self, rows=None, *, open_error=None):
        self.rows = rows if rows is not None else [{"port": "COM10",
            "instance_id": "USB\\VID_303A&PID_1001&MI_00\\SPARE-TEST",
            "driver_version": "1.2.3", "present": True}]
        self.open_error = open_error
        self.open_calls = []
        self.device = FakeDevice()

    def enumerate_pnp_ports(self): return list(self.rows)
    def open_exclusive(self, port, **kwargs):
        self.open_calls.append((port, kwargs))
        if self.open_error:
            raise self.open_error
        return self.device


PNP = {"instance_id": "USB\\VID_303A&PID_1001\\SPARE", "vid": "303a",
       "pid": "1001", "serial": "SPARE-TEST"}


class GS68AuxiliaryRunnerTests(unittest.TestCase):
    def test_case_ids_are_auxiliary_and_never_official(self):
        self.assertEqual(len(aux.AUX_CASES), 7)
        self.assertTrue(all(case.startswith("GS68-AUX-") for case in aux.AUX_CASES))
        self.assertNotIn("GS68-PHY-003", aux.AUX_CASES)
        result = aux.classify("PASS", "host simulation")
        self.assertEqual(result["qualification_scope"], "AUXILIARY_TEST_ONLY_ONLY")
        self.assertEqual(result["official_gs68_physical_acceptance"], "NOT_RUN")

    def test_command_is_bounded_nonce_bound_and_auxiliary_only(self):
        with self.assertRaises(aux.AuxiliaryDiagnosticError):
            aux.command_frame("GS68-PHY-003", nonce="a" * 64)
        with self.assertRaises(aux.AuxiliaryDiagnosticError):
            aux.command_frame("GS68-AUX-USB-001", nonce="A" * 64)
        frame = json.loads(aux.command_frame("GS68-AUX-USB-001", nonce="a" * 64))
        self.assertEqual(frame["challenge_nonce"], "a" * 64)
        self.assertLessEqual(len(aux.command_frame("GS68-AUX-USB-001", nonce="a" * 64)), 1024)

    def test_source_provenance_allows_only_named_host_observer_deltas(self):
        self.assertTrue(aux.source_delta_is_host_only({"code/tools/hil/gs68_capture.py"}))
        self.assertFalse(aux.source_delta_is_host_only(set()))
        self.assertFalse(aux.source_delta_is_host_only({"code/firmware/hub/target/esp32s3/idf/app_main.cpp"}))
        self.assertFalse(aux.source_delta_is_host_only({
            "code/tools/hil/gs68_capture.py",
            "code/firmware/hub/target/esp32s3/idf/partitions.development.csv"}))

    def test_startup_logs_are_retained_before_ready_and_frame_order_is_preserved(self):
        transport = FakeTransport([b"I (10) boot: startup\r\n", b"I (11) app: ready soon\n", ready()])
        session = aux.BoundedAuxiliarySession(transport)
        session.open()
        frame = session.wait_ready(timeout=0.2)
        self.assertEqual(frame["event"], "ready")
        self.assertEqual([record["sequence"] for record in session.console_records], [1, 2, 3])
        self.assertEqual([record["kind"] for record in session.console_records],
                         ["console_log", "console_log", "structured_frame"])
        self.assertTrue(all("host_monotonic_ns" in record and "raw_base64" in record
                            for record in session.console_records))
        session.close()

    def test_fragmented_command_response_after_startup_is_correlated(self):
        nonce = "1" * 64
        transport = FakeTransport([b"I (1) boot: log\n", ready(),
            b"I (20) app: command accepted\n",
            response(case_id="GS68-AUX-USB-001", challenge_nonce=nonce,
                     operation="OBSERVE", result="OBSERVED_NO_ACTION")])
        session = aux.BoundedAuxiliarySession(transport)
        session.open()
        session.wait_ready(timeout=0.2)
        session.write(aux.command_frame("GS68-AUX-USB-001", nonce=nonce))
        frame = session.read_correlated_response(case_id="GS68-AUX-USB-001", nonce=nonce,
                                                 operation="OBSERVE", timeout=0.2)
        self.assertEqual(frame["result"], "OBSERVED_NO_ACTION")
        self.assertEqual([record["kind"] for record in session.console_records],
                         ["console_log", "structured_frame", "console_log", "structured_frame"])
        session.close()

    def test_windows_serial_reader_assembles_delayed_fragmented_response_in_one_open(self):
        nonce = "3" * 64
        startup = b"I (10) boot: startup\r\n" + ready()
        data = (startup +
                response(case_id="GS68-AUX-USB-001", challenge_nonce=nonce,
                         operation="OBSERVE", result="OBSERVED_NO_ACTION"))
        class DelayedResponseDevice(FakeDevice):
            def __init__(self, value, pause_at):
                super().__init__(value); self.read_count = 0; self.pause_at = pause_at
            def read(self, count):
                if self.read_count == self.pause_at: time.sleep(0.05)
                result = super().read(count)
                if result: self.read_count += 1
                return result
        platform = FakeWindowsPlatform(data=data)
        platform.device = DelayedResponseDevice(data, len(startup))
        transport = capture.WindowsNativeSerialTransport("COM10", expected_port="COM10",
            expected_pnp=PNP, platform=platform)
        session = aux.BoundedAuxiliarySession(transport)
        session.open(); session.wait_ready(timeout=1)
        session.write(aux.command_frame("GS68-AUX-USB-001", nonce=nonce))
        result = session.read_correlated_response(case_id="GS68-AUX-USB-001", nonce=nonce,
                                                   operation="OBSERVE", timeout=1)
        self.assertEqual(result["result"], "OBSERVED_NO_ACTION")
        self.assertEqual(len(platform.open_calls), 1)
        session.close()

    def test_usb_sequence_matches_firmware_malformed_and_oversized_contract(self):
        nonces = [f"{number:064x}" for number in range(1, 6)]
        transport = FakeTransport([ready(),
            response(case_id="GS68-AUX-USB-001", challenge_nonce=nonces[0],
                     operation="OBSERVE", result="OBSERVED_NO_ACTION"),
            response("case_result", case_id="GS68-PHY-001", challenge_nonce="0" * 64,
                     case_outcome="FAIL", reason="INVALID_OR_OVERSIZED_COMMAND"),
            response(case_id="GS68-AUX-USB-002", challenge_nonce=nonces[1],
                     operation="OBSERVE", result="OBSERVED_NO_ACTION"),
            response("capture_error", reason="oversized_command"),
            response(case_id="GS68-AUX-USB-002", challenge_nonce=nonces[2],
                     operation="OBSERVE", result="OBSERVED_NO_ACTION"),
            response(case_id="GS68-AUX-USB-003", challenge_nonce=nonces[3],
                     operation="OBSERVE", result="OBSERVED_NO_ACTION"),
            response(case_id="GS68-AUX-USB-003", challenge_nonce=nonces[4],
                     operation="OBSERVE", result="OBSERVED_NO_ACTION")])
        session = aux.BoundedAuxiliarySession(transport)
        session.open()
        session.wait_ready(timeout=0.2)
        try:
            with patch.object(aux.secrets, "token_hex", side_effect=nonces):
                rows = aux.run_usb_sequence(session, fragment_delay=0)
        finally:
            session.close()
        self.assertTrue(transport.closed)
        self.assertEqual([row["status"] for row in rows], ["PASS", "PASS", "PASS"])
        self.assertEqual(len(transport.writes), 5)
        self.assertTrue(all(row["official_gs68_physical_acceptance"] == "NOT_RUN" for row in rows))

    def test_response_nonce_operation_mismatch_and_missing_response_fail(self):
        wrong = FakeTransport([ready(), response(case_id="GS68-AUX-USB-001",
            challenge_nonce="2" * 64, operation="OBSERVE", result="OBSERVED_NO_ACTION")])
        session = aux.BoundedAuxiliarySession(wrong); session.open(); session.wait_ready(timeout=0.2)
        with self.assertRaisesRegex(aux.AuxiliaryDiagnosticError, "challenge_nonce"):
            session.read_correlated_response(case_id="GS68-AUX-USB-001", nonce="1" * 64,
                                             operation="OBSERVE", timeout=0.2)
        session.close()
        missing = aux.BoundedAuxiliarySession(FakeTransport([ready()]), timeout_seconds=1)
        missing.open(); missing.wait_ready(timeout=0.2)
        with self.assertRaisesRegex(aux.AuxiliaryDiagnosticError, "missing before timeout"):
            missing.read_correlated_response(case_id="GS68-AUX-USB-001", nonce="1" * 64,
                                              operation="OBSERVE", timeout=0.1)
        missing.close()

    def test_operation_mismatch_is_rejected(self):
        session = aux.BoundedAuxiliarySession(FakeTransport([ready(), response(
            case_id="GS68-AUX-USB-001", challenge_nonce="1" * 64,
            operation="TIME_PROOF", result="OBSERVED_NO_ACTION")]))
        session.open(); session.wait_ready(timeout=0.2)
        with self.assertRaisesRegex(aux.AuxiliaryDiagnosticError, "operation"):
            session.read_correlated_response(case_id="GS68-AUX-USB-001", nonce="1" * 64,
                                              operation="OBSERVE", timeout=0.2)
        session.close()

    def test_unexpected_ready_during_outstanding_command_stops_qualification(self):
        session = aux.BoundedAuxiliarySession(FakeTransport([ready(), ready(reset_reason=3)]))
        session.open(); session.wait_ready(timeout=0.2)
        with self.assertRaisesRegex(aux.AuxiliaryDiagnosticError, "unexpected READY"):
            session.read_frame(timeout=0.2)
        self.assertTrue(session.ready_reobserved)
        self.assertEqual(session.console_records[-1]["kind"], "unexpected_ready")
        session.close()

    def test_repeated_startup_transcript_is_suspected_not_called_a_reset(self):
        boot_lines = [b"I (10) boot: first\n", b"I (11) boot: second\n", b"I (12) boot: third\n"]
        session = aux.BoundedAuxiliarySession(FakeTransport(boot_lines + [ready()] + boot_lines))
        session.open(); session.wait_ready(timeout=0.2)
        with self.assertRaisesRegex(aux.AuxiliaryDiagnosticError, "startup transcript replay suspected"):
            session.read_frame(timeout=0.2)
        self.assertTrue(session.startup_replay_suspected)
        replayed_ready = json.loads(ready()[len(capture.FRAME_PREFIX):-1])
        self.assertEqual(capture.classify_ready_transition(session.ready_frame, replayed_ready),
                         "BOOT_TRANSITION_AMBIGUOUS_INSUFFICIENT_TARGET_EVIDENCE")
        session.close()

    def test_true_reboot_can_be_confirmed_only_by_new_boot_generation(self):
        old = {"boot_generation": 4, "uptime_ms": 9000, "reset_reason": 1}
        new = {"boot_generation": 5, "uptime_ms": 120, "reset_reason": 3}
        self.assertEqual(capture.classify_ready_transition(old, new), "NEW_BOOT_CONFIRMED_BY_GENERATION")
        self.assertEqual(capture.classify_ready_transition(
            {"uptime_ms": 9000}, {"uptime_ms": 30}), "UPTIME_REGRESSION_POSSIBLE_NEW_BOOT")

    def test_malformed_structured_frame_and_oversized_line_are_not_discarded(self):
        session = aux.BoundedAuxiliarySession(FakeTransport([b"GS68/1 {bad}\n"]))
        session.open()
        with self.assertRaisesRegex(aux.AuxiliaryDiagnosticError, "malformed GS68/1"):
            session.wait_ready(timeout=0.2)
        self.assertEqual(session.console_records[0]["kind"], "malformed_structured_frame")
        session.close()
        session = aux.BoundedAuxiliarySession(FakeTransport([b"x" * (capture.MAX_FRAME_BYTES + 1) + b"\n"]))
        session.open()
        with self.assertRaisesRegex(aux.AuxiliaryDiagnosticError, "line exceeds size"):
            session.wait_ready(timeout=0.2)
        self.assertEqual(session.console_records[0]["kind"], "oversized_line")
        session.close()

    def test_line_and_total_capture_bounds_fail_closed(self):
        session = aux.BoundedAuxiliarySession(FakeTransport([b"log\n", b"log2\n"]), max_lines=1)
        session.open()
        with self.assertRaisesRegex(aux.AuxiliaryDiagnosticError, "line-count"):
            session.wait_ready(timeout=0.2)
        session.close()
        session = aux.BoundedAuxiliarySession(FakeTransport([b"12345\n"]), max_bytes=4)
        session.open()
        with self.assertRaisesRegex(aux.AuxiliaryDiagnosticError, "byte limit"):
            session.wait_ready(timeout=0.2)
        session.close()

    def test_timeout_disconnect_and_malformed_structured_response_never_pass(self):
        session = aux.BoundedAuxiliarySession(FakeTransport([]))
        session.open()
        with self.assertRaisesRegex(aux.AuxiliaryDiagnosticError, "READY response missing"):
            session.wait_ready(timeout=0.1)
        session.close()
        session = aux.BoundedAuxiliarySession(FakeTransport([ready(), b"GS68/1 nope\n"]))
        session.open(); session.wait_ready(timeout=0.2)
        with self.assertRaisesRegex(aux.AuxiliaryDiagnosticError, "malformed GS68/1"):
            session.read_frame(timeout=0.2)
        session.close()

    def test_esp_image_validation_digest_matches_runtime_but_not_full_artifact_hash(self):
        image = valid_esp_image()
        runtime_digest = provenance.esp_image_validation_sha256(image)
        self.assertEqual(runtime_digest, image[-32:].hex())
        self.assertEqual(runtime_digest, hashlib.sha256(image[:-32]).hexdigest())
        self.assertNotEqual(runtime_digest, hashlib.sha256(image).hexdigest())

    def test_invalid_or_unsupported_image_digest_is_rejected(self):
        image = bytearray(valid_esp_image())
        image[40] ^= 1
        with self.assertRaisesRegex(ValueError, "checksum|validation hash"):
            provenance.esp_image_validation_sha256(bytes(image))
        with self.assertRaisesRegex(ValueError, "chip ID"):
            provenance.esp_image_validation_sha256(valid_esp_image(chip_id=5))
        with self.assertRaisesRegex(ValueError, "magic"):
            provenance.esp_image_validation_sha256(b"not-an-esp-image")

    def test_build_or_fixture_runtime_digest_mismatch_is_rejected(self):
        image = valid_esp_image()
        derived = provenance.esp_image_validation_sha256(image)
        self.assertEqual(aux.expected_running_image_digest(image, {}, {}), derived)
        with self.assertRaisesRegex(aux.AuxiliaryDiagnosticError, "build report image validation digest"):
            aux.expected_running_image_digest(image, {"image_validation_sha256": "d" * 64}, {})
        with self.assertRaisesRegex(aux.AuxiliaryDiagnosticError, "fixture image validation digest"):
            aux.expected_running_image_digest(image, {}, {"image_validation_sha256": "e" * 64})

    def test_windows_transport_pins_pnp_checks_owner_and_reset_safe_open_policy(self):
        platform = FakeWindowsPlatform(data=b"abc\n")
        transport = capture.WindowsNativeSerialTransport("COM10", expected_port="COM10", expected_pnp=PNP,
                                                         platform=platform)
        transport.open()
        self.assertEqual(platform.open_calls[0][1], {"baudrate": 115200, "timeout": 0.2,
            "write_timeout": 1.0, "flow_control": False, "expected_pnp": PNP})
        self.assertEqual(transport.read_line(0.2), b"abc\n")
        transport.write(b"OBSERVE\n")
        self.assertEqual(platform.device.flush_count, 1)
        with self.assertRaisesRegex(capture.WindowsPortPreflightError, "only once"):
            transport.open()
        transport.close()
        self.assertFalse(any("reset_input_buffer" in str(event) for event in transport.control_events))

    def test_windows_transport_rejects_wrong_identity_busy_port_and_unsafe_driver(self):
        wrong = FakeWindowsPlatform(identity={**PNP, "instance_id": "OTHER-DEVICE"})
        transport = capture.WindowsNativeSerialTransport("COM10", expected_port="COM10", expected_pnp=PNP, platform=wrong)
        with self.assertRaisesRegex(capture.WindowsPortPreflightError, "PnP identity"):
            transport.open()
        busy = FakeWindowsPlatform(owner=4321)
        transport = capture.WindowsNativeSerialTransport("COM10", expected_port="COM10", expected_pnp=PNP, platform=busy)
        with self.assertRaisesRegex(capture.WindowsPortPreflightError, "owned by another"):
            transport.open()
        unsafe = FakeWindowsPlatform(safe=False)
        transport = capture.WindowsNativeSerialTransport("COM10", expected_port="COM10", expected_pnp=PNP, platform=unsafe)
        with self.assertRaisesRegex(capture.WindowsPortPreflightError, "cannot prove reset-safe"):
            transport.open()
        self.assertEqual(unsafe.open_calls, [])
        with self.assertRaises(capture.WindowsPortPreflightError):
            capture.WindowsNativeSerialTransport("COM10", expected_port="COM10", expected_pnp={"serial": "SPARE"}, platform=unsafe)
        with self.assertRaises(capture.WindowsPortPreflightError):
            capture.WindowsNativeSerialTransport("COM11", expected_port="COM10", expected_pnp=PNP, platform=wrong)

    def test_windows_transport_records_observable_control_line_events_and_disconnect(self):
        platform = FakeWindowsPlatform(data=b"x\n")
        platform.control_events = [{"line": "DTR", "operation": "unchanged", "status": "PASS"}]
        platform.port_events = [{"kind": "present", "status": "PASS"}]
        transport = capture.WindowsNativeSerialTransport("COM10", expected_port="COM10", expected_pnp=PNP, platform=platform)
        transport.open()
        transport.read_line(0.2)
        self.assertTrue(any(event.get("operation") == "control_line" for event in transport.control_events))
        self.assertTrue(any(event.get("operation") == "host_port_event" for event in transport.control_events))

        toggled = FakeWindowsPlatform()
        toggled.control_events = [{"line": "DTR", "operation": "pulse", "status": "FAIL"}]
        unsafe_transport = capture.WindowsNativeSerialTransport("COM10", expected_port="COM10",
            expected_pnp=PNP, platform=toggled)
        with self.assertRaisesRegex(capture.WindowsPortPreflightError, "DTR control-line activity"):
            unsafe_transport.open()

        class DisconnectingDevice(FakeDevice):
            def read(self, count): raise OSError("USB disconnected")
        disconnected = FakeWindowsPlatform()
        disconnected.device = DisconnectingDevice()
        transport2 = capture.WindowsNativeSerialTransport("COM10", expected_port="COM10", expected_pnp=PNP, platform=disconnected)
        transport2.open()
        with self.assertRaisesRegex(capture.CaptureError, "automatic reconnect is disabled"):
            transport2.read_line(0.1)
        self.assertEqual(len(disconnected.open_calls), 1)

    def test_windows_provider_resolves_current_pnp_identity_without_opening_port(self):
        native = FakeWindowsNativeApi()
        provider = capture.WindowsSerialPlatform(native_api=native)
        self.assertEqual(provider.inspect_pnp_identity("COM10"), {
            "instance_id": "USB\\VID_303A&PID_1001&MI_00\\SPARE-TEST",
            "vid": "303a", "pid": "1001", "serial": "SPARE-TEST", "driver_version": "1.2.3"})
        self.assertIsNone(provider.inspect_pnp_identity("COM11"))
        self.assertEqual(native.open_calls, [])
        self.assertIsNone(provider.port_owner("COM10"))
        self.assertTrue(provider.exclusive_open_is_ownership_check("COM10"))

    def test_windows_provider_rejects_duplicate_or_unparseable_pnp_and_missing_policy(self):
        for rows in (
            [{"port": "COM10", "instance_id": PNP["instance_id"], "present": True}] * 2,
            [{"port": "COM10", "instance_id": "ROOT\\SERIAL\\UNKNOWN", "present": True}],
        ):
            provider = capture.WindowsSerialPlatform(native_api=FakeWindowsNativeApi(rows))
            self.assertIsNone(provider.inspect_pnp_identity("COM10"))
        native = FakeWindowsNativeApi()
        provider = capture.WindowsSerialPlatform(native_api=native)
        self.assertIsNone(provider.port_owner("COM10"))
        self.assertFalse(provider.reset_safe_open_policy("COM10")["verified"])
        self.assertEqual(native.open_calls, [])

    def test_windows_provider_unavailable_on_non_windows_host_fails_before_port_io(self):
        expected = {"instance_id": PNP["instance_id"], "vid": "303a", "pid": "1001",
                    "serial": "SPARE-TEST"}
        transport = capture.WindowsNativeSerialTransport("COM10", expected_port="COM10",
            expected_pnp=expected)
        with self.assertRaisesRegex(capture.WindowsPortPreflightError, "unavailable on this host"):
            transport.open()

    def test_windows_transport_uses_one_exclusive_open_after_policy_and_reports_owner_unknown(self):
        native = FakeWindowsNativeApi()
        checked = []
        provider = capture.WindowsSerialPlatform(native_api=native, reset_safe_policy=lambda identity: (
            checked.append(identity) or {"verified": True, "evidence_id": "MOCK-ONLY"}))
        expected = {"instance_id": "USB\\VID_303A&PID_1001&MI_00\\SPARE-TEST",
                    "vid": "303a", "pid": "1001", "serial": "SPARE-TEST"}
        transport = capture.WindowsNativeSerialTransport("COM10", expected_port="COM10",
            expected_pnp=expected, platform=provider)
        with patch.object(capture.sys, "platform", "win32"):
            transport.open()
        self.assertEqual(len(native.open_calls), 1)
        self.assertEqual(native.open_calls[0][0], "COM10")
        self.assertEqual(native.open_calls[0][1], {"baudrate": 115200, "timeout": 0.2,
                                                    "write_timeout": 1.0})
        self.assertEqual(checked[0]["driver_version"], "1.2.3")
        self.assertTrue(any(row.get("result") == "UNKNOWN" for row in transport.control_events))
        transport.close()

    def test_windows_exclusive_open_busy_or_access_denied_never_retries(self):
        native = FakeWindowsNativeApi(open_error=capture.WindowsPortBusyError("busy"))
        provider = capture.WindowsSerialPlatform(native_api=native, reset_safe_policy=lambda _: {
            "verified": True, "evidence_id": "MOCK-ONLY"})
        expected = {"instance_id": "USB\\VID_303A&PID_1001&MI_00\\SPARE-TEST",
                    "vid": "303a", "pid": "1001", "serial": "SPARE-TEST"}
        transport = capture.WindowsNativeSerialTransport("COM10", expected_port="COM10",
            expected_pnp=expected, platform=provider)
        with patch.object(capture.sys, "platform", "win32"):
            with self.assertRaisesRegex(capture.WindowsPortBusyError, "busy"):
                transport.open()
        self.assertEqual(len(native.open_calls), 1)
        with self.assertRaisesRegex(capture.WindowsPortPreflightError, "only once"):
            transport.open()

    def test_windows_pnp_reenumeration_is_reported_without_reconnect(self):
        native = FakeWindowsNativeApi()
        provider = capture.WindowsSerialPlatform(native_api=native)
        self.assertIsNotNone(provider.inspect_pnp_identity("COM10"))
        native.rows = []
        self.assertEqual(provider.take_port_events("COM10")[0]["kind"], "removed")
        native.rows = [{"port": "COM10", "instance_id": PNP["instance_id"], "present": True}]
        self.assertEqual(provider.take_port_events("COM10")[0]["kind"], "reenumerated")
        self.assertEqual(native.open_calls, [])

    def test_windows_transport_stops_on_pnp_reenumeration_or_unknown_presence(self):
        for event in ({"kind": "reenumerated"}, {"kind": "presence_unknown"}):
            platform = FakeWindowsPlatform(data=b"late\n")
            transport = capture.WindowsNativeSerialTransport("COM10", expected_port="COM10",
                expected_pnp=PNP, platform=platform)
            transport.open()
            platform.port_events = [event]
            with self.assertRaisesRegex(capture.CaptureError, "disconnected"):
                transport.read_line(0.1)
            self.assertEqual(len(platform.open_calls), 1)
            transport.close()

    def test_windows_provider_rechecks_pnp_identity_before_single_open(self):
        original = {"port": "COM10", "instance_id": "USB\\VID_303A&PID_1001\\SPARE-TEST",
                    "driver_version": "1.2.3", "present": True}
        replacement = {"port": "COM10", "instance_id": "USB\\VID_303A&PID_1001\\OTHER-DEVICE",
                       "driver_version": "1.2.3", "present": True}

        class ChangesAfterPreflight(FakeWindowsNativeApi):
            def __init__(self):
                super().__init__()
                self.calls = 0
            def enumerate_pnp_ports(self):
                self.calls += 1
                return [replacement if self.calls >= 3 else original]

        native = ChangesAfterPreflight()
        provider = capture.WindowsSerialPlatform(native_api=native, reset_safe_policy=lambda _: {
            "verified": True, "evidence_id": "MOCK-ONLY"})
        expected = {"instance_id": original["instance_id"], "vid": "303a", "pid": "1001",
                    "serial": "SPARE-TEST"}
        transport = capture.WindowsNativeSerialTransport("COM10", expected_port="COM10",
            expected_pnp=expected, platform=provider)
        with patch.object(capture.sys, "platform", "win32"):
            with self.assertRaisesRegex(capture.WindowsPortPreflightError, "immediately before"):
                transport.open()
        self.assertEqual(native.open_calls, [])

    def test_bundle_hashes_records_and_cannot_promote_official_cases(self):
        bundle = aux.evidence_bundle(fixture_id="GS68-SPARE-001", source_commit="a" * 40,
            image_sha256="b" * 64, records=[aux.classify("BLOCKED", "inspection unavailable")])
        self.assertEqual(bundle["physical"], "AUXILIARY_TEST_ONLY_ONLY")
        self.assertEqual(bundle["official_gs68_physical_acceptance"], "NOT_RUN")
        self.assertEqual(len(bundle["records_sha256"],), 64)

    def test_unproven_fixture_install_gates_block_before_transport_creation(self):
        fixture = {"fixture_id": "GS68-SPARE-UNASSIGNED", "source_commit": "a" * 40,
                   "image": {"sha256": "b" * 64}}
        with patch.object(aux, "validate_candidate_binding", return_value=[]), \
             patch.object(aux, "PySerialTransport", side_effect=AssertionError("serial opened"),
                          create=True):
            result = aux.execute_usb_if_ready(fixture, {}, repo=__import__("pathlib").Path("."))
        self.assertEqual(result["physical"], "AUXILIARY_TEST_ONLY_ONLY")
        self.assertEqual(result["official_gs68_physical_acceptance"], "NOT_RUN")
        self.assertTrue(all(row["status"] == "BLOCKED" for row in result["records"]))

    def test_test_only_rsa_challenge_proof_and_replay_are_correlated(self):
        transport = SignedTimeTarget()
        session = aux.BoundedAuxiliarySession(transport)
        session.open(); session.wait_ready(timeout=0.2)
        try:
            rows = aux.run_signed_time_valid_and_replay(session, TestOnlySignedTimeFixture())
        finally:
            session.close()
        self.assertEqual(rows[0]["status"], "PASS")
        self.assertTrue(transport.closed)
        self.assertTrue(all(b"private" not in write for write in transport.writes))

    def test_missing_identity_target_preflight_never_constructs_http_request(self):
        from pathlib import Path
        source = Path(__file__).parents[2] / "firmware/hub/target/esp32s3/idf/gs68_cloudsync_diagnostic/app_main.cpp"
        body = source.read_text()
        start = body.index("void handle_missing_identity_case(")
        end = body.index("void handle_time_key(", start)
        handler = body[start:end]
        self.assertNotIn("channel.post", handler)
        self.assertIn("network_attempted=false", handler)
        self.assertIn("UnprovisionedS3CloudTrust", handler)

    def test_firmware_and_runner_agree_on_framing_error_shapes(self):
        from pathlib import Path
        source = Path(__file__).parents[2] / "firmware/hub/target/esp32s3/idf/gs68_cloudsync_diagnostic/app_main.cpp"
        body = source.read_text()
        self.assertIn('emit_command_failure(invalid, "INVALID_OR_OVERSIZED_COMMAND")', body)
        self.assertIn('emit_capture_error("oversized_command")', body)
        self.assertIn('event\\":\\"capture_error', body)


if __name__ == "__main__":
    unittest.main()
