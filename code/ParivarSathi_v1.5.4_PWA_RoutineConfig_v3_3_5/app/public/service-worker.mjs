// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module A02 App home
// @requirements F05, F06, F09, F11, F14, E01, E04, E10, NFR-01, NFR-02, NFR-10
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// Home view functions convert a server snapshot to readable labels. Do not move eligibility or incident
// creation into this layer. A stale value can remain visible if labelled with age; it must not acquire a
// new timestamp because the page rerendered.

const CACHE = "ghar-sajag-prototype-v1";
const ASSETS = ["./", "./index.html", "./styles.css", "./app.mjs", "./manifest.webmanifest"];

self.addEventListener("install", (event) => event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(ASSETS))));
self.addEventListener("activate", (event) => event.waitUntil(
  caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
));
self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
});
