# GS-152 Repository Restructure — Baseline and Migration Evidence

**Date:** 2026-10-11
**Baseline source HEAD:** `09bc8cd8b7baab0674bbe03157b7b50bab28e51e`
**Isolated branch:** `feature/r1-gs152-repository-refactor`
**Physical hardware:** NOT USED

## Scope and source inventory

The active version-stamped source wrapper contained application code, firmware,
host support, tests, validation, tools, packaging and generated outputs. The
source move map contains 499 tracked entries with their pre-move SHA-256:
[`GS152_SOURCE_MOVE_MAP_20261011.csv`](GS152_SOURCE_MOVE_MAP_20261011.csv).
Each tracked file was relocated to a stable responsibility path. Generated
baseline outputs were retained in the `gs152-baseline-09bc8cd8b7baab06`
subdirectories and excluded from post-migration validation claims.

The firmware functional grouping moves preserve ESP-IDF project roots and
component discovery boundaries. The backend package and existing PWA feature
modules remain cohesive to avoid a non-mechanical import/API redesign.

## Pre-migration validation

These commands ran at the verified baseline before source relocation, from the
canonical suite entry points in the isolated worktree. Logs are retained under
`/tmp/gs152-baseline/` during this execution and must not be treated as
post-migration proof.

| Command | Duration | Exit | Baseline result |
|---|---:|---:|---|
| `make validation-node` | 288.72 s | 2 | FAIL. Node component stages largely passed; `health-config` had four simulator executable `FileNotFoundError` errors because the simulator target was not built first; P0 browser step could not find the baseline Playwright binary. |
| `make validation-hub` | 300.074 s | 2 | FAIL. Same `health-config` and missing Playwright setup failures; mandatory `hub-journal-migration-host-test` also fails at `tests/cpp/hub_journal_migration_validation.cpp:194`, assertion `clean migration commits`. This is the known GS-148 historical baseline failure. |
| `make validation-contract` | 214.309 s | 2 | FAIL. Same `health-config` and missing Playwright setup failures. |

The migration assertion was already present on the pre-GS-40 baseline and is
not part of GS-152. It remains mandatory and is not skipped or weakened.
Baseline component outputs and the source revision are retained under
`code/build/gs152-baseline-09bc8cd8b7baab06/` and corresponding evidence/log
directories, but are not accepted as post-move validation.

## Migration checks

- Active wrapper path removed: PASS (no directory remains).
- Exact tracked relocation inventory: 499 entries recorded.
- Root Makefile delegates to stable `code/` source root.
- Firmware target project roots and partition/configuration files remain in
  their target directories.
- Historical source-release and source-tree documentation are archived without
  editing their original contents. Historical physical evidence retains its
  as-run path/provenance; current runnable qualification plan paths are updated
  separately where needed.
- No hardware, USB, serial, erase, reset, provisioning or storage operation was
  performed.

Post-migration commands, outcomes and source fingerprint will be appended after
the focused and affected-suite validation completes.

## Resumption and final verification — 2026-10-12

The source move map was independently rechecked against baseline `HEAD`:

| Check | Result |
|---|---|
| Mapping entries | 499 |
| Baseline SHA-256 mismatches | 0 |
| Missing destinations | 0 |
| Byte-identical destinations | 374 |
| Path/build/documentation-adapted destinations | 125 |
| Active version-stamped source wrapper | Absent |
| Archived release manifest | Byte-identical to baseline (`dba3305a4542eaecf3a337adc61ea9cbe9bb4e2c28b0592da7a637ec866b7fb3`) |

The earlier `HISTORICAL_MANIFEST_UNCHANGED=0` diagnostic was not evidence of a
manifest edit. Its `0` came from the `git diff --quiet` success convention; the
independent byte comparison and recorded source-map hash both confirm that
`docs/archive/source-release-v1.5.4/RELEASE_MANIFEST.json` retains its original
20,396 bytes. Historical reports which mention the old source path remain
unchanged and retain their as-run provenance. A scan of active source/build
files found no reference to the removed wrapper; remaining matches are in
historical reports, the migration map and this layout explanation.

### Resumed target build

The process left by the interrupted session had stopped during C3 compilation
at `[845/1027]`. Resuming that same partial directory reached ESP-IDF linker
generation, where `ldgen` rejected members of the partially generated
`libesp_hal_mspi.a` (`objdump: file format not recognized`). No source change
was made in response. That incomplete ignored build directory was preserved.
A single fresh run of the supported combined build/package script then passed:

| Command | Result |
|---|---|
| `python3 scripts/build_validation_targets.py` | PASS, ESP-IDF 6.0.3 C3 then S3 production profile; paired firmware bundle generated; no flash command executed |

Build report: `code/build/validation_targets/gs116-t5tnmd3s/report.json`.
Source HEAD was `09bc8cd8b7baab0674bbe03157b7b50bab28e51e`, source/build
fingerprint `fbe7626ccec95e3cd36f17ff1e7e456b914ebc8e83671457889e8f22893067a9`,
`GS_HIL_BUILD=OFF`, and package composition marked hardware `NONE` / physical
status `NOT_RUN`. C3 application image: 934,192 bytes, SHA-256
`7393f6c8a0e2519a41689a2474add533bad48f598c3ebd06edd7a59a537d56be`, fitting
the 1,966,080-byte OTA slot. S3 application image: 1,868,848 bytes, SHA-256
`199d7fa5fe3d5ca32c348d4dacd67cadb67268c35384c044df2ebac02a0617cf`, fitting
the 4,194,304-byte OTA slot. The S3 configure/build consumed the generated C3
asset via `GS_NODE_FIRMWARE_ASSET`; the resulting package manifest binds both
images and partition/boot artifacts. This is target compilation/package
evidence, not board or release qualification.

### Post-migration validation comparison

Component reports below identify their source fingerprints and generated JSON
evidence. The early Node/Hub/contract suites share fingerprint
`98c28126948486850ddbd8e442db7c6aea75a179df58af8192b59091453e65cd`; the later
backend/PWA runs and combined target build use
`fbe7626ccec95e3cd36f17ff1e7e456b914ebc8e83671457889e8f22893067a9`. Both are
working-source fingerprints at the same base HEAD; later path/test fixes are
included in the latter.

| Command | Before move | After move | Disposition |
|---|---|---|---|
| `make validation-node` | FAIL, 288.72 s; NodeHealth simulator setup and missing Playwright executable | FAIL, 127.968 s; 22/23 stages PASS; only `p0-full-product-e2e` failed on product `PARTIAL` adjudication | Setup/path regressions corrected; no Node stage failure remains |
| `make validation-hub` | FAIL, 300.074 s; same setup issues plus `hub-journal-migration-host-test` | FAIL, 302.055 s; 34/36 stages PASS; historical migration assertion and P0 `PARTIAL` | Historical `clean migration commits` remains visible and mandatory |
| `make validation-contract` | FAIL, 214.309 s; same setup issues | FAIL, 212.730 s; 29/30 stages PASS; P0 `PARTIAL` adjudication | No contract stage failure remains |
| `make validation-backend` | Not run before move | FAIL, 96.237 s; 13/14 stages PASS; P0 `PARTIAL` adjudication | Backend functional/API/bridge tests passed |
| `make validation-pwa` | Not run before move | FAIL, 92.846 s; 11/12 stages PASS; P0 `PARTIAL` adjudication | Frontend/API/bridge tests passed |

In all five aggregates the P0 scenario assertions and one Chromium case ran and
passed (26/26 scenario assertions). The stage still correctly reports FAIL
because the product completeness field remains `PARTIAL`; this does not become
a product PASS through source relocation. The only Hub migration failure is the
pre-existing GS-148 baseline defect at
`tests/cpp/hub_journal_migration_validation.cpp:194`, assertion `clean migration
commits`; it was neither removed nor relaxed.

Focused post-migration checks:

| Command | Result |
|---|---|
| `make -C code simulator` | PASS |
| `make -C code lab-build` | PASS |
| `make -C code cpp-test` | PASS, 1,479 checks |
| `make -C code app-test` | PASS, 23 tests |
| `make -C code contracts` | PASS |
| `python3 -m compileall -q code/backend code/validation code/scripts code/tests/python` | PASS |
| `python3 code/validation/check_p0_e2e_scenarios.py` | PASS, 17 use cases / 30 scenarios / 30 executable mappings |
| `make feature-coverage-test` | PASS, 150 feature rows / 204 modules / 14 physical cases / 19 traceability checks |
| `make -C code gs40-config-test` | PASS, 15/15 |
| `make -C code http-e2e-test` | PASS, 16 tests |
| `make -C code pwa-68-frontend-test` | PASS |
| `make -C code validation-framework-test` | PASS, 39 tests |
| `make -C code hil-tooling-test` | PASS |
| `make -C code gs130-hil-runner-test` | PASS, 15 tests; no ports opened |
| `make -C code hil-host-check` | PASS, 9 checks; no hardware access |
| `make validation-board-e2e` | PASS, 8 groups / 325 checks |
| `make validation-sanitize` | PASS, ASan/UBSan C++ 1,479 checks plus GS-40 1,320 checks |

The aggregate `p0-full-product-e2e` stage invokes
`make p0-product-e2e P0_SCENARIOS=`. Its scenario assertions and Chromium case
passed, while the component gate correctly records FAIL because the product
report status is `PARTIAL`. The backend/PWA stage suites passed independently;
the complete browser suite was not run. The exact metadata-discovery command
`python3 code/validation/component_gate.py --suite release --list` passed and
listed 73 registered stages. No `release-gate-final`, physical HIL, USB/serial
operation or device action ran.

### Final classification and checkpoint

The interrupted-directory linker failure is classified as an incomplete/stale
generated build artifact following interruption; it did not reproduce in the
fresh combined workflow. Migration path defects encountered earlier were
corrected and their affected backend/PWA suites passed. The mandatory Hub
journal-migration defect and P0 product `PARTIAL` result are pre-existing
independent failures, not GS-152 regressions. Source/module layout and build
adaptation are complete on the isolated GS-152 branch; canonical R1 remains
untouched. The branch is ready for integration review only. Product release and
physical qualification remain unapproved / not run.
