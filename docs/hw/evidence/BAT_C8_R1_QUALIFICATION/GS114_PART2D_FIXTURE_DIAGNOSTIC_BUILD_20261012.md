# GS-114 Part 2D — Fixture-Compatible S3 RPF Diagnostic Build

Date: 2026-10-12
Authorization: GS-114 Jira comment 10507
Source HEAD at build: `e31e8ef6314abcc777eb5979c3d33939cdb7b296`
Worktree: canonical `feature/r1-commercial-baseline`
Source fingerprint: `f54e3162160d4f9e96a61ed60575f434c2a33c73a866b85789cd5bce610e0dce`

## Result

The fixture-compatible S3 diagnostic application built successfully with
ESP-IDF 6.0.3. The binary is a standalone S3 application only; no image was
installed and no device interface was accessed. GS-114 remains physical
`NO-GO` until replay-fence admission and observation safety are verified on the
approved fixture and the real PIR-to-Durable-ACK chain is observed.

## Reproducible build and artifact

Command:

```sh
make gs114-s3-rpf-diagnostic-build
```

Run from `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/`. The successful
report is the ignored local build artifact:

```text
build/gs114_fixture_pair/build-kvi2pcxe/fixture_pair_report.json
```

The S3 application is:

```text
build/gs114_fixture_pair/build-kvi2pcxe/s3/gs_r1_s3_hub.bin
```

| Property | Verified build result |
|---|---|
| Image | ESP32-S3 application, project `gs_r1_s3_hub` |
| App bytes | 1,879,392 |
| SHA-256 | `48d08726d3acb686466fc8ef056609efe2b0148719ea89943bbe3e48a72c1f09` |
| App version | `e31e8ef6314a-gs114-rpfdiag-f54e` |
| ESP-IDF | v6.0.3 |
| Configured flash | 16 MiB, DIO, 40 MHz |
| PSRAM | Octal, 40 MHz |
| OTA slot | 4,194,304 bytes |
| Free slot capacity | 2,314,912 bytes |
| Embedded paired C3 asset | 939,024 bytes; SHA-256 `dd33f634f667b99b253eb657b51bf13954e0dd971ce355a318fe2dadda6e6a04` |
| Target verification | `STANDALONE_APP_BUILT_NOT_INSTALLED` |

The successful JSON report contains the complete `esptool image-info` output,
build logs, CMake flags, sdkconfig selections, partition rows and image hashes.
The candidate partition CSV SHA-256 is
`e3198d7d83f9c7661d3129c1411162ff6c5c216699a52f3640daeb441b3d4b1e`; the
compiled partition-table SHA-256 is
`bb0066feee7368e621c6f0f0d7bfdf47cbc5bbbf4cfdd9eccab9525ad683f82a`. The
compiled table decoded with ESP-IDF's partition utility and matched the CSV.

## Reconstructed Part 1 fixture profile

The saved Part 1 S3 `CMakeCache.txt` and sdkconfig establish the previous
build profile: `GS_HIL_BUILD=OFF`, `GS_HIL_CONTROL=OFF`,
`GS_HIL_COMMISSIONING=ON`, and `GS_S3_DIAGNOSTIC_ONLY=OFF`, with
`sdkconfig.defaults` plus `sdkconfig.defaults.outbox`. The selected table is
`partitions.s3-outbox-candidate.csv`:

| Partition | Type/subtype | Offset | Size |
|---|---|---:|---:|
| `ota_0` | app/ota_0 | `0x20000` | 4 MiB |
| `ota_1` | app/ota_1 | `0x420000` | 4 MiB |
| `gs_outbox` | data/LittleFS | `0x820000` | 4 MiB |
| `gs_state` | data/NVS | `0xC20000` | 256 KiB |

This is the same candidate layout reconstructed for the Part 1 disposable
fixture; it is not commercial capacity qualification or proof of the current
physical flash contents. S3 `GS_HIL_BUILD` and `GS_HIL_CONTROL` are rejected by
the target CMake configuration. Fixture commissioning stays explicitly
opt-in, default-off, and mutually excluded from the diagnostic-only build.

The new S3 image contains the RPF00–RPF08 stage strings and the sanitized
`S3 replay fence failed stage=%s` log format. Its exact fixture commissioning
strings are present. The compiled S3 profile has broad `GS_HIL_CONTROL=OFF`;
the S3 runtime portion of the application has no `INJECT_MOTION`,
`START_C3_FOTA`, or `HIL_GPIO` marker. The combined S3 application embeds its
paired C3 image, where the token `INJECT_MOTION` exists only with the
`disabled_for_physical_wake` error string; the success string is absent. The
build verifier checks the embedded C3 asset byte-for-byte and scans S3 runtime
bytes separately. The C3 output is only the S3 embedded asset, not a separate
deployment recommendation.

No production runtime, ownership, storage format, replay-fence ordering, ACK,
or event-admission behavior was changed in Part 2D. RPF diagnostics remain
fail-closed. The firmware is a disposable engineering fixture profile, not a
commercial release image: generated sdkconfig has secure boot, flash
encryption and app anti-rollback disabled. Device eFuses and current physical
security state were not inspected.

## Offline artifact comparison and provenance limits

| Baseline | Offline evidence | Compatibility result |
|---|---|---|
| A. Part 1 commissioned-fixture build | `physical_results.json` records source `73e1e842…`, IDF 6.0.3, S3 app hash `f9608d77230f136abea5794329c1a98be4062419383a1a6dbbfd29a6c793a2d1`, 1,877,344 bytes, commissioning-only, candidate outbox/state layout. The retained local binary has the same hash. Flash readback was not verified. | Candidate profile established; installed image remains **UNKNOWN**. |
| B. Earlier GS-148 diagnostic build | Build report source `abacd8ce…`, IDF 6.0.3, S3 hash `3a432fa7bd671e91cb6b4f93d437f81b0892aa878ad5e4173e196fb4623f098a`, 1,870,944 bytes; commissioning OFF and `partitions.development.csv` selecting `gs_journal` rather than `gs_outbox`/`gs_state`. | **INCOMPATIBLE** with the Part 1 fixture profile. Its RPF strings do not remedy the profile mismatch. |
| C. Part 2D fixture-compatible diagnostic app | Current source HEAD/fingerprint and hashes above; commissioning ON, broad S3 HIL controls OFF, outbox/state candidate table, RPF00–RPF08 present. | Software build/profile checks **PASS**. Physical installation and state interpretation remain **UNKNOWN/BLOCKED**. |

The retained Part 1 `fixture_pair_report.json` at the same output paths contains
earlier C3/S3 hashes (`003d9f4f…` / `638f646b…`, S3 size 1,881,792 bytes),
while the later retained binaries match the hashes recorded by
`physical_results.json`. Its manifest is therefore stale relative to those
same-path files. Neither record is flash readback; this discrepancy is
preserved rather than silently reconciled into proof of the running image.

Offline source/tool inspection confirms the Hub has no active S3 OTA receiver.
ESP-IDF provides an `app-flash` target for the configured default application
partition, but its generated command can reset the target and does not prove
which slot is active on the fixture. The device's actual partition table,
bootloader, selected OTA slot, eFuse state, image hash, NVS/LittleFS contents,
pairing/session state and stored EventKeys remain unknown. The new firmware can
run replay-fence reconciliation/publication on boot, so writing only the app
partition does **not** prove persistent-state preservation. An old app alone
does not prove safe rollback against state written by the new app. No
state-preserving install/rollback path is demonstrated; deployment is
`BLOCKED` pending separate physical provenance and preservation review and
specific installation authorization.

## Validation

| Command/check | Result |
|---|---|
| `make gs114-s3-rpf-diagnostic-build` | **PASS**, exit 0; clean C3 asset and S3 ESP-IDF builds, image-info, configuration/partition/marker checks, JSON report emitted. |
| `make s3-fixture-commissioning-test` | **PASS**, 9/9 tests, exit 0. |
| `make validation-framework-test` | **PASS**, 39/39 integrity tests, exit 0. The fixture stage was also directly confirmed in Node/Hub/contract/fast/release registry selection. |
| `make -j2 hub-runtime-checkpoint-host-test hub-retirement-snapshot-host-test hub-durable-storage-host-test hub-fresh-install-host-test rejoin-host-test association-host-test node-retirement-protocol-host-test` | **PASS**, exit 0 across seven focused targets. |
| `python3 -m py_compile scripts/build_gs114_fixture_pair.py tests/python/test_s3_fixture_commissioning.py` | **PASS**, exit 0. |
| Compiled partition decode vs fixture CSV | **PASS**, all required table rows matched. |

During focused development, an initial artifact check correctly exposed that
the embedded C3 image contains an `INJECT_MOTION` token; the validator was
narrowed to prove exact embedded-asset provenance, verify the physical-wake
guard and reject the token in S3 runtime bytes. A subsequent fully compiled
attempt exposed IDF partition-size suffixes (`24K`); the parser and regression
were fixed. The final clean build and report then passed. These were build
verification defects, not runtime test failures. The historical
`hub-journal-migration-host-test` failure at
`tests/cpp/hub_journal_migration_validation.cpp:194` was not rerun or altered;
it remains an independent known failure. No sanitizer was rerun because Part
2D changed no C++ runtime/security/storage source; prior GS-148 host evidence
does not substitute for physical qualification.

No full `validation-fast`, release gate, backend/PWA suite or physical HIL was
run. No USB, serial, board, actual NVS/LittleFS or hardware state was accessed.

## Readiness and next gate

- S3 diagnostic artifact: built and locally available; **not installed**.
- Fixture storage/profile match: verified for the build candidate, not the
  physical device.
- Replay-fence physical failure cause: still unknown until RPF diagnostics can
  be observed safely on the fixture.
- Installation, persistent-state preservation and rollback: **BLOCKED**; need
  a separate, exact user authorization after reviewing target-state evidence
  and a non-destructive preservation/recovery plan.
- GS-114 physical qualification: **NO-GO**. After separately authorized safe
  deployment and reset-safe observation are established, first verify
  admission/RPF00 without clearing state; only then schedule the separately
  prompted real AM312 → GPIO4 → EventKey → authenticated S3 durable commit →
  matching ACK → exact Node retirement test.
- Physical qualification and commercial release: **NOT_RUN / NOT_APPROVED**.

No Jira workflow state changed. GS-114 remains In Progress; GS-148 remains
OnHold. See also the [GS-148 replay-fence diagnostic](../../../exec-plans/evidence/R1_GS148_REPLAY_FENCE_DIAGNOSTIC_20261012.md)
and [Part 2C approval-gated deployment plan](GS114_PART2C_DIAGNOSTIC_DEPLOYMENT_PLAN_20261012.md).
