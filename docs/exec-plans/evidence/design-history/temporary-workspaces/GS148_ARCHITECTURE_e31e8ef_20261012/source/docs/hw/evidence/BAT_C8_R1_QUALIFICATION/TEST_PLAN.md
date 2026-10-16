# BAT-C8 R1 Physical Qualification Plan

**Status: prepared; physical tests P1–P10 have NOT_RUN.** This file is a
procedure and preparation record only. It contains no fabricated physical
results. Capture each eventual run in a dated subdirectory beneath this
directory.

## GS-150 final-candidate software handoff — 2026-10-10

The GS-150 changed receive/sleep policy supersedes the earlier image for final
candidate acceptance. Read [GS-150 evidence](../../../exec-plans/evidence/R1_GS150_SOFTWARE_VALIDATION_20261010.md)
and the [current battery guide](../../../features/BATTERY_LOW_POWER_AND_POWER_MANAGEMENT.md).
Production build is software-only; rebuild the existing explicit physical-wake
profile from the delivered commit before any separately authorized bench run.
Record source/config/image hashes. Prior image evidence below is historical.

GS-114 owns functional non-power P1–P9; GS-149 owns quantitative P10 and its
B0–B4/GS-51 prerequisites. GS-146 still requires both. Focus P1–P9 on confirmed
outage with retained events, absent/missed/late authenticated ACK, successful
MAC with slow app ACK (continuous RX), exact-key replay, Hub reboot/return
without PIR, held HIGH/bounce, deadline margin, radio restore failure, critical
admission and FOTA/control/persistence boundaries. Host tests and target build
are not physical acceptance. P8 still requires its explicit post-commit ACK-loss
fixture and per-key ledger evidence. All physical cases remain NOT_RUN here;
no authorization to modify protected boards is supplied by this handoff.

## Historical canonical pause/resume checkpoint — 2026-10-10

Owning issue: GS-114 under GS-110. Current canonical source is
`/home/udaybhan/projects/Ghar_sajag_r1`, branch `feature/r1-commercial-baseline`.
The BAT-C8 C3 software is already integrated in canonical history (battery source
commit `808080e94b6958153952ce16eb56c1ad37a9ad01` is an ancestor). Focused host
validation passed during source consolidation: 72 C++ checks and 9 Python power
invariants. Qualification image build evidence is the prepared artifact below;
no physical qualification was run during consolidation.

Next exact work: resume only remaining physical P1–P10 and GS-140/B0–B4/GS-51
matched AFTER measurement gaps after checking latest Jira and safe bench plan.
GS-144 numeric target/workload, GS-119 residual C1–C4 plus 12-hour soak with
end-of-soak real PIR-to-ACK, and GS-146 final C1–C8 closure remain open. Reuse
prior evidence only when board/image/setup hashes match. Do not flash, reset,
erase, repartition or re-enroll either protected S3 or the paired C3 with its
historically observed seven pending events. BAT-C8 remains software/host complete
and physically unqualified. No new changes to `GS-115` C9–C12 are authorized;
they remain measurement/decision-only.

The S3 pause is intentional: GS-148 P2-D remains partial with production
authentication/COMMITTED ownership, active connectivity, canonical 72-hour trace
and physical gates open. The next R1 priority is the battery qualification queue,
not S3 or GS-147 implementation.

## Preparation record

### Qualification image

- Target: ESP32-C3, repository Node IDF application.
- ESP-IDF: `ESP-IDF v6.0.3`.
- Build directory: `/tmp/ghar_sajag_r1_bat_c8_physical_wake_qual`.
- Configuration: `GS_HIL_BUILD=OFF`, `GS_HIL_CONTROL=ON`,
  `GS_BAT_C8_PHYSICAL_WAKE=ON`; target `esp32c3`.
- Source defaults: `firmware/node/target/esp32c3/idf/sdkconfig.defaults`.
- Build succeeded. The generated image is a HIL-control physical qualification
  image, not a Secure Boot, eFuse, or production-key qualification image.
- The smallest OTA application slot is `0x1e0000` (1,966,080 bytes). The app
  image is `0xe4da0` (937,376 bytes), leaving `0xfb260` (1,028,704 bytes,
  52%) free in that slot.
- Bootloader: 21,408 bytes (`0x53a0`), with 11,360 bytes (`0x2c60`, 35%) free
  in its configured region. Partition table: 3,072 bytes.

Exact configuration and build commands (ESP-IDF export was sourced first):

```sh
source /home/udaybhan/.espressif/v6.0.3/esp-idf/export.sh
idf.py -B /tmp/ghar_sajag_r1_bat_c8_physical_wake_qual \
  -DSDKCONFIG=/tmp/ghar_sajag_r1_bat_c8_physical_wake_qual/sdkconfig \
  -DSDKCONFIG_DEFAULTS=/home/udaybhan/projects/Ghar_sajag_r1/code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/node/target/esp32c3/idf/sdkconfig.defaults \
  -DGS_HIL_BUILD=OFF -DGS_HIL_CONTROL=ON \
  -DGS_BAT_C8_PHYSICAL_WAKE=ON set-target esp32c3
idf.py -B /tmp/ghar_sajag_r1_bat_c8_physical_wake_qual \
  -DSDKCONFIG=/tmp/ghar_sajag_r1_bat_c8_physical_wake_qual/sdkconfig \
  -DSDKCONFIG_DEFAULTS=/home/udaybhan/projects/Ghar_sajag_r1/code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/firmware/node/target/esp32c3/idf/sdkconfig.defaults \
  -DGS_HIL_BUILD=OFF -DGS_HIL_CONTROL=ON \
  -DGS_BAT_C8_PHYSICAL_WAKE=ON build
```

Built artifacts and SHA-256:

| Artifact | Size | SHA-256 |
|---|---:|---|
| `gs_hw_m1_node.bin` | 937,376 bytes | `6166999c619e1a1b70c78a0b38e445c7012c3c474ed4575de4a47177a19b0e4f` |
| `bootloader.bin` | 21,408 bytes | `cb43a807b9e167829717ed50c7882bca148fa52aa3c6704c6f890813d33281fe` |
| `partition-table.bin` | 3,072 bytes | `1b86379629900670bd43147c3a873a424695a67765fd1bdb28b1bffc21be137a` |

ESP-IDF printed Kconfig `NOTE` messages for NimBLE/FATFS Boolean defaults set
to `0` (treated as `n`) and duplicate legacy Bluetooth sdkconfig rename
mappings during configuration. No project compiler/linker warning or build
error was observed; `check_sizes.py` passed.

### Focused host gates

Run from the product root `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2`:

| Command | Result |
|---|---|
| `make battery-c8-host-test` | PASS: 72 focused checks and 9 Python invariants |
| `make rejoin-host-test` | PASS: mutual proof/session/Home/replay validation |
| `make node-recovery-persistence-host-test` | PASS: encrypted bounded recovery validation |

These are host results only; they do not count as physical wake or radio
qualification.

## Common bench setup and evidence rules

1. Use one installed C3 Node with the AM312 output connected to GPIO4, and one
   enrolled Hub running the compatible R1 target image. Verify AM312 idle LOW
   and active HIGH at GPIO4 before beginning. Record board identifiers, wiring,
   channel, configured TX power, supply/battery, and firmware hashes.
2. Flash only the exact hash-verified qualification image recorded above.
   Preserve a recovery image and record the active OTA slot before testing.
   Do not use injected PIR motion: this profile deliberately rejects
   `INJECT_MOTION`. Do not use Node `GET_HEALTH`: it is deliberately rejected
   so it cannot create test traffic. `GET_STATE` is allowed on both devices.
3. Capture full, unfiltered timestamped Node and Hub UART logs from before
   power-on through each test end. Use one reader per serial port. Take
   `GET_STATE` snapshots at each stated boundary. For the Hub record
   `HIL_STATE role=hub online=... processed=... durable_ack=... health=...`;
   for the C3 record `HIL_STATE role=c3 session=... retained=... in_flight=...`.
   Hub process/ACK counters reset on Hub reboot, so take a new baseline after
   each restart.
4. Correlate events by the Node `session` and `seq` in `PIR -> NodeRuntime`,
   `NodeMessage sent`, `Application ACK`, and Hub `Processed` lines. Together
   with the provisioned Node identity these identify the EventKey. Retain raw
   captures, not only filtered excerpts or summaries. The optional original
   Hub raw-capture utility can be invoked from the battery reference tree if
   byte-level UART diagnostics are needed; do not run it concurrently with
   another Hub serial reader.
5. For every run retain a manifest with UTC start/end, operator, board and
   sensor IDs, wiring/rail voltages, image hashes, IDF/build configuration,
   serial-port mapping, Hub state, instrument model/range/burden/sample rate,
   test stimulus, result, anomalies, and evidence filenames. Candidate files
   are `c3-uart.log`, `hub-uart.log`, `instrument-current.csv`, and
   `manifest.json`; create them only for tests actually run.

The current C3 INFO markers for the physical profile are
`BAT_SLEEP_DECISION`, `BAT_SLEEP_ENTER`, `BAT_SLEEP_WAKE`,
`BAT_SLEEP_RESTORE`, `PIR -> NodeRuntime`, `NodeMessage sent`, and
`Application ACK`. Hub markers include `Processed`, `Rejected stale
session=... active=...`, `Rejected unauthenticated/replayed runtime frame`,
`Authenticated rejoin`, and `HIL_STATE role=hub`. Sleep-decision records are
emitted only for eligible sleep; absence of a decision record is not itself
proof of a particular inhibitor.

## Physical test procedures

### C8-P1 — Timer-only sleep and wake

- **Setup:** Hub authenticated and online; C3 enrolled; GPIO4 held LOW and
  stable through the debounce/retrigger interval; no retained/pending event,
  maintenance, ACK wait, or other owner work. Record pre-test Hub state.
- **Stimulus:** Leave the Node undisturbed until it enters a normal eligible
  light-sleep interval and let the programmed timer expire.
- **Expected Node UART:** `BAT_SLEEP_DECISION eligible=1`,
  `BAT_SLEEP_ENTER ... gpio4=1 timer=1`, `BAT_SLEEP_WAKE ... cause=TIMER`,
  and `BAT_SLEEP_RESTORE radio=ESP_OK ... wifi=1 esp_now=1 owner=RESUMED`.
- **Hub evidence:** Before/after `GET_STATE`; `processed` and `durable_ack`
  unchanged and no new event for the timer wake.
- **PASS:** Timer is reported as the wake cause, radio restoration succeeds,
  the owner resumes, and no PIR event is synthesized.
- **FAIL:** No sleep entry, GPIO/other cause with PIR held LOW, timer wake
  failure, radio restore failure, reset, or a timer-created Hub event.
- **Retain:** Both UART logs, state snapshots, board/wiring manifest, and exact
  image hashes.

### C8-P2 — Real AM312 GPIO4 wake

- **Setup:** P1 conditions, real AM312 wired and verified, Hub online, and
  no injected-motion command. Capture baseline Hub counters.
- **Stimulus:** Wait until the C3 logs `BAT_SLEEP_ENTER`; create one real
  motion episode in the AM312 field of view.
- **Expected Node UART:** `BAT_SLEEP_WAKE ... cause=GPIO gpio4=1`, successful
  `BAT_SLEEP_RESTORE`, then exactly one `PIR -> NodeRuntime session=... seq=...`
  and the matching `NodeMessage sent`/`Application ACK`.
- **Hub evidence:** One matching `Processed session=... seq=...` with durable
  application ACK; `processed` and `durable_ack` each increase by one.
- **PASS:** The GPIO wake is real, the first qualified motion is admitted and
  durably acknowledged once, with no reset or duplicate logical event.
- **FAIL:** No GPIO wake, a timer-only wake despite active GPIO4, missing or
  multiple qualified events, failed restore, or no matching Hub ACK.
- **Retain:** Node/Hub UART, before/after Hub state, sensor/wiring details, and
  a timestamped record of the physical stimulus.

### C8-P3 — Held-HIGH PIR and first qualified event

- **Setup:** C3 awake and authenticated, Hub online, GPIO4 and AM312 output
  visible on the measurement point. Record Hub counters.
- **Stimulus:** Hold a real AM312 active-HIGH episode across the normal sleep
  eligibility window, then allow it to return LOW. Do not force an edge through
  HIL controls.
- **Expected Node UART:** One `PIR -> NodeRuntime` for the qualified episode;
  no `BAT_SLEEP_ENTER` while GPIO4 is HIGH; no repeated sleep/wake loop. After
  GPIO4 has remained LOW through the existing debounce/retrigger window, normal
  sleep may resume.
- **Hub evidence:** One matching durable `Processed`/ACK and a one-event delta.
- **PASS:** Held HIGH inhibits another sleep attempt, the qualified first
  event reaches Hub once, and LOW recovery returns to normal operation.
- **FAIL:** Sleep re-entry while HIGH, missed event, repeated duplicate event,
  or permanent awake/sleep loop after LOW stabilizes.
- **Retain:** Both UART logs, GPIO4 level/time trace if instrumented, Hub state
  snapshots, and episode duration.

### C8-P4 — Wake, radio restore, and Hub ACK

- **Setup:** Hub online, C3 authenticated, AM312 wired, sleep eligible; capture
  Hub counters before the event.
- **Stimulus:** Cause one real motion while the C3 is asleep.
- **Expected Node UART:** In order: GPIO `BAT_SLEEP_WAKE`, successful
  `BAT_SLEEP_RESTORE`, `PIR -> NodeRuntime` with key K, `NodeMessage sent` K,
  then `Application ACK` K with `retired=1`.
- **Hub evidence:** `Processed` K with `app_ack` durable and successful
  `ack_send`; `HIL_STATE` process/durable-ACK counters each increase once.
- **PASS:** Radio and peer restoration precede the first event send, the Hub
  durably acknowledges the same EventKey, and Node pending work retires.
- **FAIL:** Any ordering gap, changed key, lost event, rejected ACK, retained
  pending event after durable ACK, duplicate logical effect, or reset.
- **Retain:** Both UART logs, state snapshots, event-key correlation, and wake
  latency from GPIO assertion to Hub ACK.

### C8-P5 — Hub unavailable while Node sleeps

- **Setup:** Hub online; Node authenticated and eligible to sleep. Record Node
  session and Hub/Node state.
- **Stimulus:** After `BAT_SLEEP_ENTER`, power off only the Hub. Let the Node
  timer-wake; while Hub remains off, create one real AM312 motion episode. Then
  restore Hub power.
- **Expected Node UART:** Timer wake and successful radio restore; the PIR
  event gets one EventKey, remains retained/pending without application ACK,
  and is retried after Hub restoration. Record any bounded retry and rejoin
  markers; do not treat MAC submission alone as delivery.
- **Hub evidence:** No event while Hub is powered off; after restart/recovery,
  one durable `Processed`/ACK for the retained EventKey and a post-ACK state
  snapshot showing no retained pending Node event.
- **PASS:** Sensor event is not lost during the outage, its EventKey is stable
  across retries, and recovery produces one Hub logical effect and one durable
  retirement ACK without Node reset.
- **FAIL:** Lost event, key changes on retry, unbounded rapid retry, Node reset,
  or duplicate logical effect.
- **Retain:** Both serial logs with power-off/on timestamps, pre/post snapshots,
  EventKey/retry correlation, and Hub outage duration.

### C8-P6 — Hub-only reboot while Node sleeps

- **Setup:** Hub and Node authenticated; Node has no pending work and is
  asleep after `BAT_SLEEP_ENTER`. Record the current session and Hub state.
- **Stimulus:** Reboot only the Hub while the Node remains asleep. Do not reset
  or reflash the Node. Let the Node wake on its normal timer and continue
  observing through the existing session recovery timeout/retry window.
- **Expected Node UART:** Timer wake/radio restoration; old-session contact
  failure/recovery as applicable, including `Authenticated Hub contact
  expired; rejoining` if the configured timeout is reached. No fabricated
  contact or repeated Node reboot.
- **Hub evidence:** Hub boot/reset banner, `HIL_READY role=hub`, rejection of
  stale/unauthenticated runtime traffic where applicable, then
  `Authenticated rejoin device=... logical=... session=...` with a session
  newer than the pre-reboot session. Take a new Hub counter baseline after boot.
- **PASS:** Hub reboot alone does not lose Node identity or cause Node reset;
  stale transport/session state is not accepted as fresh; a newer authenticated
  session is established within the implementation's bounded recovery policy.
- **FAIL:** Hub cannot recover its enrolled Node, accepts old session as a new
  one, Node fails closed, or recovery requires resetting the Node.
- **Retain:** Node and Hub UART across the full interval, reset markers, old/new
  sessions, Hub state immediately after boot, and measured recovery duration.

### C8-P7 — First real PIR event after Hub reboot

- **Setup:** Complete P6 and wait until the newer authenticated session is
  established. No PIR event may be generated between Hub reboot and this test.
  Record a fresh post-reboot Hub state baseline.
- **Stimulus:** Generate the first real AM312 motion episode after Hub reboot.
- **Expected Node UART:** `PIR -> NodeRuntime` with the new session and next
  sequence; matching `NodeMessage sent` and `Application ACK retired=1`.
- **Hub evidence:** Matching `Processed` with durable ACK; one-event increase
  from the post-reboot baseline. Preserve P6 stale/rejoin evidence with this
  run so the first event is tied to the new session.
- **PASS:** First post-reboot physical motion is delivered and durably retired
  once under the new session.
- **FAIL:** First event is missed, sent under a rejected/stale session, ACKed
  only at MAC level, duplicated logically, or requires manual Node reset.
- **Retain:** Continuous Node/Hub logs, post-reboot baseline and final Hub
  state, event key, and PIR stimulus timestamp.

### C8-P8 — Lost application ACK, stable EventKey, one logical effect

- **Setup:** Hub journal is healthy and the event-ledger inspection method is
  available. Use a controlled directional RF attenuator/shield or an already
  approved fixture that can suppress one Hub-to-Node application ACK after
  the Hub commits the uplink, while preserving the Node-to-Hub uplink. Record
  the Hub event-ledger count/key set before the run.
- **Stimulus:** Cause one real PIR event. Allow the Hub to commit it, suppress
  its first application ACK, then restore the downlink so Node retry succeeds.
- **Expected Node UART:** First `NodeMessage sent` K, no `Application ACK` K
  for the suppressed reply, retry of the same K, then `Application ACK` K with
  `retired=1`. The key is the same Node identity/session/sequence throughout.
- **Hub evidence:** Two matching `Processed`/ACK-send attempts for K may be
  visible. The authoritative journal/product event ledger must show exactly
  one logical record/effect for K before and after retry; the second delivery
  must be treated as a duplicate, not re-applied.
- **PASS:** Stable EventKey across retry, eventual durable Node retirement,
  and exactly one durable logical Hub effect for K.
- **FAIL:** A changed key, no retry/retirement, two logical Hub effects, or an
  apparent pass based only on `HIL_STATE processed`/`durable_ack` counters.
- **Retain:** Both raw UART logs, attenuator/fixture settings and timing, Hub
  event-ledger before/after evidence keyed by K, Hub state snapshots, and retry
  timing.
- **Known prerequisite:** Hub `GET_STATE` exposes process/ACK counters but
  not the durable event-key inventory. The existing Hub logical-offline HIL
  command returns before event commit and is not a lost-ACK test. Do not mark
  P8 PASS until a read-only ledger inspection source and post-commit ACK-loss
  fixture are available.

### C8-P9 — FOTA and ACK work inhibit sleep

- **Setup:** Compatible Hub HIL-control image, C8 C3 image, enrolled Node, and
  a valid signed C3 test image plus known rollback/recovery image. Capture the
  initial Hub state. Run the pending-event ACK subcase and FOTA subcase
  separately so each active condition is observable.
- **Stimulus:** For the ACK subcase, produce one real PIR event and keep its
  application ACK pending using the same controlled link fixture as P8; restore
  the link after an observation interval. For the FOTA subcase, start an
  authenticated signed update while the C3 is awake, then allow the transfer
  and post-update validation to finish.
- **Expected Node UART:** No `BAT_SLEEP_ENTER` while the event is in-flight/
  awaiting application ACK or while FOTA maintenance is active. For FOTA,
  retain `FOTA maintenance ACTIVE/INACTIVE`,
  `SECURE_FOTA_IMAGE_SHA256_VERIFIED`, and `FOTA COMPLETE` (or explicit
  failure/rollback markers). Hub logs should include
  `SECURE_FOTA_SESSION_PINNED`, `SECURE_FOTA_BEGIN_ACK`, ACK progress, and
  `SECURE_FOTA_TRANSFER_COMPLETE` for success.
- **Hub evidence:** For the ACK case, matching Hub `Processed` and durable
  ACK evidence after restoring the link. For FOTA, matching transfer/session
  completion evidence and Node state after reboot/health validation.
- **PASS:** Sleep remains inhibited during each active ACK/FOTA window; event
  retirement and signed FOTA validation complete; sleep resumes only after the
  work is idle and the normal policy becomes eligible.
- **FAIL:** `BAT_SLEEP_ENTER` during active work, dropped/incorrect ACK,
  failed signature/session validation, unexpected reset/rollback, or no return
  to normal sensing/radio operation after maintenance ends.
- **Retain:** Both UART logs, signed image hash, FOTA transfer/session IDs,
  state snapshots, OTA slots before/after, and the ACK fixture record.

### C8-P10 — Matched active versus light-sleep current

- **Setup:** Same physical Node/AM312, Hub, supply/battery and measurement
  boundary for both runs. Use a logger/analyzer with documented range,
  bandwidth/sample rate, burden/shunt, and uncertainty. Use matching
  HIL-control builds and settings; the active comparison has
  `GS_BAT_C8_PHYSICAL_WAKE=OFF`, and the qualification run has it `ON`. Keep
  channel, TX power, sensor supply, board placement and logging identical.
- **Stimulus:** Measure equal-duration quiet/idle windows with the Hub online,
  then repeat a defined real-motion workload with the same number and pacing of
  events. Capture Node/Hub logs and current samples simultaneously. Run
  repeated pairs and record voltage at the measurement boundary.
- **Expected Node UART:** Active comparison remains awake. Qualification image
  demonstrates actual `BAT_SLEEP_ENTER`, timer wake, GPIO wake, and successful
  restore without changing sensing/ACK behavior.
- **Hub evidence:** Equal event workload and matching accepted/durable-ACK
  counts in both arms; preserve RSSI, retry, and latency evidence.
- **PASS:** Matched quiet-window average current/energy is repeatably lower
  with light sleep by more than the combined instrument uncertainty, while
  motion delivery/ACK correctness is not degraded. Record the measured delta;
  no battery-life target is inferred from it.
- **FAIL:** No reduction distinguishable from uncertainty, incomparable setup
  or workload, missing raw samples, or lower current achieved with lost/delayed
  motion events or degraded communication.
- **Retain:** Raw current CSV, both UART logs, instrument specifications and
  calibration/uncertainty, active and sleep image hashes/configs, workload
  schedule, calculations, and all repeated-run results.

## Diagnostics and known instrumentation limits

The three diagnostic scripts are in the battery reference tree under
`code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tools/hil/`; the paths
without that product subdirectory do not exist. They are untracked there and
were inspected read-only.

- `single_owner_hub_capture.py`: useful optional raw-byte Hub UART capture,
  with exclusive ownership, fsync, malformed/NUL/duplicate-line counts, and
  optional `GET_STATE`. It overlaps the R1 serial harness for ordinary
  timestamped logs but preserves raw bytes. It is not a C8 test driver and is
  not required for the standard line-log evidence. Do not copy it as part of
  this no-source-change preparation; use it later only if byte-level capture
  is needed, with no competing Hub serial reader.
- `hub_uart_flush_probe.py`: diagnostic only for suspected host RX-buffer or
  line-framing contamination; it flushes host RX, sends one `GET_STATE`, and
  counts UART markers. It does not qualify sleep/wake and is not needed for a
  normal C8 run. Do not copy.
- `hub_minimal_raw_probe.py`: diagnostic only for suspected byte loss/read
  chunking; it records raw bytes and read lengths around one `GET_STATE`. It
  overlaps the first script's raw capture and is not needed for normal C8
  qualification. Do not copy.

P8's current-target evidence gap is explicit: Hub `HIL_STATE processed` and
`durable_ack` counters count processing/ACK activity but do not expose the
durable EventKey set, and the current Hub HIL control has no journal dump
command. Source behavior in `HubRuntime::run_state_once` is duplicate-safe,
but source inspection alone is not physical proof. A read-only authoritative
event-ledger view and verified post-commit ACK-loss fixture are prerequisites
for P8 PASS. The C8 image may be used for P1–P7 and P9–P10 once hardware is
available; overall C8 closure still requires every applicable gate including
P8.


## GS-40 candidate prerequisite — 2026-10-10

The next separately authorized GS-114 P1–P9 fixture must include GS-150 and
GS-40 matched C3/S3 images plus validated JSON/profile manifest. Default300s
health and derived910s silent-Node lease replace historical target timing.
Verify startup configuration fingerprints, five-minute idle opportunities,
30-minute quiet six opportunities, authenticated event suppression, silent
lease expiry/caregiver unknown-offline display, legacy profile mapping,
Hub Internet versus local coverage, GPIO4/held-HIGH, timer/ESP-NOW restoration
and automatic outage rejoin without new motion. Preserve critical events and
original pending records. These are planned cases, not physical PASS evidence;
GS-40 retains its own real-target/visibility acceptance. Board/image preparation
and all hardware actions still require separate authorization.
