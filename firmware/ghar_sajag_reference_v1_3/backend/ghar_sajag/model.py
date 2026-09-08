from __future__ import annotations

from .logging_config import traced
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Role(str, Enum):
    OWNER = "OWNER"
    CAREGIVER = "CAREGIVER"
    INSTALLER = "INSTALLER"


class HomeMode(str, Enum):
    HOME = "HOME"
    AWAY = "AWAY"
    PAUSED = "PAUSED"
    VISITOR = "VISITOR"
    PRIVACY = "PRIVACY"


class IncidentState(str, Enum):
    OPEN = "OPEN"
    CLAIMED = "CLAIMED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    ROUTE_EXHAUSTED = "ROUTE_EXHAUSTED"


class DeliveryState(str, Enum):
    CREATED = "CREATED"
    PROVIDER_ACCEPTED = "PROVIDER_ACCEPTED"
    HUMAN_ACKED = "HUMAN_ACKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass(slots=True)
class Membership:
    home_id: str
    actor_id: str
    role: Role
    active: bool = True
    expires_at: int | None = None


@dataclass(slots=True)
class Resident:
    resident_id: str
    display_name: str
    consent_active: bool
    consent_recorded_at: int


@dataclass(slots=True)
class Home:
    home_id: str
    display_name: str
    timezone: str
    language: str
    owner_id: str
    residents: dict[str, Resident] = field(default_factory=dict)
    primary_caregiver_id: str | None = None
    backup_caregiver_id: str | None = None
    mode: HomeMode = HomeMode.HOME
    version: int = 1


@dataclass(slots=True)
class CloudEvent:
    home_id: str
    event_id: str
    kind: str
    location: str
    occurred_at: int
    hub_received_at: int
    server_received_at: int
    uncertainty_s: int = 0
    is_test: bool = False
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Incident:
    incident_id: str
    home_id: str
    stable_key: str
    kind: str
    created_at: int
    state: IncidentState = IncidentState.OPEN
    owner_id: str | None = None
    owner_lease_until: int | None = None
    acknowledged_at: int | None = None
    resolved_at: int | None = None
    is_test: bool = False


@dataclass(slots=True)
class NotificationJob:
    job_id: str
    incident_id: str
    home_id: str
    recipient_id: str
    stage: int
    due_at: int
    state: DeliveryState = DeliveryState.CREATED
    attempts: int = 0
    provider_reference: str | None = None


@dataclass(slots=True)
class Device:
    device_id: str
    home_id: str
    kind: str
    board_profile: str
    location: str
    capability_profile: str
    credential_version: int
    firmware_version: str
    last_seen_at: int | None = None
    sensor_fault: bool = False


@dataclass(slots=True)
class DesiredConfig:
    home_id: str
    version: int
    body: dict[str, Any]
    created_at: int
    applied_version: int | None = None


@dataclass(slots=True)
class AuditEntry:
    at: int
    actor_id: str
    home_id: str
    action: str
    subject_id: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AdvisoryNotice:
    notice_id: str
    home_id: str
    event_id: str
    kind: str
    created_at: int
    recipient_id: str
    is_test: bool = False


@dataclass(slots=True)
class DailySummary:
    home_id: str
    local_date: str
    policy_version: int
    generated_at: int
    content: dict[str, Any]
