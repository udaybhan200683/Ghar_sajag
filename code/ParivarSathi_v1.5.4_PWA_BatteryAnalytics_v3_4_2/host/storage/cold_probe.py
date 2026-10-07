"""Host-only zlib probe; no proposed production dependency or target RAM claim."""
from pathlib import Path
import statistics
import time
import tracemalloc
import zlib

data = Path('/tmp/gs-density-cold-blocks.trace').read_bytes()
blocks = []
at = 0
while at < len(data):
    count = int.from_bytes(data[at:at + 2], 'big')
    at += 2
    assert 0 < count <= 4096 and at + count <= len(data) and len(blocks) < 12
    blocks.append(data[at:at + count])
    at += count
assert at == len(data) and len(blocks) == 12
packed = [zlib.compress(block, 6) for block in blocks]
assert all(zlib.decompress(item) == block for item, block in zip(packed, blocks))


def median_ns(operation):
    times = []
    for round_number in range(10):
        start = time.perf_counter_ns()
        for i in range(1000):
            operation(i % len(blocks))
        if round_number:
            times.append((time.perf_counter_ns() - start) / 1000)
    return statistics.median(times)


tracemalloc.start()
zlib.compress(blocks[0], 6)
encode_peak = tracemalloc.get_traced_memory()[1]
tracemalloc.stop()
tracemalloc.start()
zlib.decompress(packed[0])
decode_peak = tracemalloc.get_traced_memory()[1]
tracemalloc.stop()
print('COLD_ZLIB_HOST_ONLY blocks=12',
      f'plain_B={sum(map(len, blocks))}',
      f'compressed_B={sum(map(len, packed))}',
      f'with_tag_commit20_B={sum(map(len, packed)) + 240}',
      f'encode_ns={median_ns(lambda i: zlib.compress(blocks[i], 6)):.2f}',
      f'decode_ns={median_ns(lambda i: zlib.decompress(packed[i])):.2f}',
      f'python_traced_encode_peak_B={encode_peak}',
      f'python_traced_decode_peak_B={decode_peak}',
      'TARGET_CODE_RAM_UNKNOWN ROUNDTRIP_PASS')
