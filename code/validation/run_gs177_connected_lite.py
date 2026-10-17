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
run(['node','--test','tests/js/caregiver_runtime.test.mjs'])
run(['make','lab-build'])
sys.path.insert(0,str(ROOT/'parivar_saathi_android_app/server'))
from connected_lite import run_scenario
for scenario in ('motion-room1-visible','door-open-close-order','morning-missing-covered'):
    result=run_scenario(scenario)
    if result['status']!='PASS' or not result['checks'] or result['hardware_evidence']!='NOT_RUN':
        raise SystemExit(f'GS177 SCENARIO FAIL {scenario}')
    print(f'GS177 SCENARIO PASS {scenario} timeline={len(result["state"]["timeline"])}')
print(f'GS177 CONNECTED LITE PASS tests={api_test_count} scenarios=3 runtime=6 physical=NOT_RUN')
