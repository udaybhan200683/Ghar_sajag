# GS-177 / R1 Hub simulator software slice — 2026-10-18

## Scope and ownership

This is an isolated, test-only software increment on branch
`codex/gs-hub-test-simulator-20261018`, based on canonical commit
`58487978988b609917f4d021d01480ab87bc220a`. It was created after the context
preflight passed. The canonical R1 checkout remained untouched; its existing
untracked Android, managed-component and hardware-evidence paths were preserved.
GS-40, GS-109 and GS-148 remain active owners of the shared target composition,
Hub runtime adapter, trust source, durable storage and CloudSync paths. None of
those files was changed.

This increment implements a bounded scenario planner/evaluator which reuses the
existing deterministic `RulesCore` and `RoutineService`. A host-only bridge test
also exercises event admission through a fresh `HubRuntime` with an in-memory,
volatile journal. This does not execute inside the S3 product image or traverse
the production replay-fenced runtime/durable-storage path. It does not write the
durable Hub store, call CloudSync, persist to the backend, or update
caregiver/engineering projections. Those downstream evidence stages are
explicitly `NOT_RUN`.

## Implemented

- `firmware/hub/simulation/hub_scenario_simulator.{hpp,cpp}` defines one-run-at-a-
  time execution, at most 16 steps and 24 hours of synthetic time, bounded IDs
  and locations, cancellation, and authorization re-check before each step.
- The module is inert unless `GS_HUB_SCENARIO_SIMULATOR_TEST_ONLY=1` is explicitly
  selected. Its generated events use source `hub-sim-test`, `SensorType::System`,
  `is_test=true`, and no physical device identity. The virtual clock is local to
  the simulation and never changes platform trusted time.
- Event rule evaluation invokes the existing `RulesCore` on an ephemeral sandbox
  copy. The retained result remains marked TEST_ONLY. The production runtime's
  current behavior of ignoring test events remains unchanged.
- Routine evaluation is opt-in per scenario and uses the existing `RoutineService`
  contract for a bounded, explicitly configured morning window. The simulator
  records missing-evidence decisions and routine state, while synthetic check-in
  and qualifying activity suppress the missing-activity result according to the
  existing deterministic rules. Unknown coverage and untrusted virtual time
  remain non-triggering. No GS-104 learning, resident baseline or trend is added.
- Trace output marks only the Hub simulation source and shared `RulesCore` as
  observed. Hub runtime admission, durable commit, CloudSync, backend commit and
  caregiver projection remain `NOT_RUN`.
- `make hub-scenario-simulator-host-test` is registered in
  `code/validation/suites.json` for Hub/fast/release composition. GS-130 feature
  and physical evidence rows distinguish host execution from target HIL.

## Tests and debugging

Command:

```text
make -C code hub-scenario-simulator-host-test
```

Final result: **PASS** — simulator regression `73` checks; separate default-off
regression `1` check. Covered morning sequence, night threshold, door concern and
recovery, covered inactivity, missing-morning incident, qualifying activity and
I Am OK suppression, unknown coverage, untrusted virtual clock, authorization
denial/revocation, invalid routine chronology, bounded inputs, duplicate
synthetic identity, repeatability and cancellation.

Debugging outcomes preserved:

1. Initial plan validation rejected a valid TEST_ONLY Home because the prefix
   length used `sizeof(pointer)`; changed to a compile-time character array and
   fixed epoch-overflow validation.
2. Morning sequence did not fire because the test used a bedroom label different
   from the current configured `room1`; the fixture now uses the actual rule
   configuration.
3. Reusing one engine produced zero door results because `begin()` retained the
   prior step index and scratch rule state; `begin()` now resets both.
4. The default-off build caught a `-Werror=unused-function` test-only helper;
   its compilation is now selected with the same default-off macro.

After reconciling the new traceability row to the current schema, the new
`GS177-HUB-SIM-001` row resolves. The global feature-coverage checker still
returns the pre-existing
`GS40-NODEHEALTH-CLOUD-001: command disagrees with registry` error; that GS-40
row belongs to the active GS-40 owner and was not changed. The physical HIL
catalogue integrity check passes with 109 cases. The simulator registry records
its RulesCore source/header dependencies so changes invalidate the test stage.

Additional validation on 18 Oct 2026:

- `make -C code cpp-test`: PASS, 1,509 checks.
- Validation component-gate meta-tests: PASS, 47 tests.
- Validation framework meta-tests: PASS, 13 tests.
- Feature traceability meta-tests: 19 PASS, 3 FAIL only because the same
  pre-existing GS-40 registry mismatch is returned by their global checker.
- Physical HIL catalogue tests: PASS, 7 tests; catalogue integrity PASS, 109
  cases, no device access.
- ESP-IDF Xtensa ESP32-S3 cross-compiler translation-unit check for the
  simulator with the TEST_ONLY macro enabled: PASS, object-only compile; object
  SHA-256
  `c28737240b45af64b84c7a2692c14145ea506ab24e481b4dcd3b7252f3c3691e` under
  ignored `code/build/validation_targets/gs-hub-simulator-object/s3/`; not linked
  into the Hub image. Object size is 493,364 bytes including debug and symbol
  sections; this is not a flash, IRAM, or runtime memory measurement.
- Existing paired production-profile C3/S3 builder: PASS, compile-only at source
  HEAD `58487978988b609917f4d021d01480ab87bc220a` before the simulator module.
  C3 image SHA-256 `1ca5f9916318cfe8373f418f99cd08449d9873a62be9ea5ad0c35700d2e8a11c`
  (937,536 bytes); S3 image SHA-256
  `1f8deb7f9d52f38df05c2e7de4c57a73dbd86ae562ee684ee41a1cc085e0a831`
  (2,168,144 bytes). These are baseline images and contain no simulator code.
- GS-177 Connected Lite server verification: PASS, 19 tests; PWA browser E2E:
  PASS, 3 tests including 92/92 rendered catalogue cases. Connected Lite
  browser authorization/navigation uses its mock transport.
- Live Render checks: `/healthz` and `/readyz` returned HTTP 200; anonymous
  TEST_ONLY Home and Engineering API requests returned HTTP 403. No admin
  credentials were available in the session, so authenticated cloud login was
  not attempted.
- Android workflow
  [39098215553](https://github.com/udaybhan200683/Ghar_sajag/actions/runs/39098215553)
  completed successfully from GS-177 source
  `0120f6f2f57a2568700b5933bcab8eb4ddf18edc`. It produced package
  `in.gharsajag.caregiver`, version `0.4.0-connected-lite-staging`, with the
  approved staging origin. APK SHA-256 is
  `b00c3ff89e68fab91fd87ea5aa96b703cf9f764207cb1fe8e96553069fa45a97`; CI
  verified its signature. The runner-generated debug key means an update over
  an earlier differently signed install may require uninstall. The artifact
  was downloaded to
  `/home/udaybhan/projects/Ghar_sajag_gs177/code/build/delivery/` (ignored build
  output). No authorized ADB device was present; physical phone acceptance is
  NOT_RUN.
- `make validation-hub` completed with **46 PASS / 4 FAIL of 50 stages**, aggregate
  `software_status=FAIL`, physical `NOT_RUN`, elapsed 971.427 seconds. Its report
  says `source_unchanged=false` because tracked documentation changed while the
  gate was running, so this is not a source-stable gate receipt. The report and
  logs are preserved under
  `code/evidence/validation_framework/hub-1792299726375558268/`.
  - `migration` failed the existing `clean migration commits` assertion in
    `tests/cpp/hub_journal_migration_validation.cpp`. This GS-148 owned storage
    path was not edited.
  - `cloudsync-security-unit` initially failed because `cloudsync-security-ut`
    omitted the TEST_ONLY adapter binary from prerequisites. The isolated Makefile
    now declares it and a standalone rerun passed, including 9 production adapter
    cases, 5 TEST_ONLY adapter cases, 5 trust-provider groups, and 33 Python tests
    across security, identity/time, pilot issuer and NodeHealth.
  - `https-channel` failed under `-Werror` because
    `test_only_software_identity` is unused at
    `firmware/hub/target/esp32s3/https_backend_channel.cpp:44`. The active GS-68
    transport/trust implementation was not modified.
  - `p0-full-product-e2e` first failed because Playwright was absent. After
    restoring the locked dependency with `npm ci --ignore-scripts --no-audit
    --no-fund` into ignored `code/frontend/node_modules`, `make p0-product-e2e`
    passed 26 scenario checks and one Chromium reload test. The report says
    `product_status=PARTIAL`, `physical=NOT_RUN`; the test backend uses an
    ephemeral loopback fixture credential and production Hub trust/enrollment
    binding remains unconfigured. Report SHA-256 is recorded in the build output
    and is not a physical acceptance receipt.
- The paired target builder performs compile-only C3/S3 builds in a unique ignored
  directory and does not flash or access a board. Its production-profile images
  are baseline artifacts at source HEAD `58487978988b609917f4d021d01480ab87bc220a`
  and do not include the new simulator.

## Qualification boundary

| Evidence | Result |
|---|---|
| Host simulator, enabled test profile | PASS, 73 checks |
| Default firmware macro behavior | PASS, disabled by default, 1 check |
| Baseline C3/S3 production-profile target build | PASS compile-only at base HEAD; images do not include simulator changes |
| Simulator S3 target translation-unit compile | PASS object-only; S3 target link/composition NOT_RUN |
| Simulator inclusion in S3 firmware target | NOT_RUN; no IDF target composition was changed |
| Actual Hub runtime admission and durable commit | NOT_RUN |
| Hub-resident execution / source-bound image | NOT_RUN; only an S3 compiler object check passed |
| CloudSync/backend/caregiver projections | NOT_RUN |
| Physical fixture execution | NOT_RUN; no fixture-specific authorization was available |
| Genuine C3/PIR → S3 vertical | NOT_RUN; this simulator cannot qualify it |
| R1 release gates | NOT_RUN; no frozen RC and no approved mandatory-P0 denominator |

No simulation-learning algorithm was added; GS-104 R01–R09 remains on hold. No
real Hub event, C3 identity, radio reception, ACK, durable receipt or cloud
receipt is claimed.

## Next integration action

The current GS-40/GS-148 owners must provide/merge an approved test-only call
site in the S3 composition and Hub owner task, plus a restricted authenticated
TEST_ONLY Home control adapter. Then connect the simulator output to the owned
Hub processing/durability/CloudSync path and run a source/image-matched S3
fixture test under its separately approved procedure. Until then this branch is
a tested software slice, not a working Hub-resident simulation or product E2E.

## WIP checkpoint verification — 2026-10-18

After the implementation slice above, the following focused checks were rerun
from this branch before its WIP checkpoint:

- `make -C code hub-scenario-simulator-host-test`: **PASS**, 73 enabled checks
  and 1 default-off check.
- `make -C code hub-scenario-runtime-bridge-host-test`: **PASS**, 15 checks.
  This host test verifies the bridge against a fresh runtime and volatile
  in-memory journal; it does not prove production replay-fence compatibility or
  durable storage.
- ESP-IDF 6.0.3 S3 compile-database translation-unit check for
  `hub_scenario_simulator.cpp`: **PASS**, object-only, 631,992 bytes,
  SHA-256 `16053c4e3f993a77f057f7a6168e48b8b2b7aaef3e7189c5383cc2025005b28c`.
- ESP-IDF 6.0.3 S3 compile-database translation-unit check for
  `hub_runtime_scenario_bridge.cpp`: **PASS**, object-only, 1,191,856 bytes,
  SHA-256 `02736b2ec3265fc410a791f3e1c8856a224adbabb14326de1b3dbfdbf97e913e`.
  These compile-only objects do not establish S3 target composition, image
  linking, runtime execution, memory headroom, or physical qualification.
- `git diff --check`, validation-suite JSON parsing and CSV row-width checks:
  **PASS**. The targeted scan for private-key markers and credential-shaped
  values in the simulator/evidence files returned no matches.

The known integration boundary remains unchanged: the current production runtime
rejects the bridge's radio-callback path once its replay fence is ready. No S3
target wiring, CloudSync, dashboard projection, or physical test was performed
for this checkpoint. The earlier Hub aggregate remains **FAIL** (46/50 stages,
source-unstable report); it was not rerun for this checkpoint.
