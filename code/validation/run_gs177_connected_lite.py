#!/usr/bin/env python3
"""Permanent GS-177 connected Lite host gate; no cloud or physical claim."""
from pathlib import Path
import os
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def run(command):
    result=subprocess.run(command,cwd=ROOT,env=os.environ.copy(),text=True,
                          stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    print(result.stdout,end='',flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)
    return result.stdout

api_output=run([sys.executable,'-m','unittest','discover','-s',
                'parivar_saathi_android_app/server/tests','-p','test_connected_lite.py','-v'])
match=re.search(r'^Ran (\d+) tests? in ',api_output,re.MULTILINE)
if not match:
    raise SystemExit('GS177 connected Lite API test count unavailable')
api_test_count=int(match.group(1))
for case_id in (
    'GS177_API_LAN_ORIGIN_001_ip_pairing_is_an_explicit_test_only_origin_alias',
    'GS177_API_LAN_ORIGIN_002_alias_configuration_is_rejected_outside_lan_test_only_mode',
):
    if not re.search(rf'^test_{re.escape(case_id)} .*ok$', api_output, re.MULTILINE):
        raise SystemExit(f'GS177 connected Lite missing required LAN origin case: {case_id}')
print('CASE GS177-API-LAN-ORIGIN-001 PASS')
print('CASE GS177-API-LAN-ORIGIN-002 PASS')
runtime_output=run(['node','--test','tests/js/caregiver_runtime.test.mjs'])
runtime_match=re.search(r'^# tests (\d+)$',runtime_output,re.MULTILINE)
runtime_test_count=int(runtime_match.group(1)) if runtime_match else 0
if not runtime_test_count:
    raise SystemExit('GS177 caregiver runtime test count unavailable')
run(['make','lab-build'])
sys.path.insert(0,str(ROOT/'parivar_saathi_android_app/server'))
from connected_lite import run_scenario
for scenario in ('motion-room1-visible','door-open-close-order','morning-missing-covered'):
    result=run_scenario(scenario)
    if result['status']!='PASS' or not result['checks'] or result['hardware_evidence']!='NOT_RUN':
        raise SystemExit(f'GS177 SCENARIO FAIL {scenario}')
    print(f'GS177 SCENARIO PASS {scenario} timeline={len(result["state"]["timeline"])}')
print(f'GS177 CONNECTED LITE PASS tests={api_test_count} scenarios=3 runtime={runtime_test_count} physical=NOT_RUN')
