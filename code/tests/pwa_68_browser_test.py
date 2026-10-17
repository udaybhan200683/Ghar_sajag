#!/usr/bin/env python3
from __future__ import annotations
import json, os, re, shutil, socket, subprocess, sys, tempfile, threading, time, unittest
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from wsgiref.simple_server import make_server
import websocket
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/sim'))
from local_lab import Lab, WebLab, QuietRequests

def free_port():
    s=socket.socket();s.bind(('127.0.0.1',0));p=s.getsockname()[1];s.close();return p

def cdp(ws, method, params=None, counter=[0]):
    counter[0]+=1; ident=counter[0]
    ws.send(json.dumps({'id':ident,'method':method,'params':params or {}}))
    while True:
        msg=json.loads(ws.recv())
        if msg.get('id')==ident:
            if 'error' in msg: raise RuntimeError(msg['error'])
            return msg.get('result',{})

class Pwa68BrowserTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  # Prefer the hosted Google Chrome binary over Ubuntu's possible Chromium
  # wrapper/snap stub; both implement the same DevTools protocol used below.
  cls.chromium=shutil.which('google-chrome-stable') or shutil.which('google-chrome') or shutil.which('chromium') or shutil.which('chromium-browser')
  if not cls.chromium:raise unittest.SkipTest('Chromium/Chrome not installed')
  version=subprocess.run([cls.chromium,'--version'],capture_output=True,text=True,check=False).stdout.strip()
  print(f'PWA browser E2E executable={cls.chromium} version={version or "unavailable"}')
  cls.lab=Lab();cls.web=WebLab(cls.lab,0);cls.server=make_server('127.0.0.1',0,cls.web,handler_class=QuietRequests);cls.web.port=cls.server.server_port;cls.base=f'http://127.0.0.1:{cls.server.server_port}';cls.t=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.t.start()
 @classmethod
 def tearDownClass(cls):cls.server.shutdown();cls.t.join();cls.server.server_close();cls.lab.close()
 def test_all_catalog_cases_in_real_pwa_dom(self):
  port=free_port();profile=tempfile.mkdtemp(prefix='ps-chrome-')
  proc=subprocess.Popen([self.chromium,'--headless=new','--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--disable-background-networking','--no-first-run','--remote-allow-origins=*',f'--remote-debugging-port={port}',f'--user-data-dir={profile}','about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  try:
   version=None
   for _ in range(100):
    try: version=json.loads(urlopen(f'http://127.0.0.1:{port}/json/version',timeout=.5).read());break
    except Exception: time.sleep(.1)
   self.assertIsNotNone(version,'Chromium DevTools endpoint did not start')
   req=Request(f'http://127.0.0.1:{port}/json/new?{quote(self.base+"/?validation=autorun",safe="/:?=&")}',method='PUT')
   page=json.loads(urlopen(req,timeout=3).read());ws=websocket.create_connection(page['webSocketDebuggerUrl'],timeout=10)
   try:
    cdp(ws,'Page.enable');cdp(ws,'Runtime.enable')
    catalog=json.loads(urlopen(self.base+'/pwa/validation/catalog',timeout=5).read());expected=int(catalog['count'])
    deadline=time.time()+180;status=None;count=0
    while time.time()<deadline:
     r=cdp(ws,'Runtime.evaluate',{'expression':"(()=>{const e=document.querySelector('#validationOverall');return e?{status:e.dataset.validationStatus,count:Number(e.dataset.validationCount),text:e.textContent}:null})()",'returnByValue':True})
     v=r.get('result',{}).get('value')
     if v:
      status=v.get('status');count=v.get('count',0)
      if status in ('PASS','FAIL') and count==expected:break
     time.sleep(.2)
    self.assertEqual((status,count),('PASS',expected))
    r=cdp(ws,'Runtime.evaluate',{'expression':"document.documentElement.outerHTML",'returnByValue':True});dom=r['result']['value']
    rows=re.findall(r'data-validation-case="([^"]+)" data-case-status="([^"]+)"',dom);self.assertEqual(len(rows),expected);self.assertEqual([c for c,s in rows if s!='PASS'],[])
    errors=cdp(ws,'Runtime.evaluate',{'expression':"document.querySelectorAll('.validation-row.fail').length",'returnByValue':True})['result']['value'];self.assertEqual(errors,0)
    (ROOT/'logs').mkdir(exist_ok=True);(ROOT/'logs'/'pwa_68_browser_dom.html').write_text(dom,encoding='utf-8')
    print(f'PASS PWA browser E2E: {expected}/{expected} rendered PASS')
   finally: ws.close()
  finally:
   proc.terminate()
   try:proc.wait(timeout=5)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
   shutil.rmtree(profile,ignore_errors=True)
 def test_caregiver_runtime_starts_offline_without_simulated_household_data(self):
  original=self.web.runtime_config
  self.web.runtime_config={"mode":"caregiver","backendOrigin":"https://care.gharsajag.in/","caregiverApiConfigured":False}
  port=free_port();profile=tempfile.mkdtemp(prefix='ps-caregiver-offline-')
  proc=subprocess.Popen([self.chromium,'--headless=new','--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--disable-background-networking','--no-first-run','--remote-allow-origins=*',f'--remote-debugging-port={port}',f'--user-data-dir={profile}','about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  try:
   version=None
   for _ in range(100):
    try: version=json.loads(urlopen(f'http://127.0.0.1:{port}/json/version',timeout=.5).read());break
    except Exception: time.sleep(.1)
   self.assertIsNotNone(version,'Chromium DevTools endpoint did not start')
   req=Request(f'http://127.0.0.1:{port}/json/new?{quote(self.base,safe="/:?=&")}',method='PUT')
   page=json.loads(urlopen(req,timeout=3).read());ws=websocket.create_connection(page['webSocketDebuggerUrl'],timeout=10)
   try:
    cdp(ws,'Page.enable');cdp(ws,'Runtime.enable');cdp(ws,'Network.enable')
    deadline=time.time()+15;dom=None
    while time.time()<deadline:
     result=cdp(ws,'Runtime.evaluate',{'expression':"(()=>{const e=document.querySelector('#connectionStatus');return e?{banner:e.innerText,home:document.querySelector('#homeTab')?.innerText||'',pilot:!!document.querySelector('.sim-sidebar')}:null})()",'returnByValue':True})
     dom=result.get('result',{}).get('value')
     if dom and 'Home unavailable' in dom['home']:break
     time.sleep(.1)
    self.assertIsNotNone(dom,'caregiver UI did not render')
    self.assertIn('Offline / Unable to connect',dom['banner'])
    self.assertIn('freshness are unavailable',dom['banner'])
    self.assertIn('Home unavailable',dom['home'])
    self.assertFalse(dom['pilot'])
    branding=cdp(ws,'Runtime.evaluate',{'expression':"(()=>{const name=document.querySelector('.brand-name');const icon=document.querySelector('.brand-icon');return {name:name?.textContent?.trim(),icon:icon?.getAttribute('src'),loaded:!!icon?.complete&&icon.naturalWidth===192}})()",'returnByValue':True})['result']['value']
    self.assertEqual(branding,{'name':'Parivar Saathi','icon':'assets/parivar-saathi-icon-192.png','loaded':True},'PWA branding must use the approved logo mark and name')
    forbidden=cdp(ws,'Runtime.evaluate',{'expression':"/simulation-owner|simulation-home|All is well at home|Home looks normal/.test(document.body.innerText)",'returnByValue':True})['result']['value']
    self.assertFalse(forbidden,'caregiver UI exposed simulator identity or a synthetic healthy state')
    resources=cdp(ws,'Runtime.evaluate',{'expression':"performance.getEntriesByType('resource').map(x=>x.name).filter(x=>/\\/(?:pwa|v1)\\//.test(new URL(x).pathname))",'returnByValue':True})['result']['value']
    self.assertEqual(resources,[],'offline startup must not call simulator or placeholder production API routes')
    for tab,heading in [('devices','Devices unavailable'),('reports','Reports unavailable'),('settings','Caregiver sign-in')]:
     cdp(ws,'Runtime.evaluate',{'expression':f"document.querySelector('[data-tab=\\\"{tab}\\\"]').click()"})
     panel=cdp(ws,'Runtime.evaluate',{'expression':f"document.querySelector('#{tab}Tab').innerText",'returnByValue':True})['result']['value']
     self.assertIn(heading,panel)
    print('PASS caregiver offline browser E2E: familiar tabs, explicit unavailable state, no simulator data or API calls')
   finally: ws.close()
  finally:
   self.web.runtime_config=original
   proc.terminate()
   try:proc.wait(timeout=5)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
   shutil.rmtree(profile,ignore_errors=True)
if __name__=='__main__':unittest.main(verbosity=2)
