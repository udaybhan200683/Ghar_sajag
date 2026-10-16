from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/hil"))

import gs40_qualification as qualification


class GS40QualificationRunnerTests(unittest.TestCase):
    def setUp(self):
        self.registry = qualification.load_registry()
        self.fixture = qualification.load_mock_fixture()
        self.config = qualification.load_json(qualification.CONFIG_PATH)

    def test_case_registry_has_seven_cases_and_six_physical_links(self):
        self.assertEqual([case["id"] for case in self.registry["cases"]], qualification.EXPECTED_CASE_IDS)
        self.assertEqual(sum(bool(case["physical_id"]) for case in self.registry["cases"]), 6)
        self.assertIsNone(self.registry["cases"][-1]["physical_id"])

    def test_TC01_300_second_heartbeat_has_six_unique_authenticated_opportunities(self):
        checks, physical = qualification.evaluate_mock("GS40-TC01", self.fixture, self.config)
        self.assertEqual([row["result"] for row in checks], ["PASS"] * 4)
        self.assertIsNone(physical)

    def test_TC02_mac_success_does_not_replace_authenticated_event_contact(self):
        checks, _ = qualification.evaluate_mock("GS40-TC02", self.fixture, self.config)
        self.assertEqual([row["result"] for row in checks], ["PASS"] * 3)

    def test_TC03_910_second_expiry_distinguishes_node_hub_and_wan(self):
        checks, physical = qualification.evaluate_mock("GS40-TC03", self.fixture, self.config)
        self.assertEqual([row["result"] for row in checks], ["PASS"] * 3)
        self.assertEqual(physical, "BLOCKED")

    def test_TC04_rejoin_preserves_eventkeys_pending_replay_fence_and_order(self):
        checks, physical = qualification.evaluate_mock("GS40-TC04", self.fixture, self.config)
        self.assertEqual([row["result"] for row in checks], ["PASS"] * 4)
        self.assertEqual(physical, "BLOCKED")

    def test_TC05_profiles_and_untrusted_identity_are_explicit(self):
        checks, physical = qualification.evaluate_mock("GS40-TC05", self.fixture, self.config)
        self.assertEqual([row["result"] for row in checks], ["PASS"] * 3)
        self.assertEqual(physical, "BLOCKED")

    def test_TC06_pwa_online_offline_unknown_and_resident_inactivity_are_separate(self):
        checks, physical = qualification.evaluate_mock("GS40-TC06", self.fixture, self.config)
        self.assertEqual([row["result"] for row in checks], ["PASS"] * 4)
        self.assertEqual(physical, "NOT_RUN")

    def test_TC07_sleep_usb_loss_is_observer_loss_and_faults_fail_stop(self):
        checks, physical = qualification.evaluate_mock("GS40-TC07", self.fixture, self.config)
        self.assertEqual([row["result"] for row in checks], ["PASS"] * 5)
        self.assertEqual(physical, "NOT_RUN")

    def test_11158_capture_replay_detects_boot_and_preserves_historical_provenance(self):
        fixture = qualification.CAPTURE_REPLAY_FIXTURE
        checks, detail = qualification.analyze_s3_capture(fixture)
        self.assertEqual([row["result"] for row in checks], ["PASS"] * 6)
        self.assertEqual(detail["source_jira_comment"], "11158")
        self.assertEqual(detail["source_capture_sha256"], "2ff1dab2e452883af97a3eec649f5d0b7da6984dc333b692d6c17af957cc2bc6")
        self.assertEqual(detail["reset_banner"], "POWERON")
        self.assertEqual(detail["reset_cause"], "UNPROVEN_SERIAL_OPEN_CAUSALITY")
        self.assertFalse(detail["application_level_gs40_evidence_present"])
        self.assertEqual(detail["historical_open_attempts"], 1)
        self.assertEqual(detail["historical_transmit_bytes"], 0)

    def test_capture_fault_classifier_stops_on_transport_truncation_reset_and_gap(self):
        cases = [
            (["not-json"], None, "TRUNCATED_LOG"),
            ([json.dumps({"kind": "transport_lost"})], None, "TRANSPORT_LOSS"),
            ([json.dumps({"kind": "anomaly_stop", "reason": "reset banner"})], None, "RESET_BANNER"),
            ([json.dumps({"host_utc": "2026-01-01T00:00:02Z"}),
              json.dumps({"host_utc": "2026-01-01T00:00:01Z"})], None, "TIMESTAMP_GAP"),
            ([json.dumps({"host_utc": "2026-01-01T00:00:00Z"}),
              json.dumps({"host_utc": "2026-01-01T00:00:03Z"})], 1.0, "TIMESTAMP_GAP"),
        ]
        for lines, max_gap, expected in cases:
            with self.subTest(expected=expected, max_gap=max_gap):
                classification, _ = qualification.classify_capture_lines(lines, max_gap_seconds=max_gap)
                self.assertEqual(classification, expected)

    def test_live_mode_blocks_without_any_device_access_or_physical_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_parent = Path(temporary) / "reports"
            output_parent.mkdir()
            with patch.object(qualification.subprocess, "check_output", return_value="test-head") as git_call:
                status, run_dir, reports = qualification.run(
                    "live", ["GS40-TC01", "GS40-TC07"], output_parent=output_parent
                )
            self.assertEqual(status, 3)
            self.assertTrue(all(report["verdict"] == "BLOCKED" for report in reports))
            self.assertTrue(all(report["physical_status"] != "PHYSICAL_PASS" for report in reports))
            commands = [call.args[0] for call in git_call.call_args_list]
            self.assertTrue(commands)
            self.assertTrue(all(command[0] == "git" and command[1] in {"rev-parse", "branch"} for command in commands))
            for report in reports:
                self.assertEqual(report["hardware_actions"]["serial_open_attempts"], 0)
                self.assertEqual(report["hardware_actions"]["usb_reattach_attempts"], 0)
            self.assertEqual(len(list(run_dir.rglob("*.json"))), 3)  # two case reports plus run index
            self.assertEqual(len(list(run_dir.rglob("*.md"))), 2)

    def test_report_output_is_immutable_and_has_json_and_markdown(self):
        case = self.registry["cases"][0]
        checks, _ = qualification.evaluate_mock(case["id"], self.fixture, self.config)
        report = qualification.make_report(case, "mock", "HOST_PASS", checks,
                                           physical="NOT_RUN", physical_reason="No physical run.")
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "case"
            json_path, markdown_path = qualification.write_case_report(target, report)
            parsed = json.loads(json_path.read_text())
            self.assertEqual(parsed["verdict"], "HOST_PASS")
            self.assertEqual(parsed["physical_status"], "NOT_RUN")
            self.assertTrue(markdown_path.is_file())
            with self.assertRaises(FileExistsError):
                qualification.write_case_report(target, report)


if __name__ == "__main__":
    unittest.main()
