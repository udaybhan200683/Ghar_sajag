import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
SPEC_PATH = ROOT / "tests" / "data" / "gs144_workload_spec.json"
NODE_HEALTH_PATH = ROOT / "config" / "node_health.json"


class Gs144WorkloadSpecificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads(SPEC_PATH.read_text())

    def test_product_acceptance_inputs_remain_unapproved(self):
        approved = self.spec["approved_acceptance"]
        self.assertEqual(self.spec["approval_status"], "PRODUCT_DECISION_PENDING")
        self.assertIsNone(approved["approval_comment_id"])
        self.assertIsNone(approved["selected_profile_id"])
        for section in ("battery", "measurement", "service_constraints", "endurance"):
            self.assertTrue(approved[section])
            self.assertTrue(all(value is None for value in approved[section].values()))

    def test_approved_node_health_facts_match_canonical_configuration(self):
        policy = self.spec["approved_policy_facts"]
        canonical = json.loads(NODE_HEALTH_PATH.read_text())
        self.assertEqual(policy["authority"], "GS-D031")
        self.assertEqual(policy["node_health_interval_seconds"],
                         canonical["node_health"]["heartbeat_interval_seconds"])
        self.assertEqual(policy["node_health_piggybacks_on_events"],
                         canonical["node_health"]["piggyback_on_events"])
        self.assertEqual(policy["node_offline_threshold_seconds"],
                         3 * policy["node_health_interval_seconds"] + 10)

    def test_candidate_scenarios_have_explicit_proposed_status_and_consistent_counts(self):
        profiles = self.spec["proposed_scenarios"]
        ids = [profile["id"] for profile in profiles]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(profiles), 7)
        for profile in profiles:
            with self.subTest(profile=profile["id"]):
                self.assertEqual(profile["status"], "PROPOSED_NOT_APPROVED")
                self.assertGreater(profile["window_seconds"], 0)
                motion = profile["motion"]
                self.assertEqual(motion["business_events_emitted"],
                                 motion["immediate_motion_events"] +
                                 motion["aggregated_motion_summaries"])
                self.assertIsNone(motion["timing_distribution"])
                residency = profile["residency"]
                self.assertEqual(residency["awake_seconds_candidate"] +
                                 residency["sleep_seconds_candidate"],
                                 profile["window_seconds"])
                self.assertFalse(residency["measured"])
                self.assertFalse(profile["storage"]["measured"])

    def test_outage_rf_and_physical_measurement_gaps_are_not_filled_by_guesswork(self):
        profiles = {profile["id"]: profile for profile in self.spec["proposed_scenarios"]}
        for profile_id in ("short_hub_absence_15m", "extended_hub_outage_8h",
                           "intermittent_poor_rf_24h"):
            connectivity = profiles[profile_id]["connectivity"]
            self.assertIsNone(connectivity["hub_outage_duration_seconds"])
            self.assertIsNone(connectivity["recovery_period_seconds"])
        measurement_values = self.spec["approved_acceptance"]["measurement"]
        self.assertTrue(all(value is None for value in measurement_values.values()))
        self.assertIn("repeatability_and_uncertainty",
                      self.spec["measurement_fields_required_per_run"])
        self.assertIn("raw_current_voltage_and_event_traces",
                      self.spec["measurement_fields_required_per_run"])


if __name__ == "__main__":
    unittest.main()
