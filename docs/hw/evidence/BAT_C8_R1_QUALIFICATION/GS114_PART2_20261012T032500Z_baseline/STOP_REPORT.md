# GS-114 Part 2 — Baseline observer stopped

**Date:** 2026-10-12 UTC
**Source:** `09bc8cd8b7baab0674bbe03157b7b50bab28e51e`
**Fixture:** `GS114-DISPOSABLE-C3-S3`
**Result:** stopped before any PIR stimulus after an unexpected C3 reset and an S3 admission error.

## Preflight and observation

Read-only WSL enumeration and `udevadm` identified the approved stable USB interfaces:

| Role | Stable identity | Current WSL tty | Observed USB identity |
|---|---|---|---|
| C3 | `usb-Espressif_USB_JTAG_serial_debug_unit_14:63:93:C5:D1:58-if00` | `/dev/ttyACM0` | Espressif `303a:1001`, USB serial `14:63:93:C5:D1:58` |
| S3 UART | `usb-1a86_USB_Single_Serial_5CBC401023-if00` | `/dev/ttyACM1` | QinHeng `1a86:55d3`, USB serial `5CBC401023` |

Neither port had an open file descriptor at preflight. The `lsusb` utility was absent; sysfs and `udevadm` provided the identity data. No tty-number assumption was used.

After the user explicitly authorized receive-only observation, the existing bounded observer verified both stable IDs and the candidate image hashes, requested DTR/RTS low, sent no serial bytes, and captured for 60 seconds. Candidate artifact hashes match the recorded Part 1 profile: C3 `b03b3b2ed7996b594f9fe7d59241f558a6af82774db07a661e5346731db83014`; S3 `f9608d77230f136abea5794329c1a98be4062419383a1a6dbbfd29a6c793a2d1`. These are build artifact hashes, not verified flash readbacks.

## Observations and stop reason

- C3 boot output identifies ESP32-C3 rev 0.4, 4 MB flash, ESP-IDF 6.0.3, app version `73e1e842ff84-gs114-16fca85b`, and expected station MAC `14:63:93:c5:d1:58`. Its first captured line reports `rst:0x15 (USB_UART_CHIP_RESET)`. This reset occurred during the UART observation window. It is consistent with the known UART-open reset risk; causation is not proven. This satisfies the explicit stop condition.
- S3 boot output identifies ESP32-S3 rev 0.2, 16 MB flash, 8 MB PSRAM, ESP-IDF 6.0.3, app version `73e1e842ff84-gs114-16fca85b`, and expected station MAC `7c:4f:ad:b7:2a:20`.
- S3 logged an authenticated C3 rejoin and online liveness marker, then `S3 replay-fence publication failed; admission closed`. Hub admission was therefore not healthy for event qualification.
- C3 logged a NodeMessage and MAC acceptance, but no exact EventKey, Hub durable commit, authenticated application Durable ACK, or corresponding Node retirement was observed. MAC acceptance is not Durable ACK.
- Runtime firmware identity is supported by boot banners, but installed app hashes are not proven; log firmware SHA is abbreviated and no flash readback was performed.
- No operator motion occurred. No additional port access, recovery, reset, power operation, command, flash, storage action, or pairing change was attempted.

The observer-generated `board_hil_results.json` reports `PARTIAL`; manual review found the explicit C3 reset and S3 replay-fence failure which its HIL-A06 classifier did not recognize. `operator_disposition.json` records the controlling disposition: abort, HIL-A06 FAIL, and no P1–P9 PASS.

## Case disposition

| Case | Result | Reason |
|---|---|---|
| C8-P1 | NOT_RUN | No timer-only test sequence. |
| C8-P2 | BLOCKED | No genuine AM312 stimulus; stopped at reset condition. |
| C8-P3 | BLOCKED | No genuine held-output/recovery motion test. |
| C8-P4 | BLOCKED | No correlated EventKey → Hub durable commit → authenticated ACK → Node retirement. |
| C8-P5 | BLOCKED | Outage/return requires separate disruptive authorization. |
| C8-P6 | BLOCKED | Hub reboot is not authorized. |
| C8-P7 | BLOCKED | Depends on the unauthorized Hub reboot case. |
| C8-P8 | BLOCKED | ACK loss/suppression and replay fault injection are not authorized. |
| C8-P9 | BLOCKED | ACK suppression/FOTA tests are not authorized. |
| C8-P10 | NOT_APPLICABLE | Quantitative power is GS-149. |

No physical acceptance PASS is claimed. GS-114 remains In Progress. Do not reopen the UARTs or perform recovery on this run. A subsequent attempt requires a separately verified non-resetting capture path and resolution of the Hub replay-fence admission failure without modifying stored state on these boards. Any firmware or persistent-state remediation requires separate approval and requalification planning.

## Evidence files

- `board_hil_results.json` — unchanged output from the existing observer.
- `c3_serial_redacted.log`, `s3_serial_redacted.log` — redacted independent UART captures.
- `operator_disposition.json` — manual stop/failure disposition.
