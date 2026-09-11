# Ghar Sajag v1.5.3 — P0 architecture preparation

This patch builds on v1.5.1 without changing the caregiver/family behavior fixed there.

## 1. Hardware-independent rule engine

The shared S02 rule core consumes `DomainEvent` and `RuleEvaluationContext`, never GPIO or RF frames. Hardware adapters only translate physical observations into the generic event. Included policies:

- morning expected-activity deadline → missing-morning decision, with coverage/time gating;
- door opening during configured quiet hours → unexpected-door signal;
- door left open beyond configured timeout → concern signal;
- later door close → resolution signal retaining open duration;
- no activity for configured daytime interval → check-in/concern signal;
- explicit monitor-start anchor handles the case where no activity occurs at all;
- Away/coverage-unknown/untrusted-time contexts suppress inappropriate inactivity conclusions.

## 2. Node ↔ hub protocol

Canonical message: `schema`, `node_id`, `session_id`, `sequence_number`, `sensor_type`, `event_type`, `location`, `monotonic_ms`, `occurred_at`, `time_uncertainty_ms`, `battery_mv`, `rssi_dbm`, `is_test`, bounded payload.

Frozen transport semantics:

- event identity: `(node_id, session_id, sequence_number)`;
- heartbeat: 60 s;
- offline: 190 s without valid contact;
- retry: 200 ms → 600 ms → 1800 ms → 10000 ms, then capped at 10 s, with bounded deterministic jitter;
- only `DURABLE` or explicit `DISCARDED_POLICY` may retire a business event; transport/volatile receipt cannot;
- hub journal suppresses duplicates by event identity; retries preserve the same identity.

The future ESP-NOW implementation only needs to encode/decode `NodeMessage` and `NodeAckMessage`.

## 3. Database/data model

The relational contract now contains household, rooms, family/caregiver relationships, hub, nodes, immutable events, routines, persisted routine windows, alerts, acknowledgements, notification jobs, battery history, device-health history, configurations and audit log.

The host lab remains in memory for deterministic testing; switching the repository adapter to SQLite/PostgreSQL is separate deployment work, not a domain redesign.
