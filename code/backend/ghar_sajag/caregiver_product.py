"""Read/action projection of committed product data for an authenticated app.

The caller must establish a current human session and Home membership before
calling. This adapter cannot ingest events, create authority or run scenarios.
"""
from dataclasses import asdict


class CaregiverProductView:
    def __init__(self, service, *, source):
        self.service, self.source = service, source

    def dispatch(self, session, home, sub, method, body, now):
        actor = session["account_id"]
        self.service.identity.require(home, actor, "read", now)
        snapshot = self.service.queries.snapshot(home, actor, now)
        base = {"home_id": home, "test_only": bool(session["test_only"]),
                "source": self.source, "physical_status": "NOT_RUN",
                "physical_status_reason": "HOST_SIMULATION_ONLY",
                "physical_data_contract": "GS-148_CLOUDSYNC_V2"}
        if method == "GET" and sub == "overview":
            return {**base, **snapshot, "source_freshness": "CURRENT" if snapshot["hub_reachable"] else "UNKNOWN",
                    "monitoring": "COVERED" if (snapshot["hub_reachable"] and snapshot["node_health"] and
                        all(n["status"] == "ONLINE" and n["coverage"] == "COVERED" for n in snapshot["node_health"])) else "UNKNOWN",
                    "backend_data_retrieved_at": now, "recent_events": self.service.queries.timeline(home, actor, now)}
        if method == "GET" and sub == "devices":
            return {**base, "devices": snapshot["node_health"]}
        if method == "GET" and sub == "incidents":
            return {**base, "incidents": [{**asdict(i), "state": i.state.value,
                    "severity": "URGENT" if i.kind == "CALL_FAMILY" else "CONCERN"}
                for i in self.service.store.incidents.values() if i.home_id == home]}
        if method == "GET" and sub == "reports":
            return {**base, "event_count": sum(snapshot["event_counts"].values()),
                    "event_counts": snapshot["event_counts"], "recent_events": self.service.queries.timeline(home, actor, now)}
        parts = sub.split("/")
        if (method == "POST" and len(parts) == 3 and parts[0] == "incidents"
                and parts[2] in {"claim", "acknowledge", "resolve"}):
            if body:
                raise ValueError("incident_action_accepts_no_parameters")
            incident = getattr(self.service.incidents, parts[2])(home, parts[1], actor, now)
            return {"incident_id": incident.incident_id, "state": incident.state.value, "owner_id": incident.owner_id}
        return None
