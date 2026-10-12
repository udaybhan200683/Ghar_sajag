
const CACHE='parivar-sathi-phase3a-v1';
const ASSETS=['./','index.html','styles.css','app.js','performance_runtime.mjs','validation_engine.mjs','schedule_feedback.mjs','manifest.webmanifest','assets/icon.svg'];
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS))));
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{
  if(e.request.method!=='GET' || !ASSETS.some(asset=>new URL(asset,self.registration.scope).pathname===new URL(e.request.url).pathname))return;
  e.respondWith(fetch(e.request).then(r=>{if(r.ok){const copy=r.clone();caches.open(CACHE).then(c=>c.put(e.request,copy))}return r}).catch(()=>caches.match(e.request)));
});
