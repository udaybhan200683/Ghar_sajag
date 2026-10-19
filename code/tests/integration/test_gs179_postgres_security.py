"""Focused failure-closed PostgreSQL boundary tests for GS-179 TEST_ONLY."""
import unittest
import psycopg

from ghar_sajag.postgres_database import connect_postgres, initialize_postgres
from gs179_postgres_test_db import IsolatedPostgresSchema, local_verified_postgres_url


class PostgresSecurityBoundary(unittest.TestCase):
    def test_remote_database_requires_hostname_verified_tls(self):
        for dsn in (
            "host=db.example.invalid dbname=ghar user=hub sslmode=require",
            "host=db.example.invalid dbname=ghar user=hub sslmode=prefer",
        ):
            with self.subTest(dsn=dsn), self.assertRaisesRegex(
                    ValueError, "remote_postgres_requires_sslmode_verify_full"):
                connect_postgres(dsn)

    def test_local_plaintext_requires_explicit_test_mode(self):
        dsn = "host=/tmp/no-postgres-here dbname=ghar user=hub"
        with self.assertRaisesRegex(ValueError, "local_postgres_requires_explicit_test_mode_or_tls"):
            connect_postgres(dsn)

    def test_local_test_override_does_not_allow_remote_unverified_tls(self):
        dsn = "host=db.example.invalid dbname=ghar user=hub sslmode=require"
        with self.assertRaisesRegex(ValueError, "remote_postgres_requires_sslmode_verify_full"):
            connect_postgres(dsn, allow_local_unencrypted=True)

    def test_migration_fails_before_queries_without_durable_server_settings(self):
        class UnsafeDatabase:
            dialect = "postgres"
            durable_commit_ready = False
            in_transaction = False

            def execute(self, *_args, **_kwargs):
                raise AssertionError("migration must reject before executing SQL")

        with self.assertRaisesRegex(ValueError, "postgres_durable_settings_required"):
            initialize_postgres(UnsafeDatabase())

    def test_isolated_schema_refuses_nonlocal_database_before_connecting(self):
        with self.assertRaisesRegex(ValueError, "accepts local database hosts only"):
            IsolatedPostgresSchema("host=database.example.invalid dbname=ghar user=hub")

    def test_persistent_local_server_dsn_requires_local_hostname_verified_tls(self):
        with self.assertRaisesRegex(ValueError, "loopback hosts only"):
            local_verified_postgres_url(
                "host=database.example.invalid dbname=ghar user=hub sslmode=verify-full"
            )
        with self.assertRaisesRegex(ValueError, "requires hostname-verified TLS"):
            local_verified_postgres_url("host=127.0.0.1 dbname=ghar user=hub sslmode=require")
        url = local_verified_postgres_url(
            "host=127.0.0.1 port=55432 dbname=gs179_monitoring user=gs179_app "
            "password=private sslmode=verify-full sslrootcert=/private/pg-ca.pem"
        )
        self.assertTrue(url.startswith("postgresql://gs179_app:private@127.0.0.1:55432/"))
        self.assertIn("sslmode=verify-full", url)

    def test_postgres_adapter_preserves_tls_query_when_adding_connect_timeout(self):
        dsn = ("postgresql://gs179_app:private@127.0.0.1:1/gs179_monitoring"
               "?sslmode=verify-full&sslrootcert=%2Fprivate%2Fpostgres-ca.pem")
        with self.assertRaises(psycopg.OperationalError):
            connect_postgres(dsn)


if __name__ == "__main__":
    unittest.main()
