# GS-114 Part 1 — HIL source and compatibility audit

**Date:** 2026-10-11
**Source:** `6d0318f644a400caa1f35d9bd0eb4dc9fcb0830b`
**Branch:** `feature/r1-commercial-baseline`
**Result:** source audit complete; physical execution **NOT_RUN / BLOCKED** pending fixture identification, a verified non-resetting observer, and explicit user approval.

## Scope and safety

This audit covers the existing HIL framework and the S3 target configuration.
It does not qualify hardware. No serial device was opened; no esptool, ESP-IDF,
serial monitor, fixture setup, preflight, smoke, regression, flashing, reset,
motion injection, storage operation, or board command was run. The only
hardware discovery attempted was read-only host enumeration: `lsusb` is not
installed and `/dev/serial/by-id` does not exist in this environment. Therefore
no connected board, USB interface, port, board identity, firmware, or image hash
is established.

## Existing HIL components inspected

Under `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/`:

- `tools/hil/phase1.py`: fixture discovery, active identity probing, setup,
  preflight, auto-flash, serial capture, and automated smoke/regression.
- `tools/hil/qualify.py`: supervisor stages `validation-fast`,
  `release-gate-final`, USB fixture, setup, preflight, smoke, and regression.
- `tools/hil/core.py`: historical fixed Hub and Node MAC identities, serial
  capture, fixture lock, and report utilities.
- `tools/hil/esp_idf_adapter.py`: old-target identity probe, serial capture,
  and `idf.py flash` paths.
- `scripts/build_hil_pair.py`, `scripts/build_hw_pair.py`: HIL and production
  pair build/metadata utilities.
- `tools/hil/secure_signed_fota.py`: destructive flash/erase/update scenarios;
  excluded from this task.

The campaign is not observational: supervisor stages include product/release
build validation; setup/discovery probes boards with esptool; preflight can open
serial; `HIL_FLASH=auto` can flash when image state differs; scenarios issue
`SOFTWARE_RESTART`, logical online/offline controls, and `INJECT_MOTION`.
`Phase1.motion()` sends `INJECT_MOTION`; it is not physical PIR evidence. The
existing docs also state esptool identity probing uses DTR/RTS reset sequencing.
No existing reader is verified safe for observation without reset.

## Old ESP32 → current ESP32-S3 N16R8 compatibility

| Concern | Legacy HIL assumption | Current R1 S3 source | Part 1 disposition |
|---|---|---|---|
| Hub target | `firmware/hub/target/esp32/idf`; `IDF_TARGET=esp32` | `firmware/hub/target/esp32s3/idf`; CMake requires `esp32s3`; project `gs_r1_s3_hub` | Old builder/adapter cannot be used for S3. |
| HIL firmware | Legacy Hub composes HIL control source | S3 CMake rejects `GS_HIL_BUILD`/`GS_HIL_CONTROL`; forces both OFF | No S3 HIL command protocol; use existing production observability only if safely readable. |
| Hub identity | Fixed historical MAC `5c:01:3b:be:b9:f8` | No S3 physical MAC was read; Hub identity/config is not inferred from target code | Must identify after approved safe observation; never reuse fixed MAC blindly. |
| USB identity | Hub `10c4:ea60`; C3 `303a:1001`; role by fixed MAC | No enumeration tools/devnodes present in the host | VID/PID and port mapping unknown; user confirmation required. |
| Flash | Old target build profile | `CONFIG_ESPTOOLPY_FLASHSIZE_16MB=y` | Source profile only; actual board flash unobserved. No flash action. |
| PSRAM | No equivalent current S3 assumptions in old runner | octal PSRAM, 40 MHz, boot init, memtest, caps allocator enabled | Source profile indicates N16R8 intent; actual size/health unobserved. |
| Partitions | Historical classic-ESP32 layout/image | S3 development table: NVS `0x9000/0x6000`, otadata `0xf000/0x2000`, phy `0x11000/0x1000`, two 4 MiB OTA apps at `0x20000` and `0x420000`, `gs_journal` NVS at `0x820000/0x200000`; remainder unallocated | Development-only source layout, not commercial allocation and not read from board. No storage boundary can be claimed physically. |
| OTA/security | Legacy image/version metadata and pair assumptions | S3 target enables ESP-IDF app rollback; no S3-specific HIL control image | Image/signature/version/hash unobserved. Physical FOTA is excluded. |
| Console/serial | Legacy pair USB/UART behavior and exclusive pyserial open | S3 README describes UART0 defaults GPIO43 TX/GPIO44 RX; S3 sdkconfig defaults do not establish a non-resetting USB observer | Actual adapter/routing and DTR/RTS behavior must be confirmed. Do not open port yet. |
| GPIO | Legacy HIL control and test assumptions | S3 CMake says board-specific HIL GPIO/control qualification pending | No S3 GPIO or PIR test implied by this HIL tooling. Part 2 is separate. |
| Storage/session | Old firmware/control protocol and expected node pairing | Current S3 production app and storage are separate from legacy test-control image | Existing enrolled state and retained records must remain untouched; identity/session not observed. |

Partition arithmetic: the listed S3 development allocations end at `0xA20000`,
leaving `0x5E0000` of the declared 16 MiB address space unallocated. This is a
source calculation only, not a capacity or physical flash observation.

## Part 1 case disposition before fixture approval

| Case | Intended evidence | Current disposition |
|---|---|---|
| HIL-A01 firmware/board identity | Running target, version, config, hashes | BLOCKED: would require a safe log/metadata observer; none verified. |
| HIL-A02 authenticated existing link | Session/contact evidence without disturbance | BLOCKED: no read-only event/session observer established. |
| HIL-A03 NodeHealth | Production 300-second profile, authenticated contact/piggyback | NOT_RUN: production timing and genuine logs required. |
| HIL-A04 Hub liveness | Applicable 300 s / derived 910 s behavior | NOT_RUN: healthy contact does not prove offline expiry; outage manipulation is excluded. |
| HIL-A05 Durable ACK/EventKey | Real authenticated receipt, commit, ACK/identity | NOT_RUN: no naturally occurring event or separately approved nondestructive stimulus. |
| HIL-A06 runtime stability | Reset/session/resources/queue/errors | BLOCKED: telemetry requires safe observation and board identity. |
| HIL-A07 target sleep/wake | Actual firmware markers | NOT_RUN: source/build model is not physical wake evidence. |
| HIL-A08 negative cases | Lost ACK/retry/replay/offline/rejoin | BLOCKED: available scenarios mutate state, reset, change logical link state, or require fault injection. |

Manual optical/human PIR is **not part of Part 1** and remains for Part 2.
No result converts historical ESP32 HIL or BAT-C8 evidence into current S3
evidence. Historical results retain their original image and fixture provenance.

## Approval checkpoint before any device interaction

The following was the original approval checkpoint as of this audit's source
HEAD. It was superseded by the dedicated-board authorization and completed
fixture commissioning recorded in `GS114_PART1_CLEAN_FIXTURE_20261011.md`;
retain it as historical provenance, not current status.

Please confirm all of the following before any serial port is opened or any
device interaction is attempted:

1. Which exact ESP32-C3 Node and ESP32-S3 N16R8 Hub are connected?
2. Which host ports/interfaces belong to each board?
3. Are these separate test boards, or the original protected paired devices?
4. Must firmware, persistent data, pending Node events, Hub NVS/VFS, enrollment,
   and authenticated session state all be preserved? (Default expected answer:
   yes.)
5. Approve this exact proposed *observational-only* scope: after a separately
   verified no-reset serial/log acquisition method is selected for the named
   interfaces, capture startup/current logs and wait through one configured
   300-second NodeHealth interval; record only naturally occurring authenticated
   contact/ACK and target-reported state. No injected motion, no test commands,
   no Hub-offline toggle, no reset/rejoin test, no flash, no power cycle, no
   storage/enrollment change. Confirm or narrow this scope.

If serial observation cannot be proven non-resetting for the actual interface,
the safe outcome is to leave physical tests NOT_RUN and prepare an external
non-resetting logger/approved fixture. Connected healthy operation alone cannot
qualify offline detection, lost-ACK recovery, actual GPIO4 wake, PIR response,
or power behavior.

## Repository evidence and validation

- `pwd`: `/home/udaybhan/projects/Ghar_sajag_r1`
- branch: `feature/r1-commercial-baseline`
- source HEAD and remote at audit: `6d0318f644a400caa1f35d9bd0eb4dc9fcb0830b`
- context preflight: PASS (`2026-10-10.001`)
- tracked worktree: clean before these documentation edits
- preserved unrelated untracked asset: S3 `managed_components/`
- physical test commands: **none run**
- board interactions/actions: **none**
