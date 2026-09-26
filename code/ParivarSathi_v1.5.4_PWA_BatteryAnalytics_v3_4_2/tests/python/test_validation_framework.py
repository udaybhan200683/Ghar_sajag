from pathlib import Path
import json, unittest
ROOT=Path(__file__).resolve().parents[2]
class ValidationFrameworkTest(unittest.TestCase):
    def test_master_validation_has_complete_offline_id_set(self):
        source=(ROOT/'tests/cpp/master_validation.cpp').read_text()
        for number in range(1,36):
            with self.subTest(number=number):
                self.assertIn(f'"OR-{number:03d}"',source)

    def test_master_traceability_rows_have_required_columns_and_explicit_status(self):
        import csv
        path=ROOT.parents[1]/'docs/validation/MASTER_TRACEABILITY.csv'
        with path.open(newline='') as stream:
            rows=list(csv.DictReader(stream))
        required={'FEATURE_ID','feature_requirement','implementation_modules','positive_case',
                  'negative_case','boundary_case','fault_injection_case','restart_recovery_case',
                  'stress_performance_case','simulation_TC','HIL_TC','PWA_E2E_TC',
                  'release_gate','nightly','status'}
        self.assertGreaterEqual(len(rows),30)
        self.assertTrue(required <= set(rows[0]))
        self.assertTrue(all(row['status'] in {
            'COVERED','PARTIAL','MISSING_PRODUCT_FEATURE',
            'MISSING_PRODUCT_FEATURE_TARGET_VERTICAL_BRIDGE',
            'PRODUCT_GAP','TEST_INFRA_GAP','HIL_ONLY_PHYSICAL',
            'PARTIAL_BUT_SUFFICIENT'
        } for row in rows))

    def test_fota_host_matrix_is_complete_and_uses_production_receiver(self):
        source=(ROOT/'tests/cpp/fota_host_validation.cpp').read_text()
        for number in range(1,23):
            with self.subTest(number=number):
                self.assertIn(f'"FOTA-HOST-{number:03d}"',source)
        self.assertIn('firmware/node/fota/fota_receiver.hpp',source)

    def test_complete_nightly_has_expensive_suites_once(self):
        source=(ROOT/'tools/validation/nightly.py').read_text()
        for token in ('fota-host-test','concurrency-test','STRESS_PROFILE=MEDIUM',
                      'release-gate-final','endurance-test','validation-coverage'):
            self.assertEqual(source.count(f'"{token}"'),1,token)

    def test_hil_runner_is_fail_closed_when_unconfigured(self):
        source=(ROOT/'tools/hil/nightly.py').read_text()
        self.assertIn('"status": "BLOCKED"',source)
        self.assertIn('return 2',source)

    def test_phase1_ui_contract_has_mandatory_negative_and_viewport_rules(self):
        contract=json.loads((ROOT/'tests/validation/phase1_ui_contract.json').read_text())
        self.assertEqual(contract['schema'],1)
        self.assertGreaterEqual(len(contract['components']),14)
        required={'given','when','then','must_not','severity','css','banner_change','recent_change','persistence','reset','viewports'}
        for name,row in contract['components'].items():
            with self.subTest(component=name):
                self.assertTrue(required<=set(row))
                self.assertTrue(row['then'])
                self.assertTrue(row['must_not'])
                self.assertEqual(row['viewports'],['chromium-desktop','chromium-mobile'])
        statuses={'AUTOMATED','PARTIAL','MANUAL_ONLY','HW_REQUIRED','PHASE2_PENDING'}
        self.assertTrue(contract['pairwise'])
        self.assertTrue(contract['high_risk_three_way'])
        for row in contract['coverage']:
            self.assertTrue({'requirement','domain','api','browser','positive','forbidden','desktop','mobile','status'}<=set(row))
            self.assertIn(row['status'],statuses)
        for row in contract['simulator_action_coverage'].values(): self.assertIn(row['status'],statuses)

    def test_catalog_has_required_categories_and_unique_ids(self):
        data=json.loads((ROOT/'tests/functional/scenario_catalog.json').read_text())
        ids=[s['id'] for s in data['scenarios']]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertGreaterEqual(len(ids),60)
        self.assertTrue({'expected','morning','door','inactivity','transport','caregiver','configuration','negative','diagnostics','battery'} <= {s['category'] for s in data['scenarios']})
    def test_all_fault_codes_have_scenarios(self):
        data=json.loads((ROOT/'tests/functional/scenario_catalog.json').read_text())
        text=json.dumps(data)
        for token in ('low_battery','battery_depleted','link_loss','sensor_fault','over_temp','watchdog','power_loss','node_radio_failure','internet_loss'):
            self.assertIn(token,text)
    def test_manual_plan_is_generated(self):
        text=(ROOT/'tests/MANUAL_FUNCTIONAL_VALIDATION.md').read_text()
        count=len(json.loads((ROOT/'tests/functional/scenario_catalog.json').read_text())['scenarios'])
        self.assertGreaterEqual(text.count('Result: ☐ PASS ☐ FAIL'),count)
    def test_dummy_streams_exist(self):
        self.assertGreaterEqual(len(list((ROOT/'tests/fixtures/sensor_streams').glob('*.json'))),5)
if __name__=='__main__': unittest.main()
