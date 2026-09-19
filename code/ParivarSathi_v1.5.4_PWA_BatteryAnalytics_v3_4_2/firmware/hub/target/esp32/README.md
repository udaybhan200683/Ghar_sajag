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
enter `HubRuntime`, the journal, or rules. A complete ESP-IDF product
composition must connect this queue to the already qualified FOTA maintenance
implementation.

No trustworthy wall-clock source is composed yet. The adapter uses epoch zero
for the explicitly untrusted Hub receive/ACK time rather than inventing a wall
clock; SNTP integration remains later scope.

This repository does not yet contain a unified ESP-IDF product project, so
these target-only files are intentionally excluded from the host Makefile.
Hardware build/composition and validation remain pending.
