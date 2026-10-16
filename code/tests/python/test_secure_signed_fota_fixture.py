from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from build_signed_c3 import signed_hil_control_sdkconfig, signed_profile_cmake_options

from tools.hil.secure_signed_fota import (NEGATIVE_ENV, SIGNING_ENV,
    SecureCampaign, activated_python_command, hub_flash_command,
    artifact_manifest_path, latest_c3_ready_version,
    send_commissioning_control,
    validate_signing_inputs)


class SecureSignedFotaFixtureTest(unittest.TestCase):
    def test_ready_version_is_bounded_to_one_log_token(self):
        lines = [
            "HIL_READY role=c3 protocol=1 version=sfA-physical\n",
            "2026-09-25T17:39:37Z HIL_STATE role=c3 ota_slot=ota_0\n",
        ]
        self.assertEqual(latest_c3_ready_version(lines), "sfA-physical")

    def test_artifact_manifest_path_is_json_serializable(self):
        value = artifact_manifest_path(Path("evidence/run"))
        self.assertIsInstance(value, str)
        self.assertIn("signed_fota_artifacts.json", value)
        json.dumps({"artifacts": value})

    def test_initial_uncommissioned_c3_boot_defers_pir_gate(self):
        campaign = object.__new__(SecureCampaign)
        capture = mock.Mock()
        capture.cursor.return_value = 13

        campaign.restart_and_ready(capture, "c3", "signed-a", wait_for_sensing=False)

        patterns = [item.args[0] for item in capture.wait_for.call_args_list]
        self.assertEqual(len(patterns), 1)
        self.assertIn("HIL_READY role=c3", patterns[0])
        capture.wait_for.assert_called_once()

    def test_secure_motion_verifies_authenticated_hub_event_and_matching_node_ack(self):
        campaign = object.__new__(SecureCampaign)
        campaign.c3 = mock.Mock()
        campaign.hub = mock.Mock()
        campaign.c3.cursor.return_value = 11
        campaign.hub.cursor.return_value = 17
        campaign.c3.wait_for.side_effect = [
            "PIR -> NodeRuntime session=238 seq=9",
            "NodeMessage sent session=238 seq=9 bytes=71",
            "Application ACK session=238 seq=9 class=0 retired=1",
        ]
        campaign.send = mock.Mock(return_value="HIL_OK command=INJECT_MOTION")

        campaign.motion()

        self.assertEqual(campaign.hub.wait_for.call_args.args,
            (r"Authenticated event logical=hil-signed-fota session=238 seq=9 "
             r"sensor=PIR event=MOTION event_id=.* ack=\d+ send=ESP_OK",
             20, 17))

    def test_c3_pir_gate_follows_authenticated_rejoin_and_uses_fresh_boot_cursor(self):
        campaign = object.__new__(SecureCampaign)
        events: list[str] = []
        campaign.node_id = ""
        campaign.hub = mock.Mock()
        campaign.c3 = mock.Mock()
        campaign.hub.wait_for.side_effect = lambda *args: (
            events.append("authenticated-rejoin") or
            "Authenticated rejoin device=c3-abcdef123456 session=91")

        def c3_wait(pattern, _timeout, cursor):
            if "HIL_TEST_QR" in pattern:
                events.append("test-identity")
                return "HIL_TEST_QR profile=TEST_ONLY device_id=c3-abcdef123456 public_key=" + "a" * 128
            if "HIL_TEST_CODE" in pattern:
                events.append("installer-code")
                return "HIL_TEST_CODE profile=TEST_ONLY device_id=c3-abcdef123456 installer_code=" + "b" * 64
            if "PIR ready on GPIO" in pattern:
                events.append("pir-ready")
                self.assertEqual(cursor, 7)
                return "PIR ready on GPIO4"
            self.fail(f"unexpected C3 wait pattern: {pattern}")

        campaign.c3.wait_for.side_effect = c3_wait
        campaign.send = mock.Mock(return_value="HIL_OK")

        campaign.exact_identity_and_session(rejoin_cursor=3, c3_ready_cursor=7)

        self.assertLess(events.index("authenticated-rejoin"), events.index("pir-ready"))
        self.assertEqual(campaign.before_session, "91")

    def test_session_setup_restarts_node_after_hub_and_captures_fresh_rejoin_cursor(self):
        campaign = object.__new__(SecureCampaign)
        campaign.hubs = {"NEG": {"hub_app_version": "hub-negative"}}
        campaign.images = {"A": {"version": "signed-a"}}
        campaign.hub = mock.Mock()
        campaign.c3 = mock.Mock()
        events: list[tuple] = []

        def restart(capture, role, version, *, wait_for_sensing=True):
            events.append(("restart", role, version, wait_for_sensing))
        campaign.restart_and_ready = restart
        campaign.hub.cursor.side_effect = lambda: events.append(("hub-cursor",)) or 31
        campaign.c3.cursor.side_effect = lambda: events.append(("c3-cursor",)) or 47
        campaign.exact_identity_and_session = lambda rejoin_cursor, c3_ready_cursor: \
            events.append(("associate", rejoin_cursor, c3_ready_cursor))

        campaign.establish_fresh_node_session("hub-positive", "signed-candidate-a")

        self.assertEqual(events, [
            ("restart", "hub", "hub-positive", True),
            ("hub-cursor",),
            ("c3-cursor",),
            ("restart", "c3", "signed-candidate-a", False),
            ("associate", 31, 47),
        ])

    def test_positive_hub_swap_reuses_fresh_node_session_sequence(self):
        campaign = object.__new__(SecureCampaign)
        campaign.config = {"fixture": "test"}
        campaign.hubs = {"B": {"hub_app_version": "hub-b"}}
        campaign.images = {"A": {"version": "node-a"}}
        campaign.run_dir = Path("evidence")
        campaign.hub = mock.Mock()
        campaign.c3 = mock.Mock()
        campaign.close = mock.Mock()
        campaign.open = mock.Mock()
        campaign.establish_fresh_node_session = mock.Mock()

        with mock.patch("tools.hil.secure_signed_fota.phase1.runtime_port",
                        return_value="/dev/hub"), \
             mock.patch("tools.hil.secure_signed_fota.flash_hub") as flash:
            campaign.switch_to_positive_hub()

        campaign.close.assert_called_once_with()
        flash.assert_called_once_with(campaign.config, "/dev/hub", campaign.hubs["B"],
                                      campaign.run_dir, "positive")
        campaign.open.assert_called_once_with()
        campaign.establish_fresh_node_session.assert_called_once_with("hub-b", "node-a")

    def test_first_commissioning_control_is_paced_and_still_precedes_pir_gate(self):
        class FakeStream:
            is_open = True
            def __init__(self):
                self.parts = []
            def write(self, data):
                self.parts.append(bytes(data))
            def flush(self):
                pass

        campaign = object.__new__(SecureCampaign)
        events: list[str] = []
        campaign.node_id = ""
        campaign.before_session = ""
        campaign.hub = mock.Mock()
        stream = FakeStream()
        campaign.hub.stream = stream
        campaign.hub.stream_lock = threading.RLock()
        campaign.hub.cursor.return_value = 3
        campaign.hub.wait_for.side_effect = [
            TimeoutError("not commissioned"),
            "HIL_OK command=COMMISSION_TEST_NODE",
            "Authenticated rejoin device=c3-abcdef123456 session=92",
        ]
        campaign.c3 = mock.Mock()
        campaign.c3.cursor.return_value = 7
        campaign.c3.wait_for.side_effect = lambda pattern, *_args: (
            "HIL_TEST_QR profile=TEST_ONLY device_id=c3-abcdef123456 public_key=" + "a" * 130
            if "HIL_TEST_QR" in pattern else
            "HIL_TEST_CODE profile=TEST_ONLY device_id=c3-abcdef123456 installer_code=" + "b" * 64
            if "HIL_TEST_CODE" in pattern else
            events.append("pir-ready") or "PIR ready on GPIO4"
        )

        with mock.patch("tools.hil.secure_signed_fota.time.sleep"):
            campaign.exact_identity_and_session(rejoin_cursor=3, c3_ready_cursor=7)

        self.assertGreater(len(stream.parts), 1)
        self.assertTrue(all(len(part) <= 32 for part in stream.parts))
        self.assertEqual(b"".join(stream.parts)[-1:], b"\n")
        self.assertIn(b"COMMISSION_TEST_NODE", b"".join(stream.parts))
        self.assertEqual(campaign.before_session, "92")

    def test_signed_hil_control_profile_selects_native_usb_console(self):
        base = "\n".join((
            "CONFIG_ESP_CONSOLE_UART_DEFAULT=y",
            "# CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG is not set",
            "# CONFIG_ESP_CONSOLE_UART_CUSTOM is not set",
            "# CONFIG_ESP_CONSOLE_NONE is not set",
            "# CONFIG_ESP_CONSOLE_SECONDARY_NONE is not set",
            "CONFIG_ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAG=y",
            "CONFIG_ESP_CONSOLE_UART=y",
            "CONFIG_ESP_CONSOLE_UART_NUM=0",
            "CONFIG_ESP_CONSOLE_ROM_SERIAL_PORT_NUM=0",
        )) + "\n"
        result = signed_hil_control_sdkconfig(base)
        self.assertIn("CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y", result)
        self.assertIn("CONFIG_ESP_CONSOLE_SECONDARY_NONE=y", result)
        self.assertIn("# CONFIG_ESP_CONSOLE_UART is not set", result)
        self.assertIn("CONFIG_ESP_CONSOLE_UART_NUM=-1", result)
        self.assertNotIn("CONFIG_ESP_CONSOLE_UART_DEFAULT=y", result)

    def test_secure_hil_control_profile_enables_only_existing_test_credentials(self):
        root = Path(__file__).resolve().parents[2]
        identity = (root / "firmware/common/security/target_identity_signer.cpp").read_text()
        wrapping = (root / "firmware/common/security/target_wrapping_key.cpp").read_text()
        self.assertIn("#if GS_HIL_BUILD || GS_HIL_CONTROL", identity)
        self.assertIn("#if !GS_HIL_BUILD && !GS_HIL_CONTROL", wrapping)
        self.assertIn('"gs_dev_ident"', identity)
        self.assertIn('"gs_security"', wrapping)

    def test_rollback_stack_stays_at_conservative_bytes_value(self):
        root = Path(__file__).resolve().parents[2]
        receiver = (root / "firmware/node/target/esp32c3/idf/main/fota_receiver.cpp").read_text()
        self.assertIn("constexpr std::uint32_t kImageValidationTaskStackBytes = 12U * 1024U;",
                      receiver)
        self.assertIn('xTaskCreate(validate_running_image, "gs_ota_validate",\n'
                      '                    kImageValidationTaskStackBytes', receiver)
        self.assertNotIn('"gs_ota_validate", 3072', receiver)

    def test_boot_failure_injection_requires_explicit_signed_hil_control(self):
        self.assertEqual(signed_profile_cmake_options(
            hil_control=True, force_boot_health_fail=True), [
                "-DGS_HIL_BUILD=OFF", "-DGS_HIL_CONTROL=ON",
                "-DGS_HIL_FORCE_BOOT_HEALTH_FAIL=ON"])
        self.assertEqual(signed_profile_cmake_options(
            hil_control=False, force_boot_health_fail=False), [
                "-DGS_HIL_BUILD=OFF", "-DGS_HIL_CONTROL=OFF",
                "-DGS_HIL_FORCE_BOOT_HEALTH_FAIL=OFF"])
        with self.assertRaisesRegex(ValueError, "requires --hil-control"):
            signed_profile_cmake_options(hil_control=False, force_boot_health_fail=True)

    def test_physical_wake_signed_profile_needs_no_unrelated_hil_controls(self):
        options = signed_profile_cmake_options(hil_control=False,
                                               force_boot_health_fail=False,
                                               physical_wake=True)
        self.assertIn("-DGS_HIL_CONTROL=OFF", options)
        self.assertIn("-DGS_BAT_C8_PHYSICAL_WAKE=ON", options)
        self.assertIn("-DGS_HIL_BUILD=OFF", options)

        cmake = (Path(__file__).resolve().parents[2] /
                 "firmware/node/target/esp32c3/idf/CMakeLists.txt").read_text()
        self.assertIn("if(GS_BAT_C8_PHYSICAL_WAKE AND GS_HIL_BUILD)", cmake)
        self.assertIn('option(GS_BAT_C8_ACK_TRACE "Enable bounded P9-A ACK-wait diagnostics in a qualification image" OFF)', cmake)
        self.assertIn("if(GS_BAT_C8_ACK_TRACE AND (NOT GS_BAT_C8_PHYSICAL_WAKE OR GS_HIL_BUILD))", cmake)

    def test_signed_non_hil_image_rejects_c3_uart_test_commands(self):
        source = (Path(__file__).resolve().parents[2] / "scripts/build_signed_c3.py").read_text()
        for marker in ("HIL_READY", "INJECT_MOTION", "GET_HEALTH", "GET_STATE",
                       "GET_TEST_QR", "SOFTWARE_RESTART"):
            self.assertIn(f'b"{marker}"', source)
        self.assertIn("HIL command marker in signed non-HIL image", source)

    def test_cmake_rejects_forced_failure_in_production_profiles(self):
        root = Path(__file__).resolve().parents[2]
        project = root / "firmware/node/target/esp32c3/idf"
        profiles = (
            ("OFF", "OFF"),
            ("ON", "ON"),
        )
        for index, (hil_build, hil_control) in enumerate(profiles):
            with self.subTest(hil_build=hil_build, hil_control=hil_control), \
                 tempfile.TemporaryDirectory() as temporary:
                result = subprocess.run([
                    "cmake", "-S", str(project), "-B", str(Path(temporary) / f"bad-{index}"),
                    f"-DGS_HIL_BUILD={hil_build}", f"-DGS_HIL_CONTROL={hil_control}",
                    "-DGS_HIL_FORCE_BOOT_HEALTH_FAIL=ON"],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("GS_HIL_FORCE_BOOT_HEALTH_FAIL requires", result.stdout)

        invalid_ack_trace_profiles = (
            ("OFF", "OFF", "ON"),
            ("ON", "ON", "ON"),
        )
        for index, (physical_wake, hil_build, ack_trace) in enumerate(
                invalid_ack_trace_profiles):
            with self.subTest(physical_wake=physical_wake, hil_build=hil_build), \
                 tempfile.TemporaryDirectory() as temporary:
                result = subprocess.run([
                    "cmake", "-S", str(project), "-B",
                    str(Path(temporary) / f"invalid-ack-trace-{index}"),
                    f"-DGS_BAT_C8_PHYSICAL_WAKE={physical_wake}",
                    f"-DGS_HIL_BUILD={hil_build}",
                    f"-DGS_BAT_C8_ACK_TRACE={ack_trace}"],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, check=False)
                self.assertNotEqual(result.returncode, 0)
                expected_error = ("GS_BAT_C8_PHYSICAL_WAKE requires"
                                  if physical_wake == "ON" and hil_build == "ON"
                                  else "GS_BAT_C8_ACK_TRACE requires")
                self.assertIn(expected_error, result.stdout)

    def test_failed_health_rollback_evidence_requires_fresh_recovery_and_same_event_key(self):
        candidate = [
            "rst:0x3 (SW_CPU_RESET),boot:0x13 (SPI_FAST_FLASH_BOOT)\n",
            "HIL_READY role=c3 protocol=1 version=sfR-test\n",
            "HIL_BOOT_HEALTH_FAILURE_INJECTED: suppressing validation evidence\n",
            "OTA health deadline expired; requesting rollback\n",
        ]
        recovery = ["rst:0x3 (SW_CPU_RESET),boot:0x13 (SPI_FAST_FLASH_BOOT)\n",
                    "HIL_READY role=c3 protocol=1 version=sfA-test\n"]
        evidence = dict(candidate_lines=candidate, recovery_lines=recovery,
            reset_lines=[candidate[0], recovery[0]], candidate_version="sfR-test",
            known_good_version="sfA-test", previous_slot="ota_0", recovered_slot="ota_0",
            previous_session="10", candidate_session="20", recovery_session="30",
            pending_identity=("20", "7"), retry_identity=("20", "7"),
            ack_identity=("20", "7"), ack_class=0, retired=1, retained_after_ack=0,
            processed_before=4, processed_after=5)
        SecureCampaign.validate_failed_health_rollback_evidence(**evidence)

        stale = dict(evidence, recovery_session="20")
        with self.assertRaisesRegex(RuntimeError, "stale authenticated session"):
            SecureCampaign.validate_failed_health_rollback_evidence(**stale)
        changed_key = dict(evidence, retry_identity=("20", "8"))
        with self.assertRaisesRegex(RuntimeError, "event identity changed"):
            SecureCampaign.validate_failed_health_rollback_evidence(**changed_key)
        marked_healthy = dict(evidence, candidate_lines=candidate + [
            "OTA image marked VALID after sensing/runtime/radio health\n"])
        with self.assertRaisesRegex(RuntimeError, "incorrectly marked healthy"):
            SecureCampaign.validate_failed_health_rollback_evidence(**marked_healthy)
        panicked = dict(evidence, recovery_lines=recovery + ["Guru Meditation Error: Stack protection fault\n"])
        with self.assertRaisesRegex(RuntimeError, "panic, stack fault"):
            SecureCampaign.validate_failed_health_rollback_evidence(**panicked)

    def test_build_scripts_use_idf_activated_python_from_path(self):
        self.assertEqual(activated_python_command("scripts/build_signed_c3.py", "build"),
                         ["python", "scripts/build_signed_c3.py", "build"])

    def test_signing_preflight_uses_configured_idf_activation_not_parent_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            signing = root / "ab.pem"
            negative = root / "negative.pem"
            activation = root / "activate.sh"
            signing.write_text("test-only key marker")
            negative.write_text("test-only key marker")
            activation.write_text("# activation fixture")
            with mock.patch.dict(os.environ, {
                    SIGNING_ENV: str(signing), NEGATIVE_ENV: str(negative)}, clear=True):
                actual = validate_signing_inputs({"HIL_IDF_ACTIVATE": str(activation)})
            self.assertEqual(actual, (signing.resolve(), negative.resolve()))

    def test_hub_flash_uses_exact_candidate_artifact_for_shared_build_dir(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build_dir = root / "shared-build"
            build_dir.mkdir()
            otadata = build_dir / "ota_data_initial.bin"
            otadata.write_bytes(bytes(0x2000))
            negative = root / "negative-hub.bin"
            positive = root / "positive-hub.bin"
            negative.write_bytes(b"negative candidate")
            positive.write_bytes(b"positive candidate")

            def record(path: Path) -> dict:
                return {"profile": "secure-signed-fota-hil-control",
                        "legacy_raw_fota": False,
                        "build_dir": str(build_dir),
                        "hub_image": str(path),
                        "hub_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

            negative_command = hub_flash_command(record(negative), "/dev/ttyUSB-hub")
            positive_command = hub_flash_command(record(positive), "/dev/ttyUSB-hub")
            self.assertIn(str(negative), negative_command)
            self.assertIn(str(positive), positive_command)
            self.assertNotIn("idf.py", negative_command)
            self.assertNotIn("idf.py", positive_command)
            self.assertIn("0xf000", negative_command)
            self.assertIn("0x20000", positive_command)

    def test_hub_flash_rejects_image_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build_dir = root / "build"
            build_dir.mkdir()
            (build_dir / "ota_data_initial.bin").write_bytes(bytes(0x2000))
            image = root / "hub.bin"
            image.write_bytes(b"candidate")
            record = {"profile": "secure-signed-fota-hil-control",
                      "legacy_raw_fota": False,
                      "build_dir": str(build_dir),
                      "hub_image": str(image),
                      "hub_sha256": "0" * 64}
            with self.assertRaisesRegex(RuntimeError, "profile/hash"):
                hub_flash_command(record, "/dev/ttyUSB-hub")

    def test_positive_transfer_waits_for_pre_reboot_acceptance_not_post_reboot_sha_marker(self):
        campaign = object.__new__(SecureCampaign)
        campaign.node_id = "c3-abcdef123456"
        campaign.before_session = "271"
        campaign.hub = mock.Mock()
        campaign.c3 = mock.Mock()
        campaign.transfer_ids = {}
        campaign.send = mock.Mock(return_value="HIL_OK")
        campaign.hub.cursor.return_value = 20
        campaign.c3.cursor.return_value = 30
        campaign.hub.wait_for.side_effect = [
            "SECURE_FOTA_BEGIN transfer=123 node=c3-abcdef123456 board=esp32c3 version=sfB bytes=921600",
            "SECURE_FOTA_SESSION_PINNED transfer=123 session=271",
            "SECURE_FOTA_TRANSFER_COMPLETE transfer=123 chunks=4800",
        ]
        campaign.c3.wait_for.side_effect = [
            "SECURE_FOTA_IMAGE_SIGNATURE_ACCEPTED",
            "FOTA COMPLETE; next boot partition=ota_1",
        ]

        result = campaign.secure_transfer("sfB", expect_signature_reject=False)

        self.assertEqual(result, "123")
        patterns = [call.args[0] for call in campaign.c3.wait_for.call_args_list]
        self.assertIn(r"SECURE_FOTA_IMAGE_SIGNATURE_ACCEPTED", patterns)
        self.assertNotIn(r"SECURE_FOTA_IMAGE_SHA256_VERIFIED transfer=123", patterns)

    def test_interleaved_begin_line_uses_authenticated_begin_ack_fallback(self):
        campaign = object.__new__(SecureCampaign)
        campaign.node_id = "c3-abcdef123456"
        campaign.before_session = "271"
        campaign.hub = mock.Mock()
        campaign.c3 = mock.Mock()
        campaign.transfer_ids = {}
        campaign.send = mock.Mock(return_value="HIL_OK")
        campaign.hub.cursor.return_value = 20
        campaign.c3.cursor.return_value = 30
        campaign.hub.wait_for.side_effect = [
            "SECURE_FOTA_BEGIN transfer=123 node",
            TimeoutError("interleaved session pin"),
            "SECURE_FOTA_BEGIN_ACK transfer=123 authenticated=1",
            "SECURE_FOTA_TRANSFER_FAILED transfer=123 phase=end",
        ]
        campaign.c3.wait_for.side_effect = [
            "SECURE_FOTA_IMAGE_SHA256_VERIFIED transfer=123",
            "SECURE_FOTA_IMAGE_SIGNATURE_REJECTED error=ESP_ERR_OTA_VALIDATE_FAILED",
        ]

        result = campaign.secure_transfer("sfN", expect_signature_reject=True)

        self.assertEqual(result, "SECURE_FOTA_IMAGE_SIGNATURE_REJECTED error=ESP_ERR_OTA_VALIDATE_FAILED")
        self.assertEqual(campaign.before_session, "271")


if __name__ == "__main__":
    unittest.main()
