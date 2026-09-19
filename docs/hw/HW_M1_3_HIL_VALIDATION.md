# HW-M1.3C Hardware-in-Loop Validation

Status: **MANUAL_REQUIRED / HARDWARE VALIDATION PENDING**

This is the physical acceptance checklist for the build-validated HW-M1.3
compositions. It is intentionally not part of the automated software/target
gate and no item is currently PASS. The machine-readable source is
`docs/hw/HW_M1_3_HIL_TEST_MATRIX.json`; record serial logs, photos/configuration
observations, and evidence paths there when each item is executed.

## Preconditions and boundary

- Use the ESP32-C3 and Hub images produced by `make hw-release-gate`.
- Do not change the qualified C3 channel 1, TX API value 40 / 10 dBm, GPIO4
  PIR, GPIO8 active-low LED, or qualified MAC assumptions.
- Confirm USB bootstrap starts the C3 from `ota_0`; do not infer FOTA or HIL
  results from an image build.
- FOTA is CONTROL PLANE traffic. NodeMessage/NodeAckMessage is DATA PLANE
  traffic. Record them separately.
- `MANUAL_REQUIRED` means the step needs target hardware and evidence.

## Boot and configuration

| ID | Acceptance observation | Status |
|---|---|---|
| HIL-BOOT-001 | C3 production firmware boots. | MANUAL_REQUIRED |
| HIL-BOOT-002 | Hub production firmware boots. | MANUAL_REQUIRED |
| HIL-BOOT-003 | C3 MAC is `14:63:93:C5:D1:58`. | MANUAL_REQUIRED |
| HIL-BOOT-004 | Hub MAC is `5C:01:3B:BE:B9:F8`. | MANUAL_REQUIRED |
| HIL-BOOT-005 | Channel 1 is preserved on both targets. | MANUAL_REQUIRED |
| HIL-BOOT-006 | C3 TX API value 40 / 10 dBm is preserved. | MANUAL_REQUIRED |
| HIL-BOOT-007 | AM312 input is physically operating on GPIO4. | MANUAL_REQUIRED |
| HIL-BOOT-008 | GPIO8 LED is active-low and behaves correctly. | MANUAL_REQUIRED |
| HIL-BOOT-009 | Running OTA partition, pending validation, and VALID state are observable. | MANUAL_REQUIRED |

## Normal business path

| ID | Acceptance observation | Status |
|---|---|---|
| HIL-DATA-001 | PIR stabilization completes without a fabricated boot event. | MANUAL_REQUIRED |
| HIL-DATA-002 | Physical motion reaches existing sensing semantics. | MANUAL_REQUIRED |
| HIL-DATA-003 | `NodeRuntime::record()` creates the event. | MANUAL_REQUIRED |
| HIL-DATA-004 | EventKey contains valid source/session/sequence. | MANUAL_REQUIRED |
| HIL-DATA-005 | Bounded binary NodeMessage encoding succeeds. | MANUAL_REQUIRED |
| HIL-DATA-006 | NodeMessage transmits over ESP-NOW. | MANUAL_REQUIRED |
| HIL-DATA-007 | MAC result enters `transport_result()` separately from application ACK. | MANUAL_REQUIRED |
| HIL-DATA-008 | Hub callback only bounds/copies/queues the frame. | MANUAL_REQUIRED |
| HIL-DATA-009 | Hub owner task decodes the queued frame. | MANUAL_REQUIRED |
| HIL-DATA-010 | HubRuntime authorizes the current node/session. | MANUAL_REQUIRED |
| HIL-DATA-011 | Event reaches journal/runtime processing. | MANUAL_REQUIRED |
| HIL-DATA-012 | ProcessResult produces a Durable application ACK where applicable. | MANUAL_REQUIRED |
| HIL-DATA-013 | NodeAckMessage returns and decodes on the C3. | MANUAL_REQUIRED |
| HIL-DATA-014 | Only the matching Durable ACK retires the retained event. | MANUAL_REQUIRED |

## Retry and reliability

| ID | Acceptance observation | Status |
|---|---|---|
| HIL-RETRY-001 | Deliberately drop an application ACK where practical. | MANUAL_REQUIRED |
| HIL-RETRY-002 | Event remains retained after ACK loss. | MANUAL_REQUIRED |
| HIL-RETRY-003 | Retry occurs at the runtime retry deadline. | MANUAL_REQUIRED |
| HIL-RETRY-004 | Retry uses identical source/session/sequence identity. | MANUAL_REQUIRED |
| HIL-RETRY-005 | Wrong EventKey ACK does not retire another event. | MANUAL_REQUIRED |
| HIL-RETRY-006 | `ReceivedVolatile` does not retire durable evidence. | MANUAL_REQUIRED |

## Duplicate, session, and RSSI behavior

| ID | Acceptance observation | Status |
|---|---|---|
| HIL-SESSION-001 | Duplicate packet remains identity-safe under current behavior. | MANUAL_REQUIRED |
| HIL-SESSION-002 | C3 reboot produces a new NVS boot/session identity. | MANUAL_REQUIRED |
| HIL-SESSION-003 | New authorized session is admitted according to lifecycle policy. | MANUAL_REQUIRED |
| HIL-SESSION-004 | Stale prior session is rejected. | MANUAL_REQUIRED |
| HIL-RSSI-001 | Transport RSSI and channel diagnostics remain visible. | MANUAL_REQUIRED |
| HIL-RSSI-002 | Transport RSSI does not overwrite semantic RSSI. | MANUAL_REQUIRED |

## FOTA regression

| ID | Acceptance observation | Status |
|---|---|---|
| HIL-FOTA-001 | `ota_0 -> ota_1` transfer and reboot complete. | MANUAL_REQUIRED |
| HIL-FOTA-002 | New `ota_1` image is observed pending validation. | MANUAL_REQUIRED |
| HIL-FOTA-003 | `ota_1` image is marked VALID. | MANUAL_REQUIRED |
| HIL-FOTA-004 | PIR is restored after `ota_0 -> ota_1`. | MANUAL_REQUIRED |
| HIL-FOTA-005 | Business-message path is restored after `ota_0 -> ota_1`. | MANUAL_REQUIRED |
| HIL-FOTA-006 | `ota_1 -> ota_0` transfer and reboot complete. | MANUAL_REQUIRED |
| HIL-FOTA-007 | New `ota_0` image is observed pending validation. | MANUAL_REQUIRED |
| HIL-FOTA-008 | `ota_0` image is marked VALID. | MANUAL_REQUIRED |
| HIL-FOTA-009 | PIR is restored after `ota_1 -> ota_0`. | MANUAL_REQUIRED |
| HIL-FOTA-010 | Business-message path is restored after `ota_1 -> ota_0`. | MANUAL_REQUIRED |

## Post-FOTA data path

| ID | Acceptance observation | Status |
|---|---|---|
| HIL-POSTFOTA-001 | Durable ACK path still works after FOTA. | MANUAL_REQUIRED |
| HIL-POSTFOTA-002 | Retries still work and preserve EventKey after FOTA. | MANUAL_REQUIRED |
| HIL-POSTFOTA-003 | Session identity remains valid after FOTA. | MANUAL_REQUIRED |

## Evidence record

For each row, record date/time, image hashes, running partition, target serial
log path, physical setup, observed result, and reviewer. A failed or
inconclusive item remains open; do not convert it to PASS by documentation
review. Only after all required rows and FOTA regressions are physically
demonstrated may HW-M1.3 become HW VALIDATED / QUALIFIED.
