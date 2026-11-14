from pathlib import Path
import subprocess, json, base64, os, signal
WINPY = '/mnt/c/Users/DELL/AppData/Local/Programs/Python/Python312/python.exe'
trust = Path.home() / '.config/ghar-sajag/gs117-tc001'
code = "\nimport sys,json,base64,time,os,signal\nsys.path[:0]=[r'\\\\wsl.localhost\\Ubuntu\\home\\udaybhan\\projects\\Ghar_sajag_r1\\code\\tools\\hil',r'\\\\wsl.localhost\\Ubuntu\\home\\udaybhan\\projects\\Ghar_sajag_r1\\code\\backend']\nfrom cryptography.hazmat.primitives import serialization\nfrom gs40_test_bootstrap import SignedTimeService\nfrom gs68_signed_time_fixture import TestOnlySignedTimeFixture\ncfg=json.loads(sys.stdin.readline());key=serialization.load_pem_private_key(base64.b64decode(cfg.pop('key')),password=None)\nsvc=SignedTimeService(fixture=TestOnlySignedTimeFixture(private_key=key),bind_host=cfg['address'],port=4468,allow_private_bind=True).start();print(json.dumps({'event':'SIGNED_TIME_READY','pid':os.getpid(),'address':cfg['address'],'port':4468}),flush=True)\ntry:\n svc.wait_for_owner(sys.stdin)\nfinally:print('SIGNED_TIME_STOPPED',flush=True)\n"
ps = subprocess.run(['powershell.exe', '-NoProfile', '-Command', "$p=Get-NetConnectionProfile -InterfaceAlias 'Wi-Fi'; if($p.Name -ne 'Airtel_Agrim' -or $p.NetworkCategory -ne 'Private'){exit 2};(Get-NetIPAddress -InterfaceAlias 'Wi-Fi' -AddressFamily IPv4|Where-Object AddressState -eq Preferred).IPAddress"], capture_output=True, text=True)
if ps.returncode == 2 or (ps.returncode == 0 and ps.stdout.strip() != '192.168.1.6'):
    print('EXPECTED_PRIVATE_WIFI_UNAVAILABLE',flush=True)
    raise SystemExit(75)
if ps.returncode != 0:
    raise RuntimeError('windows_network_inspection_failed')
state = Path(os.environ['GS117_SERVICE_DIRECTORY'])
with (state / 'signed-time-service.log').open('w') as log:
    p = subprocess.Popen([WINPY, '-u', '-c', code], cwd='/mnt/c', stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT, text=True)
    payload = {'address': ps.stdout.strip(), 'key': base64.b64encode((trust / 'physical-time-signing-private.pem').read_bytes()).decode()}
    p.stdin.write(json.dumps(payload) + '\n')
    p.stdin.flush()
    payload.clear()
    print('Existing signed-time service started; owned process lifetime; independent network leases', flush=True)
    def stop_owned_child(*_):
        if not p.stdin.closed:p.stdin.close()
    signal.signal(signal.SIGTERM,stop_owned_child)
    signal.signal(signal.SIGINT,stop_owned_child)
    try:
        raise SystemExit(p.wait())
    finally:
        stop_owned_child()
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(timeout=5)
