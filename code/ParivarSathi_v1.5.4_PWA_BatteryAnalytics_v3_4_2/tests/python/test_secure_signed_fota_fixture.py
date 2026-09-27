from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from build_signed_c3 import signed_hil_control_sdkconfig, signed_profile_baseline

from tools.hil.secure_signed_fota import (EXPECTED, NEGATIVE_ENV, SIGNING_ENV,
    SecureCampaign, activated_python_command, hub_flash_command,
    artifact_manifest_path, build_images, latest_c3_ready_version,
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
            (r"Authenticated event logical=hil-signed-fota seq=9 ack=\d+ send=ESP_OK",
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

    def test_signed_profile_does_not_require_untracked_signed_sdkconfig(self):
        with tempfile.TemporaryDirectory() as temporary:
            node_project = Path(temporary)
            standard = node_project / "sdkconfig"
            standard.write_text("standard target configuration")
            self.assertEqual(signed_profile_baseline(node_project), standard)
            signed = node_project / "sdkconfig.signed"
            signed.write_text("existing signed configuration")
            self.assertEqual(signed_profile_baseline(node_project), signed)

    def test_signed_profile_baseline_missing_fails_clearly(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(FileNotFoundError, "configure the target once"):
                signed_profile_baseline(Path(temporary))

    def test_secure_hil_control_profile_enables_only_existing_test_credentials(self):
        root = Path(__file__).resolve().parents[2]
        identity = (root / "firmware/common/security/target_identity_signer.cpp").read_text()
        wrapping = (root / "firmware/common/security/target_wrapping_key.cpp").read_text()
        self.assertIn("#if GS_HIL_BUILD || GS_HIL_CONTROL", identity)
        self.assertIn("#if !GS_HIL_BUILD && !GS_HIL_CONTROL", wrapping)
        self.assertIn('"gs_dev_ident"', identity)
        self.assertIn('"gs_security"', wrapping)

    def test_build_scripts_use_idf_activated_python_from_path(self):
        self.assertEqual(activated_python_command("scripts/build_signed_c3.py", "build"),
                         ["python", "scripts/build_signed_c3.py", "build"])

    def test_boot_health_failure_build_option_requires_secure_hil_control(self):
        script = Path(__file__).resolve().parents[2] / "scripts/build_signed_c3.py"
        result = subprocess.run([sys.executable, str(script), "--signing-key", "unused.pem",
                                 "--force-boot-health-fail"],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("--force-boot-health-fail requires --hil-control", result.stdout)

    def test_signed_rollback_candidate_isolated_and_only_artifact_with_fault_flag(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            key, negative, activation = root / "ab.pem", root / "neg.pem", root / "activate.sh"
            key.write_text("disposable test key")
            negative.write_text("different disposable test key")
            activation.write_text("# activation")
            seen: list[list[str]] = []

            def fake_command(args, *, cwd, config, timeout=3600):
                del cwd, config, timeout
                seen.append(args)
                output = Path(args[args.index("--output") + 1])
                version = args[args.index("--version") + 1]
                fault = "--force-boot-health-fail" in args
                output.write_bytes((version + ("-rollback" if fault else "-normal")).encode())
                fingerprint = "b" * 64 if "--trusted-key" in args else "a" * 64
                output.with_suffix(output.suffix + ".json").write_text(json.dumps({
                    "version": version, "profile": "signed-app-on-update",
                    "hil_control": True, "gs_hil_build": False,
                    "build_dir": args[args.index("--build-dir") + 1],
                    "boot_health_failure_injection": fault,
                    "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                    "size": output.stat().st_size,
                    "signing_public_key_fingerprint_sha256": fingerprint,
                }))
                return "build simulated"

            with mock.patch.dict(os.environ, {
                    SIGNING_ENV: str(key), NEGATIVE_ENV: str(negative)}), \
                 mock.patch("tools.hil.secure_signed_fota.phase1.activation",
                            return_value=activation), \
                 mock.patch("tools.hil.secure_signed_fota.ARTIFACTS", root / "artifacts"), \
                 mock.patch("tools.hil.secure_signed_fota.command", side_effect=fake_command):
                (root / "run").mkdir()
                images = build_images(root / "run", {"HIL_IDF_ACTIVATE": str(activation)})

            self.assertEqual(set(images["versions"]), {"A", "B", "NEG", "ROLLBACK"})
            self.assertEqual(len({images[name]["version"] for name in images["versions"]}), 4)
            self.assertNotEqual(images["A"]["build_dir"], images["ROLLBACK"]["build_dir"])
            self.assertFalse(images["B"]["boot_health_failure_injection"])
            self.assertTrue(images["ROLLBACK"]["boot_health_failure_injection"])
            self.assertEqual(sum("--force-boot-health-fail" in args for args in seen), 1)

    def test_secure_signed_campaign_includes_boot_rollback_case(self):
        self.assertIn("SIGNED_FOTA_BOOT_ROLLBACK", EXPECTED)

    def test_rollback_case_requires_post_deadline_rejoin_and_fresh_ack(self):
        class Capture:
            def __init__(self, role, lines, cursors=None):
                self.role, self.lines = role, lines
                self.waits = []
                self.cursors = list(cursors or [])
            def cursor(self):
                if self.cursors:
                    return self.cursors.pop(0)
                return 1 if self.role == "c3" else 4
            def wait_for(self, pattern, timeout, start=0):
                self.waits.append((pattern, timeout, start))
                import re
                compiled = re.compile(pattern)
                for line in self.lines[start:]:
                    if compiled.search(line):
                        return line
                raise AssertionError(pattern)
            def wait_for_predicate(self, predicate, description, timeout, start=0):
                self.waits.append((description, timeout, start))
                for line in self.lines[start:]:
                    if predicate(line):
                        return line
                raise AssertionError(description)

        campaign = object.__new__(SecureCampaign)
        campaign.images = {"B": {"version": "sfB-test"},
                           "ROLLBACK": {"version": "sfR-test"}}
        campaign.node_id = "c3-test"
        campaign.before_session = "299"
        campaign.hubs = {"ROLLBACK": {"hub_app_version": "hub-r"}}
        campaign.run_dir = Path("evidence")
        campaign.config = {}
        campaign.results = mock.Mock()
        campaign.c3 = Capture("c3", [
            "HIL_READY role=c3 protocol=1 version=sfB-test",
            "rst:0xc (RTC_SW_CPU_RST)",
            "HIL_READY role=c3 protocol=1 version=sfR-test",
            "HIL_BOOT_HEALTH_FAILURE_INJECTED",
            "OTA health deadline expired; requesting rollback",
            "rst:0xc (SW_CPU_RESET)",
            "HIL_READY role=c3 protocol=1 version=sfB-test",
            "PIR ready on GPIO4",
        ])
        campaign.hub = Capture("hub", ["old hub line"] * 4 + [
            "Authenticated rejoin device=c3-test session=300",  # candidate boot
            "Authenticated rejoin device=c3-test session=301",  # restored image
        ], cursors=[5])
        campaign.switch_to_rollback_hub = mock.Mock()
        campaign.secure_transfer = mock.Mock(return_value="transfer-1")
        campaign.state = mock.Mock(side_effect=[
            "HIL_STATE role=c3 ota_slot=ota_1",
            "HIL_STATE role=c3 ota_slot=ota_1",
            "HIL_STATE role=c3 retained=0 in_flight=0 ota_slot=ota_1",
        ])
        campaign.motion = mock.Mock()

        result = campaign.qualify_boot_rollback()

        campaign.secure_transfer.assert_called_once_with("sfR-test", expect_signature_reject=False)
        campaign.motion.assert_called_once_with()
        self.assertEqual(result["slot_before"], "ota_1")
        self.assertEqual(result["slot_after"], "ota_1")
        self.assertEqual(result["restored_session"], "301")
        campaign.results.add.assert_called_once()
        self.assertEqual(campaign.results.add.call_args.args[0], "SIGNED_FOTA_BOOT_ROLLBACK")
        self.assertTrue(any("PIR ready" in pattern for pattern, *_ in campaign.c3.waits))
        reset_waits = [start for description, _timeout, start in campaign.c3.waits
                       if description.startswith("fresh reset")]
        self.assertEqual(reset_waits, [1, 5])
        self.assertGreater(reset_waits[1], campaign.c3.lines.index(
            "OTA health deadline expired; requesting rollback"))
        self.assertEqual(campaign.hub.waits[-1][2], 5)

    def test_rollback_case_rejects_target_panic_even_if_b_is_restored(self):
        campaign = object.__new__(SecureCampaign)
        campaign.images = {"B": {"version": "sfB-test"},
                           "ROLLBACK": {"version": "sfR-test"}}
        campaign.node_id = "c3-test"
        campaign.before_session = "299"
        campaign.hubs = {"ROLLBACK": {"hub_app_version": "hub-r"}}
        campaign.run_dir = Path("evidence")
        campaign.config = {}
        campaign.results = mock.Mock()
        campaign.c3 = mock.Mock()
        campaign.c3.lines = [
            "HIL_READY role=c3 protocol=1 version=sfB-test",
            "OTA health deadline expired; requesting rollback",
            "Guru Meditation Error: Core 0 panic'ed (Stack protection fault)",
        ]
        campaign.c3.cursor.return_value = 1
        campaign.c3.wait_for.side_effect = [
            "HIL_READY role=c3 protocol=1 version=sfR-test",
            "HIL_BOOT_HEALTH_FAILURE_INJECTED",
            "OTA health deadline expired; requesting rollback",
            "HIL_READY role=c3 protocol=1 version=sfB-test",
            "PIR ready on GPIO4",
        ]
        campaign.c3.wait_for_predicate.return_value = "rst:0xc (SW_CPU_RESET)"
        campaign.hub = mock.Mock()
        campaign.hub.cursor.return_value = 5
        campaign.switch_to_rollback_hub = mock.Mock()
        campaign.secure_transfer = mock.Mock(return_value="transfer-1")
        campaign.state = mock.Mock(side_effect=[
            "HIL_STATE role=c3 ota_slot=ota_1",
            "HIL_STATE role=c3 ota_slot=ota_1",
        ])

        with self.assertRaisesRegex(RuntimeError, "unexpected target panic"):
            campaign.qualify_boot_rollback()

    def test_rollback_case_rejects_candidate_marked_valid_before_timeout(self):
        campaign = object.__new__(SecureCampaign)
        campaign.images = {"B": {"version": "sfB-test"},
                           "ROLLBACK": {"version": "sfR-test"}}
        campaign.node_id = "c3-test"
        campaign.before_session = "299"
        campaign.hubs = {"ROLLBACK": {"hub_app_version": "hub-r"}}
        campaign.run_dir = Path("evidence")
        campaign.config = {}
        campaign.results = mock.Mock()
        campaign.c3 = mock.Mock()
        campaign.c3.lines = [
            "HIL_READY role=c3 protocol=1 version=sfB-test",
            "OTA image marked VALID after sensing/runtime/radio health",
            "OTA health deadline expired; requesting rollback",
        ]
        campaign.c3.cursor.return_value = 1
        campaign.c3.wait_for.side_effect = [
            "HIL_READY role=c3 protocol=1 version=sfR-test",
            "HIL_BOOT_HEALTH_FAILURE_INJECTED",
            "OTA health deadline expired; requesting rollback",
            "HIL_READY role=c3 protocol=1 version=sfB-test",
            "PIR ready on GPIO4",
        ]
        campaign.c3.wait_for_predicate.return_value = "rst:0xc (SW_CPU_RESET)"
        campaign.hub = mock.Mock()
        campaign.hub.cursor.return_value = 4
        campaign.switch_to_rollback_hub = mock.Mock()
        campaign.secure_transfer = mock.Mock(return_value="transfer-1")
        campaign.state = mock.Mock(return_value="HIL_STATE role=c3 ota_slot=ota_1")

        with self.assertRaisesRegex(RuntimeError, "marked valid"):
            campaign.qualify_boot_rollback()

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

    def test_interleaved_begin_ack_uses_authenticated_ack_progress_fallback(self):
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
            "SECURE_FOTA_ACK_PROGRESS transfer=123 index=32 bytes=6144",
            "SECURE_FOTA_TRANSFER_FAILED transfer=123 phase=end",
        ]
        campaign.c3.wait_for.side_effect = [
            "SECURE_FOTA_IMAGE_SHA256_VERIFIED transfer=123",
            "SECURE_FOTA_IMAGE_SIGNATURE_REJECTED error=ESP_ERR_OTA_VALIDATE_FAILED",
        ]

        result = campaign.secure_transfer("sfN", expect_signature_reject=True)

        self.assertEqual(result, "SECURE_FOTA_IMAGE_SIGNATURE_REJECTED error=ESP_ERR_OTA_VALIDATE_FAILED")
        self.assertEqual(campaign.before_session, "271")
        admission_pattern = campaign.hub.wait_for.call_args_list[1].args[0]
        self.assertIn(r"SECURE_FOTA_BEGIN_ACK transfer=123 authenticated=1", admission_pattern)
        self.assertIn(r"SECURE_FOTA_ACK_PROGRESS transfer=123 index=\d+ bytes=\d+", admission_pattern)
        self.assertIn(r"SECURE_FOTA_SESSION_PINNED transfer=123 session=(\d+)", admission_pattern)


if __name__ == "__main__":
    unittest.main()
