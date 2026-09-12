# Ghar Sajag traceability edition 2.0 | source release 1.4.2
# @module B08 Operations/data
# @requirements F02, F11, F13, E01, E04, E05, E08, E09, E10, NFR-09
# Requirement links identify design responsibility, not completed acceptance coverage.
# See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
# OperationsService separates fleet freshness and support auditing from routine evidence. Operational
# counters can identify missing links without recording resident names or raw payloads. Backups,
# export/deletion, retention and independent service monitoring need a real storage/deployment adapter.

from __future__ import annotations

from .logging_config import traced
from dataclasses import dataclass, field
from typing import Any

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
    # Battery analytics stores typed profile/sample objects without importing the
    # battery module here (avoids a circular import). Production maps these to SQL.
    battery_profiles: dict[str, Any] = field(default_factory=dict)
    battery_samples: dict[str, list[Any]] = field(default_factory=dict)

    @traced("B09")

    def add_audit(self, entry: AuditEntry) -> None:
        self.audit.append(entry)
