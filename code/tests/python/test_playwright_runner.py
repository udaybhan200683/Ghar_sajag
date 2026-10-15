"""Socket-free diagnostics for the mandatory browser runner."""
import errno
import os
import select
import socket
import subprocess
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

from scripts.run_playwright_gate import (
    BASE,
    LAB_PORT,
    LabPortOccupiedError,
    assert_lab_port_available,
    lab_command,
    playwright_environment,
    port_start_lock,
    select_lab_port,
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
        probe.setsockopt.assert_called_with(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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
        self.assertEqual(proc.communicate.call_count, 2)

    @patch("scripts.run_playwright_gate.time.monotonic", return_value=0.0)
    @patch("scripts.run_playwright_gate.socket.socket")
    def test_wait_for_port_available_reports_internal_listener_after_bound(self, socket_factory, _clock):
        socket_factory.return_value.__enter__.return_value.bind.side_effect = OSError(errno.EADDRINUSE, "still bound")
        with self.assertRaisesRegex(RuntimeError, r"VALIDATION_HARNESS_ERROR: listener still holds"):
            wait_for_port_available(timeout=0, interval=0)

    @patch("scripts.run_playwright_gate.os.killpg")
    def test_terminate_process_group_reports_unreaped_owned_group_after_kill(self, killpg):
        proc = Mock()
        proc.pid = 1234
        proc.poll.return_value = None
        proc.communicate.side_effect = [
            subprocess.TimeoutExpired("lab", 5.0),
            subprocess.TimeoutExpired("lab", 5.0),
        ]
        with self.assertRaisesRegex(RuntimeError, r"did not terminate within 5s after SIGKILL"):
            terminate_process_group(proc)
        self.assertEqual(killpg.call_count, 2)

    def test_playwright_base_url_targets_its_dedicated_port(self):
        self.assertNotEqual(LAB_PORT, 8765)
        self.assertEqual(BASE, "http://127.0.0.1:8766")
        self.assertEqual(lab_command(), ["python3", "tools/sim/local_lab.py", "--port", "8766"])
        environment = playwright_environment()
        self.assertEqual(environment["PWA_BASE_URL"], BASE)
        self.assertEqual(
            environment["NODE_PATH"].split(os.pathsep)[0],
            str(Path(__file__).resolve().parents[2] / "frontend" / "node_modules"),
        )
        validate_base_url(f"http://127.0.0.1:{LAB_PORT}")
        with self.assertRaisesRegex(RuntimeError, r"PWA_BASE_URL must target 127.0.0.1:8766"):
            validate_base_url("http://127.0.0.1:8765")

    def test_occupied_default_selects_safe_alternate_only_when_automatic(self):
        def port_probe(_host, port):
            if port == 8766:
                raise LabPortOccupiedError("default occupied")
        with patch(
            "scripts.run_playwright_gate.assert_lab_port_available",
            side_effect=port_probe,
        ), patch("scripts.run_playwright_gate.ephemeral_lab_port", return_value=49152):
            self.assertEqual(select_lab_port(8766, allow_alternate=True), 49152)
            with self.assertRaisesRegex(LabPortOccupiedError, "default occupied"):
                select_lab_port(8766, allow_alternate=False)

    def test_alternate_port_is_shared_by_lab_and_browser_endpoint(self):
        port = 49152
        base = f"http://127.0.0.1:{port}"
        self.assertEqual(lab_command(port), ["python3", "tools/sim/local_lab.py", "--port", str(port)])
        validate_base_url(base, port)
        environment = playwright_environment(base, port)
        self.assertEqual(environment["PWA_BASE_URL"], base)
        with self.assertRaisesRegex(RuntimeError, r"must target 127.0.0.1:8766"):
            validate_base_url(base, 8766)

    def test_concurrent_worktree_startup_waits_for_shared_port_lock(self):
        script = (
            "from scripts.run_playwright_gate import port_start_lock; "
            "print('WAITING', flush=True); "
            "lock=port_start_lock(); lock.__enter__(); "
            "print('ACQUIRED', flush=True); lock.__exit__(None, None, None)"
        )
        proc = None
        try:
            with port_start_lock():
                proc = subprocess.Popen(
                    [os.sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[2],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                )
                ready, _, _ = select.select([proc.stdout], [], [], 3)
                self.assertTrue(ready, "child did not start its port-lock check")
                self.assertEqual(proc.stdout.readline().strip(), "WAITING")
                ready, _, _ = select.select([proc.stdout], [], [], 0.1)
                self.assertFalse(ready, "concurrent gate acquired the startup lock early")
            remainder, _ = proc.communicate(timeout=3)
            self.assertIn("ACQUIRED", remainder)
        finally:
            if proc is not None and proc.poll() is None:
                proc.kill()
                proc.communicate()


if __name__ == "__main__":
    unittest.main()
