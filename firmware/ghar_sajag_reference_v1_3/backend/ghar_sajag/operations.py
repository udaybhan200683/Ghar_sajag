from __future__ import annotations

from .logging_config import traced
from .model import AuditEntry
from .store import InMemoryStore


class OperationsService:
    def __init__(self, store: InMemoryStore, hub_lease_seconds: int = 190) -> None:
        self.store = store
        self.hub_lease_seconds = hub_lease_seconds

    @traced("B08")

    def hub_health(self, home_id: str, at: int) -> dict[str, int | bool | None]:
        beats = [
            event for (candidate, _), event in self.store.events.items()
            if candidate == home_id and event.kind == "HUB_HEARTBEAT"
        ]
        last_seen = max((event.server_received_at for event in beats), default=None)
        return {
            "reachable": last_seen is not None and at - last_seen <= self.hub_lease_seconds,
            "last_seen_at": last_seen,
            "lease_seconds": self.hub_lease_seconds,
        }

    @traced("B08")

    def diagnostics(self, home_id: str) -> dict[str, int]:
        return {
            "events": sum(1 for candidate, _ in self.store.events if candidate == home_id),
            "incidents": sum(1 for value in self.store.incidents.values() if value.home_id == home_id),
            "notification_jobs": sum(1 for value in self.store.notification_jobs.values() if value.home_id == home_id),
            "devices": sum(1 for value in self.store.devices.values() if value.home_id == home_id),
            "advisory_notices": sum(1 for value in self.store.advisory_notices.values() if value.home_id == home_id),
            "daily_summaries": sum(1 for key in self.store.daily_summaries if key[0] == home_id),
            "audit_entries": sum(1 for value in self.store.audit if value.home_id == home_id),
        }

    @traced("B08")

    def record_support_action(self, home_id: str, actor_id: str, action: str, subject_id: str, at: int) -> None:
        self.store.add_audit(AuditEntry(at, actor_id, home_id, f"support.{action}", subject_id))
