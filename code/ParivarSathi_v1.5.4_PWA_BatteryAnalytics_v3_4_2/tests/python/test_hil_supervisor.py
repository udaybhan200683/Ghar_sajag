from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.hil import phase1, qualify
from tools.hil.usb_attach import (FixtureBlocked, FixtureFailed,
                                  ensure_verified_fixture,
                                  invoke_windows_helper)


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += max(seconds, 0.01)


class HilWslSupervisorTest(unittest.TestCase):
    def fixture_case(self, initial_error: str):
        calls = {"discover": 0, "helper": 0}

        def discover():
            calls["discover"] += 1
            if calls["discover"] == 1:
                raise RuntimeError(initial_error)
            return {"hub": object(), "c3": object()}

        result = ensure_verified_fixture(
            discover, helper_invoker=lambda: calls.__setitem__("helper", calls["helper"] + 1),
            sleeper=lambda _: None)
        self.assertEqual(set(result), {"hub", "c3"})
        self.assertEqual(calls, {"discover": 2, "helper": 1})

    def test_01_both_visible_skips_windows_helper(self):
        helper = mock.Mock(side_effect=AssertionError("helper must not run"))
        devices = ensure_verified_fixture(lambda: {"hub": 1, "c3": 2},
                                           helper_invoker=helper)
        self.assertEqual(devices, {"hub": 1, "c3": 2})
        helper.assert_not_called()

    def test_02_hub_missing_invokes_helper_then_verifies(self):
        self.fixture_case("expected exactly one hub MAC; found 0")

    def test_03_c3_missing_invokes_helper_then_verifies(self):
        self.fixture_case("expected exactly one c3 MAC; found 0")

    def test_04_both_missing_invokes_helper_then_verifies(self):
        self.fixture_case("no serial candidates reported by pyserial")

    def test_05_changed_busid_is_owned_by_minimal_helper(self):
        helper = (qualify.REPO / "tools/hil/ensure-usb-attached.ps1").read_text()
        self.assertIn("$acceptedBus[$role] = $device.BusId", helper)
        self.assertIn("changed BUSID and informational stderr", helper)
        self.assertIn("Get-UsbipdDevices", helper)

    def test_06_07_ambiguous_hub_and_c3_fail_closed(self):
        helper = (qualify.REPO / "tools/hil/ensure-usb-attached.ps1").read_text()
        self.assertIn("if ($matches.Count -ne 1)", helper)
        self.assertIn("$($expected.Role) USB identity is ambiguous", helper)
        self.assertEqual(helper.count("Role = 'Hub'"), 1)
        self.assertEqual(helper.count("Role = 'C3'"), 1)

    def test_08_not_shared_is_explicitly_blocked(self):
        helper = (qualify.REPO / "tools/hil/ensure-usb-attached.ps1").read_text()
        self.assertIn("BLOCKED_NEEDS_USBIPD_BIND", helper)

    def test_09_nonzero_helper_blocks_qualification(self):
        def runner(*_args, **_kwargs):
            return subprocess.CompletedProcess([], 9, "", "usbipd failed")

        with self.assertRaisesRegex(FixtureBlocked, "exit=9.*usbipd failed"):
            invoke_windows_helper(runner=runner)

    def test_10_helper_success_without_wsl_device_times_out(self):
        clock = Clock()
        with self.assertRaisesRegex(FixtureBlocked, "readiness timeout"):
            ensure_verified_fixture(
                lambda: (_ for _ in ()).throw(RuntimeError("expected hub missing")),
                timeout=1, interval=.25, helper_invoker=lambda: None,
                monotonic=clock.monotonic, sleeper=clock.sleep)
        self.assertLessEqual(clock.now, 1.0)

    def test_11_visible_wrong_mac_is_failure(self):
        clock = Clock()
        with self.assertRaisesRegex(FixtureFailed, "MAC is not"):
            ensure_verified_fixture(
                lambda: (_ for _ in ()).throw(RuntimeError("MAC is not a configured Hub or C3 identity")),
                timeout=.5, interval=.25, helper_invoker=lambda: None,
                monotonic=clock.monotonic, sleeper=clock.sleep)

    def test_stale_tty_reconciles_then_identity_retries_on_new_tty(self):
        clock = Clock(); calls = {"presence": 0, "identity": 0, "helper": 0}
        def presence():
            calls["presence"] += 1
            return "/dev/ttyACM1" if calls["presence"] > 1 else "/dev/ttyACM0"
        def identity():
            calls["identity"] += 1
            if calls["identity"] == 1:
                raise RuntimeError("IDENTITY_PROBE_USB_DISAPPEARED port=/dev/ttyACM0")
            return {"hub": "verified", "c3": "verified"}
        result = ensure_verified_fixture(
            identity, presence_probe=presence, timeout=2, interval=.1,
            helper_invoker=lambda: calls.__setitem__("helper", calls["helper"] + 1),
            monotonic=clock.monotonic, sleeper=clock.sleep)
        self.assertEqual(result["c3"], "verified")
        self.assertEqual(calls["helper"], 1)
        self.assertEqual(calls["identity"], 2)

    def test_identity_probe_retry_exhaustion_is_specific_and_bounded(self):
        clock = Clock()
        with self.assertRaisesRegex(FixtureBlocked, "IDENTITY_REVERIFY_FAILED.*IDENTITY_PROBE_TIMEOUT"):
            ensure_verified_fixture(
                lambda: (_ for _ in ()).throw(RuntimeError("IDENTITY_PROBE_TIMEOUT port=/dev/ttyACM0")),
                presence_probe=lambda: {"hub": "stable", "c3": "stable"}, timeout=.3, interval=.1,
                helper_invoker=lambda: None, monotonic=clock.monotonic, sleeper=clock.sleep)
        self.assertLessEqual(clock.now, .4)

    def test_stable_verified_fixture_runs_authoritative_discovery_once(self):
        with mock.patch("tools.hil.qualify.stable_fixture_usb_snapshot") as stable, mock.patch(
                "tools.hil.qualify.discover", return_value=({"hub": "verified", "c3": "verified"}, [])) as discover:
            devices = qualify.verify_fixture()
        self.assertEqual(devices["hub"], "verified")
        stable.assert_called_once()
        discover.assert_called_once()

    def run_supervisor(self, failures=None, fixture_error=None, stages=None):
        failures = failures or {}
        calls = []
        output = []

        def stage(name):
            calls.append(name)
            return failures.get(name, 0)

        def fixture():
            calls.append("usb-fixture")
            if fixture_error:
                raise fixture_error

        supervisor = qualify.QualificationSupervisor(
            stage_runner=stage, fixture_runner=fixture,
            report_reader=lambda: "/real/evidence/report", output=output.append,
            stages=stages)
        return supervisor.run(), calls, supervisor.statuses, output

    def test_checkpoint_smoke_refreshes_setup_before_preflight_and_campaign(self):
        code, calls, states, _ = self.run_supervisor(stages=qualify.CHECKPOINT_SMOKE_STAGES)
        self.assertEqual(code, 0)
        self.assertEqual(calls, ["usb-fixture", "hil-setup", "hil-preflight", "hil-smoke"])
        self.assertTrue(all(value == "PASS" for value in states.values()))

    def test_checkpoint_smoke_setup_failure_blocks_preflight_and_hardware(self):
        code, calls, states, _ = self.run_supervisor(
            failures={"hil-setup": 1}, stages=qualify.CHECKPOINT_SMOKE_STAGES)
        self.assertEqual(code, 1)
        self.assertEqual(calls, ["usb-fixture", "hil-setup"])
        self.assertEqual(states["hil-preflight"], "BLOCKED")
        self.assertEqual(states["hil-smoke"], "BLOCKED")

    def test_checkpoint_smoke_preflight_failure_blocks_hardware(self):
        code, calls, states, _ = self.run_supervisor(
            failures={"hil-preflight": 1}, stages=qualify.CHECKPOINT_SMOKE_STAGES)
        self.assertEqual(code, 1)
        self.assertEqual(calls, ["usb-fixture", "hil-setup", "hil-preflight"])
        self.assertEqual(states["hil-smoke"], "BLOCKED")

    def test_checkpoint_fota_refreshes_provenance_before_hardware(self):
        code, calls, states, output = self.run_supervisor(
            stages=qualify.CHECKPOINT_FOTA_STAGES)
        self.assertEqual(code, 0)
        self.assertEqual(calls, ["usb-fixture", "hil-setup", "hil-preflight", "hil-fota"])
        self.assertTrue(all(value == "PASS" for value in states.values()))
        self.assertTrue(any("/real/evidence/report" in line for line in output))

    def test_checkpoint_fota_stale_preflight_blocks_transfer(self):
        code, calls, states, _ = self.run_supervisor(
            failures={"hil-preflight": 1}, stages=qualify.CHECKPOINT_FOTA_STAGES)
        self.assertEqual(code, 1)
        self.assertEqual(calls, ["usb-fixture", "hil-setup", "hil-preflight"])
        self.assertEqual(states["hil-fota"], "BLOCKED")

    def test_12_validation_fast_failure_blocks_every_later_stage(self):
        code, calls, states, _ = self.run_supervisor({"validation-fast": 3})
        self.assertEqual(code, 1)
        self.assertEqual(calls, ["validation-fast"])
        self.assertEqual(states["release-gate-final"], "BLOCKED")
        self.assertEqual(states["hil-regression"], "BLOCKED")

    def test_13_release_gate_failure_blocks_real_hardware(self):
        code, calls, states, _ = self.run_supervisor({"release-gate-final": 4})
        self.assertEqual(code, 1)
        self.assertEqual(calls, ["validation-fast", "release-gate-final"])
        self.assertEqual(states["usb-fixture"], "BLOCKED")

    def test_14_smoke_failure_blocks_regression(self):
        code, calls, states, _ = self.run_supervisor({"hil-smoke": 5})
        self.assertEqual(code, 1)
        self.assertNotIn("hil-regression", calls)
        self.assertEqual(states["hil-regression"], "BLOCKED")

    def test_15_all_mandatory_stages_pass_in_order(self):
        code, calls, states, output = self.run_supervisor()
        self.assertEqual(code, 0)
        self.assertEqual(calls, list(qualify.STAGES))
        self.assertTrue(all(value == "PASS" for value in states.values()))
        self.assertIn("OVERALL              PASS", output)
        self.assertIn("REPORT               /real/evidence/report", output)

    def test_16_zero_stage_execution_fails_closed(self):
        with mock.patch.object(qualify, "STAGES", ()):
            output = []
            supervisor = qualify.QualificationSupervisor(output=output.append)
            self.assertEqual(supervisor.run(), 1)
            self.assertIn("FAIL_NO_QUALIFICATION_EXECUTED", output)

    def test_17_informational_helper_stderr_is_not_failure(self):
        observed = {}

        def runner(command, **kwargs):
            observed.update(command=command, kwargs=kwargs)
            return subprocess.CompletedProcess([], 0, "", "usbipd: info: attached")

        result = invoke_windows_helper(runner=runner)
        self.assertEqual(result.returncode, 0)
        self.assertIn("info", result.stderr)
        self.assertIn("[Console]::In.ReadToEnd()", observed["command"][-1])
        self.assertIn("Ensure-UsbAttached", observed["kwargs"]["input"])
        self.assertTrue(all("wsl.localhost" not in argument for argument in observed["command"]))

    def test_18_stage_runner_uses_repo_not_caller_working_directory(self):
        observed = {}

        def fake_run(command, cwd):
            observed.update(command=command, cwd=cwd)
            return subprocess.CompletedProcess(command, 0)

        with tempfile.TemporaryDirectory() as directory, mock.patch(
                "tools.hil.qualify.subprocess.run", side_effect=fake_run):
            old = Path.cwd()
            try:
                os.chdir(directory)
                result = qualify.run_make_stage("validation-fast")
            finally:
                os.chdir(old)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(observed["cwd"], qualify.REPO)

    def test_19_qualification_needs_no_windows_path_conversion(self):
        source = Path(qualify.__file__).read_text() + (qualify.REPO / "code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tools/hil/usb_attach.py").read_text()
        self.assertNotIn("wslpath", source)
        self.assertNotIn("wsl.localhost", source)
        self.assertNotIn("Microsoft.PowerShell.Core", source)

    def test_20_no_powershell_master_orchestration_remains(self):
        legacy = (qualify.REPO / "tools/hil/run-hil.ps1").read_text()
        helper = (qualify.REPO / "tools/hil/ensure-usb-attached.ps1").read_text()
        self.assertIn("deprecated", legacy)
        for forbidden in ("validation-fast", "release-gate-final", "hil-setup",
                          "hil-preflight", "hil-smoke", "hil-regression",
                          "wsl.exe", "Invoke-WslStage", "Wait-ChildProcess"):
            self.assertNotIn(forbidden, helper)
        self.assertNotIn("wsl.exe", legacy)

    def test_fixture_block_produces_blocked_summary_and_exit_two(self):
        code, calls, states, output = self.run_supervisor(
            fixture_error=FixtureBlocked("BLOCKED_NEEDS_USBIPD_BIND"))
        self.assertEqual(code, 2)
        self.assertEqual(calls, ["validation-fast", "release-gate-final", "usb-fixture"])
        self.assertEqual(states["hil-setup"], "BLOCKED")
        self.assertIn("OVERALL              BLOCKED", output)

    def test_runtime_reenumeration_is_wsl_owned_and_reverified(self):
        helper = mock.Mock()
        with mock.patch("tools.hil.phase1.is_wsl", return_value=True), mock.patch(
                "tools.hil.phase1._verified_runtime_port",
                side_effect=[RuntimeError("tty disappeared"), "/dev/ttyACM9"]) as verify:
            port = phase1.runtime_port({}, "c3", helper_invoker=helper,
                                       grace_seconds=0, sleeper=lambda _: None)
        self.assertEqual(port, "/dev/ttyACM9")
        helper.assert_called_once_with()
        self.assertEqual(verify.call_count, 2)

    def test_runtime_reappearance_during_grace_skips_windows(self):
        clock = Clock()
        helper = mock.Mock(side_effect=AssertionError("helper must not run"))
        with mock.patch("tools.hil.phase1.is_wsl", return_value=True), mock.patch(
                "tools.hil.phase1._verified_runtime_port",
                side_effect=[RuntimeError("temporary reset"), "/dev/ttyUSB8"]):
            port = phase1.runtime_port({}, "hub", grace_seconds=.5,
                                       helper_invoker=helper,
                                       monotonic=clock.monotonic, sleeper=clock.sleep)
        self.assertEqual(port, "/dev/ttyUSB8")
        helper.assert_not_called()


if __name__ == "__main__":
    unittest.main()
