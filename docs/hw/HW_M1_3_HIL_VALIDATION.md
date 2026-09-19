# HW-M1.3C Hardware-in-Loop Validation

Status: **QUALIFIED / PASS**

The machine-readable checklist is
`docs/hw/HW_M1_3_HIL_TEST_MATRIX.json`. Every row is now backed by captured
physical evidence; the automated `make hw-release-gate` remains a software/
target gate and does not perform physical HIL.

## Evidence mapping

| Area | Result | Evidence |
|---|---|---|
| Boot/configuration | PASS | `docs/hw/evidence/HW_M1_3_FINAL_SMOKE/README.md` boot, provenance, and final-smoke sections |
| Normal business path | PASS | Final matched `session=17 seq=3` record in `docs/hw/evidence/HW_M1_3_FINAL_SMOKE/README.md` |
| Retry/reliability | PASS | `docs/hw/evidence/HW_M1_3_HIL/README.md` HIL-RETRY-001 through HIL-RETRY-006 |
| Duplicate/session/RSSI | PASS | `docs/hw/evidence/HW_M1_3_HIL/README.md` HIL-SESSION and HIL-RSSI records; final smoke RSSI/channel |
| FOTA regression | PASS | `docs/hw/evidence/HW_M1_FOTA/README.md` two qualified slot rotations |
| Post-FOTA data path | PASS | Existing FOTA transport/ACK/retry evidence plus final clean-production smoke |

## Qualification boundary

The final clean-production evidence proves the exact matched path:

`AM312 PIR -> NodeRuntime -> NodeMessage -> ESP-NOW -> HubRuntime processing -> Durable application ACK -> node retirement -> MAC acceptance`

The decisive event is `session=17`, `seq=3`: Durable ACK `class=0`,
`retired=1`, MAC `accepted=1`, Hub `ack_send=ESP_OK`, RSSI `-69`, channel `1`.
Hub boot version `1dfa9c3`, ESP-NOW initialization, owner channel 1, embedded
C3 size, clean flash verification, and absence of negative-HIL logs are also
recorded. The C3 startup-banner caveat is recorded without fabricating a
banner that was not retained.

The temporary negative-HIL harness remains only on
`test/hw-m1-3-negative-hil`; it was not merged into the production branch.
HW-M1.4 power/performance and future robustness gates remain separate and
unmeasured/open.
