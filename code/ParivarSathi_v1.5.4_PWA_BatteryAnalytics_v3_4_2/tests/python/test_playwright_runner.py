"""Socket-free diagnostics for the mandatory browser runner."""
import errno
import subprocess
import unittest
from unittest.mock import Mock, patch

from scripts.run_playwright_gate import (
    BASE,
    LAB_PORT,
    assert_lab_port_available,
    lab_command,
    playwright_environment,
    terminate_process_group,
    validate_base_url,
    wait_for_port_available,
)


class PlaywrightRunnerTest(unittest.TestCase):
    @patch("scripts.run_playwright_gate.socket.socket")
    def test_browser_port_conflict_is_immediate_setup_error(self, socket_factory):
        socket_factory.return_value.__enter__.return_value.bind.side_effect = OSError(errno.EADDRINUSE, "occupied")
        with self.assertRaisesRegex(RuntimeError, r"ENVIRONMENT_BLOCKED: 127.0.0.1:8765 is already occupied"):
            assert_lab_port_available(port=8765)

    @patch("scripts.run_playwright_gate.socket.socket")
    def test_playwright_port_conflict_is_immediate_setup_error(self, socket_factory):
        socket_factory.return_value.__enter__.return_value.bind.side_effect = OSError(errno.EADDRINUSE, "occupied")
        with self.assertRaisesRegex(RuntimeError, r"ENVIRONMENT_BLOCKED: 127.0.0.1:8766 is already occupied"):
            assert_lab_port_available(port=LAB_PORT)

    @patch("scripts.run_playwright_gate.socket.socket")
    def test_sandbox_bind_denial_has_manual_gate_command(self, socket_factory):
        socket_factory.return_value.__enter__.return_value.bind.side_effect = OSError(errno.EPERM, "denied")
        with self.assertRaisesRegex(RuntimeError, r"run make release-gate-final in the normal local terminal"):
            assert_lab_port_available(port=LAB_PORT)

    @patch("scripts.run_playwright_gate.time.sleep")
    @patch("scripts.run_playwright_gate.time.monotonic", side_effect=[0.0, 0.1])
    @patch("scripts.run_playwright_gate.socket.socket")
    def test_wait_for_port_available_retries_actual_bind_probe(self, socket_factory, _clock, sleep):
        probe = socket_factory.return_value.__enter__.return_value
        probe.bind.side_effect = [OSError(errno.EADDRINUSE, "closing"), None]
        wait_for_port_available(timeout=5, interval=0.05)
        self.assertEqual(probe.bind.call_count, 2)
        sleep.assert_called_once_with(0.05)

    @patch("scripts.run_playwright_gate.os.killpg")
    def test_terminate_process_group_reaps_private_lab(self, killpg):
        proc = Mock()
        proc.pid = 1234
        proc.poll.return_value = None
        proc.communicate.return_value = ("lab output", None)
        self.assertEqual(terminate_process_group(proc), "lab output")
        killpg.assert_called_once()
        proc.communicate.assert_called_once_with(timeout=5.0)

    @patch("scripts.run_playwright_gate.os.killpg")
    def test_terminate_process_group_escalates_and_reaps_after_timeout(self, killpg):
        proc = Mock()
        proc.pid = 1234
        proc.poll.return_value = None
        proc.communicate.side_effect = [
            subprocess.TimeoutExpired("lab", 5.0),
            ("forced output", None),
        ]
        self.assertEqual(terminate_process_group(proc), "forced output")
        self.assertEqual(killpg.call_count, 2)
        proc.communicate.assert_any_call(timeout=5.0)
        proc.communicate.assert_any_call()

    @patch("scripts.run_playwright_gate.time.monotonic", return_value=0.0)
    @patch("scripts.run_playwright_gate.socket.socket")
    def test_wait_for_port_available_reports_internal_listener_after_bound(self, socket_factory, _clock):
        socket_factory.return_value.__enter__.return_value.bind.side_effect = OSError(errno.EADDRINUSE, "still bound")
        with self.assertRaisesRegex(RuntimeError, r"VALIDATION_HARNESS_ERROR: owned lab did not release"):
            wait_for_port_available(timeout=0, interval=0)

    def test_playwright_base_url_targets_its_dedicated_port(self):
        self.assertNotEqual(LAB_PORT, 8765)
        self.assertEqual(BASE, "http://127.0.0.1:8766")
        self.assertEqual(lab_command(), ["python3", "tools/sim/local_lab.py", "--port", "8766"])
        self.assertEqual(playwright_environment()["PWA_BASE_URL"], BASE)
        validate_base_url(f"http://127.0.0.1:{LAB_PORT}")
        with self.assertRaisesRegex(RuntimeError, r"PWA_BASE_URL must target 127.0.0.1:8766"):
            validate_base_url("http://127.0.0.1:8765")


if __name__ == "__main__":
    unittest.main()
