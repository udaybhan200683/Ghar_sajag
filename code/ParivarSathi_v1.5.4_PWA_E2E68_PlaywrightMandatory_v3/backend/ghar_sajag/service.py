# Ghar Sajag traceability edition 2.0 | source release 1.4.2
# @module B03 Event ingestion
# @requirements E02, E05, NFR-03
# Requirement links identify design responsibility, not completed acceptance coverage.
# See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
# IngestService accepts a cloud event once per home/event key and updates receipt state. A production
# unique constraint must reproduce this behaviour under concurrent workers. Domain event acceptance must
# not be acknowledged until required incident/outbox effects are safely committed.

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

    # @requirements E02, E05, NFR-03
    # Compose deduplicated ingestion, stable incident creation and notification scheduling; production
    # needs atomic transaction/outbox.
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
        elif event.kind == "DAYTIME_INACTIVITY":
            incident, created_before = self.incidents.create(
                event.home_id,
                f"daytime-inactivity:{event.event_id}",
                "DAYTIME_INACTIVITY",
                event.server_received_at,
            )
            if not created_before:
                self.notifications.schedule_for_incident(incident.incident_id)
        elif event.kind == "DOOR_OPEN":
            self.notifications.create_door_notice(
                event.home_id, event.event_id, event.server_received_at,
                bool(event.payload.get("quiet_hours", False)), event.is_test,
            )
        return accepted, duplicate
