# Host-only ESP-IDF NVS runtime probe

This isolated Linux target uses installed ESP-IDF 6.0.3 NVS and the SDK's
emulated flash partition. It does not enter a firmware target. Values are
length-matched dummy blobs, not the frozen codec or an authenticated lifecycle
transaction. `partitions.csv` allocates a 128 KiB test NVS partition only.

The separate `compact` mode now links the native transaction, compact representation,
canonical retirement validation and OpenSSL host crypto to real SDK NVS. Original
dummy-value modes remain unchanged. Its ordinary-flash publication provider is an
explicit **negative candidate** for the native non-rollback authority contract.
SDK PASS does not mean production GO.

Build from this probe directory with ESP-IDF's Linux target:

```sh
source /home/udaybhan/.espressif/v6.0.3/esp-idf/export.sh
idf.py --preview set-target linux
idf.py build
```

The Linux SDK build also needs `libbsd-dev`, `libmd-dev`, and Ruby for its
FreeRTOS mocks. They were staged under `/tmp` for this checkpoint because
system development packages were absent. Those paths are local build inputs,
not production dependencies or repository artifacts. The first configure used
`-DCMAKE_C_FLAGS` and `-DCMAKE_CXX_FLAGS` to add the libbsd include directory
and `-DCMAKE_LIBRARY_PATH` for the staged libraries. Ruby was supplied on
`PATH`, with its extracted `RUBYLIB` and `LD_LIBRARY_PATH`.

From the repository root, run the built binary as follows:

```sh
code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/host/storage/nvs_runtime_probe/build/gs_nvs_runtime_probe.elf 9 10000 12
code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/host/storage/nvs_runtime_probe/build/gs_nvs_runtime_probe.elf 9 1000 20 promotion 32
code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/host/storage/nvs_runtime_probe/build/gs_nvs_runtime_probe.elf 9 1000 20 promotion 192
code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/host/storage/nvs_runtime_probe/build/gs_nvs_runtime_probe.elf 9 50 20 fault 1072
```

Arguments are initial sealed segment count, churn cycles, optional saturation
limit, mode, and mode value (HOT count or fault cut). The last command
intentionally exits nonzero when the report key is absent after remount.
`GCOV_PREFIX` may be set to a unique `/tmp` directory per run to avoid
coverage-file collisions.

See `docs/exec-plans/evidence/R1_STORAGE_NVS_RUNTIME_PROOF_20261008.md` at
the repository root for measurements and proof limits. No compiler output,
`sdkconfig`, or generated image is tracked.

## Focused blocker diagnosis

From repository root run `python3 <this-directory>/run_diagnostics.py fault`,
`capacity`, or `schedule`. The runner records hashes, commands, exit status and
results. Temporary SDK emulator files are removed by the exact child-emitted
path; it never deletes earlier evidence or glob-cleans `/tmp`.

Additional modes: `banks CUT` (independent report and selection keys, then old
retirement); `fault CUT freeze` (latch every later write/erase off until reboot);
`capacity HOT_COUNT` (HOT, seal, next report/root/checkpoint/root coexistence);
`schedule` (cycle-count argument becomes one day's semantic-record count).
`banks CUT resume` deliberately models a one-shot I/O error for comparison.
`GS_RECOVERY_CUT` interrupts the first remount then remounts again.
`GS_DIAG_TRACE=1` prints API/flash/page transitions and raw ret0 indices/chunks.
`GS_PEAK=1` inspects physical entries/pages after each program/erase.
`GS_HOT_BYTES=36/44/124` selects typical/P95/global-max dummy sizes.
`GS_DIAG_PAGES=32..64` passes a copied partition descriptor to IDF in the isolated
Linux image. Its extended area may overlap the unused dummy app; this is not a
production partition layout. CSVs are unchanged.

Existing staged local build environment (reuse; no dependency reinstall):

```sh
export IDF_PATH=/home/udaybhan/.espressif/v6.0.3/esp-idf
export PATH=/tmp/gs-diag-bin:$PATH
export RUBYLIB=/tmp/gs-ruby/usr/lib/ruby/3.3.0:/tmp/gs-ruby/usr/lib/x86_64-linux-gnu/ruby/3.3.0
export LD_LIBRARY_PATH=/tmp/gs-ruby/usr/lib/x86_64-linux-gnu:/tmp/gs-libbsd-dev/usr/lib/x86_64-linux-gnu
cmake --build code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/host/storage/nvs_runtime_probe/build
```

`/tmp/gs-diag-bin/ruby` links to the previously staged ruby3.3. Normal platforms
with Ruby/libbsd installed need no such paths. ASan/UBSan compile the diagnostic
main with sanitizer flags and link against unchanged SDK archives; full commands
are preserved in the sanitizer evidence. SDK internals are not instrumented.
See the focused diagnosis for limits: these values are dummy lengths, credits
and whole authenticated lifecycle transactions are not implemented.

## 72-hour ordinary-motion analysis

`../offline_72h_model.py --output /tmp/gs-72h-cases.json` produces candidate
whole-object ledgers; `../test_offline_72h_model.py` checks semantic/dependency
models. From repository root use `python3 <this-directory>/run_offline.py
--cases /tmp/gs-72h-cases.json --suite capacity`, `schedule`, or `fault`.
`build_host_sanitizer.py --output /tmp/gs-72h-san` instruments the probe main/header;
pass `--binary /tmp/gs-72h-san/probe.elf` to the runner with ASan/UBSan environment.
SDK archives remain uninstrumented.

The new `offline FIXTURE [schedule|fault CUT]` mode uses the same SDK, latch and
synthetic descriptor. Fixtures are regenerated from explicit JSON scenario
parameters, not production serializers. Capacity stops are expected evidence.
Fault tests prime GC then append independent summary/checkpoint/selector before
old-body retirement. The scalar summary model excludes native Node MotionSummary
because its millisecond fields must remain in the frozen exact representation.
See `R1_STORAGE_72H_AGGREGATION_CAPACITY_20261008.md` for the supported model
limits, actual measurement categories and remaining policy/target gates.

## Bounded readiness pressure check

Run `build/gs_nvs_runtime_probe.elf 9 1000 20 progress` after building with the
environment above. This one fixture retains twelve segments, makes three bounded
independent next-report/root attempts, then remounts and verifies all30 pre-existing
dummy blobs byte-for-byte. Expected PASS includes `progress=BLOCKED` and
`ESP_ERR_NVS_NOT_ENOUGH_SPACE`; it proves preservation in this case, not a protected
allocator reserve or production readiness. See
`R1_HUB_STORAGE_IMPLEMENTATION_READINESS_20261008.md` and its focused host log.

## Compact transaction feasibility

After the existing build, run `run_compact.py --suite basic --output /tmp/compact-basic.log`,
`--suite cuts --output /tmp/compact-cuts.log`, or `--suite capacity --output /tmp/compact-capacity.log`.
Use `--case fault 1087 gc` for one targeted cut, `--case cfault 2` for collection,
or `--case rfault 64` for retirement. `--binary` accepts the existing host sanitizer
probe. The capacity suite is four coexistence fixtures (36/448-byte bodies), **not**
the72-hour matrix. Each log includes the executable hash; synthetic48/64-page
descriptors do not modify CSVs. Each child-emitted emulator image alone is removed.

Cuts fork a process sharing the SDK's flash image. On the first injected write/
erase failure the child exits immediately, prohibiting every subsequent simulated
operation. Parent RAM was deinitialized before fork and mounts persisted bytes
afresh. Tests require exact old/new state, credit/report recovery and retry effects.
GC-primed fixtures exercise actual SDK page copying/erases; direct cuts2/1087 hit
erase operations. Collection protects the authenticated selected root's dependencies.
Older candidate banks have no recovery authority.

`rollback` restores an intact older partition after a later successful admission,
demonstrating stale authenticated recovery. `pressure` demonstrates repeated no-ACK
space rejection while preserving an accepted body, plus failed checkpoint progress.
There is **no qualified protected allocator reserve**. Object counts, attempts and
reclamation are bounded, but this is a NO-GO witness, not a deployment provider.
See `docs/exec-plans/evidence/R1_STORAGE_COMPACT_NVS_FEASIBILITY_20261008.md`.
