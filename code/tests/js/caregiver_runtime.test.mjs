import {readFileSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {dirname,resolve} from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import {normalizeRuntimeConfig,parseCaregiverBackendOrigin,requestHeaders,requestUrl} from '../../tools/sim/pwa/runtime_mode.mjs';

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

test('API URLs remain pinned to the configured HTTPS origin', () => {
  const runtime=normalizeRuntimeConfig({mode:'caregiver',backendOrigin:'https://care.gharsajag.in'},'https://appassets.androidplatform.net');
  assert.equal(requestUrl(runtime,'/healthz'),'https://care.gharsajag.in/healthz');
  assert.equal(requestUrl(runtime,'https://attacker.example/path'),'');
});


test('GS-177 connected caregiver UI keeps technical state secondary and preserves safe mobile navigation', () => {
  const codeRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
  const scriptPath = resolve(codeRoot,'tools/sim/pwa/connected_lite.mjs');
  const stylesPath = resolve(codeRoot,'tools/sim/pwa/styles.css');
  const androidPath = resolve(codeRoot,'parivar_saathi_android_app/android/app/src/main/java/in/gharsajag/caregiver/MainActivity.kt');
  // Check executable syntax, not only that expected text exists.
  execFileSync(process.execPath,['--check',scriptPath]);
  const script = readFileSync(scriptPath,'utf8');
  const css = readFileSync(stylesPath,'utf8');
  const android = readFileSync(androidPath,'utf8');

  assert.match(script,/CAREGIVER HOME · TEST ONLY/);
  assert.match(script,/Your home overview/);
  assert.match(script,/Real-home monitoring is not active yet/);
  assert.match(script,/Technical connection details/);
  assert.match(script,/function openTab\(next\)/);
  assert.match(script,/Run selected scenario/);
  assert.match(script,/id="scenarioChoice" size="1"/);
  assert.match(script,/tab!=='simulation'/);
  assert.match(css,/connected-lite-runtime \.topbar[\s\S]*?position:sticky/);
  assert.match(css,/connected-lite-runtime \.bottom-nav[\s\S]*?safe-area-inset-bottom/);
  assert.match(css,/connected-lite-runtime \.caregiver-tiles/);
  assert.match(android,/WindowInsetsCompat\.Type\.systemBars\(\)/);
  assert.match(android,/view\.setPadding\(safe\.left, safe\.top, safe\.right, safe\.bottom\)/);
});
