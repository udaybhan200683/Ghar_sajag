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
        ledger = state / (digest(path) + '.json')
        data = json.loads(ledger.read_text()) if ledger.exists() else {'sessions': 0, 'blocked': False}
        if ((data['blocked'] and not _development) or data['sessions'] >= p['max_sessions'] or
                (_development and data.get('consecutive_failures', 0) >= 3)):
            raise ValueError('standing_policy_failure_latched_or_limit_reached')
        data.update(sessions=data['sessions'] + 1, blocked=True, procedure=procedure,
                    started_at=datetime.now(timezone.utc).isoformat(), approval_ref=p['owner_approval_ref'])
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
