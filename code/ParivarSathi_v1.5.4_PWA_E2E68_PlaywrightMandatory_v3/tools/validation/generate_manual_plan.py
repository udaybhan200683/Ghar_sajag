#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
catalog=json.loads((ROOT/'tests'/'functional'/'scenario_catalog.json').read_text())

def step_text(step):
    if step.get('capture')=='first_incident': return 'Record the first incident ID shown by the simulator.'
    a=step.get('action')
    if a=='event': return f"Inject {step.get('kind')} from {step.get('node')}" + (' using the late-night control' if step.get('late_night') else '') + (f" (expect rejection: {step.get('expect_error')})" if step.get('expect_error') else '')
    if a=='advance': return f"Advance simulated clock by {step.get('seconds')} seconds" + (f" (expect rejection: {step.get('expect_error')})" if step.get('expect_error') else '')
    if a=='settings_patch': return f"Change household setting(s): {json.dumps(step.get('values',{}),sort_keys=True)}" + (f" (expect rejection: {step.get('expect_error')})" if step.get('expect_error') else '')
    if a=='time': return f"Set simulated local minute to {step.get('minute')}"
    if a=='mode': return f"Set home mode to {step.get('mode')}" + (f" (expect rejection: {step.get('expect_error')})" if step.get('expect_error') else '')
    if a in {'claim','acknowledge','resolve'}: return f"As primary caregiver, {a} the captured incident"
    if a=='node': return f"Set node {step.get('node')} link {'available' if step.get('enabled') else 'unavailable'}"
    if a=='wan': return f"Set internet {'connected' if step.get('enabled') else 'disconnected'}"
    if a=='clock': return f"Set clock {'trusted' if step.get('enabled') else 'untrusted'}"
    if a=='fault': return f"Inject {step.get('fault')} on {step.get('target')}"
    if a=='troubleshoot': return f"Run Troubleshoot on {step.get('target')}"
    if a=='reboot': return f"Run Reboot on {step.get('target')}"
    if a=='notify': return 'Run fake notification-provider delivery.'
    if a=='deadline': return 'Evaluate routine deadline again.'
    if a=='duplicate': return 'Replay the last node business event.'
    return json.dumps(step,sort_keys=True)

def assertion_text(x):
    if 'path' in x:
        op=next((o for o in ('eq','ne','ge','gt','le','lt') if o in x),None)
        if op:return f"`{x['path']}` {op} `{x[op]}`"
        if x.get('truthy'):return f"`{x['path']}` is true/non-empty"
        if x.get('falsy'):return f"`{x['path']}` is false/empty"
    if 'select' in x:
        n=x.get('count',f">={x.get('min_count')}")
        return f"`{x['select']}` contains {n} item(s) matching `{json.dumps(x.get('where',{}),sort_keys=True)}`"
    if 'order' in x:return f"`{x['order']['path']}` begins in order `{x['order']['prefix']}`"
    return f"`{json.dumps(x,sort_keys=True)}`"

out=[f"# Ghar Sajag v{catalog['release']} Manual Functional Validation Plan","",
     "Use this checklist before a release when reviewing the browser/PWA manually. It is generated from the same scenario catalog used by automation, so manual and automated coverage cannot silently drift.","",
     "## Common setup","","1. Run `make lab`.","2. Open `http://127.0.0.1:8765`.","3. Before each case press **Reset scenario** unless the case says otherwise.","4. Use only synthetic/demo data.","5. Record PASS/FAIL, screenshot failures, and attach `logs/e2e_report.json`.",""]
cur=None
for i,s in enumerate(catalog['scenarios'],1):
    if s['category']!=cur:
        cur=s['category'];out += [f"## {cur.title()} scenarios",""]
    out += [f"### M{i:03d} — {s['title']}",f"Scenario ID: `{s['id']}`  ",f"Requirements: {', '.join(s.get('requirements',[])) or 'general regression'}","","**Steps**"]
    out += [f"{j}. {step_text(st)}" for j,st in enumerate(s.get('steps',[]),1)] or ['1. No action; inspect reset state.']
    out += ["","**Expected**"]
    out += [f"- {assertion_text(a)}" for a in s.get('assertions',[])] or ["- The requested invalid operation is rejected and the simulator remains usable."]
    out += ["","Result: ☐ PASS ☐ FAIL   Notes: ______________________________",""]

out += ["## Additional visual/accessibility checks","",
        "- ☐ I am OK is visually positive/green and includes elapsed time.",
        "- ☐ Unexpected/concern events are visually distinct in red and are not communicated by color alone.",
        "- ☐ Active/degraded/offline device states have text labels as well as colored status circles.",
        "- ☐ 390 px mobile viewport has no horizontal overflow and primary controls remain usable.",
        "- ☐ Family/caregiver timeline is newest-first and missing-morning/call incidents are not hidden by later activity.",
        "- ☐ Settings values reload after Save and display the new configuration version.",
        "- ☐ No Privacy ON/OFF control is present in normal household Settings.",
        "","## Physical-hardware acceptance (cannot be completed in host simulation)","",
        "These are mandatory before an unattended pilot but are intentionally not marked automated PASS: real PIR/reed/button debounce, ESP-NOW RF/link loss, RSSI, battery calibration/runtime, brown-out, charging/UPS, actual reboot/reset reason, temperature telemetry, flash persistence/wear, OTA signature/rollback, real push delivery, and installed-home coverage.",""]
(ROOT/'tests'/'MANUAL_FUNCTIONAL_VALIDATION.md').write_text('\n'.join(out)+'\n')
print(f"generated {len(catalog['scenarios'])} manual scenario cases")
