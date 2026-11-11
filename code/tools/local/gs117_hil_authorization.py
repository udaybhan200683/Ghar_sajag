"""Local owner consent for existing GS-117 readiness procedures; no technical waiver."""
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone, timedelta
import argparse
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
            single_event_review_required = (
                'motion_event_once' in policy.get('procedures', []))
            if (record.get('single_event_scope_reviewed', False) is not
                    single_event_review_required):
                raise ValueError('development_source_review_single_event_scope_marker_invalid')
            if single_event_review_required:
                required_negative.update(DEV_MOTION_EVENT_PIN_REVIEW_TESTS)
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
        if (_development and procedure == 'motion_event_once' and
                not _development_motion_event_once_scope_valid(p)):
            raise ValueError('development_motion_event_scope_must_be_single_use')
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
DEV_OPERATIONS = ['protected_gs40_bootstrap', 'tc001_campaign', 'motion_event_once', 'observe',
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
DEV_MOTION_EVENT_PIN_REVIEW_TESTS = {
    'test_motion_event_once_authority_is_an_isolated_one_use_operation',
    'test_motion_event_readiness_requires_fresh_one_use_fixture_authority',
    'test_motion_event_source_pin_review_requires_and_records_single_use_negatives',
    'test_single_event_controller_reserves_once_and_never_falls_back_to_campaign',
    'test_single_event_fixture_change_after_reservation_consumes_scope_without_execute',
    'test_single_event_missing_or_stale_preflight_never_invokes_execute',
}
GS117_SCOPE_ISSUANCE_REVIEW_TESTS = DEV_MOTION_EVENT_PIN_REVIEW_TESTS | {
    'test_source_review_requires_current_commit_fingerprints_and_private_test_receipt',
    'test_untrusted_or_changed_owner_approval_is_rejected',
    'test_unknown_scope_and_stale_source_review_are_rejected_before_issue',
    'test_issuance_rejects_unverified_approval_without_creating_state',
    'test_readback_grant_issuance_is_pending_until_separate_activation',
    'test_scope_a_issuance_is_exactly_the_approved_fixture_ranges_and_resets',
    'test_duplicate_issuance_activation_and_scope_replay_are_rejected',
    'test_readback_wrong_tool_versions_and_incomplete_scope_fail_closed',
    'test_motion_grant_cannot_be_issued_before_scope_a_pass',
    'test_motion_grant_is_isolated_one_use_and_revocable',
    'test_scope_issuance_audit_corruption_blocks_activation',
    'test_interrupted_pending_issuance_without_audit_cannot_activate',
    'test_scope_b_activation_rejects_changed_scope_a_receipt',
    'test_unconsumed_motion_grant_can_be_revoked_without_touching_hardware_state',
    'test_private_policy_writer_rejects_group_or_world_accessible_parent',
}

# GS-117#11933 approved two distinct, one-use physical operations. These
# constants pin the actual Jira comment (issue/comment identity, author, and
# body digest); a caller-provided approval reference alone is never authority.
GS117_SCOPE_APPROVAL_REF = 'GS-117#11933'
GS117_SCOPE_APPROVAL_ISSUE = 'GS-117'
GS117_SCOPE_APPROVAL_COMMENT_ID = '11933'
GS117_SCOPE_APPROVAL_OWNER_ACCOUNT_ID = '712020:d1785a8a-5bf2-4556-a451-0805ddb6af74'
GS117_SCOPE_APPROVAL_BODY_SHA256 = '6ee1838468cc1296cf1d1acd8525eec164c1c06ad24108b2c03235adc37dad35'
GS117_SCOPE_ISSUANCE_STATE = (Path.home() /
    '.local/state/ghar-sajag/gs117-tc001/scope-issuance-11933')
GS117_SCOPE_SOURCE_NAMES = (
    'authorization_module', 'controller', 'collector', 'serial_helper',
    'readback_tests', 'console_tests', 'validation_registry',
)
GS117_SCOPE_SOURCE_PATHS = {
    'authorization_module': Path(__file__).resolve(),
    'controller': Path(__file__).resolve().with_name('gs117_tc001_console.py'),
    'collector': Path(__file__).resolve().with_name('gs117_tc001_readback.py'),
    'serial_helper': Path(__file__).resolve().with_name('gs117_tc001_serial_windows.py'),
    'readback_tests': Path(__file__).resolve().parents[2] / 'tests/python/test_gs117_readback_receipt.py',
    'console_tests': Path(__file__).resolve().parents[2] / 'tests/python/test_gs117_tc001_console.py',
    'validation_registry': Path(__file__).resolve().parents[2] / 'validation/suites.json',
}
GS117_SCOPE_APPROVAL_SCHEMA = 'GS117_OWNER_SCOPE_APPROVAL_V1'
GS117_SCOPE_ISSUANCE_SCHEMA = 'GS117_ONE_USE_GRANT_V1'
GS117_SCOPE_ISSUANCE_ZERO_HASH = '0' * 64
GS117_SCOPE_GRANT_MAX_SECONDS = {'readback_receipt': 7200, 'motion_event_once': 3600}
MOTION_EVENT_ONCE_POLICY = DEV_POLICY.with_name('motion-event-once-11933.json')
MOTION_EVENT_ONCE_STATE = DEV_STATE.with_name('motion-event-once-11933')
MOTION_EVENT_ONCE_MODE_ID = 'GS117_MOTION_EVENT_ONCE_11933'
MOTION_EVENT_ONCE_PROFILE = 'GS117_DEV_TEST_ONLY'
MOTION_EVENT_ONCE_TOOLS = {
    'authorization_module': Path(__file__).resolve(),
    'controller': Path(__file__).resolve().with_name('gs117_tc001_console.py'),
    'serial_helper': Path(__file__).resolve().with_name('gs117_tc001_serial_windows.py'),
    'collector': Path(__file__).resolve().with_name('gs117_tc001_readback.py'),
}

# Separate one-use receipt authority. This does not extend DEV_OPERATIONS,
# inherit its hardware allowance, or modify the consumed GS-117 observation
# ledger. A future owner-approved receipt manifest is provisioned through the
# existing audited owner process; this module only validates, reserves,
# revokes, and appends evidence for that exact separate scope.
READBACK_RECEIPT_POLICY = Path.home() / '.config/ghar-sajag/gs117-tc001/readback-receipt-authorization.json'
READBACK_RECEIPT_STATE = Path.home() / '.local/state/ghar-sajag/gs117-tc001/readback-receipt-authorization'
READBACK_RECEIPT_PROFILE = 'GS117_READBACK_RECEIPT'
READBACK_RECEIPT_OPERATION = 'readback_receipt'
READBACK_RECEIPT_PROCEDURE = Path(__file__).resolve().with_name('gs117_tc001_readback.py')
READBACK_RECEIPT_CONTROLLER = Path(__file__).resolve().with_name('gs117_tc001_console.py')
READBACK_RECEIPT_PARTITION_PARSER = (
    Path.home() / '.espressif/v6.0.3/esp-idf/components/partition_table/gen_esp32part.py')
READBACK_RECEIPT_FIXTURE = {
    'home_id': 'gs177-test-product',
    'c3': {'device_id': 'c3-146393c5d158', 'port': 'COM4',
           'serial_number': '14:63:93:C5:D1:58'},
    's3': {'device_id': 'hub-e072a1d38d34', 'port': 'COM10',
           'serial_number': 'E0:72:A1:D3:8D:34'},
}
READBACK_RECEIPT_RANGES = [
    {'role': 'c3', 'name': 'partition-table', 'offset': 0x8000, 'size': 0x1000},
    {'role': 'c3', 'name': 'otadata', 'offset': 0xF000, 'size': 0x2000},
    {'role': 'c3', 'name': 'active-app-image', 'offset': 0x20000, 'size': 958992},
    {'role': 's3', 'name': 'bootloader-region', 'offset': 0x000000, 'size': 0x008000},
    {'role': 's3', 'name': 'partition-table', 'offset': 0x8000, 'size': 0x1000},
    {'role': 's3', 'name': 'otadata', 'offset': 0xF000, 'size': 0x2000},
    {'role': 's3', 'name': 'active-app-image', 'offset': 0x420000, 'size': 2292864},
]
READBACK_RECEIPT_RESET_BUDGET = {
    'c3': {'rom_loader_entry_max': 1, 'normal_application_restore_max': 1,
           'connect_attempts': 1, 'additional_retry_resets': 0},
    's3': {'rom_loader_entry_max': 1, 'normal_application_restore_max': 1,
           'connect_attempts': 1, 'additional_retry_resets': 0},
}
READBACK_RECEIPT_PROHIBITED = [
    'generic_readback', 'nvs', 'credentials', 'keys', 'efuses', 'unrelated_flash',
    'flash_write', 'flash_erase', 'bootloader_write', 'partition_write',
    'ota_selector_write', 'firmware_install', 'bootstrap', 'event_injection',
    'radio_observation', 'hardware_entitlement_change',
]
READBACK_RECEIPT_TOOL_NAMES = (
    'authorization_module', 'controller', 'collector', 'python_runtime',
    'esptool', 'esptool_cmds', 'esptool_loader', 'esptool_target_c3',
    'esptool_target_s3', 'pyserial', 'pyserial_list_ports', 'partition_parser')
READBACK_RECEIPT_TOOL_VERSIONS = ('python', 'esptool', 'pyserial', 'esp_idf')
READBACK_RECEIPT_POLICY_KEYS = {
    'schema_version', 'profile', 'operation', 'authorization_id',
    'owner_approval_ref', 'owner_approved', 'active', 'revoked',
    'activated_at', 'expires_at', 'max_uses', 'renewable', 'fixture',
    'read_ranges', 'reset_budget', 'prohibited_operations', 'tool_files',
    'tool_versions', 'activation_record_sha256',
}
READBACK_RECEIPT_ZERO_HASH = '0' * 64


def _verify_gs117_11933_approval(evidence):
    """Verify the exact owner-authored Jira approval, not a caller's ref string."""
    if (not isinstance(evidence, dict) or
            set(evidence) != {'issue_key', 'comment_id', 'author_account_id', 'body'} or
            evidence.get('issue_key') != GS117_SCOPE_APPROVAL_ISSUE or
            str(evidence.get('comment_id')) != GS117_SCOPE_APPROVAL_COMMENT_ID or
            evidence.get('author_account_id') != GS117_SCOPE_APPROVAL_OWNER_ACCOUNT_ID or
            not isinstance(evidence.get('body'), str) or
            hashlib.sha256(evidence['body'].encode()).hexdigest() != GS117_SCOPE_APPROVAL_BODY_SHA256):
        raise ValueError('gs117_owner_scope_approval_not_verified')
    return {
        'issue_key': GS117_SCOPE_APPROVAL_ISSUE,
        'comment_id': GS117_SCOPE_APPROVAL_COMMENT_ID,
        'author_account_id': GS117_SCOPE_APPROVAL_OWNER_ACCOUNT_ID,
        'body_sha256': GS117_SCOPE_APPROVAL_BODY_SHA256,
        'approval_ref': GS117_SCOPE_APPROVAL_REF,
    }


def _verify_gs117_scope_source_review(review):
    """Require the reviewed commit and every scoped source fingerprint to be current."""
    review_keys = {'reviewed_commit', 'reviewer', 'source_fingerprints',
                   'reviewed_negative_tests', 'test_evidence_path', 'test_evidence_sha256'}
    if (not isinstance(review, dict) or
            set(review) not in (review_keys, review_keys | {'validation_summary'}) or
            review.get('reviewer') != GS117_SCOPE_APPROVAL_OWNER_ACCOUNT_ID or
            not isinstance(review.get('reviewed_commit'), str) or
            not re.fullmatch(r'[0-9a-f]{40}', review['reviewed_commit']) or
            not isinstance(review.get('source_fingerprints'), dict) or
            set(review['source_fingerprints']) != set(GS117_SCOPE_SOURCE_NAMES) or
            not isinstance(review.get('reviewed_negative_tests'), list) or
            review['reviewed_negative_tests'] != sorted(GS117_SCOPE_ISSUANCE_REVIEW_TESTS) or
            not isinstance(review.get('test_evidence_path'), str) or
            not Path(review['test_evidence_path']).is_absolute() or
            not re.fullmatch(r'[0-9a-f]{64}', str(review.get('test_evidence_sha256', '')))):
        raise ValueError('gs117_scope_source_review_invalid')
    repo = Path(__file__).resolve().parents[3]
    top = subprocess.run(['git', 'rev-parse', '--show-toplevel'], cwd=repo,
                         capture_output=True, text=True, timeout=10)
    branch = subprocess.run(['git', 'branch', '--show-current'], cwd=repo,
                            capture_output=True, text=True, timeout=10)
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=repo,
                          capture_output=True, text=True, timeout=10)
    dirty = subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--'], cwd=repo,
                            capture_output=True, text=True, timeout=10)
    if (top.returncode or Path(top.stdout.strip()).resolve() != repo or
            branch.returncode or branch.stdout.strip() != 'feature/r1-commercial-baseline' or
            head.returncode or head.stdout.strip() != review['reviewed_commit'] or dirty.returncode != 0):
        raise ValueError('gs117_scope_source_review_checkpoint_mismatch')
    actual = {}
    for name, path in GS117_SCOPE_SOURCE_PATHS.items():
        if path.is_symlink() or not path.is_file():
            raise ValueError('gs117_scope_source_missing:' + name)
        actual[name] = digest(path)
    if actual != review['source_fingerprints']:
        raise ValueError('gs117_scope_source_fingerprint_stale')
    evidence_path = Path(review['test_evidence_path'])
    _readback_receipt_private_file(evidence_path, 'gs117_scope_test_evidence_invalid')
    if digest(evidence_path) != review['test_evidence_sha256']:
        raise ValueError('gs117_scope_test_evidence_hash_mismatch')
    try:
        evidence = json.loads(evidence_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError('gs117_scope_test_evidence_invalid') from error
    expected_commands = {
        'authorization_receipt': ['python3', 'code/tests/python/test_gs117_readback_receipt.py'],
        'console': ['python3', 'code/tests/python/test_gs117_tc001_console.py'],
        'framework': ['make', '-C', 'code', 'validation-framework-test'],
        'feature_coverage': ['make', '-C', 'code', 'feature-coverage-test'],
    }
    reviewed_tests_registered = set()
    for name in ('console_tests', 'readback_tests'):
        reviewed_tests_registered.update(re.findall(
            r'^\s*def\s+(test_[A-Za-z0-9_]+)\s*\(',
            GS117_SCOPE_SOURCE_PATHS[name].read_text(), re.MULTILINE))
    if (evidence.get('reviewed_negative_tests') != review['reviewed_negative_tests'] or
            not GS117_SCOPE_ISSUANCE_REVIEW_TESTS.issubset(reviewed_tests_registered)):
        raise ValueError('gs117_scope_negative_test_review_incomplete')
    expected_tests = set(expected_commands)
    tests = evidence.get('tests') if isinstance(evidence, dict) else None
    if (not isinstance(evidence, dict) or evidence.get('schema_version') != 1 or
            evidence.get('reviewed_commit') != review['reviewed_commit'] or
            evidence.get('source_fingerprints') != actual or not isinstance(tests, list) or
            {row.get('name') for row in tests if isinstance(row, dict)} != expected_tests or
            len(tests) != len(expected_tests) or
            any(row.get('returncode') != 0 or row.get('command') != expected_commands.get(row.get('name')) or
                type(row.get('test_count')) is not int or row['test_count'] < 1 or
                row.get('skipped_count') != 0 or
                not re.fullmatch(r'[0-9a-f]{64}', str(row.get('stdout_sha256', ''))) or
                not re.fullmatch(r'[0-9a-f]{64}', str(row.get('stderr_sha256', '')))
                for row in tests if isinstance(row, dict))):
        raise ValueError('gs117_scope_test_evidence_incomplete')
    by_name = {row['name']: row for row in tests}
    validation_summary = {
        'gs117_focused': 'PASS',
        'framework': 'PASS' if by_name['framework']['returncode'] == 0 else 'FAIL',
        'feature_coverage': 'PASS' if by_name['feature_coverage']['returncode'] == 0 else 'FAIL',
    }
    if any(by_name[name]['returncode'] != 0 for name in expected_tests):
        raise ValueError('gs117_scope_test_evidence_failed')
    if ('validation_summary' in review and review['validation_summary'] != validation_summary):
        raise ValueError('gs117_scope_test_evidence_summary_mismatch')
    return {
        'reviewed_commit': review['reviewed_commit'],
        'reviewer': review['reviewer'].strip(),
        'source_fingerprints': actual,
        'test_evidence_path': str(evidence_path),
        'test_evidence_sha256': review['test_evidence_sha256'],
        'reviewed_negative_tests': review['reviewed_negative_tests'],
        'validation_summary': validation_summary,
    }


def _scope_issuance_state_private(state=None, *, create=False):
    state = Path(state or GS117_SCOPE_ISSUANCE_STATE)
    if state.is_symlink():
        raise ValueError('gs117_scope_issuance_state_not_private')
    if create:
        state.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        info = state.lstat()
    except OSError as error:
        raise ValueError('gs117_scope_issuance_state_not_private') from error
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077):
        raise ValueError('gs117_scope_issuance_state_not_private')
    return state


def _scope_issuance_audit(state):
    state = _scope_issuance_state_private(state)
    path = state / 'issuance.jsonl'
    if path.is_symlink():
        raise ValueError('gs117_scope_issuance_audit_invalid')
    if not path.exists():
        return [], {}
    _readback_receipt_private_file(path, 'gs117_scope_issuance_audit_invalid')
    try:
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError('gs117_scope_issuance_audit_corrupt') from error
    previous, history = GS117_SCOPE_ISSUANCE_ZERO_HASH, {}
    for row in rows:
        if (not isinstance(row, dict) or row.get('event') not in
                {'scope_grant_issued', 'scope_grant_activated'} or
                not re.fullmatch(r'[0-9a-f]{32}', str(row.get('authorization_id', ''))) or
                row.get('operation') not in {'readback_receipt', 'motion_event_once'} or
                row.get('previous_record_sha256') != previous or
                row.get('record_sha256') != _canonical_record_sha256(row)):
            raise ValueError('gs117_scope_issuance_audit_chain_invalid')
        current = history.setdefault(row['authorization_id'], {
            'operation': row['operation'], 'issued': None, 'activated': None})
        if current['operation'] != row['operation']:
            raise ValueError('gs117_scope_issuance_scope_mismatch')
        if row['event'] == 'scope_grant_issued':
            if current['issued'] is not None or row.get('approval_ref') != GS117_SCOPE_APPROVAL_REF or \
                    row.get('approval_body_sha256') != GS117_SCOPE_APPROVAL_BODY_SHA256:
                raise ValueError('gs117_scope_duplicate_issuance')
            current['issued'] = row
        elif current['issued'] is None or current['activated'] is not None:
            raise ValueError('gs117_scope_issuance_transition_invalid')
        else:
            if (row.get('issued_record_sha256') != current['issued'].get('issued_record_sha256') or
                    row.get('approval_body_sha256') != current['issued'].get('approval_body_sha256') or
                    row.get('source_review_sha256') != current['issued'].get('source_review_sha256')):
                raise ValueError('gs117_scope_issuance_binding_mismatch')
            current['activated'] = row
        previous = row['record_sha256']
    if len({(value['operation']) for value in history.values()}) > 2:
        raise ValueError('gs117_scope_issuance_audit_scope_invalid')
    for operation in ('readback_receipt', 'motion_event_once'):
        issued = [item for item in history.values()
                  if item['operation'] == operation and item['issued'] is not None]
        if len(issued) > 1:
            raise ValueError('gs117_scope_duplicate_issuance')
    return rows, history


def _append_scope_issuance_event(state, record):
    rows, _history = _scope_issuance_audit(state)
    record = dict(record)
    record['previous_record_sha256'] = (rows[-1]['record_sha256'] if rows
                                        else GS117_SCOPE_ISSUANCE_ZERO_HASH)
    record['record_sha256'] = _canonical_record_sha256(record)
    _append_private_audit(Path(state) / 'issuance.jsonl', record)
    return record


def _write_private_json_exclusive(path, value):
    path = Path(path)
    if (path.is_symlink() or not path.parent.is_dir() or
            path.parent.resolve(strict=True) != path.parent):
        raise ValueError('gs117_scope_grant_path_invalid')
    parent_info = path.parent.lstat()
    if (not stat.S_ISDIR(parent_info.st_mode) or parent_info.st_uid != os.getuid() or
            parent_info.st_mode & 0o077):
        raise ValueError('gs117_scope_grant_parent_not_private')
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            fd = -1
            json.dump(value, output, sort_keys=True)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
    finally:
        if fd >= 0:
            os.close(fd)
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


@contextmanager
def _gs117_scope_issuance_lock(state=None):
    state = _scope_issuance_state_private(state, create=True)
    lock_path = state / 'session.lock'
    if lock_path.is_symlink():
        raise ValueError('gs117_scope_issuance_state_not_private')
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'r+') as lock:
        info = os.fstat(lock.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or
                info.st_mode & 0o077):
            raise ValueError('gs117_scope_issuance_state_not_private')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('gs117_scope_issuance_already_active') from error
        yield state


@contextmanager
def _gs117_scope_operation_guard(error_code):
    with ExitStack() as locks:
        _hold_gs117_physical_scope_locks(locks, error_code=error_code)
        with _gs117_scope_issuance_lock() as state:
            yield state


def _scope_approval_record_hash(approval):
    return hashlib.sha256(json.dumps(approval, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _verify_scope_a_readback_pass(state=None, now=None):
    """Require the exact completed, integrity-checked and fresh Scope A evidence."""
    state = Path(state or READBACK_RECEIPT_STATE)
    now = now or datetime.now(timezone.utc)
    rows, histories = _readback_receipt_audit(state)
    completed = [row for row in rows if row.get('event') == 'readback_receipt_completed' and
                 row.get('outcome') == 'PASS']
    if not completed:
        raise ValueError('motion_event_once_scope_a_receipt_pass_required')
    result = completed[-1]
    try:
        finished = datetime.fromisoformat(result['completed_at'])
        evidence_dir = Path(result['evidence_dir'])
        age = (now - finished).total_seconds()
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError('motion_event_once_scope_a_receipt_invalid') from error
    if (finished.tzinfo is None or now.tzinfo is None or age < 0 or age > 86400 or
            result.get('authorization_id') not in histories or
            histories[result['authorization_id']].get('terminal') != result or
            result.get('scope_sha256') != histories[result['authorization_id']]['activated'].get('scope_sha256')):
        raise ValueError('motion_event_once_scope_a_receipt_stale_or_unverified')
    evidence_hash, entries = _readback_receipt_evidence_hash(evidence_dir)
    if evidence_hash != result.get('evidence_sha256') or entries != result.get('evidence_entries'):
        raise ValueError('motion_event_once_scope_a_receipt_integrity_failed')
    by_role = {}
    for role in ('c3', 's3'):
        receipt_path = evidence_dir / role / (role + '-readback.json')
        try:
            receipt = json.loads(receipt_path.read_text())
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError('motion_event_once_scope_a_receipt_missing') from error
        if (receipt.get('status') != 'PASS' or receipt.get('role') != role or
                receipt.get('port') != READBACK_RECEIPT_FIXTURE[role]['port'] or
                receipt.get('expected_usb_serial') != READBACK_RECEIPT_FIXTURE[role]['serial_number'] or
                receipt.get('procedure_sha256') != histories[result['authorization_id']]['activated'].get(
                    'tool_hashes', {}).get('collector') or
                receipt.get('image_match', {}).get('byte_for_byte_match') is not True or
                receipt.get('image_match', {}).get('readback_sha256') != DEV_IMAGES[role] or
                receipt.get('trusted_artifact_sha256') != DEV_IMAGES[role] or
                receipt.get('application_restoration', {}).get('status') != 'USB_IDENTITY_REENUMERATED'):
            raise ValueError('motion_event_once_scope_a_receipt_fixture_or_image_mismatch')
        by_role[role] = digest(receipt_path)
    return {
        'authorization_id': result['authorization_id'],
        'scope_sha256': result['scope_sha256'],
        'session_id': result['session_id'],
        'evidence_dir': str(evidence_dir),
        'evidence_sha256': evidence_hash,
        'completed_at': result['completed_at'],
        'receipt_sha256': by_role,
    }


def _readback_receipt_scope_sha256(policy):
    value = {key: policy[key] for key in sorted(READBACK_RECEIPT_POLICY_KEYS)
             if key != 'activation_record_sha256'}
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _readback_receipt_private_file(path, error_code):
    path = Path(path)
    if path.is_symlink():
        raise ValueError(error_code)
    try:
        info = path.lstat()
    except OSError as error:
        raise ValueError(error_code) from error
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or
            info.st_mode & 0o077):
        raise ValueError(error_code)
    return info


def _readback_receipt_audit(state):
    state = Path(state)
    if (state.is_symlink() or not state.is_dir() or state.stat().st_uid != os.getuid() or
            state.stat().st_mode & 0o077):
        raise ValueError('readback_receipt_state_not_private')
    audit = state / 'audit.jsonl'
    _readback_receipt_private_file(audit, 'readback_receipt_audit_invalid')
    try:
        rows = [json.loads(line) for line in audit.read_text().splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError('readback_receipt_audit_corrupt') from error
    previous = READBACK_RECEIPT_ZERO_HASH
    histories = {}
    allowed_events = {
        'readback_receipt_activated', 'readback_receipt_revoked',
        'readback_receipt_reserved', 'readback_receipt_completed',
        'readback_receipt_failed', 'readback_receipt_role_started',
    }
    for row in rows:
        if (not isinstance(row, dict) or row.get('event') not in allowed_events or
                not re.fullmatch(r'[0-9a-f]{32}', str(row.get('authorization_id', ''))) or
                row.get('previous_record_sha256') != previous or
                row.get('record_sha256') != _canonical_record_sha256(row)):
            raise ValueError('readback_receipt_audit_chain_invalid')
        auth_id = row['authorization_id']
        state_value = histories.setdefault(auth_id, {'activated': None, 'reserved': None,
                                                       'terminal': None, 'revoked': False,
                                                       'roles_started': set()})
        if row['event'] == 'readback_receipt_activated':
            if state_value['activated'] is not None:
                raise ValueError('readback_receipt_duplicate_activation')
            state_value['activated'] = row
        elif state_value['activated'] is None:
            raise ValueError('readback_receipt_audit_transition_invalid')
        elif row['event'] == 'readback_receipt_revoked':
            if state_value['revoked'] or state_value['reserved'] is not None or state_value['terminal'] is not None:
                raise ValueError('readback_receipt_audit_transition_invalid')
            state_value['revoked'] = True
        elif row['event'] == 'readback_receipt_reserved':
            if state_value['revoked'] or state_value['reserved'] is not None or state_value['terminal'] is not None:
                raise ValueError('readback_receipt_audit_transition_invalid')
            state_value['reserved'] = row
        elif row['event'] == 'readback_receipt_role_started':
            role = row.get('role')
            if (state_value['reserved'] is None or state_value['terminal'] is not None or
                    row.get('session_id') != state_value['reserved'].get('session_id') or
                    role not in {'c3', 's3'} or role in state_value['roles_started']):
                raise ValueError('readback_receipt_role_replay_or_transition_invalid')
            state_value['roles_started'].add(role)
        else:
            if (state_value['reserved'] is None or state_value['terminal'] is not None or
                    row.get('session_id') != state_value['reserved'].get('session_id')):
                raise ValueError('readback_receipt_audit_transition_invalid')
            state_value['terminal'] = row
        if row.get('approval_ref') != state_value['activated'].get('approval_ref'):
            raise ValueError('readback_receipt_audit_scope_mismatch')
        if row.get('scope_sha256') != state_value['activated'].get('scope_sha256'):
            raise ValueError('readback_receipt_audit_scope_mismatch')
        previous = row['record_sha256']
    if sum(1 for value in histories.values()
           if value['reserved'] is not None and value['terminal'] is None) > 1:
        raise ValueError('readback_receipt_concurrent_operation_detected')
    return rows, histories


def _append_readback_receipt_event(state, record):
    rows, _histories = _readback_receipt_audit(state)
    record = dict(record)
    record['previous_record_sha256'] = (rows[-1]['record_sha256'] if rows
                                        else READBACK_RECEIPT_ZERO_HASH)
    record['record_sha256'] = _canonical_record_sha256(record)
    _append_private_audit(Path(state) / 'audit.jsonl', record)
    return record


def _readback_receipt_tool_hashes(policy):
    tools = policy.get('tool_files')
    if not isinstance(tools, dict) or set(tools) != set(READBACK_RECEIPT_TOOL_NAMES):
        raise ValueError('readback_receipt_tool_scope_mismatch')
    hashes = {}
    expected_sources = {
        'authorization_module': Path(__file__).resolve(),
        'controller': READBACK_RECEIPT_CONTROLLER.resolve(),
        'collector': READBACK_RECEIPT_PROCEDURE.resolve(),
        'partition_parser': READBACK_RECEIPT_PARTITION_PARSER.resolve(),
    }
    for name in READBACK_RECEIPT_TOOL_NAMES:
        entry = tools.get(name)
        if (not isinstance(entry, dict) or set(entry) != {'path', 'sha256'} or
                not isinstance(entry.get('path'), str) or
                not re.fullmatch(r'[0-9a-f]{64}', str(entry.get('sha256', '')))):
            raise ValueError('readback_receipt_tool_scope_mismatch')
        path = Path(entry['path'])
        if (not path.is_absolute() or path.is_symlink() or
                path.resolve(strict=False) != path or not path.is_file() or
                digest(path) != entry['sha256']):
            raise ValueError('readback_receipt_tool_identity_mismatch')
        if name in expected_sources and path != expected_sources[name]:
            raise ValueError('readback_receipt_tool_path_mismatch')
        hashes[name] = entry['sha256']
    return hashes


def load_readback_receipt_authorization(now=None, *, _allow_reserved=False):
    """Validate a separately approved exact-scope receipt grant, without reserving it."""
    path, state = READBACK_RECEIPT_POLICY, READBACK_RECEIPT_STATE
    _readback_receipt_private_file(path, 'readback_receipt_policy_not_private')
    try:
        policy = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError('readback_receipt_policy_corrupt') from error
    if not isinstance(policy, dict) or set(policy) != READBACK_RECEIPT_POLICY_KEYS:
        raise ValueError('readback_receipt_policy_schema_mismatch')
    if (type(policy.get('schema_version')) is not int or policy.get('schema_version') != 1 or
            policy.get('profile') != READBACK_RECEIPT_PROFILE or
            policy.get('operation') != READBACK_RECEIPT_OPERATION or
            not re.fullmatch(r'[0-9a-f]{32}', str(policy.get('authorization_id', ''))) or
            not re.fullmatch(r'GS-117#\d{1,8}', str(policy.get('owner_approval_ref', ''))) or
            policy.get('owner_approved') is not True or policy.get('active') is not True or
            policy.get('revoked') is not False or type(policy.get('max_uses')) is not int or
            policy.get('max_uses') != 1 or
            policy.get('renewable') is not False or policy.get('fixture') != READBACK_RECEIPT_FIXTURE or
            policy.get('read_ranges') != READBACK_RECEIPT_RANGES or
            policy.get('reset_budget') != READBACK_RECEIPT_RESET_BUDGET or
            policy.get('prohibited_operations') != READBACK_RECEIPT_PROHIBITED or
            not re.fullmatch(r'[0-9a-f]{64}', str(policy.get('activation_record_sha256', '')))):
        raise ValueError('readback_receipt_scope_or_identity_mismatch')
    versions = policy.get('tool_versions')
    if (not isinstance(versions, dict) or set(versions) != set(READBACK_RECEIPT_TOOL_VERSIONS) or
            any(not isinstance(value, str) or not value.strip() or len(value) > 80
                for value in versions.values()) or
            versions.get('esptool') != '5.4.0' or versions.get('esp_idf') != '6.0.3'):
        raise ValueError('readback_receipt_tool_version_mismatch')
    hashes = _readback_receipt_tool_hashes(policy)
    try:
        activated = datetime.fromisoformat(policy['activated_at'])
        expires = datetime.fromisoformat(policy['expires_at'])
    except (TypeError, ValueError):
        raise ValueError('readback_receipt_time_invalid') from None
    now = now or datetime.now(timezone.utc)
    if (activated.tzinfo is None or expires.tzinfo is None or now.tzinfo is None or
            not activated < expires or not activated <= now < expires):
        raise ValueError('readback_receipt_authorization_expired_or_not_yet_active')
    audit_path = Path(state) / 'audit.jsonl'
    rows, histories = _readback_receipt_audit(state)
    history = histories.get(policy['authorization_id'])
    scope_hash = _readback_receipt_scope_sha256(policy)
    if (history is None or history['activated'] is None or
            sum(1 for row in rows if row.get('authorization_id') == policy['authorization_id'] and
                row.get('event') == 'readback_receipt_activated') != 1):
        raise ValueError('readback_receipt_activation_missing_or_replayed')
    activation = history['activated']
    expected_activation = {
        'authorization_id': policy['authorization_id'],
        'activation_id': policy['authorization_id'],
        'approval_ref': policy['owner_approval_ref'],
        'scope_sha256': scope_hash,
        'activated_at': policy['activated_at'],
        'expires_at': policy['expires_at'],
        'fixture': READBACK_RECEIPT_FIXTURE,
        'operation': READBACK_RECEIPT_OPERATION,
        'read_ranges': READBACK_RECEIPT_RANGES,
        'reset_budget': READBACK_RECEIPT_RESET_BUDGET,
        'tool_hashes': hashes,
        'tool_versions': versions,
        'max_uses': 1,
    }
    if (any(activation.get(key) != value for key, value in expected_activation.items()) or
            activation.get('record_sha256') != policy['activation_record_sha256']):
        raise ValueError('readback_receipt_activation_scope_mismatch')
    if policy['owner_approval_ref'] == GS117_SCOPE_APPROVAL_REF:
        _verify_scope_issuance_binding(
            policy['authorization_id'], 'readback_receipt', activation.get('issuance_record_sha256'),
            activation.get('approval_body_sha256'), activation.get('source_review_sha256'))
    if history['revoked']:
        raise ValueError('readback_receipt_authorization_revoked')
    if history['reserved'] is not None and not _allow_reserved:
        raise ValueError('readback_receipt_authorization_consumed')
    # Keep the fixed audit path explicit; it may not be redirected by the caller.
    if audit_path.is_symlink():
        raise ValueError('readback_receipt_audit_invalid')
    return policy


def _motion_event_tool_hashes(tool_files):
    if not isinstance(tool_files, dict) or set(tool_files) != set(MOTION_EVENT_ONCE_TOOLS):
        raise ValueError('motion_event_once_tool_scope_mismatch')
    result = {}
    for name, expected_path in MOTION_EVENT_ONCE_TOOLS.items():
        entry = tool_files.get(name)
        if (not isinstance(entry, dict) or set(entry) != {'path', 'sha256'} or
                entry.get('path') != str(expected_path) or expected_path.is_symlink() or
                not expected_path.is_file() or not re.fullmatch(r'[0-9a-f]{64}',
                                                                str(entry.get('sha256', ''))) or
                digest(expected_path) != entry['sha256']):
            raise ValueError('motion_event_once_tool_identity_mismatch:' + name)
        result[name] = entry['sha256']
    return result


def _scope_pending_path(state, operation, authorization_id):
    if (operation not in {'readback_receipt', 'motion_event_once'} or
            not re.fullmatch(r'[0-9a-f]{32}', str(authorization_id))):
        raise ValueError('gs117_scope_grant_identity_invalid')
    return Path(state) / f'{operation}-{authorization_id}.pending.json'


def issue_gs117_scope_grant(operation, approval_evidence, source_review, *,
                            tool_files=None, tool_versions=None, now=None):
    """Create one immutable pending grant from the pinned owner approval.

    Issuance does not activate a policy and cannot authorize device access.
    A separate explicit activation step is required after source review.
    """
    if operation not in {'readback_receipt', 'motion_event_once'}:
        raise ValueError('gs117_scope_operation_not_allowlisted')
    approval = _verify_gs117_11933_approval(approval_evidence)
    review = _verify_gs117_scope_source_review(source_review)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('gs117_scope_issue_time_invalid')
    if operation == 'readback_receipt':
        if not isinstance(tool_files, dict) or not isinstance(tool_versions, dict):
            raise ValueError('readback_receipt_reviewed_tool_inventory_required')
        candidate = {'tool_files': tool_files}
        tool_hashes = _readback_receipt_tool_hashes(candidate)
        if (set(tool_versions) != set(READBACK_RECEIPT_TOOL_VERSIONS) or
                any(not isinstance(value, str) or not value.strip() or len(value) > 80
                    for value in tool_versions.values()) or
                tool_versions.get('esptool') != '5.4.0' or tool_versions.get('esp_idf') != '6.0.3'):
            raise ValueError('readback_receipt_tool_version_mismatch')
        scope = {
            'fixture': READBACK_RECEIPT_FIXTURE,
            'read_ranges': READBACK_RECEIPT_RANGES,
            'reset_budget': READBACK_RECEIPT_RESET_BUDGET,
            'prohibited_operations': READBACK_RECEIPT_PROHIBITED,
            'tool_files': tool_files,
            'tool_hashes': tool_hashes,
            'tool_versions': tool_versions,
        }
    else:
        if tool_files is None:
            tool_files = {name: {'path': str(path), 'sha256': digest(path)}
                          for name, path in MOTION_EVENT_ONCE_TOOLS.items()}
        tool_hashes = _motion_event_tool_hashes(tool_files)
        receipt = _verify_scope_a_readback_pass(now=now)
        scope = {
            'fixture': READBACK_RECEIPT_FIXTURE,
            'images': DEV_IMAGES,
            'procedures': ['motion_event_once'],
            'allowed_operations': ['motion_event_once'],
            'procedure_session_limits': {'motion_event_once': 1},
            'max_sessions': 1,
            'motion_injection_authorized': True,
            'prohibited_operations': DEV_PROHIBITED + [
                'campaign', 'bootstrap', 'flash', 'erase', 'readback', 'reset',
                's3_uart', 'retry', 'second_event',
            ],
            'tool_files': tool_files,
            'tool_hashes': tool_hashes,
            'scope_a_receipt': receipt,
        }
    with _gs117_scope_operation_guard('gs117_scope_hardware_operation_already_active') as state:
        rows, history = _scope_issuance_audit(state)
        if any(value['operation'] == operation and value['issued'] is not None
               for value in history.values()):
            raise ValueError('gs117_scope_grant_already_issued')
        if any(state.glob(operation + '-*.pending.json')):
            raise ValueError('gs117_scope_grant_issue_already_pending')
        final_path = READBACK_RECEIPT_POLICY if operation == 'readback_receipt' else MOTION_EVENT_ONCE_POLICY
        if final_path.exists() or final_path.is_symlink():
            raise ValueError('gs117_scope_grant_target_already_exists')
        authorization_id = secrets.token_hex(16)
        expires = now + timedelta(seconds=GS117_SCOPE_GRANT_MAX_SECONDS[operation])
        record = {
            'schema': GS117_SCOPE_ISSUANCE_SCHEMA,
            'operation': operation,
            'authorization_id': authorization_id,
            'phase': 'ISSUED_PENDING_ACTIVATION',
            'approval': approval,
            'source_review': review,
            'source_review_sha256': _scope_approval_record_hash(review),
            'scope': scope,
            'issued_at': now.isoformat(),
            'expires_at': expires.isoformat(),
            'max_uses': 1,
            'renewable': False,
        }
        record['issued_record_sha256'] = _canonical_record_sha256(record)
        pending = _scope_pending_path(state, operation, authorization_id)
        _write_private_json_exclusive(pending, record)
        event = {
            'event': 'scope_grant_issued', 'operation': operation,
            'authorization_id': authorization_id,
            'approval_ref': approval['approval_ref'],
            'approval_body_sha256': approval['body_sha256'],
            'source_review_sha256': record['source_review_sha256'],
            'issued_record_sha256': record['issued_record_sha256'],
            'pending_path': str(pending), 'issued_at': record['issued_at'],
            'expires_at': record['expires_at'],
        }
        _append_scope_issuance_event(state, event)
        return {'status': 'ISSUED_PENDING_ACTIVATION', 'operation': operation,
                'authorization_id': authorization_id, 'expires_at': record['expires_at'],
                'issued_record_sha256': record['issued_record_sha256']}


def _scope_issuance_binding(authorization_id, operation):
    rows, history = _scope_issuance_audit(GS117_SCOPE_ISSUANCE_STATE)
    item = history.get(authorization_id)
    if (item is None or item['operation'] != operation or item['issued'] is None or
            item['activated'] is None):
        raise ValueError('gs117_scope_issuance_record_missing')
    issue, activated = item['issued'], item['activated']
    if (activated.get('issued_record_sha256') != issue.get('issued_record_sha256') or
            activated.get('approval_body_sha256') != issue.get('approval_body_sha256') or
            issue.get('approval_ref') != GS117_SCOPE_APPROVAL_REF or
            issue.get('record_sha256') != _canonical_record_sha256(issue) or
            activated.get('record_sha256') != _canonical_record_sha256(activated)):
        raise ValueError('gs117_scope_issuance_binding_mismatch')
    return issue, activated


def _verify_scope_issuance_binding(authorization_id, operation, issuance_record_sha256,
                                   approval_body_sha256, source_review_sha256):
    issue, activated = _scope_issuance_binding(authorization_id, operation)
    if (issue.get('issued_record_sha256') != issuance_record_sha256 or
            issue.get('approval_body_sha256') != approval_body_sha256 or
            activated.get('source_review_sha256') != source_review_sha256):
        raise ValueError('gs117_scope_issuance_binding_mismatch')


def activate_gs117_scope_grant(authorization_id, approval_evidence, source_review, *, now=None):
    """Activate one pending, exact-scope grant; never run its physical operation."""
    approval = _verify_gs117_11933_approval(approval_evidence)
    review = _verify_gs117_scope_source_review(source_review)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('gs117_scope_activation_time_invalid')
    with _gs117_scope_operation_guard('gs117_scope_hardware_operation_already_active') as state:
        _rows, history = _scope_issuance_audit(state)
        item = history.get(authorization_id)
        if item is None or item['issued'] is None:
            raise ValueError('gs117_scope_grant_issue_missing')
        if item['activated'] is not None:
            raise ValueError('gs117_scope_grant_already_activated')
        operation = item['operation']
        pending = _scope_pending_path(state, operation, authorization_id)
        _readback_receipt_private_file(pending, 'gs117_scope_pending_grant_invalid')
        try:
            record = json.loads(pending.read_text())
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError('gs117_scope_pending_grant_invalid') from error
        saved_hash = record.pop('issued_record_sha256', None)
        if (record.get('schema') != GS117_SCOPE_ISSUANCE_SCHEMA or
                record.get('phase') != 'ISSUED_PENDING_ACTIVATION' or
                record.get('authorization_id') != authorization_id or
                record.get('operation') != operation or
                record.get('approval') != approval or record.get('source_review') != review or
                saved_hash != item['issued'].get('issued_record_sha256') or
                saved_hash != _canonical_record_sha256(record)):
            raise ValueError('gs117_scope_pending_grant_integrity_failed')
        try:
            expires = datetime.fromisoformat(record['expires_at'])
            issued = datetime.fromisoformat(record['issued_at'])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError('gs117_scope_grant_time_invalid') from error
        if (expires.tzinfo is None or issued.tzinfo is None or now >= expires or now < issued or
                expires - issued != timedelta(seconds=GS117_SCOPE_GRANT_MAX_SECONDS[operation]) or
                record['scope'].get('fixture') != READBACK_RECEIPT_FIXTURE):
            raise ValueError('gs117_scope_grant_expired_or_scope_mismatch')
        scope = record['scope']
        activation_time = issued.isoformat()
        issuance_record_sha256 = saved_hash
        approval_hash = approval['body_sha256']
        source_review_hash = record['source_review_sha256']
        if operation == 'readback_receipt':
            tool_hashes = _readback_receipt_tool_hashes({'tool_files': scope['tool_files']})
            if (scope.get('read_ranges') != READBACK_RECEIPT_RANGES or
                    scope.get('reset_budget') != READBACK_RECEIPT_RESET_BUDGET or
                    scope.get('prohibited_operations') != READBACK_RECEIPT_PROHIBITED or
                    scope.get('tool_hashes') != tool_hashes or
                    scope.get('tool_versions') != record['scope'].get('tool_versions')):
                raise ValueError('readback_receipt_issued_scope_changed')
            policy = {
                'schema_version': 1, 'profile': READBACK_RECEIPT_PROFILE,
                'operation': READBACK_RECEIPT_OPERATION,
                'authorization_id': authorization_id,
                'owner_approval_ref': GS117_SCOPE_APPROVAL_REF,
                'owner_approved': True, 'active': True, 'revoked': False,
                'activated_at': activation_time, 'expires_at': record['expires_at'],
                'max_uses': 1, 'renewable': False,
                'fixture': READBACK_RECEIPT_FIXTURE,
                'read_ranges': READBACK_RECEIPT_RANGES,
                'reset_budget': READBACK_RECEIPT_RESET_BUDGET,
                'prohibited_operations': READBACK_RECEIPT_PROHIBITED,
                'tool_files': scope['tool_files'], 'tool_versions': scope['tool_versions'],
                'activation_record_sha256': '0' * 64,
            }
            if READBACK_RECEIPT_POLICY.exists() or READBACK_RECEIPT_POLICY.is_symlink():
                raise ValueError('readback_receipt_policy_already_exists')
            receipt_state = Path(READBACK_RECEIPT_STATE)
            receipt_state.mkdir(parents=True, exist_ok=True, mode=0o700)
            if receipt_state.is_symlink() or receipt_state.stat().st_uid != os.getuid() or receipt_state.stat().st_mode & 0o077:
                raise ValueError('readback_receipt_state_not_private')
            audit_path = receipt_state / 'audit.jsonl'
            if not audit_path.exists():
                fd = os.open(audit_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(fd, 'wb') as audit_file:
                    audit_file.flush()
                    os.fsync(audit_file.fileno())
            else:
                _readback_receipt_audit(receipt_state)
            activation = {
                'event': 'readback_receipt_activated',
                'authorization_id': authorization_id, 'activation_id': authorization_id,
                'approval_ref': GS117_SCOPE_APPROVAL_REF,
                'scope_sha256': _readback_receipt_scope_sha256(policy),
                'activated_at': activation_time, 'expires_at': record['expires_at'],
                'fixture': READBACK_RECEIPT_FIXTURE,
                'operation': READBACK_RECEIPT_OPERATION,
                'read_ranges': READBACK_RECEIPT_RANGES,
                'reset_budget': READBACK_RECEIPT_RESET_BUDGET,
                'tool_hashes': tool_hashes, 'tool_versions': scope['tool_versions'],
                'max_uses': 1, 'issuance_record_sha256': issuance_record_sha256,
                'approval_body_sha256': approval_hash,
                'source_review_sha256': source_review_hash,
            }
            activation = _append_readback_receipt_event(receipt_state, activation)
            policy['activation_record_sha256'] = activation['record_sha256']
            _write_private_json_exclusive(READBACK_RECEIPT_POLICY, policy)
            grant_sha256 = digest(READBACK_RECEIPT_POLICY)
        else:
            if _verify_scope_a_readback_pass(now=now) != scope.get('scope_a_receipt'):
                raise ValueError('motion_event_once_scope_a_receipt_changed')
            tool_hashes = _motion_event_tool_hashes(scope['tool_files'])
            if (scope.get('procedures') != ['motion_event_once'] or
                    scope.get('allowed_operations') != ['motion_event_once'] or
                    scope.get('max_sessions') != 1 or
                    scope.get('procedure_session_limits') != {'motion_event_once': 1} or
                    scope.get('motion_injection_authorized') is not True or
                    scope.get('prohibited_operations') != DEV_PROHIBITED + [
                        'campaign', 'bootstrap', 'flash', 'erase', 'readback', 'reset',
                        's3_uart', 'retry', 'second_event']):
                raise ValueError('motion_event_once_issued_scope_changed')
            if MOTION_EVENT_ONCE_POLICY.exists() or MOTION_EVENT_ONCE_POLICY.is_symlink():
                raise ValueError('motion_event_once_policy_already_exists')
            motion_state = Path(MOTION_EVENT_ONCE_STATE)
            motion_state.mkdir(parents=True, exist_ok=True, mode=0o700)
            if motion_state.is_symlink() or motion_state.stat().st_uid != os.getuid() or motion_state.stat().st_mode & 0o077:
                raise ValueError('motion_event_once_state_not_private')
            audit_path = motion_state / 'audit.jsonl'
            if not audit_path.exists():
                fd = os.open(audit_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(fd)
            mode = {
                'enabled': True, 'revoked': False, 'persistent': True,
                'mode_id': MOTION_EVENT_ONCE_MODE_ID, 'expires_at': None,
                'environment': 'GS117_TEST_ONLY',
                'authorization_ref': GS117_SCOPE_APPROVAL_REF,
                'authority_refs': {'GS-117': '11933'},
                'disable_on_release_transition': True,
                'activation_record_sha256': '0' * 64,
                'activation_id': authorization_id,
                'activated_at': activation_time,
                'reviewed_commit': review['reviewed_commit'],
                'reviewed_source_fingerprints': review['source_fingerprints'],
                'validation_summary': review['validation_summary'],
            }
            policy = {
                'schema_version': DEV_MODE_SCHEMA, 'profile': MOTION_EVENT_ONCE_PROFILE,
                'owner_approval_ref': GS117_SCOPE_APPROVAL_REF,
                'owner_approved': True, 'active': True, 'revoked': False,
                'development_mode_enabled': True,
                'identity': IDENTITY, 'images': DEV_IMAGES,
                'procedures': ['motion_event_once'],
                'allowed_operations': ['motion_event_once'],
                'procedure_session_limits': {'motion_event_once': 1},
                'max_sessions': 1, 'motion_injection_authorized': True,
                'prohibited_operations': scope['prohibited_operations'],
                'serial_reset_risk_accepted': True,
                'activated_at': activation_time, 'expires_at': record['expires_at'],
                'development_mode': mode,
                'activation_audit_path': str(audit_path),
                'motion_event_once_scope': {
                    'authorization_id': authorization_id,
                    'approval_body_sha256': approval_hash,
                    'issuance_record_sha256': issuance_record_sha256,
                    'source_review_sha256': source_review_hash,
                    'source_review': review,
                    'tool_files': scope['tool_files'],
                    'tool_hashes': tool_hashes,
                    'scope_a_receipt': scope['scope_a_receipt'],
                },
            }
            activation = {
                'event': 'motion_event_once_activated',
                'activation_id': authorization_id,
                'authorization_id': authorization_id,
                'approval_ref': GS117_SCOPE_APPROVAL_REF,
                'authorization_scope_id': _development_scope_id(policy),
                'activated_at': activation_time,
                'expires_at': record['expires_at'],
                'approval_body_sha256': approval_hash,
                'issuance_record_sha256': issuance_record_sha256,
                'source_review_sha256': source_review_hash,
                'reviewed_commit': review['reviewed_commit'],
                'tool_hashes': tool_hashes,
                'scope_a_receipt': scope['scope_a_receipt'],
            }
            activation['record_sha256'] = _canonical_record_sha256(activation)
            _append_private_audit(audit_path, activation)
            mode['activation_record_sha256'] = activation['record_sha256']
            _write_private_json_exclusive(MOTION_EVENT_ONCE_POLICY, policy)
            grant_sha256 = digest(MOTION_EVENT_ONCE_POLICY)
        activated_event = {
            'event': 'scope_grant_activated', 'operation': operation,
            'authorization_id': authorization_id,
            'approval_ref': GS117_SCOPE_APPROVAL_REF,
            'approval_body_sha256': approval_hash,
            'source_review_sha256': source_review_hash,
            'issued_record_sha256': issuance_record_sha256,
            'grant_sha256': grant_sha256,
            'activated_at': activation_time,
        }
        activated_event = _append_scope_issuance_event(state, activated_event)
        return {'status': 'ACTIVE', 'operation': operation,
                'authorization_id': authorization_id, 'expires_at': record['expires_at'],
                'grant_sha256': grant_sha256,
                'activation_record_sha256': activation.get('record_sha256')}


def _readback_receipt_active_lock(state):
    """Require the controller's process-wide receipt lock to remain held."""
    path = Path(state) / 'session.lock'
    if path.is_symlink():
        raise ValueError('readback_receipt_state_not_private')
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'r+') as lock:
        info = os.fstat(lock.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077):
            raise ValueError('readback_receipt_state_not_private')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        raise ValueError('readback_receipt_session_not_active')


def _readback_receipt_hold_exclusive_lock(stack, directory, error_code):
    directory = Path(directory)
    if directory.is_symlink():
        raise ValueError('readback_receipt_state_not_private')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = directory.stat()
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('readback_receipt_state_not_private')
    lock_path = directory / 'session.lock'
    if lock_path.is_symlink():
        raise ValueError('readback_receipt_state_not_private')
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    lock = stack.enter_context(os.fdopen(fd, 'r+'))
    info = os.fstat(lock.fileno())
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('readback_receipt_state_not_private')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        raise ValueError(error_code) from error
    return lock


@contextmanager
def _hold_gs117_physical_scope_locks(stack, *, error_code, include_motion=True,
                                     include_readback=True):
    """Serialize hardware, DEV, receipt, and single-event scopes in fixed order."""
    directories = (STATE, DEV_STATE,
                   *((READBACK_RECEIPT_STATE,) if include_readback else ()),
                   *((MOTION_EVENT_ONCE_STATE,) if include_motion else ()))
    for directory in directories:
        _readback_receipt_hold_exclusive_lock(stack, directory, error_code)


def claim_readback_receipt_role(session_id, role, procedure_sha256,
                                python_runtime_sha256, python_version,
                                pyserial_version, runtime_tool_hashes, now=None):
    """Claim one target exactly once from the still-active WSL authorization session."""
    if (not re.fullmatch(r'[0-9a-f]{32}', str(session_id)) or role not in {'c3', 's3'} or
            not re.fullmatch(r'[0-9a-f]{64}', str(procedure_sha256)) or
            not re.fullmatch(r'[0-9a-f]{64}', str(python_runtime_sha256)) or
            not isinstance(python_version, str) or not isinstance(pyserial_version, str) or
            not isinstance(runtime_tool_hashes, dict)):
        raise ValueError('readback_receipt_session_claim_invalid')
    state = Path(READBACK_RECEIPT_STATE)
    if (state.is_symlink() or not state.is_dir() or state.stat().st_uid != os.getuid() or
            state.stat().st_mode & 0o077):
        raise ValueError('readback_receipt_state_not_private')
    _readback_receipt_active_lock(state)
    claim_lock_path = state / 'claims.lock'
    if claim_lock_path.is_symlink():
        raise ValueError('readback_receipt_state_not_private')
    fd = os.open(claim_lock_path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'r+') as lock:
        info = os.fstat(lock.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077):
            raise ValueError('readback_receipt_state_not_private')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('readback_receipt_claim_already_active') from error
        policy = load_readback_receipt_authorization(now=now, _allow_reserved=True)
        expected_runtime_tools = set(READBACK_RECEIPT_TOOL_NAMES) - {
            'authorization_module', 'controller', 'collector', 'python_runtime'}
        if (set(runtime_tool_hashes) != expected_runtime_tools or
                any(not re.fullmatch(r'[0-9a-f]{64}', str(value))
                    for value in runtime_tool_hashes.values()) or
                any(runtime_tool_hashes[name] != policy['tool_files'][name]['sha256']
                    for name in expected_runtime_tools) or
                policy['tool_versions']['pyserial'] != pyserial_version):
            raise ValueError('readback_receipt_runtime_tool_identity_mismatch')
        rows, histories = _readback_receipt_audit(state)
        history = histories.get(policy['authorization_id'])
        reserved = history.get('reserved') if history else None
        if (reserved is None or history.get('terminal') is not None or
                reserved.get('session_id') != session_id or
                reserved.get('procedure_sha256') != procedure_sha256 or
                policy['tool_files']['collector']['sha256'] != procedure_sha256 or
                policy['tool_files']['python_runtime']['sha256'] != python_runtime_sha256 or
                policy['tool_versions']['python'] != python_version):
            raise ValueError('readback_receipt_session_or_procedure_mismatch')
        if role in history['roles_started']:
            raise ValueError('readback_receipt_role_replay_rejected')
        record = {
            'event': 'readback_receipt_role_started',
            'authorization_id': policy['authorization_id'],
            'approval_ref': policy['owner_approval_ref'],
            'scope_sha256': _readback_receipt_scope_sha256(policy),
            'session_id': session_id, 'role': role,
            'procedure_sha256': procedure_sha256,
            'python_runtime_sha256': python_runtime_sha256,
            'python_version': python_version,
            'pyserial_version': pyserial_version,
            'runtime_tool_hashes': runtime_tool_hashes,
            'started_at': datetime.now(timezone.utc).isoformat(),
        }
        _append_readback_receipt_event(state, record)
        return {'status': 'CLAIMED', 'role': role, 'session_id': session_id}


def _readback_receipt_evidence_hash(directory):
    root = Path(directory)
    if (root.is_symlink() or not root.is_dir() or root.stat().st_uid != os.getuid() or
            root.stat().st_mode & 0o077):
        raise ValueError('readback_receipt_evidence_not_private')
    entries = []
    for current, dirs, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in dirs:
            path = current_path / name
            info = path.lstat()
            if (stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode) or
                    info.st_uid != os.getuid() or info.st_mode & 0o077):
                raise ValueError('readback_receipt_evidence_not_private')
        for name in files:
            path = current_path / name
            info = path.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or
                    info.st_mode & 0o077):
                raise ValueError('readback_receipt_evidence_not_private')
            entries.append({'path': path.relative_to(root).as_posix(), 'size': info.st_size,
                            'sha256': digest(path)})
    if not entries:
        raise ValueError('readback_receipt_evidence_empty')
    entries.sort(key=lambda item: item['path'])
    encoded = json.dumps(entries, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(encoded).hexdigest(), entries


def readback_receipt_status(now=None):
    try:
        policy = load_readback_receipt_authorization(now=now)
        return {'status': 'ACTIVE', 'authorization_id': policy['authorization_id'],
                'operation': READBACK_RECEIPT_OPERATION, 'uses_remaining': 1,
                'expires_at': policy['expires_at']}
    except (OSError, ValueError, KeyError, TypeError) as error:
        reason = str(error)
        if reason == 'readback_receipt_authorization_consumed':
            return {'status': 'CONSUMED', 'reason': reason}
        if reason == 'readback_receipt_authorization_revoked':
            return {'status': 'REVOKED', 'reason': reason}
        if reason == 'readback_receipt_authorization_expired_or_not_yet_active':
            return {'status': 'EXPIRED_OR_INACTIVE', 'reason': reason}
        return {'status': 'BLOCKED', 'reason': reason}


@contextmanager
def readback_receipt_session(now=None):
    """Reserve the separate one-use receipt operation before the caller invokes any device tool."""
    state = Path(READBACK_RECEIPT_STATE)
    with ExitStack() as locks:
        # Serialize against both existing HIL authorization paths without
        # reading or changing either hardware entitlement or its ledger.
        _hold_gs117_physical_scope_locks(
            locks, error_code='readback_receipt_hardware_operation_already_active',
            include_readback=False)
        _readback_receipt_hold_exclusive_lock(
            locks, state, 'readback_receipt_hardware_operation_already_active')
        policy = load_readback_receipt_authorization(now=now)
        session_id = secrets.token_hex(16)
        base = {'authorization_id': policy['authorization_id'],
                'approval_ref': policy['owner_approval_ref'],
                'scope_sha256': _readback_receipt_scope_sha256(policy)}
        evidence_dir = state / ('evidence-' + session_id)
        evidence_dir.mkdir(mode=0o700)
        _append_readback_receipt_event(state, {
            'event': 'readback_receipt_reserved', **base,
            'session_id': session_id, 'started_at': datetime.now(timezone.utc).isoformat(),
            'procedure_sha256': policy['tool_files']['collector']['sha256'],
            'tool_hashes': {name: entry['sha256']
                            for name, entry in policy['tool_files'].items()},
            'tool_versions': dict(policy['tool_versions']),
            'evidence_dir': str(evidence_dir),
        })
        result = {'outcome': 'NOT_REPORTED', 'session_id': session_id,
                  'evidence_dir': str(evidence_dir),
                  'tool_files': dict(policy['tool_files']),
                  'tool_versions': dict(policy['tool_versions'])}
        try:
            yield result
        except BaseException as error:
            try:
                evidence_sha256, evidence_entries = _readback_receipt_evidence_hash(evidence_dir)
                evidence_error = None
            except (OSError, ValueError):
                evidence_sha256, evidence_entries = None, []
                evidence_error = 'evidence_incomplete_or_not_private'
            _append_readback_receipt_event(state, {
                'event': 'readback_receipt_failed', **base,
                'session_id': session_id, 'completed_at': datetime.now(timezone.utc).isoformat(),
                'failure_type': type(error).__name__,
                'evidence_dir': str(evidence_dir), 'evidence_sha256': evidence_sha256,
                'evidence_entries': evidence_entries, 'evidence_error': evidence_error,
            })
            raise
        else:
            outcome = result.get('outcome')
            try:
                evidence_sha256, evidence_entries = _readback_receipt_evidence_hash(evidence_dir)
                evidence_error = None
            except (OSError, ValueError):
                evidence_sha256, evidence_entries = None, []
                evidence_error = 'evidence_incomplete_or_not_private'
            valid_outcome = outcome in {'PASS', 'FAIL', 'BLOCKED', 'PARTIAL'}
            if not valid_outcome or evidence_sha256 is None:
                outcome = 'FAIL' if valid_outcome else 'OUTCOME_INVALID'
            if outcome == 'PASS':
                by_path = {entry['path']: entry for entry in evidence_entries}
                try:
                    receipts = [json.loads((evidence_dir / role / (role + '-readback.json')).read_text())
                                for role in ('c3', 's3')]
                except (OSError, json.JSONDecodeError):
                    receipts = []
                _audit_rows, audit_histories = _readback_receipt_audit(state)
                roles_started = audit_histories.get(policy['authorization_id'], {}).get(
                    'roles_started', set())
                if (len(receipts) != 2 or
                        roles_started != {'c3', 's3'} or
                        any(receipt.get('role') != role or receipt.get('status') != 'PASS'
                            for role, receipt in zip(('c3', 's3'), receipts)) or
                        any(receipt.get('procedure_sha256') !=
                            policy['tool_files']['collector']['sha256']
                            for receipt in receipts) or
                        any(receipt.get('application_restoration', {}).get('status') !=
                            'USB_IDENTITY_REENUMERATED' for receipt in receipts) or
                        any((role + '/' + role + '-readback.json') not in by_path
                            for role in ('c3', 's3'))):
                    outcome = 'FAIL'
            requested_outcome = result.get('outcome')
            result['outcome'] = outcome
            result['evidence_sha256'] = evidence_sha256
            _append_readback_receipt_event(state, {
                'event': 'readback_receipt_completed', **base,
                'session_id': session_id, 'completed_at': datetime.now(timezone.utc).isoformat(),
                'outcome': outcome, 'evidence_dir': str(evidence_dir),
                'evidence_sha256': evidence_sha256,
                'evidence_entries': evidence_entries, 'evidence_error': evidence_error,
            })
            if requested_outcome == 'PASS' and outcome != 'PASS':
                raise ValueError('readback_receipt_pass_evidence_validation_failed')


def _readback_receipt_cli(argv=None):
    parser = argparse.ArgumentParser(prog='gs117_hil_authorization.py')
    parser.add_argument('--claim-readback-receipt-session', dest='session_id')
    parser.add_argument('--role', choices=('c3', 's3'))
    parser.add_argument('--procedure-sha256')
    parser.add_argument('--python-runtime-sha256')
    parser.add_argument('--python-version')
    parser.add_argument('--pyserial-version')
    parser.add_argument('--runtime-tool-hashes-json')
    args = parser.parse_args(argv)
    if (not args.session_id or not args.role or not args.procedure_sha256 or
            not args.python_runtime_sha256 or not args.python_version or
            not args.pyserial_version or not args.runtime_tool_hashes_json):
        parser.error('all claim fields are required')
    try:
        runtime_tool_hashes = json.loads(args.runtime_tool_hashes_json)
        if not isinstance(runtime_tool_hashes, dict):
            raise ValueError('readback_receipt_session_claim_invalid')
        result = claim_readback_receipt_role(
            args.session_id, args.role, args.procedure_sha256,
            args.python_runtime_sha256, args.python_version,
            args.pyserial_version, runtime_tool_hashes)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({'status': 'BLOCKED', 'reason': str(error)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


def revoke_readback_receipt_authorization(reason):
    """Revoke an unused separate receipt grant; never mutates the owner manifest or hardware ledgers."""
    if (not isinstance(reason, str) or not reason.strip() or len(reason) > 240 or
            any(ord(char) < 32 for char in reason)):
        raise ValueError('readback_receipt_revocation_reason_required')
    state = Path(READBACK_RECEIPT_STATE)
    if (state.is_symlink() or not state.is_dir() or state.stat().st_uid != os.getuid() or
            state.stat().st_mode & 0o077):
        raise ValueError('readback_receipt_state_not_private')
    lock_path = state / 'session.lock'
    if lock_path.is_symlink():
        raise ValueError('readback_receipt_state_not_private')
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'r+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('readback_receipt_operation_already_active') from error
        policy = load_readback_receipt_authorization()
        base = {'authorization_id': policy['authorization_id'],
                'approval_ref': policy['owner_approval_ref'],
                'scope_sha256': _readback_receipt_scope_sha256(policy)}
        _append_readback_receipt_event(state, {
            'event': 'readback_receipt_revoked', **base,
            'revoked_at': datetime.now(timezone.utc).isoformat(),
            'reason': reason.strip(),
        })
        return {'status': 'REVOKED', 'authorization_id': policy['authorization_id']}


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
    expected_motion = bool({'tc001_campaign', 'motion_event_once'}.intersection(procedures))
    return (type(policy.get('motion_injection_authorized')) is bool and
            policy.get('motion_injection_authorized') == expected_motion)


def _development_motion_event_once_scope_valid(policy):
    """Only an isolated, one-session owner scope may authorize one USB motion input."""
    return (
        policy.get('procedures') == ['motion_event_once'] and
        policy.get('allowed_operations') == ['motion_event_once'] and
        policy.get('max_sessions') == 1 and
        policy.get('procedure_session_limits') == {'motion_event_once': 1} and
        policy.get('motion_injection_authorized') is True
    )


def _validate_development_pin_paths(path, policy):
    """Keep the active DEV manifest bound to existing GS-117 procedures."""
    path = Path(path)
    if path.resolve() == MOTION_EVENT_ONCE_POLICY.resolve():
        scope = policy.get('motion_event_once_scope')
        files = scope.get('tool_files') if isinstance(scope, dict) else None
        if (not isinstance(files, dict) or set(files) != set(MOTION_EVENT_ONCE_TOOLS) or
                any(files[name].get('path') != str(expected)
                    for name, expected in MOTION_EVENT_ONCE_TOOLS.items()
                    if isinstance(files.get(name), dict))):
            raise ValueError('motion_event_once_reviewed_procedure_path_mismatch')
        return
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


def _verify_motion_event_once_activation(policy, path, *, check_current_receipt=True,
                                         check_sources=True):
    mode = policy.get('development_mode')
    scope = policy.get('motion_event_once_scope')
    if (not isinstance(mode, dict) or not isinstance(scope, dict) or
            set(scope) != {'approval_body_sha256', 'issuance_record_sha256',
                           'source_review_sha256', 'source_review', 'tool_files',
                           'tool_hashes', 'scope_a_receipt', 'authorization_id'}):
        raise ValueError('motion_event_once_activation_scope_invalid')
    review = scope['source_review']
    if check_sources:
        review = _verify_gs117_scope_source_review(review)
    hashes = _motion_event_tool_hashes(scope['tool_files']) if check_sources else scope['tool_hashes']
    if (scope['tool_hashes'] != hashes or
            any(review.get('source_fingerprints', {}).get(name) != value
                for name, value in hashes.items()) or
            mode.get('activation_id') != scope.get('authorization_id') or
            mode.get('reviewed_commit') != review.get('reviewed_commit') or
            mode.get('reviewed_source_fingerprints') != review.get('source_fingerprints') or
            mode.get('validation_summary') != review.get('validation_summary') or
            scope.get('approval_body_sha256') != GS117_SCOPE_APPROVAL_BODY_SHA256 or
            scope.get('source_review_sha256') != _scope_approval_record_hash(review)):
        raise ValueError('motion_event_once_source_or_approval_binding_mismatch')
    if check_current_receipt:
        receipt = _verify_scope_a_readback_pass()
        if receipt != scope.get('scope_a_receipt'):
            raise ValueError('motion_event_once_scope_a_receipt_changed')
    auth_id = mode.get('activation_id')
    audit_path = Path(policy.get('activation_audit_path', ''))
    if (not isinstance(auth_id, str) or not re.fullmatch(r'[0-9a-f]{32}', auth_id) or
            audit_path.resolve() != (Path(MOTION_EVENT_ONCE_STATE) / 'audit.jsonl').resolve() or
            audit_path.is_symlink()):
        raise ValueError('motion_event_once_activation_path_invalid')
    rows = _read_private_audit(audit_path)
    activations = [row for row in rows if row.get('event') == 'motion_event_once_activated' and
                   row.get('activation_id') == auth_id]
    if len(activations) != 1:
        raise ValueError('motion_event_once_activation_audit_missing_or_replayed')
    activation = activations[0]
    expected = {
        'event': 'motion_event_once_activated',
        'activation_id': auth_id,
        'authorization_id': auth_id,
        'approval_ref': GS117_SCOPE_APPROVAL_REF,
        'authorization_scope_id': _development_scope_id(policy),
        'activated_at': policy.get('activated_at'),
        'expires_at': policy.get('expires_at'),
        'approval_body_sha256': scope['approval_body_sha256'],
        'issuance_record_sha256': scope['issuance_record_sha256'],
        'source_review_sha256': scope['source_review_sha256'],
        'reviewed_commit': review['reviewed_commit'],
        'tool_hashes': hashes,
        'scope_a_receipt': scope['scope_a_receipt'],
    }
    if (any(activation.get(key) != value for key, value in expected.items()) or
            activation.get('record_sha256') != _canonical_record_sha256(activation) or
            mode.get('activation_record_sha256') != activation.get('record_sha256')):
        raise ValueError('motion_event_once_activation_audit_mismatch')
    _verify_scope_issuance_binding(
        auth_id, 'motion_event_once', scope['issuance_record_sha256'],
        scope['approval_body_sha256'], scope['source_review_sha256'])
    if any(row.get('event') == 'motion_event_once_revoked' and
           row.get('activation_id') == auth_id for row in rows):
        raise ValueError('motion_event_once_authorization_revoked')
    return activation


def load_development(path=None, *, verify_procedure_pins=True):
    path = Path(path or DEV_POLICY)
    motion_once = path.resolve() == MOTION_EVENT_ONCE_POLICY.resolve()
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('development_consent_requires_owner_only_file')
    p = json.loads(path.read_text())
    if (motion_once and (p.get('revoked') is True or
                         (isinstance(p.get('development_mode'), dict) and
                          p['development_mode'].get('revoked') is True))):
        raise ValueError('motion_event_once_authorization_revoked')
    mode = p.get('development_mode')
    if (p.get('schema_version') != DEV_MODE_SCHEMA or p.get('profile') != 'GS117_DEV_TEST_ONLY' or
        p.get('active') is not True or p.get('revoked') is not False or
        p.get('development_mode_enabled') is not True or
        p.get('owner_approved') is not True or not p.get('owner_approval_ref') or
        str(p['owner_approval_ref']).startswith('PENDING') or p.get('identity') != IDENTITY or
        p.get('images') != DEV_IMAGES or not _development_operation_scope_valid(p) or
        p.get('prohibited_operations') != (DEV_PROHIBITED + [
            'campaign', 'bootstrap', 'flash', 'erase', 'readback', 'reset',
            's3_uart', 'retry', 'second_event'] if motion_once else DEV_PROHIBITED) or
        p.get('serial_reset_risk_accepted') is not True or
        not isinstance(mode, dict) or mode.get('enabled') is not True or
        mode.get('revoked') is not False or mode.get('persistent') is not True or
        mode.get('mode_id') != (MOTION_EVENT_ONCE_MODE_ID if motion_once else DEV_MODE_ID) or
        mode.get('expires_at') is not None or
        mode.get('environment') != 'GS117_TEST_ONLY' or
        mode.get('authorization_ref') != p.get('owner_approval_ref') or
        mode.get('authority_refs') != ({'GS-117': '11933'} if motion_once else DEV_MODE_AUTHORITY_REFS) or
        mode.get('disable_on_release_transition') is not True or
        mode.get('activation_record_sha256') is None or
        (not motion_once and not isinstance(mode.get('predecessor'), dict)) or
        (not motion_once and mode['predecessor'].get('approval_ref') == p.get('owner_approval_ref')) or
        (motion_once and (p.get('owner_approval_ref') != GS117_SCOPE_APPROVAL_REF or
                          not _development_motion_event_once_scope_valid(p)))):
        raise ValueError('development_consent_scope_mismatch')
    if _environment_is_release_qualified():
        raise ValueError('development_mode_disabled_for_release_qualification')
    activated = datetime.fromisoformat(p['activated_at'])
    if activated.tzinfo is None or activated > datetime.now(timezone.utc):
        raise ValueError('development_consent_invalid_time')
    if (not isinstance(mode.get('activated_at'), str) or
            mode['activated_at'] != p['activated_at'] or
            (not motion_once and not isinstance(mode.get('predecessor'), dict))):
        raise ValueError('development_mode_transition_invalid')
    if motion_once:
        try:
            expires = datetime.fromisoformat(p['expires_at'])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError('motion_event_once_authorization_time_invalid') from error
        if (expires.tzinfo is None or not activated <= datetime.now(timezone.utc) < expires or
                expires - activated > timedelta(seconds=GS117_SCOPE_GRANT_MAX_SECONDS['motion_event_once'])):
            raise ValueError('motion_event_once_authorization_expired_or_inactive')
        _verify_motion_event_once_activation(p, path)
        if verify_procedure_pins:
            _motion_event_tool_hashes(p['motion_event_once_scope']['tool_files'])
        return p
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
    if motion_once:
        if audit_path.resolve() != (MOTION_EVENT_ONCE_STATE / 'audit.jsonl').resolve():
            raise ValueError('motion_event_once_activation_path_invalid')
        _verify_motion_event_once_activation(p, path)
    else:
        _verify_development_mode_transition(p)
    _validate_development_pin_paths(path, p)
    if verify_procedure_pins:
        if motion_once:
            _motion_event_tool_hashes(p['motion_event_once_scope']['tool_files'])
        else:
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
        single_event_review_required = (
            bool(sensitive) and 'motion_event_once' in policy.get('procedures', []))
        if single_event_review_required:
            required_negative.update(DEV_MOTION_EVENT_PIN_REVIEW_TESTS)
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
            'single_event_scope_reviewed': single_event_review_required,
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


ENGINEERING_S3_BOOTSTRAP_SHA256 = "3f65761b13ff02d740d17a2b723939ad8c675d1541f17718fa9e8f99e3ad72b7"


def _engineering_bootstrap_files():
    root = Path(__file__).resolve().parents[3]
    script = Path.home()/'.local/state/ghar-sajag/gs117-tc001/standing-readiness-prepared/gs117-protected-bootstrap-development-v21.py'
    if script.is_symlink() or digest(script) != ENGINEERING_S3_BOOTSTRAP_SHA256:
        raise ValueError('engineering_bootstrap_reviewed_script_changed')
    return [script, Path(__file__), root/'code/tools/local/gs117_tc001_serial_windows.py',
            root/'code/tools/local/gs117_tc001_console.py',
            root/'code/tools/local/gs117_bootstrap_evidence.py',
            root/'code/tools/hil/gs40_test_bootstrap.py',
            root/'code/tests/python/test_gs117_tc001_console.py']


def review_engineering_bootstrap_sources():
    """Execute source-bound tests and register review under standing owner scope.

    This is automated review evidence, never an independent human attestation.
    Historical grants, their paths and pins are not changed.
    """
    import subprocess
    import gs179_verified_endpoint as endpoint
    endpoint.engineering_functional_admission()
    files = _engineering_bootstrap_files()
    before = {str(p): digest(p) for p in files}
    root = Path(__file__).resolve().parents[3]
    result = subprocess.run([sys.executable,str(files[-1])],cwd=root,
                            capture_output=True,text=True,timeout=180)
    report = result.stdout + result.stderr
    if result.returncode or not re.search(r'Ran [1-9][0-9]* tests',report) or not report.rstrip().endswith('OK'):
        raise ValueError('engineering_bootstrap_review_tests_failed')
    if before != {str(p):digest(p) for p in files}:
        raise ValueError('engineering_bootstrap_sources_changed_during_review')
    evidence = dict(schema='GS117_ENGINEERING_BOOTSTRAP_REVIEW_V1',
        operation='s3_runtime_bootstrap',source_files=before,
        reviewer='AUTOMATED_REVIEW_UNDER_OWNER_STANDING_SCOPE',
        reviewed_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        test_report=report,test_report_sha256=hashlib.sha256(report.encode()).hexdigest())
    sha = _canonical_record_sha256(evidence)
    target = DEV_STATE/('gs117-bootstrap-review-'+sha+'.json')
    endpoint._network_write_once(target,evidence)
    endpoint._network_event('gs117_engineering_bootstrap_reviewed',review_sha256=sha,
                            file_sha256=digest(target))
    return sha


def verify_engineering_bootstrap_review(sha):
    import gs179_verified_endpoint as endpoint
    if not re.fullmatch('[a-f0-9]{64}',sha or ''):
        raise ValueError('engineering_bootstrap_review_missing')
    target=DEV_STATE/('gs117-bootstrap-review-'+sha+'.json')
    row=endpoint._network_private_json(target)
    events=_read_private_audit(DEV_MODE_AUDIT)
    matching=[e for e in events if e.get('event')=='gs117_engineering_bootstrap_reviewed' and e.get('review_sha256')==sha]
    if (_canonical_record_sha256(row)!=sha or len(matching)!=1 or
            matching[0].get('file_sha256')!=digest(target) or
            matching[0].get('record_sha256')!=_canonical_record_sha256(matching[0]) or
            row.get('operation')!='s3_runtime_bootstrap' or
            row.get('source_files')!={str(p):digest(p) for p in _engineering_bootstrap_files()} or
            hashlib.sha256(row.get('test_report','').encode()).hexdigest()!=row.get('test_report_sha256')):
        raise ValueError('engineering_bootstrap_review_integrity_failed')
    return row


@contextmanager
def engineering_functional_session(procedure, *, bootstrap_review=None):
    """One routine real-board input with existing global locks and audit."""
    if procedure not in ('motion_event_once','s3_runtime_bootstrap'):
        raise ValueError('engineering_functional_operation_not_allowed')
    if procedure == 's3_runtime_bootstrap':
        verify_engineering_bootstrap_review(bootstrap_review)
    import gs179_verified_endpoint as endpoint
    admission=endpoint.engineering_functional_admission()
    with ExitStack() as locks:
        for directory in (STATE,DEV_STATE):
            _readback_receipt_hold_exclusive_lock(locks,directory,'engineering_hardware_operation_already_active')
        if procedure == 's3_runtime_bootstrap':
            verify_engineering_bootstrap_review(bootstrap_review)
        run={'session_id':secrets.token_hex(16),'started_at':datetime.now(timezone.utc).isoformat()}
        endpoint._network_event('gs117_engineering_input_started', **run, operation=procedure,
                                image_qualification='NOT_VERIFIED')
        policy=dict(profile='GS117_ENGINEERING_FUNCTIONAL',
                    owner_approval_ref=('GS-D034:standing-s3-runtime-bootstrap'
                        if procedure == 's3_runtime_bootstrap' else admission['owner_approval_ref']),
                    identity=admission['identity'])
        try:
            yield policy,run
        finally:
            endpoint._network_event('gs117_engineering_input_finished',session_id=run['session_id'],
                                    outcome=run.get('functional_outcome','BLOCKED'))


def development_session(procedure, path=None, state=None):
    if procedure == 'motion_event_once' and path is None:
        return motion_event_once_session()
    if path is None:
        path = MOTION_EVENT_ONCE_POLICY if procedure == 'motion_event_once' else DEV_POLICY
    path = Path(path)
    if state is None:
        if path.resolve() == MOTION_EVENT_ONCE_POLICY.resolve():
            state = MOTION_EVENT_ONCE_STATE
        elif path.resolve() == DEV_POLICY.resolve():
            state = DEV_STATE
        else:
            state = path.parent / 'development-authorization'
    p = load_development(path)
    if procedure in ('application_flash', 'test_data_erase', 'development_reprovision'):
        artifacts = p.get('recovery_artifacts', [])
        if not artifacts or any(Path(q['path']).is_symlink() or digest(q['path']) != q['sha256']
                                for q in artifacts):
            raise ValueError('development_recovery_artifacts_not_verified')
        if procedure == 'test_data_erase':
            value = p.get('pre_erase_evidence')
            if not value or not Path(value).is_absolute() or Path(value).is_symlink() or not Path(value).is_dir():
                raise ValueError('development_pre_erase_evidence_missing')
    return session(procedure, path, state, _development=True)


@contextmanager
def motion_event_once_session():
    """Reserve the isolated motion grant while excluding every other HIL scope."""
    with ExitStack() as locks:
        _hold_gs117_physical_scope_locks(
            locks, error_code='motion_event_once_hardware_operation_already_active',
            include_motion=False)
        with session('motion_event_once', MOTION_EVENT_ONCE_POLICY,
                     MOTION_EVENT_ONCE_STATE, _development=True) as result:
            yield result


def development_status(path=None):
    """Read current mode state and cumulative DEV ledger without reserving a session."""
    path = Path(path or DEV_POLICY)
    policy = load_development(path)
    scope_id = _development_scope_id(policy)
    state = (MOTION_EVENT_ONCE_STATE if path.resolve() == MOTION_EVENT_ONCE_POLICY.resolve() else
             DEV_STATE if path.resolve() == DEV_POLICY.resolve() else
             path.parent / 'development-authorization')
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


def motion_event_once_status(now=None):
    try:
        policy = load_development(MOTION_EVENT_ONCE_POLICY)
        status_value = development_status(MOTION_EVENT_ONCE_POLICY)
        if (status_value.get('sessions') == 1 or status_value.get('sessions_remaining') == 0 or
                status_value.get('status') == 'SESSION_LIMIT_REACHED'):
            return {'status': 'CONSUMED', 'authorization_id': policy['development_mode']['activation_id'],
                    'operation': 'motion_event_once', 'uses_remaining': 0,
                    'expires_at': policy['expires_at']}
        if (status_value.get('status') != 'ACTIVE' or status_value.get('sessions') != 0 or
                status_value.get('sessions_remaining') != 1 or status_value.get('blocked') is not False):
            raise ValueError('motion_event_once_authorization_consumed_or_latched')
        return {'status': 'ACTIVE',
                'authorization_id': policy['development_mode']['activation_id'],
                'operation': 'motion_event_once', 'uses_remaining': 1,
                'expires_at': policy['expires_at'],
                'sessions': status_value['sessions'],
                'sessions_remaining': status_value['sessions_remaining'],
                'blocked': status_value['blocked'],
                'authorization_scope_id': status_value['authorization_scope_id']}
    except (OSError, ValueError, KeyError, TypeError) as error:
        reason = str(error)
        if reason in {'motion_event_once_authorization_revoked', 'development_mode_revoked'}:
            return {'status': 'REVOKED', 'reason': reason}
        if 'expired' in reason:
            return {'status': 'EXPIRED_OR_INACTIVE', 'reason': reason}
        return {'status': 'BLOCKED', 'reason': reason}


def revoke_development_mode(reason, path=None):
    """Revoke the current mode once, durably auditing the disable before returning."""
    path = Path(path or DEV_POLICY)
    if path.resolve() == MOTION_EVENT_ONCE_POLICY.resolve():
        return revoke_motion_event_once_authorization(reason, path=path)
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


def revoke_motion_event_once_authorization(reason, path=None):
    """Revoke only the separately issued motion-event grant; preserve other ledgers."""
    path = Path(path or MOTION_EVENT_ONCE_POLICY)
    if path.resolve() != MOTION_EVENT_ONCE_POLICY.resolve():
        raise ValueError('motion_event_once_policy_path_mismatch')
    if (not isinstance(reason, str) or not reason.strip() or len(reason) > 240 or
            any(ord(char) < 32 for char in reason)):
        raise ValueError('motion_event_once_revocation_reason_required')
    state = Path(MOTION_EVENT_ONCE_STATE)
    state = _scope_issuance_state_private(state)
    lock_path = state / 'session.lock'
    if lock_path.is_symlink():
        raise ValueError('motion_event_once_state_not_private')
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'r+') as lock:
        info = os.fstat(lock.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('motion_event_once_state_not_private')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('motion_event_once_operation_already_active') from error
        _readback_receipt_private_file(path, 'development_consent_requires_owner_only_file')
        policy = json.loads(path.read_text())
        mode = policy.get('development_mode')
        if (policy.get('profile') != MOTION_EVENT_ONCE_PROFILE or
                policy.get('owner_approval_ref') != GS117_SCOPE_APPROVAL_REF or
                policy.get('active') is not True or policy.get('revoked') is not False or
                not isinstance(mode, dict) or mode.get('enabled') is not True or
                mode.get('revoked') is not False):
            raise ValueError('motion_event_once_authorization_not_active')
        _verify_motion_event_once_activation(policy, path, check_current_receipt=False,
                                             check_sources=False)
        history = _development_history(state, policy, _development_scope_id(policy))
        if history.get('sessions') != 0 or history.get('blocked') is True:
            raise ValueError('motion_event_once_authorization_already_consumed')
        event = {
            'event': 'motion_event_once_revoked',
            'activation_id': mode['activation_id'],
            'authorization_id': mode['activation_id'],
            'approval_ref': GS117_SCOPE_APPROVAL_REF,
            'reason': reason.strip(),
            'revoked_at': datetime.now(timezone.utc).isoformat(),
        }
        event['record_sha256'] = _canonical_record_sha256(event)
        _append_private_audit(state / 'audit.jsonl', event)
        updated = json.loads(path.read_text())
        updated.update(active=False, revoked=True, development_mode_enabled=False)
        updated['development_mode'].update(enabled=False, revoked=True,
                                            revoked_at=event['revoked_at'],
                                            revocation_record_sha256=event['record_sha256'])
        _atomic_private_json(path, updated)
        return {'status': 'REVOKED', 'authorization_id': mode['activation_id'],
                'record_sha256': event['record_sha256']}


if __name__ == '__main__':
    raise SystemExit(_readback_receipt_cli())
