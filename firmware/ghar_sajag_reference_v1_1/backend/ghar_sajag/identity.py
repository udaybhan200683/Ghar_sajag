from __future__ import annotations

from .logging_config import traced
from .model import AuditEntry, Membership, Role
from .store import InMemoryStore


class AuthorizationError(PermissionError):
    pass


class IdentityService:
    READ_ROLES = {Role.OWNER, Role.CAREGIVER, Role.INSTALLER}
    MANAGE_ROLES = {Role.OWNER}

    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    @traced("B01")

    def grant(self, home_id: str, actor_id: str, role: Role, at: int, expires_at: int | None = None) -> Membership:
        membership = Membership(home_id, actor_id, role, True, expires_at)
        self.store.memberships[(home_id, actor_id)] = membership
        self.store.add_audit(AuditEntry(at, actor_id, home_id, "membership.granted", actor_id, {"role": role.value}))
        return membership

    @traced("B01")

    def revoke(self, home_id: str, actor_id: str, performed_by: str, at: int) -> None:
        self.require(home_id, performed_by, "manage", at)
        membership = self.store.memberships.get((home_id, actor_id))
        if membership:
            membership.active = False
        self.store.add_audit(AuditEntry(at, performed_by, home_id, "membership.revoked", actor_id))

    @traced("B01")

    def require(self, home_id: str, actor_id: str, permission: str, at: int) -> Membership:
        membership = self.store.memberships.get((home_id, actor_id))
        allowed = self.MANAGE_ROLES if permission == "manage" else self.READ_ROLES
        if (
            membership is None
            or not membership.active
            or membership.role not in allowed
            or (membership.expires_at is not None and at >= membership.expires_at)
        ):
            raise AuthorizationError("not_authorized")
        return membership
