#!/usr/bin/env python3
"""Focused host evidence; run from repo root. No hardware or product policy."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[5]
PROBE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('suite', choices=('fault', 'capacity', 'schedule'))
parser.add_argument('--binary', type=Path, default=PROBE / 'build/gs_nvs_runtime_probe.elf')
args = parser.parse_args()
log = ROOT / f'docs/exec-plans/evidence/R1_STORAGE_NVS_DIAG_{args.suite.upper()}_20261008.log'
checks = 0
with log.open('w') as out:
    out.write(f'BINARY_SHA256={hashlib.sha256(args.binary.read_bytes()).hexdigest()}\n')
    out.write(f'PROBE_SHA256={hashlib.sha256((PROBE / "main/probe.cpp").read_bytes()).hexdigest()}\n')
    def run(argv, env=None, expected=0, trace=False):
        global checks
        extra = env or {}
        cmd = [str(args.binary), *map(str, argv)]
        result = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                env={**os.environ, 'GCOV_PREFIX': '/tmp/gs-diag-coverage', **extra})
        for line in result.stdout.splitlines():
            if line.startswith('EMULATOR_IMAGE=/tmp/idf-partition-'):
                # Exact path emitted by this child, not a glob or old evidence.
                Path(line.split('=',1)[1]).unlink(missing_ok=True)
        checks += 1
        out.write(f'COMMAND={" ".join(cmd)} ENV={extra} EXIT={result.returncode}\n')
        # Full IO traces preserved separately; exhaustive sweep preserves terminal
        # measurements and errors. No successful cut is silently omitted.
        if trace or result.returncode not in (expected if isinstance(expected,tuple) else (expected,)):
            out.write(result.stdout)
        else:
            out.write('\n'.join(line for line in result.stdout.splitlines()
                                if line.startswith(('NVS_RUNTIME_FAULT', 'DIAG_OPERATION',
                                                    'RECOVERY_INTERRUPTION', 'CAPACITY',
                                                    'SCHEDULE', 'NVS_RUNTIME_PROMOTION',
                                                    'REPORT_IO_PEAK', 'NVS_RUNTIME_SATURATION',
                                                    'NVS_RUNTIME phase=capacity_peak',
                                                    'NVS_RUNTIME phase=after_report_attempt')))+'\n')
        out.flush()
        if result.returncode not in (expected if isinstance(expected,tuple) else (expected,)):
            raise RuntimeError(f'Unexpected exit: {cmd}: {result.returncode}; see {log}')
    if args.suite == 'fault':
        for cut in range(1082):
            run([9,50,20,'fault',cut,'freeze'])
        for cut in range(1230):
            run([9,50,20,'banks',cut])
        for cut in (0,1071,1072,1180,1227,1228):
            for recovery_cut in range(65):
                run([9,50,20,'banks',cut], {'GS_RECOVERY_CUT': str(recovery_cut)})
    elif args.suite == 'capacity':
        run([9,1000,13], {'GS_PEAK': '1'}, trace=True)
        for size in (36,44,124):
            for segments in (3,4,5,7,9):
                # Capacity failures are measurements, not a successful admission.
                env={'GS_HOT_BYTES':str(size),'GS_PEAK':'1'}
                run([segments,1000,20,'capacity',192],env,expected=(0,2),trace=True)
        for pages in range(33,41):
            # Derive expected result from the measured 1000-cycle layout, then
            # explicitly verify it in the saved run. This is not a universal cap.
            run([9,1000,20,'capacity',192],{'GS_DIAG_PAGES':str(pages),'GS_PEAK':'1'},
                expected=0 if pages>=38 else 2,trace=True)
        for pages in (48,64):
            run([9,1000,20,'capacity',192],{'GS_DIAG_PAGES':str(pages),'GS_PEAK':'1'},trace=True)
    else:
        for records in (384,1776,23232):
            run([7,records,20,'schedule'],trace=True)
        # Previous 10000-cycle heavy result is reused rather than requalified.
        run([9,1000,12],trace=True)
    out.write(f'DIAGNOSTIC_SUITE={args.suite} CHECKS={checks} PASS\n')
print(f'{args.suite}: {checks} checks PASS; {log}')
