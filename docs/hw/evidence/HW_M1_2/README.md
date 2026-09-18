# HW-M1.2 ESP-NOW Qualification Evidence

## Status

HW-M1.0: PASS
HW-M1.1: PASS
HW-M1.2 functional path: PASS

FOTA/OTA work has not started at this checkpoint.

---

## Hardware

### Hub

- Device: ESP32 DevKit / ESP-WROOM-32
- Chip: ESP32-D0WD-V3 rev 3.1
- Hub STA MAC: 5C:01:3B:BE:B9:F8
- Interface during bring-up: CP2102 USB-UART
- ESP-NOW channel at this checkpoint: 1

### Node

- Device: ESP32-C3
- Node MAC: 14:63:93:C5:D1:58
- PIR: SmartElex AM312
- PIR input GPIO: GPIO4
- Onboard status LED: GPIO8, active low
- ESP-NOW channel at this checkpoint: 1
- Runtime Wi-Fi TX power API value: 40
- Effective configured TX power: 10 dBm

---

## HW-M1.0 - Toolchain and Board Bring-up

Qualified with ESP-IDF v6.0.3.

Verified:

- ESP32 Hub build
- ESP32 Hub flash
- ESP32 Hub serial monitor
- ESP32-C3 build
- ESP32-C3 flash
- ESP32-C3 serial monitor

Both physical boards have 4 MB flash.

The current bring-up builds were still using a 2 MB configured image layout.
OTA/4 MB production partitioning is deferred to subsequent work.

---

## HW-M1.1 - Real PIR Sensing

Verified on the ESP32-C3 using the AM312 PIR.

Signal path:

AM312 PIR
    ->
GPIO4
    ->
motion qualification
    ->
MOTION DETECTED
    ->
status LED indication

Observed PIR detection distance during standalone testing was approximately
12 ft / 3.7 m under the test conditions.

Battery-powered node operation was also verified.

---

## HW-M1.2 - Real ESP-NOW Link

Verified end-to-end path:

AM312 PIR
    ->
ESP32-C3
    ->
ESP-NOW
    ->
ESP32 Hub

Node event format:

NODE=1,SEQ=<n>,EVENT=MOTION

The Hub successfully received real PIR-generated motion events.

The C3 ESP-NOW send callback reported successful delivery during the
qualification run.

Observed received sequence numbers were continuous during the recorded test
run, with no sequence gaps observed.

---

## RF Findings

Initial testing was performed on ESP-NOW channel 6.

The ESP32-C3 board showed substantially more stable RF behavior when its
configured maximum TX power was reduced from the higher/default setting to
10 dBm.

The current qualified C3 runtime setting is:

    esp_wifi_set_max_tx_power(40)

The ESP-IDF API uses quarter-dBm units for this parameter, therefore:

    40 / 4 = 10 dBm

Channel was subsequently changed from 6 to 1 on both Hub and C3 to evaluate
whether local Wi-Fi-channel congestion was responsible for the limited
room-to-room range.

Result:

- Channel 1 communication works.
- No meaningful range improvement was observed compared with channel 6.
- Therefore channel congestion does not currently appear to be the dominant
  cause of the observed range limitation.

Further RF qualification should use measured RSSI rather than only
received/not-received observations.

---

## Hub RSSI Logging

The Hub receive path was updated to capture ESP-NOW receive metadata,
including:

- source MAC
- RSSI
- Wi-Fi channel
- payload length
- payload
- Hub RX counter

Representative log format:

RX#<n> | SRC=14:63:93:C5:D1:58 | RSSI=<value> dBm | CH=1 |
len=<n> | DATA=NODE=1,SEQ=<n>,EVENT=MOTION

The Hub application now logs each received event as one complete ESP-IDF
log message.

The serial garbage previously observed in some output lines was no longer
observed after this logging change.

---

## Time Handling

ESP-IDF log timestamps currently represent uptime, not trustworthy
wall-clock time.

Product requirement:

- Hub shall assign an absolute timestamp to every received event.
- Internally the product should retain UTC/epoch time.
- User-facing display may use DD:MM:YYYY:HH:MM:SS.
- Hub should obtain authoritative time through SNTP/NTP when Wi-Fi/backend
  integration is implemented.
- The system must distinguish synchronized time from unsynchronized time and
  must not fabricate a valid-looking wall-clock timestamp before time sync.

Absolute timestamping is therefore intentionally deferred from HW-M1.2 to
Hub Wi-Fi/runtime integration.

---

## Remaining Work

Next development areas include:

1. Additional RSSI/range characterization.
2. HW-M1.3 Hub target runtime integration.
3. Production message structure, ACK, retry and deduplication.
4. Hub event journal integration.
5. Hub Wi-Fi/backend integration.
6. SNTP/NTP wall-clock synchronization.
7. OTA/FOTA architecture and implementation.
8. 4 MB dual-slot OTA partition layout.
9. Hub self-update.
10. C3 firmware update through the Hub.

No FOTA changes are included in this checkpoint.
