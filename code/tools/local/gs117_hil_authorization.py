"""Local owner consent for existing GS-117 readiness procedures; no technical waiver."""
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat

POLICY = Path.home() / '.config/ghar-sajag/gs117-tc001/standing-authorization.json'
STATE = Path.home() / '.local/state/ghar-sajag/gs117-tc001/standing-authorization'
IDENTITY = {
    'home_id': 'gs177-test-product', 'backend': '192.168.1.6',
    'c3': {'device_id': 'c3-146393c5d158', 'port': 'COM4', 'serial_number': '14:63:93:C5:D1:58'},
    's3': {'device_id': 'hub-e072a1d38d34', 'port': 'COM10', 'serial_number': 'E0:72:A1:D3:8D:34'},
}
IMAGES = {'c3': '591e9016c4ed8123314bf115482cce4a7ff3ddf0ebfc66842578e9003c8aa6ea',
          's3': 'c26b6241a40bf5e7bd14f68351c71ed4ac158b97fd7c4af78c8c7edb9c0a7e16'}
PROCEDURES = ('protected_gs40_bootstrap',)
OPERATIONS = ['usb_identity', 'serial_open_close', 'expected_serial_reset', 'get_state',
              'bounded_logs', 'existing_encrypted_gs40_bootstrap', 'authenticated_rejoin',
              'read_only_backend_api_postgres_android_verification']
PROHIBITED = ['injection', 'campaign', 'flash', 'erase', 'readback', 'jedec',
              'credentials', 'enrollment', 'ownership', 'database_mutation',
              'security_bypass', 'new_identity_home_or_endpoint', 'unreviewed_recovery']
PREFLIGHT = ['owner_consent', 'policy_validity', 'procedure_fingerprints',
             'exact_usb_identity', 'preserved_image_receipts', 'backend_https_postgres',
             'physical_ingress_route', 'target_boot_config_validation',
             'authenticated_rejoin_liveness_progress', 'fresh_physical_time_mtls_receipt']


class AuthorizationSafetyFailure(RuntimeError):
    """An explicit identity, authorization, authentication, or safety guard failure."""


FUNCTIONAL_OUTCOMES = frozenset({'PASS', 'FAIL', 'BLOCKED', 'NOT_RUN', 'PARTIAL'})


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _development_scope_id(policy):
    """Stable across reviewed file-pin changes, but isolated by consent and fixture."""
    identity = json.dumps(policy.get('identity'), sort_keys=True, separators=(',', ':'))
    material = '\0'.join((str(policy.get('profile')), str(policy.get('owner_approval_ref')), identity))
    return hashlib.sha256(material.encode()).hexdigest()


def _read_private_json(path):
    path = Path(path)
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or
            info.st_mode & 0o077):
        raise ValueError('development_authorization_history_not_private')
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError('development_authorization_history_corrupt') from error
    if not isinstance(value, dict):
        raise ValueError('development_authorization_history_corrupt')
    return value


def _development_history(state, policy, scope_id):
    """Reconstruct one consent's cumulative usage from the append-only audit.

    Old DEV ledgers were named after the policy file's content hash. A reviewed
    pin update therefore produced a new empty ledger. The audit log carries the
    stable owner approval reference; derive usage from distinct session starts
    and treat an interrupted session as a failure. Historical files are read
    only and remain preserved.
    """
    state = Path(state)
    audit_path = state / 'audit.jsonl'
    approval_ref = policy['owner_approval_ref']
    sessions = {}
    if audit_path.is_symlink():
        raise ValueError('development_authorization_history_not_private')
    if audit_path.exists():
        info = audit_path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or
                info.st_mode & 0o077):
            raise ValueError('development_authorization_history_not_private')
        try:
            lines = audit_path.read_text().splitlines()
        except OSError as error:
            raise ValueError('development_authorization_history_unavailable') from error
        for index, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError('development_authorization_history_corrupt') from error
            if not isinstance(record, dict):
                raise ValueError('development_authorization_history_corrupt')
            if record.get('approval_ref') != approval_ref or not record.get('started_at'):
                continue
            try:
                started = datetime.fromisoformat(record['started_at'].replace('Z', '+00:00'))
            except (TypeError, ValueError) as error:
                raise ValueError('development_authorization_history_corrupt') from error
            if started.tzinfo is None:
                raise ValueError('development_authorization_history_corrupt')
            key = started.astimezone(timezone.utc).isoformat()
            sessions.setdefault(key, []).append((index, record))

    ordered = sorted(sessions.items(), key=lambda item: item[0])
    legacy = []
    for candidate in state.glob('*.json'):
        if candidate.name == f'dev-scope-{scope_id}.json':
            continue
        record = _read_private_json(candidate)
        if record.get('approval_ref') != approval_ref:
            continue
        count = record.get('sessions')
        failures = record.get('consecutive_failures', 0)
        if (type(count) is not int or count < 0 or
                type(failures) is not int or failures < 0):
            raise ValueError('development_authorization_history_corrupt')
        if count > len(ordered):
            raise ValueError('development_authorization_history_incomplete')
        started_text = record.get('started_at')
        if started_text:
            try:
                started_dt = datetime.fromisoformat(started_text.replace('Z', '+00:00'))
            except (TypeError, ValueError) as error:
                raise ValueError('development_authorization_history_corrupt') from error
            if started_dt.tzinfo is None or started_dt.astimezone(timezone.utc).isoformat() not in sessions:
                raise ValueError('development_authorization_history_incomplete')
        legacy.append(record)

    if legacy and not ordered:
        raise ValueError('development_authorization_history_unavailable')

    consecutive = 0
    procedure_counts = {}
    latest_record = None
    for _started, entries in ordered:
        _index, latest_record = entries[-1]
        if type(latest_record.get('blocked')) is not bool:
            raise ValueError('development_authorization_history_corrupt')
        procedure = latest_record.get('procedure')
        if not isinstance(procedure, str) or procedure not in DEV_OPERATIONS:
            raise ValueError('development_authorization_history_corrupt')
        procedure_counts[procedure] = procedure_counts.get(procedure, 0) + 1
        completed = latest_record.get('completed_at')
        if not latest_record['blocked'] and not completed:
            raise ValueError('development_authorization_history_corrupt')
        if completed:
            try:
                completed_dt = datetime.fromisoformat(completed.replace('Z', '+00:00'))
            except (TypeError, ValueError) as error:
                raise ValueError('development_authorization_history_corrupt') from error
            if completed_dt.tzinfo is None:
                raise ValueError('development_authorization_history_corrupt')
        if latest_record['blocked']:
            consecutive += 1
        else:
            consecutive = 0

    blocked = bool(latest_record and latest_record['blocked'])
    if legacy and ordered:
        latest_started = ordered[-1][0]
        matching_latest = [item for item in legacy
                           if item.get('started_at') and
                           datetime.fromisoformat(item['started_at'].replace('Z', '+00:00'))
                           .astimezone(timezone.utc).isoformat() == latest_started]
        for record in matching_latest:
            # A ledger may lag the append-only audit when an older policy hash
            # lost prior failures; it must never claim a newer session/outcome.
            if (record.get('blocked') != latest_record.get('blocked') or
                    (record.get('consecutive_failures', 0) > consecutive)):
                raise ValueError('development_authorization_history_mismatch')

    history = {
        'sessions': len(ordered), 'blocked': blocked,
        'consecutive_failures': consecutive,
        'procedure_counts': procedure_counts,
        'approval_ref': approval_ref,
        'authorization_scope_id': scope_id,
    }
    if latest_record:
        for name in ('procedure', 'started_at', 'completed_at', 'failure', 'failure_class',
                     'functional_outcome', 'evidence'):
            if (name in latest_record and
                    (name not in ('failure', 'failure_class') or blocked) and
                    (name != 'functional_outcome' or not blocked) and
                    (name != 'completed_at' or not blocked)):
                history[name] = latest_record[name]
    return history


def _development_ledger_path(state, policy):
    scope_id = _development_scope_id(policy)
    return Path(state) / f'dev-scope-{scope_id}.json', scope_id


def _write_private_ledger(path, data):
    path = Path(path)
    temp = path.with_name(path.name + '.tmp')
    fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, 'w') as out:
            json.dump(data, out, sort_keys=True)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass
        raise


def _append_development_migration_audit(state, policy, policy_path, scope_id, data):
    audit = Path(state) / 'audit.jsonl'
    if audit.is_symlink():
        raise ValueError('development_authorization_history_not_private')
    flags = os.O_CREAT | os.O_APPEND | os.O_WRONLY
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    fd = os.open(audit, flags, 0o600)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or
                info.st_mode & 0o077):
            raise ValueError('development_authorization_history_not_private')
        with os.fdopen(fd, 'a') as out:
            fd = -1
            event = {
                'event': 'development_ledger_reconstructed_from_audit',
                'at_utc': datetime.now(timezone.utc).isoformat(),
                'approval_ref': policy['owner_approval_ref'],
                'authorization_scope_id': scope_id,
                'policy_manifest_sha256': digest(policy_path),
                'sessions': data['sessions'],
                'consecutive_failures': data['consecutive_failures'],
                'procedure_counts': data['procedure_counts'],
                'blocked': data['blocked'],
            }
            out.write(json.dumps(event, sort_keys=True) + '\n')
            out.flush()
            os.fsync(out.fileno())
    finally:
        if fd >= 0:
            os.close(fd)


def _canonical_record_sha256(record):
    value = dict(record)
    value.pop('record_sha256', None)
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(encoded).hexdigest()


def _read_private_audit(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('development_authorization_history_not_private')
    try:
        info = path.lstat()
    except OSError as error:
        raise ValueError('development_mode_transition_audit_missing') from error
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or
            info.st_mode & 0o077):
        raise ValueError('development_authorization_history_not_private')
    try:
        lines = path.read_text().splitlines()
        records = [json.loads(line) for line in lines if line.strip()]
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError('development_authorization_history_corrupt') from error
    if any(not isinstance(record, dict) for record in records):
        raise ValueError('development_authorization_history_corrupt')
    return records


def _verify_development_mode_transition(policy, *, allow_source_pin_drift=False):
    mode = policy.get('development_mode')
    if not isinstance(mode, dict):
        raise ValueError('development_mode_transition_missing')
    activation_id = mode.get('activation_id')
    audit_path = Path(policy.get('activation_audit_path', ''))
    if (not isinstance(activation_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{12,96}', activation_id) or
            not audit_path.is_absolute() or audit_path.is_symlink()):
        raise ValueError('development_mode_transition_invalid')
    records = _read_private_audit(audit_path)
    activations = [row for row in records
                   if row.get('event') == 'development_mode_activated' and
                   row.get('activation_id') == activation_id]
    if len(activations) != 1:
        raise ValueError('development_mode_transition_audit_mismatch')
    record = activations[0]
    audit_bytes = audit_path.read_bytes()
    audit_lines = audit_bytes.splitlines(keepends=True)
    activation_line = next((index for index, line in enumerate(audit_lines)
                            if json.loads(line).get('event') == 'development_mode_activated' and
                            json.loads(line).get('activation_id') == activation_id), None)
    predecessor = mode.get('predecessor', {})
    prefix = b''.join(audit_lines[:activation_line]) if activation_line is not None else b''
    predecessor_policy = {
        'profile': policy.get('profile'),
        'owner_approval_ref': predecessor.get('approval_ref'),
        'identity': policy.get('identity'),
    }
    expected_predecessor_scope = _development_scope_id(predecessor_policy)
    predecessor_ledger_path = audit_path.parent / f"dev-scope-{expected_predecessor_scope}.json"
    try:
        predecessor_ledger = _read_private_json(predecessor_ledger_path)
    except (OSError, ValueError) as error:
        raise ValueError('development_mode_predecessor_ledger_missing_or_invalid') from error
    expected = {
        'event': 'development_mode_activated',
        'activation_id': activation_id,
        'approval_ref': policy.get('owner_approval_ref'),
        'authorization_scope_id': _development_scope_id(policy),
        'activated_at': mode.get('activated_at'),
        'authority_refs': mode.get('authority_refs'),
        'predecessor': predecessor,
        'reviewed_commit': mode.get('reviewed_commit'),
        'reviewed_source_fingerprints': mode.get('reviewed_source_fingerprints'),
        'validation_summary': mode.get('validation_summary'),
    }
    fingerprints = mode.get('reviewed_source_fingerprints')
    if (not re.fullmatch(r'[0-9a-f]{40}', str(mode.get('reviewed_commit', ''))) or
            not isinstance(fingerprints, dict) or set(fingerprints) != set(DEV_PIN_NAMES) or
            any(not re.fullmatch(r'[0-9a-f]{64}', str(fingerprints.get(name, '')))
                for name in DEV_PIN_NAMES) or
            (not allow_source_pin_drift and
             fingerprints != {name: policy.get(name, {}).get('sha256') for name in DEV_PIN_NAMES}) or
            not isinstance(mode.get('validation_summary'), dict) or
            mode['validation_summary'].get('gs117_focused') != 'PASS' or
            mode['validation_summary'].get('framework') != 'PASS' or
            mode['validation_summary'].get('feature_coverage') != 'PASS'):
        raise ValueError('development_mode_review_evidence_invalid')
    if (any(record.get(key) != value for key, value in expected.items()) or
            record.get('record_sha256') != _canonical_record_sha256(record) or
            mode.get('activation_record_sha256') != record.get('record_sha256') or
            predecessor.get('scope_id') != expected_predecessor_scope or
            predecessor.get('audit_entry_count') != activation_line or
            hashlib.sha256(prefix).hexdigest() != predecessor.get('audit_sha256') or
            digest(predecessor_ledger_path) != predecessor.get('ledger_sha256') or
            predecessor_ledger.get('authorization_scope_id') != expected_predecessor_scope or
            predecessor_ledger.get('approval_ref') != predecessor.get('approval_ref') or
            predecessor_ledger.get('sessions') != predecessor.get('sessions') or
            predecessor_ledger.get('consecutive_failures') != predecessor.get('consecutive_failures') or
            predecessor_ledger.get('blocked') != predecessor.get('blocked')):
        raise ValueError('development_mode_transition_audit_mismatch')
    if any(row.get('event') == 'development_mode_revoked' and
           row.get('activation_id') == activation_id for row in records):
        raise ValueError('development_mode_revoked')
    return mode


def _append_private_audit(path, record):
    path = Path(path)
    if path.is_symlink() or not path.parent.is_dir():
        raise ValueError('development_authorization_history_not_private')
    flags = os.O_CREAT | os.O_APPEND | os.O_WRONLY
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or
                info.st_mode & 0o077):
            raise ValueError('development_authorization_history_not_private')
        with os.fdopen(fd, 'a') as out:
            fd = -1
            out.write(json.dumps(record, sort_keys=True) + '\n')
            out.flush()
            os.fsync(out.fileno())
    finally:
        if fd >= 0:
            os.close(fd)


def _atomic_private_json(path, value):
    path = Path(path)
    if path.is_symlink() or not path.parent.is_dir():
        raise ValueError('development_consent_requires_owner_only_file')
    temp = path.with_name(path.name + '.' + secrets.token_hex(8) + '.tmp')
    fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, 'w') as out:
            json.dump(value, out, sort_keys=True)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass
        raise


def _load_development_ledger(path, state, policy):
    ledger, scope_id = _development_ledger_path(state, policy)
    if ledger.is_symlink():
        raise ValueError('development_authorization_history_not_private')
    if ledger.exists():
        data = _read_private_json(ledger)
        if (data.get('authorization_scope_id') != scope_id or
                data.get('approval_ref') != policy['owner_approval_ref'] or
                type(data.get('sessions')) is not int or data['sessions'] < 0 or
                type(data.get('consecutive_failures', 0)) is not int or
                data.get('consecutive_failures', 0) < 0 or
                not isinstance(data.get('procedure_counts'), dict) or
                any(not isinstance(key, str) or type(value) is not int or value < 0
                    for key, value in data['procedure_counts'].items()) or
                type(data.get('blocked')) is not bool):
            raise ValueError('development_authorization_history_mismatch')
        audited = _development_history(state, policy, scope_id)
        for key in ('sessions', 'blocked', 'consecutive_failures', 'procedure_counts'):
            if data.get(key) != audited.get(key):
                raise ValueError('development_authorization_history_mismatch')
        for key in ('failure_class', 'functional_outcome'):
            if key in data or key in audited:
                if data.get(key) != audited.get(key):
                    raise ValueError('development_authorization_history_mismatch')
        return ledger, data, scope_id

    # The first use after a policy-hash change migrates counters from the
    # append-only audit, not from a new empty content-hash ledger.
    data = _development_history(state, policy, scope_id)
    data['policy_manifest_sha256'] = digest(path)
    _write_private_ledger(ledger, data)
    if data['sessions']:
        _append_development_migration_audit(state, policy, path, scope_id, data)
    return ledger, data, scope_id

def load(path=POLICY, now=None):
    path = Path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('standing_policy_requires_owner_only_regular_file')
    p = json.loads(path.read_text())
    now = now or datetime.now(timezone.utc)
    start = datetime.fromisoformat(p['activated_at'])
    end = datetime.fromisoformat(p['expires_at'])
    if (p.get('schema_version') != 1 or p.get('active') is not True or
        p.get('revoked') is not False or not p.get('owner_approval_ref') or
        p.get('owner_approved') is not True or
        str(p.get('owner_approval_ref', '')).startswith('PENDING') or p.get('identity') != IDENTITY or
        p.get('images') != IMAGES or p.get('procedures') != list(PROCEDURES) or
        p.get('allowed_operations') != OPERATIONS or p.get('prohibited_operations') != PROHIBITED or
        p.get('required_preflight') != PREFLIGHT or
        p.get('motion_injection_authorized') is not False or
        p.get('serial_reset_risk_accepted') is not True or
        p.get('max_bootstraps_per_session') != 1 or p.get('max_retries') != 0 or
        p.get('max_session_seconds') != 150 or p.get('observation_seconds') != 60 or
        p.get('evidence_directory') != str(STATE) or
        type(p.get('max_sessions')) is not int or not 1 <= p['max_sessions'] <= 30 or
        not start.tzinfo or not end.tzinfo or not start <= now < end or
        end - start > timedelta(days=30)):
        raise ValueError('standing_policy_inactive_expired_or_scope_mismatch')
    for name in ('serial_helper', 'bootstrap_script', 'controller', 'validator'):
        item = p[name]
        target = Path(item['path'])
        if target.is_symlink() or not target.is_absolute() or digest(target) != item['sha256']:
            raise ValueError('standing_policy_procedure_fingerprint_mismatch')
    for role in ('c3', 's3'):
        item = p['image_receipts'][role]
        receipt_path = Path(item['path'])
        if receipt_path.is_symlink() or digest(receipt_path) != item['sha256']:
            raise ValueError('standing_policy_image_receipt_changed')
        receipt = json.loads(receipt_path.read_text())
        if (receipt.get('status') != 'PASS' or receipt.get('role') != role or
            receipt.get('port') != IDENTITY[role]['port'] or
            receipt.get('expected_usb_serial') != IDENTITY[role]['serial_number'] or
            receipt.get('trusted_artifact_sha256') != IMAGES[role] or
            receipt.get('image_match', {}).get('byte_for_byte_match') is not True):
            raise ValueError('standing_policy_image_receipt_invalid')
    return p

@contextmanager
def session(procedure, path=POLICY, state=STATE, *, _development=False):
    """Serialize processes, reserve before access, latch failures/crashes; no automatic retry."""
    state = Path(state)
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    if state.is_symlink() or state.stat().st_uid != os.getuid() or state.stat().st_mode & 0o077:
        raise ValueError('standing_audit_directory_not_private')
    with (state / 'session.lock').open('a') as lock:
        os.chmod(lock.name, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Load after taking the shared lock so revocation cannot race a session
        # reservation and authorize new work from a stale in-memory policy.
        p = load_development(path) if _development else load(path)
        if procedure not in p['procedures']:
            raise ValueError('standing_policy_operation_not_authorized')
        if _development:
            ledger, data, scope_id = _load_development_ledger(path, state, p)
        else:
            ledger = state / (digest(path) + '.json')
            data = json.loads(ledger.read_text()) if ledger.exists() else {'sessions': 0, 'blocked': False}
            scope_id = None
        # Normal campaign FAIL/BLOCKED outcomes are recorded and exit cleanly.
        # Any raised exception remains fail-closed and requires a diagnosed,
        # audited disposition before this scope can be used again.
        session_limit = p.get('max_sessions')
        if (data['blocked'] or
                (session_limit is not None and data['sessions'] >= session_limit) or
                (_development and data.get('consecutive_failures', 0) >= 3)):
            raise ValueError('standing_policy_failure_latched_or_limit_reached')
        data.update(sessions=data['sessions'] + 1, blocked=True, procedure=procedure,
                    started_at=datetime.now(timezone.utc).isoformat(), approval_ref=p['owner_approval_ref'])
        for key in ('completed_at', 'failure', 'failure_class', 'functional_outcome', 'evidence'):
            data.pop(key, None)
        if _development:
            data['authorization_scope_id'] = scope_id
            data['policy_manifest_sha256'] = digest(path)
            counts = data.setdefault('procedure_counts', {})
            counts[procedure] = counts.get(procedure, 0) + 1
        def save():
            temp = ledger.with_suffix('.tmp')
            fd = os.open(temp, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
            with os.fdopen(fd, 'w') as out:
                json.dump(data, out); out.flush(); os.fsync(out.fileno())
            os.replace(temp, ledger)
            fd = os.open(state / 'audit.jsonl', os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
            with os.fdopen(fd, 'a') as out:
                out.write(json.dumps(data) + '\n'); out.flush(); os.fsync(out.fileno())
        save()
        try:
            yield p, data
            if ('functional_outcome' in data and
                    data['functional_outcome'] not in FUNCTIONAL_OUTCOMES):
                raise ValueError('development_functional_outcome_invalid')
        except BaseException as error:
            data['failure'] = type(error).__name__
            data['failure_class'] = ('AUTHORIZATION_SAFETY' if
                                     isinstance(error, AuthorizationSafetyFailure) else
                                     'UNKNOWN_UNHANDLED')
            data.pop('functional_outcome', None)
            data['consecutive_failures'] = data.get('consecutive_failures', 0) + 1
            save()
            raise
        else:
            data.update(blocked=False, consecutive_failures=0, completed_at=datetime.now(timezone.utc).isoformat())
            data.pop('failure', None)
            data.pop('failure_class', None)
            save()

def status():
    try:
        p = load()
        ledger = STATE / (digest(POLICY) + '.json')
        data = json.loads(ledger.read_text()) if ledger.exists() else {'blocked': False, 'sessions': 0}
        if data['blocked'] or data['sessions'] >= p['max_sessions']:
            raise ValueError('standing_policy_failure_latched_or_limit_reached')
        return {'status': 'ACTIVE', 'expires_at': p['expires_at'], 'sessions': data['sessions'],
                'procedures': p['procedures'], 'motion_injection_authorized': False}
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {'status': 'BLOCKED', 'reason': str(error)}


# DEV consent is separate from one-use readiness and all production authority.
DEV_POLICY = POLICY.with_name('development-authorization.json')
DEFAULT_DEV_POLICY = DEV_POLICY
DEV_STATE = STATE.with_name('development-authorization')
DEV_MODE_AUDIT = DEV_STATE / 'audit.jsonl'
DEV_OPERATIONS = ['protected_gs40_bootstrap', 'tc001_campaign', 'observe',
                  'application_flash', 'test_data_erase', 'development_reprovision']
DEV_PROHIBITED = ['efuse', 'permanent_security_change', 'production_credentials',
                  'unknown_hardware', 'non_test_data', 'erase_irreplaceable_trust']
DEV_IMAGES = {
    'c3': '589dc9f98ef78fed97709e2ffb845b0a0eb6ccf5babfd9cc149743539932acb7',
    's3': 'ff1116344cbc05d4c6fcc18a8f003d067b809ef6d90236fd90bba6f86ab052e5',
}
DEV_MODE_AUTHORITY_REFS = {'GS-117': '11852', 'GS-116': '11853', 'GS-130': '11854'}
DEV_MODE_ID = 'GS117_DEFAULT_DEV_MODE_20261030'
DEV_MODE_SCHEMA = 2
DEV_PIN_NAMES = ('serial_helper', 'bootstrap_script', 'bootstrap_evidence_helper',
                 'controller', 'validator')


def _environment_is_release_qualified():
    return os.environ.get('GHAR_SAJAG_QUALIFICATION_MODE', '').strip().upper() in {
        'RELEASE', 'RELEASE_CANDIDATE', 'RC', 'PRODUCTION', 'COMMERCIAL'
    }


def load_development(path=None):
    path = Path(path or DEV_POLICY)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('development_consent_requires_owner_only_file')
    p = json.loads(path.read_text())
    mode = p.get('development_mode')
    if (p.get('schema_version') != DEV_MODE_SCHEMA or p.get('profile') != 'GS117_DEV_TEST_ONLY' or
        p.get('active') is not True or p.get('revoked') is not False or
        p.get('development_mode_enabled') is not True or
        p.get('owner_approved') is not True or not p.get('owner_approval_ref') or
        str(p['owner_approval_ref']).startswith('PENDING') or p.get('identity') != IDENTITY or
        p.get('images') != DEV_IMAGES or
        p.get('procedures') != DEV_OPERATIONS or p.get('allowed_operations') != DEV_OPERATIONS or
        p.get('prohibited_operations') != DEV_PROHIBITED or
        p.get('serial_reset_risk_accepted') is not True or
        p.get('max_sessions') is not None or p.get('motion_injection_authorized') is not True or
        not isinstance(mode, dict) or mode.get('enabled') is not True or
        mode.get('revoked') is not False or mode.get('persistent') is not True or
        mode.get('mode_id') != DEV_MODE_ID or mode.get('expires_at') is not None or
        mode.get('environment') != 'GS117_TEST_ONLY' or
        mode.get('authorization_ref') != p.get('owner_approval_ref') or
        mode.get('authority_refs') != DEV_MODE_AUTHORITY_REFS or
        mode.get('disable_on_release_transition') is not True or
        mode.get('activation_record_sha256') is None or
        not isinstance(mode.get('predecessor'), dict) or
        mode['predecessor'].get('approval_ref') == p.get('owner_approval_ref')):
        raise ValueError('development_consent_scope_mismatch')
    if _environment_is_release_qualified():
        raise ValueError('development_mode_disabled_for_release_qualification')
    activated = datetime.fromisoformat(p['activated_at'])
    if activated.tzinfo is None or activated > datetime.now(timezone.utc):
        raise ValueError('development_consent_invalid_time')
    if (not isinstance(mode.get('activated_at'), str) or
            mode['activated_at'] != p['activated_at'] or
            not isinstance(mode.get('predecessor'), dict)):
        raise ValueError('development_mode_transition_invalid')
    previous = mode['predecessor']
    if (not isinstance(previous.get('approval_ref'), str) or
            not re.fullmatch(r'[0-9a-f]{64}', str(previous.get('scope_id', ''))) or
            type(previous.get('sessions')) is not int or previous['sessions'] < 0 or
            type(previous.get('consecutive_failures')) is not int or
            previous['consecutive_failures'] < 0 or type(previous.get('blocked')) is not bool or
            not re.fullmatch(r'[0-9a-f]{64}', str(previous.get('audit_sha256', ''))) or
            not re.fullmatch(r'[0-9a-f]{64}', str(previous.get('ledger_sha256', '')))):
        raise ValueError('development_mode_predecessor_snapshot_invalid')
    audit_path = Path(p.get('activation_audit_path', ''))
    if path.resolve() == DEFAULT_DEV_POLICY.resolve() and audit_path.resolve() != DEV_MODE_AUDIT.resolve():
        raise ValueError('development_mode_transition_audit_path_mismatch')
    _verify_development_mode_transition(p)
    for name in DEV_PIN_NAMES:
        q = p[name]; target = Path(q['path'])
        if not target.is_absolute() or target.is_symlink() or digest(target) != q['sha256']:
            raise ValueError('development_reviewed_procedure_changed')
    return p


def development_session(procedure):
    p = load_development()
    if procedure in ('application_flash', 'test_data_erase', 'development_reprovision'):
        artifacts = p.get('recovery_artifacts', [])
        if not artifacts or any(Path(q['path']).is_symlink() or digest(q['path']) != q['sha256']
                                for q in artifacts):
            raise ValueError('development_recovery_artifacts_not_verified')
        if procedure == 'test_data_erase':
            value = p.get('pre_erase_evidence')
            if not value or not Path(value).is_absolute() or Path(value).is_symlink() or not Path(value).is_dir():
                raise ValueError('development_pre_erase_evidence_missing')
    return session(procedure, DEV_POLICY, DEV_STATE, _development=True)


def development_status(path=None):
    """Read current mode state and cumulative DEV ledger without reserving a session."""
    path = Path(path or DEV_POLICY)
    policy = load_development(path)
    scope_id = _development_scope_id(policy)
    state = DEV_STATE if path.resolve() == DEV_POLICY.resolve() else path.parent / 'development-authorization'
    history = _development_history(state, policy, scope_id)
    return {
        'status': 'ACTIVE' if not history['blocked'] else 'SAFETY_LATCHED',
        'development_mode_enabled': True,
        'persistent': True,
        'expires_at': None,
        'sessions': history['sessions'],
        'consecutive_safety_failures': history['consecutive_failures'],
        'blocked': history['blocked'],
        'procedures': policy['procedures'],
        'owner_approval_ref': policy['owner_approval_ref'],
        'authorization_scope_id': scope_id,
    }


def revoke_development_mode(reason, path=None):
    """Revoke the current mode once, durably auditing the disable before returning."""
    path = Path(path or DEV_POLICY)
    if (not isinstance(reason, str) or not reason.strip() or len(reason) > 240 or
            any(ord(char) < 32 for char in reason)):
        raise ValueError('development_mode_revocation_reason_required')
    state = DEV_STATE if path.resolve() == DEV_POLICY.resolve() else path.parent / 'development-authorization'
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    if state.is_symlink() or state.stat().st_uid != os.getuid() or state.stat().st_mode & 0o077:
        raise ValueError('standing_audit_directory_not_private')
    lock_path = state / 'session.lock'
    with lock_path.open('a') as lock:
        os.chmod(lock.name, 0o600)
        # Let an already-reserved bounded operation finish, then revoke under
        # the same lock. Revocation must remain available even if source pins
        # are stale or the environment has entered release qualification.
        fcntl.flock(lock, fcntl.LOCK_EX)
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('development_consent_requires_owner_only_file')
        policy = json.loads(path.read_text())
        mode = policy.get('development_mode')
        if (policy.get('schema_version') != DEV_MODE_SCHEMA or
                policy.get('profile') != 'GS117_DEV_TEST_ONLY' or
                policy.get('development_mode_enabled') is not True or
                not isinstance(mode, dict) or mode.get('enabled') is not True or
                mode.get('revoked') is not False):
            raise ValueError('development_mode_not_active')
        _verify_development_mode_transition(policy, allow_source_pin_drift=True)
        record = {
            'event': 'development_mode_revoked',
            'activation_id': mode['activation_id'],
            'revocation_id': secrets.token_hex(16),
            'approval_ref': policy['owner_approval_ref'],
            'at_utc': datetime.now(timezone.utc).isoformat(),
            'reason': reason.strip(),
            'policy_manifest_sha256': digest(path),
        }
        record['record_sha256'] = _canonical_record_sha256(record)
        _append_private_audit(policy['activation_audit_path'], record)
        updated = json.loads(path.read_text())
        updated.update(active=False, revoked=True, development_mode_enabled=False)
        updated['development_mode'].update(enabled=False, revoked=True,
                                            revoked_at=record['at_utc'],
                                            revocation_id=record['revocation_id'],
                                            revocation_record_sha256=record['record_sha256'])
        _atomic_private_json(path, updated)
        return {'status': 'REVOKED', 'revocation_id': record['revocation_id'],
                'record_sha256': record['record_sha256']}
