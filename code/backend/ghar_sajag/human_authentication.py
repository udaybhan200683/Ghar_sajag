"""Inactive GS-76 human authentication boundary.

The credential verifier is a required, trusted server dependency. This module
does not parse JWTs, validate signatures, issue sessions, or install HTTP routes.
An adapter must verify the credential cryptographically before returning an
assertion. The current tests inject a fixture verifier, not production identity.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Callable, Protocol

from .diagnostic_authorization import ActorSession


class AuthenticationDenied(PermissionError):
    def __init__(self):
        super().__init__("human_not_authenticated")


def _identifier(value: object, maximum: int = 256) -> bool:
    return (type(value) is str and 0 < len(value.encode("utf-8")) <= maximum
            and value.strip() == value)


@dataclass(frozen=True)
class IssuerPolicy:
    issuer: str
    audience: str
    credential_kind: str  # normalized "access" or "session"; deployment chooses one

    def __post_init__(self):
        if (not _identifier(self.issuer) or not self.issuer.startswith("https://") or
                not _identifier(self.audience) or self.credential_kind not in
                ("access", "session")):
            raise ValueError("invalid_issuer_policy")


@dataclass(frozen=True)
class VerifiedAssertion:
    """Output of a cryptographic verifier only; constructing this is not proof."""
    issuer: str
    subject: str
    audience: tuple[str, ...]
    session_id: str
    credential_kind: str
    issued_at: int
    not_before: int
    expires_at: int


class CredentialVerifier(Protocol):
    def verify(self, credential: str) -> VerifiedAssertion | None:
        """Validate signature, pinned algorithms/keys, issuer, audience and use.

        JWKS discovery/rotation must be constrained to the configured issuer;
        an unsigned, unknown-key or otherwise invalid credential returns None.
        No production implementation is provided here.
        """


@dataclass(frozen=True)
class CurrentSession:
    issuer: str
    subject: str
    session_id: str
    actor_id: str
    account_active: bool
    session_active: bool


class SessionDirectory(Protocol):
    def current(self, issuer: str, subject: str, session_id: str) -> CurrentSession | None:
        """Look up server-owned account and current, revocable session state.

        This must be a current authoritative read on every protected request;
        Home membership and company employment are separate current authorities.
        """


class HumanAuthenticationBoundary:
    """Maps a verified credential to an active server-owned actor session.

    No role, company or Home claim is accepted from the credential. This boundary
    is not connected to JsonApi or the service desk until production verifier,
    session store, Home/staff authorities and persistence fencing are qualified.
    """

    def __init__(self, policy: IssuerPolicy, verifier: CredentialVerifier | None,
                 directory: SessionDirectory | None, clock: Callable[[], int]):
        if type(policy) is not IssuerPolicy or not callable(clock):
            raise ValueError("invalid_authentication_dependencies")
        self.policy, self.verifier, self.directory, self.clock = policy, verifier, directory, clock

    def authenticate(self, credential: object) -> ActorSession:
        if (self.verifier is None or self.directory is None or
                not _identifier(credential, 8192)):
            raise AuthenticationDenied()
        at = self.clock()
        if type(at) is not int or at < 0:
            raise AuthenticationDenied()
        try:
            assertion = self.verifier.verify(credential)
        except Exception as error:
            raise AuthenticationDenied() from error
        if type(assertion) is not VerifiedAssertion:
            raise AuthenticationDenied()
        a = assertion
        if (a.issuer != self.policy.issuer or not _identifier(a.subject) or
                type(a.audience) is not tuple or not a.audience or
                any(not _identifier(item) for item in a.audience) or
                self.policy.audience not in a.audience or
                not _identifier(a.session_id) or
                a.credential_kind != self.policy.credential_kind or
                any(type(value) is not int for value in
                    (a.issued_at, a.not_before, a.expires_at)) or
                not 0 <= a.issued_at <= at or not 0 <= a.not_before <= at or
                at >= a.expires_at or a.issued_at >= a.expires_at):
            raise AuthenticationDenied()
        try:
            current = self.directory.current(a.issuer, a.subject, a.session_id)
        except Exception as error:
            raise AuthenticationDenied() from error
        if (type(current) is not CurrentSession or current.issuer != a.issuer or
                current.subject != a.subject or current.session_id != a.session_id or
                not _identifier(current.actor_id) or
                type(current.account_active) is not bool or not current.account_active or
                type(current.session_active) is not bool or not current.session_active):
            raise AuthenticationDenied()
        # A verifier or directory lookup can cross the exact expiry boundary.
        # Never return a session based only on time sampled before those calls.
        completed_at = self.clock()
        if type(completed_at) is not int or completed_at < at or completed_at >= a.expires_at:
            raise AuthenticationDenied()
        # Length prefix keeps the digest unambiguous; the reference exposes no
        # email, display name, Home or staff claim to downstream policy.
        reference = sha256(f"{len(a.issuer)}:{a.issuer}{a.subject}".encode()).hexdigest()
        return ActorSession(current.actor_id, a.session_id, reference, a.expires_at)
