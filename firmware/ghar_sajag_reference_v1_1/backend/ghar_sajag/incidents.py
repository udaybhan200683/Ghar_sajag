from __future__ import annotations

from .logging_config import traced
import uuid

from .identity import IdentityService
from .model import AuditEntry, Incident, IncidentState
from .store import InMemoryStore


class IncidentConflict(RuntimeError):
    pass


class IncidentService:
    def __init__(self, store: InMemoryStore, identity: IdentityService) -> None:
        self.store = store
        self.identity = identity

    @traced("B04")

    def create(self, home_id: str, stable_key: str, kind: str, at: int, is_test: bool = False) -> tuple[Incident, bool]:
        key = (home_id, stable_key)
        existing_id = self.store.incident_keys.get(key)
        if existing_id:
            return self.store.incidents[existing_id], True
        incident_id = f"inc_{uuid.uuid4().hex[:16]}"
        incident = Incident(incident_id, home_id, stable_key, kind, at, is_test=is_test)
        self.store.incidents[incident_id] = incident
        self.store.incident_keys[key] = incident_id
        self.store.add_audit(AuditEntry(at, "system", home_id, "incident.created", incident_id, {"kind": kind, "is_test": is_test}))
        return incident, False

    @traced("B04")

    def claim(self, home_id: str, incident_id: str, actor_id: str, at: int, lease_seconds: int = 300) -> Incident:
        self.identity.require(home_id, actor_id, "read", at)
        incident = self._get(home_id, incident_id)
        if incident.state in {IncidentState.ACKNOWLEDGED, IncidentState.RESOLVED}:
            raise IncidentConflict("incident_closed")
        if incident.owner_id and incident.owner_id != actor_id and (incident.owner_lease_until or 0) > at:
            raise IncidentConflict("owned_by_other_caregiver")
        incident.owner_id = actor_id
        incident.owner_lease_until = at + lease_seconds
        incident.state = IncidentState.CLAIMED
        return incident

    @traced("B04")

    def acknowledge(self, home_id: str, incident_id: str, actor_id: str, at: int) -> Incident:
        self.identity.require(home_id, actor_id, "read", at)
        incident = self._get(home_id, incident_id)
        if incident.state == IncidentState.RESOLVED:
            raise IncidentConflict("incident_already_resolved")
        if incident.owner_id and incident.owner_id != actor_id and (incident.owner_lease_until or 0) > at:
            raise IncidentConflict("owned_by_other_caregiver")
        incident.owner_id = actor_id
        incident.owner_lease_until = None
        incident.acknowledged_at = at
        incident.state = IncidentState.ACKNOWLEDGED
        self.store.add_audit(AuditEntry(at, actor_id, home_id, "incident.acknowledged", incident_id))
        return incident

    @traced("B04")

    def resolve(self, home_id: str, incident_id: str, actor_id: str, at: int) -> Incident:
        incident = self.acknowledge(home_id, incident_id, actor_id, at)
        incident.state = IncidentState.RESOLVED
        incident.resolved_at = at
        self.store.add_audit(AuditEntry(at, actor_id, home_id, "incident.resolved", incident_id))
        return incident

    @traced("B04")

    def _get(self, home_id: str, incident_id: str) -> Incident:
        incident = self.store.incidents.get(incident_id)
        if incident is None or incident.home_id != home_id:
            raise KeyError("incident_not_found")
        return incident
