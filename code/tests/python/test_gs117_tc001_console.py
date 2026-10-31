"""TC-001 software guard and correlation checks; never opens hardware."""
from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
import hashlib
import io
from http.server import ThreadingHTTPServer
import os
import ssl
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "local"))
import gs117_tc001_console as tc
import gs117_tc001_serial_windows as tc_serial
import gs117_tc001_backend as tc_backend


import gs117_hil_authorization as hil_auth
import gs117_bootstrap_evidence as bootstrap_evidence


class StandingAuthorizationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.mode_audit = self.root / 'development-authorization' / 'audit.jsonl'
        self.policy = self.root / 'policy.json'
        source = Path(__file__).resolve().parents[3] / 'docs/exec-plans/evidence/GS117_PHYSICAL_ACCESS_20261025T112221Z/standing-authorization.proposed.json'
        self.data = json.loads(source.read_text())
        self.data['controller'] = {'path': str(Path(tc.__file__)), 'sha256': hil_auth.digest(tc.__file__)}
        self.data['validator'] = {'path': str(Path(hil_auth.__file__)), 'sha256': hil_auth.digest(hil_auth.__file__)}
        now = datetime.now(timezone.utc)
        self.data.update(active=True, owner_approved=True, owner_approval_ref='unit-test-consent-only',
                         activated_at=now.isoformat(),
                         expires_at=(now + __import__('datetime').timedelta(hours=1)).isoformat())
        for name in ('serial_helper', 'bootstrap_script'):
            f = self.root / name
            f.write_text('test double, never executable')
            self.data[name] = {'path': str(f), 'sha256': hil_auth.digest(f)}
        self.data['image_receipts'] = {}
        for role in ('c3', 's3'):
            f = self.root / (role + '-receipt.json')
            f.write_text(json.dumps({'status': 'PASS', 'role': role,
                'port': hil_auth.IDENTITY[role]['port'],
                'expected_usb_serial': hil_auth.IDENTITY[role]['serial_number'],
                'trusted_artifact_sha256': hil_auth.IMAGES[role],
                'image_match': {'byte_for_byte_match': True}}))
            self.data['image_receipts'][role] = {'path': str(f), 'sha256': hil_auth.digest(f)}
        self.write()

    def write(self):
        self.policy.write_text(json.dumps(self.data)); self.policy.chmod(0o600)

    def write_mode_activation(self, policy, audit_path=None):
        audit_path = Path(audit_path or self.mode_audit)
        audit_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        audit_path.parent.chmod(0o700)
        mode = policy['development_mode']
        predecessor = mode['predecessor']
        predecessor_policy = {
            'profile': policy['profile'],
            'owner_approval_ref': predecessor['approval_ref'],
            'identity': policy['identity'],
        }
        predecessor_scope = hil_auth._development_scope_id(predecessor_policy)
        predecessor['scope_id'] = predecessor_scope
        predecessor_ledger_path = audit_path.parent / f'dev-scope-{predecessor_scope}.json'
        predecessor_counts = {'protected_gs40_bootstrap': 10, 'observe': 11,
                              'application_flash': 4, 'tc001_campaign': 4}
        predecessor_ledger = {
            'authorization_scope_id': predecessor_scope,
            'approval_ref': predecessor['approval_ref'], 'sessions': predecessor['sessions'],
            'consecutive_failures': predecessor['consecutive_failures'],
            'blocked': predecessor['blocked'], 'procedure_counts': predecessor_counts,
        }
        predecessor_ledger_path.write_text(json.dumps(predecessor_ledger, sort_keys=True))
        predecessor_ledger_path.chmod(0o600)
        old_audit = []
        procedures = [name for name, count in predecessor_counts.items() for _ in range(count)]
        for index, procedure in enumerate(procedures):
            started = datetime(2026, 10, 30, tzinfo=timezone.utc).replace(
                minute=index % 60, second=index // 60).isoformat()
            start = {'approval_ref': predecessor['approval_ref'], 'procedure': procedure,
                     'sessions': index + 1, 'blocked': True, 'started_at': started}
            old_audit.append(start)
            if index < len(procedures) - 3:
                old_audit.append({**start, 'blocked': False, 'consecutive_failures': 0,
                                  'completed_at': started})
            else:
                old_audit.append({**start, 'failure': 'ValueError',
                                  'failure_class': 'UNKNOWN_UNHANDLED',
                                  'consecutive_failures': index - (len(procedures) - 4)})
        audit_path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in old_audit))
        audit_path.chmod(0o600)
        old_bytes = audit_path.read_bytes()
        predecessor['audit_entry_count'] = len(old_audit)
        predecessor['audit_sha256'] = hashlib.sha256(old_bytes).hexdigest()
        predecessor['ledger_sha256'] = hil_auth.digest(predecessor_ledger_path)
        record = {
            'event': 'development_mode_activated',
            'activation_id': mode['activation_id'],
            'approval_ref': policy['owner_approval_ref'],
            'authorization_scope_id': hil_auth._development_scope_id(policy),
            'activated_at': mode['activated_at'],
            'authority_refs': mode['authority_refs'],
            'predecessor': mode['predecessor'],
            'reviewed_commit': mode['reviewed_commit'],
            'reviewed_source_fingerprints': mode['reviewed_source_fingerprints'],
            'validation_summary': mode['validation_summary'],
        }
        record['record_sha256'] = hil_auth._canonical_record_sha256(record)
        with audit_path.open('ab') as out:
            out.write(json.dumps(record, sort_keys=True).encode() + b'\n')
        audit_path.chmod(0o600)
        policy['activation_audit_path'] = str(audit_path)
        mode['activation_record_sha256'] = record['record_sha256']

    def development_policy(self, bootstrap_text=None, validator_text=None,
                           procedures=None, max_sessions=None):
        selected_procedures = list(hil_auth.DEV_OPERATIONS if procedures is None else procedures)
        p = dict(self.data, schema_version=hil_auth.DEV_MODE_SCHEMA,
                 profile='GS117_DEV_TEST_ONLY', procedures=selected_procedures,
                 allowed_operations=selected_procedures,
                 prohibited_operations=hil_auth.DEV_PROHIBITED, max_sessions=max_sessions,
                 development_mode_enabled=True, images=hil_auth.DEV_IMAGES,
                 motion_injection_authorized=('tc001_campaign' in selected_procedures))
        if selected_procedures != hil_auth.DEV_OPERATIONS:
            p['procedure_session_limits'] = {name: 1 for name in selected_procedures}
        p['owner_approval_ref'] = 'unit-test-consent-only'
        p['bootstrap_evidence_helper'] = {'path': str(Path(bootstrap_evidence.__file__)),
                                        'sha256': hil_auth.digest(bootstrap_evidence.__file__)}
        if bootstrap_text is not None:
            bootstrap_path = Path(p['bootstrap_script']['path'])
            bootstrap_path.write_text(bootstrap_text)
            p['bootstrap_script']['sha256'] = hil_auth.digest(bootstrap_path)
        if validator_text is not None:
            validator_path = self.root / 'validator.py'
            validator_path.write_text(validator_text)
            p['validator'] = {'path': str(validator_path), 'sha256': hil_auth.digest(validator_path)}
        p['development_mode'] = {
            'mode_id': hil_auth.DEV_MODE_ID,
            'enabled': True, 'revoked': False, 'persistent': True,
            'environment': 'GS117_TEST_ONLY', 'expires_at': None,
            'authorization_ref': p['owner_approval_ref'],
            'authority_refs': hil_auth.DEV_MODE_AUTHORITY_REFS,
            'disable_on_release_transition': True,
            'activated_at': p['activated_at'],
            'activation_id': 'unit-test-activation-0001',
            'reviewed_commit': '4' * 40,
            'reviewed_source_fingerprints': {
                name: p[name]['sha256'] for name in hil_auth.DEV_PIN_NAMES
            },
            'validation_summary': {'gs117_focused': 'PASS', 'framework': 'PASS',
                                   'feature_coverage': 'PASS'},
            'predecessor': {'approval_ref': 'unit-test-old-consent',
                            'scope_id': 'a' * 64, 'sessions': 29,
                            'consecutive_failures': 3, 'blocked': True,
                            'audit_sha256': 'b' * 64, 'ledger_sha256': 'c' * 64},
            'activation_record_sha256': None,
        }
        path = self.root / 'dev-policy.json'; path.write_text(json.dumps(p)); path.chmod(0o600)
        self.write_mode_activation(p)
        path.write_text(json.dumps(p)); path.chmod(0o600)
        self.data = p
        return path, p

    def test_dev_consent_revocation_identity_and_procedure_guards(self):
        path, p = self.development_policy()
        self.assertEqual(hil_auth.load_development(path)['identity'], hil_auth.IDENTITY)
        for change in ({'revoked': True}, {'active': False}, {'identity': {}},
                       {'profile': 'PRODUCTION'}, {'owner_approved': False},
                       {'procedures': hil_auth.DEV_OPERATIONS + ['efuse']}):
            path.write_text(json.dumps(dict(p, **change)))
            with self.assertRaises(ValueError): hil_auth.load_development(path)

    def test_development_successor_subset_denies_unapproved_operations_and_is_bounded(self):
        scope = ['protected_gs40_bootstrap', 'tc001_campaign']
        path, policy = self.development_policy(procedures=scope, max_sessions=2)
        loaded = hil_auth.load_development(path)
        self.assertEqual(loaded['procedures'], scope)
        self.assertEqual(loaded['allowed_operations'], scope)
        self.assertTrue(loaded['motion_injection_authorized'])

        state = path.parent / 'development-authorization'
        with self.assertRaisesRegex(ValueError, 'standing_policy_operation_not_authorized'):
            with hil_auth.session('application_flash', path, state, _development=True):
                self.fail('flash operation entered despite successor allowlist')
        initial_rows = [json.loads(line) for line in (state / 'audit.jsonl').read_text().splitlines()]
        self.assertFalse(any(row.get('approval_ref') == policy['owner_approval_ref'] and
                             row.get('started_at') for row in initial_rows))

        with hil_auth.session('protected_gs40_bootstrap', path, state, _development=True):
            pass
        with self.assertRaisesRegex(ValueError, 'standing_policy_procedure_limit_reached'):
            with hil_auth.session('protected_gs40_bootstrap', path, state, _development=True):
                self.fail('successor exceeded its single-bootstrap limit')
        with hil_auth.session('tc001_campaign', path, state, _development=True):
            pass
        with self.assertRaisesRegex(ValueError, 'standing_policy_failure_latched_or_limit_reached'):
            with hil_auth.session('tc001_campaign', path, state, _development=True):
                self.fail('bounded successor exceeded its session limit')
        rows = [json.loads(line) for line in (state / 'audit.jsonl').read_text().splitlines()]
        self.assertEqual(len({row['started_at'] for row in rows
                              if row.get('approval_ref') == policy['owner_approval_ref'] and
                              row.get('started_at')}), 2)
        status = hil_auth.development_status(path)
        self.assertEqual(status['status'], 'SESSION_LIMIT_REACHED')
        self.assertEqual(status['sessions_remaining'], 0)

    def test_development_subset_rejects_unbounded_duplicate_and_mismatched_scopes(self):
        path, policy = self.development_policy(
            procedures=['protected_gs40_bootstrap'], max_sessions=1)
        invalid_scopes = [
            ([], 1, False),
            (['protected_gs40_bootstrap', 'protected_gs40_bootstrap'], 1, False),
            (['protected_gs40_bootstrap', 'efuse'], 1, False),
            (['protected_gs40_bootstrap'], None, False),
            (['tc001_campaign'], 1, False),
        ]
        for procedures, maximum, motion in invalid_scopes:
            with self.subTest(procedures=procedures, maximum=maximum, motion=motion):
                value = json.loads(path.read_text())
                value['procedures'] = procedures
                value['allowed_operations'] = procedures
                value['max_sessions'] = maximum
                value['motion_injection_authorized'] = motion
                path.write_text(json.dumps(value))
                with self.assertRaisesRegex(ValueError, 'development_consent_scope_mismatch'):
                    hil_auth.load_development(path)
        mismatch = json.loads(path.read_text())
        mismatch['procedures'] = ['protected_gs40_bootstrap']
        mismatch['allowed_operations'] = ['protected_gs40_bootstrap', 'tc001_campaign']
        path.write_text(json.dumps(mismatch))
        with self.assertRaisesRegex(ValueError, 'development_consent_scope_mismatch'):
            hil_auth.load_development(path)
        valid = json.loads(json.dumps(policy))
        valid['procedure_session_limits'] = {'protected_gs40_bootstrap': 2,
                                             'tc001_campaign': 1}
        path.write_text(json.dumps(valid))
        with self.assertRaisesRegex(ValueError, 'development_consent_scope_mismatch'):
            hil_auth.load_development(path)
        valid['procedure_session_limits'] = {'protected_gs40_bootstrap': True,
                                             'tc001_campaign': 1}
        path.write_text(json.dumps(valid))
        with self.assertRaisesRegex(ValueError, 'development_consent_scope_mismatch'):
            hil_auth.load_development(path)

    def test_development_mode_is_persistent_unexpired_and_audits_repeated_sessions(self):
        path, policy = self.development_policy()
        state = self.root / 'development-authorization'
        self.assertIsNone(policy['max_sessions'])
        self.assertIsNone(policy['development_mode']['expires_at'])
        for _ in range(5):
            with hil_auth.session('observe', path, state, _development=True): pass
        status = hil_auth.development_status(path)
        self.assertEqual(status['status'], 'ACTIVE')
        self.assertTrue(status['development_mode_enabled'])
        self.assertTrue(status['persistent'])
        self.assertIsNone(status['expires_at'])
        self.assertEqual(status['sessions'], 5)
        audit = [json.loads(line) for line in (state/'audit.jsonl').read_text().splitlines()]
        scoped = [row for row in audit if row.get('approval_ref') == policy['owner_approval_ref']]
        self.assertEqual(len({row['started_at'] for row in scoped if row.get('started_at')}), 5)

    def _review_test_receipt(self, _repo, commit, scope_sha256, negative_tests):
        output = hashlib.sha256(b'focused validation passed').hexdigest()
        return {
            'schema_version': 1, 'reviewed_commit': commit,
            'scope_contract_sha256': scope_sha256,
            'reviewed_negative_tests': sorted(set(negative_tests)),
            'created_at': datetime.now(timezone.utc).isoformat(),
            'tests': [
                {'name': 'gs117_focused',
                 'command': [sys.executable, 'code/tests/python/test_gs117_tc001_console.py'],
                 'returncode': 0, 'test_count': 1,
                 'stdout_sha256': output, 'stderr_sha256': output},
                {'name': 'feature_coverage',
                 'command': ['make', '-C', 'code', 'feature-coverage-test'],
                 'returncode': 0, 'test_count': 1,
                 'coverage_summary': 'GS130 TRACEABILITY PASS features=1 modules=1 physical_cases=1; consistency only, not semantic/physical PASS',
                 'stdout_sha256': output, 'stderr_sha256': output},
            ],
        }

    def test_reviewed_source_update_is_chained_and_preserves_session_history(self):
        stale = '66afe888be5dcd3c862bcddc4cc6333945870b8a41bd552f9cb0e3472676058e'
        bootstrap = ("if hashlib.sha256(helper).hexdigest() != '" + stale + "':\n"
                     "    raise ValueError('REVIEWED_SERIAL_HELPER_CHANGED')\n"
                     "subprocess.Popen([WINPY])\n")
        path, policy = self.development_policy(bootstrap_text=bootstrap,
                                               validator_text='old authorization validator\n')
        original_policy_bytes = path.read_bytes()
        bootstrap_path = Path(policy['bootstrap_script']['path'])
        bootstrap_path.chmod(0o600)
        backup = self.root / 'bootstrap.before-pin-update.py'
        backup.write_bytes(bootstrap_path.read_bytes()); backup.chmod(0o600)
        helper_hash = policy['serial_helper']['sha256']
        bootstrap_path.write_text(bootstrap.replace(stale, helper_hash, 1))
        validator_path = Path(policy['validator']['path'])
        validator_path.write_text('reviewed authorization validator with chained source updates\n')
        audit_path = Path(policy['activation_audit_path'])
        original_audit = audit_path.read_bytes()
        negative_tests = [
            'test_dev_consent_revocation_identity_and_procedure_guards',
            'test_activation_record_binds_reviewed_commit_and_source_pins',
            'test_campaign_safety_failure_latches_and_denies_next_operation',
        ]
        commit = 'a' * 40
        with (patch.object(hil_auth, '_current_development_commit', return_value=commit),
              patch.object(hil_auth, '_run_development_review_tests', side_effect=self._review_test_receipt)):
            result = hil_auth.review_development_source_updates(
                'Reviewed exact stale nested helper pin correction; authorization scope and fail-closed guards unchanged.',
                negative_tests, bootstrap_backup=backup, path=path)
        loaded = hil_auth.load_development(path)
        self.assertEqual(result['status'], 'SOURCE_UPDATE_RECORDED')
        self.assertEqual(loaded['bootstrap_script']['sha256'], hil_auth.digest(bootstrap_path))
        self.assertEqual(loaded['validator']['sha256'], hil_auth.digest(validator_path))
        self.assertEqual(audit_path.read_bytes().startswith(original_audit), True)
        rows = [json.loads(line) for line in audit_path.read_text().splitlines()]
        update = next(row for row in rows if row.get('event') == 'development_mode_source_reviewed')
        self.assertEqual(update['changed_sources'], ['bootstrap_script', 'validator'])
        self.assertEqual(update['reviewed_commit'], commit)
        backup = Path(update['previous_manifest_backup_path'])
        self.assertEqual(backup.read_bytes(), original_policy_bytes)
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        status = hil_auth.development_status(path)
        self.assertEqual(status['sessions'], 0)
        self.assertFalse(status['blocked'])

    def test_reviewed_pin_update_fails_closed_if_manifest_backup_changes(self):
        path, policy = self.development_policy(validator_text='before\n')
        original_policy_bytes = path.read_bytes()
        Path(policy['validator']['path']).write_text('after\n')
        negatives = [
            'test_dev_consent_revocation_identity_and_procedure_guards',
            'test_activation_record_binds_reviewed_commit_and_source_pins',
            'test_campaign_safety_failure_latches_and_denies_next_operation',
        ]
        with (patch.object(hil_auth, '_current_development_commit', return_value='e'*40),
              patch.object(hil_auth, '_run_development_review_tests', side_effect=self._review_test_receipt)):
            hil_auth.review_development_source_updates(
                'Reviewed authorization update with original manifest bytes preserved.',
                negatives, path=path)
        audit = Path(policy['activation_audit_path'])
        review = next(row for row in map(json.loads, audit.read_text().splitlines())
                      if row.get('event') == 'development_mode_source_reviewed')
        backup = Path(review['previous_manifest_backup_path'])
        self.assertEqual(backup.read_bytes(), original_policy_bytes)
        backup.write_bytes(b'altered prior policy')
        backup.chmod(0o600)
        with self.assertRaisesRegex(ValueError, 'manifest_backup_invalid'):
            hil_auth.load_development(path)

    def test_reviewed_pin_update_rejects_non_object_manifest_backup(self):
        path, policy = self.development_policy(validator_text='before\n')
        Path(policy['validator']['path']).write_text('after\n')
        with (patch.object(hil_auth, '_current_development_commit', return_value='f'*40),
              patch.object(hil_auth, '_run_development_review_tests', side_effect=self._review_test_receipt)):
            hil_auth.review_development_source_updates(
                'Reviewed authorization source update with authenticated policy backup validation.',
                ['test_dev_consent_revocation_identity_and_procedure_guards',
                 'test_activation_record_binds_reviewed_commit_and_source_pins',
                 'test_campaign_safety_failure_latches_and_denies_next_operation'], path=path)
        audit = Path(policy['activation_audit_path'])
        review = next(row for row in map(json.loads, audit.read_text().splitlines())
                      if row.get('event') == 'development_mode_source_reviewed')
        backup = Path(review['previous_manifest_backup_path'])
        backup.write_text('[]\n')
        backup.chmod(0o600)
        with self.assertRaisesRegex(ValueError, 'manifest_backup_invalid'):
            hil_auth.load_development(path)

    def test_reviewed_source_update_requires_sensitive_negative_tests_and_intact_chain(self):
        path, policy = self.development_policy(validator_text='initial validator\n')
        validator_path = Path(policy['validator']['path'])
        validator_path.write_text('changed authorization validator\n')
        audit_path = Path(policy['activation_audit_path'])
        audit_before = audit_path.read_bytes()
        with (patch.object(hil_auth, '_current_development_commit', return_value='b' * 40),
              patch.object(hil_auth, '_run_development_review_tests', side_effect=self._review_test_receipt)):
            with self.assertRaisesRegex(ValueError, 'negative_tests_missing'):
                hil_auth.review_development_source_updates(
                    'Reviewed authorization verifier update with its bounded test set.',
                    ['test_dev_consent_revocation_identity_and_procedure_guards'], path=path)
        self.assertEqual(audit_path.read_bytes(), audit_before)
        self.assertEqual(json.loads(path.read_text())['validator']['sha256'], policy['validator']['sha256'])

    def test_source_review_rejects_unregistered_negative_test_names(self):
        path, policy = self.development_policy(validator_text='initial validator\n')
        Path(policy['validator']['path']).write_text('changed validator\n')
        negatives = [
            'test_dev_consent_revocation_identity_and_procedure_guards',
            'test_activation_record_binds_reviewed_commit_and_source_pins',
            'test_campaign_safety_failure_latches_and_denies_next_operation',
            'test_not_a_registered_regression',
        ]
        with patch.object(hil_auth, '_current_development_commit', return_value='b'*40):
            with self.assertRaisesRegex(ValueError, 'negative_test_unregistered'):
                hil_auth.review_development_source_updates(
                    'Reviewed authorization update with required fail-closed regression coverage.',
                    negatives, path=path)

    def test_source_review_requires_real_nonzero_test_summaries(self):
        reviewed = ['test_dev_consent_revocation_identity_and_procedure_guards']
        good_unit = SimpleNamespace(returncode=0, stdout='', stderr='Ran 2 tests in 1.2s\n')
        good_coverage = SimpleNamespace(returncode=0,
            stdout='GS130 TRACEABILITY PASS features=2 modules=3 physical_cases=4; consistency only, not semantic/physical PASS\n',
            stderr='Ran 3 tests in 1.2s\n')
        with patch.object(hil_auth.subprocess, 'run', side_effect=[good_unit, good_coverage]):
            receipt = hil_auth._run_development_review_tests(self.root, 'a'*40, 'b'*64, reviewed)
        self.assertEqual([item['test_count'] for item in receipt['tests']], [2, 3])
        self.assertEqual(receipt['tests'][1]['coverage_summary'], good_coverage.stdout.strip())

        missing_summary = SimpleNamespace(returncode=0, stdout='all green\n', stderr='')
        with patch.object(hil_auth.subprocess, 'run', return_value=missing_summary):
            with self.assertRaisesRegex(ValueError, 'tests_incomplete:gs117_focused'):
                hil_auth._run_development_review_tests(self.root, 'a'*40, 'b'*64, reviewed)

        no_coverage_marker = SimpleNamespace(returncode=0, stdout='Ran 22 tests in 1.2s\n', stderr='')
        with patch.object(hil_auth.subprocess, 'run', side_effect=[good_unit, no_coverage_marker]):
            with self.assertRaisesRegex(ValueError, 'tests_incomplete:feature_coverage'):
                hil_auth._run_development_review_tests(self.root, 'a'*40, 'b'*64, reviewed)

        skipped = SimpleNamespace(returncode=0, stdout='',
                                  stderr='Ran 2 tests in 1.2s\nOK (skipped=1)\n')
        with patch.object(hil_auth.subprocess, 'run', return_value=skipped):
            with self.assertRaisesRegex(ValueError, 'tests_incomplete:gs117_focused'):
                hil_auth._run_development_review_tests(self.root, 'a'*40, 'b'*64, reviewed)

    def test_pin_chain_tampering_fails_closed(self):
        path, policy = self.development_policy(validator_text='old validator\n')
        validator_path = Path(policy['validator']['path'])
        validator_path.write_text('new validator\n')
        negatives = [
            'test_dev_consent_revocation_identity_and_procedure_guards',
            'test_activation_record_binds_reviewed_commit_and_source_pins',
            'test_campaign_safety_failure_latches_and_denies_next_operation',
        ]
        with (patch.object(hil_auth, '_current_development_commit', return_value='c' * 40),
              patch.object(hil_auth, '_run_development_review_tests', side_effect=self._review_test_receipt)):
            hil_auth.review_development_source_updates(
                'Reviewed validator update with negative identity, scope and safety-latch tests.',
                negatives, path=path)
        audit_path = Path(policy['activation_audit_path'])
        rows = audit_path.read_text().splitlines()
        record = json.loads(rows[-1]); record['review_summary'] = 'unverified rewrite'
        rows[-1] = json.dumps(record, sort_keys=True)
        audit_path.write_text('\n'.join(rows) + '\n'); audit_path.chmod(0o600)
        with self.assertRaisesRegex(ValueError, 'source_review_chain_invalid'):
            hil_auth.load_development(path)

    def test_exact_preoperation_pin_failure_is_disposed_without_deleting_session(self):
        stale = '66afe888be5dcd3c862bcddc4cc6333945870b8a41bd552f9cb0e3472676058e'
        bootstrap = ("if hashlib.sha256(helper).hexdigest() != '" + stale + "':\n"
                     "    raise ValueError('REVIEWED_SERIAL_HELPER_CHANGED')\n"
                     "subprocess.Popen([WINPY])\n")
        path, policy = self.development_policy(bootstrap_text=bootstrap,
                                               validator_text='old authorization validator\n')
        state = Path(policy['activation_audit_path']).parent
        evidence_root = self.root / 'standing-authorization-evidence'
        evidence_root.mkdir(mode=0o700)
        evidence = evidence_root / 'bootstrap-known-pin-mismatch'
        evidence.mkdir(mode=0o700)
        (evidence / 'stdout.json').write_text(
            'BOOTSTRAP_FAILED_STAGE=startup TYPE=ValueError CODE=REVIEWED_SERIAL_HELPER_CHANGED\n')
        (evidence / 'stderr.log').write_text('')
        for item in evidence.iterdir(): item.chmod(0o600)
        with patch.object(hil_auth, 'STATE', evidence_root):
            with self.assertRaisesRegex(ValueError, 'REVIEWED_SERIAL_HELPER_CHANGED'):
                with hil_auth.session('protected_gs40_bootstrap', path, state, _development=True) as (_p, record):
                    record['evidence'] = str(evidence)
                    raise ValueError('REVIEWED_SERIAL_HELPER_CHANGED')
            failed_audit = Path(policy['activation_audit_path']).read_bytes()
            bootstrap_path = Path(policy['bootstrap_script']['path'])
            backup = self.root / 'bootstrap.before-pin-disposition.py'
            backup.write_bytes(bootstrap_path.read_bytes()); backup.chmod(0o600)
            bootstrap_path.write_text(bootstrap.replace(stale, policy['serial_helper']['sha256'], 1))
            Path(policy['validator']['path']).write_text('reviewed authorization validator\n')
            negatives = [
                'test_dev_consent_revocation_identity_and_procedure_guards',
                'test_activation_record_binds_reviewed_commit_and_source_pins',
                'test_campaign_safety_failure_latches_and_denies_next_operation',
            ]
            with (patch.object(hil_auth, '_current_development_commit', return_value='d' * 40),
                  patch.object(hil_auth, '_run_development_review_tests', side_effect=self._review_test_receipt)):
                hil_auth.review_development_source_updates(
                    'Reviewed exact pre-device nested pin correction and authorization verifier negative tests.',
                    negatives, bootstrap_backup=backup, path=path)
            with patch.object(hil_auth, '_write_private_ledger', side_effect=OSError('simulated interruption')):
                with self.assertRaisesRegex(OSError, 'simulated interruption'):
                    hil_auth.dispose_reviewed_preoperation_pin_failure(path)
            result = hil_auth.dispose_reviewed_preoperation_pin_failure(path)
            status = hil_auth.development_status(path)
            self.assertEqual(result['status'], 'DISPOSITION_ALREADY_RECORDED')
            self.assertEqual(result['sessions'], 1)
            self.assertEqual(result['functional_outcome'], 'NOT_RUN')
            self.assertEqual(status['status'], 'ACTIVE')
            self.assertEqual(status['sessions'], 1)
            self.assertEqual(status['consecutive_safety_failures'], 0)
            self.assertEqual(status['reviewed_failure_dispositions'], 1)
            audit_after = Path(policy['activation_audit_path']).read_bytes()
            self.assertTrue(audit_after.startswith(failed_audit))
            self.assertEqual(sum(row.get('event') == 'development_failure_disposition'
                                 for row in map(json.loads, audit_after.splitlines())), 1)
            old_rows = [json.loads(line) for line in failed_audit.splitlines()]
            self.assertTrue(any(row.get('failure') == 'ValueError' and
                                row.get('failure_class') == 'UNKNOWN_UNHANDLED' for row in old_rows))
            self.assertEqual(status['authorization_scope_id'], hil_auth._development_scope_id(policy))

    def test_preoperation_disposition_rejects_nonmatching_security_failure(self):
        path, policy = self.development_policy()
        state = Path(policy['activation_audit_path']).parent
        with self.assertRaisesRegex(hil_auth.AuthorizationSafetyFailure, 'identity mismatch'):
            with hil_auth.session('protected_gs40_bootstrap', path, state, _development=True):
                raise hil_auth.AuthorizationSafetyFailure('identity mismatch')
        with self.assertRaisesRegex(ValueError, 'not_disposition_eligible'):
            hil_auth.dispose_reviewed_preoperation_pin_failure(path)

    def test_release_qualification_environment_fails_closed(self):
        path, _policy = self.development_policy()
        with patch.dict(os.environ, {'GHAR_SAJAG_QUALIFICATION_MODE': 'release_candidate'}):
            with self.assertRaisesRegex(ValueError, 'disabled_for_release_qualification'):
                hil_auth.load_development(path)

    def test_activation_record_is_mandatory_and_immutable(self):
        path, policy = self.development_policy()
        audit = Path(policy['activation_audit_path'])
        original = audit.read_bytes()
        audit.unlink()
        with self.assertRaisesRegex(ValueError, 'transition_audit_missing'):
            hil_auth.load_development(path)
        audit.write_bytes(original); audit.chmod(0o600)
        rows = audit.read_text().splitlines()
        index = next(i for i, line in enumerate(rows)
                     if json.loads(line).get('event') == 'development_mode_activated')
        record = json.loads(rows[index]); record['predecessor']['sessions'] += 1
        rows[index] = json.dumps(record, sort_keys=True)
        audit.write_text('\n'.join(rows) + '\n'); audit.chmod(0o600)
        with self.assertRaisesRegex(ValueError, 'transition_audit_mismatch'):
            hil_auth.load_development(path)

    def test_activation_record_binds_reviewed_commit_and_source_pins(self):
        path, policy = self.development_policy()
        original = json.loads(path.read_text())
        original['controller']['sha256'] = '0' * 64
        path.write_text(json.dumps(original)); path.chmod(0o600)
        with self.assertRaisesRegex(ValueError, 'review_evidence_invalid'):
            hil_auth.load_development(path)
        path.write_text(json.dumps(policy)); path.chmod(0o600)
        changed = json.loads(path.read_text())
        changed['development_mode']['reviewed_commit'] = '5' * 40
        path.write_text(json.dumps(changed)); path.chmod(0o600)
        with self.assertRaisesRegex(ValueError, 'transition_audit_mismatch'):
            hil_auth.load_development(path)

    def test_revocation_is_audited_and_disables_future_sessions(self):
        path, _policy = self.development_policy()
        state = self.root / 'development-authorization'
        before = (state/'audit.jsonl').read_bytes()
        stale = json.loads(path.read_text())
        stale['controller']['sha256'] = '0' * 64
        path.write_text(json.dumps(stale)); path.chmod(0o600)
        result = hil_auth.revoke_development_mode('owner ended development phase', path)
        self.assertEqual(result['status'], 'REVOKED')
        with self.assertRaises(ValueError):
            with hil_auth.session('observe', path, state, _development=True): pass
        rows = [json.loads(line) for line in (state/'audit.jsonl').read_text().splitlines()]
        events = [row for row in rows if row.get('event') in {
            'development_mode_activated', 'development_mode_revoked'}]
        self.assertEqual([row['event'] for row in events], [
            'development_mode_activated', 'development_mode_revoked'])
        self.assertEqual(rows[-1]['event'], 'development_mode_revoked')
        self.assertTrue((state/'audit.jsonl').read_bytes().startswith(before))
        self.assertFalse(json.loads(path.read_text())['development_mode_enabled'])

    def test_explicit_transition_keeps_predecessor_latch_separate(self):
        path, policy = self.development_policy()
        predecessor = policy['development_mode']['predecessor']
        self.assertEqual(predecessor['sessions'], 29)
        self.assertEqual(predecessor['consecutive_failures'], 3)
        self.assertTrue(predecessor['blocked'])
        self.assertNotEqual(policy['owner_approval_ref'], predecessor['approval_ref'])
        state = self.root / 'development-authorization'
        old_bytes = (state/'audit.jsonl').read_bytes()
        old_ledger_path = state / f"dev-scope-{predecessor['scope_id']}.json"
        old_ledger_bytes = old_ledger_path.read_bytes()
        with hil_auth.session('observe', path, state, _development=True): pass
        self.assertTrue((state/'audit.jsonl').read_bytes().startswith(old_bytes))
        self.assertEqual(old_ledger_path.read_bytes(), old_ledger_bytes)
        self.assertEqual(hil_auth.development_status(path)['sessions'], 1)
        self.assertEqual(policy['development_mode']['predecessor']['sessions'], 29)

    def test_dev_failures_are_preserved_and_bounded_without_one_use_latch(self):
        path, _p = self.development_policy()
        state = self.root / 'dev-audit'
        with self.assertRaisesRegex(ValueError, 'diagnosed_test_failure'):
            with hil_auth.session('observe', path, state, _development=True):
                raise ValueError('diagnosed_test_failure')
        with self.assertRaisesRegex(ValueError, 'limit_reached'):
            with hil_auth.session('observe', path, state, _development=True): pass
        self.assertEqual(len((state/'audit.jsonl').read_text().splitlines()), 2)

    def test_dev_policy_hash_rotation_preserves_audit_usage_and_failure_latch(self):
        path, policy = self.development_policy()
        state = self.root / 'dev-rotation-audit'
        state.mkdir(mode=0o700)
        approval = policy['owner_approval_ref']
        starts = [f'2026-10-30T00:00:0{i}+00:00' for i in range(4)]
        history = []
        for index, started in enumerate(starts):
            procedure = 'tc001_campaign' if index == 2 else 'observe'
            initial = {'approval_ref': approval, 'sessions': index + 1,
                       'blocked': True, 'procedure': procedure, 'started_at': started}
            history.append(initial)
            if index == 1:
                history.append({**initial, 'blocked': False, 'consecutive_failures': 0,
                                'completed_at': '2026-10-30T00:10:00+00:00'})
            else:
                failures = 1 if index == 0 else index - 1
                history.append({**initial, 'failure': 'ValueError',
                                'consecutive_failures': failures})
        (state / 'audit.jsonl').write_text(
            ''.join(json.dumps(item) + '\n' for item in history))
        (state / 'audit.jsonl').chmod(0o600)
        legacy = state / (hil_auth.digest(path) + '.json')
        legacy_data = {**history[-1], 'sessions': 2, 'consecutive_failures': 2}
        legacy.write_text(json.dumps(legacy_data)); legacy.chmod(0o600)
        legacy_bytes = legacy.read_bytes()

        old_policy_sha = hil_auth.digest(path)
        policy['activation_note'] = 'same owner consent; reviewed procedure pin update'
        path.write_text(json.dumps(policy)); path.chmod(0o600)
        self.assertNotEqual(hil_auth.digest(path), old_policy_sha)

        with self.assertRaisesRegex(ValueError, 'failure_latched_or_limit_reached'):
            with hil_auth.session('observe', path, state, _development=True): pass
        stable, scope_id = hil_auth._development_ledger_path(state, policy)
        migrated = json.loads(stable.read_text())
        self.assertEqual(migrated['authorization_scope_id'], scope_id)
        self.assertEqual(migrated['sessions'], 4)
        self.assertEqual(migrated['consecutive_failures'], 2)
        self.assertEqual(migrated['procedure_counts']['observe'], 3)
        self.assertEqual(migrated['procedure_counts']['tc001_campaign'], 1)
        self.assertTrue(migrated['blocked'])
        self.assertEqual(legacy.read_bytes(), legacy_bytes)
        audit = [json.loads(line) for line in (state / 'audit.jsonl').read_text().splitlines()]
        migration = [row for row in audit
                     if row.get('event') == 'development_ledger_reconstructed_from_audit']
        self.assertEqual(len(migration), 1)
        self.assertNotIn('started_at', migration[0])
        self.assertEqual(len({row['started_at'] for row in audit if row.get('started_at')}), 4)
        with self.assertRaisesRegex(ValueError, 'failure_latched_or_limit_reached'):
            with hil_auth.session('observe', path, state, _development=True): pass

    def test_dev_stable_ledger_cannot_diverge_from_append_only_audit(self):
        path, policy = self.development_policy()
        state = self.root / 'dev-ledger-audit-mismatch'
        with hil_auth.session('observe', path, state, _development=True): pass
        ledger, _scope = hil_auth._development_ledger_path(state, policy)
        changed = json.loads(ledger.read_text())
        changed.update(sessions=0, procedure_counts={})
        ledger.write_text(json.dumps(changed)); ledger.chmod(0o600)
        before = ledger.read_bytes()

        with self.assertRaisesRegex(ValueError, 'development_authorization_history_mismatch'):
            with hil_auth.session('observe', path, state, _development=True): pass
        self.assertEqual(ledger.read_bytes(), before)

    def test_dev_failure_after_success_is_not_hidden_by_stale_completion(self):
        path, policy = self.development_policy()
        state = self.root / 'dev-success-then-failure'
        with hil_auth.session('observe', path, state, _development=True): pass
        with self.assertRaisesRegex(RuntimeError, 'target failed'):
            with hil_auth.session('observe', path, state, _development=True):
                raise RuntimeError('target failed')

        scope_id = hil_auth._development_scope_id(policy)
        history = hil_auth._development_history(state, policy, scope_id)
        self.assertEqual(history['sessions'], 2)
        self.assertEqual(history['consecutive_failures'], 1)
        self.assertTrue(history['blocked'])
        self.assertNotIn('completed_at', history)
        self.assertEqual(history['failure'], 'RuntimeError')

    def test_dev_failure_latches_until_a_new_approved_scope(self):
        path, policy = self.development_policy()
        state = self.root / 'dev-failure-then-success'
        with self.assertRaisesRegex(RuntimeError, 'transient failure'):
            with hil_auth.session('observe', path, state, _development=True):
                raise RuntimeError('transient failure')
        with self.assertRaisesRegex(ValueError, 'failure_latched_or_limit_reached'):
            with hil_auth.session('observe', path, state, _development=True): pass

        scope_id = hil_auth._development_scope_id(policy)
        history = hil_auth._development_history(state, policy, scope_id)
        self.assertEqual(history['sessions'], 1)
        self.assertEqual(history['consecutive_failures'], 1)
        self.assertTrue(history['blocked'])
        self.assertEqual(history['failure_class'], 'UNKNOWN_UNHANDLED')

        policy['owner_approval_ref'] = 'separate-unit-test-consent-after-latch'
        policy['development_mode']['authorization_ref'] = policy['owner_approval_ref']
        policy['development_mode']['activation_id'] = 'unit-test-successor-0001'
        successor_audit = self.root / 'successor-development-authorization' / 'audit.jsonl'
        self.write_mode_activation(policy, successor_audit)
        successor = self.root / 'new-dev-scope.json'
        successor.write_text(json.dumps(policy)); successor.chmod(0o600)
        with hil_auth.session('observe', successor, state, _development=True): pass
        self.assertEqual(hil_auth._development_history(state, policy, scope_id)['sessions'], 1)
        successor_ledger, _ = hil_auth._development_ledger_path(state, policy)
        self.assertEqual(json.loads(successor_ledger.read_text())['sessions'], 1)

    def test_functional_campaign_outcome_is_audited_without_safety_latch(self):
        path, policy = self.development_policy()
        state = self.root / 'dev-functional-outcome'
        with hil_auth.session('tc001_campaign', path, state, _development=True) as (_p, record):
            record['functional_outcome'] = 'FAIL'
        scope_id = hil_auth._development_scope_id(policy)
        history = hil_auth._development_history(state, policy, scope_id)
        self.assertEqual(history['functional_outcome'], 'FAIL')
        self.assertEqual(history['consecutive_failures'], 0)
        self.assertFalse(history['blocked'])
        self.assertEqual(hil_auth.development_status(path)['status'], 'ACTIVE')
        with hil_auth.session('tc001_campaign', path, state, _development=True): pass

    def test_campaign_functional_failure_keeps_session_reusable(self):
        path, policy = self.development_policy()
        state = self.root / 'dev-campaign-functional-failure'
        fixture = {"home_id": "gs177-test-product", "physical_device_id": "c3-146393c5d158",
                   "hub_id": "hub-e072a1d38d34",
                   "c3": {"port": "COM4", "serial_number": "14:63:93:C5:D1:58"},
                   "s3": {"port": "COM10", "serial_number": "E0:72:A1:D3:8D:34"}}
        readiness = {"backend": {"POSTGRES_READY": "PASS", "CAREGIVER_HTTPS_READY": "PASS",
                                  "DEVELOPMENT_ENDPOINT_READY": "PASS"},
                     "caregiver_home": {"caregiver_home_ready": True},
                     "physical_boards": {"c3": "PASS", "s3": "PASS"},
                     "fixture": {"status": "PASS"}, "android_apk": {"status": "PASS"},
                     "hub_ingress": {"status": "PASS"}}
        controller = tc.Controller(); controller.lock.acquire()
        campaign = {"run_id": "TC001-CAMPAIGN-functional", "planned_runs": 5,
                    "passed_runs": 0, "completed_runs": 0, "runs": [], "overall": "PARTIAL",
                    "stages": {"campaign_preflight": {"status": "NOT_VERIFIED"}}}
        def fail_run(report, **_kwargs):
            report["overall"] = "FAIL"
            report["stages"]["android_apk"] = {"status": "FAIL", "reason": "observer failed"}
        with (patch.object(hil_auth, "DEV_POLICY", path),
              patch.object(hil_auth, "DEV_STATE", state),
              patch.object(controller, "readiness", return_value=readiness),
              patch.object(tc, "exact_fixture", return_value=fixture),
              patch.object(tc, "campaign_approval", return_value={
                  "approval_ref": policy["owner_approval_ref"], "development_authorization": True}),
              patch.object(controller, "execute", side_effect=fail_run),
              patch.object(controller, "save")):
            controller.execute_campaign(campaign)
            stable, _ = hil_auth._development_ledger_path(state, policy)
            ledger = json.loads(stable.read_text())
            self.assertEqual(campaign["overall"], "FAIL")
            self.assertEqual(campaign["functional_outcome"], "FAIL")
            self.assertEqual(campaign["authorization_outcome"], "AUTHORIZED_SCOPE_OPERATION")
            self.assertEqual(campaign["completed_runs"], 1)
            self.assertEqual(ledger["functional_outcome"], "FAIL")
            self.assertEqual(ledger["consecutive_failures"], 0)
            self.assertFalse(ledger["blocked"])
            self.assertFalse(controller.lock.locked())
            with hil_auth.development_session("tc001_campaign"):
                pass

    def test_campaign_safety_failure_latches_and_denies_next_operation(self):
        path, policy = self.development_policy()
        state = self.root / 'dev-campaign-safety-failure'
        fixture = {"home_id": "gs177-test-product", "physical_device_id": "c3-146393c5d158",
                   "hub_id": "hub-e072a1d38d34",
                   "c3": {"port": "COM4", "serial_number": "14:63:93:C5:D1:58"},
                   "s3": {"port": "COM10", "serial_number": "E0:72:A1:D3:8D:34"}}
        readiness = {"backend": {"POSTGRES_READY": "PASS", "CAREGIVER_HTTPS_READY": "PASS",
                                  "DEVELOPMENT_ENDPOINT_READY": "PASS"},
                     "caregiver_home": {"caregiver_home_ready": True},
                     "physical_boards": {"c3": "PASS", "s3": "PASS"},
                     "fixture": {"status": "PASS"}, "android_apk": {"status": "PASS"},
                     "hub_ingress": {"status": "PASS"}}
        controller = tc.Controller(); controller.lock.acquire()
        campaign = {"run_id": "TC001-CAMPAIGN-safety", "planned_runs": 5,
                    "passed_runs": 0, "completed_runs": 0, "runs": [], "overall": "PARTIAL",
                    "stages": {"campaign_preflight": {"status": "NOT_VERIFIED"}}}
        with (patch.object(hil_auth, "DEV_POLICY", path),
              patch.object(hil_auth, "DEV_STATE", state),
              patch.object(controller, "readiness", return_value=readiness),
              patch.object(tc, "exact_fixture", return_value=fixture),
              patch.object(tc, "campaign_approval", return_value={
                  "approval_ref": policy["owner_approval_ref"], "development_authorization": True}),
              patch.object(controller, "execute", side_effect=hil_auth.AuthorizationSafetyFailure(
                  "TC001_VERIFIED_USB_INTERFACE_MISMATCH")),
              patch.object(controller, "save")):
            controller.execute_campaign(campaign)
            stable, _ = hil_auth._development_ledger_path(state, policy)
            ledger = json.loads(stable.read_text())
            self.assertEqual(ledger["failure_class"], "AUTHORIZATION_SAFETY")
            self.assertTrue(ledger["blocked"])
            self.assertEqual(campaign["authorization_outcome"], "SAFETY_FAILURE")
            self.assertEqual(campaign["functional_outcome"], "BLOCKED")
            self.assertFalse(controller.lock.locked())
            with self.assertRaisesRegex(ValueError, "failure_latched_or_limit_reached"):
                with hil_auth.development_session("tc001_campaign"):
                    pass

    def test_campaign_unhandled_failure_is_latched_conservatively(self):
        path, policy = self.development_policy()
        state = self.root / 'dev-campaign-unhandled-failure'
        fixture = {"home_id": "gs177-test-product", "physical_device_id": "c3-146393c5d158",
                   "hub_id": "hub-e072a1d38d34",
                   "c3": {"port": "COM4", "serial_number": "14:63:93:C5:D1:58"},
                   "s3": {"port": "COM10", "serial_number": "E0:72:A1:D3:8D:34"}}
        readiness = {"backend": {"POSTGRES_READY": "PASS", "CAREGIVER_HTTPS_READY": "PASS",
                                  "DEVELOPMENT_ENDPOINT_READY": "PASS"},
                     "caregiver_home": {"caregiver_home_ready": True},
                     "physical_boards": {"c3": "PASS", "s3": "PASS"},
                     "fixture": {"status": "PASS"}, "android_apk": {"status": "PASS"},
                     "hub_ingress": {"status": "PASS"}}
        controller = tc.Controller(); controller.lock.acquire()
        campaign = {"run_id": "TC001-CAMPAIGN-unhandled", "planned_runs": 5,
                    "passed_runs": 0, "completed_runs": 0, "runs": [], "overall": "PARTIAL",
                    "stages": {"campaign_preflight": {"status": "NOT_VERIFIED"}}}
        with (patch.object(hil_auth, "DEV_POLICY", path),
              patch.object(hil_auth, "DEV_STATE", state),
              patch.object(controller, "readiness", return_value=readiness),
              patch.object(tc, "exact_fixture", return_value=fixture),
              patch.object(tc, "campaign_approval", return_value={
                  "approval_ref": policy["owner_approval_ref"], "development_authorization": True}),
              patch.object(controller, "execute", side_effect=RuntimeError("unexpected test harness fault")),
              patch.object(controller, "save")):
            with self.assertRaisesRegex(RuntimeError, "unexpected test harness fault"):
                controller.execute_campaign(campaign)
            stable, _ = hil_auth._development_ledger_path(state, policy)
            ledger = json.loads(stable.read_text())
            self.assertEqual(ledger["failure_class"], "UNKNOWN_UNHANDLED")
            self.assertTrue(ledger["blocked"])
            self.assertEqual(campaign["authorization_outcome"], "UNKNOWN_UNHANDLED")
            self.assertFalse(controller.lock.locked())

    def test_dev_rotation_fails_closed_if_legacy_history_lost(self):
        path, policy = self.development_policy()
        state = self.root / 'dev-missing-history'
        state.mkdir(mode=0o700)
        legacy = state / (hil_auth.digest(path) + '.json')
        legacy.write_text(json.dumps({'approval_ref': policy['owner_approval_ref'],
                                      'sessions': 2, 'blocked': True,
                                      'consecutive_failures': 2,
                                      'started_at': '2026-10-30T00:00:00+00:00'}))
        legacy.chmod(0o600)
        before = legacy.read_bytes()
        with self.assertRaisesRegex(ValueError, 'development_authorization_history_(unavailable|incomplete)'):
            with hil_auth.session('observe', path, state, _development=True): pass
        stable, _scope = hil_auth._development_ledger_path(state, policy)
        self.assertFalse(stable.exists())
        self.assertEqual(legacy.read_bytes(), before)

    def test_dev_new_approval_scope_does_not_inherit_prior_scope_ledger(self):
        path, policy = self.development_policy()
        state = self.root / 'dev-scope-isolation'
        with hil_auth.session('observe', path, state, _development=True): pass
        prior_stable, prior_scope = hil_auth._development_ledger_path(state, policy)
        self.assertEqual(json.loads(prior_stable.read_text())['sessions'], 1)

        policy['owner_approval_ref'] = 'separate-unit-test-consent'
        policy['development_mode']['authorization_ref'] = policy['owner_approval_ref']
        policy['development_mode']['activation_id'] = 'unit-test-scope-successor-0001'
        successor_audit = self.root / 'successor-development-authorization' / 'audit.jsonl'
        self.write_mode_activation(policy, successor_audit)
        new_path = self.root / 'new-dev-policy.json'
        new_path.write_text(json.dumps(policy)); new_path.chmod(0o600)
        with hil_auth.session('observe', new_path, state, _development=True) as (_p, ledger):
            self.assertEqual(ledger['sessions'], 1)
            self.assertEqual(ledger['consecutive_failures'], 0)
        new_stable, new_scope = hil_auth._development_ledger_path(state, policy)
        self.assertNotEqual(prior_scope, new_scope)
        self.assertEqual(json.loads(prior_stable.read_text())['sessions'], 1)
        self.assertEqual(json.loads(new_stable.read_text())['sessions'], 1)

    def test_valid_repeatable_consent_does_not_grant_campaign(self):
        for _ in range(2):
            with hil_auth.session('protected_gs40_bootstrap', self.policy, self.root / 'audit') as (p, _):
                self.assertFalse(p['motion_injection_authorized'])
        with self.assertRaises(ValueError):
            with hil_auth.session('motion_injection', self.policy, self.root / 'audit'): pass

    def test_missing_expired_revoked_scope_and_privacy_denied(self):
        original = dict(self.data)
        for changes in ({'active': False}, {'revoked': True}, {'owner_approved': False},
                        {'motion_injection_authorized': True}, {'max_retries': 1},
                        {'expires_at': '2020-01-01T00:00:00+00:00'}, {'identity': {}},
                        {'images': {}}, {'owner_approval_ref': ''}):
            self.data = dict(original, **changes); self.write()
            with self.assertRaises(ValueError): hil_auth.load(self.policy)
        self.data = original; self.write(); self.policy.chmod(0o644)
        with self.assertRaises(ValueError): hil_auth.load(self.policy)
        self.policy.unlink()
        with self.assertRaises(OSError): hil_auth.load(self.policy)

    def test_changed_procedure_and_symlink_denied(self):
        Path(self.data['bootstrap_script']['path']).write_text('changed')
        with self.assertRaises(ValueError): hil_auth.load(self.policy)
        link = self.root / 'link'; link.symlink_to(self.policy)
        with self.assertRaises(ValueError): hil_auth.load(link)

    def test_failure_latch_and_concurrent_session_denied(self):
        with self.assertRaisesRegex(ValueError, 'technical_guard_failure'):
            with hil_auth.session('protected_gs40_bootstrap', self.policy, self.root / 'audit'):
                with self.assertRaises(BlockingIOError):
                    with hil_auth.session('protected_gs40_bootstrap', self.policy, self.root / 'audit'): pass
                raise ValueError('technical_guard_failure')
        with self.assertRaisesRegex(ValueError, 'latched'):
            with hil_auth.session('protected_gs40_bootstrap', self.policy, self.root / 'audit'): pass

    def test_target_failure_stops_existing_collector(self):
        tc_serial.readiness_guard({'stop_on_readiness_error': True}, [], ['normal startup'])
        with self.assertRaisesRegex(ValueError, 'READINESS_GUARD_FAILED'):
            tc_serial.readiness_guard({'stop_on_readiness_error': True}, [],
                                     ['signed-time bootstrap unavailable'])

    def test_image_receipt_tampering_denied(self):
        Path(self.data['image_receipts']['c3']['path']).write_text('{}')
        with self.assertRaises(ValueError): hil_auth.load(self.policy)

    def test_session_limit(self):
        self.data['max_sessions'] = 1; self.write()
        with hil_auth.session('protected_gs40_bootstrap', self.policy, self.root / 'audit'): pass
        with self.assertRaises(ValueError):
            with hil_auth.session('protected_gs40_bootstrap', self.policy, self.root / 'audit'): pass

    def test_readiness_retains_fixture_and_fresh_receipt_guards(self):
        from contextlib import contextmanager
        original_session = hil_auth.session
        @contextmanager
        def authorized(*args):
            with original_session('protected_gs40_bootstrap', self.policy, self.root / 'audit') as result:
                yield result
        self.data['bootstrap_script']['path'] = str(self.root / 'bootstrap_script')
        self.data['evidence_directory'] = str(self.root)
        self.write()
        observation = {'s3_memory_capacity': {'status': 'PASS', 'flash_size_bytes': 16777216, 'psram_size_bytes': 8388608}, 'c3': ['HIL_STATE role=c3 session=120 runtime_live=1 sensing_live=1',
                              'HIL_STATE role=c3 session=120 runtime_live=2 sensing_live=2'],
                       's3': ['Authenticated rejoin device=c3-146393c5d158 logical=bedroom session=120']}
        receipt = self.root / 'receipt.json'
        receipt.write_text(json.dumps({'observed_at': datetime.now(timezone.utc).isoformat()}))
        with patch.object(hil_auth, 'session', side_effect=authorized), \
             patch.object(hil_auth, 'STATE', self.root), \
             patch.object(tc, 'health', return_value={'exit_code': 0}), \
             patch.object(tc, 'active_hub_ingress_listener', return_value={'status': 'PASS'}), \
             patch.object(tc, 'powershell', return_value=[dict(v, usb_hwid='USB VID:PID=303A:1001 SER='+v['serial_number']) for v in hil_auth.IDENTITY.values() if isinstance(v, dict)]), \
             patch.object(tc.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(observation), stderr='')), \
             patch.object(tc, 'exact_fixture', side_effect=ValueError('fixture_not_verified')) as fixture_fn:
            with patch('builtins.print') as output:
                tc.standing_readiness()
                self.assertEqual(json.loads(output.call_args.args[0])['overall'], 'FIXTURE_PENDING')
            ledger = self.root / 'audit' / (hil_auth.digest(self.policy) + '.json')
            self.assertFalse(json.loads(ledger.read_text())['blocked'])
            def fresh_fixture():
                receipt.write_text(json.dumps({'observed_at': datetime.now(timezone.utc).isoformat()}))
                return {'hub_ingress_receipt': str(receipt)}
            fixture_fn.side_effect = fresh_fixture
            with patch('builtins.print') as output:
                tc.standing_readiness()
                self.assertEqual(json.loads(output.call_args.args[0])['overall'], 'TC001_READY')
            fixture_fn.side_effect = None
            fixture_fn.return_value = {'hub_ingress_receipt': str(receipt)}
            receipt.write_text(json.dumps({'observed_at': '2020-01-01T00:00:00+00:00'}))
            with patch('builtins.print') as output:
                tc.standing_readiness()
                self.assertEqual(json.loads(output.call_args.args[0])['overall'], 'FIXTURE_PENDING')
            with patch.object(tc.subprocess, 'run', return_value=SimpleNamespace(returncode=2, stdout='{}', stderr='')):
                with self.assertRaisesRegex(ValueError, 'bootstrap_failed'):
                    tc.standing_readiness()
            self.assertTrue(json.loads(ledger.read_text())['blocked'])

    def test_missing_ingress_receipt_is_fixture_pending(self):
        with patch.object(tc, 'exact_fixture', return_value={
                'hub_ingress_receipt': str(self.root / 'does-not-exist.json')}):
            result = tc.readiness_fixture_status(datetime.now(timezone.utc).isoformat())
        self.assertEqual(result['overall'], 'FIXTURE_PENDING')
        self.assertEqual(result['fixture_reason'], 'FileNotFoundError')

    def test_refresh_failure_needs_target_bound_authenticated_recovery(self):
        observed = {"c3": [], "s3": ["TEST_ONLY time/authority refresh failed; publication fenced"]}
        start = "2026-10-29T00:00:00+00:00"
        for receipt in (None, {"http_status": 200}):
            with self.assertRaisesRegex(ValueError, "recovery_not_verified"):
                tc.observation_refresh_guard(observed, receipt, started_at=start)
        receipt = {"profile": "GS179_TEST_ONLY", "home_id": "gs177-test-product",
            "hub_id": "hub-e072a1d38d34", "installation_epoch": 1,
            "authenticated_hub_identity": True, "trusted_time_ready": True,
            "authority_lease_installed": True,
            "target_observation_sha256": hashlib.sha256(json.dumps(observed, sort_keys=True).encode()).hexdigest(),
            "recovery_proof": "VERIFIED_TARGET_TIME_AUTHORITY_AND_AUTHENTICATED_CLOUDSYNC",
            "mtls_client_cert_sha256": "a"*64, "server_cert_sha256": "b"*64,
            "observed_at": start, "recovered_at": start}
        self.assertIn("RECOVERED", tc.observation_refresh_guard(observed, receipt, started_at=start))
        for field in ("trusted_time_ready", "authority_lease_installed", "authenticated_hub_identity"):
            bad = dict(receipt, **{field: False})
            with self.assertRaises(ValueError): tc.observation_refresh_guard(observed, bad, started_at=start)
        observed["s3"].append("GS40T/1 REJECT stage=signature")
        with self.assertRaisesRegex(ValueError, "TARGET_READINESS_GUARD_FAILED"):
            tc.observation_refresh_guard(observed, receipt, started_at=start)

    def test_transient_collection_opt_in_preserves_fatal_latch(self):
        config = {"stop_on_readiness_error": True, "defer_transient_refresh_failure": True}
        tc_serial.readiness_guard(config, [], ["time/authority refresh failed"])
        with self.assertRaises(ValueError):
            tc_serial.readiness_guard(config, [], ["panic: security fault"])

    def test_inactive_policy_prevents_all_hardware(self):
        self.data['active'] = False; self.write()
        from contextlib import contextmanager
        original_session = hil_auth.session
        @contextmanager
        def scoped(*args):
            with original_session('protected_gs40_bootstrap', self.policy, self.root / 'audit') as result:
                yield result
        with patch.object(hil_auth, 'session', side_effect=scoped), patch.object(tc, 'powershell') as hw:
            with self.assertRaises(ValueError): tc.standing_readiness()
            hw.assert_not_called()



class BootstrapChildEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)

    class Child:
        def __init__(self, stdout, stderr="", returncode=0, first_error=None,
                     drain_stdout=None, drain_stderr=None):
            self.stdout = stdout
            self.stderr = stderr
            self.returncode = returncode
            self.first_error = first_error
            self.drain_stdout = drain_stdout
            self.drain_stderr = drain_stderr
            self.calls = 0
            self.killed = False

        def communicate(self, timeout=None):
            self.calls += 1
            if self.first_error is not None and self.calls == 1:
                raise self.first_error
            if (self.calls > 1 or self.killed) and self.drain_stdout is not None:
                return self.drain_stdout, self.drain_stderr or ""
            return self.stdout, self.stderr

        def poll(self):
            return None if not self.killed and self.returncode is None else self.returncode

        def kill(self):
            self.killed = True
            self.returncode = -9

    def _evidence(self):
        return json.loads((self.root / bootstrap_evidence.EVIDENCE_NAME).read_text())

    def _run(self, child, *, timeout=85):
        return bootstrap_evidence.wait_and_record_child(
            child, self.root, stage="encrypted_config_exchange",
            started_at="2026-10-29T06:00:00+00:00",
            challenge_received_at="2026-10-29T06:00:01+00:00",
            timeout_seconds=timeout,
            challenge_line=json.dumps({"stage": "CONFIG_CHALLENGE",
                                       "nonce": "n" * 64,
                                       "public_key": "04" + "a" * 128}))

    def test_child_success_is_durably_saved_before_return(self):
        child = self.Child(json.dumps({
            "stage": "OBSERVATION",
            "c3": ["HIL_STATE role=c3 session=121 runtime_live=4 sensing_live=3"],
            "s3": ["Authenticated rejoin device=c3-146393c5d158 logical=bedroom session=121"],
            "c3_status_queries": 2,
            "bootstrap_timeline": {"s3_memory_capacity": {
                "status": "PASS", "flash_size_bytes": 16777216,
                "psram_size_bytes": 8388608,
                "evidence_lines": ["SPI Flash size: 16MB", "Found 8MB PSRAM device"],
            }, "nonce": "must-not-persist"},
        }))
        result = self._run(child, timeout=120)
        with self.assertRaisesRegex(ValueError, "BOOTSTRAP_CHILD_TIMEOUT_OUT_OF_RANGE"):
            self._run(self.Child("{}"), timeout=121)
        evidence = self._evidence()
        self.assertEqual(result["c3"], evidence["response"]["c3"])
        self.assertEqual(evidence["child_exit_code"], 0)
        self.assertEqual(evidence["response_status"], "VALID")
        self.assertEqual(evidence["child_outcome"], "EXITED")
        self.assertEqual(evidence["started_at"], "2026-10-29T06:00:00+00:00")
        self.assertEqual(evidence["challenge_received_at"], "2026-10-29T06:00:01+00:00")
        self.assertEqual(evidence["challenge"]["stage"], "CONFIG_CHALLENGE")
        self.assertNotIn("nonce", json.dumps(evidence["challenge"]))
        memory = evidence["response"]["bootstrap_timeline"]["s3_memory_capacity"]
        self.assertEqual(memory["status"], "PASS")
        self.assertEqual(memory["flash_size_bytes"], 16777216)
        self.assertEqual(memory["psram_size_bytes"], 8388608)
        self.assertNotIn("must-not-persist", json.dumps(evidence))
        self.assertEqual((self.root / bootstrap_evidence.EVIDENCE_NAME).stat().st_mode & 0o777, 0o600)

    def test_failed_target_guard_and_both_serial_observations_saved_before_raise(self):
        child = self.Child(json.dumps({
            "error": "TC001_TARGET_READINESS_GUARD_FAILED",
            "observation": {
                "c3": ["Node security owner faulted private_key=do-not-persist runtime_live=0 sensing_live=0"],
                "s3": ["signed-time bootstrap unavailable"],
            },
        }), returncode=2)
        with self.assertRaisesRegex(ValueError, "BOOTSTRAP_CHILD_TC001_TARGET_READINESS_GUARD_FAILED"):
            self._run(child)
        evidence = self._evidence()
        self.assertEqual(evidence["child_exit_code"], 2)
        self.assertEqual(evidence["child_error"], "TC001_TARGET_READINESS_GUARD_FAILED")
        self.assertEqual(evidence["response"]["observation"]["c3"],
                         ["Node security owner faulted private_key=[REDACTED] runtime_live=0 sensing_live=0"])
        self.assertNotIn("do-not-persist", json.dumps(evidence))
        self.assertEqual(evidence["response"]["observation"]["s3"],
                         ["signed-time bootstrap unavailable"])

    def test_malformed_child_response_records_digest_without_publishing_raw_text(self):
        raw = "not-json password=do-not-retain-this-value"
        child = self.Child(raw, stderr="credential=also-do-not-retain", returncode=2)
        with self.assertRaisesRegex(ValueError, "BOOTSTRAP_CHILD_RESPONSE_MALFORMED"):
            self._run(child)
        evidence = self._evidence()
        encoded = json.dumps(evidence)
        self.assertEqual(evidence["response_status"], "MALFORMED")
        self.assertEqual(evidence["child_exit_code"], 2)
        self.assertEqual(evidence["stdout"]["bytes"], len(raw.encode()))
        self.assertIsNone(evidence["response"])
        self.assertNotIn("not-json", encoded)
        self.assertNotIn("do-not-retain", encoded)
        self.assertNotIn("also-do-not-retain", encoded)
        self.assertTrue(evidence["stderr_safe_summary"])

    def test_timeout_kills_once_and_persists_available_child_observation(self):
        partial = json.dumps({
            "error": "TC001_TARGET_READINESS_GUARD_FAILED",
            "observation": {
                "c3": ["HIL_STATE role=c3 session=121 runtime_live=0 sensing_live=0"],
                "s3": ["Authenticated rejoin device=c3-146393c5d158 logical=bedroom session=121"],
            },
        })
        child = self.Child("", returncode=None,
                           first_error=subprocess.TimeoutExpired("helper", 85),
                           drain_stdout=partial)
        with self.assertRaisesRegex(ValueError, "BOOTSTRAP_CHILD_TIMEOUT"):
            self._run(child)
        evidence = self._evidence()
        self.assertTrue(child.killed)
        self.assertEqual(child.calls, 2)
        self.assertEqual(evidence["child_outcome"], "INTERRUPTED")
        self.assertEqual(evidence["interruption"], "timeout")
        self.assertEqual(evidence["child_exit_code"], -9)
        self.assertEqual(evidence["child_error"], "TC001_TARGET_READINESS_GUARD_FAILED")
        self.assertEqual(evidence["response"]["observation"]["c3"],
                         ["HIL_STATE role=c3 session=121 runtime_live=0 sensing_live=0"])

    def test_failed_first_line_retains_boot_fingerprint_without_secret_fields(self):
        first = {"error": "TC001_BOOTSTRAP_RUNNING_IMAGE_MISMATCH",
                 "nonce": "n" * 64, "private_key": "NEVER_PUBLISH",
                 "bootstrap_timeline": {"boot": {"app_offset": "0x420000",
                    "app_version": "dev", "elf_sha256_prefix": "e763e0b6e"},
                    "post_reset_boot_verified": True}}
        child = self.Child("", returncode=None)
        path = bootstrap_evidence.record_interrupted_child(
            child, self.root, stage="encrypted_config_exchange",
            started_at="2026-10-29T06:00:00+00:00", challenge_received_at=None,
            parent_error=ValueError("AUTHENTICATED_CONFIG_CHALLENGE_UNAVAILABLE"),
            challenge_line=json.dumps(first))
        saved = json.loads(path.read_text())["challenge"]["observation"]
        self.assertEqual(saved["bootstrap_timeline"]["boot"], first["bootstrap_timeline"]["boot"],
                         "GS117-CHILD-BOOT-EVIDENCE-001")
        self.assertNotIn("nonce", json.dumps(saved))
        self.assertNotIn("NEVER_PUBLISH", path.read_text())

    def test_parent_interruption_before_result_drains_child_and_records_stage(self):
        child = self.Child("", returncode=None,
                           drain_stdout=json.dumps({
                               "error": "TC001_BOOTSTRAP_TARGET_CHALLENGE_NOT_OBSERVED",
                               "bootstrap_timeline": [{"stage": "challenge_wait", "status": "failed",
                                                       "elapsed_ms": 20000}],
                           }))
        path = bootstrap_evidence.record_interrupted_child(
            child, self.root, stage="encrypted_config_exchange",
            started_at="2026-10-29T06:00:00+00:00",
            challenge_received_at=None,
            parent_error=ValueError("BOUNDED_BOOTSTRAP_CHALLENGE_TIMEOUT"),
            challenge_line=json.dumps({"error": "TC001_BOOTSTRAP_TARGET_CHALLENGE_NOT_OBSERVED",
                                       "nonce": "n" * 64}))
        evidence = json.loads(path.read_text())
        self.assertTrue(child.killed)
        self.assertEqual(child.calls, 1)
        self.assertEqual(evidence["child_outcome"], "INTERRUPTED")
        self.assertEqual(evidence["parent_failure_code"], "BOUNDED_BOOTSTRAP_CHALLENGE_TIMEOUT")
        self.assertEqual(evidence["child_error"], "TC001_BOOTSTRAP_TARGET_CHALLENGE_NOT_OBSERVED")
        self.assertEqual(evidence["challenge"]["error"],
                         "TC001_BOOTSTRAP_TARGET_CHALLENGE_NOT_OBSERVED")
        self.assertNotIn("nonce", json.dumps(evidence["challenge"]))
        self.assertEqual(evidence["response"]["bootstrap_timeline"][0]["stage"], "challenge_wait")


class TC001Test(unittest.TestCase):
    def setUp(self):
        self.dev_temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.dev_temp.cleanup)
        guard = patch.object(hil_auth, 'DEV_POLICY', Path(self.dev_temp.name) / 'absent.json')
        guard.start(); self.addCleanup(guard.stop)

    def test_dev_input_trial_is_explicit_consented_and_exact_identity_only(self):
        fixture = {'qualification_profile':'GS117_DEV_TEST_ONLY', 'home_id':hil_auth.IDENTITY['home_id'],
            'hub_id':hil_auth.IDENTITY['s3']['device_id'], 'physical_device_id':hil_auth.IDENTITY['c3']['device_id'],
            **{r:dict(hil_auth.IDENTITY[r]) for r in ('c3','s3')}}
        self.assertFalse(tc.development_input_trial({}))
        with patch.object(hil_auth, 'load_development', side_effect=ValueError('revoked')):
            with self.assertRaisesRegex(ValueError, 'revoked'):tc.development_input_trial(fixture)
        with patch.object(hil_auth, 'load_development', return_value={'identity':hil_auth.IDENTITY}):
            self.assertTrue(tc.development_input_trial(fixture))
            fixture['c3']['serial_number']='unknown'
            with self.assertRaisesRegex(ValueError, 'identity_mismatch'):tc.development_input_trial(fixture)

    def test_reusable_dev_campaign_consent_preserves_identity_checks(self):
        policy = {'identity': hil_auth.IDENTITY, 'owner_approval_ref': 'unit-dev-consent'}
        fixture = {'home_id': hil_auth.IDENTITY['home_id'], 'physical_device_id': hil_auth.IDENTITY['c3']['device_id'],
            'hub_id': hil_auth.IDENTITY['s3']['device_id'],
            **{r: dict(hil_auth.IDENTITY[r]) for r in ('c3','s3')}}
        with patch.object(hil_auth, 'load_development', return_value=policy), \
             patch.object(Path, 'exists', return_value=True):
            for _ in range(2):
                self.assertTrue(tc.campaign_approval(Path('/unused'), fixture)['development_authorization'])
            fixture['home_id'] = 'other-home'
            with self.assertRaisesRegex(ValueError, 'identity_mismatch'):
                tc.campaign_approval(Path('/unused'), fixture)

    def test_node_only_payload_keeps_both_identities_and_bounded_duration(self):
        fixture = {r: {'port': port, 'usb_hwid': 'test-hwid', 'serial_number': serial}
                   for r, port, serial in [('c3','COM4','14:63:93:C5:D1:58'),
                                           ('s3','COM10','E0:72:A1:D3:8D:34')]}
        fixture['observation_seconds'] = 30
        with patch.object(tc.subprocess, 'check_output', return_value='C:\\observer.py'), \
             patch.object(tc.subprocess, 'run', return_value=SimpleNamespace(stdout='{}', returncode=0)) as run:
            tc.powershell('ObserveNode', fixture)
        encoded = run.call_args.args[0][-1].split('"')[-2]
        payload = json.loads(base64.b64decode(encoded))
        self.assertEqual(payload['c3']['port'], 'COM4')
        self.assertEqual(payload['s3']['serial_number'], 'E0:72:A1:D3:8D:34')
        self.assertEqual(payload['observation_seconds'], 30)

    def test_windows_helper_preserves_specific_failure_before_exit_status(self):
        for output, reason in ((json.dumps({'error': 'TC001_ANDROID_SETTINGS_NAVIGATION_NOT_FOUND'}),
                'TC001_ANDROID_SETTINGS_NAVIGATION_NOT_FOUND'),
                ('not-json', 'TC001_WINDOWS_HELPER_RESPONSE_INVALID_EXIT_1'),
                ('{}', 'TC001_WINDOWS_HELPER_PROCESS_FAILED_EXIT_1')):
            with self.subTest(output=output), \
                 patch.object(tc.subprocess, 'check_output', return_value='C:\\observer.py'), \
                 patch.object(tc.subprocess, 'run', return_value=SimpleNamespace(stdout=output, returncode=1)), \
                 self.assertRaisesRegex(ValueError, reason):
                tc.powershell('List')

    def test_node_only_observer_rejects_unknown_usb_before_serial_open(self):
        with patch.object(tc_serial, 'ports', return_value=[]), patch.object(tc_serial.serial, 'Serial') as opened:
            with self.assertRaisesRegex(ValueError, 'USB_INTERFACE_MISMATCH'):
                tc_serial.observe_node({'c3': {'port':'COM4','serial_number':'14:63:93:C5:D1:58'},
                    's3': {'port':'COM10','serial_number':'E0:72:A1:D3:8D:34'}})
            opened.assert_not_called()

    def test_spi_flash_log_without_plain_boot_tag_is_retained(self):
        class Stream:
            data = b'I (400) boot.esp32s3: SPI Flash Size : 16MB\n'
            in_waiting = len(data)
            def read(self, count):
                value = self.data; self.data = b''; self.in_waiting = 0; return value
        lines = []
        tc_serial.collect(Stream(), '', lines)
        self.assertEqual(tc_serial.s3_memory_capacity(lines)['flash_size_bytes'], 16777216)


    def test_health_preserves_lan_failure_reason_and_overall_exit(self):
        result = SimpleNamespace(
            returncode=1,
            stdout=("POSTGRES_READY=PASS tls=verify-full\n"
                    "CAREGIVER_HTTPS_READY=PASS tls=ca_and_dns_san_verified\n"
                    "LOCAL_BACKEND_READY=PASS\n"
                    "LAPTOP_LAN_ENDPOINT_TLS_READY=FAIL reason=windows_forwarding_or_endpoint_unavailable\n"
                    "LAN_FORWARDING_READY=FAIL reason=windows_forwarding_or_endpoint_unavailable\n"
                    "DEVELOPMENT_ENDPOINT_READY=FAIL local_backend=PASS lan_forwarding=FAIL\n"),
        )
        with patch.object(tc.subprocess, "run", return_value=result) as run:
            state = tc.health()
        self.assertEqual(run.call_args.args[0][-1], "health")
        self.assertEqual(state["LOCAL_BACKEND_READY"], "PASS")
        self.assertEqual(state["LAPTOP_LAN_ENDPOINT_TLS_READY"], "FAIL")
        self.assertEqual(state["LAPTOP_LAN_ENDPOINT_TLS_READY_REASON"],
                         "windows_forwarding_or_endpoint_unavailable")
        self.assertEqual(state["DEVELOPMENT_ENDPOINT_READY"], "FAIL")
        self.assertEqual(state["exit_code"], 1)

    @staticmethod
    def _physical_ingress_audit(*, listener_count=1, network="Private",
                                listen_address="192.168.1.6",
                                target_address="172.17.152.10"):
        return {
            "Action": "Audit", "EndpointKind": "PhysicalHubIngress",
            "ListenPort": 8445, "TargetPort": 8445,
            "WifiAddress": "192.168.1.6", "NetworkCategory": network,
            "WslAddress": "172.17.152.10",
            "PortProxyRows": json.dumps([{
                "ListenAddress": listen_address, "ListenPort": 8445,
                "TargetAddress": target_address, "TargetPort": 8445,
            }]),
            "ListenerReadStatus": "READABLE_NETSTAT",
            "ListenerCount": listener_count,
        }

    def _mock_live_ingress_checks(self, audit):
        ss = SimpleNamespace(returncode=0,
                             stdout="LISTEN 0 64 172.17.152.10:8445 0.0.0.0:*\n")
        windows = SimpleNamespace(returncode=0, stdout=json.dumps(audit))
        return (
            patch.object(tc, "wsl_ipv4", return_value="172.17.152.10"),
            patch.object(tc.subprocess, "check_output", return_value="C:\\proxy.ps1"),
            patch.object(tc.subprocess, "run", side_effect=[ss, windows]),
        )

    def test_hub_ingress_requires_wsl_listener_and_active_windows_route(self):
        patches = self._mock_live_ingress_checks(self._physical_ingress_audit())
        with patches[0], patches[1], patches[2]:
            result = tc.active_hub_ingress_listener()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["listener"], "WSL_AND_WINDOWS_ACTIVE")
        self.assertEqual(result["authenticated_hub"], "NOT_VERIFIED")
        self.assertEqual(result["fresh_physical_receipt"], "NOT_VERIFIED")

    def test_hub_ingress_blocks_wsl_socket_without_windows_listener(self):
        patches = self._mock_live_ingress_checks(
            self._physical_ingress_audit(listener_count=0))
        with patches[0], patches[1], patches[2]:
            result = tc.active_hub_ingress_listener()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["listener"], "WSL_ONLY")
        self.assertEqual(result["reason"], "windows_physical_ingress_listener_missing")

    def test_hub_ingress_fails_closed_on_wrong_mapping_or_untrusted_wifi(self):
        for audit in (
                self._physical_ingress_audit(target_address="172.17.152.11"),
                self._physical_ingress_audit(network="Public")):
            patches = self._mock_live_ingress_checks(audit)
            with self.subTest(audit=audit), patches[0], patches[1], patches[2]:
                result = tc.active_hub_ingress_listener()
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["reason"],
                             "windows_physical_ingress_mapping_or_trusted_network_mismatch")

    @staticmethod
    def _morning_fixture():
        return {
            "home_id": "gs177-test-product", "hub_id": "test-hub-a",
            "installation_epoch": 3, "physical_device_id": "test-c3-bedroom",
            "c3": {"port": "COM4", "serial_number": "14:63:93:C5:D1:58"},
            "s3": {"port": "COM10", "serial_number": "E0:72:A1:D3:8D:34"},
            "phone_receipt": {"package": "in.gharsajag.caregiver.discoverytest",
                              "adb_serial": "ZA2237MRHN",
                              "backend_origin": "https://laptop.local"},
        }

    @classmethod
    def _ready_morning_state(cls):
        config = {"timezone": "Asia/Kolkata", "mode": "HOME",
                  "morning": {"enabled": True, "start_minute": 360,
                              "end_minute": 660, "grace_minutes": 30},
                  "activity_rules": {"morning_steps": [
                      {"location": "bedroom", "enabled": True, "required": True}]}}
        return {
            "backend": {"POSTGRES_READY": "PASS", "CAREGIVER_HTTPS_READY": "PASS", "DEVELOPMENT_ENDPOINT_READY": "PASS", "LAPTOP_LAN_ENDPOINT_TLS_READY": "PASS"},
            "caregiver_home": {"caregiver_home_ready": True,
                               "backend_origin": "https://laptop.local",
                               "configuration": {
                                   "status": "PASS",
                                   "source": "AUTHENTICATED_GS148_TEST_ONLY_SETTINGS",
                                   "test_only": True, "home_id": "gs177-test-product",
                                   "schema_version": 1, "desired_version": 4,
                                   "desired_status": "APPLIED", "applied_version": 4,
                                   "desired_config": config, "applied_config": config}},
            "physical_boards": {"status": "PARTIAL", "c3": "PASS", "s3": "PASS"},
            "fixture": {"status": "PASS", "reason": "current exact owner fixture"},
            "physical_enrollment": {"status": "PASS", "reason": "current Bedroom enrollment",
                                    "enrollment_generation": 2},
            "hub_ingress": {"status": "PASS", "listener": "ACTIVE"},
            "android_apk": {"status": "PASS", "reason": "current APK receipt"},
        }

    def test_backend_helper_reads_policy_from_authenticated_settings_route(self):
        calls = []
        snapshot = {"home_id": "gs177-test-product", "desired_version": 4,
                    "desired_status": "APPLIED", "applied_version": 4,
                    "schema_version": 1, "desired_config": {"activity_rules": {}},
                    "applied_config": {"activity_rules": {}}}

        def call(path):
            calls.append(path)
            return 200, snapshot

        result = tc_backend.read_caregiver_configuration(call)
        self.assertEqual(calls, ["/lite/v1/homes/gs177-test-product/routine-config"])
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["source"], "AUTHENTICATED_GS148_TEST_ONLY_SETTINGS")
        self.assertTrue(result["test_only"])
        self.assertEqual(result["applied_version"], 4)

    def test_backend_helper_rejects_wrong_home_and_unavailable_settings(self):
        wrong_home = tc_backend.read_caregiver_configuration(
            lambda _path: (200, {"home_id": "another-home"}))
        unavailable = tc_backend.read_caregiver_configuration(
            lambda _path: (503, {"error": "unavailable"}))
        self.assertEqual(wrong_home["reason"], "settings_snapshot_home_mismatch")
        self.assertEqual(unavailable["reason"], "authenticated_settings_snapshot_invalid")

    def test_backend_decision_projection_requires_one_matching_durable_and_api_decision(self):
        decision_id = "morning-complete:p15:test-c3-bedroomn7:bedrooms82q9"
        row = (decision_id, "MORNING_ROUTINE_COMPLETED", "EXPECTED",
               "configured_required_steps_complete", 1_798_000_000, 0,
               "event-1", "test-c3-bedroom", "bedroom", 82, 9,
               "test-hub-a", 3)
        projection = {"source": "AUTHENTICATED_GS148_TEST_ONLY",
                      "recent_events": [{"decision_id": decision_id,
                                         "kind": "MORNING_ROUTINE_COMPLETED",
                                         "source_type": "HUB_RULE"}]}
        result = tc_backend.project_morning_decision([row], projection, decision_id)
        self.assertEqual(result["decision_count"], 1)
        self.assertEqual(result["caregiver_decision_count"], 1)
        self.assertEqual(result["physical_device_id"], "test-c3-bedroom")
        self.assertEqual(result["event_sequence"], 9)
        self.assertEqual(tc_backend.project_morning_decision([], projection, decision_id),
                         {"decision_count": 0, "caregiver_decision_count": 0})
        wrong_api = dict(projection, recent_events=[dict(projection["recent_events"][0],
                                                          decision_id=decision_id + "x")])
        self.assertEqual(tc_backend.project_morning_decision([row], wrong_api, decision_id)
                         ["caregiver_decision_count"], 0)

    def test_backend_morning_decision_query_uses_read_only_event_and_hub_authority_join(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ca = root / "test-ca.pem"
            ca.write_text("test-only-placeholder", encoding="ascii")
            login = root / ".local/state/ghar-sajag/gs179-laptop/caregiver-login.json"
            login.parent.mkdir(parents=True)
            login.write_text(json.dumps({"profile": "GS179_TEST_ONLY",
                                         "home_id": "gs177-test-product",
                                         "email": "test@example.invalid",
                                         "password": "unused-without-row"}), encoding="utf-8")
            login.chmod(0o600)
            executed = []

            class Database:
                def __enter__(self):
                    return self
                def __exit__(self, *_args):
                    return False
                def execute(self, query, params):
                    executed.append((query, params))
                    return SimpleNamespace(fetchall=lambda: [])

            request = {
                "action": "morning_decision", "home_id": "gs177-test-product",
                "physical_device_id": "test-c3-bedroom", "logical_node_id": "bedroom",
                "hub_id": "test-hub-a", "installation_epoch": 3,
                "origin_session_id": 82, "event_sequence": 9,
                "decision_id": "morning-complete:p15:test-c3-bedroomn7:bedrooms82q9",
            }
            env = {"GS179_LOCAL_SERVER_DSN": "postgresql://unused",
                   "PUBLIC_ORIGIN": "https://laptop.local", "GS179_ANDROID_CA": str(ca)}
            fake_psycopg = SimpleNamespace(connect=lambda *_args, **_kwargs: Database())
            with (patch.dict(os.environ, env),
                  patch.dict(sys.modules, {"psycopg": fake_psycopg}),
                  patch.object(tc_backend.Path, "home", return_value=root)):
                result = tc_backend.run(request)

        self.assertEqual(result, {"decision_count": 0, "caregiver_decision_count": 0})
        self.assertEqual(len(executed), 1)
        query, params = executed[0]
        self.assertIn("SELECT d.decision_id", query)
        self.assertIn("JOIN durable_event_commits", query)
        self.assertIn("c.ownership_epoch=d.installation_epoch", query)
        self.assertNotRegex(query, r"(?i)\b(insert|update|delete)\b")
        self.assertEqual(params[-4:], ("test-c3-bedroom", "bedroom", 82, 9))

    def test_morning_routine_run_persists_blocked_state_without_physical_operations(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = tc.Controller()
            with patch.object(tc, "STATE", Path(directory)), \
                    patch.object(controller, "readiness", return_value={"hub_ingress": {"status": "PASS"}}), \
                    patch.object(tc, "powershell", side_effect=AssertionError("physical operation attempted")):
                controller._readiness = {"hub_ingress": {"status": "PASS"}}
                report = controller.start_morning_routine(10)
                self.assertEqual(report["overall"], "BLOCKED")
                self.assertEqual(report["acceptance"], "NOT_RUN")
                self.assertEqual(report["scenario_id"], "MORNING_ROUTINE")
                self.assertEqual(report["test_stimulus_interval_seconds"], 10)
                self.assertEqual(report["first_failing_stage"], "caregiver_network")
                self.assertEqual(report["stages"]["caregiver_network"]["status"], "BLOCKED")
                self.assertEqual(report["stages"]["android_apk"]["status"], "NOT_STARTED")
                self.assertEqual(report["physical_operations"], [])
                self.assertEqual(report["event_keys"], [])
                self.assertEqual(report["physical_ingress"]["listener_status"], "PASS")
                self.assertEqual(report["readiness_snapshot"]["postgres"], "NOT_VERIFIED")
                self.assertEqual(report["readiness_snapshot"]["android_apk"]["status"],
                                 "NOT_VERIFIED")
                self.assertEqual(len(list(Path(directory).glob("MORNING-ROUTINE-*.json"))), 1)
                history = controller.recent_morning_reports()
                self.assertEqual(len(history), 1)
                self.assertEqual(history[0]["run_id"], report["run_id"])

    def test_morning_run_blocks_when_local_https_passes_but_lan_forwarding_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = tc.Controller()
            state = self._ready_morning_state()
            state["backend"]["DEVELOPMENT_ENDPOINT_READY"] = "FAIL"
            state["backend"]["LAPTOP_LAN_ENDPOINT_TLS_READY"] = "FAIL"
            with (patch.object(tc, "STATE", Path(directory)),
                  patch.object(controller, "readiness", return_value=state),
                  patch.object(tc, "exact_fixture", return_value=self._morning_fixture()),
                  patch.object(tc, "powershell", side_effect=AssertionError("physical operation attempted")),
                  patch.object(controller, "execute", side_effect=AssertionError("USB input attempted"))):
                report = controller.start_morning_routine(10)
            self.assertEqual(report["overall"], "BLOCKED")
            self.assertEqual(report["first_failing_stage"], "caregiver_network")
            self.assertIn("LAN HTTPS", report["stages"]["caregiver_network"]["reason"])
            self.assertEqual(report["physical_operations"], [])
            self.assertEqual(report["event_keys"], [])

    def test_morning_policy_uses_exact_applied_settings_and_still_blocks_unqualified_fixture(self):
        config = {"timezone": "Asia/Kolkata", "mode": "HOME",
                  "morning": {"enabled": True, "start_minute": 360,
                              "end_minute": 660, "grace_minutes": 30},
                  "activity_rules": {"morning_steps": [
                      {"location": "bedroom", "enabled": True, "required": True}]}}
        readiness = {"backend": {"POSTGRES_READY": "PASS", "CAREGIVER_HTTPS_READY": "PASS", "DEVELOPMENT_ENDPOINT_READY": "PASS", "LAPTOP_LAN_ENDPOINT_TLS_READY": "PASS"},
            "caregiver_home": {"caregiver_home_ready": True, "configuration": {
            "status": "PASS", "source": "AUTHENTICATED_GS148_TEST_ONLY_SETTINGS",
            "test_only": True, "home_id": "gs177-test-product", "schema_version": 1,
            "desired_version": 3, "desired_status": "APPLIED", "applied_version": 3,
            "desired_config": config, "applied_config": config}},
            "hub_ingress": {"status": "PASS"}}
        status = tc.Controller.morning_policy_status(readiness)
        self.assertEqual(status["applied_policy"]["status"], "PASS")
        self.assertEqual(status["applied_policy"]["desired_version"], 3)
        self.assertEqual(status["applied_policy"]["applied_version"], 3)
        self.assertEqual(status["room_fixtures"]["configured_enabled_locations"], ["bedroom"])
        self.assertEqual(status["room_fixtures"]["status"], "BLOCKED")
        self.assertFalse(status["room_fixtures"]["enrollment_verified"])
        self.assertEqual(status["physical_ingress"]["status"], "BLOCKED")

        with tempfile.TemporaryDirectory() as directory:
            controller = tc.Controller()
            controller._readiness = readiness
            with patch.object(tc, "STATE", Path(directory)), \
                    patch.object(controller, "readiness", return_value=readiness), \
                    patch.object(tc, "powershell", side_effect=AssertionError("physical operation attempted")):
                report = controller.start_morning_routine(10)
            self.assertEqual(report["overall"], "BLOCKED")
            self.assertEqual(report["first_failing_stage"], "enrolled_room_nodes")
            self.assertEqual(report["stages"]["applied_household_policy"]["status"], "PASS")
            self.assertEqual(report["stages"]["trusted_hub_configuration"]["status"], "PASS")
            self.assertEqual(report["stages"]["enrolled_room_nodes"]["status"], "BLOCKED")
            self.assertEqual(report["physical_operations"], [])

    def test_morning_policy_blocks_rooms_without_their_own_enrolled_physical_node(self):
        config = {"timezone": "Asia/Kolkata", "mode": "HOME",
                  "morning": {"enabled": True, "start_minute": 360,
                              "end_minute": 660, "grace_minutes": 30},
                  "activity_rules": {"morning_steps": [
                      {"location": "bedroom", "enabled": True, "required": True},
                      {"location": "kitchen", "enabled": True, "required": True}]}}
        readiness = {
            "backend": {"POSTGRES_READY": "PASS", "CAREGIVER_HTTPS_READY": "PASS", "DEVELOPMENT_ENDPOINT_READY": "PASS", "LAPTOP_LAN_ENDPOINT_TLS_READY": "PASS"},
            "caregiver_home": {"caregiver_home_ready": True, "configuration": {
                "status": "PASS", "source": "AUTHENTICATED_GS148_TEST_ONLY_SETTINGS",
                "test_only": True, "home_id": "gs177-test-product", "schema_version": 1,
                "desired_version": 7, "desired_status": "APPLIED", "applied_version": 7,
                "desired_config": config, "applied_config": config}},
            "physical_boards": {"c3": "PASS", "s3": "PASS"},
            "fixture": {"status": "PASS"},
            "physical_enrollment": {"status": "PASS"},
            "hub_ingress": {"status": "PASS"},
        }
        status = tc.Controller.morning_policy_status(readiness)
        self.assertEqual(status["room_fixtures"]["status"], "BLOCKED")
        self.assertFalse(status["room_fixtures"]["scenario_policy_ready"])
        self.assertEqual(status["room_fixtures"]["unavailable_locations"], ["kitchen"])
        self.assertIn("Bedroom Node cannot represent another room",
                      status["room_fixtures"]["reason"])

    def test_morning_run_requires_its_own_one_use_approval_after_all_readiness_gates(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = tc.Controller()
            state = self._ready_morning_state()
            fixture = self._morning_fixture()
            with (patch.object(tc, "STATE", Path(directory)),
                  patch.object(tc, "MORNING_APPROVAL", Path(directory) / "missing.json"),
                  patch.object(controller, "readiness", return_value=state),
                  patch.object(tc, "exact_fixture", return_value=fixture),
                  patch.object(controller, "execute", side_effect=AssertionError("motion path reached")),
                  patch.object(tc, "powershell", side_effect=AssertionError("hardware accessed"))):
                report = controller.start_morning_routine(10)
            self.assertEqual(report["overall"], "BLOCKED")
            self.assertEqual(report["first_failing_stage"], "hardware_authorization")
            self.assertEqual(report["stages"]["hardware_authorization"]["status"], "BLOCKED")
            self.assertIn("owner_approval_missing", report["stages"]["hardware_authorization"]["reason"])
            self.assertEqual(report["physical_operations"], [])
            self.assertFalse(controller.lock.locked())

    def test_morning_one_click_orchestrates_decision_checks_after_scoped_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            approval_path = root / "morning.json"
            fixture = self._morning_fixture()
            approval = {
                "schema_version": 1, "test_id": "MORNING_ROUTINE",
                "profile": "GS179_TEST_ONLY", "operation": "C3_INJECT_MOTION_ONE_BEDROOM_RUN",
                "run_count": 1, "home_id": fixture["home_id"], "hub_id": fixture["hub_id"],
                "installation_epoch": fixture["installation_epoch"],
                "physical_device_id": fixture["physical_device_id"], "logical_node_id": "bedroom",
                "desired_config_version": 4,
                "c3": {"port": "COM4", "serial_number": fixture["c3"]["serial_number"]},
                "s3": {"port": "COM10", "serial_number": fixture["s3"]["serial_number"],
                       "uart_open_authorized": False},
                "c3_serial_open_reset_risk_accepted": True, "stop_on_first_failure": True,
                "firmware_write_authorized": False, "commissioning_authorized": False,
                "ownership_or_enrollment_mutation_authorized": False,
                "database_mutation_authorized": False,
                "approval_ref": "test-scoped-one-run", "approved_at": datetime.now(timezone.utc).isoformat(),
            }
            approval_path.write_text(json.dumps(approval), encoding="utf-8")
            approval_path.chmod(0o600)
            event_key = {"physical_device_id": fixture["physical_device_id"],
                         "logical_node_id": "bedroom", "origin_session_id": 82,
                         "event_sequence": 9}
            decision_id = "morning-complete:" + tc.event_key_text(
                fixture["physical_device_id"], 82, 9)
            decision = {"decision_count": 1, "caregiver_decision_count": 1,
                        "decision_id": decision_id, "kind": "MORNING_ROUTINE_COMPLETED",
                        "tone": "EXPECTED", "physical_device_id": fixture["physical_device_id"],
                        "logical_node_id": "bedroom", "origin_session_id": 82,
                        "event_sequence": 9, "hub_device_id": fixture["hub_id"],
                        "installation_epoch": fixture["installation_epoch"],
                        "caregiver_decision": {"decision_id": decision_id,
                                                "kind": "MORNING_ROUTINE_COMPLETED",
                                                "source_type": "HUB_RULE"}}
            screenshot = base64.b64encode(b"\x89PNG\r\n\x1a\nmock").decode()
            hierarchy = b'<hierarchy><node text="Decision ID"/></hierarchy>'
            apk = {"status": "PASS", "observation": "AUTOMATED_PASS",
                   "decision_id": decision_id, "decision_kind": "MORNING_ROUTINE_COMPLETED",
                   "home_id": fixture["home_id"], "backend_origin": "https://laptop.local",
                   "backend_status": "Backend API · CONNECTED",
                   "package": fixture["phone_receipt"]["package"],
                   "device_serial": fixture["phone_receipt"]["adb_serial"],
                   "event_label": "Morning routine completed",
                   "screenshot_png_b64": screenshot,
                   "ui_hierarchy_xml_b64": base64.b64encode(hierarchy).decode(),
                   "ui_dump_sha256": hashlib.sha256(hierarchy).hexdigest()}
            controller = tc.Controller()

            def event_pass(report, **_kwargs):
                report["overall"] = "PASS"
                report["event_key"] = event_key
                report["stages"] = {name: {"status": "PASS", "reason": "mocked"}
                                    for name in tc.STAGES}

            class InlineThread:
                def __init__(self, target, args, daemon):
                    self.target, self.args = target, args
                def start(self):
                    self.target(*self.args)

            with (patch.object(tc, "STATE", root),
                  patch.object(tc, "MORNING_APPROVAL", approval_path),
                  patch.object(controller, "readiness", return_value=self._ready_morning_state()),
                  patch.object(tc, "exact_fixture", return_value=fixture),
                  patch.object(controller, "execute", side_effect=event_pass),
                  patch.object(tc, "backend", return_value=decision),
                  patch.object(tc, "powershell", return_value=apk),
                  patch.object(tc.threading, "Thread", InlineThread)):
                report = controller.start_morning_routine(10)
            self.assertEqual(report["overall"], "PASS")
            self.assertEqual(report["acceptance"], "TARGET_TEST_INPUT_PASS")
            self.assertEqual(report["event_keys"], [event_key])
            self.assertEqual(report["expected_decision_id"], decision_id)
            self.assertTrue(all(report["stages"][name]["status"] == "PASS"
                                for name in tc.MORNING_STAGES))
            self.assertEqual(report["android_evidence"]["decision_id"], decision_id)
            self.assertFalse(approval_path.exists())
            self.assertTrue(list(root.glob("morning.consumed.*.json")))
            self.assertFalse(controller.lock.locked())

    def test_morning_routine_interval_is_bounded_and_controller_remains_idle(self):
        controller = tc.Controller()
        for interval in (0, 601, True, "10"):
            with self.subTest(interval=interval):
                with self.assertRaisesRegex(ValueError, "test_stimulus_interval"):
                    controller.start_morning_routine(interval)
        self.assertIsNone(controller.morning_current)

    def test_morning_routine_ui_is_added_alongside_fixed_tc001_campaign(self):
        self.assertIn("Run Test — five-event campaign", tc.HTML)
        self.assertIn("Run Morning Routine", tc.HTML)
        self.assertIn("Desired / applied policy version", tc.HTML)
        self.assertIn("Included rooms", tc.HTML)
        self.assertIn("Required rooms", tc.HTML)
        self.assertIn("Optional rooms", tc.HTML)
        self.assertIn('id="stimulus-interval"', tc.HTML)

    def test_morning_routine_web_route_uses_existing_origin_and_csrf_guards(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), tc.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_address[1]}/api/scenarios/morning-routine/run"
        report = {"scenario_id": "MORNING_ROUTINE", "overall": "BLOCKED",
                  "first_failing_stage": "applied_household_policy"}
        try:
            with patch.object(tc.CONTROLLER, "start_morning_routine", return_value=report) as run:
                request = urllib.request.Request(
                    url, data=b'{"interval_seconds":15}', method="POST",
                    headers={"Host": "127.0.0.1:18791", "Origin": tc.ORIGIN,
                             "X-CSRF-Token": tc.CONTROLLER.csrf,
                             "Content-Type": "application/json"})
                with urllib.request.urlopen(request, timeout=3) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.load(response), report)
                run.assert_called_once_with(15)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_console_loads_shared_identity_rules_without_pythonpath(self):
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        probe = (
            "import runpy; runpy.run_path(" + repr(str(Path(tc.__file__).resolve())) +
            ", run_name='gs117_console_import_probe')"
        )
        result = subprocess.run(
            [sys.executable, "-c", probe], cwd=Path(__file__).resolve().parents[3],
            env=environment, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_fixture_blocks_before_serial(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(tc, "FIXTURE", Path(directory) / "missing.json"):
            with self.assertRaisesRegex(ValueError, "owner_only_fixture"):
                tc.exact_fixture()

    def test_physical_mac_identity_shapes_are_strict_and_distinct_from_host_sim(self):
        self.assertTrue(tc.is_gs179_test_hub_id("test-hub-a"))
        self.assertTrue(tc.is_gs179_test_node_id("test-c3-bedroom"))
        self.assertTrue(tc.is_gs179_test_hub_id("hub-001122334455"))
        self.assertTrue(tc.is_gs179_test_node_id("c3-001122334455"))
        self.assertTrue(tc.is_gs179_test_hub_home(
            "hub-e072a1d38d34", "gs177-test-product"))
        self.assertFalse(tc.is_gs179_test_hub_home(
            "hub-001122334455", "gs177-test-product"))
        self.assertFalse(tc.is_gs179_test_hub_home(
            "hub-e072a1d38d34", "gs177-test-other"))
        self.assertTrue(tc.is_gs179_test_hub_home("test-hub-a", "gs177-test-product"))
        for invalid in ("hub-00112233445z", "hub-00112233445500", "test-hub-a "):
            with self.subTest(invalid=invalid):
                self.assertFalse(tc.is_gs179_test_hub_id(invalid))
        for invalid in ("c3-00112233445z", "c3-00112233445500", "test-c3-bedroom "):
            with self.subTest(invalid=invalid):
                self.assertFalse(tc.is_gs179_test_node_id(invalid))

    def test_second_run_is_refused_while_one_is_active(self):
        controller = tc.Controller()
        controller.lock.acquire()
        try:
            self.assertIsNone(controller.start())
        finally:
            controller.lock.release()

    def test_fixture_rejects_unsupported_firmware_untrusted_hub_and_wrong_phone(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            now = datetime.now(timezone.utc).isoformat()
            fixture = {"schema_version": 1, "test_id": "TC-001", "profile": "GS179_TEST_ONLY",
                       "home_id": "gs177-test-product", "logical_node_id": "bedroom",
                       "physical_device_id": "test-c3-bedroom", "hub_id": "test-hub-a",
                       "installation_epoch": 1, "approval_ref": "GS-117/example-explicit-approval",
                       "approval_scope": "C3 GET_STATE and INJECT_MOTION; C3/S3 UART observation",
                       "reset_safe_uart_verified": True,
                       "expected_caregiver_origin": "https://laptop.local"}
            for name, target, port in (("c3", "ESP32-C3", "COM10"), ("s3", "ESP32-S3", "COM11")):
                image = root / (name + ".bin"); image.write_bytes(name.encode())
                digest = hashlib.sha256(name.encode()).hexdigest()
                receipt = root / (name + ".json")
                receipt.write_text(json.dumps({"running_image_sha256": digest, "target": target,
                                               "usb_hwid": name, "serial_number": name + "s",
                                               "firmware_source_head": "a" * 40,
                                               "installed_at": now, "observed_at": now,
                                               "active_ota_slot": "ota_0",
                                               "partition_table_sha256": "e" * 64,
                                               "flash_size_bytes": (4 if name == "c3" else 16) * 1024 * 1024,
                                               "psram_size_bytes": 8 * 1024 * 1024 if name == "s3" else 0}))
                fixture[name] = {"port": port, "usb_hwid": name, "serial_number": name + "s",
                                 "image": str(image), "image_sha256": digest,
                                 "installed_image_receipt": str(receipt),
                                 "firmware_source_head": "a" * 40}
            fixture["c3"].update(hil_control=True, hil_build=False, physical_wake=False)
            fixture["s3"]["full_product_composition"] = True
            phone = root / "phone.json"
            phone_state = {"profile": "GS179_TEST_ONLY", "package": "in.gharsajag.caregiver.discoverytest",
                           "installed": True, "home_id": "gs177-test-product",
                           "backend_origin": "https://laptop.local", "signer_sha256": "b" * 64,
                       "adb_serial": "ZA2237MRHN", "version_name": "0.4.0-connected-lite-staging",
                           "observed_at": now}
            phone.write_text(json.dumps(phone_state)); fixture["phone_install_receipt"] = str(phone)
            ingress = root / "ingress.json"
            ingress_state = {"profile": "GS179_TEST_ONLY", "home_id": "gs177-test-product",
                             "hub_id": "test-hub-a", "installation_epoch": 1,
                             "node_device_id": "test-c3-bedroom", "node_enrollment_verified": True,
                             "mtls_client_cert_sha256": "c" * 64, "server_cert_sha256": "d" * 64,
                             "authenticated_hub_identity": True, "trusted_time_ready": True,
                             "bounded_listener_ready": True, "observed_at": now}
            ingress.write_text(json.dumps(ingress_state)); fixture["hub_ingress_receipt"] = str(ingress)
            manifest = root / "fixture.json"
            def write():
                manifest.write_text(json.dumps(fixture)); manifest.chmod(0o600)
            with patch.object(tc, "FIXTURE", manifest):
                write(); self.assertEqual(tc.exact_fixture()["hub_id"], "test-hub-a")
                fixture["c3"]["hil_control"] = False; write()
                with self.assertRaisesRegex(ValueError, "HIL"):
                    tc.exact_fixture()
                fixture["c3"]["hil_control"] = True; write()
                ingress_state["trusted_time_ready"] = False; ingress.write_text(json.dumps(ingress_state))
                with self.assertRaisesRegex(ValueError, "Hub_ingress"):
                    tc.exact_fixture()
                ingress_state["trusted_time_ready"] = True; ingress.write_text(json.dumps(ingress_state))
                phone_state["backend_origin"] = "https://other.local"; phone.write_text(json.dumps(phone_state))
                with self.assertRaisesRegex(ValueError, "installed_APK"):
                    tc.exact_fixture()
                phone_state["backend_origin"] = "https://laptop.local"; phone.write_text(json.dumps(phone_state))
                phone_state["backend_origin"] = "https://192.168.1.10/"
                phone.write_text(json.dumps(phone_state))
                proof = {"profile": "GS179_TEST_ONLY", "server_cert_sha256": "f" * 64}
                with patch.object(tc, "verify_caregiver_origin_alias", return_value=proof) as verify:
                    self.assertEqual(tc.exact_fixture()["caregiver_origin_verification"], proof)
                    self.assertEqual(verify.call_args.args[:2],
                                     ("https://laptop.local", "https://192.168.1.10/"))
                with patch.object(tc, "verify_caregiver_origin_alias",
                                  side_effect=ssl.SSLCertVerificationError("invalid test identity")):
                    with self.assertRaisesRegex(ValueError, "installed_APK"):
                        tc.exact_fixture()
                phone_state["backend_origin"] = "https://laptop.local"
                phone.write_text(json.dumps(phone_state))
                fixture["hub_id"] = "hub-e072a1d38d34"
                fixture["physical_device_id"] = "c3-146393c5d158"
                ingress_state["hub_id"] = fixture["hub_id"]
                ingress_state["node_device_id"] = fixture["physical_device_id"]
                ingress.write_text(json.dumps(ingress_state))
                for name, identity in (("c3", fixture["physical_device_id"]),
                                       ("s3", fixture["hub_id"])):
                    receipt_path = Path(fixture[name]["installed_image_receipt"])
                    receipt_state = json.loads(receipt_path.read_text())
                    receipt_state["permanent_device_id"] = identity
                    receipt_path.write_text(json.dumps(receipt_state))
                write()
                self.assertEqual(tc.exact_fixture()["physical_device_id"], "c3-146393c5d158")
                c3_receipt_path = Path(fixture["c3"]["installed_image_receipt"])
                c3_receipt = json.loads(c3_receipt_path.read_text())
                s3_receipt_path = Path(fixture["s3"]["installed_image_receipt"])
                s3_receipt = json.loads(s3_receipt_path.read_text())

                c3_receipt["observed_at"] = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
                c3_receipt_path.write_text(json.dumps(c3_receipt))
                with self.assertRaisesRegex(ValueError, "c3_installed_image_receipt_stale"):
                    tc.exact_fixture()
                c3_receipt["observed_at"] = now
                c3_receipt_path.write_text(json.dumps(c3_receipt))

                s3_receipt["observed_at"] = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
                s3_receipt_path.write_text(json.dumps(s3_receipt))
                with self.assertRaisesRegex(ValueError, "s3_installed_image_receipt_stale"):
                    tc.exact_fixture()
                s3_receipt["observed_at"] = now
                s3_receipt_path.write_text(json.dumps(s3_receipt))

                c3_receipt["observed_at"] = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()
                c3_receipt_path.write_text(json.dumps(c3_receipt))
                with self.assertRaisesRegex(ValueError, "c3_running_image_observation_time_invalid"):
                    tc.exact_fixture()
                c3_receipt["observed_at"] = now
                c3_receipt_path.write_text(json.dumps(c3_receipt))

                c3_receipt["observed_at"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
                c3_receipt_path.write_text(json.dumps(c3_receipt))
                with self.assertRaisesRegex(ValueError, "c3_running_image_observation_time_invalid"):
                    tc.exact_fixture()
                c3_receipt["observed_at"] = now
                c3_receipt_path.write_text(json.dumps(c3_receipt))

                c3_receipt["running_image_sha256"] = "f" * 64
                c3_receipt_path.write_text(json.dumps(c3_receipt))
                with self.assertRaisesRegex(ValueError, "c3_current_installed_image_provenance_missing"):
                    tc.exact_fixture()
                c3_receipt["running_image_sha256"] = fixture["c3"]["image_sha256"]
                c3_receipt_path.write_text(json.dumps(c3_receipt))

                c3_receipt["permanent_device_id"] = "c3-aabbccddeeff"
                c3_receipt_path.write_text(json.dumps(c3_receipt))
                with self.assertRaisesRegex(ValueError, "physical_MAC_derived_identity_receipts"):
                    tc.exact_fixture()

    def test_c3_event_requires_hil_ack_and_exactly_one_new_key(self):
        lines = ["HIL_OK command=INJECT_MOTION", "PIR -> NodeRuntime session=12 seq=3"]
        self.assertEqual(tc.physical_key(lines), (12, 3))
        self.assertIsNone(tc.physical_key(lines[1:]))
        self.assertIsNone(tc.physical_key(lines + ["PIR -> NodeRuntime session=12 seq=4"]))

    def test_s3_requires_authenticated_matching_durable_event(self):
        good = "Authenticated event logical=bedroom session=12 seq=3 sensor=PIR event=MOTION event_id=p15:test-c3-bedroomn7:bedrooms12q3 room=bedroom ack=0 send=ESP_OK"
        self.assertTrue(tc.s3_durable_event([good], 12, 3, "test-c3-bedroom"))
        for altered in (good.replace("seq=3", "seq=4"), good.replace("ack=0", "ack=1"),
                        good.replace("logical=bedroom", "logical=kitchen"),
                        good.replace("Authenticated", "Unauthenticated"),
                        good.replace("test-c3-bedroom", "test-c3-kitchen")):
            with self.subTest(altered=altered):
                self.assertFalse(tc.s3_durable_event([altered], 12, 3, "test-c3-bedroom"))

    def test_matching_class_zero_node_ack_is_the_s3_durable_admission_evidence(self):
        good = "Application ACK session=12 seq=3 class=0 retired=1"
        self.assertTrue(tc.c3_application_durable_ack([good], 12, 3))
        for altered in (good.replace("seq=3", "seq=4"), good.replace("class=0", "class=1"),
                        good.replace("retired=1", "retired=0"), good.replace("Application", "Transport")):
            self.assertFalse(tc.c3_application_durable_ack([altered], 12, 3))

    def test_apk_event_details_parser_requires_exact_event_key(self):
        key = {"physical_device_id": "c3-146393c5d158", "logical_node_id": "bedroom",
               "origin_session_id": 81, "event_sequence": 4}
        xml = '<hierarchy><node text="Latest recorded events"/><node text="gs177-test-product"/>' \
              '<node text="Motion recorded"/><node text="Bedroom"/><node text="EventKey: ' + \
              json.dumps(key).replace('&', '&amp;').replace('"', '&quot;') + '"/></hierarchy>'
        self.assertTrue(tc_serial.exact_key_in_ui(tc_serial.ET.fromstring(xml), key))
        altered = dict(key, event_sequence=5)
        self.assertFalse(tc_serial.exact_key_in_ui(tc_serial.ET.fromstring(xml), altered))

    def test_apk_decision_details_parser_requires_exact_hub_decision_id(self):
        decision = "morning-complete:p15:test-c3-bedroomn7:bedrooms82q9"
        root = tc_serial.ET.fromstring(
            '<hierarchy><node text="Decision ID: ' + decision + '"/></hierarchy>')
        self.assertTrue(tc_serial.exact_decision_in_ui(root, decision))
        self.assertFalse(tc_serial.exact_decision_in_ui(root, decision + "x"))

    def _android_tree(self, entries):
        root = tc_serial.ET.Element("hierarchy")
        for entry in entries:
            text, bounds = entry[:2]
            attributes = {"text": text, "bounds": bounds}
            if len(entry) >= 3 and entry[2]:
                attributes["content-desc"] = entry[2]
            if len(entry) >= 4:
                attributes.update(entry[3])
            tc_serial.ET.SubElement(root, "node", attributes)
        raw = tc_serial.ET.tostring(root, encoding="utf-8")
        return tc_serial.ET.fromstring(raw), raw

    def _reports_tree(self, *, event_key, decision_id=None, expanded=False,
                      accessible_navigation=False, page_marker="page-0",
                      home_id="gs177-test-product"):
        package = "in.gharsajag.caregiver.discoverytest"
        details_label = "Decision details" if decision_id else "Event details"
        detail_text = "" if accessible_navigation else details_label
        detail_description = details_label if accessible_navigation else None
        entries = [
            ("", "[0,0][1000,2000]", None,
             {"class": "android.webkit.WebView", "scrollable": "true",
              "package": package}),
            ("Reports", "[20,20][400,70]", None,
             {"class": "android.widget.TextView", "package": package}),
            (f"TEST_ONLY authenticated caregiver data · {home_id} · AUTHENTICATED_GS148_TEST_ONLY",
             "[30,128][1189,128]", None,
             {"class": "android.widget.TextView", "package": package}),
            ("Latest recorded events", "[20,120][900,180]", None,
             {"class": "android.widget.TextView", "package": package}),
            (page_marker, "[20,260][500,295]", None,
             {"class": "android.widget.TextView", "package": package}),
            (("Morning routine completed" if decision_id else "Motion recorded"),
             "[200,310][800,355]", None,
             {"class": "android.widget.TextView", "package": package}),
            ("Bedroom", "[200,360][800,400]", None,
             {"class": "android.widget.TextView", "package": package}),
            (detail_text, "[200,420][800,460]", detail_description,
             {"class": "android.view.View", "clickable": "true", "package": package}),
        ]
        if expanded:
            identity = ("Decision ID: " + decision_id if decision_id else
                        "EventKey: " + json.dumps(event_key, separators=(",", ":")))
            entries.append((identity, "[200,470][900,560]", None,
                            {"class": "android.view.View", "package": package}))
        for label, bounds in (("Home", "[0,1900][250,2000]"),
                              ("Devices", "[250,1900][500,2000]"),
                              ("Reports", "[500,1900][750,2000]"),
                              ("Settings", "[750,1900][1000,2000]")):
            entries.append((label, bounds, None,
                            {"class": "android.widget.Button", "clickable": "true",
                             "package": package}))
        return self._android_tree(entries)

    def _run_android_verification(self, *, event_key=None, visible_key=None,
                                  decision_id=None, visible_decision_id=None,
                                  settings_origin="https://laptop.local",
                                  accessible_navigation=False,
                                  initial_blank_dumps=0,
                                  transient_report_navigation_dumps=0,
                                  transient_post_scroll_navigation_dumps=0,
                                  transient_refresh_reports_home_dumps=0,
                                  transient_capture_reports_home_dumps=0,
                                  collapse_after_screenshot=0,
                                  report_scan_keys=None,
                                  report_scan_decisions=None,
                                  report_scan_homes=None):
        package = "in.gharsajag.caregiver.discoverytest"
        adb_serial = "ZA2237MRHN"
        expected_key = event_key or {"physical_device_id": "c3-146393c5d158",
                                     "logical_node_id": "bedroom",
                                     "origin_session_id": 82, "event_sequence": 9}
        settings_entry = ("", "[0,0][100,100]", "Settings") if accessible_navigation else \
                         ("Settings", "[0,0][100,100]")
        home = self._android_tree([("Home", "[0,0][80,80]"), settings_entry])
        settings = self._android_tree([
            ("Settings", "[0,0][100,100]"), ("App & connection", "[0,0][100,100]"),
            ("Authorized Home", "[0,0][100,100]"), ("gs177-test-product", "[0,0][100,100]"),
            ("Backend API · CONNECTED", "[0,0][100,100]"),
            (settings_origin, "[0,0][100,100]"),
            (("", "[0,0][100,100]", "Reports") if accessible_navigation else
             ("Reports", "[0,0][100,100]"))])
        scan_keys = report_scan_keys or [visible_key or expected_key]
        scan_decisions = report_scan_decisions or [visible_decision_id or decision_id]
        scan_homes = report_scan_homes or ["gs177-test-product"]
        report_pages = []
        for index in range(max(len(scan_keys), len(scan_decisions), len(scan_homes))):
            key = scan_keys[min(index, len(scan_keys) - 1)] if scan_keys else None
            decision = (scan_decisions[min(index, len(scan_decisions) - 1)]
                        if scan_decisions else None)
            home_id = scan_homes[min(index, len(scan_homes) - 1)] if scan_homes else ""
            marker = f"report-row-{index}"
            report_pages.append((
                self._reports_tree(event_key=key, decision_id=decision,
                                   accessible_navigation=accessible_navigation,
                                   page_marker=marker, home_id=home_id),
                self._reports_tree(event_key=key, decision_id=decision, expanded=True,
                                   accessible_navigation=accessible_navigation,
                                   page_marker=marker, home_id=home_id)))
        reports = report_pages[0][0]
        ui_sequence = iter((home, settings, settings, reports))
        state = {"page": 0, "expanded": False, "scan_started": False,
                 "monkey_count": 0, "scroll_navigation_pending": 0,
                 "refresh_home_pending": 0, "capture_home_pending": 0,
                 "capture_home_injected": False}
        last = [reports]
        blank = self._android_tree([])
        dump_count = [0]
        navigation_pending = [transient_report_navigation_dumps]
        capture_collapses = [collapse_after_screenshot]
        def dump(_adb, _serial):
            if dump_count[0] < initial_blank_dumps:
                dump_count[0] += 1
                last[0] = blank
                return blank
            dump_count[0] += 1
            try:
                last[0] = next(ui_sequence)
            except StopIteration:
                page = min(state["page"], len(report_pages) - 1)
                last[0] = report_pages[page][1 if state["expanded"] else 0]
            if state["scan_started"] and navigation_pending[0] > 0:
                navigation_pending[0] -= 1
                transient = tc_serial.ET.fromstring(last[0][1])
                for node in transient.iter("node"):
                    if node.get("class") == "android.widget.Button" and node.get("text") == "Reports":
                        node.set("clickable", "false")
                return transient, tc_serial.ET.tostring(transient)
            if state["scan_started"] and state["scroll_navigation_pending"] > 0:
                state["scroll_navigation_pending"] -= 1
                transient = tc_serial.ET.fromstring(last[0][1])
                for node in transient.iter("node"):
                    if node.get("class") == "android.widget.Button" and node.get("text") == "Reports":
                        node.set("clickable", "false")
                return transient, tc_serial.ET.tostring(transient)
            if state["scan_started"] and state["refresh_home_pending"] > 0:
                state["refresh_home_pending"] -= 1
                transient = tc_serial.ET.fromstring(last[0][1])
                for node in transient.iter("node"):
                    for attribute in ("text", "content-desc"):
                        node.set(attribute, node.get(attribute, "").replace(
                            "gs177-test-product", ""))
                return transient, tc_serial.ET.tostring(transient)
            if state["scan_started"] and state["capture_home_pending"] > 0:
                state["capture_home_pending"] -= 1
                transient = tc_serial.ET.fromstring(last[0][1])
                for node in list(transient.iter("node")):
                    if (node.get("text", "").strip() == "Latest recorded events" or
                            node.get("text", "").strip() == "TEST_ONLY authenticated caregiver data · gs177-test-product · AUTHENTICATED_GS148_TEST_ONLY"):
                        parent = next((candidate for candidate in transient.iter()
                                       if node in list(candidate)), None)
                        if parent is not None:
                            parent.remove(node)
                return transient, tc_serial.ET.tostring(transient)
            return last[0]

        calls = []
        def adb_call(_adb, serial_number, *args, **kwargs):
            calls.append((serial_number, args))
            if args[:2] == ("shell", "monkey"):
                state["monkey_count"] += 1
                if state["monkey_count"] >= 2:
                    state["scan_started"] = True
                    if state["monkey_count"] == 2:
                        state["refresh_home_pending"] = transient_refresh_reports_home_dumps
            if state["scan_started"] and args[:3] == ("shell", "input", "tap") and \
                    args[-2:] == ("500", "440"):
                state["expanded"] = True
            if state["scan_started"] and args[:3] == ("shell", "input", "swipe"):
                state["page"] = min(state["page"] + 1, len(report_pages) - 1)
                state["expanded"] = False
                state["scroll_navigation_pending"] = transient_post_scroll_navigation_dumps
            if args[:3] == ("shell", "pm", "path"):
                return ("package:/data/app/" + package + "/base.apk").encode()
            if args[:3] == ("shell", "dumpsys", "package"):
                return b"versionName=0.4.0-connected-lite-staging versionCode=42"
            if args[:3] == ("shell", "dumpsys", "activity"):
                return ("mResumedActivity: ActivityRecord{abc " + package + "/.MainActivity}").encode()
            if args[:2] == ("exec-out", "screencap"):
                if not state["capture_home_injected"]:
                    state["capture_home_pending"] = transient_capture_reports_home_dumps
                    state["capture_home_injected"] = True
                if capture_collapses[0] > 0:
                    capture_collapses[0] -= 1
                    state["expanded"] = False
                return b"\x89PNG\r\n\x1a\nexample"
            return b""

        config = {"phone": {"adb_serial": adb_serial, "package": package,
                             "version_name": "0.4.0-connected-lite-staging",
                             "signer_sha256": "a" * 64,
                             "backend_origin": "https://laptop.local"},
                  "home_id": "gs177-test-product", "backend_origin": "https://laptop.local"}
        if decision_id:
            config["decision_id"] = decision_id
        else:
            config["event_key"] = expected_key
        with (patch.object(tc_serial.subprocess, "run", return_value=subprocess.CompletedProcess(
                ["adb", "devices", "-l"], 0,
                "List of devices attached\n" + adb_serial + " device product:motorola\n", "")),
              patch.object(tc_serial, "ui_dump", side_effect=dump)):
            result = tc_serial.android_verify_event(config, adb_locator=lambda: Path("adb.exe"),
                                                    call=adb_call, sleep=lambda _seconds: None)
        return result, calls

    def test_android_verification_foregrounds_refreshes_and_captures_exact_event(self):
        result, calls = self._run_android_verification()
        self.assertEqual(result["observation"], "AUTOMATED_PASS")
        self.assertEqual(result["reports_view"], "Latest recorded events")
        self.assertTrue(result["event_details_open"])
        self.assertEqual(result["event_key"]["event_sequence"], 9)
        self.assertEqual(result["reports_scrolls"], 0)
        self.assertTrue(result["ui_hierarchy_xml_b64"])
        self.assertTrue(result["screenshot_png_b64"])
        commands = [args for _serial, args in calls]
        home_index = commands.index(("shell", "input", "keyevent", "KEYCODE_HOME"))
        foreground_index = next(i for i, args in enumerate(commands)
                                if i > home_index and args[:2] == ("shell", "monkey"))
        self.assertGreater(foreground_index, home_index)
        self.assertEqual(sum(args[:2] == ("shell", "monkey") for args in commands), 2)

    def test_android_observer_uses_accessibility_labels_for_navigation_and_event_details(self):
        result, _calls = self._run_android_verification(accessible_navigation=True)
        self.assertEqual(result["observation"], "AUTOMATED_PASS")
        self.assertTrue(result["event_details_open"])
        self.assertEqual(result["event_key"]["event_sequence"], 9)

    def test_android_observer_waits_for_delayed_webview_accessibility_tree(self):
        # A blank WebView tree can outlast the initial foreground wait. The
        # normal Settings/Reports hierarchy then appears without user action.
        result, _calls = self._run_android_verification(initial_blank_dumps=12)
        self.assertEqual(result["observation"], "AUTOMATED_PASS")
        self.assertTrue(result["event_details_open"])
        self.assertEqual(result["event_key"]["event_sequence"], 9)

    def test_android_observer_waits_for_reports_navigation_after_visibility_refresh(self):
        result, _calls = self._run_android_verification(transient_report_navigation_dumps=3)
        self.assertEqual(result["observation"], "AUTOMATED_PASS", "GS117-ANDROID-REFRESH-001")

    def test_android_observer_does_not_accept_persistently_missing_reports_tab(self):
        with self.assertRaisesRegex(ValueError, "REPORTS_TAB_NOT_CONFIRMED_FOR_SCROLL"):
            self._run_android_verification(transient_report_navigation_dumps=4)

    def test_android_capture_rechecks_exact_key_and_recovers_from_one_refresh(self):
        result, calls = self._run_android_verification(collapse_after_screenshot=1)
        self.assertEqual(result["capture_retries"], 1, "GS117-ANDROID-CAPTURE-001")
        self.assertEqual(result["observation"], "AUTOMATED_PASS")
        self.assertEqual(sum(args[:2] == ('exec-out', 'screencap') for _, args in calls), 2)

    def test_android_capture_retries_transient_reports_tree_without_home_header(self):
        result, calls = self._run_android_verification(
            transient_capture_reports_home_dumps=1)
        self.assertEqual(result["capture_retries"], 1)
        self.assertEqual(result["home_id"], "gs177-test-product")
        self.assertEqual(result["observation"], "AUTOMATED_PASS")
        self.assertEqual(sum(args[:2] == ('exec-out', 'screencap') for _, args in calls), 2)

    def test_android_capture_never_accepts_repeatedly_collapsing_exact_key(self):
        with self.assertRaisesRegex(ValueError, "OUTCOME_CHANGED_DURING_EVIDENCE_CAPTURE"):
            self._run_android_verification(collapse_after_screenshot=3)

    def test_android_verification_fails_when_exact_event_key_is_not_visible(self):
        with patch.object(tc_serial, "scroll_reports", wraps=tc_serial.scroll_reports) as scroll:
            with self.assertRaisesRegex(ValueError, "TC001_EXACT_EVENT_KEY_NOT_VISIBLE"):
                self._run_android_verification(
                    event_key={"physical_device_id": "c3-146393c5d158", "logical_node_id": "bedroom",
                               "origin_session_id": 82, "event_sequence": 10},
                    visible_key={"physical_device_id": "c3-146393c5d158", "logical_node_id": "bedroom",
                                 "origin_session_id": 82, "event_sequence": 9})
            self.assertEqual(scroll.call_count, tc_serial.ANDROID_REPORTS_END_NO_PROGRESS)

    def test_android_observer_scrolls_to_exact_key_on_later_reports_page(self):
        expected = {"physical_device_id": "c3-146393c5d158", "logical_node_id": "bedroom",
                    "origin_session_id": 118, "event_sequence": 100}
        earlier = {**expected, "event_sequence": 99}
        result, calls = self._run_android_verification(
            event_key=expected, report_scan_keys=[earlier, expected])
        self.assertEqual(result["observation"], "AUTOMATED_PASS")
        self.assertEqual(result["event_key"], expected)
        self.assertEqual(result["reports_scrolls"], 1)
        swipes = [args for _serial, args in calls if args[:3] == ("shell", "input", "swipe")]
        self.assertEqual(len(swipes), 1)
        # Both gesture endpoints are inside the WebView list and above the
        # fixed bottom navigation (whose top is y=1900 in this fixture).
        self.assertLess(int(swipes[0][4]), 1900)
        self.assertLess(int(swipes[0][6]), 1900)

    def test_android_observer_retries_transient_reports_tab_loss_after_scroll(self):
        expected = {"physical_device_id": "c3-146393c5d158", "logical_node_id": "bedroom",
                    "origin_session_id": 118, "event_sequence": 100}
        earlier = {**expected, "event_sequence": 99}
        result, _calls = self._run_android_verification(
            event_key=expected, report_scan_keys=[earlier, expected],
            transient_post_scroll_navigation_dumps=1)
        self.assertEqual(result["observation"], "AUTOMATED_PASS")
        self.assertEqual(result["event_key"], expected)
        self.assertEqual(result["reports_scrolls"], 1)

    def test_android_observer_waits_for_home_identity_after_foreground_refresh(self):
        result, _calls = self._run_android_verification(
            transient_refresh_reports_home_dumps=1)
        self.assertEqual(result["observation"], "AUTOMATED_PASS")
        self.assertEqual(result["home_id"], "gs177-test-product")
        self.assertEqual(result["event_key"]["event_sequence"], 9)

    def test_android_observer_fails_if_reports_tab_stays_missing_after_scroll(self):
        expected = {"physical_device_id": "c3-146393c5d158", "logical_node_id": "bedroom",
                    "origin_session_id": 118, "event_sequence": 100}
        earlier = {**expected, "event_sequence": 99}
        with patch.object(tc_serial, "ANDROID_REPORTS_SCROLL_POLL_ATTEMPTS", 3):
            with self.assertRaisesRegex(ValueError, "TC001_ANDROID_REPORTS_TAB_NOT_CONFIRMED_FOR_SCROLL"):
                self._run_android_verification(
                    event_key=expected, report_scan_keys=[earlier, expected],
                    transient_post_scroll_navigation_dumps=3)

    def test_reports_scroll_region_keeps_top_event_visible_when_header_is_collapsed(self):
        expected = {"physical_device_id": "c3-146393c5d158", "logical_node_id": "bedroom",
                    "origin_session_id": 118, "event_sequence": 100}
        root, _raw = self._android_tree([
            ("", "[0,128][1220,2577]", None,
             {"class": "android.webkit.WebView", "scrollable": "true",
              "package": "in.gharsajag.caregiver.discoverytest"}),
            ("Latest recorded events", "[770,128][1181,128]", None,
             {"class": "android.widget.TextView",
              "package": "in.gharsajag.caregiver.discoverytest"}),
            ("TEST_ONLY authenticated caregiver data · gs177-test-product · AUTHENTICATED_GS148_TEST_ONLY",
             "[30,128][1189,128]", None,
             {"class": "android.widget.TextView",
              "package": "in.gharsajag.caregiver.discoverytest"}),
            ("EventKey: " + json.dumps(expected, separators=(",", ":")),
             "[444,128][1147,206]", None,
             {"class": "android.view.View",
              "package": "in.gharsajag.caregiver.discoverytest"}),
            ("Reports", "[607,2420][916,2577]", None,
             {"class": "android.widget.Button", "clickable": "true",
              "package": "in.gharsajag.caregiver.discoverytest"}),
            ("Home", "[0,2420][306,2577]", None,
             {"class": "android.widget.Button", "clickable": "true",
              "package": "in.gharsajag.caregiver.discoverytest"}),
        ])
        viewport = tc_serial.reports_scroll_region(root)
        self.assertEqual(viewport[1], 128)
        self.assertTrue(tc_serial.exact_key_in_ui(root, expected, visible_bounds=viewport))

    def test_android_observer_stops_at_bounded_reports_scroll_limit(self):
        expected = {"physical_device_id": "c3-146393c5d158", "logical_node_id": "bedroom",
                    "origin_session_id": 118, "event_sequence": 999}
        pages = [{**expected, "event_sequence": sequence} for sequence in (1, 2, 3, 4)]
        with patch.object(tc_serial, "ANDROID_REPORTS_MAX_SCROLLS", 2), \
                patch.object(tc_serial, "scroll_reports", wraps=tc_serial.scroll_reports) as scroll:
            with self.assertRaisesRegex(ValueError, "REPORTS_SCROLL_LIMIT_REACHED"):
                self._run_android_verification(event_key=expected, report_scan_keys=pages)
            self.assertEqual(scroll.call_count, 2)

    def test_android_observer_fails_explicitly_when_key_is_absent_at_reports_end(self):
        expected = {"physical_device_id": "c3-146393c5d158", "logical_node_id": "bedroom",
                    "origin_session_id": 118, "event_sequence": 100}
        visible = {**expected, "event_sequence": 99}
        with patch.object(tc_serial, "scroll_reports", wraps=tc_serial.scroll_reports) as scroll:
            with self.assertRaisesRegex(ValueError,
                                        "TC001_EXACT_EVENT_KEY_NOT_VISIBLE_IN_ANDROID_EVENT_DETAILS"):
                self._run_android_verification(event_key=expected, report_scan_keys=[visible])
            self.assertEqual(scroll.call_count, tc_serial.ANDROID_REPORTS_END_NO_PROGRESS)

    def test_android_observer_rechecks_home_while_scrolling_reports(self):
        expected = {"physical_device_id": "c3-146393c5d158", "logical_node_id": "bedroom",
                    "origin_session_id": 118, "event_sequence": 100}
        earlier = {**expected, "event_sequence": 99}
        with self.assertRaisesRegex(ValueError, "REPORTS_HOME_CHANGED_DURING_SCROLL"):
            self._run_android_verification(
                event_key=expected, report_scan_keys=[earlier, expected],
                report_scan_homes=["gs177-test-product", "different-test-home"])

    def test_android_verification_refreshes_and_matches_exact_hub_morning_decision(self):
        decision_id = "morning-complete:p15:test-c3-bedroomn7:bedrooms82q9"
        result, calls = self._run_android_verification(decision_id=decision_id)
        self.assertEqual(result["observation"], "AUTOMATED_PASS")
        self.assertEqual(result["decision_id"], decision_id)
        self.assertEqual(result["decision_kind"], "MORNING_ROUTINE_COMPLETED")
        self.assertEqual(result["event_label"], "Morning routine completed")
        self.assertTrue(result["outcome_details_open"])
        self.assertTrue(result["screenshot_png_b64"])
        self.assertTrue(any(args[:2] == ("shell", "monkey") for _, args in calls))

    def test_android_verification_rejects_a_different_hub_decision(self):
        with self.assertRaisesRegex(ValueError, "EXACT_HUB_DECISION_NOT_VISIBLE"):
            self._run_android_verification(
                decision_id="morning-complete:p15:test-c3-bedroomn7:bedrooms82q10",
                visible_decision_id="morning-complete:p15:test-c3-bedroomn7:bedrooms82q9")

    def test_android_verification_fails_closed_on_wrong_live_backend_origin(self):
        with self.assertRaisesRegex(ValueError, "BACKEND_ORIGIN_HOME_OR_AUTHENTICATED_SESSION_MISMATCH"):
            self._run_android_verification(settings_origin="https://other.example")

    def test_android_readiness_requires_the_receipt_bound_adb_device(self):
        phone = {"adb_serial": "ZA2237MRHN", "package": "in.gharsajag.caregiver.discoverytest",
                 "version_name": "0.4.0-connected-lite-staging"}
        with patch.object(tc_serial.subprocess, "run", return_value=subprocess.CompletedProcess(
                ["adb", "devices", "-l"], 0, "List of devices attached\n", "")):
            with self.assertRaisesRegex(ValueError, "NOT_AUTHORIZED_OR_CONNECTED"):
                tc_serial.android_device_ready({"phone": phone}, adb_locator=lambda: Path("adb.exe"))

    def test_windows_injection_opens_only_c3_and_requires_matching_hub_ack(self):
        opened = []
        class FakeStream:
            def __init__(self):
                self.port = ""; self.buffer = bytearray(); self.is_open = False
                self.timeout = None; self.write_timeout = None; self.dtr = True; self.rts = True
            @property
            def in_waiting(self): return len(self.buffer)
            def open(self): self.is_open = True; opened.append(self.port)
            def write(self, value):
                if value == b"GET_STATE\n":
                    self.buffer.extend(b"I HIL_STATE role=c3 power_mode=HIL_AWAKE_TEST_ONLY "
                        b"hil_build=0 hil_control=1 physical_wake=0 runtime_live=4 sensing_live=5 "
                        b"retained=0 in_flight=0 pending_inject=0\nI HIL_OK command=GET_STATE\n")
                elif value == b"INJECT_MOTION\n":
                    self.buffer.extend(b"I HIL_OK command=INJECT_MOTION\n"
                        b"I PIR -> NodeRuntime session=81 seq=4\n"
                        b"I NodeMessage sent session=81 seq=4\n"
                        b"I Application ACK session=81 seq=4 class=0 retired=1\n")
                return len(value)
            def flush(self): pass
            def read(self, count):
                value = bytes(self.buffer[:count]); del self.buffer[:count]; return value
            def close(self): self.is_open = False
        c3 = {"port": "COM4", "usb_hwid": "USB VID:PID=303A:1001 SER=14:63:93:C5:D1:58 LOCATION=1-1",
              "serial_number": "14:63:93:C5:D1:58", "hil_control": True,
              "hil_build": False, "physical_wake": False}
        s3 = {"port": "COM10", "usb_hwid": "USB VID:PID=303A:1001 SER=E0:72:A1:D3:8D:34 LOCATION=1-2",
              "serial_number": "E0:72:A1:D3:8D:34"}
        config = {"c3": c3, "s3": s3}
        with (patch.object(tc_serial, "ports", return_value=[c3, s3]),
              patch.object(tc_serial.serial, "Serial", FakeStream)):
            result = tc_serial.run(config)
        self.assertEqual(opened, ["COM4"])
        self.assertFalse(result["s3_serial_opened"])
        self.assertEqual(result["runtime_live"], 4)
        self.assertEqual(result["sensing_live"], 5)
        self.assertTrue(result["hub_application_acknowledged"])
        self.assertEqual(tc.physical_key(result["c3"]), (81, 4))
        self.assertNotIn("reset_safe_uart_verified", result)

    def test_five_run_approval_is_exact_owner_only_and_keeps_s3_uart_closed(self):
        fixture = {"home_id": "gs177-test-product", "physical_device_id": "c3-146393c5d158",
                   "hub_id": "hub-e072a1d38d34",
                   "c3": {"port": "COM4", "serial_number": "14:63:93:C5:D1:58"},
                   "s3": {"port": "COM10", "serial_number": "E0:72:A1:D3:8D:34"}}
        approval = {"schema_version": 1, "test_id": "TC-001", "profile": "GS179_TEST_ONLY",
                    "run_count": 5, "operation": "C3_INJECT_MOTION_FIVE_RUN_CAMPAIGN",
                    "home_id": fixture["home_id"], "physical_device_id": fixture["physical_device_id"],
                    "hub_id": fixture["hub_id"], "c3": fixture["c3"],
                    "s3": {**fixture["s3"], "uart_open_authorized": False},
                    "c3_serial_open_reset_risk_accepted": True, "stop_on_first_failure": True,
                    "android_auto_verify_each_event": True, "firmware_write_authorized": False,
                    "commissioning_authorized": False,
                    "ownership_or_enrollment_mutation_authorized": False,
                    "database_mutation_authorized": False,
                    "approval_ref": "owner-chat-2026-10-27", "approved_at": datetime.now(timezone.utc).isoformat()}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "approval.json"
            path.write_text(json.dumps(approval)); path.chmod(0o600)
            self.assertEqual(tc.campaign_approval(path, fixture)["run_count"], 5)
            approval["s3"]["uart_open_authorized"] = True
            path.write_text(json.dumps(approval)); path.chmod(0o600)
            with self.assertRaisesRegex(ValueError, "scope_or_fixture_mismatch"):
                tc.campaign_approval(path, fixture)

    def test_campaign_stops_after_first_failed_run_and_marks_remaining_not_run(self):
        fixture = {"home_id": "gs177-test-product", "physical_device_id": "c3-146393c5d158",
                   "hub_id": "hub-e072a1d38d34",
                   "c3": {"port": "COM4", "serial_number": "14:63:93:C5:D1:58"},
                   "s3": {"port": "COM10", "serial_number": "E0:72:A1:D3:8D:34"}}
        approval = {"approval_ref": "owner-approved"}
        readiness = {"backend": {"POSTGRES_READY": "PASS", "CAREGIVER_HTTPS_READY": "PASS", "DEVELOPMENT_ENDPOINT_READY": "PASS", "LAPTOP_LAN_ENDPOINT_TLS_READY": "PASS"},
                     "caregiver_home": {"caregiver_home_ready": True},
                     "physical_boards": {"c3": "PASS", "s3": "PASS"},
                     "fixture": {"status": "PASS"}, "android_apk": {"status": "PASS"},
                     "hub_ingress": {"status": "PASS"}}
        with tempfile.TemporaryDirectory() as directory:
            approval_path = Path(directory) / "approval.json"
            approval_path.write_text("{}"); approval_path.chmod(0o600)
            controller = tc.Controller()
            controller.lock.acquire()
            campaign = {"run_id": "TC001-CAMPAIGN-test", "planned_runs": 5,
                        "passed_runs": 0, "completed_runs": 0, "runs": [], "overall": "PARTIAL",
                        "stages": {"campaign_preflight": {"status": "NOT_VERIFIED"}}}
            controller.current = campaign
            def fail_once(report, **_kwargs):
                report["overall"] = "FAIL"
                report["stages"]["c3_injection"] = {"status": "FAIL", "reason": "test"}
            with (patch.object(controller, "readiness", return_value=readiness),
                  patch.object(tc, "exact_fixture", return_value=fixture),
                  patch.object(tc, "campaign_approval", return_value=approval),
                  patch.object(tc, "CAMPAIGN_APPROVAL", approval_path),
                  patch.object(controller, "execute", side_effect=fail_once) as execute,
                  patch.object(controller, "save")):
                controller.execute_campaign(campaign)
            self.assertEqual(execute.call_count, 1)
            self.assertEqual(campaign["completed_runs"], 1)
            self.assertEqual(campaign["passed_runs"], 0)
            self.assertEqual(len(campaign["not_run"]), 4)
            self.assertEqual(campaign["overall"], "FAIL")
            self.assertFalse(controller.lock.locked())

    def report(self):
        return {"run_id": "TC001-test-" + tc.secrets.token_hex(4), "test_id": "TC-001", "overall": "PARTIAL",
                "apk_observation": "NOT_VERIFIED", "stages": {
                    name: {"status": "NOT_VERIFIED", "reason": "not reached"} for name in tc.STAGES}}

    def execute(self, report, serial_data, baseline=None, outcome=None, home_origin="https://laptop.local", ports_override=None, mode_state=True, pending_observations=0):
        fixture = {"home_id": "gs177-test-product", "physical_device_id": "test-c3-bedroom",
                   "expected_caregiver_origin": "https://laptop.local",
                   "approval_ref": "test", "hub_id": "test-hub-a", "installation_epoch": 1,
                   "phone_receipt": {"adb_serial": "ZA2237MRHN", "package": "in.gharsajag.caregiver.discoverytest",
                                     "version_name": "0.4.0-connected-lite-staging", "signer_sha256": "b" * 64,
                                     "backend_origin": "https://laptop.local"},
                   "c3": {"port": "COM10", "usb_hwid": "c3", "serial_number": "c3s",
                          "image_sha256": "a" * 64, "firmware_source_head": "a" * 40},
                   "s3": {"port": "COM11", "usb_hwid": "s3", "serial_number": "s3s",
                          "image_sha256": "b" * 64, "firmware_source_head": "b" * 40}}
        ports = [{"port": b["port"], "usb_hwid": b["usb_hwid"], "serial_number": b["serial_number"]}
                 for b in (fixture["c3"], fixture["s3"])]
        baseline = baseline or {"keys": [], "count": 0}
        if (mode_state and "c3" in serial_data and
                any("HIL_OK command=INJECT_MOTION" in line for line in serial_data["c3"])):
            if not any("HIL_STATE role=c3" in line for line in serial_data["c3"]):
                serial_data["c3"].insert(0, "HIL_STATE role=c3 power_mode=HIL_AWAKE_TEST_ONLY "
                    "hil_build=0 hil_control=1 physical_wake=0 runtime_live=2 sensing_live=2 "
                    "retained=0 in_flight=0 pending_inject=0")
        baseline.setdefault("authority_ready", True)
        baseline.setdefault("enrollment_generation", 1)
        outcome = outcome or {"durable_count": 1, "caregiver_count": 1,
                              "event_kind": "MOTION", "event_location": "bedroom",
                              "event_id": "evt-1", "caregiver_event_id": tc.event_key_text(
                                  "test-c3-bedroom", *(tc.physical_key(serial_data.get("c3", [])) or (12, 3))),
                              "committing_hub_id": "test-hub-a", "ownership_epoch": 1,
                              "node_enrollment_generation": 1}
        controller = tc.Controller()
        controller.lock.acquire()
        serial_data["s3"] = []
        serial_data["s3_serial_opened"] = False
        serial_data.setdefault("c3_state", next((line for line in reversed(serial_data.get("c3", []))
                                                  if "HIL_STATE role=c3" in line), ""))
        apk_png = base64.b64encode(b"\x89PNG\r\n\x1a\nTC001-test").decode()
        apk_ui = b"<hierarchy><node text=\"EventKey\"/></hierarchy>"
        apk_result = {"status": "PASS", "observation": "AUTOMATED_PASS",
                      "event_key": outcome["event_key"] if "event_key" in outcome else None,
                      "home_id": fixture["home_id"], "screenshot_png_b64": apk_png,
                      "ui_hierarchy_xml_b64": base64.b64encode(apk_ui).decode(),
                      "backend_origin": "https://laptop.local", "backend_status": "Backend API · CONNECTED",
                      "package": fixture["phone_receipt"]["package"],
                      "device_serial": fixture["phone_receipt"]["adb_serial"],
                      "version_name": fixture["phone_receipt"]["version_name"],
                      "signer_sha256": fixture["phone_receipt"]["signer_sha256"],
                      "reports_view": "Latest recorded events", "event_details_open": True,
                      "event_label": "Motion recorded", "logical_node_id": "bedroom",
                      "ui_dump_sha256": hashlib.sha256(apk_ui).hexdigest()}
        state_dir = tempfile.TemporaryDirectory()
        self.addCleanup(state_dir.cleanup)
        with (patch.object(tc, "STATE", Path(state_dir.name)),
              patch.object(controller, "readiness", return_value={"backend": {"POSTGRES_READY": "PASS", "CAREGIVER_HTTPS_READY": "PASS", "DEVELOPMENT_ENDPOINT_READY": "PASS", "LAPTOP_LAN_ENDPOINT_TLS_READY": "PASS"}, "caregiver_home": {"caregiver_home_ready": True, "backend_origin": home_origin}, "android_apk": {"status": "PASS"}, "hub_ingress": {"status": "PASS"}}),
              patch.object(tc, "exact_fixture", return_value=fixture),
              patch.object(tc, "powershell", side_effect=[ports if ports_override is None else ports_override, serial_data, apk_result]) as hardware,
              patch.object(tc, "backend", side_effect=[baseline] +
                  [{"durable_count": 0, "caregiver_count": 0}] * pending_observations + [outcome]),
              patch.object(controller, "save")):
            if "c3" in serial_data:
                pair_for_apk = tc.physical_key(serial_data["c3"])
                apk_result["event_key"] = {"physical_device_id": fixture["physical_device_id"],
                                            "logical_node_id": "bedroom",
                                            "origin_session_id": pair_for_apk[0],
                                            "event_sequence": pair_for_apk[1]}
                apk_result["screenshot_png_b64"] = apk_png
                serial_data.setdefault("c3_state", "HIL_STATE role=c3 power_mode=HIL_AWAKE_TEST_ONLY "
                                       "hil_build=0 hil_control=1 physical_wake=0 runtime_live=2 "
                                       "sensing_live=2 retained=0 in_flight=0 pending_inject=0")
                serial_data.setdefault("s3_serial_opened", False)
            controller.execute(report)
        self.assertFalse(controller.lock.locked())
        return hardware

    def test_source_linked_success_requires_automated_apk_exact_key_and_is_repeatable(self):
        for session, sequence in ((12, 3), (12, 4)):
            with self.subTest(key=(session, sequence)):
                c3 = ["HIL_OK command=INJECT_MOTION",
                      f"PIR -> NodeRuntime session={session} seq={sequence}",
                      f"NodeMessage sent session={session} seq={sequence}",
                      f"Application ACK session={session} seq={sequence} class=0 retired=1"]
                s3 = [f"Authenticated event logical=bedroom session={session} seq={sequence} sensor=PIR event=MOTION event_id=p15:test-c3-bedroomn7:bedrooms{session}q{sequence} room=bedroom ack=0 send=ESP_OK"]
                report = self.report()
                self.execute(report, {"c3": c3, "s3": s3}, baseline={"keys": [[12, sequence - 1]], "count": 1})
                self.assertEqual(report["stages"]["caregiver_api"]["status"], "PASS")
                self.assertEqual(report["stages"]["android_apk"]["status"], "PASS",
                                 report["stages"]["android_apk"])
                self.assertEqual(report["apk_observation"], "AUTOMATED_PASS")
                self.assertEqual(report["overall"], "PASS")
                self.assertEqual(report["event_key"]["event_sequence"], sequence)
                self.assertFalse(report["serial_evidence"]["s3_uart_opened"])
                self.assertEqual(report["duplicate_count"], 0)

    def test_dev_wait_accepts_late_genuine_commit_but_remains_bounded_and_separate(self):
        for development, pending, expected, attempts in ((True, 16, "PASS", 17),
                (False, 16, "FAIL", 15), (True, 100, "FAIL", 90)):
            report = self.report()
            with self.subTest(development=development, pending=pending), \
                    patch.object(tc, "development_input_trial", return_value=development), \
                    patch.object(tc.time, "sleep"):
                self.execute(report, {"c3": ["HIL_OK command=INJECT_MOTION",
                    "PIR -> NodeRuntime session=12 seq=3",
                    "Application ACK session=12 seq=3 class=0 retired=1"]},
                    pending_observations=pending)
            self.assertEqual(report["overall"], expected, "GS117-DEV-WAIT-001")
            self.assertEqual(report["backend_observation_wait"]["attempts"], attempts)
            self.assertFalse(report["backend_observation_wait"]["release_latency_qualified"])

    def test_duplicate_durable_event_count_is_recorded_before_campaign_stops(self):
        c3 = ["HIL_OK command=INJECT_MOTION", "PIR -> NodeRuntime session=12 seq=3",
              "Application ACK session=12 seq=3 class=0 retired=1"]
        report = self.report()
        self.execute(report, {"c3": c3}, outcome={
            "durable_count": 2, "caregiver_count": 2, "event_kind": "MOTION",
            "event_location": "bedroom", "event_id": "evt-1",
            "caregiver_event_id": tc.event_key_text("test-c3-bedroom", 12, 3),
            "committing_hub_id": "test-hub-a", "ownership_epoch": 1,
            "node_enrollment_generation": 1})
        self.assertEqual(report["stages"]["backend_commit"]["status"], "PASS")
        self.assertEqual(report["duplicate_count"], 1)
        self.assertEqual(report["stages"]["postgres_exactly_once"]["status"], "FAIL")
        self.assertEqual(report["stages"]["hub_cloudsync"]["status"], "NOT_VERIFIED")
        self.assertEqual(report["overall"], "FAIL")

    def test_s3_memory_capacity_parser_requires_consistent_flash_and_psram(self):
        complete = tc_serial.s3_memory_capacity([
            "I (692) boot: SPI Flash size: 16MB",
            "I (693) esp_psram: Found 8MB PSRAM device",
        ])
        self.assertEqual(complete["status"], "PASS")
        self.assertEqual(complete["flash_size_bytes"], 16 * 1024 * 1024)
        self.assertEqual(complete["psram_size_bytes"], 8 * 1024 * 1024)

        incomplete = tc_serial.s3_memory_capacity(["I (692) boot: SPI Flash size: 16MB"])
        self.assertEqual(incomplete["status"], "INCOMPLETE")
        self.assertIsNone(incomplete["psram_size_bytes"])

        conflict = tc_serial.s3_memory_capacity([
            "I (692) boot: SPI Flash size: 16MB",
            "I (693) boot: SPI Flash size: 8MB",
            "I (694) esp_psram: Found 8MB PSRAM device",
        ])
        self.assertEqual(conflict["status"], "CONFLICT")
        self.assertIsNone(conflict["flash_size_bytes"])

    def test_reset_aware_observer_queries_status_without_motion_injection(self):
        class FakeSerial:
            def __init__(self):
                self.port = ""
                self.timeout = None
                self.write_timeout = None
                self.dtr = True
                self.rts = True
                self.is_open = False
                self.buffer = bytearray()
                self.writes = []
                self.input_purges = 0

            @property
            def in_waiting(self):
                return len(self.buffer)

            def open(self):
                self.is_open = True
                if self.port == "COM10":
                    self.buffer.extend(
                        b"I (1) HIL_FIXTURE_READY protocol=1 commands=FIXTURE_STATUS\n"
                        b"I (2) HubRuntime storage=ready CloudSync=disabled\n")

            def write(self, data):
                self.writes.append(data)
                if data == b"GET_STATE\n":
                    self.buffer.extend(
                        b"I (2) HIL_STATE role=c3 power_mode=HIL_AWAKE_TEST_ONLY "
                        b"hil_build=0 hil_control=1 physical_wake=0 "
                        b"wifi_psk=private password=private\n")
                return len(data)

            def flush(self):
                pass

            def reset_input_buffer(self):
                self.input_purges += 1
                self.buffer.clear()

            def read(self, count):
                result = bytes(self.buffer[:count])
                del self.buffer[:count]
                return result

            def close(self):
                self.is_open = False

        boards = {
            "c3": {"port": "COM4", "serial_number": "14:63:93:C5:D1:58",
                   "usb_hwid": "USB VID:PID=303A:1001 SER=14:63:93:C5:D1:58"},
            "s3": {"port": "COM10", "serial_number": "E0:72:A1:D3:8D:34",
                   "usb_hwid": "USB VID:PID=303A:1001 SER=E0:72:A1:D3:8D:34"},
        }
        for query_s3, reset_s3 in ((False, False), (True, False), (True, True)):
            with self.subTest(query_s3=query_s3, reset_s3=reset_s3):
                fake_streams = [FakeSerial(), FakeSerial()]
                stream_iter = iter(fake_streams)
                clock_value = [0.0]
                resets = []

                def fake_clock():
                    clock_value[0] += 1.0
                    return clock_value[0]

                result = tc_serial.observe(
                    {"c3": boards["c3"], "s3": boards["s3"],
                     "query_s3_status": query_s3, "s3_boot_reset": reset_s3},
                    serial_factory=lambda: next(stream_iter),
                    port_finder=lambda: [boards["c3"], boards["s3"]],
                    clock=fake_clock, sleep=lambda _seconds: None,
                    boot_reset=lambda stream: resets.append(stream))
                self.assertEqual(resets, [fake_streams[0]] if reset_s3 else [])
                self.assertEqual(fake_streams[0].writes,
                                 [b"FIXTURE_STATUS\n"] if query_s3 else [])
                self.assertEqual(fake_streams[1].writes, [b"GET_STATE\n"])
                self.assertEqual(result["s3_status_command_ready"], True)
                self.assertEqual(result["s3_status_command_sent"], query_s3)
                self.assertEqual(result["s3_config_receive_pending"], False)
                self.assertTrue(all(not stream.is_open for stream in fake_streams))
                self.assertTrue(any("HIL_AWAKE_TEST_ONLY" in line for line in result["c3"]))
                self.assertTrue(any("CloudSync=disabled" in line for line in result["s3"]))
                self.assertFalse(any("private" in line
                                     for role in ("c3", "s3")
                                     for line in result[role]))

        fake_streams = [FakeSerial(), FakeSerial()]
        stream_iter = iter(fake_streams)
        clock_value = [0.0]

        def fake_clock():
            clock_value[0] += 1.0
            return clock_value[0]

        result = tc_serial.observe(
            {"c3": boards["c3"], "s3": boards["s3"],
             "query_s3_status": False, "s3_boot_reset": False,
             "observation_seconds": 10},
            serial_factory=lambda: next(stream_iter),
            port_finder=lambda: [boards["c3"], boards["s3"]],
            clock=fake_clock, sleep=lambda _seconds: None,
            bootstrap_exchange=lambda _stream, **_kwargs: 7323)
        self.assertEqual(result["bootstrap_host_write_bytes"], 7323)
        self.assertGreater(result["bootstrap_exchange_ms"], 0)
        self.assertGreaterEqual(clock_value[0], 20)

        fake_streams = [FakeSerial(), FakeSerial()]
        stream_iter = iter(fake_streams)
        def after_reset(stream):
            self.assertEqual(stream.input_purges, 1)
            self.assertEqual(stream.buffer, b"")
        def exchange(stream, **kwargs):
            self.assertTrue(kwargs["require_boot"])
            self.assertTrue(kwargs["identity_check"]())
            return 7323
        tc_serial.observe(
            {"c3": boards["c3"], "s3": boards["s3"], "s3_boot_reset": True},
            serial_factory=lambda: next(stream_iter),
            port_finder=lambda: [boards["c3"], boards["s3"]],
            clock=fake_clock, sleep=lambda _seconds: None,
            boot_reset=after_reset, bootstrap_exchange=exchange)

        # GS117-RECOVERY-STATUS-001: sample live counters without reopening ports.
        fake_streams = [FakeSerial(), FakeSerial()]
        stream_iter = iter(fake_streams)
        clock_value[0] = 0.0
        result = tc_serial.observe(
            {"c3": boards["c3"], "s3": boards["s3"],
             "observation_seconds": 30, "c3_status_interval_seconds": 5},
            serial_factory=lambda: next(stream_iter),
            port_finder=lambda: [boards["c3"], boards["s3"]],
            clock=fake_clock, sleep=lambda _seconds: None)
        self.assertGreater(result["c3_status_queries"], 1)
        self.assertLessEqual(result["c3_status_queries"], 6)
        self.assertEqual(fake_streams[0].writes, [])
        self.assertEqual(fake_streams[1].writes,
                         [b"GET_STATE\n"] * result["c3_status_queries"])
        self.assertTrue(all(not stream.is_open for stream in fake_streams))

    def test_observer_fails_closed_when_current_s3_memory_profile_is_missing(self):
        class MemorySerial:
            def __init__(self):
                self.port = ""
                self.timeout = None
                self.write_timeout = None
                self.dtr = False
                self.rts = False
                self.is_open = False
                self.buffer = bytearray()
                self.writes = []
            @property
            def in_waiting(self): return len(self.buffer)
            def open(self):
                self.is_open = True
                if self.port == "COM10":
                    self.buffer.extend(("I (1) boot: SPI Flash size: 16MB\n"
                                        "I (2) HIL_FIXTURE_READY protocol=1 commands=FIXTURE_STATUS\n").encode())
            def write(self, value):
                self.writes.append(value)
                if value == b"GET_STATE\n":
                    self.buffer.extend(b"HIL_STATE role=c3 power_mode=HIL_AWAKE_TEST_ONLY "
                                       b"hil_build=0 hil_control=1 physical_wake=0\n")
                return len(value)
            def flush(self): pass
            def reset_input_buffer(self): self.buffer.clear()
            def read(self, count):
                value = bytes(self.buffer[:count]); del self.buffer[:count]; return value
            def close(self): self.is_open = False

        boards = {
            "c3": {"port": "COM4", "serial_number": "14:63:93:C5:D1:58",
                   "usb_hwid": "USB VID:PID=303A:1001 SER=14:63:93:C5:D1:58"},
            "s3": {"port": "COM10", "serial_number": "E0:72:A1:D3:8D:34",
                   "usb_hwid": "USB VID:PID=303A:1001 SER=E0:72:A1:D3:8D:34"},
        }
        streams = iter((MemorySerial(), MemorySerial()))
        config = {"c3": boards["c3"], "s3": boards["s3"],
                  "require_s3_memory_profile": True,
                  "expected_s3_memory_profile": {"flash_size_bytes": 16 * 1024 * 1024,
                                                 "psram_size_bytes": 8 * 1024 * 1024}}
        ticks = [0.0]
        def clock():
            ticks[0] += 0.1
            return ticks[0]
        with self.assertRaisesRegex(ValueError, "TC001_S3_MEMORY_PROFILE_NOT_VERIFIED") as raised:
            tc_serial.observe(config, serial_factory=lambda: next(streams),
                              port_finder=lambda: [*boards.values()],
                              clock=clock, sleep=lambda _seconds: None)
        self.assertEqual(raised.exception.captured_observation["s3_memory_capacity"]["status"],
                         "INCOMPLETE")

    def test_observer_skips_status_command_during_secure_config_receive(self):
        """GS117-S3-STATUS-GATE-001: do not feed CLI text to GS40 envelope RX."""
        class FakeSerial:
            startup = b""
            def __init__(self):
                self.port = ""
                self.timeout = None
                self.write_timeout = None
                self.dtr = True
                self.rts = True
                self.is_open = False
                self.buffer = bytearray()
                self.writes = []
            @property
            def in_waiting(self): return len(self.buffer)
            def open(self):
                self.is_open = True
                if self.port == "COM10":
                    self.buffer.extend(self.startup)
            def write(self, data):
                self.writes.append(data)
                if data == b"GET_STATE\n":
                    self.buffer.extend(b"HIL_STATE role=c3\n")
                return len(data)
            def flush(self): pass
            def reset_input_buffer(self): self.buffer.clear()
            def read(self, count):
                value = bytes(self.buffer[:count]); del self.buffer[:count]; return value
            def close(self): self.is_open = False

        boards = {
            "c3": {"port": "COM4", "serial_number": "14:63:93:C5:D1:58",
                   "usb_hwid": "USB VID:PID=303A:1001 SER=14:63:93:C5:D1:58"},
            "s3": {"port": "COM10", "serial_number": "E0:72:A1:D3:8D:34",
                   "usb_hwid": "USB VID:PID=303A:1001 SER=E0:72:A1:D3:8D:34"},
        }
        challenge = b"GS40T/1 CHALLENGE nonce=fixture-test\n"
        ready = b"HIL_FIXTURE_READY protocol=1 commands=FIXTURE_STATUS\n"
        for startup in (challenge, ready + challenge, b""):
            with self.subTest(startup=startup):
                FakeSerial.startup = startup
                streams = [FakeSerial(), FakeSerial()]
                iterator = iter(streams)
                tick = [0.0]
                def clock():
                    tick[0] += 1.0
                    return tick[0]

                result = tc_serial.observe(
                    {"c3": boards["c3"], "s3": boards["s3"], "query_s3_status": True,
                     "s3_boot_reset": False, "observation_seconds": 10},
                    serial_factory=lambda: next(iterator),
                    port_finder=lambda: [boards["c3"], boards["s3"]],
                    clock=clock, sleep=lambda _seconds: None)
                self.assertEqual(result["s3_config_receive_pending"], bool(startup))
                self.assertEqual(result["s3_status_command_ready"], ready in startup)
                self.assertFalse(result["s3_status_command_sent"])
                self.assertEqual(streams[0].writes, [])
                self.assertEqual(streams[1].writes, [b"GET_STATE\n"])
                self.assertTrue(all(not stream.is_open for stream in streams))

    def test_serial_evidence_preserves_complete_profile_and_boot_failure(self):
        state = (
            "I (3395682) gs_node_runtime: HIL_STATE role=c3 session=99 retained=0 "
            "in_flight=0 sensing_live=0 runtime_live=0 pending_inject=0 heap=197292 "
            "min_heap=179820 ota_slot=ota_1 power_mode=HIL_AWAKE_TEST_ONLY "
            "hil_build=0 hil_control=1 physical_wake=0 wifi_psk=private"
        )
        class Stream:
            data = (state + "\nI (1) gs_hub_product: Starting product composition\n"
                    "I (2) app_init: App version: current\n"
                    "I (3) boot: SPI Flash size: 16MB\n"
                    "I (4) esp_psram: Found 8MB PSRAM device\n"
                    "abort() was called at PC 0x40370000\n"
                    "assert failed: xQueueSemaphoreTake queue.c:1713 (pxQueue->uxItemSize == 0)\n"
                    "Guru Meditation Error: Core 0 panic'ed (Stack protection fault).\n"
                    "3fca0000: 0x12345678 raw_stack_bytes\n"
                    "HIL_FIXTURE_STATUS state=idle\n").encode()
            in_waiting = len(data)

            def read(self, count):
                return self.data[:count]

        lines = []
        self.assertEqual(tc_serial.collect(Stream(), "", lines), "")
        self.assertEqual(len(lines), 9)
        self.assertIn("physical_wake=0", lines[0])
        self.assertNotIn("private", "\n".join(lines))
        self.assertIn("SPI Flash size: 16MB", "\n".join(lines))
        self.assertIn("Found 8MB PSRAM device", "\n".join(lines))
        self.assertIn("abort()", lines[5])
        self.assertIn("assert failed:", lines[6])
        self.assertIn("Guru Meditation Error", lines[7])
        self.assertNotIn("raw_stack_bytes", "\n".join(lines))

    def test_status_query_rejects_non_boolean_before_open(self):
        for flag in ("query_s3_status", "s3_boot_reset"):
            with self.subTest(flag=flag), self.assertRaisesRegex(ValueError, "FLAG_MUST_BE_BOOLEAN"):
                tc_serial.observe({"c3": {}, "s3": {}, flag: "true"})

    def test_observation_duration_is_bounded_before_open(self):
        for duration in (True, 0, 9, 61, "10"):
            with self.subTest(duration=duration), self.assertRaisesRegex(ValueError, "SECONDS_OUT_OF_RANGE"):
                tc_serial.observe({"c3": {}, "s3": {}, "observation_seconds": duration})
        for interval in (True, -1, 1, 4, 31, "10"):
            with self.subTest(interval=interval), self.assertRaisesRegex(ValueError, "INTERVAL_OUT_OF_RANGE"):
                tc_serial.observe({"c3": {}, "s3": {}, "c3_status_interval_seconds": interval})

    def test_development_observation_window_is_explicit_and_still_bounded(self):
        config = {"profile": "GS117_DEV_TEST_ONLY", "observation_seconds": 120,
                  "c3": {"port": "COM4", "serial_number": "14:63:93:C5:D1:58"},
                  "s3": {"port": "COM10", "serial_number": "E0:72:A1:D3:8D:34"}}
        with self.assertRaisesRegex(ValueError, "VERIFIED_USB_INTERFACE_MISMATCH"):
            tc_serial.observe(config, port_finder=lambda: [])
        for profile, duration in (("GS117_DEV_TEST_ONLY", 121), ("GS179_TEST_ONLY", 61)):
            with self.subTest(profile=profile), self.assertRaisesRegex(ValueError, "SECONDS_OUT_OF_RANGE"):
                tc_serial.observe({**config, "profile": profile, "observation_seconds": duration})

    def test_bootstrap_carries_only_target_bound_encrypted_frame(self):
        nonce = b"n" * 32
        public = "04" + "ab" * 64

        class Stream:
            def __init__(self):
                self.data = bytearray((f"GS40T/1 CHALLENGE nonce={nonce.hex()} "
                                      f"public_key={public} max_envelope=24576\n").encode())
                self.writes = []

            @property
            def in_waiting(self):
                return len(self.data)

            def read(self, count):
                result = bytes(self.data[:count])
                del self.data[:count]
                return result

            def write(self, data):
                self.writes.append(data)
                return len(data)

            def flush(self):
                pass

        for timeout in (True, 4, 76, "70"):
            with self.subTest(timeout=timeout), self.assertRaisesRegex(
                    ValueError, "TC001_BOOTSTRAP_CHALLENGE_TIMEOUT_OUT_OF_RANGE"):
                tc_serial.bootstrap_config(
                    Stream(), incoming=io.StringIO(), outgoing=io.StringIO(),
                    challenge_timeout_seconds=timeout)

        envelope = b"G40E\x01" + nonce + b"encrypted-not-plaintext".ljust(480, b"x")
        frame = len(envelope).to_bytes(4, "big") + envelope
        for valid in (True, False):
            stream, output = Stream(), io.StringIO()
            supplied = frame if valid else frame[:9] + b"z" * 32 + frame[41:]
            response = io.StringIO(json.dumps({
                "encrypted_envelope_b64": base64.b64encode(supplied).decode()}) + "\n")
            if valid:
                sent = tc_serial.bootstrap_config(stream, incoming=response, outgoing=output)
                self.assertEqual(sent, len(frame))
                self.assertEqual(stream.writes, [frame])
                self.assertEqual(json.loads(output.getvalue())["nonce"], nonce.hex())
            else:
                with self.assertRaisesRegex(ValueError, "ENCRYPTED_RESPONSE_INVALID"):
                    tc_serial.bootstrap_config(stream, incoming=response, outgoing=output)
                self.assertEqual(stream.writes, [])
            self.assertNotIn("encrypted-not-plaintext", output.getvalue())
            self.assertNotIn(base64.b64encode(frame).decode(), output.getvalue())

    def test_bootstrap_fences_stale_challenge_on_new_running_image(self):
        """GS117-USB-BOOT-002: reject stale boot/image/port/deadline evidence."""
        old_nonce, nonce = b"o" * 32, b"n" * 32
        public = "04" + "ab" * 64
        def challenge(value):
            return (f"GS40T/1 CHALLENGE nonce={value.hex()} public_key={public} "
                    "max_envelope=24576\n")
        boot = ("ESP-ROM:esp32s3-20210327\n"
                "I (692) boot: SPI Flash size: 16MB\n"
                "I (692) esp_psram: Found 8MB PSRAM device\n"
                "I (693) boot: Loaded app from partition at offset 0x20000\n"
                "I (1493) app_init: App version: d0e5f84\n"
                "I (1493) app_init: ELF file SHA256: b576c52f5...\n")
        expected = {"app_offset": "0x20000", "app_version": "d0e5f84",
                    "elf_sha256_prefix": "b576c52f5"}
        envelope = b"G40E\x01" + nonce + b"encrypted".ljust(480, b"x")
        frame = len(envelope).to_bytes(4, "big") + envelope
        response = json.dumps({"encrypted_envelope_b64": base64.b64encode(frame).decode()}) + "\n"

        class Stream:
            def __init__(self, text):
                self.data, self.writes = bytearray(text.encode()), []
            @property
            def in_waiting(self): return len(self.data)
            def read(self, count):
                value = bytes(self.data[:count]); del self.data[:count]
                return value
            def write(self, value): self.writes.append(value); return len(value)
            def flush(self): pass

        stream = Stream(challenge(old_nonce) + boot + challenge(nonce))
        evidence, output = {}, io.StringIO()
        tc_serial.bootstrap_config(stream, require_boot=True, expected_boot=expected,
                                   incoming=io.StringIO(response), outgoing=output,
                                   evidence=evidence)
        self.assertEqual(json.loads(output.getvalue())["nonce"], nonce.hex())
        self.assertEqual(stream.writes, [frame])
        self.assertTrue(evidence["post_reset_boot_verified"])
        self.assertEqual(evidence["ignored_pre_boot_challenges"], 1)
        self.assertEqual(evidence["boot"], expected)
        self.assertEqual(evidence["s3_memory_capacity"]["status"], "PASS")
        self.assertEqual(evidence["s3_memory_capacity"]["flash_size_bytes"], 16 * 1024 * 1024)
        self.assertEqual(evidence["s3_memory_capacity"]["psram_size_bytes"], 8 * 1024 * 1024)

        stream = Stream(boot + challenge(nonce))
        with self.assertRaisesRegex(ValueError, "USB_INTERFACE_MISMATCH"):
            tc_serial.bootstrap_config(stream, require_boot=True, expected_boot=expected,
                incoming=io.StringIO(response), outgoing=io.StringIO(), identity_check=lambda: False)
        self.assertEqual(stream.writes, [])

        for observed, error in ((challenge(old_nonce), "CHALLENGE_NOT_OBSERVED"),
                                (boot.replace("d0e5f84", "wrong") + challenge(nonce),
                                 "RUNNING_IMAGE_MISMATCH")):
            stream = Stream(observed)
            ticks = iter(range(100))
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                tc_serial.bootstrap_config(stream, require_boot=True, expected_boot=expected,
                    incoming=io.StringIO(response), outgoing=io.StringIO(), clock=lambda: next(ticks))
            self.assertEqual(stream.writes, [])

        stream = Stream(boot + challenge(nonce))
        class RestartResponse(io.StringIO):
            def readline(self, size):
                stream.data.extend(b"ESP-ROM:esp32s3-20210327\n")
                return super().readline(size)
        with self.assertRaisesRegex(ValueError, "TARGET_RESTARTED_OR_EXPIRED"):
            tc_serial.bootstrap_config(stream, require_boot=True, expected_boot=expected,
                incoming=RestartResponse(response), outgoing=io.StringIO())
        self.assertEqual(stream.writes, [])

        stream = Stream(boot + challenge(nonce))
        ticks = iter((0, 0, 0, 0, 26))
        with self.assertRaisesRegex(ValueError, "EXCEEDED_TARGET_BUDGET"):
            tc_serial.bootstrap_config(stream, require_boot=True, expected_boot=expected,
                incoming=io.StringIO(response), outgoing=io.StringIO(), clock=lambda: next(ticks))
        self.assertEqual(stream.writes, [])

    def test_exact_fixture_commissioning_keeps_qr_proof_private_and_requires_session(self):
        public, secret = "04" + "ab" * 64, "cd" * 32
        idle = ("HIL_STATE role=c3 retained=0 in_flight=0 sensing_live=0 runtime_live=0 "
                "pending_inject=0 power_mode=HIL_AWAKE_TEST_ONLY hil_build=0 hil_control=1 physical_wake=0")
        class Stream:
            def __init__(self, role, reject=False):
                self.role, self.reject = role, reject
                self.data, self.writes = bytearray(), []
            @property
            def in_waiting(self): return len(self.data)
            def read(self, count):
                out = bytes(self.data[:count]); del self.data[:count]; return out
            def flush(self): pass
            def write(self, value):
                self.writes.append(value)
                if value == b"GET_TEST_QR\n":
                    self.data.extend((f"HIL_TEST_QR profile=TEST_ONLY device_id=c3-146393c5d158 public_key={public}\n"
                                      f"HIL_TEST_CODE profile=TEST_ONLY device_id=c3-146393c5d158 installer_code={secret}\n").encode())
                elif value.startswith(b"COMMISSION_EXPECTED_NODE "):
                    self.data.extend(b"HIL_FIXTURE_OK request=exact_node\n" if not self.reject else b"HIL_FIXTURE_ERROR reason=rejected\n")
                elif value == b"FRESH_COMMISSION_GS117_TEST_FIXTURE\n":
                    self.data.extend(b"GS117_TEST_ONLY_FRESH_COMMISSIONING rejected reason=association_backup_failed\n"
                                     if self.reject else
                                     b"GS117_TEST_ONLY_FRESH_COMMISSIONING started prior_association_backed_up=1\n")
                elif value == b"GET_STATE\n":
                    self.data.extend(b"HIL_STATE role=c3 runtime_live=27 sensing_live=42\n")
                elif value == b"FIXTURE_STATUS\n":
                    self.data.extend(b"HIL_FIXTURE_STATUS state=authenticated_rejoin\n")
                return len(value)
        for reject in (False, True):
            c3, s3 = Stream("c3"), Stream("s3", reject)
            c3_lines, s3_lines = [idle], ["HIL_FIXTURE_STATUS state=idle commissioning_window_ms=120000"]
            ticks = [0.0]
            def clock(): ticks[0] += 0.05; return ticks[0]
            if reject:
                with self.assertRaisesRegex(ValueError, "REQUEST_NOT_ACCEPTED"):
                    tc_serial.commission_fixture(c3, s3, c3_lines, s3_lines, clock=clock, sleep=lambda _: None)
                self.assertNotIn(b"FRESH_COMMISSION_GS117_TEST_FIXTURE\n", c3.writes)
            else:
                result = tc_serial.commission_fixture(c3, s3, c3_lines, s3_lines, clock=clock, sleep=lambda _: None)
                self.assertEqual(result["status"], "PASS")
                self.assertEqual(result["node_public_key"], public)
                self.assertEqual(result["liveness"], {"runtime": 27, "sensing": 42})
                self.assertNotIn(secret, json.dumps([result, c3_lines, s3_lines]))
        c3, s3 = Stream("c3"), Stream("s3")
        with self.assertRaisesRegex(ValueError, "NOT_IDLE_OR_EMPTY"):
            tc_serial.commission_fixture(c3, s3, [idle.replace("retained=0", "retained=1")], [])
        self.assertEqual(c3.writes + s3.writes, [])
        c3, s3 = Stream("c3"), Stream("s3")
        with self.assertRaisesRegex(ValueError, "IDENTITY_KEY_CHANGED"):
            tc_serial.commission_fixture(c3, s3, [idle],
                ["HIL_FIXTURE_STATUS state=timed_out commissioning_window_ms=120000"],
                clock=clock, sleep=lambda _: None, expected_public_key="04" + "ef" * 64)
        self.assertEqual(s3.writes, [])
        c3, s3 = Stream("c3", True), Stream("s3")
        result = tc_serial.commission_fixture(c3, s3, [idle],
            ["HIL_FIXTURE_STATUS state=timed_out commissioning_window_ms=120000"],
            clock=clock, sleep=lambda _: None, expected_public_key=public)
        self.assertEqual(result["status"], "FAIL")
        self.assertNotIn(b"INJECT_MOTION\n", c3.writes)

    def test_bootstrap_missing_target_challenge_is_bounded_and_sends_nothing(self):
        class EmptyStream:
            in_waiting = 0

            def read(self, count):
                return b""

            def write(self, data):
                raise AssertionError("no frame may be sent without a target challenge")

        ticks = [0]

        def clock():
            ticks[0] += 1
            return ticks[0]

        with self.assertRaisesRegex(ValueError, "TARGET_CHALLENGE_NOT_OBSERVED"):
            tc_serial.bootstrap_config(EmptyStream(), clock=clock)

    def test_observer_refuses_wrong_physical_ports_before_open(self):
        opened = []
        config = {
            "c3": {"port": "COM4", "serial_number": "wrong",
                   "usb_hwid": "wrong"},
            "s3": {"port": "COM10", "serial_number": "E0:72:A1:D3:8D:34",
                   "usb_hwid": "s3"},
        }
        with self.assertRaisesRegex(ValueError, "USB_INTERFACE_MISMATCH"):
            tc_serial.observe(config, serial_factory=lambda: opened.append(True),
                              port_finder=lambda: [])
        self.assertEqual(opened, [])

    def test_duplicate_or_missing_s3_does_not_reach_backend(self):
        c3 = ["HIL_OK command=INJECT_MOTION", "PIR -> NodeRuntime session=12 seq=3"]
        report = self.report()
        self.execute(report, {"c3": c3, "s3": []}, baseline={"keys": [[12, 3]], "count": 1})
        self.assertEqual(report["stages"]["node_event_key"]["status"], "FAIL")
        report = self.report()
        self.execute(report, {"c3": c3, "s3": []})
        self.assertEqual(report["stages"]["s3_admission"]["status"], "FAIL")
        self.assertEqual(report["stages"]["backend_commit"]["status"], "NOT_VERIFIED")

    def test_wrong_or_missing_c3_power_mode_blocks_injection_result(self):
        c3 = ["HIL_OK command=INJECT_MOTION", "PIR -> NodeRuntime session=12 seq=3"]
        for mode in (None, "power_mode=SLEEP_ENABLED hil_build=0 hil_control=1 physical_wake=0"):
            with self.subTest(mode=mode):
                report = self.report()
                serial_lines = {"c3": list(c3), "s3": []}
                if mode:
                    serial_lines["c3"].insert(0, "HIL_STATE role=c3 " + mode)
                self.execute(report, serial_lines, mode_state=False)
                self.assertEqual(report["stages"]["c3_injection"]["status"], "BLOCKED")
                self.assertEqual(report["c3_power_mode"], "NOT_VERIFIED")

    def test_different_installed_apk_backend_blocks_before_serial(self):
        report = self.report()
        hardware = self.execute(report, {}, home_origin="https://wrong.local")
        hardware.assert_not_called()
        self.assertEqual(report["stages"]["environment"]["status"], "BLOCKED")

    def test_backend_unavailable_blocks_before_serial(self):
        report = self.report()
        controller = tc.Controller()
        controller.lock.acquire()
        with (patch.object(controller, "readiness", return_value={
                  "backend": {"POSTGRES_READY": "FAIL", "CAREGIVER_HTTPS_READY": "PASS"},
                  "caregiver_home": {"caregiver_home_ready": False}}),
              patch.object(tc, "powershell") as hardware,
              patch.object(controller, "save")):
            controller.execute(report)
        hardware.assert_not_called()
        self.assertEqual(report["stages"]["environment"]["status"], "BLOCKED")

    def test_missing_s3_interface_blocks_before_injection(self):
        report = self.report()
        self.execute(report, {}, ports_override=[{"port": "COM10", "usb_hwid": "c3", "serial_number": "c3s"}])
        self.assertEqual(report["stages"]["s3_identity"]["status"], "BLOCKED")
        self.assertEqual(report["stages"]["c3_injection"]["status"], "NOT_VERIFIED")

    def test_revoked_hub_or_node_enrollment_blocks_before_injection(self):
        report = self.report()
        with self.assertRaises(hil_auth.AuthorizationSafetyFailure):
            self.execute(report, {}, baseline={"keys": [], "count": 0,
                            "authority_ready": False, "enrollment_generation": None})

    def test_wrong_caregiver_room_fails_after_exact_backend_commit(self):
        c3 = ["HIL_OK command=INJECT_MOTION", "PIR -> NodeRuntime session=12 seq=3",
              "Application ACK session=12 seq=3 class=0 retired=1"]
        s3 = ["Authenticated event logical=bedroom session=12 seq=3 sensor=PIR event=MOTION event_id=p15:test-c3-bedroomn7:bedrooms12q3 room=bedroom ack=0 send=ESP_OK"]
        report = self.report()
        self.execute(report, {"c3": c3, "s3": s3}, outcome={"durable_count": 1,
                     "caregiver_count": 1, "event_kind": "MOTION", "event_location": "kitchen",
                     "event_id": "evt-1", "caregiver_event_id": tc.event_key_text("test-c3-bedroom", 12, 3),
                     "committing_hub_id": "test-hub-a", "ownership_epoch": 1,
                     "node_enrollment_generation": 1})
        self.assertEqual(report["stages"]["backend_commit"]["status"], "PASS")
        self.assertEqual(report["stages"]["caregiver_api"]["status"], "FAIL")

    def test_wrong_hub_provenance_cannot_claim_cloudsync_delivery(self):
        c3 = ["HIL_OK command=INJECT_MOTION", "PIR -> NodeRuntime session=12 seq=3",
              "Application ACK session=12 seq=3 class=0 retired=1"]
        s3 = ["Authenticated event logical=bedroom session=12 seq=3 sensor=PIR event=MOTION event_id=p15:test-c3-bedroomn7:bedrooms12q3 room=bedroom ack=0 send=ESP_OK"]
        report = self.report()
        with self.assertRaises(hil_auth.AuthorizationSafetyFailure):
            self.execute(report, {"c3": c3, "s3": s3}, outcome={"durable_count": 1,
                     "caregiver_count": 1, "event_kind": "MOTION", "event_location": "bedroom",
                     "event_id": "evt-1", "caregiver_event_id": tc.event_key_text("test-c3-bedroom", 12, 3),
                     "committing_hub_id": "test-hub-other", "ownership_epoch": 1,
                     "node_enrollment_generation": 1})

    def test_caregiver_projection_with_other_event_id_fails(self):
        c3 = ["HIL_OK command=INJECT_MOTION", "PIR -> NodeRuntime session=12 seq=3",
              "Application ACK session=12 seq=3 class=0 retired=1"]
        s3 = ["Authenticated event logical=bedroom session=12 seq=3 sensor=PIR event=MOTION event_id=p15:test-c3-bedroomn7:bedrooms12q3 room=bedroom ack=0 send=ESP_OK"]
        report = self.report()
        self.execute(report, {"c3": c3, "s3": s3}, outcome={"durable_count": 1,
                     "caregiver_count": 1, "event_kind": "MOTION", "event_location": "bedroom",
                     "event_id": "evt-1", "caregiver_event_id": "old-event",
                     "committing_hub_id": "test-hub-a", "ownership_epoch": 1,
                     "node_enrollment_generation": 1})
        self.assertEqual(report["stages"]["caregiver_api"]["status"], "FAIL")

    def test_loopback_console_rejects_cross_origin_and_missing_csrf(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), tc.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_address[1]}/api/run"
        try:
            with patch.object(tc.CONTROLLER, "start") as start:
                for origin, token in (("http://evil.example", tc.CONTROLLER.csrf),
                                      (tc.ORIGIN, "missing")):
                    request = urllib.request.Request(
                        url, data=b"{}", method="POST",
                        headers={"Host": "127.0.0.1:18791", "Origin": origin,
                                 "X-CSRF-Token": token, "Content-Type": "application/json"})
                    with self.assertRaises(urllib.error.HTTPError) as rejected:
                        urllib.request.urlopen(request, timeout=3)
                    self.assertEqual(rejected.exception.code, 403)
                    rejected.exception.close()
                start.assert_not_called()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_loopback_status_and_private_apk_evidence_reject_cross_site_gets(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), tc.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_address[1]}/api/status"
        try:
            with patch.object(tc.CONTROLLER, "readiness", return_value={}):
                for headers in ({"Origin": "http://evil.example"},
                                {"Sec-Fetch-Site": "cross-site"},
                                {"Origin": "http://127.0.0.1:18791",
                                 "Sec-Fetch-Site": "same-site"}):
                    request = urllib.request.Request(
                        url, headers={"Host": "127.0.0.1:18791", **headers})
                    with self.assertRaises(urllib.error.HTTPError) as rejected:
                        urllib.request.urlopen(request, timeout=3)
                    self.assertEqual(rejected.exception.code, 403)
                    rejected.exception.close()
                request = urllib.request.Request(
                    url, headers={"Host": "127.0.0.1:18791", "Origin": tc.ORIGIN,
                                  "Sec-Fetch-Site": "same-origin"})
                with urllib.request.urlopen(request, timeout=3) as response:
                    self.assertEqual(response.status, 200)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_console_reports_single_run_lock_for_repeatable_retry(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), tc.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_address[1]}/api/status"
        try:
            with patch.object(tc.CONTROLLER, "readiness", return_value={"backend": {}, "caregiver_home": {}, "physical_boards": {}}):
                for locked, expected in ((True, True), (False, False)):
                    if locked:
                        tc.CONTROLLER.lock.acquire()
                    try:
                        request = urllib.request.Request(url, headers={"Host": "127.0.0.1:18791"})
                        with urllib.request.urlopen(request, timeout=3) as response:
                            self.assertEqual(json.load(response)["running"], expected)
                    finally:
                        if locked:
                            tc.CONTROLLER.lock.release()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def _write_read_only_observation_approval(self, path):
        approval = {
            "schema_version": 1,
            "test_id": "TC-001",
            "profile": "GS179_TEST_ONLY",
            "approval_ref": "owner-chat-approval-2026-10-26-read-only-observe",
            "approval_scope": (
                "C3 GET_STATE and S3 FIXTURE_STATUS only; one serial-open observation; "
                "reset risk accepted"),
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "serial_open_reset_risk_accepted": True,
            "reset_safe_uart_verified": False,
            "motion_injection_authorized": False,
            "c3": {"port": "COM4", "serial_number": "14:63:93:C5:D1:58"},
            "s3": {"port": "COM10", "serial_number": "E0:72:A1:D3:8D:34"},
        }
        path.write_text(json.dumps(approval))
        path.chmod(0o600)
        return approval

    def test_read_only_observation_requires_owner_only_non_reset_safe_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = Path(directory) / "approval.json"
            approval = self._write_read_only_observation_approval(receipt)
            controller = tc.Controller()
            for field, value in (("reset_safe_uart_verified", True),
                                 ("motion_injection_authorized", True)):
                approval[field] = value
                receipt.write_text(json.dumps(approval)); receipt.chmod(0o600)
                with patch.object(tc, "powershell") as hardware:
                    with self.assertRaisesRegex(ValueError, "scope_or_identity_mismatch"):
                        controller.observe_once(approval_path=receipt)
                    hardware.assert_not_called()
                self.assertFalse(controller.lock.locked())
                approval[field] = not value

            approval["c3"]["serial_number"] = "14:63:93:C5:D1:59"
            receipt.write_text(json.dumps(approval)); receipt.chmod(0o600)
            with patch.object(tc, "powershell") as hardware:
                with self.assertRaisesRegex(ValueError, "scope_or_identity_mismatch"):
                    controller.observe_once(approval_path=receipt)
                hardware.assert_not_called()
            self.assertFalse(controller.lock.locked())

            receipt.write_text(json.dumps(approval)); receipt.chmod(0o644)
            with patch.object(tc, "powershell") as hardware:
                with self.assertRaisesRegex(ValueError, "owner_only_regular_file"):
                    controller.observe_once(approval_path=receipt)
                hardware.assert_not_called()
            self.assertFalse(controller.lock.locked())

    def test_read_only_observation_identity_mismatch_does_not_consume_or_open_serial(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = Path(directory) / "approval.json"
            self._write_read_only_observation_approval(receipt)
            visible = [
                {"port": "COM4", "serial_number": "14:63:93:C5:D1:58",
                 "usb_hwid": "USB VID:PID=303A:1001 SER=14:63:93:C5:D1:58 LOCATION=1-1"},
                {"port": "COM10", "serial_number": "wrong",
                 "usb_hwid": "USB VID:PID=303A:1001 SER=E0:72:A1:D3:8D:34 LOCATION=1-2"},
            ]
            controller = tc.Controller()
            with patch.object(tc, "powershell", return_value=visible) as hardware:
                with self.assertRaisesRegex(ValueError, "VERIFIED_USB_INTERFACE_MISMATCH"):
                    controller.observe_once(approval_path=receipt)
            self.assertEqual([call.args[0] for call in hardware.call_args_list], ["List"])
            self.assertTrue(receipt.exists())
            self.assertFalse(controller.lock.locked())

    def test_one_use_observation_queries_exact_pair_once_and_never_injects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt = root / "approval.json"
            self._write_read_only_observation_approval(receipt)
            evidence = root / "observation.json"
            visible = [
                {"port": "COM4", "serial_number": "14:63:93:C5:D1:58",
                 "usb_hwid": "USB VID:PID=303A:1001 SER=14:63:93:C5:D1:58 LOCATION=1-1"},
                {"port": "COM10", "serial_number": "E0:72:A1:D3:8D:34",
                 "usb_hwid": "USB VID:PID=303A:1001 SER=E0:72:A1:D3:8D:34 LOCATION=1-2"},
            ]
            serial_result = {
                "c3": ["I (1) HIL_STATE role=c3 power_mode=HIL_AWAKE_TEST_ONLY "
                       "hil_build=0 hil_control=1 physical_wake=0 runtime_live=0 sensing_live=0",
                       "HIL_OK command=GET_STATE"],
                "s3": ["HIL_FIXTURE_STATUS state=authenticated_rejoin"],
            }
            controller = tc.Controller()
            with patch.object(tc, "powershell", side_effect=[visible, serial_result]) as hardware:
                report = controller.observe_once(approval_path=receipt, evidence_path=evidence)
            self.assertEqual(report["overall"], "PASS")
            self.assertEqual(report["tc001_acceptance"], "NOT_RUN")
            self.assertEqual(report["stages"]["c3_get_state"], "PASS")
            self.assertEqual(report["stages"]["s3_fixture_status"], "PASS")
            self.assertEqual(report["stages"]["cloudsync"], "NOT_VERIFIED")
            self.assertFalse(report["reset_safe_uart_verified"])
            self.assertTrue(report["serial_open_reset_risk_accepted"])
            self.assertEqual(report["motion_injection"], "NOT_AUTHORIZED")
            self.assertTrue(report["approval_receipt_consumed"])
            self.assertEqual(evidence.stat().st_mode & 0o777, 0o600)
            self.assertEqual([call.args[0] for call in hardware.call_args_list], ["List", "Observe"])
            observe_payload = hardware.call_args_list[1].args[1]
            self.assertEqual(observe_payload["c3"]["serial_number"], "14:63:93:C5:D1:58")
            self.assertEqual(observe_payload["s3"]["serial_number"], "E0:72:A1:D3:8D:34")
            consumed = list(root.glob("approval.consumed.*.json"))
            self.assertEqual(len(consumed), 1)
            with self.assertRaisesRegex(ValueError, "approval_missing_or_consumed"):
                controller.observe_once(approval_path=receipt, evidence_path=evidence)
            self.assertFalse(controller.lock.locked())
            self.assertEqual(len(hardware.call_args_list), 2)


if __name__ == "__main__":
    unittest.main()
