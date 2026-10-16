"""Authenticated, bounded latest-state NodeHealth read model (GS-148)."""
from __future__ import annotations

import re
import sqlite3

from .cloud_client_identity import TimeReadiness, VerifiedHubContext
from .node_health_policy import DeploymentPolicy, load as load_policy


MAX_BODY_BYTES = 4096
MAX_ID_BYTES = 64
SOURCE_FRESH_SECONDS = 190
_ID = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
_FIELDS = {
    "home_id", "physical_node_id", "logical_node_id",
    "node_enrollment_generation", "session_id", "boot_generation",
    "source_revision", "contact_kind", "profile_id", "heartbeat_seconds",
    "offline_seconds", "hub_received_at", "hub_snapshot_at",
}


class NodeHealthRejected(PermissionError):
    pass


def _integer(value: object, *, minimum: int = 1, maximum: int = 2**63 - 1) -> bool:
    return type(value) is int and minimum <= value <= maximum


class NodeHealthStatusStore:
    """Persist one current record per active enrolled Node, in the event DB."""

    def __init__(self, db: sqlite3.Connection,
                 policy: DeploymentPolicy | None = None) -> None:
        self.db = db
        self.policy = policy or load_policy()

    def ingest(self, context: VerifiedHubContext, requested_home: str,
               body: dict, backend_received_at: int) -> dict:
        if (not isinstance(context, VerifiedHubContext) or
            not context.certificate_chain_verified or
            context.time_readiness is not TimeReadiness.TRUSTED):
            raise NodeHealthRejected("verified_hub_and_trusted_time_required")
        if requested_home != context.home_id:
            raise NodeHealthRejected("wrong_home")
        if (not isinstance(body, dict) or set(body) != _FIELDS or
            not _integer(backend_received_at)):
            raise NodeHealthRejected("invalid_node_health_request")
        if len(str(body).encode("utf-8")) > MAX_BODY_BYTES:
            raise NodeHealthRejected("node_health_request_too_large")
        for field in ("home_id", "physical_node_id", "logical_node_id"):
            value = body[field]
            if not isinstance(value, str) or not _ID.fullmatch(value):
                raise NodeHealthRejected("invalid_node_health_identity")
        if body["home_id"] != context.home_id:
            raise NodeHealthRejected("wrong_home")
        for field in ("node_enrollment_generation", "session_id", "boot_generation",
                      "source_revision", "heartbeat_seconds", "offline_seconds",
                      "hub_received_at", "hub_snapshot_at"):
            if not _integer(body[field]):
                raise NodeHealthRejected("invalid_node_health_number")
        if body["contact_kind"] not in {"NODE_HEALTH", "AUTHENTICATED_EVENT"}:
            raise NodeHealthRejected("unauthenticated_node_contact_kind")
        if body["profile_id"] not in {"configured", "legacy_60", "legacy_120"}:
            raise NodeHealthRejected("unknown_node_profile")
        # The assignment and thresholds come from the backend's trusted policy;
        # a Hub payload cannot select its own lease.
        policy = self.policy.for_device(body["physical_node_id"])
        if (policy is None or body["profile_id"] != self._profile(body["physical_node_id"]) or
            body["heartbeat_seconds"] != policy.heartbeat_seconds or
            body["offline_seconds"] != policy.offline_seconds):
            raise NodeHealthRejected("untrusted_node_profile")
        if body["hub_received_at"] > body["hub_snapshot_at"] or body["hub_snapshot_at"] > backend_received_at:
            raise NodeHealthRejected("invalid_hub_time_order")

        with self.db:
            hub = self.db.execute(
                """SELECT home_id,installation_epoch FROM hub_ownership_registry
                   WHERE hub_device_id=? AND identity_key_fingerprint=? AND state='ACTIVE'""",
                (context.permanent_hub_id, context.ownership_fingerprint_sha256),
            ).fetchone()
            if (hub is None or hub[0] != requested_home or
                hub[1] != context.installation_epoch):
                raise NodeHealthRejected("stale_hub_home_or_epoch")
            enrollment = self.db.execute(
                """SELECT 1 FROM node_enrollment_history WHERE hub_device_id=? AND home_id=?
                   AND physical_node_id=? AND logical_node_id=? AND enrollment_generation=?
                   AND state='ACTIVE'""",
                (context.permanent_hub_id, requested_home, body["physical_node_id"],
                 body["logical_node_id"], body["node_enrollment_generation"]),
            ).fetchone()
            if enrollment is None:
                raise NodeHealthRejected("node_not_currently_enrolled")
            old = self.db.execute(
                """SELECT boot_generation,source_revision FROM node_health_latest
                   WHERE home_id=? AND physical_node_id=?""",
                (requested_home, body["physical_node_id"]),
            ).fetchone()
            if old is not None and (body["boot_generation"] < old[0] or
                (body["boot_generation"] == old[0] and body["source_revision"] <= old[1])):
                raise NodeHealthRejected("replayed_or_out_of_order_node_health")
            self.db.execute(
                """INSERT INTO node_health_latest(
                   home_id,hub_device_id,ownership_fingerprint_sha256,installation_epoch,physical_node_id,logical_node_id,
                   node_enrollment_generation,session_id,boot_generation,source_revision,
                   contact_kind,profile_id,heartbeat_seconds,offline_seconds,hub_received_at,
                   hub_snapshot_at,backend_received_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(home_id,physical_node_id) DO UPDATE SET
                   hub_device_id=excluded.hub_device_id,
                   ownership_fingerprint_sha256=excluded.ownership_fingerprint_sha256,
                   installation_epoch=excluded.installation_epoch,
                   logical_node_id=excluded.logical_node_id,
                   node_enrollment_generation=excluded.node_enrollment_generation,
                   session_id=excluded.session_id,boot_generation=excluded.boot_generation,
                   source_revision=excluded.source_revision,contact_kind=excluded.contact_kind,
                   profile_id=excluded.profile_id,heartbeat_seconds=excluded.heartbeat_seconds,
                   offline_seconds=excluded.offline_seconds,hub_received_at=excluded.hub_received_at,
                   hub_snapshot_at=excluded.hub_snapshot_at,backend_received_at=excluded.backend_received_at,
                   updated_at=excluded.updated_at""",
                (requested_home, context.permanent_hub_id,
                 context.ownership_fingerprint_sha256, context.installation_epoch,
                 body["physical_node_id"], body["logical_node_id"],
                 body["node_enrollment_generation"], body["session_id"],
                 body["boot_generation"], body["source_revision"], body["contact_kind"],
                 body["profile_id"], body["heartbeat_seconds"], body["offline_seconds"],
                 body["hub_received_at"], body["hub_snapshot_at"], backend_received_at,
                 backend_received_at),
            )
        return {"accepted": True, "physical_node_id": body["physical_node_id"],
                "boot_generation": body["boot_generation"],
                "source_revision": body["source_revision"]}

    def latest(self, home_id: str, at: int) -> list[dict]:
        rows = self.db.execute(
            """SELECT h.* FROM node_health_latest h
               JOIN hub_ownership_registry r ON r.hub_device_id=h.hub_device_id
                 AND r.identity_key_fingerprint=h.ownership_fingerprint_sha256
                 AND r.home_id=h.home_id AND r.installation_epoch=h.installation_epoch
                 AND r.state='ACTIVE'
               JOIN node_enrollment_history n ON n.hub_device_id=h.hub_device_id
                 AND n.home_id=h.home_id AND n.physical_node_id=h.physical_node_id
                 AND n.logical_node_id=h.logical_node_id
                 AND n.enrollment_generation=h.node_enrollment_generation AND n.state='ACTIVE'
               WHERE h.home_id=? ORDER BY h.logical_node_id LIMIT 100""",
            (home_id,),
        ).fetchall()
        result = []
        for row in rows:
            node_age = max(0, at - row["hub_received_at"])
            source_age = max(0, at - row["backend_received_at"])
            if at < row["backend_received_at"] or source_age > SOURCE_FRESH_SECONDS:
                status = "UNKNOWN"
            elif node_age > row["offline_seconds"]:
                status = "OFFLINE"
            else:
                status = "ONLINE"
            result.append({
                "physical_node_id": row["physical_node_id"],
                "logical_node_id": row["logical_node_id"],
                "status": status,
                "coverage": "COVERED" if status == "ONLINE" else "UNKNOWN",
                "contact_kind": row["contact_kind"],
                "profile_id": row["profile_id"],
                "heartbeat_seconds": row["heartbeat_seconds"],
                "offline_seconds": row["offline_seconds"],
                "hub_received_at": row["hub_received_at"],
                "hub_contact_at": row["hub_snapshot_at"],
                "backend_received_at": row["backend_received_at"],
                "node_contact_age_seconds": node_age,
                "cloud_source_age_seconds": source_age,
                "source_fresh": (at >= row["backend_received_at"] and
                                 source_age <= SOURCE_FRESH_SECONDS),
            })
        return result

    def latest_hub_contact(self, home_id: str) -> int | None:
        row = self.db.execute(
            """SELECT MAX(hub_snapshot_at) FROM node_health_latest h
               JOIN hub_ownership_registry r ON r.hub_device_id=h.hub_device_id
                 AND r.identity_key_fingerprint=h.ownership_fingerprint_sha256
                 AND r.home_id=h.home_id AND r.installation_epoch=h.installation_epoch
                 AND r.state='ACTIVE' WHERE h.home_id=?""",
            (home_id,),
        ).fetchone()
        return None if row is None else row[0]

    def latest_hub_backend_contact(self, home_id: str) -> int | None:
        row = self.db.execute(
            """SELECT MAX(h.backend_received_at) FROM node_health_latest h
               JOIN hub_ownership_registry r ON r.hub_device_id=h.hub_device_id
                 AND r.identity_key_fingerprint=h.ownership_fingerprint_sha256
                 AND r.home_id=h.home_id AND r.installation_epoch=h.installation_epoch
                 AND r.state='ACTIVE' WHERE h.home_id=?""",
            (home_id,),
        ).fetchone()
        return None if row is None else row[0]

    def _profile(self, physical_node_id: str) -> str | None:
        return self.policy.profiles.get(physical_node_id)
