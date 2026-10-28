"""Read/action projection of committed product data for an authenticated app.

The caller must establish a current human session and Home membership before
calling. This adapter cannot ingest events, create authority or run scenarios.
"""
from dataclasses import asdict
from .model import Home, HomeMode, Membership, Role


class CaregiverProductView:
    def __init__(self, service, *, source, decision_reader=None,
                 session_authority_db=None, bind_test_only_session=False,
                 configuration_repository=None):
        self.service, self.source = service, source
        self.decision_reader = decision_reader
        self.session_authority_db = session_authority_db
        self.bind_test_only_session = bind_test_only_session
        self.configuration_repository = configuration_repository

    def _bind_verified_test_session(self, session, home, now):
        """Bind an already authenticated Lite TEST_ONLY session to the domain view.

        LiteApi performs cookie, account, membership, ownership-epoch and session
        expiry checks before calling this projection. This bridge independently
        checks the scoped TEST_ONLY claim and requires the Home to exist in the
        durable GS-148 database. It never accepts identity fields from the URL
        or request body as authority.
        """
        if self.session_authority_db is None:
            raise PermissionError("test_only_caregiver_authority_unavailable")
        keys = set(session.keys()) if callable(getattr(session, "keys", None)) else set()
        value = lambda name: session[name] if name in keys else session.get(name)
        active_test_flag = value("test_only")
        member_active = value("member_active")
        actor = value("account_id")
        role = value("role")
        if (not (active_test_flag is True or type(active_test_flag) is int and active_test_flag == 1) or
                value("home_id") != home or
                not isinstance(home, str) or not home.startswith("gs177-test-") or
                not isinstance(actor, str) or not actor or
                role not in {"ADMIN", "CAREGIVER"} or
                not (member_active is True or type(member_active) is int and member_active == 1) or
                type(value("ownership_epoch")) is not int or
                value("ownership_epoch") != value("home_epoch") or
                type(value("expires_at")) is not int or value("expires_at") <= now):
            raise PermissionError("current_test_only_home_membership_required")

        row = self.session_authority_db.execute(
            """SELECT home_id,display_name,timezone,language,mode,consent_state
                 FROM households WHERE home_id=?""", (home,)).fetchone()
        if row is None:
            # A signed-in simulation Home may predate Hub enrollment. Returning
            # None keeps its separate simulator view; it cannot imply monitoring.
            return False
        if row["consent_state"] != "ACTIVE":
            raise PermissionError("active_home_consent_required")
        roster_member = self.session_authority_db.execute(
            """SELECT role FROM household_caregivers WHERE home_id=?
                 AND caregiver_id=? AND active=1""", (home, actor)).fetchone()
        if roster_member is None or roster_member["role"] not in {
                "OWNER", "PRIMARY", "BACKUP", "FAMILY"}:
            raise PermissionError("current_durable_home_membership_required")
        owner = self.session_authority_db.execute(
            """SELECT caregiver_id FROM household_caregivers WHERE home_id=?
                 AND active=1 AND role IN ('OWNER','PRIMARY')
                 ORDER BY CASE role WHEN 'OWNER' THEN 0 ELSE 1 END LIMIT 1""", (home,)).fetchone()
        if owner is None:
            raise PermissionError("current_home_owner_required")
        try:
            mode = HomeMode(row["mode"])
        except ValueError as error:
            raise PermissionError("valid_home_mode_required") from error
        self.service.store.homes[home] = Home(
            home_id=home, display_name=row["display_name"], timezone=row["timezone"],
            language=row["language"], owner_id=owner["caregiver_id"], mode=mode)
        # Effective privilege is the intersection of the current Lite session
        # role and the durable caregiver roster. A TEST_ONLY Lite ADMIN cannot
        # become the domain owner unless this same account is a current OWNER.
        domain_role = (Role.OWNER if role == "ADMIN" and roster_member["role"] == "OWNER"
                       else Role.CAREGIVER)
        self.service.store.memberships[(home, actor)] = Membership(
            home, actor, domain_role, True, session["expires_at"])
        return True

    def _timeline(self, home, actor, now):
        events = self.service.queries.timeline(home, actor, now)
        if self.decision_reader is not None:
            events.extend(self.decision_reader.timeline(home))
            events.sort(key=lambda item: (item["occurred_at"], item["event_id"]), reverse=True)
        return events[:100]

    def dispatch(self, session, home, sub, method, body, now):
        actor = session["account_id"]
        if self.bind_test_only_session:
            if not self._bind_verified_test_session(session, home, now):
                return None
        else:
            self.service.identity.require(home, actor, "read", now)
        if sub == "routine-config":
            repository = self.configuration_repository
            if repository is None:
                raise RuntimeError("test_only_household_configuration_unavailable")
            from .diagnostic_authorization import ActorSession
            current_actor = ActorSession(
                actor, session["session_id"], "GS179_TEST_ONLY_LITE",
                session["expires_at"])
            if method == "GET":
                return asdict(repository.get_for_caregiver(
                    actor=current_actor, home_id=home, at=now))
            if method == "POST":
                if (set(body) != {"expected_version", "config"} or
                        type(body.get("expected_version")) is not int):
                    raise ValueError("invalid_configuration_publish_request")
                return ("202 Accepted", asdict(repository.publish_desired(
                    actor=current_actor, home_id=home, config=body["config"],
                    expected_version=body["expected_version"], at=now)))
            return None
        snapshot = self.service.queries.snapshot(home, actor, now)
        base = {"home_id": home, "test_only": bool(session["test_only"]),
                "source": self.source, "physical_status": "NOT_RUN",
                "physical_status_reason": "TEST_ONLY_PHYSICAL_NOT_RUN",
                "physical_data_contract": "GS-148_CLOUDSYNC_V2"}
        if method == "GET" and sub == "overview":
            last_hub = snapshot.get("last_hub_at")
            age = None if last_hub is None else now - int(last_hub)
            freshness = ("UNKNOWN" if age is None or age < 0 else
                         "CURRENT" if age <= self.service.queries.hub_lease_seconds else "STALE")
            statuses = [item["status"] for item in snapshot["node_health"]]
            coverages = [item["coverage"] for item in snapshot["node_health"]]
            if freshness != "CURRENT" or not statuses:
                monitoring = "UNKNOWN"
            elif any(state != "ONLINE" for state in statuses) or any(value != "COVERED" for value in coverages):
                monitoring = "UNKNOWN"
            else:
                monitoring = "COVERED"
            return {**base, **snapshot, "source_freshness": freshness,
                    "monitoring": monitoring,
                    "backend_data_retrieved_at": now, "recent_events": self._timeline(home, actor, now)}
        if method == "GET" and sub == "devices":
            return {**base, "devices": snapshot["node_health"]}
        if method == "GET" and sub == "incidents":
            return {**base, "incidents": [{**asdict(i), "state": i.state.value,
                    "severity": "URGENT" if i.kind == "CALL_FAMILY" else "CONCERN"}
                for i in self.service.store.incidents.values() if i.home_id == home]}
        if method == "GET" and sub == "reports":
            return {**base, "event_count": sum(snapshot["event_counts"].values()),
                    "event_counts": snapshot["event_counts"], "recent_events": self._timeline(home, actor, now)}
        if method == "GET" and sub == "routines":
            decisions = (self.decision_reader.timeline(home)
                         if self.decision_reader is not None else [])
            coverage = ("COVERED" if snapshot["hub_reachable"] and snapshot["node_health"] and
                        all(node["status"] == "ONLINE" and node["coverage"] == "COVERED"
                            for node in snapshot["node_health"]) else "UNKNOWN")
            return {**base, "learning_status": "NOT_ENABLED",
                    "decisions": decisions, "runs": [],
                    "observation_coverage": coverage}
        parts = sub.split("/")
        if (method == "POST" and len(parts) == 3 and parts[0] == "incidents"
                and parts[2] in {"claim", "acknowledge", "resolve"}):
            if body:
                raise ValueError("incident_action_accepts_no_parameters")
            incident = getattr(self.service.incidents, parts[2])(home, parts[1], actor, now)
            return {"incident_id": incident.incident_id, "state": incident.state.value, "owner_id": incident.owner_id}
        return None
