#!/usr/bin/env python3
from pathlib import Path
import json, sys
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'tests'/'validation_coverage.json'
data=json.loads(p.read_text())
required=[*(f'F{i:02d}' for i in range(1,15)),*(f'E{i:02d}' for i in range(1,11))]
missing=[r for r in required if r not in data.get('p0_requirements',{})]
errors=[]
if missing: errors.append('missing requirement coverage: '+', '.join(missing))
for rid,entry in data.get('p0_requirements',{}).items():
    refs=entry.get('automated',[])+entry.get('manual',[])
    if not refs and not entry.get('hardware_pending'): errors.append(f'{rid}: no validation reference')
    for ref in refs:
        if not (ROOT/ref).exists(): errors.append(f'{rid}: missing referenced file {ref}')
if errors:
    print('\n'.join(errors));sys.exit(1)
print(f"validation coverage: {len(required)}/{len(required)} P0 requirement IDs mapped")
