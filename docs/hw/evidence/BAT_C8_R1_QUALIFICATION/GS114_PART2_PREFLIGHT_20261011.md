# GS-114 Part 2 — Real PIR qualification preflight

**Preflight time:** 2026-10-11 21:15 UTC
**Source HEAD:** `02d7a12bd0f523a3acf7b80bfc06ac996fd14c76`
**Branch:** `feature/r1-commercial-baseline`
**Local/origin HEAD:** matched before this documentation checkpoint
**Result:** **BLOCKED before device interaction**. No serial port was opened and no physical stimulus or board operation occurred.

## Safe preflight

The read-only WSL enumeration found no `/dev/serial/by-id` directory and no
`/dev/ttyACM*` devices. The historical mappings therefore cannot be treated as
current fixture identity or availability:

| Role | Approved fixture identity | Historical interface | Current observation |
|---|---|---|---|
| C3 Node | ESP32-C3, `14:63:93:c5:d1:58` | `/dev/ttyACM1`; stable USB identity `usb-Espressif_USB_JTAG_serial_debug_unit_14:63:93:C5:D1:58-if00` | Not enumerated in this WSL environment |
| S3 Hub | ESP32-S3 N16R8, `7c:4f:ad:b7:2a:20` | `/dev/ttyACM0`; stable USB identity `usb-1a86_USB_Single_Serial_5CBC401023-if00` | Not enumerated in this WSL environment |

No port-number selection, esptool probe, serial open, USB attach/detach, command,
reset, flash, storage action, pairing action or sensor interaction was attempted.

## Existing observer and image provenance

The existing `tools/hil/gs130_motion_hil.py` is the manual-assisted path. It
rejects injected motion, requires the fixture's stable by-id paths and matching
image artifacts, and captures the C3/S3 streams without sending serial bytes.
`ReadOnlyCapture` sets DTR and RTS low before opening each port. The runner and
shared HIL helper still warn that serial open may affect reset lines on an
unverified adapter. The S3 fixture uses a CH343 USB-UART interface; no current
evidence proves opening it is non-resetting. Accordingly the observer was not
started.

The Part 1 artifacts remain present and match their recorded build hashes:

| Role | Built artifact SHA-256 | Build source |
|---|---|---|
| C3 | `b03b3b2ed7996b594f9fe7d59241f558a6af82774db07a661e5346731db83014` | `73e1e842ff843a696d592bd7c2004b72a512082c` |
| S3 | `f9608d77230f136abea5794329c1a98be4062419383a1a6dbbfd29a6c793a2d1` | `73e1e842ff843a696d592bd7c2004b72a512082c` |

The C3 production firmware files are unchanged between that build source and
this checkpoint. The intervening S3 firmware changes add CloudSync enrollment
generation provenance serialization/lookup; they do not change the local
Node-to-Hub event reception, durable ACK, or BAT-C8 sleep path under GS-114.
This source comparison does not prove which binaries are presently installed:
Part 1 explicitly records that flash readback hashes were not verified, and
current runtime identity/session could not be observed without the unavailable
fixture interfaces.

The C3 target README documents AM312 on GPIO4 and labels the signal active-low.
This is source configuration evidence only; the current physical sensor wiring
has not been visually or electrically verified.

## Case disposition at this preflight

| Case | Status | Current evidence / blocker |
|---|---|---|
| C8-P1 timer-only sleep/wake | **NOT_RUN** | Prior Part 1 A07 counters do not satisfy the case's paired pre/post Hub-state and current-run wake/restore criteria. |
| C8-P2 real AM312 GPIO4 wake | **BLOCKED** | No fixture interfaces enumerated; AM312 wiring and operator availability unconfirmed. |
| C8-P3 held-HIGH PIR/recovery | **BLOCKED** | Same fixture blocker; GPIO level/time trace and safe supported real sensor episode are not available. |
| C8-P4 wake/radio restore/Durable ACK | **BLOCKED** | No new real motion or matching EventKey→Hub durable commit/ACK→Node retirement evidence. |
| C8-P5 Hub outage/return | **BLOCKED** | Requires powering off/restoring Hub, explicitly outside this task's authorized operations. |
| C8-P6 Hub-only reboot/rejoin | **BLOCKED** | Requires Hub reset/reboot, which is not authorized in this task. |
| C8-P7 first motion after Hub reboot | **BLOCKED** | Depends on C8-P6; no Hub reboot is authorized. |
| C8-P8 lost application ACK/replay | **BLOCKED** | Requires downlink suppression/fault fixture and ledger inspection; deliberate ACK loss is not authorized. |
| C8-P9 ACK/FOTA sleep inhibition | **BLOCKED** | ACK suppression and live FOTA/recovery are outside this task's authorization. |
| C8-P10 current/energy comparison | **NOT_APPLICABLE (GS-149)** | Quantitative power acceptance belongs to GS-149 and is excluded from GS-114. |

Part 1 evidence remains at
`GS114_PART1_CLEAN_FIXTURE_20261011.md` and `attempt06/`. Its accepted
commissioning, rejoin, NodeHealth, bounded stability and timer telemetry are
not upgraded by this preflight. No first-motion latency threshold is invented;
GS-46 owns that gate. No outage, ACK-loss, FOTA, power, GS-69 soak or GS-108
test was performed.

## Resume conditions

1. The operator connects the exact dedicated C3/S3 pair to this WSL environment
   and confirms their stable identities. Do not rely on `/dev/ttyACM*` numbers.
2. The operator confirms the AM312 is already safely wired to the approved C3
   GPIO4 circuit and is available for the prompted real movements.
3. Before any UART open, provide a verified no-reset observer or explicitly
   authorize the exact bounded read-only UART open with DTR/RTS low, including
   the residual possibility that the S3 CH343 interface could reset the Hub.
   No serial writes will be sent.
4. Re-run read-only identity/interface preflight and verify the existing image
   artifact hashes. Do not flash or reset to resolve a mismatch.
5. Only after the operator's confirmation, run the existing motion observer
   one case at a time, request one real movement at a time, record actual UTC
   stimulus intervals, and stop on any reset, identity mismatch, missing ACK,
   or unsafe state.

No firmware, tooling or product behavior changed in this preflight.
