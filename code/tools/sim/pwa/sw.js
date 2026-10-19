
// Bump the cache identity when the static allowlist changes so activation
// removes entries retained by an older worker (including simulator-only JS).
const CACHE='parivar-saathi-caregiver-v5';
const ASSETS=['./','styles.css','boot.mjs','app.js','runtime_mode.mjs','performance_runtime.mjs','validation_engine.mjs','schedule_feedback.mjs','assets/parivar-saathi-icon-192.png'];
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS))));
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{
  if(e.request.method!=='GET' || !ASSETS.some(asset=>new URL(asset,self.registration.scope).pathname===new URL(e.request.url).pathname))return;
  e.respondWith(fetch(e.request).then(r=>{if(r.ok){const copy=r.clone();caches.open(CACHE).then(c=>c.put(e.request,copy))}return r}).catch(()=>caches.match(e.request)));
});
