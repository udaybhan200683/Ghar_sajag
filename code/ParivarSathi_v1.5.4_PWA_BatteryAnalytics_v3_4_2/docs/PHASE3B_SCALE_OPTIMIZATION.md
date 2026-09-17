# Phase 3B Durable-History Read Optimization

Status: **QUALIFIED CHECKPOINT `fee5854` / PHASE 3B OVERALL IN PROGRESS**

Phase 3A remains COMPLETE / QUALIFIED at implementation anchor `4dcaf99`.
This focused Phase 3B change was qualified after mandatory browser/final-gate
validation. It does not claim completion of the broader Phase 3B load/scale
scope.

## Confirmed causes

Representative `EXPLAIN QUERY PLAN` checks against a 25,000-event SQLite
fixture showed that the existing `idx_events_home_time` index did not match the
`occurred_at,event_id` ordering used by bounded snapshot/timeline queries.
SQLite used temporary B-trees for timeline, event-kind, latest-received and
event-count query shapes.

The caregiver projection also recursively converted every in-memory incident
dataclass on every poll. MEDIUM creates 500 incidents; LARGE creates 5,000.
Home consumes only whether active care concerns exist and their categories, so
serializing historical/resolved incident objects and the complete active-ID
list was projection amplification rather than caregiver-visible behavior.

## Implementation

Migration `006_phase3b_event_query_indexes.sql`:

- aligns `idx_events_home_time` with `(home_id, occurred_at DESC, event_id DESC)`;
- adds `(home_id, event_type, occurred_at DESC, event_id DESC)`;
- adds `(home_id, event_type, received_at DESC, event_id DESC)`.

The resulting representative plans use the matching indexes without temporary
sort/group B-trees. Query ordering and durable canonical history are unchanged.

The PWA Home projection now:

- asks the existing snapshot query to skip its unused active-incident ID list;
- projects distinct active incident kinds in first-seen order;
- does not call `dataclasses.asdict()` for incident history;
- preserves the public snapshot response and all existing care-alert semantics.

The stress runner now emits stage start/completion and 25/50/75/100 percent
loop milestones to stderr. Stdout remains machine-readable JSON. Diagnostic
JSON includes per-stage elapsed milliseconds; time remains diagnostic only and
is not a correctness gate.

## MEDIUM diagnostics

Same host/profile/seed (`MEDIUM`, seed `30401`):

| Diagnostic | Before | After |
|---|---:|---:|
| Unprofiled wall time | 11.93 s | 4.51 s |
| Runner duration | 11.67 s | 4.29 s |
| Profiled total | supplied ~17.45 s | 6.94 s |
| Profiled `pwa_view()` cumulative | supplied 14.22 s | 3.34 s |
| Profiled SQLite `execute()` cumulative | supplied 6.27 s | 1.33 s |
| Profiled `dataclasses.asdict()` cumulative | supplied ~6.08 s | 0.63 s |
| Database bytes | 1,183,744 | 1,818,624 |
| Correctness gate | PASS | PASS |
| Request failures | 0 | 0 |

The database-size increase is the expected index-storage tradeoff and remains
well below the MEDIUM 16 MiB correctness ceiling. Exact time/RSS values remain
host diagnostics, not release limits.

## LARGE diagnostic rerun

The explicit post-change LARGE run passed every correctness check:

| Diagnostic | Recorded baseline | After |
|---|---:|---:|
| Wall time | 461.1 s | 75.14 s |
| Runner duration | 461.1 s baseline | 74.83 s |
| Database bytes | 8,945,664 | 16,424,960 |
| Peak Python RSS | ~92 MB | 90,656,768 B |
| Request failures | 0 | 0 |
| Correctness gate | PASS | PASS |

After-stage diagnostics were 16.55 s accepted ingestion, 0.72 s duplicate
replay, 0.04 s malformed rejection, 30.05 s API/PWA reads, 27.41 s Reports and
0.02 s final verification. LARGE produced 25,000 accepted events, 2,500
duplicates, 250 rejected malformed events and 5,000 notifications. The larger
database is the deliberate index-storage tradeoff and remains below the LARGE
128 MiB correctness ceiling.

## Validation status

- focused Phase 3B tests: PASS (`5/5`);
- focused Phase 1/2/3 regression selection: PASS (`41/41`);
- full Python discovery: PASS (`101/101`);
- JavaScript application tests: PASS (`3/3`, via `make app-test`);
- performance structural budgets plus SMALL stress: PASS;
- MEDIUM stress: PASS;
- LARGE stress diagnostic: PASS;
- `git diff --check`: PASS before documentation update.

Subsequent qualification at checkpoint `fee5854` recorded:

- Playwright cleanup race: fixed;
- `make playwright-gate`: PASS (`86/86`);
- `make release-gate-final`: PASS.

Phase 3B overall remains IN PROGRESS. EXTENDED/endurance remains intentionally
unrun.
