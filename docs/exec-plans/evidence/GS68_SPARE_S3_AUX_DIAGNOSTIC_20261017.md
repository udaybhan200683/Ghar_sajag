# GS-68 / GS-172 spare-S3 auxiliary diagnostic — 2026-10-17

## Disposition

**Software candidate: BUILD PASS. Physical installation: NO-GO.** Host-only USB/PnP observations are consistent with the owner's dedicated spare and differ from the protected C8 fixture inventory. A read-only security inspection produced no security data and its USB command blocked. Secure Boot, Flash Encryption, ROM/download restrictions, installed partitions, recovery capability, and running image remain UNKNOWN. No candidate installation or physical diagnostic was performed.

This is auxiliary TEST_ONLY readiness evidence. It does not satisfy GS68-PHY-001..010, DS signing, mTLS, GS-68 physical acceptance, or GS-40 physical acceptance.

## Repository and provenance

- Repository: /home/udaybhan/projects/Ghar_sajag_r1
- Branch: feature/r1-commercial-baseline
- Source implementation HEAD: cfc89a8e7bd6009eddde5790814e557357d8a032
- Source code-tree OID: e4c8fd938d394be5f1e595bd7d3036744a9888e3
- Context preflight: PASS; version 2026-10-13.001
- Implementation commits: dbaf834, 1fafdf7, ea76ce6, cfc89a8e7bd6009eddde5790814e557357d8a032. The last fixes a C++ namespace error found by the non-flashing build.
- Existing untracked PWA, Android, managed-component, GS-114/C8, GS-40 and other evidence paths were preserved and not staged. Separate GS-177 worktree/process was not changed or signaled.
- Source-binding runner accepts an immutable image source commit only when it is an ancestor of current HEAD and the committed code tree/build inputs remain identical. Later documentation-only commits do not impersonate the artifact source commit.

## Current build candidate

Artifact: code/build/validation_targets/gs68_cloudsync_diag_20261017_auxfix/build/gs_r1_s3_hub.bin (ignored local build output).

| Property | Verified value |
|---|---|
| Build source commit | cfc89a8e7bd6009eddde5790814e557357d8a032 |
| App image | 278,944 bytes; SHA-256 855b586d6e7a51ebad22eb45c81c170897bbb0dbfd291b921d60bca72ae15049 |
| ELF SHA-256 from image metadata | 67a0ba642bca413e4018c0102d2a4c4e1d3b646e2f3b5add94abd8cf90d20c46 |
| Profile SHA-256 | 7d13aa13684953744737b653c82ec7f8b95d0c6bfc715649bc99d501313d3c72 |
| Effective sdkconfig SHA-256 | ff3150eeeac79a4a80b5a718a20408386d90d5a491cb199d763e0b6190105a7a |
| Development partition CSV SHA-256 | 9da4b591a461c8b251e3ced8107d3ff3bc4a5fe4fd8844670ba4d90163d3ea29 |
| Partition table binary SHA-256 | 4828fb04f0569bcc5ffafaf887bb7f360e6ab858ec29df00297671f5f2a468fe |
| Build inputs SHA-256 | 0d92a028bacbca7663b001fac6bb6894d402118b36e40ca9ecbe8b202d26f39b |
| ESP-IDF / target / profile | v6.0.3 / ESP32-S3 / GS68_CLOUDSYNC_DS_MTLS_HIL TEST_ONLY |
| Effective console | USB Serial/JTAG primary; UART0 primary disabled; USB secondary disabled; USB driver-backed blocking stdin |
| Image format check | esptool v5.4.0 image-info: ESP32-S3, 16 MB image header, checksum and validation hash valid |

The successful build used no serial or hardware. Its image metadata reports
DS peripheral selected but not provisioned; this is not evidence of silicon DS
signing. The candidate contains no production credential or production time
anchor and does not enable a commercial endpoint. The former c0fb82c image
(473,312 bytes, SHA-256
c0fb82c69fe030f8a4358b7783e7c537156dfdb361b4df1a620831210d1bef65) is
**superseded** by this source-corrected build and must not be installed.
Earlier e8e0a623 and installed-baseline c905af734 artifacts are not substitutes.

## Software validation

- make -C code gs130-hil-runner-test: PASS; 1,738 C++ protocol assertions and 84 Python tests. Physical/default HIL cases remained NOT_RUN; no port opened.
- Focused auxiliary runner, source-binding, and signed-time helper tests: PASS, 13 tests.
- make -C code gs68-node-diag-protocol-host-test: PASS; 1,738 assertions.
- ESP-IDF 6.0.3 non-flashing S3 diagnostic build: PASS; hardware_actions=0; physical=NOT_RUN.
- First build attempt exposed a namespace compile error. It was fixed in cfc89a8 and the final source-bound build above passed. No stale image is used as the current candidate.

## Fixture and inspection results

Host-only USB enumeration positively distinguished the owner-designated spare
from the protected C8 inventory using available USB/PnP metadata. Public
evidence intentionally omits serial, MAC, full by-id path, Windows device
instance IDs, and private evidence paths; the private host receipt is stored
under /home/udaybhan/.local/share/ghar-sajag/GS68-20261017 with restrictive
permissions.

ESP-IDF v6.0.3 / esptool v5.4.0 was used for one attempted read-only security
inspection. The command included --before default-reset and --after hard-reset;
these are reset-capable transport options. It printed the tool and serial-path
header, then blocked without returning security information. The process was
not killed, retried, or detached; no further device I/O was attempted. No flash
readback or backup was made. No flash, erase, eFuse/security write, credential,
production endpoint, or C8 operation occurred.

| Physical result | State | Reason |
|---|---|---|
| Fixture identity | OBSERVED, consistent with designated spare | Host USB/PnP only; identifiers redacted publicly |
| Secure Boot / Flash Encryption / ROM restrictions | UNKNOWN | Security query returned no data |
| Installed partition map / active OTA slot | UNKNOWN | No flash inspection |
| Usable backup and recovery route | NOT ESTABLISHED | No baseline image/metadata readback or restore validation |
| Candidate installed / running image verified | NO / NO | Installation gates not met |
| USB delayed/fragmented/malformed/sequential commands | NOT_RUN | Candidate not installed |
| Silicon PSA RNG / RSA signed-time proof and negatives | NOT_RUN | Candidate not installed |
| DS signing / live mTLS | NOT_RUN | No provisioned DS context or client credential; outside scope |
| Official GS-68 and GS-40 physical acceptance | NOT_RUN | No official physical cases executed |

## Exact next action and stop conditions

The installation gate remains NO-GO until a stable USB connection permits a
successful documented read-only security inspection, the installed bootloader,
partition table, OTA metadata/slot and application are identified, Secure
Boot/Flash Encryption/download restrictions are understood, and a restorable
baseline recovery image plus metadata is obtained and verified offline. Then
re-evaluate app-only compatibility at the measured application offset. Do not
reuse historical offsets as observed facts, force security overrides, or
substitute an older image. After all gates pass, use the owner's conditional
authorization only for the exact current digest and a bounded application-only
TEST_ONLY installation; stop on any reset, identity, image or behavior mismatch.

If USB transport remains blocked or the protection/recovery state cannot be
established, installation stays NO-GO. The next safe action is to repair the
USB/IP connection and repeat only the read-only preflight, with no flash write.

Production D05/D12/D06 approvals remain open: pilot CA/issuer and trust
custody; S3 DS key/eFuse custody and lifecycle; authenticated-time authority,
anchor, freshness and rollback-resistant state; authoritative ownership and
credential registry/lifecycle; Secure Boot, Flash Encryption and recovery
policy. Existing P0 product_status=PARTIAL and the Hub migration assertion and
sanitizer timeout blockers remain open.

## 2026-10-17 — Windows-native transport recovery attempt

Canonical HEAD and `origin/feature/r1-commercial-baseline` were both
`e81272909d803a311f9e6a08bf85eeba29b97d3f`; tracked state was clean. Existing
untracked assets and the separate GS-177 worktree were preserved. Context
preflight returned PASS. No esptool process was running before inspection; the
separate GS-177 PWA/Playwright validation remained active and was not
interrupted.

Host-only checks found no WSL `/dev/ttyACM*`, `/dev/ttyUSB*`, or
`/dev/serial/by-id` device. Current `/sys/bus/usb` entries were only vhci root
hubs. Windows reported the owner-designated spare on BUSID 3-1, VID:PID
303a:1001, as USB Serial Device (COM10) plus USB JTAG/serial debug unit;
`usbipd list` state was **Shared**, not Attached to WSL. No detach or attach was
performed. The Windows USB parent identity token hash matched the restricted
prior spare receipt; no full identifier is included in public evidence. COM10
WMI status was OK. Windows `mode COM10` read only the host line configuration.

Candidate artifact recheck: 278,944 bytes and SHA-256
`855b586d6e7a51ebad22eb45c81c170897bbb0dbfd291b921d60bca72ae15049`, matching
the report's TEST_ONLY candidate. Source `cfc89a8e7bd6009eddde5790814e557357d8a032`
is an ancestor of current HEAD. Effective sdkconfig hash remains
`ff3150eeeac79a4a80b5a718a20408386d90d5a491cb199d763e0b6190105a7a`; profile
hash remains `7d13aa13684953744737b653c82ec7f8b95d0c6bfc715649bc99d501313d3c72`.
The build report identifies USB Serial/JTAG as primary console, no UART0
primary, TEST_ONLY diagnostic composition, and no provisioned DS context. No
build or firmware validation was repeated.

Windows esptool v5.4.0 help confirmed `--before no-reset`, `--after no-reset`,
`--no-stub`, and one connection attempt are available. The single bounded
read-only command was:

```text
esptool.exe --chip esp32s3 --port COM10 --baud 115200 --before no-reset --after no-reset --no-stub --connect-attempts 1 get-security-info
```

Observed output reached “Connecting....” and returned pySerial **Write timeout**
after about 11.4 seconds (exit 1). No security information was returned. This
is consistent with ROM sync not being available on the current application-side
USB console; it does not establish a device or driver fault. The command
explicitly selected no-reset before and after connection. No flash write, flash
read, eFuse operation, or USB/IP detach was requested. No further board I/O was
performed after the timeout.

The private redacted console receipt was retained with mode 0600 outside the
repository; its SHA-256 is
`7b09368bda3a72441cec194260379f341b35fce552152f65321a8d07ba9f698b`.

| Gate | Updated result |
|---|---|
| Spare identity | Windows USB parent token hash matches the prior restricted spare receipt; owner designation remains spare, not C8 |
| WSL USB/IP | No serial device attached; BUSID 3-1 remains Windows-side Shared |
| esptool transport | COM10 opened; one no-reset ROM sync attempt ended in pySerial Write timeout |
| Secure Boot / Flash Encryption / ROM restrictions | UNKNOWN; no device security report |
| Installed partition table / OTA slot / app image | NOT READ |
| Baseline backup / validated restoration | NOT ESTABLISHED |
| Candidate installed / running image matched | NO / NO |
| Physical auxiliary USB / PSA-RNG / signed-time tests | NOT_RUN |
| Installation decision | **NO-GO** |

The transport issue is narrowed: the stale WSL attachment is not current because
usbipd shows Shared and WSL has no serial device; the Windows COM interface is
present and matches the spare receipt, but no-reset ROM protocol communication
is unavailable. `get-security-info` requires ROM bootloader protocol. The
candidate's USB console firmware does not itself provide that ROM interface.
Recovery therefore requires a separately planned and approved ROM-entry method
or a qualified non-resetting debug path, followed by fresh security inspection.
Do not change COM line state, force reset/download mode, detach unrelated USB
devices, or retry esptool blindly. Until security state is known, partition
compatibility and readback permissions remain unknown; until a restorable
baseline and offline-validated method exist, application-only installation
remains NO-GO.

Private host-only transport receipts remain outside the repository under the
existing restricted evidence directory. Public evidence contains no serial
number, PnP instance ID, full port identity, raw flash or credential material.

## 2026-10-17 — Controlled ROM-entry preflight blocked before device operation

Canonical branch remains `feature/r1-commercial-baseline`; starting HEAD was
`ac42690c7c75b686aec27f5a0e61f1ced1dad40c` and matched origin. Context
preflight passed. The candidate was rehashed at 278,944 bytes with SHA-256
`855b586d6e7a51ebad22eb45c81c170897bbb0dbfd291b921d60bca72ae15049`.
No implementation tests or builds were repeated. WSL again had no
`/dev/ttyACM*`, `/dev/ttyUSB*`, or `/dev/serial/by-id` device.

The authorized automatic ROM-entry attempt was **not started**. A host-only
Windows interop probe failed before returning any Windows state:
`UtilAcceptVsock:273: accept4 failed 110` (exit 1). As a result, current
COM10/BUSID ownership, current spare identity and any competing COM10 handle
could not be verified. No Windows-native esptool command, reset, ROM sync,
USB/IP attach/detach, or other device I/O was performed. The prior session's
Windows observation (COM10, BUSID 3-1, Shared and matching the spare receipt)
is historical, not a current verification.

The installed esptool v5.4.0 help was previously observed to offer
`--before usb-reset`, `--before no-reset`, `--after no-reset`, and
`--no-stub`. Espressif's S3 serial-connection guide documents entering ROM
download mode using BOOT held while RESET is pressed; the USB Serial/JTAG
controller documentation describes its ROM download behavior. The previous
no-reset query demonstrated that application-console communication alone did
not complete ROM synchronization. References: [ESP32-S3 serial connection and
download mode](https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/get-started/establish-serial-connection.html),
[ESP32-S3 USB Serial/JTAG console](https://docs.espressif.com/projects/esp-idf/en/release-v5.5/esp32s3/api-guides/usb-serial-jtag-console.html),
[esptool reset options](https://docs.espressif.com/projects/esptool/en/release-v4/esp32s3/esptool/advanced-options.html).

| Gate | Result |
|---|---|
| Current Windows device and competing-handle check | BLOCKED by Windows interop failure; not verified this session |
| Automatic ROM entry / reset | NOT_RUN; no device command issued |
| Security information | UNKNOWN; no query executed |
| Installed partition / OTA slot | NOT READ |
| Recovery backup / validated restore path | NOT ESTABLISHED |
| Candidate installed | NO |
| Application-only installation readiness | **NO-GO** |

Private host receipt is outside the repository with mode 0600; SHA-256
`129c4d1588d64c8f82c8d16142266d97731dcee3472da20dc3338125f128a18e`.
Next step: restore Windows interop without shutting down WSL or interrupting
other work, then repeat host-only COM10/BUSID identity and handle checks. Only
if the current device still matches the spare and the port is uncontended may
the single owner-authorized `usb-reset`/documented automatic ROM-entry sequence
be attempted, with a bounded `get-security-info` query and no stub. Stop on any
failure; manual BOOT/EN intervention needs separate owner availability and
approval. No partition access or installation is permitted until protection
state and recovery readiness are known.

## 2026-10-17 — ROM security and read-only partition/recovery inspection

### Current fixture and transport

Windows interoperability recovered: `cmd.exe /c ver` returned Windows
10.0.19045.6466 and PowerShell returned 5.1.19041.6456. Canonical repository
started at `39f52be046b399492e7259b6f5a6f0de826e1fb3`, synchronized with origin;
context preflight passed. Current Windows USB parent metadata matched the
restricted spare token hash; COM10 was present with WMI status OK, and usbipd
showed BUSID 3-1 / VID:PID 303a:1001 as Shared. No other process command line
referenced COM10; no handle-inspection utility was installed. The USB parent
identity matched the prior spare receipt and is distinct from protected C8
inventory. No C8 interface was opened.

Installed Windows esptool/espefuse version was 5.4.0. A single automatic
ROM-entry and read-only security query succeeded using:

```text
esptool.exe --chip esp32s3 --port COM10 --baud 115200 --before usb-reset --after no-reset --no-stub --connect-attempts 1 get-security-info
```

It identified ESP32-S3 QFN56 revision v0.2, 8 MiB embedded PSRAM, USB
Serial/JTAG, and returned security flags `0x00000000`: **Secure Boot Disabled**,
**Flash Encryption Disabled**, `SPI_BOOT_CRYPT_CNT=0`. The command left the
device in ROM bootloader. A filtered, read-only `espefuse summary` query (no key
blocks) confirmed `DIS_DOWNLOAD_MODE=False`, `ENABLE_SECURITY_DOWNLOAD=False`,
`DIS_FORCE_DOWNLOAD=False`, `DIS_USB_SERIAL_JTAG_DOWNLOAD_MODE=False`,
`DIS_USB_OTG_DOWNLOAD_MODE=False`, `DIS_USB_JTAG=False`,
`DIS_USB_SERIAL_JTAG=False`, `DIS_DOWNLOAD_MANUAL_ENCRYPT=False`,
`SECURE_BOOT_EN=False`, `SPI_BOOT_CRYPT_CNT=0`, and `RD_DIS=0`. The S3 ROM
download path is therefore not fuse-disabled and secure-download mode is not
enabled. This is observed eFuse/report data, not an inference from compilation.

`esptool flash-id` returned manufacturer `0x68`, device `0x4018`, and detected
flash capacity **16 MiB**. A real `read-flash` command succeeded, establishing
ROM flash readback capability. Flash writes were not tested.

### Installed layout and image evidence

The following data was read with Windows-native esptool `--before no-reset
--after no-reset --no-stub --connect-attempts 1`; no reset occurred after ROM
entry:

| Readback | Observed result | Private SHA-256 |
|---|---|---|
| Bootloader, 0x00000000, 0x8000 bytes | Valid ESP32-S3 image, flash size 16 MiB, checksum and image hash valid; ESP-IDF v6.0.3, compiled 2026-10-17 05:50:18 UTC | `ae304441aaaad2b52765d48f4b37752f2ab26a65a480f5f1f9586cd54ebe1580` |
| Partition table, 0x8000, 0x1000 bytes | Valid entry MD5; six entries below; first 3072 bytes match candidate table exactly, followed by erased 0xFF padding | `101adada9e724af39b0ff503d609f7cf90378f5aa3a6be03799ba695160337d9` |
| OTA metadata, 0xF000, 0x2000 bytes | Valid OTA data CRC; sequence 1 and valid state select OTA0; second record erased/invalid | `8ba3b110139f45443d4f268d1a3373ef99a1718b71d51664531b83ee2d4b91a3` |
| OTA0 app recovery range, 0x20000, 0x100000 bytes | Complete ESP32-S3 app image validates checksum and SHA-256 footer; app version `072e94`, ESP-IDF v6.0.3; source commit not established | `f15fb947e95e8e1526508bd79258554b2511ff6860d63e9059ca51908d5af41d` |

Measured installed partition entries:

| Label | Type/subtype | Offset | Size |
|---|---:|---:|---:|
| nvs | 0x01/0x02 | 0x9000 | 0x6000 |
| otadata | 0x01/0x00 | 0xF000 | 0x2000 |
| phy_init | 0x01/0x01 | 0x11000 | 0x1000 |
| ota_0 | 0x00/0x10 | 0x20000 | 0x400000 |
| ota_1 | 0x00/0x11 | 0x420000 | 0x400000 |
| gs_journal | 0x01/0x02 | 0x820000 | 0x200000 |

The installed 16 MiB table matches the TEST_ONLY candidate's partition entries
and offsets. The installed app image is not the candidate: its observed app
version/ELF digest differ from candidate version `cfc89a8` / ELF SHA-256
`67a0ba642bca413e4018c0102d2a4c4e1d3b646e2f3b5add94abd8cf90d20c46`. The
candidate remains 278,944 bytes, SHA-256
`855b586d6e7a51ebad22eb45c81c170897bbb0dbfd291b921d60bca72ae15049`, and fits
the measured 4 MiB OTA slots.

### Recovery assessment and limits

A 4 MiB OTA0 readback was attempted with a 330-second bound; it timed out at
approximately 94.9% and produced no output file. It is not treated as a
backup. Two successful 512 KiB reads were then combined into a contiguous 1 MiB
private capture. `esptool image-info` validates the entire installed app image
within that 1 MiB range. The range is larger than the candidate's 278,944-byte
write length and covers the bytes/sectors an app-only update of the candidate
would alter. Bootloader, partition table and OTA metadata were also read and
hashed; NVS, OTA1 and `gs_journal` contents were intentionally not read.

The private backup directory is mode 0700; readback and manifest files are
mode 0600. The manifest SHA-256 is
`4021c2294e7ee157800edffc4e115f03635611e9b0aaa0c822935bba44f607c6`. It records
the commands and all private artifact hashes. No raw device identifiers,
backups, NVS contents, credentials, or key material were committed or uploaded.

**Recovery path:** after separate authorization, an app-only restore can write
the private 1 MiB OTA0 capture back at the measured address `0x20000`, using
esptool's documented `write-flash` address/file form, ROM USB Serial/JTAG, and
no force/security override. The bootloader, table and OTA metadata are not part
of the app write and remain unchanged. This command path and source image are
validated offline, but restoration was not exercised (would modify flash).
Therefore the recovery path is prepared and bounded to the app region, not
destructive-restore tested. Full-flash, NVS, OTA1 or journal recovery is not
established.

| Gate | Result |
|---|---|
| Spare identity / C8 exclusion | PASS, current USB parent token matches restricted spare receipt; C8 untouched |
| ROM entry and security report | PASS; one `usb-reset`, one connect attempt, no stub |
| Secure Boot / Flash Encryption | Observed disabled / disabled |
| ROM download restrictions | Queried download-disable bits false; normal ROM download not fuse-disabled |
| Flash readback | PASS; flash-id and read-flash succeeded |
| Installed partition/active slot | PASS; measured table, valid OTA metadata selects OTA0 |
| Candidate partition compatibility | PASS; table content matches and candidate fits OTA0 |
| App-only recovery artifact | PASS; complete valid app image plus candidate write-range margin, private/hash-verified |
| Physical restore test | NOT_RUN; no flash modifications authorized |
| Candidate installed / running-image match | NO / NO |
| GS-68 and GS-40 official physical acceptance | NOT_RUN |

The earlier 330-second full-slot read timeout did not change flash. Current task
prohibits installation or writes, so no candidate was flashed. A separate task
must authorize any future installation and use the exact current candidate
digest, measured OTA0 offset, private app recovery file, no `--force`, and
stop/recovery conditions. Production DS signing/mTLS, credentials and all
official GS-68/GS-40 physical cases remain unqualified. Espressif documents the
filtered eFuse summary as a read operation and ROM/download behavior in its
[ESP32-S3 eFuse summary guide](https://docs.espressif.com/projects/esptool/en/latest/esp32s3/espefuse/summary-cmd.html)
and [ESP32-S3 serial connection guide](https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/get-started/establish-serial-connection.html).
