from pathlib import Path
import json, unittest
ROOT=Path(__file__).resolve().parents[2]
class ValidationFrameworkTest(unittest.TestCase):
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
