# Storage-first refinement validation — 2026-10-07

Initial context preflight PASS: local/canonical2026-10-07.001, HEAD94fe1a8.
Qualified isolated core committed as45f6b00. Production firmware/CSV unchanged.
New approved requirements GS-D021/022/023 advance local context to.002; the
canonical branch remains.001. No automatic worktree synchronization or guard
override is authorized. New dependent model implementation must wait for PASS.

Commands run from the code project:

```sh
make storage-efficiency-host-test
make hub-backend-commit-host-test hub-journal-persistence-host-test
python3 -m unittest discover -s tests/python -p test_node_retirement_protocol_model.py
g++ -std=c++17 -O1 -g -Wall -Wextra -Werror -pedantic -fsanitize=address,undefined -fno-omit-frame-pointer -I. tests/cpp/storage_efficiency_validation.cpp -o /tmp/gs-storage-refinement-sanitized
ASAN_OPTIONS=detect_leaks=0 /tmp/gs-storage-refinement-sanitized
```

Results: storage efficiency validation PASS; LONG_RUN_EVENTS=1000000,
LIVE_RECORDS=192, FIXED_RECORD_POOL_BYTES=17088, INDEX_BYTES=12452,
HOT_NEW_ALLOCATIONS=0. ASan/UBSan PASS with leak detection disabled because of
the prior environment ptrace restriction; no LeakSanitizer PASS claimed.
HUB-BACKEND-COMMIT HOST PASS; P2-PERSIST-HUB-JOURNAL HOST PASS capacity=128
full=129 replacement/dedupe/restart/tamper/write-fault/reducer-replay.
Retirement model24 tests PASS. These are existing tests; new coverage/day/GC
fault tests are specified in ExecPlan21.12 but not implemented or claimed PASS.

Static Python arithmetic/path checks PASS: reservation sum131072;
4032//104=38, 11*38=418>=416; 4032//128=31; 4032//320=12;
72h conservative normal allocation122880+ceil(1152/38)*4096=249856,
deficit118784. Checked relative Markdown links in changed domain/context/index/
ExecPlan docs, unique decision IDs and version. git diff --check PASS before
staging. No allocator, cryptographic nonce, wear or physical crash proof.

Build reproduction from repository root, after sourcing installed ESP-IDF6.0.3:

```sh
idf.py -DIDF_TARGET=esp32c3 -DSDKCONFIG=/tmp/gs-r1-storage-c3-sdkconfig -C code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/node/target/esp32c3/idf -B /tmp/gs-r1-storage-c3-build build
cp /tmp/gs-r1-storage-c3-build/gs_hw_m1_node.bin code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/target/esp32/idf/main/node_firmware.bin
idf.py -DIDF_TARGET=esp32 -DSDKCONFIG=/tmp/gs-r1-storage-hub-sdkconfig -C code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/target/esp32/idf -B /tmp/gs-r1-storage-hub-build build
```

Initial Hub configure failed because embedded Node artifact was absent. Initial
Node attempt defaulted toesp32 and was stopped; no resulting binary accepted.
Its newly generated ignored sdkconfig was preserved under/tmp, leaving no wrong-
target SDKCONFIG in the Node source directory. Explicit C3 build PASS:
0xe3650=931408-byte C3 app. Hub embeds this generated ignored artifact; no source
change, hardware or signing/physical qualification is claimed. Defaults retain
4 MB/custom partitions/rollback. HIL build/control options OFF.

Current Hub build PASS, actual app .bin1,864,624 bytes (0x1C73B0); slot1,966,080 (0x1E0000); margin101,456 (0x18C50). ESP-IDF size reports total unpadded image1,864,512; use the actual .bin for margin. Static DRAM45,783 (bss28,080/data17,703), linker-region remaining134,953; IRAM87,359 (text86,331/vectors1,028), remaining43,713. Runtime stack/heap usage is not measured. Bootloader26,304 bytes, margin2,368; partition binary3,072 bytes. Generated table verified all six current CSV entries and end0x400000.

SHA256 artifacts under/tmp/gs-r1-storage-hub-build:

- gs_hw_m1_hub.bin: a7af1113a45c1986855f5f6f5d731c4322f273324fe9743cd2d3a392ca3a3cbe
- partition_table/partition-table.bin: ea9cfa7831ef46afdb5c12299d23e93dc765dcdb796c13994d08d3a16223898a
- bootloader/bootloader.bin: c9d89aba64ed0e06b1dcc286b5259d4ee8dda76d31d6f1a1743a2b75fdcfeb50

Build source45f6b00 with documentation-only dirty worktree; IDF6.0.3 toolchain15.2.0, no experimental core production wiring. `idf.py ... size` and ESP-IDF gen_esp32part.py decode supplied size/table figures. App is not newly signed or physically qualified. Existing repository defaults have platform secure boot/flash encryption disabled; the production-component authenticated storage design is separate and was not weakened. Any changed signing/encryption deployment config needs its own size/alignment check.

Comparison:0x1D0000 OTA slots leave35,920 bytes;0x1C0000 slots fail by29,616. Thus the old384 KiB candidate does not fit this reproduced image. Partition decision stays UNDECIDED; source CSV unchanged. No hardware was opened or used.
