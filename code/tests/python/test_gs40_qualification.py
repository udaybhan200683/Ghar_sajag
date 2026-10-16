from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
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

    def observation_bundle(self, *, age_seconds=10, provenance="SYNTHETIC_DETERMINISTIC_FIXTURE",
                           hub_reachable=True, internet_connected=True, trusted=True,
                           identity="c3-146393c5d158", profile_known=True,
                           profile="configured", authenticated=True, pwa_snapshot_age=0):
        captured = datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc)
        stamp = lambda age: (captured - timedelta(seconds=age)).isoformat().replace("+00:00", "Z")
        contact = None
        if identity is not None:
            contact = {"authenticated": authenticated, "identity": identity, "session_id": "sess-7",
                       "contact_id": "health-8", "received_at_utc": stamp(age_seconds)}
        node = {"identity": identity, "trusted_identity": trusted, "observed_at_utc": stamp(0),
                "last_authenticated_contact": contact}
        offline_after = {"configured": 910, "legacy_60": 190, "legacy_120": 310}.get(profile)
        hub_status = "ONLINE" if trusted and profile_known and contact and authenticated and offline_after is not None and age_seconds <= offline_after else \
                     "OFFLINE" if trusted and profile_known and contact and authenticated and offline_after is not None and age_seconds > offline_after else "UNKNOWN"
        if not hub_reachable:
            hub_status = "UNKNOWN"
        downstream_status = hub_status if hub_reachable and internet_connected else "UNKNOWN"
        downstream_coverage = "COVERED" if downstream_status == "ONLINE" else "UNKNOWN"
        pwa_status = downstream_status if pwa_snapshot_age <= 190 else "UNKNOWN"
        pwa_coverage = "COVERED" if pwa_status == "ONLINE" else "UNKNOWN"
        hub = {"identity": identity, "reachable": hub_reachable,
               "internet_connected": internet_connected, "observed_at_utc": stamp(0),
               "last_backend_contact_at_utc": stamp(10), "node_status": hub_status,
               "source_contact": json.loads(json.dumps(contact)) if contact is not None and authenticated else None}
        backend = {"identity": identity, "reachable": True, "observed_at_utc": stamp(0),
                   "node_status": downstream_status, "coverage_status": downstream_coverage,
                   "source_contact": json.loads(json.dumps(contact)) if contact is not None and authenticated else None}
        pwa = {"identity": identity, "reachable": True, "observed_at_utc": stamp(0),
               "backend_snapshot_observed_at_utc": stamp(pwa_snapshot_age),
               "node_status": pwa_status, "coverage_status": pwa_coverage,
               "source_contact": json.loads(json.dumps(contact)) if contact is not None and authenticated else None}
        config = json.loads(json.dumps(self.config))
        if profile_known:
            config["deployment_profiles"][identity] = profile
        else:
            config["deployment_profiles"].pop(identity, None)
        return {"schema_version": 1, "provenance": provenance,
                "captured_at_utc": stamp(0), "node": node, "hub": hub,
                "backend": backend, "pwa": pwa}, config

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
            self.assertTrue(all(report["provenance"]["live_observation_source_inventory"][
                "production_path_complete"] is False for report in reports))
            self.assertTrue(all("s3_instantiates_cloudsync_worker" in report["failure"]
                                for report in reports))
            commands = [call.args[0] for call in git_call.call_args_list]
            self.assertTrue(commands)
            self.assertTrue(all(command[0] == "git" and command[1] in {"rev-parse", "branch"} for command in commands))
            for report in reports:
                self.assertEqual(report["hardware_actions"]["serial_open_attempts"], 0)
                self.assertEqual(report["hardware_actions"]["usb_reattach_attempts"], 0)
            self.assertEqual(len(list(run_dir.rglob("*.json"))), 3)  # two case reports plus run index
            self.assertEqual(len(list(run_dir.rglob("*.md"))), 2)

    def test_source_audit_distinguishes_authenticated_radio_ingress_from_missing_cloud_path(self):
        inventory = qualification.inspect_live_observation_sources()
        checks = inventory["checks"]
        self.assertTrue(checks["hub_authenticates_and_records_node_health"])
        self.assertFalse(checks["cloudsync_has_node_health_publication"])
        self.assertFalse(checks["s3_instantiates_cloudsync_worker"])
        self.assertFalse(checks["s3_has_trusted_cloud_authority_source"])
        self.assertFalse(checks["backend_has_authenticated_node_health_ingest"])
        self.assertFalse(checks["backend_snapshot_projects_node_health"])
        self.assertFalse(checks["caregiver_pwa_projects_node_health"])
        self.assertTrue(checks["backend_event_api_is_local_host_adapter"])
        self.assertFalse(inventory["production_path_complete"])
        self.assertEqual(inventory["device_access"], "NONE")
        self.assertFalse(inventory["physical_pass_claimed"])

    def test_observation_adapter_correlates_300_910_status_and_separates_connectivity(self):
        cases = [
            ("online", {"age_seconds": 910}, "ONLINE", "COVERED"),
            ("silent-node", {"age_seconds": 911}, "OFFLINE", "UNKNOWN"),
            ("hub-disconnected", {"hub_reachable": False}, "UNKNOWN", "UNKNOWN"),
            ("internet-outage", {"internet_connected": False}, "UNKNOWN", "UNKNOWN"),
            ("unknown-profile", {"profile_known": False}, "UNKNOWN", "UNKNOWN"),
            ("untrusted-identity", {"trusted": False}, "UNKNOWN", "UNKNOWN"),
            ("missing-contact", {"authenticated": False}, "UNKNOWN", "UNKNOWN"),
            ("stale-pwa-snapshot", {"pwa_snapshot_age": 191}, "UNKNOWN", "UNKNOWN"),
            ("legacy-60-expiry", {"profile": "legacy_60", "age_seconds": 191}, "OFFLINE", "UNKNOWN"),
            ("legacy-120-expiry", {"profile": "legacy_120", "age_seconds": 311}, "OFFLINE", "UNKNOWN"),
        ]
        for label, options, expected_status, expected_coverage in cases:
            with self.subTest(case=label):
                bundle, config = self.observation_bundle(**options)
                result = qualification.assess_observation_bundle(bundle, config)
                self.assertEqual(result["verdict"], "HOST_PASS")
                self.assertFalse(result["physical_pass_claimed"])
                self.assertEqual(result["observed_caregiver_status"], expected_status)
                self.assertEqual(result["observed_caregiver_coverage"], expected_coverage)

    def test_observation_adapter_rejects_uncorrelated_or_live_unattested_status(self):
        bundle, config = self.observation_bundle()
        bundle["pwa"]["source_contact"]["session_id"] = "wrong-session"
        result = qualification.assess_observation_bundle(bundle, config)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertTrue(any(row["check"] == "pwa_contact_correlation" and row["result"] == "FAIL"
                            for row in result["assertions"]))

        live, config = self.observation_bundle(provenance="LIVE_CURRENT_TARGET")
        live_result = qualification.assess_observation_bundle(live, config)
        self.assertEqual(live_result["verdict"], "BLOCKED")
        self.assertEqual(live_result["failure"], "LIVE_PROVIDER_ATTESTATION_UNAVAILABLE")
        self.assertFalse(live_result["physical_pass_claimed"])

        bundle, config = self.observation_bundle()
        config["node_health"]["heartbeat_interval_seconds"] = True
        malformed_config = qualification.assess_observation_bundle(bundle, config)
        self.assertEqual(malformed_config["verdict"], "BLOCKED")
        self.assertIn("effective NodeHealth configuration is invalid", malformed_config["failure"])

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
