# ESP32-C3 HW-M1.3 target adapter

This directory contains the isolated ESP-IDF binding for normal data-plane
traffic. `start_runtime_adapter()` creates the bounded callback queues and the
single owner task for `NodeRuntime`; callbacks never invoke portable business
logic.

The adapter preserves the qualified C3 configuration: AM312 GPIO4, active-low
LED GPIO8, ESP-NOW channel 1, TX power API value 40 (10 dBm), qualified node
and Hub MAC addresses. It fails closed if the NVS boot-session counter cannot
be durably incremented, so a reboot does not knowingly reuse
`(node_id, session_id, sequence)` identity.

FOTA frames are classified by their existing control-plane magic and copied to
the separate bounded queue returned by `control_plane_queue()`. The product
composition under `idf/` connects that queue to the wire-compatible FOTA
receiver. Normal sensing/transmission pauses during active maintenance; FOTA
is never decoded as `NodeMessage` and never enters `NodeRuntime`.

Build with ESP-IDF v6.0.3:

```sh
source ~/.espressif/tools/activate_idf_v6.0.3.sh
cd idf
idf.py set-target esp32c3
idf.py build
```

The custom `partitions.csv` provides two 0x1E0000 OTA slots and
`sdkconfig.defaults` enables 4 MB flash and rollback. The target-only files
remain excluded from the host Makefile. Target build is validated; flashing
and physical validation remain pending.
