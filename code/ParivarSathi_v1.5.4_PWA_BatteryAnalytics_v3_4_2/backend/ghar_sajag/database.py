"""Relational persistence schema adapter for the host application.

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
OPERATIONAL_TABLES = {"notification_jobs", "device_health_history", "audit_log", "battery_power_profiles", "battery_usage_history"}
APPLICATION_TABLES = {"family_members", "device_registry", "application_policy", "schema_migrations"}
REQUIRED_TABLES = CORE_TABLES | OPERATIONAL_TABLES | APPLICATION_TABLES


def initialize_sqlite(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    for migration in sorted(MIGRATIONS.glob("*.sql")):
        if connection.execute("SELECT 1 FROM schema_migrations WHERE name=?", (migration.name,)).fetchone():
            continue
        connection.executescript(migration.read_text(encoding="utf-8"))
        connection.execute("INSERT INTO schema_migrations(name) VALUES(?)", (migration.name,))
    connection.commit()


def table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        if not row[0].startswith("sqlite_")
    }
