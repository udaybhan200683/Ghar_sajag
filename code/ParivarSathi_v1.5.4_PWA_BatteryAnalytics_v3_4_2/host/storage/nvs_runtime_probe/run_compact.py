#!/usr/bin/env python3
"""Bounded real-SDK transaction checks; removes only each child's scratch image."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--suite', choices=('basic', 'cuts', 'capacity'), default='basic')
parser.add_argument('--binary', type=Path, default=HERE/'build/gs_nvs_runtime_probe.elf')
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--case', nargs='+', help='One targeted compact mode and arguments')
args = parser.parse_args()
binary = args.binary.resolve()
with args.output.open('w') as log:
    def emit(text):
        print(text, file=log, flush=True)
    emit('SDK=ESP-IDF6.0.3 commit76f5dedd9950a3012fee8fb7d5586df21fc67802')
    emit('BINARY_SHA256='+hashlib.sha256(binary.read_bytes()).hexdigest())
    cases = [('basic',), ('damage',), ('missing',), ('child',), ('head',), ('rollback',), ('pressure',)]
    if args.suite == 'cuts':
        cases = [(mode, str(cut), *extra)
                 for mode, extra, cuts in (
                     ('fault', (), range(0, 1601, 32)),
                     ('rfault', (), range(0, 321, 8)),
                     ('cfault', (), (0,1,2,3,4,8)),
                     ('fault', ('gc',), range(0, 2401, 64)))
                 for cut in (*cuts, 999999)]
    if args.suite == 'capacity':
        cases = [(str(pages), str(body)) for pages, body in ((32,36),(32,448),(48,448),(64,448))]
    if args.case:
        if args.suite == 'capacity':
            parser.error('--case uses basic/cuts, not the capacity suite')
        cases = [tuple(args.case)]
    for case in cases:
        env = os.environ.copy()
        with tempfile.TemporaryDirectory(prefix='gs-compact-gcov-') as scratch:
            env['GCOV_PREFIX'] = scratch
            env['GS_PEAK'] = '1'
            if args.suite == 'capacity':
                env['GS_DIAG_PAGES'] = case[0]
                command = [str(binary), 'compact', 'capacity', case[1]]
            else:
                command = [str(binary), 'compact', *case]
            emit('COMMAND='+' '.join(command))
            result = subprocess.run(command, cwd=HERE, env=env, capture_output=True, text=True, timeout=60)
            emit(result.stdout.rstrip())
            emit(result.stderr.rstrip())
            emit('EXIT='+str(result.returncode))
            for name in re.findall(r'^EMULATOR_IMAGE=(/tmp/idf-partition-[A-Za-z0-9]+)$', result.stderr, re.M):
                Path(name).unlink(missing_ok=True)
            if result.returncode:
                raise SystemExit(result.returncode)
    emit('COMPACT_SUITE_PASS cases='+str(len(cases)))
print('LOG='+str(args.output))
