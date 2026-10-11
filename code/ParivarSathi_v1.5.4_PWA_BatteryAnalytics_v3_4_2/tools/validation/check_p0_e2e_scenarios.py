#!/usr/bin/env python3
"""Check P0 scenario registry IDs and concrete executable test anchors."""
import json
import csv
from pathlib import Path
import re
import sys

PRODUCT = Path(__file__).resolve().parents[2]
REPO = PRODUCT.parents[1]
REGISTRY = REPO / "docs/validation/P0_E2E_SCENARIOS.json"
EXPECTED_USES = {f"P0-UC-{n:02d}" for n in range(1, 18)}


def main():
    try:
        data = json.loads(REGISTRY.read_text())
        cases = data["use_cases"]
        scenarios = data["scenarios"]
        with (REPO / "docs/validation/MASTER_TRACEABILITY.csv").open(newline="") as stream:
            feature_rows = list(csv.DictReader(stream))
        suites_path = PRODUCT / "tools/validation/suites.json"
        suites = json.loads(suites_path.read_text())
        known_features = {row["FEATURE_ID"] for row in feature_rows}
        use_ids = [item["use_case_id"] for item in cases]
        scenario_ids = [item["scenario_id"] for item in scenarios]
        errors = []
        if len(set(use_ids)) != len(use_ids) or set(use_ids) != EXPECTED_USES:
            errors.append("P0 use-case IDs must map the canonical 17 groups exactly once")
        if len(set(scenario_ids)) != len(scenario_ids) or not scenarios:
            errors.append("scenario IDs must be nonempty and unique")
        known = set(scenario_ids)
        for case in cases:
            if not case.get("feature_ids") or not case.get("requirements"):
                errors.append(case.get("use_case_id", "unknown") + " lacks feature/requirement mapping")
            unknown = set(case.get("feature_ids", [])) - known_features
            if unknown:
                errors.append(case["use_case_id"] + " maps unknown features: " + ",".join(sorted(unknown)))
            if set(case.get("scenario_ids", [])) - known:
                errors.append(case["use_case_id"] + " references an unknown scenario")
            if not case.get("scenario_ids") and not case.get("gap"):
                errors.append(case.get("use_case_id", "unknown") + " has neither an executable scenario nor an explicit gap")
            if case.get("classification") in {"PARTIAL", "PRODUCT_GAP", "BLOCKED"} and not case.get("gap"):
                errors.append(case.get("use_case_id", "unknown") + " has a partial classification without a gap reason")
        executable = 0
        for scenario in scenarios:
            if not scenario.get("expected") or not scenario.get("production_sources") or not scenario.get("jira_owner"):
                errors.append(scenario.get("scenario_id", "unknown") + " lacks source/expectation/owner")
            paths = [p for p in scenario.get("test_source", "").split(";") if p]
            if not paths:
                errors.append(scenario["scenario_id"] + " has no executable source")
            test_contents = []
            for rel in paths:
                source_path = PRODUCT / rel
                if not source_path.is_file():
                    errors.append(scenario["scenario_id"] + " source missing: " + rel)
                else:
                    test_contents.append(source_path.read_text(errors="replace"))
            if scenario.get("execution_status") == "RUNTIME_REPORT" and not any(
                scenario["scenario_id"] in content for content in test_contents
            ):
                errors.append(scenario["scenario_id"] + " is not present in any executable source")
            for rel in scenario.get("production_sources", []):
                if not (PRODUCT / rel).is_file():
                    errors.append(scenario["scenario_id"] + " production anchor missing: " + rel)
            executable += 1
        stage = next((item for item in suites["stages"] if item["id"] == "p0-full-product-e2e"), None)
        if stage is None or not stage.get("require_complete_product") or not stage.get("fast") or not stage.get("release"):
            errors.append("P0 full-product stage must be a mandatory software and release candidate stage")
        else:
            registered = set(stage.get("required_success", []))
            stage_inputs = set(stage.get("inputs", []))
            for scenario_id in scenario_ids:
                marker = f"^" + scenario_id + r" PASS"
                if marker not in registered:
                    errors.append(scenario_id + " is not a mandatory success marker in the P0 gate")
            production_anchors = {
                source for scenario in scenarios for source in scenario.get("production_sources", [])
            }
            for anchor in sorted(production_anchors - stage_inputs):
                errors.append("production source is not a fingerprinted P0-gate input: " + anchor)
            required_inputs = {
                "tests/python/run_full_product_p0_e2e.py",
                "tests/python/test_p0_e2e_selection.py",
                "tests/playwright/p0_full_product.spec.ts",
                "../../docs/validation/P0_E2E_SCENARIOS.json",
            }
            if not required_inputs.issubset(set(stage.get("inputs", []))):
                errors.append("P0 product gate does not fingerprint all scenario/browser inputs")
        if errors:
            print("P0 SCENARIO REGISTRY FAIL", *errors, sep="\n- ")
            return 1
        print(f"P0 SCENARIO REGISTRY PASS use_cases={len(cases)} scenarios={len(scenarios)} executable_sources={executable}")
        return 0
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        print("P0 SCENARIO REGISTRY FAIL", error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
