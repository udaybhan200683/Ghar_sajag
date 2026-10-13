#!/usr/bin/env python3
"""Compile pinned OLD production code and read FIX's exact v1 byte snapshots.
All extracted files are disposable build inputs, not another development tree.
No Git ref/worktree operations, hardware, migration or on-device writes.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib, json, os, re, subprocess, tempfile

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parent
BASELINE='371a560f04b99bce8fd86e58739a75184b555b55'

def run(args, **kwargs):
    return subprocess.run(args,cwd=ROOT,text=True,capture_output=True,**kwargs)

def main():
    folder=ROOT/'build/gs148_reader_compatibility';folder.mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix='reader-',dir=folder));source=work/'baseline';source.mkdir()
    names=subprocess.check_output(['git','ls-tree','-r','--name-only',BASELINE,'--',
        'code/firmware','code/tests/support'],cwd=REPO,text=True).splitlines()
    hashes={}
    for name in names:
        if Path(name).suffix not in {'.hpp','.h','.cpp','.c'}: continue
        data=subprocess.check_output(['git','show',BASELINE+':'+name],cwd=REPO)
        relative=Path(name).relative_to('code');path=source/relative
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        hashes[str(relative)]=hashlib.sha256(data).hexdigest()
    makefile=(ROOT/'Makefile').read_text()
    sources=re.search(r'CPP_SOURCES := \\\n(.*?)\n\n',makefile,re.S).group(1).replace('\\','').split()
    sources+=['firmware/hub/storage/durable_event_outbox.cpp','firmware/hub/storage/outbox_journal_backend.cpp',
        'firmware/hub/target/esp32/nvs_durable_key_codec.cpp',
        'firmware/hub/commissioning/registry/registry_persistence.cpp',
        'firmware/common/security/runtime_frame_security.cpp','firmware/common/security/rejoin_protocol.cpp',
        'tests/support/host/security/openssl_commissioning_crypto.cpp']
    sources=list(dict.fromkeys(sources))
    flags=['-B/usr/bin','-std=c++17','-O2','-Wall','-Wextra','-Werror','-pedantic',
        '-DGS_PRODUCT_AI=0','-DGS_ENABLE_TRACE=0','-DGS148_OLD_READER',
        '-I'+str(source),'-I'+str(source/'firmware/common/shared/include'),
        '-I'+str(source/'firmware/node'),'-I'+str(source/'firmware/hub'),
        '-I'+str(source/'firmware/common/security'),'-I'+str(ROOT/'build/gs40_generated'),'-I'+str(ROOT)]
    compiler=os.environ.get('CXX','g++')
    def compile_one(name):
        obj=work/'objects'/(name+'.o');obj.parent.mkdir(parents=True,exist_ok=True)
        result=run([compiler,*flags,'-c',str(source/name),'-o',str(obj)])
        if result.returncode: raise RuntimeError(name+'\n'+result.stderr)
        return str(obj)
    with ThreadPoolExecutor(max_workers=4) as pool: objects=list(pool.map(compile_one,sources))
    old=work/'old_reader'
    result=run([compiler,*flags,*objects,str(ROOT/'tests/cpp/hub_first_event_reader_validation.cpp'),
        '-lcrypto','-o',str(old)])
    (work/'old-build.log').write_text(result.stdout+result.stderr)
    if result.returncode: raise RuntimeError(result.stderr)
    cases={
        'empty':(True,True,0,0), 'empty-interrupted':(False,True,0,0),
        'prepared':(True,True,0,1), 'pending':(False,True,0,1),
        'pending-two-boots':(False,True,0,1), 'published':(True,True,1,1),
        'committed':(True,True,1,1), 'acked-missing-head':(False,False,0,0),
        'populated-missing-head':(False,False,0,0), 'malformed-head':(False,False,0,0),
        'pending-missing-checkpoint':(False,False,0,0)}
    records=[];fixed=ROOT/'build/gs148_fixed_reader'
    for name,(old_ready,fixed_ready,public,identities) in cases.items():
        snapshot=work/(name+'.bin');writer=run([str(fixed),'write',name,str(snapshot)])
        if writer.returncode: raise RuntimeError(writer.stderr)
        digest=hashlib.sha256(snapshot.read_bytes()).hexdigest()
        record={'state':name,'snapshot_sha256':digest,'readers':{}}
        for label,executable,ready in [('OLD',old,old_ready),('FIX',fixed,fixed_ready)]:
            result=run([str(executable),'probe',name,str(snapshot)])
            expected=0 if ready else 2
            status='READY' if ready else 'FAIL_CLOSED'
            valid=result.returncode==expected and f'{name} {status}' in result.stdout and 'boots=2' in result.stdout
            if ready: valid=valid and f'public={public} identities={identities}' in result.stdout
            record['readers'][label]={'exit':result.returncode,'expected_ready':ready,'passed':valid,
                'stdout':result.stdout,'stderr':result.stderr}
            if hashlib.sha256(snapshot.read_bytes()).hexdigest()!=digest:
                raise RuntimeError('reader mutated shared input snapshot')
            if not valid: raise RuntimeError(json.dumps(record,indent=2))
        records.append(record)
    report={'baseline':BASELINE,'baseline_source_sha256':hashes,'compiler':compiler,'flags':flags,
        'cases':records,'checks':len(records)*2,'software_compatibility':'PASS',
        'old_reader_supported_availability':'FAIL_KNOWN_FIRST_EVENT_LIMITATION',
        'commercial_signed_image_pair':'NOT_SELECTED_NOT_QUALIFIED','physical_ota':'NOT_RUN'}
    (work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'GS148-ARCH-049 PASS actual_readers=2 byte_states={len(records)} reboot_per_reader=2')
    print('OLD_READER_COMMERCIAL_ROLLBACK_AVAILABILITY=FAIL_KNOWN_FIRST_EVENT_LIMITATION')
    print('GS148_READER_REPORT='+str((work/'report.json').relative_to(ROOT)))
    return 0

if __name__=='__main__':
    try: raise SystemExit(main())
    except (RuntimeError,OSError,subprocess.SubprocessError) as error:
        print('GS148 reader compatibility FAIL: '+str(error));raise SystemExit(1)
