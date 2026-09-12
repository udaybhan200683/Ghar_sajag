// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module A02 App home
// @requirements F05, F06, F09, F11, F14, E01, E04, E10, NFR-01, NFR-02, NFR-10
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// Home view functions convert a server snapshot to readable labels. Do not move eligibility or incident
// creation into this layer. A stale value can remain visible if labelled with age; it must not acquire a
// new timestamp because the page rerendered.

import { buildHomeView } from "../src/features/home/index.mjs";
import { incidentActions } from "../src/features/incidents/index.mjs";

const now = Math.floor(Date.now() / 1000);
const sample = {
  mode: "HOME",
  hub_reachable: true,
  last_hub_at: now - 32,
  latest_activity: { kind: "MOTION", location: "Common room", occurred_at: now - 420, uncertainty_s: 2 },
  active_incidents: ["inc_demo"],
  fetched_at: now,
};
const view = buildHomeView(sample, now);
const connectivity = document.querySelector("#connectivity");
connectivity.classList.add(view.connectivity.tone);
connectivity.innerHTML = `<h2>${view.connectivity.title}</h2><p>${view.connectivity.detail}</p>`;
document.querySelector("#activity").innerHTML = `<h2>${view.activity.title}</h2><p>${view.activity.detail}</p>`;

const incident = { state: "OPEN", owner_id: null, owner_lease_until: null };
const buttons = incidentActions(incident, "caregiver-demo", now)
  .map((action) => `<button data-action="${action.id}">${action.label}</button>`)
  .join("");
document.querySelector("#incidents").innerHTML = `<p>No morning activity was observed in the configured window. Sensor coverage was available.</p>${buttons}`;
document.querySelector("#updated").textContent = `Updated ${new Date(now * 1000).toLocaleTimeString()}`;

if ("serviceWorker" in navigator) navigator.serviceWorker.register("./service-worker.mjs");
