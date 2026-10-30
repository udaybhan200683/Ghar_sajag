"""Local owner consent for existing GS-117 readiness procedures; no technical waiver."""
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
import fcntl
import hashlib
import json
import os
from pathlib import Path
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
        for name in ('procedure', 'started_at', 'completed_at', 'failure', 'evidence'):
            if (name in latest_record and
                    (name != 'failure' or blocked) and
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
    p = load_development(path) if _development else load(path)
    if procedure not in p['procedures']:
        raise ValueError('standing_policy_operation_not_authorized')
    state = Path(state)
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    if state.is_symlink() or state.stat().st_uid != os.getuid() or state.stat().st_mode & 0o077:
        raise ValueError('standing_audit_directory_not_private')
    with (state / 'session.lock').open('a') as lock:
        os.chmod(lock.name, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if _development:
            ledger, data, scope_id = _load_development_ledger(path, state, p)
        else:
            ledger = state / (digest(path) + '.json')
            data = json.loads(ledger.read_text()) if ledger.exists() else {'sessions': 0, 'blocked': False}
            scope_id = None
        if ((data['blocked'] and not _development) or data['sessions'] >= p['max_sessions'] or
                (_development and data.get('consecutive_failures', 0) >= 3)):
            raise ValueError('standing_policy_failure_latched_or_limit_reached')
        data.update(sessions=data['sessions'] + 1, blocked=True, procedure=procedure,
                    started_at=datetime.now(timezone.utc).isoformat(), approval_ref=p['owner_approval_ref'])
        for key in ('completed_at', 'failure', 'evidence'):
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
        except BaseException as error:
            data['failure'] = type(error).__name__
            data['consecutive_failures'] = data.get('consecutive_failures', 0) + 1
            save()
            raise
        else:
            data.update(blocked=False, consecutive_failures=0, completed_at=datetime.now(timezone.utc).isoformat())
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
DEV_STATE = STATE.with_name('development-authorization')
DEV_OPERATIONS = ['protected_gs40_bootstrap', 'tc001_campaign', 'observe',
                  'application_flash', 'test_data_erase', 'development_reprovision']
DEV_PROHIBITED = ['efuse', 'permanent_security_change', 'production_credentials',
                  'unknown_hardware', 'non_test_data', 'erase_irreplaceable_trust']


def load_development(path=None):
    path = Path(path or DEV_POLICY)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('development_consent_requires_owner_only_file')
    p = json.loads(path.read_text())
    if (p.get('schema_version') != 1 or p.get('profile') != 'GS117_DEV_TEST_ONLY' or
        p.get('active') is not True or p.get('revoked') is not False or
        p.get('owner_approved') is not True or not p.get('owner_approval_ref') or
        str(p['owner_approval_ref']).startswith('PENDING') or p.get('identity') != IDENTITY or
        p.get('procedures') != DEV_OPERATIONS or p.get('allowed_operations') != DEV_OPERATIONS or
        p.get('prohibited_operations') != DEV_PROHIBITED or
        p.get('serial_reset_risk_accepted') is not True or
        p.get('max_sessions') != 1000 or p.get('motion_injection_authorized') is not True):
        raise ValueError('development_consent_scope_mismatch')
    activated = datetime.fromisoformat(p['activated_at'])
    if activated.tzinfo is None or activated > datetime.now(timezone.utc):
        raise ValueError('development_consent_invalid_time')
    for name in ('serial_helper', 'bootstrap_script', 'bootstrap_evidence_helper', 'controller', 'validator'):
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
