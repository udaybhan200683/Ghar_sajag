from __future__ import annotations

from .logging_config import traced
from dataclasses import dataclass, field

from .model import AdvisoryNotice, AuditEntry, CloudEvent, DailySummary, DesiredConfig, Device, Home, Incident, Membership, NotificationJob


@dataclass
class InMemoryStore:
    """Single-process transactional model used by host tests.

    Production replaces this with PostgreSQL transactions and unique constraints;
    service method boundaries intentionally match those future transactions.
    """

    homes: dict[str, Home] = field(default_factory=dict)
    memberships: dict[tuple[str, str], Membership] = field(default_factory=dict)
    events: dict[tuple[str, str], CloudEvent] = field(default_factory=dict)
    incidents: dict[str, Incident] = field(default_factory=dict)
    incident_keys: dict[tuple[str, str], str] = field(default_factory=dict)
    notification_jobs: dict[str, NotificationJob] = field(default_factory=dict)
    notification_keys: dict[tuple[str, str, int], str] = field(default_factory=dict)
    devices: dict[str, Device] = field(default_factory=dict)
    configs: dict[str, DesiredConfig] = field(default_factory=dict)
    audit: list[AuditEntry] = field(default_factory=list)
    advisory_notices: dict[str, AdvisoryNotice] = field(default_factory=dict)
    advisory_keys: dict[tuple[str, str, str], str] = field(default_factory=dict)
    daily_summaries: dict[tuple[str, str, int], DailySummary] = field(default_factory=dict)

    @traced("B09")

    def add_audit(self, entry: AuditEntry) -> None:
        self.audit.append(entry)
