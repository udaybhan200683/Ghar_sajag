# GS-114 Part 1 — Authorized clean-fixture preparation checkpoint

**Run date:** 2026-10-11 UTC
**Source HEAD:** `5201abcbe930a4e1f47863ab1a7b3b974a0dd9ca`
**Branch:** `feature/r1-commercial-baseline`
**Result:** board identities and fresh images verified; erase/flash and HIL campaign **BLOCKED before erase** because no existing supported test-only commissioning path can pair the fresh boards without an unavailable provisioning procedure.

## Authorized fixtures and observed identities

The user authorized full-chip erase and fresh firmware only for the dedicated
boards identified below. User-provided stable USB links resolved to the exact
specified ports. All esptool commands used explicit target and port arguments;
there was no automatic port selection.

| Role | Stable USB ID / port | Observed chip and MAC | Flash / PSRAM | Security |
|---|---|---|---|---|
| C3 Node | `usb-Espressif_USB_JTAG_serial_debug_unit_14:63:93:C5:D1:58-if00` → `/dev/ttyACM1` (COM4 / BUSID 5-4 per user) | ESP32-C3 QFN32 rev 0.4; `14:63:93:c5:d1:58` | 4 MB flash; embedded flash manufacturer 46 / device 4016 (XMC) | Secure Boot disabled; flash encryption disabled; crypt count 0 |
| S3 Hub | `usb-1a86_USB_Single_Serial_5CBC401023-if00` → `/dev/ttyACM0` (COM9 / BUSID 5-1 per user) | ESP32-S3 QFN56 rev 0.2; `7c:4f:ad:b7:2a:20` | 16 MB flash; manufacturer 68 / device 4018; 8 MB embedded PSRAM AP_3v3 | Secure Boot disabled; flash encryption disabled; crypt count 0 |

ESP-IDF was sourced from `/home/udaybhan/.espressif/v6.0.3/esp-idf/export.sh`;
`idf.py --version` reported `ESP-IDF v6.0.3`. esptool reported `v5.4.0`.
Identity and flash/security probes use RTS reset sequencing; this was within
the user's explicit setup authorization. No flash erase or write occurred.

Exact identity commands (each explicitly targets its authorized port):

```sh
python -m esptool --chip auto --port /dev/ttyACM1 chip-id
python -m esptool --chip auto --port /dev/ttyACM0 chip-id
python -m esptool --chip esp32c3 --port /dev/ttyACM1 flash-id
python -m esptool --chip esp32c3 --port /dev/ttyACM1 get-security-info
python -m esptool --chip esp32s3 --port /dev/ttyACM0 flash-id
python -m esptool --chip esp32s3 --port /dev/ttyACM0 get-security-info
```

No eFuse, secure-boot, flash-encryption, or security configuration was changed.
The detected targets/capacity/security states do not trip the user's stop
conditions.

## Fresh source-matched firmware artifacts

At the verified current source HEAD, `scripts/build_validation_targets.py`
completed PASS with ESP-IDF 6.0.3 and the production profile
`GS_HIL_BUILD=OFF`. It produced an isolated, matching C3/S3 pair and GS-40
configuration bundle at:

`code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/build/validation_targets/gs116-26s4vrei/`

The build report is `report.json`; `bundle/manifest.json` records offsets,
sizes, hashes, source HEAD, JSON configuration hash and the 300 s / 910 s
NodeHealth policy. The current bundle—not an older `build/gs40_bundle`—is the
only candidate artifact. The old bundle directory was inspected and rejected
as stale because it reported source `e36bd883...`; no artifact was flashed.

| Role/artifact | Offset | Bytes | SHA-256 |
|---|---:|---:|---|
| C3 bootloader | `0x0` | 21,408 | `fed92ca36766f487c91c62f26aed2391446ea0e10168e8a04aa35768b0def0d2` |
| C3 partition table | `0x8000` | 3,072 | `1b86379629900670bd43147c3a873a424695a67765fd1bdb28b1bffc21be137a` |
| C3 initial OTA metadata | `0xf000` | 8,192 | `7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f` |
| C3 app | `0x20000` | 934,192 | `e9f902f597f9f63063d7ca19831ea17485e7e173e98bf60503046c191919b853` |
| S3 bootloader | `0x0` | 21,264 | `de0802a633625eb71c035895d304f7ff9fb68e4d20bf14556dbcbe7cb444dc54` |
| S3 partition table | `0x8000` | 3,072 | `4828fb04f0569bcc5ffafaf887bb7f360e6ab858ec29df00297671f5f2a468fe` |
| S3 initial OTA metadata | `0xf000` | 8,192 | `7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f` |
| S3 app (includes exact C3 app) | `0x20000` | 1,868,800 | `95563bc6d28ff9a7e0fcbb767a28e1b54b6334dd5d4b4e95d5b392a663662051` |

Image headers independently report C3/4 MB/DIO/80 MHz and S3/16 MB/DIO/40 MHz,
both ESP-IDF 6.0.3, version `5201abc-gs116-50833308`. C3 OTA slots are 1,920 KiB;
S3 OTA slots are 4 MiB each. The S3 build configuration selects octal PSRAM,
40 MHz, boot initialization, startup memtest, and capability allocation. The
compiled S3 partition table matches the current development CSV, including the
2 MiB `gs_journal`; the C3 table matches `partitions.csv`. Both tables passed
ESP-IDF partition parser verification. The matching source C3 app is embedded
in the S3 app and verified by the packaging script.

Build command:

```sh
source /home/udaybhan/.espressif/v6.0.3/esp-idf/export.sh
python scripts/build_validation_targets.py
```

Build result: PASS (C3 934,192 bytes; S3 1,868,800 bytes). This is target
compilation only; no board boot or firmware runtime has yet been observed.

## Stop condition: fresh test pairing is not currently available

Before erasing, source review showed that a fresh supported authenticated pair
cannot be established through the current S3 production target without a
separate provisioning procedure and test credentials/material:

- The identity/lifecycle guide says kit preparation and secure distribution of
  exact expected-Node records is not implemented, and the product commissioning
  entry point / fully authorized external control channel is incomplete.
- Hub commissioning requires an exact `ExpectedNode` record (physical MAC,
  Device ID, public key, installer code, Home/Hub, logical/room/function
  assignments). `request_node_commissioning()` is only called by the legacy
  ESP32 HIL control path; the S3 target rejects `GS_HIL_BUILD` and
  `GS_HIL_CONTROL` and provides no compatible request interface.
- The C3 `GET_TEST_QR` command is part of the test-only Node control path. It
  does not provision the S3 Hub's expected record. We will not invent an
  installer code, Home/Hub identity, ownership record, or alternate protocol.

The user directed the campaign to pause if a different provisioning procedure
is required. Therefore the full-chip erase/firmware write was **not started**;
this avoids leaving the fixtures freshly erased but unable to pair. No flash
erase or write was issued. The identity probes reset both MCUs via RTS; the
existing applications may then have performed normal boot/rejoin activity and
persistence. Pending-event count/content and post-probe NVS/session state were
not inspected and are not claimed unchanged. Boot logs and current running
firmware versions were not captured.

Required to resume: provide/approve the supported test-only commissioning
provisioning path for these exact boards, including an authorized test Home/Hub
identity and exact C3 `ExpectedNode` record/installer authorization, or approve
a narrowly scoped S3 commissioning control/tooling implementation. The latter
would be a software scope change and requires a new validated firmware build
before erase. No secret may be placed in Git or evidence logs.

## HIL-A01 through HIL-A08 status

| Test | Status | Evidence/limitation |
|---|---|---|
| HIL-A01 firmware and board identity | **BLOCKED (identity subcheck PASS)** | C3/S3 silicon, MAC, flash and security state verified; current running firmware/config/hash and boot identity not observed. Candidate image manifest is verified but not installed. |
| HIL-A02 authenticated existing Node–Hub link | **BLOCKED** | Clean pairing needs the unavailable supported provisioning path. Existing board association was not inspected or reused. |
| HIL-A03 NodeHealth | **BLOCKED** | No runtime logs or authenticated contact captured; 300-second interval not observed. |
| HIL-A04 Hub liveness | **BLOCKED** | No current pair or installed candidate firmware; no offline transition was induced. Live connectivity alone would not establish the 910-second timeout. |
| HIL-A05 Durable ACK/EventKey | **BLOCKED** | No authenticated pair; no event stimulus or actual app-level Durable ACK observed. |
| HIL-A06 runtime stability | **BLOCKED** | No startup/serial runtime logs; heap, session continuity, queue and reset diagnostics unavailable. |
| HIL-A07 timer/light-sleep | **BLOCKED** | No candidate firmware installed; no firmware runtime or physical wake behavior observed. |
| HIL-A08 negative-case compatibility | **BLOCKED** | Existing cases require test controls, fault injection, reset/rejoin, or state changes; none is supported for the current S3 production image. |

No HIL campaign, smoke, regression, manual PIR, physical FOTA, current/power,
storage operation, erase or flash command was run. No serial log path exists for
this checkpoint. Existing historical physical evidence remains tied to its
original images and fixtures.

## Repository and next action

- Worktree: `/home/udaybhan/projects/Ghar_sajag_r1`
- Branch: `feature/r1-commercial-baseline`
- HEAD/remote at build: `5201abcbe930a4e1f47863ab1a7b3b974a0dd9ca`
- Context preflight: PASS
- `make release-gate-final`, broad GS-108 campaign: NOT_RUN
- Physical tests: NOT_RUN / BLOCKED; Part 2 human-motion PIR remains out of scope
- Hardware actions: target-detection/flash-ID/security-info probes only; these
  performed RTS resets. No erase, write, eFuse change, or destructive action.
- Pending Node records: not read, erased, or inspected by this task; exact
  post-probe state is unverified.
- Next: resolve the commissioning prerequisite above; then resume without
  rebuilding unchanged images unless source/profile changes, reverify the exact
  ports/identities and hashes, erase/write only these two boards, boot/log,
  provision a test-only pair through the approved path, and run supported
  Part 1 cases only.
