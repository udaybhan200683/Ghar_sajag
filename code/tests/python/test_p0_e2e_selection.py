import unittest

from tests.python.run_full_product_p0_e2e import parse_scenario_selection


class P0ScenarioSelectionTests(unittest.TestCase):
    def test_omitted_selection_means_all_registered_scenarios(self):
        self.assertIsNone(parse_scenario_selection(None))

    def test_known_selection_is_exact_and_deduplicated(self):
        self.assertEqual(parse_scenario_selection("P0-E2E-001,P0-E2E-017"),
                         {"P0-E2E-001", "P0-E2E-017"})

    def test_unknown_duplicate_or_empty_selection_fails_closed(self):
        for value in ("P0-E2E-999", "P0-E2E-001,P0-E2E-001", "P0-E2E-001,", ""):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_scenario_selection(value)


if __name__ == "__main__":
    unittest.main()
