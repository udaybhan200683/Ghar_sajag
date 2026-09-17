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
from .model import AuditEntry, CloudEvent
from .store import InMemoryStore


class EventValidationError(ValueError):
    pass


class IngestService:
    ALLOWED_KINDS = {
        "MOTION", "DOOR_OPEN", "DOOR_CLOSED", "OK_PRESSED", "CALL_FAMILY",
        "HEARTBEAT", "PRIVACY_ON", "PRIVACY_OFF", "GAP", "HUB_HEARTBEAT",
        "MISSING_MORNING_ACTIVITY", "COVERAGE_CHANGED", "DOOR_LEFT_OPEN", "DAYTIME_INACTIVITY",
        "MORNING_ROUTINE_COMPLETED", "UNUSUAL_NIGHT_BATHROOM_ACTIVITY", "UNUSUAL_NIGHT_COMMON_ACTIVITY",
        "POST_DOOR_INACTIVITY",
    }

    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    @traced("B03")

    def accept(self, event: CloudEvent) -> tuple[CloudEvent, bool]:
        if event.home_id not in self.store.homes:
            raise EventValidationError("unknown_home")
        if event.kind not in self.ALLOWED_KINDS:
            raise EventValidationError("unknown_kind")
        if not event.event_id or event.uncertainty_s < 0 or event.server_received_at < event.hub_received_at:
            raise EventValidationError("invalid_event")
        key = (event.home_id, event.event_id)
        durable_accept = getattr(self.store.events, "accept_once", None)
        if durable_accept is not None:
            accepted, duplicate = durable_accept(event)
            if duplicate:
                return accepted, True
            self.store.add_audit(AuditEntry(event.server_received_at, "device", event.home_id, "event.accepted", event.event_id, {"kind": event.kind}))
            return event, False
        existing = self.store.events.get(key)
        if existing is not None:
            return existing, True
        self.store.events[key] = event
        self.store.add_audit(AuditEntry(event.server_received_at, "device", event.home_id, "event.accepted", event.event_id, {"kind": event.kind}))
        return event, False
