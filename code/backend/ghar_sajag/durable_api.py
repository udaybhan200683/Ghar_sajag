"""Durable composition for the existing authenticated Hub event API seam.

This module wires the existing relational transaction and durable event query map
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
from .sqlite_incidents import SQLiteIncidentMap, SQLiteIncidentKeys, SQLiteIncidentService
from .hub_rule_decisions import HubRuleDecisionCommit


@dataclass
class DurableEventApi:
    """A JsonApi backed by one durable relational event connection."""

    api: JsonApi
    db: object

    def close(self) -> None:
        self.db.close()


def open_durable_event_api(
    service: GharSajagService,
    database_path: str | Path,
    authorize_hub: Callable[[dict, str, dict], bool] | None = None,
    now: Callable[[], int] | None = None,
    require_registered_ownership: bool = False,
    enable_test_hub_rule_decisions: bool = False,
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
        service.store.incidents = SQLiteIncidentMap(db, service.lock)
        service.store.incident_keys = SQLiteIncidentKeys(service.store.incidents)
        service.incidents = SQLiteIncidentService(service.store, service.identity, db, service.lock)
        committer = DurableEventCommit(db, service.lock)
        ownership_registry = HubOwnershipRegistry(db, service.lock) if require_registered_ownership else None
        node_health_status = NodeHealthStatusStore(db)
        service.queries.node_health_status = node_health_status
        hub_rule_decisions = (HubRuleDecisionCommit(db, service.lock)
                              if enable_test_hub_rule_decisions and require_registered_ownership
                              else None)
        return DurableEventApi(
            JsonApi(service=service, now=now, durable_events=committer,
                    authorize_hub=authorize_hub, hub_ownership_registry=ownership_registry,
                    node_health_status=node_health_status,
                    hub_rule_decisions=hub_rule_decisions),
            db,
        )
    except BaseException:
        db.close()
        raise


def open_postgres_durable_event_api(
    service: GharSajagService,
    dsn: str,
    authorize_hub: Callable[[dict, str, dict], bool] | None = None,
    now: Callable[[], int] | None = None,
    require_registered_ownership: bool = True,
    enable_test_hub_rule_decisions: bool = True,
    *,
    allow_local_unencrypted: bool = False,
    enable_household_configuration: bool = False,
    human_authentication=None,
    caregiver_credential_from_request=None,
    verified_hub_context_from_request=None,
    authorize_caregiver_settings=None,
    authorize_hub_configuration=None,
) -> DurableEventApi:
    """Compose the existing Hub event and caregiver read paths on PostgreSQL.

    The TLS/identity boundary must still create the typed Hub context. A remote
    DSN must use verified TLS; local plaintext is opt-in for isolated tests.
    """
    from .postgres_database import connect_postgres, initialize_postgres
    from .configuration_repository import PostgresConfigurationRepository

    if not callable(authorize_hub) and not require_registered_ownership:
        raise ValueError("trusted_hub_authorizer_required")
    db = connect_postgres(dsn, allow_local_unencrypted=allow_local_unencrypted)
    try:
        initialize_postgres(db)
        configuration_repository = None
        if enable_household_configuration:
            if not callable(authorize_hub_configuration):
                raise ValueError("trusted_hub_configuration_adapter_required")
            # The repository is shared by independently authenticated
            # composition roots. A Hub-only mTLS listener can install only its
            # Hub adapter; caregiver routes remain fail-closed until that
            # composition supplies its own human-session boundary.
            configuration_repository = PostgresConfigurationRepository(
                db, authorize_caregiver_settings=authorize_caregiver_settings,
                authorize_hub_configuration=authorize_hub_configuration,
                lock=service.lock)
        event_map = SQLiteEventMap(db, service.lock)
        service.store.events = event_map
        service.store.incidents = SQLiteIncidentMap(db, service.lock)
        service.store.incident_keys = SQLiteIncidentKeys(service.store.incidents)
        service.incidents = SQLiteIncidentService(service.store, service.identity, db, service.lock)
        committer = DurableEventCommit(db, service.lock)
        ownership_registry = HubOwnershipRegistry(db, service.lock) if require_registered_ownership else None
        node_health_status = NodeHealthStatusStore(db)
        service.queries.node_health_status = node_health_status
        hub_rule_decisions = (HubRuleDecisionCommit(db, service.lock)
                              if enable_test_hub_rule_decisions and require_registered_ownership
                              else None)
        return DurableEventApi(
            JsonApi(service=service, now=now, durable_events=committer,
                    authorize_hub=authorize_hub, hub_ownership_registry=ownership_registry,
                    node_health_status=node_health_status,
                    hub_rule_decisions=hub_rule_decisions,
                    configuration_repository=configuration_repository,
                    human_authentication=human_authentication,
                    caregiver_credential_from_request=caregiver_credential_from_request,
                    verified_hub_context_from_request=verified_hub_context_from_request),
            db,
        )
    except BaseException:
        db.close()
        raise
