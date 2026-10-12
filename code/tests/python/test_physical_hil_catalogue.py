import csv
import json
import tempfile
import unittest
from pathlib import Path

from validation.physical_hil_catalogue import CATALOGUE, REPO, TRACEABILITY, validate
from validation.component_gate import adjudicate, load_registry, select


class PhysicalHilCatalogueTest(unittest.TestCase):
    def test_catalogue_maps_every_required_implemented_feature(self):
        errors, cases, features, conditional = validate()
        self.assertEqual(errors, [])
        self.assertGreaterEqual(cases, 99)
        self.assertGreater(features, 0)
        self.assertGreater(conditional, 0)

    def test_release_gate_is_registered_outside_software_fast_gates(self):
        registry = json.loads((REPO / "code/validation/suites.json").read_text())
        stage = next(s for s in registry["stages"] if s["id"] == "physical-hil-release-evidence")
        self.assertFalse(stage.get("fast", True))
        self.assertTrue(stage.get("release"))
        self.assertIn("--release", stage["command"])
        self.assertNotIn("physical-hil-release-evidence", [s["id"] for s in registry["stages"] if s.get("fast", True)])
        self.assertIn("physical-hil-release-evidence", {s["id"] for s in select(load_registry(), "release")})
        tooling = next(s for s in registry["stages"] if s["id"] == "hil-tooling")
        self.assertEqual(adjudicate(tooling, {"exit_code": 0, "output": "HIL-USB POWERSHELL CHECK: SKIP - Windows interop unavailable\nRan 7 tests in 0.1s\nOK", "seconds": 0}), "PASS")
        self.assertEqual(adjudicate(tooling, {"exit_code": 0, "output": "SKIP - unexpected\nRan 7 tests in 0.1s\nOK", "seconds": 0}), "FAIL")

    def test_release_check_rejects_current_not_run_evidence(self):
        errors, _, _, _ = validate(require_release=True)
        self.assertTrue(any("release evidence incomplete" in error for error in errors))

    def test_release_checker_accepts_complete_provenance_fixture(self):
        with CATALOGUE.open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            evidence = folder / "evidence.md"
            evidence.write_text("synthetic checker input; not physical evidence\n")
            for row in rows:
                row["EVIDENCE"] = "evidence.md"
                if row["RELEASE_BLOCKING"] == "YES":
                    row["STATUS"] = "PASS"
                    row["SOURCE_HEAD"] = "a" * 40
                    row["IMAGE_SHA256"] = "a" * 64
            catalogue = folder / "catalogue.csv"
            with catalogue.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            errors, _, _, _ = validate(catalogue, TRACEABILITY, require_release=True)
        self.assertEqual(errors, [])

    def test_duplicate_case_id_is_detected(self):
        with CATALOGUE.open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            catalogue = folder / "catalogue.csv"
            with catalogue.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows + [rows[0]])
            errors, _, _, _ = validate(catalogue, TRACEABILITY)
        self.assertIn("test IDs must be nonempty and unique", errors)

    def test_catalogue_status_is_not_promoted_to_physical_pass(self):
        with CATALOGUE.open(newline="") as stream:
            rows = {r["TEST_ID"]: r for r in csv.DictReader(stream)}
        self.assertEqual(rows["HIL-A04"]["STATUS"], "NOT_RUN")
        self.assertEqual(rows["HIL-A05"]["STATUS"], "NOT_RUN")
        self.assertEqual(rows["HIL-A07"]["STATUS"], "PARTIAL")
        self.assertEqual(rows["HIL-PHASE1-LEGACY-71"]["STATUS"], "HISTORICAL_EVIDENCE_ONLY")

    def test_all_legacy_phase1_case_ids_are_individually_catalogued(self):
        with CATALOGUE.open(newline="") as stream:
            ids = {r["TEST_ID"] for r in csv.DictReader(stream)}
        ranges = (("HIL-SMOKE-", 17), ("HIL-RADIO-", 10), ("HIL-OR-", 20),
                  ("HIL-HUB-RST-", 10), ("HIL-C3-RST-", 8), ("HIL-BOTH-RST-", 6))
        for prefix, count in ranges:
            for number in range(1, count + 1):
                self.assertIn(f"{prefix}{number:03d}", ids)


if __name__ == "__main__":
    unittest.main()
