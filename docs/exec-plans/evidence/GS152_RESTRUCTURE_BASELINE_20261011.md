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

## GS-152 approved final integration — 2026-10-12

### Source and history

The user-approved integration authorization is GS-152 Jira comment 10527.
Before integration, canonical `feature/r1-commercial-baseline` was at
`9272cc7efe171f6fc5f6ceb7fac4ad1c4924fd33`; the isolated GS-152 branch was at
`79bc28dd9e623657cf9e43e37596fd281d3aab4a`. The GitHub `origin` was
`https://github.com/udaybhan200683/Ghar_sajag.git`, and the live remote refs
matched both local checkpoints. The canonical tracked worktree was clean.
Untracked S3 `managed_components/` and protected GS-114 evidence were retained.

The GS-152 branch merged canonical history using `--no-ff` (no rebase, reset or
force push): merge commit
`0ab12c38b8115c211b66b203289d77f8a835ec00`. Three registration conflicts were
resolved: `code/validation/suites.json`,
`docs/validation/MASTER_TRACEABILITY.csv` and
`docs/validation/SOURCE_FEATURE_INVENTORY.csv`. Resolution retained the stable
`code/` ownership paths and all newer canonical GS-114 registrations. The
merged GS-114 work retains fixture-compatible S3 diagnostics, commissioning
configuration, RPF00–RPF08, and the candidate `gs_outbox` / `gs_state` partition
profile. No storage format, security, protocol or firmware behavior change was
introduced. The isolated branch then added two validation/build-infrastructure
commits: `fc9f0a71d9a071abbf4553ad4c606fec98f16089` and
`d802485ee04227b6e1ca16810768e01f0da94009`.

The 499-entry source map still has 499 unique destinations, 0 missing files and
0 baseline hash mismatches. There are 368 byte-identical destinations, the 125
original path/build/documentation adaptations, and six destinations changed by
the newer canonical GS-114 work. The production source inventory has 204 unique
modules, no missing or duplicate module. All 73 registered stage input lists
resolve under the stable code root; the feature traceability check reports 151
features, 204 modules, 14 physical cases and 19 checks. This is 499-file
relocation plus newer canonical changes, not a claim that every post-merge file
is byte-identical to the 2026-10-11 baseline.

### Clean-checkout validation

A detached fresh source checkout at the integrated branch tip was used for
verification. `tools/context/ghar_sajag_context_preflight.sh` reported PASS at
`0ab12c3` with context `2026-10-11.001`. Its later test/build commands ran on
the same clean checkout advanced to `d802485`; only ignored build/evidence
outputs and lockfile-installed frontend dependencies were generated. No
untracked managed-components directory was deleted.

| Validation | Result |
|---|---|
| Original 499-file mapping and source inventory | PASS; 499/499 hashes, 499/499 destinations; 204 unique production modules |
| Validation input resolution | PASS; 73 stages, no missing or duplicate inputs |
| `make validation-framework-test` | PASS, 39 tests |
| `make feature-coverage-test` | PASS, 19 checks; 151 features / 204 modules / 14 physical cases |
| `make -C code s3-fixture-commissioning-test` | PASS, 10 tests; registered in Node, Hub and contract suites |
| `python3 code/scripts/build_validation_targets.py` | PASS on merge checkpoint; ESP-IDF 6.0.3 paired C3 934,192-byte and S3 1,870,896-byte production-profile builds |
| `make gs114-s3-rpf-diagnostic-build` | PASS on `d802485` before a later redundant rebuild hit temporary-filesystem exhaustion; C3 939,024 bytes (SHA-256 `8ba895f6fe45483463d3e80efafcc069218d576b2ae72b65a9682b5dad4126a3`), S3 1,879,280 bytes (SHA-256 `0edbc1540a60243320d4671f8f1f19528fea50e83585e500ed3b583f86dca736`); fixture commissioning ON, broad HIL OFF, RPF00–RPF08 present, C3 guard verified, compiled partition table matches CSV |
| Focused Node/Hub/contract/backend/PWA stage regressions | Individual regression stages PASS as listed below; aggregate gates retain required failures |
| `make validation-board-e2e` | PASS, 8 groups; physical NOT_RUN |
| `make -C code validation-sanitize` | PASS, ASan/UBSan; C++ 1,479 checks and GS-40 1,320 checks |
| `make p0-product-e2e` | Scenario execution PASS, 26/26 scenarios and one Chromium test; product status PARTIAL |

The Node gate passed its registered stage checks for GS-114 fixture commissioning
(10), host build, board stack (8), feature boundaries (111), factory reset,
signed FOTA tooling (16), C++ (1,479), BAT-C8 (72), GS-150 (1,481), GS-40
(1,320), commissioning, rejoin, association, Node recovery/persistence/
retirement, secure FOTA, FOTA (34), master (49), health configuration (15),
product base and product AI. Its aggregate remains FAIL solely because the P0
stage correctly reports `product_status=PARTIAL`.

The Hub gate's registered checkpoint, retirement, replay-fence, registry,
durable codec/provider, fresh-install, rejoin, CloudSync contract, HTTPS, health
configuration and other listed Hub stages passed. Its required
`hub-journal-migration-host-test` still fails at
`tests/cpp/hub_journal_migration_validation.cpp:194`, assertion `clean migration
commits`, unchanged from the pre-integration baseline. The Hub aggregate also
retains the P0 `PARTIAL` failure. Contract, backend and PWA suites ran their
registered stages: backend Python 448 tests, JavaScript 23 tests, functional 92,
dummy-streams 5, HTTP 17, bridge 13, API 2 and frontend 2 all passed; aggregate
gate status remains FAIL due to P0 `PARTIAL`. Each P0 invocation executed all
26 scenario checks and the Chromium caregiver reload case successfully, while
the product completeness requirement remains open. This status is not upgraded
to PASS.

Initial clean-checkout issues were corrected in the two test-infrastructure
commits: the paired C3 asset is now exported before ESP-IDF component discovery;
the NodeHealth gate builds its interactive simulator; GS-114 test-count parsing
matches unittest output; and the root Makefile exposes the documented GS-114
targets. The final redundant diagnostic rebuild attempt failed because `/tmp`
was full (no space left on device); verified outputs from the earlier successful
build were preserved. No cleanup/deletion was performed. This late resource
limit did not invalidate the successful paired target build or the successful
fixture diagnostic build at the final code commit.

### Integration and delivery evidence

The integrated branch contains all eight canonical GS-114 commits that were
newer than the original GS-152 base. It contains no GS-144 forward-port. The
existing common-baseline GS-148 files were not modified by this integration.
No hardware, USB/serial, flash, erase, reset or storage operation ran. No full
release gate ran; release approval and physical qualification remain NOT_RUN.

The canonical branch was subsequently fast-forwarded from
`9272cc7efe171f6fc5f6ceb7fac4ad1c4924fd33` to the final GS-152 tip after the
isolated branch passed its source integrity, fresh-checkout and focused
validation checks. Local and GitHub remote refs were verified to match after
the push. The exact final commit and Jira closure evidence are recorded in the
GS-152 delivery comment. GS-114, GS-144 and GS-148 Jira statuses were not
changed. GS-152 is closed only for repository-layout restructuring; this does
not claim product release readiness, P0 product acceptance, Hub journal
migration repair, or physical qualification.
