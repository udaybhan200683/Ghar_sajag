# Phase 3B Controlled Concurrent API Load and Household Isolation

Status: **QUALIFIED (MANUAL QUALIFICATION COMPLETE)**

Phase 3B remains IN PROGRESS. The qualified Reports scalability checkpoint is
`0e5a9e3`; the earlier qualified scale/read-path checkpoint remains `fee5854`;
the permanent Phase 3A anchor remains `4dcaf99`. This uncommitted work does not
replace any of those anchors.

## Concurrency model found

- The local HTTP adapter uses `ThreadingWSGIServer`, so browser/API requests can
  enter concurrently.
- `FoundationService` owns one SQLite connection configured with
  `check_same_thread=False` and an `RLock`; each foundation method already holds
  that lock through its transaction.
- `SQLiteEventMap` uses the same foundation lock in the integrated lab, but the
  previous event duplicate check and insert were separate mapping operations.
- Core homes, memberships, incidents, notification jobs, devices and configs
  are process-local dictionaries. Their request path therefore needs one
  process lock around a complete core API operation.
- Reports execute household-filtered SQLite reads under the event-map lock.
  Notification preferences/records and device registry/health reads and writes
  are household-filtered SQLite operations under the foundation lock.
- Parallel WSGI dispatch is retained, while shared local application state is
  intentionally serialized by the existing re-entrant application lock.
  Contention is diagnostic; wall-clock duration is not a correctness gate.

## Isolation risks corrected

The Python event-store contract used `(home_id, event_id)`, but the original
SQLite table retained a global `event_id` primary key. `INSERT OR REPLACE`
could therefore replace another household's durable row when both households
used the same canonical event ID. The check-then-insert ingestion sequence was
also not atomic as a complete duplicate decision.

Migration `007_phase3b_household_event_identity.sql` adds the explicit
household-local `canonical_event_id`, a unique `(home_id,canonical_event_id)`
index, and aligned chronology indexes. The existing relational `event_id`
column remains an opaque internal key so historical foreign-key contracts are
not rewritten. API/read-model ordering and returned identity use the canonical
ID.

`SQLiteEventMap.accept_once()` now performs the durable duplicate decision and
insert under one lock/transaction. Core JSON API dispatch and the integrated
threaded lab request boundary hold the same application lock through complete
operations. The existing safety serialization was strengthened, not removed.

The device-health history insert also now includes `home_id` in its registry
source predicate.

## Bounded harness

`tools/stress/run_concurrency.py` is a dedicated socket-free WSGI concurrency
qualification harness. It uses six bounded workers and fixed seed `30401`.
It creates two households through the existing home/foundation services, then
overlaps:

- canonical event ingestion and replay in both households;
- malformed-event rejection;
- compact and full PWA reads;
- household snapshots and Today/Week/Month reports;
- device health and registry reads;
- notification history/preferences and persisted notification decisions;
- caregiver incident acknowledgement.

Both households intentionally use the same canonical event IDs, event kinds,
and the caregiver-facing device name `Shared Hall Sensor`. Their physical
device IDs remain distinct because the current registry ownership contract
binds a device identity to one household.

The harness verifies deterministic accepted/duplicate/rejected counts,
chronology, bounded Home/report/notification projections, per-domain household
markers, authorization denial across households, persisted row ownership,
SQLite busy/lock diagnostics, and worker/simulator cleanup. It is exposed as
`make concurrency-test` and remains separate from the normal final release
gate.

## Current host evidence

- focused concurrency plus Phase 3B projection/report regressions: PASS (`9/9`);
- focused schema/migration suite: PASS (`9/9`), including an explicit existing
  schema-006 to schema-007 history/report/reference upgrade fixture;
- full `make python-test`: PASS (`107/107`);
- `make app-test`: PASS (`3/3`);
- `make performance-test`: PASS, including structural budgets and SMALL stress;
- `make stress-test`: PASS (MEDIUM);
- six-worker harness: PASS;
- per household: 12 accepted, 6 duplicates, 2 malformed rejected;
- per household: 3 incidents and 3 persisted notification records;
- SQLite busy/locked failures: zero;
- unexpected request failures: zero;
- worker-thread leaks: zero;
- simulator process cleaned up: yes;
- final recorded harness duration: 147.446 ms on this host (diagnostic only);
- SMALL: 120 accepted / 12 duplicate / 6 rejected, zero request failures;
- MEDIUM: 2,500 accepted / 250 duplicate / 50 rejected, zero request failures;
- MEDIUM total: 3,945.727 ms; report stage: 111.019 ms (diagnostic only).
- Manual qualification: `make concurrency-test`: PASS;
  `make release-gate-final`: PASS; Playwright: `86/86` PASS; SMALL: PASS;
  MEDIUM: PASS; LARGE: PASS with 25,000 accepted, 2,500 duplicates, 250
  rejected, zero request failures, `correctness_gate` PASS, database size
  20,828,160 bytes, maximum RSS approximately 64 MB and wall time
  approximately 49.9 seconds; migration 006→007 preservation regression:
  PASS.

LARGE and EXTENDED were intentionally not run for this focused task.

## Remaining Phase 3B work

- notification-provider storm qualification;
- restart/recovery campaign;
- database/resource failure injection in its later scoped campaign;
- EXTENDED/endurance and remaining long-soak work.

This checkpoint is qualified based on the completed manual review and
validation. The later approved checkpoint commit hash is intentionally not
recorded here yet.
