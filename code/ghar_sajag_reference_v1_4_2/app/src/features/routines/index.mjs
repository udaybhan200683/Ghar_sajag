// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module A03 App routines
// @requirements F04, F10, F14, E07
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// Routine functions validate local form values and build a desired-version request. The hub remains
// authoritative for what it has applied. A newer applied version than the screen knows about is a conflict
// requiring refresh, not permission to overwrite it.

import { logTrace, logError } from "../../platform/logging.mjs";
/** A03 — local validation and desired-configuration construction. */

export const MODES = Object.freeze(["HOME", "AWAY", "PAUSED", "VISITOR", "PRIVACY"]);

export function validateMorningRoutine(routine) {
  logTrace("APP", "A03", "validateMorningRoutine.enter");
  const errors = {};
  if (!Number.isInteger(routine.startMinute) || routine.startMinute < 0 || routine.startMinute > 1439) errors.startMinute = "Invalid start";
  if (!Number.isInteger(routine.endMinute) || routine.endMinute < 1 || routine.endMinute > 1440) errors.endMinute = "Invalid end";
  if (Number.isInteger(routine.startMinute) && Number.isInteger(routine.endMinute) && routine.startMinute >= routine.endMinute) errors.range = "End must be after start";
  if (!Number.isInteger(routine.graceMinutes) || routine.graceMinutes < 0 || routine.graceMinutes > 180) errors.graceMinutes = "Grace must be 0–180 minutes";
  return { valid: Object.keys(errors).length === 0, errors };
}

export function buildDesiredConfig(homeId, version, timezone, mode, routine) {
  logTrace("APP", "A03", "buildDesiredConfig.enter");
  if (!MODES.includes(mode)) throw new Error("invalid_mode");
  const validation = validateMorningRoutine(routine);
  if (!validation.valid) throw new Error("invalid_routine");
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
