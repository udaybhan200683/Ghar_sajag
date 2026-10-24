# GS-117 C3 HIL-awake app deployment evidence — 2026-10-24

## Scope and authorization

Owner-authorized current-source ESP32-C3 HIL-awake TEST_ONLY application
deployment on COM4 / USB serial `14:63:93:C5:D1:58`. Source branch was
`feature/r1-commercial-baseline`, HEAD `60574c4d3b98ded68bd18df611335afea48862fc`;
context preflight passed (`2026-10-13.001`). No S3 flash, erase, eFuse,
credential, enrollment, ownership, or NVS operation was performed. COM10's
read-only `flash-id` used its expected reset to identify the S3. The inactive
C3 OTA app partition was erased/written as part of the authorized app-only
update; no whole-chip erase was used. No motion injection was issued.

## Live identity and recoverable layout

- COM4 was re-identified by Windows PnP, pySerial, and esptool as ESP32-C3
  revision 0.4, MAC `14:63:93:c5:d1:58`, 4 MiB XMC flash.
- COM10 was identified by Windows PnP and `esptool flash-id` as ESP32-S3
  revision 0.2, MAC `e0:72:a1:d3:8d:34`, 16 MiB flash and 8 MiB PSRAM. This
  proves the chip/board class, not its running firmware composition.
- Live C3 partition table SHA-256:
  `219614d3586ae564ce51dfc462e6e7773b590abe41048a10bc513e1a7d799469`.
  Partitions include NVS at `0x9000`, OTA metadata at `0xF000` (8 KiB),
  `ota_0` at `0x20000` (1,966,080 bytes), and `ota_1` at `0x200000`
  (1,966,080 bytes). The candidate build partition table matched.
- Before update, OTA sequence 1 selected `ota_0`; sequence 1 CRC was valid,
  the second OTA record was erased. `ota_1` readback was all `0xFF`.
- The prior `ota_0` full-partition readback is retained locally under the
  ignored build directory and hashes to
  `766d62677f345e146e2a5056ef8f9a0c94c93b8d9a7bcc6b031286b26084f7bb`.
  Its trimmed installed app was version
  `c69960fb064a-gs114-rpfdiag-4e1b` and SHA-256
  `70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530`.
- The live bootloader region matched the local bootloader artifact from the
  same prior build; its region readback SHA-256 is
  `65a208754270687749b53c75a4c1c32df84d5106ec133eac560879881f26a659`.
  That build's sdkconfig has
  `CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE=y`. No bootloader bytes were written.

## Candidate and separate normal build

Both builds used ESP-IDF 6.0.3 and explicit `IDF_TARGET=esp32c3` from the
current source. The candidate version is
`60574c4-gs117-hilawake-20261024`, size 945,584 bytes, SHA-256
`d1e7f89d473d3443b4b0380a53764f7521e88df2a452251f8a326656a8d74136`.
`CMakeCache.txt` confirms:

```text
GS_HIL_BUILD=OFF
GS_HIL_CONTROL=ON
GS_BAT_C8_PHYSICAL_WAKE=OFF
IDF_TARGET=esp32c3
```

The product NodeRuntime, security, NVS storage, ESP-NOW, retry/ACK, and HIL
control sources are shared with the normal product composition. Existing
profile logic reports `HIL_AWAKE_TEST_ONLY`; production light-sleep logic is
not changed by this build profile. The separate normal C3 build completed
without installation, version `60574c4-gs117-sleep-20261024`, size 940,608
bytes, SHA-256
`e9993988feac724f31715a9e0b5ee351dbd6d52c68ecec6762856561cba28a78`, with
`GS_HIL_BUILD=OFF`, `GS_HIL_CONTROL=OFF`,
`GS_BAT_C8_PHYSICAL_WAKE=OFF`, `IDF_TARGET=esp32c3`. No GS-114 physical-wake
or battery qualification status is changed by either build.

## App-only deployment and verification

The existing ESP-IDF 6.0.3 `otatool.py write_ota_partition` wrapper was
attempted first; it failed before any app write because its wrapper passes
`input` to `_write_ota_partition`, whose parameter is named `input_file`.
The failure was `TypeError: _write_ota_partition() got an unexpected keyword
argument 'input'`. No image bytes were written by that attempt.

The official ESP-IDF `parttool.py write_partition --partition-name ota_1`
path was then used. Its observed flash operations targeted only OTA app slot
`0x200000..0x3DFFFF`; the slot had been verified blank beforehand. It wrote
the 945,584-byte candidate at `0x200000`, esptool verified the write hash,
and a full 1,966,080-byte readback confirmed the candidate prefix byte for
byte with all remaining bytes erased. Full readback SHA-256:
`f85872b76aa53990016770a4bc570f918e50992d610405653014bfec38d472e6`.
The active `ota_0`, bootloader, partition table, NVS, and retained-event
storage were not in the app write range.

The official `otatool.py switch_ota_partition --slot 1` then updated only the
8 KiB OTA selector at `0xF000..0x10FFF`; esptool verified its write hash. The
board booted the exact candidate from `ota_1`. The firmware's read-only
`GET_STATE` response reported:

```text
ota_slot=ota_1 power_mode=HIL_AWAKE_TEST_ONLY hil_build=0 hil_control=1 physical_wake=0
```

Across 27 read-only `GET_STATE` observations spanning roughly 15–132 seconds
of continuous uptime, COM4 remained responsive and the USB serial identity
remained exact. Heap stayed stable after initialization (`heap=197816`,
`min_heap=180344` in the later observations); no injection was pending and no
event was created.

The old `ota_0` image remains a recoverable application image. A manual
recovery selector operation is available through the same official tool:
`otatool.py --port COM4 --baud 460800 switch_ota_partition --slot 0`.
Automatic rollback is **not claimed**: the host selector operation changes
the sequence/CRC but does not establish the `ESP_OTA_IMG_NEW` state required
for the bootloader's pending-verify path. The new app remained on `ota_1`
after the 90-second interval. The existing prior app image is preserved; a
manual rollback was not needed or executed.

## Readiness and result

- Candidate image: **FLASHED and byte-for-byte VERIFIED** in `ota_1`.
- HIL-awake mode and `INJECT_MOTION`-eligible build flags: **VERIFIED** by the
  installed app's `GET_STATE` output.
- USB serial stability: **PASS** for the observed 27 status queries; no event
  injection was sent.
- `sensing_live=0` and `runtime_live=0` throughout; NodeRuntime owner-start
  was not observed. The source sets owner-start evidence only after the
  authenticated session/channel path completes, so authenticated Hub session
  readiness remains unproven. The current GS-179 health
  probe reports PostgreSQL, caregiver HTTPS, local backend and LAN TLS
  `PASS`, but `HUB_INGRESS_READY=NOT_CONFIGURED`. The TC-001 owner-only fixture
  receipt is absent. The S3 firmware image/profile and authenticated Hub
  ownership/trusted-time/enrollment remain unverified.
- Therefore TC-001 injection was not run. No EventKey, backend event, or APK
  event was generated or claimed. The historical HOST_SIM seed is not used.
- GS-114 light-sleep/physical-wake and battery qualification remain unchanged;
  this HIL image is not physical PIR qualification evidence.

Build outputs and complete flash readbacks remain under the ignored path
`code/build/gs117-c3-hil-awake-20261024-c3target/`; no binary or credential is
committed. Focused C3 profile tests passed **4/4** and TC-001 console tests
passed **17/17**. `make -C code validation-node` exited **2** with
`software_status=FAIL`, `physical_status=NOT_RUN`, and `source_unchanged=true`.
Its C3 HIL profile stage passed 4/4; the P0 stage failed its required
`product_status=PASS` check because physical qualification is `NOT_RUN` (26
scenario checks passed). The GS-178 caregiver browser test had one failure
out of 33 tests: expected two `[data-event-key]` elements, received zero.
Host board-stack simulation passed 10 groups; this is not physical evidence.
The captured report is
`code/evidence/validation_framework/node-1792812572305490461/report.json`.
Full stage notes are in the dated GS-117 handoff and R1 work state.
