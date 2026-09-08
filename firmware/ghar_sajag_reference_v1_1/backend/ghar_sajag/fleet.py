from __future__ import annotations

from .logging_config import traced
from typing import Any

from .identity import IdentityService
from .model import AuditEntry, DesiredConfig, Device
from .store import InMemoryStore


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

    def publish_config(self, home_id: str, actor_id: str, body: dict[str, Any], at: int) -> DesiredConfig:
        self.identity.require(home_id, actor_id, "manage", at)
        previous = self.store.configs.get(home_id)
        version = 1 if previous is None else previous.version + 1
        desired = DesiredConfig(home_id, version, body.copy(), at)
        self.store.configs[home_id] = desired
        self.store.add_audit(AuditEntry(at, actor_id, home_id, "config.published", str(version)))
        return desired

    @traced("B06")

    def record_applied(self, home_id: str, version: int, at: int) -> DesiredConfig:
        desired = self.store.configs[home_id]
        if version > desired.version:
            raise ValueError("unknown_config_version")
        desired.applied_version = max(version, desired.applied_version or 0)
        self.store.add_audit(AuditEntry(at, "hub", home_id, "config.applied", str(version)))
        return desired
