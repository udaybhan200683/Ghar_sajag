# GS-118 Phase-2 Rollback Reconciliation and Evidence Preservation

Date: 2026-10-15
Canonical branch: `feature/r1-commercial-baseline`
Validation source checkpoint: `851a7fbcd3d9dd61a7b6329b5e86789b0403be47`
Historical branch/worktree: `feature/hw-m1-4-hil-phase2` / `/home/udaybhan/projects/Ghar_sajag_phase2`

## Executive summary

The C3 Node remains the same ESP32-C3 with 4 MiB flash. Only the Hub has moved
to the ESP32-S3 N16R8 with 16 MiB flash. The C3 OTA layout and the signed-FOTA
receiver therefore remain 4 MiB C3 concerns; the larger Hub flash does not
increase C3 flash, heap, or OTA-slot capacity.

The historical September 27 rollback evidence records a stack-protection panic
in the `gs_ota_validate` task configured with 3,072 bytes. The run did not
qualify rollback: its original fixture incorrectly accepted stale-session
evidence as recovery. No stack high-water measurement exists. Canonical now
uses a provisional 12,288-byte stack for that task, adds a strictly opt-in
signed-HIL failed-health injection, and adds host checks for rollback evidence
and failure-injection boundaries. This resolves the source configuration gap;
it does not establish runtime stack margin or physical rollback acceptance.

The software profile and focused fixture tests passed, and the C3 target built
for both production and explicit HIL-injection profiles. A signed candidate
build could not run because signed-profile configuration and signing
credentials were unavailable. Physical rollback was not run. The existing
signed-FOTA HIL supervisor still builds a classic ESP32 Hub; the current S3
Hub rejects legacy broad HIL controls. Consequently, the runner is not yet a
current S3 N16R8 + C3 qualification path. Do not infer commercial R1
qualification from the host checks or C3 compile.

The complete historical Phase-2 worktree contents and Git history were copied
to a restricted external backup and verified. The source worktree and branch
remain untouched.

## Requirement and audit scope

GS-118 latest Jira comment 10065 bounds this work to failed-boot rollback,
representative interrupted/corrupt update recovery, and secure restart
behavior. It explicitly excludes repeating already-passed signed A-to-B and
wrong-signer cases and excludes PKI/HSM/eFuse productionization. GS-95 remains
the source-consolidation owner. No Jira workflow status changed.

The completed Phase-2 audit identified 11 historical commits unique to the
Phase-2 branch. This remediation does not repeat that audit or import its
history. The historical commit SHAs and top-level dispositions are:

| Historical commit | Subject | Disposition in this remediation |
|---|---|---|
| `480ec95a781b89f5139de9bd39bd9b4b0e0174ee` | Qualify signed OTA boot rollback | Historical physical evidence only; the September 27 result is not a rollback PASS. |
| `b6d04ad1ee1de0735554dae879dd607d6d8253b7` | Accept authenticated progress after interleaved FOTA ACK | Existing canonical protocol behavior and regressions retained; no duplicate implementation. |
| `10f6af7c708c1506580118203fa8c348b849289b` | Fix signed OTA rollback task stack | Its 12 KiB source adjustment is adopted provisionally in canonical and guarded by a regression test. |
| `97b3546f18b150007af7ae706634b14749f1ba4a` | Correct signed FOTA rollback qualification record | Provenance/evidence correction retained; it does not establish physical rollback PASS. |
| `08b698bc203293d7e7e548df91192cf738fb42c3` | Qualify Hub journal restart recovery | Historical classic-Hub evidence only; it does not qualify the current S3 storage design. |
| `8f9de2ab01b67a4b2acdd86dd331845ddfc96111` | Accept fresh boot evidence after truncated reset UART | Historical fixture robustness change; current recovery assertions require fresh boot/session evidence. |
| `79d53107467460f0598b98170b4a7711b2a81aa7` | Probe live C3 before fixture restart | Historical fixture safeguard/evidence; no physical operation was repeated here. |
| `441643f8274d6287bfe01d5ff3bb889e9b099f1c` | Rejoin authenticated session after Hub outage | Covered by current authenticated rejoin and retained-event identity contracts; no parallel runtime path added. |
| `b131894bb15ab5ac1321ce050d1679b14af23458` | Reuse verified identity during HIL preflight | Historical HIL supervisor/provenance behavior; no separate HIL framework introduced. |
| `9bd131ebcc9bd7d1c625c7f910f6221616987f65` | Reuse setup identity in supervised HIL campaigns | Historical HIL supervisor/provenance behavior; no separate HIL framework introduced. |
| `8f053b45b1c6b8ec772565336582c7e63a68a6a6` | Record Hub journal restart recovery qualification | Historical qualification record only; not current S3 physical evidence. |

The Phase-2 local and remote branch were both at
`8f053b45b1c6b8ec772565336582c7e63a68a6a6` during this work. The branch has
11 commits outside canonical ancestry. Canonical remained at
`851a7fbcd3d9dd61a7b6329b5e86789b0403be47` before this delivery. No history
merge, cherry-pick, or historical-source edit was performed.

## C3 rollback stack investigation

The canonical path still creates `gs_ota_validate` in
`code/firmware/node/target/esp32c3/idf/main/fota_receiver.cpp`. When the
running image is pending verification, it evaluates boot health and calls
`esp_ota_mark_app_invalid_rollback_and_reboot()` on a failed health deadline.
This is the same rollback call path implicated by the historical panic.

The captured September 27 `c3_serial.log` records a Guru Meditation
stack-protection fault during rollback on ESP-IDF 6.0.3 while the task used a
3,072-byte stack. The evidence identifies a credible insufficient-task-stack
failure. It does not identify the deepest frame or peak usage. The later
historical source used 12,288 bytes, but there is no physical run after that
change with a stack high-water result. Heap snapshots cannot substitute for a
task stack high-water measurement.

ESP-IDF 6.0.3 documents the `xTaskCreate` stack-depth value in bytes on
ESP32-C3. The task remains dynamically allocated from heap. The configured
12 KiB is four times the failed 3 KiB allocation, adding 9,216 bytes. It is a
conservative provisional bound based on the recorded failure, not a measured
minimum or proven margin. The next authorized physical rollback run must
capture `uxTaskGetStackHighWaterMark` for this task under the rollback path and
record remaining free heap. Do not reduce the stack based on static build
size alone.

### Resource and flash profile

The C3 defaults still select 4 MiB flash in
`code/firmware/node/target/esp32c3/idf/sdkconfig.defaults`. Its OTA partitions
remain `ota_0` at `0x20000` and `ota_1` at `0x200000`, each `0x1E0000` bytes.
The updated Hub baseline is ESP32-S3 N16R8, with 16 MiB flash and 8 MiB PSRAM;
it is a separate board and does not alter this Node layout.

On the production C3 target build, ESP-IDF 6.0.3 reported static DRAM use of
113,974 / 321,296 bytes (35.47%), leaving 207,322 bytes in the reported DRAM
region. The production application binary was 934,992 bytes, within the
1,966,080-byte OTA slot. These are link/build measurements only. They do not
measure runtime heap fragmentation, dynamic task allocation success under
load, or the rollback task's high-water margin. Therefore
`CURRENT_C3_RESOURCE_CHECK=PARTIAL`.

## Narrow failed-health rollback test controls

Canonical reuses `tools/hil/secure_signed_fota.py` and
`tests/python/test_secure_signed_fota_fixture.py`. The bounded rollback-only
fixture path validates candidate and known-good image provenance, requires a
fresh authenticated recovery session, checks that the pending EventKey stays
the same through retry and matching Durable ACK retirement, rejects candidate
healthy markers and panic/stack-fault evidence, and requires one resulting
caregiver event without false PASS from the candidate session.

The failure-injection compile option defaults OFF. CMake rejects it unless
`GS_HIL_CONTROL=ON` and `GS_HIL_BUILD=OFF`; the signed-image builder requires
the explicit `--force-boot-health-fail --hil-control` combination. The injected
build suppresses only the required health observation, allowing the regular
health deadline and bootloader rollback path to execute. Negative tests reject
production-profile option combinations. This injection is for explicitly
configured disposable HIL candidates only and must not be enabled on protected
boards.

### Current Hub fixture limitation

`code/tools/hil/secure_signed_fota.py` still selects
`firmware/hub/target/esp32/idf` and its Hub builder targets classic `esp32`.
The current S3 Hub project rejects `GS_HIL_BUILD` and `GS_HIL_CONTROL` because
S3 board-specific HIL controls are pending. The S3 development partition
profile and 16 MiB flash do not make this old fixture compatible. A current
S3 + C3 physical campaign therefore needs an approved S3-compatible fixture
control/profile and a separate validation review. This task did not implement
those controls or operate hardware.

## Changes made in canonical working tree

The source changes are limited to the C3 rollback task stack, test-only
failed-health injection, the existing signed-C3 builder and FOTA HIL fixture,
and their focused tests/registration:

| File | Change |
|---|---|
| `code/firmware/node/target/esp32c3/idf/main/fota_receiver.cpp` | Set `gs_ota_validate` to 12 KiB; add compile-guarded test-only health-failure injection. |
| `code/firmware/node/target/esp32c3/idf/CMakeLists.txt` | Add OFF-by-default injection option and reject invalid profiles. |
| `code/firmware/node/target/esp32c3/idf/main/CMakeLists.txt` | Pass the injection compile definition to the target component. |
| `code/scripts/build_signed_c3.py` | Require explicit HIL control for failure injection and record build configuration in provenance. |
| `code/tools/hil/secure_signed_fota.py` | Add bounded `--rollback-only` flow to the existing supervisor and evidence verifier. |
| `code/tests/python/test_secure_signed_fota_fixture.py` | Cover stack configuration, production profile rejection and rollback evidence validation. |
| `code/validation/suites.json` | Include CMake/receiver inputs in the registered signed-FOTA tooling stage. |
| `docs/validation/MASTER_TRACEABILITY.csv` | Register three GS-118 stack, injection and rollback-recovery cases with physical status NOT_RUN. |
| `docs/validation/SOURCE_FEATURE_INVENTORY.csv` | Map the recovery case to the C3 FOTA receiver source. |

No production protocol, Node identity, ACK, retry or event-retirement contract
was changed. No commercial signing or S3 HIL controls were enabled.

## Validation evidence

| Check | Result | Evidence/limitation |
|---|---|---|
| `python3 -m unittest discover -s tests/python -p test_secure_signed_fota_fixture.py -v` | PASS, 20 tests | Host fixture assertions only; no hardware qualification. |
| C3 ESP-IDF production build, IDF 6.0.3, 4 MiB | PASS | Isolated build directory; `GS_HIL_BUILD=OFF`, `GS_HIL_CONTROL=OFF`, injection OFF. |
| C3 ESP-IDF signed-HIL injection-profile build, IDF 6.0.3 | PASS | Isolated build directory; explicit HIL control, `GS_HIL_BUILD=OFF`; build only. |
| Signed-profile build | BLOCKED | No local `sdkconfig.signed`, `GS_HIL_SIGNED_FOTA_KEY`, or negative-signer key. No signing credentials were generated or exposed. |
| `make validation-board-e2e` | PASS, 10 groups | Host board-stack simulation; not a physical board result. |
| `make validation-framework-test` | PASS, 46/46 | Validation framework. |
| `make feature-coverage-test` | PASS, 22/22 | Final mapping: 202 features, 210 modules, 15 physical cases. |
| `make physical-hil-catalogue-test` | PASS, 99 cases | Catalogue structure only; physical cases remain NOT_RUN. |
| `make validation-node` | FAIL / exit 2 aggregate | Affected registered stages, including signed-FOTA tooling (20), passed. Aggregate remains blocked by required P0 `product_status=PARTIAL`. |
| `make validation-contract` | FAIL / exit 2 aggregate | Affected signed-FOTA and contract stages passed; required P0 remains `product_status=PARTIAL`. |
| `make validation-hub` | FAIL / exit 2 aggregate | Existing `hub-journal-migration-host-test` reports `clean migration commits` failure; P0 also remains PARTIAL. Relevant Hub FOTA/codec/rejoin/outbox stages passed. |
| `git diff --check` | PASS after final documentation edits | Covers the source/registry changes and the final report/work-state handoff. |
| Full release gate / physical HIL | NOT RUN | Explicitly outside this task. No USB/serial access, flash, reset, erase, or provisioning occurred. |

The isolated target-build commands were:

```bash
source /home/udaybhan/.espressif/tools/activate_idf_v6.0.3.sh && \
idf.py -B build_gs118_c3_prod_20261015 \
  -DIDF_TARGET=esp32c3 \
  -DSDKCONFIG=build_gs118_c3_prod_20261015/sdkconfig \
  -DSDKCONFIG_DEFAULTS=sdkconfig.defaults \
  -DGS_HIL_BUILD=OFF -DGS_HIL_CONTROL=OFF \
  -DGS_HIL_FORCE_BOOT_HEALTH_FAIL=OFF build

source /home/udaybhan/.espressif/tools/activate_idf_v6.0.3.sh && \
idf.py -B build_gs118_c3_rollback_hil_20261015 \
  -DIDF_TARGET=esp32c3 \
  -DSDKCONFIG=build_gs118_c3_rollback_hil_20261015/sdkconfig \
  '-DSDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.hil.defaults' \
  -DGS_HIL_BUILD=OFF -DGS_HIL_CONTROL=ON \
  -DGS_HIL_FORCE_BOOT_HEALTH_FAIL=ON build
```

The validation targets run were `make validation-node`,
`make validation-contract`, `make validation-hub`,
`make validation-board-e2e`, `make validation-framework-test`,
`make feature-coverage-test`, and `make physical-hil-catalogue-test` from
`code/`. The focused Python command was
`python3 -m unittest discover -s tests/python -p test_secure_signed_fota_fixture.py -v`
from `code/`.

The P0 gap and Hub migration failure are preserved as failures; they are not
relabelled as PASS or repaired in this GS-118 task.

## Evidence preservation

The full historical Phase-2 worktree contents (excluding only its Git
administrative `.git` pointer) and Git history bundle are preserved at:

`/home/udaybhan/projects/phase2_evidence_backup_20261015T101912Z`

The copy verification found 57,145 entries: 36,903 files and 20,242
directories, with 5,578,823,672 file bytes, no missing entries and no extra
entries. The full history bundle SHA-256 is
`e30814f73a9932846f16805ff0efa8b52c4e964cfb4b716ce1e08f743d0c9712`.
The worktree manifest SHA-256 is
`a6efe6e11631eff1a53a8849172f38d4745ffd7e375ba6aa6b15143412f91295`.
The raw September 27 panic log, the initial misleading PASS record, later
fixture correction evidence, images, manifests, ignored configuration, build
outputs, and historical source are preserved. Sensitive local configuration
is restricted (backup root mode 700; `config/hil.local.env` mode 600); no
private key contents were printed or added to Git. No historical build
artifacts were excluded.

Two current-task generated artifacts were preserved outside canonical:

- `/home/udaybhan/projects/gs118_build_outputs_20261015` — three isolated build
  outputs; 3,506 files / 554,879,624 bytes; SHA-256 manifest included.
- `/home/udaybhan/projects/gs118_config_backup_20261015T103900Z/sdkconfig_after_initial_configure`
  — mode 600; SHA-256
  `f3ffa60f215f26ef230f50e034f5cc2378a9000e6f27b0d830c74157201ff33a`.

An initial build command selected the default classic ESP32 target before the
target mismatch was detected and canceled after partial compilation. It
regenerated the ignored C3 target-root `sdkconfig`; its prior bytes were not
captured, so they cannot be certified unchanged. The current regenerated file
was preserved at the path above. All subsequent target builds used isolated
SDKCONFIG and build paths. This is recorded as a tooling side effect, not
physical device activity.

The Phase-2 worktree still has untracked historical build directories under
its nested archived project path. They remain untouched and are included in
the verified full backup. The Phase-2 worktree and branch were not removed.

## Open blockers and next plan

1. Review and push this canonical remediation with the focused evidence and
   accurate aggregate failures; do not change Jira status.
2. Obtain a safe, disposable C3 fixture and an approved S3 N16R8-compatible
   Hub HIL control/profile, or an explicit product decision defining a
   supported legacy fixture for this narrowly scoped Node rollback test.
3. Provide approved signed-profile configuration and test signing material
   outside the repository. Keep signing credentials out of source control.
4. On explicitly authorized hardware only, install known-good A and signed
   failed-health candidate B, exercise rollback, capture panic/reset/session/
   EventKey/ACK evidence, and measure `gs_ota_validate` stack high-water and
   free heap. Do not count the September 27 run as a PASS.
5. Separately resolve P0 product completeness and the Hub journal migration
   failure through their owning work; neither is silently closed here.
6. Preserve the Phase-2 branch/worktree until the owner authorizes retirement
   after confirming its Jira/PR/process dependencies. The 11 historical
   commits remain outside canonical ancestry; the verified backup preserves
   their source and history.

`GS118_ROLLBACK_STACK_GAP=RESOLVED` means the confirmed 3 KiB source
configuration has been replaced by the provisional 12 KiB allocation. Runtime
stack sufficiency and signed physical rollback remain open. Commercial R1 FOTA
qualification is therefore not complete.
