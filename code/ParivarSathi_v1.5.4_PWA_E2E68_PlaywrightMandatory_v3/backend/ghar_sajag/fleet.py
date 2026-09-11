# Ghar Sajag traceability edition 2.0 | source release 1.4.2
# @module B06 Fleet/config
# @requirements F03, F04, E07, E08, E09, NFR-06
# Requirement links identify design responsibility, not completed acceptance coverage.
# See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
# FleetService handles device records and desired/applied configuration. A desired configuration cannot be
# called active until the target confirms it. The service needs manufacturing claim trust, protected
# device credentials and persisted version concurrency before field rollout.

from __future__ import annotations

from .logging_config import traced
from typing import Any

from .identity import IdentityService
from .model import AuditEntry, DesiredConfig, Device
from .store import InMemoryStore


def _validate_household_config(body: dict[str, Any]) -> None:
    if not isinstance(body, dict):
        raise ValueError("invalid_config")
    morning = body.get("morning")
    rules = body.get("activity_rules")
    if not isinstance(morning, dict) or not isinstance(rules, dict):
        raise ValueError("missing_policy_sections")
    def minute(value: Any) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 1439
    if not minute(rules.get("quiet_start_minute")) or not minute(rules.get("quiet_end_minute")):
        raise ValueError("invalid_quiet_hours")
    door_timeout = rules.get("door_open_timeout_seconds")
    if not isinstance(door_timeout, int) or isinstance(door_timeout, bool) or not 30 <= door_timeout <= 86400:
        raise ValueError("invalid_door_open_timeout")
    if not minute(rules.get("daytime_start_minute")) or not minute(rules.get("daytime_end_minute")):
        raise ValueError("invalid_daytime_window")
    inactivity = rules.get("daytime_inactivity_seconds")
    if not isinstance(inactivity, int) or isinstance(inactivity, bool) or not 300 <= inactivity <= 86400:
        raise ValueError("invalid_inactivity_threshold")


class FleetService:
    def __init__(self, store: InMemoryStore, identity: IdentityService) -> None:
        self.store = store
        self.identity = identity

    @traced("B06")

    def register_device(self, device: Device, actor_id: str, at: int) -> Device:
        self.identity.require(device.home_id, actor_id, "manage", at)
        existing = self.store.devices.get(device.device_id)
        if existing and existing.home_id != device.home_id:
            raise ValueError("device_bound_to_another_home")
        self.store.devices[device.device_id] = device
        self.store.add_audit(AuditEntry(at, actor_id, device.home_id, "device.registered", device.device_id))
        return device

    @traced("B06")

    # @requirements F03, F04, E07, E08, E09, NFR-06
    # Persist desired-version intent in the reference store; active device state changes only after
    # applied acknowledgement.
    def publish_config(self, home_id: str, actor_id: str, body: dict[str, Any], at: int) -> DesiredConfig:
        self.identity.require(home_id, actor_id, "manage", at)
        _validate_household_config(body)
        previous = self.store.configs.get(home_id)
        version = 1 if previous is None else previous.version + 1
        canonical = body.copy()
        canonical["schema"] = 1
        canonical["home_id"] = home_id
        canonical["version"] = version
        desired = DesiredConfig(home_id, version, canonical, at)
        self.store.configs[home_id] = desired
        self.store.add_audit(AuditEntry(at, actor_id, home_id, "config.published", str(version)))
        return desired

    @traced("B06")

    # @requirements F03, F04, E07, E08, E09, NFR-06
    # Record device-reported application version rather than assuming publish success means application.
    def record_applied(self, home_id: str, version: int, at: int) -> DesiredConfig:
        desired = self.store.configs[home_id]
        if version > desired.version:
            raise ValueError("unknown_config_version")
        desired.applied_version = max(version, desired.applied_version or 0)
        self.store.add_audit(AuditEntry(at, "hub", home_id, "config.applied", str(version)))
        return desired
