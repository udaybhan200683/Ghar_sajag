#!/usr/bin/env python3
"""HOST ONLY fresh-format image occupancy using installed official IDF generator.
Not the runtime NVS allocator, GC, flash encryption or power-failure testing.
Run: python3 host/storage/nvs_physical_probe.py --idf-python <IDF venv python>
"""
import argparse
import csv
import hashlib
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--idf-python', required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='gs-nvs-physical-') as directory:
        base = Path(directory)
        for segments in (7, 8, 9):
            rows = [['key', 'type', 'encoding', 'value'], ['life', 'namespace', '', '']]
            for name, size, count in [('cert', 4079, 6), ('ret', 3485, 3),
                                     ('state', 6144, 3), ('root', 512, 2),
                                     ('meta', 4096, 2), ('crit', 4096, 2),
                                     ('seg', 4096, segments)]:
                for index in range(count):
                    path = base / f'{name}{index}.blob'
                    path.write_bytes(bytes([index + 1]) * size)
                    rows.append([f'{name}{index}', 'file', 'binary', str(path)])
            source = base / f'{segments}.csv'
            with source.open('w', newline='') as stream:
                csv.writer(stream).writerows(rows)
            minimum = None
            failed = []
            for pages in range(26, 32):
                image = base / 'image.bin'
                result = subprocess.run([args.idf_python, '-m', 'esp_idf_nvs_partition_gen',
                                         'generate', str(source), str(image), str(4096 * pages)],
                                        capture_output=True, text=True)
                if result.returncode:
                    # Only capacity failure is acceptable; tool errors are not evidence.
                    output = result.stdout + result.stderr
                    if 'InsufficientSizeError' not in output and 'Size of partition is less' not in output:
                        raise RuntimeError(output)
                    failed.append(pages)
                    continue
                minimum = pages
                raw = image.read_bytes()
                assert len(raw) == pages * 4096
                used = 0
                allocated = 0
                for offset in range(0, len(raw), 4096):
                    page = raw[offset:offset + 4096]
                    if page == b'\xff' * 4096:
                        continue
                    allocated += 1
                    bitmap = int.from_bytes(page[32:64], 'little')
                    used += sum(((bitmap >> (2 * entry)) & 3) == 2 for entry in range(126))
                # Generator includes one internal empty page. Add only the two
                # APPLICATION COW scratch pages + one engineering page (3).
                print(f'NVS_GENERATOR segments={segments} minimum_image_pages={pages} '
                      f'allocated_pages={allocated} used_entries={used} '
                      f'lower_bound_entries={2265 + segments * 131} '
                      f'additional_reserved_pages=3 total_bytes={(pages + 3) * 4096} '
                      f'margin={131072 - (pages + 3) * 4096} rejected_pages={failed} '
                      f'image_sha256={hashlib.sha256(raw).hexdigest()}')
                break
            assert minimum is not None
        print('NVS_FRESH_IMAGE_PROBE_PASS dummy-value-lengths only; no runtime/GC proof')


if __name__ == '__main__':
    main()
