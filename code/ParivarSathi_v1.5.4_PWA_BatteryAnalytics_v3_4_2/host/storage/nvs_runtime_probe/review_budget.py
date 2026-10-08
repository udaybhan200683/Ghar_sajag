#!/usr/bin/env python3
"""Derived dummy-object ledger and temporary partition review; no CSV mutation."""
from math import ceil
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[5]
IDF = Path('/home/udaybhan/.espressif/v6.0.3/esp-idf')
PYTHON = '/home/udaybhan/.espressif/python_env/idf6.0_py3.14_env/bin/python'

def entries(size):
    return ceil(size / 32) + ceil(size / 4000) + 1

base = dict(certificates=3 * entries(4079), reports=3 * entries(3485),
            state=3 * entries(6144), roots=2 * entries(512),
            metadata=2 * entries(4096), critical=2 * entries(4096),
            backend_history=9 * entries(4096), namespace=1)
cow = entries(3485) + entries(6144) + 2 * entries(512)
for size in (36, 44, 124):
    hot = 192 * entries(size)
    used = sum(base.values()) + hot + cow
    pages = ceil(used / 126) + 1
    print(f'DERIVED hot_size={size} components_entry_bytes={ {k:v*32 for k,v in base.items()} } '
          f'hot_bytes={hot*32} cow_bytes={cow*32} '
          f'page_metadata={(pages-1)*64} gc_bytes=4096 '
          f'tail_rounding={pages*4096-used*32-(pages-1)*64-4096} '
          f'minimum_partition={pages*4096} deficit={pages*4096-131072}')
print('BOUNDARY=entry/page lower bounds only; fragmentation, authenticated grammar and product policy unproven')
source = ROOT / 'code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/target/esp32/idf/partitions.csv'
prefix = source.read_text().split('ota_0,')[0]
layouts = {
    128: ((0x20000, 0x1E0000), (0x200000, 0x1E0000), (0x3E0000, 0x20000)),
    192: ((0x20000, 0x1E0000), (0x200000, 0x1D0000), (0x3D0000, 0x30000)),
    256: ((0x20000, 0x1D0000), (0x1F0000, 0x1D0000), (0x3C0000, 0x40000)),
}
with tempfile.TemporaryDirectory(prefix='gs-nvs-layout-review-') as directory:
    for size, rows in layouts.items():
        p = Path(directory) / f'{size}.csv'
        kinds = ('ota_0,app,ota_0', 'ota_1,app,ota_1', 'gs_journal,data,nvs')
        p.write_text(prefix + '\n'.join(f'{kind},0x{offset:X},0x{length:X}'
                     for kind, (offset, length) in zip(kinds, rows)) + '\n')
        cmd = [PYTHON, str(IDF / 'components/partition_table/gen_esp32part.py'),
               '--flash-size', '4MB', str(p), str(p.with_suffix('.bin'))]
        r = subprocess.run(cmd, capture_output=True, text=True)
        print('COMMAND=' + ' '.join(cmd) + '\nEXIT=' + str(r.returncode))
        print(p.read_text(), r.stdout, r.stderr)
        assert r.returncode == 0
        print(f'LAYOUT storage_kib={size} ota_sizes={rows[0][1]},{rows[1][1]} '
              f'current_image=1864624 limiting_margin={min(rows[0][1], rows[1][1])-1864624}')
print('PARTITION_REVIEW_PASS temporary layouts only; current image evidence reused, no integrated image qualification')
