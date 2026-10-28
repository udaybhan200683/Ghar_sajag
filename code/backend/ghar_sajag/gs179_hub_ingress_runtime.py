"""Default-disabled composition for the GS-179 TEST_ONLY Hub ingress.

This runtime composes the existing TLS listener and durable PostgreSQL API. It
is deliberately separate from WSGI/Gunicorn: ordinary caregiver startup never
opens a Hub socket. All credentials, ownership and trusted-time dependencies
are injected by the caller, and this TEST_ONLY composition cannot serve a
commercial identity or non-test Home namespace. Private-network binding needs
an explicit opt-in and a fixed RFC1918 IPv4 address; loopback remains default.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import ipaddress
import os
from pathlib import Path
import re
import stat
import threading
from typing import Mapping, Protocol

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from psycopg.conninfo import conninfo_to_dict

from .cloud_client_identity import TimeReadiness, VerifiedHubContext
from .durable_api import DurableEventApi, open_postgres_durable_event_api
from .identity_namespaces import is_gs179_test_hub_home
from .service import GharSajagService
from .test_only_mtls_listener import TestOnlyMtlsListener


_PROFILE = "GS179_TEST_ONLY"
_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")


class TrustedTimeSource(Protocol):
    """An explicit time authority; wall-clock fallbacks are not accepted."""

    def readiness(self) -> TimeReadiness: ...

    def current_utc(self) -> datetime | None: ...


@dataclass(frozen=True)
class HubIngressRuntimeConfig:
    enabled: bool = False
    profile: str = ""
    dsn: str | None = field(default=None, repr=False)
    server_cert: Path | None = None
    server_key: Path | None = None
    client_ca: Path | None = None
    hub_id: str = ""
    home_id: str = ""
    installation_epoch: int = 0
    bind_host: str = "127.0.0.1"
    port: int = 0
    allow_private_bind: bool = False

    @classmethod
    def disabled(cls) -> "HubIngressRuntimeConfig":
        return cls()

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "HubIngressRuntimeConfig":
        """Read an explicit TEST_ONLY enable flag and its dependency references.

        An unset/false flag produces a disabled configuration without touching
        PostgreSQL, credential files, or a listening socket.
        """
        env = os.environ if environ is None else environ
        if env.get("GS179_TEST_ONLY_HUB_INGRESS", "0") != "1":
            return cls.disabled()
        names = {
            "profile": "GS179_TEST_ONLY_HUB_PROFILE",
            "dsn": "GS179_TEST_ONLY_HUB_DSN",
            "server_cert": "GS179_TEST_ONLY_HUB_SERVER_CERT",
            "server_key": "GS179_TEST_ONLY_HUB_SERVER_KEY",
            "client_ca": "GS179_TEST_ONLY_HUB_CLIENT_CA",
            "hub_id": "GS179_TEST_ONLY_HUB_ID",
            "home_id": "GS179_TEST_ONLY_HUB_HOME_ID",
            "installation_epoch": "GS179_TEST_ONLY_HUB_INSTALLATION_EPOCH",
        }
        missing = [key for key, name in names.items() if not env.get(name, "").strip()]
        if missing:
            raise ValueError("hub_ingress_configuration_incomplete:" + ",".join(missing))
        try:
            epoch = int(env[names["installation_epoch"]], 10)
            port = int(env.get("GS179_TEST_ONLY_HUB_PORT", "0"), 10)
        except (TypeError, ValueError) as error:
            raise ValueError("hub_ingress_numeric_configuration_invalid") from error
        private_bind_flag = env.get("GS179_TEST_ONLY_HUB_ALLOW_PRIVATE_BIND", "0")
        if private_bind_flag not in {"0", "1"}:
            raise ValueError("hub_ingress_private_bind_flag_invalid")
        return cls(
            enabled=True,
            profile=env[names["profile"]],
            dsn=env[names["dsn"]],
            server_cert=Path(env[names["server_cert"]]),
            server_key=Path(env[names["server_key"]]),
            client_ca=Path(env[names["client_ca"]]),
            hub_id=env[names["hub_id"]],
            home_id=env[names["home_id"]],
            installation_epoch=epoch,
            bind_host=env.get("GS179_TEST_ONLY_HUB_BIND_HOST", "127.0.0.1"),
            port=port,
            allow_private_bind=private_bind_flag == "1",
        )


class _ScopedCredentialRegistry:
    """Narrow an existing registry to the one explicitly configured TEST Hub."""

    def __init__(self, delegate, hub_id: str):
        self._delegate = delegate
        self._hub_id = hub_id
        self.environment = getattr(delegate, "environment", None)
        self.ca_fingerprint = getattr(delegate, "ca_fingerprint", None)

    def by_fingerprint(self, fingerprint_sha256: str):
        record = self._delegate.by_fingerprint(fingerprint_sha256)
        if record is None or record.permanent_hub_id != self._hub_id:
            return None
        return record


def _trusted_utc(source: TrustedTimeSource) -> datetime:
    if source.readiness() is not TimeReadiness.TRUSTED:
        raise ValueError("hub_ingress_trusted_time_not_ready")
    value = source.current_utc()
    if (not isinstance(value, datetime) or value.tzinfo is None or
            value.utcoffset() is None):
        raise ValueError("hub_ingress_trusted_time_invalid")
    return value


def _validate_runtime_bind(bind_host: str, port: int, allow_private_bind: bool) -> None:
    if type(allow_private_bind) is not bool:
        raise ValueError("hub_ingress_private_bind_flag_must_be_boolean")
    if type(port) is not int or not 0 <= port <= 65_535:
        raise ValueError("hub_ingress_port_out_of_bounds")
    if not isinstance(bind_host, str) or not bind_host:
        raise ValueError("hub_ingress_ipv4_bind_required")
    try:
        address = ipaddress.ip_address(bind_host)
    except ValueError as error:
        raise ValueError("hub_ingress_ipv4_bind_required") from error
    if not isinstance(address, ipaddress.IPv4Address):
        raise ValueError("hub_ingress_ipv4_bind_required")
    if address.is_loopback:
        return
    private_ranges = (
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
    )
    if (address.is_unspecified or address.is_multicast or address.is_reserved or
            not any(address in network for network in private_ranges)):
        raise ValueError("hub_ingress_rfc1918_bind_required")
    if not allow_private_bind:
        raise ValueError("hub_ingress_private_bind_requires_explicit_opt_in")
    if port == 0:
        raise ValueError("hub_ingress_private_bind_fixed_port_required")


def _validate_config(config: HubIngressRuntimeConfig) -> tuple[str, str, str]:
    if config.profile != _PROFILE:
        raise ValueError("explicit_gs179_test_only_profile_required")
    if not is_gs179_test_hub_home(config.hub_id, config.home_id):
        raise ValueError("test_only_hub_home_namespace_required")
    if type(config.installation_epoch) is not int or config.installation_epoch <= 0:
        raise ValueError("current_installation_epoch_required")
    _validate_runtime_bind(
        config.bind_host, config.port, config.allow_private_bind
    )
    if not isinstance(config.dsn, str) or not config.dsn.strip():
        raise ValueError("hub_ingress_postgres_dsn_required")
    fields = conninfo_to_dict(config.dsn)
    host = fields.get("host", "localhost")
    if host not in {None, "", "localhost", "127.0.0.1", "::1"}:
        raise ValueError("test_only_hub_ingress_postgres_loopback_required")
    if fields.get("dbname") != "gs179_monitoring" or fields.get("sslmode") != "verify-full":
        raise ValueError("test_only_hub_ingress_postgres_tls_and_database_required")
    paths = (config.server_cert, config.server_key, config.client_ca)
    if any(path is None for path in paths):
        raise ValueError("hub_ingress_tls_configuration_required")
    cert_path, key_path, ca_path = (Path(path) for path in paths)
    for path in (cert_path, key_path, ca_path):
        if path.is_symlink() or not path.is_file():
            raise ValueError("hub_ingress_tls_material_missing_or_unsafe")
    key_mode = stat.S_IMODE(key_path.stat().st_mode)
    if key_mode & 0o177:
        raise ValueError("hub_ingress_server_key_permissions_must_be_owner_only")
    try:
        ca_cert = x509.load_pem_x509_certificate(ca_path.read_bytes())
        if not ca_cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca:
            raise ValueError("hub_ingress_client_ca_must_be_ca")
    except (ValueError, x509.ExtensionNotFound) as error:
        raise ValueError("hub_ingress_client_ca_invalid") from error
    return str(cert_path), str(key_path), str(ca_path)


class Gs179TestOnlyHubIngressRuntime:
    """Own the existing listener and durable API in one bounded process."""

    def __init__(self, config: HubIngressRuntimeConfig, *, credentials=None,
                 trusted_time: TrustedTimeSource | None = None,
                 authority_refresh=None, on_result=None, drop_response=None):
        self.config = config
        self.credentials = credentials
        self.trusted_time = trusted_time
        self.authority_refresh = authority_refresh
        self.on_result = on_result
        self.drop_response = drop_response
        self._durable: DurableEventApi | None = None
        self._listener: TestOnlyMtlsListener | None = None
        self._origin: str | None = None
        self._closed = False
        self._lock = threading.RLock()

    def start(self) -> str | None:
        with self._lock:
            if type(self.config.enabled) is not bool:
                raise ValueError("hub_ingress_enable_flag_must_be_boolean")
            if not self.config.enabled:
                return None
            if self._closed:
                raise RuntimeError("hub_ingress_runtime_closed")
            if self._listener is not None:
                raise RuntimeError("hub_ingress_runtime_already_started")
            try:
                cert_path, key_path, ca_path = _validate_config(self.config)
                if self.credentials is None or getattr(self.credentials, "environment", None) != "TEST_ONLY":
                    raise ValueError("test_only_credential_registry_required")
                if not callable(getattr(self.credentials, "by_fingerprint", None)):
                    raise ValueError("hub_credential_registry_interface_required")
                if not callable(self.authority_refresh):
                    raise ValueError("test_only_authority_refresh_provider_required")
                if self.trusted_time is None:
                    raise ValueError("explicit_trusted_time_source_required")
                trusted_now = _trusted_utc(self.trusted_time)
                ca_cert = x509.load_pem_x509_certificate(Path(ca_path).read_bytes())
                ca_fingerprint = ca_cert.fingerprint(hashes.SHA256()).hex()
                if getattr(self.credentials, "ca_fingerprint", None) != ca_fingerprint:
                    raise ValueError("test_only_client_ca_registry_mismatch")

                scoped_credentials = _ScopedCredentialRegistry(self.credentials, self.config.hub_id)
                if scoped_credentials.environment != "TEST_ONLY" or scoped_credentials.ca_fingerprint != ca_fingerprint:
                    raise ValueError("test_only_credential_registry_invalid")

                service = GharSajagService()
                durable = open_postgres_durable_event_api(
                    service, self.config.dsn, now=lambda: int(_trusted_utc(self.trusted_time).timestamp()),
                    require_registered_ownership=True,
                    enable_test_hub_rule_decisions=True,
                    enable_household_configuration=True,
                    verified_hub_context_from_request=lambda request:
                        request if type(request) is VerifiedHubContext else None,
                    authorize_hub_configuration=lambda context, home_id, _at: (
                        type(context) is VerifiedHubContext and
                        context.permanent_hub_id == self.config.hub_id and
                        context.home_id == self.config.home_id == home_id and
                        context.installation_epoch == self.config.installation_epoch and
                        is_gs179_test_hub_home(context.permanent_hub_id, context.home_id)
                    ),
                )
                self._durable = durable
                if getattr(durable.db, "dialect", None) != "postgres" or getattr(
                        durable.db, "durable_commit_ready", False) is not True:
                    raise ValueError("hub_ingress_postgres_durability_not_ready")
                with service.lock:
                    if durable.db.execute("SELECT 1").fetchone() is None:
                        raise ValueError("hub_ingress_postgres_not_ready")
                    ownership = durable.db.execute(
                        "SELECT identity_key_fingerprint,home_id,installation_epoch "
                        "FROM hub_ownership_registry WHERE hub_device_id=? AND state='ACTIVE'",
                        (self.config.hub_id,),
                    ).fetchone()
                    if (ownership is None or ownership[1] != self.config.home_id or
                            ownership[2] != self.config.installation_epoch or
                            not isinstance(ownership[0], str) or
                            not _FINGERPRINT.fullmatch(ownership[0])):
                        raise ValueError("current_hub_home_epoch_binding_required")
                    enrollment = durable.db.execute(
                        "SELECT 1 FROM node_enrollment_history WHERE hub_device_id=? "
                        "AND home_id=? AND state='ACTIVE' LIMIT 1",
                        (self.config.hub_id, self.config.home_id),
                    ).fetchone()
                    if enrollment is None:
                        raise ValueError("current_node_enrollment_required")

                self._listener = TestOnlyMtlsListener(
                    profile=_PROFILE,
                    api=durable.api,
                    credentials=scoped_credentials,
                    ownership_db=durable.db,
                    server_cert=cert_path,
                    server_key=key_path,
                    client_ca=ca_path,
                    trusted_time=lambda: _trusted_utc(self.trusted_time),
                    authority_refresh=self.authority_refresh,
                    bind_host=self.config.bind_host,
                    port=self.config.port,
                    allow_private_bind=self.config.allow_private_bind,
                    max_request_bytes=16_384,
                    timeout_seconds=5.0,
                    available=self._backend_ready,
                    max_concurrent_requests=8,
                    on_result=self.on_result,
                    drop_response=self.drop_response,
                )
                self._origin = self._listener.start()
                return self._origin
            except BaseException:
                self._close_components()
                raise

    def _backend_ready(self) -> bool:
        durable = self._durable
        if durable is None or getattr(durable.db, "durable_commit_ready", False) is not True:
            return False
        service = durable.api.service
        try:
            with service.lock:
                return durable.db.execute("SELECT 1").fetchone() is not None
        except Exception:
            return False

    def status(self) -> dict[str, object]:
        """Report listener readiness without claiming a Hub is connected."""
        with self._lock:
            enabled = self.config.enabled
            started = self._listener is not None and self._origin is not None and not self._closed
            backend_ready = started and self._backend_ready()
            trusted_ready = started and self._time_ready()
            return {
                "runtime_implemented": "YES",
                "profile": _PROFILE if enabled else "DISABLED",
                "runtime_enabled": "YES" if enabled else "NO",
                "listener_started": "YES" if started else "NO",
                "listener_ready": "YES" if backend_ready and trusted_ready else "NO",
                "postgres_ready": "YES" if backend_ready else "NO",
                "trusted_time_ready": "YES" if trusted_ready else "NO",
                "real_hub_authenticated": "NO",
                "hub_connected": "NO",
                "monitoring_freshness": "UNKNOWN",
                "persistent_hub_ingress": "NOT_CONFIGURED",
            }

    @property
    def origin(self) -> str | None:
        return self._origin

    @property
    def durable_api(self) -> DurableEventApi | None:
        """Expose the owned API to injected TEST_ONLY domain adapters."""
        return self._durable

    def _time_ready(self) -> bool:
        try:
            _trusted_utc(self.trusted_time)
            return True
        except Exception:
            return False

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            try:
                self._close_components()
            finally:
                self._closed = True

    def _close_components(self) -> None:
        listener, self._listener = self._listener, None
        durable, self._durable = self._durable, None
        self._origin = None
        try:
            if listener is not None:
                listener.close()
        finally:
            if durable is not None:
                durable.close()


def start_gs179_test_only_hub_ingress(config: HubIngressRuntimeConfig, *,
                                      credentials=None, trusted_time: TrustedTimeSource | None = None,
                                      authority_refresh=None, on_result=None,
                                      drop_response=None) -> Gs179TestOnlyHubIngressRuntime:
    """Actual runtime entry point; caller owns and must close the returned runtime."""
    runtime = Gs179TestOnlyHubIngressRuntime(
        config, credentials=credentials, trusted_time=trusted_time,
        authority_refresh=authority_refresh, on_result=on_result,
        drop_response=drop_response,
    )
    runtime.start()
    return runtime
