# Ghar Sajag traceability edition 2.0 | source release 1.5.1
# @module B07 Read models/API
# @requirements F05, F06, F07, F09, F11, F12, F14, E04

from __future__ import annotations

from .logging_config import traced
from collections import Counter
from typing import Any

from .identity import IdentityService
from .model import IncidentState
from .store import InMemoryStore


_ACTIVITY_KINDS = {"MOTION", "DOOR_OPEN", "DOOR_CLOSED", "OK_PRESSED"}
_MEANINGFUL_KINDS = _ACTIVITY_KINDS | {"CALL_FAMILY", "MISSING_MORNING_ACTIVITY", "DOOR_LEFT_OPEN", "DAYTIME_INACTIVITY"}
_SAFE_PAYLOAD_KEYS = {
    "quiet_hours", "unexpected", "open_duration_s", "was_left_open", "resolved_left_open",
    "opened_at", "duration_s", "source_event_id", "window_id", "left_open_timeout_s", "reason",
}


class QueryService:
    def __init__(self, store: InMemoryStore, identity: IdentityService, hub_lease_seconds: int = 190) -> None:
        self.store = store
        self.identity = identity
        self.hub_lease_seconds = hub_lease_seconds

    def _event_view(self, item) -> dict[str, Any]:
        payload = {k: v for k, v in item.payload.items() if k in _SAFE_PAYLOAD_KEYS}
        if item.kind in {"MISSING_MORNING_ACTIVITY", "DOOR_LEFT_OPEN", "DAYTIME_INACTIVITY"}:
            tone = "danger"
        elif item.kind == "DOOR_OPEN" and payload.get("unexpected"):
            tone = "danger"
        elif item.kind in {"OK_PRESSED", "DOOR_CLOSED"}:
            tone = "positive"
        elif item.kind in {"MOTION", "DOOR_OPEN"}:
            tone = "positive"
        elif item.kind == "CALL_FAMILY":
            tone = "warning"
        else:
            tone = "neutral"
        return {
            "event_id": item.event_id,
            "kind": item.kind,
            "location": item.location,
            "occurred_at": item.occurred_at,
            "received_at": item.server_received_at,
            "uncertainty_s": item.uncertainty_s,
            "delayed": item.server_received_at - item.occurred_at > 60,
            "tone": tone,
            "details": payload,
        }

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
        latest_activity = next((item for item in events if item.kind in _ACTIVITY_KINDS), None)
        recent = [self._event_view(item) for item in events if item.kind in _MEANINGFUL_KINDS][:6]

        door_events = [item for item in events if item.kind in {"DOOR_OPEN", "DOOR_CLOSED"}]
        latest_door = door_events[0] if door_events else None
        door_status = None
        if latest_door is not None:
            details = self._event_view(latest_door)["details"]
            door_status = {
                "state": "OPEN" if latest_door.kind == "DOOR_OPEN" else "CLOSED",
                "since": latest_door.occurred_at,
                "location": latest_door.location,
                "unexpected": bool(details.get("unexpected", False)),
                "open_duration_s": details.get("open_duration_s"),
                "left_open": latest_door.kind == "DOOR_OPEN" and at - latest_door.occurred_at >= int(details.get("left_open_timeout_s", 300)),
            }

        return {
            "home_id": home_id,
            "mode": home.mode.value,
            "home_version": home.version,
            "hub_reachable": hub_reachable,
            "last_hub_at": last_hub,
            "latest_activity": None if latest_activity is None else self._event_view(latest_activity),
            "recent_events": recent,
            "door_status": door_status,
            "active_incidents": [item.incident_id for item in active_incidents],
            "event_counts": dict(Counter(item.kind for item in events)),
            "fetched_at": at,
        }

    @traced("B07")
    def timeline(self, home_id: str, actor_id: str, at: int, limit: int = 100) -> list[dict[str, Any]]:
        self.identity.require(home_id, actor_id, "read", at)
        events = [event for (candidate, _), event in self.store.events.items() if candidate == home_id and not event.is_test]
        events.sort(key=lambda item: (item.occurred_at, item.event_id), reverse=True)
        return [self._event_view(item) for item in events[:limit]]
