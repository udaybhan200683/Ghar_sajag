# GS-148 S3 replay-fence diagnostic and storage-history checkpoint

**Date:** 2026-10-12 UTC
**Authorized scope:** GS-148 comment 10499; narrow diagnostic only.
**Canonical source start:** `abacd8ce1fc54b8641dcefbdcdb8f585c758c20f`, branch `feature/r1-commercial-baseline`.
**Physical devices:** NOT ACCESSED. No USB enumeration, serial open, firmware write, storage read, reset, reprovisioning or PIR stimulus occurred.
**Status:** host diagnostics and deterministic tests implemented; physical S3 root cause remains UNKNOWN; GS-114 physical retest is NO-GO.

## Observed error and what it establishes

The preserved S3 log says `S3 replay-fence publication failed; admission closed` while the Hub handles a complete authenticated `NodeRetirementFragment`. The source reaches this diagnostic only after the retirement report was either accepted as `Duplicate`, or a `Prepared` retirement snapshot had been selected by a durable checkpoint, recovered and verified against the prepared reference. The saved log does not identify which of the subsequent selected-state/snapshot/checkpoint loads, LittleFS witness preconditions/publication/readback, or runtime binding failed. No host fixture recreates the physical board's stored contents, so the physical lower-level cause remains unknown.

The C3 `rst:0x15 (USB_UART_CHIP_RESET)` is a separate observed reset class. Existing observer analysis shows pySerial opens the file descriptor before applying requested DTR/RTS-low states. That makes interface-open/reset coupling plausible, but does not prove the reset's cause or timing. A passive receive tap with no modem-control lines is a candidate only; no host-only check can establish that it is physically non-resetting. The C3 and S3 failures may be trigger and consequence through rejoin/retirement reporting, but the saved logs do not prove that relationship.

## Diagnostic contract now in source

The Hub emits one sanitized terminal message synchronously at the failed reconciliation branch, before the handler continues without its retirement-report ACK. It includes a stable stage ID, safe result category, `BOOT`/`DUPLICATE`/`PREPARED` path, and `admission=CLOSED` or `PRIOR_FENCE_VALID`. It omits device/Home identifiers, event payloads, digests, keys, nonces and cryptographic material. For ambiguous publication failures, the existing outbox closes admission before returning the classified failure; logging happens immediately afterward in the serialized Hub owner path. That fail-closed ordering was deliberately preserved rather than delaying closure for logging. The report handler's existing `continue` remains before its retirement ACK. The replay-fence helper does not create an event or issue an application Durable ACK.

| Stage | Meaning | Available result detail |
|---|---|---|
| RPF00 | Reconciliation completed | `BOUND` or `ALREADY_PUBLISHED` |
| RPF01 | Selected durable checkpoint recovery failed | generic durable checkpoint recovery result |
| RPF02 | Selected checkpoint lacks retirement-snapshot reference | selected reference missing |
| RPF03 | Selected retirement snapshot reload/verification failed | storage interface returns only boolean; read/authentication/digest subreason is unavailable |
| RPF04 | Reducer checkpoint reload failed | storage interface returns only boolean; read/decode subreason is unavailable |
| RPF05 | Reducer checkpoint is absent | explicit missing result |
| RPF06 | Replay-fence witness precondition, publication or readback failed | stable enum category such as `EVENT_PUBLICATION_INVALID`, `FENCE_ROOT_PUBLISH_FAILED`, `FENCE_ROOT_READBACK_FAILED`, `FENCE_ROOT_READBACK_MISSING`, or `FENCE_ROOT_READBACK_MISMATCH` |
| RPF07 | Runtime refused the matching fence bind | stable category such as `SNAPSHOT_EPOCH_MISMATCH` or `OUTBOX_FENCE_MISMATCH` |
| RPF08 | Required retirement storage owner dependency unavailable at boot | `RETIREMENT_STORAGE_OWNER_UNAVAILABLE` |

Underlying BlobStore/LittleFS methods return booleans, not errno/native filesystem detail. The new names distinguish all information available at those interfaces; they do not claim an underlying physical I/O code. A publication failure is deliberately called `FENCE_ROOT_PUBLISH_FAILED`, not “not written”: it may have reached persistent media before returning failure. Recovery determines which fence actually persisted.

The former boolean `publish_replay_fence` and `bind_replay_fence` APIs remain wrappers with the same success result and condition ordering. No root/checkpoint encoding, NVS/LittleFS record, ordering, ownership epoch, EventKey, event ACK condition or recovery policy changed. Existing ambiguous-write behavior remains fail-closed.

## Deterministic host fault-injection coverage

`hub_runtime_checkpoint_validation.cpp::replay_fence_diagnostic_tests` exercises production `HubRuntime` reconciliation, production `RetirementSnapshotRepository`, `RuntimeStateStore` and `DurableEventOutbox`, with faults injected at BlobStore/RuntimeStateFiles/SegmentStore boundaries. It has 21 explicit `require` assertions. The existing before/after publication-cut test now also asserts the exact sanitized publication category and outbox mutation closure, then reopens the outbox and checks which fence actually survived.

| Requested case | Host evidence |
|---|---|
| A. Selected retirement snapshot reload fails | Injected retirement BlobStore read failure returns RPF03; outbox remains healthy and unchanged. |
| B. Matching reducer checkpoint reload fails or is absent | Injected `application.head` read failure returns RPF04; deleting it returns RPF05. |
| C. Snapshot/checkpoint identity disagrees | Wrong epoch reaches runtime binding and returns RPF07 `SNAPSHOT_EPOCH_MISMATCH`; no event record is admitted. |
| D. Witness prevalidation fails | Injected publication-head read failure, malformed publication, invalid epoch and invalid reference return stable distinct categories at RPF06. |
| E. LittleFS lifecycle-root publication fails | Pre-write failure returns `FENCE_ROOT_PUBLISH_FAILED`, faults the outbox, and mutates no event records. |
| F. Publication is interrupted at a defined host boundary | Existing before-write and persist-then-fail cuts both return the publication category; reboot selects old fence before write and new fence after write. |
| G. Fence readback/integrity fails | Read I/O, absent readback and corrupted readback have distinct stable categories; outbox faults closed. |
| H. Runtime refuses inconsistent bind | Bind reports a specific safe reason and sets runtime replay-fence fault/not-ready. |
| I. Valid duplicate retirement report | Production repository classifies the identical authenticated fixture report `Duplicate`; repeat fence reconciliation returns `ALREADY_PUBLISHED`. |
| J. Valid prepared report | Fixture creates the snapshot with production `apply_authenticated_report`, selects it through production durable checkpoint, and reconciliation publishes/binds the reference. |
| K. Stale/mismatched owner/epoch/session report | Existing `hub-retirement-snapshot-host-test` and `node-retirement-protocol-host-test` regressions pass; wrong owner/generation/session checks remain fail-closed. |
| L. Restart/recovery at publication boundaries | Reopened outbox recovers the actual old/new witness for each publication cut, without fabricated event data. |

The adapter code was reviewed to confirm the failed reconciliation branch `continue`s before sending the retirement-report ACK. The helper does not perform event admission, reducer effects, or event Durable ACK. Host helper tests are not a hardware test of the ESP-IDF task/transport callback; target compilation is separately reported below.

## Validation executed

Base source revision for the implementation is `abacd8ce1fc54b8641dcefbdcdb8f585c758c20f`; host profile is C++17, `GS_PRODUCT_AI=0`, trace disabled, OpenSSL host crypto. The worktree diff fingerprint is recorded in the final work-state/Jira closeout after all documentation edits.

| Command | Result | Detail |
|---|---|---|
| `make -j2 hub-runtime-checkpoint-host-test hub-retirement-snapshot-host-test hub-segmented-outbox-runtime-host-test node-retirement-protocol-host-test rejoin-host-test` | PASS, exit 0 | Production checkpoint/fence/recovery harness; retirement owner checks; S3 outbox runtime; Node retirement protocol; secure rejoin. New diagnostic function has 21 explicit assertions. Existing 12,000 cumulative identity / 6,556 completion model output remained unchanged. |
| `make validation-framework-test` | PASS, exit 0 | GS-116 registration, false-PASS, stale-source, failure propagation and physical-NOT_RUN integrity: 39 tests. |
| `make feature-coverage-test` | PASS, exit 0 | 151 feature rows / 204 source modules / 14 physical cases; 19 matrix/registry tests. This validates traceability consistency, not semantic or physical completeness. |
| `ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 make -j2 hub-runtime-checkpoint-host-test CXXFLAGS='-std=c++17 -O1 -g -Wall -Wextra -Werror -pedantic -DGS_PRODUCT_AI=0 -fsanitize=address,undefined -fno-omit-frame-pointer' TRACE_FLAGS=-DGS_ENABLE_TRACE=0 HOST_TOOLCHAIN_GUARD=-B/usr/bin` | PASS, exit 0 | Distinct sanitizer object profile; same checkpoint/replay-fence/crash-boundary executable. LeakSanitizer was not run. |
| `python3 scripts/build_validation_targets.py` | PASS, exit 0 | Clean paired production-profile C3/S3 target build and package with ESP-IDF 6.0.3; report `build/validation_targets/gs116-whsxuzya/report.json`; no flash target invoked. C3 934,192 bytes; S3 1,870,944 bytes. Target compile only, not physical qualification. |

The paired build report records source HEAD `abacd8ce1fc54b8641dcefbdcdb8f585c758c20f`, source fingerprint `5082c629d484310831ac73588e7e41a606a5bc0833c0c7f5ac8cfa0d073ac693`, ESP-IDF 6.0.3 and profile `production GS_HIL_BUILD=OFF`. C3 application SHA-256 is `50cd6cc007e84c25898fc86fadff1784a8bf85a4237b52699206f4ced816c067` (934,192 / 1,966,080 slot bytes); S3 application SHA-256 is `3a432fa7bd671e91cb6b4f93d437f81b0892aa878ad5e4173e196fb4623f098a` (1,870,944 / 4,194,304 slot bytes). The packaged S3 asset matches the C3 image hash. The bundle includes bootloader, partition table, OTA metadata and application images; `physical_status=NOT_RUN`, `hardware_actions=NONE`, `qualification=TARGET_COMPILED_ONLY`. The report marks `tracked_source_dirty=true`, as expected for the reviewed diagnostic changes, and these are build artifacts, not a claim of committed source provenance.

The untracked S3 `managed_components/` directory remained in place with 118 files; its file modification times predate this build. It remains untracked and is excluded from staging. Previous untracked redacted GS-114 evidence directories and logs also remain preserved.

The historical `hub-journal-migration-host-test` assertion at `tests/cpp/hub_journal_migration_validation.cpp:194` was not changed, skipped or rerun for this diagnostic. Its known `clean migration commits` failure is a separate legacy cross-owner-domain migration issue, independently classified `HISTORICAL_BASELINE_DEFECT` under GS-148/GS-145; it is not evidence about this S3 replay-fence failure. Release gate remains NOT_RUN.

## 4 MiB classic journal → S3 candidate storage reconciliation

| Historical problem | Old implementation | New implementation | Software evidence | Physical evidence | Remaining gap | Jira owner |
|---|---|---|---|---|---|---|
| Fixed 128-event Hub journal | Classic ESP32 adapter uses `NvsJournalSlotStore` with `kCapacity=128`; the 4 MiB target reserves a 128 KiB `gs_journal` NVS partition at `0x3E0000`. Source foundation is commit `7bffce5e884fe66a99168ba63223ec867f21585c` (2026-09-24). Append-only event/completion slots are not a lifetime-safe reclamation policy. | S3 integration commit `9ce54b52c940053ae89e9830bb265a0c1d033436` (2026-10-10) selects LittleFS `DurableEventOutbox` rather than the classic slot store. Its active target sets 16 segments × 128 KiB (2 MiB body segment budget in source comment) in a **4 MiB engineering-candidate** `gs_outbox`; `gs_state` is a 256 KiB candidate NVS partition. The S3 partition file is explicitly candidate/development, not commercial qualification. The 128 KiB *segment size* is not a 128-event limit. | Existing bounded byte/segment capacity and reclamation tests; prior GS-148 evidence includes 6,556 cumulative completion records and two 6,000-identity compaction windows (12,000 cumulative identity admissions). These are host workloads, not expected customer lifetime or flash endurance. | No current-image physical LittleFS capacity, power-cut, wear or endurance qualification. | Supported event volume, retention horizon, low-space behavior and flash endurance remain unqualified; 16 MiB flash does not establish unlimited storage. | GS-148 / GS-138 |
| Completed-event and identity growth | Old journal had no qualified safe production retirement/lifetime policy; fixed slots could fill. | S3 has byte-bounded encrypted body/outbox segments, a completion stream constrained by 512 KiB filesystem workspace, a 1 MiB RuntimeStateStore identity log, authenticated report/checkpoint-gated incremental completion/body/identity compaction code, a 512 KiB protected reserve and a fixed-size authenticated lifecycle root. Body retirement defaults disabled unless explicitly enabled at build/runtime; the candidate partition's actual free space/workspace can still block safe compaction. | P2-C host tests previously validated crash cuts, pending-body preservation, 6,556 completions and cumulative 12,000 identities. Current checkpoint test still prints prior identity-size metrics. | Target memory/PSRAM high-water, filesystem allocator rounding, repeated flash writes and physical recovery are not proven by POSIX fixtures. | P2-E/P2-F capacity, retention and endurance work is not authorized here. | GS-148 / GS-138 |
| Retirement and replay proof bounds | No LittleFS witness existed in the old slot model. | Three authenticated NVS retirement snapshot banks (6,100 bytes each); maximum 10 Node records and 32 pending EventKeys per Node report. The selected snapshot reference (epoch/bank/generation/digest) is joined to a fixed-size authenticated LittleFS lifecycle replay-fence root before runtime binding. Reducer checkpoint is bounded at 64 KiB; `ExactEventKeyLedger` has a 128-entry compile-time bound but repository search finds no production S3 runtime instance—do not mistake it for the S3 outbox's lifetime event cap. | Current source bounds and production-code host recovery/fence tests. | Original fixture state is inaccessible by authorization in this task; the saved physical error is not reproduced. | Verify product semantics/retention of these bounded structures and current target power-cut behavior under GS-145/GS-148. | GS-145 / GS-148 |
| Legacy development-format migration | The old importer has an ownership-domain disagreement and its `clean migration commits` assertion fails. | Current S3 production path rejects unsupported legacy NVS-to-outbox migration; current-format fresh install/recovery is a separate supported path. | Historical migration failure remains independently visible and GS-D001 keeps arbitrary dev-era migration outside R1 fresh-install acceptance. | No migration/erase performed. | Do not change importer or treat the legacy test as a replay-fence reproduction. | GS-148 / GS-145 |

The S3 outbox also uses a standalone 128-entry reducer-facing exact-key helper. It is not instantiated by the production S3 path found in this audit; durable S3 event identities are byte-bounded by `RuntimeStateStore`. Keep that distinction visible and do not infer its future status without the owning storage review.

## Diagnostic disposition and next action

The new terminal message distinguishes available software stages, but its snapshot/checkpoint interfaces and LittleFS wrapper return booleans. No underlying native filesystem errno or physical medium detail is available, so the original failure is **still UNKNOWN**. The C3 USB reset class is observed; opening-order causation is plausible but not physically proven. The two failures remain potentially related through rejoin-triggered retirement reporting, not proven causally linked.

**GS-114 remains NO-GO.** A separately authorized diagnostic deployment to the exact disposable S3 fixture or a separately risk-assessed observation setup is required to observe a new sanitized stage code without clearing its persisted state. Preserve current pairing and journals; do not reset, erase, reprovision, or use a host result as physical proof. GS-148 returns to OnHold after this checkpoint. Its production credential/CloudSync trust, historical legacy-migration defect, capacity/retention/endurance, and P2-E/P2-F work remain outside this authorization.

## Physical retest gate and remaining ownership

**GS-114 is physical NO-GO.** The saved pair had no correlated PIR → EventKey → authenticated S3 durable commit → matching application ACK → C3 retirement chain. No image has been flashed to gather the new diagnostic. A future diagnostic requires a separate explicit approval covering either (1) a reviewed diagnostic firmware build/deployment to the exact disposable fixture, or (2) a different independently validated, non-reset-risk observation setup. Before any retest, require observed RPF00/healthy admission without clearing state, verified fixture/session/pending events, a capture safety plan, and new explicit authorization for the precise test. Any unexpected reset, pairing/session loss, admission failure or missing ACK stops the campaign. Real motion remains separately prompted.

GS-114 remains In Progress. GS-148's broader capacity, production cloud trust, historical migration and physical qualification scopes remain outside this narrow checkpoint and return to OnHold after delivery. No product decision, storage migration or `CONTEXT_VERSION` change was made.
