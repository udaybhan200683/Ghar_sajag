# Host-only ESP-IDF NVS runtime probe

This isolated Linux target uses installed ESP-IDF 6.0.3 NVS and the SDK's
emulated flash partition. It does not enter a firmware target. Values are
length-matched dummy blobs, not the frozen codec or an authenticated lifecycle
transaction. `partitions.csv` allocates a 128 KiB test NVS partition only.

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
