#!/usr/bin/env python3
"""Check GS-130 traceability consistency. This is not semantic code coverage.

Assertions and category assessments still require engineering review. Registration,
matching source text, and PASS receipts cannot prove physical qualification.
"""
import csv
import json
import re
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from validation import component_gate as gate
REPO=ROOT.parent
DOC=REPO/'docs/validation'
PREFIXES=('firmware','backend','tests/support/host','tools/sim','frontend','parivar_saathi_android_app')
SUFFIXES={'.cpp','.hpp','.c','.h','.py','.js','.mjs','.sql','.html','.kt'}
REQUIRED=set('FEATURE_ID JIRA_KEY FEATURE_NAME COMPONENT MODULE REQUIREMENT_ID REQUIREMENT_OR_INVARIANT IMPLEMENTATION_STATUS TEST_CASE_ID TEST_CASE_NAME TEST_TYPE TEST_SOURCE EXACT_TEST_EXECUTION_COMMAND POSITIVE_COVERAGE NEGATIVE_COVERAGE BOUNDARY_COVERAGE RECOVERY_COVERAGE NODE_GATE HUB_GATE CONTRACT_GATE BACKEND_GATE PWA_GATE VALIDATION_FAST_REGISTERED RELEASE_GATE_REGISTERED EXTENDED_TEST_REQUIRED PHYSICAL_REQUIRED PHYSICAL_TEST_ID PHYSICAL_EVIDENCE_STATUS SOURCE_HEAD BUILD_PROFILE LATEST_EXECUTED_HEAD LATEST_TEST_RESULT COVERAGE_CLASS COVERAGE_GAP GAP_REASON REMAINING_OWNER PRIORITY STAGE_IDS ASSERTION_ANCHOR REQUIREMENT_SOURCE'.split())
STATUSES={'IMPLEMENTED','PARTIALLY_IMPLEMENTED','NOT_IMPLEMENTED','DEFERRED','ON_HOLD','HISTORICAL_ONLY'}
COVERAGE_STATUSES={'COVERED','PARTIAL','MISSING_PRODUCT_FEATURE',
    'MISSING_PRODUCT_FEATURE_TARGET_VERTICAL_BRIDGE','PRODUCT_GAP','TEST_INFRA_GAP',
    'HIL_ONLY_PHYSICAL','PARTIAL_BUT_SUFFICIENT'}

def source_modules(root=ROOT):
    names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','--',*PREFIXES],cwd=root,text=True).splitlines()
    return {n for n in names if Path(n).suffix in SUFFIXES and '/managed_components/' not in n}

def read_csv(path):
    with path.open(newline='') as stream:return list(csv.DictReader(stream))

def load():
    return (read_csv(DOC/'MASTER_TRACEABILITY.csv'),read_csv(DOC/'SOURCE_FEATURE_INVENTORY.csv'),
            read_csv(DOC/'PHYSICAL_QUALIFICATION.csv'),json.loads((ROOT/'validation/suites.json').read_text()))

def known_requirement_ids(repo=REPO):
    index=(repo/'docs/product/CANONICAL_REQUIREMENTS_INDEX.md').read_text()
    current='## Current requirement register'
    scoped='## Dashboard-branch scoped approvals — not canonical requirement-register entries'
    if current not in index:return set()
    canonical_rows=index.split(current,1)[1].split('## Open decisions',1)[0]
    scoped_rows=''
    if scoped in index:
        scoped_rows=index.split(scoped,1)[1].split(current,1)[0]
    pattern=r'^\|\s*(GS-[A-Z0-9-]+)\s*\|'
    return set(re.findall(pattern,canonical_rows+'\n'+scoped_rows,re.M))

def board_registration_errors(source,stage,rows):
    cases=set(re.findall(r'\{"(BOARD-TC-[0-9-]+)"',source))
    markers={f'^{case} PASS$' for case in cases}
    required=set(stage.get('required_success',[]))
    mapped={r['TEST_CASE_ID'] for r in rows if r.get('STAGE_IDS')=='board-stack-e2e'}
    if not cases or markers!=required or cases!=mapped:
        return ['board case/mandatory-marker/matrix registration mismatch']
    return []

def errors(rows,ledger,physical,registry,modules=None,root=ROOT,repo=REPO):
    failures=[]
    if not rows:return ['zero feature rows']
    stages={s['id']:s for s in registry['stages']}
    pwa_stage_ids={s['id'] for s in gate.select(registry,'pwa')}
    features={r['FEATURE_ID']:r for r in rows}
    board=stages.get('board-stack-e2e')
    source=root/'tests/cpp/board_stack_e2e_validation.cpp'
    if board and source.is_file():
        failures.extend(board_registration_errors(source.read_text(),board,rows))
    if len(features)!=len(rows):failures.append('duplicate feature ID')
    physical_ids={r['TEST_ID'] for r in physical}
    known_requirements=known_requirement_ids(repo)
    for row in rows:
        fid=row['FEATURE_ID']
        if not REQUIRED<=set(row):failures.append(fid+': missing columns');continue
        if row.get('status') not in COVERAGE_STATUSES:failures.append(fid+': unknown coverage status')
        if row['IMPLEMENTATION_STATUS'] not in STATUSES:failures.append(fid+': unknown implementation status')
        if set(row['REQUIREMENT_ID'].split(';'))-known_requirements:failures.append(fid+': unknown requirement ID')
        if not row['REQUIREMENT_ID'] or not (repo/row['REQUIREMENT_SOURCE'].split('#')[0]).is_file():failures.append(fid+': missing requirement source')
        for name in ('POSITIVE_COVERAGE','NEGATIVE_COVERAGE','BOUNDARY_COVERAGE','RECOVERY_COVERAGE'):
            if not row[name]:failures.append(fid+': missing category assessment '+name)
        if row['IMPLEMENTATION_STATUS'] in {'IMPLEMENTED','PARTIALLY_IMPLEMENTED'} and not row['STAGE_IDS']:
            if not all(row[k] for k in ('COVERAGE_GAP','GAP_REASON','REMAINING_OWNER')):failures.append(fid+': implemented feature has no test or justified gap')
        if row['PHYSICAL_REQUIRED']=='YES':
            if row['PHYSICAL_TEST_ID'] not in physical_ids:failures.append(fid+': missing physical definition')
            if row['PHYSICAL_EVIDENCE_STATUS']=='PASS':failures.append(fid+': physical PASS requires separately reviewed image-matched evidence, not this host matrix')
        selected=[]
        for sid in filter(None,row['STAGE_IDS'].split(';')):
            if sid not in stages:failures.append(fid+': missing registered stage '+sid);continue
            selected.append(stages[sid])
        if selected:
            expected=';'.join(' '.join(s['command']) for s in selected)
            if row['EXACT_TEST_EXECUTION_COMMAND']!=expected:failures.append(fid+': command disagrees with registry')
            if not row['TEST_CASE_ID'] or row['TEST_CASE_ID']=='NONE' or not row['ASSERTION_ANCHOR']:failures.append(fid+': test ID/anchor missing')
            texts=[]
            for name in filter(None,row['TEST_SOURCE'].split(';')):
                p=root/name
                if not p.is_file():failures.append(fid+': missing test source '+name);continue
                texts.append(p.read_text())
                owned=any(name in s.get('inputs',[]) or
                    s['id']=='python' and name.startswith('tests/python/test_') and name.endswith('.py') or
                    s['id']=='javascript' and name.startswith('tests/js/') and name.endswith('.test.mjs') or
                    s['id']=='browser' and name.startswith('tests/playwright/') and name.endswith('.spec.ts') or
                    s['id']=='hil-tooling' and name.startswith('tests/python/test_hil_') for s in selected)
                if not owned:failures.append(fid+': test not owned/executed by mapped stage '+name)
            if not texts or row['ASSERTION_ANCHOR'] not in '\n'.join(texts):failures.append(fid+': test anchor does not resolve')
        for component,column in [('node','NODE_GATE'),('hub','HUB_GATE'),('contract','CONTRACT_GATE'),('backend','BACKEND_GATE'),('pwa','PWA_GATE')]:
            if component=='pwa':
                actual={s['id'] for s in selected if s['id'] in pwa_stage_ids and component in s['components']}
            else:
                actual={s['id'] for s in selected if component in s['components'] and s.get('fast',True)}
            mapped=set(row[column].split(';'))-{'NO',''}
            if actual!=mapped:failures.append(fid+': incorrect '+column)
        fast=bool(selected) and all(s.get('fast',True) for s in selected)
        release=bool(selected) and all(s.get('fast',True) or s.get('release',False) for s in selected)
        if row['VALIDATION_FAST_REGISTERED']!=('YES' if fast else 'NO'):failures.append(fid+': incorrect fast membership')
        if row['RELEASE_GATE_REGISTERED']!=('YES' if release else 'NO'):failures.append(fid+': incorrect release membership')
    inventory={r['MODULE']:r for r in ledger}
    if len(inventory)!=len(ledger):failures.append('duplicate source module')
    live=source_modules(root) if modules is None else modules
    if live!=set(inventory):failures.append('unaccounted/stale production modules: '+','.join(sorted(live^set(inventory))))
    for name,row in inventory.items():
        if not row['FEATURE_IDS'] or not row['REVIEW_STATUS'] or not row['GAP']:failures.append(name+': missing source assessment')
        for fid in row['FEATURE_IDS'].split(';'):
            if fid not in features:failures.append(name+': unresolved feature '+fid)
            elif name not in features[fid]['MODULE'].split(';'):failures.append(name+': missing reciprocal feature module')
    for row in physical:
        for key in ('TEST_ID','FEATURE_ID','JIRA_OWNER','HARDWARE_PROFILE','PRECONDITIONS','STEPS','EXPECTED_RESULT','FAILURE_CONDITIONS','REQUIRED_LOGS','SOURCE_HEAD_IMAGE_HASH','EXECUTION_STATUS'):
            if not row.get(key):failures.append(row.get('TEST_ID','physical')+': incomplete physical '+key)
        status=row.get('EXECUTION_STATUS')
        if status not in {'NOT_RUN','HISTORICAL_EVIDENCE_ONLY','PASS','PARTIAL','FAIL','BLOCKED'}:
            failures.append(row.get('TEST_ID','physical')+': unknown physical execution status')
        # The catalogue records real, separately executed physical evidence as
        # well as plans. A host traceability check may preserve a recorded
        # outcome, but must not promote a plan-only row into an execution.
        evidence=row.get('SOURCE_HEAD_IMAGE_HASH','')
        if status in {'PASS','PARTIAL','FAIL'} and 'REQUIRED_AT_EXECUTION' in evidence:
            failures.append(row['TEST_ID']+': physical execution status lacks source/image evidence')
    return failures

def main():
    rows,ledger,physical,registry=load();bad=errors(rows,ledger,physical,registry)
    if bad:print('\n'.join(bad));return 1
    print(f'GS130 TRACEABILITY PASS features={len(rows)} modules={len(ledger)} physical_cases={len(physical)}; consistency only, not semantic/physical PASS')
    return 0
if __name__=='__main__':sys.exit(main())
