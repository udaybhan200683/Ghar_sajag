# Device Health, Liveness and Offline Detection

Feature documentation type:
ENGINEERING FUNCTIONAL GUIDE

This guide explains stable feature functionality and implementation.

It is NOT the current project-status authority.

For current status: `docs/progress/CURRENT_STATUS_AND_ROADMAP.md`
For implementation/evidence traceability: `docs/validation/MASTER_TRACEABILITY.csv`
For physical qualification: `docs/validation/` and `evidence/hil/runs/`

## 1. Easy mental model

```text
Node periodically reports a health snapshot
                    +
valid authenticated event traffic also proves contact
                    ↓
Hub tracks recent contact separately for each enrolled Node
                    ↓
online/contact and health diagnostics
                    ↓
contact expires → offline/unknown result; new contact → online again
```

These observations answer different questions. **No resident motion does not
mean the Node is offline.** A quiet sensor can still send health, and valid
event traffic can show that a Node is reachable between health reports.

## 2. Terms that must stay separate

| Term | Meaning in this implementation |
|---|---|
| `NodeHealth` | Best-effort engineering snapshot with its own session and health sequence; not a business event and never a durable-ACK transaction. |
| Liveness/contact | Hub's monotonic-time record of last accepted authenticated health or event traffic for a Node. |
| Connectivity/offline | A derived answer from recent contact age (`node_online`) or present routine coverage; it is not a PIR/motion state. |
| Sensing activity | PIR raw transitions, accepted/rejected sensing counters and runtime liveness counters reported for diagnostics. |
| Resident activity | Domain events such as Motion or explicit check-in, consumed by activity/routine rules. Silence may be meaningful for a routine but does not itself indicate Node connectivity. |

The Hub's current `CoverageTracker` is a separate epoch-time coverage view
used by routine evaluation. Target secure runtime liveness uses local
monotonic milliseconds, avoiding fabricated wall-clock contact time.

## 3. NodeHealth contents

`NodeHealthSnapshot` schema 1 carries:

- logical Node ID, authenticated transport session and independent health
  sequence;
- uptime and reset reason;
- current raw PIR level, edge count, accepted/rejected PIR count;
- store-full, dropped-motion and priority-rejection counters;
- sensing/runtime loop liveness counters and last breadcrumb;
- retained count, oldest event sequence and radio in-flight indication;
- transmit attempts, MAC successes/failures, durable/volatile ACKs, retries
  and periodic-backoff entries;
- last error, free heap, minimum free heap and maintenance-active flag.

There is no battery ADC/voltage field in this schema. Event messages have a
battery value field and the wider protocol defines `NodePowerTelemetry`, but
those are separate from NodeHealth and do not prove a physical battery
measurement is wired to this health report. Current target health reports
heap and runtime counters; do not call them a real battery gauge.

## 4. Health transmission and Hub acceptance

```text
C3 NodeRuntime owner
  → build NodeHealthSnapshot (own health sequence)
  → encode NodeHealth frame
  → seal uplink with current per-Node session
  → ESP-NOW callback queue (depth one: newest health wins)
  → Hub chooses active session by source route and opens AEAD
  → verify logical identity, health session and strictly newer health sequence
  → HubRuntime stores per-node snapshot + monotonic last-seen time
```

Node health is sent every 60 seconds in the current target adapter when the
Node is not already waiting on event/health radio work and not in maintenance.
It is best effort: the target health receive queue has depth one and overwrites
older queued snapshots. After pending-image OTA boot, an immediate health send
may be requested for the boot gate. None of this changes event ACK semantics.

## 5. Sequence, session and reset behavior

`HubRuntime::observe_authenticated_health` checks schema and nonzero IDs,
requires the reported logical ID to equal the authenticated Node, requires
snapshot session to equal transport session and current authorized peer
session, and rejects health sequence values less than or equal to the last
accepted health sequence. It also rejects monotonic time moving backwards.
Only accepted health updates the stored snapshot and liveness.

The Node health sequence begins again after target restart, but the target
also rejoins with a strictly newer authenticated runtime session. Hub
`authorize_node` clears old health/contact state when the authorized session
changes, so a sequence from the previous session cannot be interpreted as
fresh health in the new session. Old-session frames also fail runtime AEAD
context/replay checks.

## 6. Event traffic refreshes liveness

After authentication and identity/session admission, a valid Node event
accepted into Hub ingest updates `last_authenticated_contact_ms_`. A health
frame is not required for every contact. This supports Nodes with active
events even if their most recent health report was lost or overwritten.
Contact is recorded from Hub monotonic runtime time, not from a Node wall
clock, and therefore does not invent an absolute timestamp. Current target
adapter passes monotonic `esp_timer` milliseconds for contact.

## 7. Offline detection and thresholds

The shared policy sets expected heartbeat/health cadence to 60 seconds, three
missed intervals, plus a 10-second grace: `offline_after_seconds = 190`.
`HubRuntime::node_online(node, now_monotonic_ms)` returns true while an
authenticated health or admitted event contact is no more than 190 seconds
old. Missing contact, an expired interval, or a time value earlier than the
stored contact returns false. There is no background transition task in this
class; callers query the derived result. Routine `CoverageTracker` similarly
uses the 190-second lease but reports coverage Unknown/Fault, not PIR
activity.

The target sends health at 60-second intervals in the current profile. No
production battery-optimized cadence is implemented here. Any future slower
cadence must be paired with a compatible offline lease; it must not be
presented as current behavior.

## 8. Rejoin and recovery

```text
Node disappears; last contact ages past 190 seconds
   ↓
Hub query reports offline / coverage may become unknown
   ↓
Node returns and proves association in authenticated rejoin
   ↓
Hub commits newer session and replaces runtime context
   ↓
fresh-session health or accepted event updates per-Node contact
   ↓
node_online becomes true; current-epoch health snapshot becomes available
```

Rejoin itself establishes an authorized fresh session; accepted health/event
traffic refreshes liveness. Runtime liveness and health are RAM state, so a
Hub restart begins without recent contact and each Node must rejoin/contact
again.

## 9. Failure matrix

| Failure | Expected behavior | Implementation status | Engineer action |
|---|---|---|---|
| Health packet lost | No contact refresh from that report; later event/health may refresh it | Target best-effort queue/send; physical current-HEAD qualification pending | Check send callback, health sequence gap and later authenticated contact |
| Duplicate/stale health | Reject non-increasing per-Node health sequence | HubRuntime host logic and target route build verified | Compare logical ID, session and last accepted health sequence |
| Node reboot | Old volatile contact ages out; fresh session and new health sequence after rejoin | Rejoin/health owner target-built; physical secure reboot pending | Inspect reset reason, rejoin session and first accepted health log |
| Hub reboot | Contact/health maps reset; registry/journal restore; Node rejoin required | Target startup integration; physical persistence qualification open | Check restore success then per-Node rejoin and first contact |
| Session replacement | Clear old per-Node health/contact authorization; reject old frames | HubRuntime and security owner implementation; target build verified | Compare prior/current session and reauthorization event |
| Event received but health missed | Accepted authenticated event refreshes contact even without health | HubRuntime path implemented; secure physical route pending | Inspect event admission and monotonic contact update |
| Radio outage | Contact expires after 190 seconds absent authenticated traffic | Threshold implemented; current-HEAD physical secure outage not qualified | Check source queue drops, RF/channel, rejoin and last contact age |
| Queue pressure | Health queue depth one overwrites stale snapshot; data/control queues count drops | Target behavior implemented/build evidence; physical load pending | Check callback drop counters, health sequence and queue state |
| Node genuinely offline | Query returns false after lease; no inference about resident motion | `node_online` implemented; product/backend presentation may differ | Check expected-node registration and Hub monotonic now/contact values |

## 10. Multi-Node behavior

Health snapshots and contact timestamps are keyed by logical Node ID only
after the security owner maps the physical Device ID/source route to that
logical ID and active session. Each Node has its own health sequence, session,
snapshot and last-contact timestamp. One noisy Node therefore does not
overwrite another Node's state. Host multi-Node tests cover independent
contexts and authenticated attribution; RF capacity and real ten-Node
behavior require physical qualification.

## 11. Important source files/classes

Paths are relative to `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/`.

- `shared/include/gs/protocol.hpp` — `NodeHealthSnapshot`, `NodeHealthError`, `NodeProtocolPolicy` and 60 s/190 s constants.
- `firmware/common/transport/data_plane_codec.*` — NodeHealth encoding, decoding and schema validation.
- `firmware/node/target/esp32c3/node_runtime_adapter.cpp` — 60 s schedule, snapshot population, secure send and diagnostics.
- `firmware/hub/target/esp32/hub_runtime_adapter.cpp` — secure open, health/event routing and target logs.
- `firmware/hub/runtime/hub_runtime.*` — `observe_authenticated_health`, `node_health`, `node_online`, event contact refresh and per-Node maps.
- `firmware/hub/components/coverage/coverage.*` — epoch-time coverage lease and Unknown/Fault calculation.
- `firmware/hub/components/registry/node_registry.*` — physical/logical identity and session authorization backing health mapping.
- `tests/cpp/multinode_host_validation.cpp` and `tests/cpp/test_main.cpp` — host health/liveness and threshold behavior.

## 12. Verification boundaries

**IMPLEMENTED:** Schema-1 health snapshot, 60-second target cadence, secure
target health frame path, per-Node strict health sequence/session checks,
event-based contact refresh, monotonic 190-second online query, and
epoch-based coverage lease.

**HOST_VERIFIED:** Multi-node host validation exercises authenticated
per-Node health and liveness behavior. Shared protocol tests assert the
60-second cadence, three missed reports plus 10-second grace (190 seconds),
and health codec fields.

**TARGET_BUILD_VERIFIED:** Authenticated Hub/C3 health owner paths and
diagnostic logging compile in ESP-IDF builds. Traceability records a recent
authenticated per-node health/liveness checkpoint as partial; build and host
results do not imply physical secure-path results.

**PHYSICALLY_VERIFIED:** Historical Phase-1 health logs/results use the
legacy qualification path and are not current-HEAD authenticated health
qualification.

**NOT_YET_PHYSICALLY_QUALIFIED:** Current-HEAD authenticated health sequence
rejection, per-Node secure liveness refresh, offline/recovered transitions,
reboot/session replacement and multi-Node radio behavior.

**PLANNED / INCOMPLETE:** Backend/cloud presentation integration where not
wired, physical secure-path qualification and future battery-aware health
cadence policy.

## 13. Diagnostics

Inspect physical Device ID and logical ID mapping, current transport session,
health sequence, uptime/reset reason, last contact monotonic age, whether
contact came from health or event traffic, online query result, rejoin
transition, retained/oldest event counters, sensing/runtime liveness,
free/minimum heap, maintenance and last error. Hub logs include authenticated
NodeHealth logical ID/session/heap/retained count/RSSI and reject
stale/mismatched snapshots. A health sequence is not a timestamp. No
absolute last-contact wall-clock is currently available on this path.

## 14. Known limitations

- Target event receive currently sets `hub_received_at` to zero because no
  trusted wall clock is configured. Liveness uses monotonic Hub time instead.
- Current-HEAD physical authenticated health/liveness qualification remains
  open; historical Phase-1 PASS is not evidence for this path.
- NodeHealth contains no real battery voltage/ADC sample. Battery/power data
  in other protocol structures must be traced to its producer before use.
- Health/contact maps are volatile and reset on Hub restart.
- Backend/cloud offline status presentation is not proven by HubRuntime's
  local `node_online` query.
- Future battery-saving health cadence is planned work, not implemented
  behavior in this target profile.
