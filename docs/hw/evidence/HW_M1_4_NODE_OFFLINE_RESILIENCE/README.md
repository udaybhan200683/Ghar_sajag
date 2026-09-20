# HW-M1.4 node offline resilience

**Status:** IMPLEMENTED / HOST VALIDATED / TARGET BUILD VALIDATED / PHYSICAL VALIDATION PENDING

**Qualified reference:** `7c08bdd78bc6fdbd33f3ea1b614203a0629f4c17`

**Branch:** `fix/hw-m1-4-node-offline-resilience`

**Date:** 2026-09-20

This is follow-on robustness work. It does not revise the historical
HW-M1.3 **QUALIFIED / PASS** decision or the qualified artifact hashes.

## Field observation

With only the battery-powered C3 node active and the Hub intentionally off,
GPIO8 stopped showing its normal blue indication after roughly 32 motions.
Earlier runs reached this state after about seven hours and about one hour.
Power-cycling restored operation, but a later controlled run showed that a
C3 reset was not required: the node remained in session 21 and communication
resumed when the Hub returned.

Measurements taken before reset in the failed-looking state were:

| Point | Measurement |
|---|---:|
| Battery | 3.39 V |
| C3 3V3 | 3.29 V |
| AM312 VCC | 3.29 V |
| AM312 OUT, idle / motion | 0 V / approximately 3.0 V |
| C3 GPIO4 pin, idle / motion | approximately 0 V / approximately 3.0 V |

The Hub later processed session 21 sequence 198, then 199 through 205, with
Durable ACK, `ESP_OK`, channel 1 and RSSI around -49 to -50 dBm. This proves
the C3 had remained alive and that the PIR/electrical path still reached GPIO4.

## Forensic result

The exact path was:

1. `owner_task()` polled GPIO4 every 20 ms.
2. `QualifiedInput::sample()` debounced the transition and emitted Motion.
3. `NodeRuntime::record()` allocated `next_sequence_++` before admission.
4. `NodeStore::append()` retained business evidence, with capacity 64 in the
   qualified implementation.
5. `NodeRadio::enqueue()` attempted to add a retry entry, with capacity 32.
6. GPIO8 blinked only if `record()` returned an EventKey, which required both
   store and TX admission.

Without Durable ACKs, the 32-entry TX deque filled. The next event could enter
the 64-entry store and then fail TX enqueue. `record()` returned failure, so
GPIO8 did not blink. There was no rollback or refill path, leaving these later
records stranded. After 64 retained records, store append also failed. Every
attempt still consumed a sequence ID because allocation preceded both checks.

Therefore the approximate 32 threshold is the actual `NodeRadio` capacity,
adjusted by any entries already pending. A jump such as approximately 156 to
198 is consistent with qualified PIR events continuing to call `record()` and
consume sequence IDs while admission failed. It does not prove delivery or
retention of every intervening identity.

The old GPIO8 meaning was “qualified PIR plus successful store and TX-queue
admission.” It was not raw GPIO, local debounce acceptance, MAC success, or
application ACK. That downstream coupling made a live node look dead.

## Existing retry and recovery behavior

Retry was already timer-polled by the owner task and did not require a new PIR.
The same EventKey was reused. A missing MAC callback cleared after one second.
MAC results scheduled retries at 200, 600, 1800 and 10000 ms plus deterministic
jitter, with 10 seconds repeating. Hub return allowed queued events to retry;
Durable ACK then freed store/TX slots. GPIO8 itself could only resume on a later
successfully admitted PIR—it was not driven by Hub return.

Before this fix, offline event disposition was:

- first TX-capacity entries: retained and retryable;
- later entries up to store capacity: retained but stranded;
- after store capacity: dropped;
- coalesced or overwritten: none.

## Design decision

This revision keeps the current one-event-per-motion domain representation.
Changing caregiver/rule semantics to a first/last/count coalesced motion record
is a larger product decision and is deferred.

The bounded policy is now:

- store and retry defaults are both 32;
- Motion may consume 28 entries;
- four entries are reserved for non-motion evidence such as button, door,
  privacy and gap events;
- newest events that cannot be admitted are rejected immediately and counted;
- higher-priority exhaustion has a distinct counter;
- no event is silently overwritten or coalesced;
- admission preflights TX capacity, and a defensive rollback preserves
  `store count == retry count` if enqueue unexpectedly fails;
- sequence allocation remains before admission, making loss visible as a gap.

This is RAM retention, not flash persistence. A node reboot still loses the
in-memory backlog; persistent retained-event storage remains a separate risk.

Retry now reaches a 60-second periodic backoff after the existing fast stages.
A global opportunity gate prevents a full backlog from producing one packet
per retained event each minute, and round-robin selection prevents starvation.
Durable ACK clears that gate so a recovered Hub can drain the next identity
immediately. Retry remains timer-driven, reuses EventKey, and recovers without
a new PIR event. A failed MAC callback still has the one-second target timeout.

GPIO8 now means **locally qualified PIR accepted by sensing**. It blinks for
200 ms before store/radio admission. Transport state is exposed separately.

## Observability

The versioned `NodeHealthSnapshot` is a separate ESP-NOW frame type. It has an
independent health sequence, is never retained, never consumes business
EventKey space, and has no Durable ACK. The node attempts only the latest
snapshot every 60 seconds; failures do not accumulate. The Hub uses a separate
depth-one overwrite queue and serializes one compact log line with receive RSSI
and channel.

The configured `node-1` frame is 131 bytes (149-byte maximum with a 24-byte
node ID), below the 224-byte data-plane and 250-byte ESP-NOW limits. Fields are:

- schema, node/session, health sequence, uptime and reset reason;
- raw PIR level/edge count, accepted/rejected PIR counters;
- store-full, dropped Motion and priority-rejected counters;
- sensing/runtime liveness and latest breadcrumb;
- retained count and oldest pending sequence;
- in-flight flag, TX/MAC/ACK/retry/backoff counters and last error;
- free/minimum heap and maintenance state.

Breadcrumbs cover boot, raw/accepted PIR, record enter/success/rejection,
TX/MAC/ACK/retirement, retry, and FOTA pause/resume. They are state only and do
not create per-transition serial traffic.

Reset reason is now transmitted. Existing ESP-IDF configuration retains stack
canaries, brownout detection, interrupt watchdog, idle-task watchdog and
panic-print/reboot. Core dump and heap poisoning remain disabled. No periodic
reboot was added.

## Concurrency and maintenance

The C3 owner remains the sole `NodeRuntime` task (priority 8, 8192-byte stack).
The FOTA worker remains priority 7/6144 bytes and the one-shot validation task
priority 6/3072 bytes. Static callback queues remain ACK 8, control 8 and MAC
result 4. Callback sends are nonblocking; drops are counted.

Local PIR sampling and GPIO8 indication now continue during FOTA, while
business admission/radio transmission pause. An active FOTA session has a
30-second inactivity lease; abandonment aborts OTA, clears maintenance and
resumes the data plane. No new task, software timer or node queue was added.

## Validation

Focused host result: **245 checks PASS** under
`-Wall -Wextra -Werror -pedantic` (previous baseline 124).

Added deterministic coverage includes:

- Hub absent from boot and after active operation;
- 1000 qualified Motion attempts with simulated time and offline MAC failure;
- capacity, capacity-plus-one, priority reserve and store/TX mismatch cases;
- bounded store/retry equality and explicit loss counters;
- sequence consumption on rejection;
- retry identity, MAC failure, application-ACK timeout and no-new-PIR recovery;
- correct versus stale Durable ACK;
- repeated Hub off/on recovery;
- 1000 independent sensing cycles;
- separate bounded health-frame classification and codec round trip.

Target builds with ESP-IDF v6.0.3 pass:

| Artifact | HW-M1.3 qualified | HW-M1.4 build | Delta |
|---|---:|---:|---:|
| C3 `gs_hw_m1_node.bin` | 824,368 B | 828,000 B | +3,632 B |
| Hub `gs_hw_m1_hub.bin` | 1,592,848 B | 1,599,312 B | +6,464 B |

The C3 slot remains 58% free; the Hub slot remains 19% free. The Hub increase
includes the embedded C3 image growth. Static RAM adds one Hub depth-one
`ReceivedFrame` queue (approximately 260 bytes plus queue metadata) and bounded
diagnostic counters/state. Reducing the node store default from 64 to 32 removes
up to 32 duplicate retained `DomainEvent` entries. No task stack or queue
capacity was increased.

`make hw-release-gate`: **SOFTWARE/TARGET GATE PASS; PHYSICAL
QUALIFICATION PENDING**. Host regression, partition layout, rollback config,
qualified hardware constants, static structure, both target builds and image
headroom passed. Functional/FOTA HIL remain manual, power/performance remains
not baselined, and endurance remains not run.

## Physical validation still required

No hardware was flashed or exercised in this change. HW-M1.4 must run:

1. **A — Hub online baseline:** verify PIR → Hub → Durable ACK and confirm
   local-PIR GPIO8 semantics plus health logs.
2. **B — Hub off beyond old threshold:** turn Hub off and create at least 100
   deliberate/simulated PIR events. GPIO8 and PIR counters must continue;
   retained count must stay bounded and drops must be explicit.
3. **C — Extended Hub off:** run several hours and confirm sensing/liveness,
   bounded heap/store, retry/backoff and no reset.
4. **D — Recovery without motion:** turn Hub on and create no new motion.
   Pending EventKey traffic must retry within the 60-second periodic backoff
   plus jitter and receive Durable ACK.
5. **E — Fresh motion after recovery:** verify immediate local indication and
   normal Hub processing.
6. **F — Repeated cycling:** repeat Hub off/on at least five times without C3
   reset.
7. **G — Endurance:** 8–12 hours with timestamped Hub serial capture.
8. **H — Resource/power:** measure current, retry energy, heap/stack/queue high
   water, packet loss and thermal behavior. Static analysis makes no CPU/power
   claim.

Capture Hub serial with host wall-clock prefixes and retain session,
`health_seq`, uptime, PIR/drop counters, retained/oldest sequence, retry state,
breadcrumb, heap, RSSI and channel. A dependency-free serial logger may be
added later once the qualification host/port conventions are chosen.

## Deferred work and residual risk

- Backend/PWA integration is intentionally deferred. The same schema can later
  flow Node → Hub → backend → an engineering-only diagnostics page, separate
  from caregiver UX.
- Motion coalescing with first/last/count is not implemented.
- Retained events are not flash-persistent across C3 reset.
- ESP-NOW peer encryption/authenticated FOTA limitations are unchanged.
- Physical retry energy and the suitability of the 60-second/28-entry policy
  require HW-M1.4 measurement.
- ESP-NOW send callbacks do not carry business EventKey identity. The target
  serializes sends and times out at one second, but very late callbacks remain
  a platform-level correlation risk to exercise in fault-injection HIL.
