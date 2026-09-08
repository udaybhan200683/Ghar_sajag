import { logTrace, logError } from "../../platform/logging.mjs";
/** A04 — incident actions and human-acknowledgement display state. */

const TERMINAL = new Set(["RESOLVED"]);

export function incidentActions(incident, actorId, now) {
  logTrace("APP", "A04", "incidentActions.enter");
  if (TERMINAL.has(incident.state)) return [];
  const ownedByOther = incident.owner_id && incident.owner_id !== actorId && (incident.owner_lease_until ?? 0) > now;
  if (ownedByOther) return [{ id: "view", label: "View", enabled: true }];
  const actions = [];
  if (incident.state === "OPEN") actions.push({ id: "claim", label: "I’ll check", enabled: true });
  if (incident.state === "OPEN" || incident.state === "CLAIMED") actions.push({ id: "acknowledge", label: "Acknowledged", enabled: true });
  if (incident.state === "ACKNOWLEDGED" || incident.state === "CLAIMED") actions.push({ id: "resolve", label: "Resolve", enabled: true });
  return actions;
}

export function actionCommand(homeId, incidentId, action, idempotencyKey) {
  logTrace("APP", "A04", "actionCommand.enter");
  if (!["claim", "acknowledge", "resolve"].includes(action)) throw new Error("unsupported_incident_action");
  return {
    method: "POST",
    path: `/v1/homes/${homeId}/incidents/${incidentId}/${action}`,
    idempotencyKey,
    body: {},
  };
}

export function deliveryLabel(job) {
  logTrace("APP", "A04", "deliveryLabel.enter");
  const labels = {
    CREATED: "Waiting to send",
    PROVIDER_ACCEPTED: "Accepted by notification service",
    HUMAN_ACKED: "Caregiver acknowledged",
    FAILED: "Delivery failed",
    CANCELLED: "No longer needed",
  };
  return labels[job.state] ?? "Unknown delivery state";
}
