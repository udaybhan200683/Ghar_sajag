# HW-M1.3 Host Validation Evidence

## Status

**HOST VALIDATION ONLY**

**HARDWARE VALIDATION PENDING**

HW-M1.3 is **IMPLEMENTED / HOST VALIDATED / HARDWARE VALIDATION PENDING**.
This document does not claim HW VALIDATED, QUALIFIED, or PASS on target
hardware.

## Implemented scope

- Portable bounded data-plane codec for `NodeMessage` and `NodeAckMessage`.
- Explicit big-endian integers, bounded strings, presence flags, magic,
  protocol version, frame type, and exact payload length.
- Maximum encoded normal frame below the 250-byte ESP-NOW v1 payload limit.
- Separate classification of the existing FOTA magic as control-plane traffic.
- Portable fail-closed persistent boot-session counter policy.
- ESP32-C3 adapter with qualified GPIO/MAC/channel/TX settings, one
  `NodeRuntime` owner task, callback queues, typed sends, MAC result handling,
  application ACK handling, and NVS-backed session allocation.
- ESP32 Hub adapter with qualified MAC/channel settings, bounded callback
  queues, transport RSSI/channel diagnostics, monotonically increasing session
  admission, one `HubRuntime` owner task, and typed application ACK return.
- Separate target control-plane queues for later composition with the existing
  qualified FOTA maintenance path.

The repository has no unified ESP-IDF product project/CMake composition.
Target-only adapter files are therefore isolated from the host Makefile and
have not yet been target-built or flashed. The FOTA queues must be connected
to the qualified maintenance implementation during target image composition.

## Host test results

Successful focused command:

`PATH=/usr/bin:/bin make cpp-test CXX=/usr/bin/g++`

Result: **PASS — 124 checks**.

Coverage includes NodeMessage and NodeAckMessage round trips, maximum bounded
fields, complete EventKey and power telemetry preservation, malformed/truncated
frame rejection, bad magic/version/type/enums/length/flags/trailing-data
rejection, FOTA separation, MAC-result versus application-ACK semantics,
ReceivedVolatile retention, Durable retirement, wrong-key protection, retry
identity, distinct reboot sessions, stale Hub session rejection, and
fail-closed persistent session allocation.

`PATH=/usr/bin:$PATH make release-gate-final CXX=/usr/bin/g++` was run. C++
unit, Python, JavaScript, contracts, validation coverage, both product variants,
feature variants, simulator/lab build, dummy streams, functional catalog,
sanitizers, and trace build passed. The overall command did **not** pass:
HTTP/PWA/browser stages require localhost sockets, while this sandbox rejects
socket creation/binding. A focused `make http-e2e-test` confirmed
`PermissionError: [Errno 1] Operation not permitted` during Python socket
creation; browser validation reported that the sandbox cannot bind
`127.0.0.1:8765`. Rerun `make release-gate-final` in the normal local terminal.

## Manual hardware validation sequence

1. Compose the node adapter and qualified FOTA maintenance consumer into the
   ESP32-C3 ESP-IDF image; target-build it with the existing dual-OTA layout.
2. Compose the Hub adapter and qualified FOTA maintenance consumer into the
   ESP32 Hub ESP-IDF image; target-build it with the existing dual-OTA layout.
3. Flash/boot the qualified C3 and verify MAC `14:63:93:C5:D1:58`, channel 1,
   TX API value 40 (10 dBm), GPIO4 PIR and active-low GPIO8 LED diagnostics.
4. Flash/boot the qualified Hub and verify MAC `5C:01:3B:BE:B9:F8`, channel 1,
   bounded data/control queues, and the sole Hub owner task.
5. Allow the AM312 ten-second stabilization interval to complete without a
   fabricated boot-time motion event.
6. Trigger motion and capture the C3 log proving sensing -> `NodeRuntime::record`
   with node/session/sequence identity.
7. Capture the C3 log proving bounded `NodeMessage` encoding and ESP-NOW send;
   separately capture the MAC send result passed to `transport_result()`.
8. Capture the Hub callback/owner logs proving callback enqueue with MAC,
   transport RSSI/channel and deferred owner-task decode.
9. Verify the Hub accepts the mapped node and current NVS boot session, calls
   `radio_message_callback()` and `run_state_once()`, and journals the event.
10. Capture the typed Durable `NodeAckMessage` sent by the Hub and decoded by
    the C3 owner task; verify only the matching retained event is retired.
11. Deliberately suppress/drop one application ACK where practical; verify MAC
    success alone does not retire the event and the retry preserves the exact
    EventKey.
12. Deliver a duplicate retry and verify journal identity remains duplicate-safe;
    record the existing duplicate-reducer gap if its effects are observable.
13. Reboot the C3 and verify the NVS session increments while sequence restarts,
    so the complete EventKey differs and the Hub rejects the stale prior session.
14. Verify Hub RSSI/channel diagnostics remain visible and semantic message RSSI
    is not overwritten by transport metadata.
15. Run both qualified FOTA rotations, verify post-update PIR operation, then
    repeat steps 6-10 to prove the business data path still works after FOTA.

Only after this sequence and retained evidence pass may HW-M1.3 be considered
for HW VALIDATED / QUALIFIED status.
