# GS-114 C3 diagnostic install and authenticated trace — 2026-10-14

## Checkpoint and fixture identity

- Canonical source: `c69960fb064a60c3e6dc52b27d90fbbbe30b560a`; branch `feature/r1-commercial-baseline`; local and `origin` HEAD matched at observation.
- Context preflight: PASS, `2026-10-13.001`.
- Operator's latest Windows USB/IP listing: C3 `BUSID 3-3`, `303a:1001`, COM4, Attached; S3 `BUSID 3-1`, `1a86:55d3`, COM9, Attached. No attach command was issued.
- WSL stable links: C3 `/dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_14:63:93:C5:D1:58-if00` -> `/dev/ttyACM1`; S3 `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5CBC401023-if00` -> `/dev/ttyACM0`.
- Sysfs reports C3 VID:PID `303a:1001`, USB serial `14:63:93:C5:D1:58`; S3 VID:PID `1a86:55d3`, USB serial `5CBC401023`.
- C3 install log identifies ESP32-C3 revision 0.4, 4 MiB flash, MAC `14:63:93:c5:d1:58`. The S3 is the previously verified ESP32-S3 N16R8 fixture, MAC `7c:4f:ad:b7:2a:20`, 16 MiB flash / 8 MiB PSRAM.
- USB-only supply and AM312 wiring (3.3 V, GND, GPIO4) remain the previously operator-confirmed arrangement; no changed setup was reported.
- Exclusive S3 capture is PID 324978. It owns ACM0 only. ACM1 was unowned during this checkpoint. No esptool, IDF build or other serial owner was active.

## C3 application install and running evidence

- Build manifest: `code/build/gs114_fixture_pair/build-8rqa0oi5/fixture_pair_report.json`; source `c69960fb064a60c3e6dc52b27d90fbbbe30b560a`, fingerprint `4e1b08ac9da29ab67f76b62e195abb5d8e2f209015fc2effa67a771f40b6fea7`, ESP-IDF 6.0.3.
- C3 image: `code/build/gs114_fixture_pair/build-8rqa0oi5/c3/gs_hw_m1_node.bin`, 940,752 bytes, SHA-256 `70c638b07b46981d6abba3031348449c5afcd2a25d3263cd1e3aa5dfb5d8d530`; `GS_HIL_BUILD=OFF`, `GS_HIL_CONTROL=ON`, `GS_BAT_C8_PHYSICAL_WAKE=ON`.
- At 06:13:26–06:13:32 UTC, after confirming the active C3 `ota_0` slot at `0x20000`, the app-only write completed at that offset. Esptool reported `Hash of data verified`, exit 0. No partition table, OTA metadata, NVS, commissioning, durable storage or security data was erased.
- A later read-only actual partition-table/otadata read recorded `ota_seq=1` selecting `ota_0`; the table matched the source build. The readback file is 4,096 bytes, while the generated table artifact is 3,072 bytes; the first 3,072 bytes match byte-for-byte, SHA-256 `1b86379629900670bd43147c3a873a424695a67765fd1bdb28b1bffc21be137a`. The differing whole-file hashes are only due to the longer flash read. The captured files and full command output are `c3_app_only_install.log`, `c3_partition_table_actual.bin`, `c3_otadata_actual.bin` and `c3_flash_selector_read.log` in this run directory.
- Subsequent authenticated NodeHealth and schema-3 trace received by the S3 prove that the installed C3 image booted and communicated. Session 15, health_seq 1 at `2026-10-14T06:37:24.484466352Z` reported reset=1, retained=0, durable_ack=1, one GPIO wake, and no pending event. The associated trace at `06:37:24.506002952Z` reported GPIO4 LOW, one observed HIGH episode totaling/maxing 6,793 ms, 339 GPIO-high sleep-inhibition samples, zero sleep entries with GPIO4 HIGH, GPIO wake, radio restore OK and owner resume.
- The trace and Hub compatibility are verified behaviorally. The exact active S3 binary hash was not read back during this checkpoint. The source-matched S3 build candidate is `code/build/gs114_fixture_pair/build-8rqa0oi5/s3/gs_r1_s3_hub.bin`, SHA-256 `ca178fe30cc620d3fe0cb5817da9d8a98b07b70cb5f7c443045c85180dd46379`; the S3 responded to `FIXTURE_STATUS` at `06:58:28.214244408Z` with commissioning state `idle`.

## Physical case disposition at this checkpoint

- **Reuse PASS:** RPF07, P1, P2, P4 controlled retest, P5 controlled outage/recovery retest, P6 and P7. Their original case reports remain authoritative; preserve P4 q10–q12 multiplicity and P5 retry-key observability limitations. The c699 observer is bounded qualification telemetry; it does not change EventKey, ACK, authentication, persistence or sleep policy, so these PASS results are not repeated.
- **C8-P3:** remains BLOCKED / no new controlled result. A controlled sustained-motion action was requested after the Hub responded to `FIXTURE_STATUS`, but no operator completion confirmation or new matching NodeHealth/event/trace line was received in the observation window. The prior S3 log records Node liveness offline at `06:52:38.225783443Z`, session 15. The requested window cannot be counted as a confirmed sensor stimulus or PASS. No reset, reflash or recommission was performed.
- **C8-P8:** physical NOT_RUN. The c699 S3 diagnostic profile has `GS_HIL_C8_ACK_DROP=OFF`. The available ACK-drop image in `code/build/gs114_c8_p8_20261014/` is from the earlier source/profile recorded in `C8_P8.md`, so it is not a source-matched installation candidate for this C3 image. A current-source S3 fixture build and verified app-only slot operation are required before a physical P8 run.
- **C8-P9 ACK:** BLOCKED pending a fixture that holds the application ACK outstanding for the required observation interval and supports proving no premature sleep. One-shot P8 suppression alone is not sufficient evidence.
- **C8-P9 signed FOTA:** BLOCKED; no matched signed C3 test/recovery image pair, verified signing provenance, supported authenticated trigger or proven recovery plan is available. No FOTA operation was attempted.
- **P10:** separate GS-149 measurement scope; no current or battery-life values were measured here.

The complete S3 capture and C3 installation outputs are retained locally in this run directory. The S3 log's unsolicited q1/q2 events during setup are not attributed to the controlled P3 window and are not used as a P3 result.
