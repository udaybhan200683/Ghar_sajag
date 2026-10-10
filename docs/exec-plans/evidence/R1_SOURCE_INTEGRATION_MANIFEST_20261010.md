# R1 one-time source integration manifest — 2026-10-10

Classification: integration provenance and validation evidence, not a product requirement or release qualification.

## Canonical destination

- Worktree: `/home/udaybhan/projects/Ghar_sajag_r1`
- Branch: `feature/r1-commercial-baseline`
- Starting local/remote HEAD: `f6e949a79354ebd1a25c55a9b9a9b750bf387dac`
- Starting tracked tree: clean. Local generated/untracked source files: none.
- GitHub origin: `https://github.com/udaybhan200683/Ghar_sajag.git`
- All six registered worktrees and five actual remote refs were inspected. No cleanup or hardware operation was performed.
- Repository `AGENTS.md` now makes this the single R1 development worktree/branch. Global Codex rules were appended at `/home/udaybhan/.codex/AGENTS.md`; SHA-256 `1f973228f7e04f683c17254328b5757c17eaef39716be6d2bcbf12dbdbf47f92`. This external file is not part of the Git commit.

## Worktree inventory and disposition

| Worktree / branch | Local HEAD; actual remote HEAD | Changes / disposition |
|---|---|---|
| `Ghar_sajag` / `feature/battery-power-policy` | `808080e94b6958153952ce16eb56c1ad37a9ad01`; same | `808080e` is an ancestor of canonical R1. BAT-C8 PowerPolicy, light sleep, GPIO4/timer, runtime, diagnostics and tests are already integrated. Three untracked HIL scripts remain untouched in this source worktree. No second C3 copy was imported. |
| `Ghar_sajag_r1` / `feature/r1-commercial-baseline` | started `f6e949a`; integration commits recorded below; remote initially `f6e949a` | Canonical destination. No uncommitted source edits existed at start. |
| `Ghar_sajag_r1_s3` / `feature/r1-s3-hub-bringup` | `5b8b1485f80b5989db0fbbd77588c91986fc6ca9`; same | P2-A/B/C and partial P2-D source/evidence selectively imported. Untracked `sdkconfig` and `managed_components/` remain in the source tree. Its uncommitted AGENTS change was reviewed for the approved one-worktree policy and that policy was added to canonical global/repository instructions; other S3 generated files were not imported. |
| `Ghar_sajag_r1_storage` / `feature/r1-hub-storage-lifecycle` | `389ffd3048cd44afdbb9ef074ed2a96020a3641e`; actual remote `2b3c6730f8c490ba88a13ba2c23d6674c4c30fa8` | Eleven local commits are not published. They primarily contain classic 4 MiB capacity/NVS prototypes and evidence. No code or whole-tree merge was taken. Relevant historical measurements remain available in this preserved worktree; use only as comparative evidence under GS-D030. Untracked `prompt.txt` remains untouched. |
| `Ghar_sajag_phase2` / `feature/hw-m1-4-hil-phase2` | `8f053b45b1c6b8ec772565336582c7e63a68a6a6`; same | Older HIL/FOTA branch is divergent and its comparison includes removals of later S3/current sources. No merge/import. Numerous untracked generated target-build outputs remain untouched; retain branch-specific physical evidence with its original hardware/image provenance. |
| `Ghar_sajag_durable_storage_impl` / `feature/hub-durable-storage-primitives` | `e1ef65e3f647bffa0cef75695e1af6d135c0df4a`; same | Historical classic-Hub migration/ownership experiments. Its comparison deletes current components and conflicts with the selected S3 architecture; no production code import. Preserve as historical reference. |

The six trees are kept in place. The battery commit ancestry confirms approved C3 changes already reached canonical R1; the S3 and other divergent branches were not treated as supersets. No remote branch was changed by this reconciliation checkpoint.

## S3 source commits integrated

Reviewed S3 implementation commits were cherry-picked in dependency order, retaining each source commit message and author date. Canonical replacements are:

| Source commit | Canonical commit | Scope |
|---|---|---|
| `e5d13f615c5f1c10d01325460879425b32d8721a` | `2c5d1e2` | S3 target composition and dated bring-up evidence |
| `f2be15029cf2f3f348d2784581fcd8a516c5a65a` | `bd9dcdf` | Encrypted segmented outbox and LittleFS adapter |
| `928a252f7e8269da915a4e1941cdfef44a8b8284` | `9ce54b5` | Runtime admission/replay integration and host regression |
| `ea690024d136e855f62a4b255e003e39f67c9427` | `d8f1ae3` | Authenticated outbox completion state |
| `51ca0addde6ada597f5f70448f5763b811190047` | `3032bb5` | Selectable candidate partition profile |
| `eb94524f71fc25cd95f54e0bedf9368d28a33fa8` | `b05c40d` | Reducer checkpoints and independent identities |
| `479c6d0082890bc19b5c88e570fb0b176f5ff474` | `396d78e` | Checkpoint replay validation |
| `5b473912d690d19b9b0d3aaecbdbabc1806775a6` | `9dbbb72` | Guarded lifecycle reclamation |
| `f82fa8f827b89dbe5084c3f6bd9db4d8b9b5a038` | `7a457c3` | Incremental completion reclamation |
| `a9238ba2f0516c6f6b454f69f01f5ece2b4b07b0` | `6462a83` | Replay fence and identity eligibility |
| `00d9c0ceb0eb5ebb3381acb3e7e49945b07c6aa6` | `38e967b` | Identity compaction planner |
| `a0d1adf8c1a806270332e1257b4d35937871e3f6` | `dbc2d38` | Crash-safe identity generation compaction |
| `984913a7194439d628598b5d79adbb156ed9c25d` | `4f87b67` | Mixed-segment event-body reclamation |
| `17c5cfded8d809535bc846fbf8108a9b8cca0e1a` | `0b7720a` | Reserve enforcement and P2-C final evidence |
| `e1941d7136c43fe6e21f4eff42527aa2d0de9a9a` | `1febcf0` | Bounded HTTP/HTTPS adapter, strict receipt parsing and partial P2-D evidence |

Conflicts in stale S3 copies of `R1_WORK_STATE.md`, the active storage ExecPlan, `DECISION_LOG.md` and the canonical index were resolved by retaining canonical R1 versions; they are updated from current verified state, not old branch snapshots. GS-D030 approval is already represented by canonical commit `9cda6ad`; the older source decision was not replayed. The uncommitted S3 `AGENTS.md` is not copied wholesale.

## Retained and excluded work

- The five source lineages outside the canonical R1 ancestry were not blanket merged. The local unpublished 11-commit storage range, Phase 2 HIL history and durable-migration experiment remain intact at their original refs.
- Classic 4 MiB capacity claims, speculative allocation/retention values, legacy migration code and historical S3/C3 pairing evidence do not become current product guarantees. No fixed 128-event lifetime or new partition/retention policy was introduced.
- Backend and PWA code was not changed by the selected S3 source sequence. P2-D host SQLite fixtures do not prove live service interoperability, production credential provisioning, owner-generation receipt binding or active connectivity.
- Production event-body and identity deletion remain disabled. No board was flashed, reset, erased, repartitioned or re-enrolled; the historical seven C3 pending events were not accessed.

## Validation checkpoint

### Validation integration gap triage

```text
BUG_CLASSIFICATION=TEST_INFRA_ONLY
REQUIREMENT_SOURCE=Makefile lab-build target and the newly integrated S3 HubRuntime source dependency
DECISION_IDS=NONE
TASK_SCOPE=Link the S3 durable outbox source in the existing host simulator build so backend Python tests can build/run against the integrated runtime
OUT_OF_SCOPE=Product behavior, Node/BAT-C8 changes, backend semantics, physical qualification
```

The first integrated `make python-test` attempt failed before Python tests ran:
`lab-build` linked `HubRuntime` without `durable_event_outbox.cpp`, leaving
`DurableEventOutbox::replay_fence_matches` undefined. The existing simulator
link now includes that implementation file. The rerun built the simulator,
passed the backend durable-commit host test and ran 344 Python tests: 341 passed,
one failed and two errored. Failures are outside the changed line: two G01
capacity tests raise `KeyError: RetirementBank` because the current capacity
fixture lacks that key; one HIL infrastructure test expects the obsolete exact
text `validation-fast: hil-tooling-test hil-host-check` although the current
target includes additional prerequisites. These remain FAIL/ERROR; no unrelated
capacity policy or test expectation was changed. The P2-D bridge result in the
same run was PASS: 300 events committed, zero pending, three duplicate
submissions and one logical effect set, 90,112 allocated bytes, 26,458 ms
measured catch-up and three backend restarts.

The source branch's P2-C/P2-D evidence is retained under `docs/exec-plans/evidence/` with its raw logs. Integrated-tree fresh reruns: focused BAT-C8 C++ (72 checks) and Python (9 invariants), S3 outbox, runtime, replay/checkpoint, identity compaction, completion reclamation, mixed-body reclamation, P2-D HTTP/HTTPS, Node recovery/retirement, commissioning crypto and backend commit host tests PASS. Mixed-body results: 42 mutation boundaries/84 cuts; 32 reclaim/refill windows/3,232 admissions; six-node 12 windows/1,440 admissions; 32,768 POSIX allocated bytes recovered, 57,344 temporary peak, 20,480 protected copy workspace. P2-D contract cases: 14 invalid receipt modes, 200 pending events, 16 staged queue peak and 64 retry hints; HTTPS framing bounds 2,048-byte body, 1,024-byte response and 256-byte I/O buffer. `make cpp-test` FAILS at `test_node_offline_resilience` expecting `next_sequence()==1001` after 1000 attempts. The S3 replay-fence source advances sequence only after durable admission; source P2-D evidence records the same assertion. It remains FAIL, and Node/BAT-C8 was not changed to silence it.

Clean ESP-IDF 6.0.3 target builds PASS using temporary build directories (no flash action):

| Target | Output | Size | Configured smallest app slot | Margin | SHA-256 |
|---|---|---:|---:|---:|---|
| ESP32-S3 | `/tmp/ghar_sajag_r1_s3_integration_build/build/gs_r1_s3_hub.bin` | 1,865,056 bytes (0x1c7560) | 4,194,304 bytes | 2,329,248 bytes (56%) | `5e61c6eaf9f644e02a78d8bc29b2b79601fd2f34e34ab2971a44f7e0c9b9fcb4` |
| ESP32-C3 | `/tmp/ghar_sajag_r1_c3_integration_build/build/gs_hw_m1_node.bin` | 931,424 bytes (0xe3660) | 1,966,080 bytes | 1,034,656 bytes (53%) | `c2085e1a6cd177f30a6974c1d921c98d190dde1d902585e4b287a06b141e732e` |

The S3 build used the current checked-in `sdkconfig.defaults` in an isolated temporary config and produced a 4 MiB app slot in the build profile; this does not approve commercial partition sizing or establish physical flash capacity. The two temporary build output directories were removed after recording build logs, image hashes and partition margins to recover `/tmp` space; the output paths above identify the build-time images, which are not retained or committed. No physical test was run.

Focused sanitizer validation used GCC ASan+UBSan (`-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer`) with isolated object files under `/tmp/r1-consolidation-asan-objects`. Mixed-body compaction PASS (42 mutation boundaries/84 before-after cuts, 32 windows/3,232 admissions, six-node 1,440 admissions; sanitizer process peak RSS 376,868 KiB); incremental completion/replay/crash recovery PASS (6,556 completions, six crash cuts, wrong owner/key and missing proof rejected); P2-D HTTP contract PASS (14 invalid receipt modes, pending 200, batch peak 16, retry hint peak 64, completion persistence cuts); HTTPS channel PASS (8 modes, configured size bounds). The first combined run stopped before the last two sanitizer targets because `/tmp` filled while separate clean C3/S3 build directories occupied about 471 MiB; only those task-created temporary build outputs were removed, and the P2-D/HTTPS sanitizer targets then passed on rerun. No original worktree `sdkconfig`, `managed_components`, `prompt.txt` or repo build outputs were cleaned.

Other exact validation commands and outcomes:

| Command | Result |
|---|---|
| `make -j2 battery-c8-host-test s3-durable-outbox-host-test hub-segmented-outbox-runtime-host-test hub-runtime-checkpoint-host-test hub-identity-compaction-host-test hub-incremental-completion-host-test hub-mixed-body-compaction-host-test p2d-cloud-contract-host-test p2d-https-channel-host-test node-recovery-persistence-host-test node-retirement-protocol-host-test commissioning-crypto-host-test hub-backend-commit-host-test` | Focused tests PASS, including BAT-C8 72 C++ checks / 9 Python invariants, segmented outbox 6,556 records, 12,000 cumulative identity compactions, six-node mixed recovery and P2-D receipt/HTTPS checks. |
| `make cpp-test` | FAIL at `test_node_offline_resilience`: expected `next_sequence()==1001` after 1,000 attempts; same assertion is in source P2-D evidence. No Node behavior was changed. |
| `make app-test contracts` | PASS: 17 JS tests; four JSON schemas, protocol examples, power telemetry, battery config and OpenAPI verified. |
| `make python-test` after `lab-build` source-link fix | 344 tests: 341 PASS, one FAIL, two ERROR as described above. The P2-D SQLite bridge itself PASSed: 300 committed, 0 pending, three duplicates without duplicate effects, 90,112 allocated bytes, 26,458 ms host catch-up, three backend restarts. |

Target builds used ESP-IDF v6.0.3 (sourced `/home/udaybhan/.espressif/v6.0.3/esp-idf/export.sh`) and isolated configs/build directories. S3 command: `idf.py -C firmware/hub/target/esp32s3/idf -B /tmp/ghar_sajag_r1_s3_integration_build/build -D SDKCONFIG=/tmp/ghar_sajag_r1_s3_integration_build/sdkconfig -D IDF_TARGET=esp32s3 build`. C3 command: `idf.py -C firmware/node/target/esp32c3/idf -B /tmp/ghar_sajag_r1_c3_integration_build/build -D SDKCONFIG=/tmp/ghar_sajag_r1_c3_integration_build/sdkconfig -D IDF_TARGET=esp32c3 build`. Both exited 0; exact image sizes/hashes and configured app margins are in the table above.

At the initial integration snapshot (superseded by the follow-up closure below), repository context preflight passed on the integrated source checkpoint (`2026-10-09.001`); negative guard check using a deliberately incorrect test canonical ref returned INCOMPLETE/exit 1. `git diff --check` passed. Markdown relative-link validation covered seven updated/current files with zero missing paths. The PWA bridge/API/frontend scenarios described the failures reproduced at that checkpoint. PWA test/scenario files were unchanged from the starting R1 checkpoint. The initial source inspection found no production changes in the imported path, but did not isolate the local simulator's one-batch fixture behavior. The follow-up closure below records the direct reproductions and host adapter correction.

The canonical integration and final documentation closeout are committed as `ed6cffcdbfcbd69118e41b436ef616a0bea927db` and pushed to `origin/feature/r1-commercial-baseline`; `git rev-parse HEAD` and the actual GitHub ref matched at verification. Jira comments were read back successfully: GS-110/10321, GS-114/10322, GS-115/10323, GS-131/10324, GS-147/10325, GS-148/10326. No workflow or ranking changes were made. The current delivery record is in `docs/product/R1_WORK_STATE.md`.

At the initial integration snapshot, overall consolidation remained PARTIAL because aggregate C++/Python/PWA checks included documented failures. That test status is superseded by the follow-up closure below. Production backend contracts, canonical 72-hour workloads, live E2E, capacity/retention policy and physical qualification remain open. Focused suites, ASan/UBSan subset and clean S3/C3 builds passed as detailed above. Physical qualification is not claimed; production destructive event/identity reclamation remains disabled.

## Integrated software regression closure — 2026-10-10

This section records follow-up work in the same canonical R1 worktree. Intake
state was `feature/r1-commercial-baseline` at
`5648d90426fb12b584a009eac0a88e754ad909c6`; the only initial untracked path was
the existing S3 `managed_components/` directory, which remains untouched.
Context preflight passed at `2026-10-09.001`. `git ls-remote` could not resolve
`github.com` at intake, so remote HEAD was not verified during this closure.

### Failure classification and correction

| Failure / exact command | Expected vs actual and source | Requirement / baseline | Classification, correction and risk |
|---|---|---|---|
| `test_node_offline_resilience` — `make cpp-test` (initial exit 2) | Test expected `next_sequence()==1001` after 1,000 record calls, but only 28 ordinary motions were admitted and sequence was 29. `NodeRuntime::record()` (`firmware/node/runtime/node_runtime.cpp:52-90`) increments sequence only after queue preflight and durable store append. Its comment requires a contiguous admitted prefix because authenticated retirement uses a high-water. A rejected motion has no EventKey; admitted keys and timestamps are unchanged. | `docs/features/EVENT_DELIVERY_RETRY_AND_RECOVERY.md`; Node retirement contract in `docs/features/HUB_NODE_SECURE_COMMUNICATION.md`; durable-before-ACK and retained-event rules. The same assertion is present in the earlier P2-D source evidence and `core-baseline.log` reproduces it with START_HEAD CloudSync, so it predates this S3 integration. | `VALID_TEST_EXPECTATION_MISMATCH`. Test now asserts `admitted+1` both before and after queue drain; production behavior is unchanged. Low risk; verifies admission sequence continuity rather than requiring nonexistent identities/gaps. |
| `test_ledger_from_provider_layout` — `make python-test` (initial exit 2, ERROR) | `production_caps()` parsed `nvs_durable_blob_store.cpp`, which no longer owns the provider capacity switch, yielding `KeyError: RetirementBank`. Reading `nvs_store_inventory.cpp` and the retirement constant fixes the parser. The recomputed classic ESP32 fixture then measured 19.816% free NVS entries against its old test-only 20% minimum. | GS-D030 retires classic ESP32 as the active Hub target and preserves it as historical evidence. S3 commercial capacity/reserve are explicitly open; no current R1 20% NVS reserve requirement is approved. Pre-integration reproduction is unverified. | `VALID_TEST_EXPECTATION_MISMATCH`. The capacity/reserve-only classic-target case is now an explicit skip with GS-D030 and open S3 qualification in its reason. Its stale floor is not relaxed or reported PASS. Medium risk if interpreted as a current S3 result; the skip is explicit and does not qualify S3 capacity. |
| `test_raw_profile_and_extra_object_stop` — `make python-test` (initial exit 2, ERROR) | Same stale parser caused `KeyError: RetirementBank` at `tests/python/test_g01_coordinator_crash_model.py:645`. | Same classic-target/G01 historical model boundary; no S3 capacity inference. Pre-integration reproduction unverified. | `TEST_INFRASTRUCTURE_DEFECT`. Parser now reads current inventory source and retirement bound; the test passes with recalculated source-derived layout values. No product code changes. Low risk. |
| `test_phase1_gate_integration_has_one_authoritative_owner` — `make python-test` (initial exit 2, FAIL) | `tests/python/test_hil_phase1.py:809` required literal `validation-fast: hil-tooling-test hil-host-check`. The current Makefile correctly includes those dependencies plus required earlier gates, so the old exact substring failed. | Current repository Makefile target; test only. Pre-integration reproduction unverified. | `TEST_INFRASTRUCTURE_DEFECT`. Test now asserts both required dependency names on the authoritative `validation-fast` line without forbidding other valid prerequisites. Low risk; does not skip the HIL tooling/host checks. |
| `test_each_care_toggle_round_trips`, `post-missing-activity-visible`, and `door-close-after-warning` — `make pwa-e2e-test` (bridge/API/frontend components initially exited 2) | `CloudSync::next_batch()` is capped at 16. The host `Lab.sync()` submitted only one batch per action; when synthetic heartbeats exceeded it, later original MOTION/DOOR_CLOSED EventKeys stayed pending. The API therefore lacked expected activity and presented the prior door as OPEN; frontend consumed that incorrect fixture snapshot. Direct backend ingestion of the same DOOR_CLOSED event updated state to CLOSED, isolating this to test infrastructure. Relevant checks: `tests/pwa_bridge_test.py:80-84`, `tests/functional/scenario_catalog.json` scenarios `post-missing-activity-visible` and `door-close-after-warning`. | F08/F11 later activity visibility and F09 door chronology/closure in the current routine/caregiver behavior documents; `docs/features/ROUTINE_ACTIVITY_AND_INCIDENT_RULES.md` and `docs/features/CAREGIVER_ACTIONS_AND_NOTIFICATIONS.md`. First proven failure is current intake HEAD; pre-integration run is unverified. | `TEST_INFRASTRUCTURE_DEFECT`. `tools/sim/local_lab.py::Lab.sync()` now refreshes and submits bounded batches until `pending_cloud==0`, then proceeds with the single host heartbeat. Original EventKeys, timestamps, door-open/closed types and resident actions are retained. Medium risk limited to host fixture catch-up behavior; no production/backend/frontend change. |

### Exact validation outcomes after correction

| Command | Exit | Result |
|---|---:|---|
| `make cpp-test` | 0 | PASS, 1,479 checks; sequence assertion now verifies the contiguous admitted prefix. |
| `make python-test` | 0 | PASS, 344 tests; 343 passed and one explicit classic-target capacity/reserve skip. Backend commit and P2-D SQLite bridge passed. |
| `make pwa-e2e-test` | 0 | PASS: 12/12 bridge tests, complete catalog API assertions, complete frontend interpretation/render assertions. |
| `make app-test contracts` | 0 | PASS: three JavaScript test files; four JSON schemas, protocol examples, power telemetry, battery config and OpenAPI. |
| `make battery-c8-host-test s3-durable-outbox-host-test hub-segmented-outbox-runtime-host-test hub-runtime-checkpoint-host-test hub-identity-compaction-host-test hub-incremental-completion-host-test hub-mixed-body-compaction-host-test p2d-cloud-contract-host-test p2d-https-channel-host-test node-recovery-persistence-host-test node-retirement-protocol-host-test commissioning-crypto-host-test hub-backend-commit-host-test` | 0 | PASS: focused BAT-C8, S3 storage/durability/replay/reclamation, P2-D channel, Node persistence/retirement and commissioning gates. |
| `make contracts` (`python3 scripts/verify_contracts.py`) | 0 | PASS: four JSON schemas, protocol examples, power telemetry, battery config and OpenAPI. This repository target is the available contract validator; it does not claim Markdown link validation. No link checker was added. |
| Selected ASan/UBSan and clean C3/S3 builds | Existing evidence applies | No firmware implementation/build inputs changed. Previous evidence remains attached above; these are not physical/production qualification. |

The initial sandboxed PWA bridge command was blocked at loopback bind (`EPERM`);
the exact PWA gates were rerun with loopback permission and reproduced the
documented failures before the host adapter correction. No tests are classified
as `HARDWARE_REQUIRED`; all physical HIL remains not run and unauthorized here.
No product requirements or decision log entries changed; context version remains
unchanged. BAT-C8 physical qualification is separately gated by its existing
approved plan. Overall source consolidation remains partial for the unrelated
open production backend, 72-hour workload/capacity, S3 physical durability/FOTA
and physical battery gates.

### Regression-closure delivery and Jira sync

Validated regression changes were committed as
`dfc24d1db88fe6cd0fa7a51232a10f4152a4d5ae` (`Close integrated host regression
failures`) and pushed normally to
`origin/feature/r1-commercial-baseline`. The actual remote ref was read back as
the same hash. `git status --porcelain` showed only the pre-existing untracked
S3 `managed_components/` directory; tracked files are clean. No generated file,
secret, hardware artifact or unrelated modification was staged.

Dated Jira comments were added without changing issue rank/status: GS-110/10327,
GS-114/10328, GS-131/10329 and GS-148/10330. GS-114 records software readiness
for its separately planned physical qualification; no physical test was started.
