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
