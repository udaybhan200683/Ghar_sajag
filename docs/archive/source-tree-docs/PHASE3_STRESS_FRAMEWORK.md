# Phase 3 Deterministic Stress Framework

Document revision: **P3A-R1**

`tools/stress/run_stress.py` creates an isolated temporary SQLite database,
uses a fixed seed, drives the real JSON/domain ingestion and report paths, emits
machine-readable JSON, records counts/payload/storage/RSS diagnostics, and
removes its test data on exit.

## Profiles

| Profile | Intended use | Events | Duplicates | Malformed | Extra devices | Default gate |
|---|---|---:|---:|---:|---:|---|
| SMALL | developer/release smoke | 120 | 12 | 6 | 5 | Python discovery and `make performance-test` |
| MEDIUM | thousands-scale host stress | 2,500 | 250 | 50 | 18 (25 total) | `make stress-test` |
| LARGE | substantial explicit stress | 25,000 | 2,500 | 250 | 25 | manual opt-in only |
| EXTENDED | endurance/soak foundation | 100,000 | 10,000 | 1,000 | 25 | `make endurance-test`; never a normal gate |

Configuration is centralized in `tools/stress/profiles.json`. LARGE and
EXTENDED reject direct execution unless `--allow-large` is explicit. Profile
database ceilings are conservative safety bounds; temporary data is never
written into the normal application database.

## Correctness gate versus diagnostics

Correctness failures include count mismatches, unexpected request failures,
unbounded Home/notification/report collections, payload-budget violations or a
profile database exceeding its configured ceiling.

Diagnostic-only metrics include duration, process/simulator RSS, payload maxima
and actual database bytes. These vary by host and are reported without fragile
timing or exact-memory assertions.

## Coverage foundation

| Area | Phase 3A status | Later expansion |
|---|---|---|
| Event storm, duplicates, malformed events | bounded SMALL/MEDIUM implemented | LARGE/EXTENDED qualification |
| Many devices | 25-total MEDIUM projection implemented | architecture maximum and simultaneous health transitions |
| Durable history and Reports | real SQLite history plus Today/Week/Month cycles | multi-month/accelerated 30-day oracle |
| Notification storm | distinct/deduplicated records and bounded browser response measured | provider/rate-limit/failure storm matrix |
| API load | serialized repeated Home/full/report reads | controlled concurrency and household isolation |
| Repeated navigation/resource trend | Playwright Phase 3A spec | long browser endurance campaign |
| Database failure/disk-full equivalent | existing transactional unit seams retained | consolidated failure-injection campaign |
| Restart/recovery | existing Phase 1/2 persistence tests retained | stress restart checkpoints |
| Accelerated household soak | profile/configuration seam established | Phase 3B/3C 30-day deterministic scenario |

Commands:

```bash
make performance-test
make stress-test
make stress-test STRESS_PROFILE=LARGE
make endurance-test
```

Release-gate policy:

- `make release-gate-final` includes `performance-test`, which runs the
  deterministic performance profile and the SMALL stress smoke;
- `make stress-test` remains a separate stronger MEDIUM qualification target
  (with LARGE only by explicit profile/opt-in);
- `make endurance-test` remains the explicit EXTENDED endurance/soak target and
  is not part of the normal final gate.

## Phase 3B observability update - IN PROGRESS

The focused Phase 3B durable-history optimization adds bounded stderr progress
for setup/devices, accepted ingestion, duplicate replay, malformed rejection,
API/PWA reads, report cycles and final verification. Long loops report only
25/50/75/100 percent milestones. JSON/stdout remains machine-readable, and the
final `diagnostics.stage_duration_ms` object records diagnostic-only stage
elapsed times. No elapsed time is a correctness gate.

Query-plan, projection and progress/JSON regression coverage is in
`tests/python/test_phase3b_projection_scale.py`. Implementation evidence is
recorded in `docs/PHASE3B_SCALE_OPTIMIZATION.md`. This focused scale/read-path
work was subsequently qualified at checkpoint `fee5854`; Phase 3B overall
remains IN PROGRESS and EXTENDED is not claimed.

## Phase 3B Reports scalability update - IN PROGRESS

The stress runner preserves the existing report-cycle stage timing and now also
records diagnostic-only cumulative `TODAY`, `WEEK`, and `MONTH` durations under
`diagnostics.report_period_duration_ms`. Timing remains non-gating, stderr
progress is unchanged, and stdout remains machine-readable JSON.

The host-validated report read model aggregates durable history in SQLite and
materializes only bounded highlights. MEDIUM report cycles improved from
675.680 ms to 106.244 ms on the same host. An explicit LARGE run passed all
correctness checks and reduced report cycles from approximately 27.3 s to
5.320 s. Evidence is in `docs/PHASE3B_REPORT_SCALABILITY.md`.

Phase 3B remains IN PROGRESS. `fee5854` remains the previous qualified Phase 3B
checkpoint until this Reports work is manually qualified and committed.

## Phase 3B controlled concurrency and isolation update - IN PROGRESS

`tools/stress/run_concurrency.py` adds a separate fixed-seed, six-worker
concurrency mode. It overlaps real WSGI core API requests and persistent
foundation operations for two households, including compact/full state,
snapshots, Today/Week/Month Reports, canonical event ingestion/replay,
malformed rejection, device health, notification preferences/history, and a
caregiver acknowledgement.

The households deliberately reuse canonical event IDs and caregiver-facing
device names. Correctness checks cover household-local event identity,
snapshots, reports, incidents, notifications, devices, preferences and raw
database row ownership, plus deterministic counts, collection bounds, SQLite
busy/lock errors, and thread/process cleanup. Timing is diagnostic only.

Run it explicitly with:

```bash
make concurrency-test
```

The focused Python regression is included in normal discovery because the
SMALL harness is bounded and fast. The separate target is not added to
`release-gate-final`; MEDIUM/LARGE/EXTENDED concurrency is not implied.
Detailed evidence is in `docs/PHASE3B_CONCURRENT_API_ISOLATION.md`.
