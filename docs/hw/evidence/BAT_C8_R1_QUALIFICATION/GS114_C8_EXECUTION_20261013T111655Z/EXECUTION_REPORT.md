# GS-114 C8 physical execution

## 2026-10-14 controlled C3 reset recovery — P3 stimulus pending

The operator authorized one C3-only EN/RST reset after the pre-reset Hub
capture was preserved. The existing S3 reader observed authenticated C3
rejoin as session 16 at `08:15:49.543439605Z`, liveness online at
`08:15:50.028801212Z`, RPF00 `PREPARED admission=OPEN` at
`08:15:59.778409608Z`, and authenticated retirement ACK send `ESP_OK` at
`08:15:59.786565707Z`. Authenticated NodeHealth and schema-3 sleep traces
arrived on the configured heartbeat at 08:20:49, 08:25:48 and 08:30:48 UTC.
Across health_seq 1–3 the Node remained in session 16 with no retained events,
no PIR edges, GPIO4 LOW, no GPIO wakes, timer sleep/wake counts 10→20→30,
radio restoration OK, owner resume OK, and no offline transition by 08:30:59.
This verifies successful post-reset operation and sustained authenticated
liveness. `reset=1` was preserved as the raw reported field; because it was
also present before reset and there is no C3 boot UART for this action, it does
not alone identify the physical reset source.

The operator is away, so no P3 motion occurred. The zero-HIGH trace is a quiet
baseline, not a P3 attempt; **P3 remains BLOCKED / NOT RUN** pending one
controlled real AM312 stimulus after fresh readiness is confirmed. No new
`usbipd attach`, C3 USB serial probe, flash, erase, S3 reset, recommission, or security
change occurred. The current C3 app remains SHA-256
`70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530`; exact
active S3 image hash remains unverified. See the [reset recovery evidence and
resume handoff](run04_20261014/C3_RESET_RECOVERY_AND_P3_HANDOFF_20261014.md).

**Current matrix:** RPF07 PASS (reused); P1 PASS (reused); P2 PASS (reused);
P3 BLOCKED / NOT RUN awaiting operator stimulus; P4 PASS (controlled retest
reused, earlier q10–q12 issue retained); P5 PASS (controlled outage retest
reused, retry observability limitation retained); P6 PASS (reused); P7 PASS
(reused); P8 physical NOT_RUN; P9 ACK and signed-FOTA BLOCKED; P10 remains
separate under GS-149. GS-114 remains In Progress.

## 2026-10-14 diagnostic installation checkpoint — C3 image verified; physical P3 pending

The committed c69960f observer build was verified against its manifest and the
C3 app-only update completed without erasing commissioning or durable state.
The C3 image SHA-256 is
`70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530`; the
actual C3 MAC/revision/flash were `14:63:93:c5:d1:58`, ESP32-C3 v0.4, 4 MiB.
The active `ota_0` slot at `0x20000` was verified, the write hash matched,
and a later partition/otadata read again selected `ota_0`. The C3 then sent
authenticated NodeHealth schema 3 and a physical GPIO/sleep trace through the
Hub. The Hub's S3 runtime decoded the trace and answered `FIXTURE_STATUS`.
The candidate S3 image hash is
`ca178fe30cc620d3fe0cb5817da9d8a98b07b70cb5f7c443045c85180dd46379`; its
exact active flash hash was not read back, so it is not asserted as the exact
running S3 SHA.

The latest authenticated trace (session 15, health_seq 1 at 06:37:24.506Z)
reported one sampled GPIO4 HIGH episode with 6,793 ms max duration, 339
sleep-inhibition samples, zero sleep entries while HIGH, GPIO wake, successful
radio restoration and owner resume. This proves the deferred trace is received
and decoded. The associated setup events were unsolicited and have no
controlled stimulus timestamp, so they are not counted as a P3 result. The Hub
later reported Node liveness offline at 06:52:38.225Z. `FIXTURE_STATUS` at
06:58:28.214Z returned `state=idle`. A later sustained-motion action was
requested, but no completion confirmation or new authenticated Hub line was
received; P3 therefore remains BLOCKED and no reset/reflash/recommission was
performed. Full provenance and limits are in
[the run04 installation/trace note](run04_20261014/C8_C3_DIAGNOSTIC_INSTALL_AND_TRACE.md).

**Current matrix:** RPF07 PASS (reused); P1 PASS (reused); P2 PASS (reused);
P3 BLOCKED; P4 PASS (controlled retest reused, earlier q10–q12 issue retained);
P5 PASS (controlled outage retest reused, retry observability limitation
retained); P6 PASS (reused); P7 PASS (reused); P8 physical NOT_RUN; P9 ACK and
signed-FOTA BLOCKED; P10 is separate under GS-149. GS-114 remains In Progress.

P8's c699 S3 image profile has ACK-drop disabled. The older ACK-drop image
recorded in run03 is from a different source checkpoint and cannot be installed
as the source-matched pair without a current-source build. P9 still lacks the
long ACK-hold observation fixture and a qualified signed test/recovery image,
authenticated trigger and recovery plan.

## Latest run03 checkpoint — 2026-10-14 03:58 UTC

The controlled P7 first-event-after-reboot case now **PASSes**. Hub-only
reboot booted with `POWERON` at 03:34:27.008Z; authenticated Node rejoin
advanced to session 4 at 03:41:27.932Z; RPF00 remained OPEN. The first
post-reboot event after pre-reboot q21 was the operator-requested real AM312
event q22 `p15:c3-146393c5d158n8:gs114-c8s1q22` at 03:52:15.856Z. The Hub
committed one effect, two same-key repeats made no further state changes, and
authenticated retirement ACK send returned `ESP_OK`. NodeHealth at 03:57:15
confirmed `reset=11 retained=0 durable_ack=22 pir_ok=27 gpio_wakes=27`.
The Hub boot banner was captured in full. See [P6 run 02](run03_20261014/C8_P6.md)
and [controlled P7 run 02](run03_20261014/C8_P7.md).

Current statuses: P1/P2 PASS; P3 BLOCKED because the held-HIGH interval lacks
direct GPIO-level/sleep-inhibition evidence; P4 PASS on controlled retest while
the original q10–q12 multiplicity failure remains unresolved; P5 retest is
pending a reconnect-aware exclusive S3 reader; P6/P7 PASS; P8 physical NOT_RUN;
P9 ACK/FOTA blocked on separate fixture prerequisites. No firmware or image
change occurred. Existing authenticated commissioning and image hashes remain
unchanged. Next, transition the single S3 observer to reconnect-aware capture,
then execute P5 with one isolated real motion while only the Hub USB is off.
GS-114 remains In Progress; P10 remains separate under GS-149.

## Latest run03 checkpoint — 2026-10-14 03:25 UTC

The installed, commissioned R&D images remain unchanged. The operator completed
another real sustained-movement P3 attempt. Four distinct PIR EventKeys q17–q20
were durably accepted and ACKed, with same-key retries deduplicated. Authenticated
NodeHealth at 03:25:04.945156252 UTC confirmed `pir_raw=0`, retained=0, reset=11,
durable_ack=20, and continued timer/sleep counters. No C3 UART or direct GPIO4
trace captured the active-HIGH interval, so P3 remains BLOCKED for held-HIGH
sleep inhibition and the four distinct motion events remain unexplained. The
post-stop LOW and normal timer/sleep recovery are observed. Details are in
[C8-P3](run03_20261014/C8_P3.md); the complete live Hub capture is
`run03_20261014/s3_uart_timestamped.log`.

P4's controlled q16 retest remains PASS; its earlier q10–q12 one-stimulus
multi-event failure remains separately preserved. P5 remains BLOCKED/inconclusive,
P6 PASS, and P7 requires a controlled first motion after a new Hub-only reboot.
Before P5, replace the current S3 reader with a single reconnect-capable reader;
the current exclusive reader does not reopen after the Hub USB interface
disappears. Keep P8 physical NOT_RUN and P9 ACK/FOTA blocked on their fixture
prerequisites. No firmware change, reset, reflash or recommission occurred.
GS-114 remains In Progress; P10 remains separate under GS-149.

## Latest run03 checkpoint — 2026-10-14 03:13 UTC (campaign active)

The run03 code checkpoint is `72716c141a788b251e6b630f4684df12028ea847`; the
bounded default-off P8 implementation and target evidence are committed there.
The subsequent q15/q16 evidence and handoff commits are `610c3f3d754ef647d9b0ab0faa284b0465928470`,
`9664b4b9848a67f290dabfe2108c8dd06051675c`, and
`0ae61bd2234da0af8fb1a636cc58f4ef4380347d`; local and GitHub HEAD matched at
the last check. The existing physical pair remains on the previously verified
commissioned images; no reset, reflash or recommission occurred. The exclusive
timestamped S3 capture remains active.

Authenticated NodeHealth at `2026-10-14T02:53:43.472786229Z` was session 3,
health_seq=115, reset=11, retained=0, durable_ack=14, pir_ok=19, gpio_wakes=19,
sleep_entries=1212, timer_wakes=1193, last_wake=TIMER. Four seconds later, with
no controlled motion request/window established, the S3 recorded a qualified
PIR event `p15:c3-146393c5d158n8:gs114-c8s1q15`: first authenticated durable
effect at 02:53:47.987Z (`state_changed=1`, records=15, exact-key outbox found,
admission OPEN), Durable event ACK `ESP_OK`, same-key repeat with
`state_changed=0`, and RPF00 remaining OPEN. An authenticated retirement ACK
send under Hub session 3 returned ESP_OK. The event is an unsolicited physical
observation with no attributable operator stimulus; it is not counted as a
controlled P7 PASS. Authenticated NodeHealth at `02:58:47.560721096Z`
(health_seq=116) then confirmed `retained=0`, `durable_ack=15`, `pir_ok=20`,
`gpio_wakes=20`, reset=11. q15's physical wake and Node retirement are
confirmed; its external motion source and exact GPIO assertion time remain
unknown. P7 stays BLOCKED for the controlled stimulus/timestamp evidence.

The operator then completed one brief, controlled real motion episode for a P4
retest (approximate chat action window 03:00:06–03:00:21 UTC; exact message
receipt time is unavailable). At `03:00:23.713208665Z` the S3 accepted
`p15:c3-146393c5d158n8:gs114-c8s1q16`: first delivery changed the durable
state once (`records=16`, exact-key outbox found, admission OPEN); same-key
delivery at `03:00:23.845314170Z` left `state_changed=0`. The Durable ACK send
returned ESP_OK and the authenticated retirement ACK under Hub session 3
returned ESP_OK at `03:00:24.164475782Z`, with RPF00 admission OPEN. NodeHealth
at `03:05:23.259112457Z` (session 3 / health_seq 117) confirmed reset=11,
retained=0, durable_ack=16, `pir_ok=21`, `gpio_wakes=21`, `last_wake=TIMER`.
There was no additional EventKey during the three-minute post-DONE quiet
window. This is a PASS for the controlled P4 retest; the earlier q10–q12
multi-event FAIL remains preserved and its cause is unproven. No source/image
change, reset or reflash occurred.

Capture verification at 03:06 UTC found the original S3 reader (PID 283926)
still owning the S3 stable by-id port; no C3 port reader was present. No new
reader was opened. Installed hashes remain C3
`1df36cd1a7c779869ea439f2b1e1e45e599c136fd6957ebb59a129870288b814` and S3
`84358b7deab37c1c66aab3fd134fb23dffd6f497493b806c27accb6b19f56df7`, with
the diagnostic manifest's build source `72a223fc3b290c01c9f93fbb90db83d87601ad54`.

The offline P8 ACK-loss target pair remains unflashed: C3 app
SHA-256 `5256779c8c0b592cea219f3e3a3d0c7da72892a37207399bfce388e549c25659`,
S3 commissioning/ACK-drop app SHA-256
`f94192a7c59fa1a7221a7dc4a8394c1bd8c448c2009553e35dfed2f074eccd08`.
`make -C code c8-ack-drop-gate-host-test` passed 16 checks; the S3 fixture
profile suite passed 12/12; GS-130 traceability passed (175 features, 205
modules, 15 physical cases) and its 19 tests passed; physical catalogue
consistency passed for 99 cases with no device access. Previous ASan/UBSan and
TSan runs passed. A Hub validation attempt was intentionally interrupted before
the `host-build` stage could invoke Python: the ACK-drop gate passed 16 checks
and S3 fixture commissioning passed 12 checks; the Hub gate is INCOMPLETE, not
PASS (exit 130). P8 remains physically NOT_RUN; P9 remains blocked on its
independent ACK-hold and signed FOTA prerequisites. Jira GS-114 comment 10861
records the offline build/test milestone. GS-114 remains In Progress.

## Latest run03 checkpoint — 2026-10-14 02:04 UTC (campaign active)

The installed diagnostic firmware remains unchanged on the verified C3/S3 pair. The consolidated results now include actual P1/P2 PASS, P3 held-HIGH BLOCKED, P4 FAIL due three distinct qualified event keys during one requested motion episode, P5 BLOCKED/inconclusive because the S3 capture missed the first outage-recovery key, and P6 PASS for Hub-only reboot recovery. P6 established authenticated session 3 and healthy RPF00 admission without a C3 reset; the S3 boot banner was missed because capture attached after USB enumeration. Case records: [P1](run03_20261014/C8_P1.md), [P2](run03_20261014/C8_P2.md), [P3](run03_20261014/C8_P3.md), [P4](run03_20261014/C8_P4.md), [P5](run03_20261014/C8_P5.md), [P6](run03_20261014/C8_P6.md). The live single-reader S3 capture is `run03_20261014/s3_uart_timestamped.log`.

P7 requires one real PIR event under the post-reboot session. Authenticated NodeHealth at 01:58:46 UTC remained session 3 with no event/pending/reset changes and ten additional timer wakes. Per the operator's instruction, do not request motion until the operator sends **available**. The P8/P9 read-only fixture review found a narrow S3 ACK-drop test profile is feasible after P7, while the P9 ACK hold and signed FOTA image/trigger/recovery prerequisites remain unavailable. Do not reset/reflash/recommission; keep S3 capture running. GS-114 remains In Progress; P10 remains separate under GS-149. No firmware defect has yet been demonstrated by the P4/P5 event anomalies, so no source change or new image was made.

## Operator-requested pause handoff — 2026-10-13 16:56 UTC

## Operator-requested pause handoff — 2026-10-13 16:56 UTC

The owner requested a pause before the session limit. Physical measurement stopped at the logical checkpoint **after the repaired first-retirement RPF07 physical retest succeeded and before any run-02 PIR stimulus**. The run-02 capture process was closed with SIGINT; its C3/S3 serial readers exited and both ttyACM ports were unowned. The credential-bearing raw capture remains in ignored `code/build/gs114_clean_install/session-diagnostic-20261013T1653Z/`; [C3](diagnostic_run02_c3_redacted.log) and [S3](diagnostic_run02_s3_redacted.log) redacted copies are retained here, 108 and 122 lines respectively. No unexpected reset was logged during the run-02 measurement interval. The S3's `POWERON` and C3's `USB_UART_CHIP_RESET` occurred at initial setup capture opening before measurement. Capture stopped before the first five-minute authenticated NodeHealth report; do not infer P1 from that interrupted interval.

Installed on the **only authorized USB-powered R&D pair**: ESP32-C3 MAC `14:63:93:c5:d1:58`, 4 MiB, C3 app SHA-256 `1df36cd1a7c779869ea439f2b1e1e45e599c136fd6957ebb59a129870288b814`; ESP32-S3 MAC `7c:4f:ad:b7:2a:20`, 16 MiB/8 MiB PSRAM profile, S3 app SHA-256 `84358b7deab37c1c66aab3fd134fb23dffd6f497493b806c27accb6b19f56df7`. Both full clean installations and all image writes were verified. The exact nine-file [manifest](diagnostic_manifest.json), [S3 verify](diagnostic_run02_s3_verify.log), [C3 verify](diagnostic_run02_c3_verify.log) and first [C3 USB probe failure](diagnostic_run02_c3_probe_failure.log) are preserved. Fresh exact-identity test-only commissioning succeeded. The S3 reported `RPF00 path=PREPARED admission=OPEN report_generation=2` and authenticated retirement ACK send `ESP_OK` at 16:52:50 UTC. **RPF07 repair physical first-report retest PASS; C8 P1–P9 have no full PASS.** Run-01 real PIR evidence remains partial, not a substituted run-02 test.

The C3 built-in USB Serial/JTAG observer again stopped emitting after its first light-sleep entry; this is distinct from firmware liveness. The earlier C3 installer probe failure was a WSL USBIP attachment fault, resolved by operator C3-only reconnect and exact Windows `usbipd attach --wsl --busid 3-4`; no C3 erase occurred before fresh ROM identity verification. Do not blindly erase, reflash, reopen an occupied port or infer the USB bus ID will remain `3-4` on resume. The S3 commissioning image supports `FIXTURE_STATUS`, not broad `GET_STATE` or ACK-drop/FOTA controls. P8 still lacks a postcommit ACK-loss fixture; P9 FOTA still lacks a qualified signed pair/trigger/recovery plan. An independent 3.3 V UART/GPIO observer may be required if literal continuous C3 UART and held-HIGH traces remain mandatory. Prior migration FAIL and product P0 PARTIAL remain separate.

Canonical worktree `/home/udaybhan/projects/Ghar_sajag_r1`, branch `feature/r1-commercial-baseline`, source/evidence checkpoint `b3217b977b6bf77070bc1a52c0c6706eb9cf7a29` matched actual GitHub remote HEAD before this pause update. Context preflight PASS `2026-10-13.001`. This report and `docs/product/R1_WORK_STATE.md` plus new run-02 verification/redacted evidence are the scoped handoff changes to commit and push. Nine pre-existing unrelated untracked entries, ignored build/raw logs and old failure reports are preserved; no reset/rebase/merge/stash/clean. Jira comments 10818 and 10819 record the physical milestones; a dated pause comment will follow the handoff commit.

**Exact resume action:** verify canonical Git/remote/status and context preflight; read this handoff, Jira GS-114 latest comment, the test plan and diagnostic manifest. Recheck the two stable by-id links, serial owners, C3/S3 power and AM312 3.3 V/GND/GPIO4 wiring before opening a port. Reuse the installed images and preserved commissioning state; do not start with another erase. Start one independent timestamped reader per port with a live stdin/control channel (`tty=true` or equivalent; the last capture lost stdin when launched after IDF shell activation), documenting setup resets separately. Verify authenticated rejoin, fresh `RPF00`/admission health and a five-minute NodeHealth baseline with timer wakes and zero false PIR events. Then ask the operator for real P2 motion and correlate GPIO-wake increment, exact EventKey, `HIL_AUTH_EVENT` outbox lookup/state change, Hub Durable ACK, and subsequent authenticated NodeHealth durable-ACK/retained counters. Continue P3–P9 only where their distinct physical fixtures and prerequisites are met. If Node UART remains silent, keep literal UART-dependent cases BLOCKED or obtain an approved equivalent observation decision; do not call incomplete counters PASS. Do not start GS-148 CloudSync while this explicit pause is in force.

## Repaired-image physical run 01 — 2026-10-13 16:17–16:32 UTC

The canonical local and remote HEAD matched `72a223fc3b290c01c9f93fbb90db83d87601ad54`; context preflight passed. Stable by-id ports had exchanged ttyACM numbers. Direct ROM probes verified the authorized C3 (`14:63:93:c5:d1:58`, 4 MiB) and S3 (`7c:4f:ad:b7:2a:20`, 16 MiB; 8 MiB PSRAM profile). The operator's USB-only supply and AM312 3.3 V/GND/GPIO4 arrangement remained the authorized setup. No other serial owner was present. The ignored installer guard was corrected to resolve stable by-id targets and reject occupied or non-ttyACM links; it no longer assumes fixed ttyACM numbering. All nine repair-manifest hashes and partition/profile bounds were rechecked before writing.

Using the already authorized disposable R&D scope, the S3 was erased, written and `verify-flash` checked at 16:17:42–16:18:59 UTC; the C3 followed at 16:19:00–16:19:08 UTC. Both installer runs exited zero. The installed C3 application SHA-256 was `89b01dfa9c6b48d8430f5427f7f9f89a69b46330280f56923a73a093ffa73da6`; S3 was `c7d63a9959b5df812cae14eb92edc4c18044608a7851fef54f55e8aea7e9a4a6`. The S3 commissioning-only profile retained two 4 MiB OTA slots, `gs_outbox`, `gs_state`, and 16 MiB flash/8 MiB PSRAM. Installer transcripts and credential-bearing raw captures remain ignored under `code/build/gs114_clean_install/`; [C3 redacted log](repair_run01_c3_redacted.log) and [S3 redacted log](repair_run01_s3_redacted.log) are preserved here. Opening the capture caused setup resets before measurement; there was no observed reset afterward. Neither eFuses nor security settings were changed.

Both devices booted. The supported `GET_TEST_QR` → `COMMISSION_EXPECTED_NODE` flow freshly commissioned exact device `c3-146393c5d158` as logical `gs114-c8`; the Hub logged authenticated rejoin session 1 at 16:19:26.333 UTC. The Node logged PIR ready at 16:19:36, then `BAT_SLEEP_DECISION eligible=1` and `BAT_SLEEP_ENTER gpio4=1 timer=1`. The authenticated Hub NodeHealth at 16:24:25 reported 10 light-sleep entries and 10 timer wakes, zero GPIO wakes, no retained event. This proves the Node remained operational and could restore its radio to transmit authenticated health.

The operator performed one real AM312 motion episode for P2 and replied DONE. At 16:26:55.880 and 16:26:56.081 UTC, the Hub accepted the **same** exact EventKey `p15:c3-146393c5d158n8:gs114-c8s1q1` twice, both `ack=0` (`AckClass::Durable`) with `ESP_OK` send. At 16:31:55, authenticated NodeHealth showed `gpio_wakes=1`, `sleep_entries=26`, `timer_wakes=25`, `retained=0`. This is positive physical GPIO wake, authenticated PIR transport and durable ACK evidence. It does not alone prove the exact C3 ACK retirement or one authoritative logical effect. No RPF error appeared, and the successful event confirms admission was open, but this image emits no `RPF00` success record, so the exact first-retirement-report reconciliation remains unproven directly.

The C3 native USB Serial/JTAG reader emitted no bytes after its first light-sleep entry, including after a queued `GET_STATE`, while authenticated radio health/events continued. ESP-IDF 6.0.3's USB Serial/JTAG documentation warns that light sleep can interrupt host enumeration. The continuous Node UART ordering and Hub counter snapshots required by the test plan therefore are unavailable. **P1/P2 remain BLOCKED on observer completeness, P3–P9 remain NOT_RUN/BLOCKED; no physical PASS is claimed.** Capture was closed at 16:32:21 without reopening either port. This is an observation failure; the live C3 did not show a runtime stall.

`BUG_CLASSIFICATION=TEST_INFRA_ONLY`; `REQUIREMENT_SOURCE=docs/hw/evidence/BAT_C8_R1_QUALIFICATION/TEST_PLAN.md`; `DECISION_IDS=GS-D020`; `TASK_SCOPE=GS-114 physical observer and RPF07 retest`; `OUT_OF_SCOPE=CloudSync, storage redesign, C9–C11`. A commissioning-profile-only read-only S3 diagnostic was added to log authenticated NodeHealth detail, successful `RPF00`, retirement ACK send result, and authoritative per-key outbox lookup. It changes no protocol, eFuse, durable admission or production profile. Retest requires source-matched target build/hash/verify and a justified fresh R&D installation. If post-sleep Node UART is still required literally, an independent GPIO/UART measurement interface is an external fixture prerequisite.

The paired diagnostic build subsequently passed with source fingerprint `1eec58fa1f77902c589e416db661b793d842320e33b1acc8073d677c460d1879`, ESP-IDF 6.0.3, C3 app SHA-256 `1df36cd1a7c779869ea439f2b1e1e45e599c136fd6957ebb59a129870288b814` and S3 app SHA-256 `84358b7deab37c1c66aab3fd134fb23dffd6f497493b806c27accb6b19f56df7`. All nine exact artifacts passed independent manifest hash checks; S3 remains commissioning ON, broad HIL OFF, two 4 MiB OTA slots, `gs_outbox`/`gs_state` and 16 MiB/8 MiB PSRAM. Focused Hub replay/checkpoint host regression, 19 traceability framework tests and `git diff --check` passed. This new pair has **not** yet been installed; the boards still carry the run-01 repair images at this checkpoint.

## Diagnostic physical run 02 — 2026-10-13 16:47 UTC onward

The source/evidence checkpoint was committed and pushed as `b3217b977b6bf77070bc1a52c0c6706eb9cf7a29`; exact GitHub remote HEAD matched, and tracked files were clean. Context preflight passed. The [diagnostic manifest](diagnostic_manifest.json) was rechecked against all nine artifact hashes and build receipt. Both stable by-id ports were unowned. The S3 re-probe matched ESP32-S3 MAC `7c:4f:ad:b7:2a:20`, 16 MiB and unchanged disabled Secure Boot/Flash Encryption. It was clean erased, written and [verified](diagnostic_run02_s3_verify.log) at 16:47:36–16:48:52 UTC. This verification left the board in the expected setup bootloader state until capture opened.

The first C3 read-only identity probe then failed at the USB serial RTS ioctl with `OSError: [Errno 62] Timer expired`; [the first failure](diagnostic_run02_c3_probe_failure.log) is preserved. The installer stopped **before C3 erase** and did not repeat S3 erase. WSL's by-id link still existed but the native-USB interface was unresponsive after light sleep/manual `screen`; WSL logged USBIP URB errors. On the operator's requested C3-only USB disconnect/reconnect, Windows `usbipd list` showed COM4, VID:PID `303a:1001`, bus `3-4` as `Shared` rather than attached to WSL. A targeted `usbipd attach --wsl --busid 3-4` restored only that identified C3 interface. A new ROM probe independently returned ESP32-C3 MAC `14:63:93:c5:d1:58`, 4 MiB. The guarded C3-only continuation rechecked exact identity, security and hashes, then erased, wrote and [verified](diagnostic_run02_c3_verify.log) at 16:52:09–16:52:17 UTC. The [continuation installer](execute_install_run02.py) required the five successful prior S3 verify digests and refused any other role sequence. This was a USB/WSL fixture transport failure, not a C3 firmware or flash error. No eFuse operation occurred.

Opening the two independent capture readers caused documented setup resets before measurements: C3 `USB_UART_CHIP_RESET`, S3 `POWERON`. Both diagnostic images booted. Fresh `GET_TEST_QR` → `COMMISSION_EXPECTED_NODE` succeeded; authenticated rejoin device `c3-146393c5d158`, logical `gs114-c8`, session 1 was logged at 16:52:39.929 UTC. **At 16:52:50.150 UTC the S3 logged `S3 replay fence healthy stage=RPF00 path=PREPARED admission=OPEN report_generation=2` for the first authenticated Node retirement report, followed at 16:52:50.151 by `Authenticated retirement ACK session=1 generation=2 send=ESP_OK`.** This is direct physical confirmation that the repaired first-report reconciliation no longer fails at RPF07. The C3 entered light sleep at 16:52:50.441; no P1–P9 PASS is inferred from commissioning or this first report alone. The full ongoing raw capture remains private under `code/build/gs114_clean_install/session-diagnostic-20261013T1653Z/`; redacted copies and later case dispositions will be added after observation.

## Resume checkpoint — 2026-10-13 UTC

GS-114 Jira comment 10800 and the pause handoff were reconciled against the
canonical branch. Local and remote HEAD remained
`93935e345a29e3b119f460fda5e9294477b6f798` at resume; all scoped dirty
source/evidence and pre-existing untracked data were preserved. Context
preflight PASS. The old S3 esptool process is gone and no serial reader owns a
port, but **neither authorized `/dev/ttyACM0` nor `/dev/ttyACM1` currently
exists in WSL**. No serial port was opened and no repair erase, write, reset,
recommissioning or P1–P4 stimulus was attempted on resume. Operator USB
reattachment and renewed power/wiring confirmation are pending.

All nine selected repair artifacts exist and their byte lengths and SHA-256
match [the corrected repair manifest](repair_manifest.json) and actual build
receipt. The manifest's previously copied S3 profile fields were updated to
the verified repair receipt: S3 app 1,889,280 bytes and embedded C3 SHA-256
`89b01dfa9c6b48d8430f5427f7f9f89a69b46330280f56923a73a093ffa73da6`.
The fixture remains the commissioning-enabled 16 MiB/8 MiB PSRAM profile with
`gs_outbox`/`gs_state`. `GS114_REPAIR_MANIFEST_CHECK=PASS`. This is offline
artifact evidence; installed boards still run the first failed image.

Focused `hub-runtime-checkpoint-host-test`, `hub-fresh-install-host-test`,
`feature-coverage-test` and the paired target build PASS. The completed
`make validation-hub` receipt at
`code/evidence/validation_framework/hub-1791904599768894359/report.json`
records 38/40 stages PASS, source unchanged, exit 2: known journal migration
failure (`clean migration commits`) and product P0 `PARTIAL`; checkpoint,
fresh-install, board-stack, storage correctness and sanitizers PASS. The
completed `make validation-contract` receipt at
`code/evidence/validation_framework/contract-1791905308298399721/report.json`
records 33/34 stages PASS, source unchanged, exit 2: only product P0 `PARTIAL`;
the contracts, board-stack, fresh-install and affected Hub cases PASS. Both
receipts use source fingerprint
`51484c36451d1502c75e4f4ba2a101b1144b416407bfbe6adbc79695e391f3bc`
and classify physical evidence NOT_RUN. These known broader gates are not
reported as PASS. The initial interrupted Hub invocation remains recorded
as interrupted in the pause checkpoint below; this completed rerun supersedes
its incomplete gate status.

## Pause/resume handoff — 2026-10-13 UTC

The operator requested a pause before the session limit. Physical execution is
stopped at the first-failure repair checkpoint: original clean images are still
on the C3/S3 boards; repaired images are built and hash-verified but **have not
been flashed**. Phase A is FAIL at fresh-install S3 `RPF07`; P1–P9 have no
physical PASS. No repeat erase or flash for the repair was attempted.

Canonical worktree `/home/udaybhan/projects/Ghar_sajag_r1`, branch
`feature/r1-commercial-baseline`, pre-handoff local HEAD
`93935e345a29e3b119f460fda5e9294477b6f798`; remote matched at task
startup. Context preflight PASS `2026-10-13.001`. This report, the four scoped
Hub source/test files, and the validation traceability CSV were modified for
this checkpoint; new redacted logs, verification logs and repair manifest are
being committed. Nine pre-existing unrelated untracked entries and ignored
private raw logs/builds remain untouched. No reset/rebase/merge/stash/clean.

Repair target build: ESP-IDF 6.0.3, C3 app SHA-256
`89b01dfa9c6b48d8430f5427f7f9f89a69b46330280f56923a73a093ffa73da6`,
S3 app SHA-256
`c7d63a9959b5df812cae14eb92edc4c18044608a7851fef54f55e8aea7e9a4a6`.
[Repair manifest](repair_manifest.json) records bootloader, partition, OTA,
outbox, image and build-receipt hashes. The S3 build uses its 16 MiB
commissioning profile with `gs_outbox`/`gs_state`, 4 MiB OTA slots and 8 MiB
PSRAM; C3 is 4 MiB. At-build source fingerprint
`ee9fe393cfed897ef392547dc92cc3b5bd85d9e8e7f78f124505d5a80ab2a249`;
the only later source-fingerprint input change was registering the new test in
`MASTER_TRACEABILITY.csv`, not a firmware source edit.

`make hub-runtime-checkpoint-host-test`, `make hub-fresh-install-host-test`,
`make feature-coverage-test`, target paired fixture build and `git diff --check`
PASS. `make validation-hub` was interrupted for this requested pause after the
known `hub-journal-migration-host-test` failure was reproduced; no full gate
PASS is claimed. Contract and physical repair retest NOT_RUN. The attempted
read-only S3 `flash-id` re-probe hung in uninterruptible kernel I/O before an
identity result; its parent and the validation gate were terminated. The C3
re-probe was not reached. S3 boot/serial state is therefore unknown at pause.

Resume at USB/process inspection, then independently reidentify both exact
authorized chips/ports and verify repair image/profile hashes before any
further erase/write. If safe, perform one controlled clean repair installation,
verify flash, recommission via `GET_TEST_QR` → `COMMISSION_EXPECTED_NODE`,
capture independent timestamped logs, and physically retest admission/RPF00
and durable authenticated transaction. Start P1–P4 only after stable Phase A;
retain the test plan's separate P5–P9 operator actions and prerequisites.
Never infer a physical PASS from these software results.

2026-10-13 UTC. Current checkpoint: Phase A clean installation and authenticated commissioning were executed; first Hub replay-fence reconciliation **FAILED**, and admission closed. A targeted source repair passed focused host validation; rebuilt target images and physical retest are pending. P1–P9 are not qualified.

## Phase A first physical attempt, 11:58–12:05 UTC

The operator confirmed USB-only power, no competing supply, and AM312 VCC at 3.3 V/GND shared/OUT to C3 GPIO4. Stable USB interfaces matched COM4 (`/dev/ttyACM0`) and COM9 (`/dev/ttyACM1`). Direct ROM probes before the first erase identified C3 revision 0.4, MAC `14:63:93:c5:d1:58`, embedded 4 MiB XMC flash; S3 revision 0.2, MAC `7c:4f:ad:b7:2a:20`, 16 MiB flash and reported 8 MiB PSRAM. Both reported Secure Boot and flash encryption disabled. No eFuse operation occurred. Probe outputs are retained in private ignored storage.

The first, hash-checked manifest was installed only on those identified boards. Both complete flashes were erased, written and `esptool verify-flash`-verified, including S3's empty 4 MiB `gs_outbox` image. C3 app SHA-256 `ad173384e827614bcbb62c0deac60b5d866dd144088528523c5711e5c2409e43`; S3 app SHA-256 `8c53b999c001095030c7f150854b9637404b666364470131f1511cffdc34a4f7`. [C3 verification](install_c3_verify.log) and [S3 verification](install_s3_verify.log) are retained. Setup resets on opening the UARTs occurred before any qualification measurement; they are not claimed as stable observation.

Both images booted. The first host bridge sent LF-only S3 commands that produced no usable fixture response; a bounded `FIXTURE_STATUS` probe with CR framing returned `state=idle`. The bridge was corrected in private ignored test tooling to pace S3 UART bytes and terminate with CR. No reflash was used for this fixture-side correction. The corrected setup accepted `GET_TEST_QR` on C3 and `COMMISSION_EXPECTED_NODE` on S3, then the Hub logged exact authenticated rejoin of `c3-146393c5d158`, logical `gs114-c8`, session 2 at 12:04:37.803 UTC. S3 `FIXTURE_STATUS` returned `authenticated_rejoin`; C3 started its runtime and reported PIR ready on GPIO4. Credentials remain only in ignored private raw logs; the [C3](setup02_first_rpf07_c3_redacted.log) and [S3](setup02_first_rpf07_s3_redacted.log) evidence copies redact them.

At 12:04:48.028 UTC, before any qualified PIR event, the S3 logged `RPF07 SELECTED_CHECKPOINT_MISSING path=PREPARED admission=CLOSED report_ack=withheld`. Capture stopped immediately. The authenticated report had advanced the NVS selected checkpoint, while `HubDurabilityOwner::recovery_state()` still held the initial boot snapshot with no report reference. `HubRuntime::reconcile_replay_fence()` reloaded the new selection for publication but its binding check compared the old owner cache. This is a fresh-install runtime defect, not a residual from erased experimental state. No EventKey-to-Durable-ACK physical PASS exists.

`BUG_CLASSIFICATION=R1_BLOCKER`; `REQUIREMENT_SOURCE=docs/product/R1_RELEASE_CONTRACT.md; docs/product/CANONICAL_REQUIREMENTS_INDEX.md (durable-before-ACK and replay-fence invariants)`; `DECISION_IDS=GS-D020; GS-D030`; `TASK_SCOPE=GS-114 Phase A targeted durability repair`; `OUT_OF_SCOPE=storage redesign, CloudSync, C9-C11`.

The scoped repair refreshes the owner cache from the authenticated selected durable store during runtime fence reconciliation, checks the store/epoch binding, and closes admission if refresh fails. A new production-code host regression reproduces fresh genesis → first authenticated retirement report → selected checkpoint advance → fence bind, plus a failed-refresh negative case. `make hub-runtime-checkpoint-host-test` and `make hub-fresh-install-host-test` passed with `TMPDIR=code/build/gs114_tmp` after the default 1.9 GiB `/tmp` tmpfs proved full. This is software evidence only; the physical retest is pending.

Historical preparation source: `5ee96fd24b4a82b2a11b928cb40f2638eaee9616`, canonical `feature/r1-commercial-baseline`; actual GitHub HEAD matched at that preparation startup. Context preflight PASS `2026-10-13.001`.

This execution follows GS-114 10732, which supersedes old experimental-state preservation for the identified disposable R&D C3/S3 pair. Prior failure logs and STOP reports are preserved.

Verified current-source fingerprint: `c07ae9a0cb79491379d4de65f6c83d7b31b3c0d7613bc3d9e2f912c2c1fcce83`; build receipt records `774da5c2ee8073c535df2fe56ecdbf548c16ebf0` with the Option A working-source implementation. Both current app hashes match that receipt. ESP-IDF 6.0.3 and esptool 5.4.0 activated. No source changes or repeat GS-148 fault campaign.

See [preparation manifest](preparation_manifest.json) for first-install bootloader/table/otadata/app/outbox hashes, offsets, profiles and exact command argument arrays, and [USB inventory](usb_inventory.txt). Artifact verification and compiled partition decode PASS. Fresh 4 MiB empty LittleFS generated with the component-pinned littlefs-python 0.15.0; host mount with target read/program/cache configuration and empty directory check PASS. A preliminary host validation invocation used an incorrect UserContext constructor and failed; corrected API invocation passed without changing the generated image.

Prior `USB_UART_CHIP_RESET` and replay-fence admission closure remain UNRESOLVED HISTORICAL REGRESSIONS. Clean installation cannot qualify recovery of that discarded old state.

## Execution scope

Owning Jira GS-114; affected C3/S3 fixture setup, USB capture, authenticated commissioning, Hub replay-fence runtime, GPIO4 light sleep, EventKey/ACK/durability contracts. Existing GS-150 and GS-148 software receipts are reused after exact source/artifact checks. The scoped Hub runtime owner-cache repair changes no protocol, security, persistent format or app/backend behavior. Physical tests require actual operator stimuli. Full release/current/GS-148 fault campaigns NOT_RUN; prior mandatory migration FAIL and product P0 PARTIAL remain.

## Case results

| Case | Disposition | Evidence / blocker |
|---|---|---|
| Phase A | PASS for RPF07 repair / fresh authenticated fixture; C3 USB observer limitation remains | Repaired image install/verification and fresh commissioning; first authenticated retirement report produced `RPF00 admission=OPEN` and ACK send; continued physical event admission confirmed |
| P1 | PASS | Ten timer sleep/wake cycles plus 25 more; authenticated post-wake health, no false PIR event or Node reset; see [P1](run03_20261014/C8_P1.md) |
| P2 | PASS | Real AM312 motion, exact q1 EventKey, GPIO wake, one durable effect, authenticated Durable ACK and retained=0/durable_ack increment; see [P2](run03_20261014/C8_P2.md) |
| P3 | BLOCKED / latest controlled window NOT RUN | Prior sustained movement produced multiple distinct qualified events and eventual LOW recovery, but did not prove a continuous GPIO4 HIGH interval. On 2026-10-14 at 07:55 UTC the operator confirmed the latest requested window had no motion; the Hub had marked session 15 offline at 06:52:38.225783443Z, beyond its configured 910-second lease, with no fresh authenticated NodeHealth/rejoin/event. USB enumeration remains present but does not prove application liveness. No P3 prompt was issued and no board operation was performed. See [P3](run03_20261014/C8_P3.md) and [run04](run04_20261014/C8_C3_DIAGNOSTIC_INSTALL_AND_TRACE.md). |
| P4 | PASS on controlled retest; original trial FAIL retained | Controlled brief motion produced q16, one Hub durable effect, same-key duplicate suppression, authenticated Durable ACK and Node retirement; no extra key in the three-minute quiet window. Earlier q10/q11/q12 remain distinct durable events with unexplained cause; see [P4](run03_20261014/C8_P4.md) |
| P5 | PASS — controlled reconnect-aware run 03; initial run02 remains inconclusive | One real AM312 event during Hub power-off arrived as q24 after authenticated session 6, changed durable state once, received Durable ACK, and was retired with reset unchanged; post-ACK retained=0, durable_ack +1. See [P5](run03_20261014/C8_P5.md). |
| P6 | PASS | Run 02 captured full Hub POWERON boot, authenticated session 4, RPF00 admission OPEN and Node reset counter unchanged at 11; see [P6](run03_20261014/C8_P6.md) |
| P7 | PASS — controlled run 02 | First event q22 during prompted AM312 action window; one durable effect, two same-key idempotent repeats, authenticated retirement ACK, post-event health confirms retained=0 and durable_ack increment; see [P7](run03_20261014/C8_P7.md) |
| P8 | BLOCKED physically; fixture implemented | Default-off S3 commissioning-profile-only one-shot postcommit ACK suppression and 16-check normal/ASan/UBSan/TSan PASS; matched target build, installation and real same-key retry await P7; see [P8](run03_20261014/C8_P8.md) and [software validation](run03_20261014/C8_P8_SOFTWARE_VALIDATION_20261014.md) |
| P9 ACK | BLOCKED | No qualified directional ACK hold fixture; P8 one-shot loss alone is shorter than the required pending-ACK observation window; see [P9](run03_20261014/C8_P9.md) |
| P9 FOTA | BLOCKED | No matched signed C3 test/recovery image pair, supported signed trigger or known recovery procedure; see [P9](run03_20261014/C8_P9.md) |
| P10 | NOT_RUN | GS-149 owns quantitative acceptance; no instrument/current measurements |

Next action: the minimal HIL-only authenticated deferred C3 sleep/PIR trace is implemented and its Node/Hub/contract component stages pass. Commit and push this scoped change, build and hash-verify the source-matched C3/S3 commissioning pair, then install only on the identified R&D fixtures and physically retest P1/P3. P8 still needs physical ACK-loss qualification; P9 ACK and signed FOTA remain blocked on their specific fixtures. Do not move GS-114 to Done while applicable criteria remain incomplete or blocked.

## Validation and precise operator checkpoint

- `tools/context/ghar_sajag_context_preflight.sh`: PASS, exit 0, context `2026-10-13.001`, at startup and after documentation edits.
- Retained fixture app hash/size, exact embedded C3, current source fingerprint and S3 profile verification: PASS, exit 0. Both compiled partition tables decoded with IDF's `gen_esp32part.py`; OTA fit and outbox offsets checked. Build reuse only; target compilation was not repeated.
- `idf.py --version`: ESP-IDF v6.0.3, exit 0. Offline C3 `esptool image-info`: valid checksum/hash, C3/4 MB/DIO/80 MHz, ESP-IDF 6.0.3, exit 0. S3 independent image-info is retained in the matching build receipt.
- `littlefs-python create ... --fs-size=4194304 --block-size=4096 --name-max=64`: exit 0. Corrected host read-only image mount with target geometry: empty root directory, exit 0. S3 actual mount NOT_RUN.
- `make physical-hil-catalogue-test`: PASS, exit 0; 99 cases, 68 required and 40 conditional feature mappings checked, `device_access=NONE`.
- `python3 -m py_compile code/build/gs114_clean_install/prepare-20261013T111214Z/live_capture.py`: exit 0. This is an ignored session wrapper around existing `tools.hil.core.SerialCapture` and `FixtureLock`, not a new HIL framework or an executed capture. It requests DTR/RTS low before opening, keeps one reader per port, never automatically reopens a disconnected port, and stores credential-bearing raw commissioning output only under ignored private storage. Syntax check does not prove observation reliability.
- `git diff --check`: exit 0. The later scoped Hub firmware repair and its focused tests are recorded in the pause handoff above. Backend/PWA and release campaigns were not run. Prior GS-148 migration FAIL and product P0 PARTIAL remain independently recorded.

The owner subsequently supplied the exact board, power, wiring and Phase A erase/flash authorization. The first manifest's operations above were executed and verified. A repair retest must reidentify both exact chips/ports and verify new image hashes before another clean installation. Use only fresh private test credentials and `GET_TEST_QR` → `COMMISSION_EXPECTED_NODE`, never the incompatible generic factory driver.

The S3 commissioning-only image accepts `FIXTURE_STATUS`, **not** `GET_STATE`, broad HIL, ACK-drop or FOTA controls. Canonical P1/P4 Hub-counter snapshots therefore require a verified compatible read-only observation path before complete acceptance; do not label unsupported commands or counter-only reasoning PASS. The current RPF diagnostic emits failure stages only; absence of RPF errors alone is not an observed `RPF00` success. Confirm healthy admission through authenticated durable transactions and capture the required fence proof before qualification. These instrumentation limits remain explicit; no acceptance criterion is waived.

## Subsequent measured work

GS-144 still needs owner acceptance of representative event/outage workload rates, selected battery/power-path usable capacity and reserve, minimum endurance and caregiver latency/reliability bounds. The 150–180 day goal remains aspirational; no measured battery-life claim. Its separate historical workload branch is a read-only provenance source and was not integrated or recreated.

GS-140/B0 requires a real identified instrument, range/burden/sample rate/uncertainty, voltage and measurement boundary. GS-41/42/141/43/44 own comparable B1–B4 BEFORE and GS-51 owns AFTER; current C3/S3 images are not interchangeable with the old `bb34f5e` baseline without a matched-profile decision. None was physically measured here. GS-149 P10 remains blocked by those inputs and GS-114 acceptance; GS-146 also needs GS-119, GS-46 and GS-69 accepted evidence. GS-115 decisions remain C9 REQUIRES_MEASUREMENT/product semantics, C10 MEASURE_ACTUAL_WRITES_FIRST, C11 POST_R1, C12 DEFERRED. No subsequent firmware implementation is approved by these statuses.
