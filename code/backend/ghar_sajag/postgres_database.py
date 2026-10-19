"""PostgreSQL adapter for the canonical durable Hub event/read model.

The domain adapters keep their existing transaction and identity rules. This
module supplies their small DB-API surface over psycopg and translates the
repository's SQLite migration set into PostgreSQL DDL. It does not authenticate
Hub requests; only a trusted TLS listener may create ``VerifiedHubContext``.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from psycopg import Connection, IntegrityError, OperationalError, connect
from psycopg.conninfo import conninfo_to_dict, make_conninfo


MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"
_MIGRATION_LOCK = 0x475331798


class HybridRow(tuple):
    """Tuple-compatible row with SQLite-style named access."""

    def __new__(cls, values, names):
        row = super().__new__(cls, values)
        row._names = tuple(names)
        row._indices = {name: index for index, name in enumerate(names)}
        return row

    def __getitem__(self, key):
        if isinstance(key, str):
            key = self._indices[key]
        return super().__getitem__(key)

    def keys(self):
        # Match sqlite3.Row's mapping protocol so existing `dict(row)` reads
        # remain portable without changing domain/query code.
        return self._names


def _row_factory(cursor):
    names = tuple(column.name for column in cursor.description or ())
    return lambda values: HybridRow(values, names)


def _replace_placeholders(sql: str) -> str:
    """Convert the backend's positional ``?`` placeholders outside literals."""
    output: list[str] = []
    in_single = False
    in_double = False
    index = 0
    while index < len(sql):
        char = sql[index]
        if char == "'" and not in_double:
            output.append(char)
            if in_single and index + 1 < len(sql) and sql[index + 1] == "'":
                output.append("'")
                index += 2
                continue
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
            output.append(char)
        elif char == "?" and not in_single and not in_double:
            output.append("%s")
        else:
            output.append(char)
        index += 1
    return "".join(output)


def _translate_sql(sql: str) -> str:
    sql = _replace_placeholders(sql)
    # SQLite JSON1 returns scalar JSON values; PostgreSQL extracts text from the
    # same canonical JSON payload stored by the event adapter.
    sql = re.sub(
        r"json_extract\(\s*payload_json\s*,\s*'\$\.([A-Za-z0-9_]+)'\s*\)",
        r"(payload_json::jsonb ->> '\1')",
        sql,
        flags=re.IGNORECASE,
    )
    return sql


class PostgresConnection:
    """Connection facade for the existing durable SQLite-oriented adapters."""

    dialect = "postgres"

    def __init__(self, connection: Connection, *, durable_commit_ready: bool):
        self._connection = connection
        self.durable_commit_ready = durable_commit_ready

    @property
    def in_transaction(self) -> bool:
        return self._connection.info.transaction_status.name != "IDLE"

    def execute(self, sql: str, parameters=()):
        if sql.strip().upper() == "BEGIN IMMEDIATE":
            self._connection.execute("BEGIN")
            return self._connection.execute(
                "SELECT pg_advisory_xact_lock(%s)", (_MIGRATION_LOCK,)
            )
        try:
            parameters = tuple(parameters)
            translated = _translate_sql(sql)
            if parameters:
                return self._connection.execute(translated, parameters)
            return self._connection.execute(translated, prepare=False)
        except IntegrityError as error:
            raise sqlite3.IntegrityError(str(error)) from error
        except OperationalError as error:
            raise sqlite3.OperationalError(str(error)) from error
        except Exception as error:
            # Preserve the current JsonApi's database-failure mapping without
            # exposing SQL or connection details to callers.
            from psycopg import Error as PsycopgError
            if isinstance(error, PsycopgError):
                raise sqlite3.DatabaseError(str(error)) from error
            raise

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self):
        # sqlite3's context manager commits/rolls back but keeps the connection
        # open; match that behavior (psycopg's native context also closes it).
        return self

    def __exit__(self, exc_type, _exc, _traceback):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False


def connect_postgres(dsn: str, *, allow_local_unencrypted: bool = False) -> PostgresConnection:
    """Open PostgreSQL with bounded connect time and durable commit settings.

    Remote deployments must use certificate and hostname validation. Plain
    local Unix-socket access is allowed only to explicitly isolated tests.
    """
    if not isinstance(dsn, str) or not dsn.strip():
        raise ValueError("postgres_dsn_required")
    fields = conninfo_to_dict(dsn)
    host = fields.get("host", "localhost")
    local = host in {None, "", "localhost", "127.0.0.1", "::1"} or str(host).startswith("/")
    sslmode = fields.get("sslmode")
    if not local and sslmode != "verify-full":
        raise ValueError("remote_postgres_requires_sslmode_verify_full")
    if local and not allow_local_unencrypted and sslmode not in {"verify-full", "verify-ca"}:
        raise ValueError("local_postgres_requires_explicit_test_mode_or_tls")
    # A URI cannot be extended with libpq keyword syntax. make_conninfo keeps
    # both PostgreSQL URI and keyword DSNs valid while adding the bounded
    # timeout without corrupting TLS query parameters such as sslrootcert.
    connect_dsn = dsn if "connect_timeout" in fields else make_conninfo(dsn, connect_timeout=5)
    raw = connect(connect_dsn, row_factory=_row_factory, application_name="ghar-sajag-gs179",
                  autocommit=True)
    try:
        settings = {row[0]: row[1] for row in raw.execute(
            "SELECT name, setting FROM pg_settings WHERE name IN ('fsync','synchronous_commit')"
        ).fetchall()}
        ready = settings.get("fsync") == "on" and settings.get("synchronous_commit") in {
            "on", "remote_write", "remote_apply"
        }
        return PostgresConnection(raw, durable_commit_ready=ready)
    except BaseException:
        raw.close()
        raise


def _migration_sql(path: Path) -> str:
    sql = path.read_text(encoding="utf-8")
    sql = re.sub(r"^\s*PRAGMA\s+[^;]+;\s*", "", sql, flags=re.IGNORECASE)
    # These triggers use SQLite rowid and RAISE(ABORT). The equivalent
    # PostgreSQL trigger is installed after the canonical-ID migration below.
    sql = re.sub(
        r"CREATE\s+TRIGGER\s+IF\s+NOT\s+EXISTS\s+events_fill_canonical_id.*?END\s*;",
        "",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    sql = re.sub(
        r"CREATE\s+TRIGGER\s+IF\s+NOT\s+EXISTS\s+events_reject_null_canonical_id.*?END\s*;",
        "",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    sql = "\n".join(line.split("--", 1)[0] for line in sql.splitlines())
    sql = re.sub(r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT", "BIGSERIAL PRIMARY KEY", sql,
                 flags=re.IGNORECASE)
    # SQLite INTEGER has signed 64-bit storage. PostgreSQL INTEGER is only
    # signed 32-bit; timestamps, sequences and generations use BIGINT so the
    # existing schema does not acquire a 2038 overflow boundary.
    sql = re.sub(r"\bINTEGER\b", "BIGINT", sql, flags=re.IGNORECASE)
    return sql


def _install_event_identity_trigger(db: PostgresConnection) -> None:
    db.execute("""
        CREATE OR REPLACE FUNCTION gs_events_canonical_identity_guard()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.canonical_event_id IS NULL THEN
                IF TG_OP = 'INSERT' THEN
                    NEW.canonical_event_id := NEW.event_id;
                ELSE
                    RAISE EXCEPTION 'canonical_event_id_required';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    db.execute("DROP TRIGGER IF EXISTS gs_events_canonical_identity_guard ON events")
    db.execute("""
        CREATE TRIGGER gs_events_canonical_identity_guard
        BEFORE INSERT OR UPDATE OF canonical_event_id ON events
        FOR EACH ROW EXECUTE FUNCTION gs_events_canonical_identity_guard()
    """)


def initialize_postgres(db: PostgresConnection) -> None:
    """Apply the existing canonical schema migrations in one serialized step."""
    if getattr(db, "dialect", None) != "postgres" or not db.durable_commit_ready:
        raise ValueError("postgres_durable_settings_required")
    if db.in_transaction:
        raise ValueError("postgres_migration_requires_clean_transaction")
    db.execute("BEGIN IMMEDIATE")
    try:
        db.execute("""
            CREATE TABLE IF NOT EXISTS gs_schema_migrations (
                name TEXT PRIMARY KEY,
                source_sha256 TEXT NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        for path in sorted(MIGRATIONS.glob("*.sql")):
            source = path.read_bytes()
            import hashlib
            digest = hashlib.sha256(source).hexdigest()
            prior = db.execute(
                "SELECT source_sha256 FROM gs_schema_migrations WHERE name=?", (path.name,)
            ).fetchone()
            if prior is not None:
                if prior[0] != digest:
                    raise RuntimeError("postgres_migration_source_changed:" + path.name)
                continue
            script = _migration_sql(path)
            for statement in script.split(";"):
                if statement.strip():
                    db.execute(statement)
            if path.name == "007_phase3b_household_event_identity.sql":
                _install_event_identity_trigger(db)
            db.execute(
                "INSERT INTO gs_schema_migrations(name,source_sha256) VALUES(?,?)",
                (path.name, digest),
            )
        db.commit()
    except BaseException:
        db.rollback()
        raise
