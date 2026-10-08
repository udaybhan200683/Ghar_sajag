#!/usr/bin/env python3
"""Reproducible bounded SDK capacity/schedule/fault runner; deletes its own images."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
p = argparse.ArgumentParser()
p.add_argument('--cases', type=Path, required=True)
p.add_argument('--suite', choices=('capacity','schedule','fault'), required=True)
p.add_argument('--binary', type=Path, default=HERE/'build/gs_nvs_runtime_probe.elf')
a = p.parse_args()
rows = json.loads(a.cases.read_text())
selected = []
for r in rows:
    if r['profile'] == 'comparison' or r['profile'].startswith('reserve_'): continue
    if a.suite == 'capacity':
        if (r['scenario']=='NORMAL' and r['profile'] in ('ordinary','mixed','door_user','node_loss','simultaneous')) or (
                r['scenario']=='HIGH' and r['profile'] in ('ordinary','mixed','simultaneous')) or (
                r['scenario']=='STRESS' and r['profile']=='ordinary'):
            selected.append(r)
    elif a.suite == 'schedule':
        if r['profile']=='ordinary' and r['worst']:selected.append(r)
    elif r['scenario']=='NORMAL' and ((r['profile']=='ordinary' and r['worst']) or (
            r['profile']=='mixed' and not r['worst'])): selected.append(r)
print('SDK_BINARY_SHA256='+hashlib.sha256(a.binary.read_bytes()).hexdigest(),flush=True)
print('SDK_SOURCE_COMMIT=76f5dedd9950a3012fee8fb7d5586df21fc67802',flush=True)
counts = {'runs':0,'passes':0,'capacity_stops':0}
with tempfile.TemporaryDirectory(prefix='gs-72h-nvs-') as directory:
    for row in selected:
        f = Path(directory)/'fixture.txt'
        f.write_text(' '.join(map(str,(row['history_segments'],row['cow_segments'],2*row['reserve_events']//32,
                                      row['inputs'])))+'\n' +
                     '\n'.join(map(str,row['object_sizes']))+'\n')
        page_cases = (32,48,64) if a.suite=='capacity' else (64,)
        cuts = (0,1,8,16,31,32,63,64,127,512,1023,1024,1071,1072,1073,1080,1081,
                1536,2047,2048,2560,2600,2687,2688,2750,3000,4000,4096,6000,100000) if a.suite=='fault' else (None,)
        for pages in page_cases:
            for cut in cuts:
                env = os.environ.copy();env['GS_DIAG_PAGES']=str(pages)
                if a.suite=='capacity':env['GS_PEAK']='1'
                else:env.pop('GS_PEAK',None)
                cmd = [str(a.binary.resolve()),'offline',str(f)]
                if a.suite=='schedule':cmd.append('schedule')
                if a.suite=='fault':cmd+=['fault',str(cut)]
                print('CASE='+json.dumps({k:row[k] for k in ('scenario','profile','worst','history_segments','cow_segments','protected_peak_bytes')}),flush=True)
                print(f'COMMAND=GS_DIAG_PAGES={pages} '+' '.join(cmd)+'\nFIXTURE_SHA256='+hashlib.sha256(f.read_bytes()).hexdigest(),flush=True)
                r = subprocess.run(cmd,env=env,text=True,capture_output=True)
                print(r.stdout,end='');print(r.stderr,end='');print('EXIT='+str(r.returncode),flush=True)
                # SDK creates a fresh private file per process; never delete an
                # unrelated file or a still-running probe image.
                for path in re.findall(r'EMULATOR_IMAGE=(/tmp/idf-partition-[^\s]+)',r.stderr):Path(path).unlink(missing_ok=True)
                counts['runs']+=1
                if r.returncode==0:counts['passes']+=1
                else:
                    assert r.returncode in (2,3,4) and ('OFFLINE_STOP' in r.stdout or 'OFFLINE_SCHEDULE_STOP' in r.stdout)
                    counts['capacity_stops']+=1
                if a.suite=='fault':assert r.returncode==0
print('RUNNER_RESULT='+json.dumps(counts),flush=True)
print('BOUNDARY=SDK NVS EMULATED; dummy bodies/selectors; TARGET HARDWARE UNPROVEN',flush=True)
