"""Relational P0 persistence schema adapter.

The deterministic simulator keeps its in-memory store so scenario tests stay fast and reproducible. This
module owns the concrete persistent schema contract. SQLite validates the model on the host; a production
PostgreSQL adapter must preserve the identities, foreign keys, uniqueness and state semantics defined by
these migrations.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"
CORE_TABLES = {
    "households", "rooms", "caregivers", "household_caregivers", "hubs", "nodes",
    "events", "alerts", "acknowledgements", "routines", "routine_windows",
    "battery_history", "configurations",
}
OPERATIONAL_TABLES = {"notification_jobs", "device_health_history", "audit_log"}
REQUIRED_TABLES = CORE_TABLES | OPERATIONAL_TABLES


def initialize_sqlite(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys = ON")
    for migration in sorted(MIGRATIONS.glob("*.sql")):
        connection.executescript(migration.read_text(encoding="utf-8"))
    connection.commit()


def table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        if not row[0].startswith("sqlite_")
    }
