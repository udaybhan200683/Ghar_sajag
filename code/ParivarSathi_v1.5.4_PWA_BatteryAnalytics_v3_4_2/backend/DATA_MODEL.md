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
`(home_id, occurred_at, event_id)`, event-kind chronology adds `event_type`, and
latest receipt queries use `(home_id, event_type, received_at, event_id)`.
Representative query plans avoid temporary sort/group B-trees while preserving
canonical event rows, ordering and report windows.
