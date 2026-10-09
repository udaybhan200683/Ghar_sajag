# R1 Current Work State

**Updated:** 2026-10-09

## Authoritative work line
- Worktree: `/home/udaybhan/projects/Ghar_sajag_r1`
- Branch: `feature/r1-commercial-baseline`
- Current P0 product behavior and application-vs-physical evidence boundaries: `docs/product/P0_PRODUCT_REQUIREMENTS.md`.

## Closed / physically qualified

Fresh-install durability path physically proven:
- fresh native ownership/enrollment;
- Node empty-AEAD hardware-AES regression;
- Hub owner stack sizing;
- first durable event commit;
- Hub recovery without watchdog starvation;
- authenticated Node runtime/rejoin;
- Node→Hub transmission;
- ACK class 0 and retirement;
- duplicate ACK safe;
- lost-ACK/reboot/retry duplicate safety;
- final Node retained/in-flight queues empty in lost-ACK qualification.

Do not reopen unless later code/hardware changes can invalidate these gates.

## USB automation

Zero-touch USB automation is convenience tooling, not an R1 product requirement. Keep it out of the critical path while product blockers remain.

## Working-tree reconciliation — 2026-10-07

The previously uncommitted qualified Node empty-AEAD and Hub native durability,
first-commit, stack/recovery, and lost-ACK controls are now committed, along with
their focused tests and existing factory/USB tooling. The canonical storage
contract and GS-D020 Jira traceability are tracked. Existing physical evidence
is preserved unchanged; no hardware test, initialization or flash was repeated.
See [the reconciliation snapshot](../progress/R1_WORKTREE_RECONCILIATION_20261007.md)
for every initial file, commit units, validations and remaining metadata.

Seven focused C++ gates, the production PSA host regression, factory/dispatcher/
profile tests, real Hub ELF checks and USB offline mocks passed. Two optional
initializer-ELF tests were skipped because their artifact is absent. The legacy
`hub-journal-migration-host-test` fails at `clean migration commits` on both the
start commit and reconciled sources; this pre-existing legacy failure is
DEFER_POST_R1 under GS-D001, with no migration fix attempted. `validation-fast`
still includes that target and is not claimed green. Eleven Windows download
metadata streams remain untracked and untouched; no uncommitted implementation
remains. Requirements and context version `2026-10-07.001` are unchanged.

Final lost-ACK source: `docs/hw/evidence/R1_LOST_ACK_FINAL/lost-ack-2h5v9gjp/status.json`.
Selected duplicate record growth is `79 - 78 - 1 independent event = 0`; selected
Node ACK is class=0 retired=1 and final retained=0/in_flight=0. This preserves the
previous physical PASS rather than claiming a new qualification run.

## Current R1 blocker

Hub storage lifetime/data-lifecycle architecture.

The previous fresh-install durability and lost-ACK qualification remains closed. This blocker concerns lifetime behavior after continued household activity; it does not invalidate the already-passed physical proof. Do not spend journal capacity or repeat HIL to investigate the design.

Known requirements:
- current finite append-only journal lifetime is unacceptable;
- reducer/routine state must be durably materialized/bounded;
- exact dedupe retained until retirement semantics safely cover it;
- backend outbox separated logically from local correctness;
- cloud-connected Hub pushes near-real-time;
- PWA reads already-current backend data;
- cloud outage does not stop local safety/routine learning;
- repetitive raw sensor detail can be coalesced;
- new Hub work targets ESP32-S3 N16R8 under GS-D030; preserve prior 4 MiB evidence;
- GS-D025 locks the 72-hour internet-only outage design target; exact retention, supported volume and guaranteed offline capacity remain open.

## Initial storage architecture checkpoint (historical proposal)

Architecture analysis at storage-worktree baseline
`cd8d126ab44689cc9c6ebbbe74e6dce058d4323b` is recorded in
[R1_HUB_STORAGE_DATA_LIFECYCLE.md](../exec-plans/active/R1_HUB_STORAGE_DATA_LIFECYCLE.md).
It recommends a **conditional** 384 KiB lifecycle allocation with dual OTA,
not an approved partition change. Current secure target uses the durability
owner/slot adapter and persisted receipts/reports, but retains 128 immutable
events. The 192 simultaneous Node-pending-key bound does not bound accumulated
ACKed-but-unreported Hub evidence without a report/admission window.

Implementation remains STOP pending product outage/overflow decisions, bounded
retirement progress, reducer/model limits, backend summary/effect completion,
safe rollback/format transition, current image fit and crash/wear proof.
Historical build sizes do not establish current-baseline OTA margin.
Existing physical qualification and deferred legacy migration classification
are unchanged; no firmware, physical event or new qualification was performed.

Subsequent efficiency phase preserves that architecture as documentation commit
`94fe1a8` and implements **isolated host-only policy-neutral primitives** under
the code project's `host/storage/`, with dedicated tests and benchmarks. No
production target lists or ACK path are changed. The optimized candidate shares
one immutable event across lifecycle owners; existing 128 KiB feasibility is
**CONDITIONAL**, so partition enlargement remains UNDECIDED rather than assumed.
The current 128-event production limit is unchanged. One million simulated events
show fixed 192-record storage and allocation-free primitives; existing journal
and backend completion host regressions pass. These are host results, not
physical durability/GC/rollback qualification. See ExecPlan section 20 and its
host evidence for exact byte budgets, benchmark scope and remaining STOP gates.

Derive and close the storage/data-lifecycle design for the GS-D030 S3 Hub and six-Node worst case before production storage integration. Separate:

1. active correctness journal and dedupe state;
2. materialized routine/reducer state;
3. backend outbox and completion semantics;
4. short local history/cache and safe reclamation;
5. offline capacity and six-Node worst-case event rates;
6. flash wear, crash-safe cleanup reserve and OTA budget.

Do not implement a guessed retention policy or merely increase the 128-event constant. The 72-hour outage design target is LOCKED by GS-D025; exact retention, supported volume, guaranteed offline capacity and partition-layout changes remain open decisions. See `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md` and `docs/product/DECISION_LOG.md`.

## BAT-C8

GS-D020 traceability: GS-114 — implementation/focused qualification; GS-146 — final R1 battery closure. Issue completion is not inferred from this mapping.

BAT-C8 is an R1-required feature with physical qualification pending (GS-D020). Physical cases P1–P10 remain NOT_RUN; these are test case IDs, not priority labels. Required production proof covers sleep entry, GPIO/timer wake, bounded resume, sensing/runtime and radio restoration, safe fail-awake behavior, and event-processing regression. Do not block on final battery-life optimization or long-duration endurance absent an explicit R1 battery-life claim. No BAT-C8 tests were run as part of the documentation decision.

## Stop rule

If work does not fix an R1 blocker or implement a locked R1 requirement, strongly consider backlog.

## Storage-first requirement checkpoint — 2026-10-07

Qualified isolated core checkpoint: `45f6b00`; million-event bounded fixture re-run PASS. GS-D021/022/023 now lock storage/retrieval-before-CPU priority and failure-aware routine/daily recovery with NO_ACTIVITY distinct from NO_OBSERVATION. Context revision advances from `2026-10-07.001` to `2026-10-07.002`. No production integration or partition approval. Existing primitive evidence does not prove daily finalization, retirement progress, AEAD GC or rollback. Current 128 KiB feasibility remains CONDITIONAL pending those proofs and product/backend limits.

At the GS-D021/022/023 checkpoint, the designated canonical branch still had `.001`; that storage-worktree requirement commit required review/promotion by an explicitly authorized canonical-source action. The density run subsequently started with local/canonical `.002` PASS. Do not silently synchronize worktrees or bypass the context guard. Next step: align approved canonical context, then implement policy-neutral failure models and close time/coverage, backend aggregate revisions, retirement-credit and COW recovery proofs before production work.

Refinement design is in ExecPlan section21: one shared immutable body, conditional derived-nonce84/104-byte records, coverage-aware320-byte daily aggregates,6,144-byte checkpoint candidate, exact128 KiB reservation arithmetic and Node/Hub/backend/day/reclaim failure matrices. No final record size or retention promise is approved. Conservative normal incremental detail capacity is76 records (4.75 hours at384/day);72-hour comparison needs249,856 bytes under the stated worst-record independent-reserve allocation, not a new requirement. Critical reserve8,192 protects one bounded32-record burst only; it does not solve indefinite critical saturation. The finite384 exact-key induction requires persisted admission credits/report progress; production bound remains unproven.

Unchanged core million-event and ASan/UBSan checks, journal/full129 recovery and backend completion regressions, and24 retirement-model tests pass; static byte arithmetic/relative paths and diff checks pass. New coverage/day/reclaim failure models are specified but not implemented: canonical requirement commit must precede dependent implementation, and the new local version must pass the context guard against the designated canonical source first. No hardware result, production integration, CSV change, BAT-C8 or Jira action.

Current no-HIL Hub target build now PASS after explicit C3 artifact build: actual Hub.bin1,864,624 B; current1,966,080-byte slots leave101,456 B. Static DRAM45,783 B/IRAM87,359 B are linker figures, not runtime heap margins. The old384 KiB candidate fails image fit by29,616 B;256 KiB leaves only35,920 B before future code/reserve. No partition resize approved. Build/test provenance: [refinement evidence](../exec-plans/evidence/R1_STORAGE_FIRST_REFINEMENT_20261007.md).

## Storage-density closeout — current handoff, 2026-10-07

Host-only codec/tests/benchmark/evidence commit: `74c4b99`. Initial resume
preflight PASS at local/canonical2026-10-07.002. Existing files and all evidence
were preserved; no expensive passed tests were repeated. Final density
million-event PASS (peak192 keys, fixed storage/RAM, portable hot new0),
ASan/UBSan terminal PASS and current storage/backend/journal regressions
are preserved. Sanitizer exit-status session handle was lost on interruption;
its completed temporary output is byte-identical to the tracked PASS log.
No LeakSanitizer or physical result is claimed.81-field inventory and
static budgets/links/diff checks passed; CSV cells were preserved during
line-ending normalization. Only the missing fast one-day size comparison
was completed with the unchanged codec.

[ExecPlan sections22.10/22.11](../exec-plans/active/R1_HUB_STORAGE_DATA_LIFECYCLE.md)
and [density evidence](../exec-plans/evidence/R1_STORAGE_ENCODING_DENSITY_20261007.md)
supersede earlier density recommendations for current planning while
preserving historical/numeric-only comparisons. Full self-contained identity
and config context costs728 B sample /1370 B maximum per independently
restartable4 KiB sector; serializers/security integration are PROPOSED.
Timing-variation median body13/HOT36/WARM15–16 B excludes shared header/tail;
maxima raw101/HOT124/WARM103 B. Conditional fixed100 KiB +variable28 KiB
reservation fits the existing partition arithmetically, not by allocator proof.

Full-source timing-variation retention: NORMAL1281 sample /1056 max-name
records (80.0625/66 hours), HIGH1347/1103, STRESS1457/1181. Synthetic72h
NORMAL plus daily/fixed reserve requires131072 B sample (zero spare),
135168 B maximum (4096 deficit).128 KiB remains CONDITIONAL; no approved
72-hour guarantee or proven partition enlargement requirement. The conservative
prior76-record result and narrower uniform-numeric1595 result use different
representations/reservations and are not production guarantees. Current
1864624-byte image and101456-byte OTA margin remain prior build evidence.

GS-D024 now locks redundancy elimination and compact bounded context/restart
evaluation before storage enlargement. Context advances.002 ->.003, separately
from host work. Designated canonical remains.002; final preflight is expected
STALE and all substantive work must STOP then. No automatic synchronization
or promotion. Next step is explicitly authorized canonical review/promotion
and preflight PASS, followed by policy-neutral authenticated allocator/root/
nonce/reclaim and full dictionary/config recovery proofs. Also close retirement
credit/report bound, exact witness retry projection, offline/saturation policy,
backend daily/effect/revision/substitution, coverage/trusted-time/day recovery,
rollback and target RAM/wear/OTA growth before production integration.

Production integration NO; partition CSV/ACK/backend/PWA unchanged; hardware
unused; BAT-C8/Jira untouched. Existing physical fresh-install gates stay closed.


## 2026-10-07 lifecycle proof checkpoint (context .003)

Canonical promotion is complete; storage preflight PASS at2026-10-07.003.
The [focused lifecycle evidence](../exec-plans/evidence/R1_STORAGE_RETIREMENT_RECLAIM_PROOF_20261007.md)
and ExecPlan section23 preserve the new host-only findings. Node pending192 is
source-proven; historical Hub exact evidence has no finite current protocol
progress bound when event ACKs succeed and reports are lost. A proposed32-credit
per-owner gate gives384 live witnesses in a fixed host model, not production.
4,325 abstract COW cuts, million-event bounded run, sanitizers and relevant
existing regressions PASS. Full authenticated allocator/root/nonce/erase/rollback
and credit durability/fairness/critical policy remain OPEN. No hardware used.

A conditional53-byte dedupe-only witness raw ledger frees one sector: fixed
98,304 +shared32,768 =131,072. Synthetic72h NORMAL sample/max raw sizes
126,976/131,072 B; NVS pool tax and simultaneous192-body worst case prevent
a production guarantee.128 KiB remains CONDITIONAL; enlargement not proven
necessary. Native retry digest includes Hub receive time; outer journal key-only
duplicate bypass versus component digest checking needs end-to-end investigation.
Next close progress/admission and authenticated peak allocator proofs, then
explicit backend/offline/critical decisions; do not production-integrate.
No new locked requirement or CONTEXT_VERSION change.

## 2026-10-07 bounded admission and NVS/raw comparison

[Focused host proof](../exec-plans/evidence/R1_STORAGE_ADMISSION_RAWFLASH_PROOF_20261007.md)
and ExecPlan section24 derive `6*(32+W)` exact keys under persisted complete
report +uncovered admission credits. W32 gives384 for one retained flight;
final W/C, critical mapping and safe saturation remain unapproved. Reports/control
must progress without normal credits; reboot/generation alone never replenishes.
Million-event admission, six-Node saturation and host authenticated4 KiB flash
models pass; actual durable credits/full allocator/freshness remain OPEN.

Whole-object NVS remapping corrects the earlier event-pool-only tax sensitivity:
official generator fresh images for synthetic72h NORMAL sample/max need
122880/126976 B including stated COW/free/engineering reserves. This is not
runtime GC/capacity proof. Conservative raw three independently erasable6144-byte
state banks need24576 rather than prior20480, leaving seven event sectors;
sample72h131072 fits, max135168 misses4096. Neither72h nor these reserve choices
are locked.128 KiB remains CONDITIONAL; enlargement not proven necessary;
backend UNDECIDED. Next host-only step: actual IDF NVS runtime/GC/tail/promotion
peak proof and explicit product critical/offline/substitution decisions.
Codec/production/ACK/backend/partition unchanged; no hardware or context bump.

## 2026-10-08 final NVS runtime/saturation checkpoint — NOT CLOSED

[Host-only installed-IDF evidence](../exec-plans/evidence/R1_STORAGE_NVS_RUNTIME_PROOF_20261008.md)
and ExecPlan section25 close the *fresh-image-only* evidence gap with actual
Linux NVS allocation/GC, but **do not close the final storage proof**. A nine-
segment candidate completes 10,000 heavy replacement cycles with one erased
NVS page at operation boundaries and 69,755 erases; the prior two application
COW plus one engineering pages are consumed by churn. After three more live
segments, report replacement fails with `ESP_ERR_NVS_NOT_ENOUGH_SPACE`.
After replacing 192 certificate keys with full-HOT bodies, only 138/192
maximum124-byte HOT blobs admit in the nine-segment fixture. An injected
report replacement cut1072 remounts with `ret0` absent, reproduced three
times. Other sampled cuts recover old or new single-key values. An application
authenticated bank/root protocol is required; there is no final credit or
NVS crash proof.

The384 exact-key bound remains conditional on durable admission/report
selection and actual body/GC capacity. NORMAL/HIGH/STRESS write amplification,
target engine RAM, rollback, and OTA growth are not established. Current128 KiB
remains CONDITIONAL overall; the unrestricted nine-segment fresh-image reserve
mapping fails. Partition enlargement and a4 MB Hub upgrade are not proven
necessary, and current image OTA fit is unchanged prior evidence. NVS remains
preferred candidate; raw remains fallback. `READY_TO_START_PRODUCTION_STORAGE_IMPLEMENTATION=NO`.
No production code, partition, hardware or BAT-C8 change. Context stays
`2026-10-07.003`; no new LOCKED decision. Next resolve product critical/offline/
overflow/backend substitution semantics and close the persisted credit/root,
physical admission guard, bounded NVS wear and target RAM/rollback proofs.

## 2026-10-08 NVS blocker root cause — technical diagnosis checkpoint

[Focused evidence](../exec-plans/evidence/R1_STORAGE_NVS_BLOCKER_DIAGNOSIS_20261008.md)
resolves cut1072 as FAULT_INJECTION_MODEL_DEFECT: one-shot emulator failure
allows cleanup writes after the supposed power cut. Blocking subsequent writes
recovers new; independent report/selection keys pass2702 focused cut/remount
checks. This corrects only the earlier SDK power-loss inference; actual
saturation and192-HOT failures remain. Nine-segment maximum coexistence needs
a modeled155648 B; three-segment fixture progresses at128 KiB. R1 minimum and
128 KiB viability remain UNPROVEN pending policy and complete admission proof.

NVS is the technical candidate; raw advantage is not demonstrated. Retain4 MB
Hub.192/256 KiB review layouts fit the current image with35920 B limiting margin;
no partition decision. Connected checkpoint32 sensitivities reduce erases to
90/461/6089 per modeled day but do not qualify outage/rejoin/target endurance.
Application RAM allowance49648+NVS internals and target headroom are unproven.
Next is policy closure plus persisted authenticated credit/root/guarded allocation,
then target RAM/code/wear/rollback gates; no new architecture campaign or codec
redesign. READY_TO_START_PRODUCTION_STORAGE_IMPLEMENTATION=NO. Context.003 and
all LOCKED decisions unchanged; no product code/hardware/partition change.

## Product governance prepared — 2026-10-08

Documentation-only governance at starting HEAD
`d8631e656bd37f05294853de40cec93d65f0cec6`, storage branch
`feature/r1-hub-storage-lifecycle`. Initial preflight PASS and context
`2026-10-07.003`; only user-owned untracked `prompt.txt` was present.

GS-D025–028 now LOCK the approved 72-hour internet-only outage design target,
loss-aware eligible ordinary-motion aggregation, battery-first ESP32-C3 Node
processing and PIR/door/future-bed boundaries. GS-D013/017 are only partially
superseded for these approved directions; their numerical/protocol decisions
remain OPEN. Context advances to `2026-10-08.001`. This preparation does not
authorize production integration or claim capacity/battery qualification.
Existing host evidence is preserved; simulations, hardware and release gates
were not repeated. No production, partition, BAT-C8 or hardware scope changes.

OPEN: critical-event classification/reserve, NORMAL/HIGH/STRESS guaranteed
volumes, critical saturation behavior, quiet gap, progress frequency, final
backend summary protocol and final NVS size. The 4 MB ESP32 Hub remains baseline.
New Node protocol work must prove battery and correctness impact before
implementation; no 40–120-second periodic consolidation wake-ups are approved.
BAT-C8 physical qualification remains pending, with its requirements unchanged.

**Promotion requirement:** the canonical source remains
`/home/udaybhan/projects/Ghar_sajag_r1` on `feature/r1-commercial-baseline`,
initially clean at `5dcd2f7c10682bd1f6801821deaff20ad4a803e4` and context
`2026-10-07.003`. It is not modified by this task. After the local increment,
preflight STALE / CONTEXT_VERSION_MISMATCH is expected. Stop substantive work.
Explicitly authorize review/apply/commit of the governance commit's documentation
patch to these eight canonical files as one coherent change:

- `docs/product/DECISION_LOG.md`
- `docs/product/R1_RELEASE_CONTRACT.md`
- `docs/product/R1_WORK_STATE.md`
- `docs/product/P0_PRODUCT_REQUIREMENTS.md`
- `docs/product/CANONICAL_REQUIREMENTS_INDEX.md`
- `docs/product/GHAR_SAJAG_PROJECT_CONTEXT.md`
- `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md`
- `docs/product/CONTEXT_VERSION`

Review ExecPlan section29 separately as implementation-design status; canonical
does not yet contain the linked storage-worktree checkpoint evidence. Promotion
must preserve canonical work and avoid importing host-model/production changes
merely to synchronize context. Resolve reviewed documentation differences,
commit canonical governance, then rerun preflight and require PASS before
substantive work. Never weaken the guard or auto-promote.

## Current security-scope governance — GS-D029, 2026-10-08

Product-owner approval locks ordinary power-failure/interrupted-flash crash consistency,
detected-corruption/missing/inconsistent-state fail-closed recovery, and no silent
stale/uncertain routine state. Ownership, durable-before-ACK, retry/deduplication,
retirement credits and protected dependencies are preserved.

Deliberate restoration of an otherwise valid older flash image is outside R1's
data-freshness detection guarantee; AES-GCM is not malicious full-flash rollback
protection. Automatic signed FOTA APPLICATION rollback through ESP-IDF remains
MANDATORY, including firmware validation and compatibility with storage created
by an unsuccessful upgrade. Data rollback exclusion does not waive application
rollback or permit silent erase/reset/stale recovery.

Context advances2026-10-08.001 ->2026-10-08.002. This task explicitly authorizes
reviewed promotion of only these new governance edits into canonical; independent
worktree history is preserved. No storage experiment, code, test, evidence or
ExecPlan is promoted. Previous governance preparation/promotion notes above are
historical checkpoints. Both worktrees must PASS preflight at the new version
before implementation; no guard bypass or new qualification is claimed.

The deliberate older-image replay limitation no longer establishes an R1 requirement
for an independent malicious-data-rollback anchor. Stronger historical host-authority
assumptions remain valid in their stated proof scope. Ordinary power-failure/corruption
freshness, production mapping and FOTA/storage compatibility still require evidence;
this approval does not declare those implementation gates or Gate C passed.

**Next:** resume Gate C protected NVS admission and progress implementation, retaining
ordinary crash/corruption and dependency regressions. Protected reserve/progress,
supported event volumes, critical saturation and the 72-hour capacity guarantee
remain OPEN. No new security hardware, ESP32-S3 or partition change; existing 4 MB
Hub/ESP32-C3 baseline and BAT-C8 requirements/pending qualification remain unchanged.

## Current Hub development direction — GS-D030

Context2026-10-09.001 records the explicit S3 N16R8 selection. Canonical governance
remains in this worktree; new Hub target work is in `/home/udaybhan/projects/Ghar_sajag_r1_s3`
on `feature/r1-s3-hub-bringup`, based on storage checkpoint `389ffd3`. Preserve
independent worktree content and historical evidence; no experimental storage
code or evidence is promoted to canonical. The preserved storage worktree may
remain at context2026-10-08.002 and therefore STALE until separately synchronized.

The 4 MiB classic Hub is retired from active development, not deleted. Existing
physical PASS results remain valid only for their original hardware/configuration.
S3 target/PSRAM/ESP-NOW/FOTA/heap-stack/recovery qualification is pending.
Initial bring-up must identify and preserve existing device firmware/data before
writing flash. Commercial partitions, sustainable storage reclamation, supported
72-hour volume, critical saturation and R1 end-to-end qualification remain open.
Do not resume classic-ESP32 footprint/capacity optimization or change C3/BAT-C8.

### S3 bring-up checkpoint — 2026-10-09

[S3 evidence](../exec-plans/evidence/R1_S3_HUB_BRINGUP_20261009.md) records
GS-D030 governance, direct reuse of the existing Hub composition and unchanged
C3 asset, successful ESP-IDF6.0.3 S3 builds and a physical diagnostic PASS.
Actual board: ESP32-S3rev0.2,16 MiB flash,8 MiB Octal PSRAM40 MHz; startup/scratch
memory, Wi-Fi and ESP-NOW init and six10-second heartbeats pass. Full private
flash backup verified before writing; original NVS/VFS digests still match.
Final Hub composition1791792 B; development dual4 MiB OTA slots/2 MiB journal
leave2402512 B current unsigned-image margin per slot. The product image was
not flashed. Module/PCB GPIO mapping, provisioning/C3 application interchange,
storage/reclaim/72-hour volume, signed FOTA/rollback and full runtime remain
unqualified; diagnostic heap values do not qualify product peak memory.
Existing host1479 checks, fresh-install, FOTA guard and retirement pass.
Canonical receives governance only; storage worktree/history and C3/BAT-C8 remain
unchanged. No commercial partition/retention decision or new R1 qualification.
Next bring up one authenticated S3-Hub/C3 pair and prove durable ACK/retry/reboot.

### First S3/C3 pair preflight — 2026-10-09

[Pair evidence](../exec-plans/evidence/R1_S3_C3_FIRST_PAIR_20261009.md) records
both boards accessible, but C3 `c3-146393c5d158` is still authenticated as Paired
to `hub-5c013bbeb9f8` with seven persisted retained Motion records. Private full
flash backup/device verification and before/after-restart record comparison pass;
original S3 NVS/VFS remain unchanged. Stop before commissioning, disposal or
flashing. RAM retained=0 during unauthenticated rejoin does not mean empty storage.
Four focused existing host authentication/association/rejoin/recovery targets pass;
physical S3 product boot, authenticated interchange and durable ACK/reboot dedupe
remain unqualified. No production/Node/partition/BAT-C8/context changes. Resolve
the existing Node ownership and pending records before resuming this pair.

### S3 durable-storage closure checkpoint — 2026-10-09

[Storage evidence](../exec-plans/evidence/R1_S3_DURABLE_STORAGE_CLOSURE_20261009.md)
records a clean ESP-IDF 6.0.3 S3 Hub build and focused host storage regressions.
The built runtime includes the authenticated NVS durability owner and
durable-before-ACK path, but still constructs a 128-record `HubRuntime`; the
compact host representation is not integrated into the target lifecycle. Host
Gate A/B checks pass within their assumptions, while Gate C reserve restoration
and sustained reclamation remain open. NORMAL/HIGH 72-hour storage, physical
power-failure behavior, target runtime memory, reconnect catch-up and FOTA remain
unqualified. No board write was made because the current development map
overlaps preserved NVS/VFS data. Storage closure is BLOCKED; BAT-C8 has not
started.

### S3 segmented outbox source slice — 2026-10-09

The [focused implementation evidence](../exec-plans/evidence/R1_S3_SEGMENTED_OUTBOX_SLICE_20261009.md)
records a new encrypted, append-only outbox core and pinned LittleFS adapter,
authenticated event publication marker, 6,556-record host stress test and clean
ESP-IDF 6.0.3 S3 build. The S3 Hub runtime is still `HubRuntime(32, 128)` and
continues using the old NVS slot provider; no Node Durable ACK flows through the
new outbox yet. Backend completion, safe retirement, segment reuse, reducer
checkpoint separation, workload fixtures and physical flash qualification are
not complete. This implementation does not close the 72-hour target or change
product policy. Next: integrate outbox admission/replay behind the authenticated
Hub durability boundary with ACK-after-publication tests, then implement
completion and reclamation without dropping dependencies.

### S3 segmented outbox runtime integration — 2026-10-09

[Runtime integration evidence](../exec-plans/evidence/R1_S3_SEGMENTED_OUTBOX_RUNTIME_INTEGRATION_20261009.md)
records the first S3 HubRuntime path backed by the encrypted LittleFS outbox.
Authenticated event admission now commits and publishes the exact EventKey and
event body before returning the existing Durable ACK; retries are deduplicated,
and reducer state is rebuilt by bounded streaming replay. The S3 path no longer
uses the legacy 128-slot event journal. Focused host coverage admits 2,048
records, including events 129/385, and verifies lost-ACK/reboot retry, interrupted
publication, storage-full rejection, owner mismatch and bounded cloud batches.
The existing 6,556-record outbox and storage regressions remain passing.

ESP-IDF 6.0.3 clean S3 build passes at 1,818,352 bytes; the isolated development map
has 4 MiB OTA slots and a 2 MiB `gs_journal`, not the required `gs_outbox` plus
`gs_state` labels. Runtime therefore fails closed on the current board layout;
no flash or partition operation was performed. Backend completion/retirement,
sustained reclamation, NORMAL/HIGH 72-hour capacity, actual LittleFS power-cut,
PSRAM/internal-heap/stack qualification and physical validation remain open.
This source integration does not close the locked72-hour design target or alter
product requirements.

### S3 outbox completion and candidate partition profile — 2026-10-09

[Focused evidence](../exec-plans/evidence/R1_S3_OUTBOX_COMPLETION_PARTITION_20261009.md)
records durable authenticated backend-completion publication in the S3 outbox
and an isolated, build-selectable ESP-IDF 6.0.3 partition profile. Host tests
admit/recover 6,556 records and persist 3,278 authenticated host-controlled
COMMITTED receipts. The candidate map builds with two 4 MiB OTA slots, 4 MiB
`gs_outbox`, 256 KiB `gs_state`, and 3.625 MiB unallocated. No board flash or
format operation was performed.

This does not close storage: completed bodies are not retired, exact EventKey
identity still resides with retained bodies, and Hub routine/coverage state is
reconstructed by replay without a persistent materialized checkpoint. The
completion stream is bounded and has no compaction. Physical LittleFS recovery,
production backend transport, sustained reclamation, 72-hour NORMAL/HIGH
capacity and S3 runtime resource qualification remain open. No product decision,
context version, C3 data or physical S3 data changed.

### S3 storage Phase 1 — 2026-10-09

[Phase 1 evidence](../exec-plans/evidence/R1_S3_STORAGE_PHASE1_20261009.md) records encrypted reducer/coverage/configuration
checkpoints and an independent exact-identity/payload/context ledger connected to
the S3 authenticated event path. Host checkpoint-plus-tail equivalence, timer
latches, gaps/retries, interruption/corruption handling and 2,048-event recovery
pass; ASan/UBSan and the full S3 build pass. The image is 1,839,392 bytes. The
legacy slot migration test remains a traced development-format ownership-domain
FAIL; fresh-install owner tests pass. Existing body-only development installations
fail closed without the new auxiliary evidence. Bodies are retained; no expiry
policy is invented. Identity/reducer byte budgets are finite, physical heap/stack
and LittleFS power-cut behavior remain pending, and cross-version upgrade/rollback
compatibility is unqualified. Phase 2 reclamation and Phase 3 workload/physical
qualification were not started. No policy, context version, C3 or physical flash
change. Next: Phase 2 with protected checkpoint/identity dependencies.

### S3 storage Phase 2 — bounded lifecycle progress, NOT CLOSED

[Phase 2 evidence](../exec-plans/evidence/R1_S3_STORAGE_PHASE2_20261009.md)
records ordinal-preserving checkpoint replay, host completion-path coverage, and
measured identity/completion pressure. Identity remains on `gs_outbox` LittleFS:
733,165 logical bytes at 6,556 fixture events, with a 372,992-byte reconstructed
index allocation on the host (S3 mapping uses PSRAM). The 256 KiB `gs_state` NVS
partition does not hold this ledger. The 512 KiB logical completion stream
rejects the 5,473rd receipt after 5,472 published receipts / 524,205 bytes; the
rejection is restart-safe but space is not reclaimed. S3 has no production
CloudBackendTransport caller. Authenticated retirement snapshots are not joined
to the LittleFS identity ledger, so identities and event bodies remain retained.
No segment or completion compaction, sustained reuse, body-retention policy,
72-hour capacity, physical flash behavior or runtime memory has been qualified.
The known body-only/development migration remains fail-closed, and the legacy
registry-domain migration test still fails before and after this slice. Focused
outbox, runtime checkpoint, backend receipt, retirement snapshot and Node
retirement protocol tests pass; the checkpoint test also passes ASan/UBSan. A
clean isolated ESP-IDF 6.0.3 S3 build passes at 1,839,504 bytes with 2,354,800
bytes of 4 MiB OTA-slot headroom. Runtime heap, PSRAM and physical power-failure
behavior remain unqualified. No product policy, C3, physical flash or context
version changed. Phase 2 remains open; do not begin Phase 3 until completion
transport, identity retirement, crash-safe compaction and repeated refill pass.

### S3 Phase 2 lifecycle implementation update — 2026-10-09

[Lifecycle evidence](../exec-plans/evidence/R1_S3_PHASE2_LIFECYCLE_PROGRESS_20261009.md)
records a recoverable authenticated lifecycle root joining the selected NVS
Node-retirement report and reducer checkpoint to LittleFS body reclamation.
Three 100-event refill cycles and a 3,278-event mixed lifecycle pass in host
tests, including a restart after an interrupted reclaim. The outbox completion
log is compacted only after full-history retirement; exact identity evidence is
still retained and uncompacted. The 6,556-record admission/recovery stress
passes, while full stress retirement exceeds current completion workspace.
Production body deletion remains disabled because post-sync retention/time
semantics and physical S3 power-cut qualification are open. The isolated S3
build passes at 1,843,728 bytes. Phase 2 remains open; identity-safe compaction,
partial completion/segment reclamation, production cloud transport and physical
qualification remain. No product policy, partition, C3, flash or context version
changed.

### S3 incremental completion reclamation — 2026-10-09

[Focused evidence](../exec-plans/evidence/R1_S3_INCREMENTAL_COMPLETION_RECLAMATION_20261009.md)
records exact completion snapshots in the existing authenticated lifecycle root,
proof/checkpoint-gated receipt-log reuse with pending bodies retained, and
fail-closed generation-bound completion heads. Host tests pass 6,556 cumulative
completions, actual receipt-stream recovery from 524,262 bytes to zero (883-byte
replacement root), six publication/reclamation cuts and ASan/UBSan. The isolated
ESP-IDF 6.0.3 S3 build passes at 1,849,056 bytes. Event bodies and identities remain
retained in production; deletion stays disabled. Identity compaction, mixed-
segment body compaction, production cloud transport, retention policy and physical
qualification remain open. Phase 2 remains IN_PROGRESS; no Phase 3, C3/BAT-C8,
hardware or product-policy change. Context remains `2026-10-09.001`.
