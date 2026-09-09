// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module A02 App home
// @requirements F05, F06, F09, F11, F14, E01, E04, E10, NFR-01, NFR-02, NFR-10
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// Home view functions convert a server snapshot to readable labels. Do not move eligibility or incident
// creation into this layer. A stale value can remain visible if labelled with age; it must not acquire a
// new timestamp because the page rerendered.

import { logTrace, logError } from "../../platform/logging.mjs";
/** A02 — evidence and health view models; no wellbeing inference. */

// @requirements F05, F06, F09, F11, F14, E01, E04, E10, NFR-01, NFR-02, NFR-10
// Calculate view age from the observed timestamp, not from the most recent page render.
export function formatFreshness(timestamp, now) {
  logTrace("APP", "A02", "formatFreshness.enter");
  if (timestamp == null) return { label: "Never confirmed", stale: true };
  const age = Math.max(0, now - timestamp);
  if (age < 60) return { label: "Just now", stale: false };
  if (age < 3600) return { label: `${Math.floor(age / 60)} min ago`, stale: false };
  return { label: `${Math.floor(age / 3600)} hr ago`, stale: true };
}

// @requirements F05, F06, F09, F11, F14, E01, E04, E10, NFR-01, NFR-02, NFR-10
// Present activity, resident OK and service freshness separately; do not infer wellbeing from missing
// data.
export function buildHomeView(snapshot, now) {
  logTrace("APP", "A02", "buildHomeView.enter");
  const hub = formatFreshness(snapshot.last_hub_at, now);
  const activity = snapshot.latest_activity
    ? {
        title: "Household activity observed",
        detail: `${snapshot.latest_activity.location} · ${formatFreshness(snapshot.latest_activity.occurred_at, now).label}`,
        kind: snapshot.latest_activity.kind,
      }
    : { title: "No activity evidence available", detail: "This does not mean nobody is present.", kind: null };
  return {
    mode: snapshot.mode,
    connectivity: snapshot.hub_reachable
      ? { tone: "positive", title: "Hub connected", detail: hub.label }
      : { tone: "warning", title: "Hub connection unavailable", detail: `Last confirmed: ${hub.label}` },
    activity,
    incidents: snapshot.active_incidents ?? [],
    fetchedAt: snapshot.fetched_at,
  };
}

export function timelineLabel(event) {
  logTrace("APP", "A02", "timelineLabel.enter");
  const base = event.kind === "MOTION" ? "Activity observed" : event.kind.replaceAll("_", " ").toLowerCase();
  return `${base} · ${event.location}${event.delayed ? " · received later" : ""}`;
}
