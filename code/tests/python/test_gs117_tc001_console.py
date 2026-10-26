"""TC-001 software guard and correlation checks; never opens hardware."""
from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
import hashlib
import io
from http.server import ThreadingHTTPServer
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "local"))
import gs117_tc001_console as tc
import gs117_tc001_serial_windows as tc_serial


class TC001Test(unittest.TestCase):
    def test_console_loads_shared_identity_rules_without_pythonpath(self):
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        probe = (
            "import runpy; runpy.run_path(" + repr(str(Path(tc.__file__).resolve())) +
            ", run_name='gs117_console_import_probe')"
        )
        result = subprocess.run(
            [sys.executable, "-c", probe], cwd=Path(__file__).resolve().parents[3],
            env=environment, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_fixture_blocks_before_serial(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(tc, "FIXTURE", Path(directory) / "missing.json"):
            with self.assertRaisesRegex(ValueError, "owner_only_fixture"):
                tc.exact_fixture()

    def test_physical_mac_identity_shapes_are_strict_and_distinct_from_host_sim(self):
        self.assertTrue(tc.is_gs179_test_hub_id("test-hub-a"))
        self.assertTrue(tc.is_gs179_test_node_id("test-c3-bedroom"))
        self.assertTrue(tc.is_gs179_test_hub_id("hub-001122334455"))
        self.assertTrue(tc.is_gs179_test_node_id("c3-001122334455"))
        self.assertTrue(tc.is_gs179_test_hub_home(
            "hub-e072a1d38d34", "gs177-test-product"))
        self.assertFalse(tc.is_gs179_test_hub_home(
            "hub-001122334455", "gs177-test-product"))
        self.assertFalse(tc.is_gs179_test_hub_home(
            "hub-e072a1d38d34", "gs177-test-other"))
        self.assertTrue(tc.is_gs179_test_hub_home("test-hub-a", "gs177-test-product"))
        for invalid in ("hub-00112233445z", "hub-00112233445500", "test-hub-a "):
            with self.subTest(invalid=invalid):
                self.assertFalse(tc.is_gs179_test_hub_id(invalid))
        for invalid in ("c3-00112233445z", "c3-00112233445500", "test-c3-bedroom "):
            with self.subTest(invalid=invalid):
                self.assertFalse(tc.is_gs179_test_node_id(invalid))

    def test_second_run_is_refused_while_one_is_active(self):
        controller = tc.Controller()
        controller.lock.acquire()
        try:
            self.assertIsNone(controller.start())
        finally:
            controller.lock.release()

    def test_fixture_rejects_unsupported_firmware_untrusted_hub_and_wrong_phone(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            now = datetime.now(timezone.utc).isoformat()
            fixture = {"schema_version": 1, "test_id": "TC-001", "profile": "GS179_TEST_ONLY",
                       "home_id": "gs177-test-product", "logical_node_id": "bedroom",
                       "physical_device_id": "test-c3-bedroom", "hub_id": "test-hub-a",
                       "installation_epoch": 1, "approval_ref": "GS-117/example-explicit-approval",
                       "approval_scope": "C3 GET_STATE and INJECT_MOTION; C3/S3 UART observation",
                       "reset_safe_uart_verified": True,
                       "expected_caregiver_origin": "https://laptop.local"}
            for name, target, port in (("c3", "ESP32-C3", "COM10"), ("s3", "ESP32-S3", "COM11")):
                image = root / (name + ".bin"); image.write_bytes(name.encode())
                digest = hashlib.sha256(name.encode()).hexdigest()
                receipt = root / (name + ".json")
                receipt.write_text(json.dumps({"running_image_sha256": digest, "target": target,
                                               "usb_hwid": name, "serial_number": name + "s",
                                               "firmware_source_head": "a" * 40,
                                               "installed_at": now, "observed_at": now,
                                               "active_ota_slot": "ota_0",
                                               "partition_table_sha256": "e" * 64,
                                               "flash_size_bytes": (4 if name == "c3" else 16) * 1024 * 1024,
                                               "psram_size_bytes": 8 * 1024 * 1024 if name == "s3" else 0}))
                fixture[name] = {"port": port, "usb_hwid": name, "serial_number": name + "s",
                                 "image": str(image), "image_sha256": digest,
                                 "installed_image_receipt": str(receipt),
                                 "firmware_source_head": "a" * 40}
            fixture["c3"].update(hil_control=True, hil_build=False, physical_wake=False)
            fixture["s3"]["full_product_composition"] = True
            phone = root / "phone.json"
            phone_state = {"profile": "GS179_TEST_ONLY", "package": "in.gharsajag.caregiver.discoverytest",
                           "installed": True, "home_id": "gs177-test-product",
                           "backend_origin": "https://laptop.local", "signer_sha256": "b" * 64,
                           "observed_at": now}
            phone.write_text(json.dumps(phone_state)); fixture["phone_install_receipt"] = str(phone)
            ingress = root / "ingress.json"
            ingress_state = {"profile": "GS179_TEST_ONLY", "home_id": "gs177-test-product",
                             "hub_id": "test-hub-a", "installation_epoch": 1,
                             "node_device_id": "test-c3-bedroom", "node_enrollment_verified": True,
                             "mtls_client_cert_sha256": "c" * 64, "server_cert_sha256": "d" * 64,
                             "authenticated_hub_identity": True, "trusted_time_ready": True,
                             "persistent_listener_ready": True, "observed_at": now}
            ingress.write_text(json.dumps(ingress_state)); fixture["hub_ingress_receipt"] = str(ingress)
            manifest = root / "fixture.json"
            def write():
                manifest.write_text(json.dumps(fixture)); manifest.chmod(0o600)
            with patch.object(tc, "FIXTURE", manifest):
                write(); self.assertEqual(tc.exact_fixture()["hub_id"], "test-hub-a")
                fixture["c3"]["hil_control"] = False; write()
                with self.assertRaisesRegex(ValueError, "HIL"):
                    tc.exact_fixture()
                fixture["c3"]["hil_control"] = True; write()
                ingress_state["trusted_time_ready"] = False; ingress.write_text(json.dumps(ingress_state))
                with self.assertRaisesRegex(ValueError, "Hub_ingress"):
                    tc.exact_fixture()
                ingress_state["trusted_time_ready"] = True; ingress.write_text(json.dumps(ingress_state))
                phone_state["backend_origin"] = "https://other.local"; phone.write_text(json.dumps(phone_state))
                with self.assertRaisesRegex(ValueError, "installed_APK"):
                    tc.exact_fixture()
                phone_state["backend_origin"] = "https://laptop.local"; phone.write_text(json.dumps(phone_state))
                fixture["hub_id"] = "hub-e072a1d38d34"
                fixture["physical_device_id"] = "c3-146393c5d158"
                ingress_state["hub_id"] = fixture["hub_id"]
                ingress_state["node_device_id"] = fixture["physical_device_id"]
                ingress.write_text(json.dumps(ingress_state))
                for name, identity in (("c3", fixture["physical_device_id"]),
                                       ("s3", fixture["hub_id"])):
                    receipt_path = Path(fixture[name]["installed_image_receipt"])
                    receipt_state = json.loads(receipt_path.read_text())
                    receipt_state["permanent_device_id"] = identity
                    receipt_path.write_text(json.dumps(receipt_state))
                write()
                self.assertEqual(tc.exact_fixture()["physical_device_id"], "c3-146393c5d158")
                c3_receipt_path = Path(fixture["c3"]["installed_image_receipt"])
                c3_receipt = json.loads(c3_receipt_path.read_text())
                c3_receipt["permanent_device_id"] = "c3-aabbccddeeff"
                c3_receipt_path.write_text(json.dumps(c3_receipt))
                with self.assertRaisesRegex(ValueError, "physical_MAC_derived_identity_receipts"):
                    tc.exact_fixture()

    def test_c3_event_requires_hil_ack_and_exactly_one_new_key(self):
        lines = ["HIL_OK command=INJECT_MOTION", "PIR -> NodeRuntime session=12 seq=3"]
        self.assertEqual(tc.physical_key(lines), (12, 3))
        self.assertIsNone(tc.physical_key(lines[1:]))
        self.assertIsNone(tc.physical_key(lines + ["PIR -> NodeRuntime session=12 seq=4"]))

    def test_s3_requires_authenticated_matching_durable_event(self):
        good = "Authenticated event logical=bedroom session=12 seq=3 sensor=PIR event=MOTION event_id=p15:test-c3-bedroomn7:bedrooms12q3 room=bedroom ack=0 send=ESP_OK"
        self.assertTrue(tc.s3_durable_event([good], 12, 3, "test-c3-bedroom"))
        for altered in (good.replace("seq=3", "seq=4"), good.replace("ack=0", "ack=1"),
                        good.replace("logical=bedroom", "logical=kitchen"),
                        good.replace("Authenticated", "Unauthenticated"),
                        good.replace("test-c3-bedroom", "test-c3-kitchen")):
            with self.subTest(altered=altered):
                self.assertFalse(tc.s3_durable_event([altered], 12, 3, "test-c3-bedroom"))

    def report(self):
        return {"run_id": "TC001-test", "test_id": "TC-001", "overall": "PARTIAL",
                "apk_observation": "NOT_VERIFIED", "stages": {
                    name: {"status": "NOT_VERIFIED", "reason": "not reached"} for name in tc.STAGES}}

    def execute(self, report, serial_data, baseline=None, outcome=None, home_origin="https://laptop.local", ports_override=None, mode_state=True):
        fixture = {"home_id": "gs177-test-product", "physical_device_id": "test-c3-bedroom",
                   "expected_caregiver_origin": "https://laptop.local",
                   "approval_ref": "test", "hub_id": "test-hub-a", "installation_epoch": 1,
                   "c3": {"port": "COM10", "usb_hwid": "c3", "serial_number": "c3s",
                          "image_sha256": "a" * 64, "firmware_source_head": "a" * 40},
                   "s3": {"port": "COM11", "usb_hwid": "s3", "serial_number": "s3s",
                          "image_sha256": "b" * 64, "firmware_source_head": "b" * 40}}
        ports = [{"port": b["port"], "usb_hwid": b["usb_hwid"], "serial_number": b["serial_number"]}
                 for b in (fixture["c3"], fixture["s3"])]
        baseline = baseline or {"keys": [], "count": 0}
        if (mode_state and "c3" in serial_data and
                any("HIL_OK command=INJECT_MOTION" in line for line in serial_data["c3"])):
            serial_data["c3"].insert(0, "HIL_STATE role=c3 power_mode=HIL_AWAKE_TEST_ONLY hil_build=0 hil_control=1 physical_wake=0")
        baseline.setdefault("authority_ready", True)
        baseline.setdefault("enrollment_generation", 1)
        outcome = outcome or {"durable_count": 1, "caregiver_count": 1,
                              "event_kind": "MOTION", "event_location": "bedroom",
                              "event_id": "evt-1", "caregiver_event_id": tc.event_key_text(
                                  "test-c3-bedroom", *(tc.physical_key(serial_data.get("c3", [])) or (12, 3))),
                              "committing_hub_id": "test-hub-a", "ownership_epoch": 1,
                              "node_enrollment_generation": 1}
        controller = tc.Controller()
        controller.lock.acquire()
        with (patch.object(controller, "readiness", return_value={"backend": {"POSTGRES_READY": "PASS", "CAREGIVER_HTTPS_READY": "PASS"}, "caregiver_home": {"caregiver_home_ready": True, "backend_origin": home_origin}}),
              patch.object(tc, "exact_fixture", return_value=fixture),
              patch.object(tc, "powershell", side_effect=[ports if ports_override is None else ports_override, serial_data]) as hardware,
              patch.object(tc, "backend", side_effect=[baseline, outcome]),
              patch.object(controller, "save")):
            controller.execute(report)
        self.assertFalse(controller.lock.locked())
        return hardware

    def test_source_linked_success_waits_for_apk_and_is_repeatable(self):
        for session, sequence in ((12, 3), (12, 4)):
            with self.subTest(key=(session, sequence)):
                c3 = ["HIL_OK command=INJECT_MOTION",
                      f"PIR -> NodeRuntime session={session} seq={sequence}"]
                s3 = [f"Authenticated event logical=bedroom session={session} seq={sequence} sensor=PIR event=MOTION event_id=p15:test-c3-bedroomn7:bedrooms{session}q{sequence} room=bedroom ack=0 send=ESP_OK"]
                report = self.report()
                self.execute(report, {"c3": c3, "s3": s3}, baseline={"keys": [[12, sequence - 1]], "count": 1})
                self.assertEqual(report["stages"]["caregiver_api"]["status"], "PASS")
                self.assertEqual(report["stages"]["android_apk"]["status"], "NOT_VERIFIED")
                self.assertEqual(report["apk_observation"], "NOT_VERIFIED")
                self.assertEqual(report["event_key"]["event_sequence"], sequence)

    def test_reset_aware_observer_queries_status_without_motion_injection(self):
        class FakeSerial:
            def __init__(self):
                self.port = ""
                self.timeout = None
                self.write_timeout = None
                self.dtr = True
                self.rts = True
                self.is_open = False
                self.buffer = bytearray()
                self.writes = []
                self.input_purges = 0

            @property
            def in_waiting(self):
                return len(self.buffer)

            def open(self):
                self.is_open = True
                if self.port == "COM10":
                    self.buffer.extend(
                        b"I (1) HIL_FIXTURE_READY protocol=1 commands=FIXTURE_STATUS\n"
                        b"I (2) HubRuntime storage=ready CloudSync=disabled\n")

            def write(self, data):
                self.writes.append(data)
                if data == b"GET_STATE\n":
                    self.buffer.extend(
                        b"I (2) HIL_STATE role=c3 power_mode=HIL_AWAKE_TEST_ONLY "
                        b"hil_build=0 hil_control=1 physical_wake=0 "
                        b"wifi_psk=private password=private\n")
                return len(data)

            def flush(self):
                pass

            def reset_input_buffer(self):
                self.input_purges += 1
                self.buffer.clear()

            def read(self, count):
                result = bytes(self.buffer[:count])
                del self.buffer[:count]
                return result

            def close(self):
                self.is_open = False

        boards = {
            "c3": {"port": "COM4", "serial_number": "14:63:93:C5:D1:58",
                   "usb_hwid": "USB VID:PID=303A:1001 SER=14:63:93:C5:D1:58"},
            "s3": {"port": "COM10", "serial_number": "E0:72:A1:D3:8D:34",
                   "usb_hwid": "USB VID:PID=303A:1001 SER=E0:72:A1:D3:8D:34"},
        }
        for query_s3, reset_s3 in ((False, False), (True, False), (True, True)):
            with self.subTest(query_s3=query_s3, reset_s3=reset_s3):
                fake_streams = [FakeSerial(), FakeSerial()]
                stream_iter = iter(fake_streams)
                clock_value = [0.0]
                resets = []

                def fake_clock():
                    clock_value[0] += 1.0
                    return clock_value[0]

                result = tc_serial.observe(
                    {"c3": boards["c3"], "s3": boards["s3"],
                     "query_s3_status": query_s3, "s3_boot_reset": reset_s3},
                    serial_factory=lambda: next(stream_iter),
                    port_finder=lambda: [boards["c3"], boards["s3"]],
                    clock=fake_clock, sleep=lambda _seconds: None,
                    boot_reset=lambda stream: resets.append(stream))
                self.assertEqual(resets, [fake_streams[0]] if reset_s3 else [])
                self.assertEqual(fake_streams[0].writes,
                                 [b"FIXTURE_STATUS\n"] if query_s3 else [])
                self.assertEqual(fake_streams[1].writes, [b"GET_STATE\n"])
                self.assertEqual(result["s3_status_command_ready"], True)
                self.assertEqual(result["s3_status_command_sent"], query_s3)
                self.assertEqual(result["s3_config_receive_pending"], False)
                self.assertTrue(all(not stream.is_open for stream in fake_streams))
                self.assertTrue(any("HIL_AWAKE_TEST_ONLY" in line for line in result["c3"]))
                self.assertTrue(any("CloudSync=disabled" in line for line in result["s3"]))
                self.assertFalse(any("private" in line
                                     for role in ("c3", "s3")
                                     for line in result[role]))

        fake_streams = [FakeSerial(), FakeSerial()]
        stream_iter = iter(fake_streams)
        clock_value = [0.0]

        def fake_clock():
            clock_value[0] += 1.0
            return clock_value[0]

        result = tc_serial.observe(
            {"c3": boards["c3"], "s3": boards["s3"],
             "query_s3_status": False, "s3_boot_reset": False,
             "observation_seconds": 10},
            serial_factory=lambda: next(stream_iter),
            port_finder=lambda: [boards["c3"], boards["s3"]],
            clock=fake_clock, sleep=lambda _seconds: None,
            bootstrap_exchange=lambda _stream, **_kwargs: 7323)
        self.assertEqual(result["bootstrap_host_write_bytes"], 7323)
        self.assertGreater(result["bootstrap_exchange_ms"], 0)
        self.assertGreaterEqual(clock_value[0], 20)

        fake_streams = [FakeSerial(), FakeSerial()]
        stream_iter = iter(fake_streams)
        def after_reset(stream):
            self.assertEqual(stream.input_purges, 1)
            self.assertEqual(stream.buffer, b"")
        def exchange(stream, **kwargs):
            self.assertTrue(kwargs["require_boot"])
            self.assertTrue(kwargs["identity_check"]())
            return 7323
        tc_serial.observe(
            {"c3": boards["c3"], "s3": boards["s3"], "s3_boot_reset": True},
            serial_factory=lambda: next(stream_iter),
            port_finder=lambda: [boards["c3"], boards["s3"]],
            clock=fake_clock, sleep=lambda _seconds: None,
            boot_reset=after_reset, bootstrap_exchange=exchange)

    def test_observer_skips_status_command_during_secure_config_receive(self):
        """GS117-S3-STATUS-GATE-001: do not feed CLI text to GS40 envelope RX."""
        class FakeSerial:
            def __init__(self):
                self.port = ""
                self.timeout = None
                self.write_timeout = None
                self.dtr = True
                self.rts = True
                self.is_open = False
                self.buffer = bytearray()
                self.writes = []
            @property
            def in_waiting(self): return len(self.buffer)
            def open(self):
                self.is_open = True
                if self.port == "COM10":
                    self.buffer.extend(b"GS40T/1 CHALLENGE nonce=fixture-test\n")
            def write(self, data):
                self.writes.append(data)
                if data == b"GET_STATE\n":
                    self.buffer.extend(b"HIL_STATE role=c3\n")
                return len(data)
            def flush(self): pass
            def reset_input_buffer(self): self.buffer.clear()
            def read(self, count):
                value = bytes(self.buffer[:count]); del self.buffer[:count]; return value
            def close(self): self.is_open = False

        boards = {
            "c3": {"port": "COM4", "serial_number": "14:63:93:C5:D1:58",
                   "usb_hwid": "USB VID:PID=303A:1001 SER=14:63:93:C5:D1:58"},
            "s3": {"port": "COM10", "serial_number": "E0:72:A1:D3:8D:34",
                   "usb_hwid": "USB VID:PID=303A:1001 SER=E0:72:A1:D3:8D:34"},
        }
        streams = [FakeSerial(), FakeSerial()]
        iterator = iter(streams)
        tick = [0.0]
        def clock():
            tick[0] += 1.0
            return tick[0]

        result = tc_serial.observe(
            {"c3": boards["c3"], "s3": boards["s3"], "query_s3_status": True,
             "s3_boot_reset": False, "observation_seconds": 10},
            serial_factory=lambda: next(iterator),
            port_finder=lambda: [boards["c3"], boards["s3"]],
            clock=clock, sleep=lambda _seconds: None)
        self.assertTrue(result["s3_config_receive_pending"])
        self.assertFalse(result["s3_status_command_ready"])
        self.assertFalse(result["s3_status_command_sent"])
        self.assertEqual(streams[0].writes, [])
        self.assertEqual(streams[1].writes, [b"GET_STATE\n"])
        self.assertTrue(all(not stream.is_open for stream in streams))

    def test_serial_evidence_preserves_complete_profile_and_boot_failure(self):
        state = (
            "I (3395682) gs_node_runtime: HIL_STATE role=c3 session=99 retained=0 "
            "in_flight=0 sensing_live=0 runtime_live=0 pending_inject=0 heap=197292 "
            "min_heap=179820 ota_slot=ota_1 power_mode=HIL_AWAKE_TEST_ONLY "
            "hil_build=0 hil_control=1 physical_wake=0 wifi_psk=private"
        )
        class Stream:
            data = (state + "\nI (1) gs_hub_product: Starting product composition\n"
                    "I (2) app_init: App version: current\n"
                    "abort() was called at PC 0x40370000\n"
                    "assert failed: xQueueSemaphoreTake queue.c:1713 (pxQueue->uxItemSize == 0)\n"
                    "Guru Meditation Error: Core 0 panic'ed (Stack protection fault).\n"
                    "3fca0000: 0x12345678 raw_stack_bytes\n"
                    "HIL_FIXTURE_STATUS state=idle\n").encode()
            in_waiting = len(data)

            def read(self, count):
                return self.data[:count]

        lines = []
        self.assertEqual(tc_serial.collect(Stream(), "", lines), "")
        self.assertEqual(len(lines), 7)
        self.assertIn("physical_wake=0", lines[0])
        self.assertNotIn("private", "\n".join(lines))
        self.assertIn("abort()", lines[3])
        self.assertIn("assert failed:", lines[4])
        self.assertIn("Guru Meditation Error", lines[5])
        self.assertNotIn("raw_stack_bytes", "\n".join(lines))

    def test_status_query_rejects_non_boolean_before_open(self):
        for flag in ("query_s3_status", "s3_boot_reset"):
            with self.subTest(flag=flag), self.assertRaisesRegex(ValueError, "FLAG_MUST_BE_BOOLEAN"):
                tc_serial.observe({"c3": {}, "s3": {}, flag: "true"})

    def test_observation_duration_is_bounded_before_open(self):
        for duration in (True, 0, 9, 61, "10"):
            with self.subTest(duration=duration), self.assertRaisesRegex(ValueError, "SECONDS_OUT_OF_RANGE"):
                tc_serial.observe({"c3": {}, "s3": {}, "observation_seconds": duration})

    def test_bootstrap_carries_only_target_bound_encrypted_frame(self):
        nonce = b"n" * 32
        public = "04" + "ab" * 64

        class Stream:
            def __init__(self):
                self.data = bytearray((f"GS40T/1 CHALLENGE nonce={nonce.hex()} "
                                      f"public_key={public} max_envelope=24576\n").encode())
                self.writes = []

            @property
            def in_waiting(self):
                return len(self.data)

            def read(self, count):
                result = bytes(self.data[:count])
                del self.data[:count]
                return result

            def write(self, data):
                self.writes.append(data)
                return len(data)

            def flush(self):
                pass

        for timeout in (True, 4, 76, "70"):
            with self.subTest(timeout=timeout), self.assertRaisesRegex(
                    ValueError, "TC001_BOOTSTRAP_CHALLENGE_TIMEOUT_OUT_OF_RANGE"):
                tc_serial.bootstrap_config(
                    Stream(), incoming=io.StringIO(), outgoing=io.StringIO(),
                    challenge_timeout_seconds=timeout)

        envelope = b"G40E\x01" + nonce + b"encrypted-not-plaintext".ljust(480, b"x")
        frame = len(envelope).to_bytes(4, "big") + envelope
        for valid in (True, False):
            stream, output = Stream(), io.StringIO()
            supplied = frame if valid else frame[:9] + b"z" * 32 + frame[41:]
            response = io.StringIO(json.dumps({
                "encrypted_envelope_b64": base64.b64encode(supplied).decode()}) + "\n")
            if valid:
                sent = tc_serial.bootstrap_config(stream, incoming=response, outgoing=output)
                self.assertEqual(sent, len(frame))
                self.assertEqual(stream.writes, [frame])
                self.assertEqual(json.loads(output.getvalue())["nonce"], nonce.hex())
            else:
                with self.assertRaisesRegex(ValueError, "ENCRYPTED_RESPONSE_INVALID"):
                    tc_serial.bootstrap_config(stream, incoming=response, outgoing=output)
                self.assertEqual(stream.writes, [])
            self.assertNotIn("encrypted-not-plaintext", output.getvalue())
            self.assertNotIn(base64.b64encode(frame).decode(), output.getvalue())

    def test_bootstrap_fences_stale_challenge_on_new_running_image(self):
        """GS117-USB-BOOT-002: reject stale boot/image/port/deadline evidence."""
        old_nonce, nonce = b"o" * 32, b"n" * 32
        public = "04" + "ab" * 64
        def challenge(value):
            return (f"GS40T/1 CHALLENGE nonce={value.hex()} public_key={public} "
                    "max_envelope=24576\n")
        boot = ("ESP-ROM:esp32s3-20210327\n"
                "I (693) boot: Loaded app from partition at offset 0x20000\n"
                "I (1493) app_init: App version: d0e5f84\n"
                "I (1493) app_init: ELF file SHA256: b576c52f5...\n")
        expected = {"app_offset": "0x20000", "app_version": "d0e5f84",
                    "elf_sha256_prefix": "b576c52f5"}
        envelope = b"G40E\x01" + nonce + b"encrypted".ljust(480, b"x")
        frame = len(envelope).to_bytes(4, "big") + envelope
        response = json.dumps({"encrypted_envelope_b64": base64.b64encode(frame).decode()}) + "\n"

        class Stream:
            def __init__(self, text):
                self.data, self.writes = bytearray(text.encode()), []
            @property
            def in_waiting(self): return len(self.data)
            def read(self, count):
                value = bytes(self.data[:count]); del self.data[:count]
                return value
            def write(self, value): self.writes.append(value); return len(value)
            def flush(self): pass

        stream = Stream(challenge(old_nonce) + boot + challenge(nonce))
        evidence, output = {}, io.StringIO()
        tc_serial.bootstrap_config(stream, require_boot=True, expected_boot=expected,
                                   incoming=io.StringIO(response), outgoing=output,
                                   evidence=evidence)
        self.assertEqual(json.loads(output.getvalue())["nonce"], nonce.hex())
        self.assertEqual(stream.writes, [frame])
        self.assertTrue(evidence["post_reset_boot_verified"])
        self.assertEqual(evidence["ignored_pre_boot_challenges"], 1)
        self.assertEqual(evidence["boot"], expected)

        stream = Stream(boot + challenge(nonce))
        with self.assertRaisesRegex(ValueError, "USB_INTERFACE_MISMATCH"):
            tc_serial.bootstrap_config(stream, require_boot=True, expected_boot=expected,
                incoming=io.StringIO(response), outgoing=io.StringIO(), identity_check=lambda: False)
        self.assertEqual(stream.writes, [])

        for observed, error in ((challenge(old_nonce), "CHALLENGE_NOT_OBSERVED"),
                                (boot.replace("d0e5f84", "wrong") + challenge(nonce),
                                 "RUNNING_IMAGE_MISMATCH")):
            stream = Stream(observed)
            ticks = iter(range(100))
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                tc_serial.bootstrap_config(stream, require_boot=True, expected_boot=expected,
                    incoming=io.StringIO(response), outgoing=io.StringIO(), clock=lambda: next(ticks))
            self.assertEqual(stream.writes, [])

        stream = Stream(boot + challenge(nonce))
        class RestartResponse(io.StringIO):
            def readline(self, size):
                stream.data.extend(b"ESP-ROM:esp32s3-20210327\n")
                return super().readline(size)
        with self.assertRaisesRegex(ValueError, "TARGET_RESTARTED_OR_EXPIRED"):
            tc_serial.bootstrap_config(stream, require_boot=True, expected_boot=expected,
                incoming=RestartResponse(response), outgoing=io.StringIO())
        self.assertEqual(stream.writes, [])

        stream = Stream(boot + challenge(nonce))
        ticks = iter((0, 0, 0, 0, 26))
        with self.assertRaisesRegex(ValueError, "EXCEEDED_TARGET_BUDGET"):
            tc_serial.bootstrap_config(stream, require_boot=True, expected_boot=expected,
                incoming=io.StringIO(response), outgoing=io.StringIO(), clock=lambda: next(ticks))
        self.assertEqual(stream.writes, [])

    def test_exact_fixture_commissioning_keeps_qr_proof_private_and_requires_session(self):
        public, secret = "04" + "ab" * 64, "cd" * 32
        idle = ("HIL_STATE role=c3 retained=0 in_flight=0 sensing_live=0 runtime_live=0 "
                "pending_inject=0 power_mode=HIL_AWAKE_TEST_ONLY hil_build=0 hil_control=1 physical_wake=0")
        class Stream:
            def __init__(self, role, reject=False):
                self.role, self.reject = role, reject
                self.data, self.writes = bytearray(), []
            @property
            def in_waiting(self): return len(self.data)
            def read(self, count):
                out = bytes(self.data[:count]); del self.data[:count]; return out
            def flush(self): pass
            def write(self, value):
                self.writes.append(value)
                if value == b"GET_TEST_QR\n":
                    self.data.extend((f"HIL_TEST_QR profile=TEST_ONLY device_id=c3-146393c5d158 public_key={public}\n"
                                      f"HIL_TEST_CODE profile=TEST_ONLY device_id=c3-146393c5d158 installer_code={secret}\n").encode())
                elif value.startswith(b"COMMISSION_EXPECTED_NODE "):
                    self.data.extend(b"HIL_FIXTURE_OK request=exact_node\n" if not self.reject else b"HIL_FIXTURE_ERROR reason=rejected\n")
                elif value == b"FRESH_COMMISSION_GS117_TEST_FIXTURE\n":
                    self.data.extend(b"GS117_TEST_ONLY_FRESH_COMMISSIONING rejected reason=association_backup_failed\n"
                                     if self.reject else
                                     b"GS117_TEST_ONLY_FRESH_COMMISSIONING started prior_association_backed_up=1\n")
                elif value == b"GET_STATE\n":
                    self.data.extend(b"HIL_STATE role=c3 runtime_live=27 sensing_live=42\n")
                elif value == b"FIXTURE_STATUS\n":
                    self.data.extend(b"HIL_FIXTURE_STATUS state=authenticated_rejoin\n")
                return len(value)
        for reject in (False, True):
            c3, s3 = Stream("c3"), Stream("s3", reject)
            c3_lines, s3_lines = [idle], ["HIL_FIXTURE_STATUS state=idle commissioning_window_ms=120000"]
            ticks = [0.0]
            def clock(): ticks[0] += 0.05; return ticks[0]
            if reject:
                with self.assertRaisesRegex(ValueError, "REQUEST_NOT_ACCEPTED"):
                    tc_serial.commission_fixture(c3, s3, c3_lines, s3_lines, clock=clock, sleep=lambda _: None)
                self.assertNotIn(b"FRESH_COMMISSION_GS117_TEST_FIXTURE\n", c3.writes)
            else:
                result = tc_serial.commission_fixture(c3, s3, c3_lines, s3_lines, clock=clock, sleep=lambda _: None)
                self.assertEqual(result["status"], "PASS")
                self.assertEqual(result["node_public_key"], public)
                self.assertEqual(result["liveness"], {"runtime": 27, "sensing": 42})
                self.assertNotIn(secret, json.dumps([result, c3_lines, s3_lines]))
        c3, s3 = Stream("c3"), Stream("s3")
        with self.assertRaisesRegex(ValueError, "NOT_IDLE_OR_EMPTY"):
            tc_serial.commission_fixture(c3, s3, [idle.replace("retained=0", "retained=1")], [])
        self.assertEqual(c3.writes + s3.writes, [])
        c3, s3 = Stream("c3"), Stream("s3")
        with self.assertRaisesRegex(ValueError, "IDENTITY_KEY_CHANGED"):
            tc_serial.commission_fixture(c3, s3, [idle],
                ["HIL_FIXTURE_STATUS state=timed_out commissioning_window_ms=120000"],
                clock=clock, sleep=lambda _: None, expected_public_key="04" + "ef" * 64)
        self.assertEqual(s3.writes, [])
        c3, s3 = Stream("c3", True), Stream("s3")
        result = tc_serial.commission_fixture(c3, s3, [idle],
            ["HIL_FIXTURE_STATUS state=timed_out commissioning_window_ms=120000"],
            clock=clock, sleep=lambda _: None, expected_public_key=public)
        self.assertEqual(result["status"], "FAIL")
        self.assertNotIn(b"INJECT_MOTION\n", c3.writes)

    def test_bootstrap_missing_target_challenge_is_bounded_and_sends_nothing(self):
        class EmptyStream:
            in_waiting = 0

            def read(self, count):
                return b""

            def write(self, data):
                raise AssertionError("no frame may be sent without a target challenge")

        ticks = [0]

        def clock():
            ticks[0] += 1
            return ticks[0]

        with self.assertRaisesRegex(ValueError, "TARGET_CHALLENGE_NOT_OBSERVED"):
            tc_serial.bootstrap_config(EmptyStream(), clock=clock)

    def test_observer_refuses_wrong_physical_ports_before_open(self):
        opened = []
        config = {
            "c3": {"port": "COM4", "serial_number": "wrong",
                   "usb_hwid": "wrong"},
            "s3": {"port": "COM10", "serial_number": "E0:72:A1:D3:8D:34",
                   "usb_hwid": "s3"},
        }
        with self.assertRaisesRegex(ValueError, "USB_INTERFACE_MISMATCH"):
            tc_serial.observe(config, serial_factory=lambda: opened.append(True),
                              port_finder=lambda: [])
        self.assertEqual(opened, [])

    def test_duplicate_or_missing_s3_does_not_reach_backend(self):
        c3 = ["HIL_OK command=INJECT_MOTION", "PIR -> NodeRuntime session=12 seq=3"]
        report = self.report()
        self.execute(report, {"c3": c3, "s3": []}, baseline={"keys": [[12, 3]], "count": 1})
        self.assertEqual(report["stages"]["node_event_key"]["status"], "FAIL")
        report = self.report()
        self.execute(report, {"c3": c3, "s3": []})
        self.assertEqual(report["stages"]["s3_admission"]["status"], "FAIL")
        self.assertEqual(report["stages"]["backend_commit"]["status"], "NOT_VERIFIED")

    def test_wrong_or_missing_c3_power_mode_blocks_injection_result(self):
        c3 = ["HIL_OK command=INJECT_MOTION", "PIR -> NodeRuntime session=12 seq=3"]
        for mode in (None, "power_mode=SLEEP_ENABLED hil_build=0 hil_control=1 physical_wake=0"):
            with self.subTest(mode=mode):
                report = self.report()
                serial_lines = {"c3": list(c3), "s3": []}
                if mode:
                    serial_lines["c3"].insert(0, "HIL_STATE role=c3 " + mode)
                self.execute(report, serial_lines, mode_state=False)
                self.assertEqual(report["stages"]["c3_injection"]["status"], "BLOCKED")
                self.assertEqual(report["c3_power_mode"], "NOT_VERIFIED")

    def test_different_installed_apk_backend_blocks_before_serial(self):
        report = self.report()
        hardware = self.execute(report, {}, home_origin="https://wrong.local")
        hardware.assert_not_called()
        self.assertEqual(report["stages"]["environment"]["status"], "BLOCKED")

    def test_backend_unavailable_blocks_before_serial(self):
        report = self.report()
        controller = tc.Controller()
        controller.lock.acquire()
        with (patch.object(controller, "readiness", return_value={
                  "backend": {"POSTGRES_READY": "FAIL", "CAREGIVER_HTTPS_READY": "PASS"},
                  "caregiver_home": {"caregiver_home_ready": False}}),
              patch.object(tc, "powershell") as hardware,
              patch.object(controller, "save")):
            controller.execute(report)
        hardware.assert_not_called()
        self.assertEqual(report["stages"]["environment"]["status"], "BLOCKED")

    def test_missing_s3_interface_blocks_before_injection(self):
        report = self.report()
        self.execute(report, {}, ports_override=[{"port": "COM10", "usb_hwid": "c3", "serial_number": "c3s"}])
        self.assertEqual(report["stages"]["s3_identity"]["status"], "BLOCKED")
        self.assertEqual(report["stages"]["c3_injection"]["status"], "NOT_VERIFIED")

    def test_revoked_hub_or_node_enrollment_blocks_before_injection(self):
        report = self.report()
        hardware = self.execute(report, {}, baseline={"keys": [], "count": 0,
                                "authority_ready": False, "enrollment_generation": None})
        self.assertEqual(hardware.call_count, 1)  # read-only COM listing only
        self.assertEqual(report["stages"]["environment"]["status"], "BLOCKED")
        self.assertEqual(report["stages"]["c3_injection"]["status"], "NOT_VERIFIED")

    def test_wrong_caregiver_room_fails_after_exact_backend_commit(self):
        c3 = ["HIL_OK command=INJECT_MOTION", "PIR -> NodeRuntime session=12 seq=3"]
        s3 = ["Authenticated event logical=bedroom session=12 seq=3 sensor=PIR event=MOTION event_id=p15:test-c3-bedroomn7:bedrooms12q3 room=bedroom ack=0 send=ESP_OK"]
        report = self.report()
        self.execute(report, {"c3": c3, "s3": s3}, outcome={"durable_count": 1,
                     "caregiver_count": 1, "event_kind": "MOTION", "event_location": "kitchen",
                     "event_id": "evt-1", "caregiver_event_id": tc.event_key_text("test-c3-bedroom", 12, 3),
                     "committing_hub_id": "test-hub-a", "ownership_epoch": 1,
                     "node_enrollment_generation": 1})
        self.assertEqual(report["stages"]["backend_commit"]["status"], "PASS")
        self.assertEqual(report["stages"]["caregiver_api"]["status"], "FAIL")

    def test_wrong_hub_provenance_cannot_claim_cloudsync_delivery(self):
        c3 = ["HIL_OK command=INJECT_MOTION", "PIR -> NodeRuntime session=12 seq=3"]
        s3 = ["Authenticated event logical=bedroom session=12 seq=3 sensor=PIR event=MOTION event_id=p15:test-c3-bedroomn7:bedrooms12q3 room=bedroom ack=0 send=ESP_OK"]
        report = self.report()
        self.execute(report, {"c3": c3, "s3": s3}, outcome={"durable_count": 1,
                     "caregiver_count": 1, "event_kind": "MOTION", "event_location": "bedroom",
                     "event_id": "evt-1", "caregiver_event_id": tc.event_key_text("test-c3-bedroom", 12, 3),
                     "committing_hub_id": "test-hub-other", "ownership_epoch": 1,
                     "node_enrollment_generation": 1})
        self.assertEqual(report["stages"]["hub_cloudsync"]["status"], "FAIL")
        self.assertEqual(report["stages"]["backend_commit"]["status"], "PASS")

    def test_caregiver_projection_with_other_event_id_fails(self):
        c3 = ["HIL_OK command=INJECT_MOTION", "PIR -> NodeRuntime session=12 seq=3"]
        s3 = ["Authenticated event logical=bedroom session=12 seq=3 sensor=PIR event=MOTION event_id=p15:test-c3-bedroomn7:bedrooms12q3 room=bedroom ack=0 send=ESP_OK"]
        report = self.report()
        self.execute(report, {"c3": c3, "s3": s3}, outcome={"durable_count": 1,
                     "caregiver_count": 1, "event_kind": "MOTION", "event_location": "bedroom",
                     "event_id": "evt-1", "caregiver_event_id": "old-event",
                     "committing_hub_id": "test-hub-a", "ownership_epoch": 1,
                     "node_enrollment_generation": 1})
        self.assertEqual(report["stages"]["caregiver_api"]["status"], "FAIL")

    def test_loopback_console_rejects_cross_origin_and_missing_csrf(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), tc.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_address[1]}/api/run"
        try:
            with patch.object(tc.CONTROLLER, "start") as start:
                for origin, token in (("http://evil.example", tc.CONTROLLER.csrf),
                                      (tc.ORIGIN, "missing")):
                    request = urllib.request.Request(
                        url, data=b"{}", method="POST",
                        headers={"Host": "127.0.0.1:18791", "Origin": origin,
                                 "X-CSRF-Token": token, "Content-Type": "application/json"})
                    with self.assertRaises(urllib.error.HTTPError) as rejected:
                        urllib.request.urlopen(request, timeout=3)
                    self.assertEqual(rejected.exception.code, 403)
                    rejected.exception.close()
                start.assert_not_called()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_console_reports_single_run_lock_for_repeatable_retry(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), tc.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_address[1]}/api/status"
        try:
            with patch.object(tc.CONTROLLER, "readiness", return_value={"backend": {}, "caregiver_home": {}, "physical_boards": {}}):
                for locked, expected in ((True, True), (False, False)):
                    if locked:
                        tc.CONTROLLER.lock.acquire()
                    try:
                        request = urllib.request.Request(url, headers={"Host": "127.0.0.1:18791"})
                        with urllib.request.urlopen(request, timeout=3) as response:
                            self.assertEqual(json.load(response)["running"], expected)
                    finally:
                        if locked:
                            tc.CONTROLLER.lock.release()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def _write_read_only_observation_approval(self, path):
        approval = {
            "schema_version": 1,
            "test_id": "TC-001",
            "profile": "GS179_TEST_ONLY",
            "approval_ref": "owner-chat-approval-2026-10-26-read-only-observe",
            "approval_scope": (
                "C3 GET_STATE and S3 FIXTURE_STATUS only; one serial-open observation; "
                "reset risk accepted"),
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "serial_open_reset_risk_accepted": True,
            "reset_safe_uart_verified": False,
            "motion_injection_authorized": False,
            "c3": {"port": "COM4", "serial_number": "14:63:93:C5:D1:58"},
            "s3": {"port": "COM10", "serial_number": "E0:72:A1:D3:8D:34"},
        }
        path.write_text(json.dumps(approval))
        path.chmod(0o600)
        return approval

    def test_read_only_observation_requires_owner_only_non_reset_safe_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = Path(directory) / "approval.json"
            approval = self._write_read_only_observation_approval(receipt)
            controller = tc.Controller()
            for field, value in (("reset_safe_uart_verified", True),
                                 ("motion_injection_authorized", True)):
                approval[field] = value
                receipt.write_text(json.dumps(approval)); receipt.chmod(0o600)
                with patch.object(tc, "powershell") as hardware:
                    with self.assertRaisesRegex(ValueError, "scope_or_identity_mismatch"):
                        controller.observe_once(approval_path=receipt)
                    hardware.assert_not_called()
                self.assertFalse(controller.lock.locked())
                approval[field] = not value

            approval["c3"]["serial_number"] = "14:63:93:C5:D1:59"
            receipt.write_text(json.dumps(approval)); receipt.chmod(0o600)
            with patch.object(tc, "powershell") as hardware:
                with self.assertRaisesRegex(ValueError, "scope_or_identity_mismatch"):
                    controller.observe_once(approval_path=receipt)
                hardware.assert_not_called()
            self.assertFalse(controller.lock.locked())

            receipt.write_text(json.dumps(approval)); receipt.chmod(0o644)
            with patch.object(tc, "powershell") as hardware:
                with self.assertRaisesRegex(ValueError, "owner_only_regular_file"):
                    controller.observe_once(approval_path=receipt)
                hardware.assert_not_called()
            self.assertFalse(controller.lock.locked())

    def test_read_only_observation_identity_mismatch_does_not_consume_or_open_serial(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = Path(directory) / "approval.json"
            self._write_read_only_observation_approval(receipt)
            visible = [
                {"port": "COM4", "serial_number": "14:63:93:C5:D1:58",
                 "usb_hwid": "USB VID:PID=303A:1001 SER=14:63:93:C5:D1:58 LOCATION=1-1"},
                {"port": "COM10", "serial_number": "wrong",
                 "usb_hwid": "USB VID:PID=303A:1001 SER=E0:72:A1:D3:8D:34 LOCATION=1-2"},
            ]
            controller = tc.Controller()
            with patch.object(tc, "powershell", return_value=visible) as hardware:
                with self.assertRaisesRegex(ValueError, "VERIFIED_USB_INTERFACE_MISMATCH"):
                    controller.observe_once(approval_path=receipt)
            self.assertEqual([call.args[0] for call in hardware.call_args_list], ["List"])
            self.assertTrue(receipt.exists())
            self.assertFalse(controller.lock.locked())

    def test_one_use_observation_queries_exact_pair_once_and_never_injects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt = root / "approval.json"
            self._write_read_only_observation_approval(receipt)
            evidence = root / "observation.json"
            visible = [
                {"port": "COM4", "serial_number": "14:63:93:C5:D1:58",
                 "usb_hwid": "USB VID:PID=303A:1001 SER=14:63:93:C5:D1:58 LOCATION=1-1"},
                {"port": "COM10", "serial_number": "E0:72:A1:D3:8D:34",
                 "usb_hwid": "USB VID:PID=303A:1001 SER=E0:72:A1:D3:8D:34 LOCATION=1-2"},
            ]
            serial_result = {
                "c3": ["I (1) HIL_STATE role=c3 power_mode=HIL_AWAKE_TEST_ONLY "
                       "hil_build=0 hil_control=1 physical_wake=0 runtime_live=0 sensing_live=0",
                       "HIL_OK command=GET_STATE"],
                "s3": ["HIL_FIXTURE_STATUS state=authenticated_rejoin"],
            }
            controller = tc.Controller()
            with patch.object(tc, "powershell", side_effect=[visible, serial_result]) as hardware:
                report = controller.observe_once(approval_path=receipt, evidence_path=evidence)
            self.assertEqual(report["overall"], "PASS")
            self.assertEqual(report["tc001_acceptance"], "NOT_RUN")
            self.assertEqual(report["stages"]["c3_get_state"], "PASS")
            self.assertEqual(report["stages"]["s3_fixture_status"], "PASS")
            self.assertEqual(report["stages"]["cloudsync"], "NOT_VERIFIED")
            self.assertFalse(report["reset_safe_uart_verified"])
            self.assertTrue(report["serial_open_reset_risk_accepted"])
            self.assertEqual(report["motion_injection"], "NOT_AUTHORIZED")
            self.assertTrue(report["approval_receipt_consumed"])
            self.assertEqual(evidence.stat().st_mode & 0o777, 0o600)
            self.assertEqual([call.args[0] for call in hardware.call_args_list], ["List", "Observe"])
            observe_payload = hardware.call_args_list[1].args[1]
            self.assertEqual(observe_payload["c3"]["serial_number"], "14:63:93:C5:D1:58")
            self.assertEqual(observe_payload["s3"]["serial_number"], "E0:72:A1:D3:8D:34")
            consumed = list(root.glob("approval.consumed.*.json"))
            self.assertEqual(len(consumed), 1)
            with self.assertRaisesRegex(ValueError, "approval_missing_or_consumed"):
                controller.observe_once(approval_path=receipt, evidence_path=evidence)
            self.assertFalse(controller.lock.locked())
            self.assertEqual(len(hardware.call_args_list), 2)


if __name__ == "__main__":
    unittest.main()
