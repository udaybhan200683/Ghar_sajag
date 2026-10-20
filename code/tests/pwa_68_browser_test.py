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
  self.web.runtime_config={"mode":"caregiver","backendOrigin":"","caregiverApiConfigured":False}
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
    cdp(ws,'Page.navigate',{'url':self.base+'/'})
    deadline=time.time()+15;dom=None
    while time.time()<deadline:
     result=cdp(ws,'Runtime.evaluate',{'expression':"(()=>{const e=document.querySelector('#connectionStatus');return e?{banner:e.innerText,home:document.querySelector('#homeTab')?.innerText||'',pilot:!!document.querySelector('.sim-sidebar')}:null})()",'returnByValue':True})
     dom=result.get('result',{}).get('value')
     if dom and 'Sign in to your authorized Home' in dom['home']:break
     time.sleep(.1)
    self.assertIsNotNone(dom,f'caregiver UI did not render; last evaluation={result!r}')
    self.assertIn('OFFLINE / UNCONFIGURED',dom['banner'])
    self.assertIn('no approved HTTPS backend',dom['banner'])
    self.assertIn('Monitoring status is unknown',dom['home'])
    self.assertIn('Approved HTTPS backend is not configured',dom['home'])
    self.assertFalse(dom['pilot'])
    branding=cdp(ws,'Runtime.evaluate',{'expression':"(()=>{const name=document.querySelector('.brand-name');const icon=document.querySelector('.brand-icon');return {name:name?.textContent?.trim(),icon:icon?.getAttribute('src'),loaded:!!icon?.complete&&icon.naturalWidth===192}})()",'returnByValue':True})['result']['value']
    self.assertEqual(branding,{'name':'Parivar Saathi','icon':'assets/parivar-saathi-icon-192.png','loaded':True},'PWA branding must use the approved logo mark and name')
    forbidden=cdp(ws,'Runtime.evaluate',{'expression':"/simulation-owner|simulation-home|All is well at home|Home looks normal/.test(document.body.innerText)",'returnByValue':True})['result']['value']
    self.assertFalse(forbidden,'caregiver UI exposed simulator identity or a synthetic healthy state')
    resources=cdp(ws,'Runtime.evaluate',{'expression':"performance.getEntriesByType('resource').map(x=>x.name).filter(x=>/\\/(?:pwa|v1)\\//.test(new URL(x).pathname))",'returnByValue':True})['result']['value']
    self.assertEqual(resources,[],'offline startup must not call simulator or placeholder production API routes')
    app_assets=cdp(ws,'Runtime.evaluate',{'expression':"performance.getEntriesByType('resource').map(x=>new URL(x.name).pathname)",'returnByValue':True})['result']['value']
    self.assertIn('/caregiver.css',app_assets,'caregiver runtime must load its bounded production stylesheet')
    self.assertNotIn('/styles.css',app_assets,'caregiver runtime must not download the development simulator stylesheet')
    self.assertNotIn('/app.js',app_assets,'caregiver runtime must not download local simulator code')
    self.assertNotIn('/sw.js',app_assets,'caregiver runtime must not register or fetch simulator service-worker code')
    nav=cdp(ws,'Runtime.evaluate',{'expression':"document.querySelector('.bottom-nav').hidden",'returnByValue':True})['result']['value']
    self.assertTrue(nav,'caregiver navigation must stay hidden until server authentication')
    print('PASS caregiver offline browser E2E: login gate, explicit unavailable state, no simulator data or API calls')
   finally: ws.close()
  finally:
   self.web.runtime_config=original
   proc.terminate()
   try:proc.wait(timeout=5)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
   shutil.rmtree(profile,ignore_errors=True)
 def test_connected_lite_admin_navigation_simulation_and_caregiver_restriction(self):
  original=self.web.runtime_config
  self.web.runtime_config={"mode":"caregiver","backendOrigin":"https://care.gharsajag.in/","caregiverApiConfigured":True,"appVersion":"browser-test","sourceRevision":"0123456789ab"}
  port=free_port();profile=tempfile.mkdtemp(prefix='ps-connected-lite-')
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
    mock=r'''(()=>{
      const home='gs177-test-browser-home',runs=[];let role=null;
      const profile=()=>({account_id:'browser-account',email:role==='ADMIN'?'owner@example.org':'caregiver@example.org',home_id:home,role,test_only:true,expires_at:4102444800,backend_revision:'browser-test'});
      const makeResult=scenario=>({status:'PASS',scenario:{id:scenario,title:scenario==='morning-missing-covered'?'Missing morning activity':'Motion in visible room',category:scenario==='morning-missing-covered'?'morning':'expected'},provenance:'HOST_SIMULATION_TEST_ONLY',hardware_evidence:'NOT_RUN',source_revision:'0123456789ab',step_results:[{index:1,passed:true,detail:'scenario rule evaluated'}],checks:[{pass:true,detail:scenario==='morning-missing-covered'?'Expected morning concern appears under covered test input':'Expected motion appears in the simulated timeline'}],state:{timeline:[{kind:scenario==='morning-missing-covered'?'MORNING_ROUTINE_MISSING':'MOTION',event_id:'simulated-event-'+(runs.length+1),occurred_at:'2026-10-17T08:00:00Z',received_at:'2026-10-17T08:00:01Z',location:'room1',source:'HOST_SIMULATION_TEST_ONLY',routine_decision:scenario==='morning-missing-covered'?'CONCERN':'ACTIVITY'}],simulation:{reason:scenario==='morning-missing-covered'?'no_qualifying_evidence':'motion_observed'},incidents:[],notifications:[],devices:[]}});
      const events=()=>runs.flatMap(run=>(run.result?.state?.timeline||[]).map((event,index)=>({trace_id:'sim:'+run.run_id+':'+(index+1),run_id:run.run_id,scenario_id:run.scenario_id,event_id:event.event_id,event_key:null,original_event_key_available:false,source:'HOST_SIMULATION_TEST_ONLY',provenance:'HOST_SIMULATION_TEST_ONLY',kind:event.kind,location:event.location,occurred_at:event.occurred_at,received_at:event.received_at,delayed:false,run_created_at:run.created_at})));
      const decisions=()=>runs.filter(run=>['routine','morning','inactivity'].includes(run.result?.scenario?.category)).map(run=>({run_id:run.run_id,trace_id:'sim:'+run.run_id,scenario_id:run.scenario_id,scenario_title:run.result.scenario.title,category:run.result.scenario.category,evaluated_at:run.created_at,result:run.status,decision_reason:run.result.state.simulation.reason,step_results:run.result.step_results,checks:run.result.checks,event_ids:run.result.state.timeline.map(event=>event.event_id),incident_ids:[],incident_count:0,provenance:'HOST_SIMULATION_TEST_ONLY',learning_status:'UNSUPPORTED_MULTI_DAY'}));
      const send=(body,status=200)=>Promise.resolve(new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json'}}));
      const original=window.fetch.bind(window);
      window.fetch=async(input,options={})=>{
        const url=new URL(String(input));
        if(url.origin!=='https://care.gharsajag.in')return original(input,options);
        const path=url.pathname.replace('/lite/v1/','');
        if(path==='auth/login'&&options.method==='POST'){const credentials=JSON.parse(options.body);role=credentials.email==='caregiver@example.org'?'CAREGIVER':'ADMIN';return send(profile())}
        if(path==='auth/logout'&&options.method==='POST'){role=null;return send({status:'logged_out'})}
        if(path==='me')return role?send(profile()):send({error:'not_authorized'},403);
        if(!role)return send({error:'not_authorized'},403);
        const prefix='homes/'+home+'/';
        if(!path.startsWith(prefix))return send({error:'not_authorized'},403);
        const sub=path.slice(prefix.length);
        if(['sim/catalog','sim/runs','sim/reset','engineering'].some(value=>sub===value||sub.startsWith(value+'/'))&&role!=='ADMIN')return send({error:'not_authorized'},403);
        if(sub==='overview')return send({home_id:home,test_only:true,source:'HOST_SIMULATION_TEST_ONLY',physical_status:'UNAVAILABLE',physical_status_reason:'NO_HUB_CLOUDSYNC',physical_data_contract:'GS-148_CLOUDSYNC',monitoring:'UNKNOWN',source_freshness:'UNKNOWN',recent_events:events(),routine_decisions:decisions(),runs})
        if(sub==='devices')return send({home_id:home,test_only:true,devices:[],physical_status:'UNAVAILABLE',physical_status_reason:'NO_HUB_CLOUDSYNC',physical_data_contract:'GS-148_CLOUDSYNC'})
        if(sub==='incidents')return send({home_id:home,test_only:true,incidents:[]})
        if(sub.startsWith('reports'))return send({home_id:home,test_only:true,run_count:runs.length,runs,outcomes:{PASS:runs.length,FAIL:0,BLOCKED:0,NOT_RUN:0},event_count:runs.length,incident_count:0,period:'week'})
        if(sub==='routines')return send({home_id:home,test_only:true,learning_status:'UNSUPPORTED_MULTI_DAY',source:'HOST_SIMULATION_TEST_ONLY',decisions:decisions(),runs:runs.filter(run=>run.scenario_id.startsWith('morning-'))})
        if(sub==='engineering')return send({home_id:home,test_only:true,gs124_health:{status:'UNSUPPORTED',devices:[]},hardware_evidence:'UNKNOWN',physical_status:'UNAVAILABLE',physical_status_reason:'NO_HUB_CLOUDSYNC',physical_data_contract:'GS-148_CLOUDSYNC',source_revision:'0123456789ab',runs})
        if(sub==='sim/catalog')return send({scenarios:[{id:'motion-room1-visible',title:'Motion in visible room'},{id:'morning-missing-covered',title:'Morning activity absent'}]})
        if(sub==='sim/runs'&&options.method==='POST'){const scenario=JSON.parse(options.body).scenario_id,result=makeResult(scenario),item={run_id:'mock-run-'+(runs.length+1),scenario_id:scenario,status:'PASS',created_at:1000,result};runs.unshift(item);return send(item,201)}
        if(sub==='sim/runs')return send({runs})
        if(sub.startsWith('sim/runs/')){const saved=runs.find(run=>run.run_id===sub.split('/').at(-1));return saved?send(saved):send({error:'not_found'},404)}
        if(sub==='sim/reset')return send({simulation_generation:2,saved_history:'PRESERVED'})
        return send({error:'not_found'},404)
      };
    })()'''
    cdp(ws,'Page.enable');cdp(ws,'Runtime.enable')
    cdp(ws,'Page.addScriptToEvaluateOnNewDocument',{'source':mock})
    cdp(ws,'Page.navigate',{'url':self.base+'/'})
    def evaluate(expression):
     return cdp(ws,'Runtime.evaluate',{'expression':expression,'returnByValue':True}).get('result',{}).get('value')
    deadline=time.time()+15;screen=''
    while time.time()<deadline:
     screen=evaluate("document.querySelector('#homeTab')?.innerText||''") or ''
     if 'Sign in to your authorized Home' in screen:break
     time.sleep(.1)
    self.assertIn('Sign in to your authorized Home',screen)
    evaluate("(()=>{document.querySelector('[name=email]').value='owner@example.org';document.querySelector('[name=password]').value='test-password';document.querySelector('#loginForm').requestSubmit()})()")
    deadline=time.time()+15;tabs=[]
    while time.time()<deadline:
     tabs=evaluate("Array.from(document.querySelectorAll('.bottom-nav button')).map(button=>button.dataset.tab)") or []
     if 'simulation' in tabs:break
     time.sleep(.1)
    self.assertEqual(tabs,['home','simulation','reports','devices','incidents','routines','engineering','settings'])
    self.assertIn('Your home overview',evaluate("document.querySelector('#homeTab').innerText"))
    self.assertIn('Real-home monitoring is not active yet.',evaluate("document.querySelector('#homeTab').innerText"))
    self.assertIn('Run a test scenario',evaluate("document.querySelector('#homeTab').innerText"))
    evaluate("document.querySelector('.caregiver-tech summary').click()")
    self.assertIn('Physical Home: UNAVAILABLE / NO_HUB_CLOUDSYNC',evaluate("document.querySelector('#homeTab').innerText"))
    self.assertIn('Planned real Hub event interface: GS-148_CLOUDSYNC.',evaluate("document.querySelector('#homeTab').innerText"))
    self.assertIn('Real monitoring freshness: UNKNOWN',evaluate("document.querySelector('#homeTab').innerText"))
    evaluate("document.querySelector('#openSimulation').click()")
    deadline=time.time()+15
    while time.time()<deadline and evaluate("!!document.querySelector('#scenarioChoice')") is not True:time.sleep(.1)
    self.assertIsNotNone(evaluate("document.querySelector('#scenarioChoice')"))
    evaluate("(()=>{const select=document.querySelector('#scenarioChoice');select.options[0].selected=true;document.querySelector('#runScenario').click()})()")
    deadline=time.time()+15;detail=''
    while time.time()<deadline:
     detail=evaluate("document.querySelector('#homeTab')?.innerText||''") or ''
     if 'Expected versus observed' in detail:break
     time.sleep(.1)
    self.assertIn('simulated-event-1',detail)
    self.assertIn('Export JSON',detail)
    evaluate("document.querySelector('[data-tab=simulation]').click()")
    deadline=time.time()+15
    while time.time()<deadline and evaluate("!!document.querySelector('#scenarioChoice')") is not True:time.sleep(.1)
    evaluate("(()=>{const select=document.querySelector('#scenarioChoice');Array.from(select.options).forEach(option=>option.selected=option.value==='morning-missing-covered');document.querySelector('#runScenario').click()})()")
    deadline=time.time()+15;morning=''
    while time.time()<deadline:
     morning=evaluate("document.querySelector('#homeTab')?.innerText||''") or ''
     if 'MORNING_ROUTINE_MISSING' in morning:break
     time.sleep(.1)
    self.assertIn('Expected morning concern',morning)
    evaluate("document.querySelector('[data-tab=home]').click()")
    deadline=time.time()+15;home_trace=''
    while time.time()<deadline:
     home_trace=evaluate("document.querySelector('#homeTab')?.innerText||''") or ''
     if 'Recent routine decisions' in home_trace:break
     time.sleep(.1)
    self.assertIn('Recent test events',home_trace)
    self.assertIn('MORNING_ROUTINE_MISSING',home_trace)
    self.assertIn('Recent routine decisions',home_trace)
    self.assertIn('no_qualifying_evidence',home_trace)
    evaluate("document.querySelector('[data-tab=routines]').click()")
    deadline=time.time()+15;routine=''
    while time.time()<deadline:
     routine=evaluate("document.querySelector('#homeTab')?.innerText||''") or ''
     if 'UNSUPPORTED_MULTI_DAY' in routine:break
     time.sleep(.1)
    self.assertIn('Inspect morning-missing-covered',routine)
    evaluate("document.querySelector('.open-run').click()")
    deadline=time.time()+15;routine_detail=''
    while time.time()<deadline:
     routine_detail=evaluate("document.querySelector('#homeTab')?.innerText||''") or ''
     if 'Expected morning concern' in routine_detail:break
     time.sleep(.1)
    self.assertIn('MORNING_ROUTINE_MISSING',routine_detail)
    self.assertIn('not form a multi-day resident baseline',routine_detail)
    evaluate("document.querySelector('[data-tab=engineering]').click()")
    deadline=time.time()+15;engineering=''
    while time.time()<deadline:
     engineering=evaluate("document.querySelector('#homeTab')?.innerText||''") or ''
     if 'Installation Overview' in engineering:break
     time.sleep(.1)
    areas=evaluate("Array.from(document.querySelectorAll('#engineeringArea option')).map(option=>option.textContent)")
    self.assertEqual(len(areas),7)
    self.assertIn('UNSUPPORTED',engineering)
    evaluate("document.querySelector('[data-tab=settings]').click()")
    deadline=time.time()+15
    while time.time()<deadline and evaluate("!!document.querySelector('#logoutButton')") is not True:time.sleep(.1)
    self.assertIsNotNone(evaluate("document.querySelector('#logoutButton')"))
    evaluate("document.querySelector('#logoutButton').click()")
    deadline=time.time()+10
    while time.time()<deadline and evaluate("!!document.querySelector('#loginForm')") is not True:time.sleep(.1)
    evaluate("(()=>{document.querySelector('[name=email]').value='caregiver@example.org';document.querySelector('[name=password]').value='test-password';document.querySelector('#loginForm').requestSubmit()})()")
    deadline=time.time()+15;caregiver_tabs=[]
    while time.time()<deadline:
     caregiver_tabs=evaluate("Array.from(document.querySelectorAll('.bottom-nav button')).map(button=>button.dataset.tab)") or []
     visible=evaluate("!document.querySelector('.bottom-nav').hidden")
     if visible and 'home' in caregiver_tabs:break
     time.sleep(.1)
    self.assertEqual(caregiver_tabs,['home','reports','devices','incidents','routines','settings'])
    direct=cdp(ws,'Runtime.evaluate',{'expression':"fetch('https://care.gharsajag.in/lite/v1/homes/gs177-test-browser-home/engineering',{credentials:'include'}).then(response=>response.status)",'awaitPromise':True,'returnByValue':True})
    self.assertEqual(direct.get('result',{}).get('value'),403)
    print('PASS connected Lite browser E2E: admin login/navigation, simulation result, routine boundary, seven Engineering areas, caregiver UI/API denial (mock transport)')
   finally: ws.close()
  finally:
   self.web.runtime_config=original
   proc.terminate()
   try:proc.wait(timeout=5)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
   shutil.rmtree(profile,ignore_errors=True)
 def test_authenticated_gs148_home_shows_committed_host_sim_event_and_docked_tabs(self):
  original=self.web.runtime_config
  self.web.runtime_config={"mode":"caregiver","backendOrigin":"https://care.gharsajag.in/","caregiverApiConfigured":True,"appVersion":"browser-test","sourceRevision":"0123456789ab"}
  port=free_port();profile=tempfile.mkdtemp(prefix='ps-connected-product-home-')
  proc=subprocess.Popen([self.chromium,'--headless=new','--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--disable-background-networking','--no-first-run','--remote-allow-origins=*',f'--remote-debugging-port={port}',f'--user-data-dir={profile}','about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  try:
   version=None
   for _ in range(100):
    try:version=json.loads(urlopen(f'http://127.0.0.1:{port}/json/version',timeout=.5).read());break
    except Exception:time.sleep(.1)
   self.assertIsNotNone(version,'Chromium DevTools endpoint did not start')
   req=Request(f'http://127.0.0.1:{port}/json/new?{quote(self.base,safe="/:?=&")}',method='PUT')
   page=json.loads(urlopen(req,timeout=3).read());ws=websocket.create_connection(page['webSocketDebuggerUrl'],timeout=10)
   try:
    mock=r'''(()=>{
      const home='gs177-test-product';let role=null,homeSource='AUTHENTICATED_GS148_TEST_ONLY';window.__caregiverRequests=[];
      window.__setHomeSource=value=>{homeSource=value};
      const eventKey={physical_device_id:'test-c3-bedroom',logical_node_id:'bedroom',origin_session_id:10,event_sequence:1};
      const event={event_id:'evt-host-sim-1',event_key:eventKey,kind:'MOTION',location:'bedroom',occurred_at:1792442670,received_at:1792442675,source_type:'NODE',tone:'positive'};
      const profile=()=>({account_id:'browser-owner',email:'owner@example.org',home_id:home,role,test_only:true,expires_at:4102444800,backend_revision:'browser-test'});
      const send=(body,status=200)=>Promise.resolve(new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json'}}));
      const original=window.fetch.bind(window);
      window.fetch=async(input,options={})=>{
        const url=new URL(String(input));
        if(url.origin!=='https://care.gharsajag.in')return original(input,options);
        const path=url.pathname.replace('/lite/v1/','');window.__caregiverRequests.push(path);
        if(path==='auth/login'&&options.method==='POST'){role='ADMIN';return send(profile())}
        if(path==='me')return role?send(profile()):send({error:'not_authorized'},403);
        if(!role)return send({error:'not_authorized'},403);
        const prefix='homes/'+home+'/';if(!path.startsWith(prefix))return send({error:'not_authorized'},403);
        const sub=path.slice(prefix.length);
        if(sub==='overview')return send({home_id:home,test_only:true,source:homeSource,physical_status:'NOT_RUN',physical_status_reason:'TEST_ONLY_PHYSICAL_NOT_RUN',physical_data_contract:'GS-148_CLOUDSYNC_V2',monitoring:'UNKNOWN',source_freshness:'STALE',last_hub_at:1792440000,event_count:1,recent_events:[event]});
        if(sub==='devices')return send({home_id:home,test_only:true,source:homeSource,devices:[{physical_node_id:'test-c3-bedroom',logical_node_id:'bedroom',status:'ONLINE',coverage:'COVERED',profile_id:'default'}]});
        if(sub==='routines')return send({home_id:home,test_only:true,source:homeSource,learning_status:'NOT_ENABLED',decisions:[]});
        if(sub==='incidents')return send({home_id:home,test_only:true,source:homeSource,incidents:[]});
        if(sub==='reports')return send({home_id:home,test_only:true,source:homeSource,event_count:1,recent_events:[event]});
        if(sub==='auth/logout'&&options.method==='POST'){role=null;return send({status:'logged_out'})}
        if(sub==='engineering')return send({error:'not_authorized'},403);
        return send({error:'not_found'},404);
      };
    })()'''
    cdp(ws,'Page.enable');cdp(ws,'Runtime.enable')
    cdp(ws,'Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
    cdp(ws,'Page.addScriptToEvaluateOnNewDocument',{'source':mock})
    cdp(ws,'Page.navigate',{'url':self.base+'/'})
    def evaluate(expression):
     return cdp(ws,'Runtime.evaluate',{'expression':expression,'returnByValue':True}).get('result',{}).get('value')
    deadline=time.time()+15;screen=''
    while time.time()<deadline:
     screen=evaluate("document.querySelector('#homeTab')?.innerText||''") or ''
     if 'Sign in to your authorized Home' in screen:break
     time.sleep(.1)
    self.assertIn('Sign in to your authorized Home',screen)
    evaluate("(()=>{document.querySelector('[name=email]').value='owner@example.org';document.querySelector('[name=password]').value='test-password';document.querySelector('#loginForm').requestSubmit()})()")
    deadline=time.time()+15;home_text=''
    while time.time()<deadline:
     home_text=evaluate("document.querySelector('#homeTab')?.innerText||''") or ''
     if 'Motion recorded' in home_text:break
     time.sleep(.1)
    self.assertIn('Monitoring data is stale',home_text)
    self.assertIn('Monitoring source stale · status unknown',home_text)
    self.assertIn('Motion recorded',home_text)
    self.assertIn('bedroom',home_text)
    self.assertIn('HOST_SIM · TEST_ONLY',home_text)
    self.assertIn('physical C3/S3 qualification NOT_RUN',home_text)
    self.assertNotIn('Run a test scenario',home_text)
    node=evaluate("(()=>{const e=document.querySelector('[data-home-card=devices] [data-node-status]');return {status:e?.dataset.nodeStatus,text:e?.innerText}})()")
    self.assertEqual(node['status'],'UNKNOWN')
    self.assertIn('Last authenticated report: ONLINE · source not current',node['text'])
    event=evaluate("(()=>{const e=document.querySelector('.connected-product-event');return {origin:e?.dataset.sourceOrigin,key:e?.getAttribute('data-event-key'),homeSource:document.querySelector('.test-watermark')?.innerText}})()")
    self.assertEqual(event['origin'],'HOST_SIM · TEST_ONLY')
    self.assertEqual(event['key'],json.dumps({'physical_device_id':'test-c3-bedroom','logical_node_id':'bedroom','origin_session_id':10,'event_sequence':1},separators=(',',':')))
    nav=evaluate("(()=>{const n=document.querySelector('.bottom-nav'),h=document.querySelector('.topbar'),r=n.getBoundingClientRect(),hr=h.getBoundingClientRect(),s=getComputedStyle(n);return {position:s.position,left:Math.round(r.left),width:Math.round(r.width),viewport:innerWidth,radius:s.borderRadius,shadow:s.boxShadow,gap:Math.round(r.top-hr.bottom),adjacent:h.nextElementSibling===n,scrollWidth:n.scrollWidth,clientWidth:n.clientWidth,tabs:Array.from(n.querySelectorAll('button[data-tab]')).map(b=>b.dataset.tab)}})()")
    self.assertEqual(nav['position'],'sticky')
    self.assertEqual(nav['left'],0)
    self.assertEqual(nav['width'],nav['viewport'])
    self.assertEqual(nav['radius'],'0px')
    self.assertIn(nav['shadow'],('none','rgba(0, 0, 0, 0) 0px 0px 0px 0px'))
    self.assertLessEqual(abs(nav['gap']),1)
    self.assertTrue(nav['adjacent'])
    self.assertEqual(nav['tabs'],['home','simulation','reports','devices','incidents','routines','engineering','settings'])
    self.assertGreater(nav['scrollWidth'],nav['clientWidth'])
    self.assertFalse(any(path.startswith(('sim/','simulation')) for path in evaluate('window.__caregiverRequests')))
    evaluate("document.querySelector('[data-tab=settings]').click()")
    deadline=time.time()+15
    while time.time()<deadline and evaluate("!!document.querySelector('#logoutButton')") is not True:time.sleep(.1)
    self.assertIsNotNone(evaluate("document.querySelector('#logoutButton')"))
    settings_tab=evaluate("(()=>{const b=document.querySelector('[data-tab=settings]'),n=document.querySelector('.bottom-nav').getBoundingClientRect(),r=b.getBoundingClientRect();return {current:b.getAttribute('aria-current'),active:b.classList.contains('active'),visible:r.left>=n.left&&r.right<=n.right}})()")
    self.assertEqual(settings_tab,{'current':'page','active':True,'visible':True})
    evaluate("document.querySelector('[data-tab=devices]').click()")
    deadline=time.time()+15
    while time.time()<deadline and 'Devices and NodeHealth' not in (evaluate("document.querySelector('#homeTab')?.innerText||''") or ''):time.sleep(.1)
    self.assertIn('Devices and NodeHealth',evaluate("document.querySelector('#homeTab').innerText"))
    evaluate("document.querySelector('[data-tab=reports]').click()")
    deadline=time.time()+15
    while time.time()<deadline and 'Committed event history' not in (evaluate("document.querySelector('#homeTab')?.innerText||''") or ''):time.sleep(.1)
    self.assertIn('Committed event history',evaluate("document.querySelector('#homeTab').innerText"))
    evaluate("window.__setHomeSource('UNRECOGNIZED_SOURCE');document.querySelector('[data-tab=home]').click()")
    deadline=time.time()+15;unknown_text=''
    while time.time()<deadline:
     unknown_text=evaluate("document.querySelector('#homeTab')?.innerText||''") or ''
     if 'simulated data is not shown' in unknown_text:break
     time.sleep(.1)
    self.assertIn('Monitoring, events and resident status are unknown; simulated data is not shown',unknown_text)
    self.assertNotIn('Motion recorded',unknown_text)
    self.assertIsNone(evaluate("document.querySelector('.connected-product-event')"))
    print('PASS authenticated GS-148 Home browser regression: committed HOST_SIM EventKey/room/time, stale UNKNOWN, stale Node ONLINE downgraded to UNKNOWN, full-width docked navigation, existing tabs preserved, unrecognized source fail-closed; no simulator request')
   finally:ws.close()
  finally:
   self.web.runtime_config=original
   proc.terminate()
   try:proc.wait(timeout=5)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
   shutil.rmtree(profile,ignore_errors=True)
if __name__=='__main__':unittest.main(verbosity=2)
