# R1 Hub storage implementation readiness — 2026-10-08

**Result: NOT READY for production integration.** Gates A–C remain blocked by
specific application transactions and capacity admission, not by a demonstrated
ESP-IDF power-loss defect. Keep ESP-IDF NVS, the 4 MiB Hub and the current Node
stream. No new Node batching, compression investigation or hardware dependency.

This is supporting host evidence, not canonical policy or target qualification.
Preflight PASS at `2026-10-08.001`; source branch
`feature/r1-hub-storage-lifecycle`, starting HEAD
`3201886636807925f84478e88edd8dc9cc2a4731`. Canonical HEAD `3b72892` and matching
context were checked. Origin is `https://github.com/udaybhan200683/Ghar_sajag.git`.
The starting reviewed commit was ahead one, behind zero; explicit dry-run/push
and fetch established origin equality. New proof changes are not authorized for
push. Only existing untracked `prompt.txt` was present; its content was not read.

Read AGENTS, the mandatory context/release/work-state/index sequence, Decision
Log, canonical storage contract, active ExecPlan, 72-hour checkpoint/capacity
and both closed Node investigations. GS-D025–028 are active. Earlier documents'
`.003` and pending-promotion statements are historical. No canonical files or
CONTEXT_VERSION change in this run.

```text
BUG_CLASSIFICATION=R1_BLOCKER (storage lifetime/readiness); INVESTIGATE_ONLY (new counterexamples)
REQUIREMENT_SOURCE=docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md; docs/product/R1_RELEASE_CONTRACT.md
DECISION_IDS=GS-D005/016/020/021/022/023/024/025/026/027/028
TASK_SCOPE=bounded host admission, recovery and protected-progress proof and handoff
OUT_OF_SCOPE=production integration, Node delivery changes, partitions, BAT-C8, backend/PWA, canonical governance, Jira, hardware, new proof push
```

`P = code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/` below. Source references
are unchanged production at the starting HEAD. New checks reuse its codecs,
MemoryBlobStore fault fixture, report repository, admission model and SDK probe.

## Gate A — exact admission and retirement credits

For each **retained authenticated enrollment owner** i, define:

- P_i: the complete pending set in the durably selected report, size <=32.
- U_i: accepted immutable keys not covered by that selected report, size <=W.
- E_i: accepted keys whose exact retry identity has not been safely retired.

The required invariant is `E_i subset P_i union U_i`. Consequently
`sum |E_i| <=6*(32+W)` only if there are at most six retained owners and both
report selection and uncovered-credit spending survive restart atomically.
`W=32` gives 384 **exact identities**, not 384 full bodies, history objects,
backend obligations or free-space admission rights. W and class reserves remain
unapproved proof parameters.

Induction: a new covered key must be explicitly pending; covered absent keys
are retired/stale. A new uncovered key consumes one credit in the same durable
transaction as its identity/body. An identical retry consumes none; a changed
digest conflicts. A newer complete report retains every listed covered key,
removes only covered absent identities, and recomputes U from surviving keys.
An uncovered key becoming covered-but-pending returns credit without deleting
its witness. Merely increasing report generation, event ACK count, boot or
transport session cannot refill credit. Replacing an enrollment cannot erase
its accepted obligations or authorize its reports through a new owner.

The new finite test reaches 384 with six owners, rejects a 65th uncovered/covered
combined key per owner, accepts exact lost-ACK retry at fullness, rejects changed
retry, replay/oversized reports and enrollment mismatch, and proves generation
increments alone do not refill. A selected progress report keeps an accepted
pending key and makes absent covered keys Stale; resurrection conflicts.
Copied-snapshot recovery passes **only the existing atomic host assumption**.
No flash credit serialization was implemented.

**Concrete missing enforcement:**
`P/firmware/hub/components/storage/node_retirement_snapshot.hpp:15–16` currently
provides a 128-entry ExactEventKeyLedger; its `classify/insert` methods
(`.cpp:371–411`) have no per-owner uncovered gate. The new test admits 33 distinct
uncovered keys for one owner without a report. Sequential creation/durable ACK/
Node retirement permits Node queue peak one, so its 32-pending limit does not
bound this lifetime. This is a component counterexample; it does not simulate
every target scheduler interleaving. `DurableStore::commit` (`durable_transition.cpp:730`)
checks exact tail/evidence/report identity but has no such credit transaction.
Existing global limits eventually reject work; they are not a 384-key lifecycle
proof. Reports are sent preferentially by the C3 adapter at 1366–1423, but frame
completion and report ACK are distinct, and the data-send guard at 1425 does not
require acknowledgement of each latest report generation. Report delivery is
not a replacement for persisted Hub admission accounting.

**Six-owner premise is also not yet enforced by this implementation:**
`P/firmware/hub/target/esp32/hub_security_link.hpp:28` has installed capacity ten;
registry and retirement arrays also have ten slots. Restricting an R1 installation
to six active devices still needs a bounded old-enrollment obligation/revocation
rule. Old required identities must stay charged until legitimate retirement or
an authenticated, durably fenced revocation that preserves other owners' bodies
and cloud responsibilities. Do not map ten enrollment slots modulo six or reset
credit on replacement. This finding is within Gate A, not a new registry project.

Reusable authenticated path: `HubSecurityLink::resolve_enrollment_binding`
(`hub_security_link.cpp:536`) verifies physical/logical identity, home/Hub,
quarantine, active slot, owner digest and generation. The adapter's report
reassembler verifies the installation-key-derived HMAC before
`apply_authenticated_report` (`hub_runtime_adapter.cpp:829–887`). The latter
rejects epoch/transport-origin errors, generation conflicts, decreasing highwater
and resurrection (`node_retirement_snapshot.cpp:285–369`); `prepare_bank/load`
bind exact authenticated snapshot bytes and generation. This path is reused,
not replaced by trusting the synthetic model digest or nonzero HMAC argument.

Lost/delayed reports must leave U charged and all accepted E intact. Missing or
corrupt **selected** reports cause fail-closed recovery; corrupt incoming or
incomplete reports grant no credits. Fullness rejects new admission without
durable ACK while allowing validated duplicates; control/report traffic needs
independent progress space. Infinite lost reports cannot imply infinite continued
safety-event storage. The bounded critical saturation/delivery response needs
product approval; this proof does not call exhaustion harmless.

**Gate A: FAIL / integration invariant not established.** Conditional induction
and finite tests PASS; smallest remaining work is authenticated persisted
report/credit/exact-key association, retained-owner enforcement/revocation, and
physical admission integrated before ACK. No new Node ACK token or protocol is
needed for the safety invariant. Backend-pending bodies remain even after their
retry identity becomes retirement-eligible.

## Gate B — selected root, interruption and corruption

Reuse `DurableStore::commit/checkpoint/recover`, `HubDurabilityOwner`,
`RetirementSnapshotRepository` and `NvsDurableBlobStore`. Current NVS initialization
never erases on failure; writes commit and verify exact bytes, immutable collisions
fail, and ambiguous API failure is distinguished (`nvs_durable_blob_store.cpp:36–157`).
`DurableJournalSlotStore::append_event` verifies enrollment and canonical payload
HMAC, accepts only Committed/AmbiguousResolvedCommitted (`.cpp:177–207`).
`HubRuntime::process_next` refuses Full/StorageFault and ACKs duplicates without
reapplying reducers (`hub_runtime.cpp:176–198`). Preserve this external ACK contract.

The prior tests remain scoped evidence: record fail-before-write is not ACKed;
persist-then-error resolves through exact readback; torn event records fail
closed; inactive checkpoint tears preserve old checkpoint plus required tail;
selected report/evidence children authenticate. Prior independent NVS report/
selector/old-retirement tests cover 2,702 supported interruption/recovery cases;
the 60 GC-primed SDK samples and corrected freeze-after-cut1072 model remain
valid for their unchanged operations. No broad campaigns were repeated.

**New selected-root counterexample using actual production codecs/store:**
publish and verify checkpoint generation1 with reducer byte0x11; publish and
verify generation2 with reducer byte0x22; keep both authenticated selectors.
Corrupt generation2's checkpoint bank, then restart. `DurableStore::recover`
returns success, generation1, reducer0x11. Removing generation2's bank gives the
same result. `durable_transition.cpp:608–624,694–695` chooses the newest selector
whose *child is valid*, not the newest authenticated publication followed by
mandatory child validation. `HubDurabilityOwner::inspect_checkpoint_set`
(`.cpp:130–164`) expressly permits older-selector fallback. The focused test is
at the DurableStore layer, not a full target/owner/alert simulation.

The fixture contains no event tail; it demonstrates lost durably published
reducer state. It does **not** assert that a current physical Hub has lost an
ACKed input. Retained tails can make specific older-root replays safe today.
Nevertheless this selection rule cannot certify a new compacting/credit engine:
an older root may lack newer credits, learning/outbox application or required
identity, once newer ownership has enabled reclamation. Generation rollback
needs an explicit replay/ownership equivalence proof, never an assumption.

Smallest correction to prove next: select the highest authenticated publication
before validating its complete dependency closure; fail closed when that
publication's child is corrupt/missing. Separately distinguish an unpublished
torn candidate from loss of a committed selector using durable publication/
freshness state, reusing the existing authenticated bank/transaction patterns.
If a committed selector itself vanishes, a surviving older selector alone cannot
prove freshness. Bind epoch, owner generations, report reference, exact evidence,
credit/class state, reducer/outbox cursors and release authority to the selected
transaction. Prove nonce uniqueness and format/rollback behavior; no custom
raw-flash engine is warranted. Do not simply reject every harmless unselected
torn checkpoint and claim interruption availability is qualified.

**Gate B: FAIL.** Record/old-new bank primitives are qualified within their prior
host scope; complete authenticated credit/root recovery and publication freshness
are not. A recoverable old state is valid only when it still includes/reconstructs
every accepted obligation; otherwise fail closed and emit no durable ACK.

## Gate C — required ownership, temporary space and progress

**Report dependency counterexample:** the adapter at 865–870 protects only the
currently selected report bank when calling `prepare_bank`. Seed old report bank0
and selected bank1, with old/selected roots still potentially recoverable. A torn
generation3 write with mask `1<<bank1` overwrites bank0; bank1 survives but the old
root's child no longer authenticates. The new host check reproduces this with
the actual encrypted repository. Passing the union of both referenced banks to
the same three-bank repository makes both old and selected children survive.
That is a demonstrated reusable correction, not a firmware modification.
Protect dependencies of **every still-authorized recovery root**, then release
old roots and their dependencies only after verified new publication/fencing.
Blindly protecting all historical blobs is neither bounded nor necessary.

The new `progress` mode in the existing SDK probe seeds the existing nine-segment
layout, performs the existing 1,000-cycle setup, then retains 12 segments. It
captures all 30 dummy certificate/report/state/root/metadata/critical/history
blobs. Three bounded candidate-report/root attempts each return
`ESP_ERR_NVS_NOT_ENOUGH_SPACE`; after remount all 30 exact byte strings survive.
Final stats: 31 nonblank pages, one erased page, 3,844 live entries, 188 reported
free entries. Enough-looking entry totals and the SDK's free GC page do not
ensure a blob/checkpoint operation can allocate. The test does not authenticate
these dummy objects or run the full application transaction.

**Gate C: FAIL.** Preservation after this insufficient-space case PASS;
protected next-operation progress is BLOCKED. Three retries are a test bound,
not an approved product retry policy. Identical pressure does not create free
space; production must return a bounded storage fault/backpressure result rather
than loop, ACK, remove unretired evidence or reset epoch.

Prior arithmetic remains: next report+root requires at least4,128 NVS entry bytes
plus4,096 internal GC and page/fragmentation allowance. Three pages /12,288 B are
a lower reservation obligation, not a qualified guard. Nine history segments,
192 maximum-HOT bodies and independent report/checkpoint/root coexistence require
155,648 B in the prior tested mapping; 128 KiB is short24,576 B. Three history
segments progress at128 KiB only in their narrower fixture. Neither proves a
supported72-hour information envelope. Accounting must include all still-live
old/candidate roots and their children, physical page/chunk/COW duplication,
control updates, HOT promotion and interrupted reclamation/resume.

Smallest necessary guard: before new event admission, bound the full next
admission **and** required report/root/checkpoint/GC operation against a proven
allowed layout; preserve their workspace independently of ordinary traffic.
An NVS used-entry percentage or a single passing layout cannot substitute for
that proof. Serialize bounded promotion; only reclaim objects with no selected
root, retry, local consumer or cloud owner. Resume interrupted reclamation from
selected durable state, with a bounded amount of work per owner-loop step.
Re-run relevant SDK cuts for the actual new authenticated transaction when it
exists; do not infer its safety from the dummy or CRC-only raw fixtures.

## Capacity and OTA reality — inherited results, no new matrix

Actual unchanged CSV: `P/firmware/hub/target/esp32/idf/partitions.csv`,
`gs_journal=0x3E0000+0x20000` (131,072 B, 32 pages); dual OTA slots each
`0x1E0000` (1,966,080 B); whole layout ends at4,194,304 B. Separate system NVS
is24 KiB and cannot be silently borrowed. Raw partition bytes are not usable
payload bytes: headers, chunks, live recovery copies, reserved operations and
internal GC remain charged. There is no universally qualified usable-payload cap.

Current semantic source-derived six-Node72h inputs remain1176 NORMAL,5352 HIGH,
10476 literal paired45s STRESS (includes24 Hub-local outcomes). STRESS is a
scenario, not worst case; paired46s sensitivity remains68220. Retain existing
PIR consolidation and ESP-NOW ACK-driven delivery; no speculative event reduction.

The latest source-derived **conditional** Hub compaction peaks from the closed
Node audit, including source-native summaries and protected owners, are:

| Fixture | Exact Hub inputs | Candidate protected peak | Gap against128 KiB |
|---|---:|---:|---:|
| NORMAL ordinary |1176|249,856 B /244 KiB|118,784 B /116 KiB|
| NORMAL mixed |1176|278,528 B /272 KiB|147,456 B /144 KiB|
| HIGH ordinary |5352|638,976 B /624 KiB|507,904 B /496 KiB|
| HIGH mixed |5352|745,472 B /728 KiB|614,400 B /600 KiB|
| STRESS literal ordinary |10476|1,204,224 B /1176 KiB|1,073,152 B /1048 KiB|
| STRESS literal mixed |10476|1,384,448 B /1352 KiB|1,253,376 B /1224 KiB|

These figures assume trusted time/coverage and an unapproved summary/backlog
contract; they are not deployable format sizes or promised event bounds. Initial
durable admission still handles every exact input. Existing secure target time
uncertainty prevents using the modeled eligibility as a production capacity claim.
Exact fallback NORMAL alone models308 KiB. The older narrower72h analysis's
232 KiB NORMAL ordinary,276 KiB mixed and524 KiB HIGH inputs remain scoped to
their earlier composition. Do not choose the smaller figures as current qualification.

No supported guaranteed workload has been approved or qualified. Current128 KiB
does **not** satisfy the tested complete72h fixtures. It is not proven impossible
for every narrower future approved envelope. Prior192 KiB typical-NORMAL passes
are narrower; latest source-derived worst-size fixtures fail192 KiB. Latest256 KiB
ordinary NORMAL has one successful capacity/update/reclaim witness; mixed NORMAL,
HIGH and STRESS still fail. Thus256 KiB is not a solution for all supported workloads.

Prior image1,864,624 B leaves101,456 B in current slots. Reviewed temporary192/
256 KiB layouts both leave only35,920 B limiting image margin because of OTA
alignment. No integrated image was built, so future code/RAM/embedded Node-image/
rollback headroom is UNPROVEN. Application RAM planning budgets also remain
unmeasured target allowances, not qualification. No partition file changed.

Viable decisions after the transaction proof: approve a realistic bounded
information/volume envelope and saturation response; verify safe reduction of
still-required live owners/HOT coexistence within128 KiB; or review a partition
increase against that envelope and a measured integrated dual-OTA image. Keep
summary/backend equivalence and time/coverage prerequisites explicit. If the
approved workload plus recovery/OTA cannot fit4 MiB, raise a product hardware/
scope decision; do not repeat optimization experiments indefinitely or select S3.

## Small implementation handoff after the failing gates are corrected

1. **First, host transaction proof:** correct/prove native publication freshness
   and all-root dependency ownership with the existing authenticated codecs and
   bank repository. Add persisted admission-credit/class/owner associations to
   the same selected state; reconstruct them from selected exact evidence on
   restart. Exercise the counterexamples here as desired fail-closed/recovery
   acceptance checks, not permanently expected unsafe outcomes.
2. **Then protected physical admission:** prove finite next-operation reservation,
   bounded HOT promotion, old-root release and resumable reclamation on SDK NVS.
   Inject interruptions at event creation, credit spend, report-bank preparation,
   checkpoint and selector publication, old-root release, reclamation and remount.
   A cut before publication never permits ACK; a cut after publication preserves
   the full obligation or fails closed. Lost ACK retries retain immutable identity
   and cause no duplicate local/cloud effects.
3. **Only after A–C PASS and policy closure, integrate durable admission/recovery
   first:** `storage/durable_transition.{hpp,cpp}` (`Checkpoint`, `commit`,
   `checkpoint`, `recover`); `storage/node_retirement_snapshot.{hpp,cpp}`
   (`prepare_bank`, `load`, `classify`, retirement reduction);
   `storage/hub_durability_owner.{hpp,cpp}` (`recover`, checkpoint inventory);
   `target/esp32/nvs_durable_blob_store.{hpp,cpp}` (bounded provider writes/errors);
   `storage/durable_journal_slot_store.cpp` (`append_event`, `flush`, `rows`);
   `target/esp32/hub_runtime_adapter.cpp` (authenticated report selection/ACK);
   and `runtime/hub_runtime.cpp` (`process_next`) at the existing ACK boundary.
   Reuse authenticated owner resolution in `hub_security_link`; enforce the
   approved six-retained-owner rule rather than renumbering raw enrollment slots.
   Do not replace all modules at once or introduce a Node protocol dependency.
4. **Scoped integration acceptance:** relevant durable-storage/provider,
   retirement-snapshot and fresh-install recovery host gates; new complete
   transaction cut/retry/dedup/owner/class tests; installed SDK GC/COW/recovery
   checks for the changed transaction. Build the ESP32 Hub IDF target and measure
   image/partition fit, RAM peak and rollback compatibility before hardware use.
   Run separately authorized target power-interruption/lost-ACK qualification
   only when changes invalidate prior evidence. No full release gate here.

Urgent preemption/bounded delivery, physical BAT-C8 sleep-current/wake qualification,
ESP-NOW retransmission energy and health/coverage freshness remain separate R1
Node/power qualification. They are not discarded or dependencies on a speculative
new batching protocol. No Node production or BAT-C8 change in this run.

## Validation and stopping point

[Raw focused results](R1_STORAGE_READINESS_HOST_20261008.log):
`make -C P storage-readiness-host-test` PASS (conditional invariant and four named
counterexamples); ASan+UBSan PASS outside sandbox (LeakSanitizer cannot run under
the sandbox's ptrace); one new installed-SDK `9 1000 20 progress` case PASS,
with progress explicitly BLOCKED and all30 baseline blobs preserved after remount.
An initial CMake invocation lacked IDF_PATH; retry with the existing README
environment built successfully. Prior logs are preserved; no new general matrix,
million-event loop, Node campaign or hardware result. The new progress branch
does not change existing SDK fault/capacity modes.

Reproduce the focused C++ case with the Make target; for SDK, build using the
existing [probe README](../../../code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/host/storage/nvs_runtime_probe/README.md)
environment, then run its executable with `9 1000 20 progress`. Scratch images
are removed only by the exact path emitted by that child. `git diff --check` and
final context preflight PASS are required before commit. No production format,
partition, context, canonical worktree, BAT-C8 or backend change.

**Next bounded task:** prove the native authenticated publication/credit/report
transaction and its all-root ownership using these counterexamples; then qualify
its protected NVS next-operation admission. Product supported-volume/critical
saturation and summary/time/coverage decisions remain separate formal governance
work. Stop before production integration or new-proof push.
