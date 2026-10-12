"""Focused Phase 3B concurrent API and household-isolation regression."""
import unittest

from tools.stress.run_concurrency import (
    DUPLICATES_PER_HOME,
    EVENTS_PER_HOME,
    HOME,
    HOME_B,
    REJECTIONS_PER_HOME,
    run,
)


class Phase3BConcurrencyTest(unittest.TestCase):
    def test_bounded_concurrent_api_load_and_household_isolation(self):
        result = run(seed=30401, workers=6)
        self.assertEqual(result["correctness_gate"]["status"], "PASS", result)
        self.assertEqual(result["counts"]["accepted_by_home"], {
            HOME: EVENTS_PER_HOME, HOME_B: EVENTS_PER_HOME,
        })
        self.assertEqual(result["counts"]["duplicates_by_home"], {
            HOME: DUPLICATES_PER_HOME, HOME_B: DUPLICATES_PER_HOME,
        })
        self.assertEqual(result["counts"]["rejected_by_home"], {
            HOME: REJECTIONS_PER_HOME, HOME_B: REJECTIONS_PER_HOME,
        })
        self.assertEqual(result["sqlite_busy_or_lock_failures"], [])
        self.assertEqual(result["diagnostics"]["worker_threads_after_cleanup"], [])
        self.assertTrue(result["diagnostics"]["simulator_exited"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
