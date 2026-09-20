# Ghar Sajag P0 node-to-hub protocol

## Canonical message

The physical transport is an adapter. ESP-NOW may be used first, but rules never consume GPIO/RF frames directly. A node converts sensor input into the versioned `node.schema.json` message and the hub converts that message into `gs::DomainEvent`.

Canonical fields: `node_id`, `session_id`, `sequence_number`, `sensor_type`, `event_type`, `location`, `monotonic_ms`, `occurred_at`, `time_uncertainty_ms`, `battery_mv`, `rssi_dbm`, optional `is_test`, and optional typed `payload`.

`node_id + session_id + sequence_number` is the immutable event identity. The C++ internal `EventKey.source_id` is the same value as wire `node_id`; `EventKey.sequence` maps to `sequence_number`.

## Session and sequence rules

- `sequence_number` increases monotonically inside one authenticated session.
- Deep-sleep wake retains session and sequence state.
- A true cold boot/power loss creates a new random `session_id`; old retained events keep their old identity.
- Sequence wrap is not supported. Start a new authenticated session before wrap.

## Acknowledgement

The hub returns `node_ack.schema.json` using the same identity tuple.

- `DURABLE`: hub journal committed the business event (or already contained the same event). The node may retire it.
- `RECEIVED_VOLATILE`: transport/callback received it but durable commit is not proven. Business events stay retained.
- `DISCARDED_POLICY`: authenticated event was intentionally discarded by policy (for example consent/privacy gating). The node may retire it.
- `REJECTED`: invalid identity/session/schema/capacity. The node keeps the event and follows bounded retry/recovery policy.

Transport-layer success alone is never a durable ACK.

## Retry and duplicate suppression

Retry schedule is `200 ms, 600 ms, 1800 ms, 10000 ms, 60000 ms`, then capped at a 60-second periodic probe, with deterministic 0–100 ms jitter. A global opportunity gate and round-robin selection bound aggregate offline radio work; Durable ACK releases the gate to drain recovered traffic. Retries reuse the same event identity and payload. They never mint a new sequence number and do not require a new sensor event.

The hub journal suppresses duplicates by `(node_id, session_id, sequence_number)`. Backend `event_id` is derived from that same identity, so replay after WAN loss remains idempotent end-to-end.

## Heartbeat and offline detection

- Default heartbeat: **60 s**.
- A node is considered offline/coverage-unknown after **190 s** without a valid node contact: three missed 60 s heartbeats plus 10 s grace.
- Heartbeats may be coalesced and need not use durable node storage; business events must be retained before transmission.
- Offline status is a device/coverage state, not evidence of resident inactivity.

These constants live in `shared/include/gs/protocol.hpp` and are reused by node retry and hub coverage code to prevent configuration drift.

## Bounded offline admission

The HW-M1.4 node keeps at most 32 retained/retry entries. Repetitive Motion
events may occupy 28; four slots are reserved for non-motion evidence. When a
class allocation is full, the newest event is rejected nonblockingly and a
cumulative diagnostic counter advances. Sequence allocation occurs before
admission, so such rejection is visible as an intentional sequence gap. Store
and retry admission are atomic: no record may be retained without retry state.
No event is silently overwritten or coalesced in this revision.

## Engineering health frame

`NodeHealthSnapshot` uses a separate `NodeHealth` frame type and independent
health sequence. It is emitted best-effort every 60 seconds, is never retained,
does not consume business EventKey space, and receives no Durable ACK. The Hub
keeps at most the latest queued snapshot and logs its node counters plus receive
RSSI/channel. Diagnostic loss is harmless and cannot fill the business store.

## Code binding

`shared/include/gs/protocol.hpp` is the C++ semantic binding for this contract:

- `NodeMessage` mirrors the canonical node message independent of ESP-NOW/GPIO.
- `node_message_from_event()` and `domain_event_from_node_message()` are the hardware/domain boundary.
- `NodeAckMessage` + `make_node_ack()` preserve the same event identity in acknowledgements.
- `NodeRuntime::next_message()` is what a future ESP-NOW adapter serializes.
- `HubRuntime::radio_message_callback()` validates/decodes that message and feeds the same `DomainEvent`
  path used by host simulation.

Reference JSON payloads live under `contracts/examples/`; they are interoperability fixtures, not a mandate
that the final RF frame be JSON.

## Rule/config relationship

The node protocol carries observations, not business decisions. Quiet hours, missing-morning windows,
door-open timeout and daytime-inactivity thresholds are hub configuration. `config.schema.json` contains an
optional `activity_rules` object so the policy can be configured/versioned without changing sensor firmware.

### RSSI ownership note

For ESP-NOW/802.11 receive paths, the most useful `rssi_dbm` is **hub-observed receive metadata**. The node
must not be treated as authoritative for the RSSI of the packet it is currently transmitting. The canonical
normalized message includes `rssi_dbm` because the hub/rule/health pipeline needs it; the physical RF adapter
may append/overwrite that field from its receive metadata after decoding the authenticated node frame.
