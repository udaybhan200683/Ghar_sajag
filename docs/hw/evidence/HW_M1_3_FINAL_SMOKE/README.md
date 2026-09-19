# HW-M1.3 Final Clean-Production Smoke Evidence

## Status

**STATUS: PASS — HW-M1.3 QUALIFIED / PASS**

This record captures the final clean-production restore and matched normal PIR
smoke performed on 2026-09-19. It is distinct from the temporary negative-HIL
evidence in `docs/hw/evidence/HW_M1_3_HIL/README.md`.

## Run metadata and provenance

- Date: `2026-09-19`
- Branch: `feature/hw-m1-runtime-integration`
- Firmware/artifact provenance Git version: `1dfa9c3`
- `1dfa9c3` is documentation-only relative to the production runtime/release-gate lineage. No temporary negative-HIL source exists on the production branch.
- Hub: ESP32 DevKit / ESP-WROOM-32, MAC `5C:01:3B:BE:B9:F8`
- C3: ESP32-C3, MAC `14:63:93:C5:D1:58`
- Windows ports during final activity: Hub `COM3`; C3 `COM4`
- Windows Python: `3.12.10`
- esptool: `5.4.0`

The COM assignments are historical/session-specific. Future sessions must
re-detect ports after reconnecting.

## Exact qualified production artifacts

| Artifact | Size | SHA-256 |
|---|---:|---|
| Standalone C3 `firmware/node/target/esp32c3/idf/build/gs_hw_m1_node.bin` | 824,368 bytes | `f2c81ad8794fe766664ce253f588124665bb7c3e91da3b2b2ab4dc3b5c9104b2` |
| Hub embedded C3 `firmware/hub/target/esp32/idf/main/node_firmware.bin` | 824,368 bytes | `f2c81ad8794fe766664ce253f588124665bb7c3e91da3b2b2ab4dc3b5c9104b2` |
| Production Hub `firmware/hub/target/esp32/idf/build/gs_hw_m1_hub.bin` | 1,592,848 bytes | `f48a455658cf59d4f3e6a857bac36360ca045da2fd890d9b23ce7438e779a7f1` |

The Hub embedded C3 image exactly matches the standalone C3 image. The C3
image and Hub embedded image contain version `1dfa9c3`; the Hub production
image also contains the embedded C3 version string `1dfa9c3`.

Production-source and binary checks found `GS_HW_M1_3_NEGATIVE_HIL` absent and
found no negative-HIL runtime strings in the standalone C3, Hub embedded C3,
or Hub production binary.

## Flash and transport observations

Native Windows flashing passed for both targets. The exact flash arguments for
the C3 were `--flash-mode dio --flash-freq 80m --flash-size 4MB`, with the
bootloader at `0x0`, partition table at `0x8000`, `ota_data_initial` at
`0xf000`, and the application at `0x20000`. Hash verification passed for all
written images, and hard reset completed. No erase-flash was used.

Initial Hub flashing through WSL plus USB-IP was unstable during long writes:
115200 baud dropped around 18% of the application write, 57600 baud failed to
start the stub flasher, and `esptool --no-stub` dropped around 35.8%;
`dmesg` included `vhci_hcd` / USB-IP `urb->status -104` errors. Short flash-id
operations passed repeatedly. This was a workstation transport/tooling
observation, not a product defect. For future physical flashing, use native
Windows serial/esptool when USB-IP is unstable for sustained writes; native
Windows is not asserted to be universally required.

## Boot verification

The Hub clean-production boot was physically captured:

- Project: `gs_hw_m1_hub`
- App version: `1dfa9c3`
- ESP-IDF: `v6.0.3`
- Chip: ESP32-D0WD-V3 rev 3.1
- Flash: 4 MB; partition boot `ota_0` at `0x20000`
- MAC: `5c:01:3b:be:b9:f8`
- `ESPNOW initialized`
- `HubRuntime owner started channel=1`
- FOTA prompt: `Hold BOOT for 2000 ms to start C3 FOTA`
- Embedded C3 image: `824368 bytes`
- `main_task returned normally` was observed and is normal for this composition, not a failure.
- No negative-HIL fault-injection logs were observed.

The C3 clean startup banner showing `App version: 1dfa9c3` was not retained:
its native USB Serial/JTAG connection can reset or re-enumerate when the
monitor/reset is used. This is not a fabricated observation. The C3 provenance
chain is: SHA-256 verified image, embedded version `1dfa9c3`, complete native
Windows write, esptool `Hash of data verified`, then valid normal PIR events,
Durable ACKs, and retirement. Native USB monitor/reset can emit
`USB_UART_CHIP_RESET` and increment the NVS boot/session identity; that is
known behavior and not itself a firmware failure.

## Final matched physical smoke

The decisive matched event was:

```text
C3:
I (...) gs_node_runtime: PIR -> NodeRuntime session=17 seq=3
I (...) gs_node_runtime: NodeMessage sent session=17 seq=3 bytes=63
I (...) gs_node_runtime: Application ACK session=17 seq=3 class=0 retired=1
I (...) gs_node_runtime: MAC result session=17 seq=3 accepted=1

Hub:
I (...) gs_hub_runtime:
Processed session=17 seq=3 app_ack=0 ack_send=ESP_OK RSSI=-69 CH=1
```

This proves the final clean-production path:

`AM312 PIR -> NodeRuntime -> NodeMessage -> ESP-NOW -> HubRuntime processing -> Durable application ACK -> node retirement -> MAC acceptance`

Observed result: EventKey `session=17`, `seq=3`; Durable ACK `class=0`;
`retired=1`; MAC `accepted=1`; Hub `ack_send=ESP_OK`; RSSI `-69` dBm;
channel `1`. Several other normal events were also observed, including
sessions 15 and 16.

## Decision

- Native Windows clean-production Hub flash: **PASS**
- Native Windows clean-production C3 flash: **PASS**
- Clean-production Hub boot/version verification: **PASS**
- Clean-production C3 normal runtime exercise: **PASS**
- Final matched normal PIR smoke: **PASS**
- Qualification decision: **HW-M1.3 QUALIFIED / PASS**

Related evidence: `docs/hw/evidence/HW_M1_3_HIL/README.md`,
`docs/hw/HW_M1_3_HIL_VALIDATION.md`,
`docs/hw/HW_M1_3_HIL_TEST_MATRIX.json`, and
`docs/hw/evidence/HW_M1_FOTA/README.md`.
