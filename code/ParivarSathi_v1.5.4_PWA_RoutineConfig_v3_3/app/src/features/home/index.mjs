// Ghar Sajag traceability edition 2.0 | source release 1.5.1
// @module A02 App home
// @requirements F05, F06, F07, F09, F11, F14, E01, E04, E10, NFR-01, NFR-02, NFR-10

import { logTrace } from "../../platform/logging.mjs";

export function formatFreshness(timestamp, now) {
  logTrace("APP", "A02", "formatFreshness.enter");
  if (timestamp == null) return { label: "Never confirmed", stale: true };
  const age = Math.max(0, now - timestamp);
  if (age < 60) return { label: "Just now", stale: false };
  if (age < 3600) return { label: `${Math.floor(age / 60)} min ago`, stale: false };
  if (age < 86400) return { label: `${Math.floor(age / 3600)} hr ago`, stale: true };
  return { label: `${Math.floor(age / 86400)} day ago`, stale: true };
}

export function formatDuration(seconds) {
  const value = Math.max(0, Number(seconds || 0));
  if (value < 60) return `${Math.round(value)} sec`;
  if (value < 3600) return `${Math.floor(value / 60)} min`;
  const h = Math.floor(value / 3600);
  const m = Math.floor((value % 3600) / 60);
  return m ? `${h} hr ${m} min` : `${h} hr`;
}

export function eventPresentation(event, now) {
  const age = formatFreshness(event.occurred_at, now).label;
  const d = event.details || {};
  switch (event.kind) {
    case "OK_PRESSED":
      return { title: "I am OK", detail: `${event.location} · ${age}`, tone: "positive" };
    case "MOTION":
      return { title: `Motion detected — ${event.location}`, detail: age, tone: "positive" };
    case "DOOR_OPEN":
      return {
        title: d.unexpected ? "Main door opened during quiet hours" : "Main door opened",
        detail: `${event.location} · ${age}`,
        tone: d.unexpected ? "danger" : "positive",
      };
    case "DOOR_CLOSED": {
      const duration = d.open_duration_s == null ? "" : ` · was open ${formatDuration(d.open_duration_s)}`;
      const cleared = d.resolved_left_open ? " · left-open warning cleared" : "";
      return { title: "Main door closed", detail: `${event.location} · ${age}${duration}${cleared}`, tone: "positive" };
    }
    case "DOOR_LEFT_OPEN":
      return { title: "Main door kept open", detail: `${event.location} · open for ${formatDuration(d.duration_s || 300)}`, tone: "danger" };
    case "CALL_FAMILY":
      return { title: "Call Family requested", detail: `${event.location} · ${age}`, tone: "warning" };
    case "MISSING_MORNING_ACTIVITY":
      return { title: "Missing morning activity", detail: `${age} · keep this visible until reviewed`, tone: "danger" };
    case "DAYTIME_INACTIVITY":
      return { title: "No activity for longer than expected", detail: `${age} · family check-in suggested`, tone: "danger" };
    default:
      return { title: event.kind.replaceAll("_", " "), detail: `${event.location || "Home"} · ${age}`, tone: event.tone || "neutral" };
  }
}

export function buildHomeView(snapshot, now) {
  logTrace("APP", "A02", "buildHomeView.enter");
  const hub = formatFreshness(snapshot.last_hub_at, now);
  const activity = snapshot.latest_activity
    ? (() => {
        const presented = eventPresentation(snapshot.latest_activity, now);
        return { ...presented, kind: snapshot.latest_activity.kind };
      })()
    : { title: "No activity evidence available", detail: "This does not mean nobody is present.", kind: null, tone: "neutral" };
  return {
    mode: snapshot.mode,
    connectivity: snapshot.hub_reachable
      ? { tone: "positive", title: "Hub connected", detail: hub.label }
      : { tone: "warning", title: "Hub connection unavailable", detail: `Last confirmed: ${hub.label}` },
    activity,
    recentEvents: (snapshot.recent_events || []).map((event) => ({ ...eventPresentation(event, now), event })),
    incidents: snapshot.active_incidents ?? [],
    fetchedAt: snapshot.fetched_at,
  };
}

export function timelineLabel(event, now = event.received_at ?? event.occurred_at) {
  logTrace("APP", "A02", "timelineLabel.enter");
  const view = eventPresentation(event, now);
  return `${view.title}${view.detail ? ` · ${view.detail}` : ""}${event.delayed ? " · received later" : ""}`;
}

export function timelineTone(event) {
  return eventPresentation(event, event.received_at ?? event.occurred_at).tone;
}
