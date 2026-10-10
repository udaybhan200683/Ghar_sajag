# R1 Current Work State

## GS-150 software implementation — 2026-10-10

The user clarified safe best-effort missed-ACK replay and confirmed-outage
alternatives, superseding the prior guaranteed-ACK-latency stop. Production C3
now permits safe light sleep with committed pending events in the existing
confirmed-outage profile after the existing 10 s active-contact receive budget.
A successful application MAC result keeps continuous reception while pending;
it never marks contact authenticated or retires work. Connected/transient
pending reception, original retry/rejoin timing, EventKeys/timestamps, queue
limits and ACK-driven durable retirement remain intact. Rejoin, retirement,
active/idle contact, fallback and ambiguity deadlines bound the same owner
sleep decision. Radio restore failure keeps PIR sensing running and fails awake.

Current implementation/evidence: [battery design](../features/BATTERY_LOW_POWER_AND_POWER_MANAGEMENT.md),
[GS-150 validation and scenario metrics](../exec-plans/evidence/R1_GS150_SOFTWARE_VALIDATION_20261010.md).
GS-150 is SOFTWARE_IMPLEMENTED / HOST_TESTED / SIMULATED / TARGET_COMPILED.
New deterministic gate PASS (1,481 checks / 19 paired workloads); BAT-C8 PASS
(72 C++ / 11 Python); full C++ PASS (1,479); full Python PASS (346 run, one
historical scoped skip); frontend 17/17 and contracts PASS; PWA bridge 12/12,
API/frontend 92 canonical scenarios each PASS. Master runtime 49/49 and FOTA
34/34 PASS after correcting its matching stale rejected-admission sequence
assumption and host-only outbox link recipes. No production sequence change.
Encrypted recovery,
authenticated retirement/rejoin, security/FOTA and Hub persistent dedupe gates
PASS. ASan/UBSan PASS for the new gate and full C++ suite. Clean C3 ESP-IDF
6.0.3 PASS: 933,520-byte image, 53% OTA-slot free. Evidence records all actual
commands and the corrected pre-existing Hub host-test link recipe. No physical
actions, physical current measurement or battery-life claims.

Identical six-minute outage workloads: one/eight pending records reduce owner
loops 18,000→3,189/3,171 and modeled awake time 360,000→63,540/63,180 ms, with
unchanged eight TX opportunities. One modeled sleeping ACK miss needs one
additional same-key replay and preserves one logical effect. Protected rejoin
and auxiliary receive windows add awake time in already sleeping paths; these
costs and model limitations are explicit in the evidence.

Canonical worktree `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`, starting local/remote
`ff0f6f159890b86f26b998ca3d1218600ff34cc8`; the pre-existing untracked S3
`managed_components/` remains preserved. This task is the narrow GS-150 exception
to GS-147; expanded journal/retirement/capacity, deep sleep and C9–C12 remain
excluded. No LOCKED decision/context revision change. Next sequential task is
GS-114 image-matched physical functional P1–P9, requiring separately authorized
fixture/board actions. GS-149 quantitative P10 and GS-146 closure remain open.

### Delivery and sequential handoff

Implementation commit `1262400408e780044d928d84286d9b6f392b9d5a`
was pushed normally to `origin/feature/r1-commercial-baseline` on 2026-10-10;
actual `git ls-remote --heads` equals local HEAD at that checkpoint. Tracked
tree was clean; only the original S3 `managed_components/` was untracked.
This subsequent documentation-only closeout records that verified delivery;
the final closeout HEAD is reported in GS-150 Jira and the session handoff.
No firmware source changed after the validated clean image.

No GS-150 software blocker remains. Read this section, the battery guide,
linked validation/CSV and latest GS-150/GS-114 comments before resuming.
The precise next action is GS-114 fixture/image preparation and separately
authorized P1–P9 qualification, including pending-event outage sleep,
missed-ACK replay, held-HIGH/overnight PIR, radio restore and FOTA/control
entry races. Rebuild the approved qualification profile from the final
checkpoint, record its hash and fixture readiness. Do not use protected
original paired boards or treat this handoff as hardware authorization.
GS-149 P10 current/residency and GS-146 final closure follow their existing
dependencies. GS-147 remains gated; no new scope or security decision needed
to resume GS-150 software.


## Historical GS-150 ACK-boundary blocker, 2026-10-10

Superseded by the current GS-150 software delivery above. The absence of a
guaranteed ACK-arrival maximum remains true; safe missed-ACK replay is now the
approved basis for a conservative implementation.

GS-150 is a user-approved narrow C3 software implementation exception to the
broader GS-147 hold. Source verification reached its explicit stop condition:
there is no source-defined maximum authenticated application Durable-ACK
arrival time. The Node's 1,000 ms timeout covers its local MAC send callback
only; after that callback, `NodeRadio` schedules the existing retry ladder. The
Hub authenticates/processes the Node event, completes the durable runtime step,
then submits the application ACK, but does not publish a maximum arrival bound.
The existing retry deadline cannot create a safe interval to sleep before the
same retry is due. Do not repurpose the MAC timeout or change retry/ACK policy.

**GS150_RESULT=BLOCKED** before production behavior changes. The needed product
input is an approved end-to-end application Durable-ACK listening maximum,
measured from Node MAC callback completion, with a source/build-supported Hub
commit/ACK path bound that leaves time to sleep before the unchanged retry. This
must preserve exact EventKey, authenticated Durable ACK retirement, first-event
and critical-event priority, health/freshness, FOTA/control, GPIO4 and radio
restoration. No firmware behavior changed; no GS-147 queue/journal, protocol,
retry or deep-sleep work was added.

Validation on canonical source HEAD `f245eebcd80c9e43a230ae0ee814f59a37adefd0`:
`make -j2 battery-c8-host-test node-recovery-persistence-host-test
node-retirement-protocol-host-test rejoin-host-test secure-fota-adapter-host-test`
PASS; `make cpp-test` PASS (1,479); `make python-test` PASS (344, one scoped
skip). No source changed, so existing clean C3 ESP-IDF 6.0.3 build evidence
remains applicable. GS-150-specific new behavior tests/simulation and final
candidate build are blocked; no hardware action. Exact source analysis and
validation are recorded in the [battery guide](../features/BATTERY_LOW_POWER_AND_POWER_MANAGEMENT.md).

Starting local/remote checkpoint: `f245eebcd80c9e43a230ae0ee814f59a37adefd0`
on `feature/r1-commercial-baseline`; pre-existing untracked S3
`managed_components/` preserved. After documenting and commenting this stop,
commit/push the handoff. Next action: approve the ACK receive bound and validate
it against the Hub durable commit and Node existing retry schedule. GS-150
blocks final-candidate GS-114 physical qualification; GS-149 remains pending.

## C3 software-first battery audit — 2026-10-10

At canonical start HEAD `3279294e31345f0ff34d5d97ee456145375eb46a`, the
confirmed Hub-outage/backlog software gap remains: C3 light sleep is inhibited
by outage, every pending TX/ACK and retained event, so the single owner falls
back to a 20 ms poll while the existing retry/rejoin schedules remain much
slower. GS-D027 supports avoiding unnecessary Node wake-ups, but sleep with an
unacknowledged EventKey would stop authenticated ACK reception until radio
restore; the locked requirements do not define an ACK receive-window boundary
or a Hub-power-off recovery target. GS-D025 is only a powered Hub/local-radio
internet outage target. GS-147 remains design-only, blocked by GS-146, and its
expanded journal, offline envelope and ACK/retirement scope are not approved.
No firmware behavior or requirement changed pending that decision.

Read-only scope review and validation: `make battery-c8-host-test` PASS (72
C++ checks / 9 Python invariants); `make cpp-test` PASS (1,479); `make
python-test` PASS (344, one documented skip). Existing C3 ESP-IDF 6.0.3 clean
build evidence (931,424-byte image) remains applicable because no firmware
changed. No hardware actions. Diagnostics limitations, source references,
modeled wake frequency and C9–C12 disposition are in the existing
[battery/power guide](../features/BATTERY_LOW_POWER_AND_POWER_MANAGEMENT.md).

The 2026-10-10 latest Jira decision splits functional BAT-C8 P1–P9 to GS-114
and quantitative P10 to GS-149; GS-146 requires both. BAT-C12 deep sleep is
explicitly deferred. Next software action is to obtain an approved ACK-window
and Hub-off recovery/service contract before changing offline sleep eligibility;
then add deterministic outage/backlog/rejoin tests and rebuild C3. Preserve the
existing untracked S3 `managed_components/` directory. No branch/worktree
change, hardware work or journal expansion.

## Integrated software regression closure — 2026-10-10

Starting at canonical HEAD `5648d90426fb12b584a009eac0a88e754ad909c6`, the
confirmed C++ and PWA failures are closed with test-only/host-simulator fixes;
no firmware behavior or product requirement changed. `make cpp-test` passes
1,479 checks. `make python-test` passes 344 discovered tests with one explicit
skip: the classic ESP32 NVS capacity/reserve model is historical under GS-D030,
and S3 commercial capacity/reserve remain open. Its current source-bound parser
and raw-profile test pass. The PWA bridge, API scenario catalogue and frontend
suite pass after the host lab drains all bounded CloudSync batches, keeping
later activity and door-close events visible to the backend fixture.

The individual root causes, exact pre/post-fix exits, classifications, source
locations and regression risks are recorded in the [dated integration manifest](../exec-plans/evidence/R1_SOURCE_INTEGRATION_MANIFEST_20261010.md).
Focused BAT-C8 (72 C++ checks / 9 Python invariants), S3 durability/security,
replay/reclamation, P2-D HTTP/HTTPS, Node recovery/retirement and commissioning
crypto host gates pass. Firmware source is unchanged, so the existing clean
ESP-IDF 6.0.3 C3/S3 builds and selected ASan/UBSan evidence remain applicable;
no physical, production backend or OTA result is claimed. GitHub DNS was
unavailable at intake; the normal push then succeeded and actual remote HEAD
matched `dfc24d1db88fe6cd0fa7a51232a10f4152a4d5ae`.

**SOFTWARE_REGRESSION_STATUS=PASS_WITH_ONE_SCOPED_SKIP.** This does not close
S3 production backend authentication/receipt/connectivity, capacity/retention,
physical storage/FOTA qualification, or BAT-C8 physical P1–P10. No hardware was
touched. `READY_FOR_GS_114_PHYSICAL=YES`: software gates in this task
pass, but this work does not authorize or start physical qualification.
Jira comments for this closure were added to GS-110/10327, GS-114/10328,
GS-131/10329 and GS-148/10330; no status or rank changed.

## One-time source consolidation — snapshot at initial closeout, 2026-10-10

The user-approved destination is this canonical worktree `/home/udaybhan/projects/Ghar_sajag_r1`, branch `feature/r1-commercial-baseline`. Starting local and remote HEAD were `f6e949a79354ebd1a25c55a9b9a9b750bf387dac`; context preflight passed at `2026-10-09.001`. C3 BAT-C8 implementation is already in canonical history through ancestor `808080e`. Reviewed S3 target, P2-A/B/C and partial P2-D code/evidence were selectively cherry-picked with provenance; see [source integration manifest](../exec-plans/evidence/R1_SOURCE_INTEGRATION_MANIFEST_20261010.md). Integration source checkpoint before final handoff: `1febcf027baea892b95ed3a57615a4a562ee9b82`.

At initial consolidation closeout (the aggregate results are superseded by the regression-closure section above), BAT-C8 focused C++ (72 checks) and nine Python power-policy invariants passed; S3 outbox, segmented runtime, replay/checkpoint, identity, completion, mixed-body and P2-D HTTP/HTTPS suites passed. The P2-D SQLite bridge processed 300 events with no pending records; catch-up measured 26,458 ms in that host fixture. `make cpp-test` failed at `test_node_offline_resilience` expecting `next_sequence()==1001` after 1000 attempts; this same assertion is in the source P2-D evidence. `make python-test` ran 344 tests after the simulator link fix: 341 passed, one failed and two errored in G01/HIL checks (details in the integration manifest). Those historical results are not represented as passes. No Node/BAT-C8 production edit was made. Clean S3 and C3 ESP-IDF 6.0.3 builds passed in isolated `/tmp` build directories; sanitizer outcomes are recorded in the integration manifest. No hardware validation was performed.

**Active next product work remains BAT-C8 physical qualification** (GS-114), plus GS-144 target, GS-140/B0–B4 and matched AFTER measurements, GS-119 residual cases/12-hour soak, and GS-146 closure. No hardware action was taken. GS-115 C9–C12 remains conditional and measurement/decision-only; current boundaries are in [battery power management](../features/BATTERY_LOW_POWER_AND_POWER_MANAGEMENT.md). GS-147 remains a proposed sleep-first/offline-journal design only, not implementation approval; retain its Hub-off target, retirement/ACK interoperability and capacity requirements as unresolved until the issue contract is approved (audit findings: [C3/GS-147 section](../exec-plans/evidence/R1_CROSS_WORKTREE_REQUIREMENTS_CODE_AUDIT_20261010.md)). S3 GS-148 and parent GS-131 remain intentionally OnHold as a workstream; P2-D remains partial, production deletion disabled, and P2-E/F/Phase 3 gates open. The pre-integration cross-worktree audit is historical for source-absence claims; this manifest and checkpoint supersede those claims.

Cross-component follow-up remains open: production backend authentication/COMMITTED ownership and live Hub-to-backend-to-PWA flows (GS-117/121) are not proven; S3 storage/FOTA interruption and rollback compatibility (GS-118) remains unqualified. The activity/door assertion failures recorded at the initial integration snapshot are closed as a host fixture defect in the updated integration manifest. The P2-D handoff documents missing production contracts and the supported host fixture without representing it as live deployment evidence.

Untracked user files remain at their original worktrees: battery HIL scripts; S3 `sdkconfig` and `managed_components/`; storage `prompt.txt`; and Phase 2 generated build directories. No code from the unpublished 11-commit classic-storage range was merged.

## Initial integration delivery closeout — snapshot before regression follow-up

**CONSOLIDATION_STATUS=PARTIAL.** Commit `ed6cffcdbfcbd69118e41b436ef616a0bea927db` (`Record R1 source consolidation and validation handoff`) is pushed to `origin/feature/r1-commercial-baseline`; at verification, local HEAD and actual GitHub ref both equaled that hash. The tracked worktree is clean; generated untracked S3 `managed_components/` remains preserved.

At this initial integration snapshot, focused BAT-C8, S3 storage/security/recovery, P2-D HTTP/HTTPS and ASan/UBSan checks passed; clean isolated ESP-IDF 6.0.3 C3 and S3 builds passed. The aggregate failure details are historical and are superseded by the regression-closure section above. Production P2-D authentication/receipt/connectivity, canonical workload, live backend E2E, capacity/retention and physical qualification remain open. No hardware actions occurred; production destructive event/identity reclamation remains disabled.

Jira synchronization comments were added and read back successfully, without workflow or ranking changes: GS-110 comment 10321, GS-114 10322, GS-115 10323, GS-131 10324, GS-147 10325, and GS-148 10326. Evidence and source provenance are in the [dated integration manifest](../exec-plans/evidence/R1_SOURCE_INTEGRATION_MANIFEST_20261010.md). The six-worktree inventory and exact validation details are recorded there.

## Cross-worktree audit handoff — 2026-10-10

The active priority is BAT-C8 physical qualification (GS-114), with GS-144 target, GS-140/B0–B4 and matched AFTER power measurements, GS-119 remaining physical evidence/12-hour soak, and GS-146 C1–C8 closure. Reuse valid battery-branch physical PIR/GPIO4/ACK evidence only when image and setup provenance match. BAT-C8 software/host/build are complete; physical gate remains open. GS-115 stays conditional and To Do.

S3 GS-148/GS-131 are intentionally paused, not cancelled or complete. The reviewed source branch checkpoint is `e1941d7136c43fe6e21f4eff42527aa2d0de9a9a`; P2-D remains partial and production auth/receipt/connectivity/workload acceptance remains open. GS-148 is still In Progress in Jira while its description/comments document the pause; no workflow transition is made here. Production destructive reclamation remains disabled. The [cross-worktree audit](../exec-plans/evidence/R1_CROSS_WORKTREE_REQUIREMENTS_CODE_AUDIT_20261010.md) is preserved as historical triage; current source dispositions are in the [integration manifest](../exec-plans/evidence/R1_SOURCE_INTEGRATION_MANIFEST_20261010.md). No product decision or context-version change is made here.

**Updated:** 2026-10-10

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
not an approved partition change. Those implementation observations describe
the historical classic ESP32 target at that checkpoint. The canonical branch
now includes the selected S3 segmented encrypted outbox, checkpoint/replay
recovery, completion/identity metadata, mixed-segment host reclamation and
partial P2-D HTTP/HTTPS adapters. The 192 simultaneous Node-pending-key bound
still does not by itself bound accumulated ACKed-but-unreported Hub evidence.

S3 production acceptance remains STOP pending product outage/overflow decisions,
bounded retirement progress, reducer/model limits, backend summary/effect
completion, safe rollback/format transition, commercial image/partition fit and
crash/wear proof. Historical classic-target build sizes do not establish the
current S3 commercial OTA margin.
Existing physical qualification and deferred legacy migration classification
are unchanged; no firmware, physical event or new qualification was performed.

Subsequent efficiency phase preserves that architecture as documentation commit
`94fe1a8` and implements **isolated host-only policy-neutral primitives** under
the code project's `host/storage/`, with dedicated tests and benchmarks. No
production target lists or ACK path are changed. The optimized candidate shares
one immutable event across lifecycle owners; existing 128 KiB feasibility is
**CONDITIONAL**, so partition enlargement remains UNDECIDED rather than assumed.
The 128-event production limit describes the historical classic target, not the
integrated S3 segmented outbox. S3 commercial capacity and lifetime guarantees
remain unqualified. One million simulated events
show fixed 192-record storage and allocation-free primitives; existing journal
and backend completion host regressions pass. These are host results, not
physical durability/GC/rollback qualification. See ExecPlan section 20 and its
host evidence for exact byte budgets, benchmark scope and remaining STOP gates.

Complete S3 production storage/data-lifecycle qualification for the GS-D030 Hub and six-Node worst case. The following accepted implementation areas are integrated, but remain subject to product acceptance and physical proof:

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
and [density evidence](https://github.com/udaybhan200683/Ghar_sajag/blob/2b3c6730f8c490ba88a13ba2c23d6674c4c30fa8/docs/exec-plans/evidence/R1_STORAGE_ENCODING_DENSITY_20261007.md)
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

## Product governance preparation and canonical promotion — 2026-10-08

Storage-worktree preparation (historical checkpoint) at starting HEAD
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

**Authorized canonical promotion:** promote only the reviewed governance edits
from source commit `4732679aabbe354bb6c771a4b8ac81437d8c45c5` to
`/home/udaybhan/projects/Ghar_sajag_r1` on `feature/r1-commercial-baseline`,
starting clean at `5dcd2f7c10682bd1f6801821deaff20ad4a803e4` and context
`2026-10-07.003`. Canonical context becomes `2026-10-08.001`, matching storage.
The promoted scope is exactly these eight governance files:

- `docs/product/DECISION_LOG.md`
- `docs/product/R1_RELEASE_CONTRACT.md`
- `docs/product/R1_WORK_STATE.md`
- `docs/product/P0_PRODUCT_REQUIREMENTS.md`
- `docs/product/CANONICAL_REQUIREMENTS_INDEX.md`
- `docs/product/GHAR_SAJAG_PROJECT_CONTEXT.md`
- `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md`
- `docs/product/CONTEXT_VERSION`


Existing canonical content is preserved. Storage-only technical checkpoint
notes, ExecPlan section29, prototype code, tests and evidence files are excluded.
The source branch and user-owned untracked `prompt.txt` remain unchanged.
Validate both worktrees with the existing preflight, commit canonical governance,
and push only the canonical branch to the verified origin using a fast-forward
update. Do not weaken the guard. No capacity/battery/hardware qualification or
production implementation is implied; subsequent work requires a separate task.

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

Context2026-10-09.001 records the explicit S3 N16R8 selection. By the user-approved
one-time consolidation on 2026-10-10, reviewed S3 source/evidence is integrated
into this canonical worktree and `feature/r1-commercial-baseline`; see the
[source integration manifest](../exec-plans/evidence/R1_SOURCE_INTEGRATION_MANIFEST_20261010.md).
The former S3 worktree and storage branch are preserved as provenance; do not
resume development there. No experimental storage lifecycle code or unapproved
capacity policy was promoted.

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
C3 asset, successful ESP-IDF6.0.3 S3 builds and a physical diagnostic PASS at
that historical checkpoint. No physical tests were performed during the
2026-10-10 consolidation.
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
