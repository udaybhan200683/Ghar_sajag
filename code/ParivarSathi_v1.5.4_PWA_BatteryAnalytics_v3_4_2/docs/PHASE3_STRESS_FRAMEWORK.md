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
