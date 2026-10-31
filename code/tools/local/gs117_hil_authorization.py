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
import subprocess
import sys

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


def _development_scope_contract_sha256(policy):
    """Bind reviewed pin maintenance to the active TEST_ONLY scope.

    Source hashes are the only mutable policy fields in this contract. Paths,
    identities, images, owner authority, operation limits, and prohibitions are
    included so a source update cannot be used to rotate authorization scope.
    """
    value = json.loads(json.dumps(policy))
    for name in DEV_PIN_NAMES:
        if isinstance(value.get(name), dict):
            value[name].pop('sha256', None)
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(encoded).hexdigest()


def _read_review_receipt(path, expected_sha256):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('development_source_review_receipt_invalid')
    try:
        info = path.lstat()
    except OSError as error:
        raise ValueError('development_source_review_receipt_invalid') from error
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or
            info.st_mode & 0o077 or digest(path) != expected_sha256):
        raise ValueError('development_source_review_receipt_invalid')
    try:
        receipt = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError('development_source_review_receipt_invalid') from error
    required = {'gs117_focused', 'feature_coverage'}
    tests = receipt.get('tests') if isinstance(receipt, dict) else None
    if (not isinstance(receipt, dict) or receipt.get('schema_version') != 1 or
            not re.fullmatch(r'[0-9a-f]{40}', str(receipt.get('reviewed_commit', ''))) or
            not isinstance(tests, list) or
            {item.get('name') for item in tests if isinstance(item, dict)} != required or
            any(item.get('returncode') != 0 or
                not re.fullmatch(r'[0-9a-f]{64}', str(item.get('stdout_sha256', ''))) or
                not re.fullmatch(r'[0-9a-f]{64}', str(item.get('stderr_sha256', '')))
                for item in tests if isinstance(item, dict)) or
            len(tests) != len(required) or
            not isinstance(receipt.get('reviewed_negative_tests'), list) or
            any(not isinstance(item, str) for item in receipt['reviewed_negative_tests'])):
        raise ValueError('development_source_review_receipt_invalid')
    if receipt.get('reviewed_negative_tests') != sorted(set(receipt['reviewed_negative_tests'])):
        raise ValueError('development_source_review_receipt_invalid')
    expected_commands = {
        'gs117_focused': ['code/tests/python/test_gs117_tc001_console.py'],
        'feature_coverage': ['make', '-C', 'code', 'feature-coverage-test'],
    }
    for test in tests:
        command = test.get('command') if isinstance(test, dict) else None
        if (not isinstance(command, list) or not command or
                type(test.get('test_count')) is not int or test['test_count'] < 1 or
                (test['name'] == 'gs117_focused' and
                 (not Path(command[0]).name.startswith('python3') or
                  command[1:] != expected_commands['gs117_focused'])) or
                (test['name'] == 'feature_coverage' and
                 (command != expected_commands['feature_coverage'] or
                  not re.fullmatch(r'GS130 TRACEABILITY PASS features=[1-9][0-9]* modules=[1-9][0-9]* physical_cases=[1-9][0-9]*; consistency only, not semantic/physical PASS',
                                   str(test.get('coverage_summary', '')))))):
            raise ValueError('development_source_review_receipt_invalid')
    if receipt.get('reviewed_negative_tests') != sorted(set(receipt['reviewed_negative_tests'])):
        raise ValueError('development_source_review_receipt_invalid')
    return receipt


def _verify_development_source_review_chain(policy, mode, records, activation_line,
                                           allow_source_pin_drift=False):
    pins = dict(mode['reviewed_source_fingerprints'])
    previous_record_sha256 = mode['activation_record_sha256']
    scope_sha256 = _development_scope_contract_sha256(policy)
    updates = []
    for index, row in enumerate(records):
        if index <= activation_line or row.get('event') != 'development_mode_source_reviewed':
            continue
        record = dict(row)
        record_sha256 = record.pop('record_sha256', None)
        source_before = record.get('source_pins_before')
        source_after = record.get('source_pins_after')
        changed = {name for name in DEV_PIN_NAMES
                   if isinstance(source_after, dict) and source_after.get(name) != pins.get(name)}
        receipt_path = record.get('test_receipt_path')
        if (record.get('activation_id') != mode.get('activation_id') or
                record.get('approval_ref') != policy.get('owner_approval_ref') or
                record.get('chain_previous_sha256') != previous_record_sha256 or
                record.get('scope_contract_sha256') != scope_sha256 or
                source_before != pins or not isinstance(source_after, dict) or
                set(source_after) != set(DEV_PIN_NAMES) or not changed or
                record.get('changed_sources') != sorted(changed) or
                any(not re.fullmatch(r'[0-9a-f]{64}', str(source_after[name]))
                    for name in DEV_PIN_NAMES) or
                record.get('source_paths') != {name: policy[name].get('path') for name in DEV_PIN_NAMES} or
                not isinstance(record.get('review_summary'), str) or
                len(record['review_summary'].strip()) < 32 or
                not re.fullmatch(r'[0-9a-f]{40}', str(record.get('reviewed_commit', ''))) or
                not isinstance(receipt_path, str) or
                not re.fullmatch(r'[0-9a-f]{64}', str(record.get('test_receipt_sha256', ''))) or
                record_sha256 != _canonical_record_sha256(row)):
            raise ValueError('development_mode_source_review_chain_invalid')
        receipt = _read_review_receipt(receipt_path, record['test_receipt_sha256'])
        if Path(receipt_path).parent.resolve() != \
                Path(policy.get('activation_audit_path', '')).parent.resolve():
            raise ValueError('development_source_review_receipt_invalid')
        backup_path = Path(str(record.get('previous_manifest_backup_path', '')))
        try:
            backup_info = backup_path.lstat()
            backup_policy = json.loads(backup_path.read_text())
            if (not isinstance(backup_policy, dict) or
                    not isinstance(backup_policy.get('development_mode'), dict) or
                    any(not isinstance(backup_policy.get(name), dict)
                        for name in DEV_PIN_NAMES)):
                raise ValueError('development_source_review_manifest_backup_invalid')
            backup_valid = (
                stat.S_ISREG(backup_info.st_mode) and backup_info.st_uid == os.getuid() and
                not (backup_info.st_mode & 0o077) and
                backup_path.parent.resolve() ==
                Path(policy.get('activation_audit_path', '')).parent.resolve() and
                re.fullmatch(r'development-policy-before-source-review-[0-9a-f]{24}\.json',
                             backup_path.name) and
                digest(backup_path) == record.get('previous_manifest_sha256') and
                _development_scope_contract_sha256(backup_policy) == scope_sha256 and
                {name: backup_policy.get(name, {}).get('sha256') for name in DEV_PIN_NAMES} ==
                source_before)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            backup_valid = False
            backup_policy = {}
        if (not backup_valid or
                backup_policy.get('development_mode', {}).get('activation_id') !=
                mode.get('activation_id')):
            raise ValueError('development_source_review_manifest_backup_invalid')
        if (receipt.get('reviewed_commit') != record.get('reviewed_commit') or
                receipt.get('scope_contract_sha256') != scope_sha256 or
                receipt.get('reviewed_negative_tests') != record.get('reviewed_negative_tests')):
            raise ValueError('development_source_review_receipt_invalid')
        if 'validator' in changed or 'controller' in changed:
            required_negative = {
                'test_dev_consent_revocation_identity_and_procedure_guards',
                'test_activation_record_binds_reviewed_commit_and_source_pins',
                'test_campaign_safety_failure_latches_and_denies_next_operation',
            }
            if not required_negative.issubset(set(record.get('reviewed_negative_tests', []))) or \
                    not required_negative.issubset(set(receipt.get('reviewed_negative_tests', []))):
                raise ValueError('development_source_review_negative_tests_missing')
        if 'bootstrap_script' in changed:
            replacement = record.get('bootstrap_pin_replacement')
            backup = Path(replacement.get('backup_path', '')) if isinstance(replacement, dict) else Path('/')
            try:
                backup_info = backup.lstat()
                backup_valid = (stat.S_ISREG(backup_info.st_mode) and backup_info.st_uid == os.getuid() and
                                not (backup_info.st_mode & 0o077) and
                                digest(backup) == replacement.get('backup_sha256') and
                                backup.parent.resolve() ==
                                Path(record['source_paths']['bootstrap_script']).parent.resolve())
                old_bootstrap = backup.read_text()
                current_bootstrap = Path(record['source_paths']['bootstrap_script']).read_text()
            except (OSError, ValueError, TypeError):
                backup_valid = False
                old_bootstrap = current_bootstrap = ''
            if (not isinstance(replacement, dict) or
                    not backup_valid or
                    backup.parent.resolve() != Path(record['source_paths']['bootstrap_script']).parent.resolve() or
                    replacement.get('embedded_old_helper_sha256') !=
                    '66afe888be5dcd3c862bcddc4cc6333945870b8a41bd552f9cb0e3472676058e' or
                    replacement.get('embedded_new_helper_sha256') != pins.get('serial_helper') or
                    replacement.get('old_file_sha256') != pins.get('bootstrap_script') or
                    replacement.get('new_file_sha256') != source_after.get('bootstrap_script') or
                    old_bootstrap.count(replacement.get('embedded_old_helper_sha256', '')) != 1 or
                    current_bootstrap != old_bootstrap.replace(
                        replacement.get('embedded_old_helper_sha256', ''),
                        replacement.get('embedded_new_helper_sha256', ''), 1)):
                raise ValueError('development_source_review_bootstrap_change_unreviewed')
        pins = dict(source_after)
        previous_record_sha256 = record_sha256
        updates.append(row)
    current = {name: policy.get(name, {}).get('sha256') for name in DEV_PIN_NAMES}
    if current != pins and not allow_source_pin_drift:
        raise ValueError('development_mode_review_evidence_invalid' if not updates else
                         'development_mode_source_review_chain_mismatch')
    if (updates and not allow_source_pin_drift and
            hashlib.sha256(json.dumps(policy, sort_keys=True).encode()).hexdigest() !=
            updates[-1].get('policy_sha256_after')):
        raise ValueError('development_mode_source_review_manifest_mismatch')
    return updates


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
    audit_records = []
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
            audit_records.append(record)
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
        if latest_record.get('event') == 'development_failure_disposition':
            if len(entries) < 2:
                raise ValueError('development_authorization_history_corrupt')
            failed_record = entries[-2][1]
            _validate_pin_failure_disposition(latest_record, failed_record, audit_records)
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

    dispositions = [row for row in audit_records
                    if row.get('event') == 'development_failure_disposition' and
                    row.get('approval_ref') == approval_ref]
    history = {
        'sessions': len(ordered), 'blocked': blocked,
        'consecutive_failures': consecutive,
        'procedure_counts': procedure_counts,
        'approval_ref': approval_ref,
        'authorization_scope_id': scope_id,
        'reviewed_failure_dispositions': len(dispositions),
    }
    if dispositions:
        history['failure_disposition'] = dispositions[-1].get('disposition')
    if latest_record:
        for name in ('procedure', 'started_at', 'completed_at', 'failure', 'failure_class',
                     'functional_outcome', 'evidence'):
            if (name in latest_record and
                    (name not in ('failure', 'failure_class') or blocked) and
                    (name != 'functional_outcome' or not blocked) and
                    (name != 'completed_at' or not blocked)):
                history[name] = latest_record[name]
        if latest_record.get('event') == 'development_failure_disposition':
            history['failure_disposition'] = latest_record['disposition']
    return history


def _validate_pin_failure_disposition(disposition, failed_record, audit_records):
    record_sha256 = disposition.get('record_sha256')
    evidence = Path(str(disposition.get('evidence', '')))
    expected_parent = Path(STATE)
    review_sha = disposition.get('source_review_record_sha256')
    matching_reviews = [row for row in audit_records
                        if row.get('event') == 'development_mode_source_reviewed' and
                        row.get('record_sha256') == review_sha]
    try:
        info = evidence.lstat()
        stdout_path = evidence / 'stdout.json'
        stderr_path = evidence / 'stderr.log'
        stdout = stdout_path.read_text()
        stderr = stderr_path.read_text()
        evidence_private = (stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and
                            info.st_mode & 0o077 == 0 and evidence.parent.resolve() == expected_parent.resolve())
        evidence_matches = (
            stdout == 'BOOTSTRAP_FAILED_STAGE=startup TYPE=ValueError CODE=REVIEWED_SERIAL_HELPER_CHANGED\n' and
            stderr == '' and digest(stdout_path) == disposition.get('stdout_sha256') and
            digest(stderr_path) == disposition.get('stderr_sha256'))
    except OSError:
        evidence_private = evidence_matches = False
    if (disposition.get('disposition') != 'REVIEWED_PRE_OPERATION_PIN_MISMATCH' or
            disposition.get('failure') != 'ValueError' or
            disposition.get('failure_code') != 'REVIEWED_SERIAL_HELPER_CHANGED' or
            disposition.get('failure_class') != 'REVIEWED_PRE_OPERATION_CONFIGURATION' or
            disposition.get('blocked') is not False or
            disposition.get('functional_outcome') != 'NOT_RUN' or
            failed_record.get('blocked') is not True or
            failed_record.get('procedure') != 'protected_gs40_bootstrap' or
            failed_record.get('approval_ref') != disposition.get('approval_ref') or
            failed_record.get('started_at') != disposition.get('started_at') or
            failed_record.get('failure') != 'ValueError' or
            failed_record.get('failure_class') != 'UNKNOWN_UNHANDLED' or
            disposition.get('disposition_of_sha256') != _canonical_record_sha256(failed_record) or
            disposition.get('evidence') != failed_record.get('evidence') or
            not evidence_private or not evidence_matches or len(matching_reviews) != 1 or
            matching_reviews[0].get('activation_id') != disposition.get('activation_id') or
            matching_reviews[0].get('changed_sources') != ['bootstrap_script', 'validator'] or
            matching_reviews[0].get('reviewed_commit') != disposition.get('reviewed_commit') or
            not re.fullmatch(r'[0-9a-f]{40}', str(disposition.get('reviewed_commit', ''))) or
            not re.fullmatch(r'[0-9a-f]{64}', str(record_sha256 or '')) or
            record_sha256 != _canonical_record_sha256(disposition)):
        raise ValueError('development_authorization_history_mismatch')


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
    activation_record_index = next(index for index, row in enumerate(records)
                                   if row.get('event') == 'development_mode_activated' and
                                   row.get('activation_id') == activation_id)
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
    _verify_development_source_review_chain(
        policy, mode, records, activation_record_index,
        allow_source_pin_drift=allow_source_pin_drift)
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
        if _development:
            procedure_limit = p.get('procedure_session_limits', {}).get(procedure)
            procedure_count = data.get('procedure_counts', {}).get(procedure, 0)
            if procedure_limit is not None and procedure_count >= procedure_limit:
                raise ValueError('standing_policy_procedure_limit_reached')
        data.update(sessions=data['sessions'] + 1, blocked=True, procedure=procedure,
                    started_at=datetime.now(timezone.utc).isoformat(), approval_ref=p['owner_approval_ref'])
        for key in ('completed_at', 'failure', 'failure_class', 'functional_outcome', 'evidence',
                    'failure_disposition', 'reviewed_failure_dispositions'):
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


def _development_operation_scope_valid(policy):
    """Validate an explicit, bounded allowlist for an owner-approved DEV scope."""
    procedures = policy.get('procedures')
    if (not isinstance(procedures, list) or not procedures or
            procedures != [name for name in DEV_OPERATIONS if name in procedures] or
            policy.get('allowed_operations') != procedures):
        return False
    max_sessions = policy.get('max_sessions')
    if (max_sessions is not None and
            (type(max_sessions) is not int or not 1 <= max_sessions <= 30)):
        return False
    if procedures != DEV_OPERATIONS and max_sessions is None:
        return False
    procedure_limits = policy.get('procedure_session_limits')
    if procedures != DEV_OPERATIONS:
        if (not isinstance(procedure_limits, dict) or
                set(procedure_limits) != set(procedures) or
                any(type(limit) is not int or not 1 <= limit <= max_sessions
                    for limit in procedure_limits.values()) or
                sum(procedure_limits.values()) != max_sessions):
            return False
    elif procedure_limits is not None:
        if (not isinstance(procedure_limits, dict) or
                set(procedure_limits) != set(procedures) or
                any(type(limit) is not int or limit < 1 for limit in procedure_limits.values()) or
                (max_sessions is not None and sum(procedure_limits.values()) != max_sessions)):
            return False
    expected_motion = 'tc001_campaign' in procedures
    return (type(policy.get('motion_injection_authorized')) is bool and
            policy.get('motion_injection_authorized') == expected_motion)


def _validate_development_pin_paths(path, policy):
    """Keep the active DEV manifest bound to existing GS-117 procedures."""
    path = Path(path)
    if path.resolve() != DEFAULT_DEV_POLICY.resolve():
        return
    root = Path(__file__).resolve().parents[3]
    expected = {
        'serial_helper': root / 'code/tools/local/gs117_tc001_serial_windows.py',
        'bootstrap_evidence_helper': root / 'code/tools/local/gs117_bootstrap_evidence.py',
        'controller': root / 'code/tools/local/gs117_tc001_console.py',
        'validator': root / 'code/tools/local/gs117_hil_authorization.py',
    }
    for name, expected_path in expected.items():
        if Path(policy[name].get('path', '')).resolve() != expected_path.resolve():
            raise ValueError('development_reviewed_procedure_path_mismatch')
    bootstrap_path = Path(policy['bootstrap_script'].get('path', ''))
    prepared = Path.home() / '.local/state/ghar-sajag/gs117-tc001/standing-readiness-prepared'
    if (not bootstrap_path.is_absolute() or bootstrap_path.is_symlink() or
            bootstrap_path.parent.resolve() != prepared.resolve() or
            not re.fullmatch(r'gs117-protected-bootstrap-development-v[0-9]+\.py',
                             bootstrap_path.name)):
        raise ValueError('development_reviewed_procedure_path_mismatch')


def load_development(path=None, *, verify_procedure_pins=True):
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
        p.get('images') != DEV_IMAGES or not _development_operation_scope_valid(p) or
        p.get('prohibited_operations') != DEV_PROHIBITED or
        p.get('serial_reset_risk_accepted') is not True or
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
    _validate_development_pin_paths(path, p)
    if verify_procedure_pins:
        for name in DEV_PIN_NAMES:
            q = p[name]; target = Path(q['path'])
            if (not target.is_absolute() or target.is_symlink() or
                    not target.is_file() or digest(target) != q['sha256']):
                raise ValueError('development_reviewed_procedure_changed')
    return p


def _current_development_commit(repo):
    top = subprocess.run(['git', 'rev-parse', '--show-toplevel'], cwd=repo,
                         capture_output=True, text=True, timeout=10)
    branch = subprocess.run(['git', 'branch', '--show-current'], cwd=repo,
                            capture_output=True, text=True, timeout=10)
    if (top.returncode != 0 or Path(top.stdout.strip()).resolve() != Path(repo).resolve() or
            branch.returncode != 0 or branch.stdout.strip() != 'feature/r1-commercial-baseline'):
        raise ValueError('development_source_review_wrong_repository_or_branch')
    result = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=repo,
                            capture_output=True, text=True, timeout=10)
    value = result.stdout.strip()
    if (result.returncode != 0 or not re.fullmatch(r'[0-9a-f]{40}', value)):
        raise ValueError('development_source_review_commit_unavailable')
    dirty = subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--'], cwd=repo,
                           capture_output=True, text=True, timeout=10)
    if dirty.returncode != 0:
        raise ValueError('development_source_review_requires_committed_source')
    return value


def _run_development_review_tests(repo, reviewed_commit, scope_sha256,
                                 reviewed_negative_tests):
    commands = [
        ('gs117_focused', [sys.executable, 'code/tests/python/test_gs117_tc001_console.py']),
        ('feature_coverage', ['make', '-C', 'code', 'feature-coverage-test']),
    ]
    results = []
    for name, command in commands:
        result = subprocess.run(command, cwd=repo, capture_output=True, text=True,
                                timeout=900)
        output = result.stdout + '\n' + result.stderr
        test_summary = re.search(r'^Ran ([1-9][0-9]*) tests? in ', output, re.MULTILINE)
        coverage_summary = re.search(
            r'^GS130 TRACEABILITY PASS features=[1-9][0-9]* modules=[1-9][0-9]* physical_cases=[1-9][0-9]*; consistency only, not semantic/physical PASS$',
            output, re.MULTILINE)
        if result.returncode == 0 and (not test_summary or re.search(r'\bskipped\s*=\s*[1-9]', output) or
                                       (name == 'feature_coverage' and not coverage_summary)):
            raise ValueError('development_source_review_tests_incomplete:' + name)
        results.append({
            'name': name, 'command': command, 'returncode': result.returncode,
            'test_count': int(test_summary.group(1)) if test_summary else 0,
            'stdout_sha256': hashlib.sha256(result.stdout.encode()).hexdigest(),
            'stderr_sha256': hashlib.sha256(result.stderr.encode()).hexdigest(),
        })
        if coverage_summary:
            results[-1]['coverage_summary'] = coverage_summary.group(0)
        if result.returncode != 0:
            raise ValueError('development_source_review_tests_failed:' + name)
    return {
        'schema_version': 1, 'reviewed_commit': reviewed_commit,
        'scope_contract_sha256': scope_sha256,
        'reviewed_negative_tests': sorted(set(reviewed_negative_tests)),
        'created_at': datetime.now(timezone.utc).isoformat(), 'tests': results,
    }


def review_development_source_updates(review_summary, reviewed_negative_tests,
                                     bootstrap_backup=None, path=None):
    """Commit-, test-, and scope-bound pin maintenance; never grants a session.

    The updater changes only SHA-256 values for the five existing procedure
    paths. The active identity, operation list, consent, policy path, and
    release transition remain fixed. Authorization-module/controller changes
    require explicit review notes and named negative tests.
    """
    path = Path(path or DEV_POLICY)
    audit_path = Path(path.parent / 'development-authorization' / 'audit.jsonl')
    if path.resolve() == DEFAULT_DEV_POLICY.resolve():
        audit_path = DEV_MODE_AUDIT
    state = audit_path.parent
    if (not isinstance(review_summary, str) or len(review_summary.strip()) < 32 or
            not isinstance(reviewed_negative_tests, (list, tuple)) or
            any(not isinstance(name, str) for name in reviewed_negative_tests)):
        raise ValueError('development_source_review_details_required')
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    if state.is_symlink() or state.stat().st_uid != os.getuid() or state.stat().st_mode & 0o077:
        raise ValueError('standing_audit_directory_not_private')
    lock_path = state / 'session.lock'
    with lock_path.open('a') as lock:
        os.chmod(lock.name, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('development_source_review_session_active') from error
        policy = load_development(path, verify_procedure_pins=False)
        _validate_development_pin_paths(path, policy)
        old_pins = {name: policy[name]['sha256'] for name in DEV_PIN_NAMES}
        old_paths = {name: policy[name]['path'] for name in DEV_PIN_NAMES}
        actual_pins = {}
        for name in DEV_PIN_NAMES:
            target = Path(old_paths[name])
            if (not target.is_absolute() or target.is_symlink() or not target.is_file() or
                    target.stat().st_uid != os.getuid() and name == 'bootstrap_script'):
                raise ValueError('development_source_review_source_invalid:' + name)
            actual_pins[name] = digest(target)
        changed = {name for name in DEV_PIN_NAMES if old_pins[name] != actual_pins[name]}
        if not changed:
            raise ValueError('development_source_review_no_pin_changes')
        if 'bootstrap_script' in changed:
            backup = Path(bootstrap_backup or '')
            if backup.is_symlink() or not backup.is_file():
                raise ValueError('development_source_review_bootstrap_backup_required')
            info = backup.lstat()
            old_text = backup.read_text()
            new_text = Path(old_paths['bootstrap_script']).read_text()
            helper_hash = actual_pins['serial_helper']
            stale = '66afe888be5dcd3c862bcddc4cc6333945870b8a41bd552f9cb0e3472676058e'
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or
                    digest(backup) != old_pins['bootstrap_script'] or
                    old_text.count(stale) != 1 or
                    new_text != old_text.replace(stale, helper_hash, 1) or
                    actual_pins['serial_helper'] != old_pins['serial_helper']):
                raise ValueError('development_source_review_bootstrap_change_unreviewed')
        sensitive = changed.intersection({'controller', 'validator'})
        required_negative = {
            'test_dev_consent_revocation_identity_and_procedure_guards',
            'test_activation_record_binds_reviewed_commit_and_source_pins',
            'test_campaign_safety_failure_latches_and_denies_next_operation',
        }
        if sensitive and not required_negative.issubset(set(reviewed_negative_tests)):
            raise ValueError('development_source_review_negative_tests_missing')
        repo = Path(__file__).resolve().parents[3]
        test_source = repo / 'code/tests/python/test_gs117_tc001_console.py'
        try:
            registered_tests = set(re.findall(
                r'^\s*def\s+(test_[A-Za-z0-9_]+)\s*\(',
                test_source.read_text(), re.MULTILINE))
        except OSError as error:
            raise ValueError('development_source_review_tests_unavailable') from error
        if not set(reviewed_negative_tests).issubset(registered_tests):
            raise ValueError('development_source_review_negative_test_unregistered')
        commit = _current_development_commit(repo)
        scope_sha256 = _development_scope_contract_sha256(policy)
        receipt = _run_development_review_tests(
            repo, commit, scope_sha256, reviewed_negative_tests)
        if (_current_development_commit(repo) != commit or
                any(digest(old_paths[name]) != actual_pins[name] for name in DEV_PIN_NAMES)):
            raise ValueError('development_source_review_commit_changed_during_validation')
        receipt_path = state / ('source-review-' + secrets.token_hex(12) + '.json')
        _atomic_private_json(receipt_path, receipt)
        receipt_sha256 = digest(receipt_path)
        previous_manifest_sha256 = digest(path)
        backup_path = state / ('development-policy-before-source-review-' + secrets.token_hex(12) + '.json')
        raw_policy = path.read_bytes()
        if hashlib.sha256(raw_policy).hexdigest() != previous_manifest_sha256:
            raise ValueError('development_source_review_manifest_changed_during_validation')
        fd = os.open(backup_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'wb') as out:
            out.write(raw_policy)
            out.flush()
            os.fsync(out.fileno())
        directory_fd = os.open(state, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        updated = json.loads(json.dumps(policy))
        for name in DEV_PIN_NAMES:
            updated[name]['sha256'] = actual_pins[name]
        existing_records = _read_private_audit(audit_path)
        activation = next(row for row in existing_records
                          if row.get('event') == 'development_mode_activated' and
                          row.get('activation_id') == policy['development_mode']['activation_id'])
        previous_review = next((row for row in reversed(existing_records)
                                if row.get('event') == 'development_mode_source_reviewed' and
                                row.get('activation_id') == policy['development_mode']['activation_id']), None)
        chain_previous = ((previous_review or activation).get('record_sha256'))
        new_pins = dict(actual_pins)
        record = {
            'event': 'development_mode_source_reviewed',
            'activation_id': policy['development_mode']['activation_id'],
            'approval_ref': policy['owner_approval_ref'],
            'chain_previous_sha256': chain_previous,
            'scope_contract_sha256': scope_sha256,
            'source_pins_before': old_pins, 'source_pins_after': new_pins,
            'source_paths': old_paths, 'changed_sources': sorted(changed),
            'reviewed_commit': commit,
            'review_summary': review_summary.strip(),
            'reviewed_negative_tests': sorted(set(reviewed_negative_tests)),
            'test_receipt_path': str(receipt_path),
            'test_receipt_sha256': receipt_sha256,
            'previous_manifest_backup_path': str(backup_path),
            'previous_manifest_sha256': previous_manifest_sha256,
            'at_utc': datetime.now(timezone.utc).isoformat(),
        }
        if 'bootstrap_script' in changed:
            record['bootstrap_pin_replacement'] = {
                'embedded_old_helper_sha256': stale,
                'embedded_new_helper_sha256': actual_pins['serial_helper'],
                'old_file_sha256': old_pins['bootstrap_script'],
                'new_file_sha256': actual_pins['bootstrap_script'],
                'backup_path': str(Path(bootstrap_backup)),
                'backup_sha256': digest(bootstrap_backup),
            }
        record['record_sha256'] = _canonical_record_sha256(record)
        updated_sha256 = hashlib.sha256(
            json.dumps(updated, sort_keys=True).encode()).hexdigest()
        record['policy_sha256_after'] = updated_sha256
        record['record_sha256'] = _canonical_record_sha256(record)
        _append_private_audit(audit_path, record)
        _atomic_private_json(path, updated)
        return {
            'status': 'SOURCE_UPDATE_RECORDED', 'reviewed_commit': commit,
            'changed_sources': sorted(changed), 'sessions_preserved': True,
            'safety_latch_unchanged': True, 'policy_sha256': digest(path),
            'review_record_sha256': record['record_sha256'],
            'test_receipt_sha256': receipt_sha256,
        }


def dispose_reviewed_preoperation_pin_failure(path=None):
    """Resolve only the proven stale nested serial-helper pin failure.

    This appends a disposition for the exact startup-only failure. It does not
    delete the failed session, change its original audit row, reduce its session
    count, or authorize a hardware operation by itself.
    """
    path = Path(path or DEV_POLICY)
    audit_path = Path(path.parent / 'development-authorization' / 'audit.jsonl')
    if path.resolve() == DEFAULT_DEV_POLICY.resolve():
        audit_path = DEV_MODE_AUDIT
    state = audit_path.parent
    lock_path = state / 'session.lock'
    with lock_path.open('a') as lock:
        os.chmod(lock.name, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('development_failure_disposition_session_active') from error
        policy = load_development(path)
        scope_id = _development_scope_id(policy)
        history = _development_history(state, policy, scope_id)
        if history.get('failure_disposition') == 'REVIEWED_PRE_OPERATION_PIN_MISMATCH':
            ledger_path, _ = _development_ledger_path(state, policy)
            if ledger_path.exists():
                current_ledger = _read_private_json(ledger_path)
                if (current_ledger.get('authorization_scope_id') != scope_id or
                        current_ledger.get('approval_ref') != policy['owner_approval_ref']):
                    raise ValueError('development_authorization_history_mismatch')
                backup = ledger_path.with_name(ledger_path.name + '.before-reviewed-disposition-' +
                                               secrets.token_hex(6))
                fd = os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(fd, 'wb') as out:
                    out.write(ledger_path.read_bytes()); out.flush(); os.fsync(out.fileno())
            history['policy_manifest_sha256'] = digest(path)
            _write_private_ledger(ledger_path, history)
            return {'status': 'DISPOSITION_ALREADY_RECORDED', 'sessions': history['sessions'],
                    'consecutive_safety_failures': history['consecutive_failures'],
                    'functional_outcome': history.get('functional_outcome'),
                    'failure_disposition': history.get('failure_disposition')}
        if (history.get('sessions') != 1 or not history.get('blocked') or
                history.get('failure') != 'ValueError' or
                history.get('failure_class') != 'UNKNOWN_UNHANDLED' or
                history.get('procedure') != 'protected_gs40_bootstrap'):
            raise ValueError('development_preoperation_failure_not_disposition_eligible')
        records = _read_private_audit(audit_path)
        starts = [row.get('started_at') for row in records
                  if row.get('approval_ref') == policy['owner_approval_ref'] and row.get('started_at')]
        started_at = history.get('started_at')
        rows = [row for row in records if row.get('approval_ref') == policy['owner_approval_ref'] and
                row.get('started_at') == started_at]
        if not starts or started_at != starts[-1] or len(rows) < 2:
            raise ValueError('development_preoperation_failure_not_latest')
        failed = rows[-1]
        if (failed.get('blocked') is not True or failed.get('failure') != 'ValueError' or
                failed.get('failure_class') != 'UNKNOWN_UNHANDLED' or
                failed.get('procedure') != 'protected_gs40_bootstrap'):
            raise ValueError('development_preoperation_failure_not_disposition_eligible')
        evidence = Path(str(failed.get('evidence', '')))
        stdout_path, stderr_path = evidence / 'stdout.json', evidence / 'stderr.log'
        try:
            info = evidence.lstat()
            stdout, stderr = stdout_path.read_text(), stderr_path.read_text()
        except OSError as error:
            raise ValueError('development_preoperation_failure_evidence_invalid') from error
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or
                evidence.parent.resolve() != Path(STATE).resolve() or
                stdout != 'BOOTSTRAP_FAILED_STAGE=startup TYPE=ValueError CODE=REVIEWED_SERIAL_HELPER_CHANGED\n' or
                stderr != ''):
            raise ValueError('development_preoperation_failure_evidence_invalid')
        reviews = [row for row in records
                   if row.get('event') == 'development_mode_source_reviewed' and
                   row.get('activation_id') == policy['development_mode']['activation_id']]
        if (not reviews or reviews[-1].get('changed_sources') != ['bootstrap_script', 'validator'] or
                reviews[-1].get('bootstrap_pin_replacement', {}).get('embedded_new_helper_sha256') !=
                policy['serial_helper']['sha256'] or
                reviews[-1].get('source_pins_after', {}).get('bootstrap_script') !=
                policy['bootstrap_script']['sha256']):
            raise ValueError('development_preoperation_failure_source_review_missing')
        bootstrap_path = Path(policy['bootstrap_script']['path'])
        bootstrap_text = bootstrap_path.read_text()
        helper_hash = policy['serial_helper']['sha256']
        marker = "hexdigest() != '" + helper_hash + "':"
        guard = bootstrap_text.find('REVIEWED_SERIAL_HELPER_CHANGED')
        first_target_start = bootstrap_text.find('subprocess.Popen([WINPY')
        if (digest(bootstrap_path) != policy['bootstrap_script']['sha256'] or
                bootstrap_text.count(marker) != 1 or guard < 0 or
                first_target_start < 0 or guard > first_target_start):
            raise ValueError('development_preoperation_pin_guard_order_unverified')
        disposition = dict(failed)
        disposition.update({
            'event': 'development_failure_disposition',
            'disposition': 'REVIEWED_PRE_OPERATION_PIN_MISMATCH',
            'activation_id': policy['development_mode']['activation_id'],
            'failure': 'ValueError', 'failure_code': 'REVIEWED_SERIAL_HELPER_CHANGED',
            'failure_class': 'REVIEWED_PRE_OPERATION_CONFIGURATION',
            'disposition_of_sha256': _canonical_record_sha256(failed),
            'source_review_record_sha256': reviews[-1]['record_sha256'],
            'reviewed_commit': reviews[-1]['reviewed_commit'],
            'stdout_sha256': digest(stdout_path), 'stderr_sha256': digest(stderr_path),
            'at_utc': datetime.now(timezone.utc).isoformat(),
            'blocked': False, 'consecutive_failures': 0,
            'functional_outcome': 'NOT_RUN',
            'completed_at': datetime.now(timezone.utc).isoformat(),
        })
        disposition['record_sha256'] = _canonical_record_sha256(disposition)
        _append_private_audit(audit_path, disposition)
        ledger_path, _scope = _development_ledger_path(state, policy)
        if ledger_path.exists():
            backup = ledger_path.with_name(ledger_path.name + '.before-reviewed-disposition-' +
                                           secrets.token_hex(6))
            fd = os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, 'wb') as out:
                out.write(ledger_path.read_bytes()); out.flush(); os.fsync(out.fileno())
        history = _development_history(state, policy, scope_id)
        history['policy_manifest_sha256'] = digest(path)
        _write_private_ledger(ledger_path, history)
        return {'status': 'REVIEWED_PRE_OPERATION_FAILURE_DISPOSED',
                'sessions': history['sessions'],
                'consecutive_safety_failures': history['consecutive_failures'],
                'functional_outcome': history.get('functional_outcome'),
                'failure_disposition': history.get('failure_disposition'),
                'source_review_record_sha256': reviews[-1]['record_sha256']}


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
    session_limit = policy.get('max_sessions')
    exhausted = session_limit is not None and history['sessions'] >= session_limit
    return {
        'status': ('SAFETY_LATCHED' if history['blocked'] else
                   'SESSION_LIMIT_REACHED' if exhausted else 'ACTIVE'),
        'development_mode_enabled': True,
        'persistent': True,
        'expires_at': None,
        'sessions': history['sessions'],
        'session_limit': session_limit,
        'sessions_remaining': None if session_limit is None else max(0, session_limit-history['sessions']),
        'consecutive_safety_failures': history['consecutive_failures'],
        'blocked': history['blocked'],
        'procedures': policy['procedures'],
        'owner_approval_ref': policy['owner_approval_ref'],
        'authorization_scope_id': scope_id,
        'reviewed_failure_dispositions': history.get('reviewed_failure_dispositions', 0),
        'failure_disposition': history.get('failure_disposition'),
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
