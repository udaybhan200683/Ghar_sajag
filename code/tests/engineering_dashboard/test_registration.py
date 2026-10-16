"""GS-116 actual registry selection/subprocess/fingerprint checks, no new runner."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from validation import component_gate as gate

CANONICAL_BASELINE = "c48e0d2fa8e0bc9c0d0a1f5eccdef789ff0b02df"
ACTIVE_BRANCH_BASELINE = "d738dc51a25e72de570a11fc39f0e26522ead3d8"
PROTECTED_CANONICAL_STAGES = {
    "c8-ack-drop-gate",
    "storage-correctness",
    "first-event-reader-compatibility",
    "first-event-recovery-projection",
    "storage-correctness-sanitizers",
    "cloud-worker-backend-integration",
}


class RegistrationTest(unittest.TestCase):
    def stage(self):
        return next(s for s in gate.load_registry()["stages"] if s["id"]=="diagnostic-foundation")

    def test_R01_selected_backend_fast_release_only_expected_ownership(self):
        data=gate.load_registry()
        for suite in ("backend","fast","release"):
            self.assertIn("diagnostic-foundation",{s["id"] for s in gate.select(data,suite)})
        for suite in ("node","hub","contract"):
            self.assertNotIn("diagnostic-foundation",{s["id"] for s in gate.select(data,suite)})
        self.assertIn("diagnostic-foundation",{s["id"] for s in gate.select(data,"pwa")})
        self.assertIn("NOT_PRODUCTION_AUTHENTICATION",self.stage()["qualification_scope"])

    def test_R02_all_parent_registry_stages_preserved_without_canonical_overwrite(self):
        # Preserve both the canonical integration parent and the verified R1
        # branch checkpoint. The active branch already carries four stages
        # added after the canonical parent; this candidate adds only GS-40.
        prior=json.loads(subprocess.check_output(
            ["git","show",f"{CANONICAL_BASELINE}:code/validation/suites.json"],
            cwd=gate.ROOT,text=True))
        active=json.loads(subprocess.check_output(
            ["git","show",f"{ACTIVE_BRANCH_BASELINE}:code/validation/suites.json"],
            cwd=gate.ROOT,text=True))
        current=gate.load_registry()
        current_by_id={s['id']:s for s in current['stages']}
        current_ids={s['id'] for s in current['stages']}
        prior_ids={s['id'] for s in prior['stages']}
        active_by_id={s['id']:s for s in active['stages']}
        active_ids={s['id'] for s in active['stages']}
        self.assertEqual(current_ids-active_ids,{
            "gs40-qualification-host",
            "cloudsync-security-unit",
            "cloudsync-security-sim-hil",
            "cloudsync-mtls-integration",
        })
        self.assertEqual(active_ids-current_ids,set())
        for original in active["stages"]:
            updated=current_by_id[original['id']]
            if original['id']=="gs130-hil-runner-integrity":
                expected=dict(original)
                expected["components"]=["tooling","hub","contract","backend"]
                expected_inputs=set(original["inputs"]) | {
                    "Makefile",
                    "validation/suites.json",
                    "validation/component_gate.py",
                    "tests/python/test_component_gate.py",
                    "tools/hil/gs68_cloudsync_hil.py",
                    "tools/hil/gs68_capture.py",
                    "tools/hil/gs68_test_backend.py",
                    "tools/hil/test_gs68_cloudsync_runners.py",
                    "tools/hil/test_gs68_physical_runners.py",
                    "tools/hil/gs68_cloudsync_cases.json",
                    "tools/hil/gs68_spare_fixture.template.json",
                    "tools/hil/gs68_test_backend.template.json",
                    "firmware/hub/target/esp32s3/idf/sdkconfig.gs68_cloudsync_hil.defaults",
                    "firmware/hub/target/esp32s3/idf/CMakeLists.txt",
                    "firmware/hub/target/esp32s3/idf/gs68_cloudsync_diagnostic/CMakeLists.txt",
                    "firmware/hub/target/esp32s3/idf/gs68_cloudsync_diagnostic/app_main.cpp",
                    "scripts/build_gs68_cloudsync_diagnostic.py",
                    "../docs/validation/PHYSICAL_QUALIFICATION.csv",
                }
                self.assertEqual(set(updated["inputs"]),expected_inputs)
                expected["inputs"]=updated["inputs"]
                self.assertEqual(updated,expected,
                                 "GS-130 integrity expansion must remain exact")
            else:
                self.assertEqual(updated,original,
                                 f"active branch stage changed: {original['id']}")
        self.assertEqual(current_ids-prior_ids,{
            "diagnostic-foundation",
            "gs114-p9-signed-artifact-safety",
            "gs114-ack-wait-trace",
            "gs144-workload-spec",
            "c8-ack-hold-gate",
            "gs40-qualification-host",
            "cloudsync-security-unit",
            "cloudsync-security-sim-hil",
            "cloudsync-mtls-integration",
        })
        self.assertEqual(prior_ids-current_ids,set())
        for original in prior["stages"]:
            updated=current_by_id[original['id']]
            for field in ("command", "components", "fast", "release", "run_when",
                          "count_kind", "timeout", "success", "failure_patterns",
                          "require_complete_product", "allowed_skips", "allowed_skip_lines"):
                if original["id"]=="gs130-hil-runner-integrity" and field=="components":
                    self.assertEqual(updated.get(field),["tooling","hub","contract","backend"])
                    continue
                self.assertEqual(updated.get(field),original.get(field),
                                 f"canonical stage field changed: {original['id']}:{field}")
            self.assertTrue(set(original.get("inputs",[]))<=set(updated.get("inputs",[])))
            self.assertTrue(set(original.get("required_success",[]))<=
                            set(updated.get("required_success",[])))
            allowed_additions={"inputs","required_success","pwa","qualification_scope","prerequisites"}
            for field in original.keys()|updated.keys():
                if original["id"]=="gs130-hil-runner-integrity" and field=="components":
                    self.assertEqual(updated.get(field),["tooling","hub","contract","backend"])
                elif field not in allowed_additions:
                    self.assertEqual(updated.get(field),original.get(field),
                                     f"canonical stage changed: {original['id']}:{field}")
            if original["id"] in PROTECTED_CANONICAL_STAGES:
                self.assertEqual(updated,original,
                                 f"protected canonical stage changed: {original['id']}")
        browser=current_by_id["browser"]
        self.assertTrue(browser.get("pwa"))
        self.assertIn("PREVIEW_ONLY",browser["qualification_scope"])
        self.assertFalse(browser.get("fast",False))
        self.assertTrue(browser.get("release"))
        self.assertEqual(len(browser.get("required_success",[])),21)
        self.assertEqual(current_by_id["python"].get("prerequisites"),["backend-receipts"])
        self.assertIn("tests/engineering_dashboard/test_service_access.py",
                      current["stages"][-1]["inputs"])
        for key in prior:
            if key=="opt_in_physical_suites":
                self.assertEqual(set(current[key])-set(prior[key]),{"validation-cloudsync-hil"})
                self.assertEqual(prior[key],{name:value for name,value in current[key].items()
                                             if name!="validation-cloudsync-hil"})
            elif key!="stages":
                self.assertEqual(prior[key],current[key])

    def test_R03_actual_nonzero_exit_cannot_pass_despite_ok_marker(self):
        result=gate.run_process([sys.executable,"-c","print('Ran 54 tests'); print('OK'); raise SystemExit(7)"],gate.ROOT,dict(os.environ),10)
        self.assertEqual(result["exit_code"],7)
        self.assertEqual(gate.adjudicate(self.stage(),result),"FAIL")

    def test_R04_zero_or_missing_execution_and_missing_ok_marker_fail(self):
        for text in ("Ran 0 tests\nOK\n","OK\n","Ran 54 tests\n"):
            self.assertEqual(gate.adjudicate(self.stage(),{"exit_code":0,"output":text}),"FAIL")

    def test_R05_missing_owned_test_input_rejected(self):
        data=copy.deepcopy(gate.load_registry())
        data["stages"][-1]["inputs"].append("tests/engineering_dashboard/MISSING.py")
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/"registry.json";path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"missing dependency"):
                gate.load_registry(path)

    def test_R06_registered_sources_and_body_invalidate_fingerprint(self):
        owned={*self.stage()["inputs"]}
        self.assertTrue({"backend/ghar_sajag/diagnostics.py","backend/ghar_sajag/diagnostic_authorization.py"}<=owned)
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"owned-test.py";p.write_text("first")
            first=gate.source_fingerprint(extra=[str(p)])
            p.write_text("second")
            self.assertNotEqual(first,gate.source_fingerprint(extra=[str(p)]))


if __name__=="__main__":unittest.main()
