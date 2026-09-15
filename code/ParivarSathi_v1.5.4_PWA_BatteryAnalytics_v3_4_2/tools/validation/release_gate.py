# MANDATORY_BROWSER_NOTE: use `make release-gate-final` for shipment; Playwright/Chromium is mandatory there.
#!/usr/bin/env python3
"""Fail-closed host release gate for Ghar Sajag.

A host/software release is acceptable only when all mandatory stages pass. Browser automation is
reported separately because Playwright/Chromium is an optional developer dependency; use
--require-browser in CI/release environments where it is installed. Physical hardware gates remain
outside this host gate and are listed in the generated report/manual plan.
"""
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys, time, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.run_playwright_gate import (
    assert_lab_port_available,
    terminate_process_group,
)
EVIDENCE=ROOT/'evidence'/'release_gate_v1.5.4'
EVIDENCE.mkdir(parents=True,exist_ok=True)
BROWSER_HOST='127.0.0.1'
BROWSER_PORT=8765

parser=argparse.ArgumentParser()
parser.add_argument('--quick',action='store_true',help='skip feature matrix, sanitizer and trace build')
parser.add_argument('--require-browser',action='store_true',help='fail if Playwright browser validation cannot run')
args=parser.parse_args()

stages=[]
def run(name,cmd,timeout=240,env=None,mandatory=True):
    started=time.time(); merged=os.environ.copy(); merged.update(env or {})
    try:
        cp=subprocess.run(cmd,cwd=ROOT,env=merged,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
        status='PASS' if cp.returncode==0 else 'FAIL'
        output=cp.stdout
    except subprocess.TimeoutExpired as exc:
        status='FAIL'; output=(exc.stdout or '')+f"\nTIMEOUT after {timeout}s\n"
    log=EVIDENCE/f'{len(stages)+1:02d}_{name}.log';log.write_text(output or '')
    stages.append({'name':name,'status':status,'mandatory':mandatory,'seconds':round(time.time()-started,2),'command':cmd,'log':str(log.relative_to(ROOT))})
    print(f"{status:4} {name} ({stages[-1]['seconds']}s)")
    if status=='FAIL' and mandatory:
        return False
    return True

def playwright_available():
    cp=subprocess.run(['node','-e','require("playwright");'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return cp.returncode==0

def wait_http_ready(url, proc, timeout=60):
    """Wait for the local lab to accept HTTP instead of assuming a fixed startup delay."""
    deadline=time.time()+timeout
    last_error=None
    while time.time()<deadline:
        rc=proc.poll()
        if rc is not None:
            output=''
            try:
                output=proc.stdout.read() if proc.stdout else ''
            except Exception:
                pass
            return False, f"lab exited early rc={rc}\n{output[-4000:]}"
        try:
            with urllib.request.urlopen(url,timeout=2) as response:
                if response.status < 500:
                    return True, ''
        except Exception as exc:
            last_error=exc
        time.sleep(0.5)
    return False, f"lab not ready after {timeout}s: {last_error}"

def browser_stage():
    if not playwright_available():
        stages.append({'name':'browser-e2e','status':'FAIL' if args.require_browser else 'MANUAL_REQUIRED','mandatory':args.require_browser,'seconds':0,'command':['node','tests/simulation_browser_test.cjs'],'log':None})
        print(('FAIL' if args.require_browser else 'MANUAL_REQUIRED'), 'browser-e2e (Playwright not installed)')
        return not args.require_browser

    server_log=EVIDENCE/'browser-e2e-server.log'
    try:
        assert_lab_port_available(BROWSER_HOST, BROWSER_PORT)
    except RuntimeError as exc:
        server_log.write_text(str(exc)+'\n')
        stages.append({'name':'browser-e2e','status':'FAIL','mandatory':True,'seconds':0,
                       'command':['node','tests/simulation_browser_test.cjs'],
                       'log':str(server_log.relative_to(ROOT))})
        print(f'FAIL browser-e2e ({exc})')
        return False
    subprocess.run(['make','lab-build'],cwd=ROOT,check=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    try:
        assert_lab_port_available(BROWSER_HOST, BROWSER_PORT)
    except RuntimeError as exc:
        server_log.write_text(str(exc)+'\n')
        stages.append({'name':'browser-e2e','status':'FAIL','mandatory':True,'seconds':0,
                       'command':['node','tests/simulation_browser_test.cjs'],
                       'log':str(server_log.relative_to(ROOT))})
        print(f'FAIL browser-e2e ({exc})')
        return False
    server=subprocess.Popen(
        [sys.executable,'tools/sim/local_lab.py','--port',str(BROWSER_PORT)],
        cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,
        env={**os.environ,'GS_APP_DB':':memory:'},
        start_new_session=True,
    )
    stage_result=False
    server_details=''
    try:
        browser_url=f'http://{BROWSER_HOST}:{BROWSER_PORT}/lab'
        ready,why=wait_http_ready(browser_url,server,timeout=60)
        if not ready:
            # Do not read a live child's pipe to EOF here; the finally block
            # must be able to terminate/reap it on readiness timeout as well.
            output=''
            if server.poll() is not None:
                try:
                    output=server.stdout.read() if server.stdout else ''
                except Exception:
                    output=''
            server_details=(why+'\n'+output)[-12000:]
            stages.append({
                'name':'browser-e2e','status':'FAIL','mandatory':True,'seconds':0,
                'command':['node','tests/simulation_browser_test.cjs'],
                'log':str(server_log.relative_to(ROOT))
            })
            print('FAIL browser-e2e (local lab did not become ready)')
        else:
            stage_result = run(
                'browser-e2e',
                ['node','tests/simulation_browser_test.cjs'],
                timeout=180,
                mandatory=True,
                env={'GS_LAB_URL':browser_url}
            )
    finally:
        out=terminate_process_group(server)
        server_log.write_text((server_details+'\n'+(out or ''))[-12000:])
    return stage_result

ok=True
# Reproducibility/traceability first.
ok &= run('validation-coverage',[sys.executable,'scripts/check_validation_coverage.py'])
ok &= run('contracts',[sys.executable,'scripts/verify_contracts.py'])
ok &= run('cpp-unit',['make','cpp-test'])
# make python-test discovers all tests/python/test_*.py, including the Phase 1
# FoundationService persistence/domain and WSGI application-path suites.
ok &= run('python-backend-db-logging',['make','python-test'])
ok &= run('javascript-app',['make','app-test'])
ok &= run('product-base',['make','product-test','PRODUCT=base'])
ok &= run('product-ai',['make','product-test','PRODUCT=ai'])
if not args.quick:
    feature_variants = [
        ('feature-p0-default', '-DGS_FEATURE_MORNING_ROUTINE=1 -DGS_FEATURE_CALL_FAMILY=1 -DGS_FEATURE_LOCAL_OFFLINE=1'),
        ('feature-routine-disabled', '-DGS_FEATURE_MORNING_ROUTINE=0'),
        ('feature-call-disabled', '-DGS_FEATURE_CALL_FAMILY=0'),
        ('feature-offline-disabled', '-DGS_FEATURE_LOCAL_OFFLINE=0'),
    ]
    for variant_name, flags in feature_variants:
        ok &= run(variant_name + '-clean', ['make','clean'], timeout=60)
        ok &= run(variant_name, ['make','simulator', f'TRACE_FLAGS={flags}'], timeout=120)
ok &= run('lab-build',['make','lab-build'])
ok &= run('dummy-sensor-streams',[sys.executable,'tools/validation/run_dummy_sensor_streams.py'])
ok &= run('functional-catalog',[sys.executable,'tools/validation/run_functional_suite.py'],timeout=240)
ok &= run('http-integration',[sys.executable,'tests/simulation_http_test.py'],timeout=240)
ok &= run('pwa-bridge',[sys.executable,'tests/pwa_bridge_test.py'],timeout=240)
ok &= run('pwa-68-api',[sys.executable,'tests/pwa_68_api_test.py'],timeout=300)
# Phase 1 browser coverage is included by scripts/run_playwright_gate.py, which
# runs every spec under tests/playwright for both configured Chromium projects.
ok &= run('pwa-68-frontend',[sys.executable,'tests/pwa_68_frontend_test.py'],timeout=300)
if not args.quick:
    ok &= run('cpp-sanitizers',['make','verify-sanitize'],timeout=300,env={'ASAN_OPTIONS':'detect_leaks=0'})
    ok &= run('trace-build',['make','cpp-test','TRACE_FLAGS=-DGS_ENABLE_TRACE=1'],timeout=180)
ok &= browser_stage()

mandatory_fail=[s for s in stages if s['mandatory'] and s['status']!='PASS']
status='PASS' if not mandatory_fail else 'FAIL'
report={
    'release':'1.5.4','status':status,'quick':args.quick,'require_browser':args.require_browser,
    'stages':stages,
    'host_release_ready':status=='PASS',
    'physical_hardware_acceptance':'PENDING',
    'physical_pending':['real PIR/reed/buttons','ESP-NOW RF/RSSI/offline timing','battery/runtime/charging/UPS','brown-out/reset/watchdog','flash persistence/wear','OTA signing/rollback','real push/provider delivery','installed-home coverage'],
}
(ROOT/'evidence'/'Release_Gate_v1.5.4.json').write_text(json.dumps(report,indent=2)+'\n')
md=['# Ghar Sajag v1.5.4 Release Gate','',f"**Host/software result: {status}**",'', '| Stage | Result | Seconds |','|---|---:|---:|']
for s in stages: md.append(f"| {s['name']} | {s['status']} | {s['seconds']} |")
md += ['','## Boundary','', 'A PASS means the hardware-independent host/software release gate passed. It does **not** certify physical ESP32/RF/power behaviour. Those gates remain pending until hardware is available.','', 'Manual browser/PWA cases are in `tests/MANUAL_FUNCTIONAL_VALIDATION.md`. Use `--require-browser` when Playwright is installed so the browser test becomes mandatory.','']
(ROOT/'evidence'/'Release_Gate_v1.5.4.md').write_text('\n'.join(md)+'\n')
print(f"\nHost release gate: {status}")
raise SystemExit(0 if status=='PASS' else 1)
