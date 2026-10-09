# R1 ESP32-S3 N16R8 Hub bring-up — 2026-10-09

Authority: GS-D030, LOCKED hardware direction; context `2026-10-09.001`.
Source checkpoint `389ffd3048cd44afdbb9ef074ed2a96020a3641e`.
Canonical governance commit `9cda6ad4227bf54b8cb0ddc4279d72e20d6aafd7`;
S3 governance commit `1272d13af024dc886df398ac23c0e4e260d9593c`.
Both preflights PASS before target work. Canonical receives only governance;
independent storage history/source remains unchanged at context2026-10-08.002
and therefore becomes STALE against the new canonical version. No guard bypass.

## Physical identity and preservation

Windows CH343 adapter previously COM8 / bus5-1, VID:PID `1a86:55d3`, serial
`5C83119376`; WSL `cdc_acm` device `/dev/ttyACM0`, stable link
`/dev/serial/by-id/usb-1a86_USB_Single_Serial_5C83119376-if00`.
Read-only esptool5.4.0 checks report ESP32-S3 QFN56 revisionv0.2,
MAC `e0:72:a1:d3:8d:34`, 40 MHz crystal, flash16 MiB (reported manufacturer68 /
device4018), quad-flash eFuse mode and 3.3 V. Secure boot and flash encryption
are disabled on this development device; no security/eFuse settings were changed.

Full original flash16777216 B was privately saved and verified using on-device
`verify-flash` before any write. SHA-256:
`d73b6dd5a15e469a30629798664fb6e9e5c0ee30ef2679d75858d97a72b6fb15`.
Backup directory: `/home/udaybhan/.local/share/ghar-sajag/board-backups/e072a1d38d34-20261009/`.
Backups, manifest and exact changed-sector restore chunks have private permissions
and are outside Git. Original factory image identifies ESP-IDFv4.4.1 / June2022;
project/version fields do not identify the PCB. Original layout:

| Region | Offset | Bytes |
|---|---:|---:|
| NVS | 0x9000 | 24576 |
| PHY | 0xf000 | 4096 |
| Factory application | 0x10000 | 2031616 |
| VFS | 0x200000 | 6291456 |

Only the diagnostic bootloader, partition table, initial OTA metadata and app
were written, with esptool hash verification. Modified sector ranges:
`0x0..0x6000`, `0x8000..0x9000`, `0xf000..0x11000`, `0x20000..0xc4000`
(exclusive ends). No whole-chip erase. After the diagnostic run, on-device
checks confirmed original NVS24576 B and VFS6291456 B still match their backup.
The board now runs the diagnostic with a development partition table; restoring
the original firmware/layout is a separate explicitly controlled operation using
the preserved flash/chunks. Original VFS is preserved but the new table does
not expose it. No sensor Node was flashed or enrolled.

Chip/flash identity and working memory are established; module markings, PCB
model, camera-reserved pins, connectors and power/reset schematic remain unknown.
No camera/sensor/LED/button GPIO is assigned or driven. UART0 uses the S3 defaults
GPIO43/44, physically exercised through CH343. Reserve Octal PSRAM GPIO35–37;
native USB19/20 and strapping0/3/45/46 require the actual board schematic before
peripheral use. No pin equivalence with future Elecsynergy hardware is claimed.

## Target and measurements

New target: `firmware/hub/target/esp32s3/idf`. ESP-IDFv6.0.3, Xtensa GCC15.2.0,
`esp32s3`, `-Os` candidate, DIO flash40 MHz, Octal PSRAM40 MHz with startup
memory test. Native capability allocations expose PSRAM while standard malloc,
task stacks, BSS and recovery buffers retain their original internal-memory
policy. No XiP, external stacks, camera/ML components or new event protocol.

The product build directly reuses the complete original Hub `main` component,
entry point, shared application/security/storage/routine processing and C3 asset.
Configuration-only S3 PSRAM dependency; no entry wrappers or original-source edits.
Legacy HIL modes are rejected pending board-specific qualification. Diagnostic
is a separate build; it does not compose the product owner, enrollment or event ACK.

| Measured bytes | Hub composition | Diagnostic |
|---|---:|---:|
| Application .bin | 1791792 | 669760 |
| Unstripped .elf | 18721720 | 8374224 |
| Flash IROM (.flash.text) | 653952 | 478604 |
| Flash DROM (.flash.rodata) | 1039900 | 95524 |
| Additional flash appdesc/tdata | 272 | 272 |
| Static DRAM initialized data | 20962 | 20738 |
| BSS | 26504 | 16120 |
| Additional noinit | 2 | 2 |
| IRAM text + vectors | 76551 | 74475 |
| Bootloader | 21264 | 21264 |
| Current unsigned OTA slot margin | 2402512 | 3524544 |

RTC36 B slow +24 B fast are additional. S3 IDF `DIRAM` combines shared instruction
and data RAM; do not double-count its text with the ELF IRAM total. Both builds
and final relink exit0; no compiler/CMake warnings/errors observed. Retain matching
unstripped ELF/map and images under ignored `idf/build/{product,diagnostic}/`.
ELF debugging/symbol sections remain outside the loadable application image.
Product SHA-256: `4fe21d8521ce9252a604a6ca895eb99d0b89ce61d713ff7094e9431459d2ca81`.
Diagnostic SHA-256: `6780c921fb1a83f002879806e813c5a0218478e513a005a58850a06144379d3c`.
The final linked product ELF contains the exact931408-byte source C3 asset,
SHA-256 `ffaefebce02db03bea320b9a86898459b1a53ad864d23fa35ab2eaf9f8984772`.

## Development-only partitions

SDK-generated table and independent checks PASS: page alignment, app64 KiB
alignment, no overlap, two OTA slots and end below16 MiB.

| Partition | Offset | Size |
|---|---:|---:|
| nvs | 0x9000 | 0x6000 |
| otadata | 0xf000 | 0x2000 |
| phy_init | 0x11000 | 0x1000 |
| ota_0 | 0x20000 | 0x400000 |
| ota_1 | 0x420000 | 0x400000 |
| gs_journal | 0x820000 | 0x200000 |

Remainder intentionally unallocated. Existing classic partition files are
unchanged. This layout is authorized only for development, not a commercial
allocation, signed-image margin or 72-hour capacity guarantee. Rollback Kconfig
is enabled; signed FOTA/validation/failed-upgrade storage compatibility remain
mandatory and unqualified. No keys/eFuses/security policy were changed.

## Executed validation and boundaries

- Existing `make cpp-test`: PASS1479 checks.
- `hub-fresh-install-host-test`: PASS authenticated genesis/registry/event/reboot/
  duplicate/fault/domain/legacy cases in its supported fresh-install fixture.
- `hub-fota-guard-host-test`: PASS.
- `node-retirement-protocol-host-test`: PASS.
- SDK product and diagnostic builds, partition checks, linked-asset equality,
  evidence measurements, context preflights and whitespace: PASS.
- Physical diagnostic: flash hash checks; successful boot; AP64 Mbit/3 V Octal
  PSRAM detected8 MiB at40 MHz; SDK startup SRAM test and64 KiB scratch PASS;
  Wi-Fi STA initialization and ESP-NOW initialization PASS. No association,
  application transmissions, peers, NVS initialization or event ACKs.
- At boot: internal free346668 B / largest278528 B; PSRAM free8386156 B.
  Radio ready: internal free300144 B, minimum300052 B, largest258048 B;
  PSRAM free8386128 B. Six10-second heartbeats completed with internal free
  unchanged300144 B, minimum299960 B and main-stack minimum2368 B.
  No panic/boot loop or memory failure observed in this bounded run.

Physical logs: [R1_S3_HUB_BRINGUP_20261009.log](R1_S3_HUB_BRINGUP_20261009.log).
The committed text normalizes ANSI/line endings/trailing whitespace; the raw
serial capture remains preserved in the ignored artifact directory.
Reproduction build commands and board boundary: the new target's `README.md`.
Host logs and SDK build/config/measurement logs are preserved in the ignored
artifact directory. No historical capacity matrix, BAT-C8 gate, full release
gate or former instruction-encoding assertion was rerun. No broad audit.

**Full Hub composition was built, not flashed or physically qualified.** Its
secure identity/provisioning, durable ACK/retry/reboot, routines/alerts and C3
interchange remain pending on S3. The previous128-event lifecycle is unchanged;
production compact storage/sustainable reclamation and supported72-hour workload
are unqualified. Diagnostic heap/stack numbers do not qualify the full Hub's
80 KiB owner stack, FOTA/recovery peaks, fragmentation or endurance. GPIO mapping
and full S3 signed-FOTA/automatic rollback remain pending. C3/BAT-C8 unchanged.

Next essential action: bring up the authenticated S3 Hub application with one
existing C3 Node and qualify durable ACK, lost-ACK retry/dedupe and reboot recovery.
Later bounded milestones remain larger NVS lifecycle/retention, signed dual-OTA
rollback, routines/alerts, peak memory/endurance and BAT-C8/full R1 closure.
No push or automatic next-milestone implementation is authorized by this evidence.
