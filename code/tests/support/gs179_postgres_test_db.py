"""Per-stack PostgreSQL schema isolation for opt-in GS-179 E2E runs.

The fixture refuses remote databases. Its DSN must explicitly point at a local
developer PostgreSQL instance; every ProductStack gets a fresh random schema.
"""
from __future__ import annotations

import secrets
from urllib.parse import quote, urlencode

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg import sql


class IsolatedPostgresSchema:
    def __init__(self, base_dsn: str):
        fields = conninfo_to_dict(base_dsn)
        host = fields.get("host", "localhost")
        if host not in {None, "", "localhost", "127.0.0.1", "::1"} and not str(host).startswith("/"):
            raise ValueError("GS179 PostgreSQL E2E accepts local database hosts only")
        self.schema = "gs179_e2e_" + secrets.token_hex(8)
        self._base_dsn = base_dsn
        with psycopg.connect(base_dsn, connect_timeout=5, autocommit=True) as connection:
            connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(self.schema)))
        self.dsn = make_conninfo(base_dsn, options=f"-c search_path={self.schema},public",
                                 connect_timeout=5)
        fields = conninfo_to_dict(self.dsn)
        user = quote(fields.pop("user", ""), safe="")
        password = fields.pop("password", None)
        credentials = user + ((":" + quote(password, safe="")) if password else "")
        credentials += "@" if credentials else ""
        database = quote(fields.pop("dbname", "postgres"), safe="")
        host = fields.pop("host", "localhost")
        port = fields.pop("port", "5432")
        query = urlencode(fields, quote_via=quote)
        if str(host).startswith("/"):
            query = urlencode({**fields, "host": host, "port": port}, quote_via=quote)
            authority = credentials + "/" + database
        else:
            authority = credentials + quote(str(host), safe="[]") + ":" + quote(str(port), safe="") + "/" + database
        self.url = "postgresql://" + authority + ("?" + query if query else "")

    def close(self) -> None:
        with psycopg.connect(self._base_dsn, connect_timeout=5, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                sql.Identifier(self.schema)))
