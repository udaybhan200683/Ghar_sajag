#!/usr/bin/env python
"""Validate actual S3 partition and OTA readbacks against the approved image."""
from pathlib import Path
import binascii
import csv
import hashlib
import struct

HERE = Path(__file__).parent
READ_TABLE = HERE / "p8_s3_partition_table_read.bin"
ACTUAL_CSV = HERE / "p8_s3_partition_table_actual.csv"
OTA = HERE / "p8_s3_otadata_read.bin"
CANDIDATE_PART = Path("code/build/gs114_fixture_pair/build-snmafa7y/s3/partition_table/partition-table.bin")
APP = Path("code/build/gs114_fixture_pair/build-snmafa7y/s3/gs_r1_s3_hub.bin")
EXPECTED_APP = "f296c984dabda9fe537d2ae1c9d553af55287b5640b0ce34c48527dc50c369a8"

actual_read = READ_TABLE.read_bytes()
candidate_part = CANDIDATE_PART.read_bytes()
assert len(actual_read) == 0x1000
assert len(candidate_part) <= len(actual_read)
assert hashlib.sha256(actual_read[:len(candidate_part)]).digest() == hashlib.sha256(candidate_part).digest()
assert all(value == 0xFF for value in actual_read[len(candidate_part):])
print(f"PARTITION_PREFIX_SHA256={hashlib.sha256(actual_read[:len(candidate_part)]).hexdigest()}")
print("PARTITION_TABLE_BINARY_MATCH=1; padding=0xff")

with ACTUAL_CSV.open(newline="") as f:
    rows = list(csv.reader(line for line in f if not line.lstrip().startswith("#") and line.strip()))
partitions = {}
for row in rows:
    name, kind, subtype, offset, size, *_ = row
    partitions[name] = (kind, subtype, int(offset, 0), size)
for name, wanted in {
    "ota_0": ("app", "ota_0", 0x20000, "4M"),
    "ota_1": ("app", "ota_1", 0x420000, "4M"),
    "gs_outbox": ("data", "littlefs", 0x820000, "4M"),
    "gs_state": ("data", "nvs", 0xC20000, "256K"),
}.items():
    assert partitions.get(name) == wanted, (name, partitions.get(name), wanted)
print("PARTITION_LAYOUT=PASS ota_0@0x20000 ota_1@0x420000 gs_outbox@0x820000 gs_state@0xc20000")

ota_data = OTA.read_bytes()
assert len(ota_data) == 0x2000
valid = []
for index in range(2):
    start = index * 0x1000
    seq = struct.unpack_from("<I", ota_data, start)[0]
    stored_crc = struct.unpack_from("<I", ota_data, start + 28)[0]
    state = struct.unpack_from("<I", ota_data, start + 24)[0]
    calc_crc = binascii.crc32(struct.pack("<I", seq), 0xFFFFFFFF) & 0xFFFFFFFF
    is_valid = seq != 0xFFFFFFFF and stored_crc == calc_crc
    print(f"OTA_COPY={index} seq=0x{seq:08x} state=0x{state:08x} stored_crc=0x{stored_crc:08x} calc_crc=0x{calc_crc:08x} valid={int(is_valid)}")
    if is_valid:
        valid.append((seq, index, (seq - 1) % 2))
assert valid, "STOP: no valid OTA selector copy"
seq, index, ota_id = max(valid)
selected = f"ota_{ota_id}"
print(f"OTA_SELECTOR_COPY={index} seq={seq} SELECTED={selected}")
assert selected == "ota_0", f"STOP: selector chose {selected}, not ota_0"
assert partitions[selected][2] == 0x20000
app_sha = hashlib.sha256(APP.read_bytes()).hexdigest()
print(f"APP_SHA256={app_sha}")
assert app_sha == EXPECTED_APP
print("INSTALL_PRECONDITIONS=PASS; approved single app-only write target=0x20000")
