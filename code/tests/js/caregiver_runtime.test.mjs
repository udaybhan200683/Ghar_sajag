import {readFileSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {dirname,resolve} from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import {normalizeRuntimeConfig,parseCaregiverBackendOrigin,requestHeaders,requestUrl} from '../../tools/sim/pwa/runtime_mode.mjs';
import {bindPasswordVisibility} from '../../tools/sim/pwa/password_visibility.mjs';

test('GS177 caregiver password visibility toggles accessibly without changing value or selection', () => {
  class PasswordInput {
    constructor() {
      this._type='password';this.value='private-development-secret';
      this.selectionStart=4;this.selectionEnd=14;this.selectionDirection='forward';
    }
    get type(){return this._type;}
    set type(value){this._type=value;this.selectionStart=this.selectionEnd=this.value.length;}
    setSelectionRange(start,end,direction){this.selectionStart=start;this.selectionEnd=end;this.selectionDirection=direction;}
  }
  class ToggleButton {
    constructor(){this.attributes={};this.listeners={};this.textContent='';}
    addEventListener(name,listener){this.listeners[name]=listener;}
    setAttribute(name,value){this.attributes[name]=value;}
    click(){this.listeners.click();}
  }
  const input=new PasswordInput(),button=new ToggleButton();
  const reset=bindPasswordVisibility(input,button);
  assert.equal(input.type,'password');
  assert.equal(button.textContent,'Show');
  assert.equal(button.attributes['aria-label'],'Show password');
  assert.equal(button.attributes['aria-pressed'],'false');
  button.click();
  assert.equal(input.type,'text');
  assert.equal(input.value,'private-development-secret');
  assert.deepEqual([input.selectionStart,input.selectionEnd,input.selectionDirection],[4,14,'forward']);
  assert.equal(button.textContent,'Hide');
  assert.equal(button.attributes['aria-label'],'Hide password');
  assert.equal(button.attributes['aria-pressed'],'true');
  button.click();
  assert.equal(input.type,'password');
  assert.equal(input.value,'private-development-secret');
  assert.deepEqual([input.selectionStart,input.selectionEnd,input.selectionDirection],[4,14,'forward']);
  button.click();
  reset();
  assert.equal(input.type,'password','authentication failure resets a visible value to hidden');
  assert.equal(button.attributes['aria-pressed'],'false');
});

test('caregiver mode accepts only a public HTTPS origin and enables authenticated API transport', () => {
  const runtime=normalizeRuntimeConfig({mode:'caregiver',backendOrigin:'https://care.gharsajag.in/',caregiverApiConfigured:true},'https://care.gharsajag.in');
  assert.equal(runtime.mode,'caregiver');
  assert.equal(runtime.backendOrigin,'https://care.gharsajag.in/');
  assert.equal(runtime.caregiverApiConfigured,true);
  assert.deepEqual(requestHeaders(runtime),{});
});

test('caregiver mode rejects HTTP, local, reserved, credential-bearing and path origins', () => {
  for (const input of ['http://care.gharsajag.in','https://localhost','https://api.local','https://api.invalid','https://user:pass@care.gharsajag.in','https://care.gharsajag.in/app','https://care.gharsajag.in/?home=demo']) {
    assert.equal(parseCaregiverBackendOrigin(input),'',input);
  }
});

test('private LAN backend origin is accepted only in the explicit GS-179 TEST_ONLY profile', () => {
  assert.equal(parseCaregiverBackendOrigin('https://192.168.1.6'), '');
  const raw = {mode:'caregiver',backendOrigin:'https://192.168.1.6',gs179LocalLanTestOnly:true};
  const runtime = normalizeRuntimeConfig(raw,'https://192.168.1.6');
  assert.equal(runtime.backendOrigin,'https://192.168.1.6/');
  assert.equal(runtime.caregiverApiConfigured,true);
  assert.equal(requestUrl(runtime,'/lite/v1/me'),'https://192.168.1.6/lite/v1/me');
  for (const input of ['https://8.8.8.8','https://172.15.1.2','https://172.32.1.2',
    'https://192.168.001.6','https://10.0.0.256','https://127.0.0.1']) {
    assert.equal(parseCaregiverBackendOrigin(input,{gs179LocalLanTestOnly:true}),'',input);
  }
  assert.equal(normalizeRuntimeConfig({...raw,gs179LocalLanTestOnly:false},'https://192.168.1.6').backendOrigin,'');
  assert.equal(runtime.localBackendReconnect,false);
});

test('GS177-PWA-LAN-RECONNECT-001 stable mDNS origin survives router changes and pairing stays TEST_ONLY', () => {
  const origin='https://desktop-r1.local';
  assert.equal(parseCaregiverBackendOrigin(origin), '');
  const runtime=normalizeRuntimeConfig({mode:'caregiver',backendOrigin:origin,
    gs179LocalLanTestOnly:true,localBackendReconnect:true},origin);
  assert.equal(runtime.backendOrigin,`${origin}/`);
  assert.equal(runtime.localBackendReconnect,true);
  assert.equal(requestUrl(runtime,'/lite/v1/me'),`${origin}/lite/v1/me`);
  const codeRoot=resolve(dirname(fileURLToPath(import.meta.url)), '../..');
  const caregiverUi=readFileSync(resolve(codeRoot,'tools/sim/pwa/connected_lite.mjs'),'utf8');
  assert.match(caregiverUi,/runtime\.localBackendReconnect\?'<p><a class="local-backend-reconnect"/);
  assert.match(caregiverUi,/gharsajag:\/\/backend\/reconnect/);
  for(const input of ['https://local','https://evil.example.local','https://user@desktop-r1.local',
    'https://desktop-r1.local:8443','http://desktop-r1.local'])
    assert.equal(parseCaregiverBackendOrigin(input,{gs179LocalLanTestOnly:true}),'',input);
  assert.equal(normalizeRuntimeConfig({mode:'caregiver',backendOrigin:origin,
    gs179LocalLanTestOnly:false,localBackendReconnect:true},origin).localBackendReconnect,false);
});

test('simulator identity is enabled only by an explicit same-origin lab config', () => {
  const explicit=normalizeRuntimeConfig({mode:'local-simulator',allowSimulator:true,actorId:'simulation-owner',homeId:'simulation-home',backendOrigin:'http://127.0.0.1:8765/'},'http://127.0.0.1:8765');
  assert.equal(explicit.mode,'local-simulator');
  assert.equal(requestHeaders(explicit)['X-Actor-Id'],'simulation-owner');
  assert.equal(requestUrl(explicit,'/pwa/state'),'http://127.0.0.1:8765/pwa/state');
});

test('missing simulator opt-in or cross-origin endpoint strips development identity', () => {
  for (const raw of [
    {mode:'local-simulator',actorId:'simulation-owner',homeId:'simulation-home',backendOrigin:'http://127.0.0.1:8765/'},
    {mode:'local-simulator',allowSimulator:true,actorId:'simulation-owner',homeId:'simulation-home',backendOrigin:'http://attacker.local/'},
  ]) {
    const runtime=normalizeRuntimeConfig(raw,'http://127.0.0.1:8765');
    assert.equal(runtime.mode,'caregiver');
    assert.deepEqual(requestHeaders(runtime),{});
  }
});

test('offline caregiver runtime has no data route when backend origin is absent', () => {
  const runtime=normalizeRuntimeConfig({mode:'caregiver'},'https://appassets.androidplatform.net');
  assert.equal(runtime.mode,'caregiver');
  assert.equal(runtime.backendOrigin,'');
  assert.equal(requestUrl(runtime,'/v1/homes/home/reports'),'');
});

test('Hub Wi-Fi native discovery is explicit and cannot become credential submission', () => {
  const base={mode:'caregiver',backendOrigin:'https://care.gharsajag.in/'};
  assert.equal(normalizeRuntimeConfig(base,'https://care.gharsajag.in').hubWifiNativeDiscovery,false);
  assert.equal(normalizeRuntimeConfig({...base,hubWifiNativeDiscovery:'true'},'https://care.gharsajag.in').hubWifiNativeDiscovery,false);
  assert.equal(normalizeRuntimeConfig({...base,hubWifiNativeDiscovery:true},'https://care.gharsajag.in').hubWifiNativeDiscovery,true);
  const codeRoot=resolve(dirname(fileURLToPath(import.meta.url)), '../..');
  const settings=readFileSync(resolve(codeRoot,'tools/sim/pwa/connected_lite.mjs'),'utf8');
  assert.match(settings,/Add Hub \/ configure Hub Wi-Fi/);
  assert.match(settings,/Secure pairing, protected credential storage and Home claim/);
  assert.doesNotMatch(settings,/wifiPassword|wifi_password|provisionCredential/);
});

test('caregiver Settings shows only authenticated server-confirmed desired/applied routine versions', () => {
  const codeRoot=resolve(dirname(fileURLToPath(import.meta.url)), '../..');
  const settings=readFileSync(resolve(codeRoot,'tools/sim/pwa/connected_lite.mjs'),'utf8');
  assert.match(settings,/Household routine policy · TEST_ONLY/);
  assert.match(settings,/refreshHouseholdRoutineConfiguration\(profile\.home_id\)/);
  assert.match(settings,/profile\?\.test_only===true\)void refreshHouseholdRoutineConfiguration/);
  assert.match(settings,/api\(`homes\/\$\{encodeURIComponent\(homeId\)\}\/routine-config`\)/);
  assert.match(settings,/snapshot\.home_id!==homeId/);
  assert.match(settings,/desired_version/);
  assert.match(settings,/applied_version/);
  assert.match(settings,/snapshot\.desired_config\|\|snapshot\.applied_config/);
  assert.doesNotMatch(settings,/X-Actor-Id/);
});

test('API URLs remain pinned to the configured HTTPS origin', () => {
  const runtime=normalizeRuntimeConfig({mode:'caregiver',backendOrigin:'https://care.gharsajag.in'},'https://appassets.androidplatform.net');
  assert.equal(requestUrl(runtime,'/healthz'),'https://care.gharsajag.in/healthz');
  assert.equal(requestUrl(runtime,'https://attacker.example/path'),'');
});


test('GS-177 connected caregiver UI restores Home safely and keeps the approved four-tab layout', () => {
  const codeRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
  const scriptPath = resolve(codeRoot,'tools/sim/pwa/connected_lite.mjs');
  const caregiverStylesPath = resolve(codeRoot,'tools/sim/pwa/caregiver.css');
  const androidPath = resolve(codeRoot,'parivar_saathi_android_app/android/app/src/main/java/in/gharsajag/caregiver/MainActivity.kt');
  const androidManifestPath = resolve(codeRoot,'parivar_saathi_android_app/android/app/src/main/AndroidManifest.xml');
  const indexPath = resolve(codeRoot,'tools/sim/pwa/index.html');
  // Check executable syntax, not only that expected text exists.
  execFileSync(process.execPath,['--check',scriptPath]);
  const script = readFileSync(scriptPath,'utf8');
  const caregiverCss = readFileSync(caregiverStylesPath,'utf8');
  const android = readFileSync(androidPath,'utf8');
  const androidManifest = readFileSync(androidManifestPath,'utf8');
  const index = readFileSync(indexPath,'utf8');

  assert.match(script,/performance\.measure\('gs177-login-form-visible'/);
  assert.match(script,/GS177_STARTUP login_form_visible_ms=/);
  assert.match(script,/async function restoreSession\(\)/);
  assert.match(script,/form\.addEventListener\('focusin',markCredentialEntry/);
  assert.match(script,/form\.addEventListener\('input',markCredentialEntry/);
  assert.match(script,/profile=verifiedProfile;view=null;tab='home'/);
  assert.match(script,/bindPasswordVisibility\(/);
  assert.match(script,/resetPasswordVisibility\(\)/);
  assert.match(script,/<button type="button" data-password-visibility aria-controls="loginPassword" aria-label="Show password" aria-pressed="false">Show<\/button>/);
  assert.match(script,/querySelector\('button\[type="submit"\]'\)/);
  assert.match(script,/const verifiedProfile=await api\('me'\)/);
  assert.match(script,/Current authorized Home data is unavailable/);
  assert.match(script,/function renderHome\(\)/);
  for(const title of ['I am OK','Main door','Night activity','Device health','Recent important events'])
    assert.ok(script.includes(title),`Home must render ${title}`);
  assert.match(script,/Monitoring status is unknown/);
  assert.match(script,/simulated data is not shown/);
  assert.doesNotMatch(script,/Home looks normal|All is well at home|4\/4 devices online|No unusual activity/);
  assert.match(script,/const available=\['home','devices','reports','settings'\]/);
  assert.match(script,/profile\?\.role==='ADMIN'&&profile\?\.test_only===true/);
  assert.match(script,/function navCategory\(name\)/);
  assert.doesNotMatch(script,/dockNavigationUnderHeader/);
  assert.match(script,/function openTab\(next\)/);
  assert.match(script,/runtime\.localBackendReconnect\?'<p><a class="local-backend-reconnect"/);
  assert.match(script,/gharsajag:\/\/backend\/reconnect/);
  assert.match(script,/const localReconnect=runtime\.localBackendReconnect\?'<div class="settings-actions"/);
  assert.match(script,/gharsajag:\/\/backend\/reset/);
  assert.match(script,/Run selected scenario/);
  assert.match(script,/id="scenarioChoice" size="1"/);
  assert.match(script,/function productEvents\(events,/);
  assert.match(script,/HOST_SIM · TEST_ONLY/);
  assert.match(script,/function eventVisualSeverity\(event/);
  assert.match(script,/details\?\.tone==='CONCERN'/);
  assert.match(script,/routineCoverage!=='COVERED'/);
  assert.match(script,/const ACTIVE_INCIDENT_STATES=new Set\(\['OPEN','CLAIMED','ROUTE_EXHAUSTED'\]\)/);
  assert.match(script,/data-visual-severity=/);
  assert.match(script,/STALE · last reported/);
  assert.match(script,/routine_coverage:routines\.observation_coverage/);
  assert.match(script,/requestedTab==='devices'\|\|requestedTab==='incidents'/);
  assert.match(script,/if\(!explicitSimulationHome\(\)\)/);
  assert.match(script,/api\(`\$\{base\}\/overview`\),api\(`\$\{base\}\/devices`\),api\(`\$\{base\}\/routines`\),api\(`\$\{base\}\/incidents`\)/);
  assert.match(script,/function runDetail\(run\)/);
  assert.match(script,/Engine processing steps/);
  assert.match(script,/Routine \/ abnormality decision/);
  assert.match(script,/tab!=='simulation'/);
  assert.match(caregiverCss,/\.bottom-nav\{position:fixed;left:0;right:0;bottom:0/);
  assert.match(caregiverCss,/grid-template-columns:repeat\(4,minmax\(0,1fr\)\)/);
  assert.match(caregiverCss,/height:56px/);
  assert.match(caregiverCss,/border:0;border-top:1px solid #dceae1;border-radius:0;background:#fff;box-shadow:none/);
  assert.doesNotMatch(caregiverCss,/\.bottom-nav\{position:sticky;top:/);
  assert.match(caregiverCss,/\.connected-home \.hero/);
  assert.match(caregiverCss,/\.connected-home-timeline/);
  assert.match(caregiverCss,/\.connected-home \.hero\[data-attention="CONCERN"\]/);
  assert.match(caregiverCss,/overflow-wrap:break-word/);
  assert.match(caregiverCss,/grid-template-areas:"brand away" "brand datetime"/);
  assert.match(caregiverCss,/\.datetime\{text-align:right/);
  assert.match(caregiverCss,/\.away-wrap\{display:flex/);
  assert.match(index,/Apno ka khayal, har pal/);
  assert.match(index,/aria-label="Away mode unavailable"/);
  assert.match(index,/id="dateText"/);
  assert.match(index,/id="timeText"/);
  assert.match(index,/class="brand-icon"/);
  assert.match(android,/WindowInsetsCompat\.Type\.ime\(\)/);
  assert.match(android,/max\(safe\.bottom, keyboard\.bottom\)/);
  assert.match(androidManifest,/android:windowSoftInputMode="adjustResize"/);
  assert.match(android,/WindowInsetsCompat\.Type\.systemBars\(\)/);
  assert.match(android,/view\.setPadding\(safe\.left, safe\.top, safe\.right, max\(safe\.bottom, keyboard\.bottom\)\)/);
});
