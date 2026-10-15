# BAT-C8 R1 Physical Qualification Plan

**Status: current procedure; result dispositions are recorded in the
[consolidated execution report](GS114_C8_EXECUTION_20261013T111655Z/EXECUTION_REPORT.md).**
As of 2026-10-15, P1/P2/P4/P5/P6/P7/P8 have supported physical PASS evidence;
P3 behavior passed with incomplete running-S3 provenance; P9 authenticated
ACK-hold and signed-FOTA subcases are BLOCKED / NOT_RUN; P10 remains NOT_RUN
under GS-149. This plan defines acceptance procedures and is not itself a
physical result. Capture any future run in a dated subdirectory beneath this
directory.

**Current operation boundary — 2026-10-15:** this documentation update does
not authorize board, USB/serial, reset, flash, erase, OTA, power-cycle, or
recommissioning operations. Obtain separate authorization for the exact
fixture, image hashes, physical action, observer path, stop conditions, and
recovery procedure before any such operation.

## Current R&D execution authority — 2026-10-13

GS-114 comment 10732 and the user execution instruction supersede preservation
of old experimental flash/enrollment/pending state for the existing identified
R&D C3/S3 pair. Deliberate clean erase/reinstallation/recommissioning is allowed
after the supervising operator confirms exact connected targets, ports, safe
power/wiring and the operation. Retain previous failure reports and redacted
logs. The earlier protected-state warnings below describe their historical
checkpoints; all authenticated durability and P1–P9 acceptance criteria remain.

Prepared candidate pair recorded at that checkpoint (not evidence of a current
installed/running image): C3 939,024 bytes,
SHA-256 `ad173384e827614bcbb62c0deac60b5d866dd144088528523c5711e5c2409e43`;
S3 1,887,440 bytes,
SHA-256 `8c53b999c001095030c7f150854b9637404b666364470131f1511cffdc34a4f7`.
They were built with GS-150/GS-40 and GS-148 Option A, ESP-IDF 6.0.3, C3
physical wake and S3 commissioning/outbox-state profile. Reuse was verified
against fingerprint
`c07ae9a0cb79491379d4de65f6c83d7b31b3c0d7613bc3d9e2f912c2c1fcce83`.
The [current execution report](GS114_C8_EXECUTION_20261013T111655Z/EXECUTION_REPORT.md)
owns actual per-case images, installed/running provenance, results and the exact
resume action. Candidate build hashes are not installed-image evidence. A
documented setup reset is allowed; unexplained resets within a measurement
window fail qualification.

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
  -DSDKCONFIG_DEFAULTS=/home/udaybhan/projects/Ghar_sajag_r1/code/firmware/node/target/esp32c3/idf/sdkconfig.defaults \
  -DGS_HIL_BUILD=OFF -DGS_HIL_CONTROL=ON \
  -DGS_BAT_C8_PHYSICAL_WAKE=ON set-target esp32c3
idf.py -B /tmp/ghar_sajag_r1_bat_c8_physical_wake_qual \
  -DSDKCONFIG=/tmp/ghar_sajag_r1_bat_c8_physical_wake_qual/sdkconfig \
  -DSDKCONFIG_DEFAULTS=/home/udaybhan/projects/Ghar_sajag_r1/code/firmware/node/target/esp32c3/idf/sdkconfig.defaults \
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

Run from the product root `code`:

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

### C8-P9 — authenticated ACK hold and signed-FOTA sleep inhibition

P9 has two independent physical subcases. Both are currently **BLOCKED /
NOT_RUN**. The 2026-10-14 host/state-machine PASS does not satisfy either
physical result. The preserved 2026-09-25 signed-FOTA campaign is historical
evidence for a different source/image profile; it did not measure this C8
sleep-inhibition case and does not close P9.

#### P9-A — held authenticated Durable ACK

**Required fixture and image prerequisites:**

- Named C3/S3 pair, exact MACs/serials, wiring, supply and active OTA slots;
  healthy authenticated ownership/session and OPEN replay admission.
- Source, clean/dirty state, C3/S3 BIN hashes, configuration hashes, build
  profile, partition map and installed/running image identity captured before
  the case. The C3 build must include the C8 physical-wake path and the
  production ACK-wait/sleep policy under test.
- A bounded test-only postcommit ACK-hold control that delays only the valid
  authenticated Durable ACK for the selected new EventKey, or a qualified
  directional RF fixture that suppresses Hub-to-Node application ACKs while
  preserving Node-to-Hub traffic. The control must fail closed, be default-off,
  have a watchdog release, and leave event admission, identity, session,
  signature checks and persistence semantics unchanged. Do not enable broad
  Hub HIL controls.
- A read-only authoritative per-EventKey Hub ledger view. `GET_STATE` counters
  alone cannot prove one logical effect. The existing P8 one-shot ACK-drop
  image suppresses only one ACK and the confirmed fixture has no directional
  attenuator/shield; neither provides this longer hold.
- A continuously verified, non-resetting Node observation path that can show
  the ACK-wait interval and any `BAT_SLEEP_ENTER` marker. Do not open a C3
  console unless its DTR/RTS behavior is proven not to reset the target.

**Procedure:**

1. Record Hub/Node identity, authenticated session, replay admission, current
   event-ledger key set, Node retained count, reset count and sleep-entry count.
   Preserve every pre-existing pending key; if they prevent unambiguous case
   attribution, stop without clearing them.
2. Create one real AM312/GPIO4 event. Record its exact EventKey `K` and require
   the Hub's durable commit for `K` before arming the ACK hold. Confirm exactly
   one logical ledger effect and that `K` remains pending on the Node.
3. Hold the valid application ACK for **12,000 ms after the durable commit**
   (longer than the existing 10,000 ms software receive-budget scenario), with
   a **15,000 ms fixture watchdog maximum**. Record actual start/end times.
   Keep the authenticated session and event identity unchanged.
4. Capture continuously through the full hold. Require no sleep entry while
   `K` is awaiting ACK, with target observation alive across the interval.
   Release the original valid authenticated Durable ACK; do not synthesize a
   success response or change `K`.
5. Require authenticated ACK acceptance, exact-key retirement, retained count
   returning to baseline, one Hub logical effect for `K`, no reset, and later
   return to ordinary sleep eligibility after all work is idle.

**PASS:** all five steps are evidenced on the matched target pair. **FAIL:**
sleep begins during the hold, the ACK is unauthenticated/for a different key,
the event is lost or duplicated, the session changes unexpectedly, or normal
operation does not recover. **BLOCKED:** fixture release, exact-key ledger, or
continuous reset-safe target observation is missing. The 12-second interval is
a bounded test stimulus, not a product maximum-ACK-latency promise.

#### P9-B — signed FOTA maintenance sleep inhibition and recovery

**Required signing, firmware and rollback prerequisites:**

- Matched C3 and Hub firmware from the selected source checkpoint. The C3
  profile must keep the signed-app-on-update verifier enabled and trust the
  recorded test public key. The Hub must expose a supported authenticated
  owner-task FOTA trigger for the exact enrolled Node and embed the exact C3
  signed artifact bytes. Current GS-114 notes say the S3 profile has
  `GS_HIL_BUILD=OFF`, `GS_HIL_CONTROL=OFF` and no supported physical trigger;
  this must be resolved by an existing safe path or a separately reviewed,
  narrow fixture-only control. Do not enable broad HIL control.
- Signed baseline image **A**, valid update image **B** signed by A's trusted
  test key with a distinct version, and wrong-key negative image **N** whose
  authenticated transport and declared digest remain valid through the target
  signature-verification step. Record hashes, sizes, versions, build profiles,
  public-key fingerprints, C3 trust configuration, and Hub-embedded-image
  hash. Use distinct disposable **RSA-3072** test keys stored outside the
  repository; A/B share the target-trusted test key, and N uses the negative
  key. Never copy private keys into source or evidence. The separate CloudSync
  RSA/mTLS decision is not a FOTA signing authority.
- Verify the exact on-device partition map and active slot using a read-only
  method; confirm A/B fit the actual OTA slot and the Hub embeds the exact
  selected image. Keep a known-good signed recovery image and a proven
  app-level rollback path. Record boot-health/rollback behavior and how the
  original authenticated identity and pending EventKeys survive. If recovery
  would require erase, factory reset, eFuse change, or unapproved full-device
  flashing, do not start.
- A reset-safe continuous C3/S3 capture, fresh authenticated session, healthy
  replay admission, and a baseline of retained/in-flight EventKeys. Do not
  clear NVS, outbox/state, enrollment, or pending records to make the case pass.

**Procedure:**

1. Record the A baseline, Node/Hub identities and session, active OTA slots,
   partition hashes, replay admission, retained EventKeys, reset counters,
   sleep-entry counter, and current sensor/radio readiness.
2. Run the wrong-key **N** transfer first. Require authenticated session and
   image digest success followed by target signature rejection. Require the
   active slot and A version to remain selected, all pre-existing retained
   keys unchanged, and a normal application event to remain deliverable.
3. Trigger authenticated FOTA for the exact Node using valid **B**. Capture
   maintenance-active state, transfer/session IDs, authenticated ACK progress,
   digest/signature acceptance, and continuous target sleep markers. Require
   no `BAT_SLEEP_ENTER` while maintenance/transfer/persistence is active.
4. Require the alternate slot selection, expected B boot, boot-health success,
   fresh authenticated rejoin, sensing-ready state, unchanged pre-existing
   EventKeys, then one new real application event with a Durable ACK.
5. Verify sleep becomes eligible only after FOTA ends and the normal post-boot
   readiness gates pass. Record whether rollback stayed unused or was invoked.
   Do not force an unsafe power cut or boot failure as part of this case.

**PASS:** N is rejected at target signature verification without slot/state
change; B is accepted, boots and recovers under the exact signed-image
provenance; sleep remains inhibited throughout active maintenance and resumes
only after safe recovery. **FAIL:** sleep during active work, signature bypass,
wrong slot/image, lost or changed retained key, failed boot-health/rejoin, or
unsafe recovery. **BLOCKED:** missing trusted signing manifest, matched images,
supported trigger, actual slot readback, reset-safe observer, or approved
rollback/recovery route. Full physical operation still needs separate
authorization naming the pair, exact image hashes, expected OTA/reset actions,
observer wiring, stop conditions and recovery steps.

**Retain:** both device logs; all A/B/N hashes, sizes and public-key
fingerprints; source/config/profile/partition hashes; transfer/session IDs;
active-slot before/after evidence; sleep markers/counters; exact EventKeys and
ACKs; boot-health, rejoin, reset and rollback record; and unique run manifest.

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

An earlier audit observed three untracked diagnostic scripts in a legacy
battery reference tree. That observation is historical and does not establish
active runnable paths. The maintained R1 HIL tools are under `code/tools/hil/`.

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
