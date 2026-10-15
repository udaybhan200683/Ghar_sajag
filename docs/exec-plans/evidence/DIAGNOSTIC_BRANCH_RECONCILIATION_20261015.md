# Diagnostic Branch Reconciliation — 2026-10-15

## Executive summary

Both diagnostic tips were verified against canonical `feature/r1-commercial-baseline` at `1eba6c561e8a908fc899219cb7098af30ddcff80`. Each branch has one unique commit outside canonical ancestry and no additional local commits. Neither branch is checked out in a registered worktree. Local and remote refs match the expected SHAs.

Neither branch contains unique production behavior. The Node branch adds temporary `ACKDIAG_*` target logging and recovery ACK tests. The Hub branch adds temporary journal outcome fields/logging and tests. Canonical already implements the ACK-retirement and journal outcome policies through the current runtime, persistent storage and outbox architecture.

The audit found two useful regression gaps and closed them in existing registered suites: ACK retirement after restoring supported v1/v2 retained business records, and the serialized ACK class for legacy `HubJournal` Stored/Duplicate/Full/StorageFault results. No production source changed. The target suites pass after these additions.

The branches are semantically ready for eventual retirement without a history merge, after final local-file/evidence checks. They remain intact; this task did not delete, merge, or rewrite either branch. Host tests and the historical diagnostic records do not establish current commercial R1 qualification. The current commercial storage path remains the segmented outbox, with its separate capacity, retention and physical qualification requirements.

## Repository and Git checkpoints

| Ref | Local SHA | Remote SHA | Unique commits outside canonical | Worktree |
|---|---|---|---:|---|
| Canonical `feature/r1-commercial-baseline` | `1eba6c561e8a908fc899219cb7098af30ddcff80` | `1eba6c561e8a908fc899219cb7098af30ddcff80` | — | `/home/udaybhan/projects/Ghar_sajag_r1` |
| `diag/bat-c8b-ack-retirement` | `d67e14234cee50debc657ee83be4d44e184e39ce` | same | 1 | None |
| `diag/hub-journal-rejection` | `e431dd730555ad8d34a5b3830f36c1b57d227490` | same | 1 | None |

Both diagnostic commits descend from common boundary `808080e94b6958153952ce16eb56c1ad37a9ad01`; their SHAs are not reachable from canonical. This is the **Git ancestry** result only. Canonical local/remote HEADs agree. The context preflight passed (`2026-10-13.001`). Tracked canonical files were clean at preflight; existing unrelated untracked firmware/build, managed-component and GS-114 physical-evidence content was inventoried and left in place.

No second process was found writing canonical. The other Codex process and local simulation were confined to `Ghar_sajag_r1_integration`; dashboard integration was left untouched. FOTA worktree and branch were left untouched. Jira search for the diagnostic branch names and full commit SHAs found no issue explicitly depending on either ref. No branch or worktree operation was performed.

## Historical commit contents

### `d67e14234cee50debc657ee83be4d44e184e39ce` — Add ACK retirement diagnostics

- **Target instrumentation:** Adds `ACKDIAG_RESTORE`, `ACKDIAG_RETAINED_KEY`, `ACKDIAG_PENDING_KEY`, `ACKDIAG_ACK`, pending/retained lookup and send records in the historical C3 adapter. These are conditional HIL diagnostics, not Node behavior or a security control.
- **Historical regression:** Adds `persisted_ack_case` to the old-path `node_recovery_persistence_validation.cpp`; it fabricates authenticated v1/v2 envelopes, restores a retained Motion identity, rejects a Rejected ACK, accepts a matching Durable ACK, saves the resulting state and verifies the event is gone after reload. It invokes the ACK data-plane codec.
- **Build change:** Adds `data_plane_codec.cpp` to the old persistence-test command.
- **Canonical mapping:** The source moved to `code/firmware/node/target/esp32c3/node_runtime_adapter.cpp`; `NodeRuntime::acknowledge` remains in `code/firmware/node/runtime/node_runtime.cpp`; encrypted recovery decode/restore is in `code/firmware/node/storage/node_recovery_persistence.cpp`. The runtime logs the actual ACK and the production `recovery_snapshot` API already exposes keys for test/evidence use. No current requirement calls for the historical `ACKDIAG_*` format.

### `e431dd730555ad8d34a5b3830f36c1b57d227490` — Diagnose Hub journal event rejection

- **Runtime instrumentation:** Extends historical `ProcessResult` with commit result, record counts and capacity; records `Stored`, `Duplicate`, `Full`, and `StorageFault` in `run_state_once`; emits `HUB_JOURNAL_COMMIT` in target HIL builds. The production ACK decision remains the existing mapping: Full/StorageFault → Rejected; Duplicate/Stored → Durable.
- **Historical regression:** Adds Full and StorageFault mapping assertions, unchanged count checks, ACK wire encode/decode, retained old EventKey acceptance with newer authorized transport session, duplicate behavior after restart, and legacy append-only `acknowledge_cloud` capacity behavior.
- **Build change:** Adds `data_plane_codec.cpp` to the old journal-test command.
- **Canonical mapping:** `HubRuntime::run_state_once` in `code/firmware/hub/runtime/hub_runtime.cpp` maps failed commit outcomes to Rejected and known duplicates to Durable. `HubJournal` persists and deduplicates the historical journal format. Current production R1 storage is `DurableEventOutbox` via `OutboxJournalBackend`; its admission/reclamation rules are independent of the old fixed 128-entry journal. Historical counts and diagnostic fields are not required by current product behavior.

## Scenario reconciliation matrix

“Canonical test” cites current assertions; the two additions in this audit are marked **added**. All dispositions below are the result after the focused additions.

### Node ACK retirement (`diag/bat-c8b-ack-retirement`)

| ID | Historical source/test | Canonical implementation | Canonical test/assertion | Disposition | Explanation / action |
|---|---|---|---|---|---|
| N1 | `node_recovery_persistence_validation.cpp::persisted_ack_case` | `NodeRecoveryRepository::load`; `NodeRuntime::restore_recovery` | `node_recovery_persistence_validation.cpp`: reloads Ready v1/v2 fixture with pending+retained Motion; exact EventKey assertion (**added**) | COVERED | v1 and v2 persisted business events restore their original source/session/sequence. No production change. |
| N2 | Same historical helper; Rejected ACK assertion | `NodeRuntime::acknowledge` | `test_main.cpp`: Rejected/volatile/wrong identity leave persisted event; legacy v1/v2 Rejected case remains pending (**added**) | COVERED | Rejected outcomes preserve Node evidence; exercise on restored legacy rows as well as current runtime. |
| N3 | Same historical helper; ACK policy | `NodeRuntime::acknowledge` and `NodeRadio::acknowledge` | `test_main.cpp`: “ReceivedVolatile does not retire a business event”; board-stack lossy-channel assertion | COVERED | A volatile receipt does not release durable business data. |
| N4 | Historical branch tests only Rejected and matching Durable ACK, not a mismatched key | Exact EventKey check in `NodeRuntime::acknowledge` / retained store | `test_main.cpp`: “wrong EventKey ACK cannot retire another event”; legacy fixture wrong-sequence assertion (**added**) | COVERED | Wrong sequence cannot retire the restored event. |
| N5 | Historical helper saves and reloads empty state after Durable ACK | `NodeRuntime::acknowledge`; `NodeRecoveryRepository::save` | Current persistence test verifies pending empty after reload; new v1/v2 fixture checks pending and retained empty after reload | COVERED | Only exact Durable ACK retires; retirement is persisted. |
| N6 | Historical helper requires `next_message` to keep the old business key | `NodeRuntime::restore_recovery` / `NodeRadio::next_due` | Current persistence assertion on original key; board-stack `restarts_without_pir` sends retained event after Hub and Node restart | COVERED | Link-session refresh does not rewrite business identity or lose retryability. |
| N7 | Historical helper tests v1 and v2 retained Motion records | Recovery decoder accepts versions 1–3 | Existing test verifies v2 Heartbeat migration; added v1/v2 Motion restore/ACK/reload cases | COVERED | Compatibility code explicitly accepts v1/v2; business-event ACK lifecycle was the missing focused assertion and is now covered. |
| N8 | Historical runtime diagnostics show counts before/after; helper checks ACK behavior | Exact-key Node retirement plus authenticated frame handling | `test_main.cpp`: wrong-key and repeated Durable policy; board-stack `lossy_channel` rejects tampered/replayed ACK; `restarts_without_pir` rejects old-session ACK | COVERED | Duplicate, stale-session and invalid ACKs cannot cause second or incorrect retirement. |

### Hub journal rejection (`diag/hub-journal-rejection`)

| ID | Historical source/test | Canonical implementation | Canonical test/assertion | Disposition | Explanation / action |
|---|---|---|---|---|---|
| H1 | Historical Hub journal test: Full → Rejected; encoded ACK | `HubRuntime::run_state_once`; `HubJournal::commit` | `multinode_host_validation.cpp::ten_node_journal_full_is_explicit`; added `hub_journal_persistence_validation.cpp::runtime_ack_mapping` fills 128 entries and decodes Rejected ACK | COVERED | Full does not produce Durable ACK; exact legacy boundary now has explicit wire-level assertion. |
| H2 | Historical test: StorageFault → Rejected | Journal commit and runtime result mapping | `hub_fresh_install_validation.cpp` failed-write path; added persistent-journal StorageFault with decoded Rejected ACK | COVERED | Failed durable write leaves journal count unchanged and serializes Rejected. |
| H3 | Historical `journal_count_before/after` fields | Journal records/size and outbox committed prefix | Added legacy full/fault assertions; `hub_storage_correctness_validation.cpp::admission_refusal_test` asserts no body/identity/state commit; modern full path preserves committed prefix | COVERED | Diagnostic counters are unnecessary; the test observes actual committed state. |
| H4 | Historical duplicate identity result | Journal/outbox exact-key duplicate detection | `hub_journal_persistence_validation.cpp`: duplicate after restart is Durable without reducer change; board-stack duplicate has one logical effect | COVERED | The duplicate receives a safe Durable response without second application effect. |
| H5 | Historical duplicate replay/restart checks | `HubJournal::attach_persistence` / `restore_from_journal`; current checkpoint/outbox recovery | `hub_journal_persistence_validation.cpp` restart/dedupe/reducer replay; `board_stack_e2e_validation.cpp::restarts_without_pir` | COVERED | Durable event and reducer state survive restart; retry does not duplicate logical effect. |
| H6 | Historical old business session with newer authorized transport session | Authenticated ingress separates transport session from retained EventKey | `board_stack_e2e_validation.cpp::restarts_without_pir`: Hub restarts/rejoins, Node resends original retained key over fresh link; Hub dedupes and ACKs | COVERED | Current architecture preserves the old event identity while authenticating the new link session. |
| H7 | Historical tests newer session acceptance and stale identity handling | `HubRuntime::authenticated_radio_message_callback` and session admission | `board_stack_e2e_validation.cpp`: old ACK rejected after Hub rejoin; stale payload under new authenticated envelope rejected; current source includes these assertions | COVERED | Old/stale/unauthorized session material remains rejected. |
| H8 | Historical 128-entry journal must remain full after cloud receipt | Legacy append-only `HubJournal` completion semantics | `hub_journal_migration_validation.cpp`: Full at event 129 even after completion; asserts completion does not free logical event capacity and state survives recovery | COVERED | This limitation remains true only for that legacy journal. It is not imposed on R1 outbox. |
| H9 | Historical diagnostic branch includes fixed-journal capacity behavior | Current segmented `DurableEventOutbox` and authorized reclamation | `hub_mixed_body_compaction_validation.cpp::repeated_body_capacity`, `hub_runtime_checkpoint_validation.cpp` reclaim/refill/recovery and protected-reserve assertions | COVERED | Current outbox uses its own protected capacity, owner proofs, checkpoint and crash-safe reclaim contract. No legacy algorithm is copied. |
| H10 | Historical test encoded Full Rejected ACK; runtime logger reports commit result | Target adapter serializes `ProcessResult::ack` via `make_node_ack` and `encode_node_ack` | Added `require_wire_ack`: Stored/Duplicate decode Durable; Full/StorageFault decode Rejected | COVERED | Test now pins the commit-to-wire class mapping without extending `ProcessResult` or adding diagnostic logger fields. |

## Gap decision and changes

Before the additions, two test gaps were meaningful:

1. **N7:** the decoder accepted v1/v2, but canonical ACK persistence testing combined legacy migration with Heartbeat and current-format ACK testing with Motion. It did not prove that a supported legacy retained business event survives a retry and exact Durable retirement. Added v1 and v2 authenticated Motion fixtures and assertions in the existing `node-recovery-persistence-host-test` suite.
2. **H1/H2/H3/H10 integration:** canonical tests covered modern outbox refusal, legacy storage failures and ACK codec classes, but did not directly join the legacy `HubJournal` Full/StorageFault result to serialized ACK class and unchanged committed count. Added this mapping to the existing `hub-journal-persistence-host-test`. Its existing Make target now links the already-existing `data_plane_codec.cpp` needed for the wire assertion.

No new target or parallel implementation was added. No historical `ACKDIAG_*` logging, `ProcessResult` outcome fields, verbose journal logger, or fixed-capacity rule for the modern outbox was retained. The historical diagnostics are useful provenance but not current production requirements. No canonical production source changed.

## Focused validation

Commands run from the canonical repository root:

| Command | Result | Evidence |
|---|---|---|
| `bash tools/context/ghar_sajag_context_preflight.sh` | PASS | context version `2026-10-13.001`; canonical source and branch matched. |
| `make -C code node-recovery-persistence-host-test` | PASS | `P2-PERSIST-NODE-RECOVERY HOST PASS encrypted bounded recovery`; includes the new v1/v2 Motion ACK-retirement cases. |
| `make -C code hub-journal-persistence-host-test` | PASS on final run | `P2-PERSIST-HUB-JOURNAL HOST PASS capacity=128 full=129 replacement/dedupe/restart/tamper/write-fault/reducer-replay`; includes Full/StorageFault/Duplicate ACK codec checks. |
| `git diff --check` | PASS | No whitespace errors. |
| Existing board-stack E2E receipt | PASS, reused | `GS130_RISK_REGRESSION_20261014.md`: board E2E 10 groups / 398 checks; current `board_stack_e2e_validation.cpp` contains the mapped restart/session assertions. No rerun was needed for this test-only change. |

The initial Hub target run exposed a missing codec link dependency, which was added to that existing target. Two subsequent fixture setup attempts exposed the legacy journal's fixed 128-slot persisted capacity and required Node authorization; the fixture was corrected to use the actual supported capacity and authorize its event source. The final run passed. These were test setup failures, not product behavior changes.

No `validation-fast`, `release-gate-final`, browser campaign, target build, physical HIL, flash, reset, or device access was performed. Historical and host test PASS evidence does not establish commercial R1 physical qualification. BAT-C8 P1–P9, GS-148 storage capacity/retention/physical acceptance, P0 product status, and known Hub migration failure remain at their existing separately tracked dispositions.

## Retirement readiness

| Branch | Semantic reconciliation | Git ancestry | Missing required functionality/tests/evidence | Retirement recommendation |
|---|---|---|---|---|
| `diag/bat-c8b-ack-retirement` | Complete | One unique historical commit outside canonical | None after N7 regression addition; historical temporary target logs are not required evidence | Ready for later owner-approved ref retirement without history merge, after final local-file/evidence preservation check. |
| `diag/hub-journal-rejection` | Complete | One unique historical commit outside canonical | None after ACK-result mapping addition; diagnostic fields/log format are not required evidence | Ready for later owner-approved ref retirement without history merge, after final local-file/evidence preservation check. |

Retirement is not performed here. Keep both branch refs until the separate approved cleanup task verifies target-specific local files and evidence. Do not treat semantic equivalence as Git ancestry preservation; the unique commit objects are not ancestors of canonical. The relevant negative scenarios are now represented by canonical production-code tests and the existing committed qualification evidence; no historical production patch needs merging.

## Next plan

1. Review this report and the two focused regression additions.
2. After owner review, retire only the two diagnostic refs in a separate explicitly scoped cleanup task, first confirming no branch-specific local evidence or active dependent task has appeared.
3. Continue BAT-C8 physical work under GS-114 with its current fixture/image authorization requirements. Keep current commercial storage, capacity, migration and physical qualification blockers under GS-148; this diagnostic reconciliation does not close them.
