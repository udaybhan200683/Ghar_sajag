#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'/'sim'))
sys.path.insert(0,str(ROOT/'tools'/'validation'))
from local_lab import Lab
from functional_scenarios import _execute_step, _assert_one

lab=Lab(); results=[]
try:
    for path in sorted((ROOT/'tests'/'fixtures'/'sensor_streams').glob('*.json')):
        case=json.loads(path.read_text())
        failures=[]; vars={}; lab.reset(test_fixture=True)
        for i,step in enumerate(case.get('steps',[]),1):
            ok,detail=_execute_step(lab,step,vars)
            if not ok: failures.append(f'step {i}: {detail}'); break
        state=lab.snapshot()
        if not failures:
            for i,a in enumerate(case.get('assertions',[]),1):
                ok,detail=_assert_one(state,a)
                if not ok: failures.append(f'assertion {i}: {detail}')
        results.append({'id':case['id'],'file':path.name,'title':case['title'],'passed':not failures,'failures':failures})
finally:
    lab.close()
report={'release':'1.5.4','status':'PASS' if all(r['passed'] for r in results) else 'FAIL','passed':sum(r['passed'] for r in results),'total':len(results),'streams':results}
(ROOT/'logs').mkdir(exist_ok=True)
(ROOT/'logs'/'dummy_sensor_stream_report.json').write_text(json.dumps(report,indent=2)+'\n')
print(f"{report['status']} dummy sensor streams {report['passed']}/{report['total']}")
for r in results: print(('PASS' if r['passed'] else 'FAIL'),r['id'],(' :: '+'; '.join(r['failures'])) if r['failures'] else '')
raise SystemExit(0 if report['status']=='PASS' else 1)
