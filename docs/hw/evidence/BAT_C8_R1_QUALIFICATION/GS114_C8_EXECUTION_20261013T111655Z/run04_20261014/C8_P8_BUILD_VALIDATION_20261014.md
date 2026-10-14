# GS-114 C8-P8 S3 candidate build and install approval — 2026-10-14

## 2026-10-14 physical installation follow-up

**App-only write verified; runtime boot remains unverified. Physical P8 was
not started.** This section supersedes the pending-install status below while
preserving that build-time record.

### Hardware and pre-write readback

- Windows S3: BUSID `3-1`, CH343 COM9, `1a86:55d3`, serial `5CBC401023`,
  `Attached`; WSL stable path
  `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5CBC401023-if00` resolved to
  `/dev/ttyACM0`. C3 was still the unrelated `0000:0002` descriptor-error
  device and was not attached or accessed.
- ROM identity: ESP32-S3 rev 0.2, MAC `7c:4f:ad:b7:2a:20`, flash ID
  `0x184068`, 16 MiB flash, 8 MiB PSRAM. Read-only security state:
  Secure Boot 0, Secure Download 0, flash-crypt counter `0x00`; no eFuse was
  modified.
- Actual partition payload SHA-256:
  `bb0066feee7368e621c6f0f0d7bfdf47cbc5bbbf4cfdd9eccab9525ad683f82a`,
  identical to the candidate's compiled 3,072-byte table. The 4,096-byte
  target read had `0xff` padding after that payload. Decoded rows exactly
  match `ota_0` 0x20000/4 MiB, `ota_1` 0x420000/4 MiB, `gs_outbox`
  0x820000/4 MiB, and `gs_state` 0xC20000/256 KiB.
- `otadata` SHA-256:
  `8ba3b110139f45443d4f268d1a3373ef99a1718b71d51664531b83ee2d4b91a3`.
  Copy 0: sequence 1, state 2, CRC valid; selector resolves to `ota_0`.
  Copy 1 is erased/invalid. This satisfied the authorized write condition.

### App write and post-write observation

The current-source candidate at
`code/build/gs114_fixture_pair/build-snmafa7y/s3/gs_r1_s3_hub.bin` was
rehashed immediately before installation: 1,894,496 bytes,
`f296c984dabda9fe537d2ae1c9d553af55287b5640b0ce34c48527dc50c369a8`.
Source/build commit is `ce9c436f0e9a8324c0785bad996ed9c4a421de3d`; its
embedded C3 hash remains the installed C3 app
`70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530`.
The only write address was `0x20000`; esptool reported erase range
`0x00020000–0x001eefff`, `Hash of data verified`, and expected RTS hard reset.
No other partition or device was written.

An exclusive ESP-IDF monitor opened on the same stable S3 path using
`--no-reset`. Its capture remained active for at least 300 seconds with no
USB/IP loss, but received no UART device bytes. Two `FIXTURE_STATUS` attempts
had no observed response. The monitor exited cleanly and released the port.
No boot banner, running-image identity, authenticated C3 rejoin, schema-3
NodeHealth, `RPF00 admission=OPEN`, or Durable ACK has been observed since
installation. The current app partition write is verified, but app boot and
runtime identity are not; the reason for UART silence remains unknown.

**Disposition: C8-P8 BLOCKED before stimulus / physical P8 NOT RUN.** No
`DROP_NEXT_DURABLE_ACK` command or PIR motion was issued. Do not perform another
reset, flash, power operation, or recovery write under the current approval.
The next physical P8 prerequisite is verified S3 runtime output/status plus
fresh authenticated C3 rejoin, schema-3 trace, and RPF00 OPEN. If recovery
requires another reset or app write, obtain separate authorization for that
exact action first. P3 and prior RPF07/P1/P2/P4/P5/P6/P7 PASS evidence remains
reused. P9 ACK/FOTA stay blocked on their separate fixtures.

Raw evidence files are listed in `p8_s3_physical_install_record_20261014.json`
and retained beside this report. Source branch HEAD before this evidence update
was `ead9a83b9df0a1cc928280760496747f1901e38e`.

## Disposition

**Build-time disposition at 2026-10-14 11:07 UTC:** Offline S3 candidate build and focused software validation PASS; the candidate had not yet been installed. The following section records the later approved physical installation attempt.

## Source and exact artifacts

- Canonical worktree: `/home/udaybhan/projects/Ghar_sajag_r1`, branch `feature/r1-commercial-baseline`.
- Builder/tooling commit: `ce9c436f0e9a8324c0785bad996ed9c4a421de3d` (pushed to `origin`).
- Build manifest source fingerprint: `59b8341efe0ea2b69d81d913349fbb37fba942f461f4de555f7283f09c018818`.
- Context preflight: PASS, context `2026-10-13.001` at task startup.
- Toolchain: ESP-IDF 6.0.3, `esptool image-info` v5.4.0.
- Build command: `make -C code gs114-s3-c8-p8-build GS114_C3_APP=build/gs114_fixture_pair/build-8rqa0oi5/c3/gs_hw_m1_node.bin GS114_C3_SHA256=70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530` (exit 0).
- Unique build root: `code/build/gs114_fixture_pair/build-snmafa7y/` (ignored local build output).
- S3 app: `code/build/gs114_fixture_pair/build-snmafa7y/s3/gs_r1_s3_hub.bin`, 1,894,496 bytes, SHA-256 `f296c984dabda9fe537d2ae1c9d553af55287b5640b0ce34c48527dc50c369a8`.
- Reused C3 app input: `code/build/gs114_fixture_pair/build-8rqa0oi5/c3/gs_hw_m1_node.bin`, 940,752 bytes, SHA-256 `70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530`. This matches the installed C3 app recorded in the physical P3 evidence. The builder verified the expected digest, staged byte-identical content, skipped the C3 build, and checked the S3 image embeds exactly one matching copy.
- Compiled S3 partition binary SHA-256: `bb0066feee7368e621c6f0f0d7bfdf47cbc5bbbf4cfdd9eccab9525ad683f82a`; decoded compiled rows match the source partition CSV.

The manifest records only an S3 app artifact for this build, `hardware_actions=NONE`, `physical_status=NOT_RUN`, and `deployment.status=NOT_INSTALLED`. No full-device flashing command was run.

## Profile and image compatibility

The built image is ESP32-S3, 16 MiB flash, DIO/40 MHz, octal PSRAM/40 MHz, with rollback support in the fixture profile. Build options are `GS_HIL_BUILD=OFF`, `GS_HIL_CONTROL=OFF`, `GS_HIL_COMMISSIONING=ON`, `GS_S3_DIAGNOSTIC_ONLY=OFF`, and `GS_HIL_C8_ACK_DROP=ON`. The existing one-shot ACK suppression remains isolated and default OFF outside this explicit profile; no production ACK, authentication, replay, or durability code was changed for this builder extension.

The compiled table is:

| Label | Offset | Size |
|---|---:|---:|
| `nvs` | `0x9000` | 24 KiB |
| `otadata` | `0xF000` | 8 KiB |
| `phy_init` | `0x11000` | 4 KiB |
| `ota_0` | `0x20000` | 4 MiB |
| `ota_1` | `0x420000` | 4 MiB |
| `gs_outbox` | `0x820000` | 4 MiB |
| `gs_state` | `0xC20000` | 256 KiB |

S3 app size is 1,894,496 bytes, leaving 2,299,808 bytes in a 4 MiB OTA slot. The manifest and independent `esptool image-info` report valid ESP32-S3 image checksum/hash metadata. The existing target profile reports Secure Boot and flash encryption disabled in its `sdkconfig`; no eFuse or security setting was read or changed in this software-only build.

## Focused validation

- `make -C code s3-fixture-commissioning-test`: PASS, 14 tests. Includes default/profile isolation, postcommit gate checks, exact C3 asset hash staging and mismatch rejection, and OTA/partition compatibility checks.
- `make -C code c8-ack-drop-gate-host-test`: PASS, 16 checks.
- AddressSanitizer + UndefinedBehaviorSanitizer build/run of `tests/cpp/c8_ack_drop_gate_validation.cpp`: PASS, 16 checks.
- ThreadSanitizer build/run of the same gate: PASS, 16 checks.
- Target build validator: PASS; ACK-drop command marker present only for the selected profile, broad Hub HIL control markers absent, RPF/commissioning markers present, exact embedded C3 hash verified, compiled S3 partitions match the source table, and app fits both OTA slots.
- Prior source-matched P8 fixture/security receipts remain reusable: the gate's eligible-new-durable-effect conditions, default-off behavior, one-shot behavior, duplicate handling, bounded arm/expiry, overflow, concurrency and invalid-profile rejection were already tested. No firmware behavior source changed in this build-tool task.

These are offline software/build results only. They do not establish that this binary is installed or that physical P8 passed.

## Build-checkpoint active-slot notes and pre-approval plan

This section records the state before the operator's later approval and actual
readback. The physical follow-up at the start of this report supersedes this
pending plan.

The latest preserved S3 boot banner in `run03_20261014/s3_uart_timestamped.log` is at `2026-10-14T03:34:27.579676954Z`; it reports the fixture partition table and `Loaded app from partition at offset 0x20000`, i.e. `ota_0`. The banner's app version is `72a223fc3b29-gs114-rpfdiag-1eec`, not a byte-level identity for the later c699-based candidate. Later authenticated schema-3 trace decoding and `FIXTURE_STATUS` responses establish runtime behavior, but do not attest the current S3 app hash or a fresh OTA-selector readback. Therefore the last boot-observed slot/offset is `ota_0`/`0x20000`; the current running S3 image SHA-256 and post-detach active selector remain **unverified**.

Proposed bounded installation after explicit operator approval:

1. Refresh Windows `usbipd list`; confirm exact S3 CH343 serial `5CBC401023`, VID:PID `1a86:55d3` (historically BUSID `3-1`/COM9, last observed Shared). Reattach only that identified S3 to WSL after approval; do not attach or probe C3. Preserve all existing captures. Verify one S3 reader only and capture a fresh pre-operation `FIXTURE_STATUS` and authenticated C3 health/admission.
2. Identify S3 MAC `7c:4f:ad:b7:2a:20` and 16 MiB flash, then enter S3 ROM download mode under the same approval to read the partition table and `otadata` without writing. This controlled reset is required for the readback. Stop if the identity/profile differs or the selected app partition cannot be resolved unambiguously. The historical `ota_0`/`0x20000` boot record is supporting evidence, not the pre-write check.
3. If the readback confirms `ota_0` at `0x20000`, write **only** `gs_r1_s3_hub.bin` there. Use the stable S3 by-id path `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5CBC401023-if00`; app offset `0x20000`, image SHA-256 `f296c984dabda9fe537d2ae1c9d553af55287b5640b0ce34c48527dc50c369a8`. Do not apply the generated full-device `flasher_args.json`; do not write bootloader, partition table, `otadata`, NVS, `gs_outbox`, or `gs_state`; do not touch C3. The app-only write overwrites the currently selected app; ROM-download recovery remains available if boot fails. If selector reports `ota_1` or any other state, stop without writing and revise the plan.

The planned app command, after the selector check, is `python -m esptool --chip esp32s3 -p /dev/serial/by-id/usb-1a86_USB_Single_Serial_5CBC401023-if00 --before no-reset --after hard-reset write-flash --flash-mode dio --flash-size 16MB --flash-freq 40m 0x20000 code/build/gs114_fixture_pair/build-snmafa7y/s3/gs_r1_s3_hub.bin`. The readback step enters ROM with esptool's normal reset sequence and leaves the chip there; if that sequence cannot be performed safely or the active selector is unclear, stop before write.
4. Verify the app write, perform the expected boot reset, then restore one exclusive S3 timestamped capture. Observe the actual boot offset/app version, `FIXTURE_STATUS`, fresh authenticated C3 NodeHealth/schema-3, RPF00 OPEN, and normal Durable ACK behavior before arming P8.
5. Recovery candidate if the new app fails to boot: the previously built ACK-drop-OFF S3 app `code/build/gs114_fixture_pair/build-8rqa0oi5/s3/gs_r1_s3_hub.bin`, SHA-256 `ca178fe30cc620d3fe0cb5817da9d8a98b07b70cb5f7c443045c85180dd46379`; it embeds the same verified C3 app and uses the same compiled partition map. Recovery is app-only at `0x20000`, preserving all non-app partitions. Do not erase or recommission.

Capture restoration must account for the prior USB/IP socket abort 10053 and stale reader. The current process snapshot showed no esptool, build, or serial capture process; the remaining `tail -F` follows only an old raw log. After approval, use a fresh Windows `usbipd list` to identify S3 BUSID before any S3-only reattachment, verify WSL stable by-id mapping, and start a new exclusive reader into a new uniquely named evidence file only after checking ownership. If the transport again detaches or a reader is blocked in kernel I/O, preserve logs and stop; do not force-kill it or retry blind attachment.

At the 11:07 build checkpoint, operator approval was still required before
USB/IP reattachment, reset, firmware write, or physical P8 stimulus. The later
approved installation and its runtime observation are recorded at the start of
this report. P3 and prior RPF07/P1/P2/P4/P5/P6/P7 PASS evidence remain reused.
P8 remains BLOCKED before stimulus. P9 ACK remains blocked on a verified long
ACK-hold observation fixture; signed FOTA remains blocked on matched signed
test/recovery images, trusted signing provenance, supported authenticated
trigger and recovery procedure. P10 remains separate under GS-149. GS-114
remains In Progress.
