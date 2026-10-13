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


class RegistrationTest(unittest.TestCase):
    def stage(self):
        return next(s for s in gate.load_registry()["stages"] if s["id"]=="diagnostic-foundation")

    def test_R01_selected_backend_fast_release_only_expected_ownership(self):
        data=gate.load_registry()
        for suite in ("backend","fast","release"):
            self.assertIn("diagnostic-foundation",{s["id"] for s in gate.select(data,suite)})
        for suite in ("node","hub","contract","pwa"):
            self.assertNotIn("diagnostic-foundation",{s["id"] for s in gate.select(data,suite)})
        self.assertIn("NOT_PRODUCTION_AUTHENTICATION",self.stage()["qualification_scope"])

    def test_R02_all_parent_registry_stages_preserved_without_canonical_overwrite(self):
        prior=json.loads(subprocess.check_output(["git","show","31822b1:code/validation/suites.json"],cwd=gate.ROOT,text=True))
        current=gate.load_registry()
        self.assertEqual(current["stages"][:-1],prior["stages"])
        self.assertIn("tests/engineering_dashboard/test_service_access.py",
                      current["stages"][-1]["inputs"])
        for key in prior:
            if key!="stages":self.assertEqual(prior[key],current[key])

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
