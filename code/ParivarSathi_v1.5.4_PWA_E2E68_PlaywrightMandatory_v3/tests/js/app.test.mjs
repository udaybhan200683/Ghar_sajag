// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module T01 Simulation/CI
// @requirements E08, E10, V01, AI01, AI03, NFR-08
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// The Makefile builds host C++17 and runs Python/JavaScript tests plus simulator fixtures. Tests prove
// their asserted paths, not every SRD criterion. Keep a clean command transcript and attach additional
// scenario tests as requirements are integrated.

import test from "node:test";
import assert from "node:assert/strict";

import { buildCreateHomeCommand, installationGate, validateHouseholdDraft } from "../../app/src/features/onboarding/index.mjs";
import { buildHomeView, eventPresentation, timelineLabel } from "../../app/src/features/home/index.mjs";
import { buildDesiredConfig, configStatus, validateActivityRules } from "../../app/src/features/routines/index.mjs";
import { actionCommand, incidentActions } from "../../app/src/features/incidents/index.mjs";
import { VersionedCache, pushCapability } from "../../app/src/platform/index.mjs";
import { clearLogsForTest, exportLogText, logError, logTrace } from "../../app/src/platform/logging.mjs";
import { featureFlags, isFeatureEnabled } from "../../app/src/platform/feature_flags.mjs";

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



test("A02 presents exact activity meaning and age", () => {
  const ok = eventPresentation({ kind: "OK_PRESSED", location: "Room 1", occurred_at: 100, details: {} }, 220);
  assert.equal(ok.title, "I am OK");
  assert.equal(ok.tone, "positive");
  assert.match(ok.detail, /2 min ago/);
  assert.match(timelineLabel({ kind: "DOOR_OPEN", location: "Main door", occurred_at: 100, received_at: 100, details: { unexpected: true } }, 100), /quiet hours/);
});

test("A02 presents daytime inactivity as a concern", () => {
  const inactivity = eventPresentation({ kind: "DAYTIME_INACTIVITY", location: "home", occurred_at: 100, details: { duration_s: 10800 } }, 200);
  assert.equal(inactivity.tone, "danger");
  assert.match(inactivity.title, /No activity/);
});

test("A03 produces versioned routine and household-policy config", () => {
  const rules = { quietHoursEnabled: true, quietStartMinute: 120, quietEndMinute: 330, doorOpenTimeoutSeconds: 420, daytimeInactivityEnabled: true, daytimeStartMinute: 450, daytimeEndMinute: 1230, daytimeInactivitySeconds: 7200 };
  assert.equal(validateActivityRules(rules).valid, true);
  const config = buildDesiredConfig("h1", 3, "Asia/Kolkata", "HOME", { startMinute: 420, endMinute: 600, graceMinutes: 30, qualifyingLocations: ["kitchen", "kitchen"] }, rules);
  assert.deepEqual(config.morning.qualifying_locations, ["kitchen"]);
  assert.equal(config.activity_rules.quiet_start_minute, 120);
  assert.equal(config.activity_rules.door_open_timeout_seconds, 420);
  assert.equal(config.activity_rules.daytime_inactivity_seconds, 7200);
  assert.equal(configStatus(3, 2).state, "PENDING");
  assert.equal(configStatus(3, 3).state, "APPLIED");
  assert.throws(() => buildDesiredConfig("h1", 4, "Asia/Kolkata", "PRIVACY", { startMinute: 420, endMinute: 600, graceMinutes: 30 }), /invalid_mode/);
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

test("feature flags keep unfinished capabilities disabled", () => {
  assert.equal(isFeatureEnabled("morning_routine"), true);
  assert.equal(isFeatureEnabled("fall_detection"), false);
  assert.equal(Object.hasOwn(featureFlags, "external_camera"), true);
});
