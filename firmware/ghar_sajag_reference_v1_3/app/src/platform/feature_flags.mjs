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
