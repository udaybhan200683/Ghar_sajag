// Ghar Sajag traceability edition 2.0 | source release 1.5.4
// @module A03 App routines/settings
// @requirements F04, F09, F10, F14, E07
// Household behaviour policy is configurable per home. Transport reliability policy remains engineering-owned.

import { logTrace } from "../../platform/logging.mjs";

// PRIVACY is deliberately not a user-selectable mode. Consent withdrawal may still force an internal
// privacy state in backend/hub policy, but the ordinary Settings page does not expose an ON/OFF switch.
export const MODES = Object.freeze(["HOME", "AWAY", "PAUSED", "VISITOR"]);

export const DEFAULT_ACTIVITY_RULES = Object.freeze({
  quietHoursEnabled: true,
  quietStartMinute: 60,       // 01:00 local
  quietEndMinute: 300,        // 05:00 local
  doorOpenTimeoutSeconds: 300,
  daytimeInactivityEnabled: true,
  daytimeStartMinute: 8 * 60,
  daytimeEndMinute: 21 * 60,
  daytimeInactivitySeconds: 3 * 60 * 60,
  morningSequenceEnabled: true,
  morningStartMinute: 6 * 60,
  morningEndMinute: 11 * 60,
  morningSequenceWindowSeconds: 4 * 60 * 60,
  morningBedroomLocation: "room1",
  morningBathroomLocation: "bathroom",
  morningKitchenLocation: "kitchen",
  nightActivityEnabled: true,
  nightStartMinute: 22 * 60,
  nightEndMinute: 6 * 60,
  nightBathroomLocation: "bathroom",
  nightBathroomVisitThreshold: 4,
  nightCommonLocation: "common",
  nightCommonVisitThreshold: 4,
  nightVisitMergeSeconds: 5 * 60,
  postDoorInactivityEnabled: true,
  postDoorInactivitySeconds: 2 * 60 * 60,
});

export function validateMorningRoutine(routine) {
  logTrace("APP", "A03", "validateMorningRoutine.enter");
  const errors = {};
  if (!Number.isInteger(routine.startMinute) || routine.startMinute < 0 || routine.startMinute > 1439) errors.startMinute = "Invalid start";
  if (!Number.isInteger(routine.endMinute) || routine.endMinute < 1 || routine.endMinute > 1440) errors.endMinute = "Invalid end";
  if (Number.isInteger(routine.startMinute) && Number.isInteger(routine.endMinute) && routine.startMinute >= routine.endMinute) errors.range = "End must be after start";
  if (!Number.isInteger(routine.graceMinutes) || routine.graceMinutes < 0 || routine.graceMinutes > 180) errors.graceMinutes = "Grace must be 0–180 minutes";
  return { valid: Object.keys(errors).length === 0, errors };
}

export function validateActivityRules(rules) {
  logTrace("APP", "A03", "validateActivityRules.enter");
  const policy = { ...DEFAULT_ACTIVITY_RULES, ...(rules ?? {}) };
  const errors = {};
  const minute = (v) => Number.isInteger(v) && v >= 0 && v <= 1439;
  rules = policy;
  if (!minute(rules.quietStartMinute)) errors.quietStartMinute = "Invalid quiet-hours start";
  if (!minute(rules.quietEndMinute)) errors.quietEndMinute = "Invalid quiet-hours end";
  if (!Number.isInteger(rules.doorOpenTimeoutSeconds) || rules.doorOpenTimeoutSeconds < 30 || rules.doorOpenTimeoutSeconds > 86400) errors.doorOpenTimeoutSeconds = "Door warning must be 30 seconds–24 hours";
  if (!minute(rules.daytimeStartMinute)) errors.daytimeStartMinute = "Invalid daytime start";
  if (!minute(rules.daytimeEndMinute)) errors.daytimeEndMinute = "Invalid daytime end";
  if (!Number.isInteger(rules.daytimeInactivitySeconds) || rules.daytimeInactivitySeconds < 300 || rules.daytimeInactivitySeconds > 86400) errors.daytimeInactivitySeconds = "Inactivity threshold must be 5 minutes–24 hours";
  for (const key of ["morningStartMinute","morningEndMinute","nightStartMinute","nightEndMinute"]) if (!minute(rules[key])) errors[key] = "Invalid schedule minute";
  if (!Number.isInteger(rules.morningSequenceWindowSeconds) || rules.morningSequenceWindowSeconds < 60 || rules.morningSequenceWindowSeconds > 86400) errors.morningSequenceWindowSeconds = "Morning sequence window must be 1 minute–24 hours";
  if (!Number.isInteger(rules.nightBathroomVisitThreshold) || rules.nightBathroomVisitThreshold < 0 || rules.nightBathroomVisitThreshold > 50) errors.nightBathroomVisitThreshold = "Night bathroom threshold must be 0–50";
  if (!Number.isInteger(rules.nightCommonVisitThreshold) || rules.nightCommonVisitThreshold < 0 || rules.nightCommonVisitThreshold > 50) errors.nightCommonVisitThreshold = "Night common-room threshold must be 0–50";
  if (!Number.isInteger(rules.nightVisitMergeSeconds) || rules.nightVisitMergeSeconds < 0 || rules.nightVisitMergeSeconds > 7200) errors.nightVisitMergeSeconds = "Visit merge interval must be 0–2 hours";
  if (!Number.isInteger(rules.postDoorInactivitySeconds) || rules.postDoorInactivitySeconds < 300 || rules.postDoorInactivitySeconds > 86400) errors.postDoorInactivitySeconds = "Post-door inactivity must be 5 minutes–24 hours";
  for (const key of ["morningBedroomLocation","morningBathroomLocation","morningKitchenLocation","nightBathroomLocation","nightCommonLocation"]) if (typeof rules[key] !== "string" || !rules[key]) errors[key] = "Location is required";
  return { valid: Object.keys(errors).length === 0, errors };
}

export function buildDesiredConfig(homeId, version, timezone, mode, routine, activityRules = DEFAULT_ACTIVITY_RULES) {
  logTrace("APP", "A03", "buildDesiredConfig.enter");
  if (!MODES.includes(mode)) throw new Error("invalid_mode");
  const routineValidation = validateMorningRoutine(routine);
  if (!routineValidation.valid) throw new Error("invalid_routine");
  const policy = { ...DEFAULT_ACTIVITY_RULES, ...(activityRules ?? {}) };
  const policyValidation = validateActivityRules(policy);
  if (!policyValidation.valid) throw new Error("invalid_activity_rules");
  return {
    schema: 1,
    home_id: homeId,
    version,
    timezone,
    mode,
    morning: {
      enabled: routine.enabled !== false,
      start_minute: routine.startMinute,
      end_minute: routine.endMinute,
      grace_minutes: routine.graceMinutes,
      qualifying_locations: [...new Set(routine.qualifyingLocations ?? [])],
    },
    activity_rules: {
      quiet_hours_enabled: policy.quietHoursEnabled !== false,
      quiet_start_minute: policy.quietStartMinute,
      quiet_end_minute: policy.quietEndMinute,
      door_open_timeout_seconds: policy.doorOpenTimeoutSeconds,
      daytime_inactivity_enabled: policy.daytimeInactivityEnabled !== false,
      daytime_start_minute: policy.daytimeStartMinute,
      daytime_end_minute: policy.daytimeEndMinute,
      daytime_inactivity_seconds: policy.daytimeInactivitySeconds,
      morning_sequence_enabled: policy.morningSequenceEnabled !== false,
      morning_start_minute: policy.morningStartMinute,
      morning_end_minute: policy.morningEndMinute,
      morning_sequence_window_seconds: policy.morningSequenceWindowSeconds,
      morning_bedroom_location: policy.morningBedroomLocation,
      morning_bathroom_location: policy.morningBathroomLocation,
      morning_kitchen_location: policy.morningKitchenLocation,
      night_activity_enabled: policy.nightActivityEnabled !== false,
      night_start_minute: policy.nightStartMinute,
      night_end_minute: policy.nightEndMinute,
      night_bathroom_location: policy.nightBathroomLocation,
      night_bathroom_visit_threshold: policy.nightBathroomVisitThreshold,
      night_common_location: policy.nightCommonLocation,
      night_common_visit_threshold: policy.nightCommonVisitThreshold,
      night_visit_merge_seconds: policy.nightVisitMergeSeconds,
      post_door_inactivity_enabled: policy.postDoorInactivityEnabled !== false,
      post_door_inactivity_seconds: policy.postDoorInactivitySeconds,
    },
  };
}

// @requirements F04, F10, F14, E07
// Distinguish desired, applied and conflicting versions; an offline device must stay visibly pending.
export function configStatus(desiredVersion, appliedVersion) {
  logTrace("APP", "A03", "configStatus.enter");
  if (appliedVersion == null) return { state: "PENDING", label: "Waiting for hub" };
  if (appliedVersion < desiredVersion) return { state: "PENDING", label: `Hub has version ${appliedVersion}` };
  if (appliedVersion === desiredVersion) return { state: "APPLIED", label: "Applied on hub" };
  return { state: "CONFLICT", label: "Hub reports a newer configuration" };
}
