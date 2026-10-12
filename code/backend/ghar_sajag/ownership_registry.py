"""Durable ownership policy behind a trusted identity/installer boundary.

This module enforces Home/Hub/Node lifecycle invariants. It does not verify
certificates, issue credentials, or authenticate caregivers. The only callers
allowed to construct the proof/authorization records below are the future
trusted GS-109 identity and installer adapters; no HTTP route accepts them.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import sqlite3
import threading

from .durable_commit import AuthorizationDecision


class OwnershipConflict(PermissionError):
    pass


class TransferBlocked(OwnershipConflict):
    pass


@dataclass(frozen=True)
class VerifiedHubIdentity:
    hub_device_id: str
    identity_key_fingerprint: str
    proof_reference: str


@dataclass(frozen=True)
class AuthorizedHomeOperation:
    actor_id: str
    home_id: str
    action: str
    authorization_reference: str


@dataclass(frozen=True)
class VerifiedNodeEnrollment:
    physical_node_id: str
    logical_node_id: str
    enrollment_generation: int
    identity_key_fingerprint: str
    proof_reference: str


_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")


class HubOwnershipRegistry:
    """SQLite ownership state machine; use the same DB as event commits."""

    def __init__(self, db: sqlite3.Connection, lock: threading.RLock | None = None) -> None:
        self.db = db
        self.lock = lock or threading.RLock()

    @staticmethod
    def _valid_ref(*values: str) -> bool:
        return all(isinstance(value, str) and 1 <= len(value) <= 160 for value in values)

    @staticmethod
    def _fingerprint(value: str) -> bool:
        return isinstance(value, str) and _FINGERPRINT.fullmatch(value) is not None

    def register_unclaimed_identity(self, identity: VerifiedHubIdentity, at: int) -> None:
        if (not self._valid_ref(identity.hub_device_id, identity.proof_reference) or
            not self._fingerprint(identity.identity_key_fingerprint) or type(at) is not int):
            raise ValueError("invalid_verified_hub_identity")
        with self._transaction():
            existing = self.db.execute(
                "SELECT identity_key_fingerprint FROM hub_ownership_registry WHERE hub_device_id=?",
                (identity.hub_device_id,),
            ).fetchone()
            if existing is not None:
                if existing[0] != identity.identity_key_fingerprint:
                    raise OwnershipConflict("permanent_hub_identity_key_changed")
                raise OwnershipConflict("hub_identity_already_registered")
            try:
                self.db.execute(
                    """INSERT INTO hub_ownership_registry
                       (hub_device_id,identity_key_fingerprint,state,installation_epoch,created_at,updated_at)
                       VALUES(?,?,'UNCLAIMED',0,?,?)""",
                    (identity.hub_device_id, identity.identity_key_fingerprint, at, at),
                )
                self.db.execute(
                    """INSERT INTO hub_ownership_history
                       (hub_device_id,transition,prior_epoch,new_epoch,actor_id,
                        authorization_reference,possession_proof_reference,occurred_at)
                       VALUES(?,'IDENTITY_REGISTERED',0,0,'identity-authority',?,?,?)""",
                    (identity.hub_device_id, identity.proof_reference,
                     identity.proof_reference, at),
                )
            except sqlite3.IntegrityError as error:
                raise OwnershipConflict("hub_identity_already_registered") from error

    def claim_home(self, identity: VerifiedHubIdentity,
                   operation: AuthorizedHomeOperation, at: int) -> int:
        self._validate_operation(identity, operation, "CLAIM_HUB")
        with self._transaction():
            row = self.db.execute(
                "SELECT identity_key_fingerprint,state,home_id,installation_epoch FROM hub_ownership_registry WHERE hub_device_id=?",
                (identity.hub_device_id,),
            ).fetchone()
            if row is None or row[0] != identity.identity_key_fingerprint:
                raise OwnershipConflict("hub_identity_proof_mismatch")
            if row[1] != "UNCLAIMED" or row[2] is not None or row[3] != 0:
                raise OwnershipConflict("hub_not_claimable")
            if not self.db.execute("SELECT 1 FROM households WHERE home_id=?", (operation.home_id,)).fetchone():
                raise OwnershipConflict("unknown_home")
            self.db.execute(
                "UPDATE hub_ownership_registry SET state='ACTIVE',home_id=?,installation_epoch=1,updated_at=? WHERE hub_device_id=?",
                (operation.home_id, at, identity.hub_device_id),
            )
            self._history(identity.hub_device_id, "CLAIMED", None, operation.home_id,
                          0, 1, operation, identity, at)
            return 1

    def begin_transfer(self, identity: VerifiedHubIdentity,
                       operation: AuthorizedHomeOperation, new_home_id: str,
                       at: int) -> int:
        self._validate_operation(identity, operation, "TRANSFER_HUB")
        if not self._valid_ref(new_home_id):
            raise ValueError("invalid_transfer_home")
        with self._transaction():
            row = self.db.execute(
                "SELECT identity_key_fingerprint,state,home_id,installation_epoch FROM hub_ownership_registry WHERE hub_device_id=?",
                (identity.hub_device_id,),
            ).fetchone()
            if row is None or row[0] != identity.identity_key_fingerprint:
                raise OwnershipConflict("hub_identity_proof_mismatch")
            if row[1] != "ACTIVE" or row[2] != operation.home_id:
                raise OwnershipConflict("current_home_transfer_authorization_required")
            if row[2] == new_home_id or not self.db.execute(
                    "SELECT 1 FROM households WHERE home_id=?", (new_home_id,)).fetchone():
                raise OwnershipConflict("invalid_transfer_destination")
            new_epoch = row[3] + 1
            self.db.execute(
                """UPDATE hub_ownership_registry SET state='TRANSFER_PENDING',pending_home_id=?,
                   installation_epoch=?,updated_at=? WHERE hub_device_id=?""",
                (new_home_id, new_epoch, at, identity.hub_device_id),
            )
            self._history(identity.hub_device_id, "TRANSFER_PENDING", row[2], new_home_id,
                          row[3], new_epoch, operation, identity, at)
            return new_epoch

    def complete_transfer(self, *_args, **_kwargs) -> None:
        # The old-Home durable outbox may still contain records and the approved
        # data disposition/local reset protocol is not defined. Never guess.
        raise TransferBlocked("pending_old_home_data_disposition_and_local_rebind_unapproved")

    def revoke_hub(self, identity: VerifiedHubIdentity,
                   operation: AuthorizedHomeOperation, at: int) -> int:
        self._validate_operation(identity, operation, "REVOKE_HUB")
        with self._transaction():
            row = self.db.execute(
                "SELECT identity_key_fingerprint,state,home_id,installation_epoch FROM hub_ownership_registry WHERE hub_device_id=?",
                (identity.hub_device_id,),
            ).fetchone()
            if row is None or row[0] != identity.identity_key_fingerprint or row[1] != "ACTIVE" or row[2] != operation.home_id:
                raise OwnershipConflict("hub_revocation_not_authorized")
            epoch = row[3] + 1
            self.db.execute(
                "UPDATE hub_ownership_registry SET state='REVOKED',installation_epoch=?,updated_at=? WHERE hub_device_id=?",
                (epoch, at, identity.hub_device_id),
            )
            self.db.execute("UPDATE node_enrollment_history SET state='REVOKED',ended_at=? WHERE hub_device_id=? AND state='ACTIVE'",
                             (at, identity.hub_device_id))
            self._history(identity.hub_device_id, "REVOKED", row[2], None, row[3], epoch,
                          operation, identity, at)
            return epoch

    def enroll_node(self, identity: VerifiedHubIdentity,
                    operation: AuthorizedHomeOperation,
                    node: VerifiedNodeEnrollment, at: int) -> None:
        self._validate_operation(identity, operation, "ENROLL_NODE")
        if (not self._valid_ref(node.physical_node_id, node.logical_node_id, node.proof_reference) or
            not self._fingerprint(node.identity_key_fingerprint) or
            type(node.enrollment_generation) is not int or node.enrollment_generation <= 0):
            raise ValueError("invalid_verified_node_enrollment")
        with self._transaction():
            hub = self.db.execute(
                "SELECT identity_key_fingerprint,state,home_id FROM hub_ownership_registry WHERE hub_device_id=?",
                (identity.hub_device_id,),
            ).fetchone()
            if (hub is None or hub[0] != identity.identity_key_fingerprint or hub[1] != "ACTIVE" or
                hub[2] != operation.home_id):
                raise OwnershipConflict("active_home_hub_required_for_node_enrollment")
            prior = self.db.execute(
                "SELECT MAX(enrollment_generation) FROM node_enrollment_history WHERE physical_node_id=?",
                (node.physical_node_id,),
            ).fetchone()[0]
            if prior is not None and node.enrollment_generation <= prior:
                raise OwnershipConflict("node_enrollment_generation_not_globally_monotonic")
            self.db.execute(
                "UPDATE node_enrollment_history SET state='REPLACED',ended_at=? WHERE hub_device_id=? AND physical_node_id=? AND state='ACTIVE'",
                (at, identity.hub_device_id, node.physical_node_id),
            )
            try:
                self.db.execute(
                    """INSERT INTO node_enrollment_history
                       (hub_device_id,home_id,physical_node_id,logical_node_id,enrollment_generation,
                        identity_key_fingerprint,state,authorization_reference,proof_reference,enrolled_at)
                       VALUES(?,?,?,?,?,?,'ACTIVE',?,?,?)""",
                    (identity.hub_device_id, operation.home_id, node.physical_node_id,
                     node.logical_node_id, node.enrollment_generation,
                     node.identity_key_fingerprint, operation.authorization_reference,
                     node.proof_reference, at),
                )
            except sqlite3.IntegrityError as error:
                if "node_enrollment_history.physical_node_id" in str(error):
                    raise OwnershipConflict("node_identity_already_active") from error
                raise

    def revoke_node(self, identity: VerifiedHubIdentity,
                    operation: AuthorizedHomeOperation, physical_node_id: str,
                    generation: int, at: int) -> None:
        self._validate_operation(identity, operation, "REVOKE_NODE")
        with self._transaction():
            hub = self.db.execute(
                "SELECT identity_key_fingerprint,state,home_id FROM hub_ownership_registry WHERE hub_device_id=?",
                (identity.hub_device_id,),
            ).fetchone()
            if hub is None or hub[0] != identity.identity_key_fingerprint or hub[1] != "ACTIVE" or hub[2] != operation.home_id:
                raise OwnershipConflict("active_home_hub_required_for_node_revocation")
            changed = self.db.execute(
                """UPDATE node_enrollment_history SET state='REVOKED',ended_at=?
                   WHERE hub_device_id=? AND physical_node_id=? AND enrollment_generation=? AND state='ACTIVE'""",
                (at, identity.hub_device_id, physical_node_id, generation),
            ).rowcount
            if changed != 1:
                raise OwnershipConflict("active_node_generation_not_found")

    @staticmethod
    def authorize_cloud_event(db: sqlite3.Connection, context: dict,
                              home_id: str, body: dict) -> AuthorizationDecision | None:
        """Validate trusted Hub epoch and original Node generation in caller's tx."""
        if not db.in_transaction:
            raise RuntimeError("ownership_check_requires_event_transaction")
        hub_id = context.get("gs.verified_hub") if isinstance(context, dict) else None
        fingerprint = context.get("gs.hub_key_fingerprint") if isinstance(context, dict) else None
        epoch = context.get("gs.installation_epoch") if isinstance(context, dict) else None
        if (not isinstance(hub_id, str) or not HubOwnershipRegistry._fingerprint(fingerprint) or
            type(epoch) is not int or epoch <= 0 or not isinstance(body, dict) or
            body.get("cloudsync_version") != 2 or
            type(body.get("node_enrollment_generation")) is not int or
            body["node_enrollment_generation"] <= 0):
            return None
        hub = db.execute(
            """SELECT home_id,installation_epoch FROM hub_ownership_registry
               WHERE hub_device_id=? AND identity_key_fingerprint=? AND state='ACTIVE'""",
            (hub_id, fingerprint),
        ).fetchone()
        if hub is None or hub[0] != home_id or hub[1] != epoch:
            return None
        key = body.get("event_key")
        if not isinstance(key, dict) or set(key) != {
                "physical_device_id", "logical_node_id", "origin_session_id", "event_sequence"}:
            return None
        node = db.execute(
            """SELECT 1 FROM node_enrollment_history
               WHERE hub_device_id=? AND home_id=? AND physical_node_id=? AND logical_node_id=?
                 AND enrollment_generation=? AND state='ACTIVE'""",
            (hub_id, home_id, key.get("physical_device_id"), key.get("logical_node_id"),
             body["node_enrollment_generation"]),
        ).fetchone()
        if node is not None:
            return AuthorizationDecision(hub_id, epoch, body["node_enrollment_generation"])

        # A generation that has since been replaced/revoked may only replay an
        # already durable, exact EventKey under the same active Hub epoch. The
        # committer still compares the immutable payload hash and persisted
        # provenance before returning duplicate COMMITTED. This cannot admit a
        # new event from an old generation or move data across Home/epoch.
        prior = db.execute(
            """SELECT hub_device_id,ownership_epoch,node_enrollment_generation
               FROM durable_event_commits WHERE home_id=? AND physical_device_id=?
                 AND logical_node_id=? AND origin_session_id=? AND event_sequence=?""",
            (home_id, key["physical_device_id"], key["logical_node_id"],
             key["origin_session_id"], key["event_sequence"]),
        ).fetchone()
        if prior is None or tuple(prior) != (hub_id, epoch, body["node_enrollment_generation"]):
            return None
        return AuthorizationDecision(hub_id, epoch, body["node_enrollment_generation"])

    def _history(self, hub_id: str, transition: str, old_home: str | None,
                 new_home: str | None, old_epoch: int, new_epoch: int,
                 operation: AuthorizedHomeOperation, identity: VerifiedHubIdentity,
                 at: int) -> None:
        self.db.execute(
            """INSERT INTO hub_ownership_history
               (hub_device_id,transition,from_home_id,to_home_id,prior_epoch,new_epoch,
                actor_id,authorization_reference,possession_proof_reference,occurred_at)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (hub_id, transition, old_home, new_home, old_epoch, new_epoch,
             operation.actor_id, operation.authorization_reference,
             identity.proof_reference, at),
        )

    @staticmethod
    def _validate_operation(identity: VerifiedHubIdentity,
                            operation: AuthorizedHomeOperation, expected_action: str) -> None:
        if (not HubOwnershipRegistry._valid_ref(identity.hub_device_id, identity.proof_reference,
                operation.actor_id, operation.home_id, operation.authorization_reference) or
            not HubOwnershipRegistry._fingerprint(identity.identity_key_fingerprint) or
            operation.action != expected_action):
            raise OwnershipConflict("authenticated_authorized_operation_required")

    class _Transaction:
        def __init__(self, registry: "HubOwnershipRegistry") -> None:
            self.registry = registry
        def __enter__(self):
            self.registry.lock.acquire()
            if self.registry.db.in_transaction:
                self.registry.lock.release()
                raise RuntimeError("ownership_registry_requires_clean_transaction")
            self.registry.db.execute("BEGIN IMMEDIATE")
            return self.registry
        def __exit__(self, kind, error, _traceback):
            try:
                if kind is None:
                    self.registry.db.commit()
                else:
                    self.registry.db.rollback()
            finally:
                self.registry.lock.release()
            return False

    def _transaction(self):
        return self._Transaction(self)
