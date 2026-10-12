# GS-114 Part 2B — Root-cause investigation

**Date:** 2026-10-12 UTC
**Investigation source HEAD:** `7c1fee29e17fc3fe12c840e0afef5fa6b7217b68`
**Physical log source:** `09bc8cd8b7baab0674bbe03157b7b50bab28e51e`
**Scope:** saved evidence, source and host-only tests. No USB enumeration, serial open, board access, firmware/storage change or physical test was performed.

## Findings

The two observed messages identify different events. The C3 reset reason is a USB-UART reset source. The S3 error is a fail-closed consistency gate between its selected retirement snapshot and the replay-fence witness used for durable event admission. A C3 reconnect may have caused the report that entered the S3 path, but the saved logs do not prove that causal link or the lower-level S3 failure.

## C3 reset and observer ordering

The saved C3 log begins with `rst:0x15 (USB_UART_CHIP_RESET)`. ESP-IDF 6.0.3's ESP32-C3 ROM header assigns enum value 21 to `USB_UART_CHIP_RESET` and describes it as a USB-UART reset of the digital core. This identifies the reset class; it does not timestamp when the reset signal was asserted or identify which host operation asserted it.

The observer sequence is in `tools/hil/gs130_hil_common.py:132-151`. It creates a pySerial 3.5 object with no open port, sets its requested DTR and RTS states low, assigns the interface, then calls `open()`. The installed POSIX `Serial.open()` implementation at `/usr/lib/python3/dist-packages/serial/serialposix.py:319-338` calls `os.open()` first, then configures termios, then applies DTR and RTS through ioctls. Thus the requested low states are not applied before the kernel device-open operation. The observer sends no serial bytes or commands, but the interface open can still change modem-control state. Existing R1 hardware notes also record C3 native USB Serial/JTAG monitor reconnects causing `USB_UART_CHIP_RESET` and a new boot/session identity.

**Assessment:** observer open or its USB re-enumeration is the most likely cause (high likelihood, not proven for this capture). The reset banner was received during the 60-second capture, but neither raw log timestamps individual lines against the host open timestamp. The evidence therefore cannot distinguish a reset just before open, during the open/line-configuration window, or an independent reset immediately before capture. No evidence indicates that the observer sent a device command.

The current C3 console is the Espressif USB Serial/JTAG interface. There is no host-only proof that opening it is non-resetting. Repeating pySerial with DTR/RTS low would retain the same open-order risk. A future candidate is a passive receive-only tap on an already configured target log TX path with no DTR/RTS connection, after the actual pin/routing is verified. That path is not currently established or physically validated; changing the firmware console or fixture wiring would need a separate reviewed plan and authorization.

## S3 replay-fence path

The exact log is emitted at `firmware/hub/target/esp32/hub_runtime_adapter.cpp:1051-1068` while handling a complete authenticated `NodeRetirementFragment` report. It is not the normal Node event-receive or application Durable ACK path.

The relevant sequence is:

1. Hub authenticates/decrypts the uplink frame and classifies it as a retirement-report fragment.
2. It reassembles the report, derives the report key and enrollment binding from the existing authenticated session, and verifies the report HMAC.
3. It checks the report storage epoch, loads the currently selected NVS retirement snapshot, and applies the report. A prepared report is written into a retirement bank, selected by a durable checkpoint, recovered and read back.
4. It reloads the selected report and reducer checkpoint, then calls `DurableEventOutbox::publish_replay_fence()` to publish the matching owner epoch, bank, generation and digest into the authenticated LittleFS lifecycle root.
5. It calls `HubRuntime::bind_replay_fence()` to ensure the in-memory admission gate matches both the selected NVS checkpoint and the persisted outbox witness.
6. Only after these steps does it send the Node retirement acknowledgement. The observed failure branch continues before that send.

The exact invariant is that the active Hub storage epoch and selected authenticated retirement snapshot must have an exact persisted replay-fence witness, and the runtime must be bound to that same witness before event admission/retirement proceeds. `DurableEventOutbox::publish_replay_fence()` checks eligibility and publication/readback at `firmware/hub/components/storage/durable_event_outbox.cpp:1461-1501`; `HubRuntime::bind_replay_fence()` checks the same reference at `firmware/hub/runtime/hub_runtime.cpp:188-209`; `durable_admission_open()` gates event admission at `hub_runtime.cpp:168-185`. The log establishes that this path did not complete and that admission was not usable for qualification. The runtime fails closed when a selected report lacks a ready fence or when the in-memory reference disagrees with the selected recovery state.

The log does **not** identify which predicate failed. The combined condition can fail while recovering/loading the selected report or checkpoint, because the checkpoint is absent, because `publish_replay_fence()` rejects an epoch/reference/generation/checkpoint-boundary condition, because publication/readback fails, or because `bind_replay_fence()` finds a mismatch. `publish_replay_fence()` has guarded state/monotonicity checks and verifies the authenticated lifecycle-root write by reading it back. The runtime log contains no lower-level return code, filesystem error, expected/observed reference, or indication of whether the NVS checkpoint had advanced before the failure. The saved board log contains no such lower-level diagnostic either.

**Assessment:** an S3 replay-fence publication/binding or selected-state consistency failure is confirmed; its precise root cause is unresolved. A transient LittleFS publish/readback problem and a persistent state/reference/boundary mismatch remain possible. Do not clear or rewrite NVS/LittleFS, reset a generation, recommission, or accept the report without the witness. Admission closure is the required fail-safe response. The physical record does not establish whether the S3 can recover through an ordinary authenticated report retry or whether an ambiguous outbox write left the current runtime faulted.

### Relationship between the failures

The S3 log shows authenticated C3 rejoin at approximately 2.633 seconds of S3 uptime, Node liveness at 3.393 seconds, then the replay-fence failure at 12.993 seconds. The C3 log shows its runtime owner starting at 2.724 seconds, PIR readiness at 12.724 seconds, and a NodeMessage/MAC acceptance at 12.784/12.804 seconds. On rejoin, the S3 source advertises its storage epoch; the C3 source then persists a changed retirement epoch and schedules an authenticated retirement report. This makes the C3 reset/rejoin → epoch advertisement → retirement report → S3 replay-fence path a plausible causal chain.

The report fragments themselves are not identified in the saved serial logs, and the nearby NodeMessage is not proof that the replay-fence error came from that message. So the failures are **potentially causally related as trigger and consequence, but not proven**. The reset and S3 persistence/consistency check are not the same failure. The S3 replay-fence failure is independently sufficient to block event admission even if the C3 had not reset.

This is not the historical `hub_journal_migration_validation.cpp:194` failure. That issue is a legacy importer/ownership-domain mismatch and remains the independently recorded GS-148 historical-baseline failure. The current S3 observation concerns runtime publication/binding of an authenticated retirement snapshot to a LittleFS replay-fence witness.

## Observer status classification correction

The previous HIL-A06 classifier searched only for generic `unexpected reset`, `panic`, `abort` and `fatal error`. It therefore returned PARTIAL for this capture, despite the explicit `USB_UART_CHIP_RESET` and S3 replay-fence/admission error. The human operator disposition correctly stopped the run and overrode the generated summary.

The HIL-A06 classifier now returns FAIL for `USB_UART_CHIP_RESET`, explicit S3 replay-fence publication/recovery failures, and `admission closed`, as well as its existing fatal markers. Normal `POWERON` boot text remains PARTIAL rather than being misclassified as an in-capture failure. Permanent regression cases were added to `tools/hil/test_gs130_runners.py`; the hardware runners remain opt-in and were not invoked.

## Host-only validation

| Command | Result | Evidence/limit |
|---|---|---|
| `make gs130-hil-runner-test` | PASS, 17 tests, exit 0 | Covers explicit reset and Hub admission-error classification, normal POWERON behavior, fail-closed runner defaults; no port open. |
| `PYTHONPATH=tools/hil python3` classifier against saved redacted C3/S3 logs | HIL-A06 `FAIL` on `USB_UART_CHIP_RESET`; HIL-A05 `NOT_RUN` | No EventKey → Durable ACK → Node retirement transaction is present in the saved logs. |
| `make hub-runtime-checkpoint-host-test` | PASS, exit 0 | Existing synthetic host tests cover valid replay-fence publication/binding and lifecycle-root write cuts before/after publication, recovery selection, stale/mismatched references and fail-closed behavior. This does not reproduce the physical board's persistent state or its exact failure. |
| `make validation-framework-test` | PASS, 39 tests, exit 0 | Existing GS-116 registry/failure-propagation tests confirm the HIL runner stage is registered and component/release gates reject failed or incomplete stages. |

No host test identifies the physical S3's failed predicate. No production Hub/Node security or storage semantics were changed. The historical journal migration test was not rerun or modified; its existing FAIL remains independent.

## Gated physical retest proposal — currently NO-GO

Do not resume PIR qualification yet.

**GO prerequisites:**

1. A separately reviewed capture path must avoid opening the C3 native USB Serial/JTAG control interface, or its residual reset risk must be explicitly accepted in a new test plan. A host-only mock cannot prove physical non-reset behavior.
2. The S3 failure must be localized to a concrete return condition using preserved state and a host reproduction, or a narrowly scoped source diagnostic must distinguish prerequisites, outbox publication and runtime binding. Any firmware diagnostic change requires a new build/image provenance review and user authorization before deployment.
3. The S3 selected NVS snapshot and LittleFS lifecycle witness must be shown to agree and replay-fence readiness must be confirmed through an approved nondestructive method. Do not erase, reset, reprovision or mutate stored state to make the check pass.
4. Existing pairing, owner/session and pending-event state must be verified unchanged. Candidate build hashes are not proof of installed image hashes; the current saved boot banner only gives abbreviated ELF SHA values.
5. A new user authorization must cover the exact observation method and the real optical PIR sequence. No permission is inferred from this investigation.

**After those gates:** capture separate C3 and S3 observations, request each genuine AM312 motion individually, and require the same EventKey to be correlated through GPIO4 wake/admission, Node persistence, authenticated S3 reception, S3 durable commit, matching application Durable ACK and C3 retirement. Stop on any reset, pairing/session loss, admission closure, unexplained storage error, or missing/mismatched ACK. Keep C8-P1 through P9 dispositions from the existing stop report until each applicable criterion has actual evidence; P10 remains GS-149.

**Current decision:** NO-GO. No physical retest, recovery, board access or further fixture interaction is authorized by this investigation.
