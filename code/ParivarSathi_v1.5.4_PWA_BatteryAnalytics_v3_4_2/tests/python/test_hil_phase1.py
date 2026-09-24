from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools.hil import phase1
from tools.hil.phase1 import (Campaign, IdentityProbeError, SOFTWARE_RESET_EVIDENCE,
                              cached_campaign_ports, fixture_usb_snapshot, is_usb_candidate,
                              normalize_rom_reset_class, parse_esptool_output,
                              probe_port, run_identity_probe, stable_fixture_usb_snapshot)
from tools.hil.core import (Device, FixtureLock, Results, SerialCapture,
                            assign_devices, write_report)


HUB_ESPTOOL_V54 = """\
esptool v5.4.0
Connected to ESP32 on /dev/ttyUSB0:
Chip type: ESP32-D0WD-V3 (revision v3.1)
Features: Wi-Fi, BT, Dual Core + LP Core, 240MHz
MAC: 5c:01:3b:be:b9:f8
Stub flasher running.
WARNING: ESP32 has no chip ID. Reading MAC address instead.
MAC: 5c:01:3b:be:b9:f8
Hard resetting via RTS pin...
"""


class FakeSerial:
    def __init__(self, *_args, **_kwargs):
        self.is_open = True; self.queue = []; self.writes = []
    def read(self, _size=1):
        if self.queue: return self.queue.pop(0)
        time.sleep(.01); return b""
    def write(self, data): self.writes.append(data); return len(data)
    def flush(self): pass
    def close(self): self.is_open = False


class RestartSerial(FakeSerial):
    def __init__(self, restart_chunks):
        super().__init__()
        self.restart_chunks = list(restart_chunks)

    def write(self, data):
        result = super().write(data)
        if data == b"SOFTWARE_RESTART\n":
            self.queue.extend(self.restart_chunks)
        return result


class BrokenSerial(FakeSerial):
    def read(self, _size=1): raise OSError("USB disappeared")


class RecordingTarget:
    def __init__(self, reset_line="rst:0xc (SW_CPU_RESET)"):
        self.calls = []; self.lines = []; self.reset_line = reset_line
    def cursor(self): return 0
    def send(self, command): self.calls.append(("send", command))
    def wait_for(self, pattern, timeout, start=0):
        self.calls.append(("wait", pattern, timeout, start)); return "NodeHealth schema=1 session=2"
    def wait_for_predicate(self, predicate, description, timeout, start=0):
        self.calls.append(("wait_predicate", description, timeout, start))
        if not predicate(self.reset_line):
            raise AssertionError(f"predicate rejected {self.reset_line}")
        return self.reset_line


class ProbeProcess:
    def __init__(self, result=None, alive=False): self.result, self.alive, self.pid = result, alive, 4242
    def poll(self): return None if self.alive else 0


class HilInfrastructureTest(unittest.TestCase):
    @staticmethod
    def wait_software_reset(capture, timeout, start):
        return capture.wait_for_predicate(
            lambda line: normalize_rom_reset_class(line) == SOFTWARE_RESET_EVIDENCE,
            "normalized SOFTWARE_RESET ROM evidence", timeout, start)

    def devices(self):
        return [Device("/dev/hub", "5c013bbeb9f8", "ESP32-D0WD-V3", 0x10c4, 0xea60, "H"),
                Device("/dev/c3", "146393c5d158", "ESP32-C3", 0x303a, 0x1001, "C")]

    def test_cached_campaign_ports_use_metadata_without_esptool(self):
        hub, c3 = self.devices()
        config = {"HIL_HUB_MAC": hub.mac, "HIL_C3_MAC": c3.mac}
        snapshot = {
            "hub": SimpleNamespace(device="/dev/ttyUSB7", vid=hub.vid, pid=hub.pid, serial_number="H"),
            "c3": SimpleNamespace(device="/dev/ttyACM8", vid=c3.vid, pid=c3.pid, serial_number="C"),
        }
        with patch.object(phase1, "stable_fixture_usb_snapshot", return_value=snapshot), \
             patch.object(phase1, "run_identity_probe", side_effect=AssertionError("intrusive probe")):
            self.assertEqual(cached_campaign_ports(config, {"hub": hub, "c3": c3}),
                             {"hub": "/dev/ttyUSB7", "c3": "/dev/ttyACM8"})

    def test_cached_campaign_ports_reject_changed_usb_identity(self):
        hub, c3 = self.devices()
        config = {"HIL_HUB_MAC": hub.mac, "HIL_C3_MAC": c3.mac}
        snapshot = {
            "hub": SimpleNamespace(device="/dev/ttyUSB7", vid=hub.vid, pid=hub.pid, serial_number="different"),
            "c3": SimpleNamespace(device="/dev/ttyACM8", vid=c3.vid, pid=c3.pid, serial_number="C"),
        }
        with patch.object(phase1, "stable_fixture_usb_snapshot", return_value=snapshot):
            with self.assertRaisesRegex(RuntimeError, "USB serial changed"):
                cached_campaign_ports(config, {"hub": hub, "c3": c3})

    def test_cached_campaign_ports_reverify_when_usb_serial_absent(self):
        hub, c3 = self.devices()
        hub = replace(hub, serial_number="")
        config = {"HIL_HUB_MAC": hub.mac, "HIL_C3_MAC": c3.mac}
        snapshot = {
            "hub": SimpleNamespace(device="/dev/ttyUSB7", vid=hub.vid, pid=hub.pid, serial_number=""),
            "c3": SimpleNamespace(device="/dev/ttyACM8", vid=c3.vid, pid=c3.pid, serial_number="C"),
        }
        with patch.object(phase1, "stable_fixture_usb_snapshot", return_value=snapshot), \
             patch.object(phase1, "_verified_runtime_port", return_value="/dev/ttyUSB7") as verify:
            self.assertEqual(cached_campaign_ports(config, {"hub": hub, "c3": c3})["hub"], "/dev/ttyUSB7")
            verify.assert_called_once_with(config, "hub")

    def test_preflight_rejects_stale_branch_commit_and_source_setup(self):
        config = {"HIL_HUB_MAC": "5c013bbeb9f8", "HIL_C3_MAC": "146393c5d158",
                  "HIL_EXPECTED_BRANCH": "expected-branch", "HIL_EXPECTED_COMMIT": "expected-commit",
                  "HIL_SOURCE_FINGERPRINT": "expected-source", "HIL_IDF_ACTIVATE": "/unused"}
        cases = [(["other-branch"], "expected-source", "branch differs"),
                 (["expected-branch", "other-commit"], "expected-source", "commit differs"),
                 (["expected-branch", "expected-commit"], "other-source", "source changed")]
        for git_results, source, message in cases:
            with self.subTest(message=message), \
                 patch.object(phase1, "git", side_effect=git_results), \
                 patch.object(phase1, "source_fingerprint", return_value=source), \
                 patch.object(phase1, "discover", side_effect=AssertionError("stale setup reached hardware")):
                with self.assertRaisesRegex(RuntimeError, message):
                    phase1.preflight(config, quiet=True)

    def test_no_devices_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "exactly one hub"):
            assign_devices([], "5c013bbeb9f8", "146393c5d158")

    def test_wrong_identity_fails_closed(self):
        with self.assertRaises(RuntimeError):
            assign_devices(self.devices(), "000000000001", "146393c5d158")

    def test_esptool_v54_hub_duplicate_mac_and_chip_type(self):
        chip, mac = parse_esptool_output(HUB_ESPTOOL_V54)
        self.assertEqual(chip, "ESP32-D0WD-V3")
        self.assertEqual(mac, "5c013bbeb9f8")

    def test_mac_normalization_case_and_colons(self):
        chip, mac = parse_esptool_output(
            "Chip type: ESP32-C3 (revision v0.4)\nMAC: 14:63:93:C5:D1:58\nMAC: 14:63:93:C5:D1:58\n")
        self.assertEqual(chip, "ESP32-C3")
        self.assertEqual(mac, "146393c5d158")

    def test_cp2102_usb_serial_is_not_device_identity(self):
        chip, mac = parse_esptool_output(HUB_ESPTOOL_V54.replace("5c:01:3b:be:b9:f8", "5C:01:3B:BE:B9:F8"))
        self.assertEqual(chip, "ESP32-D0WD-V3")
        self.assertNotEqual("0001", mac)

    def test_non_usb_tty_is_filtered_before_esptool(self):
        self.assertFalse(is_usb_candidate(SimpleNamespace(device="/dev/ttyS0", vid=0, pid=0)))
        self.assertFalse(is_usb_candidate(SimpleNamespace(device="/dev/ttyS7", vid=None, pid=None)))
        self.assertTrue(is_usb_candidate(SimpleNamespace(device="/dev/ttyUSB9", vid=None, pid=None)))
        self.assertTrue(is_usb_candidate(SimpleNamespace(device="/dev/ttyUSB0", vid=0x10C4,
                                                         pid=0xEA60)))
        self.assertTrue(is_usb_candidate(SimpleNamespace(device="/dev/ttyACM0", vid=0x303A,
                                                         pid=0x1001)))

    def test_rom_reset_reasons_normalize_by_supported_soc(self):
        self.assertEqual(normalize_rom_reset_class("rst:0xc (SW_CPU_RESET),boot:0x13"),
                         SOFTWARE_RESET_EVIDENCE)
        self.assertEqual(normalize_rom_reset_class("rst:0xc (RTC_SW_CPU_RST)"),
                         SOFTWARE_RESET_EVIDENCE)

    def test_rom_reset_normalizer_rejects_wrong_or_malformed_reasons(self):
        for line in (
                "rst:0x1 (POWERON_RESET)",
                "rst:0x8 (TG1WDT_SYS_RESET)",
                "rst:0x10 (RTCWDT_RTC_RESET)",
                "rst:0x3 (EXT_CPU_RESET)",
                "rst:0xc (PANIC_RESET)",
                "boot:0x13 (SPI_FAST_FLASH_BOOT)"):
            self.assertEqual(normalize_rom_reset_class(line),
                             "OTHER_RESET" if "rst:" in line else None)

    def test_metadata_stability_precedes_identity_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            hub, c3 = Path(tmp)/"ttyUSB0", Path(tmp)/"ttyACM0"
            hub.touch(); c3.touch()
            ports = [SimpleNamespace(device=str(hub), vid=0x10c4, pid=0xea60, serial_number="h"),
                     SimpleNamespace(device=str(c3), vid=0x303a, pid=0x1001, serial_number="c")]
            with patch("tools.hil.phase1.list_ports.comports", return_value=ports):
                snapshot = stable_fixture_usb_snapshot({}, interval=0, sleeper=lambda _: None)
            self.assertEqual(snapshot["hub"].device, str(hub))
            self.assertEqual(snapshot["c3"].device, str(c3))

    def test_identity_probe_normal_result_is_authoritative(self):
        with tempfile.TemporaryDirectory() as tmp:
            port = Path(tmp)/"ttyACM0"; port.touch()
            def launch(command, **_kwargs):
                result = Path(command[command.index("--result") + 1])
                result.write_text(json.dumps({"returncode": 0, "stdout": HUB_ESPTOOL_V54}))
                return ProbeProcess()
            result = run_identity_probe({}, str(port), timeout=.2, popen=launch, sleeper=lambda _: None)
            self.assertEqual(result.returncode, 0)
            self.assertIn("ESP32-D0WD-V3", result.stdout)

    def test_identity_probe_usb_disappearance_is_classified(self):
        with tempfile.TemporaryDirectory() as tmp:
            port = Path(tmp)/"ttyACM0"; port.touch(); clock = [0.0]
            def sleep(_):
                clock[0] += .1
                if port.exists(): port.unlink()
            def launch(command, **_kwargs):
                Path(command[command.index("--pid") + 1]).write_text("4242")
                return ProbeProcess(alive=True)
            with patch("tools.hil.phase1.os.kill"):
                with self.assertRaisesRegex(IdentityProbeError, "IDENTITY_PROBE_USB_DISAPPEARED"):
                    run_identity_probe({}, str(port), timeout=1, popen=launch,
                                       monotonic=lambda: clock[0], sleeper=sleep)
            phase1._ACTIVE_IDENTITY_PROBES.clear()

    def test_d_state_like_identity_probe_timeout_does_not_block_supervisor(self):
        with tempfile.TemporaryDirectory() as tmp:
            port = Path(tmp)/"ttyACM0"; port.touch(); clock = [0.0]
            def launch(command, **_kwargs):
                Path(command[command.index("--pid") + 1]).write_text("4242")
                return ProbeProcess(alive=True)
            with patch("tools.hil.phase1.os.kill") as kill:
                with self.assertRaisesRegex(IdentityProbeError, "IDENTITY_PROBE_TIMEOUT"):
                    run_identity_probe({}, str(port), timeout=.3,
                                       popen=launch,
                                       monotonic=lambda: clock[0],
                                       sleeper=lambda seconds: clock.__setitem__(0, clock[0] + seconds))
            self.assertGreaterEqual(clock[0], .3)
            kill.assert_called_once()
            # A second cycle refuses to spawn a second orphan while the first
            # D-state-like worker is still active.
            with self.assertRaisesRegex(IdentityProbeError, "prior probe still active"):
                run_identity_probe({}, str(port), timeout=.1,
                                   popen=launch, sleeper=lambda _: None)
            phase1._ACTIVE_IDENTITY_PROBES.clear()

    @patch("tools.hil.phase1.run_identity_probe")
    def test_probe_classifies_real_cp2102_hub_by_chip_mac(self, run_identity_probe):
        import subprocess
        run_identity_probe.return_value = subprocess.CompletedProcess(
            ["python", "-m", "esptool"], 0, HUB_ESPTOOL_V54)
        info = SimpleNamespace(device="/dev/ttyUSB0", vid=0x10C4, pid=0xEA60,
                               serial_number="0001", location="3-1")
        record = probe_port(info, {"HIL_HUB_MAC": "5C:01:3B:BE:B9:F8",
                                   "HIL_C3_MAC": "14:63:93:C5:D1:58"})
        self.assertEqual(record.classification, "Hub")
        self.assertEqual(record.device.mac, "5c013bbeb9f8")
        self.assertEqual(record.device.chip, "ESP32-D0WD-V3")
        self.assertEqual(record.usb_serial, "0001")
        run_identity_probe.assert_called_once()
        self.assertEqual(run_identity_probe.call_args.args[1], "/dev/ttyUSB0")

    @patch("tools.hil.phase1.run_identity_probe")
    def test_probe_failure_keeps_actionable_diagnostic(self, run_identity_probe):
        import subprocess
        run_identity_probe.return_value = subprocess.CompletedProcess(
            ["python", "-m", "esptool"], 2, "Could not open /dev/ttyUSB0: Permission denied\n")
        info = SimpleNamespace(device="/dev/ttyUSB0", vid=0x10C4, pid=0xEA60,
                               serial_number="0001", location="3-1")
        record = probe_port(info, {"HIL_HUB_MAC": "5c013bbeb9f8",
                                   "HIL_C3_MAC": "146393c5d158"})
        diagnostic = record.diagnostic()
        self.assertIn("esptool probe=FAIL", diagnostic)
        self.assertIn("exit=2", diagnostic)
        self.assertIn("Permission denied", diagnostic)

    def test_malformed_or_no_mac_output_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "no six-octet MAC"):
            parse_esptool_output("Chip type: ESP32-D0WD-V3 (revision v3.1)\n")
        with self.assertRaisesRegex(ValueError, "no Chip type"):
            parse_esptool_output("MAC: 5c:01:3b:be:b9:f8\n")

    def test_conflicting_duplicate_macs_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "conflicting MACs"):
            parse_esptool_output("Chip type: ESP32\nMAC: 5c:01:3b:be:b9:f8\nMAC: 14:63:93:c5:d1:58\n")

    def test_ambiguous_device_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "found 2"):
            assign_devices(self.devices() + [self.devices()[0]], "5c013bbeb9f8", "146393c5d158")

    def test_board_type_mismatch_fails(self):
        rows = [Device("h", "5c013bbeb9f8", "ESP32-C3"), Device("c", "146393c5d158", "ESP32")]
        with self.assertRaisesRegex(RuntimeError, "board type mismatch"):
            assign_devices(rows, "5c013bbeb9f8", "146393c5d158")

    def test_port_unavailable_is_propagated(self):
        with tempfile.TemporaryDirectory() as tmp:
            def unavailable(*_a, **_k): raise PermissionError("busy")
            capture = SerialCapture("hub", "bad", Path(tmp)/"x.log", unavailable)
            with self.assertRaises(PermissionError): capture.start()

    def test_serial_capture_command_log_wait_and_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeSerial(); capture = SerialCapture("c3", "fake", Path(tmp)/"c3.log", lambda *_a, **_k: fake)
            capture.start(); fake.queue.append(b"HIL_OK command=GET_STATE\r\n")
            capture.wait_for("HIL_OK", 1); capture.send("GET_STATE"); capture.close()
            self.assertEqual(fake.writes, [b"GET_STATE\n"]); self.assertFalse(fake.is_open)
            self.assertIn("[c3] HIL_OK", (Path(tmp)/"c3.log").read_text())

    def test_serial_capture_reassembles_fragmented_uart_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeSerial()
            capture = SerialCapture("hub", "fake", Path(tmp)/"hub.log", lambda *_a, **_k: fake)
            capture.start()
            fake.queue.extend([b"HIL_OK command=SOFTWARE_RES", b"TART reset_class=SOFTWARE_RESET\r\n"])
            line = capture.wait_for(r"SOFTWARE_RESTART reset_class=SOFTWARE_RESET", 1)
            capture.close()
            self.assertIn("SOFTWARE_RESTART", line)
            self.assertEqual(len(capture.lines), 1)

    def test_hub_restart_accepts_pristine_ack_and_fresh_rom_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = RestartSerial([
                b"HIL_OK command=SOFTWARE_RESTART reset_class=SOFTWARE_RESET\r\n",
                b"rst:0xc (SW_CPU_RESET),boot:0x13 (SPI_FAST_FLASH_BOOT)\r\n",
                b"HIL_READY role=hub protocol=1 version=test\r\n",
            ])
            capture = SerialCapture("hub", "fake", Path(tmp)/"hub.log", lambda *_a, **_k: fake)
            capture.start()
            Campaign("regression", {}, {}, {"image_version": "test"}, Path(tmp)).reboot(capture, "hub", 1)
            capture.close()

    def test_restart_accepts_truncated_ack_when_fresh_rom_reset_and_ready_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = RestartSerial([
                b"HIL_OK command=SOFTWARE_RES\r\n",
                b"TART HILet_class=SOFTWARE_RESET\r\n",
                b"rst:0xc (SW_CPU_RESET),boot:0x13 (SPI_FAST_FLASH_BOOT)\r\n",
                b"HIL_READY role=hub protocol=1 version=test\r\n",
            ])
            capture = SerialCapture("hub", "fake", Path(tmp)/"hub.log", lambda *_a, **_k: fake)
            capture.start()
            Campaign("regression", {}, {}, {"image_version": "test"}, Path(tmp)).reboot(capture, "hub", 1)
            capture.close()

    def test_restart_does_not_require_pre_reset_marker_when_rom_reset_is_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = RestartSerial([
                b"rst:0xc (SW_CPU_RESET),boot:0x13 (SPI_FAST_FLASH_BOOT)\r\n",
                b"HIL_READY role=hub protocol=1 version=test\r\n",
            ])
            capture = SerialCapture("hub", "fake", Path(tmp)/"hub.log", lambda *_a, **_k: fake)
            capture.start()
            Campaign("regression", {}, {}, {"image_version": "test"}, Path(tmp)).reboot(capture, "hub", 1)
            capture.close()

    def test_c3_restart_accepts_rtc_software_reset_and_sensing_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = RestartSerial([
                b"HIL_OK command=SOFTWARE_RESTART reset_class=SOFTWARE_RESET\r\n",
                b"rst:0xc (RTC_SW_CPU_RST)\r\n",
                b"HIL_READY role=c3 protocol=1 version=test\r\n",
                b"PIR ready on GPIO\r\n",
            ])
            capture = SerialCapture("c3", "fake", Path(tmp)/"c3.log", lambda *_a, **_k: fake)
            capture.start()
            Campaign("regression", {}, {}, {"image_version": "test"}, Path(tmp)).reboot(capture, "c3", 1)
            capture.close()

    def test_stale_reset_and_ready_lines_before_cursor_do_not_prove_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeSerial()
            capture = SerialCapture("hub", "fake", Path(tmp)/"hub.log", lambda *_a, **_k: fake)
            capture.start()
            capture._record_line(b"rst:0xc (SW_CPU_RESET),boot:0x13")
            capture._record_line(b"rst:0xc (RTC_SW_CPU_RST)")
            capture._record_line(b"HIL_READY role=hub protocol=1 version=test")
            cursor = capture.cursor()
            with self.assertRaises(TimeoutError):
                self.wait_software_reset(capture, .05, cursor)
            with self.assertRaises(TimeoutError):
                capture.wait_for(r"HIL_READY role=hub protocol=1 version=test", .05, cursor)
            capture.close()

    def test_fresh_ready_without_reset_evidence_does_not_prove_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeSerial()
            capture = SerialCapture("hub", "fake", Path(tmp)/"hub.log", lambda *_a, **_k: fake)
            capture.start(); cursor = capture.cursor()
            fake.queue.append(b"HIL_READY role=hub protocol=1 version=test\r\n")
            with self.assertRaises(TimeoutError):
                self.wait_software_reset(capture, .1, cursor)
            capture.close()

    def test_pre_reset_marker_alone_is_not_authoritative_restart_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeSerial()
            capture = SerialCapture("hub", "fake", Path(tmp)/"hub.log", lambda *_a, **_k: fake)
            capture.start(); cursor = capture.cursor()
            fake.queue.extend([
                b"HIL_OK command=SOFTWARE_RESTART reset_class=SOFTWARE_RESET\r\n",
                b"HIL_READY role=hub protocol=1 version=test\r\n",
            ])
            with self.assertRaises(TimeoutError):
                self.wait_software_reset(capture, .1, cursor)
            capture.close()

    def test_reset_evidence_without_fresh_ready_does_not_prove_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeSerial()
            capture = SerialCapture("hub", "fake", Path(tmp)/"hub.log", lambda *_a, **_k: fake)
            capture.start(); cursor = capture.cursor()
            fake.queue.append(b"rst:0xc (SW_CPU_RESET)\r\n")
            self.wait_software_reset(capture, .1, cursor)
            with self.assertRaises(TimeoutError):
                capture.wait_for(r"HIL_READY role=hub protocol=1 version=test", .1, cursor)
            capture.close()

    def test_wrong_reset_reason_does_not_satisfy_software_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeSerial(); fake.queue.append(b"rst:0x3 (POWERON_RESET)\r\n")
            capture = SerialCapture("hub", "fake", Path(tmp)/"hub.log", lambda *_a, **_k: fake)
            capture.start(); cursor = capture.cursor()
            with self.assertRaises(TimeoutError):
                self.wait_software_reset(capture, .1, cursor)
            capture.close()

    def test_restart_requires_expected_firmware_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = RestartSerial([
                b"rst:0xc (SW_CPU_RESET)\r\n",
                b"HIL_READY role=hub protocol=1 version=unexpected\r\n",
            ])
            capture = SerialCapture("hub", "fake", Path(tmp)/"hub.log", lambda *_a, **_k: fake)
            capture.start()
            with self.assertRaises(TimeoutError):
                Campaign("regression", {}, {}, {"image_version": "test"}, Path(tmp)).reboot(capture, "hub", .1)
            capture.close()

    def test_boot_timeout_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            capture = SerialCapture("c3", "fake", Path(tmp)/"c3.log", lambda *_a, **_k: FakeSerial())
            capture.start(); started = time.monotonic()
            with self.assertRaises(TimeoutError): capture.wait_for("never", .05)
            self.assertLess(time.monotonic()-started, .5); capture.close()

    def test_serial_reconnect_uses_resolver_and_continues(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = FakeSerial(); good.queue.append(b"HIL_READY role=c3\n")
            calls = []
            def factory(port, *_a, **_k):
                calls.append(port)
                return BrokenSerial() if len(calls) == 1 else good
            capture = SerialCapture("c3", "old", Path(tmp)/"c3.log", factory,
                                    port_resolver=lambda: "new")
            capture.start(); capture.wait_for("HIL_READY", 1); capture.close()
            self.assertEqual(calls[:2], ["old", "new"])

    def test_serial_reconnect_reopens_same_tty_after_native_usb_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            failed, good = BrokenSerial(), FakeSerial()
            good.queue.append(b"HIL_READY role=c3\n")
            calls = []
            def factory(port, *_a, **_k):
                calls.append(port)
                return failed if len(calls) == 1 else good
            capture = SerialCapture("c3", "/dev/ttyACM0", Path(tmp)/"c3.log", factory,
                                    port_resolver=lambda: "/dev/ttyACM0")
            capture.start(); capture.wait_for("HIL_READY", 1); capture.close()
            self.assertEqual(calls[:2], ["/dev/ttyACM0", "/dev/ttyACM0"])
            self.assertFalse(failed.is_open)

    def test_serial_reconnect_closes_stale_fd_before_changed_tty_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            failed, good = BrokenSerial(), FakeSerial()
            good.queue.append(b"HIL_READY role=c3\n")
            opened = []
            def factory(port, *_a, **_k):
                opened.append(port)
                return failed if len(opened) == 1 else good
            capture = SerialCapture("c3", "/dev/ttyACM0", Path(tmp)/"c3.log", factory,
                                    port_resolver=lambda: "/dev/ttyACM1")
            capture.start(); capture.wait_for("HIL_READY", 1); capture.close()
            self.assertEqual(opened[:2], ["/dev/ttyACM0", "/dev/ttyACM1"])
            self.assertFalse(failed.is_open)
            self.assertIn("SERIAL_RECONNECTED port=/dev/ttyACM1", (Path(tmp)/"c3.log").read_text())

    def test_c3_reboot_waits_for_real_sensing_boundary_not_just_hil_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign = Campaign("regression", {}, {}, {"image_version": "test"}, Path(tmp))
            target = RecordingTarget()
            campaign.reboot(target, "c3")
            waits = [call[1] for call in target.calls if call[0] in ("wait", "wait_predicate")]
            self.assertIn("normalized SOFTWARE_RESET ROM evidence", waits)
            self.assertIn("PIR ready on GPIO", waits[-1])
            self.assertEqual(target.calls[0], ("send", "SOFTWARE_RESTART"))

    def test_hub_reboot_does_not_require_c3_sensing_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign = Campaign("regression", {}, {}, {"image_version": "test"}, Path(tmp))
            target = RecordingTarget()
            campaign.reboot(target, "hub")
            waits = [call[1] for call in target.calls if call[0] in ("wait", "wait_predicate")]
            self.assertIn("normalized SOFTWARE_RESET ROM evidence", waits)
            self.assertNotIn("PIR ready on GPIO", waits)

    def test_both_restart_requires_fresh_reset_and_versioned_ready_for_each_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign = Campaign("regression", {}, {}, {"image_version": "test"}, Path(tmp))
            campaign.hub = RecordingTarget("rst:0xc (SW_CPU_RESET)")
            campaign.c3 = RecordingTarget("rst:0xc (RTC_SW_CPU_RST)")
            campaign.reboot = lambda *_args, **_kwargs: None
            campaign.motion = lambda: None
            self.assertTrue(campaign.both_restart())
            for target, role in ((campaign.hub, "hub"), (campaign.c3, "c3")):
                waits = [call[1] for call in target.calls if call[0] in ("wait", "wait_predicate")]
                self.assertIn("normalized SOFTWARE_RESET ROM evidence", waits)
                self.assertTrue(any(f"HIL_READY role={role} protocol=1 version=test" in pattern
                                    for pattern in waits))

    def test_phase2_fota_requires_fresh_transfer_reset_slot_and_sensing(self):
        class FotaTarget(RecordingTarget):
            def __init__(self, role):
                super().__init__("rst:0xc (RTC_SW_CPU_RST)" if role == "c3" else
                                 "rst:0xc (SW_CPU_RESET)")
                self.role = role
                self.state_reads = 0
                self.cursor_value = 0
            def cursor(self):
                self.cursor_value += 1
                return self.cursor_value
            def wait_for(self, pattern, timeout, start=0):
                super().wait_for(pattern, timeout, start)
                if self.role == "c3" and "HIL_STATE role=c3" in pattern:
                    self.state_reads += 1
                    return ("HIL_STATE role=c3 retained=0 in_flight=0 "
                            f"ota_slot=ota_{0 if self.state_reads == 1 else 1}")
                return "matched"
        with tempfile.TemporaryDirectory() as tmp:
            campaign = Campaign("fota", {}, {}, {"image_version": "test"}, Path(tmp))
            campaign.hub, campaign.c3 = FotaTarget("hub"), FotaTarget("c3")
            motions = []
            campaign.motion = lambda timeout=20: motions.append(timeout)
            campaign._check_resets_resources = lambda: None
            self.assertTrue(campaign.fota_same_image())
            self.assertEqual(motions, [30])
            self.assertIn(("send", "START_C3_FOTA"), campaign.hub.calls)
            self.assertTrue(any(call[0] == "wait_predicate" and
                                "post-FOTA normalized SOFTWARE_RESET" in call[1]
                                for call in campaign.c3.calls))
            self.assertTrue(any(call[0] == "wait" and "PIR ready on GPIO" in call[1]
                                for call in campaign.c3.calls))
            self.assertEqual([r["status"] for r in campaign.results.rows], ["PASS"] * 3)

    def test_phase2_fota_rejects_unchanged_ota_slot(self):
        class SameSlotTarget(RecordingTarget):
            def wait_for(self, pattern, timeout, start=0):
                super().wait_for(pattern, timeout, start)
                if "HIL_STATE role=c3" in pattern:
                    return "HIL_STATE role=c3 retained=0 in_flight=0 ota_slot=ota_0"
                return "matched"
        with tempfile.TemporaryDirectory() as tmp:
            campaign = Campaign("fota", {}, {}, {"image_version": "test"}, Path(tmp))
            campaign.hub = RecordingTarget()
            campaign.c3 = SameSlotTarget("rst:0xc (RTC_SW_CPU_RST)")
            self.assertFalse(campaign.fota_same_image())
            self.assertIn("slot did not change",
                          (Path(tmp)/"failures"/"P2-FOTA-SAME-001.txt").read_text())

    def test_recovery_sensing_timeout_has_specific_evidence_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign = Campaign("regression", {}, {}, {"image_version": "test"}, Path(tmp))
            campaign.hub = RecordingTarget(); campaign.c3 = RecordingTarget()
            def fail_reboot(_target, role, timeout=25):
                if role == "c3": raise TimeoutError("c3: timeout waiting for PIR ready on GPIO")
            campaign.reboot = fail_reboot
            self.assertFalse(campaign.recover())
            evidence = (Path(tmp)/"failures"/"recovery.txt").read_text()
            self.assertIn("RECOVERY_FAILED_C3_SENSING_READY_TIMEOUT", evidence)

    def test_recovery_waits_for_post_restart_health_then_motion(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign = Campaign("regression", {}, {}, {"image_version": "test"}, Path(tmp))
            campaign.hub = RecordingTarget(); campaign.c3 = RecordingTarget()
            motion = []
            campaign.motion = lambda: motion.append("motion")
            self.assertTrue(campaign.recover())
            self.assertIn(("send", "GET_HEALTH"), campaign.c3.calls)
            self.assertTrue(any(call[0] == "wait" and "NodeHealth schema=" in call[1]
                                for call in campaign.hub.calls))
            self.assertEqual(motion, ["motion"])

    def test_bounded_c3_tty_recovery_failure_has_specific_code(self):
        error = RuntimeError("bounded c3 USB reattachment failed after 15s: missing")
        self.assertEqual(Campaign._recovery_failure_code(error),
                         "RECOVERY_FAILED_C3_TTY_TIMEOUT")

    def test_exclusive_lock_and_exception_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"fixture.lock"
            with FixtureLock(path):
                with self.assertRaisesRegex(RuntimeError, "already locked"):
                    with FixtureLock(path): pass
            with FixtureLock(path): pass

    def test_report_generation_and_failure_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            results = Results(); results.add("OK", "PASS", "yes"); results.add("BAD", "FAIL", "no")
            payload = write_report(Path(tmp), {"commit": "abc"}, results)
            self.assertEqual(payload["overall"], "FAIL")
            self.assertEqual(json.loads((Path(tmp)/"summary.json").read_text())["counts"]["FAIL"], 1)

    def test_extra_fixture_does_not_fail_configured_campaign(self):
        results = Results(); results.add("HIL-SMOKE-001", "PASS", "ok")
        results.add("PHYSICAL-PIR", "BLOCKED_EXTRA_FIXTURE", "optical fixture")
        self.assertTrue(results.mandatory_pass())

    def test_production_hil_control_isolation_is_structural(self):
        root = Path(__file__).resolve().parents[2]
        for role in ("node/target/esp32c3", "hub/target/esp32"):
            cmake = (root/f"firmware/{role}/idf/main/CMakeLists.txt").read_text()
            self.assertIn("if(GS_HIL_BUILD)", cmake)
            self.assertIn('list(APPEND', cmake)
        for role in ("node/target/esp32c3", "hub/target/esp32"):
            app = (root/f"firmware/{role}/idf/main/app_main.cpp").read_text()
            self.assertIn("#if GS_HIL_BUILD", app)

    def test_hil_control_accumulates_commands_until_newline(self):
        root = Path(__file__).resolve().parents[2]
        for role in ("node/target/esp32c3", "hub/target/esp32"):
            source = (root/f"firmware/{role}/idf/main/hil_control.cpp").read_text()
            self.assertIn("std::fgetc(stdin)", source)
            self.assertIn("if (ch == '\\n')", source)
            self.assertNotIn("std::fgets(command", source)

    def test_windows_usb_helper_is_identity_and_fail_closed(self):
        repo = Path(__file__).resolve().parents[4]
        source = (repo / "tools/hil/ensure-usb-attached.ps1").read_text()
        for token in ("usbipd.exe", "--parsable", "10c4", "ea60", "303a", "1001",
                      "Select-ExpectedUsbDevices", "Ensure-UsbAttached", "Invoke-SelfTest"):
            self.assertIn(token, source)
        self.assertNotIn("COM3", source)
        self.assertNotIn("COM4", source)
        self.assertNotIn("3-1", source)
        self.assertNotIn("3-3", source)
        self.assertIn("ambiguous", source)
        self.assertIn("$process.ExitCode", source)
        production = source[:source.index("function Invoke-SelfTest")]
        self.assertNotIn("add_OutputDataReceived", production)
        self.assertNotIn("BeginOutputReadLine", production)
        for forbidden in ("wsl.exe", "make", "hil-setup", "hil-regression"):
            self.assertNotIn(forbidden, production)

    def test_wsl_supervisor_qualify_sequence_is_ordered_and_fail_fast(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "tools/hil/qualify.py").read_text()
        stages = ["validation-fast", "release-gate-final", "hil-setup",
                  "hil-preflight", "hil-smoke", "hil-regression"]
        positions = [source.index(f'"{stage}"') for stage in stages]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('"usb-fixture"', source)
        self.assertIn('self.statuses[name] = "BLOCKED"', source)
        self.assertIn("print_summary", source)

    def test_windows_supervisor_is_ascii_safe_for_powershell_5_1(self):
        repo = Path(__file__).resolve().parents[4]
        script = repo / "tools/hil/ensure-usb-attached.ps1"
        raw = script.read_bytes()
        self.assertTrue(all(byte < 128 for byte in raw),
                        "Windows PowerShell 5.1 supervisor must remain ASCII-only")
        text = raw.decode("ascii")
        self.assertNotIn("—", text)
        self.assertNotIn("–", text)

    def test_wsl_supervisor_has_no_windows_repo_path_conversion(self):
        repo = Path(__file__).resolve().parents[4]
        source = (repo / "code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tools/hil/usb_attach.py").read_text()
        self.assertIn("[Console]::In.ReadToEnd()", source)
        self.assertIn("input=helper.read_text", source)
        for forbidden in ("wslpath", "wsl.localhost", "Microsoft.PowerShell.Core"):
            self.assertNotIn(forbidden, source)

    def test_usbipd_legacy_fallback_and_connected_table_contract(self):
        repo = Path(__file__).resolve().parents[4]
        source = (repo / "tools/hil/ensure-usb-attached.ps1").read_text()
        self.assertIn("unrecognized command or argument", source)
        self.assertIn("$unsupported", source)
        self.assertIn("Invoke-Usbipd @('list')", source)
        self.assertIn("Connected\\s*:", source)
        self.assertIn("Persisted\\s*:", source)
        self.assertIn("$section -eq 'Connected'", source)
        self.assertIn("BLOCKED_NEEDS_USBIPD_BIND", source)

    def test_windows_helper_avoids_powershell_backslash_quote_hazards(self):
        repo = Path(__file__).resolve().parents[4]
        source = (repo / "tools/hil/ensure-usb-attached.ps1").read_text()
        self.assertNotIn('\\"', source,
                         "PowerShell uses backtick, not backslash, for quote escaping")
        self.assertNotIn("\\'", source,
                         "PowerShell single quotes are not escaped with backslashes")
        self.assertIn("$combined -match '(?i)unrecognized command or argument.*--parsable", source)
        self.assertIn("[System.Management.Automation.Language.Parser]::ParseFile", source)
        self.assertIn("ParserCheck", source)

    def test_windows_native_process_and_usb_attach_result_contract(self):
        repo = Path(__file__).resolve().parents[4]
        source = (repo / "tools/hil/ensure-usb-attached.ps1").read_text()
        native = source[source.index("function Invoke-NativeProcess"):source.index("function ConvertFrom-UsbipdList")]
        self.assertIn("ReadToEndAsync()", native)
        self.assertIn("$process.WaitForExit()", native)
        self.assertIn("StdOut", native)
        self.assertIn("StdErr", native)
        self.assertNotIn("2>&1", native)
        self.assertNotIn("$LASTEXITCODE", source)
        self.assertIn("changed BUSID and informational stderr", source)
        self.assertIn("BLOCKED_USB_ATTACH_TIMEOUT", source)
        self.assertIn("USBIPD_ATTACH_FAILED", source)
        self.assertIn("if ($Value -notmatch '\\s') { return $Value }", source)

    def test_windows_helper_never_executes_wsl_or_bash(self):
        repo = Path(__file__).resolve().parents[4]
        source = (repo / "tools/hil/ensure-usb-attached.ps1").read_text()
        self.assertNotIn("wsl.exe", source)
        self.assertNotIn("bash", source)
        self.assertNotIn("make", source)

    def test_old_wsl_stage_runner_is_deprecated_and_not_authoritative(self):
        repo = Path(__file__).resolve().parents[4]
        runner = (repo / "tools/hil/run-wsl-stage.sh").read_text()
        qualifier = (repo / "code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tools/hil/qualify.py").read_text()
        self.assertIn("Deprecated", runner)
        self.assertNotIn("run-wsl-stage.sh", qualifier)

    def test_qualification_zero_stage_is_fail_closed(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "tools/hil/qualify.py").read_text()
        self.assertIn("FAIL_NO_QUALIFICATION_EXECUTED", source)
        self.assertIn("self.executed == 0", source)
        self.assertIn("PHASE-1 HIL QUALIFICATION", source)

    def test_usb_helper_state_matrix_attaches_only_shared_devices(self):
        repo = Path(__file__).resolve().parents[4]
        source = (repo / "tools/hil/ensure-usb-attached.ps1").read_text()
        self.assertIn("if ($device.State -eq 'Attached')", source)
        self.assertIn("Invoke-Usbipd @('attach', '--wsl', '--busid', $device.BusId)", source)
        self.assertIn("$acceptedBus.ContainsKey($role)", source)

    def test_windows_helper_waits_for_native_usbipd_and_propagates_exit(self):
        repo = Path(__file__).resolve().parents[4]
        source = (repo / "tools/hil/ensure-usb-attached.ps1").read_text()
        native = source[source.index("function Invoke-NativeProcess"):source.index("function Format-NativeResult")]
        self.assertLess(native.index("$process.WaitForExit()"), native.index("ExitCode = [int]$process.ExitCode"))
        self.assertNotIn("add_OutputDataReceived", native)
        self.assertNotIn("BeginOutputReadLine", native)

    def test_usbipd_human_table_contract_covers_states_and_persisted_only_rows(self):
        repo = Path(__file__).resolve().parents[4]
        source = (repo / "tools/hil/ensure-usb-attached.ps1").read_text()
        for state in ("Not shared", "Shared", "Attached"):
            self.assertIn(state, source)
        self.assertIn("10c4:ea60", source)
        self.assertIn("303a:1001", source)
        self.assertIn("USBIPD_LIST_FAILED", source)

    def test_phase1_gate_integration_has_one_authoritative_owner(self):
        product = Path(__file__).resolve().parents[2]
        makefile = (product / "Makefile").read_text()
        nightly = (product / "tools/validation/nightly.py").read_text()
        hw_gate = (product / "tools/validation/hw_release_gate.py").read_text()
        self.assertIn("validation-fast: hil-tooling-test hil-host-check", makefile)
        self.assertIn("hil-qualify:", makefile)
        self.assertIn("python3 tools/hil/qualify.py", makefile)
        self.assertIn("hil-supervisor-test:", makefile)
        self.assertIn("python3 tools/hil/check_usb_helper.py", makefile)
        self.assertIn("hil-target-build-check", makefile)
        self.assertIn("release-gate-final: hil-tooling-test hil-host-check hil-target-build-check", makefile)
        self.assertIn('["make", "hil-qualify"]', nightly)
        self.assertIn('name == "connected-target-hil-phase1" and cp.returncode == 2', nightly)
        self.assertNotIn("HIL_SUPERVISOR_COMMAND", nightly)
        self.assertNotIn('"tools/hil/nightly.py"', nightly)
        self.assertIn('["make", "hil-qualify"]', hw_gate)
        self.assertNotIn("HIL_SUPERVISOR_COMMAND", hw_gate)
        self.assertIn("BLOCKED_HIL_FIXTURE_UNAVAILABLE", hw_gate)
        self.assertIn("authoritative Phase-1 HIL regression", hw_gate)

    def test_flash_failure_recovery_and_ctrl_c_cleanup_contracts_present(self):
        source = (Path(__file__).resolve().parents[2]/"tools/hil/phase1.py").read_text()
        for token in ("flash failed", "def recover", "KeyboardInterrupt", "BLOCKED_BY_FIXTURE_STATE"):
            self.assertIn(token, source)


if __name__ == "__main__": unittest.main()
