# Event Delivery, Retry and Recovery

Feature documentation type:
ENGINEERING FUNCTIONAL GUIDE

This guide explains stable feature functionality and implementation.

It is NOT the current project-status authority.

For current status: `docs/progress/CURRENT_STATUS_AND_ROADMAP.md`
For implementation/evidence traceability: `docs/validation/MASTER_TRACEABILITY.csv`
For physical qualification: `docs/validation/` and `evidence/hil/runs/`

## 1. Purpose and mental model

An event is retained until the Hub confirms application-level acceptance. A
radio send callback only says the radio stack accepted a transmission; it
does not prove that the Hub decoded, stored or processed the event.

```text
PIR/activity
   ↓
NodeRuntime creates event
   ↓
event receives stable physical/logical/session/sequence identity
   ↓
retained + pending retry state
   ↓
authenticated transmission
   ↓
Hub identity/session validation and ingest
   ↓
dedupe + journal commit
   ↓
authenticated application ACK
   ↓
Node retires pending and retained event
```

## 2. Event identity

`NodeRuntime::record` allocates an `EventKey` from the Node's logical source
ID, current boot session and monotonically assigned sequence. After the Hub
authenticates the physical Node, it adds the physical Device ID to the key.
The Hub journal's stable string key includes physical and logical identity,
session and sequence. Event identity survives a retry unchanged, including a
retry after reboot. A retry is the same observation; allocating a fresh
sequence would turn a delivery problem into a second logical event.

The boot/runtime session identifies a communication epoch and participates in
the key. The event sequence identifies an event within that epoch. Following
reboot, rejoin creates a newer communication session, while retained events
keep their original event keys. This separation lets the Hub accept the old
event identity inside the newly authenticated transport session and dedupe a
previously committed copy.

## 3. Node event state and capacity

Business events appear in two bounded Node structures: `NodeStore` retains
the event record and `NodeRadio` holds `PendingTx` retry state. In practical
terms:

- **Pending:** queued for transmission or retry; not yet accepted by Hub ACK.
- **Retained:** business event remains in `NodeStore` until durable or
  explicit discard-policy acknowledgement.
- **In-flight:** adapter currently waits for one MAC send result or one
  application ACK. The durable recovery record stores pending retry state,
  not an RF callback in progress; after restart pending items become due.
- **Acknowledged/retired:** a matching accepted ACK removes radio work and
  retained evidence, then target persists the updated recovery snapshot.

Default host `NodeRuntime` capacities are 32 retained and 32 pending; the C3
target uses those defaults. Motion events reserve four radio slots (or one
quarter of smaller queues) for higher-priority event kinds. Record admission
preflights both queues. Full capacity rejects the new event and increments
store/queue/drop or priority-rejection counters; it does not mutate the
existing event into a fresh retry. Storage gap-marker state is retained so a
later recovery can expose loss. A failed persistence write is a target owner
fault and stops further event admission rather than sending an uncommitted
event.

## 4. Send and ACK flow

```text
Node chooses due PendingTx
  → encodes original event key/payload
  → seals under current authenticated uplink session
  → ESP-NOW result schedules retry (MAC success is not an application ACK)
  → Hub opens AEAD and checks routed identity/session
  → bounded ingest queue
  → privacy policy, journal commit/dedupe, reducer
  → Hub seals ACK for exact event key under current downlink session
  → Node authenticates/decodes ACK and matches pending key
  → Node retires event and persists recovery snapshot
```

For a normal event, `AckClass::Durable` means the Hub journal returned
`Stored` after target encrypted-slot commit and readback, or `Duplicate` for
the already known event identity. A duplicate ACK does not reapply reducers.
While privacy mode discards passive activity, the Hub returns
`DiscardedPolicy` without journaling; this is an explicit policy discard, not
a durable event record. `ReceivedVolatile` exists in shared policy but does
not retire business evidence. `Rejected` never retires it.

An ACK proves Hub-side acceptance at that boundary, not cloud/backend commit,
caregiver notification, or resident acknowledgement. Those are different
application actions.

## 5. Retry behavior

`NodeRadio` schedules from the radio-result callback, whether ESP-NOW reports
success or failure, because MAC success does not establish Hub acceptance.
Configured delay bases are 200 ms, 600 ms, 1.8 s, 10 s, then 60 s
periodically, with deterministic per-sequence jitter from 0 to 100 ms. The
last interval repeats indefinitely; retry does not require another PIR edge.
One global opportunity gate and round-robin cursor avoid releasing all
retained packets as one burst. After event ACK, the gate is cleared so the
next pending item can drain immediately. A missing MAC callback times out in
the target adapter and schedules a failed transport result.

An ACK is accepted only after current-session AEAD open, valid ACK decoding,
and a key match in pending state. Wrong event/session IDs cannot retire an
event. Old event keys from a prior boot are valid pending identities after
rejoin, but an old-session encrypted ACK is not: the ACK must be protected in
the current runtime session and name the correct old-or-current event key.
Lost ACK causes same-key retry. The Hub returns duplicate ACK if that event
was already committed.

## 6. Hub ingest, dedupe and journal

The target security owner maps the source MAC to an active Node session, then
opens the authenticated uplink and checks NodeMessage logical identity against
the enrolled record. `HubRuntime` checks physical/logical/session mapping and
submits the event to a bounded ingest queue. Queue pressure rejects without
ACK, leaving the Node to retry.

`run_state_once` commits the event before applying event-derived rules. The
journal indexes `EventKey::str()`: exact duplicate returns `Duplicate`, emits
a durable ACK and skips a second reducer application. New records update the
in-memory journal index only after durable target slot write/readback. Journal
full or storage fault returns rejection, so no durable ACK is sent. The
production Hub path uses 128 append-only persistent slots; there is no
reclamation/compaction path yet.

## 7. Node and Hub outages

These cases have different owners:

- **Hub unavailable:** Node continues its sensing loop and attempts retained
  sends on backoff. Validly admitted new events are retained too, subject to
  local bounded capacity. Rejected due to full queue/store is counted and
  cannot be recovered as if accepted.
- **Events already pending when Hub fails:** same EventKey and event data are
  retried; no new sensor edge is required.
- **Hub returns:** Node security state performs authenticated rejoin and
  installs a fresh session. Pending business events are sealed again under
  the new session, preserving their original event identities.
- **Hub accepted before ACK was lost:** retransmit is deduped by the journal;
  Hub re-ACKs without repeating reducer side effects.

## 8. Restart recovery

```text
Motion detected → Event 1042 created
       ↓
Hub unavailable → Event retained
       ↓
C3 restart → association + encrypted recovery record loaded
       ↓
authenticated rejoin → fresh runtime session
       ↓
same Event 1042 retransmitted under fresh session
       ↓
Hub journal dedupes or stores → current-session ACK
       ↓
Node retires Event 1042 and commits recovery update
```

On C3 target, authenticated association/rejoin completes before recovery
restore and before new event admission. The recovery snapshot stores retained
business events and pending retry metadata. `restore_pending` makes them due
in the new monotonic clock domain while preserving attempt count and event
identity. Runtime AEAD counters/session keys are intentionally regenerated
after rejoin. Hub restart restores the registry and encrypted journal before
authenticated event admission; runtime sessions and per-node liveness are
rebuilt in RAM through rejoin and new traffic. Neither restart path has
current-HEAD physical restart qualification.

## 9. Node recovery persistence

The bounded `GSNR` version-1 snapshot stores generation, Node ID, prior boot
session, gap-marker requirement, and up to 32 pending events with retry
attempt/backoff marker and whether each remains retained. Event fields include
logical event/session/sequence, location, monotonic and epoch-like event
values, uncertainty, battery value, test/sensor type and RSSI. The payload is
AES-256-GCM wrapped; header and Home/Hub/Node identity context are
authenticated. Maximum blob size is 8192 bytes. Target NVS adapter writes one
blob and rereads it after commit.

Target owner persists a newly admitted event before sending it and persists
after ACK retirement; the first transition to a gap marker is also persisted.
Repository generation advances from the current valid record. A failed write
preserves the prior record where the store provides that behavior and target
stops the owner. Corrupt or unreadable records fail restore and stop event
admission; the code does not silently erase them. No wear-level policy,
long-life write endurance or physical power-cut atomicity claim is qualified.
Writes occur on event admission, event retirement and first gap transition,
not on every radio retry.

## 10. Event ordering and time

Sequence/session identity determines duplicate identity and ordering within
one Node event stream; physical identity keeps replacement hardware separate.
It is not absolute time. `monotonic_ms` is elapsed Node time and restarts with
the device. `occurred_at` is a Node-origin epoch-like field with uncertainty;
current C3 production adapter supplies zero because it lacks a trusted wall
clock. The authenticated Hub adapter also currently sets `hub_received_at`
to zero (“No trusted clock yet”). A host/runtime caller may supply a receive
time, but the current target path must not be described as reliable UTC
stamping. Do not sort solely by wall-clock fields when they are untrusted.

## 11. Failure and recovery matrix

| FAILURE | EXPECTED PRODUCT BEHAVIOR | IMPLEMENTATION STATUS | ENGINEER ACTION |
|---|---|---|---|
| ACK lost | Retry same identity; Hub dedupes and ACKs again | Host modeled; target secure path built; physical current-HEAD pending | Compare event key, Hub journal key and ACK send log |
| Event duplicated | Exact journal key yields duplicate ACK without reducer replay | Host and persistent-journal logic verified; physical secure path pending | Verify physical Device ID/logical/session/sequence composition |
| Hub offline | Retain accepted local event and periodic retry; capacity remains bounded | Retry logic current; physical outage under secure route unqualified | Check retry/backoff, retained count and queue/store refusal counters |
| C3 restart | Load association/recovery, rejoin fresh session, resend same event IDs | Host recovery plus target wiring/build; physical restart pending | Check reset reason, recovery generation, prior session and rejoin |
| Hub restart | Restore registry/journal; nodes rejoin; pending event can be duplicate-ACKed | Host restore and target build; physical restart/power-cut pending | Check startup restore logs, journal count, Node new session |
| Both restart | Restore Hub and Node records, rejoin then resume retries | Host model; target build; physical combined restart pending | Preserve both logs/records and compare old event IDs/new sessions |
| Full queue/store | Reject new admission and expose counters/gap behavior; do not overwrite old events | Host boundary validation and target implementation; physical load pending | Inspect `tx_queue_full`, `store_full`, priority/drop and gap marker |
| Persistence failure | Stop Node owner before exposing uncommitted event; retirement failure stops owner | Host fault coverage and target code/build; physical fault injection pending | Inspect NVS result; preserve prior snapshot for analysis |
| Corrupt recovery record | Fail closed; no silent new event stream over lost pending state | Host corruption checks and target fail-closed wiring/build | Preserve blob and wrapping-key context; service recovery required |
| Rejoin failure | No application traffic until authenticated fresh session | Protocol/host verified and target-built; physical rejoin pending | Inspect association, boot session, Hub session floor and transcript result |
| Stale session | Reject rejoin/frame; do not accept old ciphertext | Host verified; target-build integration; physical replay pending | Compare session progression and current frame owner |
| Wrong ACK | No matching pending EventKey means no retirement | Host coverage; target authenticated ACK route built | Check ACK physical/logical/event/session fields and AEAD counter |

## 12. Important source files/classes

Paths are relative to `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/`.

- `firmware/node/runtime/node_runtime.*` — `NodeRuntime::record`, ACK and recovery snapshot/restore.
- `firmware/node/components/storage/node_store.*` — bounded retained business events and gap marker.
- `firmware/node/components/radio/node_radio.*` — `PendingTx`, retry schedule, queue admission and reboot deadline reset.
- `firmware/node/components/storage/node_recovery_persistence.*` — encrypted `GSNR` snapshot and generation.
- `firmware/node/target/esp32c3/node_runtime_adapter.cpp` — sensing, persist-before-send, ACK retirement, health and radio queue.
- `firmware/node/target/esp32c3/node_security_link.*` — rejoin and recovery restore/persist boundary.
- `firmware/hub/components/ingest/ingest.*` — authorized bounded ingest queue.
- `firmware/hub/runtime/hub_runtime.*` — authenticated admission, journal commit/dedupe, reducer and ACK result.
- `firmware/hub/components/storage/journal.*` and `firmware/hub/target/esp32/nvs_journal_slot_store.*` — 128-slot encrypted journal.
- `firmware/hub/target/esp32/hub_runtime_adapter.cpp` and `hub_security_link.*` — secure frame admission, per-Node session and ACK transmission.

## 13. Verification boundaries

**IMPLEMENTED:** Node event identity, bounded retained/pending queues, retry,
authenticated target frame routing, journal dedupe, encrypted Node recovery
record, Hub encrypted journal and replay of journal-derived basic state.

**HOST_VERIFIED:** `tests/cpp/node_runtime_recovery_validation.cpp`,
`node_recovery_persistence_validation.cpp`,
`hub_journal_persistence_validation.cpp`, and
`multinode_host_validation.cpp` cover retry identity, restart recovery,
duplicates, stale/wrong ACK, corruption, storage failures, capacity and
multi-node attribution as captured in validation traceability.

**TARGET_BUILD_VERIFIED:** C3 persistence before send/after retirement and
Hub security/journal owner paths are integrated and target-build verified per
traceability. Build is not a physical delivery result.

**PHYSICALLY_VERIFIED:** Historical Phase-1 event/radio/restart evidence
belongs to its recorded commit/profile. It is not current-HEAD secure event
delivery qualification.

**NOT_YET_PHYSICALLY_QUALIFIED:** Current-HEAD authenticated event/ACK,
restart with encrypted pending records, real power interruption, write
failure, full journal and secure outage/rejoin behavior.

**PLANNED / INCOMPLETE:** Long-term flash wear/reclamation, power-cut
atomicity, trusted event wall clock and production recovery/service UX.

## 14. Diagnostics

Inspect physical Device ID, logical source ID, event session and sequence,
retained count/oldest sequence, pending/in-flight event, retry attempt,
MAC result, application ACK class and `retired` result, Node recovery
generation, gap/store/queue counters, Hub journal size/contains result,
Hub ACK reason (`journal_committed` or `already_committed`), reset reason,
rejoin session and current security owner. MAC success alone is not delivery.

## 15. Known limitations

- Hub journal is append-only, limited to 128 target slots, and currently has
  no safe reclamation/compaction path. ACKed records still consume slots.
- Node target recovery writes and encryption are integrated, but production
  wrapping-key protection, flash wear and physical power-cut durability are
  not qualified.
- The current target path has no trusted absolute event/receive clock.
- Queue-full and storage-fault behavior is fail-closed/counted, but physical
  fault-injection qualification remains open.
- Backend application commit and caregiver delivery are separate from the
  Node-to-Hub durable ACK boundary.
