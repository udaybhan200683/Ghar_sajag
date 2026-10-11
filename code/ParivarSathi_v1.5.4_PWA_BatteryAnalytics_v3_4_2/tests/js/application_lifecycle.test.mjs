import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { runInNewContext } from "node:vm";

import { buildCreateHomeCommand, validateHouseholdDraft } from "../../app/src/features/onboarding/index.mjs";
import { buildDesiredConfig, configStatus } from "../../app/src/features/routines/index.mjs";
import { incidentActions } from "../../app/src/features/incidents/index.mjs";
import { ApiClient, VersionedCache, pushCapability } from "../../app/src/platform/index.mjs";
import { buildHomeView, timelineLabel } from "../../app/src/features/home/index.mjs";
import { addBounded } from "../../tools/sim/pwa/performance_runtime.mjs";

const app = (path) => new URL(`../../${path}`, import.meta.url);

test("PWA-GS130-ONBOARD-01 interrupted/reloaded create keeps retry idempotent", () => {
  const valid = { displayName: "Parents", timezone: "Asia/Kolkata", residents: [{ residentId: "r1", displayName: "R", consentActive: true }], primaryCaregiverId: "c1", backupCaregiverId: "c2" };
  assert.equal(validateHouseholdDraft({ ...valid, residents: [{ ...valid.residents[0], consentActive: false }] }).valid, false);
  const beforeReload = buildCreateHomeCommand(valid, "onboard-attempt-7");
  const afterReload = buildCreateHomeCommand(valid, "onboard-attempt-7");
  assert.deepEqual(afterReload, beforeReload);
  assert.equal(afterReload.idempotencyKey, "onboard-attempt-7");
  assert.deepEqual(afterReload.body.residents, [{ resident_id: "r1", display_name: "R", consent_active: true }]);
});

test("PWA-GS130-SCHEDULE-01 offline settings do not report success and retry after reconnect", async () => {
  let online = false;
  let sent;
  const api = new ApiClient(async (_path, request) => {
    if (!online) throw new TypeError("offline");
    sent = request;
    return { ok: true, status: 202, json: async () => ({ version: 8, applied_version: 7 }) };
  }, async () => "test-token");
  const config = buildDesiredConfig("home-1", 8, "Asia/Kolkata", "HOME", { startMinute: 420, endMinute: 600, graceMinutes: 30 });
  const command = { method: "POST", path: "/v1/homes/home-1/config", idempotencyKey: "settings-8", body: config };
  await assert.rejects(api.request(command), /offline/);
  online = true;
  const result = await api.request(command);
  assert.deepEqual(result, { version: 8, applied_version: 7 });
  assert.equal(configStatus(result.version, result.applied_version).state, "PENDING");
  assert.equal(sent.headers["idempotency-key"], "settings-8");
  assert.equal(JSON.parse(sent.body).schema, 1);
});

test("PWA-GS130-CLAIM-01 another caregiver may claim only at lease expiry boundary", () => {
  const lease = { state: "CLAIMED", owner_id: "care-1", owner_lease_until: 500 };
  assert.deepEqual(incidentActions(lease, "care-2", 499).map(({ id }) => id), ["view"]);
  assert.deepEqual(incidentActions(lease, "care-2", 500).map(({ id }) => id), ["acknowledge", "resolve"]);
  assert.deepEqual(incidentActions({ ...lease, owner_lease_until: 700 }, "care-1", 500).map(({ id }) => id), ["acknowledge", "resolve"]);
});

test("PWA-GS130-NOTIFY-01 permission and subscription recovery are explicit and delivery IDs deduplicate", () => {
  assert.deepEqual(pushCapability("default", false), { usable: false, reason: "permission_not_granted" });
  assert.deepEqual(pushCapability("denied", true), { usable: false, reason: "permission_denied" });
  assert.deepEqual(pushCapability("granted", false), { usable: false, reason: "subscription_missing" });
  assert.deepEqual(pushCapability("granted", true), { usable: true, reason: "ready" });
  const deliveries = new Set();
  addBounded(deliveries, "event-1", 200);
  addBounded(deliveries, "event-1", 200);
  assert.equal(deliveries.size, 1);
});

test("PWA-GS130-ACTIVITY-01 cached reload and API reconciliation retain identity, order and age", () => {
  const cache = new VersionedCache();
  const snapshot = { fetched_at: 100, hub_reachable: false, last_hub_at: 80, mode: "HOME", latest_activity: { event_id: "evt-2", kind: "DOOR_CLOSED", location: "Main door", occurred_at: 90, details: { open_duration_s: 30 } }, recent_events: [{ event_id: "evt-2", kind: "DOOR_CLOSED", location: "Main door", occurred_at: 90, received_at: 91, details: { open_duration_s: 30 } }, { event_id: "evt-1", kind: "MOTION", location: "Kitchen", occurred_at: 70, received_at: 72, details: {} }] };
  cache.put("home", 4, snapshot, 100);
  const reload = cache.get("home", 160, 120);
  assert.equal(reload.hit, true);
  assert.equal(reload.stale, false);
  const view = buildHomeView(reload.value, 160);
  assert.deepEqual(view.recentEvents.map(({ event }) => event.event_id), ["evt-2", "evt-1"]);
  assert.match(view.recentEvents[0].title, /door closed/i);
  assert.match(timelineLabel(view.recentEvents[1].event), /Motion detected/);
  const fresher = { ...snapshot, fetched_at: 180, hub_reachable: true };
  cache.put("home", 5, fresher, 180);
  cache.put("home", 4, snapshot, 190);
  assert.equal(cache.get("home", 200, 120).value.fetched_at, 180);
});

test("PWA-GS130-SW-01 real service worker installs, updates, serves cache, falls back and reports corruption", async () => {
  const source = await readFile(app("app/public/service-worker.mjs"), "utf8");
  const listeners = new Map();
  const cacheData = new Map([["./index.html", { body: "shell" }], ["/cached", { body: "cached" }]]);
  const deleted = [];
  const cache = { addAll: async (assets) => { assert.ok(assets.includes("./index.html")); } };
  const cachesApi = {
    open: async () => cache,
    keys: async () => ["old-cache", "ghar-sajag-prototype-v1"],
    delete: async (key) => { deleted.push(key); },
    match: async (request) => {
      if (request === "corrupt") throw new Error("cache read failed");
      return cacheData.get(typeof request === "string" ? request : request.url);
    },
  };
  let online = false;
  runInNewContext(source, { self: { addEventListener: (name, fn) => listeners.set(name, fn) }, caches: cachesApi, fetch: async () => { if (online) return { body: "online" }; throw new TypeError("offline"); }, Response });
  let waited;
  listeners.get("install")({ waitUntil: (promise) => { waited = promise; } });
  await waited;
  listeners.get("activate")({ waitUntil: (promise) => { waited = promise; } });
  await waited;
  assert.deepEqual(deleted, ["old-cache"]);
  const respond = async (url, mode = "navigate") => {
    let result;
    listeners.get("fetch")({ request: { method: "GET", url, mode }, respondWith: (promise) => { result = promise; } });
    return result;
  };
  online = true;
  assert.deepEqual(await respond("/fresh", "same-origin"), { body: "online" });
  online = false;
  assert.deepEqual(await respond("/cached", "same-origin"), { body: "cached" });
  assert.deepEqual(await respond("/deep-link"), { body: "shell" });
  const missing = await respond("/missing.png", "no-cors");
  assert.equal(missing.status, 503);
  assert.equal(missing.headers.get("cache-control"), "no-store");
  const corrupt = await respond("corrupt", "no-cors");
  assert.equal(corrupt.status, 503);
});
