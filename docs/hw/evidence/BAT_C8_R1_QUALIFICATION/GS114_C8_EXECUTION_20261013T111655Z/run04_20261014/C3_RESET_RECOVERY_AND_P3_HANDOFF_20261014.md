# GS-114 C3 reset recovery and P3 handoff — 2026-10-14

## Latest resume checkpoint — P8 physical PASS, USB/IP capture stopped

This dated handoff was originally written before the P3 retest. It now resumes
from the later run04 evidence: P3 and P8 are physical PASS; reuse RPF07, P1,
P2, P4, P5, P6 and P7 PASS evidence without repetition. P8's exact EventKey is
`p15:c3-146393c5d158n8:gs114-c8s16q14`; its postcommit ACK suppression, same-key
retries, single durable effect, authenticated ACK and Node retirement are
recorded in [C8_P8_PHYSICAL_20261014.md](C8_P8_PHYSICAL_20261014.md).

The operator clarified that real movement occurred before the direct prompt;
its exact physical timestamp is unknown, and no latency or prompt causality is
claimed. A separate arm at 12:14:59 UTC had no event/health evidence. The later
S3 monitor reported write timeouts; read-only WSL kernel logs show USB/IP URB
status `-104` beginning 12:12:37 UTC. After preserving logs, the monitor was
gracefully interrupted; it held no serial fd and `fuser` found no tty owner.
No reset, reattach, firmware write, power change or further serial command was
performed. Do not repeat P1–P8 or try to recover USB/IP by blind attach.

P9 ACK remains blocked on a validated, sufficiently long ACK-hold fixture.
P9 signed FOTA remains blocked pending matched signed C3 images, trusted
signing provenance, authenticated trigger and safe recovery. P10 remains
GS-149. Leave GS-114 In Progress.

**Next action:** use only a newly verified, exclusive S3 observer if further
physical work is explicitly resumed; first action is passive identity/port
ownership verification. Do not start a P9 physical test without its missing
fixtures. All earlier raw evidence remains preserved. Documentation source
checkpoint at this update began at `fd679334780f3bcbac3113554bd43d7e2916bdd8`
with context preflight PASS.

## Scope and preserved state

The operator authorized one C3-only EN/RST reset to diagnose the Node that the
Hub had marked offline. Before the action, the existing S3 capture and its
pre-reset snapshot were preserved in `pre_c3_reset_20261014T0815Z/`. The S3
capture was confirmed as the only reader of `/dev/ttyACM0`. No S3 reset, C3
flash, erase, repartition, recommission, security change, `usbipd attach`, or C3
USB serial probe was performed for this reset. The operator clarified that the C3 USB connection
was only supplying power and that WSL attachment is unnecessary unless a flash
is planned.

The operator confirmed the C3 reset action with `done`. The action time was not
independently timestamped in the UART capture. The first observed recovery
evidence is the Hub's authenticated rejoin at `2026-10-14T08:15:49.543439605Z`.

## Authenticated recovery evidence

The existing S3 capture at
`s3_uart_timestamped.log` records:

| UTC | Evidence |
|---|---|
| 08:15:49.543439605 | Authenticated C3 rejoin as device `c3-146393c5d158`, logical `gs114-c8`, Hub session 16. |
| 08:15:50.028801212 | Hub liveness `online=1`, `profile_known=1`, session 16. |
| 08:15:59.778409608 | RPF00 `path=PREPARED admission=OPEN`, generation 69. |
| 08:15:59.786565707 | Authenticated retirement ACK send returned `ESP_OK`, session 16. |
| 08:20:49.037122720–08:20:49.088271521 | Authenticated NodeHealth and decoded schema-3 sleep trace, session 16 / health sequence 1. |
| 08:25:48.751715908–08:25:48.806355172 | Authenticated NodeHealth and decoded schema-3 sleep trace, session 16 / health sequence 2. |
| 08:30:48.571278556–08:30:48.625590257 | Authenticated NodeHealth and decoded schema-3 sleep trace, session 16 / health sequence 3. |
| 08:35:48.410252759–08:35:48.465006359 | Authenticated NodeHealth and decoded schema-3 sleep trace, session 16 / health sequence 4. |

All four health reports show `reset=1`, `retained=0`, `pir_raw=0`, zero PIR
edges/accepted events, zero GPIO wakes, timer wake as the last wake, and no
pending event. Sleep-entry and timer-wake counts advanced together from 10 to
20 to 30 to 40. Each trace reports `gpio4_now=0`, no HIGH episodes, no sleep entries
while GPIO4 HIGH, `wake_cause=TIMER`, `radio_restore=OK`, and
`owner_resumed=1`. The health timestamps are spaced by the configured 300 s
heartbeat. No session-16 offline transition is present through the last
observation at 08:36:11 UTC. This establishes sustained authenticated Node
liveness across four heartbeat reports after rejoin.

The application reports `reset=1` through the `esp_reset_reason()` value. The
same raw value was present in session 15 before the operator action, and no C3
boot console was captured during this reset. Therefore the observed field is
recorded as raw value `1`; it is not used by itself to attribute the physical
reset source. The new authenticated session, increasing uptime (300,734 ms,
600,853 ms, 900,972 ms, 1,201,091 ms), health sequence and runtime counters establish that
the Node application restarted and is operating.

## P3 disposition and next action

No PIR motion occurred during this recovery interval; the operator is away and
unavailable for the required optical stimulus. The zero-HIGH trace is a quiet
baseline, not P3 evidence. **C8-P3 remains BLOCKED / NOT RUN.**

When the operator returns, first confirm the existing S3 capture is still
active and check for fresh session-16 authenticated health and OPEN replay
admission. If ready, request one continuous 20–30 second real AM312 movement
episode, then inspect the trace for a measured GPIO4 HIGH interval, no sleep
entry while HIGH, no wake/sleep storm, LOW recovery, normal sleep eligibility,
and correlated event/ACK/retirement outcomes. Do not repeat the motion request
if the trace cannot prove continuous HIGH; record the exact limitation.

Keep the existing C3 image, S3 commissioned state, and sole S3 capture intact.
The verified C3 application SHA-256 remains
`70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530`. The
exact active S3 application SHA-256 remains unverified; its candidate build
hash must not be called the running hash. No `usbipd attach` is needed for this
observation-only continuation. After P3 disposition, P8 is next; P9
ACK/FOTA prerequisites remain blocked, and P10 remains under GS-149.

## Capture and repository checkpoint

At the end of this observation the S3 timestamped capture was still active as
the exclusive reader of `/dev/ttyACM0` (capture owner PID 324978). The C3
native USB interface was absent while the Node was in its timer/light-sleep
cycle; this alone does not indicate failure and no new WSL attach was attempted.

Canonical repository: `/home/udaybhan/projects/Ghar_sajag_r1`; branch
`feature/r1-commercial-baseline`. Starting HEAD and remote HEAD before this
documentation checkpoint were both
`8f911ba502d44e84f9cf61cd9dca8ed9e02d1a4d`; context preflight passed as
`2026-10-13.001`. Existing untracked PWA/build-managed-component files,
historical failure reports, private/raw logs, install/selector readbacks, and
other run evidence were preserved. No source/build artifact changed.

## P3 readiness recheck — 2026-10-14 08:59 UTC

The operator is now available for the controlled movement action. The existing
S3 capture process (PID 324978) is still the sole owner of `/dev/ttyACM0` and
is configured to append to this run's `s3_uart_timestamped.log`. The process
is alive, but the capture has received no bytes after the schema-3 trace at
`08:35:48.465006359Z`; the log mtime is unchanged. Thus the capture process
ownership is intact, but current capture activity has not been demonstrated.

The latest authenticated NodeHealth is session 16 / health_seq 4 at
`08:35:48.443225859Z`; its trace reports GPIO4 LOW, no retained event, timer
wake, radio restoration OK and owner resumed. The configured heartbeat is
300 s and the offline lease is 910 s. The next health was due at approximately
08:40:48 UTC and no health, trace, event, or new RPF00 OPEN evidence followed.
The 910 s lease from the latest health elapsed at `08:50:58.443225859Z`, before
this 08:59:02 UTC check. No explicit `online=0` transition was captured, so the
evidence does not distinguish a stopped Node from an S3/runtime or observation
gap. Authenticated Node liveness is stale and cannot qualify P3 readiness.

No movement prompt was issued despite operator availability. No additional
C3 reset, WSL attach, serial probe, S3 command, flash, erase, recommission, or
power change occurred. The single previously authorized C3 reset has already
been used; keep it that way while investigating the missing heartbeat/trace.
**P3 remains BLOCKED / NOT RUN.** Retain the sole S3 reader and wait for fresh
authenticated session/health, decoded schema-3 trace and OPEN replay admission
before requesting one controlled 20–30 s AM312 movement episode. If those do
not return, identify a safe recovery action before any further reset.
