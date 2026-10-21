# GS-75 Autonomous Notification Worker — 2026-10-20

## Scope and baseline

Branch `feature/gs75-autonomous-notifications-20261020` starts at canonical
`7e41eb8a606ce5e48534b0114e2d902c26523c28`. The canonical worktree contained
active GS-58 edits and was not modified. The separate worktree passed
`tools/context/ghar_sajag_context_preflight.sh` before code changes.

GS-75 was moved from To Do to In Progress. GS-25 remains Done. This change does
not update shared product decisions, `R1_WORK_STATE.md`, GS-116/130 registries,
Android/PWA sources, Wi-Fi onboarding or firmware.

## Existing versus missing

| Capability | Finding | Reused / change |
|---|---|---|
| Authenticated event commit, EventKey conflict detection and transactional notification effect | Already implemented | Existing `DurableEventCommit`; no ingestion, incident or policy rewrite |
| Durable outbox and stable `outbox_id` | Already implemented, but read-only due listing and non-leased completion | Same outbox; added lease/retry fields and claim/complete operations |
| Primary and delayed backup scheduling | Already implemented in the commit transaction | Preserved due times; store stage for newly written rows and infer legacy stage from existing `notification_jobs` |
| Caregiver notification preferences and Home consent | Existing Home-scoped preference and consent records | Re-read before each send; missing, withdrawn or disabled state denies delivery |
| Persistent concurrent worker, bounded retries and scheduler process | Missing | Added `notification_worker.py` and default-disabled process entry point |
| Real Web Push provider / destination resolution | Not implemented; owned by GS-74 | Injection contract only; no provider, credential or actual send added |

GS-157 voice calling remains separate. No second event queue, identity authority,
preference database, broker or scheduler framework was introduced.

## Implementation

Migration `014_notification_worker_leases.sql` adds retry count, lease token and
generation, lease expiry, attempt/error metadata, provider acceptance time and
notification stage to the existing `durable_notification_outbox`. Existing
outbox IDs, payloads, due times, states and uniqueness remain intact. Legacy
rows keep a null stage; the first claim derives it from the matching existing
`notification_jobs` record, then the current role for rows without an incident
job (such as door quiet notices).

`NotificationWorker` claims a bounded batch. SQLite uses `BEGIN IMMEDIATE`;
PostgreSQL uses row locks with `FOR UPDATE SKIP LOCKED`. A claim increments a
generation and attempt count and assigns a random token and bounded lease. An
expired lease can be reclaimed; stale, expired and replaced lease holders cannot
complete. Completion updates the outbox and existing `notification_jobs` in one
transaction. A retry remains `PENDING` with a future `due_at`; exhaustion and
permanent failure become terminal `FAILED`. Acknowledged/resolved incidents
and changed/withdrawn recipient authority turn unsent jobs into terminal
cancellations; late completion does not overwrite a human state.

Retry delay is exponential from 10 seconds, capped at 900 seconds by default,
with bounded ±20% jitter. Limits, delay, lease, batch and jitter are injectable
or constructor-bounded. A provider must declare a 1–30 second maximum send time;
the lease must exceed that bound by at least five seconds. The approved provider
must enforce the declared network timeout itself. PostgreSQL connection setup
retains the existing bounded connection timeout and verified TLS requirements.

The process polls at a bounded interval, processes only bounded batches, checks
database/provider readiness, and exits cleanly on SIGTERM/SIGINT after the
current bounded batch. It has no in-memory backlog. `python -m
ghar_sajag.notification_worker` returns disabled unless
`GS_NOTIFICATION_WORKER_ENABLED=1`; it also requires existing `DATABASE_URL`
and an explicitly injected `GS_NOTIFICATION_PROVIDER_FACTORY`. Production
activation remains disabled.

## Security and delivery semantics

Immediately before provider I/O the worker re-reads the durable row, event,
Home, incident, membership, role and preference. It requires a non-test event,
active Home consent, active matching PRIMARY/BACKUP membership, stage/role match,
an active incident (or the established door quiet effect), and an explicit
`safety_alerts: true` preference. Missing/corrupt preference or membership data
fails closed. The provider sees only Home/recipient opaque identifiers, event
type, stage and severity; raw sensor payload, location, EventKey and contact
details are not sent. Logs contain no row IDs, recipients, tokens, provider
references or exception text.

`DELIVERED` is the existing outbox name for local completion after provider
acceptance. `provider_accepted_at` and `PROVIDER_ACCEPTED` on
`notification_jobs` record acceptance; neither means the phone displayed the
message, that it was read, or that a person acknowledged it. Human alert state
and notification-job acknowledgement remain separate.

The crash window after a provider accepts but before the local transaction
commits is unavoidable here. The lease eventually expires and the worker retries
the same stable `outbox_id` as provider idempotency key. If a real provider does
not guarantee idempotency for that key, the external effect may be duplicated;
the system makes no exactly-once claim. The provider contract must document its
idempotency behavior before activation.

## Validation

All database tests used disposable temporary SQLite files. PostgreSQL tests used
the fresh, task-specific cluster `/tmp/gs75_notification_pg_20261020` and
database `gs75_worker_final` on port 55439. The existing laptop GS-179 PostgreSQL
cluster was not contacted. Temporary psycopg packages were installed under
`/tmp/gs75_notification_pydeps_20261020`; no repository dependency was changed.

| Command / target | Result |
|---|---|
| `make -C code lab-build` | PASS; host simulator target built for the existing Phase 2B regression; no target firmware build or flash |
| `PYTHONPATH=backend python3 -m unittest tests.python.test_notification_worker tests.python.test_durable_event_commit tests.python.test_database_schema -v` | PASS, 35/35 (19 worker, 7 durable commit, 9 schema/migration) |
| `PYTHONPATH=backend python3 -m unittest tests.python.test_phase2b_notifications -v` | PASS, 8/8 |
| `PYTHONPATH=/tmp/gs75_notification_pydeps_20261020:backend GS75_ISOLATED_TEST_DSN='host=127.0.0.1 port=55439 dbname=gs75_worker_final user=udaybhan' python3 -m unittest tests.integration.test_gs75_notification_worker_postgres -v` | PASS, 1/1; fresh PostgreSQL migration, two-worker `SKIP LOCKED` race and retry persistence after connection reopen |
| `PYTHONPATH=/tmp/gs75_notification_pydeps_20261020:backend:tests/integration:tests/support python3 -m unittest discover -s tests/integration -p 'test_gs179_postgres_security.py' -v` | PASS, 14/14 |
| `PYTHONPATH=backend python3 -m unittest tests.python.test_durable_api -v` | PASS, 3/3 caregiver projection / durable API |
| `python3 -m py_compile ...; git diff --check` | PASS |
| Combined `test_component_gate` + `test_feature_traceability` | 70 passed, 3 failed. `test_component_gate` passed; the traceability suite correctly flags the two new production paths as absent from shared source inventory: `backend/ghar_sajag/notification_worker.py` and `backend/migrations/014_notification_worker_leases.sql`. No shared catalog was edited during the concurrent GS-58 work. |

The worker tests cover committed/duplicate effects, restart/backoff, SQLite and
PostgreSQL competing workers, lease expiry and stale tokens, acceptance/retry/
permanent rejection/timeout/network failure, commit failure, crash after remote
acceptance, stable idempotency key, ACK/resolve races, delayed backup, removed
and wrong-Home caregivers, missing consent/preference, test events, corrupt
payloads, final-attempt crash exhaustion, aggregate-only metrics and disabled
process startup. Test-only fake
provider acceptance is not real push evidence.

## Registry integration requirement

The shared `code/validation/suites.json`,
`docs/validation/SOURCE_FEATURE_INVENTORY.csv` and
`docs/validation/MASTER_TRACEABILITY.csv` were left untouched because the GS-58
session owns concurrent shared-file changes. Before canonical integration, the
owner must:

1. Add `backend/ghar_sajag/notification_worker.py` and
   `backend/migrations/014_notification_worker_leases.sql` to
   `SOURCE_FEATURE_INVENTORY.csv` under a new GS75 notification-worker feature
   row, with the limitation that the real provider is deferred to GS-74.
2. Add a `backend` stage named `gs75-notification-worker` to
   `code/validation/suites.json`, running
   `python3 -m unittest tests.python.test_notification_worker -v`, with inputs
   `backend/ghar_sajag/notification_worker.py`,
   `backend/ghar_sajag/durable_commit.py`,
   `backend/migrations/014_notification_worker_leases.sql`, and
   `tests/python/test_notification_worker.py`; require a nonzero unittest count
   and failure propagation. Include the stage in backend, fast and release
   selection according to GS-116/130 policy.
3. Add a GS75 row to `MASTER_TRACEABILITY.csv` linking that test source, worker
   and migration to backend execution; preserve the provider/physical gap as
   explicit rather than claiming end-to-end push delivery.
4. Register the opt-in PostgreSQL test with a harness that provisions a fresh
   disposable local database; it must reject remote or persistent database
   targets. The checked-in test already requires a local database named with the
   `gs75` prefix.

## Blockers and qualification

- **GS-74 provider dependency:** no real push adapter, destination/token resolver,
  delivery credentials or provider idempotency promise exists in this branch.
  The provider must resolve only a currently authorized destination and enforce
  bounded readiness/send timeouts.
- **Production activation:** disabled until provider approval/configuration,
  deployment topology, database migration and operational monitoring are
  reviewed and separately authorized. No paid service or deployment was changed.
- **Registry merge prerequisite:** the new source and tests need the shared
  GS-116/130 mappings above; the traceability checks currently fail for that
  known integration gap.
- **Physical/commercial:** no real device, phone, push provider, commercial
  delivery or release qualification was executed. Physical and commercial
  notification acceptance remain NOT_RUN.

## Integration handoff

Changed source is limited to `durable_commit.py`, the new worker module and
forward migration, dedicated SQLite/PostgreSQL tests, and this evidence file.
No firmware, Android, PWA, GS-58, GS-157 or shared release files changed. The
canonical owner should first finish the GS-58 checkpoint, then review the
transaction/migration and security code, integrate the shared GS-116/130 rows,
run the registered backend worker stage plus the isolated PostgreSQL test, and
only then merge. No automatic merge is requested.

## 2026-10-21 canonical reconciliation and timing fixes

This section supersedes the earlier registry-integration requirement and
integration handoff above. Those statements describe the original 2026-10-20
branch checkpoint. The GS-75 worktree was reconciled with the then-current
canonical remote `5fd6fe0cb5e161f6e8d8e14e00f2d5f21c20747f` using a normal merge;
merge commit `fbf50fd8f2c2d3714cf5c468baaa7d1140b41aad` has canonical ancestry.
The latest canonical GS-58 and GS-179 changes are present. No canonical files
were edited, and no feature branches or worktrees were created or removed.

Two timing defects were reproduced and corrected in source commit `94b6167`:

- `run_once()` now claims one outbox row at a time immediately before handling
  it, up to the configured batch bound. A slow earlier provider call therefore
  cannot leave later jobs waiting under leases started at the beginning of the
  batch. The worker stops the cycle when its authorization/completion fence is
  lost, so it cannot continue a batch with stale ownership.
- Retry `due_at` is based on the current clock after the provider failure
  returns, then adds the existing bounded retry delay. Retry policy and
  idempotency keys are unchanged.

The shared validation integration is now present: the `gs75-notification-worker`
stage is registered in `code/validation/suites.json`; the worker and migration
are inventoried; `GS75-NOTIFICATION-01` is mapped in
`MASTER_TRACEABILITY.csv`. This stage tests the worker boundary only. The
provider remains injected; no real FCM delivery is claimed.

### Focused validation

- `PYTHONPATH=backend:. python3 -m unittest tests.python.test_notification_worker tests.python.test_phase2b_notifications tests.python.test_durable_event_commit tests.python.test_database_schema tests.python.test_durable_api tests.python.test_p2d_cloud_contract -v` — PASS, 50/50.
- `GS75_ISOLATED_TEST_DSN='host=127.0.0.1 port=35557 dbname=gs75_worker_isolated user=udaybhan' PYTHONPATH='/tmp/gs75_notification_pydeps_20261020:backend:.' python3 -m unittest tests.integration.test_gs75_notification_worker_postgres -v` — PASS, 1/1 against a newly initialized disposable UTF-8 PostgreSQL 18.6 cluster; concurrent workers used `SKIP LOCKED`, and retry state survived connection reopen. The pre-existing GS-179 laptop database was not contacted.
- `PYTHONPATH=backend:. python3 -m unittest tests.python.test_component_gate tests.python.test_feature_traceability -v` — PASS, 73/73, including selection and failure-propagation checks.
- `make feature-coverage-test` — PASS: 223 feature rows, 277 modules, 26 physical cases; mapping tests 22/22.
- `make p2d-cloud-contract-host-test` — PASS; its generated executable was then available to the combined 50-test regression.
- `python3 -m py_compile ...`, `python3 -m json.tool code/validation/suites.json`, and `git diff --check` — PASS.

An initial combined invocation before building the P2D host-contract executable
reported two `FileNotFoundError` setup errors for that absent generated binary.
After `make p2d-cloud-contract-host-test` built it, the combined affected suite
passed 50/50. This was a missing generated test executable, not a product-test
assertion failure. `validation-fast`, `release-gate-final`, firmware builds,
Android builds, physical HIL and live provider delivery were not run.

### Delivery and remaining limits

The worker's SQLite/PostgreSQL persistence, authorization reread, lease fencing,
restart recovery and provider boundary are software-validated. The worker
remains disabled by default. GS-74 still owns Android FCM provider integration
and destination/token resolution; GS-177 owns native registration, permission,
receipt display and phone qualification. Provider idempotency and deployment
activation require their own review. Provider acceptance is not proof of phone
delivery or caregiver acknowledgement. GS-75 remains In Progress, and PR #4
remains open as a draft; no merge or worktree deletion is authorized here.

The root engineering-principles document referenced by the supplied current
policy was not present in this checkout at preflight. This is recorded as a
repository-policy documentation gap; the existing tracked AGENTS instructions
and this task's boundaries were followed, and no AGENTS file was overwritten.
