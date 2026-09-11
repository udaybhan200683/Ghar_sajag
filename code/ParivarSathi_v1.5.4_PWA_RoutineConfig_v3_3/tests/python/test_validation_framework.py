from pathlib import Path
import json, unittest
ROOT=Path(__file__).resolve().parents[2]
class ValidationFrameworkTest(unittest.TestCase):
    def test_catalog_has_required_categories_and_unique_ids(self):
        data=json.loads((ROOT/'tests/functional/scenario_catalog.json').read_text())
        ids=[s['id'] for s in data['scenarios']]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertGreaterEqual(len(ids),60)
        self.assertTrue({'expected','morning','door','inactivity','transport','caregiver','configuration','negative','diagnostics'} <= {s['category'] for s in data['scenarios']})
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
