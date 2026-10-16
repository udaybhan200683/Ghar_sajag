# Device Health, Liveness and Offline Detection

## Current GS-40 configuration (GS-D031)

The GS-40 candidate uses 300 s / derived 910 s by default, the same day/night
algorithm, authenticated contact suppression and optional existing event power
telemetry. Canonical JSON, strict validator, embedded typed C3/S3 startup policy,
trusted per-device legacy/configured profile map and backend/PWA lease consumers
are described in the [configuration guide](../../code/config/README.md).
Prior 60/190 and BAT-C5 120/310 default statements below describe historical
profiles; GS-112/150 evidence remains history, not GS-40 validation. GS-150
receive, sleep, GPIO and recovery contracts are preserved. A missing deployment
profile is unknown. Hub cloud freshness retains its separate 190 s lease.
Per-device current coverage uses its selected lease only with trusted received
time; target epoch and production cloud-path limitations remain explicit.
Full real-target acceptance and physical power results are not claimed.

The backend Foundation consumer now discards explicit online observations whose
received-contact timestamp is duplicate/older than its last accepted contact or
already outside the selected lease. Cached ACTIVE telemetry cannot resurrect an
expired device or clear newer DEGRADED telemetry. A newer still-fresh contact
recovers availability; the configured Node lease and separate Hub 190 s lease
remain unchanged. This is a consumer correctness guard, not a production Hub
authenticator or a live WAN root-cause detector. See the
[GS-130 focused regression evidence](../exec-plans/evidence/GS130_RISK_REGRESSION_20261014.md).


Feature documentation type:
ENGINEERING FUNCTIONAL GUIDE

This guide explains stable feature functionality and implementation.

It is NOT the current project-status authority.

For current status: [R1 work state](../product/R1_WORK_STATE.md)
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

For the configured GS-40 profile, standalone NodeHealth is due every 300 seconds
unless a newer authenticated application contact has already refreshed the
cadence. Existing explicit legacy profiles remain 60/190 and 120/310. Sending
is best effort: the target health receive queue has depth one and overwrites
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

For the configured GS-40 profile the lease is derived as
`3 * 300 + 10 = 910` seconds. HubRuntime remains online through exactly 910
seconds and expires strictly after 910 seconds. A trusted legacy profile uses
its own 190- or 310-second lease; missing or untrusted identity/profile is
UNKNOWN. Event contact refreshes liveness only after authenticated application
admission; MAC send success alone does not.

The local Hub lease and the 190-second Hub/cloud freshness lease answer
different questions. A silent Node with a reachable Hub can become OFFLINE,
with motion-monitoring coverage UNKNOWN. If Hub/cloud observation is missing
or stale, caregiver-facing status is UNKNOWN because the source cannot confirm
current coverage. None of these states describe resident activity.

## 8. Rejoin and recovery

```text
Node disappears; last authenticated contact ages past its trusted profile lease
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
| Radio outage | Contact expires strictly after the trusted profile lease (910 s configured; 190/310 s legacy) | Threshold implemented; current-HEAD physical secure outage not qualified | Check source queue drops, RF/channel, rejoin and last contact age |
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

Paths are relative to `code/`.

- `firmware/common/shared/include/gs/protocol.hpp` — `NodeHealthSnapshot`, `NodeHealthError` and shared policy definitions.
- `firmware/common/transport/data_plane_codec.*` — NodeHealth encoding, decoding and schema validation.
- `firmware/node/target/esp32c3/node_runtime_adapter.cpp` — configured schedule, snapshot population, secure send and diagnostics.
- `firmware/hub/target/esp32/hub_runtime_adapter.cpp` — secure open, health/event routing and target logs.
- `firmware/hub/runtime/hub_runtime.*` — `observe_authenticated_health`, `node_health`, `node_online`, event contact refresh and per-Node maps.
- `firmware/hub/event_processing/coverage/coverage.*` — epoch-time coverage lease and Unknown/Fault calculation.
- `firmware/hub/commissioning/registry/node_registry.*` — physical/logical identity and session authorization backing health mapping.
- `tests/cpp/multinode_host_validation.cpp` and `tests/cpp/test_main.cpp` — host health/liveness and threshold behavior.

## 12. Verification boundaries

**IMPLEMENTED:** Schema-1 health snapshot, configured 300/910 and trusted
legacy profiles, secure target health frame path, per-Node strict health
sequence/session checks, authenticated event-based contact refresh, and
monotonic Hub liveness queries.

**HOST_VERIFIED:** Multi-node host validation exercises authenticated
per-Node health and liveness behavior. GS-40 tests assert six 300-second quiet
opportunities, 910-second strict expiry and mixed 60/190 and 120/310 legacy
profiles. Host evidence does not establish physical delivery or caregiver cloud
visibility.

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


## GS-40 approved policy — software implemented, real-target acceptance open

GS-D031 supersedes this guide's historical 60/190 default with 300/910.
The actual preceding BAT-C5 production profile was 120/310. Legacy deployments
retain explicit profiles; existing health schema alone cannot identify them.
Only heartbeat interval is adjustable, with offline timeout derived 3 × interval
+ 10. Hub cloud lease and resident inactivity remain distinct. Firmware applies
validated embedded configuration at startup. Physical acceptance is pending.

### Production observation gap confirmed — 2026-10-16

The Foundation/backend/PWA behavior described by the host suites does not
establish a production S3 NodeHealth publisher or caregiver read path. The S3
runtime authenticates NodeHealth into volatile HubRuntime lease state and
local logs. Its target `app_main.cpp` does not instantiate the CloudSync worker;
the existing worker synchronizes durable events only. The local backend adapter
does not authenticate Hub requests, and the caregiver snapshot does not project
per-Node health. GS-109 owns Hub identity/verifier decisions; GS-148 owns the
durable CloudSync/backend integration. GS-40 must not add a parallel
credential, event commit, or trust contract. Caregiver visibility remains
blocked until those owners expose the trusted source-to-snapshot path and it
passes a real contract test. See the
[GS-40 real-target readiness evidence](../exec-plans/evidence/GS40_REAL_TARGET_READINESS_20261016.md).

### Required additive CloudSync-to-caregiver contract

GS-40's existing policy requires the current GS-68/GS-148 path to carry only
Hub-accepted authenticated Node application contact and its trusted per-Node
profile. The status projection must bind the Hub, Home and current ownership
epoch from GS-109, retain Node identity/session/contact sequence, and preserve
Hub receive time separately from backend receive and caregiver snapshot time.
No Node self-asserted profile, MAC-only success, synthetic event/EventKey, or
durable event ACK may substitute for that status evidence. The backend/PWA
must show Node ONLINE/OFFLINE/UNKNOWN separately from coverage COVERED/UNKNOWN
and resident activity; a silent Node becomes OFFLINE only after its profile
lease (strictly after 910 s for configured 300 s) while coverage becomes
UNKNOWN. Missing/stale Hub, Internet, backend or PWA source means UNKNOWN.
The Hub must publish an OFFLINE state after lease expiry without waiting for
another NodeHealth packet, using the existing trusted CloudSync architecture.
Event durability, replay, and ACK/retirement remain unchanged.

No configurable caregiver sensor-offline notification has been identified in
the current code or Jira search. Existing notification code schedules incident
and door notices and daily summaries; it is not a sensor-coverage alert
preference or delivery contract. If product wants a push/SMS alert in addition
to visible PWA status, define it as a separate linked GS-40/GS-148 requirement
(recipients, delay, quiet hours, deduplication and recovery/clear behavior) and
obtain product approval before implementation. GS-40's current visibility
acceptance does not itself promise a notification.
