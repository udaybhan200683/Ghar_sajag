// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module S04 Product profile
// @requirements V01, AI01, AI07, E07, E10, NFR-08
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// Product::ai is decided by GS_PRODUCT_AI and exposed through PRODUCT=base or ai in the Makefile. Invalid
// values fail the build. The runtime returns Disabled before calling a provider in the Base profile; the
// shared core remains identical. The older per-feature flags need separate enforcement review.

/** Build-injected flags. P1/P2 capabilities remain off unless explicitly built in. */
const defaults = Object.freeze({
  morning_routine: true, call_family: true, door_history: true, daily_summary: true,
  local_offline: true, temperature_context: false, external_camera: false,
  fall_detection: false, professional_response: false,
});

const injected = globalThis.__GS_FEATURES__ ?? {};
export const featureFlags = Object.freeze(Object.fromEntries(
  Object.keys(defaults).map((name) => [name, typeof injected[name] === "boolean" ? injected[name] : defaults[name]])
));
export function isFeatureEnabled(name) { return featureFlags[name] === true; }
