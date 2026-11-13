# Isolated R1 ESP32-S3 N16R8 target

Authority: GS-D030. ESP-IDF v6.0.3. Raw ESP-IDF defaults still include the
historical 2 MiB `gs_journal` map. The authoritative product entry point,
`build-outbox.sh`, always selects the separate 4 MiB `gs_outbox` plus 256 KiB
`gs_state` layout and two 4 MiB OTA slots. These remain development layouts,
not approved commercial capacity guarantees.
The original classic target and C3 firmware are unchanged. Product composition
reuses the entire classic target's `main` component and shared application;
a configuration-only S3 component enables native ESP-IDF PSRAM startup.
The original Hub entry point is reused without wrappers or processing changes.
Do not flash that product build as a replacement for storage/FOTA qualification.

## Board boundary

Current adapter: CH343, VID:PID 1a86:55d3, UART console `/dev/ttyACM0`.
Chip/flash/PSRAM package identification is not a PCB model/pinout identification.
UART0 uses the ESP-IDF S3 default GPIO43/TX and GPIO44/RX, already reachable via
the board's adapter. No camera, sensor, LED, button or other board GPIO is driven.
GPIO35–37 are reserved for Octal PSRAM; GPIO26–32 are memory interface pins.
GPIO19/20 are native USB; GPIO0/3/45/46 are strapping pins. Actual camera-reserved
pins, exposed connectors, reset/power arrangement and module markings remain
unverified until the exact board schematic/markings are supplied. Legacy HIL
controls are rejected rather than assigning the old board's GPIO0 trigger.
No camera/AI library is added. No efuse or security configuration is changed.

## Reproducible builds

Use the existing outbox entry point for S3 product images. A no-argument call
selects the GS-117 Engineering profile; `release` explicitly selects a Release
profile. Both profiles use the same partition table and isolated build logic.

```sh
cd code/firmware/hub/target/esp32s3/idf
./build-outbox.sh
GS_NODE_FIRMWARE_ASSET=/path/to/existing/production-pair/assets/node_firmware.bin ./build-outbox.sh release
```

The default Engineering build reads the registered TEST_ONLY fixture at
`~/.config/ghar-sajag/gs117-tc001/fixture.json`, verifies its Home/Hub/C3
identity and pinned C3 image SHA-256, and resolves exactly one matching
`c3-current-app.bin` under the fixture's existing
`~/.local/state/ghar-sajag/gs117-tc001/provenance-refresh-*/trusted-artifacts/`
records. The image is copied byte-for-byte into that run's isolated `assets`
directory under the linker-required name `node_firmware.bin`; the C3 image is
not rebuilt or modified. The existing public config-root DER is resolved from
`~/.config/ghar-sajag/gs117-tc001/config-root-public.der` and checked as a DER
public key. Explicit input overrides are accepted only when their content
matches the registered fixture input.

Release requires an explicitly selected existing C3 production-pair asset in
an `assets/` directory and its sibling `report.json`; the report must bind the
asset hash and show TEST_ONLY/HIL pathways disabled. There is no fallback to
the Engineering fixture asset. Missing or ambiguous inputs fail before CMake.

Each call creates a fresh, profile-specific SDK config and build directory
outside the source tree. `GS_S3_OUTBOX_BUILD_ROOT` may select a parent directory;
the script creates a unique child for the chosen profile and preserves earlier
builds. This prevents an old Release/Engineering `sdkconfig` from contaminating
the next invocation. Only `engineering` and `release` are accepted; selecting
`gs_journal` as a profile is rejected.

Before success, the script decodes the generated partition-table binary using
the installed ESP-IDF parser and requires the generated table and source CSV to
match these exact entries: `ota_0` 0x20000/4 MiB, `ota_1` 0x420000/4 MiB,
`gs_outbox` 0x820000/4 MiB LittleFS and `gs_state` 0xC20000/256 KiB NVS,
including the NVS/OTA-data/PHY entries. It also verifies ESP32-S3 target and
image header, the 4 MiB application-slot fit, C3 image target, and profile
flags. Engineering must have GS40 TEST_ONLY CloudSync, UART0, and its existing
software-key/stack configuration enabled. Release must have TEST_ONLY and HIL
features disabled. The command only builds; it never flashes, resets, formats
or accesses a board. Do not add generated assets or binaries to Git.

For the isolated diagnostic only, activate
`/home/udaybhan/.espressif/v6.0.3/esp-idf/export.sh` and use a separate build
directory. Raw `idf.py` product builds are not the deployable S3 R1 entry point:
they do not resolve the registered fixture pair or run the outbox contract
verifier.

```sh
idf.py -C firmware/hub/target/esp32s3/idf -B /tmp/gs-s3-diagnostic-build \
  -D SDKCONFIG=/tmp/gs-s3-diagnostic-sdkconfig -D IDF_TARGET=esp32s3 \
  -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.diagnostic.defaults' \
  -D GS_S3_DIAGNOSTIC_ONLY=ON build size
```

For a separate explicitly selected physical commissioning fixture image, the
full product composition may combine `GS40_TEST_ONLY_CLOUDSYNC=ON` with
`GS_HIL_COMMISSIONING=ON`. Both options remain default-OFF in the raw CMake
configuration. Supply the isolated
TEST_ONLY config-root public DER outside the repository and the exact paired
C3 app asset; this composes the existing fixture commissioning adapter with
the existing CloudSync runtime. It does not create credentials, enroll devices,
or make the image deployable by itself. `GS_HIL_BUILD`, `GS_HIL_CONTROL`,
`GS_HIL_C8_ACK_DROP`, `GS_HIL_C8_ACK_HOLD`, and `GS_HIL_SIGNED_FOTA` remain
rejected in this CloudSync profile. This is a distinct GS-114 fixture profile;
the canonical GS-117 Engineering build enables GS40 TEST_ONLY CloudSync but
keeps `GS_HIL_COMMISSIONING=OFF`. Build and deployment are separate actions.

The GS-117 default Engineering invocation selects
`sdkconfig.gs40_test_only.defaults` followed by
`sdkconfig.gs40_test_only_uart.defaults`, because its identified board console
is the CH343 UART0 bridge. The raw GS40 SDK defaults remain opt-in for other
build paths; this wrapper's no-argument profile is explicitly Engineering.

The diagnostic verifies PSRAM startup/scratch, heap, Wi-Fi STA and ESP-NOW init
with no association, peers, application transmissions, ownership enrollment or
event ACKs. It does not initialize/erase application NVS, change sensor Nodes,
exercise secure commissioning, durable storage, FOTA or routine alerts. It uses
the same Octal 40 MHz PSRAM, conservative DIO 40 MHz flash, and `-Os` candidate.
PSRAM is available through explicit capability allocations; standard malloc,
stacks, BSS and recovery paths are not silently moved into external memory.

Before flashing, verify a private full-flash backup against the device; record
original layout and recovery steps. Keep backups outside Git. Flash only the
explicit bootloader/table/OTA-metadata/diagnostic image ranges required by the
validated development layout. Never erase the whole device. Preserve matching
unstripped ELF/map files for crash analysis. Development builds are unsigned;
signed FOTA, application rollback and cross-version storage remain mandatory
separate qualification gates. No security eFuse changes are part of bring-up.

Next milestones: product integration, secure C3 ESP-NOW interchange, sustainable
NVS lifecycle/retention, signed dual-OTA rollback, routines/alerts, peak memory
and endurance, BAT-C8 and full R1 qualification. Do not execute them automatically.

## GS-114 RPF fixture diagnostic build — build only

From the repository root, run:

~~~sh
make gs114-s3-rpf-diagnostic-build
~~~

This uses the existing paired fixture builder in a fresh unique output
directory. It rebuilds the C3 app as the embedded Node firmware asset, then
builds the S3 product composition with GS_HIL_BUILD=OFF,
GS_HIL_CONTROL=OFF, GS_HIL_COMMISSIONING=ON, and
GS_S3_DIAGNOSTIC_ONLY=OFF. The S3 uses sdkconfig.defaults plus
sdkconfig.defaults.outbox, selecting the 16 MiB / Octal 40 MHz profile and
the candidate ota_0/ota_1, gs_outbox, and gs_state table. The builder
checks the generated CMake options, sdkconfig, source and compiled partition
table, OTA-slot fit, RPF00–RPF08 strings, commissioning command strings, and
absence of broad HIL markers. It writes a JSON report beside the build.

The standalone app is s3/gs_r1_s3_hub.bin; its hash, size, version metadata,
source fingerprint, flags, table digest and image information are in
fixture_pair_report.json. ESP-IDF also generates a complete-device
flasher_args.json as a build byproduct. That bundle is
NOT_AUTHORIZED_FOR_DEPLOYMENT; this command invokes only build size, never
flash, app-flash, erase, reset, OTA or provisioning.
The paired C3 output exists only to reproduce the S3 embedded-node-asset input;
it is not a C3 deployment recommendation or a separately authorized deliverable.

The profile guard treats the S3's embedded C3 image separately from S3 runtime
bytes. The paired C3 image may contain the HIL UART token `INJECT_MOTION`, but
the checker requires its physical-wake-disabled diagnostic and rejects the
synthetic-motion success path; the same token in S3 runtime bytes fails the
build. The candidate partition file is not proof of the connected fixture's current
partition table. A standalone application image and a successful target build
do not establish safe installation, persistent-state preservation or rollback.
The current S3 application has no implemented S3 OTA receiver; ESP-IDF's
app-flash target is a separate host command which writes the configured
default app partition and resets the target. Do not run it under this
build-only task. Physical deployment needs separate authorization and verified
device/slot/storage provenance.
