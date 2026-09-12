"""PWA bridge integration checks for v1.5.4 local lab."""
import json, sys, threading, unittest
from pathlib import Path
from urllib.request import Request, urlopen
from wsgiref.simple_server import make_server

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/sim'))
from local_lab import Lab, WebLab, QuietRequests

class PwaBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lab=Lab(); cls.web=WebLab(cls.lab,0)
        cls.server=make_server('127.0.0.1',0,cls.web,handler_class=QuietRequests)
        cls.web.port=cls.server.server_port
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True); cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.thread.join(); cls.server.server_close(); cls.lab.close()
    def req(self,path,body=None):
        raw=None if body is None else json.dumps(body).encode()
        r=Request(self.base+path,data=raw,headers={'Content-Type':'application/json'})
        with urlopen(r,timeout=10) as x:return json.loads(x.read())
    def reset(self): return self.req('/pwa/action',{'action':'reset_pass'})
    def toggle(self,name): return self.req('/pwa/action',{'action':'toggle','scenario':name})
    def test_reset_is_pass(self):
        s=self.reset(); self.assertFalse(s['care']['alert']); self.assertTrue(s['morning']['ok']); self.assertTrue(s['iam_ok']['ok']); self.assertFalse(s['door']['open']); self.assertFalse(s['night']['unusual']); self.assertFalse(s['device_health']['attention'])
    def test_battery_is_health_only(self):
        self.reset(); s=self.toggle('battery'); self.assertTrue(s['device_health']['attention']); self.assertFalse(s['care']['alert']); s=self.toggle('battery'); self.assertFalse(s['device_health']['attention']); self.assertFalse(s['care']['alert'])
    def test_battery_prediction_fields_are_backend_driven(self):
        s=self.reset()
        kitchen=next(d for d in s['devices'] if d['id']=='kitchen')
        self.assertGreater(kitchen['estimated_days'],30)
        self.assertGreater(kitchen['daily_mah'],0)
        self.assertEqual(kitchen['confidence'],'HIGH')
        self.assertEqual(kitchen['drain_status'],'NORMAL')
        self.assertGreater(kitchen['wakeups_per_day'],0)
        self.assertIn('days',kitchen['left'])

    def test_low_confidence_runtime_is_learning_not_overpromised(self):
        self.reset()
        self.req('/sim/action',{'action':'battery_counter_reset','target':'kitchen'})
        s=self.req('/pwa/state')
        kitchen=next(d for d in s['devices'] if d['id']=='kitchen')
        self.assertEqual(kitchen['confidence'],'LOW')
        self.assertEqual(kitchen['left'],'calculating')
        self.assertFalse(s['care']['alert'])

    def test_high_drain_is_device_health_only(self):
        self.reset()
        self.req('/sim/action',{'action':'battery_usage','target':'kitchen','days':2,'intensity':20})
        s=self.req('/pwa/state')
        kitchen=next(d for d in s['devices'] if d['id']=='kitchen')
        self.assertEqual(kitchen['drain_status'],'HIGH')
        self.assertLess(kitchen['estimated_days'],100)
        self.assertTrue(s['device_health']['attention'])
        self.assertIn('kitchen',s['device_health']['high_drain_devices'])
        self.assertFalse(s['care']['alert'])

    def test_each_care_toggle_round_trips(self):
        for name,path in [('morning',('morning','ok')),('ok',('iam_ok','ok')),('door',('door','open')),('night',('night','unusual'))]:
            self.reset(); bad=self.toggle(name); self.assertTrue(bad['care']['alert'],name); self.assertFalse(bad[path[0]][path[1]]) if name in {'morning','ok'} else self.assertTrue(bad[path[0]][path[1]])
            good=self.toggle(name); self.assertFalse(good['care']['alert'],name)
    def test_events_are_newest_first(self):
        self.reset(); self.toggle('battery'); self.toggle('door')
        s=self.req('/pwa/state'); times=[e['at'] for e in s['events']]; self.assertEqual(times,sorted(times,reverse=True))
    def test_pwa_assets(self):
        for path in ('/','/app.js','/styles.css','/manifest.webmanifest','/assets/icon.svg','/lab'):
            r=Request(self.base+path); data=urlopen(r,timeout=10).read(); self.assertGreater(len(data),50,path)

    def test_incomplete_morning_is_pending_not_missing(self):
        self.lab.reset()
        s=self.req('/pwa/state')
        self.assertFalse(s['care']['alert'])
        self.assertFalse(s['morning']['sequence_completed'])
        self.assertFalse(s['morning']['missing'])
        self.assertEqual(s['care']['subtitle'],'All is well at home.')

if __name__=='__main__': unittest.main(verbosity=2)
