#!/usr/bin/env python3
"""Three frozen size fixtures and aligned partition proposals; no target writes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--idf', type=Path, required=True)
parser.add_argument('--image', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--binary', type=Path, default=HERE/'build/gs_nvs_runtime_probe.elf')
args = parser.parse_args()
image = args.image.read_bytes()
fixtures = HERE/'flash_review_fixtures.json'
with args.output.open('w') as log, tempfile.TemporaryDirectory(prefix='gs-flash-review-') as directory:
    def emit(value):
        print(value, file=log, flush=True)

    emit('IMAGE_BYTES='+str(len(image)))
    emit('IMAGE_PATH='+str(args.image))
    emit('IMAGE_SHA256='+hashlib.sha256(image).hexdigest())
    emit('FIXTURES_SHA256='+hashlib.sha256(fixtures.read_bytes()).hexdigest())
    emit('SDK_BINARY_SHA256='+hashlib.sha256(args.binary.read_bytes()).hexdigest())
    # App offsets/sizes aligned to 64 KiB; data aligned to 4 KiB.
    # Explicit proposals, not changes to the production CSV/configuration.
    layouts = [('4MB_current',4,0x1e0000,0x20000),
               ('4MB_512K_witness',4,0x1b0000,0x80000),
               ('8MB_1M_option',8,0x300000,0x100000),
               ('8MB_recommended',8,0x280000,0x200000),
               ('16MB_comparison',16,0x300000,0x800000)]
    for name, flash, slot, journal in layouts:
        ota0 = 0x20000
        ota1 = ota0+slot
        storage = ota1+slot
        end = storage+journal
        assert end <= flash*1024*1024
        csv = ("nvs,data,nvs,0x9000,0x6000\n"
               "otadata,data,ota,0xf000,0x2000\n"
               "phy_init,data,phy,0x11000,0x1000\n"
               f"ota_0,app,ota_0,{ota0:#x},{slot:#x}\n"
               f"ota_1,app,ota_1,{ota1:#x},{slot:#x}\n"
               f"gs_journal,data,nvs,{storage:#x},{journal:#x}\n")
        path = Path(directory)/(name+'.csv')
        path.write_text(csv)
        command = ['python3', str(args.idf/'components/partition_table/gen_esp32part.py'),
                   '--flash-size', str(flash)+'MB', '--secure', 'v1', str(path), str(path.with_suffix('.bin'))]
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        emit('LAYOUT='+json.dumps({'name':name,'flash_bytes':flash*1024*1024,
             'ota_slot_bytes':slot,'journal_bytes':journal,'image_margin':slot-len(image),
             'spare_bytes':flash*1024*1024-end,'ota0':hex(ota0),'ota1':hex(ota1),
             'journal_offset':hex(storage),'image_fits':len(image)<=slot}))
        emit(csv.rstrip())
        emit(result.stdout.rstrip()); emit(result.stderr.rstrip())
        emit('PARTITION_TOOL_EXIT='+str(result.returncode))
        assert result.returncode == 0
        # --secure v1 validates layout alignment, NOT firmware signatures.
    for row in json.loads(fixtures.read_text()):
        sizes = [size for size,count in row['object_size_runs'] for _ in range(count)]
        f = Path(directory)/'fixture.txt'
        f.write_text(' '.join(map(str,(row['history_segments'],row['cow_segments'],
                     2*row['reserve_events']//32,row['inputs'])))+'\n'+
                     '\n'.join(map(str,sizes))+'\n')
        emit('CASE='+json.dumps({k:v for k,v in row.items() if k!='object_size_runs'}))
        emit('LOGICAL_OBJECT_BYTES='+str(sum(sizes)))
        emit('FIXTURE_SHA256='+hashlib.sha256(f.read_bytes()).hexdigest())
        env = os.environ.copy()
        env['GS_DIAG_PAGES']=str(row['pages']); env['GS_PEAK']='1'
        env['GS_EMULATOR_FLASH_BYTES']='4194304'
        env['GCOV_PREFIX']=directory
        command = [str(args.binary.resolve()),'offline',str(f)]
        result = subprocess.run(command, cwd=HERE, env=env, text=True, capture_output=True, timeout=60)
        emit(result.stdout.rstrip()); emit(result.stderr.rstrip())
        emit('SDK_EXIT='+str(result.returncode))
        for name in re.findall(r'^EMULATOR_IMAGE=(/tmp/idf-partition-[A-Za-z0-9]+)$',result.stderr,re.M):
            Path(name).unlink(missing_ok=True)
        assert result.returncode == 0 and 'OFFLINE_PASS' in result.stdout
    emit('FLASH_REVIEW_PASS layouts=5 capacity_fixtures=3')
    emit('BOUNDARY=length-matched objects; not authenticated 72h storage or target qualification; dummy emulator app unused')
print('LOG='+str(args.output))
