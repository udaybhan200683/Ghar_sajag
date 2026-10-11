// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module A02 App home
// @requirements F05, F06, F09, F11, F14, E01, E04, E10, NFR-01, NFR-02, NFR-10
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// Home view functions convert a server snapshot to readable labels. Do not move eligibility or incident
// creation into this layer. A stale value can remain visible if labelled with age; it must not acquire a
// new timestamp because the page rerendered.

import { buildHomeView } from "../src/features/home/index.mjs";

const connectivity = document.querySelector("#connectivity");
const activity = document.querySelector("#activity");
const incidents = document.querySelector("#incidents");
const timeline = document.querySelector("#timeline");
const door = document.querySelector("#door");

function replaceContent(root, title, detail, tone = "") {
  root.replaceChildren();
  root.className = `card ${tone}`.trim();
  const heading = document.createElement("h2");
  heading.textContent = title;
  root.append(heading);
  if (detail) {
    const paragraph = document.createElement("p");
    paragraph.textContent = detail;
    root.append(paragraph);
  }
}

async function loadCaregiverSnapshot() {
  const updated = document.querySelector("#updated");
  try {
    const configResponse = await fetch("./runtime-config.json", { cache: "no-store" });
    if (!configResponse.ok) throw new Error("runtime_config_unavailable");
    const config = await configResponse.json();
    if (!config || typeof config.home_id !== "string" || !config.home_id.trim()) {
      throw new Error("home_not_configured");
    }
    const apiBase = String(config.api_base || ".").replace(/\/$/, "");
    const response = await fetch(`${apiBase}/v1/homes/${encodeURIComponent(config.home_id)}/snapshot`, {
      headers: { accept: "application/json" },
      credentials: "same-origin",
      cache: "no-store",
    });
    if (!response.ok) throw new Error(`snapshot_unavailable_${response.status}`);
    const snapshot = await response.json();
    const now = Number(snapshot.fetched_at) || Math.floor(Date.now() / 1000);
    const view = buildHomeView(snapshot, now);
    replaceContent(connectivity, view.connectivity.title, view.connectivity.detail, view.connectivity.tone);
    replaceContent(activity, view.activity.title, view.activity.detail, view.activity.tone);

    const doorStatus = snapshot.door_status;
    if (!doorStatus) {
      replaceContent(door, "Door status unavailable", "No current door transition was reported.");
    } else if (doorStatus.state === "OPEN") {
      const detail = doorStatus.unexpected
        ? "Main door opened during the configured quiet period."
        : "Main door is currently open.";
      replaceContent(door, "Main door open", detail, doorStatus.unexpected || doorStatus.left_open ? "warning" : "");
    } else {
      replaceContent(door, "Main door closed", "The latest reported door transition is closed.");
    }

    incidents.replaceChildren();
    if (view.incidents.length === 0) {
      const empty = document.createElement("p");
      empty.textContent = "No active caregiver alerts.";
      incidents.append(empty);
    } else {
      for (const incidentId of view.incidents) {
        const item = document.createElement("p");
        item.dataset.incidentId = incidentId;
        item.textContent = "An active household concern needs review.";
        incidents.append(item);
      }
    }

    timeline.replaceChildren();
    for (const item of view.recentEvents) {
      const row = document.createElement("li");
      row.className = `event ${item.tone}`;
      row.dataset.eventId = item.event.event_id;
      row.textContent = `${item.title} · ${item.detail}`;
      timeline.append(row);
    }
    if (view.recentEvents.length === 0) {
      const row = document.createElement("li");
      row.textContent = "No activity evidence available. This does not mean nobody is present.";
      timeline.append(row);
    }
    updated.textContent = `Updated ${new Date((snapshot.fetched_at || now) * 1000).toLocaleTimeString()}`;
  } catch (error) {
    replaceContent(connectivity, "Caregiver data unavailable", "No current Hub or activity status can be confirmed.", "warning");
    replaceContent(activity, "Activity status unavailable", "The app could not load an authorized household snapshot.", "warning");
    incidents.replaceChildren();
    timeline.replaceChildren();
    updated.textContent = "Not updated";
  }
}

loadCaregiverSnapshot();

if ("serviceWorker" in navigator) navigator.serviceWorker.register("./service-worker.mjs");
