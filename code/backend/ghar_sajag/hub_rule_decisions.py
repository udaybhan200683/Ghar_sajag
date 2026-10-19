"""Durable, separately identified Hub rule decisions for the isolated GS-178 path.

The caller supplies a TLS-verified Hub context. The transaction rechecks the
current ownership registry; no request body or HTTP header grants authority.
"""
from __future__ import annotations

import hashlib
import json
import re

from .cloud_client_identity import VerifiedHubContext, TimeReadiness


class HubDecisionConflict(ValueError):
    pass


_KEY = re.compile(r"^[\x21-\x7e]{1,256}$")
_KINDS = {
    "MORNING_ROUTINE_COMPLETED": "EXPECTED",
    "UNUSUAL_NIGHT_BATHROOM_ACTIVITY": "CONCERN",
    "UNUSUAL_NIGHT_COMMON_ACTIVITY": "CONCERN",
    "MISSING_MORNING_ACTIVITY": "CONCERN",
    "DAYTIME_INACTIVITY": "CONCERN",
    "DOOR_LEFT_OPEN": "CONCERN",
    "UNEXPECTED_DOOR_OPEN": "CONCERN",
    "POST_DOOR_INACTIVITY": "CONCERN",
    "DOOR_CLOSED_AFTER_LONG_OPEN": "EXPECTED",
}
_EVENT_DERIVED = {"MORNING_ROUTINE_COMPLETED", "UNUSUAL_NIGHT_BATHROOM_ACTIVITY",
                  "UNUSUAL_NIGHT_COMMON_ACTIVITY", "UNEXPECTED_DOOR_OPEN",
                  "DOOR_CLOSED_AFTER_LONG_OPEN", "DOOR_LEFT_OPEN"}


class HubRuleDecisionCommit:
    """Idempotent Hub decision commit using the existing SQLite authority DB."""

    def __init__(self, db, lock):
        self.db, self.lock = db, lock

    @staticmethod
    def _normalized(body):
        fields = {"decision_version", "decision_id", "kind", "tone", "reason",
                  "decided_at", "duration_seconds", "source_event_key", "resolves_prior_id"}
        if (not isinstance(body, dict) or set(body) != fields or
            type(body["decision_version"]) is not int or body["decision_version"] != 1):
            raise ValueError("invalid_hub_decision")
        decision_id, kind, tone = body["decision_id"], body["kind"], body["tone"]
        reason, source = body["reason"], body["source_event_key"]
        prior = body["resolves_prior_id"]
        if (not isinstance(decision_id, str) or not _KEY.fullmatch(decision_id) or
            not isinstance(kind, str) or kind not in _KINDS or tone != _KINDS[kind] or
            not isinstance(reason, str) or not 1 <= len(reason) <= 96 or
            not all(32 <= ord(char) <= 126 for char in reason) or
            type(body["decided_at"]) is not int or body["decided_at"] <= 0 or
            type(body["duration_seconds"]) is not int or
            not 0 <= body["duration_seconds"] <= 7 * 86400 or
            (source is not None and (not isinstance(source, str) or not _KEY.fullmatch(source))) or
            (kind in _EVENT_DERIVED and source is None) or
            (kind == "DOOR_CLOSED_AFTER_LONG_OPEN" and
             (not isinstance(prior, str) or not _KEY.fullmatch(prior) or
              decision_id != prior + ":clear")) or
            (kind != "DOOR_CLOSED_AFTER_LONG_OPEN" and prior is not None)):
            raise ValueError("invalid_hub_decision")
        return body

    def commit(self, home_id, body, context, received_at):
        body = self._normalized(body)
        prior = body["resolves_prior_id"]
        if (not isinstance(context, VerifiedHubContext) or
            not context.certificate_chain_verified or
            context.time_readiness is not TimeReadiness.TRUSTED or
            context.home_id != home_id or type(received_at) is not int or received_at <= 0):
            raise PermissionError("verified_hub_context_required")
        if body["decided_at"] > received_at + 300:
            raise ValueError("hub_decision_future_time")
        payload = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False)
        fingerprint = hashlib.sha256(payload.encode()).hexdigest()
        hub, epoch = context.permanent_hub_id, context.installation_epoch
        identity = (home_id, hub, epoch, body["decision_id"])
        with self.lock:
            if self.db.in_transaction:
                raise RuntimeError("hub_decision_requires_clean_transaction")
            self.db.execute("BEGIN IMMEDIATE")
            try:
                current = self.db.execute(
                    """SELECT 1 FROM hub_ownership_registry WHERE hub_device_id=?
                       AND identity_key_fingerprint=? AND home_id=?
                       AND installation_epoch=? AND state='ACTIVE'""",
                    (hub, context.ownership_fingerprint_sha256, home_id, epoch)).fetchone()
                if current is None:
                    raise PermissionError("current_hub_authority_required")
                previous = self.db.execute(
                    """SELECT payload_sha256 FROM hub_rule_decisions WHERE home_id=?
                       AND hub_device_id=? AND installation_epoch=? AND decision_id=?""",
                    identity).fetchone()
                if previous is not None:
                    if previous[0] != fingerprint:
                        raise HubDecisionConflict("hub_decision_identity_conflict")
                    self.db.commit()
                    return {"decision_id": body["decision_id"], "status": "COMMITTED", "duplicate": True}
                source_event_id = None
                if body["source_event_key"] is not None:
                    source = self.db.execute(
                        """SELECT c.event_id FROM events e JOIN durable_event_commits c
                           ON c.event_id=e.event_id WHERE e.home_id=? AND e.canonical_event_id=?
                           AND c.hub_device_id=? AND c.ownership_epoch=?""",
                        (home_id, body["source_event_key"], hub, epoch)).fetchone()
                    if source is None:
                        raise HubDecisionConflict("source_event_not_committed_under_current_owner")
                    source_event_id = source[0]
                self.db.execute(
                    """INSERT INTO hub_rule_decisions(home_id,hub_device_id,installation_epoch,
                       decision_id,payload_sha256,kind,tone,reason,decided_at,duration_seconds,
                       source_event_id,resolves_prior_id,committed_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (*identity, fingerprint, body["kind"], body["tone"], body["reason"],
                     body["decided_at"], body["duration_seconds"], source_event_id,
                     prior, received_at))
                if body["tone"] == "CONCERN":
                    stable = "hub-rule:" + hub + ":" + str(epoch) + ":" + body["decision_id"]
                    alert_id = "inc_" + hashlib.sha256((home_id + "\0" + stable).encode()).hexdigest()
                    cleared = self.db.execute(
                        """SELECT committed_at FROM hub_rule_decisions WHERE home_id=?
                           AND hub_device_id=? AND installation_epoch=? AND resolves_prior_id=?""",
                        (home_id, hub, epoch, body["decision_id"])).fetchone()
                    self.db.execute(
                        """INSERT INTO alerts(alert_id,home_id,stable_key,alert_type,severity,
                           state,source_event_id,created_at,is_test,details_json,resolved_at)
                           VALUES(?,?,?,?,?,?,?,?,1,?,?)""",
                        (alert_id, home_id, stable, body["kind"], "CONCERN",
                         "RESOLVED" if cleared else "OPEN", source_event_id,
                         received_at, payload,
                         cleared[0] if cleared else None))
                if prior is not None:
                    stable = "hub-rule:" + hub + ":" + str(epoch) + ":" + prior
                    self.db.execute(
                        """UPDATE alerts SET state='RESOLVED',resolved_at=?
                           WHERE home_id=? AND stable_key=? AND state!='RESOLVED'""",
                        (received_at, home_id, stable))
                self.db.commit()
            except BaseException:
                self.db.rollback()
                raise
        return {"decision_id": body["decision_id"], "status": "COMMITTED", "duplicate": False}

    def timeline(self, home_id, limit=100):
        with self.lock:
            rows = self.db.execute(
                """SELECT hub_device_id,installation_epoch,decision_id,kind,tone,
                   reason,decided_at,duration_seconds,committed_at
                   FROM hub_rule_decisions WHERE home_id=?
                   ORDER BY decided_at DESC,decision_id DESC LIMIT ?""",
                (home_id, min(max(limit, 0), 100))).fetchall()
        return [{"event_id": "hub-rule:" + row[0] + ":" + str(row[1]) + ":" + row[2],
                 "kind": row[3], "source_type": "HUB_RULE", "location": "",
                 "occurred_at": row[6], "hub_received_at": row[6],
                 "server_received_at": row[8],
                 "uncertainty_s": 0, "is_test": True,
                 "details": {"tone": row[4], "reason": row[5],
                             "duration_seconds": row[7]}, "decision_id": row[2],
                 "hub_device_id": row[0], "installation_epoch": row[1]}
                for row in rows]
