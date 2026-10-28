# Ghar Sajag traceability edition 2.0 | source release 1.4.2
# @module B07 Read models/API
# @requirements F05, F06, F09, F11, F12, F14, E04
# Requirement links identify design responsibility, not completed acceptance coverage.
# See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
# QueryService builds a caregiver projection from authoritative backend records and checks household
# access. The projection may be stale even when the backend is healthy; include source ages. The demo HTTP
# adapter is a local development adapter and is not equivalent to the planned authenticated production
# API.

from __future__ import annotations

from .logging_config import traced
import json
import re
import sqlite3
from typing import Callable, Iterable
from urllib.parse import parse_qs

from .model import CloudEvent, Resident
from .service import GharSajagService
from .durable_commit import DurableEventCommit, EventCommitConflict
from .cloud_client_identity import VerifiedHubContext
from .node_health_status import NodeHealthStatusStore
from .hub_rule_decisions import HubDecisionConflict, HubRuleDecisionCommit
from .configuration_repository import (
    ConfigurationConflict, ConfigurationDenied, PostgresConfigurationRepository,
    HouseholdConfigurationSnapshot,
)
from .human_authentication import AuthenticationDenied, HumanAuthenticationBoundary
from .diagnostic_authorization import ActorSession


class ConfigurationIntegrationUnavailable(RuntimeError):
    """A trusted production adapter was not installed for this request."""


class JsonApi:
    """Small WSGI adapter for local integration tests.

    `X-Actor-Id` is a development adapter only. Production must replace it with
    verified OIDC claims at the trust boundary.
    """

    def __init__(self, service: GharSajagService | None = None, now: Callable[[], int] | None = None,
                 durable_events: DurableEventCommit | None = None,
                 authorize_hub: Callable[[dict, str, dict], bool] | None = None,
                 hub_ownership_registry=None,
                 node_health_status: NodeHealthStatusStore | None = None,
                 hub_rule_decisions: HubRuleDecisionCommit | None = None,
                 configuration_repository: PostgresConfigurationRepository | None = None,
                 human_authentication: HumanAuthenticationBoundary | None = None,
                 caregiver_credential_from_request: Callable[[dict], object] | None = None,
                 verified_hub_context_from_request: Callable[[dict], VerifiedHubContext | None] | None = None) -> None:
        import time

        self.service = service or GharSajagService()
        self.now = now or (lambda: int(time.time()))
        self.durable_events = durable_events
        self.authorize_hub = authorize_hub
        self.hub_ownership_registry = hub_ownership_registry
        self.node_health_status = node_health_status
        self.hub_rule_decisions = hub_rule_decisions
        self.configuration_repository = configuration_repository
        self.human_authentication = human_authentication
        self.caregiver_credential_from_request = caregiver_credential_from_request
        self.verified_hub_context_from_request = verified_hub_context_from_request

    def __call__(self, environ: dict, start_response: Callable) -> Iterable[bytes]:
        try:
            method = environ.get("REQUEST_METHOD", "GET")
            path = environ.get("PATH_INFO", "/")
            actor = environ.get("HTTP_X_ACTOR_ID", "")
            body = self._body(environ)
            query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
            status, payload = self.dispatch(method, path, actor, body, query, environ)
        except AuthenticationDenied:
            status, payload = "401 Unauthorized", {"error": "human_not_authenticated"}
        except ConfigurationIntegrationUnavailable as error:
            status, payload = "503 Service Unavailable", {"error": str(error)}
        except ConfigurationDenied as error:
            status, payload = "403 Forbidden", {"error": str(error)}
        except PermissionError as error:
            status, payload = "403 Forbidden", {"error": str(error)}
        except (EventCommitConflict, HubDecisionConflict, ConfigurationConflict) as error:
            status, payload = "409 Conflict", {"error": str(error)}
        except sqlite3.Error:
            status, payload = "503 Service Unavailable", {"error": "event_commit_unavailable"}
        except KeyError as error:
            status, payload = "404 Not Found", {"error": str(error)}
        except (ValueError, json.JSONDecodeError) as error:
            status, payload = "400 Bad Request", {"error": str(error)}
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        start_response(status, [("content-type", "application/json"), ("content-length", str(len(encoded)))])
        return [encoded]

    @traced("B11")

    def dispatch(self, method: str, path: str, actor: str, body: dict, query: dict | None = None,
                 request_context: dict | None = None) -> tuple[str, dict]:
        with self.service.lock:
            return self._dispatch(method, path, actor, body, query, request_context)

    def _dispatch(self, method: str, path: str, actor: str, body: dict, query: dict | None = None,
                  request_context: dict | None = None) -> tuple[str, dict]:
        at = self.now()
        query = query or {}
        if method == "GET" and path == "/healthz":
            return "200 OK", {"status": "ok"}
        if method == "POST" and path == "/v1/homes":
            residents = [Resident(item["resident_id"], item["display_name"], bool(item["consent_active"]), at) for item in body["residents"]]
            home = self.service.homes.create(body["home_id"], body["display_name"], body["timezone"], body.get("language", "en-IN"), actor, residents, at)
            return "201 Created", {"home_id": home.home_id, "version": home.version}
        match = re.fullmatch(r"/v1/homes/([^/]+)/hub-rule-decisions", path)
        if method == "POST" and match:
            if self.hub_rule_decisions is None:
                return "503 Service Unavailable", {"error": "hub_rule_decision_commit_unavailable"}
            result = self.hub_rule_decisions.commit(match.group(1), body, request_context, at)
            return ("200 OK" if result["duplicate"] else "201 Created"), result
        match = re.fullmatch(r"/v1/homes/([^/]+)/events", path)
        if method == "POST" and match:
            home_id = match.group(1)
            if "event_key" in body or self.durable_events is not None:
                if self.durable_events is None:
                    return "503 Service Unavailable", {"error": "durable_event_store_unavailable"}
                context = request_context or {}
                if isinstance(context, VerifiedHubContext):
                    context = context.internal_event_context()
                # Trusted middleware sets this internal WSGI key; it must never
                # be copied from a client-controlled HTTP header.
                if not isinstance(context.get("gs.verified_hub"), str):
                    raise PermissionError("hub_not_authorized")
                if self.hub_ownership_registry is not None:
                    result = self.durable_events.commit(
                        home_id, body, at,
                        authorization_guard=lambda db, requested_home, request_body:
                            self.hub_ownership_registry.authorize_cloud_event(
                                db, context, requested_home, request_body),
                    )
                else:
                    if (self.authorize_hub is None or
                        not self.authorize_hub(context, home_id, body.get("event_key"))):
                        raise PermissionError("hub_not_authorized")
                    result = self.durable_events.commit(home_id, body, at)
                return ("200 OK" if result["duplicate"] else "201 Created"), result
            event = CloudEvent(home_id, body["event_id"], body["kind"], body.get("location", ""), int(body["occurred_at"]), int(body["hub_received_at"]), at, int(body.get("uncertainty_s", 0)), bool(body.get("is_test", False)), body.get("payload", {}))
            _, duplicate = self.service.accept_hub_event(event)
            return ("200 OK" if duplicate else "202 Accepted"), {"event_id": event.event_id, "duplicate": duplicate, "commit": "DURABLE_MODEL"}
        match = re.fullmatch(r"/v1/homes/([^/]+)/node-health", path)
        if method == "POST" and match:
            if self.node_health_status is None:
                return "503 Service Unavailable", {"error": "node_health_store_unavailable"}
            if not isinstance(request_context, VerifiedHubContext):
                raise PermissionError("verified_hub_context_required")
            accepted = self.node_health_status.ingest(
                request_context, match.group(1), body, at)
            return "200 OK", {"status": "ACCEPTED", **accepted}
        match = re.fullmatch(r"/v1/homes/([^/]+)/config(?:/(desired|applied))?", path)
        if match:
            home_id, operation = match.groups()
            repository = self.configuration_repository
            if repository is not None:
                if operation == "desired" and method == "GET":
                    context = self._verified_hub_context(request_context)
                    snapshot = repository.get_for_hub(context=context, home_id=home_id, at=at)
                    return "200 OK", self._desired_configuration(snapshot)
                if operation == "applied" and method == "POST":
                    if set(body) != {"version"} or type(body["version"]) is not int:
                        raise ValueError("invalid_applied_configuration_ack")
                    context = self._verified_hub_context(request_context)
                    snapshot = repository.record_applied(context=context, home_id=home_id,
                                                         version=body["version"], at=at)
                    return "200 OK", {
                        "home_id": snapshot.home_id,
                        "desired_version": snapshot.desired_version,
                        "desired_status": snapshot.desired_status,
                        "applied_version": snapshot.applied_version,
                    }
                if operation is not None:
                    return "405 Method Not Allowed", {"error": "method_not_allowed"}
                if method == "POST":
                    if set(body) != {"expected_version", "config"} or type(body["expected_version"]) is not int:
                        raise ValueError("invalid_configuration_publish_request")
                    session = self._caregiver_session(request_context)
                    snapshot = repository.publish_desired(
                        actor=session, home_id=home_id, config=body["config"],
                        expected_version=body["expected_version"], at=at)
                    return "202 Accepted", self._configuration_snapshot(snapshot)
                if method == "GET":
                    session = self._caregiver_session(request_context)
                    snapshot = repository.get_for_caregiver(actor=session, home_id=home_id, at=at)
                    return "200 OK", self._configuration_snapshot(snapshot)
                return "405 Method Not Allowed", {"error": "method_not_allowed"}

            # Keep the existing explicit in-memory development adapter intact.
            # Production/durable compositions use the repository branch above.
            if operation is not None:
                return "503 Service Unavailable", {"error": "household_configuration_repository_unavailable"}
            if method == "POST":
                desired = self.service.fleet.publish_config(home_id, actor, body, at)
                return "202 Accepted", {"home_id": home_id, "version": desired.version, "applied_version": desired.applied_version}
            if method == "GET":
                self.service.identity.require(home_id, actor, "read", at)
                desired = self.service.store.configs.get(home_id)
                if desired is None:
                    return "200 OK", {"home_id": home_id, "version": 0, "applied_version": None, "config": None}
                return "200 OK", {"home_id": home_id, "version": desired.version, "applied_version": desired.applied_version, "config": desired.body}
            return "405 Method Not Allowed", {"error": "method_not_allowed"}
        match = re.fullmatch(r"/v1/homes/([^/]+)/snapshot", path)
        if method == "GET" and match:
            return "200 OK", self.service.queries.snapshot(match.group(1), actor, at)
        match = re.fullmatch(r"/v1/homes/([^/]+)/reports", path)
        if method == "GET" and match:
            if set(query) != {"period"} or len(query.get("period", [])) != 1:
                raise ValueError("invalid_report_request")
            return "200 OK", self.service.queries.report(match.group(1), actor, at, query["period"][0])
        match = re.fullmatch(r"/v1/homes/([^/]+)/incidents/([^/]+)/(claim|acknowledge|resolve)", path)
        if method == "POST" and match:
            home_id, incident_id, action = match.groups()
            incident = getattr(self.service.incidents, action)(home_id, incident_id, actor, at)
            if action in {"acknowledge", "resolve"}:
                self.service.notifications.human_acknowledged(incident_id)
            return "200 OK", {"incident_id": incident.incident_id, "state": incident.state.value, "owner_id": incident.owner_id}
        return "404 Not Found", {"error": "route_not_found"}

    def _caregiver_session(self, request_context: dict | None) -> ActorSession:
        if (self.configuration_repository is None or self.human_authentication is None or
                not callable(self.caregiver_credential_from_request)):
            raise ConfigurationIntegrationUnavailable(
                "caregiver_configuration_authentication_unavailable")
        credential = self.caregiver_credential_from_request(request_context or {})
        return self.human_authentication.authenticate(credential)

    def _verified_hub_context(self, request_context: dict | None) -> VerifiedHubContext:
        if (self.configuration_repository is None or
                not callable(self.verified_hub_context_from_request)):
            raise ConfigurationIntegrationUnavailable(
                "hub_configuration_authentication_unavailable")
        context = self.verified_hub_context_from_request(request_context or {})
        if type(context) is not VerifiedHubContext:
            raise PermissionError("verified_hub_context_required")
        return context

    @staticmethod
    def _configuration_snapshot(snapshot: HouseholdConfigurationSnapshot) -> dict:
        return {
            "home_id": snapshot.home_id,
            "desired_version": snapshot.desired_version,
            "desired_status": snapshot.desired_status,
            "desired_config": snapshot.desired_config,
            "applied_version": snapshot.applied_version,
            "applied_config": snapshot.applied_config,
            "schema_version": snapshot.schema_version,
        }

    @staticmethod
    def _desired_configuration(snapshot: HouseholdConfigurationSnapshot) -> dict:
        # The server-owned path/version/schema envelope is distinct from policy
        # content. An empty desired state is a valid no-op, never a policy reset.
        return {
            "home_id": snapshot.home_id,
            "version": snapshot.desired_version,
            "schema": snapshot.schema_version or PostgresConfigurationRepository.SCHEMA_VERSION,
            "status": snapshot.desired_status,
            "config": snapshot.desired_config,
            "applied_version": snapshot.applied_version,
        }

    @staticmethod
    @traced("B11")
    def _body(environ: dict) -> dict:
        length = int(environ.get("CONTENT_LENGTH") or 0)
        if length <= 0:
            return {}
        return json.loads(environ["wsgi.input"].read(length).decode("utf-8"))


@traced("B11")


def main() -> None:
    from wsgiref.simple_server import make_server

    with make_server("127.0.0.1", 8080, JsonApi()) as server:
        print("Ghar Sajag development API listening on http://127.0.0.1:8080")
        server.serve_forever()


if __name__ == "__main__":
    main()
