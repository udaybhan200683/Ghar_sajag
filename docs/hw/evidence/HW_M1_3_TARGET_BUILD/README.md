# HW-M1.3B Target Build Evidence

## Status

**TARGET BUILD VALIDATION ONLY — HARDWARE VALIDATION PENDING**

Branch: `feature/hw-m1-runtime-integration`

Starting checkpoint: `0546b28` (`Document HW-M1.3 checkpoint and resume
state`), with host-validated implementation parent `1d41864`.

No firmware was flashed and no physical behavior was tested. This evidence
does not make HW-M1.3 HW VALIDATED or QUALIFIED. The last physically qualified
checkpoint remains `50abdce`.

## Projects and environment

- ESP-IDF: v6.0.3, activated with
  `source ~/.espressif/tools/activate_idf_v6.0.3.sh`.
- C3 project: `firmware/node/target/esp32c3/idf/`, target `esp32c3`.
- Hub project: `firmware/hub/target/esp32/idf/`, target `esp32`.
- Both projects use C++17 and compile the portable runtime dependencies and
  HW-M1.3 adapters directly.

Build the C3 first. Copy
`firmware/node/target/esp32c3/idf/build/gs_hw_m1_node.bin` to the ignored Hub
embed input `firmware/hub/target/esp32/idf/main/node_firmware.bin`, then build
the Hub. The embedded image is an engineering FOTA qualification mechanism,
not a production firmware distribution design.

## Build results

| Target | Result | Application binary | Size | 0x1E0000 slot headroom |
|---|---|---|---:|---:|
| ESP32-C3 node | PASS | `gs_hw_m1_node.bin` | `0xC9430` = 824,368 bytes | `0x116BD0` = 1,141,712 bytes (58%) |
| ESP32 Hub | PASS | `gs_hw_m1_hub.bin` | `0x184E10` = 1,592,848 bytes | `0x5B1F0` = 373,232 bytes (19%) |

SHA-256 at validation time:

- C3: `1b267107c07cf2973f9d26311d25be68c9c41d58bd277ec1602d4c1d6168b77e`.
- Hub: `f3ad157cdd83504cfec2ed339ebfd7a36b9b79b4d8b8d5b710e3977669f7550e`.

Both generated configurations contain
`CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE=y`, 4 MB flash, and the custom partition
table. Both partition tables preserve:

```text
nvs      data nvs     0x9000    0x6000
otadata  data ota     0xF000    0x2000
phy_init data phy     0x11000   0x1000
ota_0    app  ota_0   0x20000   0x1E0000
ota_1    app  ota_1   0x200000  0x1E0000
```

## FOTA coexistence

The product compositions retain one ESP-NOW receive callback per target. That
callback performs bounded classification/copy and routes qualified FOTA magic
to the bounded control queue. Dedicated owner/worker tasks consume control
frames; normal data-plane work pauses during active maintenance. FOTA is never
decoded as `NodeMessage`, admitted to `HubRuntime`, journaled, or processed by
rules. The C3 retains inactive-partition selection, CRC checks, OTA boot switch,
rollback-enabled boot, and post-boot VALID marking. The Hub retains application
FOTA ACK/retry/duplicate behavior and the temporary BOOT long-press trigger.
Physical requalification remains mandatory.

## Host regression

Command:

`PATH=/usr/bin:/bin make cpp-test CXX=/usr/bin/g++`

Result: **PASS — 124 checks** under `-Wall -Wextra -Werror -pedantic`.

`git diff --check`: **PASS** before checkpoint commit.

The previously recorded complete `make release-gate-final` result remains
environment-blocked for localhost HTTP/PWA/browser stages; it is not a full
PASS and was not rerun for this target-only composition checkpoint.

## Next

HW-M1.3C physical qualification must flash both build-validated images and
prove the runtime data path, callback ownership, Durable application ACK and
retry/session behavior, RSSI diagnostics, both FOTA slot rotations, and
post-FOTA PIR/business operation. Record that work in a new physical evidence
snapshot; do not relabel this folder as physical evidence.
