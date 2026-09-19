# HW-M1.3 Negative-HIL Physical Evidence

## Status

**NEGATIVE HIL: PASS**

HW-M1.3 implementation, host validation, target-build validation, automated
release gate, positive HIL, FOTA HIL, and negative HIL are complete. Final
clean-production restore/smoke verification remains **PENDING**; therefore
HW-M1.3 final QUALIFIED status remains **PENDING**.

This is a temporary fault-injection qualification snapshot. The harness is
not production runtime and must not be merged or cherry-picked into
`feature/hw-m1-runtime-integration`.

## Run metadata

- Date: `2026-09-19`
- Production baseline: `efbeaf9` (`Add HW firmware regression release gate`)
- Temporary branch: `test/hw-m1-3-negative-hil`
- HIL harness commit: `d8fafd701c5215dbfbde2b144d7729b8c5393712`
- Physical artifacts were built before that commit and report app version
  `efbeaf9-dirty`; the hashes below are authoritative for the physical run.
- No rebuild was performed after the harness commit.

## Hardware and exact artifacts

| Target | Board / identity | Channel | Other configuration |
|---|---|---:|---|
| Hub | ESP32 DevKit / ESP-WROOM-32, MAC `5C:01:3B:BE:B9:F8` | 1 | — |
| Node | ESP32-C3, MAC `14:63:93:C5:D1:58` | 1 | TX power `qdbm=40`, PIR GPIO4 |

| Artifact | Size | SHA-256 |
|---|---:|---|
| Directly flashed C3 HIL binary | 825936 bytes | `b73b98a8a4c26ccd971c70daaa624348433fa46e07b369331b4b775c2ca3963a` |
| Hub embedded `node_firmware.bin` | 825936 bytes | `b73b98a8a4c26ccd971c70daaa624348433fa46e07b369331b4b775c2ca3963a` |
| Hub HIL binary | 1596624 bytes | `ab732eabc7d817e85c538ba85ca38ebb01628b68e69570385e2bf482b75a5114` |

The embedded C3 image exactly matched the directly flashed C3 image.

## Physically proven negative-HIL cases

### HIL-RETRY-001 through HIL-RETRY-004 — PASS

For session 8, sequence 1, the Hub deliberately dropped the application ACK:

```text
HIL PROCESS session=8 seq=1 state_changed=1 app_ack=0
HIL DROP_ACK session=8 seq=1
HIL PROCESS session=8 seq=1 state_changed=0 app_ack=0
HIL DROP_ACK_RETRY session=8 seq=1
HIL RETRY_ACK_ACTION_COMMITTED session=8 seq=1
Processed session=8 seq=1 app_ack=0 ack_send=ESP_OK
```

The same EventKey was retried, proving ACK-loss retention, retry, and identity
preservation. The duplicate showed `state_changed=0`; this records current
duplicate behavior and does not claim reducer idempotence beyond the existing
documented G02 semantics.

### HIL-RETRY-005 — PASS

For session 8, sequence 2, the Hub injected an ACK for sequence 3. The
original EventKey was not retired by the wrong ACK; its retry then committed
the retry ACK action.

```text
HIL WRONG_ACK original_session=8 original_seq=2 ack_session=8 ack_seq=3
HIL FIRST_ACK_ACTION_COMMITTED session=8 seq=2
HIL WRONG_ACK_RETRY session=8 seq=2
HIL RETRY_ACK_ACTION_COMMITTED session=8 seq=2
```

### HIL-RETRY-006 — PASS

For session 9, sequence 1, `ReceivedVolatile` was delivered first:

```text
HIL VOLATILE_ACK session=9 seq=1
Application ACK session=9 seq=1 class=1 retired=0
MAC result session=9 seq=1 accepted=1
```

The same EventKey was retried and only the subsequent Durable ACK retired it:

```text
Application ACK session=9 seq=1 class=0 retired=1
HIL DURABLE_RETIREMENT count=1 session=9 seq=1
```

### HIL-SESSION-001 — PASS / behavior recorded

The physical dropped-ACK retry produced the same EventKey and
`state_changed=0` on duplicate processing. This is the observed current
duplicate behavior; no stronger reducer-idempotence claim is made.

### HIL-SESSION-002 and HIL-SESSION-003 — PASS

Native USB monitor reconnects caused C3 resets and new NVS boot/session
identities. Sessions progressed through values including 6, 8, and 9. The Hub
explicitly accepted the newer session:

```text
Authorized boot session=9
```

The reset behavior was `USB_UART_CHIP_RESET`, expected from monitor attachment,
not a firmware crash.

### HIL-SESSION-004 — PASS

After three Durable retirements in current session 9, the one-shot HIL stale
frame was sent:

```text
HIL DURABLE_RETIREMENT count=3 session=9 seq=3
HIL STALE_TX current_session=9 stale_session=8 seq=3 send=ESP_OK
HIL STALE_TX_MAC_RESULT accepted=1 complete=1
Rejected stale session=8 active=9
```

The injected stale frame was HIL-only and did not enter NodeRuntime storage or
retry state.

### HIL-RSSI-001 and HIL-RSSI-002 — PASS

Transport diagnostics included channel and physical RSSI, while semantic RSSI
remained independent:

```text
HIL RSSI semantic_rssi=0 transport_rssi=-65 channel=1
HIL RSSI semantic_rssi=0 transport_rssi=-61 channel=1
HIL RSSI semantic_rssi=0 transport_rssi=-52 channel=1
HIL RSSI semantic_rssi=0 transport_rssi=-45 channel=1
HIL RSSI semantic_rssi=0 transport_rssi=-47 channel=1
```

## Prior positive and FOTA evidence

Prior clean production and FOTA physical evidence remains immutable and was not
overwritten. The clean production `efbeaf9` artifacts were C3
`2d29a808569c2ba4d2ee218f42f6f5dc28c38c7a5834fb0a92fa87b8720fc77a` and Hub
`bf4ed7972bdee16ea785e1040ed396e594c5f85dcd490b5fa05f79f1137d5cf2`; the clean
FOTA CRC was `0x8734269A`. See
`docs/hw/evidence/HW_M1_3_HOST/README.md`,
`docs/hw/evidence/HW_M1_3_TARGET_BUILD/README.md`, and the prior immutable
FOTA evidence for the positive/FOTA record.

## Qualification boundary

- Implementation: PASS
- Host validation: PASS
- Target build validation: PASS
- Automated release gate: PASS
- Positive HIL: PASS
- FOTA HIL: PASS
- Negative HIL: PASS
- Final clean-production restore/smoke verification: **PENDING**
- Final HW-M1.3 QUALIFIED status: **PENDING** that restore/smoke check

HW-M1.4 power/performance remains separate and is not an HW-M1.3 functional
blocker.
