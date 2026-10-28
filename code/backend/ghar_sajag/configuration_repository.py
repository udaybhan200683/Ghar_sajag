"""Durable desired/applied household configuration repository.

This repository deliberately exposes no HTTP route and creates no identity.
Callers must supply explicitly trusted caregiver-settings and verified-Hub
authorization adapters. No production adapters are currently installed. Without
those adapters every protected operation fails closed. PostgreSQL uses the
existing ``configurations`` and ``audit_log`` schema.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
import re
import sqlite3
import threading
from typing import Callable
from uuid import uuid4

from .cloud_client_identity import TimeReadiness, VerifiedHubContext
from .diagnostic_authorization import ActorSession
from .fleet import _validate_household_config


class ConfigurationDenied(PermissionError):
    """Trusted current actor or Hub authority is missing or no longer valid."""


class ConfigurationConflict(ValueError):
    """The requested version is stale, unknown, or no longer applicable."""


@dataclass(frozen=True)
class HouseholdConfigurationSnapshot:
    home_id: str
    desired_version: int
    desired_status: str | None
    desired_config: dict | None
    applied_version: int | None
    applied_config: dict | None
    schema_version: int | None


CaregiverSettingsAuthorizer = Callable[[ActorSession, str, int], bool]
HubConfigurationAuthorizer = Callable[[VerifiedHubContext, str, int], bool]


class PostgresConfigurationRepository:
    """Versioned config persistence behind server-owned authorization adapters.

    The implementation also accepts the project's SQLite migration-backed DB
    facade for deterministic contract tests. A PostgreSQL ``PostgresConnection``
    serializes configuration writers in its existing transaction wrapper; the
    unique ``(home_id, version)`` constraint remains the final conflict guard.
    The callbacks must be backed by the approved current caregiver authority and
    the GS-109 verified Hub middleware. The typed context classes alone are not
    evidence of authentication.
    """

    SCHEMA_VERSION = 1
    MAX_CONFIG_BYTES = 64 * 1024
    _FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")

    def __init__(self, db, *,
                 authorize_caregiver_settings: CaregiverSettingsAuthorizer | None = None,
                 authorize_hub_configuration: HubConfigurationAuthorizer | None = None,
                 lock: threading.RLock | None = None):
        self.db = db
        if (getattr(db, "dialect", None) == "postgres" and
                getattr(db, "durable_commit_ready", False) is not True):
            raise ConfigurationDenied("postgres_durable_commit_not_ready")
        self.authorize_caregiver_settings = authorize_caregiver_settings
        self.authorize_hub_configuration = authorize_hub_configuration
        self.lock = lock or threading.RLock()

    def publish_desired(self, *, actor: ActorSession, home_id: str, config: dict,
                        expected_version: int, at: int) -> HouseholdConfigurationSnapshot:
        """Persist a caregiver-authorized desired version using optimistic concurrency."""
        self._validate_time(at)
        self._validate_home(home_id)
        if (type(expected_version) is not int or expected_version < 0):
            raise ValueError("invalid_expected_config_version")
        canonical = self._request_policy(config, home_id=home_id,
                                         expected_version=expected_version)

        with self.lock:
            self._begin()
            try:
                if self.db.execute("SELECT 1 FROM households WHERE home_id=?", (home_id,)).fetchone() is None:
                    raise ConfigurationDenied("home_not_found")
                self._authorize_caregiver(actor, home_id, at)
                row = self.db.execute(
                    "SELECT COALESCE(MAX(version),0) FROM configurations WHERE home_id=?",
                    (home_id,),
                ).fetchone()
                current_version = int(row[0])
                if current_version != expected_version:
                    raise ConfigurationConflict("stale_desired_configuration_version")
                version = current_version + 1
                self.db.execute(
                    "UPDATE configurations SET status='SUPERSEDED' "
                    "WHERE home_id=? AND status='DESIRED'", (home_id,),
                )
                try:
                    self.db.execute(
                        """INSERT INTO configurations
                           (config_id,home_id,version,schema_version,config_json,desired_at,
                            applied_at,status,rejection_reason)
                           VALUES(?,?,?,?,?,?,NULL,'DESIRED',NULL)""",
                        (str(uuid4()), home_id, version, self.SCHEMA_VERSION,
                         json.dumps(canonical, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False), at),
                    )
                except sqlite3.IntegrityError as error:
                    raise ConfigurationConflict("configuration_version_conflict") from error
                self._audit(home_id, at, "CAREGIVER", actor.actor_id,
                            "config.desired.published", str(version),
                            {"schema_version": self.SCHEMA_VERSION})
                snapshot = self._snapshot(home_id)
                self.db.commit()
                return snapshot
            except BaseException:
                self.db.rollback()
                raise

    def get_for_caregiver(self, *, actor: ActorSession, home_id: str,
                          at: int) -> HouseholdConfigurationSnapshot:
        """Read desired/applied state only for a current Home Settings member."""
        self._validate_time(at)
        self._validate_home(home_id)
        with self.lock:
            self._begin()
            try:
                if self.db.execute("SELECT 1 FROM households WHERE home_id=?", (home_id,)).fetchone() is None:
                    raise ConfigurationDenied("home_not_found")
                self._authorize_caregiver(actor, home_id, at)
                snapshot = self._snapshot(home_id)
                self.db.commit()
                return snapshot
            except BaseException:
                self.db.rollback()
                raise

    def get_for_hub(self, *, context: VerifiedHubContext, home_id: str,
                    at: int) -> HouseholdConfigurationSnapshot:
        """Return current desired/applied state only for a currently owned Hub."""
        self._validate_time(at)
        self._validate_home(home_id)
        with self.lock:
            self._begin()
            try:
                self._authorize_hub(context, home_id, at)
                snapshot = self._snapshot(home_id)
                self.db.commit()
                return snapshot
            except BaseException:
                self.db.rollback()
                raise

    def record_applied(self, *, context: VerifiedHubContext, home_id: str,
                       version: int, at: int) -> HouseholdConfigurationSnapshot:
        """Accept an exact current desired-version acknowledgement from its Hub."""
        self._validate_time(at)
        self._validate_home(home_id)
        if type(version) is not int or version <= 0:
            raise ValueError("invalid_applied_config_version")
        with self.lock:
            self._begin()
            try:
                self._authorize_hub(context, home_id, at)
                latest = self.db.execute(
                    "SELECT version,status FROM configurations WHERE home_id=? "
                    "ORDER BY version DESC LIMIT 1", (home_id,),
                ).fetchone()
                if latest is None or int(latest[0]) != version:
                    raise ConfigurationConflict("stale_or_unknown_applied_configuration")
                if latest[1] == "APPLIED":
                    snapshot = self._snapshot(home_id)
                    self.db.commit()
                    return snapshot
                if latest[1] != "DESIRED":
                    raise ConfigurationConflict("configuration_is_not_currently_desired")
                changed = self.db.execute(
                    "UPDATE configurations SET status='APPLIED',applied_at=? "
                    "WHERE home_id=? AND version=? AND status='DESIRED'",
                    (at, home_id, version),
                )
                if getattr(changed, "rowcount", 1) != 1:
                    raise ConfigurationConflict("configuration_apply_conflict")
                self._audit(home_id, at, "DEVICE", context.permanent_hub_id,
                            "config.applied.acknowledged", str(version),
                            {"installation_epoch": context.installation_epoch})
                snapshot = self._snapshot(home_id)
                self.db.commit()
                return snapshot
            except BaseException:
                self.db.rollback()
                raise

    def _authorize_hub(self, context: VerifiedHubContext, home_id: str, at: int) -> None:
        if (type(context) is not VerifiedHubContext or
                not self._identifier(context.permanent_hub_id) or
                context.home_id != home_id or type(context.installation_epoch) is not int or
                context.installation_epoch <= 0 or
                self._FINGERPRINT.fullmatch(context.certificate_fingerprint_sha256 or "") is None or
                self._FINGERPRINT.fullmatch(context.ownership_fingerprint_sha256 or "") is None or
                context.certificate_chain_verified is not True or
                context.time_readiness is not TimeReadiness.TRUSTED):
            raise ConfigurationDenied("verified_current_hub_context_required")
        if self.authorize_hub_configuration is None:
            raise ConfigurationDenied("trusted_hub_configuration_authority_unavailable")
        if self.authorize_hub_configuration(context, home_id, at) is not True:
            raise ConfigurationDenied("current_hub_configuration_authority_required")
        row = self.db.execute(
            """SELECT identity_key_fingerprint,home_id,installation_epoch,state
               FROM hub_ownership_registry WHERE hub_device_id=?""",
            (context.permanent_hub_id,),
        ).fetchone()
        if (row is None or row[3] != "ACTIVE" or row[1] != home_id or
                int(row[2]) != context.installation_epoch or
                row[0] != context.ownership_fingerprint_sha256):
            raise ConfigurationDenied("hub_home_epoch_ownership_changed")

    def _authorize_caregiver(self, actor: ActorSession, home_id: str, at: int) -> None:
        if (type(actor) is not ActorSession or not self._identifier(actor.actor_id) or
                not self._identifier(actor.session_id) or
                not self._identifier(actor.issuer_reference) or
                type(actor.expires_at) is not int or at >= actor.expires_at):
            raise ConfigurationDenied("current_caregiver_session_required")
        if self.authorize_caregiver_settings is None:
            raise ConfigurationDenied("trusted_home_settings_authority_unavailable")
        if self.authorize_caregiver_settings(actor, home_id, at) is not True:
            raise ConfigurationDenied("current_home_settings_membership_required")

    def _snapshot(self, home_id: str) -> HouseholdConfigurationSnapshot:
        latest = self.db.execute(
            """SELECT version,schema_version,config_json,status
               FROM configurations WHERE home_id=? ORDER BY version DESC LIMIT 1""",
            (home_id,),
        ).fetchone()
        applied = self.db.execute(
            """SELECT version,schema_version,config_json FROM configurations
               WHERE home_id=? AND status='APPLIED' ORDER BY version DESC LIMIT 1""",
            (home_id,),
        ).fetchone()
        if latest is not None and int(latest[1]) != self.SCHEMA_VERSION:
            raise ConfigurationConflict("unsupported_household_configuration_schema")
        if applied is not None and int(applied[1]) != self.SCHEMA_VERSION:
            raise ConfigurationConflict("unsupported_applied_configuration_schema")
        desired_config = (self._decode_policy(latest[2])
                          if latest and latest[3] in {"DESIRED", "APPLIED"} else None)
        applied_config = self._decode_policy(applied[2]) if applied else None
        return HouseholdConfigurationSnapshot(
            home_id=home_id,
            desired_version=int(latest[0]) if latest else 0,
            desired_status=latest[3] if latest else None,
            desired_config=desired_config,
            applied_version=int(applied[0]) if applied else None,
            applied_config=applied_config,
            schema_version=int(latest[1]) if latest else None,
        )

    def _audit(self, home_id: str, at: int, actor_type: str, actor_id: str,
               action: str, subject_id: str, details: dict) -> None:
        self.db.execute(
            """INSERT INTO audit_log
               (home_id,occurred_at,actor_type,actor_id,action,subject_type,subject_id,details_json)
               VALUES(?,?,?,?,?,'CONFIGURATION',?,?)""",
            (home_id, at, actor_type, actor_id, action, subject_id,
             json.dumps(details, sort_keys=True, separators=(",", ":"))),
        )

    def _begin(self) -> None:
        if getattr(self.db, "in_transaction", False):
            raise RuntimeError("configuration_repository_requires_clean_transaction")
        self.db.execute("BEGIN IMMEDIATE")

    @classmethod
    def _canonical_policy(cls, config: object) -> dict:
        if not isinstance(config, dict) or any(key in config for key in ("home_id", "version", "schema")):
            raise ValueError("configuration_policy_metadata_is_repository_owned")
        try:
            encoded = json.dumps(config, sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError) as error:
            raise ValueError("configuration_policy_must_be_json") from error
        if len(encoded) > cls.MAX_CONFIG_BYTES:
            raise ValueError("configuration_policy_too_large")
        canonical = json.loads(encoded)
        _validate_household_config(canonical)
        return canonical

    @classmethod
    def _request_policy(cls, config: object, *, home_id: str,
                        expected_version: int) -> dict:
        """Accept legacy matching envelope metadata, but keep authority server-owned."""
        if not isinstance(config, dict):
            raise ValueError("invalid_config")
        request = deepcopy(config)
        if "home_id" in request:
            if request["home_id"] != home_id:
                raise ValueError("configuration_home_mismatch")
            del request["home_id"]
        if "schema" in request:
            if type(request["schema"]) is not int or request["schema"] != cls.SCHEMA_VERSION:
                raise ValueError("unsupported_configuration_schema")
            del request["schema"]
        if "version" in request:
            if type(request["version"]) is not int or request["version"] != expected_version:
                raise ConfigurationConflict("request_configuration_version_mismatch")
            del request["version"]
        return cls._canonical_policy(request)

    @classmethod
    def _decode_policy(cls, encoded: str) -> dict:
        try:
            return cls._canonical_policy(json.loads(encoded))
        except (TypeError, json.JSONDecodeError, ValueError) as error:
            raise ConfigurationConflict("stored_household_configuration_invalid") from error

    @staticmethod
    def _validate_time(at: object) -> None:
        if type(at) is not int or at < 0:
            raise ValueError("invalid_configuration_timestamp")

    @staticmethod
    def _validate_home(home_id: object) -> None:
        if (type(home_id) is not str or not 1 <= len(home_id.encode("utf-8")) <= 128 or
                home_id.strip() != home_id):
            raise ValueError("invalid_home_id")

    @staticmethod
    def _identifier(value: object) -> bool:
        return type(value) is str and 1 <= len(value.encode("utf-8")) <= 256 and value.strip() == value
