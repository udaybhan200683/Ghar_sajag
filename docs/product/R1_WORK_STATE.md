# R1 Current Work State

**Updated:** 2026-10-07

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
- design must first fit the existing 4 MB Hub;
- exact retention/offline-capacity numbers are not yet locked.

## Next engineering task

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

Derive and close the storage/data-lifecycle design for the existing 4 MB Hub and six-Node worst case before implementation. Separate:

1. active correctness journal and dedupe state;
2. materialized routine/reducer state;
3. backend outbox and completion semantics;
4. short local history/cache and safe reclamation;
5. offline capacity and six-Node worst-case event rates;
6. flash wear, crash-safe cleanup reserve and OTA budget.

Do not implement a guessed retention policy or merely increase the 128-event constant. Exact retention/offline-capacity numbers and partition-layout changes remain open decisions. See `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md` and `docs/product/DECISION_LOG.md`.

## BAT-C8

GS-D020 traceability: GS-114 — implementation/focused qualification; GS-146 — final R1 battery closure. Issue completion is not inferred from this mapping.

BAT-C8 is an R1-required feature with physical qualification pending (GS-D020). Physical cases P1–P10 remain NOT_RUN; these are test case IDs, not priority labels. Required production proof covers sleep entry, GPIO/timer wake, bounded resume, sensing/runtime and radio restoration, safe fail-awake behavior, and event-processing regression. Do not block on final battery-life optimization or long-duration endurance absent an explicit R1 battery-life claim. No BAT-C8 tests were run as part of the documentation decision.

## Stop rule

If work does not fix an R1 blocker or implement a locked R1 requirement, strongly consider backlog.
