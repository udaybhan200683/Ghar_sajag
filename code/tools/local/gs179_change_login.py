#!/usr/bin/env python3
"""Change the existing private GS-179 local TEST_ONLY caregiver login.

The database row and its sessions are changed in one transaction.  A private,
fsynced pending envelope makes the credential-file update recoverable if the
process stops between the database commit and atomic file replacement.
"""
from __future__ import annotations

import fcntl
import getpass
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import sys
import time

SERVER = Path(__file__).resolve().parents[2] / "parivar_saathi_android_app" / "server"
sys.path.insert(0, str(SERVER))
from connected_lite import Store, password_hash, password_valid  # noqa: E402

MAX_CREDENTIAL_BYTES = 16_384
EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class LoginChangeError(Exception):
    """Safe, non-secret error suitable for operator display."""


class DuplicateEmail(LoginChangeError):
    pass


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if len(email) > 254 or not EMAIL.fullmatch(email):
        raise LoginChangeError("invalid_email")
    return email


def validate_password(password: str, confirmation: str | None = None) -> None:
    if not isinstance(password, str) or not 16 <= len(password) <= 256:
        raise LoginChangeError("password_must_be_16_to_256_characters")
    if confirmation is not None and password != confirmation:
        raise LoginChangeError("password_confirmation_mismatch")


def _check_private_directory(path: Path) -> None:
    try:
        info = path.stat(follow_symlinks=False)
    except OSError as error:
        raise LoginChangeError("private_credential_directory_unavailable") from error
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or
            stat.S_IMODE(info.st_mode) != 0o700):
        raise LoginChangeError("private_credential_directory_permissions_invalid")


def _check_private_file(path: Path, *, missing_ok: bool = False) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        if missing_ok:
            return False
        raise LoginChangeError("private_credential_file_missing") from None
    except (OSError, UnicodeError) as error:
        raise LoginChangeError("private_credential_file_unavailable") from error
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or
            stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
        raise LoginChangeError("private_credential_file_permissions_invalid")
    return True


def _read_json(path: Path, *, missing_ok: bool = False) -> dict | None:
    if not _check_private_file(path, missing_ok=missing_ok):
        return None
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
        with os.fdopen(fd, "r", encoding="utf-8") as stream:
            opened = os.fstat(stream.fileno())
            if (not stat.S_ISREG(opened.st_mode) or opened.st_uid != os.getuid() or
                    stat.S_IMODE(opened.st_mode) != 0o600 or opened.st_nlink != 1):
                raise LoginChangeError("private_credential_file_permissions_invalid")
            raw = stream.read(MAX_CREDENTIAL_BYTES + 1)
    except LoginChangeError:
        raise
    except (OSError, UnicodeError) as error:
        raise LoginChangeError("private_credential_file_unavailable") from error
    if len(raw.encode("utf-8")) > MAX_CREDENTIAL_BYTES:
        raise LoginChangeError("private_credential_file_too_large")
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeError) as error:
        raise LoginChangeError("private_credential_file_invalid") from error
    if not isinstance(value, dict):
        raise LoginChangeError("private_credential_file_invalid")
    return value


def _fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_write(path: Path, content: bytes) -> None:
    if len(content) > MAX_CREDENTIAL_BYTES:
        raise LoginChangeError("private_credential_file_too_large")
    _check_private_directory(path.parent)
    if path.exists() or path.is_symlink():
        _check_private_file(path)
    temp = path.parent / ("." + path.name + "." + secrets.token_hex(12) + ".tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(temp, flags, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        _fsync_directory(path.parent)
    except OSError as error:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        raise LoginChangeError("private_credential_file_update_failed") from error


def _encode_json(value: dict) -> bytes:
    try:
        return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    except (TypeError, ValueError) as error:
        raise LoginChangeError("private_credential_file_invalid") from error


def _check_profile(credentials: dict) -> tuple[str, str]:
    if credentials.get("profile") != "GS179_TEST_ONLY":
        raise LoginChangeError("test_only_caregiver_account_required")
    home = credentials.get("home_id")
    if not isinstance(home, str) or not home.startswith("gs177-test-"):
        raise LoginChangeError("test_only_home_required")
    email = credentials.get("email")
    password = credentials.get("password")
    if not isinstance(email, str) or not isinstance(password, str):
        raise LoginChangeError("private_credential_file_invalid")
    return normalize_email(email), home


def _account_in_transaction(store: Store, db, credentials: dict, *, lock: bool = False) -> dict:
    email, home = _check_profile(credentials)
    account_id = credentials.get("account_id")
    if account_id is not None and (not isinstance(account_id, str) or not account_id):
        raise LoginChangeError("private_credential_file_invalid")
    suffix = " FOR UPDATE" if lock and not store.local else ""
    if account_id:
        row = store.sql(db, "SELECT account_id,email,password_hash,active FROM lite_accounts WHERE account_id=?" + suffix,
                        (account_id,)).fetchone()
    else:
        row = store.sql(db, "SELECT account_id,email,password_hash,active FROM lite_accounts WHERE email=?" + suffix,
                        (email,)).fetchone()
    if (not row or not row["active"] or row["email"].lower() != email or
            not password_valid(credentials["password"], row["password_hash"])):
        raise LoginChangeError("current_caregiver_login_invalid")
    membership = store.sql(db,
        "SELECT m.active,m.ownership_epoch,h.test_only,h.ownership_epoch AS home_epoch "
        "FROM lite_memberships m JOIN lite_homes h ON h.home_id=m.home_id "
        "WHERE m.account_id=? AND m.home_id=?",
        (row["account_id"], home)).fetchone()
    if (not membership or not membership["active"] or not membership["test_only"] or
            membership["ownership_epoch"] != membership["home_epoch"]):
        raise LoginChangeError("current_test_home_membership_invalid")
    return dict(row)


def _remove_pending(path: Path) -> None:
    _check_private_file(path)
    path.unlink()
    _fsync_directory(path.parent)


def _pending_matches_account(store: Store, pending: dict, *, lock: bool = False) -> dict | None:
    if (pending.get("version") != 1 or not isinstance(pending.get("target"), dict) or
            not isinstance(pending.get("target_password_hash"), str)):
        raise LoginChangeError("pending_login_recovery_invalid")
    target = pending["target"]
    target_email, target_home = _check_profile(target)
    account_id = target.get("account_id")
    if (not isinstance(account_id, str) or not account_id or
            pending.get("account_id") != account_id or pending.get("home_id") != target_home or
            not password_valid(target["password"], pending["target_password_hash"])):
        raise LoginChangeError("pending_login_recovery_invalid")
    with store.connect() as db:
        suffix = " FOR UPDATE" if lock and not store.local else ""
        account = store.sql(db,
            "SELECT account_id,email,password_hash,active FROM lite_accounts WHERE account_id=?" + suffix,
            (account_id,)).fetchone()
        membership = store.sql(db,
            "SELECT m.active,m.ownership_epoch,h.test_only,h.ownership_epoch AS home_epoch "
            "FROM lite_memberships m JOIN lite_homes h ON h.home_id=m.home_id "
            "WHERE m.account_id=? AND m.home_id=?",
            (account_id, target_home)).fetchone()
    if (account and account["active"] and account["email"] == target_email and
            account["password_hash"] == pending["target_password_hash"] and
            membership and membership["active"] and membership["test_only"] and
            membership["ownership_epoch"] == membership["home_epoch"]):
        return target
    return None


def _reconcile_pending(store: Store, credentials_path: Path, pending_path: Path) -> bool:
    pending = _read_json(pending_path, missing_ok=True)
    if pending is None:
        return False
    target = _pending_matches_account(store, pending)
    if target is not None:
        _atomic_write(credentials_path, _encode_json(target))
        _remove_pending(pending_path)
        return True

    current = _read_json(credentials_path)
    current_email, current_home = _check_profile(current)
    target_email, target_home = _check_profile(pending["target"])
    if (current_home != target_home or
            pending.get("account_id") != pending["target"].get("account_id") or
            pending.get("home_id") != target_home):
        raise LoginChangeError("pending_login_recovery_identity_mismatch")
    with store.connect() as db:
        old_account = _account_in_transaction(store, db, current)
    pending_account_id = pending["target"].get("account_id")
    if (pending_account_id != old_account["account_id"] or
            (current.get("account_id") and current["account_id"] != pending_account_id) or
            pending.get("previous_email") != current_email):
        raise LoginChangeError("pending_login_recovery_identity_mismatch")
    # A staged update that did not commit is safe to discard only while the
    # original private credential still authenticates the unchanged DB row.
    if current_email == old_account["email"].lower() and target_email:
        _remove_pending(pending_path)
        return False
    raise LoginChangeError("pending_login_recovery_state_ambiguous")


def _locked(credentials_path: Path):
    class Lock:
        def __enter__(self):
            _check_private_directory(credentials_path.parent)
            self.path = credentials_path.parent / ("." + credentials_path.name + ".lock")
            flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
            try:
                self.fd = os.open(self.path, flags, 0o600)
                info = os.fstat(self.fd)
                if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or
                        stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
                    raise LoginChangeError("private_login_lock_permissions_invalid")
                fcntl.flock(self.fd, fcntl.LOCK_EX)
            except LoginChangeError:
                if hasattr(self, "fd"):
                    os.close(self.fd)
                raise
            except OSError as error:
                if hasattr(self, "fd"):
                    os.close(self.fd)
                raise LoginChangeError("private_login_lock_unavailable") from error
            return self

        def __exit__(self, *_exc):
            try:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
            finally:
                os.close(self.fd)
    return Lock()


def update_existing_login(store: Store, credentials_path: Path, new_email: str,
                          new_password: str, confirmation: str | None = None) -> None:
    """Update only the current account and its sessions; preserve all other rows."""
    email = normalize_email(new_email)
    validate_password(new_password, confirmation)
    credentials_path = Path(credentials_path)
    _check_private_directory(credentials_path.parent)
    _check_private_file(credentials_path)
    pending_path = credentials_path.with_name(credentials_path.name + ".pending")
    with _locked(credentials_path):
        if _reconcile_pending(store, credentials_path, pending_path):
            raise LoginChangeError("previous_login_change_recovered_retry_with_new_values")
        if _check_private_file(pending_path, missing_ok=True):
            raise LoginChangeError("pending_login_recovery_unresolved")
        credentials = _read_json(credentials_path)
        if credentials is None:
            raise LoginChangeError("private_credential_file_missing")
        target_email, _ = _check_profile(credentials)
        with store.connect() as db:
            account = _account_in_transaction(store, db, credentials, lock=True)
            duplicate = store.sql(db,
                "SELECT account_id FROM lite_accounts WHERE email=? AND account_id<>?",
                (email, account["account_id"])).fetchone()
            if duplicate:
                raise DuplicateEmail("email_already_in_use")
        target = dict(credentials)
        target.update(email=email, password=new_password, account_id=account["account_id"])
        target_hash = password_hash(new_password)
        pending = {"version": 1, "target": target,
                   "target_password_hash": target_hash,
                   "previous_email": target_email,
                   "account_id": account["account_id"],
                   "home_id": credentials["home_id"]}
        _atomic_write(pending_path, _encode_json(pending))
        try:
            with store.connect() as db:
                current = _account_in_transaction(store, db, credentials, lock=True)
                if current["account_id"] != account["account_id"]:
                    raise LoginChangeError("account_changed_during_login_change")
                try:
                    result = store.sql(db,
                        "UPDATE lite_accounts SET email=?,password_hash=? "
                        "WHERE account_id=? AND email=? AND password_hash=? AND active=?",
                        (email, target_hash, account["account_id"], account["email"],
                         account["password_hash"], True))
                except Exception as error:
                    if isinstance(error, sqlite3.IntegrityError) or getattr(error, "sqlstate", None) == "23505":
                        raise DuplicateEmail("email_already_in_use") from None
                    raise
                if result.rowcount != 1:
                    raise LoginChangeError("account_changed_during_login_change")
                store.sql(db,
                    "UPDATE lite_sessions SET revoked_at=? WHERE account_id=? AND revoked_at IS NULL",
                    (int(time.time()), account["account_id"]))
        except DuplicateEmail:
            # No database change committed. Keep recovery state until it is
            # verified against the original credential on the next invocation.
            raise
        except LoginChangeError:
            raise
        except Exception as error:
            if isinstance(error, sqlite3.IntegrityError) or getattr(error, "sqlstate", None) == "23505":
                raise DuplicateEmail("email_already_in_use") from None
            raise LoginChangeError("database_update_failed_pending_recovery_preserved") from error

        _atomic_write(credentials_path, _encode_json(target))
        _remove_pending(pending_path)


def main() -> int:
    dsn = os.environ.get("GS179_LOCAL_SERVER_DSN", "")
    credential_value = os.environ.get("GS179_CAREGIVER_CREDENTIALS", "")
    if not dsn or not credential_value:
        print("BLOCKED local_test_database_or_credentials_path_missing")
        return 2
    credentials_path = Path(credential_value).expanduser()
    try:
        if not sys.stdin.isatty() or not sys.stderr.isatty():
            raise LoginChangeError("interactive_tty_required_hidden_password_input_unavailable")
        store = Store(dsn)
        with _locked(credentials_path):
            pending_path = credentials_path.with_name(credentials_path.name + ".pending")
            if _reconcile_pending(store, credentials_path, pending_path):
                print("GS179 caregiver login change recovery completed; active sessions are revoked")
                return 0
            if _check_private_file(pending_path, missing_ok=True):
                raise LoginChangeError("pending_login_recovery_unresolved")
            current = _read_json(credentials_path)
            if current is None:
                raise LoginChangeError("private_credential_file_missing")
            with store.connect() as db:
                _account_in_transaction(store, db, current)
        new_email = normalize_email(input("New caregiver email: "))
        password = getpass.getpass("New password (16-256 characters): ")
        confirmation = getpass.getpass("Confirm new password: ")
        try:
            update_existing_login(store, credentials_path, new_email, password, confirmation)
        finally:
            password = ""
            confirmation = ""
        print("GS179 caregiver login updated; account and Home preserved; active sessions revoked")
        return 0
    except (LoginChangeError, DuplicateEmail) as error:
        print("BLOCKED " + str(error), file=sys.stderr)
        return 2
    except (EOFError, KeyboardInterrupt):
        print("BLOCKED login_change_cancelled", file=sys.stderr)
        return 2
    except Exception:
        # Do not emit tracebacks that could disclose local connection details or
        # private credential context through a terminal transcript.
        print("BLOCKED login_change_failed_check_database_and_private_recovery_state", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
