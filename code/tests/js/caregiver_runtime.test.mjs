import test from 'node:test';
import assert from 'node:assert/strict';
import {normalizeRuntimeConfig,parseCaregiverBackendOrigin,requestHeaders,requestUrl} from '../../tools/sim/pwa/runtime_mode.mjs';

test('caregiver mode accepts only an internal public HTTPS origin and never enables API claims', () => {
  const runtime=normalizeRuntimeConfig({mode:'caregiver',backendOrigin:'https://care.gharsajag.in/',caregiverApiConfigured:true},'https://care.gharsajag.in');
  assert.equal(runtime.mode,'caregiver');
  assert.equal(runtime.backendOrigin,'https://care.gharsajag.in/');
  assert.equal(runtime.caregiverApiConfigured,false);
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
