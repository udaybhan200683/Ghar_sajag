from __future__ import annotations

import hashlib
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from build_signed_c3 import signed_hil_control_sdkconfig

from tools.hil.secure_signed_fota import (NEGATIVE_ENV, SIGNING_ENV,
    SecureCampaign, activated_python_command, hub_flash_command,
    send_commissioning_control,
    validate_signing_inputs)


class SecureSignedFotaFixtureTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
