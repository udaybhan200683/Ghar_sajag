# Ghar Sajag traceability edition 2.0 | source release 1.4.2
# @module B07 Read models/API
# @requirements F05, F06, F09, F11, F12, F14, E04
# Requirement links identify design responsibility, not completed acceptance coverage.
# See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
# QueryService builds a caregiver projection from authoritative backend records and checks household
# access. The projection may be stale even when the backend is healthy; include source ages. The demo HTTP
# adapter is a local development adapter and is not equivalent to the planned authenticated production
# API.

from __future__ import annotations

from .logging_config import traced
from collections import Counter
from typing import Any

from .identity import IdentityService
from .model import IncidentState
from .store import InMemoryStore


class QueryService:
    def __init__(self, store: InMemoryStore, identity: IdentityService, hub_lease_seconds: int = 190) -> None:
        self.store = store
        self.identity = identity
        self.hub_lease_seconds = hub_lease_seconds

    @traced("B07")

    def snapshot(self, home_id: str, actor_id: str, at: int) -> dict[str, Any]:
        self.identity.require(home_id, actor_id, "read", at)
        home = self.store.homes[home_id]
        events = [event for (candidate, _), event in self.store.events.items() if candidate == home_id]
        events.sort(key=lambda item: (item.occurred_at, item.event_id), reverse=True)
        hub_beats = [item for item in events if item.kind == "HUB_HEARTBEAT"]
        last_hub = max((item.server_received_at for item in hub_beats), default=None)
        hub_reachable = last_hub is not None and at - last_hub <= self.hub_lease_seconds
        active_incidents = [
            item for item in self.store.incidents.values()
            if item.home_id == home_id and item.state not in {IncidentState.RESOLVED}
        ]
        latest_activity = next((item for item in events if item.kind in {"MOTION", "DOOR_OPEN", "DOOR_CLOSED", "OK_PRESSED"}), None)
        return {
            "home_id": home_id,
            "mode": home.mode.value,
            "home_version": home.version,
            "hub_reachable": hub_reachable,
            "last_hub_at": last_hub,
            "latest_activity": None if latest_activity is None else {
                "kind": latest_activity.kind,
                "location": latest_activity.location,
                "occurred_at": latest_activity.occurred_at,
                "uncertainty_s": latest_activity.uncertainty_s,
            },
            "active_incidents": [item.incident_id for item in active_incidents],
            "event_counts": dict(Counter(item.kind for item in events)),
            "fetched_at": at,
        }

    @traced("B07")

    def timeline(self, home_id: str, actor_id: str, at: int, limit: int = 100) -> list[dict[str, Any]]:
        self.identity.require(home_id, actor_id, "read", at)
        events = [event for (candidate, _), event in self.store.events.items() if candidate == home_id and not event.is_test]
        events.sort(key=lambda item: (item.occurred_at, item.event_id), reverse=True)
        return [
            {"event_id": item.event_id, "kind": item.kind, "location": item.location,
             "occurred_at": item.occurred_at, "received_at": item.server_received_at,
             "delayed": item.server_received_at - item.occurred_at > 60}
            for item in events[:limit]
        ]
