# C8-P3 controlled AM312 held-HIGH qualification — 2026-10-14

## Disposition

**PASS for the measured physical P3 behavior**, with an explicit image-provenance
limitation: the C3 installed application hash is verified, but the exact hash
of the *running* S3 application has not been read back. The S3 candidate build
hash below is not asserted as its running hash. GS-114 and release acceptance
remain In Progress. Earlier uncontrolled or unstimulated P3 windows retain
their original dispositions; this is a new, separately timestamped run.

## Fixture and baseline

- Source at test: canonical branch `feature/r1-commercial-baseline`, HEAD
  `d18ed3e52d61a4f0f33f563eceb84f1d2f2294fb`; firmware trace source
  commit `c69960fb064a60c3e6dc52b27d90fbbbe30b560a`.
- C3: ESP32-C3 MAC `14:63:93:c5:d1:58`, 4 MiB, installed app SHA-256
  `70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530`,
  active `ota_0` at `0x20000`, C8 physical-wake/schema-3 profile. Its USB
  enumeration was not used to infer application state or opened for this run.
- S3: ESP32-S3 MAC `7c:4f:ad:b7:2a:20`, 16 MiB flash/8 MiB PSRAM,
  commissioning profile with `ota_0`/`ota_1`, `gs_outbox`, `gs_state`. Source-matched
  **build candidate** app SHA-256
  `ca178fe30cc620d3fe0cb5817da9d8a98b07b70cb5f7c443045c85180dd46379`;
  running binary SHA-256 remains unverified. S3 CH343 USB serial
  `1a86:55d3` / `5CBC401023` was reattached by the operator at Windows BUSID
  `3-1`, COM9, and resolved in WSL to stable by-id
  `usb-1a86_USB_Single_Serial_5CBC401023-if00` -> `/dev/ttyACM1`.
- Both boards USB powered, no battery or external supply. Real AM312:
  VCC 3.3 V, common GND, OUT to C3 GPIO4. No synthetic motion, reset,
  firmware write, erase, recommission or security change was used.
- The original exclusive S3 capture PID 324978 automatically detached its
  stale `/dev/ttyACM0` and reopened the new `/dev/ttyACM1` at
  `09:48:53.644–09:48:53.721Z`. The blocked old status writer was gone; `fuser`
  showed PID 324978 as the only `/dev/ttyACM1` owner. No second reader was
  started. Fresh session-16 NodeHealth sequence 19 and schema-3 trace were
  captured at `09:49:06.755–09:49:06.812Z`; `RPF00` admission was OPEN at
  `09:49:05.763Z`. These proved the C3 remained active through the preceding
  USB/IP observation gap (same session, progressing uptime/health sequence).

At the controlled prompt `09:50:56.473Z`, the authenticated baseline was
session 16 / health sequence 19: `pir_raw=0`, `pir_edges=2`, `pir_ok=1`,
`retained=0`, `durable_ack=1`, `sleep_entries=187`, `timer_wakes=186`,
`gpio_wakes=1`, `high_episodes=1`, `high_total_ms=2395`,
`high_max_ms=2395`, `sleep_inhibited_high=119`,
`sleep_entries_gpio4_high=0`, radio restoration OK and owner resumed.
The preceding unrelated EventKey q1 was already retired; it is outside this
controlled P3 window.

## Controlled stimulus and authenticated evidence

The operator was instructed to move continuously in front of the AM312 for
approximately 20–30 seconds, then stop and leave it undisturbed. The prompt
timestamp is above; the operator's DONE reply was received at
`09:51:50.806722193Z`. The separate marker file records these timestamps.
The actual GPIO4 HIGH duration comes from the authenticated Node trace, not
from the time between chat messages.

| UTC | Physical/Hub observation |
|---|---|
| 09:51:13.673–09:51:13.681 | Exact EventKey `p15:c3-146393c5d158n8:gs114-c8s16q2` was authenticated and durably admitted with `state_changed=1`, outbox exact-key lookup `Found`, `records=31`, admission OPEN, `ack=0` (`AckClass::Durable`), ACK send `ESP_OK`. |
| 09:51:13.763–09:51:13.771 | Same EventKey retry was authenticated; `state_changed=0`, `records=31`, outbox key still found, and normal Durable ACK send `ESP_OK`. One logical effect for q2. |
| 09:51:14.025–09:51:14.042 | RPF00 `path=PREPARED admission=OPEN`, followed by authenticated retirement ACK send `ESP_OK`, generation 73. |
| 09:51:41.140–09:51:41.194 | Authenticated NodeHealth sequence 20 and schema-3 trace: `pir_raw=0`, `pir_edges=4`, `pir_ok=2`, `retained=0`, `durable_ack=2`, `gpio_wakes=2`; HIGH episodes 2, total 30,913 ms, maximum continuous episode 28,518 ms, sleep-inhibition samples 1,544, zero sleep entries while GPIO4 HIGH, GPIO wake, radio restore OK and owner resumed. |
| 09:56:40.800–09:56:40.855 | Authenticated NodeHealth sequence 21 and trace after LOW recovery: GPIO4 LOW, no further PIR edge/event, `retained=0`, `durable_ack=2`, `sleep_entries=203`, `timer_wakes=201`, `gpio_wakes=2`, last wake TIMER, radio restore OK and owner resumed. |

The C3 recorder samples the real GPIO4 level in the owner loop and closes
each HIGH episode on the sampled HIGH-to-LOW transition. Between baseline
sequence 19 and sequence 20, `high_episodes` increased by exactly one,
`high_total_ms` increased by **28,518 ms**, and `high_max_ms` became **28,518 ms**.
The HIGH-inhibition counter increased by **1,425** decisions; the cumulative
`sleep_entries_gpio4_high` remained **zero**. `pir_edges` increased by two,
`pir_ok` by one, and `gpio_wakes` by one. This supports one qualified event
from one continuous measured active-HIGH episode, without a sleep-entry/wake
storm while HIGH.

After LOW, sequence 21 shows **11 additional sleep entries and 11 timer wakes**
relative to sequence 20, no new GPIO wake or PIR event, and the same session
with steadily increasing Node uptime. Node durable-ACK count increased by one
and pending/retained count remained zero. The Hub journal count increased only
for the first q2 delivery. No unexpected reset or stall was observed in the
authenticated session/uptime evidence.

## Later activity outside the controlled window

The exclusive capture continued after the `09:56:40Z` LOW/timer-wake recovery
sample. It recorded later authenticated activity at `09:58:48–10:01:33Z`,
starting nearly seven minutes after the operator's DONE reply. These lines are preserved
separately; the source of the later PIR activity is unknown, and it is not
attributed to the controlled 20–30-second movement:

The timestamped selected lines are in `p3_postwindow_s3_excerpt.log`; the
complete capture remains in the preserved local raw log.

| UTC | Observation |
|---|---|
| 09:58:48–09:58:50 | New PIR `MOTION` key `p15:c3-146393c5d158n8:gs114-c8s16q3`; first durable effect `state_changed=1`, same-key repeat `state_changed=0`, RPF00 OPEN, Durable ACK, NodeHealth sequence 22 with HIGH episodes 3 and GPIO4 LOW. |
| 09:59:20 | NodeHealth sequence 23: HIGH episodes 4, GPIO4 LOW, `pir_ok=4`; no Hub event for this episode yet. |
| 10:00:02 | Distinct `MOTION_SUMMARY` key `p15:c3-146393c5d158n8:gs114-c8s16q4`; one durable effect, same-key repeat with no new effect, RPF00 OPEN and Durable ACK. This is a summary event, not evidence of another PIR rising edge at 10:00:02. |
| 10:01:31–10:01:33 | New PIR `MOTION` key `p15:c3-146393c5d158n8:gs114-c8s16q5`; one durable effect, same-key repeat with no new effect, RPF00 OPEN and Durable ACK. NodeHealth sequence 24: HIGH episodes 5, GPIO4 LOW, `pir_ok=5`, `retained=0`, `durable_ack=5`, radio restore OK and owner resumed. |

Between health sequences 21 and 24, sampled HIGH episodes increased from 2 to
5. The later episodes lasted approximately 2,377, 3,680 and 2,378 ms from
the cumulative HIGH counters; none altered the measured 28,518 ms maximum
continuous HIGH interval in the controlled P3 run. Their cause requires
separate physical context if false-activity diagnosis becomes necessary.

## Evidence and limits

- Full timestamped S3 raw capture:
  `s3_uart_timestamped.log` (preserved locally as untracked raw evidence).
- Controlled prompt/DONE and pre-test baseline:
  `p3_run01_controlled_stimulus.txt` (local raw marker).
- Focused S3 excerpt: `p3_run01_s3_excerpt.log`.
- The authenticated deferred trace substitutes for the C3 native USB console,
  which is unreliable during actual light sleep; no direct oscilloscope trace
  was collected. The trace's 20 ms owner sampling bounds the measured HIGH
  duration and is HIL-profile-only. The Hub's exact running app hash remains
  an evidence provenance gap; source-matched behavior and a candidate build
  hash do not prove byte-for-byte installed identity.
- P8 physical ACK loss is next. The currently paired S3 build has
  `GS_HIL_C8_ACK_DROP=OFF`; the older ON build is not source-matched to this
  installed C3. Do not flash it. P9 ACK-hold and signed FOTA remain blocked by
  their separate fixtures; P10 current measurement remains GS-149.
