# ESP32 Hub HW-M1.3 target adapter

This directory contains the isolated ESP-IDF binding for normal data-plane
traffic. The Wi-Fi/ESP-NOW callback performs source-MAC and size checks,
captures RSSI/channel diagnostics, copies bytes into a static bounded queue,
and returns. Only `gs_hub_owner` decodes frames or calls `HubRuntime`.

The owner maps the qualified node MAC and `node-1` identity, accepts a new
monotonically increasing NVS boot session, rejects stale sessions, calls
`radio_message_callback()` and `run_state_once()`, and sends the resulting
typed application ACK. ESP-NOW MAC receipt is never treated as a durable ACK.
Transport RSSI is logged separately and does not overwrite semantic message
RSSI.

FOTA frames are classified by their existing control-plane magic and copied to
the separate bounded queue returned by `control_plane_queue()`. They never
enter `HubRuntime`, the journal, or rules. The product composition under
`idf/` connects this queue to the wire-compatible FOTA sender, pauses normal
data-plane processing during maintenance, and retains the temporary BOOT
button long-press trigger used for engineering qualification.

No trustworthy wall-clock source is composed yet. The adapter uses epoch zero
for the explicitly untrusted Hub receive/ACK time rather than inventing a wall
clock; SNTP integration remains later scope.

Build the C3 image first, copy its application binary to the ignored embed
input, then build with ESP-IDF v6.0.3:

```sh
cp ../../../node/target/esp32c3/idf/build/gs_hw_m1_node.bin \
  idf/main/node_firmware.bin
source ~/.espressif/tools/activate_idf_v6.0.3.sh
cd idf
idf.py set-target esp32
idf.py build
```

The custom `partitions.csv` provides two 0x1E0000 OTA slots and
`sdkconfig.defaults` enables 4 MB flash and rollback. The target-only files
remain excluded from the host Makefile. Target build is validated; flashing
and physical validation remain pending.
