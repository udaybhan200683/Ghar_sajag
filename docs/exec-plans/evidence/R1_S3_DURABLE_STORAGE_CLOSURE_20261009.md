# R1 S3 durable-storage closure checkpoint — 2026-10-09

## Result

**STORAGE_CLOSURE=BLOCKED.** The S3 product build succeeds and the existing
authenticated NVS durability owner is compiled into the Hub runtime, but the
runtime still has a fixed 128-event journal. The compact host representation is
not integrated into the target lifecycle, and the protected-NVS SDK evidence
does not establish sustained reserve restoration. The locked 72-hour target
therefore has no evidence-backed S3 closure.

No product source, partition, Node, BAT-C8, or hardware data was changed. The
connected board was not flashed. The old storage worktree was used only as
read-only historical evidence; its protected `prompt.txt` was not accessed.

## Reproducible checks

Start commit: `5d4c58df70bfe6ae69b11d2600865e8826e64a4c`, branch
`feature/r1-s3-hub-bringup`, context `2026-10-09.001`; context preflight PASS.

The clean ESP-IDF 6.0.3 build used an isolated `/tmp` output and sdkconfig:

```text
source /home/udaybhan/.espressif/v6.0.3/esp-idf/export.sh
idf.py -C code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/hub/target/esp32s3/idf \
  -B /tmp/ghar-sajag-s3-storage-clean-build \
  -D SDKCONFIG=/tmp/ghar-sajag-s3-storage-sdkconfig \
  -D IDF_TARGET=esp32s3 build size
```

Build PASS. The target image is 1,791,792 bytes; ESP-IDF reports 1,791,673
bytes total image sections (the `.bin` includes image padding). The development
CSV gives each OTA slot 4,194,304 bytes, leaving 2,402,512 bytes from the
measured `.bin`. This is a development layout, not a commercial partition or
72-hour capacity qualification. `idf.py size` reports Flash Data 1,040,172 B,
Flash Code 653,952 B, DIRAM 107,633 B (including 60,167 B text, 26,504 B BSS,
20,962 B data), IRAM 16,384 B, RTC slow 36 B and RTC fast 24 B. These are link
measurements, not runtime heap/stack qualification. The ELF is 18,721,728 B and
the map is 10,216,053 B. Kconfig emitted non-fatal bool-default notices for
ESP-IDF NimBLE/FATFS symbols; no compile or link errors occurred.

The host regression command exited 0:

```text
make hub-durable-storage-host-test hub-fresh-install-host-test \
  hub-durable-provider-host-test hub-journal-persistence-host-test \
  hub-backend-commit-host-test hub-recovery-scheduling-host-test \
  registry-host-test registry-persistence-host-test \
  node-retirement-protocol-host-test hub-retirement-snapshot-host-test \
  storage-native-transaction-host-test storage-compact-representation-host-test
```

All requested targets passed, including durable owner/provider and restart
regressions, the 128-record journal/dedupe test, registry and retirement
protocol/snapshot tests, native Gate A/B crash/recovery checks, and compact
representation/protected-plan checks. The native transaction output explicitly
reports `gate_A=PASS_DEFINED_SCOPE`, `gate_B=PASS_WITH_TRUSTED_AUTHORITY`,
`gate_C=OPEN`; compact tests are host evidence and do not qualify target NVS
GC/replenishment. No physical product tests or sanitizers were run in this
checkpoint.

## Implementation findings

- `firmware/hub/target/esp32/hub_runtime_adapter.cpp` initializes
  `NvsDurableBlobStore`, recovers `HubDurabilityOwner`, binds it to `HubRuntime`,
  restores the journal before admission, and processes the event before
  constructing/sending the ACK. The existing path preserves fail-closed owner
  recovery and durable-before-ACK in its implemented scope.
- `firmware/hub/target/esp32/nvs_durable_blob_store.cpp` maps that store to the
  `gs_journal` NVS partition, validates object bounds and verifies write/readback.
- `firmware/hub/components/storage/durable_journal_slot_store.cpp` rejects
  slots above 127; `durable_transition.cpp` recovers legacy slots 0–127; the
  production runtime constructs `HubRuntime(32, 128)`. These are concrete
  limits in the currently built composition.
- `host/storage/compact_nvs_representation.*` and
  `host/storage/native_transaction.*` are not wired into the ESP-IDF target
  CMake/runtime as the scalable lifecycle. Host Gate A/B proofs depend on their
  stated owner/report and independent publication-authority assumptions.
- Earlier 72-hour evidence models NORMAL mixed at 282,624 B protected peak and
  HIGH mixed at 745,472 B. These are frozen host fixture results, not accepted
  operational workload guarantees. The active 128-slot runtime cannot claim
  those histories; increasing the 2 MiB development partition does not remove
  the record bound or prove reserve progress.
- Gate C proves bounded protected operations or safe rejection in its tested
  SDK envelope. It does not prove erased-workspace restoration or repeated
  offline/online admission cycles. Internet outage provides no backend ACK, so
  cloud-dependent body retirement cannot be assumed during the 72-hour interval.
- The exact supported 72-hour volume, critical-event classification/reserve,
  saturation behavior, and any summary/coverage/backfill contract remain open.
  The current exact-event backend path does not provide a qualified replacement
  contract for discarding unsynchronized event identities or summaries.

## Physical-test boundary and remaining gates

The existing `partitions.development.csv` is unsafe to apply to the preserved
board data as-is: its `nvs` partition is at `0x9000`, where existing NVS resides;
`ota_0` (`0x20000`–`0x420000`) and `ota_1` (`0x420000`–`0x820000`) overlap the
previously preserved 6 MiB VFS range (`0x200000`–`0x800000`). Product startup
also initializes NVS. No region-preserving map and restore procedure for this
image/layout was qualified here, so no flash write or repartition was attempted.
The C3 and its seven old-Hub retained events were not accessed.

Remaining release gates are: integrate a bounded target lifecycle instead of
the fixed 128-slot composition; prove protected reserve restoration and
dependency-safe sustained reclamation; resolve supported volume/critical
saturation and offline representation/backfill semantics; validate NORMAL and
HIGH 72-hour fixtures against that implementation; qualify restart/power loss,
durable ACK, dedupe, storage-full and reconnect catch-up on target; and measure
full-runtime internal heap, PSRAM use, stack high-water marks, storage timing,
signed dual-OTA/FOTA rollback and storage-schema compatibility. The existing
NVS/VFS preservation constraint must be resolved before physical flash testing.

The next action is a product decision that bounds the supported 72-hour event
volume and critical saturation/retention contract, including what exact offline
information must be replayed to the backend. Only then can the target lifecycle
and capacity be completed without inventing product behavior. BAT-C8 was not
started.
