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
the separate bounded queue returned by `control_plane_queue()`. A complete
ESP-IDF product composition must connect that queue to the already qualified
FOTA maintenance implementation. FOTA is never decoded as `NodeMessage` and
never enters `NodeRuntime`.

This repository does not yet contain a unified ESP-IDF product project, so
these target-only files are intentionally excluded from the host Makefile.
Hardware build/composition and validation remain pending.
