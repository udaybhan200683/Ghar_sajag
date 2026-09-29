# Ghar Sajag P0 persistent data model — v1.5.4

The host simulator intentionally continues to use `InMemoryStore` for deterministic, fast scenario tests.
`backend/migrations/001_p0_core.sql` is the concrete persistent relational contract for the pilot backend.
A production PostgreSQL implementation should preserve these identities, keys, relationships and state
semantics while strengthening JSON/time types (`jsonb`, `timestamptz`, etc.).

| Table | Purpose |
|---|---|
| `households` | Home identity, timezone/language, operating mode and consent state |
| `rooms` | Stable room/location catalogue per household |
| `caregivers` + `household_caregivers` | Family/caregiver identity, role and escalation ordering |
| `hubs` | Hub firmware/config/freshness, internet state, reset reason and diagnostic code |
| `nodes` | Node placement, capability, hub binding, firmware/config, freshness, RSSI/battery and error state |
| `events` | Immutable generic events using `(source_id, session_id, sequence_number)` as the duplicate key |
| `routines` | Versioned morning, quiet-hours, daytime-inactivity and door-open policies |
| `routine_windows` | Durable per-window state/evidence so reboot does not restart or duplicate a routine decision |
| `alerts` | Missing-routine, unexpected-door, inactivity, door-left-open and contact-request workflows |
| `acknowledgements` | Human claim/ack/contact/resolve/handoff audit trail |
| `notification_jobs` | Primary/backup routing, attempts, provider acceptance and cancellation |
| `battery_history` | Node battery samples over time |
| `device_health_history` | Hub/node status, error-code, RSSI, battery and temperature diagnostic history |
| `configurations` | Versioned desired/applied household configuration |
| `audit_log` | Security/operations audit trail for device, family/caregiver, resident and support actions |

## Frozen identity rules

- Every event has a stable `source_id + session_id + sequence_number` identity. For a node, `source_id` is
  its `node_id`; hub/system producers use their own stable source identity.
- `events` are append-only evidence. A later correction or recovery does not overwrite historical evidence.
- `alerts.stable_key` is unique per household so retries/replays cannot create duplicate workflows.
- `routine_windows.window_id` is stable and persisted so a reboot at a deadline can resume the same decision.
- Notification jobs have an idempotency key; provider acceptance is not the same as human acknowledgement.

## Separation of concerns

- Device reachability/health is stored separately from resident activity. An offline node cannot become a
  resident-inactivity event.
- Current battery/RSSI lives on `nodes`; historical measurements live in time-series tables.
- Configuration is versioned. Desired and applied versions are explicit; stale configuration is not silently
  accepted.
- The same household relationship model supports primary/backup caregivers and ordinary authorised family
  members; a separate family database is not required.

## Persistence boundary

This schema closes the **data-model/design** work. It does not claim that the current host simulator has been
converted from `InMemoryStore` to PostgreSQL/SQLite persistence. That adapter is a deployment/integration task;
the schema and integrity tests are designed so doing it later does not require changing the domain model.
# Phase 1 application persistence

Migration `003_phase1_application.sql` extends the existing SQLite schema with `family_members`, `device_registry` and `application_policy`. `schema_migrations` tracks applied files and bootstrap uses `INSERT OR IGNORE`, so saved household and device state survive lab restart. `FoundationService` owns this store for Home Details, family roles, the single application device registry, health snapshots/history and versioned policy. `registered=0` is a tombstone: device/event/health history is retained. The simulator still holds event/incident runtime state in memory; physical flash recovery and production database deployment are separate pending gates.

## Phase 3B durable-history query indexes

Migration `006_phase3b_event_query_indexes.sql` aligns the SQLite event indexes
with the bounded read models: household chronology uses
`(home_id, occurred_at, canonical_event_id)`, event-kind chronology adds
`event_type`, and latest receipt queries use
`(home_id, event_type, received_at, canonical_event_id)`.
Representative query plans avoid temporary sort/group B-trees while preserving
canonical event rows, ordering and report windows.

Migration `007_phase3b_household_event_identity.sql` makes the API CloudEvent
identity explicitly unique on `(home_id,canonical_event_id)`. The legacy
`events.event_id` remains an opaque relational key for compatibility with
existing foreign keys. This permits two households to use the same canonical
device event ID without replacement or duplicate misclassification.

## Phase 3B report read model

Reports remain reproducible projections over canonical `events`; no report
cache or second history store was added. The SQLite adapter uses the existing
Phase 3B indexes to aggregate summary/trend facts inside the exact
household-local bucket boundaries, fetch grouped motion timestamps for
timezone-aware night classification, aggregate bounded room activity, and
materialize only the six newest reportable highlights. The generic in-memory
mapping path remains the semantic reference/fallback. SQL aggregate operations
may use bounded temporary grouping B-trees; full report history is no longer
deserialized into Python objects for every request.

## Durable Hub event commit contract

Migration `008_durable_event_commit.sql` adds an immutable EventKey receipt and
notification outbox to the existing `events`, `alerts`, and `notification_jobs`
tables. `DurableEventCommit` uses one file-backed SQLite connection with foreign
keys and FULL synchronous writes. Its caller must start outside a transaction.
It starts `BEGIN IMMEDIATE`, checks the exact identity, inserts the event and
applicable incident and notification work, then commits before returning
`status: "COMMITTED"`. A database error rolls back the whole operation.

The canonical identity is `(home_id, physical_device_id, logical_node_id,
origin_session_id, event_sequence)`. The serialized event ID uses the same
length-prefixed physical/logical ID form as the Hub `EventKey::str()`. Origin
session and sequence come from the event; the current radio transport session
must never replace them. The SHA-256 comparison covers event type, source and
Hub timestamps, location, uncertainty, test flag, and a sorted canonical JSON
payload. Backend receipt time is deliberately excluded, so a lost HTTP response
can be retried later. The identity columns are unique in SQLite. An identical
retry returns the existing committed result without writing; a changed payload
returns a conflict without changing the original event.

The configured durable event API responds with `201` and
`{"event_key": ..., "status": "COMMITTED", "duplicate": false}` for first
commit, `200` with `duplicate: true` for an exact retry, and `409` for a
conflicting retry. Trusted middleware must set the internal WSGI
`gs.verified_hub` field, and an injected authorizer must bind that identity,
the home, and EventKey. A raw `X-Actor-Id` header is not Hub authentication.
Without a configured durable store the structured EventKey
request fails closed. The old local simulator API returns `DURABLE_MODEL`; it
does not establish backend business commitment.

Incident creation and primary/backup `notification_jobs` are in the same
transaction as the event and outbox rows. Quiet-door notices receive a pending
outbox row. No external provider call occurs in that transaction. A sender
reads `due_outbox`, supplies `outbox_id` as the provider idempotency key, and
marks delivery only after provider acceptance. A sender crash may retry a
provider request; provider-side idempotency is therefore required for
exactly-once external delivery. `COMMITTED` proves durable enqueue, not phone
delivery or human acknowledgement.

This SQLite contract does not configure a production Hub HTTP client, TLS
identity, or a production PostgreSQL deployment. A production adapter must
preserve the same transaction and uniqueness rules before the Hub may treat an
HTTP response as `BACKEND_COMMIT_ACK`.
