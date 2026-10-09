# Isolated R1 ESP32-S3 N16R8 target

Authority: GS-D030. ESP-IDF v6.0.3. The default target profile still uses the
historical 2 MiB `gs_journal` map. `build-outbox.sh` selects the separate
4 MiB `gs_outbox` plus 256 KiB `gs_state` candidate map and two 4 MiB OTA slots.
Both are development layouts, not approved commercial capacity guarantees.
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

Activate `/home/udaybhan/.espressif/v6.0.3/esp-idf/export.sh` first.
For the product composition, preserve the exact existing ignored C3 asset at
`../../esp32/idf/main/node_firmware.bin` (931408 bytes at the source checkpoint).
Copy the source-worktree asset without rebuilding or modifying C3 firmware,
then compare SHA-256. Do not add generated assets/binaries to Git.

```sh
idf.py -C firmware/hub/target/esp32s3/idf -B /tmp/gs-s3-product-build \
  -D SDKCONFIG=/tmp/gs-s3-product-sdkconfig -D IDF_TARGET=esp32s3 build size
idf.py -C firmware/hub/target/esp32s3/idf -B /tmp/gs-s3-diagnostic-build \
  -D SDKCONFIG=/tmp/gs-s3-diagnostic-sdkconfig -D IDF_TARGET=esp32s3 \
  -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.diagnostic.defaults' \
  -D GS_S3_DIAGNOSTIC_ONLY=ON build size
```

From this directory, `./build-outbox.sh` builds the full Hub against the
explicit `gs_outbox` / `gs_state` candidate profile in an isolated build tree
under `/home/udaybhan/projects/.ghar_sajag_s3_outbox_lifecycle_build`. It does
not flash or format a device. The selected profile is source-controlled in
`sdkconfig.defaults.outbox`; the generated sdkconfig and build files stay
outside the repository.

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
