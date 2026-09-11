#!/usr/bin/env python3
import os, subprocess, sys, threading, unittest
from pathlib import Path
from wsgiref.simple_server import make_server
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/sim'))
from local_lab import Lab,WebLab,QuietRequests
class Frontend68(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.lab=Lab();cls.web=WebLab(cls.lab,0);cls.server=make_server('127.0.0.1',0,cls.web,handler_class=QuietRequests);cls.web.port=cls.server.server_port;cls.base=f'http://127.0.0.1:{cls.server.server_port}';cls.t=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.t.start()
 @classmethod
 def tearDownClass(cls):cls.server.shutdown();cls.t.join();cls.server.server_close();cls.lab.close()
 def test_frontend_68(self):
  env=os.environ.copy();env['GS_PWA_BASE']=self.base
  cp=subprocess.run(['node','tests/pwa_68_frontend_runner.mjs'],cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
  self.assertEqual(cp.returncode,0,cp.stdout);self.assertIn('68/68',cp.stdout)
if __name__=='__main__':unittest.main(verbosity=2)
