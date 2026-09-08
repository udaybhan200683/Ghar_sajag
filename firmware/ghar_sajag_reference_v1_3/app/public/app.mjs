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
