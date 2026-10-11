import copy
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('coverage',ROOT/'scripts/check_feature_traceability.py')
coverage=importlib.util.module_from_spec(spec);spec.loader.exec_module(coverage)
from tools.validation import component_gate as gate

class FeatureTraceabilityTest(unittest.TestCase):
    def setUp(self):
        self.rows,self.modules,self.physical,self.registry=copy.deepcopy(coverage.load())
    def issues(self):return coverage.errors(self.rows,self.modules,self.physical,self.registry)
    def test_future_board_case_requires_marker_and_matrix(self):
        stage=next(s for s in self.registry['stages'] if s['id']=='board-stack-e2e')
        source=(ROOT/'tests/cpp/board_stack_e2e_validation.cpp').read_text()
        source+='\n{"BOARD-TC-130-999", future_case}'
        self.assertTrue(coverage.board_registration_errors(source,stage,self.rows))
    def test_omitted_board_case_mapping_fails(self):
        self.rows=[r for r in self.rows if r['FEATURE_ID']!='BOARD-TC-130-008']
        self.assertTrue(self.issues())
    def test_unknown_canonical_requirement_fails(self):
        self.rows[0]['REQUIREMENT_ID']='GS-NOT-A-REAL-REQUIREMENT';self.assertTrue(self.issues())
    def test_current_mapping_and_source_inventory(self):self.assertEqual(self.issues(),[])
    def test_zero_rows_fails(self):self.rows=[];self.assertIn('zero feature rows',self.issues())
    def test_missing_registration_fails(self):
        self.registry['stages']=[s for s in self.registry['stages'] if s['id']!='feature-boundaries'];self.assertTrue(self.issues())
    def test_test_id_must_resolve(self):
        self.rows[0]['ASSERTION_ANCHOR']='NONEXISTENT_TEST';self.assertTrue(self.issues())
    def test_missing_source_fails(self):
        self.rows[0]['TEST_SOURCE']='tests/cpp/absent.cpp';self.assertTrue(self.issues())
    def test_wrong_command_fails(self):
        self.rows[0]['EXACT_TEST_EXECUTION_COMMAND']='true';self.assertTrue(self.issues())
    def test_wrong_component_gate_fails(self):
        self.rows[0]['NODE_GATE']='NO';self.assertTrue(self.issues())
    def test_omitted_new_module_fails(self):
        self.modules.pop();self.assertTrue(self.issues())
    def test_module_feature_must_resolve(self):
        self.modules[0]['FEATURE_IDS']='NEW-UNMAPPED';self.assertTrue(self.issues())
    def test_physical_not_run_cannot_be_host_pass(self):
        self.physical[0]['EXECUTION_STATUS']='PASS';self.assertTrue(self.issues())
    def test_row_cannot_claim_physical_pass(self):
        self.rows[0]['PHYSICAL_EVIDENCE_STATUS']='PASS';self.assertTrue(self.issues())
    def test_implemented_unmapped_without_gap_fails(self):
        row=self.rows[0];row['STAGE_IDS']='';row['COVERAGE_GAP']='';self.assertTrue(self.issues())
    def test_new_component_registration_reaches_fast_release(self):
        stage={'id':'future-node-case','components':['node'],'command':['test'],'success':'PASS','timeout':1}
        self.registry['stages'].append(stage)
        for suite in ('node','fast','release'):self.assertIn(stage,gate.select(self.registry,suite))
    def test_board_gate_is_distinct_and_registered_in_components(self):
        self.assertEqual([s['id'] for s in gate.select(self.registry,'board-e2e')],['board-stack-e2e'])
        for suite in ('node','hub','contract','fast','release'):
            self.assertIn('board-stack-e2e',[s['id'] for s in gate.select(self.registry,suite)])
    def test_release_still_includes_all_required_application_and_build_stages(self):
        ids={s['id'] for s in gate.select(self.registry,'release')}
        self.assertLessEqual({'python','javascript','browser','target-builds','sanitizers','migration','factory-reset','feature-boundaries','feature-traceability'},ids)
    def test_migration_remains_mandatory_without_skip(self):
        stage=next(s for s in self.registry['stages'] if s['id']=='migration')
        self.assertNotIn('allowed_skips',stage);self.assertEqual(gate.adjudicate(stage,{'exit_code':2,'output':'clean migration commits'}),'FAIL')

if __name__=='__main__':unittest.main()
