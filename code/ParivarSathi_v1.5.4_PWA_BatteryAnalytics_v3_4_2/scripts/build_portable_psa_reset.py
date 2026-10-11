#!/usr/bin/env python3
"""Build real installed TF-PSA Crypto and execute the offline reset regression.

Compatibility headers expose upstream private declarations used by the IDF fork;
they provide no crypto functions. No target hardware or SDK files are modified.
"""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def dependency_fingerprint(env=None):
    """Receipt provenance includes real upstream crypto and extracted IDF guard."""
    env=os.environ if env is None else env
    idf=Path(env.get('IDF_PATH','/home/udaybhan/.espressif/v6.0.3/esp-idf'))
    source=idf/'components/mbedtls/mbedtls/tf-psa-crypto'
    guard=idf/'components/mbedtls/port/aes/esp_aes_gcm.c'
    if not (source/'CMakeLists.txt').is_file() or not guard.is_file():
        return 'MISSING:'+str(idf)
    digest=hashlib.sha256()
    for p in sorted(source.rglob('*')):
        if p.is_file() and (p.suffix in {'.c','.h','.cmake'} or p.name=='CMakeLists.txt'):
            digest.update(str(p.relative_to(source)).encode()+b'\0'+p.read_bytes())
    digest.update(guard.read_bytes())
    return digest.hexdigest()

def main():
    for tool in ('cmake','cc','g++'):
        if not shutil.which(tool):
            raise RuntimeError('mandatory portable crypto dependency missing: '+tool)
    idf=Path(os.environ.get('IDF_PATH','/home/udaybhan/.espressif/v6.0.3/esp-idf'))
    source=idf/'components/mbedtls/mbedtls/tf-psa-crypto'
    if not (source/'CMakeLists.txt').is_file():
        raise RuntimeError('mandatory installed TF-PSA source missing: '+str(source))
    digest=hashlib.sha256()
    for p in sorted(source.rglob('*')):
        if p.is_file() and (p.suffix in {'.c','.h','.cmake'} or p.name=='CMakeLists.txt'):
            digest.update(str(p.relative_to(source)).encode()+b'\0'+p.read_bytes())
    # Header changes and compiler versions invalidate this dependency cache.
    digest.update(Path(__file__).read_bytes())
    digest.update(dependency_fingerprint().encode())
    for tool in ('cc','g++','cmake'):
        digest.update(subprocess.check_output([tool,'--version']))
    profile=digest.hexdigest()
    build=ROOT/'build'/('portable_psa_'+profile[:16])
    compat=build/'compat'
    (compat/'mbedtls').mkdir(parents=True,exist_ok=True)
    for name in ('bignum','ecp'):
        (compat/'mbedtls'/f'{name}.h').write_text(
            '#pragma once\n#define MBEDTLS_DECLARE_PRIVATE_IDENTIFIERS\n'
            f'#include "mbedtls/private/{name}.h"\n')
    def run(args):
        print('PORTABLE PSA:', ' '.join(map(str,args)),flush=True)
        subprocess.run(list(map(str,args)),check=True,cwd=ROOT)
    print('PORTABLE PSA source SHA256='+profile,flush=True)
    run(['cmake','-S',source,'-B',build,'-DENABLE_PROGRAMS=OFF',
         '-DENABLE_TESTING=OFF','-DGEN_FILES=OFF','-DCMAKE_BUILD_TYPE=Release',
         '-DCMAKE_C_FLAGS=-B/usr/bin -I'+str(compat)])
    run(['cmake','--build',build,'-j2'])
    run([sys.executable,ROOT/'tools/factory/validate_node_reset.py',
         '--crypto-build',build,'--compat-include',compat,
         '--output',ROOT/'build/factory_reset_validation'])

if __name__=='__main__':
    try: main()
    except (RuntimeError,OSError,subprocess.CalledProcessError) as error:
        print('PORTABLE PSA RESET FAIL: '+str(error),file=sys.stderr)
        sys.exit(1)
