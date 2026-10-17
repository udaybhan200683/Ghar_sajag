# Matched-pair deployment and baseline result

Source: `808080e94b6958153952ce16eb56c1ad37a9ad01`.

## Deployment

- Hub flashed first on native Windows COM3. ESP32-D0WD-V3 MAC `[REDACTED_HARDWARE_MAC]`; all writes verified; final RTS hard reset completed at `2026-09-28T22:44:26.1651617+05:30`.
- C3 flashed second on native Windows COM4. ESP32-C3 MAC `[REDACTED_HARDWARE_MAC]`; all writes verified; final RTS hard reset completed at `2026-09-28T22:44:49.9806158+05:30`.
- Image SHA-256s match the prepared manifest. No manual reset, eFuse write, source edit, `INJECT_MOTION`, or timer-wake test was performed.

## Baseline capture

- Captured for 120 seconds using native Windows PowerShell on COM3 and COM4, with DTR/RTS disabled. Raw output files and checksum list are preserved alongside this report.
- C3 `GET_STATE`: `session=409 retained=5 in_flight=0`, sensing/runtime live.
- Hub `GET_STATE`: `online=1 processed=0 durable_ack=0 health=0` in the captured response.
- C3 logged previously retained messages from sessions 406 and 408 with `Application ACK ... retired=0`.
- C3 then logged one actual GPIO/PIR path event: `PIR -> NodeRuntime session=409 seq=1`; a later send/ACK was logged with `retired=0`. No `INJECT_MOTION` command was issued. This event occurred before the planned quiet-recovery phase and is not counted as a qualification event.
- Hub capture contains substantial NUL/garbled data mixed with valid lines; it is preserved but not clean enough to establish Hub-side delivery, HealthAck, or dedupe evidence. C3 capture has valid readable lines.

## Stop point

Baseline precondition `retained=0` failed, initial session/contact baseline was not recorded before deployment, and an unexpected physical Motion was admitted. No Hub-only qualification reset or planned PIR stimulus was performed. Stop here; classify pending-event state as `FIXTURE/STATE PRECONDITION` and Hub-log quality as `WINDOWS_CAPTURE`. Do not clear pending events, reset, or generate motion without operator direction.
