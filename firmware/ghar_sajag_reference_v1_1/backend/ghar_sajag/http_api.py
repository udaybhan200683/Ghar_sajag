from __future__ import annotations

from .logging_config import traced
import json
import re
from typing import Callable, Iterable

from .model import CloudEvent, Resident
from .service import GharSajagService


class JsonApi:
    """Small WSGI adapter for local integration tests.

    `X-Actor-Id` is a development adapter only. Production must replace it with
    verified OIDC claims at the trust boundary.
    """

    def __init__(self, service: GharSajagService | None = None, now: Callable[[], int] | None = None) -> None:
        import time

        self.service = service or GharSajagService()
        self.now = now or (lambda: int(time.time()))

    def __call__(self, environ: dict, start_response: Callable) -> Iterable[bytes]:
        try:
            method = environ.get("REQUEST_METHOD", "GET")
            path = environ.get("PATH_INFO", "/")
            actor = environ.get("HTTP_X_ACTOR_ID", "")
            body = self._body(environ)
            status, payload = self.dispatch(method, path, actor, body)
        except PermissionError as error:
            status, payload = "403 Forbidden", {"error": str(error)}
        except KeyError as error:
            status, payload = "404 Not Found", {"error": str(error)}
        except (ValueError, json.JSONDecodeError) as error:
            status, payload = "400 Bad Request", {"error": str(error)}
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        start_response(status, [("content-type", "application/json"), ("content-length", str(len(encoded)))])
        return [encoded]

    @traced("B11")

    def dispatch(self, method: str, path: str, actor: str, body: dict) -> tuple[str, dict]:
        at = self.now()
        if method == "GET" and path == "/healthz":
            return "200 OK", {"status": "ok"}
        if method == "POST" and path == "/v1/homes":
            residents = [Resident(item["resident_id"], item["display_name"], bool(item["consent_active"]), at) for item in body["residents"]]
            home = self.service.homes.create(body["home_id"], body["display_name"], body["timezone"], body.get("language", "en-IN"), actor, residents, at)
            return "201 Created", {"home_id": home.home_id, "version": home.version}
        match = re.fullmatch(r"/v1/homes/([^/]+)/events", path)
        if method == "POST" and match:
            home_id = match.group(1)
            event = CloudEvent(home_id, body["event_id"], body["kind"], body.get("location", ""), int(body["occurred_at"]), int(body["hub_received_at"]), at, int(body.get("uncertainty_s", 0)), bool(body.get("is_test", False)), body.get("payload", {}))
            _, duplicate = self.service.accept_hub_event(event)
            return ("200 OK" if duplicate else "202 Accepted"), {"event_id": event.event_id, "duplicate": duplicate, "commit": "DURABLE"}
        match = re.fullmatch(r"/v1/homes/([^/]+)/snapshot", path)
        if method == "GET" and match:
            return "200 OK", self.service.queries.snapshot(match.group(1), actor, at)
        match = re.fullmatch(r"/v1/homes/([^/]+)/incidents/([^/]+)/(claim|acknowledge|resolve)", path)
        if method == "POST" and match:
            home_id, incident_id, action = match.groups()
            incident = getattr(self.service.incidents, action)(home_id, incident_id, actor, at)
            if action in {"acknowledge", "resolve"}:
                self.service.notifications.human_acknowledged(incident_id)
            return "200 OK", {"incident_id": incident.incident_id, "state": incident.state.value, "owner_id": incident.owner_id}
        return "404 Not Found", {"error": "route_not_found"}

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
