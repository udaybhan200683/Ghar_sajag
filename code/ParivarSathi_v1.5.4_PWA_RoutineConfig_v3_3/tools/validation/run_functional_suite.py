#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'/'sim'))
sys.path.insert(0,str(ROOT/'tools'/'validation'))
from local_lab import Lab
from functional_scenarios import run_catalog

p=argparse.ArgumentParser()
p.add_argument('--catalog',default=str(ROOT/'tests'/'functional'/'scenario_catalog.json'))
p.add_argument('--category',action='append',default=[])
p.add_argument('--json-out',default=str(ROOT/'logs'/'functional_report.json'))
p.add_argument('--text-out',default=str(ROOT/'logs'/'functional_report.txt'))
a=p.parse_args()
lab=Lab()
try:
    report=run_catalog(lab,Path(a.catalog),set(a.category) or None)
finally:
    lab.close()
Path(a.json_out).parent.mkdir(parents=True,exist_ok=True)
Path(a.json_out).write_text(json.dumps(report,indent=2)+'\n')
lines=[f"Ghar Sajag functional suite {report['release']}",f"{report['status']} {report['passed']}/{report['total']}"]
for c in report['cases']:
    line=f"{'PASS' if c['passed'] else 'FAIL'} {c['id']}: {c['title']}"
    if c['failures']: line+=' :: '+'; '.join(c['failures'])
    lines.append(line)
Path(a.text_out).write_text('\n'.join(lines)+'\n')
print('\n'.join(lines))
raise SystemExit(0 if report['status']=='PASS' else 1)
