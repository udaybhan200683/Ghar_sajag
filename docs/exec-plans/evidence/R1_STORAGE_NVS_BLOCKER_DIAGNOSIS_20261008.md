# NVS blocker diagnosis — 2026-10-08

Technical proof, not a product requirement or storage integration approval.
Context preflight PASS, branch `feature/r1-hub-storage-lifecycle`, context
`2026-10-07.003`, start `a3e9da9bfabf9ca56b68756fd2bdfd33539fc75a`.
Previous proof checkpoint: `4cdcaab169e95aa837d6438ff4b0084dd7e23564`.
After checkpoint only the task-request copy `prompt.txt` remained untracked.
All original probe/evidence/document changes were identified and checkpointed;
no unrelated source changes, conflicts, synchronization, hardware or policy change.

## Recommendation and stopping point

**Continue with NVS as the implementation candidate. Do not production-integrate
yet.** Cut1072 is a fault-harness power-interruption modeling defect, not evidence
of an ESP-IDF sudden-power-loss recovery bug. Independent report/selection keys
provide the small application transaction prototype. The unrestricted nine-segment
128 KiB mapping fails simultaneous maximum-HOT plus recovery/progress capacity.
A152 KiB isolated fixture completes that modeled peak;192 KiB is a defensible
partition-review candidate if retaining nine segments and this standalone-tail
mapping is required. A three-segment fixture also progresses at128 KiB, so
partition enlargement is **not** proven necessary for R1. Selecting its smaller
history/outage capacity requires the still-open information contract.

`NVS_CORRECTABLE_WITHIN_128K=UNPROVEN` for the complete R1 system;
`RAW_ADVANTAGE_PROVEN=NO`; `RECOMMENDED_BACKEND=NVS` as a technical candidate.
`MINIMUM_SAFE_STORAGE_BYTES=UNPROVEN` for R1; **155648 B is the modeled
nine-segment peak floor and observed passing size**, not a universal safe minimum.
Retain the4 MB Hub. No MCU/RAM need or hardware upgrade is established.
Stop backend/architecture exploration here. The remaining next steps are a
bounded policy decision, persisted authenticated credit/root/replay proof,
physical admission guard, target RAM/code/wear and rollback qualification.
Production implementation belongs to a separate task after those gates close.

## Evidence labels and reproducibility

- **ACTUAL ESP-IDF NVS EMULATION:** installed6.0.3, source commit
  `76f5dedd9950a3012fee8fb7d5586df21fc67802`; real NVS allocator/chunks/bitmap/
  GC/remount and Linux partition driver. All values remain length-matched dummy
  blobs, without the production codec, AEAD, backend service or reducer.
- **HOST-ONLY ALGORITHM MODEL:** prior lifecycle/admission/density regressions;
  copied ledger snapshots are not persisted credit transactions.
- **DERIVED CAPACITY ESTIMATE:**32-byte entry arithmetic and partition reviews.
  Extra chunks/fragmentation/GC-copy peaks are separately measured.
- **PRODUCTION/HARDWARE UNPROVEN:** firmware integration, flash encryption,
  partial four-byte programming, partially erased sectors, actual endurance,
  runtime heap/task/network/crypto peaks and rollback.

From the repository root, build the existing Linux probe with the environment
in its [README](../../../code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/host/storage/nvs_runtime_probe/README.md), then:

```sh
python3 code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/host/storage/nvs_runtime_probe/run_diagnostics.py fault
python3 code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/host/storage/nvs_runtime_probe/run_diagnostics.py capacity
python3 code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/host/storage/nvs_runtime_probe/run_diagnostics.py schedule
```

The budget can be reproduced with `python3 code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/host/storage/nvs_runtime_probe/review_budget.py`;
[derived ledger and temporary layout output](R1_STORAGE_NVS_DIAG_BUDGET_20261008.log)
preserves component arithmetic and generator inputs.

Runner logs record executable/source SHA256, commands, environment, every exit
status and terminal results. SDK temporary images are removed by **the exact
filename printed by that child** after the run; old images/evidence are preserved.
An initial exhaustive attempt filled `/tmp` with SDK scratch images and exited
SIGBUS at bank cut313. This is a resource failure, not a recovery failure;
[interrupted output](R1_STORAGE_NVS_DIAG_FAULT_INTERRUPTED_20261008.log) is retained.
After scoped cleanup and child-specific cleanup, the complete sweep passes.

## Baseline reconciliation

The original [proof](R1_STORAGE_NVS_RUNTIME_PROOF_20261008.md) and all its logs
are preserved in the checkpoint. Reproduction again fails cut1072 three times,
12-segment replacement, and admission139 after138 accepted maximum-HOT values.
See [baseline](R1_STORAGE_NVS_DIAG_BASELINE_20261008.log) and the full trace below.
The aborting unmodified executable buffered stdout in the baseline rerun;
its stderr/exit and later unbuffered trace jointly preserve the reproduction.

| Observation | Reconciliation |
|---|---|
|131072 partition;3885 live peak | Matches original192-HOT attempt at nine segments |
|31 nonblank+one erased;32-page GC peak | Call-boundary versus transient physical occupancy; newly instrumented report failure peaks3960 physical live entries and32 pages |
|118816 live entry bytes |3713 entries in the11-segment **report-progress** run, not a universal supported-live threshold |
|12-segment live entries |3844 after1000 cycles;3848 after10000. Both report replacements fail; preserve both numbers |
|32-HOT transient at least10336 B |32*6 entries*32=6144 plus4096 segment's131 entries*32=4192. Excludes root/report/page metadata and GC |
|297789032 programmed bytes | Original terminal counter **includes112616 setup bytes**. Post-setup bytes297676416;29,767.6416/cycle; ratio1.612810. Rounded1.613 remains correct |
|69755 erases;max2961 | Original10000 heavy cycles, after setup erase counters reset;6.9755/cycle |
|OTA margin101456 | Existing image1864624 in slot1966080; integration growth unmeasured |

## Cut1072 root cause

`FAULT_1072_REPRODUCED=YES`.
`FAULT_1072_CLASSIFICATION=FAULT_INJECTION_MODEL_DEFECT`.

[Full before/failure/cleanup/remount trace](R1_STORAGE_NVS_DIAG_FAULT_TRACE_20261008.log)
uses link wrappers around both `esp_partition_write` and `write_raw`, plus erase.
The first wrapper alone missed bitmap writes; the complete trace includes them.
No SDK source was edited. SDK `partition_linux.c::esp_partition_hook_write`
counts one cut unit per four bytes and one per erased sector. At the threshold it
can write the entire requested last word, return failure, then reset the failure
counter to SIZE_MAX: later writes are enabled. This is a **one-shot I/O error**,
not power remaining off.

Before the operation, `ret0` generation49 is still needed. Its old BLOB_DATA and
BLOB_IDX are live on page7 (version128). During `nvs_set_blob(ret0,3485,127)`:

1. New data chunks are written,1344 B on page12 and2141 B on page22.
2. GC marks a victim FREEING, activates page22, copies live entries and erases
   page13. GC finishes before the final index publication.
3. The new BLOB_IDX is page22/entry85,version0. Call55 writes its32-byte header.
4. Call56 writes its bitmap word at offset90164. Cut1072 writes all four bytes,
   **so the new index and both chunks are complete**, but returns FLASH_OP_FAIL.
5. With the old harness, `writeMultiPageBlob` runs error cleanup. Calls57–59
   successfully erase bitmap entries for the page12 new chunk. The new index
   remains valid, but references an incomplete blob. The old index remains too.
6. On remount `PageManager::load` removes the old duplicate index;
   `Storage::eraseMismatchedBlobIndexes` then removes the incomplete new index.
   `nvs_get_blob(ret0)` is NOT_FOUND.

There is no application `nvs_erase_key` in this failing operation; chunk erasure
is internal SDK cleanup. `nvs_set_blob` never reports success, and **nvs_commit
is never called** for the candidate. The physical new blob was complete at the
cut, but the caller had not accepted/committed it. The SDK's installed
`NVSHandleSimple::commit` returns ESP_OK without additional flash writes; it
is not a multi-key atomic transaction.

The smallest **power-fault harness correction** is to latch failure for every
subsequent program/erase until reboot. With that correction the exact cut1072
recovers complete generation127, not NO_VALID_REPORT. This does not claim the
one-shot-error cleanup path is safe on hardware: a recoverable/ambiguous write
error requires independent old authority and owner stop/remount, not continuing
normal ingestion or ACK.

Small host-only application correction: preserve selected `ret0` and old selector
`pick0`; append complete generation-specific `r127`; commit; append fresh
`pick1` carrying its generation reference; commit; only then erase `ret0`.
Recover by validating selection and complete report together. An interrupted
unselected candidate does not authorize pruning/refilling credits. This is one
transition: a production implementation must use bounded immutable/rotating
**unselected** keys, never overwrite the selected or recovery-root dependencies,
and prove orphan cleanup, root/credit/class/digest binding, authentication and
freshness. The dummy selector encodes its report reference through generation;
it is not the full authenticated lifecycle root. No atomic multi-key assumption.

[Fault sweep](R1_STORAGE_NVS_DIAG_FAULT_20261008.log): in-place cuts0..1081,
independent-key transition cuts0..1229, and six transition cuts paired with
remount cuts0..64. All3485 report bytes and selected root generation/body are
checked. Result: **2702 PASS; OLD_VALID_REPORT OR NEW_VALID_REPORT; no missing
selected report**. Second interruptions exercise remount's repair writes, not
an unimplemented credit-ledger rebuild. Four-byte cut and whole-sector erase
emulation does not cover arbitrary hardware bit/erase tears.

## High-occupancy report progress

A4096-byte segment costs at least131 entries;3485 report111;512 root18.
NVS has126 entries/page,32 B/entry,64 B/page header+bitmap, one erased GC page.
At12 segments after1000 churn cycles,3844 live entries leave188 free entries in
NVS stats:126 belong to the GC page, leaving only62 entry equivalents outside
that page. A new111-entry report needs49 more entries even before root publication.
Holding a new18-entry selector increases that shortage to67 (2144 B). Blob
chunk splits/page fragmentation and GC copying can increase it further.

| Resource | Logical B | Minimum NVS entry B |
|---|---:|---:|
|Old report |3485 |3552 |
|New report |3485 |3552 |
|Independent new root |512 |576 |
|Additional report+root COW |3997 |4128 |
|Internal erased GC page |— |4096 physical |
|Sector-rounded application report+root workspace |— |8192 physical |

`TRANSIENT_COW_BYTES=4128` entry minimum;
`GC_REQUIRED_BYTES=4096`;
`MINIMUM_SAFE_HEADROOM_BYTES>=12288` **includes**8192 application plus4096 GC.
This is a reservation obligation, not a proven admission threshold: arbitrary
fragmentation can need more. At the measured3844-entry steady layout, complete
report+selector coexistence plus GC has a sector-rounded lower bound
`ceil((3844+111+18)/126)+1=33 pages`, or **135168 B**. Actual attempted operation
hits131072 physical bytes and fails; it does not magically occupy135168 B.
`REPORT_REPLACEMENT_PEAK_BYTES>=135168` is therefore a **derived required peak**.

STEADY capacity can hold12 segments; TRANSIENT replacement cannot; GC capacity
keeps one erased page but cannot turn its space into permanent new live entries.
At11 segments this particular replacement succeeds. Release already-unreferenced
history or reject normal admission **before** spending the workspace. Do not
delete evidence requiring the candidate report merely to let that report fit.
An independent generation key corrects transaction authority, but does not
eliminate the capacity needed for old/new coexistence.

## Simultaneous192-HOT capacity

The source-proven Node flight is6*32=192. Proposed6*(32+32)=384 exact obligations
is conditional on durable credit/report progress; no production guarantee is
created here. The favorable probe releases three certificate blocks first,
leaving192 exact certificates;192 new HOT bodies carry the other exact keys.
That release/transfer and class charging are not a persisted production proof.
Holding additional overlapping certificate generations would need more capacity.

Nine existing sealed segments serve **shared** backend-pending/history bodies;
no separate duplicate backend payload is charged. The192 HOT bodies are a
separate new flight, not already among those nine segments. Routine/current-day/
daily state resides in the6144-byte state banks. Lifecycle/context/class/completion
metadata resides in two4096-byte placeholders. Critical space is two4096-byte
placeholders, not an approved saturated-critical guarantee. Source context728..
1370 must be bound within the charged segment/metadata objects; full serializers
and encryption integration remain unproven.

| Worst-flight component | Entry / physical B | Meaning |
|---|---:|---|
|HOT_EVENT_BYTES |36864 |192*6 entries for124-byte blobs; logical23808 |
|EXACT_EVIDENCE_BYTES |23232 |192 certificates12576 plus three report banks10656 |
|BACKEND_OUTBOX_BYTES |37728 |Nine4096-byte shared pending/history segments |
|ROUTINE_DAY_BYTES |18720 |Three6144-byte state banks |
|CHECKPOINT_COW_BYTES |10944 |New report3552+state6240+two independent roots1152; no necessary old copy dropped |
|ROOT_BYTES |1152 |Existing two roots |
|CRITICAL_RESERVE_BYTES |8384 |Entry footprint of two4096 placeholders |
|Lifecycle metadata+namespace |8416 |8384+32 |
|Page header/bitmap |2368 |37 occupied pages*64 |
|GC_RESERVE_BYTES |4096 |One erased page |
|Sector rounding/unused tails |3744 |Lower-bound page packing |
|TOTAL_PEAK_BYTES |**155648** |38 pages |
|DEFICIT_BYTES |**24576** |Versus existing131072 |

Blob entry lower bounds assume chunk sizes up to4000; runtime may split more.
The measured38-page run reaches4632 physical live entries during copying;
logical final4550, versus arithmetic4545. It retains one erased page at stable
boundaries, all38 pages can be nonblank during GC. This is not extra application
headroom. At32 pages, maximum flight stops after138 admitted,3885 live entries
at the call boundary. Physical in-call GC peaks4007 entries/32 pages.

[Capacity matrix](R1_STORAGE_NVS_DIAG_CAPACITY_20261008.log), all after1000
heavy churn cycles; admission AND segment replacement AND independent next
report/root/state/root coexistence must complete:

|HOT size |3 segments |4 |5 |7 |9 |
|---|---|---|---|---|---|
|Typical36 |PASS |PASS |PASS |FAIL progress |FAIL progress |
|NORMAL trace P95 44 |PASS |PASS |PASS |FAIL progress |FAIL progress |
|Global maximum124 |PASS |FAIL progress |FAIL progress |182/192 admitted |138/192 admitted |

Typical/P95 are compact **fixture** sizes, not safe worst-admission bounds.
At nine segments their page-rounded peak lower bound is143360 (12288 deficit);
maximum needs155648 (24576 deficit). Passing3 segments with maximum flight shows
object lifetime/history allocation can help without sacrificing report/state
copies. It does not approve a shorter outage horizon or ignored backend owners.

For nine/max:132/136 KiB still fail admission;140 KiB admits192 but fails seal;
144 KiB seals but fails later progress;148 KiB fails later progress;
152/156/160/192/256 KiB complete this sequence. Descriptor copies use
`nvs_flash_init_partition_ptr` on the isolated Linux image; **no partition CSV
was changed**. The enlarged descriptors overlap the probe's unused dummy app
area, intentionally; they are not claimed to be deployable partition layouts.
`192_HOT_ADMISSION_SAFE=NO` for the nine-segment128 KiB mapping; complete R1
admission including authenticated ledger/critical/recovery/fragmentation is
UNPROVEN at every size.

## Write schedule and wear

NORMAL384, HIGH1776 and STRESS23232 are engineering scenarios, not measured
homes. Actual `ActivityEpisode` (`power.hpp/.cpp`) uses45 s quiet,300 s maximum
connected episode and30 min outage idle. First motion is durable; repeats are
RAM coalesced; a closing episode emits a separate immutable summary when repeats
exist. Stable continuous activity would produce roughly2*288*6=3456 motion
records/day, before other events. That is an illustrative continuous-motion
scenario, not a universal limit/distribution; short separated episodes, room
changes, reboots, admission failure, door/buttons and report traffic differ.
No sensor interrupt rate is substituted for semantic arrivals.

Proposed schedule obligations, **not a numerical product policy**:

1. Append each immutable canonical event/replay obligation and commit/readback
   before ACK. Pending bodies also serve the backend; no full checkpoint per event.
2. Apply only affected routine/day counters in RAM with a bounded durable replay
   tail; materialize at32 dirty events or earlier time/replay/config/day pressure.
   A time-trigger can increase writes beyond the counts below.
3. Publish complete reports on progress/flight/credit pressure; unchanged replay
   never refills credit or rewrites every owner. Per-Node report children/incremental
   completion/class records are possible refinements, not redesigned serializers.
4. Connected upload is event driven. Persist authenticated durable completion
   receipts; do not treat a lost response as completion. Outage retains bodies,
   reports can still release independent dedupe owners. Reconnection commits
   receipts incrementally and reclaims only after local/report/backend owners clear.
5. Node outage/rejoin preserves report/credit debt and original EventKey; Hub
   reboot rebuilds from selected checkpoint and immutable tail, with no automatic
   credit reset. Day rollover adds aggregate+next-day/model root transaction.
6. Reclamation copies live dependencies before root selection and erase; reserve
   report/checkpoint/GC work even while event admission is stopped.

[Measured schedule sensitivity](R1_STORAGE_NVS_DIAG_SCHEDULE_20261008.log):
seven baseline segments; each36-byte event and48-byte completion receipt committed
individually; each32-event group writes one3485 report,6144 state,4096 sealed
segment,4096 metadata and512 root, then releases the bounded tails; final partial
group also checkpoints. One320 daily object. Report/state use an inactive bank
at the operation boundary; this workload is not the authenticated transaction
proof. Connected completion and report/local eligibility are assumed. This
conservative map retains whole metadata/segment replacements at checkpoint,
but avoids rewriting all owners on every arrival. Per-owner incremental records
or packing have **not** been assumed as free savings.

|Scenario |Logical B/day |Programmed B/day |Ratio |NVS entry writes |Page erases |Maximum erases on one sector |
|---|---:|---:|---:|---:|---:|---:|
|NORMAL |252572 |414648 |1.641702 |11884 |90 |5 |
|HIGH |1176152 |2033292 |1.728766 |58160 |461 |24 |
|STRESS |15261566 |26635932 |1.745295 |761482 |6089 |267 |
|HEAVY_SYNTHETIC,10000 cycles total |184570000 |297676416 |1.612810 |UNPROVEN in prior log |69755 |2961 |

Logical denominator is **all changed dummy values**, including reports/checkpoint,
not source-only information bytes. Entry writes count programmed entry spans
including GC copies, exclude page headers/bitmap writes, and are not unique live
keys. Setup is excluded. Heavy synthetic is a total-run measurement, not/day.
Production NORMAL/HIGH/STRESS amplification, outage/backfill/rejoin/reboot/day
revisions and low-rate timed checkpoints are **UNPROVEN**; these numbers only
measure the explicit connected schedule. STRESS does not have a proven acceptable
wear level. Report loss may stop credits rather than silently reduce durability.

Hot concentration: `PageManager::requestNewPage` chooses the page with most
unused entries; cold certificate/critical data can pin pages at zero erases.
Repeated state/segment/root replacement cycles through the remaining hot pages.
The old maximum2961 is about1.36 times the32-sector erase mean2179.84;
it is not evidence of one fixed root sector being erased every transaction.
More partition space alone does not guarantee all sectors participate in wear
levelling (192/256 fixtures also settle to one erased page after churn).
No flash lifetime or acceptable endurance is asserted without the exact chip
specification, measured workload distribution and target implementation.

## NVS versus existing raw candidate

No raw engine redesign or migration was performed.

|Criterion |NVS evidence |Existing raw evidence |
|---|---|---|
|128 KiB capacity |Nine/max simultaneous peak fails; three/max fixture progresses |Conservative fixed102400+28672 body map fills128 KiB; max-name72h fixture needs135168; no same192-HOT+pending peak proof |
|Peak occupancy |Measured full partition during GC; one erased page is internal |Explicit sectors/COW ownership in model, complete matching peak still unproven |
|Crash recovery |Corrected real-IDF cut sweep old/new; whole authenticated credit/root open |Host authenticated sector/root cut model, production engine and hardware recovery open |
|Forward progress |Requires enforced physical headroom and owner release; demonstrated counterexamples |Explicit allocation/victim control helps reasoning; report/owner policy and production admission still open |
|Write amplification/erase concentration |Connected schedule and heavy counters measured on real NVS emulator |Source/reduction arithmetic and host flash model; no comparable whole-schedule target wear proof |
|RAM |Application allowance plus NVS pages/hash/heap; target unknown |Prior39985 B full-context candidate, target unknown |
|Complexity |Existing SDK allocator/recovery; custom application transactions still required |Custom allocator/append/nonce/root/recovery/GC/encryption/rollback obligations |
|OTA |Same partition cost, code growth unknown |Same partition cost, custom engine code growth unknown |

RAW_ADVANTAGE_PROVEN=NO means no demonstrated complete R1 advantage, not that
raw lacks allocation control. Prefer the corrected NVS candidate; keep raw as
fallback if target wear or guarded admission later fails. Do not redesign raw
merely to turn this result into a different predetermined answer.

## Partition/hardware review

[Official generator validation](R1_STORAGE_NVS_DIAG_PARTITIONS_20261008.log)
constructs **temporary**4 MiB candidate CSVs, preserves supporting partitions,
checks alignment/overlap/flash bounds and gives the following current-image margins:

|Lifecycle |OTA0 offset/size |OTA1 offset/size |Journal offset |Current image limiting headroom |
|---|---|---|---|---:|
|128 KiB |0x20000 /1966080 |0x200000 /1966080 |0x3E0000 |101456 |
|192 KiB |0x20000 /1966080 |0x200000 /1900544 |0x3D0000 |35920 |
|256 KiB |0x20000 /1900544 |0x1F0000 /1900544 |0x3C0000 |35920 |

192 uses asymmetric slots;256 relocates both and uses equal slots. Generator
validation proves layout arithmetic only: no migration, boot/rollback/security,
signed-profile fit or post-integration code margin is proved. Do not spend the
existing101456 margin twice. No repository CSV changed.152 KiB fixture floor is
an increase24576 B;192 is the smallest requested review option above it.
256 has more modeled storage margin with the same limiting current-image margin,
but is not justified/approved as a requirement.

`128K_VIABLE=UNPROVEN` overall (nine/max fixture NO, three/max fixture YES);
`192K_VIABLE=CONDITIONAL`; `256K_VIABLE=CONDITIONAL`;
`CURRENT_4MB_HUB_VIABLE=CONDITIONAL`; `HARDWARE_UPGRADE_REQUIRED=UNPROVEN`.
MCU performance need: no new evidence of insufficiency. RAM need: target unknown.
Flash need: workload/policy dependent. OTA safety: current image fits all three,
future storage-integrated image unmeasured. No ESP32-S3 recommendation.

## Bounded RAM estimate and validation limits

A conservative **planning allowance**, not a measured ESP32 allocation:

|Component |Bytes |
|---|---:|
|Exact EventKey index (existing prototype) |12452 |
|Nine sealed offset directories+owner bitmaps |10647 |
|192 standalone HOT offsets/owner bits |456 |
|64 descriptors+queue cursors |2304 |
|Single selected report cache |3485 |
|Six64-byte credit workspaces+class bitmap |432 |
|Owned full-context workspace |1536 |
|Routine/day plus reducer |5408 |
|RX+encoder |640 |
|Flash authenticate/reclaim buffer+checkpoint buffer |10240 |
|Stack allowance |2048 |
|Application total |**49648** |

Credits/metadata grammar is not finalized; this allowance does not establish
its real size. Buffers require serialization under one storage owner; concurrent
operations need extra RAM. Backend pending selection reuses owner bitmaps and
cursors, not a second full source array. SDK internal page structures,128..640 B
per-page hash blocks, heap bookkeeping and blob temporaries are **additional**.
The [official6.0.3 guide](https://docs.espressif.com/projects/esp-idf/en/v6.0.3/esp32/api-reference/storage/nvs_flash.html)
provides approximate NVS heap scaling, not a guaranteed bound or target result.
Its approximation for roughly222 keys and192 KiB is about5.35 KiB; do not add
that as a certified maximum. Exact page/hash allocation depends on fragmentation.

`STORAGE_ENGINE_RAM_BYTES=UNPROVEN` (planning49648+SDK/internal additional RAM);
`ADDITIONAL_RUNTIME_RAM_BYTES=UNPROVEN`; `ESTIMATED_RAM_HEADROOM=UNPROVEN`.
Prior linker remaining134953 B is not runtime headroom and is not subtracted
from this host-layout estimate. No new target or host-RSS measurement is substituted.

Focused existing lifecycle/density/admission executables pass:
[regression output](R1_STORAGE_NVS_DIAG_REGRESSIONS_20261008.log). Their existing
million-event loops are built into these unchanged required regressions; no new
million-event campaign was added. Lost-report/replay tests remain **algorithm
model**, not proof of persisted NVS admission credits.
[ASan/UBSan](R1_STORAGE_NVS_DIAG_SANITIZERS_20261008.log) compile the new diagnostic
main and link unchanged SDK libraries: focused cuts/recovery/capacity/schedule
pass without diagnostics. SDK internals are not fully sanitizer-instrumented.
Seven focused sanitizer checks pass. Leak detection disabled; no LeakSanitizer claim. Original10000 heavy-cycle evidence
is reused; focused1000-cycle update/reclaim check passes.

Open product decisions: GS-D013/014/015/017, critical class/reserve/saturation,
full-detail/offline horizon, backend derived completion/revision/substitution.
Open technical blockers: persisted authenticated admission/credit/class/root and
source-digest binding; physical admission guard across owner transfers and crash;
complete failure-aware reducer/day/backend schedule; target RAM/OTA/endurance;
rollback/format activation; real bit/erase tear recovery. Technical finding only:
no LOCKED decision changed and context remains2026-10-07.003.

`READY_TO_START_PRODUCTION_STORAGE_IMPLEMENTATION=NO`.
`PRODUCT_CODE_INTEGRATED=NO`; `PARTITION_CHANGED=NO`; `HARDWARE_USED=NO`.
