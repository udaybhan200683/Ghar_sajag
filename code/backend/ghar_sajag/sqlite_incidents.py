"""Durable alert read/action adapter reusing the canonical incident workflow."""
from collections.abc import MutableMapping
import uuid

from .incidents import IncidentService
from .model import Incident, IncidentState


class SQLiteIncidentMap(MutableMapping):
    def __init__(self, db, lock):
        self.db, self.lock = db, lock

    @staticmethod
    def _incident(row):
        return Incident(row["alert_id"], row["home_id"], row["stable_key"], row["alert_type"],
                        row["created_at"], state=IncidentState(row["state"]),
                        owner_id=row["owner_caregiver_id"], owner_lease_until=row["owner_lease_until"],
                        acknowledged_at=row["acknowledged_at"], resolved_at=row["resolved_at"],
                        is_test=bool(row["is_test"]))

    def __getitem__(self, key):
        with self.lock:
            row = self.db.execute("SELECT * FROM alerts WHERE alert_id=?", (key,)).fetchone()
            if row is None:
                raise KeyError(key)
            return self._incident(row)

    def __setitem__(self, key, incident):
        if key != incident.incident_id:
            raise ValueError("incident_identity_mismatch")
        with self.lock:
            self.db.execute("""INSERT INTO alerts(alert_id,home_id,stable_key,alert_type,severity,state,
                created_at,is_test,owner_caregiver_id,owner_lease_until,acknowledged_at,resolved_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(alert_id) DO UPDATE SET
                state=excluded.state,owner_caregiver_id=excluded.owner_caregiver_id,
                owner_lease_until=excluded.owner_lease_until,acknowledged_at=excluded.acknowledged_at,
                resolved_at=excluded.resolved_at""", (key, incident.home_id, incident.stable_key,
                incident.kind, "URGENT" if incident.kind == "CALL_FAMILY" else "CONCERN",
                incident.state.value, incident.created_at, int(incident.is_test), incident.owner_id,
                incident.owner_lease_until, incident.acknowledged_at, incident.resolved_at))

    def __delitem__(self, key):
        raise TypeError("incident_history_cannot_be_deleted")

    def __iter__(self):
        with self.lock:
            return iter([row[0] for row in self.db.execute("SELECT alert_id FROM alerts ORDER BY created_at,alert_id")])

    def __len__(self):
        with self.lock:
            return self.db.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]


class SQLiteIncidentKeys(MutableMapping):
    def __init__(self, incidents):
        self.incidents = incidents

    def __getitem__(self, key):
        with self.incidents.lock:
            row = self.incidents.db.execute("SELECT alert_id FROM alerts WHERE home_id=? AND stable_key=?", key).fetchone()
        if row is None:
            raise KeyError(key)
        return row[0]

    def __setitem__(self, key, value):
        if self[key] != value:
            raise ValueError("incident_stable_key_conflict")

    def __delitem__(self, key):
        raise TypeError("incident_history_cannot_be_deleted")

    def __iter__(self):
        with self.incidents.lock:
            return iter([tuple(row) for row in self.incidents.db.execute("SELECT home_id,stable_key FROM alerts")])

    def __len__(self):
        return len(self.incidents)


class SQLiteIncidentService(IncidentService):
    """Serialize existing claim/ack/resolve semantics and persist before return."""
    def __init__(self, store, identity, db, lock):
        super().__init__(store, identity)
        self.db, self.lock = db, lock
        self._action_depth = 0

    def _perform(self, action, home, incident_id, actor, at, callback):
        with self.lock:
            # resolve invokes the canonical acknowledge method within its own
            # transaction. Only the outer operation commits and records it.
            if self.db.in_transaction and self._action_depth:
                return callback()
            if self.db.in_transaction:
                raise RuntimeError("incident_action_requires_clean_transaction")
            audit_size = len(self.store.audit)
            self.db.execute("BEGIN IMMEDIATE")
            self._action_depth += 1
            try:
                result = callback()
                self.store.incidents[incident_id] = result
                if action in {"ACKNOWLEDGE", "RESOLVE"}:
                    self.db.execute("""UPDATE notification_jobs SET state=CASE
                        WHEN state='PROVIDER_ACCEPTED' THEN 'HUMAN_ACKED' ELSE 'CANCELLED' END
                        WHERE alert_id=? AND state IN ('CREATED','PROVIDER_ACCEPTED')""", (incident_id,))
                self.db.execute("""INSERT INTO acknowledgements(acknowledgement_id,alert_id,
                    caregiver_id,action,occurred_at) VALUES(?,?,?,?,?)""",
                    ("ack_" + uuid.uuid4().hex, incident_id, actor, action, at))
                self.db.commit()
                return result
            except BaseException:
                self.db.rollback()
                del self.store.audit[audit_size:]
                raise
            finally:
                self._action_depth -= 1

    def claim(self, home, incident_id, actor, at, lease_seconds=300):
        return self._perform("CLAIM", home, incident_id, actor, at,
            lambda: super(SQLiteIncidentService, self).claim(home, incident_id, actor, at, lease_seconds))

    def acknowledge(self, home, incident_id, actor, at):
        return self._perform("ACKNOWLEDGE", home, incident_id, actor, at,
            lambda: super(SQLiteIncidentService, self).acknowledge(home, incident_id, actor, at))

    def resolve(self, home, incident_id, actor, at):
        return self._perform("RESOLVE", home, incident_id, actor, at,
            lambda: super(SQLiteIncidentService, self).resolve(home, incident_id, actor, at))
