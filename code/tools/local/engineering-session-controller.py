"""Existing GS117 service controller, retained while explicitly enabled.

Privileged networking still uses the installed fixed GS179 executor and its
independent bounded sessions. This controller never operates a board.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse
import fcntl
import hashlib
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DIRECTORY = Path.home()/'.local/state/ghar-sajag/gs117-tc001/renewal-integration-20261113'
SOURCE = 'GS117_EXISTING_BOUNDED_ENGINEERING_INGRESS'

class TemporaryUnavailable(RuntimeError):
    pass


def service_status_current(row, pid, started_at, now=None):
    try:
        at=datetime.fromisoformat(row['at']); now=now or datetime.now(timezone.utc)
        return (row['pid']==pid and started_at<=at<=now and (now-at).total_seconds()<=10
                and row['status'].get('profile')=='GS179_TEST_ONLY'
                and all(row['status'].get(k)=='YES' for k in
                        ('listener_ready','postgres_ready','trusted_time_ready')))
    except (KeyError,TypeError,ValueError):
        return False


def rotation_due(authority, now=None):
    now=now or datetime.now(timezone.utc)
    deadline=min(datetime.fromisoformat(authority[k]) for k in ('lease_deadline','activity_deadline'))
    return now>=deadline-timedelta(seconds=60)


def lease_needs_rotation(read_authority, now=None):
    try:return rotation_due(read_authority(),now)
    except ValueError as error:
        if str(error)=='network_sublease_expired_or_idle':return True
        raise


def enabled_lifecycle(cycle, stop, wait):
    failures=0
    while not stop():
        try:
            cycle()
            failures=0
        except TemporaryUnavailable as error:
            failures=min(failures+1,6)
            delay=min(60,2**failures)
            print(json.dumps({'state':'WAITING_FOR_APPROVED_DEPENDENCY','reason':str(error),
                              'retry_after_seconds':delay}),flush=True)
            wait(delay)


def write_private(path, data):
    temporary=path.with_name(path.name+'.tmp')
    temporary.write_text(json.dumps(data,sort_keys=True)+'\n');temporary.chmod(0o600)
    os.replace(temporary,path)


def acquire_controller_lock(directory):
    handle=(directory/'controller.lock').open('a')
    try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close();return None
    return handle


def approved_network():
    command="$p=Get-NetConnectionProfile -InterfaceAlias 'Wi-Fi'; if($p.Name -ne 'Airtel_Agrim' -or $p.NetworkCategory -ne 'Private'){exit 2}; $a=@(Get-NetIPAddress -InterfaceAlias 'Wi-Fi' -AddressFamily IPv4|Where-Object AddressState -eq Preferred); if($a.Count -ne 1 -or $a[0].IPAddress -ne '192.168.1.6'){exit 2}"
    try:
        result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],
                              capture_output=True,text=True,timeout=20)
    except subprocess.TimeoutExpired as error:
        raise TemporaryUnavailable('windows_network_inspection_timeout') from error
    if result.returncode==2:
        # Reuse only the saved approved profile, and only after a current scan
        # sees it. An absent AP never triggers disconnect/profile replacement.
        try:
            scan=subprocess.run(['netsh.exe','wlan','show','networks','interface=Wi-Fi'],
                                capture_output=True,text=True,timeout=20)
            if scan.returncode==0 and re.search(r'^\s*SSID\s+\d+\s*:\s*Airtel_Agrim\s*$',scan.stdout,re.M):
                connected=subprocess.run(['netsh.exe','wlan','connect','name=Airtel_Agrim','interface=Wi-Fi'],
                                         capture_output=True,text=True,timeout=20)
                if connected.returncode:raise TemporaryUnavailable('saved_approved_wifi_reconnect_pending')
        except subprocess.TimeoutExpired as error:
            raise TemporaryUnavailable('saved_approved_wifi_inspection_timeout') from error
        raise TemporaryUnavailable('expected_private_wifi_unavailable')
    if result.returncode:raise RuntimeError('windows_network_inspection_failed')


def invoke_executor(operation, directory, lease_id):
    if operation not in ('Start','Close') or len(lease_id)!=64 or any(c not in '0123456789abcdef' for c in lease_id):
        raise ValueError('fixed_engineering_operation_required')
    command=['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass',
             '-File',r'C:\ProgramData\GharSajagEngineeringIngress\gs179-windows-lan-proxy.ps1',
             '-Action','InvokeEngineeringExecutor','-EndpointKind','PhysicalHubIngress',
             '-EngineeringOperation',operation,'-ControllerPid',str(os.getpid()),
             '-ServiceDirectory',str(directory),'-NetworkLeaseId',lease_id]
    result=subprocess.run(command,capture_output=True,text=True,timeout=170)
    try:receipt=json.loads(result.stdout)
    except ValueError:raise RuntimeError('engineering_executor_response_invalid') from None
    with (directory/'controller-network-actions.jsonl').open('a') as out:
        out.write(json.dumps({'at':datetime.now(timezone.utc).isoformat(),
            'operation':operation,'lease_id':lease_id,'exit':result.returncode,'receipt':receipt})+'\n')
    (directory/'controller-network-actions.jsonl').chmod(0o600)
    if result.returncode or receipt.get('success') is not True:
        raise RuntimeError('engineering_executor_'+operation.lower()+'_failed')


def close_session(directory, lease):
    try:invoke_executor('Close',directory,lease['lease_id'])
    except RuntimeError:
        # An independently expired session has no matching live Close target.
        # Preserve that failed receipt; never label it automatic-cleanup PASS.
        probe=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',
            '$n=@(Get-NetTCPConnection -State Listen -LocalPort 8445 -ErrorAction SilentlyContinue); if($n.Count -ne 0){exit 2}'],
            capture_output=True,text=True,timeout=20)
        if probe.returncode:raise
        print('PRIOR_CLOSE_FAILED_RECEIPT_PRESERVED_ROUTE_ABSENT',flush=True)


def stop_children(children):
    for _,process,_ in children:
        if process.poll() is None:process.terminate()
    end=time.monotonic()+8
    for _,process,_ in children:
        if process.poll() is None:
            try:process.wait(timeout=max(.1,end-time.monotonic()))
            except subprocess.TimeoutExpired:
                process.kill();process.wait(timeout=5)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('service_directory',nargs='?',default=str(DEFAULT_DIRECTORY))
    args=parser.parse_args(argv)
    supplied=Path(args.service_directory)
    if supplied.is_symlink():raise ValueError('private_registered_service_directory_required')
    directory=supplied.resolve()
    allowed=Path.home()/'.local/state/ghar-sajag/gs117-tc001'
    if directory.parent!=allowed or directory.stat().st_uid!=os.getuid() or directory.stat().st_mode&0o077:
        raise ValueError('private_registered_service_directory_required')
    lock=acquire_controller_lock(directory)
    if lock is None:
        print('EXISTING_CONTROLLER_REUSED',flush=True);return 0
    from gs179_verified_endpoint import (engineering_functional_admission,
        development_network_authority,issue_development_sublease,development_sublease_authority)
    engineering_functional_admission()
    subprocess.run([sys.executable,'-c','import psycopg'],check=True)
    installed=json.loads(Path('/mnt/c/ProgramData/GharSajagEngineeringIngress/installation.json').read_text(encoding='utf-8-sig'))
    authority_hash=installed['authorityHash']
    stop=threading.Event()
    signal.signal(signal.SIGTERM,lambda *_:stop.set())
    signal.signal(signal.SIGINT,lambda *_:stop.set())
    os.environ['GS117_SERVICE_DIRECTORY']=str(directory)

    def cycle():
        children=[];lease=None
        try:
            development_network_authority(authority_hash)
            approved_network()
            archive=directory/('previous-session-'+secrets.token_hex(8));archive.mkdir(mode=0o700)
            for name in ('signed-time-service.log','ingress-runtime.log','portal-runtime.log',
                         'controller-ready.json','ingress-runtime-status.json','launch-manifest.json'):
                path=directory/name
                if path.exists():shutil.move(str(path),str(archive/name))
            started=datetime.now(timezone.utc)
            def launch(name,logname,copy=True):
                source=Path(__file__).resolve().parent/name
                script=directory/name if copy else source
                if script.is_symlink():raise ValueError('service_script_symlink_rejected')
                if copy:shutil.copy2(source,script);script.chmod(0o600)
                with (directory/logname).open('ab',buffering=0) as log:
                    process=subprocess.Popen([sys.executable,'-u',str(script)],cwd=str(ROOT),
                        stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                children.append((name,process,script));return process
            def wait_ready(predicate):
                end=time.monotonic()+30
                while not stop.is_set() and time.monotonic()<end:
                    for _,process,_ in children:
                        code=process.poll()
                        if code==75:raise TemporaryUnavailable('service_dependency_unavailable')
                        if code is not None:raise RuntimeError('service_start_failed_closed')
                    try:
                        if predicate():return
                    except (OSError,ValueError,KeyError,TypeError):pass
                    stop.wait(.25)
                if not stop.is_set():raise TemporaryUnavailable('service_readiness_timeout')
            launch('gs117-start-existing-signed-time.py','signed-time-service.log')
            wait_ready(lambda:'SIGNED_TIME_READY' in (directory/'signed-time-service.log').read_text(errors='replace'))
            ingress=launch('gs117-active-ingress.py','ingress-runtime.log')
            wait_ready(lambda:service_status_current(json.loads((directory/'ingress-runtime-status.json').read_text()),ingress.pid,started))
            if stop.is_set():return
            launch('gs117_tc001_console.py','portal-runtime.log',copy=False)
            manifest={'controller_pid':os.getpid(),'lifetime_seconds':None,'source':SOURCE,
                      'processes':[{'pid':p.pid,'script':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()} for name,p,path in children]}
            write_private(directory/'launch-manifest.json',manifest)
            write_private(directory/'controller-ready.json',dict(controller_pid=os.getpid(),service_directory=str(directory),source=SOURCE,processes=manifest['processes']))
            while not stop.is_set():
                development_network_authority(authority_hash)
                approved_network()
                for _,process,_ in children:
                    code=process.poll()
                    if code==75:raise TemporaryUnavailable('service_dependency_unavailable')
                    if code is not None:raise RuntimeError('owned_service_exited_fail_closed')
                if lease is None or lease_needs_rotation(lambda:development_sublease_authority(lease['lease_id'],authority_hash,os.getpid(),str(directory))):
                    if lease is not None:
                        close_session(directory,lease);lease=None
                    lease=issue_development_sublease(authority_hash,os.getpid(),str(directory))
                    invoke_executor('Start',directory,lease['lease_id'])
                    write_private(directory/'current-network-lease.json',lease)
                    print('CONTROLLER_READY '+json.dumps({'controller_pid':os.getpid(),'lease':lease,'continuous_until_stopped':True}),flush=True)
                stop.wait(10)
        finally:
            if lease is not None:
                try:close_session(directory,lease)
                except (RuntimeError,OSError,subprocess.SubprocessError) as error:
                    print('EXPLICIT_CLOSE_NOT_VERIFIED '+type(error).__name__,flush=True)
            stop_children(children)
            write_private(directory/'controller-status.json',{'pid':os.getpid(),'services_ready':False,'at':datetime.now(timezone.utc).isoformat()})
    try:
        enabled_lifecycle(cycle,stop.is_set,stop.wait)
    finally:
        lock.close();print('CONTROLLER_STOPPED',flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
