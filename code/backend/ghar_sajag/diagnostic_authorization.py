"""ED-D02 non-composed policy boundary; NOT an authenticator or grant issuer.

Only a future trusted GS-76/143 adapter may supply these snapshots. Types and
issuer references are not cryptographic proof. No production caller is wired.
Request headers/dictionaries are never decoded into identities here.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .model import Role


class DiagnosticAction(str, Enum):
    READ_DIAGNOSTICS = "READ_DIAGNOSTICS"


class DiagnosticDenied(PermissionError):
    def __init__(self, *, unauthenticated=False):
        super().__init__("diagnostic_not_authorized")
        self.unauthenticated = unauthenticated


@dataclass(frozen=True)
class ActorSession:
    actor_id: str
    session_id: str
    issuer_reference: str
    expires_at: int


@dataclass(frozen=True)
class HomeMembership:
    home_id: str
    actor_id: str
    role: Role
    version: int
    active: bool
    expires_at: int | None = None


@dataclass(frozen=True)
class DiagnosticGrant:
    home_id: str
    actor_id: str
    ownership_epoch: int
    membership_version: int
    version: int
    expires_at: int
    revoked: bool
    action: DiagnosticAction = DiagnosticAction.READ_DIAGNOSTICS


@dataclass(frozen=True)
class TrustedAccessSnapshot:
    actor: ActorSession
    membership: HomeMembership
    grant: DiagnosticGrant | None
    ownership_epoch: int


@dataclass(frozen=True)
class EventAccess:
    home_id: str
    canonical_event_id: str
    ownership_epoch: int
    enrollment_generation: int


class TrustedDiagnosticAuthority(Protocol):
    def resolve(self, server_context: object, home_id: str) -> TrustedAccessSnapshot | None:
        """Verify issuer/session and read CURRENT atomic membership/grant/epoch.

        MUST invalidate sessions on logout and versions on membership/role/grant
        changes. No claims from an untrusted request may create this snapshot.
        This production adapter and its durable lifecycle are NOT implemented.
        """

    def event_access(self, server_context: object, home_id: str, canonical_event_id: str) -> EventAccess | None:
        """Resolve current authorized Home/device/original-generation binding.

        No binding means no row access. Original/retired generation eligibility
        is supplied by the ownership authority, never inferred by diagnostics.
        """


def positive(value):
    return type(value) is int and value > 0


class DiagnosticAuthorizer:
    def __init__(self, authority: TrustedDiagnosticAuthority | None = None):
        self.authority = authority

    def require(self, context, home_id, action, at) -> TrustedAccessSnapshot:
        # There is deliberately no GRANT, control, generic READ or admin bypass.
        if action != DiagnosticAction.READ_DIAGNOSTICS or type(action) not in (str, DiagnosticAction):
            raise DiagnosticDenied()
        if self.authority is None:
            raise DiagnosticDenied(unauthenticated=True)
        if type(home_id) is not str or not home_id or type(at) is not int or at < 0:
            raise DiagnosticDenied()
        resolver = getattr(self.authority, "resolve", None)
        if not callable(resolver):
            raise DiagnosticDenied(unauthenticated=True)
        state = resolver(context, home_id)
        if state is None:
            raise DiagnosticDenied(unauthenticated=True)
        if type(state) is not TrustedAccessSnapshot or type(state.actor) is not ActorSession:
            raise DiagnosticDenied()
        a, m, g = state.actor, state.membership, state.grant
        if (not all(type(v) is str and 0 < len(v.encode()) <= 256
                    for v in (a.actor_id, a.session_id, a.issuer_reference)) or
                not positive(a.expires_at) or at >= a.expires_at):
            raise DiagnosticDenied(unauthenticated=True)
        if (type(m) is not HomeMembership or type(g) is not DiagnosticGrant or
                m.home_id != home_id or g.home_id != home_id or
                m.actor_id != a.actor_id or g.actor_id != a.actor_id or
                type(m.active) is not bool or not m.active or type(m.role) is not Role or
                type(g.revoked) is not bool or g.revoked or
                g.action is not DiagnosticAction.READ_DIAGNOSTICS or
                not all(positive(v) for v in (state.ownership_epoch, m.version,
                                             g.ownership_epoch, g.membership_version, g.version, g.expires_at)) or
                g.ownership_epoch != state.ownership_epoch or g.membership_version != m.version or
                at >= g.expires_at or
                (m.expires_at is not None and (not positive(m.expires_at) or at >= m.expires_at))):
            raise DiagnosticDenied()
        return state

    def event_access(self, context, state, canonical):
        resolver = getattr(self.authority, "event_access", None)
        if not callable(resolver):
            raise DiagnosticDenied()
        binding = resolver(context, state.membership.home_id, canonical)
        if binding is None:
            return None
        if (type(binding) is not EventAccess or binding.home_id != state.membership.home_id or
                binding.canonical_event_id != canonical or not positive(binding.ownership_epoch) or
                binding.ownership_epoch != state.ownership_epoch or not positive(binding.enrollment_generation)):
            raise DiagnosticDenied()
        return binding
