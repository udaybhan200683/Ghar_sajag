# HW-M1 ESP-NOW FOTA Qualification

## Result

PASS

Dual-slot ESP-NOW firmware update of the ESP32-C3 node was successfully
demonstrated through the ESP32 Hub.

## Configuration

Hub:
- ESP32-D0WD-V3
- MAC: 5C:01:3B:BE:B9:F8
- ESP-NOW channel: 1
- 4 MB flash
- ota_0: 1920 KB
- ota_1: 1920 KB
- rollback enabled

Node:
- ESP32-C3
- MAC: 14:63:93:C5:D1:58
- ESP-NOW channel: 1
- TX power: 10 dBm
- PIR GPIO4
- LED GPIO8 active-low
- 4 MB flash
- ota_0: 1920 KB
- ota_1: 1920 KB
- rollback enabled

Node firmware image transferred:
- Size: 797600 bytes
- Transfer chunk: <=200 bytes
- Total chunks: 3988
- Image CRC32 observed during qualification: 0x378234F3

## Qualification

Initial USB bootstrap:
- Node booted from ota_0
- PIR operation verified

FOTA cycle 1:
- ota_0 -> ota_1
- Transfer reached 100%
- Hub reported FOTA RESULT: PASS
- Node rebooted from ota_1
- OTA image entered pending validation state
- Node marked image VALID
- PIR operation restored
- Hub received post-update motion events

FOTA cycle 2:
- ota_1 -> ota_0
- Transfer reached 100%
- Hub reported FOTA RESULT: PASS
- Node rebooted from ota_0
- OTA image entered pending validation state
- Node marked image VALID
- PIR operation restored
- Hub received post-update motion events

Dual-slot rotation is therefore qualified:

ota_0 -> ota_1 -> ota_0

## Transport Features Demonstrated

- ESP-NOW firmware transfer
- Application-level ACK
- Chunk sequencing
- Retry support
- Duplicate handling
- Per-chunk CRC32
- Whole-image CRC32
- Inactive OTA partition selection
- OTA boot partition switching
- Rollback-enabled bootloader
- Application validation after reboot
- Existing PIR functionality preserved after update

## Known Follow-up Work

1. Sequence number currently restarts after reboot.
   Production protocol needs boot/session identity or persisted sequence state.

2. Current OTA image validation uses a basic timed health window.
   Production validation should include communication and subsystem health checks.

3. CRC32 provides corruption detection only.
   Production firmware must add cryptographic authenticity/signature verification.

4. Current qualification Hub embeds the C3 firmware image.
   Production Hub should obtain/version firmware from the backend.

5. ESP-NOW peer encryption/key-management remains to be implemented.

6. RF range qualification remains separate from FOTA functional qualification.

7. Hub self-OTA over backend/Wi-Fi remains to be implemented.

## Status

HW-M1 ESP-NOW node FOTA: QUALIFIED

USB should no longer be required for normal C3 application firmware updates.
