"""File-backed composition for the existing authenticated Hub event API seam.

This module wires the implemented SQLite transaction and durable event query map
into ``JsonApi``. It deliberately does not authenticate Hub requests: the server
deployment must provide trusted middleware that sets ``gs.verified_hub`` and an
authorizer bound to its enrollment registry. The local development ``main`` entry
point remains a separate, in-memory adapter.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Callable

from .database import initialize_sqlite
from .durable_commit import DurableEventCommit
from .http_api import JsonApi
from .service import GharSajagService
from .sqlite_events import SQLiteEventMap
from .ownership_registry import HubOwnershipRegistry
from .node_health_status import NodeHealthStatusStore


@dataclass
class DurableEventApi:
    """A JsonApi backed by one durable SQLite event connection."""

    api: JsonApi
    db: sqlite3.Connection

    def close(self) -> None:
        self.db.close()


def open_durable_event_api(
    service: GharSajagService,
    database_path: str | Path,
    authorize_hub: Callable[[dict, str, dict], bool] | None = None,
    now: Callable[[], int] | None = None,
    require_registered_ownership: bool = False,
) -> DurableEventApi:
    """Compose existing migrations, event projection and durable commit logic.

    The caller must provide a file-backed database and an authorization callback
    whose input context was populated by a trusted server-side authenticator.
    No HTTP header is promoted to a trusted identity here.
    """
    if not callable(authorize_hub) and not require_registered_ownership:
        raise ValueError("trusted_hub_authorizer_required")
    path = Path(database_path)
    if str(database_path) == ":memory:":
        raise ValueError("durable_event_api_requires_file_database")
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    try:
        db.row_factory = sqlite3.Row
        initialize_sqlite(db)
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        if db.in_transaction:
            raise ValueError("durable_event_api_requires_clean_database")
        event_map = SQLiteEventMap(db, service.lock)
        # QueryService uses the event mapping interface, so a committed Hub event
        # becomes visible through the existing caregiver projection after commit
        # and remains visible after this composition is reopened.
        service.store.events = event_map
        committer = DurableEventCommit(db, service.lock)
        ownership_registry = HubOwnershipRegistry(db, service.lock) if require_registered_ownership else None
        node_health_status = NodeHealthStatusStore(db)
        service.queries.node_health_status = node_health_status
        return DurableEventApi(
            JsonApi(service=service, now=now, durable_events=committer,
                    authorize_hub=authorize_hub, hub_ownership_registry=ownership_registry,
                    node_health_status=node_health_status),
            db,
        )
    except BaseException:
        db.close()
        raise
