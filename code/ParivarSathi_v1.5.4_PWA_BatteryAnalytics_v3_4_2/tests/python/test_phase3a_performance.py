"""Phase 3A structural budgets and bounded deterministic stress smoke."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.performance.profile_pwa import run_profile
from tools.stress.run_stress import run


class Phase3APerformanceTest(unittest.TestCase):
    def test_static_payload_and_collection_budgets(self):
        result = run_profile(check=True)
        self.assertEqual(result["correctness_gate"]["status"], "PASS", result["correctness_gate"]["failures"])
        self.assertEqual(result["startup"]["reports_requested_initially"], 0)
        self.assertEqual(result["startup"]["full_state_requested_initially"], 0)
        self.assertLessEqual(result["bounds"]["home_recent_events"], 20)
        self.assertEqual(result["bounds"]["notification_history_records"], 20)

    def test_small_stress_profile_is_deterministic_and_bounded(self):
        result = run("SMALL", seed=30401)
        self.assertEqual(result["correctness_gate"]["status"], "PASS", result["correctness_gate"]["checks"])
        self.assertEqual(result["counts"]["accepted"], 120)
        self.assertEqual(result["counts"]["duplicates"], 12)
        self.assertEqual(result["counts"]["rejected"], 6)
        self.assertEqual(result["counts"]["request_failures"], 0)

    def test_large_profiles_require_explicit_opt_in(self):
        profiles = json.loads((ROOT / "tools/stress/profiles.json").read_text())["profiles"]
        self.assertTrue(profiles["LARGE"]["manual_only"])
        self.assertTrue(profiles["EXTENDED"]["manual_only"])
        with self.assertRaisesRegex(ValueError, "manual-only"):
            run("LARGE")

    def test_service_worker_allowlist_has_no_dynamic_api(self):
        source = (ROOT / "tools/sim/pwa/sw.js").read_text()
        self.assertIn("performance_runtime.mjs", source)
        for dynamic in ("/pwa/state", "/pwa/foundation", "/v1/homes", "/reports"):
            self.assertNotIn(dynamic, source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
