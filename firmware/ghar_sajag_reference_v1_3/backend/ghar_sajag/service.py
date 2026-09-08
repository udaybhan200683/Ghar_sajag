from __future__ import annotations

from .logging_config import traced
from .fleet import FleetService
from .homes import HomeService
from .identity import IdentityService
from .incidents import IncidentService
from .ingest import IngestService
from .model import CloudEvent
from .notifications import NotificationService
from .operations import OperationsService
from .queries import QueryService
from .store import InMemoryStore


class GharSajagService:
    """Composition root for host tests and a future FastAPI adapter."""

    def __init__(self, store: InMemoryStore | None = None) -> None:
        self.store = store or InMemoryStore()
        self.identity = IdentityService(self.store)
        self.homes = HomeService(self.store, self.identity)
        self.ingest = IngestService(self.store)
        self.incidents = IncidentService(self.store, self.identity)
        self.notifications = NotificationService(self.store)
        self.fleet = FleetService(self.store, self.identity)
        self.queries = QueryService(self.store, self.identity)
        self.operations = OperationsService(self.store)

    @traced("B10")

    def accept_hub_event(self, event: CloudEvent) -> tuple[CloudEvent, bool]:
        accepted, duplicate = self.ingest.accept(event)
        if duplicate or event.is_test:
            return accepted, duplicate
        if event.kind == "CALL_FAMILY":
            incident, created_before = self.incidents.create(
                event.home_id,
                f"call-family:{event.event_id}",
                "CALL_FAMILY",
                event.server_received_at,
            )
            if not created_before:
                self.notifications.schedule_for_incident(incident.incident_id)
        elif event.kind == "MISSING_MORNING_ACTIVITY":
            window_id = str(event.payload.get("window_id", event.event_id))
            incident, created_before = self.incidents.create(
                event.home_id,
                f"missing-morning:{window_id}",
                "MISSING_MORNING_ACTIVITY",
                event.server_received_at,
            )
            if not created_before:
                self.notifications.schedule_for_incident(incident.incident_id)
        return accepted, duplicate
