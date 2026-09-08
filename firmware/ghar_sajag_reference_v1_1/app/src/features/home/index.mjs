import { logTrace, logError } from "../../platform/logging.mjs";
/** A02 — evidence and health view models; no wellbeing inference. */

export function formatFreshness(timestamp, now) {
  logTrace("APP", "A02", "formatFreshness.enter");
  if (timestamp == null) return { label: "Never confirmed", stale: true };
  const age = Math.max(0, now - timestamp);
  if (age < 60) return { label: "Just now", stale: false };
  if (age < 3600) return { label: `${Math.floor(age / 60)} min ago`, stale: false };
  return { label: `${Math.floor(age / 3600)} hr ago`, stale: true };
}

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
