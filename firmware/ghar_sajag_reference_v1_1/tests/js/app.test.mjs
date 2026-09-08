import test from "node:test";
import assert from "node:assert/strict";

import { buildCreateHomeCommand, installationGate, validateHouseholdDraft } from "../../app/src/features/onboarding/index.mjs";
import { buildHomeView } from "../../app/src/features/home/index.mjs";
import { buildDesiredConfig, configStatus } from "../../app/src/features/routines/index.mjs";
import { actionCommand, incidentActions } from "../../app/src/features/incidents/index.mjs";
import { VersionedCache, pushCapability } from "../../app/src/platform/index.mjs";
import { clearLogsForTest, exportLogText, logError, logTrace } from "../../app/src/platform/logging.mjs";

test("A01 requires resident consent and distinct backup", () => {
  const draft = {
    displayName: "Parents' home", timezone: "Asia/Kolkata", language: "hi-IN",
    residents: [{ residentId: "r1", displayName: "Resident", consentActive: true }],
    primaryCaregiverId: "c1", backupCaregiverId: "c2",
  };
  assert.equal(validateHouseholdDraft(draft).valid, true);
  assert.equal(buildCreateHomeCommand(draft, "key-1").body.residents[0].consent_active, true);
  assert.equal(validateHouseholdDraft({ ...draft, backupCaregiverId: "c1" }).valid, false);
});

test("A01 installation gate enumerates missing device tests", () => {
  const result = installationGate({
    nodes: [{ nodeId: "n1", enabledCapabilities: ["pir"] }],
    passes: { hub_buttons: true, privacy_switch: true, caregiver_delivery: true },
  });
  assert.deepEqual(result, { eligible: false, missing: ["n1:pir"] });
});

test("A02 never converts absent evidence into wellbeing", () => {
  const view = buildHomeView({ mode: "HOME", hub_reachable: false, last_hub_at: 50, latest_activity: null, active_incidents: [], fetched_at: 200 }, 200);
  assert.equal(view.connectivity.title, "Hub connection unavailable");
  assert.match(view.activity.detail, /does not mean/);
});

test("A03 produces versioned routine config and applied state", () => {
  const config = buildDesiredConfig("h1", 3, "Asia/Kolkata", "HOME", { startMinute: 420, endMinute: 600, graceMinutes: 30, qualifyingLocations: ["kitchen", "kitchen"] });
  assert.deepEqual(config.morning.qualifying_locations, ["kitchen"]);
  assert.equal(configStatus(3, 2).state, "PENDING");
  assert.equal(configStatus(3, 3).state, "APPLIED");
});

test("A04 prevents action when another caregiver owns a live lease", () => {
  const actions = incidentActions({ state: "CLAIMED", owner_id: "c2", owner_lease_until: 500 }, "c1", 100);
  assert.deepEqual(actions.map((item) => item.id), ["view"]);
  assert.match(actionCommand("h1", "i1", "claim", "k").path, /claim$/);
});

test("A05 cache rejects older versions and reports push gaps", () => {
  const cache = new VersionedCache();
  cache.put("home", 2, { value: "new" }, 100);
  cache.put("home", 1, { value: "old" }, 110);
  assert.equal(cache.get("home", 120, 60).value.value, "new");
  assert.deepEqual(pushCapability("granted", false), { usable: false, reason: "subscription_missing" });
});

test("A05 logger retains errors and applies the build trace gate", () => {
  clearLogsForTest();
  logTrace("TEST", "T03", "trace.hidden");
  logError("TEST", "T03", "error.visible", "forced");
  const text = exportLogText();
  assert.match(text, /level=ERROR/);
  if (process.env.GS_TRACE === "1") assert.match(text, /level=TRACE/);
  else assert.doesNotMatch(text, /level=TRACE/);
});
