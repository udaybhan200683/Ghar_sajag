#!/usr/bin/env python3
import json, sys, threading, unittest
from pathlib import Path
from urllib.request import Request, urlopen
from wsgiref.simple_server import make_server
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/sim'));sys.path.insert(0,str(ROOT/'tools/validation'))
from local_lab import Lab, WebLab, QuietRequests
from functional_scenarios import _assert_one
class TestPwa68Api(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.lab=Lab();cls.web=WebLab(cls.lab,0);cls.server=make_server('127.0.0.1',0,cls.web,handler_class=QuietRequests);cls.web.port=cls.server.server_port;cls.base=f'http://127.0.0.1:{cls.server.server_port}';cls.t=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.t.start()
 @classmethod
 def tearDownClass(cls):cls.server.shutdown();cls.t.join();cls.server.server_close();cls.lab.close()
 def get(self,p):return json.loads(urlopen(self.base+p,timeout=20).read())
 def post(self,p,b):
  r=Request(self.base+p,data=json.dumps(b).encode(),headers={'Content-Type':'application/json'});return json.loads(urlopen(r,timeout=30).read())
 def test_68_bridge(self):
  cat=self.get('/pwa/validation/catalog');self.assertGreaterEqual(cat['count'],68);fail=[]
  for sc in cat['scenarios']:
   payload=self.post('/pwa/validation/run',{'scenario_id':sc['id']})
   if not payload['steps_passed']:fail.append((sc['id'],'step',payload['step_results']));continue
   for a in payload['scenario']['assertions']:
    ok,detail=_assert_one(payload['state'],a)
    if not ok:fail.append((sc['id'],'assertion',detail))
  self.assertEqual(fail,[])
if __name__=='__main__':unittest.main(verbosity=2)
