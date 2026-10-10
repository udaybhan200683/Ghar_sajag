#!/usr/bin/env python3
"""GS-40 reproducible software bundle. Does not access serial ports or flash."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from ghar_sajag.node_health_policy import load

def package(config,c3_build,s3_build,output):
    policy=load(config)
    canonical=json.dumps(json.loads(config.read_text()),sort_keys=True,separators=(',',':'))
    digest=hashlib.sha256(canonical.encode()).hexdigest()
    projects=[('c3',c3_build,'gs_hw_m1_node'),('s3',s3_build,'gs_r1_s3_hub')]
    apps={name:(build/(project+'.bin')).read_bytes() for name,build,project in projects}
    for name,build,_ in projects:
        header=build/'gs40_generated/gs/node_health_config.hpp'
        if digest not in header.read_text() or digest.encode() not in apps[name]:
            raise ValueError(name+' image/configuration fingerprint mismatch; rebuild')
    if apps['c3'] not in apps['s3']:
        raise ValueError('Hub embedded C3 asset differs from candidate; rebuild Hub with GS_NODE_FIRMWARE_ASSET')
    manifest={'schema_version':1,'configuration_sha256':digest,
              'heartbeat_interval_seconds':policy.configured.heartbeat_seconds,
              'node_offline_timeout_seconds':policy.configured.offline_seconds,
              'deployment_profiles':policy.profiles,'hardware_actions':'NONE',
              'qualification':'SOFTWARE_ONLY','images':{}}
    output.mkdir(parents=True,exist_ok=True)
    for name,build,project in projects:
        args=json.loads((build/'flasher_args.json').read_text())
        for offset,relative in args['flash_files'].items():
            source=build/relative;target=output/name/relative
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
            manifest['images'].setdefault(name,[]).append({'offset':offset,'file':name+'/'+relative,
                'bytes':source.stat().st_size,'sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
        shutil.copyfile(build/'flasher_args.json',output/name/'flasher_args.json')
    shutil.copyfile(config,output/'node_health.json')
    shutil.copyfile(ROOT/'config/node_health.schema.json',output/'node_health.schema.json')
    manifest['source_head']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    manifest['tracked_source_dirty']=bool(subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip())
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',type=Path,default=ROOT/'config/node_health.json')
    parser.add_argument('--c3-build',type=Path,required=True)
    parser.add_argument('--s3-build',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'build/gs40_bundle')
    args=parser.parse_args()
    try:package(args.config,args.c3_build,args.s3_build,args.output)
    except (ValueError,OSError,KeyError) as error:parser.exit(1,'GS40_PACKAGE_INVALID: '+str(error)+'\n')
