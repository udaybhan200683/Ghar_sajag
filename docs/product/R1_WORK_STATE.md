# R1 Current Work State

## GS-148 P4/P5-B1 bounded CloudSync caller checkpoint — 2026-10-14

On canonical `feature/r1-commercial-baseline`, starting local/remote HEAD
`94c2c5e29838f05d37ac15ca4342e6784ae06d16`, context preflight PASS,
the CloudSync worker gained a test-injected current Home/Hub/epoch and original
event-owner authority gate. It preserves original EventKey and generation,
requires exact backend COMMITTED via existing strict receipt handling, and
refuses completion after authority transfer. It is not wired into the S3
runtime: GS-109 commercial credential issuance/verification and target
ownership/concurrency contracts remain open, so commercial sending stays
disabled. No hardware or backend production configuration changed.

[GS-148 execution and exact resume handoff](../exec-plans/evidence/R1_GS148_P4P5_B1_20261014.md)
records source scope, prior audit, original fixture/mapping test failures,
focused checkpoint PASS (`GS148-CLOUD-WORKER-001`), framework 41/41 and mapping
20/20. Full affected component gates, backend trigger-to-caregiver E2E,
sanitizer and S3 build remain NOT_RUN for this change; do not claim product
completion or release PASS. Historical Hub migration FAIL, P0 PARTIAL and C8
physical evidence remain unchanged. Untracked GS-114 logs, managed components
and PWA assets are preserved. The next action is the affected gates and a real
backend-path integration scenario, followed by sanitizer/target build where
applicable; GS-109 authority and concurrency decisions are prerequisites for
commercial target activation. Commit and remote checkpoint are recorded in
the dated Jira GS-148 comment and Git history after this report is delivered.

The owner-requested allowance guard triggered at 17:54:53 UTC with 4% left
(reset reported at 20:54:43 UTC). Engineering paused at pushed commit
`42a89c33c37cf7ba4681422c56294b98bdcba634`; the detailed handoff-only
follow-up is in the linked report. No affected aggregate gate or target build
may be inferred from the scoped PASS.

## GS-130 bounded risk-prioritized regression checkpoint — 2026-10-14

GS-130 comment 10932 was executed in the canonical worktree on
`feature/r1-commercial-baseline`, starting at local/remote
`ed1a7dfde0299e8c84e4f12a9f1dd48dd39836ed`; context preflight PASS,
version `2026-10-13.001`. There was no competing canonical source writer.
[Focused report and resume handoff](../exec-plans/evidence/GS130_RISK_REGRESSION_20261014.md)
records scope, six added scenarios, original failures, repaired source,
per-scenario assertions, registration, receipts and exact next action.

One actual R1 blocker was reproduced and repaired in FoundationService: cached
or old explicit received-contact telemetry could resurrect OFFLINE or clear a
newer DEGRADED state. Duplicate/older and already-expired online observations
are ignored; genuinely new, still-fresh contact recovers under the existing
Node/Hub leases. Authentication, transport, EventKey, storage and target firmware
are unchanged. No new product requirement or context version is introduced.

Six permanent production-code scenarios extend existing board/health/rules/API
harnesses. Board E2E is now 10 groups / 398 checks; feature boundaries 133;
health-config 17; focused backend/durable API 17; framework 41; mapping integrity
20, with 182 rows / 205 modules / 15 physical definitions. The 78-stage registry
and local/release membership remain. Omitted/failed new cases propagate failure.
Mandatory Python discovery found six legacy invalid coverage statuses; these
are corrected to PARTIAL with an added schema regression. Physical results and
implementation fields were preserved.

Final affected gates ran at fingerprint
`11b8ce399cce108c2dc2fedede0c54e31a31a6d45df05beef8539eba3d7fe574`,
all with source unchanged. Node 23/24, Hub 39/41, contract 33/34, backend
13/14 and PWA 11/12 stages passed. **Every aggregate remains FAIL** because
of mandatory P0 `product_status=PARTIAL`; Hub additionally retains migration
`clean migration commits` FAIL. Full Python discovery is OK, 459 tests with
one declared historical classic ESP32 skip; storage ASan/UBSan PASS. Existing
P0 26 assertions plus one targeted Chromium case pass without closing its
production trust gaps. No unexpected regression remains in these receipts.

No hardware, USB/IP, reset, flash, commissioning or motion occurred. Existing
untracked PWA assets, managed components and private GS-114 logs remain intact.
Prior C8 physical results are reused: P3 catalogue remains PARTIAL for S3 image
provenance; P9 ACK/FOTA physical BLOCKED; P10 GS-149. GS-104 R01–R09, GS-89,
GS-148 production credentials, historical interval coverage, unconnected generic
backend flags, human OIDC and external provider delivery remain genuine gaps.
`validation-fast`, full browser campaign and `release-gate-final` were NOT_RUN.
The implementation/closeout commit and verified remote are recorded in the
latest Jira delivery comments and the Git checkpoint below.

Git checkpoint: implementation/tests/evidence commit
`df31bbda9e34bbd8640e232ab37ee1fe317f71d3` was pushed to the canonical branch;
`git ls-remote origin refs/heads/feature/r1-commercial-baseline` matched local
HEAD. Tracked files were clean after that push; pre-existing untracked assets
and raw hardware evidence remained. The following documentation-only closeout
records this verification; its exact final HEAD is in GS-130/GS-116 delivery
comments. Resume from actual canonical HEAD, not an older prompt checkpoint.

**Next separate task:** GS-148 P4/P5-B1 CloudSync under comments 10810/10933.
Read its active lifecycle handoff, existing caller/worker, strict receipt parser
and backend trusted ownership before implementation. Preserve exact key/time,
Home/Hub/Node/enrollment binding and durable COMMITTED-before-completion. If
production issuer/verifier authority is undefined, keep commercial sending
not-ready and surface that precise security prerequisite. GS-148 implementation
has not started; do not automatically begin unrelated work from this checkpoint.

## GS-116 / GS-130 BAT-C8 coverage integration — 2026-10-14

Task-start canonical checkpoint was local/remote HEAD
`51ffc694308b16672c68e114c74deb8c96d36037` on
`feature/r1-commercial-baseline`; context preflight PASS. The board-stack
software suite and C8 P1–P10 test mapping were audited. Detailed matrix, actual
receipts, provenance and physical limitations are in
[GS-116/GS-130 C8 coverage audit](../exec-plans/evidence/GS116_GS130_C8_COVERAGE_AUDIT_20261014.md).
The validated implementation/evidence commit is
`ab72ac2f141f32c375d9f7fe7598ef7456ce1a87`; it was pushed and origin matched
at verification. The final closeout documentation commit and remote checkpoint
are recorded in the Jira delivery comments.

The 78-stage registry currently selects 68 fast and 78 release stages, with
Node/Hub/contract ownership counts 24/41/34. Added explicit production-code
board-stack case `BOARD-TC-130-009` for the first newly qualified PIR event
after Hub reboot; the existing board stage now requires all nine case markers.
This fills a software simulation gap only. No product firmware behavior or
requirement changed.

Validation: `make validation-board-e2e` PASS, 9 groups / 358 checks;
`make battery-c8-host-test` PASS, 72 C++ + 11 Python invariants;
`make validation-framework-test` PASS, 40/40;
`make feature-coverage-test` PASS, 176 rows / 205 modules / 15 physical cases
and 19/19 tests; `make physical-hil-catalogue-test` PASS, 99 cases. Full
`validation-fast` and `release-gate-final` were not run.

The physical catalogue now maps individual GS-114 evidence: P1/P2/P4/P5/P6/P7/P8
PASS, P3 physical behavior PASS but catalogue PARTIAL because the exact running
S3 image SHA is unavailable, P9 ACK/FOTA BLOCKED, and P10 remains GS-149.
Preserved P4 q10–q12 as an unresolved failed trial and P5's per-attempt retry
key observation limitation. The historical Hub journal migration assertion
`clean migration commits` still fails; P0 `product_status=PARTIAL` is a separate
open release blocker. GS-114 stays In Progress.

No hardware was accessed. At task start, tracked files were clean. Existing
untracked PWA assets, managed ESP-IDF components and GS-114 raw logs/install
evidence remain preserved. Work completed in this task touches the board-stack
test, the existing suite registration, traceability, physical catalogue, master
validation guide and this work-state handoff. Next GS-114 physical gaps are P3
image provenance, P9 ACK-hold/signed-FOTA fixtures, and separate GS-149 P10
measurement. Do not start another major implementation from this checkpoint.

## GS-114 P9 software validation complete; physical P9 fixtures outstanding — 2026-10-14 15:31 UTC

The P9 ACK and FOTA software coverage audit is complete. Source checkpoint at
task start was local/remote HEAD
`3c677f0b6fa2ed77405cd87905f9e80b71e89fbf` on
`feature/r1-commercial-baseline`; context preflight passed. The only source
change is a permanent GS-150 host regression plus its traceability mapping;
production firmware did not change, and no hardware/serial/image/commissioning
operation occurred.

`ack_wait_sleep_transition()` exercises production NodeRuntime/HubRuntime. It
proves an unresolved authenticated Durable ACK keeps the exact event pending
and inhibits sleep beyond the 10,000 ms receive budget, then an authenticated
exact-key ACK retires the event and restores normal idle sleep eligibility.
`make gs150-host-test` PASS 1,500 checks; the focused ASan/UBSan rerun PASS
1,500 checks. Reused tests also passed: BAT-C8 72 C++ + 11 Python,
secure-FOTA adapter 2 groups, FOTA host 34, board-stack E2E 8 groups/325,
signed-FOTA fixture orchestration 16/16, and feature coverage 175 features /
205 modules / 15 physical cases (19 framework tests).

P9 disposition: **ACK software PASS / physical BLOCKED, NOT_RUN** pending a
bounded long ACK-hold or qualified directional RF fixture, target no-sleep
observation and exact-key commit/ACK/retirement evidence. **FOTA software
state-machine/host fixture coverage PASS / signed-target physical BLOCKED,
NOT_RUN** pending matched signed test/recovery images, trusted signing
provenance, authenticated trigger, and safe rollback/recovery. Host fixture
orchestration does not prove ESP-IDF target signature acceptance. Prior RPF07
and C8 P1–P8 physical PASS evidence is preserved and reused. P10 remains
separate under GS-149.

`make validation-node` and `make validation-contract` reached their registered
P0 product E2E and returned gate FAIL because P0 reports
`product_status=PARTIAL` / `physical=NOT_RUN`; the 26 P0 scenario assertions
passed. This remains an independent release gap, not a P9 failure. The
historical Hub journal migration assertion failure remains recorded and was
not reclassified here. GS-114 remains In Progress.

Evidence: [P9 software validation](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run05_software_20261014/C8_P9_SOFTWARE_VALIDATION_20261014.md), [consolidated GS-114 report](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/EXECUTION_REPORT.md).

**Next priorities after this safe GS-114 checkpoint:** follow the user-approved
sequence for GS-116/GS-130 comprehensive implemented-feature regression
coverage, then authorized GS-148 CloudSync work as product priority directs.
Do not begin either scope without its applicable explicit instruction.

## GS-114 C8-P8 physical lost-ACK PASS; S3 capture transport paused — 2026-10-14 12:12 UTC

The latest physical P8 run passed on the existing commissioned R&D pair. The
S3 app-only P8 image was installed and write-verified at the read-back active
`ota_0` slot, `0x20000`. Its app SHA-256 is
`f296c984dabda9fe537d2ae1c9d553af55287b5640b0ce34c48527dc50c369a8`; boot
reported `ce9c436f0e9a-gs114-c8p8-59b8341`. The image embeds the installed C3
app SHA-256 `70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530`.

At 12:11:57 UTC the S3 armed one-shot postcommit ACK loss. At 12:12:11 UTC it
received real PIR EventKey `p15:c3-146393c5d158n8:gs114-c8s16q14`, found its
durable outbox key under RPF00 OPEN, committed one effect (`state_changed=1`,
`records=43`), and withheld the first application ACK. Same-key deliveries
reported `state_changed=0` with unchanged record count. Authenticated Durable
ACK sends returned `ESP_OK`; NodeHealth at 12:12:13 UTC showed
`retained=0`, `durable_ack=14` (+1), `retry=15` (+2), GPIO wake, radio restore
OK and owner resumed. **P8 physical PASS.** The operator said the physical
movement preceded the direct prompt; its exact timestamp is unknown. The
prompt is not attributed as the cause of q14, and no event latency is claimed.
Full evidence is in [P8 physical run](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run04_20261014/C8_P8_PHYSICAL_20261014.md)
and its captured UART log.

A separate later ACK-drop arm was captured at 12:14:59 UTC. The operator
completed that requested movement and replied DONE, but no event/health report
followed. WSL `vhci_hcd` logs show USB/IP URB errors `-104` from 12:12:37 UTC
and the monitor later timed out on writes. The stale monitor was gracefully
interrupted and no longer owns the serial device; it has no tty fd. No further
attach, reset, flash, power operation or serial command was made. The q14
evidence predates this transport gap and remains valid. Keep all untracked raw
logs and prior evidence intact.

P3 and prior RPF07/P1/P2/P4/P5/P6/P7 PASS evidence are reused; P4's earlier
multi-key observation and P5's retry-identity observability limitation remain
documented. P9 ACK is BLOCKED because no qualified prolonged ACK-hold fixture
is available. P9 signed FOTA is BLOCKED pending matched signed test/recovery
images, trusted provenance, authenticated trigger and safe recovery. P10 is
GS-149. GS-114 remains In Progress.

**Next action:** stop hardware work at this safe checkpoint after the USB/IP
observer loss. Resume only with a fresh identified S3 capture path; do not
repeat P1–P8. Keep P9 blockers explicit and report any fixture prerequisites.
The latest source/docs checkpoint at execution start was local/remote HEAD
`fd679334780f3bcbac3113554bd43d7e2916bdd8`, context preflight PASS.

## GS-114 C8-P8 S3 app write verified; runtime boot unresolved — 2026-10-14 11:32 UTC

The operator approved the bounded S3-only P8 installation procedure. Starting
source checkpoint was local/remote HEAD
`ead9a83b9df0a1cc928280760496747f1901e38e` on
`feature/r1-commercial-baseline`; context preflight PASS. Existing untracked
assets, managed components, and earlier raw C8 logs remain preserved.

Windows reported the identified S3 CH343 (`1a86:55d3`, serial `5CBC401023`,
COM9, BUSID `3-1`) Attached. Its WSL stable by-id path mapped to `/dev/ttyACM0`.
The C3 remains the separate `0000:0002` descriptor-error device; it was not
attached, opened, reset, flashed, or recommissioned. A stale capture had an
old `/dev/ttyACM1` fd; normal TERM moved it to uninterruptible USB/IP kernel
wait, so it was not force-killed. That stale process later disappeared. The
current S3 port is now unowned; the device remained Windows Attached at the
11:32 UTC final check.

One authorized S3 ROM entry verified ESP32-S3 rev 0.2 / MAC
`7c:4f:ad:b7:2a:20`, 16 MiB flash, 8 MiB PSRAM, Secure Boot/Secure Download
disabled, and `FLASH_CRYPT_CNT=0`; no eFuse was modified. The actual table
matches the candidate table payload and preserves `ota_0`, `ota_1`,
`gs_outbox`, and `gs_state`. The valid `otadata` record selects `ota_0` at
`0x20000` (sequence 1, state 2, CRC valid).

The current-source ACK-drop S3 app was written only to `0x20000` and esptool
reported `Hash of data verified`; candidate SHA-256 is
`f296c984dabda9fe537d2ae1c9d553af55287b5640b0ce34c48527dc50c369a8`.
The expected hard reset ran. An exclusive ESP-IDF monitor with `--no-reset`
then remained attached for at least 300 seconds while USB/IP stayed Attached,
but no S3 UART bytes arrived and two read-only `FIXTURE_STATUS` attempts had
no response. Monitor closed cleanly. **The flash write is verified; S3 app
boot/running identity, fresh authenticated C3 rejoin, schema-3 NodeHealth,
RPF00 OPEN, and Durable ACK are not verified.** The silence's cause is
unknown. No further reset, recovery flash, power action, or PIR stimulus was
performed. Evidence is in [P8 installation record](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run04_20261014/C8_P8_BUILD_VALIDATION_20261014.md)
and adjacent raw logs/readbacks.

**C8-P8: BLOCKED before stimulus / physical test NOT RUN.** Do not arm
`DROP_NEXT_DURABLE_ACK` or request motion until S3 runtime/status, authenticated
C3 rejoin, schema-3 trace, and RPF00 OPEN are positively observed. Any further
reset, firmware write, or power operation requires separate authorization.
P3 controlled physical PASS and RPF07/P1/P2/P4/P5/P6/P7 PASS results remain
preserved/reused without repetition. P9 ACK/FOTA remain BLOCKED on their own
fixtures; P10 is GS-149. GS-114 remains In Progress.

## GS-114 C8-P8 candidate build checkpoint — 2026-10-14 11:07 UTC

The operator explicitly approved Python 3 for the existing ESP-IDF 6.0.3
toolchain and approved offline build/software validation; this supersedes the
earlier Python 3 restriction for this GS-114 P8 task only. The existing
`gs114-s3-c8-p8-build` builder path reuses the exact installed C3 app and
skips C3 compilation. Builder/tooling commit
`ce9c436f0e9a8324c0785bad996ed9c4a421de3d` is pushed to the canonical branch.
Context preflight passed at task startup, and no firmware source was changed
by the builder extension.

ESP-IDF 6.0.3 built an S3-only candidate with
`GS_HIL_C8_ACK_DROP=ON`, broad Hub HIL control OFF, commissioning ON, and the
16 MiB/8 MiB PSRAM fixture profile. S3 app SHA-256 is
`f296c984dabda9fe537d2ae1c9d553af55287b5640b0ce34c48527dc50c369a8`;
candidate size is 1,894,496 bytes. Its embedded Node app SHA-256 exactly
matches the installed C3 value
`70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530`.
The compiled table matches the existing `ota_0`/`ota_1`, `gs_outbox` and
`gs_state` layout; the complete build/profile and focused validation receipts
are in [P8 build evidence](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run04_20261014/C8_P8_BUILD_VALIDATION_20261014.md).
At this 11:07 build checkpoint, the S3 binary was built but not yet installed;
the later installation attempt is recorded above.

Focused results: S3 fixture suite 14/14 PASS; ACK-drop host gate 16/16 PASS;
ASan/UBSan 16/16 PASS; TSan 16/16 PASS; image and compiled-partition
compatibility checks PASS. Existing wider suites and firmware-source
sanitizer evidence are reused because product/firmware source is unchanged.

At this build checkpoint, active-slot evidence was limited to the earlier
boot banner. The subsequent actual selector readback is recorded above. The
prior record stated: the last captured S3 boot banner reports app offset
`0x20000` (`ota_0`) at 03:34:27 UTC, but reports app version
`72a223fc3b29-gs114-rpfdiag-1eec`; the exact running S3 hash and a current
post-detach selector readback remain unverified. The install plan therefore
requires a fresh exact S3 identity/active-slot check before any write and stops
if `ota_0`/`0x20000` is not confirmed. A stable S3 capture must also be
restored before a P8 stimulus. No USB/IP reattachment, reset, firmware write,
commissioning change or physical stimulus has been authorized yet. The C3
descriptor-error device remains untouched.

P3 remains controlled physical PASS; reuse RPF07/P1/P2/P4/P5/P6/P7 evidence.
P8 remains physical NOT_RUN pending explicit approval of the S3-only observer
recovery/app install plan and then a real same-EventKey retry test. P9 ACK is
blocked on a validated long ACK-hold observation fixture; signed FOTA is
blocked on matched signed test/recovery images, trusted provenance, a
supported authenticated trigger and recovery procedure. P10 remains GS-149.
GS-114 stays In Progress. Existing raw logs, generated managed components,
untracked product asset directory and historical failure evidence remain
preserved.

Next action: obtain explicit approval for the exact bounded S3-only observer
recovery and app-only install plan in the linked P8 evidence. Do not attach,
reset, write or request physical P8 motion before that approval.

## GS-114 observer checkpoint — 2026-10-14 10:08 UTC

The S3 USB/IP observer failed again after the controlled P3 PASS. Last fresh
authenticated C3 session-16 health/schema-3 trace was sequence 25 at
`10:06:33Z`, showing GPIO4 LOW, retained zero and timer wake. Windows
`usbipd-win` recorded release of the exact S3 CH343 COM9 at `10:07:57Z`
and socket abort 10053 at `10:07:58Z`, alongside WSL virtual-switch NIC
reinitialization. At `10:13:13Z`, Windows listed S3 BUSID `3-1` as Shared;
C3 remained an unknown descriptor-error USB device. WSL's S3 by-id tty and
capture PID 324978 were stale. The cause of the host socket abort remains
unproven; no post-release Node/Hub application liveness inference is made.
No board, serial or USB recovery operation was attempted. Preserve the sole
capture and commissioned state. A working, operator-approved S3 observer is
required before physical P8; the existing Python 3 build clarification also
remains open. No additional PIR motion is needed now. See [transport
evidence](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run04_20261014/S3_USBIP_CAPTURE_DIAGNOSIS_20261014.md).

## GS-114 controlled C8-P3 physical PASS — 2026-10-14 09:57 UTC

After the operator reattached the exact S3 CH343 `1a86:55d3` /
`5CBC401023`, the existing exclusive capture PID 324978 recovered on the new
WSL `/dev/ttyACM1`. No second reader, board reset or C3 USB operation was
needed. The post-gap stream at `09:49:04–09:49:06Z` showed OPEN RPF admission,
authenticated C3 session 16, health sequence 19 and schema-3 GPIO/sleep trace.
Hub uptime and C3 uptime/health progression through the gap show both target
applications continued operating. The earlier absent heartbeat and Hub
offline UART line were caused by the S3 USB/IP observation loss.

One operator-controlled real AM312 movement window was prompted at
`09:50:56.473Z`, DONE at `09:51:50.807Z`. The authenticated trace measured one
continuous GPIO4 HIGH episode of **28,518 ms**, 1,425 additional HIGH sleep
inhibitions, no sleep entry with GPIO4 HIGH, one additional GPIO wake and one
qualified PIR event. Hub EventKey
`p15:c3-146393c5d158n8:gs114-c8s16q2` produced one durable logical effect;
same-key retry produced none. Authenticated Durable ACK was sent, C3 durable
ACK count increased once and retained events stayed zero. The
`09:56:40.800–09:56:40.855Z` health/trace showed GPIO4 LOW, 11 additional
sleep entries and timer wakes, last wake TIMER, radio restore OK and owner
resumed. **C8-P3 physical behavior PASS.** Historical P3 windows remain
separate. See [case evidence](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run04_20261014/C8_P3_CONTROLLED_20261014.md).

The exclusive capture later recorded separate q3 `MOTION`, q4
`MOTION_SUMMARY` and q5 `MOTION` keys at `09:58:48–10:01:33Z`, after the
controlled run and the `09:56:40Z` LOW/timer-recovery sample. Three additional
short GPIO4 HIGH episodes were authenticated. Each key produced one durable
effect and ACK; the physical cause of this later activity is unknown. It is
preserved separately from the q2 P3 stimulus, with no inferred false-alarm
finding.

The C3 installed app SHA-256 remains verified as
`70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530`.
Exact *running* S3 app hash remains unverified; its source-matched candidate
hash must not be labeled as installed. This is a release-provenance gap. The
only active capture is S3 PID 324978 on the stable CH343 by-id path, currently
`/dev/ttyACM1`; its raw log remains untracked/preserved. The C3 USB descriptor
error is irrelevant to the observed authenticated ESP-NOW liveness and was
not probed. No image, commissioning, power or security state changed.

RPF07/P1/P2/controlled P4/P5/P6/P7 physical PASS evidence remains reused.
P8 physical lost-ACK is next: current S3 diagnostic build has
`GS_HIL_C8_ACK_DROP=OFF`; the existing older ON image is not source-matched.
Prepare a new exact image before requesting installation authorization. The
operator's earlier Python 3 restriction is being clarified before any
ESP-IDF rebuild. P9 ACK/FOTA remain independently BLOCKED on their fixtures;
P10 is GS-149. GS-114 stays In Progress. Current source branch
`feature/r1-commercial-baseline`; source at P3 test was
`d18ed3e52d61a4f0f33f563eceb84f1d2f2294fb` (local/remote matched at
start); context preflight PASS `2026-10-13.001`. Existing untracked files and
raw evidence remain preserved.

## GS-114 S3 USB/IP capture root-cause checkpoint — 2026-10-14 09:40 UTC

The apparent loss of C3 NodeHealth after `08:35:48Z` is an **observation
gap**, not evidence that either application stopped. Windows `usbipd-win`
recorded a transport socket abort (10053) and release of the exact S3 CH343
adapter `1a86:55d3` / `5CBC401023` at `08:37:43Z`, before the next C3
heartbeat was due. Windows now shows S3 BUSID `3-1` `Shared`; WSL retains a
stale `/dev/ttyACM0` and by-id link. The exclusive S3 capture PID 324978 has
received no bytes since `08:35:48Z`. One allowed `FIXTURE_STATUS` attempt
blocked while opening its stale fd and sent no command bytes; no further
serial request is safe on this attachment. Windows also shows C3 USB as
descriptor-error `0000:0002`; this does not prove C3 radio/app state.

The Hub's source checks liveness every 1000 ms against the authenticated
910-second lease. Its missing `online=0` UART line is explained by the broken
S3 observer. C3 health scheduling and sleep deadlines were inspected; no
firmware liveness defect is established. Nearby Windows WSL virtual-switch
events support a host transport disruption; its initiating cause remains
unproven. No firmware source/image, board power, commissioning or security
state changed. The prior one-time C3 reset authorization is exhausted.

Current safe action is S3-only observer recovery after explicit authorization:
account for the stale capture/writer, reverify the exact CH343 serial identity,
reattach only that identified S3 adapter to WSL, establish one fresh reader,
and verify authenticated C3 health/schema-3 trace and OPEN replay admission.
Do not request PIR motion or infer P3 readiness before those observations.
Do not attach the C3 descriptor-error device. P3 remains BLOCKED / NOT RUN;
P8 physical NOT_RUN; P9 ACK/FOTA BLOCKED. Prior RPF07/P1/P2/controlled
P4/P5/P6/P7 physical PASS evidence remains valid and is not being repeated.
P10 remains GS-149. See [diagnostic evidence](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run04_20261014/S3_USBIP_CAPTURE_DIAGNOSIS_20261014.md).

Local and remote HEAD at investigation start were both
`cec251a96b30ca85ed1b256162b2a3f47317258b` on
`feature/r1-commercial-baseline`; context preflight PASS
`2026-10-13.001`. Untracked raw logs, generated components and unrelated
assets remain preserved. Exact running S3 binary hash remains unverified; the
previously verified installed C3 app SHA-256 remains
`70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530`.

## GS-114 P3 readiness recheck — 2026-10-14 08:59 UTC

The operator is available for the single controlled P3 movement episode, but
the physical fixture is not ready. Existing S3 capture PID 324978 remains the
sole reader/owner of `/dev/ttyACM0`, configured to append to the run04 log.
The process is alive, but the log has no bytes after the authenticated
session-16 health_seq-4 trace at `08:35:48.465006359Z`; current capture activity
is not proven.

Latest authenticated NodeHealth: session 16 / health_seq 4 at
`08:35:48.443225859Z`; its schema-3 trace reports GPIO4 LOW, no retained event,
timer wake, radio restoration OK, and owner resumed. Configured heartbeat is
300 s; a new report was due around 08:40:48 UTC. No later authenticated health,
trace, event or RPF00 OPEN line was captured. The 910 s lease elapsed at
`08:50:58.443225859Z`. No explicit `online=0` transition is present, so the
evidence does not identify whether the Node, Hub runtime or observation path
stopped. Authenticated liveness is stale and P3 must not start.

No movement prompt, port probe, fixture command, USB/IP attach, reset, flash,
erase, recommission or power change occurred. The one authorized C3 reset has
already been used. Keep the existing S3 reader and commissioned pair intact;
continue passive observation for fresh authenticated liveness, schema-3 trace
and OPEN replay admission. If none returns, identify a safe recovery action
before any further reset. P3 remains BLOCKED / NOT RUN. Preserve prior RPF07,
P1, P2, controlled P4/P5, P6 and P7 physical PASS evidence. P8 follows after
P3; P9 remains fixture-blocked; P10 belongs to GS-149.

Checkpoint: `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`, local and remote HEAD
`e4e036a5d3c92bd7d53ce478a5d4e8099cc957b9`; context preflight PASS
`2026-10-13.001`. Existing untracked raw logs, readbacks, generated
components and unrelated assets remain preserved. No source/image changed.
The verified C3 app SHA remains
`70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530`; exact
active S3 app SHA remains unverified.

## GS-114 controlled C3 reset recovery — 2026-10-14 08:31 UTC

The operator authorized and completed one C3-only EN/RST reset after the
pre-reset S3 UART snapshot and log were preserved. No new `usbipd attach`, C3
USB serial probe, flash, erase, S3 reset, recommission, or security change was
performed. The user clarified that USB is currently only providing C3 power;
WSL attachment is unnecessary unless a flash is planned.

The existing exclusive S3 capture observed authenticated C3 rejoin as session
16 at `08:15:49.543439605Z`, online liveness at `08:15:50.028801212Z`, RPF00
`PREPARED admission=OPEN` at `08:15:59.778409608Z`, and an authenticated
retirement ACK send of `ESP_OK` at `08:15:59.786565707Z`. Authenticated
NodeHealth/schema-3 traces then arrived at `08:20:49.037–08:20:49.088Z`,
`08:25:48.751–08:25:48.806Z`, `08:30:48.571–08:30:48.626Z`, and
`08:35:48.410–08:35:48.465Z` (health_seq 1–4), matching the configured 300 s
heartbeat. Across these reports, retained
events stayed at zero, GPIO4 stayed LOW with no PIR edges or GPIO wakes, timer
sleep/wakes advanced 10→20→30→40, radio restoration was OK, owner resumed, and no
session-16 offline transition appeared by `08:36:11Z`. This verifies
post-reset application operation and sustained authenticated liveness. The
raw health `reset=1` is retained without using it alone to attribute reset
source: the same value was present before reset, and no C3 boot UART was
captured.

**P3 remains BLOCKED / NOT RUN.** The operator is currently away and no PIR
motion was performed; the quiet GPIO4 trace is only a baseline. When the
operator returns, preserve the current S3 capture and commissioned state,
recheck fresh health/admission, and request one 20–30 s real AM312 stimulus
only when ready. If continuous HIGH cannot be proved, retain BLOCKED. After
P3, P8 is next. P9 ACK/FOTA remain blocked on their fixture/signing
prerequisites; P10 remains separate under GS-149. Previously qualified RPF07,
P1, P2, P4, P5, P6 and P7 evidence remains reused.

Evidence: [C3 reset recovery and P3 handoff](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run04_20261014/C3_RESET_RECOVERY_AND_P3_HANDOFF_20261014.md)
and the live S3 capture
`docs/hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run04_20261014/s3_uart_timestamped.log`.
At this checkpoint canonical branch is `feature/r1-commercial-baseline`,
starting HEAD and remote both
`8f911ba502d44e84f9cf61cd9dca8ed9e02d1a4d`; context preflight PASS
`2026-10-13.001`. Existing untracked evidence and unrelated assets remain
preserved. The S3 capture remains the sole reader of `/dev/ttyACM0` (PID
324978); no port operation is required for this
observation-only work.

## GS-114 P3 readiness checkpoint — 2026-10-14 07:55 UTC

The requested P3 motion window was not performed, per operator confirmation;
it is not a physical test. No movement prompt was repeated. Read-only checks
showed local `HEAD` and `origin/feature/r1-commercial-baseline` both at
`27974e0759ac2aadf9886aaeb202d85dcd5998fe`, tracked worktree clean, and
context preflight PASS (`2026-10-13.001`). Existing unrelated untracked assets
and private/raw evidence remain untouched.

The active S3 capture is still PID 324978, the sole owner of `/dev/ttyACM0`
(stable S3 by-id path); its output is the run04 S3 log, whose last line is the
read-only `FIXTURE_STATUS state=idle` at `06:58:28.214244408Z`. No later S3
UART evidence has been captured. C3's stable by-id path resolves to
`/dev/ttyACM1`; sysfs still identifies USB `303a:1001`, serial
`14:63:93:C5:D1:58`, with runtime status `active`, and no process owns ACM1.
This confirms USB enumeration only, not a running or authenticated Node.

The newest authenticated C3 evidence remains session 15 / health_seq 1 at
`06:37:24.484466352Z`, with its schema-3 sleep trace at
`06:37:24.506002952Z`. The Hub marked session 15 offline at
`06:52:38.225783443Z`. The configured heartbeat is 300 seconds and offline
lease is 910 seconds; the lease has expired with no subsequent authenticated
NodeHealth, rejoin or event. Therefore **P3 remains BLOCKED / NOT RUN** and the
fixture is not ready for physical motion. No reset, port probe, flash, command
or commissioning operation was performed. The exact active S3 binary hash
also remains unverified; its candidate build hash must not be represented as
the installed hash.

Next action: recover C3 authenticated liveness through a separately authorized
safe action while preserving the commissioned state and exclusive S3 capture.
Only after fresh authenticated NodeHealth, current schema-3 trace decoding and
OPEN admission are observed should the single controlled 20–30 second P3
movement request be made. P8 remains the subsequent priority; P9 ACK/FOTA
remain blocked on their specific fixtures, and P10 remains GS-149.

## GS-114 C8 resume checkpoint — 2026-10-14 07:18 UTC

Canonical path `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`; execution source is `c69960fb064a60c3e6dc52b27d90fbbbe30b560a`.
At the start of this checkpoint update, documentation/evidence commit
`81f4407afa824de8b63b3e5ba27bbf175ffa8604` matched `origin`; context preflight
PASS `2026-10-13.001`, and the tracked worktree was clean. Existing untracked
PWA assets, generated managed components, old failure reports, private logs
and run04 binary/log evidence remain preserved. No destructive Git operation
or firmware/source rebuild occurred.

Windows reports only the intended fixtures attached: C3 `BUSID 3-3`,
`303a:1001`, COM4; S3 `BUSID 3-1`, `1a86:55d3`, COM9. WSL stable links resolve
to C3 `/dev/ttyACM1` (USB serial `14:63:93:C5:D1:58`) and S3 `/dev/ttyACM0`
(USB serial `5CBC401023`). The exclusive S3 capture is PID 324978 and owns
ACM0; ACM1 was unowned. No `usbipd attach` or competing serial probe was used.

The already-built c699 ESP-IDF 6.0.3 pair was hash-verified. C3 application
`70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530` was
installed app-only at verified active `ota_0` offset `0x20000`; esptool
reported write verification success and partition/otadata reads confirmed
`ota_seq=1`. NVS, commission, event data, security state, partition table and
other OTA metadata were preserved. The C3 later authenticated under Hub session
15 and delivered NodeHealth schema 3 with the physical GPIO/sleep trace. The
S3 log proves trace decoding and a valid `FIXTURE_STATUS` response, but its
exact active binary hash was not read back; the built S3 candidate is
`ca178fe30cc620d3fe0cb5817da9d8a98b07b70cb5f7c443045c85180dd46379`.

At 06:52:38Z the Hub marked Node session 15 offline after missed health. A
06:58:28Z `FIXTURE_STATUS` returned `idle`. No later authenticated NodeHealth,
GPIO trace or event was captured during the requested P3 movement window, and
operator completion was not confirmed. Do not count it as a controlled test or
PASS. No additional physical reset/reflash/recommission is justified yet.

Evidence reuse ledger: RPF07 PASS; P1 PASS; P2 PASS; P4 controlled q16 retest
PASS (retain the earlier q10–q12 multiplicity); P5 controlled outage/recovery
q24 PASS (retain retry-key observability limitation); P6 PASS; P7 q22 PASS.
The diagnostic change is bounded HIL telemetry, and these prior behaviors were
not repeated. P3 remains BLOCKED on controlled high/low evidence; P8 remains
physical NOT_RUN because the active c699 Hub profile has
`GS_HIL_C8_ACK_DROP=OFF` and the available ACK-drop image is from an older
source checkpoint; P9 ACK/FOTA remain BLOCKED on distinct fixture/signing
prerequisites. P10 remains under GS-149.

Next action: wait for the operator's completion of the already-requested P3
stimulus; no DONE confirmation has arrived. If the motion occurred, inspect
the existing S3 log before any new stimulus. If no authenticated data appeared
after confirmed movement, preserve that first failure and diagnose Node
wake/rejoin before asking for any reset or additional motion.

P8's current-source S3 image is not available: the c699 Hub build has
`GS_HIL_C8_ACK_DROP=OFF`, and the older ACK-drop artifact is not source-matched.
The registered `gs114-s3-rpf-diagnostic-build` Make target invokes
`python3 scripts/build_gs114_fixture_pair.py`; respecting the operator's
instruction not to use Python3, no rebuild or flash was attempted. P8 requires
a supported build path that avoids Python3 or a changed operator constraint,
then exact image/slot verification before any installation. P9 ACK/FOTA remain
blocked on their fixture/signing prerequisites. No P1/P2/P4/P5/P6/P7 retest,
broad suite rerun or FOTA operation is justified at this checkpoint.

Jira GS-114 comment 10873 records the install/trace milestone. The consolidated
documentation commit `81f4407afa824de8b63b3e5ba27bbf175ffa8604` was pushed and
remote-verified. GS-114 remains In Progress; do not start GS-116/GS-130.

## GS-114 C8 resumed execution checkpoint — 2026-10-14 05:20 UTC

Canonical path `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`, starting HEAD `988fa44ee1207ed67a3a253a5eb2c9dc7813277b`;
context preflight PASS `2026-10-13.001`. The source/evidence modifications
listed by `git status` are uncommitted; prior untracked P5 evidence, private
historical logs, ignored target builds, PWA and generated managed components
remain preserved. No destructive Git or hardware operation occurred in this
checkpoint.

The physical pair remains commissioned on C3 app
`1df36cd1a7c779869ea439f2b1e1e45e599c136fd6957ebb59a129870288b814` and S3 app
`84358b7deab37c1c66aab3fd134fb23dffd6f497493b806c27accb6b19f56df7`. Stable
paths remain C3
`/dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_14:63:93:C5:D1:58-if00`
and S3
`/dev/serial/by-id/usb-1a86_USB_Single_Serial_5CBC401023-if00`. The sole S3
reader is PID 302734 and owns only S3; no C3 reader is open. USB-only power and
AM312 3.3 V/GND/GPIO4 remain the previously operator-confirmed arrangement.
No board has yet received the trace image.

P5 run03 now PASSes: during Hub-only USB outage the real AM312 event q24 was
retained, then admitted once after authenticated session-6 rejoin with RPF00
OPEN; Hub durable state changed once, Durable ACK send succeeded, and NodeHealth
confirmed reset unchanged, retained=0 and durable_ack +1. Retry identity is
inferred from the single new pending event because the C3 native USB console is
silent in light sleep; preserve that limitation and the earlier run02 capture
gap. P6/P7, P1/P2 and controlled P4 retest remain PASS on the installed pair;
P3 remains BLOCKED pending GPIO4 HIGH/sleep trace; P8 remains physical NOT_RUN;
P9 ACK/FOTA remain fixture-blocked; P10 remains separate under GS-149.

A TEST_INFRA_ONLY observer is implemented: C3's `GS_BAT_C8_PHYSICAL_WAKE`
profile records sampled GPIO4 HIGH episodes, sleep inhibition/race counts,
entry/wake GPIO levels, radio restore and owner resume in an optional bounded
authenticated NodeHealth schema-3 trace. The S3 commissioning fixture prints
the trace. Normal C3 builds exclude the recorder object and owner-resume call.
Node/Hub/contract registered component stages pass, including 1,483 C++ checks,
72 BAT-C8 checks and Hub storage ASan/UBSan. Aggregate gates exit 1: Node and
contract on P0 `product_status=PARTIAL`/physical `NOT_RUN`; Hub also retains the
known `hub-journal-migration-host-test` failure (`clean migration commits`).
None is described as a full-gate PASS.

Next exact action: commit and push only the scoped source, test mapping and
current GS-114 evidence updates; build the source-matched C3/S3 commissioning
pair with ESP-IDF 6.0.3 and verify the complete profile/hash manifest. Then
stop PID 302734 after preserving its final log, verify exact chips/MAC/flash and
ownerless stable ports, flash only the authorized two R&D fixtures, restart one
S3 capture, and run P1 then P3 with actual AM312 motion. Do not claim P3 until
authenticated trace shows HIGH/inhibition and LOW recovery without a HIGH sleep
entry, reset or wake storm. GS-114 stays In Progress.

## GS-114 resumed C8 execution checkpoint — 2026-10-14 03:58 UTC

Controlled P7 now PASSes. The operator performed one real AM312 movement
episode during the requested window after Hub-only reboot. Hub booted at
03:34:27.008Z, authenticated Node rejoin advanced to session 4, and RPF00
admission remained OPEN. First post-reboot key q22
`p15:c3-146393c5d158n8:gs114-c8s1q22` produced one durable logical effect;
two same-key retries were idempotent. Authenticated retirement ACK send
returned `ESP_OK`; NodeHealth at 03:57:15.413Z confirmed reset=11, retained=0,
durable_ack=22, pir_ok=27 and gpio_wakes=27. P6 also PASSes with the full S3
boot banner captured. See [GS-114 P6](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run03_20261014/C8_P6.md)
and [GS-114 P7](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run03_20261014/C8_P7.md).

P5 remains BLOCKED/inconclusive from its prior capture gap and is next for a
controlled retest using the existing reconnect-aware exclusive S3 reader.
P3 remains BLOCKED for direct GPIO4 HIGH/sleep-inhibition evidence; P4 passes
on its controlled retest while the earlier q10–q12 multi-key result remains
unexplained. P1/P2 PASS. P8 is still physical NOT_RUN pending installation of
the isolated ACK-loss image set after exact-device/profile verification; P9
ACK-window and signed FOTA subcases remain blocked by missing fixtures/images.
RPF07 physical retest remains PASS. No source/image change, reset, reflash or
recommission occurred in this checkpoint. GS-114 remains In Progress; GS-149
P10 current measurement and other GS-146 evidence remain separate.

## GS-114 resumed C8 execution checkpoint — 2026-10-14 03:25 UTC

The R&D pair remains on its existing commissioned images; no source/image
change, reset, reflash or recommission occurred. The operator completed another
continuous real-motion P3 attempt. Hub events q17–q20 were four distinct keys,
each durably accepted once, same-key deduplicated, and ACKed. Authenticated
NodeHealth at `2026-10-14T03:25:04.945156252Z` (session 3, health_seq 120)
reported reset=11, `pir_raw=0`, retained=0, durable_ack=20, pir_ok=25,
gpio_wakes=25, sleep_entries=1273 and timer_wakes=1248. Relative to health_seq
119 before the stimulus, GPIO wakes and accepted PIR events each increased by
four, while sleep entries increased by 14 and timer wakes by 10.

P3 remains BLOCKED for held-HIGH sleep-inhibition qualification: C3 native USB
UART/direct GPIO4 did not expose HIGH during movement, and aggregate counters
cannot identify sleep entries relative to the pin level. Post-stop LOW and
timer/sleep recovery are observed. Four distinct EventKeys during continuous
movement are preserved as unexplained physical event multiplicity, not
same-key duplicate effects. See [C8-P3 evidence](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run03_20261014/C8_P3.md).

Current physical statuses: RPF07 PASS; P1/P2 PASS; P3 BLOCKED; P4 controlled
retest PASS with the original q10–q12 failure retained; P5 BLOCKED/inconclusive;
P6 PASS; P7 requires a new Hub-only reboot followed by a controlled first real
motion; P8 physical NOT_RUN; P9 ACK/FOTA BLOCKED. P5 requires a reconnect-capable
exclusive S3 log reader before Hub power removal; the existing reader does not
reopen after USB disconnect. Preserve installed image hashes C3
`1df36cd1a7c779869ea439f2b1e1e45e599c136fd6957ebb59a129870288b814` and S3
`84358b7deab37c1c66aab3fd134fb23dffd6f497493b806c27accb6b19f56df7`. No C3
reader is active. Keep GS-114 In Progress; P10 remains separate under GS-149.
Next, repeat the Hub-only P6 reset needed to establish a fresh controlled P7
first-event window, then run P7 after authenticated rejoin. Before the later P5
Hub power-removal test, replace the S3 observer with a reconnect-capable single
reader and verify the replacement does not reset the Hub.

## GS-114 resumed C8 execution checkpoint — 2026-10-14 03:13 UTC

Canonical path `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`; run03 code checkpoint
`72716c141a788b251e6b630f4684df12028ea847`. q15/q16 evidence and handoff
updates were committed and pushed as `610c3f3d754ef647d9b0ab0faa284b0465928470`,
`9664b4b9848a67f290dabfe2108c8dd06051675c`, and
`0ae61bd2234da0af8fb1a636cc58f4ef4380347d`; local and remote matched at the
last verified checkpoint. Context preflight passed `2026-10-13.001`. The
tracked tree was clean after those commits. Existing untracked PWA,
managed-component and historical physical-evidence paths remain preserved.
The untracked raw S3 capture was owned by reader PID 283926 at 03:06 UTC. No C3
reader was present at that check; do not open another S3 reader or stop the
active capture.

The installed C3/S3 pair remains unchanged and commissioned. Authenticated
NodeHealth at `2026-10-14T02:53:43.472786229Z` was Hub session 3 / health_seq
115, reset 11, retained 0, durable ACK 14, accepted PIR 19, GPIO wakes 19,
sleep entries 1212, timer wakes 1193, last wake TIMER. The first physical
GPIO/PIR-path event after the Hub reboot was q15
`p15:c3-146393c5d158n8:gs114-c8s1q15`; it was durably accepted once, same-key
deduplicated and ACKed. NodeHealth at `02:58:47.560721096Z` (health_seq 116)
confirmed retained=0 and durable_ack/pir_ok/gpio_wakes each incremented once.
The event's external physical trigger and GPIO assertion time are unknown, so
P7 remains BLOCKED for controlled stimulus attribution/timestamp evidence. To
run the controlled first-event P7 case requested by the owner, repeat Hub-only
P6 and then generate the first real PIR event after that reboot; q15 itself
already consumed the first-event position after the previous P6.

The operator performed one brief controlled movement for the P4 retest after
the q15 chain had completed. q16
`p15:c3-146393c5d158n8:gs114-c8s1q16` produced one authenticated Hub durable
effect, same-key duplicate suppression, successful Durable ACK and authenticated
Node retirement; NodeHealth at `03:05:23.259112457Z` (health_seq 117) confirmed
retained=0, durable_ack=16, `pir_ok=21`, `gpio_wakes=21`, reset=11. No extra key
appeared during the three-minute post-DONE quiet window. P4 controlled retest
PASS; retain the original q10–q12 multi-event FAIL and its unresolved cause.
No source/image change, reflash or reset occurred.

While waiting, ESP-IDF 6.0.3 built the matched P8 target pair offline under
`code/build/gs114_c8_p8_20261014/`. C3 app SHA-256 is
`5256779c8c0b592cea219f3e3a3d0c7da72892a37207399bfce388e549c25659`; S3 app
SHA-256 is `f94192a7c59fa1a7221a7dc4a8394c1bd8c448c2009553e35dfed2f074eccd08`.
The S3 profile uses `GS_HIL_CONTROL=OFF`, commissioning ON, isolated P8 ACK-drop
ON, 16-MiB flash, octal PSRAM configuration, and `ota_0`/`ota_1`/`gs_outbox`/
`gs_state`. Both builds exited 0; `make -C code c8-ack-drop-gate-host-test`
passed 16 checks. Neither image was flashed. Offline image-info checks matched
the C3/4-MiB and S3/16-MiB target types and verified checksums. The S3 fixture
profile suite passed 12/12; traceability passed for 175 features/205 modules/15
physical cases and its 19 tests passed; the physical catalogue check passed for
99 cases with no device access. An attempted `make -C code validation-hub` was
stopped before `host-build` could invoke Python per the user's instruction; its
16-check ACK-drop gate and 12-check S3 fixture-profile stage passed, but the
Hub validation target is incomplete (exit 130), not PASS. Full artifact/profile
hashes and commands are recorded in the [GS-114 P8 target evidence](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run03_20261014/C8_P8.md).

Physical dispositions: RPF07 PASS, P1 PASS, P2 PASS, P3 BLOCKED, P4 PASS on
controlled retest (initial trial FAIL retained), P5 BLOCKED/inconclusive, P6
PASS, P7 BLOCKED for missing controlled stimulus attribution/timestamp after
q15's observed and retired first post-reboot event, P8 physical NOT_RUN, and P9
ACK/FOTA BLOCKED. P8 installation requires presenting the exact prepared
image/partition hashes for operator confirmation before flashing; no P8/P9
image has been installed. The next physical case is P3, which needs a real
sustained-HIGH stimulus and an authenticated NodeHealth sample during the
episode; the current P3 evidence remains blocked without a verified high-level
interval. Keep GS-114 In Progress; P10 remains separate under
GS-149. Jira GS-114 comment 10862 records q15 retirement, the q16 controlled P4
retest and both evidence commits. GS-114 remains In Progress; no issue workflow
status changed.

## GS-114 resumed software checkpoint — 2026-10-13 UTC

Jira GS-114 comment 10800 and the pause handoff were reconciled. Canonical
local and remote HEAD were both `93935e345a29e3b119f460fda5e9294477b6f798`
at resume, branch `feature/r1-commercial-baseline`; preflight PASS. All
uncommitted repair work and prior evidence were preserved. The old stuck S3
esptool process exited, but neither `/dev/ttyACM0` nor `/dev/ttyACM1` exists
in WSL. No port was reopened or hardware operation performed on resume.

All nine repair artifacts have matching byte size and SHA-256; the repair
manifest was corrected to reflect the actual 1,889,280-byte S3 app and its
embedded new C3 image. `make validation-hub` completed: 38/40 stages PASS;
the known journal migration test FAIL and product P0 `PARTIAL` classify the
gate FAIL (exit 2). Affected checkpoint, fresh-install, board-stack, storage
correctness and sanitizer stages PASS. `make validation-contract` completed
33/34 stages PASS; only product P0 `PARTIAL` makes that gate FAIL (exit 2),
while its contracts and affected component stages PASS. Both receipt reports
are identified in the execution handoff.
Physical repair retest and P1–P4 remain NOT_RUN/BLOCKED pending restored USB,
renewed exact-board identity/power/wiring checks and the operator's requested
pre-flash confirmation of the repaired image hashes. See the
[consolidated GS-114 execution handoff](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/EXECUTION_REPORT.md).


## GS-114 paused at physical repair checkpoint — 2026-10-13 UTC

The operator requested a logical pause before the session limit. The canonical
worktree remains `/home/udaybhan/projects/Ghar_sajag_r1` on
`feature/r1-commercial-baseline`; starting local HEAD was
`93935e345a29e3b119f460fda5e9294477b6f798`, with no branch switch or
destructive Git operation. Context preflight PASS `2026-10-13.001`. The existing
nine unrelated untracked entries and prior failure evidence are preserved.

The exact authorized C3 (`14:63:93:c5:d1:58`, 4 MiB, COM4/ttyACM0) and S3
(`7c:4f:ad:b7:2a:20`, 16 MiB/8 MiB PSRAM, COM9/ttyACM1) were ROM-identified,
clean erased, flashed and verified with the original manifest. Both booted;
`GET_TEST_QR` → `COMMISSION_EXPECTED_NODE` produced authenticated rejoin,
session 2. At 12:04:48.028 UTC the fresh S3 closed admission with `RPF07
SELECTED_CHECKPOINT_MISSING`. Phase A therefore FAIL; P1–P9 have no current
physical PASS. The [execution report](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/EXECUTION_REPORT.md)
contains redacted first-failure logs and the verified install receipts.

A scoped Hub owner-cache refresh fix and production-code regression are in the
canonical tree. Focused checkpoint and fresh-install host tests, feature
coverage, target C3/S3 fixture build and `git diff --check` PASS. The full
`validation-hub` run was stopped for this pause after reproducing the known
`hub-journal-migration-host-test` failure; it is not a gate PASS. Rebuilt repair
images (C3 `89b01dfa9c6b48d8430f5427f7f9f89a69b46330280f56923a73a093ffa73da6`,
S3 `c7d63a9959b5df812cae14eb92edc4c18044608a7851fef54f55e8aea7e9a4a6`)
are hash-checked but **not installed**. No repair erase/write occurred.

At pause, a read-only S3 `flash-id` probe was hung in uninterruptible kernel
I/O after its parent was terminated. S3 runtime state must be treated as
unknown; do not infer stable serial observation or start qualification from
this point. Next action on resume: check that probe/USB state first, then
reidentify both exact chips/ports and image/profile hashes, perform the
authorized controlled repair installation if safe, recommission with the
supported fixture APIs, and physically retest healthy replay-fence admission
and reliable dual logs before P1–P4. Preserve separate P5–P9 operator
checkpoints. GS-114 stays In Progress; GS-149/GS-146/GS-115 remain dependent.

The older GS-114 sections below describe prior checkpoints; this section is
the current pause/resume state.

## GS-114 clean R&D execution — 2026-10-13

Active task: actual C8 P1–P9 on the existing commissioned R&D pair, under
GS-114 comment 10732 and the user's execution instruction. Old experimental
flash, enrollment and pending events may be deliberately erased/recommissioned.
Earlier preservation-first gates below are superseded for these two fixtures;
previous redacted failure evidence remains preserved. No spare pair is needed.

Startup canonical/local/GitHub HEAD `5ee96fd24b4a82b2a11b928cb40f2638eaee9616`,
branch `feature/r1-commercial-baseline`; tracked clean, original nine untracked
entries preserved; context PASS `2026-10-13.001`. GS-148 Option A and GS-150
source/artifacts reconciled without repeating their completed campaigns.
Current fingerprint `c07ae9a0cb79491379d4de65f6c83d7b31b3c0d7613bc3d9e2f912c2c1fcce83`
matches the retained commissioning-compatible C3/S3 fixture build. Full
bootloader/partition/otadata/app hashes and fresh blank outbox are recorded in
[the execution report and preparation manifest](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/EXECUTION_REPORT.md).
ESP-IDF 6.0.3/esptool 5.4.0 activated; offline image/profile/partition checks and
host mount of the component-pinned empty LittleFS image PASS. No runtime source
change, release/current campaign or repeated GS-148 fault injection.

After the operator reported "boards connectd", read-only OS inventory matched
C3 USB serial `14:63:93:C5:D1:58` at `/dev/ttyACM0` (COM4, BUSID 3-4) and
S3 UART serial `5CBC401023` at `/dev/ttyACM1` (COM9, BUSID 3-1), both attached
to WSL, with no other serial reader. Actual silicon/MAC/security, present safe
power and AM312 wiring still need confirmation. **No port opened, probe/reset,
erase/write, commissioning or physical test yet.** Exact Phase A confirmation
requested under user section 3.6 / GS-114 10732; P1 NOT_RUN, P2–P9 BLOCKED.

Next: confirm exact board/power/wiring/Phase A operation, probe identities and
security on the stable named interfaces, stop on mismatch; then supervised clean
erase/write/verification, boot and test-only secure commissioning. Establish
stable independent timestamped capture before actual P1–P4 motion. A documented
setup reset is permitted; unexpected measurement resets are failures. P5–P7
power/reboot, P8 postcommit ACK loss/per-key ledger and P9 signed FOTA require
their separate operator checkpoints. Prior USB reset/replay-fence faults remain
unresolved historical regressions; clean fresh-install evidence cannot prove
recovery of the discarded old state. GS-114 stays In Progress; GS-149/GS-146 and
measured GS-115 decisions remain separate, with no invented current/endurance.

## GS-114 C8 physical readiness — 2026-10-13

Historical offline checkpoint, superseded only where GS-114 10732 and the active
clean R&D execution above remove experimental-state preservation prerequisites.

Offline review at canonical/GitHub `ca87e2cd058586d9c7231df9ab313c4b237f8085`,
context preflight PASS, found current source-matched C3/S3 fixture binaries and
RPF00–RPF08 but no installed-image/storage provenance, verified non-resetting
C3 observer, safe state-preserving S3 app installation, or healthy physical
replay-fence admission. The saved run stopped on `USB_UART_CHIP_RESET` and
`admission closed`; no second spare pair is confirmed. [The dated readiness
report](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_PHYSICAL_READINESS_20261013.md)
defines a preferred separately confirmed disposable-pair route and gated
fallback for the commissioned fixture. **NO-GO** for P1–P9 now; P1 NOT_RUN,
P2–P9 BLOCKED. Next action is separate approval for identified-fixture
power-off visual inventory; no physical action, software rebuild, flash or
serial access occurred here. GS-114 stays In Progress; P10 remains GS-149.

## GS-148 Option A software delivered — 2026-10-13

GS-148 10688/10690 and GS-145 10689 approve bounded native-v1 recovery and
software validation. GS-D033 locks corrected recovery in both supported S3
images; exact signed pair and physical OTA remain pending. Start baseline local
and actual GitHub `19ec67c365e1bdea8fce61fb46f481f407fa42b9`, canonical branch,
tracked clean, nine preserved untracked entries. Other observed session writes
only separate dashboard worktree; canonical writer is exclusive for GS-148.
Context updated to `2026-10-13.001` for the approved policy before source work.
[Implementation handoff](../exec-plans/evidence/R1_GS148_OPTION_A_20261013.md)
records exact source, 59 primary fault cuts, 24 authority negatives, 22 actual
old/corrected reader checks, real C3/S3/API projection, ASan/UBSan, framework
and source-traceability PASS. Frozen fingerprint
`c07ae9a0cb79491379d4de65f6c83d7b31b3c0d7613bc3d9e2f912c2c1fcce83`
has Hub 38/40, Node 23/24 and contract 33/34 PASS. Only historical journal
migration and product P0 PARTIAL stages fail. Board-stack E2E passed eight cases;
ESP-IDF 6.0.3 S3 production and GS-114 fixture profiles compiled. Old reader
availability on interrupted first events remains a known FAIL_CLOSED limitation;
both commercial supported images must include the corrected reader (GS-D033).
The concrete signed pair, physical reboot/OTA/rollback, lifetime storage capacity
and full release qualification remain NOT_RUN/BLOCKED. GS-148 In Progress;
GS-145 To Do; no status transition. Next action is separate image/physical and
remaining commercial lifecycle qualification under its own authorization.


## GS-148 / GS-145 first-event design review — 2026-10-13

**DESIGN_READY_FOR_APPROVAL**, documentation only. Reviewed actual canonical
local/GitHub HEAD `371a560f04b99bce8fd86e58739a75184b555b55`, clean tracked
tree, context PASS `2026-10-11.001`, current code and Jira 10678–10682.
[Focused decision report](../architecture/GS148_FIRST_EVENT_RECOVERY_DESIGN_20261013.md)
recommends Option A: the existing authenticated zero-boundary application checkpoint,
selected first identity/body and native owner/root/fence checks establish one
pending transaction. Original authenticated retry finishes ordinary v1
publication/checkpoint before Durable ACK. A narrowly proven interrupted empty
checkpoint may be completed using its current format. No new persistent bytes,
keys, partitions or installation manifest; all proposed logic remains unimplemented.

This replaces the earlier assumption that the 116-byte genesis candidate is
necessary for the demonstrated first event. It does not weaken current failure
checks: standalone missing-head, populated history, missing/corrupt checkpoint,
owner/epoch and inconsistent witness cases still fail closed. Native epoch-1
scope is explicit; future transfer/incarnation remains separate.

S3 uses the shared Hub-to-C3 FOTA sender, with rollback configured but no inspected
Hub self-OTA receiver or pending-image health confirmation. Signed S3 rollback
is not qualified. Recommend corrected v1 recovery in both supported R1 images;
old engineering readers retain their existing fail-closed initial-pending limit.
Image support approval and qualification cannot be inferred from unchanged bytes.

No production code or validation registry changed; no completed test campaign
repeated. New cases PROPOSED_NOT_EXECUTED; documentation checks only. Prior
P0/P1/P2 PARTIAL, historical migration FAIL and product P0 PARTIAL remain.
Physical NOT_RUN/BLOCKED; release NOT_RUN. GS-148 In Progress, GS-145 To Do;
GS-152 Done. No issue transition or hardware action. Final docs commit/actual
remote equality and Jira IDs are recorded in dated delivery comments.
Next action: approve the bounded design and supported image recommendation,
then separately authorize its ordered implementation package. Stop after review.

## GS-148 bounded P0/P1/P2 correctness checkpoint — 2026-10-13 (started 2026-10-12)

Delivery: architecture `2b17924be86c7ce78f8e1ec1c7c03b402fc48a6c`, tested source `23636a921409b52afe56823ca4302d5fb09683cb`; normal push and actual
GitHub/local HEAD equality verified, tracked tree clean before this final Markdown
handoff. The dated GS-148 delivery comment records the final handoff-only descendant
HEAD. Source fingerprint `7fd270f6cbd5f94f520945cd218d2bdddc7b4d77ab24c31a4936932ad4973250`
remains identical. Hub 36/38, contract 31/32 and Node 22/23 stages PASS; only
migration and/or product P0 PARTIAL fail. Board eight cases PASS; new normal /
ASan / UBSan fault tests, production and GS-114 target builds, framework and
traceability PASS. See the full receipt/count/hash table in the package handoff.

GS-152 is Done; bounded work resumes from canonical `77e29d4` on
`feature/r1-commercial-baseline`, context PASS `2026-10-11.001`. Start comment
10594 records the authorized software scope. The approved Sol direction is
integrated with its historical source audit; D-A–D-M remain OPEN and no new
LOCKED requirement/context version is introduced.

Implemented: exact next-reducer/identity/body immediate admission checks before
identity selection; active/fallback/witness report-bank protection; cross-epoch
witness refusal; equal-generation checkpoint conflict rejection, permitting
nonce-different identical authority. Permanent production tests cover 28 cuts,
two-boot exact retry/original context, conflicting payload/lost ACK, repeated
capacity refusal, all three bank pins and the existing 64-KiB reducer boundary.
Final component/build/fixture/sanitizer/framework results and delivery checkpoint
are in the [current package handoff](../exec-plans/evidence/R1_GS148_P0_P1_P2_20261012.md).

**PARTIAL:** complete first body without its first v1 event head remains fail
closed. The genesis/rollback format proposal is unimplemented pending approval.
Immediate checking does not qualify lifetime completion/metadata/COW/GC reserve.
Historical migration FAIL and product P0 PARTIAL remain visible. Physical
NOT_RUN/BLOCKED; release approval NOT_RUN. GS-148 stays In Progress; other
requested issue statuses are unchanged. Stop after this package. Next action:
review/approve genesis compatibility and owning commercial prerequisites, then
authorize a separate package. Do not resume the original audit or hardware.

## GS-114 Part 2D — fixture-compatible S3 RPF diagnostic build — 2026-10-12

At source HEAD `e31e8ef6314abcc777eb5979c3d33939cdb7b296` (source fingerprint
`f54e3162160d4f9e96a61ed60575f434c2a33c73a866b85789cd5bce610e0dce`), the
new explicit `make gs114-s3-rpf-diagnostic-build` target completed successfully
with ESP-IDF 6.0.3. The standalone local S3 app is
`code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/build/gs114_fixture_pair/build-kvi2pcxe/s3/gs_r1_s3_hub.bin`,
1,879,392 bytes, SHA-256
`48d08726d3acb686466fc8ef056609efe2b0148719ea89943bbe3e48a72c1f09`; it fits
the candidate 4 MiB OTA slot with 2,314,912 bytes free. The build checks the
Part 1 `GS_HIL_COMMISSIONING=ON`, broad S3 HIL-off, 16 MiB/Octal PSRAM and
`gs_outbox`/`gs_state` profile; all RPF00–RPF08 diagnostics and bounded fixture
commissioning strings are present. It decodes the compiled partition table and
confirms it matches the candidate CSV. The generated full-device flash bundle
is not authorized for deployment.

Focused validation: fixture/profile test 9/9 PASS; validation framework
39/39 PASS; seven focused Hub retirement/checkpoint/storage/fresh-install/
rejoin/association/protocol targets PASS. The historical GS-148 journal
migration failure remains an independent known FAIL and was not rerun or
changed. No production runtime/storage/security C++ source changed; no physical
device or data was accessed. The new S3 image is not installed. Actual fixture
image, active OTA slot, partition contents, eFuse state, retained events and
safe rollback remain unverified; first-boot replay-fence reconciliation can
write persistent state. Deployment and GS-114 physical qualification remain
**BLOCKED / NO-GO** pending separate preservation review and installation
authorization. The exact comparison, successful build JSON and caveats are in
[GS-114 Part 2D evidence](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_PART2D_FIXTURE_DIAGNOSTIC_BUILD_20261012.md).

The Part 1 provenance note below is corrected: its later retained local app
binaries match `physical_results.json`, while the `fixture_pair_report.json`
at the same paths records earlier different hashes and is stale relative to
those files. Neither source is physical flash readback. No previous physical
PASS is upgraded.

**Part 2D delivery checkpoint:** commit `2545e9a94e6fc87f43ec8a3b672e88dbb1fcbbae`
is pushed to `origin/feature/r1-commercial-baseline`. Local and remote HEAD
matched at verification. No fixture deployment or physical qualification was
performed. The pre-existing untracked S3 `managed_components/` and redacted
Part 1 evidence remain unmodified; the separate GS-152 worktree remains
isolated and unchanged.

## GS-114 Part 2C — supervised diagnostic deployment plan — 2026-10-12

Planning-only review was performed at canonical source/remote checkpoint
`cbbf12d1b4fba9cd1e38730685ccede32f23f558` on
`feature/r1-commercial-baseline`. Context preflight passed. No USB, serial,
target storage, build, or physical device was accessed. See the dated
[GS-114 Part 2C deployment plan](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_PART2C_DIAGNOSTIC_DEPLOYMENT_PLAN_20261012.md).

The saved GS-148 diagnostic S3 image hash was verified locally and contains
RPF stage strings, but it is not suitable for the commissioned fixture:
`GS_HIL_COMMISSIONING=OFF` does not use the fixture's persisted development
identity, and its packaged partition table is the development `gs_journal`
map, not the fixture's `gs_outbox`/`gs_state` map. Its complete flash bundle
also rewrites bootloader, partition table and OTA metadata and resets the
target. The current source fingerprint differs from the report fingerprint.
There is no proven S3 app-only update path, storage backup/restore, or
reset-safe two-board observation route. Normal rejoin may attempt replay-fence
publication, which can write LittleFS; this diagnostic is not application-level
read-only. Therefore deployment, observation and real PIR qualification remain
**NO-GO**. The physical failure root cause remains unknown.

The saved Part 1 C3/S3 application artifacts are present in the ignored local
fixture-pair build directory. Their hashes match Part 1 `physical_results.json`,
but the colocated `fixture_pair_report.json` records earlier different hashes
for those same paths and is stale relative to the retained binaries. Neither is
flash readback; installed image, partition table, OTA slot and live persistent-
state provenance remain unknown.
The deployment plan records this distinction and the required separate
approval gates. GS-114 planning result is in Jira comment 10504; the diagnostic
profile incompatibility is cross-referenced to GS-148 in comment 10505. The
deployment plan is documentation-only and records the exact source checkpoint,
offline artifact checks and future approval gates.

Plan/documentation commit `c077bee73befac3afc9bbdb50f9234ac46fe2b18` was pushed
normally; local HEAD and `origin/feature/r1-commercial-baseline` matched at
that delivery checkpoint. Only the plan and this work-state file were staged.
The pre-existing untracked S3 `managed_components/` and redacted fixture
evidence remain untouched.

GS-114 remains In Progress; GS-148 remains OnHold; GS-145 remains a separate
fresh-format durability gate. Next action is user review of the state
preservation strategy, corrected fixture image profile, installation method
and reset-safe observation candidate. No hardware action is authorized by the
plan. Preserve the untracked S3 `managed_components/`, all redacted fixture
evidence, and the isolated GS-152 worktree.

## GS-148 narrow replay-fence diagnostic checkpoint — 2026-10-12

Authorized by GS-148 comment 10499. On the canonical
`feature/r1-commercial-baseline` branch, production Hub replay-fence failure
diagnostics now distinguish selected-state/checkpoint recovery, witness
prevalidation/publication/readback, and runtime binding stages with sanitized
stable codes. Production-code host fault tests cover valid Prepared/Duplicate
reports, failure boundaries and restart selection. The error remains fail
closed and does not send a retirement-report ACK. No storage format, ownership,
durable-before-ACK, event identity or recovery policy changed.

Focused Hub/Node retirement, outbox, checkpoint, rejoin, framework and
traceability tests passed; the checkpoint suite also passed ASan/UBSan. Clean
ESP-IDF 6.0.3 paired C3/S3 production-profile builds passed (C3 934,192 bytes;
S3 1,870,944 bytes) with matching embedded Node image provenance; no flash
target ran. See the dated [GS-148 replay-fence diagnostic evidence](../exec-plans/evidence/R1_GS148_REPLAY_FENCE_DIAGNOSTIC_20261012.md)
for image hashes and the exact target report. The historical Hub journal
migration assertion remains an independent FAIL. No physical devices, USB,
serial, storage or HIL interfaces were accessed. Physical root cause remains
unknown and GS-114 remains physical NO-GO.

The storage reconciliation confirms the old classic ESP32 fixed 128-slot
NVS journal is not the active S3 outbox implementation. S3 uses bounded
segmented LittleFS plus checkpointed identity/completion state; its current
candidate capacity, retention and physical endurance are not qualified. This
checkpoint does not start GS-148 P2-E/P2-F. After final validation and push,
GS-148 returns to OnHold. Preserve the untracked S3 `managed_components/` and
existing redacted GS-114 evidence. Next action: review this diagnostic and
authorize a separate, state-preserving physical diagnostic plan before any
GS-114 retest.

## GS-114 Part 2B — software-only root-cause investigation — 2026-10-12

Investigation source HEAD was `7c1fee29e17fc3fe12c840e0afef5fa6b7217b68`;
canonical local and origin refs matched before the tooling/documentation
checkpoint. No board, USB or serial interface was accessed. The saved C3
`USB_UART_CHIP_RESET` is most likely associated with opening its native USB
Serial/JTAG console: pySerial 3.5 applies DTR/RTS after `os.open()`, and prior
fixture notes document monitor-attachment resets. Exact causation/timing is
not proven by the captured logs. The HIL-A06 classifier was corrected and its
registered host test now fails on this marker.

The S3 replay-fence error occurs while handling an authenticated Node
retirement report after rejoin/epoch advertisement. The source emits this error
only after report application returned Duplicate or a Prepared snapshot passed
NVS checkpoint recovery/reference verification. The later selected-state or
reducer-checkpoint reload, LittleFS fence validation/publication/readback, or
runtime bind remains the unresolved step. Admission correctly fails closed
and the report ACK is not sent on this error path. A C3 reset/rejoin may have
triggered the report, but the report fragments are not directly observed. This
is not the separate historical GS-148 journal-migration assertion failure.

Host-only `make gs130-hil-runner-test` passed 17 tests, `make
validation-framework-test` passed 39 registration/failure-propagation tests,
and `make hub-runtime-checkpoint-host-test` passed its synthetic publication-
cut, recovery and mismatch checks. These tests do not reproduce the fixture's
persistent state. Production security/storage semantics and device data were
not changed. The physical retest is **NO-GO** until the S3
failure is localized without clearing storage and the capture path is
independently assessed for reset risk. Details and exact future gates are in
[GS-114 Part 2B evidence](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_PART2B_ROOT_CAUSE_20261012.md).

## GS-114 Part 2 — observer stopped on reset and Hub admission error — 2026-10-12

At canonical source `09bc8cd8b7baab0674bbe03157b7b50bab28e51e`, read-only
USB/sysfs/udevadm preflight found the approved C3 USB identity on
`/dev/ttyACM0` and the approved S3 USB-UART identity on `/dev/ttyACM1`; neither
port was already open. The user authorized opening only their two stable by-id
interfaces for DTR/RTS-low receive-only capture. The existing observer verified
the by-id serials and Part 1 candidate artifact hashes, then captured 60 seconds
without sending serial bytes.

The capture reported C3 boot reason `USB_UART_CHIP_RESET` during the observation
window. The cause is consistent with opening the UART but cannot be proven. S3
reported `S3 replay-fence publication failed; admission closed`. Per operator
instruction, the physical campaign stopped immediately; no recovery or further
device access occurred and no real PIR movement was requested. Logs are retained
at [GS-114 Part 2 stopped baseline](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_PART2_20261012T032500Z_baseline/STOP_REPORT.md).

Boot banners show the fixture's expected C3/S3 MACs, chip revisions, flash/PSRAM
profiles, ESP-IDF 6.0.3, and app version `73e1e842ff84-gs114-16fca85b`; installed
image hashes are not proven. Authenticated rejoin and online liveness appeared,
but no EventKey-to-durable-commit-to-application-ACK-to-retirement chain was
observed. The observer's aggregate `PARTIAL` is overridden by the explicit
stop-condition evidence; HIL-A06 is FAIL. GS-114 P1 is NOT_RUN, P2–P4 BLOCKED,
P5–P9 remain BLOCKED/NOT_RUN as detailed in the stop report, and P10 belongs to
GS-149. No PIR physical PASS is claimed. GS-114 remains In Progress.

Next action requires a verified non-resetting receive path and resolution of
the S3 replay-fence admission failure; do not reopen the ports, reset, reflash,
or modify stored state without a new explicit authorization. Isolated GS-152
and protected original boards were not accessed.

## GS-114 Part 2 physical preflight — 2026-10-11

Preflight at source checkpoint `02d7a12bd0f523a3acf7b80bfc06ac996fd14c76`
found no `/dev/serial/by-id` directory or `/dev/ttyACM*` interfaces in the
current WSL environment. No board was opened or otherwise interacted with. The
existing genuine-motion observer sets DTR/RTS low and sends no bytes, but its
own safety note says serial open may affect an unverified adapter; the S3
fixture is CH343 and a non-reset guarantee is not established. Real PIR
qualification is therefore **BLOCKED before stimulus**. Operator still needs
to confirm the exact disposable pair is attached, the AM312 is already safely
wired to C3 GPIO4, and they are available for prompted motion; a verified
no-reset observer or explicit approval for the bounded DTR/RTS-low serial open
is also required.

Part 1 hashes remain the recorded build artifacts from source
`73e1e842ff843a696d592bd7c2004b72a512082c` (C3
`b03b3b2ed7996b594f9fe7d59241f558a6af82774db07a661e5346731db83014`, S3
`f9608d77230f136abea5794329c1a98be4062419383a1a6dbbfd29a6c793a2d1`), not
verified flash readbacks. C3 firmware sources are unchanged through this
checkpoint; the intervening S3 delta adds CloudSync generation provenance and
does not affect GS-114 local event/ACK/sleep behavior. This does not establish
which images currently run on the fixture. No motion, reset, outage, FOTA,
storage operation or physical measurement occurred. Exact case dispositions
and the next safe action are in
[`GS114_PART2_PREFLIGHT_20261011.md`](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_PART2_PREFLIGHT_20261011.md).

**GS-114 remains In Progress and is not eligible for closure.** P1 is NOT_RUN;
P2–P9 remain NOT_RUN/BLOCKED as mapped in the preflight record; P10 belongs to
GS-149. The preserved Part 1 evidence remains limited to its recorded scopes.
Local/remote HEAD at preflight was `02d7a12bd0f523a3acf7b80bfc06ac996fd14c76`;
only this work-state/evidence documentation is intended to change. Untracked
S3 `managed_components/` and prior redacted Part 1 logs remain preserved.


## GS-130 P0 full-product E2E and HIL runner checkpoint — 2026-10-11

Current implementation adds `make validation-p0-e2e` to the existing GS-116
registry, joining the production C3/S3 host event path and S3 CloudSync serializer
to the actual local API/service and shipped caregiver PWA in one focused
Chromium scenario. The separate GS-116 opt-in `make validation-board-hil` and
`make validation-motion-hil` runners are implemented with no-run JSON evidence,
fixture/image/USB-serial preflight, operator confirmation, no UART writes and
unique evidence directories. Their unit tests exercise safe-block/NOT_RUN paths
only. **No physical ports were opened and no physical stimulus occurred.**

The initial product vertical test is PARTIAL. It proves C3/S3 host stack
EventKey retry/dedupe/Durable ACK, local API activity and incident processing,
Hub API lease projection, household isolation, configuration validation and
Chromium timeline/door/connectivity/alert rendering. The production-shaped Hub
CloudSync event-key request receives fail-closed 503
`durable_event_store_unavailable`; the local API test route is not the unfinished
GS-148 authenticated COMMITTED contract or production OIDC. The official
`make validation-p0-e2e` stage therefore reports FAIL when the harness's
`product_status=PARTIAL`. This is intentional release safety, not a failed
scenario assertion. No product feature coverage or release qualification is
claimed complete. Exact scenario/gap mapping, outputs, gate results and physical
limits are in [dated GS-130 P0 E2E/HIL evidence](../exec-plans/evidence/R1_GS130_P0_E2E_HIL_20261011.md).

Final focused checkpoint: the P0 stage executed 17/17 scenario markers and one
Chromium case, then correctly exited nonzero at the PARTIAL completeness check;
the existing board-stack suite reran PASS at 8 groups/325 checks. Runner
integrity is 15/15, component-gate integrity 39/39, feature mapping 19/19,
focused API/durable regressions 19/19 and app tests 23/23. No serial port or
board was accessed; physical status stays NOT_RUN.

Latest same-source verification after adding exact scenario selection: the
scoped `make p0-product-e2e P0_SCENARIOS=P0-E2E-002` passed its selected
assertion and selection tests (3/3), with browser tests correctly omitted. The
unfiltered registered `make validation-p0-e2e` then ran 17/17 assertions plus
one Chromium test; its component command exited 0 but completeness adjudication
returned FAIL / outer exit 2 because the product result is PARTIAL. Final
post-commit report at source HEAD
`5e785b49839fc2fa914a3baf8886f6e707a3de3d`:
`code/evidence/validation_framework/p0-e2e-1791729788813148262/report.json`,
source fingerprint `add14d809ae6ee942f0d282a668bbe72e7071b6d25efb6353d24027f11f85285`,
tracked source unchanged; stage 11.661 s, total 12.170 s. Board-stack rerun at
the same source/fingerprint passed at 8 groups/325 checks in 6.681 s.

Implementation commit `4fd36f31518cb5f7e3c33d0b62862d59813516ce` was pushed
normally and the actual origin branch was verified equal. GS-130 comment 10436
records implementation evidence without changing workflow fields. This work
state/evidence delivery closeout is a documentation-only follow-up. The final
task handoff records its resulting local/remote HEAD and Jira comment. Existing
untracked S3 `managed_components/` and redacted GS-114 evidence were preserved
and excluded from the GS-130 implementation commit.

GS-148 retains the CloudSync commit integration gap and historical journal
migration FAIL. GS-130 still has partial P0 use cases where production scheduler,
provider, persistent backend, OIDC, firmware lifecycle or physical acceptance is
not implemented/testable in this vertical. `make release-gate-final` and broad
unchanged suites remain NOT_RUN. No product requirement/context version, Jira
workflow/rank, firmware behavior or physical authorization changed. Next
software handoff remains GS-130 gap closure; next physical campaign remains
separately authorized GS-114.

## Permanent physical HIL catalogue audit — 2026-10-11

GS-114 coverage audit reuses GS-130's 149-row traceability matrix and 200-row
source inventory (the two GS-114 fixture commissioning-adapter modules are now
reciprocally mapped to secure commissioning). The matrix classifies implemented/partial features as 45
`PHYSICAL_REQUIRED`, 40 `PHYSICAL_CONDITIONAL`, and 57 `SOFTWARE_ONLY`; the
remaining seven are one `NOT_IMPLEMENTED` (FOTA-HUB-SELF-01), three `ON_HOLD`
(BAT-C9, GS128-RUNTIME-CONFIG, GS147-JOURNAL), and three `DEFERRED` (BAT-C11,
BAT-C12, P1-TEMP-CAMERA), not rows missing physical classification. Required and conditional
rows resolve to case IDs in `docs/validation/PHYSICAL_HIL_CATALOGUE.csv`.
Catalogue registration is separate from execution and physical acceptance.

The case catalogue preserves the existing HW-M1.4 supervisor/71 test IDs and
marks its classic ESP32 Hub campaign historical-only for current S3. It records
the actual bounded GS-114 Part 1 observations: A02/A03/A06 PASS, A01 PARTIAL,
A07 timer-counter-only PARTIAL, A04/A05 NOT_RUN, A08 BLOCKED. BAT-C8 C8-P1–P9
remain NOT_RUN. No boards/serial ports were accessed in this audit. No current
S3-compatible unattended or operator-prompting HIL runner existed at that audit
checkpoint; GS-130 later added separate opt-in observational and genuine-motion
runners, documented in the current section above. Legacy `hil-regression` is not
safe for this S3 fixture and can build/flash/reset/inject motion.

Added hardware-independent catalogue mapping tests to `hil-tooling-test` and a
release-only evidence checker in GS-116's registry. The release checker fails
when mandatory physical rows are partial, missing or historical; it never
operates hardware. See [dated HIL coverage evidence](../exec-plans/evidence/R1_HIL_COVERAGE_AUDIT_20261011.md)
for commands and exact evidence. The full software release gate was not run;
physical qualification and product release remain NOT_APPROVED. The existing
GS-148 journal migration failure remains visible and unchanged.

Next physical work remains **GS-114**, on the separately authorized matching
fixture: current-image P1–P9, actual optical PIR/GPIO4, timer/radio restoration,
event Durable ACK/EventKey, sleep/retry/rejoin, outage recovery and maintenance
inhibitors. GS-108 later owns broad stable-head HIL after S3 runner compatibility
work. No Jira workflow/rank/dependency changes are implied.

## GS-114 fixture commissioning and focused Part 1 result — 2026-10-11

User-approved, S3-only `GS_HIL_COMMISSIONING` adapter reuses the existing
HubSecurityLink commissioning owner and cryptographic protocol. It is opt-in
and disabled by default; broad S3 HIL-control rejection remains. The two
specifically authorized disposable boards were clean-installed after exact
C3/S3 identity checks. Fresh association, authenticated rejoin, C3
software-restart rejoin, and a subsequent authenticated NodeHealth from the
same Node after the S3 app restart were observed. The five-minute health
opportunity and timer-wake counters were captured without PIR stimulus.
Detailed image hashes, logs and limitations are in [GS-114 Part 1 fixture
evidence](../hw/evidence/GS114_PART1_CLEAN_FIXTURE_20261011.md).

`make validation-node` and `make validation-contract` PASS. `make validation-hub`
remains FAIL (exit 2) solely at the known GS-148 `hub-journal-migration-host-test`
assertion `clean migration commits`; all other registered Hub stages passed.
The test and ownership constraints remain unchanged. Focused adapter parser /
isolation tests and existing commissioning crypto, rejoin, association and
fresh-install checks pass. The ESP-IDF 6.0.3 production-profile C3/S3 builds
pass (C3 934,192 B; S3 1,868,880 B); fixture UART command strings are absent
from the production S3 image.

Physical outcomes are bounded: HIL-A01/A02/A03/A06 PASS within stated scope,
A07 PASS for timer-wake telemetry only, A04/A05 NOT_RUN, A08 BLOCKED. No genuine
PIR exercise, event Durable ACK, offline threshold, FOTA, RF fault, current
measurement, broad HIL or release gate was performed. GS-114 P1–P9 physical
qualification remains open; Part 2 PIR and battery qualification are not
started. The fixture adapter is not GS-109 product commissioning and uses
unprotected development identity material; never ship or use it on protected
or production devices.

Work remains on `/home/udaybhan/projects/Ghar_sajag_r1`,
`feature/r1-commercial-baseline`, starting at
`73e1e842ff843a696d592bd7c2004b72a512082c`; source, tests and documentation
passed focused validation. Commit `fee4b230ce954ea8b429390f1d89c44f105458f0`
was pushed normally and matched the actual origin branch at verification.
Existing untracked S3
`managed_components/` and prior redacted failed-attempt evidence are preserved.
Documentation closeout commit `ad93cea52f6bbf0e628fee5ed5fb24981dd877c6` is
also pushed and remote-verified. GS-114 comment 10428 records implementation,
test and bounded physical evidence. GS-109 comment 10429 explicitly states the
fixture adapter does not satisfy product Add Device authorization; GS-114 ↔
GS-109 is linked without changing either workflow status or rank. Next is the
separately authorized GS-114 Part 2 physical PIR work.

## GS-130 focused application lifecycle continuation — 2026-10-11

Starting local and GitHub HEAD: `17fb074cdb1caa5ff1a08135222b29ec502c1dda`,
branch `feature/r1-commercial-baseline`. Focused app lifecycle continuation
added six stable application regression cases and one Python claim-expiry case.
`make app-test` passes 23/23, notification backend regressions 8/8, related claim/
identity/activity backend tests 4/4, and settings persistence tests 2/2. Direct
service-worker script execution exposed and fixed unsafe rejected-cache behavior:
navigation now falls back to the cached shell and unavailable/corrupt resources
return explicit 503. Details and limitations are in the linked dated GS-130
evidence section below.

Gap disposition: worker navigation/recovery PASS in a deterministic VM harness;
claim expiry/reconnection PASS in UI-policy and API model tests. Onboarding,
offline settings and notification/activity browser lifecycle are PARTIAL because
the current app has no persisted onboarding transaction or durable offline settings
queue, and live browser storage/push subscription lifecycle remains untested. No
broader feature was invented. Full PWA/browser, full release and physical suites
remain NOT_RUN. Historical GS-148 Hub migration FAIL remains unchanged; no Node,
Hub, contract or 325-check board-stack suite was rerun. Jira status/rank/dependencies
and product requirements are unchanged.

Implementation commit `a0452084b50d2d720010719cbc3a5d18ccd71b8b` and evidence
commit `44f27ce1215dfdce7f51c576fd26cf457edb0ab8` are normally pushed; actual
remote HEAD matched. GS-130 Jira delivery comment10419 records the focused results.
This work remains PARTIAL pending the listed lifecycle gaps and historical
migration disposition. Separately authorized GS-114 P1–P9 remains the next
physical qualification.

## GS-130 feature regressions / board-stack checkpoint — 2026-10-11

Canonical worktree `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`; starting local/remote
`d3857fd76aff71b58287bee72aaa3b36b6042d89`. The implementation is preserved
sequentially; no new branch/worktree or physical action. Resume at actual verified
branch HEAD, recorded in the final GS-130 Jira delivery comment.
Validated implementation checkpoint `9349ed33ba72b7cf80d35a87c4108d4a9b1bda66` is normally
pushed; actual local/remote HEAD matched. The subsequent Markdown closeout
revision is recorded in Jira. Tracked tree clean; original S3 untracked assets preserved.

[GS-130 evidence and exact resume](../exec-plans/evidence/R1_GS130_FEATURE_COVERAGE_20261011.md)
and [MASTER_VALIDATION](../validation/MASTER_VALIDATION.md) index the existing
feature matrix (149 behavior/validation rows), source inventory (198 files) and
14 physical campaigns. These counts do not prove 100% semantic coverage.

**A: feature/category coverage PARTIAL.** New production boundary regressions,
real portable TF-PSA reset execution, prior Node/Hub/contract regressions and
permanent mapping/integrity enforcement are delivered. Specific application
offline/cache/onboarding/config/claim/notification lifecycle gaps remain mapped
under GS-130; unchanged application execution is NOT_RUN by focused user policy.

**B: portable C3/S3 E2E executable PASS, eight groups/325 checks.** Real sensing,
runtime, crypto/session, encrypted Node recovery, S3 outbox/journal/reducers,
health/piggyback, outage/sleep/priority and FOTA interruption run through host
hardware boundaries. Complete target-stack acceptance remains PARTIAL: target
app_main/task/callback/radio suspension-restoration orchestration is not executed
by this driver. Do not equate policy/runtime simulation with every firmware entry
point. Target-only qualification belongs to GS-114/108; any future host seam must
exercise production orchestration. Physical proof remains separate.

Focused Node and contract gates PASS; Hub FAIL only for mandatory historical
`clean migration commits` (line194), owned by GS-148. GS-D001 deferred arbitrary
legacy migration and GS-D029 fail-closed ownership remain unchanged. Fresh current-
format/S3 recovery passes separately. The test is neither skipped nor weakened.
Evidence records exact final commands/counts/durations/exits/profile/fingerprint.
Framework/traceability and new focused ASan/UBSan checks pass. Firmware/config/
partition bodies unchanged; existing verified IDF6.0.3 GS-116 C3/S3 image/build
evidence still applies. Fresh target builds NOT_RUN; full fast/release/browser
NOT_RUN; product release NOT_APPROVED; physical qualification NOT_RUN.

**Next executable action: finish GS-130 coverage gaps**, starting with precise application lifecycle mappings
and tests when within the authorized validation scope. Target-only owner/radio
qualification remains with GS-114/108; do not create a second business algorithm. Do not rediscover/restart
the delivered boundary/board/PSA framework. Then **GS-114 P1–P9** requires separately
authorized fixtures and current matched GS-40/150 firmware/config. GS-40 actual
heartbeat/offline caregiver acceptance remains open; GS-149/146 retain their
existing dependencies. Preserve original S3 managed_components and ignored assets.
No requirement/context, Jira status/rank/dependency or production behavior change.

New GS-130 comments10411/10413 were reconciled during delivery: Track C is an
inventory/reuse handoff of existing canonical HIL, not greenfield implementation.
GS-108 owns broad stable-head HIL; GS-114 owns P1–P9. Existing supervisor motion
is synthetic INJECT_MOTION and campaign defaults flash. C1/C2 actual execution
NOT_RUN without approved safe fixture; genuine optical evidence and historical
image-matched traces remain distinct. No serial/USB/board command was invoked.

## GS-116 resumed framework delivery — 2026-10-11

Canonical worktree `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`, starting/verified remote checkpoint
`7b93dea9561ec4f0301ecd77a7b578bee8a1c36a`. Resumed preserved uncommitted
framework from GS-116 comment10370; no new branch/worktree or hardware action.
GS-116 implementation/qualification checkpoint `c71bb9624e62f350fa22f9b19d8692615982f316` is normally
pushed and actual local/remote HEAD verified equal. Post-commit source fingerprint
matches every final component/build report. The following documentation closeout
revision is recorded in the final Jira handoff; resume at actual canonical branch HEAD.

See [GS-116 execution evidence](../exec-plans/evidence/R1_GS116_VALIDATION_FRAMEWORK_20261010.md)
and [permanent execution guide](../validation/MASTER_VALIDATION.md).

Node/Hub/contract/backend/PWA commands share one executable stage registry;
fast is their deterministic union; final release dominates fast and adds fresh
C3/S3 production builds, sanitizer/trace/product variants, browser and bounded
performance. AGENTS.md permanently enforces new plus prior-component regressions,
contract impact, registration and distinct software/physical/release evidence.
GS-130 owns exhaustive feature-to-test completeness, including the separately
built portable PSA factory-reset harness and physical evidence definitions.

**Migration diagnosis supersedes the GS-40 UNRESOLVED finding below:** current
and independently compiled pre-GS-40 `913b1ded` reproduce `clean migration commits`
at tests/cpp/hub_journal_migration_validation.cpp:194. Classification
HISTORICAL_BASELINE_DEFECT: legacy checkpoint owner domain versus current
registry-domain import; the durable-transition guard correctly rejects it before
legacy erasure. GS-D001 defers arbitrary legacy migration; GS-D029 ownership
safety is preserved. GS-148 receives the technical storage handoff; GS-126 is not
the storage owner. No production migration fix or assertion weakening in GS-116.
The test remains mandatory; aggregate Hub/fast/release cannot be PASS while it fails.

GS-11610405 permanently distinguishes component development from release acceptance.
Current work runs Node/Hub/shared security contracts, framework tests and relevant
builds/sanitizers. Full release execution is NOT_RUN/deferred until a genuine
release candidate; lightweight registration tests establish composition only.
The pre-correction interrupted release attempt remains disclosed in evidence.

Final component qualification: Node15/15PASS (280.585s), shared contracts23/23PASS
(0.844s verified receipt campaign), Hub27/28PASS (374.234s), aggregate HubFAIL only
for migration. Framework33testsPASS; simulator default link/runPASS. Sanitizer and
target-build final results PASS: ASan/UBSan CPP1479/GS-401320; clean IDF6.0.3
C3 934,192bytes and S3 1,868,800bytes, slots/config/exact embedding PASS. This is framework delivery
with a known software qualification failure, not complete product release acceptance.

Current qualification results and exact checkpoint are recorded in the linked
evidence and final owning Jira delivery comment. Physical remains NOT_RUN.
Next executable task **GS-130**, then separately authorized **GS-114 P1–P9**
with matching GS-40/150 C3/S3 images/configuration; GS-149 power and GS-146 retain
existing prerequisites. Preserve S3 managed_components and original ignored
assets. GS-40 real-target heartbeat/offline visibility, GPIO4/radio/power-cut/
signed-FOTA and endurance acceptance remain open. No workflow/rank/dependency change.


## GS-40 software delivery / physical handoff — 2026-10-10

GS-40 source implementation is complete: default 300 s, internally derived 910 s,
identical day/night authenticated-contact/piggyback cadence, validated schema 1
JSON embedded into C3/S3 startup policy, trusted physical identity mixed-profile
mapping, and per-device backend/PWA received-contact freshness. GS-D031/context
2026-10-10.001 record the approved policy; GS-128 remains OnHold. Actual preceding
production cadence was 120/310; historical 60/190 remains an explicit legacy profile.
No wire/storage migration, retry changes, GS-150 rewrite or hardware action.

Starting local/remote checkpoint `913b1dedb483ca63aff7244dbbd224053206c7f2`;
approved canonical policy commit `821da80b25dc11c8a01252333abc9734036fc66b`.
Implementation `e36bd88371449421420ec86995e82d3695a680d5` was normally pushed;
actual origin branch HEAD matched local HEAD with tracked cleanliness. GS-40
design/implementation comments10360/10363 and GS-114 candidate comment10368
record the milestones. Final documentation closeout HEAD is recorded in Jira
after its own normal push/verification. Canonical worktree `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`. Original untracked S3 managed_components and
original ignored Node asset are preserved; bundle/build directories are generated.

Evidence: [GS-40 software validation](../exec-plans/evidence/R1_GS40_SOFTWARE_VALIDATION_20261010.md),
[paired software metrics](../exec-plans/evidence/R1_GS40_SOFTWARE_METRICS_20261010.csv),
[JSON/build/profile guide](../../code/config/README.md).
Host C++ 1,479, Python 361 with one historical skip, GS-40 model 1,320 / configuration 15,
GS-150 1,481, BAT-C8 72+11, PWA bridge 12 / API 92 / frontend 92 and security/FOTA passed.
ASan/UBSan CPP/model passed. Clean IDF 6.0.3 C3 app 934,192 bytes and S3 app 1,868,800 bytes
pass existing slots; exact paired C3 asset/config fingerprint packaging passes.
Quiet 30 minutes health 15→6, night 8 hours 240→96: 60% fewer standalone health transmissions versus
actual120 baseline. Event identities/effects/retry and recovery latencies unchanged;
physical current/endurance unmeasured. Quick release gate with mandatory Chromium
passes 17 stages (master 49/49, FOTA 34/34). Extended validation-fast exit2 is
retained below. Final `make playwright-gate` exit0: all86 desktop/mobile cases
PASS after exact received-contact boundary fixture correction; the earlier
failed/interrupted runs remain recorded in the evidence.

Expanded regression fixture corrections were TEST_INFRA_ONLY /
VALID_TEST_EXPECTATION_MISMATCH under R1 release gates and GS-D031: missing six
host linker dependencies, current snapshot cap 6,100, persistent journal requirement,
selected authenticated replay-fence/owner evidence and configured coverage timing (including browser boundary assertions).
No storage/security production behavior was changed for these corrections. Historical
25-Node stress is explicitly SKIPPED with ten-slot rejection verified; supported
1/4/10 cases remain checked. Baseline source provenance is in the evidence.

**Remaining software limitation:** extended `validation-fast` still fails historical
`hub-journal-migration-host-test`: `clean migration commits` (line 194), unchanged
storage path/fixture from starting HEAD; baseline execution unverified. Classification
UNRESOLVED / INVESTIGATE_ONLY under deferred legacy storage work. Do not suppress
this failure or change migration ownership/storage contracts under GS-40. Independent
fresh-install, current S3 durability/replay and GS-40 gates are recorded separately.
Secure target trusted-epoch and production cloud-contract limitations remain open;
host backend/PWA validation does not qualify real-target caregiver visibility.

**Next sequential task: GS-116, then GS-130, then GS-114 BAT-C8 P1–P9.** Latest
user GS-40 comment10366 supersedes the earlier immediate-GS-114 plan. GS-116
owns component/contract gates and permanent AGENTS/master validation policy;
GS-130 owns exhaustive feature/test/physical traceability. Their new policy
sections were read and this deliverable reviewed: GS-40 deterministic gates are
registered in validation-fast, but remaining migration failure, full inventory
and release-gate dominance gaps prevent an all-green product release claim.
Do not start those follow-on implementations automatically in this GS-40 task.
GS-114 remains conditional on those audits and separate authorization of
fixture/image preparation and hardware actions. Include matched GS-40/GS-150 images,
startup config SHA/profile map, actual GPIO4/held-HIGH, timer/radio restoration,
NodeHealth 300/910, Hub outage/rejoin without new motion and honest coverage cases.
GS-40 stays In Progress pending its own real-target heartbeat and caregiver offline
visibility acceptance; overlapping evidence may be reused only when traceable.
No protected board flash/reset/erase/re-enrollment is authorized here. GS-149 power
acceptance follows existing GS-144/GS-51 prerequisites; GS-146 full physical/HIL
closure retains all dependencies. GS-126/128 statuses/ranks/dependencies unchanged.

The final committed-source bundle records implementation HEAD `e36bd883`,
tracked_source_dirty=false; C3/S3 image Git metadata is `e36bd88`. Hashes and
package commands are in the evidence. It is a production software candidate,
not a signed/physical-wake-qualified image. Documentation-only closeout preserves
the validated firmware source and existing runtime/storage/wire contracts.

## GS-150 software implementation — 2026-10-10

The user clarified safe best-effort missed-ACK replay and confirmed-outage
alternatives, superseding the prior guaranteed-ACK-latency stop. Production C3
now permits safe light sleep with committed pending events in the existing
confirmed-outage profile after the existing 10 s active-contact receive budget.
A successful application MAC result keeps continuous reception while pending;
it never marks contact authenticated or retires work. Connected/transient
pending reception, original retry/rejoin timing, EventKeys/timestamps, queue
limits and ACK-driven durable retirement remain intact. Rejoin, retirement,
active/idle contact, fallback and ambiguity deadlines bound the same owner
sleep decision. Radio restore failure keeps PIR sensing running and fails awake.

Current implementation/evidence: [battery design](../features/BATTERY_LOW_POWER_AND_POWER_MANAGEMENT.md),
[GS-150 validation and scenario metrics](../exec-plans/evidence/R1_GS150_SOFTWARE_VALIDATION_20261010.md).
GS-150 is SOFTWARE_IMPLEMENTED / HOST_TESTED / SIMULATED / TARGET_COMPILED.
New deterministic gate PASS (1,481 checks / 19 paired workloads); BAT-C8 PASS
(72 C++ / 11 Python); full C++ PASS (1,479); full Python PASS (346 run, one
historical scoped skip); frontend 17/17 and contracts PASS; PWA bridge 12/12,
API/frontend 92 canonical scenarios each PASS. Master runtime 49/49 and FOTA
34/34 PASS after correcting its matching stale rejected-admission sequence
assumption and host-only outbox link recipes. No production sequence change.
Encrypted recovery,
authenticated retirement/rejoin, security/FOTA and Hub persistent dedupe gates
PASS. ASan/UBSan PASS for the new gate and full C++ suite. Clean C3 ESP-IDF
6.0.3 PASS: 933,520-byte image, 53% OTA-slot free. Evidence records all actual
commands and the corrected pre-existing Hub host-test link recipe. No physical
actions, physical current measurement or battery-life claims.

Identical six-minute outage workloads: one/eight pending records reduce owner
loops 18,000→3,189/3,171 and modeled awake time 360,000→63,540/63,180 ms, with
unchanged eight TX opportunities. One modeled sleeping ACK miss needs one
additional same-key replay and preserves one logical effect. Protected rejoin
and auxiliary receive windows add awake time in already sleeping paths; these
costs and model limitations are explicit in the evidence.

Canonical worktree `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`, starting local/remote
`ff0f6f159890b86f26b998ca3d1218600ff34cc8`; the pre-existing untracked S3
`managed_components/` remains preserved. This task is the narrow GS-150 exception
to GS-147; expanded journal/retirement/capacity, deep sleep and C9–C12 remain
excluded. No LOCKED decision/context revision change. Next sequential task is
GS-114 image-matched physical functional P1–P9, requiring separately authorized
fixture/board actions. GS-149 quantitative P10 and GS-146 closure remain open.

### Delivery and sequential handoff

Implementation commit `1262400408e780044d928d84286d9b6f392b9d5a`
was pushed normally to `origin/feature/r1-commercial-baseline` on 2026-10-10;
actual `git ls-remote --heads` equals local HEAD at that checkpoint. Tracked
tree was clean; only the original S3 `managed_components/` was untracked.
This subsequent documentation-only closeout records that verified delivery;
the final closeout HEAD is reported in GS-150 Jira and the session handoff.
No firmware source changed after the validated clean image.

No GS-150 software blocker remains. Read this section, the battery guide,
linked validation/CSV and latest GS-150/GS-114 comments before resuming.
The precise next action is GS-114 fixture/image preparation and separately
authorized P1–P9 qualification, including pending-event outage sleep,
missed-ACK replay, held-HIGH/overnight PIR, radio restore and FOTA/control
entry races. Rebuild the approved qualification profile from the final
checkpoint, record its hash and fixture readiness. Do not use protected
original paired boards or treat this handoff as hardware authorization.
GS-149 P10 current/residency and GS-146 final closure follow their existing
dependencies. GS-147 remains gated; no new scope or security decision needed
to resume GS-150 software.


## Historical GS-150 ACK-boundary blocker, 2026-10-10

Superseded by the current GS-150 software delivery above. The absence of a
guaranteed ACK-arrival maximum remains true; safe missed-ACK replay is now the
approved basis for a conservative implementation.

GS-150 is a user-approved narrow C3 software implementation exception to the
broader GS-147 hold. Source verification reached its explicit stop condition:
there is no source-defined maximum authenticated application Durable-ACK
arrival time. The Node's 1,000 ms timeout covers its local MAC send callback
only; after that callback, `NodeRadio` schedules the existing retry ladder. The
Hub authenticates/processes the Node event, completes the durable runtime step,
then submits the application ACK, but does not publish a maximum arrival bound.
The existing retry deadline cannot create a safe interval to sleep before the
same retry is due. Do not repurpose the MAC timeout or change retry/ACK policy.

**GS150_RESULT=BLOCKED** before production behavior changes. The needed product
input is an approved end-to-end application Durable-ACK listening maximum,
measured from Node MAC callback completion, with a source/build-supported Hub
commit/ACK path bound that leaves time to sleep before the unchanged retry. This
must preserve exact EventKey, authenticated Durable ACK retirement, first-event
and critical-event priority, health/freshness, FOTA/control, GPIO4 and radio
restoration. No firmware behavior changed; no GS-147 queue/journal, protocol,
retry or deep-sleep work was added.

Validation on canonical source HEAD `f245eebcd80c9e43a230ae0ee814f59a37adefd0`:
`make -j2 battery-c8-host-test node-recovery-persistence-host-test
node-retirement-protocol-host-test rejoin-host-test secure-fota-adapter-host-test`
PASS; `make cpp-test` PASS (1,479); `make python-test` PASS (344, one scoped
skip). No source changed, so existing clean C3 ESP-IDF 6.0.3 build evidence
remains applicable. GS-150-specific new behavior tests/simulation and final
candidate build are blocked; no hardware action. Exact source analysis and
validation are recorded in the [battery guide](../features/BATTERY_LOW_POWER_AND_POWER_MANAGEMENT.md).

Starting local/remote checkpoint: `f245eebcd80c9e43a230ae0ee814f59a37adefd0`
on `feature/r1-commercial-baseline`; pre-existing untracked S3
`managed_components/` preserved. After documenting and commenting this stop,
commit/push the handoff. Next action: approve the ACK receive bound and validate
it against the Hub durable commit and Node existing retry schedule. GS-150
blocks final-candidate GS-114 physical qualification; GS-149 remains pending.

## C3 software-first battery audit — 2026-10-10

At canonical start HEAD `3279294e31345f0ff34d5d97ee456145375eb46a`, the
confirmed Hub-outage/backlog software gap remains: C3 light sleep is inhibited
by outage, every pending TX/ACK and retained event, so the single owner falls
back to a 20 ms poll while the existing retry/rejoin schedules remain much
slower. GS-D027 supports avoiding unnecessary Node wake-ups, but sleep with an
unacknowledged EventKey would stop authenticated ACK reception until radio
restore; the locked requirements do not define an ACK receive-window boundary
or a Hub-power-off recovery target. GS-D025 is only a powered Hub/local-radio
internet outage target. GS-147 remains design-only, blocked by GS-146, and its
expanded journal, offline envelope and ACK/retirement scope are not approved.
No firmware behavior or requirement changed pending that decision.

Read-only scope review and validation: `make battery-c8-host-test` PASS (72
C++ checks / 9 Python invariants); `make cpp-test` PASS (1,479); `make
python-test` PASS (344, one documented skip). Existing C3 ESP-IDF 6.0.3 clean
build evidence (931,424-byte image) remains applicable because no firmware
changed. No hardware actions. Diagnostics limitations, source references,
modeled wake frequency and C9–C12 disposition are in the existing
[battery/power guide](../features/BATTERY_LOW_POWER_AND_POWER_MANAGEMENT.md).

The 2026-10-10 latest Jira decision splits functional BAT-C8 P1–P9 to GS-114
and quantitative P10 to GS-149; GS-146 requires both. BAT-C12 deep sleep is
explicitly deferred. Next software action is to obtain an approved ACK-window
and Hub-off recovery/service contract before changing offline sleep eligibility;
then add deterministic outage/backlog/rejoin tests and rebuild C3. Preserve the
existing untracked S3 `managed_components/` directory. No branch/worktree
change, hardware work or journal expansion.

## Integrated software regression closure — 2026-10-10

Starting at canonical HEAD `5648d90426fb12b584a009eac0a88e754ad909c6`, the
confirmed C++ and PWA failures are closed with test-only/host-simulator fixes;
no firmware behavior or product requirement changed. `make cpp-test` passes
1,479 checks. `make python-test` passes 344 discovered tests with one explicit
skip: the classic ESP32 NVS capacity/reserve model is historical under GS-D030,
and S3 commercial capacity/reserve remain open. Its current source-bound parser
and raw-profile test pass. The PWA bridge, API scenario catalogue and frontend
suite pass after the host lab drains all bounded CloudSync batches, keeping
later activity and door-close events visible to the backend fixture.

The individual root causes, exact pre/post-fix exits, classifications, source
locations and regression risks are recorded in the [dated integration manifest](../exec-plans/evidence/R1_SOURCE_INTEGRATION_MANIFEST_20261010.md).
Focused BAT-C8 (72 C++ checks / 9 Python invariants), S3 durability/security,
replay/reclamation, P2-D HTTP/HTTPS, Node recovery/retirement and commissioning
crypto host gates pass. Firmware source is unchanged, so the existing clean
ESP-IDF 6.0.3 C3/S3 builds and selected ASan/UBSan evidence remain applicable;
no physical, production backend or OTA result is claimed. GitHub DNS was
unavailable at intake; the normal push then succeeded and actual remote HEAD
matched `dfc24d1db88fe6cd0fa7a51232a10f4152a4d5ae`.

**SOFTWARE_REGRESSION_STATUS=PASS_WITH_ONE_SCOPED_SKIP.** This does not close
S3 production backend authentication/receipt/connectivity, capacity/retention,
physical storage/FOTA qualification, or BAT-C8 physical P1–P10. No hardware was
touched. `READY_FOR_GS_114_PHYSICAL=YES`: software gates in this task
pass, but this work does not authorize or start physical qualification.
Jira comments for this closure were added to GS-110/10327, GS-114/10328,
GS-131/10329 and GS-148/10330; no status or rank changed.

## One-time source consolidation — snapshot at initial closeout, 2026-10-10

The user-approved destination is this canonical worktree `/home/udaybhan/projects/Ghar_sajag_r1`, branch `feature/r1-commercial-baseline`. Starting local and remote HEAD were `f6e949a79354ebd1a25c55a9b9a9b750bf387dac`; context preflight passed at `2026-10-09.001`. C3 BAT-C8 implementation is already in canonical history through ancestor `808080e`. Reviewed S3 target, P2-A/B/C and partial P2-D code/evidence were selectively cherry-picked with provenance; see [source integration manifest](../exec-plans/evidence/R1_SOURCE_INTEGRATION_MANIFEST_20261010.md). Integration source checkpoint before final handoff: `1febcf027baea892b95ed3a57615a4a562ee9b82`.

At initial consolidation closeout (the aggregate results are superseded by the regression-closure section above), BAT-C8 focused C++ (72 checks) and nine Python power-policy invariants passed; S3 outbox, segmented runtime, replay/checkpoint, identity, completion, mixed-body and P2-D HTTP/HTTPS suites passed. The P2-D SQLite bridge processed 300 events with no pending records; catch-up measured 26,458 ms in that host fixture. `make cpp-test` failed at `test_node_offline_resilience` expecting `next_sequence()==1001` after 1000 attempts; this same assertion is in the source P2-D evidence. `make python-test` ran 344 tests after the simulator link fix: 341 passed, one failed and two errored in G01/HIL checks (details in the integration manifest). Those historical results are not represented as passes. No Node/BAT-C8 production edit was made. Clean S3 and C3 ESP-IDF 6.0.3 builds passed in isolated `/tmp` build directories; sanitizer outcomes are recorded in the integration manifest. No hardware validation was performed.

**Active next product work remains BAT-C8 physical qualification** (GS-114), plus GS-144 target, GS-140/B0–B4 and matched AFTER measurements, GS-119 residual cases/12-hour soak, and GS-146 closure. No hardware action was taken. GS-115 C9–C12 remains conditional and measurement/decision-only; current boundaries are in [battery power management](../features/BATTERY_LOW_POWER_AND_POWER_MANAGEMENT.md). GS-147 remains a proposed sleep-first/offline-journal design only, not implementation approval; retain its Hub-off target, retirement/ACK interoperability and capacity requirements as unresolved until the issue contract is approved (audit findings: [C3/GS-147 section](../exec-plans/evidence/R1_CROSS_WORKTREE_REQUIREMENTS_CODE_AUDIT_20261010.md)). S3 GS-148 and parent GS-131 remain intentionally OnHold as a workstream; P2-D remains partial, production deletion disabled, and P2-E/F/Phase 3 gates open. The pre-integration cross-worktree audit is historical for source-absence claims; this manifest and checkpoint supersede those claims.

Cross-component follow-up remains open: production backend authentication/COMMITTED ownership and live Hub-to-backend-to-PWA flows (GS-117/121) are not proven; S3 storage/FOTA interruption and rollback compatibility (GS-118) remains unqualified. The activity/door assertion failures recorded at the initial integration snapshot are closed as a host fixture defect in the updated integration manifest. The P2-D handoff documents missing production contracts and the supported host fixture without representing it as live deployment evidence.

Untracked user files remain at their original worktrees: battery HIL scripts; S3 `sdkconfig` and `managed_components/`; storage `prompt.txt`; and Phase 2 generated build directories. No code from the unpublished 11-commit classic-storage range was merged.

## Initial integration delivery closeout — snapshot before regression follow-up

**CONSOLIDATION_STATUS=PARTIAL.** Commit `ed6cffcdbfcbd69118e41b436ef616a0bea927db` (`Record R1 source consolidation and validation handoff`) is pushed to `origin/feature/r1-commercial-baseline`; at verification, local HEAD and actual GitHub ref both equaled that hash. The tracked worktree is clean; generated untracked S3 `managed_components/` remains preserved.

At this initial integration snapshot, focused BAT-C8, S3 storage/security/recovery, P2-D HTTP/HTTPS and ASan/UBSan checks passed; clean isolated ESP-IDF 6.0.3 C3 and S3 builds passed. The aggregate failure details are historical and are superseded by the regression-closure section above. Production P2-D authentication/receipt/connectivity, canonical workload, live backend E2E, capacity/retention and physical qualification remain open. No hardware actions occurred; production destructive event/identity reclamation remains disabled.

Jira synchronization comments were added and read back successfully, without workflow or ranking changes: GS-110 comment 10321, GS-114 10322, GS-115 10323, GS-131 10324, GS-147 10325, and GS-148 10326. Evidence and source provenance are in the [dated integration manifest](../exec-plans/evidence/R1_SOURCE_INTEGRATION_MANIFEST_20261010.md). The six-worktree inventory and exact validation details are recorded there.

## Cross-worktree audit handoff — 2026-10-10

The active priority is BAT-C8 physical qualification (GS-114), with GS-144 target, GS-140/B0–B4 and matched AFTER power measurements, GS-119 remaining physical evidence/12-hour soak, and GS-146 C1–C8 closure. Reuse valid battery-branch physical PIR/GPIO4/ACK evidence only when image and setup provenance match. BAT-C8 software/host/build are complete; physical gate remains open. GS-115 stays conditional and To Do.

S3 GS-148/GS-131 are intentionally paused, not cancelled or complete. The reviewed source branch checkpoint is `e1941d7136c43fe6e21f4eff42527aa2d0de9a9a`; P2-D remains partial and production auth/receipt/connectivity/workload acceptance remains open. GS-148 is still In Progress in Jira while its description/comments document the pause; no workflow transition is made here. Production destructive reclamation remains disabled. The [cross-worktree audit](../exec-plans/evidence/R1_CROSS_WORKTREE_REQUIREMENTS_CODE_AUDIT_20261010.md) is preserved as historical triage; current source dispositions are in the [integration manifest](../exec-plans/evidence/R1_SOURCE_INTEGRATION_MANIFEST_20261010.md). No product decision or context-version change is made here.

**Updated:** 2026-10-10

## Authoritative work line
- Worktree: `/home/udaybhan/projects/Ghar_sajag_r1`
- Branch: `feature/r1-commercial-baseline`
- Current P0 product behavior and application-vs-physical evidence boundaries: `docs/product/P0_PRODUCT_REQUIREMENTS.md`.

## Closed / physically qualified

Fresh-install durability path physically proven:
- fresh native ownership/enrollment;
- Node empty-AEAD hardware-AES regression;
- Hub owner stack sizing;
- first durable event commit;
- Hub recovery without watchdog starvation;
- authenticated Node runtime/rejoin;
- Node→Hub transmission;
- ACK class 0 and retirement;
- duplicate ACK safe;
- lost-ACK/reboot/retry duplicate safety;
- final Node retained/in-flight queues empty in lost-ACK qualification.

Do not reopen unless later code/hardware changes can invalidate these gates.

## USB automation

Zero-touch USB automation is convenience tooling, not an R1 product requirement. Keep it out of the critical path while product blockers remain.

## Working-tree reconciliation — 2026-10-07

The previously uncommitted qualified Node empty-AEAD and Hub native durability,
first-commit, stack/recovery, and lost-ACK controls are now committed, along with
their focused tests and existing factory/USB tooling. The canonical storage
contract and GS-D020 Jira traceability are tracked. Existing physical evidence
is preserved unchanged; no hardware test, initialization or flash was repeated.
See [the reconciliation snapshot](../progress/R1_WORKTREE_RECONCILIATION_20261007.md)
for every initial file, commit units, validations and remaining metadata.

Seven focused C++ gates, the production PSA host regression, factory/dispatcher/
profile tests, real Hub ELF checks and USB offline mocks passed. Two optional
initializer-ELF tests were skipped because their artifact is absent. The legacy
`hub-journal-migration-host-test` fails at `clean migration commits` on both the
start commit and reconciled sources; this pre-existing legacy failure is
DEFER_POST_R1 under GS-D001, with no migration fix attempted. `validation-fast`
still includes that target and is not claimed green. Eleven Windows download
metadata streams remain untracked and untouched; no uncommitted implementation
remains. Requirements and context version `2026-10-07.001` are unchanged.

Final lost-ACK source: `docs/hw/evidence/R1_LOST_ACK_FINAL/lost-ack-2h5v9gjp/status.json`.
Selected duplicate record growth is `79 - 78 - 1 independent event = 0`; selected
Node ACK is class=0 retired=1 and final retained=0/in_flight=0. This preserves the
previous physical PASS rather than claiming a new qualification run.

## Current R1 blocker

Hub storage lifetime/data-lifecycle architecture.

The previous fresh-install durability and lost-ACK qualification remains closed. This blocker concerns lifetime behavior after continued household activity; it does not invalidate the already-passed physical proof. Do not spend journal capacity or repeat HIL to investigate the design.

Known requirements:
- current finite append-only journal lifetime is unacceptable;
- reducer/routine state must be durably materialized/bounded;
- exact dedupe retained until retirement semantics safely cover it;
- backend outbox separated logically from local correctness;
- cloud-connected Hub pushes near-real-time;
- PWA reads already-current backend data;
- cloud outage does not stop local safety/routine learning;
- repetitive raw sensor detail can be coalesced;
- new Hub work targets ESP32-S3 N16R8 under GS-D030; preserve prior 4 MiB evidence;
- GS-D025 locks the 72-hour internet-only outage design target; exact retention, supported volume and guaranteed offline capacity remain open.

## Initial storage architecture checkpoint (historical proposal)

Architecture analysis at storage-worktree baseline
`cd8d126ab44689cc9c6ebbbe74e6dce058d4323b` is recorded in
[R1_HUB_STORAGE_DATA_LIFECYCLE.md](../exec-plans/active/R1_HUB_STORAGE_DATA_LIFECYCLE.md).
It recommends a **conditional** 384 KiB lifecycle allocation with dual OTA,
not an approved partition change. Those implementation observations describe
the historical classic ESP32 target at that checkpoint. The canonical branch
now includes the selected S3 segmented encrypted outbox, checkpoint/replay
recovery, completion/identity metadata, mixed-segment host reclamation and
partial P2-D HTTP/HTTPS adapters. The 192 simultaneous Node-pending-key bound
still does not by itself bound accumulated ACKed-but-unreported Hub evidence.

S3 production acceptance remains STOP pending product outage/overflow decisions,
bounded retirement progress, reducer/model limits, backend summary/effect
completion, safe rollback/format transition, commercial image/partition fit and
crash/wear proof. Historical classic-target build sizes do not establish the
current S3 commercial OTA margin.
Existing physical qualification and deferred legacy migration classification
are unchanged; no firmware, physical event or new qualification was performed.

Subsequent efficiency phase preserves that architecture as documentation commit
`94fe1a8` and implements **isolated host-only policy-neutral primitives** under
the code project's `host/storage/`, with dedicated tests and benchmarks. No
production target lists or ACK path are changed. The optimized candidate shares
one immutable event across lifecycle owners; existing 128 KiB feasibility is
**CONDITIONAL**, so partition enlargement remains UNDECIDED rather than assumed.
The 128-event production limit describes the historical classic target, not the
integrated S3 segmented outbox. S3 commercial capacity and lifetime guarantees
remain unqualified. One million simulated events
show fixed 192-record storage and allocation-free primitives; existing journal
and backend completion host regressions pass. These are host results, not
physical durability/GC/rollback qualification. See ExecPlan section 20 and its
host evidence for exact byte budgets, benchmark scope and remaining STOP gates.

Complete S3 production storage/data-lifecycle qualification for the GS-D030 Hub and six-Node worst case. The following accepted implementation areas are integrated, but remain subject to product acceptance and physical proof:

1. active correctness journal and dedupe state;
2. materialized routine/reducer state;
3. backend outbox and completion semantics;
4. short local history/cache and safe reclamation;
5. offline capacity and six-Node worst-case event rates;
6. flash wear, crash-safe cleanup reserve and OTA budget.

Do not implement a guessed retention policy or merely increase the 128-event constant. The 72-hour outage design target is LOCKED by GS-D025; exact retention, supported volume, guaranteed offline capacity and partition-layout changes remain open decisions. See `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md` and `docs/product/DECISION_LOG.md`.

## BAT-C8

GS-D020 traceability: GS-114 — implementation/focused qualification; GS-146 — final R1 battery closure. Issue completion is not inferred from this mapping.

BAT-C8 is an R1-required feature with physical qualification pending (GS-D020). Physical cases P1–P10 remain NOT_RUN; these are test case IDs, not priority labels. Required production proof covers sleep entry, GPIO/timer wake, bounded resume, sensing/runtime and radio restoration, safe fail-awake behavior, and event-processing regression. Do not block on final battery-life optimization or long-duration endurance absent an explicit R1 battery-life claim. No BAT-C8 tests were run as part of the documentation decision.

## Stop rule

If work does not fix an R1 blocker or implement a locked R1 requirement, strongly consider backlog.

## Storage-first requirement checkpoint — 2026-10-07

Qualified isolated core checkpoint: `45f6b00`; million-event bounded fixture re-run PASS. GS-D021/022/023 now lock storage/retrieval-before-CPU priority and failure-aware routine/daily recovery with NO_ACTIVITY distinct from NO_OBSERVATION. Context revision advances from `2026-10-07.001` to `2026-10-07.002`. No production integration or partition approval. Existing primitive evidence does not prove daily finalization, retirement progress, AEAD GC or rollback. Current 128 KiB feasibility remains CONDITIONAL pending those proofs and product/backend limits.

At the GS-D021/022/023 checkpoint, the designated canonical branch still had `.001`; that storage-worktree requirement commit required review/promotion by an explicitly authorized canonical-source action. The density run subsequently started with local/canonical `.002` PASS. Do not silently synchronize worktrees or bypass the context guard. Next step: align approved canonical context, then implement policy-neutral failure models and close time/coverage, backend aggregate revisions, retirement-credit and COW recovery proofs before production work.

Refinement design is in ExecPlan section21: one shared immutable body, conditional derived-nonce84/104-byte records, coverage-aware320-byte daily aggregates,6,144-byte checkpoint candidate, exact128 KiB reservation arithmetic and Node/Hub/backend/day/reclaim failure matrices. No final record size or retention promise is approved. Conservative normal incremental detail capacity is76 records (4.75 hours at384/day);72-hour comparison needs249,856 bytes under the stated worst-record independent-reserve allocation, not a new requirement. Critical reserve8,192 protects one bounded32-record burst only; it does not solve indefinite critical saturation. The finite384 exact-key induction requires persisted admission credits/report progress; production bound remains unproven.

Unchanged core million-event and ASan/UBSan checks, journal/full129 recovery and backend completion regressions, and24 retirement-model tests pass; static byte arithmetic/relative paths and diff checks pass. New coverage/day/reclaim failure models are specified but not implemented: canonical requirement commit must precede dependent implementation, and the new local version must pass the context guard against the designated canonical source first. No hardware result, production integration, CSV change, BAT-C8 or Jira action.

Current no-HIL Hub target build now PASS after explicit C3 artifact build: actual Hub.bin1,864,624 B; current1,966,080-byte slots leave101,456 B. Static DRAM45,783 B/IRAM87,359 B are linker figures, not runtime heap margins. The old384 KiB candidate fails image fit by29,616 B;256 KiB leaves only35,920 B before future code/reserve. No partition resize approved. Build/test provenance: [refinement evidence](../exec-plans/evidence/R1_STORAGE_FIRST_REFINEMENT_20261007.md).

## Storage-density closeout — current handoff, 2026-10-07

Host-only codec/tests/benchmark/evidence commit: `74c4b99`. Initial resume
preflight PASS at local/canonical2026-10-07.002. Existing files and all evidence
were preserved; no expensive passed tests were repeated. Final density
million-event PASS (peak192 keys, fixed storage/RAM, portable hot new0),
ASan/UBSan terminal PASS and current storage/backend/journal regressions
are preserved. Sanitizer exit-status session handle was lost on interruption;
its completed temporary output is byte-identical to the tracked PASS log.
No LeakSanitizer or physical result is claimed.81-field inventory and
static budgets/links/diff checks passed; CSV cells were preserved during
line-ending normalization. Only the missing fast one-day size comparison
was completed with the unchanged codec.

[ExecPlan sections22.10/22.11](../exec-plans/active/R1_HUB_STORAGE_DATA_LIFECYCLE.md)
and [density evidence](https://github.com/udaybhan200683/Ghar_sajag/blob/2b3c6730f8c490ba88a13ba2c23d6674c4c30fa8/docs/exec-plans/evidence/R1_STORAGE_ENCODING_DENSITY_20261007.md)
supersede earlier density recommendations for current planning while
preserving historical/numeric-only comparisons. Full self-contained identity
and config context costs728 B sample /1370 B maximum per independently
restartable4 KiB sector; serializers/security integration are PROPOSED.
Timing-variation median body13/HOT36/WARM15–16 B excludes shared header/tail;
maxima raw101/HOT124/WARM103 B. Conditional fixed100 KiB +variable28 KiB
reservation fits the existing partition arithmetically, not by allocator proof.

Full-source timing-variation retention: NORMAL1281 sample /1056 max-name
records (80.0625/66 hours), HIGH1347/1103, STRESS1457/1181. Synthetic72h
NORMAL plus daily/fixed reserve requires131072 B sample (zero spare),
135168 B maximum (4096 deficit).128 KiB remains CONDITIONAL; no approved
72-hour guarantee or proven partition enlargement requirement. The conservative
prior76-record result and narrower uniform-numeric1595 result use different
representations/reservations and are not production guarantees. Current
1864624-byte image and101456-byte OTA margin remain prior build evidence.

GS-D024 now locks redundancy elimination and compact bounded context/restart
evaluation before storage enlargement. Context advances.002 ->.003, separately
from host work. Designated canonical remains.002; final preflight is expected
STALE and all substantive work must STOP then. No automatic synchronization
or promotion. Next step is explicitly authorized canonical review/promotion
and preflight PASS, followed by policy-neutral authenticated allocator/root/
nonce/reclaim and full dictionary/config recovery proofs. Also close retirement
credit/report bound, exact witness retry projection, offline/saturation policy,
backend daily/effect/revision/substitution, coverage/trusted-time/day recovery,
rollback and target RAM/wear/OTA growth before production integration.

Production integration NO; partition CSV/ACK/backend/PWA unchanged; hardware
unused; BAT-C8/Jira untouched. Existing physical fresh-install gates stay closed.

## Product governance preparation and canonical promotion — 2026-10-08

Storage-worktree preparation (historical checkpoint) at starting HEAD
`d8631e656bd37f05294853de40cec93d65f0cec6`, storage branch
`feature/r1-hub-storage-lifecycle`. Initial preflight PASS and context
`2026-10-07.003`; only user-owned untracked `prompt.txt` was present.

GS-D025–028 now LOCK the approved 72-hour internet-only outage design target,
loss-aware eligible ordinary-motion aggregation, battery-first ESP32-C3 Node
processing and PIR/door/future-bed boundaries. GS-D013/017 are only partially
superseded for these approved directions; their numerical/protocol decisions
remain OPEN. Context advances to `2026-10-08.001`. This preparation does not
authorize production integration or claim capacity/battery qualification.
Existing host evidence is preserved; simulations, hardware and release gates
were not repeated. No production, partition, BAT-C8 or hardware scope changes.

OPEN: critical-event classification/reserve, NORMAL/HIGH/STRESS guaranteed
volumes, critical saturation behavior, quiet gap, progress frequency, final
backend summary protocol and final NVS size. The 4 MB ESP32 Hub remains baseline.
New Node protocol work must prove battery and correctness impact before
implementation; no 40–120-second periodic consolidation wake-ups are approved.
BAT-C8 physical qualification remains pending, with its requirements unchanged.

**Authorized canonical promotion:** promote only the reviewed governance edits
from source commit `4732679aabbe354bb6c771a4b8ac81437d8c45c5` to
`/home/udaybhan/projects/Ghar_sajag_r1` on `feature/r1-commercial-baseline`,
starting clean at `5dcd2f7c10682bd1f6801821deaff20ad4a803e4` and context
`2026-10-07.003`. Canonical context becomes `2026-10-08.001`, matching storage.
The promoted scope is exactly these eight governance files:

- `docs/product/DECISION_LOG.md`
- `docs/product/R1_RELEASE_CONTRACT.md`
- `docs/product/R1_WORK_STATE.md`
- `docs/product/P0_PRODUCT_REQUIREMENTS.md`
- `docs/product/CANONICAL_REQUIREMENTS_INDEX.md`
- `docs/product/GHAR_SAJAG_PROJECT_CONTEXT.md`
- `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md`
- `docs/product/CONTEXT_VERSION`


Existing canonical content is preserved. Storage-only technical checkpoint
notes, ExecPlan section29, prototype code, tests and evidence files are excluded.
The source branch and user-owned untracked `prompt.txt` remain unchanged.
Validate both worktrees with the existing preflight, commit canonical governance,
and push only the canonical branch to the verified origin using a fast-forward
update. Do not weaken the guard. No capacity/battery/hardware qualification or
production implementation is implied; subsequent work requires a separate task.

## Current security-scope governance — GS-D029, 2026-10-08

Product-owner approval locks ordinary power-failure/interrupted-flash crash consistency,
detected-corruption/missing/inconsistent-state fail-closed recovery, and no silent
stale/uncertain routine state. Ownership, durable-before-ACK, retry/deduplication,
retirement credits and protected dependencies are preserved.

Deliberate restoration of an otherwise valid older flash image is outside R1's
data-freshness detection guarantee; AES-GCM is not malicious full-flash rollback
protection. Automatic signed FOTA APPLICATION rollback through ESP-IDF remains
MANDATORY, including firmware validation and compatibility with storage created
by an unsuccessful upgrade. Data rollback exclusion does not waive application
rollback or permit silent erase/reset/stale recovery.

Context advances2026-10-08.001 ->2026-10-08.002. This task explicitly authorizes
reviewed promotion of only these new governance edits into canonical; independent
worktree history is preserved. No storage experiment, code, test, evidence or
ExecPlan is promoted. Previous governance preparation/promotion notes above are
historical checkpoints. Both worktrees must PASS preflight at the new version
before implementation; no guard bypass or new qualification is claimed.

The deliberate older-image replay limitation no longer establishes an R1 requirement
for an independent malicious-data-rollback anchor. Stronger historical host-authority
assumptions remain valid in their stated proof scope. Ordinary power-failure/corruption
freshness, production mapping and FOTA/storage compatibility still require evidence;
this approval does not declare those implementation gates or Gate C passed.

**Next:** resume Gate C protected NVS admission and progress implementation, retaining
ordinary crash/corruption and dependency regressions. Protected reserve/progress,
supported event volumes, critical saturation and the 72-hour capacity guarantee
remain OPEN. No new security hardware, ESP32-S3 or partition change; existing 4 MB
Hub/ESP32-C3 baseline and BAT-C8 requirements/pending qualification remain unchanged.

## Current Hub development direction — GS-D030

Context2026-10-09.001 records the explicit S3 N16R8 selection. By the user-approved
one-time consolidation on 2026-10-10, reviewed S3 source/evidence is integrated
into this canonical worktree and `feature/r1-commercial-baseline`; see the
[source integration manifest](../exec-plans/evidence/R1_SOURCE_INTEGRATION_MANIFEST_20261010.md).
The former S3 worktree and storage branch are preserved as provenance; do not
resume development there. No experimental storage lifecycle code or unapproved
capacity policy was promoted.

The 4 MiB classic Hub is retired from active development, not deleted. Existing
physical PASS results remain valid only for their original hardware/configuration.
S3 target/PSRAM/ESP-NOW/FOTA/heap-stack/recovery qualification is pending.
Initial bring-up must identify and preserve existing device firmware/data before
writing flash. Commercial partitions, sustainable storage reclamation, supported
72-hour volume, critical saturation and R1 end-to-end qualification remain open.
Do not resume classic-ESP32 footprint/capacity optimization or change C3/BAT-C8.

### S3 bring-up checkpoint — 2026-10-09

[S3 evidence](../exec-plans/evidence/R1_S3_HUB_BRINGUP_20261009.md) records
GS-D030 governance, direct reuse of the existing Hub composition and unchanged
C3 asset, successful ESP-IDF6.0.3 S3 builds and a physical diagnostic PASS at
that historical checkpoint. No physical tests were performed during the
2026-10-10 consolidation.
Actual board: ESP32-S3rev0.2,16 MiB flash,8 MiB Octal PSRAM40 MHz; startup/scratch
memory, Wi-Fi and ESP-NOW init and six10-second heartbeats pass. Full private
flash backup verified before writing; original NVS/VFS digests still match.
Final Hub composition1791792 B; development dual4 MiB OTA slots/2 MiB journal
leave2402512 B current unsigned-image margin per slot. The product image was
not flashed. Module/PCB GPIO mapping, provisioning/C3 application interchange,
storage/reclaim/72-hour volume, signed FOTA/rollback and full runtime remain
unqualified; diagnostic heap values do not qualify product peak memory.
Existing host1479 checks, fresh-install, FOTA guard and retirement pass.
Canonical receives governance only; storage worktree/history and C3/BAT-C8 remain
unchanged. No commercial partition/retention decision or new R1 qualification.
Next bring up one authenticated S3-Hub/C3 pair and prove durable ACK/retry/reboot.

## GS-114 Part 1 HIL source audit — 2026-10-11

Source/compatibility audit is complete at `6d0318f644a400caa1f35d9bd0eb4dc9fcb0830b`.
No serial port was opened and no board command was sent. Read-only USB
enumeration was unavailable (`lsusb` is not installed and
`/dev/serial/by-id` is absent), so connected hardware, ports, identities,
firmware, and image hashes are unverified. The existing HIL supervisor remains
incompatible with the selected S3 N16R8 target and has flash/reset/logical-state/
motion-injection paths; the S3 target explicitly rejects legacy HIL controls.
The detailed old-ESP32→S3 compatibility matrix and safe execution boundary are
in [GS-114 Part 1 audit](../hw/evidence/GS114_PART1_HIL_AUDIT_20261011.md),
with the historical HIL document applicability notice in
[HIL automation](../validation/HIL_AUTOMATION.md).

**Status: Part 1 hardware tests NOT_RUN / BLOCKED pending named fixture and
explicit approval.** Before any port open or device interaction, obtain the
five confirmations listed in the evidence record. No production source behavior
changed. Preserve paired-device data and existing authenticated state. After
approval, implement/verify a genuinely non-resetting observation path and an
S3-aware identity/evidence adapter before running only the approved
observational cases. GS-114 Part 2 physical PIR tests remain separate.

## GS-114 authorized clean-fixture checkpoint — 2026-10-11

After explicit user authorization, exact stable USB links and user-designated
ports were checked. esptool confirmed `/dev/ttyACM1` is the dedicated C3
(`14:63:93:c5:d1:58`, 4 MB) and `/dev/ttyACM0` is the dedicated S3
(`7c:4f:ad:b7:2a:20`, 16 MB, 8 MB PSRAM); Secure Boot and flash encryption are
disabled. Fresh matching ESP-IDF 6.0.3 C3/S3 production-profile images and GS-40
configuration bundle built and their image headers, hashes, and partition
tables were verified. No erase/write occurred. The setup stopped before erase
because current R1 commissioning requires an exact authorized `ExpectedNode`
and installer code, but kit provisioning/external authorization is incomplete
and the S3 target lacks the legacy HIL commissioning control. No credentials or
protocol were invented. Detailed source/image evidence, per-test status, RTS
reset disclosure, and the precise prerequisite are in [the clean-fixture
checkpoint](../hw/evidence/GS114_PART1_CLEAN_FIXTURE_20261011.md). Latest Jira
comment records this blocker and required resume action. GS-114 Part 1 A01 has
identity evidence only; A02–A08 remain blocked/not run as listed. No erase/write
occurred, but the dedicated Node's pending-event contents and post-probe runtime
state were not inspected. No Part 2 motion test.
## GS-114 fixture commissioning and focused Part 1 result — 2026-10-11

User-approved, S3-only `GS_HIL_COMMISSIONING` adapter reuses the existing
HubSecurityLink commissioning owner and cryptographic protocol. It is opt-in
and disabled by default; broad S3 HIL-control rejection remains. The disposable
pair was clean-installed after exact C3/S3 identity checks. Fresh association,
authenticated rejoin, C3 software-restart rejoin, and a subsequent authenticated
NodeHealth from the same Node after the S3 app restart were observed. The
five-minute authenticated health cadence and timer-wake counters were captured
without PIR stimulus. Detailed image hashes, logs, machine-readable outcomes,
limitations and validation reports are in
[GS-114 Part 1 fixture evidence](../hw/evidence/GS114_PART1_CLEAN_FIXTURE_20261011.md).

`make validation-node` and `make validation-contract` PASS. `make validation-hub`
remains FAIL (exit 2) solely at the known GS-148
`hub-journal-migration-host-test` assertion `clean migration commits`; all
other registered Hub stages passed. Do not suppress or relabel it. The focused
adapter parser/isolation tests and existing commissioning crypto, rejoin,
association and fresh-install checks pass. Production-profile C3/S3 target
build outcome is recorded in the evidence after completion.

Physical outcomes are bounded: HIL-A01/A02/A03/A06 PASS within the stated
scope, A07 PASS for reported timer wakes only, A04/A05 NOT_RUN, A08 BLOCKED.
No genuine PIR exercise, event Durable ACK, outage threshold, FOTA, RF fault,
current measurement, broad HIL or release gate was performed. GS-114 P1–P9
physical qualification remains open; Part 2 PIR and battery qualification are
not started. The fixture adapter is not GS-109 product commissioning and uses
unprotected development identity material; never ship or use it on protected
or production devices.

Current work remains on `feature/r1-commercial-baseline`, originally at
`73e1e842ff843a696d592bd7c2004b72a512082c`; source, tests and documentation
are pending focused final validation and commit. Existing untracked S3
`managed_components/` is preserved. Next: finish the ESP-IDF 6.0.3 production
profile builds, run preflight/diff checks, commit and push, verify remote HEAD,
then use the already installed disposable pair only for separately approved
GS-114 Part 2 physical PIR qualification.

## GS-148 P2-D CloudSync/API implementation checkpoint — 2026-10-11

**Scope:** User-approved P2-D only. GS-148 P2-E/P2-F, physical Phase 3, GS-114,
hardware, destructive event reclamation and release campaigns remain on hold.
Starting canonical local and origin HEAD: `2b1c15c97a917521c142db1b3973382274c306ff`.
Context preflight PASS (`2026-10-10.001`).

The original P0 failure was reproduced: an unchanged CloudSync EventKey request
reached `JsonApi` with `durable_events=None` and returned its intended
fail-closed `503 durable_event_store_unavailable`. The P0 harness had never
composed the existing file-backed `DurableEventCommit`; this was not a commit
transaction failure or an authorization rejection. The default `http_api.main`
remains the documented development adapter.

Added `backend/ghar_sajag/durable_api.py` as an explicit file-backed composition
of existing migrations, FULL-sync SQLite, `DurableEventCommit`, and
`SQLiteEventMap` caregiver event queries. It requires an externally supplied
authorizer and does not itself authenticate clients. P0 passes the exact
production-shaped CloudSync request through this real API/store, using only an
ephemeral loopback fixture authenticator. The committed exact EventKey is
queryable in Chromium after backend reopen. Positive/negative tests cover
commit-before-receipt, exact retry/restart, conflict, missing/wrong principal,
Home, fixture generation, physical/logical identity, storage failure, timestamp
and payload preservation. The P2-D bridge runs production C++ CloudSync/receipt
code against the real API transaction for 300 events.

**Validation:** latest `make validation-p0-e2e` ran 25/25 scenario assertions
and one Chromium test PASS; its stage command exited 0 but the complete-product
adjudicator and outer make gate FAIL because `product_status=PARTIAL`. P2-D
bridge: 300/300 committed/completed, 3 restarts, 0 pending. Focused API/P2-D
host regressions PASS. `make feature-coverage-test` PASS: 149 feature rows,
201 source modules, 14 physical cases and 19 framework integrity tests. See
[P2-D evidence](../exec-plans/evidence/R1_S3_P2D_CLOUD_VALIDATION_20261010.md)
and report
`code/evidence/validation_framework/p0-e2e-1791733150540893734/report.json`.
No firmware changed; no target build/sanitizer was necessary. No hardware
operation occurred. The historical GS-148 journal-migration assertion FAIL is
preserved and was not rerun.

**Still blocked:** no production Hub credential provisioning/verification is
connected. Hub HTTPS verifies the server CA/hostname and sends an injected
`Authorization` value, while backend trusted middleware is absent. Current API
and schema do not provide the production Hub/Home/Node enrollment-generation
lookup or revocation lifecycle; the Hub request/receipt do not carry generation
fields. File-backed SQLite composition is host validation and not a deployed
PostgreSQL service or complete persistent backend. Do not invent a bearer
credential policy, auth principal contract, generation storage, or wire/schema
change. Exact next prerequisite: approve/document the trusted Hub principal
source, ownership and enrollment-generation binding/revocation source, and
production durable-store deployment adapter; then wire those existing approved
contracts and rerun the P0 E2E. P2-D remains PARTIAL; full P0 and release remain
NOT_APPROVED. Preserve any required GS-130 blocker disposition.

Uncommitted intended changes are limited to P2-D composition/tests, P0 scenario
registration and related validation evidence. Existing unrelated S3
`managed_components/`, GS-114 attempts and redacted logs remain untracked and
preserved. No branch/worktree/history operation or hardware access was made.

## GS-148 P2-D production trust contract checkpoint — 2026-10-11

Scope resumed under GS-148 comment 10444 / GS-109 comment 10445 only. Starting
local and origin HEAD: `18e542873ceec568f70a9358bae6845e39992a54`; preflight
PASS (`2026-10-10.001`). No production firmware/backend security behavior or
wire/storage format changed. Only P0/CloudSync regression tests, scenario
registration, validation traceability and documentation changed. Untracked S3
`managed_components/`, GS-114 attempt directories and redacted fixture logs are
preserved; no physical device was accessed.

The fail-closed API composition/transaction seam is testable and the previous
503 was a harness omission, but the requested production authorization is not
implementable under current approved contracts: no registered Hub principal
issuer/verification and Home ownership authority, no backend Node-generation /
revocation source, no defined retained-old-generation disposition, no approved
receipt-authentication semantics beyond exact EventKey over verified TLS, and
no deployed trusted middleware/database composition or active target CloudSync
caller. The local Hub's persisted commissioning generation is not carried in
the canonical CloudSync body. See the open security-contract entry in
`DECISION_LOG.md` and the 2026-10-11 section of the existing GS-148 P2-D
evidence. This is an explicit `REQUIREMENT_GAP`, not a production defect to
patch by inventing credentials or protocol fields.

Focused evidence: `make p2d-cloud-contract-host-test` PASS (15 invalid receipt
modes and two completion interruption modes); focused durable API/commit/P2-D
Python suite PASS (9 tests; 300/300 deterministic local fixture completions,
three restarts); P0 revocation seam scenario PASS (1/1); P0 scenario registry
integrity PASS (17 use cases/26 scenarios); HTTPS channel host test PASS (8
modes). `make validation-p0-e2e` ran 26/26 scenario assertions and one Chromium
test but exits 2 because complete-product status remains PARTIAL. Report:
`code/evidence/validation_framework/p0-e2e-1791734099302365499/report.json`;
source fingerprint `06487176039b60ddee4c368b72eea5b53c1616bfcd3987e285960c0ce94dd571`.
The historical `hub-journal-migration-host-test` failure remains separately
mandatory and unchanged; it was not rerun. Full P0/release is not approved;
physical HIL is NOT_RUN.

**Next action:** obtain one approved GS-109/GS-148 shared trust contract naming
the Hub credential authority and lifecycle, Hub↔Home registry, Node
generation/revocation source and pending-event behavior on replacement, exact
COMMITTED receipt trust semantics, and production middleware/durable-store
composition. Then implement only that approved slice and rerun focused P2-D/P0
tests. Do not start P2-E/P2-F, hardware/HIL or release-gate-final.

## GS-148 P2-D ownership registry and original-generation provenance — 2026-10-11

Implementation continuation from `ac70f82431c51cc9f7d2975cbc0d04dda4aecb1a`
adds a persistent backend Hub/Home ownership registry, installation-epoch
fencing, Node enrollment generation/revocation history, and a fail-closed
CloudSync authorization guard inside the same durable commit transaction.
Transfer start fences old epochs; transfer completion intentionally remains
blocked until old-Home journal disposition and secure local rebind/reset are
approved. Replaced-generation events cannot be newly admitted; only an exact
already-committed EventKey with matching payload and provenance may replay
under the same active Hub/Home epoch.

S3 CloudSync now has a version-2 host-tested request path that obtains the
original Node enrollment generation from persistent authenticated owner
evidence bound to the event. It reproduces the same request after restart and
fails closed when the evidence is absent. The version-1 compatibility path
remains. No active S3 CloudSync worker calls this path today.

Focused ownership/lifecycle tests pass (6/6), C++ runtime checkpoint and Hub
backend-commit tests pass, P0 scenario registration passes (17 use cases / 30
scenarios), and feature-mapping integrity passes (19 checks; 150 features,
204 source modules, 14 physical cases). `make validation-hub` is FAIL (exit 1,
403.934 s; 34/36 stages PASS) because the historical
`hub-journal-migration-host-test` fails at `clean migration commits` (exit 2)
and the required P0 product status is PARTIAL. `make validation-contract` is
FAIL (exit 1, 264.616 s) at that same P0 PARTIAL status. `make validation-backend`
with the registered command-line receipt reuse is FAIL (exit 1, 147.696 s):
439 Python tests completed with 1 allowed skip and the registered API/frontend
stages passed, but its required P0 product stage remains PARTIAL. After the
final backend-only single-active-Node uniqueness constraint, current
`make python-test` passed 440 tests with one allowed skip in 37.572 s and the
registered ownership stage passed 6/6. Failures remain visible and are not
treated as successful product qualification.
The official clean ESP-IDF 6.0.3 `GS_HIL_BUILD=OFF` C3/S3 target build and
image-capacity/package check passed: C3 934,192 bytes (1,966,080-byte OTA slot)
and S3 1,868,880 bytes (4,194,304-byte OTA slot). Image hashes and build report
are in the linked P2-D evidence record. The build fingerprint preceded the
final backend-only active-Node uniqueness index and test addition; no
Hub/C3/S3 firmware source changed after that build.

The focused Hub runtime checkpoint and backend-commit tests also passed under
ASan/UBSan using the documented `CXXFLAGS` sanitizer profile. After adding the
single-active-Node binding constraint, its conflict test, scenario registration
and GS-116 required marker, the ownership stage passed (6/6), and
`make validation-p0-e2e` reran against source fingerprint
`6af24081bcc769bd73c61cfb498dfa27e6308e63dbb47931ef207ad7cbc49729`. It
completed in 42.025 seconds, executed all 26 full-P0 scenario assertions and
one Chromium test, then exited 2 because product status remains PARTIAL. Current
report: `evidence/validation_framework/p0-e2e-1791742316138312319/report.json`.
The focused P0 registry checker reports 30 registered scenarios; three
ownership scenarios are separately executed by the registered component test.

The registry accepts verified-identity and authorized-operation capability
objects from its caller; this code does not itself verify credentials, issue
them, authenticate the caregiver/installer, or establish production
middleware/deployment. Those trust boundaries remain `BLOCKED` by the open
technical mechanism decisions in `DECISION_LOG.md`. SQLite and lifecycle
behavior are host-tested, not deployed/authenticated production trust. The
previously untracked S3 component directory and GS-114 evidence are preserved;
no hardware or stored device data was touched. Full release is
`NOT_APPROVED`; physical HIL is `NOT_RUN`.

See the implementation and validation record in
`docs/exec-plans/evidence/R1_S3_P2D_CLOUD_VALIDATION_20261010.md`. After final
target-build and remote verification, the next prerequisite is one approved
GS-109/GS-148 technical trust contract for production Hub credential authority,
authorized claim middleware, enrollment/revocation provenance and retained
old-generation event disposition. Do not start P2-E/P2-F, HIL or release-gate.

### GS-148 P2-D final implementation checkpoint — 2026-10-11

This same-worktree continuation implements the approved Hub/Home ownership
policy and original Node-generation provenance at fail-closed backend/Hub
seams. Backend SQLite now records permanent Hub identity/key fingerprint,
one active Home binding, ownership epoch/history, globally monotonic Node
generation history and revocation. The authorization guard runs inside the
durable EventKey commit transaction and stores Hub/epoch/generation provenance.
Hub CloudSync has a host-tested v2 serializer that reads the original
generation from persisted authenticated per-event owner evidence; v1 remains
for compatibility. A single physical Node cannot have active enrollment rows
under two Hubs/Homes. Re-home after explicit revocation requires a strictly
higher generation; the old Home's event stays there and an old generation can
only retry its exact matching previously committed key.

The transition model safely starts and fences a transfer, but cannot complete
it while retained old-Home journal data disposition and local association/key
rebind remain undecided. Capability objects used by the policy are inputs from
a future trusted adapter; their type names do not prove identity or authorization.
No production issuer/verifier, caregiver/installer authorization, deployed
trusted API middleware/database, active S3 CloudSync worker or generation
allocation authority is configured. The existing protected local P256 key is
not asserted to be a cloud credential. TLS plus exact EventKey COMMITTED
remains the implementation's response check; whether production needs a
separately signed owner/generation-bound receipt remains open.

**Final focused evidence** (working-source fingerprint
`dc8e0f8bc91cfcaab9a600e9904e124e5cd64162843b15d29ca1eb9709e9e517`, base
HEAD `ac70f82431c51cc9f7d2975cbc0d04dda4aecb1a`): ownership lifecycle stage
6/6 PASS; full Python suite 440 PASS / 1 allowed skip; feature traceability
integrity 19/19 PASS (150 features, 204 modules, 14 physical cases); P0
registry 17 use cases / 30 scenarios / 30 executable mappings PASS. Latest
P0 run executes 26/26 assertions and one Chromium test successfully, but
`make validation-p0-e2e` exits 2 because product status is PARTIAL; report is
`p0-e2e-1791742681161360468/report.json`. Full Hub/contract/backend reports
remain as earlier recorded; the Hub report includes the mandatory historical
`hub-journal-migration-host-test` failure (`clean migration commits`). That
failure is still FAIL and was not suppressed. Clean ESP-IDF 6.0.3 C3/S3 builds
and targeted ASan/UBSan evidence remain applicable to unchanged firmware
sources, but their earlier aggregate source fingerprint predates the final
backend-only generation constraint.

P0/production trust remains PARTIAL/BLOCKED; product release is
`NOT_APPROVED`; physical HIL is `NOT_RUN`. No hardware, live cloud, production
credential or stored device data was used. No workflow/status/rank/dependency,
locked requirement, storage format or context version changed. Existing S3
`managed_components/` and GS-114 untracked/redacted evidence are preserved.

**Delivery verified:** implementation commit
`1860ebe5d675c8593290bef904a9409004c01681` was pushed to
`origin/feature/r1-commercial-baseline`; local and remote matched. Jira evidence
comments were added to GS-148/GS-109/GS-130 as 10453/10454/10455. This work-state
delivery pointer is included in the final closeout documentation commit.

**Next dependency:** before production trust can be completed, GS-109/GS-148
must identify the Hub credential issuer and key lifecycle, caregiver/installer
claim authority, trusted runtime middleware/database composition,
Node-generation allocation authority, exact COMMITTED receipt trust contract,
and pending old-Home event disposition. GS-109 still owns full Add Device;
GS-148 P2-E/P2-F and physical qualification remain on hold. Product P0 remains
PARTIAL/FAIL, the historical journal migration gate remains FAIL, physical HIL
is NOT_RUN, and release is NOT_APPROVED.

## GS-152 isolated repository restructuring — 2026-10-11

GS-152 is active only on the isolated worktree
`/home/udaybhan/projects/Ghar_sajag_r1_gs152`, branch
`feature/r1-gs152-repository-refactor`, based on canonical source HEAD
`09bc8cd8b7baab0674bbe03157b7b50bab28e51e`. No canonical files, GS-114
fixtures, boards, USB devices or serial ports were changed or accessed.

The active version-stamped source wrapper has been moved to the stable `code/`
layout. Node, Hub, common firmware, backend, frontend, tests, validation and tools
are grouped by responsibility; ESP-IDF target roots remain in place. See
[GS-152 repository layout](../architecture/GS152_STABLE_REPOSITORY_LAYOUT.md)
and [GS-152 baseline evidence](../exec-plans/evidence/GS152_RESTRUCTURE_BASELINE_20261011.md).
The 499-entry source move map records pre-move SHA-256 for tracked files.

Before/after results and baseline failures are recorded in the evidence document.
At the 2026-10-11 implementation checkpoint, baseline `validation-node`,
`validation-hub` and `validation-contract` exited 2 before relocation due to four
existing NodeHealth-config simulator setup errors and a missing Playwright
dependency; Hub also retained the known `hub-journal-migration-host-test`
assertion failure. The migration test remains mandatory and must not be
suppressed. Final post-migration and integration outcomes follow below.

### GS-152 final integration checkpoint — 2026-10-12

The 499-entry move map has 499/499 baseline hashes verified and 499/499
destinations present. It records the original 125 path/build/documentation
adaptations; 6 additional destinations include newer canonical GS-114 changes,
for 368 byte-identical destinations in the integrated source. The
active version-named source wrapper is absent. The archived release manifest
matches its baseline SHA-256 exactly; the prior `UNCHANGED=0` diagnostic was
consistent with the successful `git diff --quiet` return code and did not
indicate an edit.

History-preserving merge commit `0ab12c38b8115c211b66b203289d77f8a835ec00`
incorporated canonical GS-114 through `9272cc7efe171f6fc5f6ceb7fac4ad1c4924fd33`.
The branch then added clean-checkout GS-114 build-discovery and validation
runner fixes, ending at `d802485ee04227b6e1ca16810768e01f0da94009`. Canonical
integration used a fast-forward; exact GitHub and test evidence is in the linked
[GS-152 integration record](../exec-plans/evidence/GS152_RESTRUCTURE_BASELINE_20261011.md).

The clean-checkout C3/S3 target pair and GS-114 S3 RPF diagnostic build passed
under ESP-IDF 6.0.3; the diagnostic selected the fixture commissioning profile,
validated RPF00–RPF08 and matched the candidate partition CSV to the compiled
table. A later redundant rebuild attempt could not start to completion because
the temporary filesystem filled after the earlier verified artifacts had been
produced. No artifacts were deleted. Focused Node, Hub, backend, PWA and
contract regressions ran; ASan/UBSan passed C++ 1,479 and GS-40 1,320 checks,
and board-stack E2E passed all 8 groups.

The aggregate Node/Hub/contract/backend/PWA gates correctly retain FAIL because
P0 reports `product_status=PARTIAL`; all 26 P0 scenario checks and its Chromium
case pass. Hub also retains the pre-existing `clean migration commits`
assertion failure. Both failures remain mandatory and visible, and were present
before this restructuring. No new regression was found. Release qualification
and physical HIL remain NOT_RUN. No serial port or device was accessed.

Canonical source integration is complete. GS-114 hardware qualification was
not changed, and the pre-existing untracked S3 `managed_components/` and
redacted physical evidence were preserved. GS-144 and GS-148 work/statuses were
not changed by GS-152.

## GS-114 repaired C8 physical checkpoint — 2026-10-13

Canonical branch `feature/r1-commercial-baseline` at initial local/remote HEAD
`72a223fc3b290c01c9f93fbb90db83d87601ad54`; context preflight PASS
`2026-10-13.001`. The authorized C3/S3 R&D pair was independently reidentified,
and the RPF07 repair images were clean-installed and flash-verified. Fresh
test-only commissioning and authenticated rejoin succeeded. A real AM312 motion
produced EventKey `p15:c3-146393c5d158n8:gs114-c8s1q1`, authenticated Hub
Durable ACK and one GPIO wake in post-event authenticated NodeHealth. Hub
admission was operational; no RPF07 was logged. The exact successful `RPF00`
reconciliation, C3 application-ACK retirement trace and per-key one-effect
ledger remain unproved because the built-in C3 USB Serial/JTAG console stopped
emitting after light sleep. P1/P2 have partial physical evidence, no PASS;
P3–P9 remain pending or blocked by their specific fixtures. The complete
timestamped redacted logs, hashes and dispositions are in the [GS-114 execution
report](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/EXECUTION_REPORT.md),
and GS-114 Jira comment 10818 records the same checkpoint. Prior migration FAIL
and product P0 PARTIAL remain separate.

A scoped `GS_HIL_COMMISSIONING` S3 diagnostic now builds under ESP-IDF 6.0.3,
logging authenticated NodeHealth detail, successful replay-fence reconciliation,
retirement-ACK send result and per-key durable outbox lookup. The paired build
and focused replay/checkpoint host regression passed; exact image hashes and
partition profile are in the [diagnostic manifest](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/diagnostic_manifest.json).
Both new diagnostic images were then clean installed and flash verified on the
same identified R&D pair. A C3 read-only probe initially stopped at a WSL USB
RTS ioctl timeout before C3 erase; operator C3-only reconnect and an exact
Windows USBIP attach restored the interface, after which the C3-only guarded
install passed. Fresh test-only commissioning succeeded. The first authenticated
Node retirement report physically logged `RPF00 path=PREPARED admission=OPEN`
and authenticated retirement ACK at 16:52:50 UTC: **RPF07 repair physical
retest PASS**. The owner requested pause before the five-minute P1 health
baseline and before any run-02 PIR stimulus. Capture was closed, both serial
ports are unowned, and the installed images/commissioning remain on the boards.
The latest full [pause handoff and results](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/EXECUTION_REPORT.md)
preserve all redacted run-02 evidence and the exact resume action. Source/evidence
commit `b3217b977b6bf77070bc1a52c0c6706eb9cf7a29` matched GitHub before
the pause update; the handoff changes require their own commit/push verification.
Jira GS-114 comment 10819 records the direct RPF00 milestone. The USB console
observer may still require an independent 3.3 V UART/GPIO probe for literal C3
UART and held-HIGH acceptance. GS-114 P1–P9 and GS-146 remain open; GS-149
current/P10 measurements were not made. No CloudSync or C9–C11 implementation
was started. At resume, recheck by-id ports/identity/power/wiring and capture
with a live control channel; reuse installed images, wait for authenticated
timer-wake health and then prompt for real P2 motion. Do not erase first.

## GS-114 C8 physical execution update — 2026-10-14 02:14 UTC

The run03 campaign continued on the existing commissioned boards and diagnostic
images without erase, reflash or recommission. Canonical branch
`feature/r1-commercial-baseline` is at `ec469303d17ea2037019a5bb18d29ce070c249e2`,
matching `origin` at this checkpoint. The P8 fixture, test registration and
evidence updates are now tracked-file modifications in the working tree and
remain unstaged/uncommitted. Existing unrelated untracked PWA/build/evidence
directories are preserved. The new run03 raw capture is also untracked and
active. Context preflight PASS `2026-10-13.001` was verified at resume.

Physical dispositions: Phase A/RPF07 repair PASS; P1 PASS; P2 PASS; P3 BLOCKED
because no GPIO4 level trace proves held-HIGH sleep inhibition; P4 FAIL because
three distinct qualified EventKeys followed one requested motion episode; P5
BLOCKED/inconclusive because first outage-recovery key traffic fell in the S3
capture gap and another distinct durable event appeared; P6 PASS because the
Hub-only restart led to authenticated session 3, RPF00 admission OPEN, and no
Node reset/pending event. Detailed timestamped records are in the
[GS-114 execution report](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/EXECUTION_REPORT.md)
and run03 per-case notes. No source/image change is justified by the observed
P4/P5 anomalies; exact GPIO/event causation remains unproven.

The one-owner S3 capture remains active at the stable by-id path. The Node's
native USB console is silent during light sleep; authenticated NodeHealth over
ESP-NOW is the deferred wake/sleep observer. P7 is ready for a physical
post-reboot event but the operator instructed that motion prompts wait until
they send `available`. The active S3 capture recorded stable session-3 health
through 02:18:45 UTC: reset 11, retained 0, durable ACK 14, GPIO wakes 19 and 40
additional timer wakes since 01:58:46, with no new event or pending work. Do not
reset/reflash/recommission.

While waiting for P7 motion, the separate S3 commissioning-profile-only
`GS_HIL_C8_ACK_DROP` path was implemented in the working tree, default OFF and
separate from broad `GS_HIL_CONTROL`. It requires an authenticated Durable ACK,
new state effect, successful exact-key outbox lookup and OPEN admission before
suppressing one ACK; the same-key duplicate remains on the normal ACK path. The
registered C++ gate test passed 16 checks in ordinary, ASan/UBSan and TSan
builds. The target P8 image has not been built or installed, and no P8 physical
stimulus occurred. P7 still takes priority after the operator sends
`available`. Current installed app hashes remain C3
`1df36cd1a7c779869ea439f2b1e1e45e599c136fd6957ebb59a129870288b814` and S3
`84358b7deab37c1c66aab3fd134fb23dffd6f497493b806c27accb6b19f56df7`.

At this checkpoint local and remote HEAD are both
`ec469303d17ea2037019a5bb18d29ce070c249e2`; source and documentation changes
are uncommitted and unstaged. The active raw S3 capture and pre-existing PWA,
managed-component and historical evidence paths remain untracked and preserved.
Context preflight PASS `2026-10-13.001`. P9's ACK hold still needs a longer
controlled window; no matched signed C3 test/recovery image or trigger was found
for FOTA. GS-114 stays In Progress; P10 is separate under GS-149.
Jira GS-114 comment 10860 records this host-validation milestone and P7 wait.

## GS-148 P4/P5-B1 CloudSync caller — resumed validation checkpoint, 2026-10-14

Resumed at base HEAD `bac66ad3a2fb05307c5200fafd34925a04203d42`, with local
and `origin/feature/r1-commercial-baseline` matching and context preflight PASS
`2026-10-13.001`. Added a registered host production-path scenario joining the
bounded C++ CloudSync worker and HTTP transport to the real local durable API,
SQLite commit, ownership policy and caregiver projection. It covers wrong-Home
and stale-epoch denial before writes, exact original EventKey/timestamps, loss
of the first response after durable commit, backend reopen, byte-identical
retry, duplicate COMMITTED, one durable logical effect and one caregiver
projection. Registration is in the existing local/release stage for Hub,
contract and backend. Full details, commands, source fingerprint, build hashes
and component reports are in the [GS-148 resume execution
record](../exec-plans/evidence/R1_GS148_P4P5_B1_20261014.md).

The new worker/API stage passed in contract and backend component runs at source
fingerprint `a6987bd82c8ce32e41522e030fa31e7e9eca3bb7b3e62550e48d60738a3efc15`.
Framework tests passed 41/41 and feature mapping passed for 184 features, 205
source modules and 15 physical cases. The legacy first-event reader
compatibility test initially exposed a test-only compile dependency on new
worker APIs; a `GS148_OLD_READER` guard fixed it and the focused compatibility
retest passed 11 states for two readers. The new stage's initial matcher also
missed its `unittest`-prefixed PASS line; the registry matcher was corrected and
both affected gates then counted the stage as PASS. Hub storage ASan/UBSan
passed.

`validation-hub` aggregate remains FAIL: its first resumed run also reproduced
the known `clean migration commits` assertion and P0 `product_status=PARTIAL`.
The later contract/backend aggregates remain FAIL only because P0 remains
PARTIAL; the registered worker/API stage and other selected software stages
passed. The full Hub aggregate was not rerun after the two focused test-harness
corrections. P0's 26 scenario checks and Chromium test pass but do not close the
product gap. The Hub migration assertion remains mandatory and unchanged.

An offline ESP-IDF 6.0.3 S3 RPF diagnostic build passed at that same source
fingerprint. Candidate S3 app SHA-256 is
`380790d92bb4ced76c716939d3789157c27ebe8ca1643057d066afa0ef1b5b11`; paired
C3 build SHA-256 is
`c46ceda27adac2175c041a6b0850fddd6d216a2745bb57bd381008e744fb2998`. This is
not a P8 ACK-drop image (`GS_HIL_C8_ACK_DROP=OFF`), neither image was installed,
and no running-image identity or physical CloudSync result is claimed.

Commercial target sending remains disabled pending GS-109 decisions on
credential issuance/verification, trusted Home/Hub/epoch authority and safe
coordination between CloudSync networking and the ESP-NOW admission owner.
P0 is PARTIAL, Hub journal migration is FAIL and release is not approved. No
hardware or `release-gate-final` operation was run. The validated checkpoint is
committed as `3bf08d187e7be24e2cbbc83c3998ec31ee2de962` and pushed with local and
remote HEAD matching. Keep GS-148 In Progress and carry the unresolved
trust/runtime contracts to GS-109 before enabling target sending. GS-148 Jira
comment 10974 records the resumed validation checkpoint.
