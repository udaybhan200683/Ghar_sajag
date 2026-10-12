import unittest
from unittest.mock import patch
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import subprocess

import gs130_hil_common as common
import gs130_board_hil as board
import gs130_motion_hil as motion


class GS130RunnerTests(unittest.TestCase):
    def test_runner_cases_resolve_to_permanent_physical_catalogue(self):
        registered = common.catalogue_test_ids()
        self.assertTrue(set(board.CASES).issubset(registered))
        self.assertTrue({case_id for case_id, _ in motion.CASES}.issubset(registered))

    def test_motion_failure_is_not_hidden_by_partial_or_abort(self):
        self.assertEqual(motion.overall_motion_status([{"status": "FAIL"}, {"status": "NOT_RUN"}]), "FAIL")
        self.assertEqual(motion.overall_motion_status([{"status": "NOT_RUN"}]), "NOT_RUN")
        self.assertEqual(motion.overall_motion_status([{"status": "PASS"}, {"status": "NOT_RUN"}]), "PARTIAL")

    def test_only_complete_physical_pass_has_zero_exit(self):
        self.assertEqual(common.report_exit_code("PASS"), 0)
        self.assertEqual(common.report_exit_code("FAIL"), 1)
        for incomplete in ("PARTIAL", "BLOCKED", "NOT_RUN"):
            self.assertEqual(common.report_exit_code(incomplete), 3)

    def test_fixture_ports_must_match_exact_stable_identity_and_images(self):
        errors = common.verify_preflight("/dev/ttyACM1", "/dev/ttyACM0", None, None)
        self.assertEqual(len(errors), 4)
        self.assertTrue(all("by-id path" in error or "image artifact" in error for error in errors))

    def test_preflight_requires_exact_read_only_usb_serial_identity(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            c3_port, s3_port = root / "c3-by-id", root / "s3-by-id"
            c3_port.symlink_to("/dev/null")
            s3_port.symlink_to("/dev/null")
            c3_image, s3_image = root / "c3.bin", root / "s3.bin"
            c3_image.write_bytes(b"c3 image")
            s3_image.write_bytes(b"s3 image")
            fixture = {"boards": {
                "c3": {"by_id": str(c3_port), "usb_serial_short": "C3-IDENT", "image_sha256": hashlib.sha256(b"c3 image").hexdigest()},
                "s3": {"by_id": str(s3_port), "usb_serial_short": "S3-IDENT", "image_sha256": hashlib.sha256(b"s3 image").hexdigest()},
            }}
            good = [subprocess.CompletedProcess([], 0, "ID_SERIAL_SHORT=C3-IDENT\n", ""),
                    subprocess.CompletedProcess([], 0, "ID_SERIAL_SHORT=S3-IDENT\n", "")]
            with patch.object(common, "FIXTURE", fixture), patch.object(common.subprocess, "run", side_effect=good):
                self.assertEqual(common.verify_preflight(str(c3_port), str(s3_port), c3_image, s3_image), [])
            bad = [subprocess.CompletedProcess([], 0, "ID_SERIAL_SHORT=OTHER\n", ""),
                   subprocess.CompletedProcess([], 0, "ID_SERIAL_SHORT=S3-IDENT\n", "")]
            with patch.object(common, "FIXTURE", fixture), patch.object(common.subprocess, "run", side_effect=bad):
                errors = common.verify_preflight(str(c3_port), str(s3_port), c3_image, s3_image)
            self.assertTrue(any("USB serial mismatch" in error for error in errors))

    def test_default_board_command_never_opens_uart(self):
        with TemporaryDirectory() as temporary:
            report = Path(temporary) / "board"
            with patch("sys.argv", ["gs130_board_hil.py", "--report", str(report)]), \
                 patch.object(board.ReadOnlyCapture, "open") as open_uart:
                self.assertEqual(board.main(), 3)
                open_uart.assert_not_called()
            result = json.loads((report / "board_hil_results.json").read_text())
            self.assertEqual(result["overall"], "NOT_RUN")
            self.assertEqual(len(result["cases"]), 8)
            self.assertEqual(result["hardware_actions"], [])

    def test_default_motion_command_never_requests_stimulus_or_opens_uart(self):
        with TemporaryDirectory() as temporary:
            report = Path(temporary) / "motion"
            with patch("sys.argv", ["gs130_motion_hil.py", "--report", str(report)]), \
                 patch.object(motion.ReadOnlyCapture, "open") as open_uart:
                self.assertEqual(motion.main(), 3)
                open_uart.assert_not_called()
            result = json.loads((report / "motion_hil_results.json").read_text())
            self.assertEqual(result["overall"], "NOT_RUN")
            self.assertEqual(len(result["cases"]), len(motion.CASES))
            self.assertEqual(result["hardware_actions"], [])

    def test_wrong_operator_confirmation_is_rejected(self):
        with TemporaryDirectory() as temporary:
            report = Path(temporary) / "board"
            with patch("builtins.input", return_value=""), patch.object(common, "verify_preflight", return_value=[]), \
                 patch.object(board.ReadOnlyCapture, "open") as open_uart, \
                 patch("sys.argv", ["gs130_board_hil.py", "--observe", "--c3-port", common.FIXTURE["boards"]["c3"]["by_id"], "--s3-port", common.FIXTURE["boards"]["s3"]["by_id"], "--c3-image", "x", "--s3-image", "y", "--report", str(report)]):
                self.assertEqual(board.main(), 3)
                open_uart.assert_not_called()
            result = json.loads((report / "board_hil_results.json").read_text())
            self.assertEqual(result["overall"], "BLOCKED")

    def test_motion_runner_wrong_confirmation_never_opens_uart(self):
        with TemporaryDirectory() as temporary:
            report = Path(temporary) / "motion"
            with patch("builtins.input", return_value=""), patch.object(common, "verify_preflight", return_value=[]), \
                 patch.object(motion.ReadOnlyCapture, "open") as open_uart, \
                 patch("sys.argv", ["gs130_motion_hil.py", "--run", "--c3-port", common.FIXTURE["boards"]["c3"]["by_id"], "--s3-port", common.FIXTURE["boards"]["s3"]["by_id"], "--c3-image", "x", "--s3-image", "y", "--report", str(report)]):
                self.assertEqual(motion.main(), 3)
                open_uart.assert_not_called()
            result = json.loads((report / "motion_hil_results.json").read_text())
            self.assertEqual(result["overall"], "BLOCKED")

    def test_evidence_directory_refuses_to_overwrite_existing_campaign(self):
        with TemporaryDirectory() as temporary:
            target = Path(temporary) / "prior"
            target.mkdir()
            (target / "results.json").write_text("prior evidence")
            with self.assertRaises(FileExistsError):
                common.create_evidence_dir(target, "unused")

    def test_observational_gaps_never_become_pass(self):
        for case_id in ("HIL-A01", "HIL-A03", "HIL-A04", "HIL-A05", "HIL-A08"):
            status, _ = common.status_from_logs(case_id, "", "")
            self.assertIn(status, {"BLOCKED", "NOT_RUN"})

    def test_link_needs_both_sides_and_runtime_stability_is_bounded_partial(self):
        self.assertEqual(common.status_from_logs("HIL-A02", "authenticated session", "")[0], "NOT_RUN")
        self.assertEqual(common.status_from_logs("HIL-A02", "authenticated session", "authenticated Node")[0], "PASS")
        self.assertEqual(common.status_from_logs("HIL-A06", "boot log", "running log")[0], "PARTIAL")

    def test_hil_a05_requires_same_key_authenticated_ack_and_retirement(self):
        unrelated_c3 = "EventKey=room:10:1\nMAC send success\nEventKey=room:10:1 pending=0"
        unrelated_s3 = "Authenticated Durable ACK EventKey=room:10:2"
        self.assertEqual(common.status_from_logs("HIL-A05", unrelated_c3, unrelated_s3)[0], "NOT_RUN")
        matched_c3 = "EventKey=room:10:1 retired pending=0"
        matched_s3 = "EventKey=room:10:1 authenticated Durable ACK"
        self.assertEqual(common.status_from_logs("HIL-A05", matched_c3, matched_s3)[0], "PASS")

    def test_genuine_gpio4_event_ack_markers_required(self):
        status, _ = motion.evaluate_motion_evidence("", "")
        self.assertEqual(status, "BLOCKED")
        injected = "INJECT_MOTION BAT_SLEEP_WAKE cause=GPIO gpio4=1 BAT_SLEEP_RESTORE PIR -> NodeRuntime NodeMessage sent Application ACK Processed"
        self.assertEqual(motion.evaluate_motion_evidence(injected, injected)[0], "FAIL")
        real = ("BAT_SLEEP_WAKE cause=GPIO gpio4=1\nBAT_SLEEP_RESTORE\n"
                "PIR -> NodeRuntime NodeMessage sent EventKey=room:10:1\n"
                "Authenticated Application Durable ACK EventKey=room:10:1\n"
                "EventKey=room:10:1 retired pending=0\nProcessed")
        self.assertEqual(motion.evaluate_motion_evidence(real, real)[0], "PASS")
        mac_only = "BAT_SLEEP_WAKE cause=GPIO gpio4=1 BAT_SLEEP_RESTORE PIR -> NodeRuntime EventKey=room:10:1 MAC send success"
        self.assertEqual(motion.evaluate_motion_evidence(mac_only, mac_only)[0], "BLOCKED")

    def test_sensitive_uart_fields_are_redacted(self):
        self.assertIn("[REDACTED]", common.redact("installer_code=abc123"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
