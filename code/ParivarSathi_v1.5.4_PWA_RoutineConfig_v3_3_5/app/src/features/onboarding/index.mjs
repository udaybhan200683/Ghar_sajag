// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module A01 App onboarding
// @requirements F01, F02, F03, NFR-10
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// Onboarding functions validate a draft and produce a command; they do not persist it. installationGate
// consumes evidence flags, so the caller must distinguish a genuine completed drill from a manually
// checked box. The UI should explain every missing prerequisite.

import { logTrace, logError } from "../../platform/logging.mjs";
/** A01 — pure onboarding validation and command construction. */

export const ROLES = Object.freeze({ OWNER: "OWNER", CAREGIVER: "CAREGIVER", INSTALLER: "INSTALLER" });

export function validateHouseholdDraft(draft) {
  logTrace("APP", "A01", "validateHouseholdDraft.enter");
  const errors = {};
  if (!draft.displayName?.trim()) errors.displayName = "Home name is required";
  if (!draft.timezone?.includes("/")) errors.timezone = "Choose an IANA timezone";
  if (!Array.isArray(draft.residents) || draft.residents.length === 0) errors.residents = "At least one resident is required";
  else if (draft.residents.some((item) => item.consentActive !== true)) errors.consent = "Every listed resident must actively consent";
  if (!draft.primaryCaregiverId) errors.primary = "Primary caregiver is required";
  if (!draft.backupCaregiverId) errors.backup = "Backup caregiver is required for unattended use";
  if (draft.primaryCaregiverId && draft.primaryCaregiverId === draft.backupCaregiverId) errors.backup = "Backup must be a different person";
  return { valid: Object.keys(errors).length === 0, errors };
}

export function buildCreateHomeCommand(draft, idempotencyKey) {
  logTrace("APP", "A01", "buildCreateHomeCommand.enter");
  const validation = validateHouseholdDraft(draft);
  if (!validation.valid) throw new Error("invalid_household_draft");
  return {
    method: "POST",
    path: "/v1/homes",
    idempotencyKey,
    body: {
      display_name: draft.displayName.trim(),
      timezone: draft.timezone,
      language: draft.language ?? "en-IN",
      residents: draft.residents.map((item) => ({
        resident_id: item.residentId,
        display_name: item.displayName,
        consent_active: true,
      })),
      primary_caregiver_id: draft.primaryCaregiverId,
      backup_caregiver_id: draft.backupCaregiverId,
    },
  };
}

// @requirements F01, F02, F03, NFR-10
// Expose missing installation checks; supplied booleans require actual physical evidence before field
// eligibility.
export function installationGate(results) {
  logTrace("APP", "A01", "installationGate.enter");
  const required = ["hub_buttons", "privacy_switch", "caregiver_delivery"];
  for (const node of results.nodes ?? []) {
    for (const capability of node.enabledCapabilities ?? []) required.push(`${node.nodeId}:${capability}`);
  }
  const missing = required.filter((key) => results.passes?.[key] !== true);
  return { eligible: missing.length === 0, missing };
}
