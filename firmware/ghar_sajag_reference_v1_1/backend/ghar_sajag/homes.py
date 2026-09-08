from __future__ import annotations

from .logging_config import traced
from .identity import IdentityService
from .model import AuditEntry, Home, HomeMode, Resident, Role
from .store import InMemoryStore


class HomeValidationError(ValueError):
    pass


class HomeService:
    def __init__(self, store: InMemoryStore, identity: IdentityService) -> None:
        self.store = store
        self.identity = identity

    @traced("B02")

    def create(
        self,
        home_id: str,
        display_name: str,
        timezone: str,
        language: str,
        owner_id: str,
        residents: list[Resident],
        at: int,
    ) -> Home:
        if home_id in self.store.homes:
            raise HomeValidationError("home_exists")
        if "/" not in timezone or not display_name.strip():
            raise HomeValidationError("invalid_timezone_or_name")
        if not residents or not all(item.consent_active for item in residents):
            raise HomeValidationError("active_resident_consent_required")
        home = Home(home_id, display_name.strip(), timezone, language, owner_id)
        home.residents = {item.resident_id: item for item in residents}
        self.store.homes[home_id] = home
        self.identity.grant(home_id, owner_id, Role.OWNER, at)
        self.store.add_audit(AuditEntry(at, owner_id, home_id, "home.created", home_id))
        return home

    @traced("B02")

    def set_caregivers(self, home_id: str, owner_id: str, primary_id: str, backup_id: str, at: int) -> Home:
        self.identity.require(home_id, owner_id, "manage", at)
        if primary_id == backup_id:
            raise HomeValidationError("backup_must_be_distinct")
        self.identity.grant(home_id, primary_id, Role.CAREGIVER, at)
        self.identity.grant(home_id, backup_id, Role.CAREGIVER, at)
        home = self.store.homes[home_id]
        home.primary_caregiver_id = primary_id
        home.backup_caregiver_id = backup_id
        home.version += 1
        return home

    @traced("B02")

    def set_mode(self, home_id: str, actor_id: str, mode: HomeMode, at: int) -> Home:
        self.identity.require(home_id, actor_id, "manage", at)
        home = self.store.homes[home_id]
        home.mode = mode
        home.version += 1
        self.store.add_audit(AuditEntry(at, actor_id, home_id, "home.mode_changed", home_id, {"mode": mode.value}))
        return home

    @traced("B02")

    def withdraw_resident_consent(self, home_id: str, resident_id: str, actor_id: str, at: int) -> Home:
        self.identity.require(home_id, actor_id, "manage", at)
        home = self.store.homes[home_id]
        resident = home.residents.get(resident_id)
        if resident is None:
            raise HomeValidationError("resident_not_found")
        resident.consent_active = False
        home.mode = HomeMode.PRIVACY
        home.version += 1
        self.store.add_audit(AuditEntry(at, actor_id, home_id, "consent.withdrawn", resident_id))
        return home
