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

The HW-M1.4 offline-resilience runtime implementation remains the parent
commit `cfcee972dab6045bbb8f7fbfeb51bf66097cfae9` (`cfcee97`).  Firmware built
for physical HIL must be produced from a later clean tooling commit with the
repository-owned pair builder.  Pre-commit or dirty-tree builds are useful for
development validation only and are not qualification artifacts.

Use the canonical pair build from the product root; it rebuilds both projects,
always replaces the ignored embed input, verifies versions/SHA/byte equality,
and writes a provenance manifest:

```sh
make hw-pair-build
```

The command fails closed unless tracked Git files are clean, each image app
version equals the current committed short SHA (with no `-dirty` suffix), the
standalone C3 image and `main/node_firmware.bin` are byte-for-byte/SHA equal,
and the Hub image and generated embedded object are rebuilt after
synchronization.  Never trust or manually copy an existing
`node_firmware.bin`.  The generated manifest is
`build/hw_pair/provenance.json` and accompanies HIL evidence; it is ignored
build output, not a source or runtime change.

The existing `make hw-release-gate` includes this strict pair-integrity stage
for full target gates.  `make hw-validation-fast` remains a developer/static
gate and does not build qualification images.

The custom `partitions.csv` provides two 0x1E0000 OTA slots and
`sdkconfig.defaults` enables 4 MB flash and rollback. The target-only files
remain excluded from the host Makefile. Target build is validated; flashing
and physical validation remain pending.
