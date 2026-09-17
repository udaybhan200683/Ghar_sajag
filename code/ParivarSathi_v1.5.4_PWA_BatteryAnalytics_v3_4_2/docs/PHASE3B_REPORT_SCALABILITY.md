# Phase 3B Reports Scalability

Status: **IMPLEMENTED / HOST VALIDATED / MANUAL QUALIFICATION PENDING**

Phase 3B remains IN PROGRESS. The previous qualified Phase 3B scale/read-path
checkpoint remains `fee5854`; this uncommitted work does not replace it. Phase
3A remains COMPLETE / QUALIFIED at permanent anchor `4dcaf99`.

## Root cause

`QueryService.report()` requested every reportable event in the selected
Today/Week/Month window through `SQLiteEventMap.home_events()`. Each repeated
report request selected full SQLite rows, parsed every `payload_json`, built a
`CloudEvent` for every row, filtered in Python, and traversed the full result
again for summary, bucket, room, night-activity, and highlight projections.

The range query already used `idx_events_home_time`; a missing basic range
index was not the cause. The LARGE stress harness intentionally requests 50
unchanged reports, so the full materialization cost was repeated 50 times. No
cache was added because correct invalidation across durable event writes,
timezone/policy changes, and process boundaries would need a separate contract.

## Profiling and query-plan evidence

Same-host MEDIUM diagnostics before the change:

- unprofiled report stage: 675.680 ms for 12 report requests;
- cProfile report stage: 1.234 s;
- cProfile `QueryService.report()`: 1.222 s cumulative;
- 60,000 `_count_report_event()` calls and 30,000 reportability checks;
- the full run performed 52,663 `_row_to_event()` conversions, including
  repeated report-window materialization.

After the change, the same cProfile workload recorded:

- report stage: 115.302 ms;
- `QueryService.report()`: 0.109 s cumulative;
- report aggregate query: 0.046 s cumulative;
- room aggregate query: 0.042 s cumulative;
- motion-time query: 0.004 s cumulative;
- bounded highlight query: 0.003 s cumulative;
- 120 `_count_report_event()` calls;
- report history is no longer converted into `CloudEvent` objects; only the
  six returned highlights are materialized per report.

Representative post-change `EXPLAIN QUERY PLAN` results:

- summary/trend aggregation searches `idx_events_home_type_time` for the
  household, event type, and time range, then uses a bounded aggregate B-tree;
- grouped motion timestamps search `idx_events_home_type_time`;
- room aggregation searches the existing event-type/time indexes;
- the six-row highlight query searches `idx_events_home_time` in report order.

No additional index was justified. The existing Phase 3B indexes provide the
needed range/order access; the remaining temporary B-trees perform the intended
bounded SQL aggregation instead of sorting or materializing report history in
Python.

## Implementation

The durable SQLite event map now provides report-specific reads for:

- SQL summary/trend grouping by the exact household-local bucket boundaries
  calculated by `QueryService`;
- grouped motion timestamps for existing timezone-aware night classification;
- bounded room-activity totals with deterministic first-event tie ordering;
- the newest six reportable highlights only.

The in-memory mapping path remains as the semantic reference/fallback. No API
schema, report period, cache, migration, or product behavior changed. Stress
JSON now includes diagnostic-only cumulative Today/Week/Month durations while
preserving the existing stage progress and machine-readable stdout contract.

## Semantic checks

Automated optimized-versus-reference payload comparison covers Today, Week,
and calendar Month and confirms identical output for:

- household timezone and inclusive-start/exclusive-end windows;
- test-event exclusion;
- care versus maintenance/reportable-event filtering;
- coverage reason filtering and unexpected-door concerns;
- timezone-aware night motion;
- removed-device-compatible location history;
- deterministic trend/highlight ordering;
- merged and bounded room activity;
- bounded highlights and current response schema.

Existing Phase 2A report tests continue to cover explicit no-data behavior,
invalid requests, duplicate/replay handling, restart durability, removed-device
history, and persisted timezone changes.

## Timing diagnostics

MEDIUM (`2,500` accepted events, 12 report requests, seed `30401`):

| Diagnostic | Before | After |
|---|---:|---:|
| Report stage | 675.680 ms | 106.244 ms |
| Correctness gate | PASS | PASS |
| Request failures | 0 | 0 |

The required `make stress-test` rerun recorded 112.877 ms for the report stage;
Today/Week/Month cumulative diagnostics were 37.747/36.264/37.584 ms.

LARGE (`25,000` accepted events, 50 report requests, seed `30401`):

| Diagnostic | Qualified `fee5854` baseline | Current host run |
|---|---:|---:|
| Total duration | ~72.2 s | 52.290 s |
| Report stage | ~27.3 s | 5.320 s |
| Request failures | 0 | 0 |
| Database bytes | ~16.4 MB | 16,424,960 B |
| Correctness gate | PASS | PASS |

Current LARGE cumulative period diagnostics were 1.763 s Today, 1.873 s Week,
and 1.679 s Month. Timings remain host diagnostics, not correctness limits.

## Validation

- focused report/Phase 2/Phase 3 regressions: PASS (`21/21`);
- full `make python-test`: PASS (`105/105`);
- `make app-test`: PASS (`3/3`);
- `make performance-test`: PASS, including deterministic profile and SMALL;
- `make stress-test`: PASS (MEDIUM);
- explicit LARGE: PASS;
- EXTENDED/endurance: not run.

Manual/browser qualification remains pending. Remaining Phase 3B scope is
controlled concurrent API load, household isolation, notification-provider
storm qualification, and restart/recovery; EXTENDED/endurance also remains
pending.
