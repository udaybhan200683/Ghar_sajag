# First S3/C3 hardware pair — stopped at ownership preflight

Date: 2026-10-09. Context: `2026-10-09.001` (PASS against canonical).
Branch: `feature/r1-s3-hub-bringup`. Starting HEAD:
`e5d13f615c5f1c10d01325460879425b32d8721a`; starting status clean.
Authority: GS-D030; GS-D025–029 and existing ownership/durability requirements
remain unchanged. No production readiness or new product decision is recorded.

## Executable result

**BLOCKED_EXISTING_NODE_OWNERSHIP_AND_PENDING_EVIDENCE.** Both boards are
accessible, but the C3 is authenticated as Paired to the former Hub,
`hub-5c013bbeb9f8`, association generation 3. Its authenticated recovery snapshot
contains **seven retained/pending Motion records**, session 1530, sequences
12–18, logical source `hil-signed-fota`. The S3 MAC is `e0:72:a1:d3:8d:34`;
it is a different authenticated Hub identity. No commissioning, reset/disposal,
identity impersonation, event injection, synthetic ACK or application flash was
attempted. Stop before changing ownership or stranding the old pending records.

| Check | This run's physical result |
|---|---|
| S3 identity/flash | ESP32-S3 QFN56 rev0.2, MAC e0:72:a1:d3:8d:34, 16 MiB; flash manufacturer68/device4018, quad3.3V eFuse configuration |
| S3 serial | CH343, `/dev/ttyACM0`; stable alias `usb-1a86_USB_Single_Serial_5C83119376-if00` |
| C3 identity/flash | ESP32-C3 QFN32 rev0.4, MAC14:63:93:c5:d1:58, 4 MiB XMC embedded flash; manufacturer46/device4016 |
| C3 serial | USB Serial/JTAG, `/dev/ttyACM1`; stable alias `usb-Espressif_USB_JTAG_serial_debug_unit_14:63:93:C5:D1:58-if00` |
| C3 existing application | Boot PASS: IDF6.0.3, `gs_hw_m1_node`, `cfec7d2-node-usb-stable-qualifi`, active ota_0 at0x20000 |
| C3 local initialization | Wi-Fi STA and ESP-NOW2.0 init observed; empty-AEAD hardware AES self-test PASS,13 checks |
| C3 runtime | Waiting for authenticated rejoin; GET_STATE reports sensing_live=0/runtime_live=0. Its RAM retained=0 is **not** evidence of an empty persistent queue |
| C3 restart preservation | Association, recovery snapshot, wrapping key, signing identity and installer code byte-identical in before/after NVS captures; seven persisted records preserved |
| S3 data preservation | Original NVS0x9000/0x6000 and VFS0x200000/0x600000 verified against private backups; both digests match |
| S3 product boot / pair / event / invalid-event rejection | NOT_RUN on this pair; ownership preflight blocked |
| Durable ACK / lost ACK / restart dedupe | NOT_RUN on this pair; no ACK issued and no physical S3 durability claim |

Current S3 firmware remains the previously qualified diagnostic. Reuse
[the bring-up checkpoint](R1_S3_HUB_BRINGUP_20261009.md) for physical8 MiB Octal
PSRAM40MHz, diagnostic boot/Wi-Fi/ESP-NOW PASS and the full Hub build PASS
(1,791,792 bytes, product image not flashed). Those are previous results,
not a product boot or S3/C3 interchange result in this run. No redundant build.

## Preservation and verification

Private C3 backup:
`~/.local/share/ghar-sajag/board-backups/146393c5d158-s3-pair-20261009/before-flash.bin`,
4,194,304 bytes; SHA-256
`311fef4b5dfbebf843a5fe98efefbc23b7758749843717ef8472f009fdef78c7`.
`esptool verify-flash 0 before-flash.bin` passed with an on-device digest match.
Backup directory mode0700; raw flash/NVS and manifest mode0600, outside Git.

Read-only offline inspection used the installed IDF partition/NVS parsers,
checked live NVS page/entry/blob CRCs and blob-index/chunk framing, authenticated
the association with AES-GCM, derived the existing NodeRecovery/v1 key with
HKDF-SHA256, authenticated its domain-bound snapshot and checked complete v3
record framing. No keys, installer codes or raw NVS are published. This is a
backup inspection, not execution of the production Node recovery state machine.
Recovery generation196, prior boot session1530, retirement epoch1, admission
highwater18, report generation196; all seven pending records have retained=true.
Node-side EventKeys are `hil-signed-fota:1530:12` through `:18`; physical owner
qualification is added at authenticated Hub admission, which was not exercised.

After returning the C3 from the read-only flash stub to its existing application,
read NVS again and compare the five preserved records above. They match exactly.
The boot-session counter naturally advanced1540→1541 in the compared captures;
reboots can advance it further. No manual NVS mutation, reset of ownership,
queue disposal, eFuse write, erase or application write command occurred.
The Node was returned to normal application boot, not left in the flash stub.

## Existing protocol and next bring-up boundaries

Both target configurations select ESP-NOW channel1. Reuse the existing exact-node
commissioning handshake, P-256 identity proofs, installation/Home binding,
authenticated rejoin, directional AES-GCM runtime frames and replay checks.
ESP-NOW peer encrypt=false is explicitly protected by application AEAD;
it is not authorization for plaintext or a temporary replacement protocol.
See `node_security_link.cpp` initialize(): a Paired Node rejoins its saved Hub;
it does not open the unpaired commissioning window for another Hub.

The shared Hub secure owner already recovers `HubDurabilityOwner`, binds
`DurableJournalSlotStore` and refuses admission if recovery is not Ready;
the ACK follows `run_state_once()`'s result. Existing native durability code is
present. The **new protected compact lifecycle/reclamation is not integrated**,
and the native path has not been physically qualified on S3. Neither is bypassed.
If a later pair cannot establish real persistent admission/restart recovery,
test only safe receive/authentication and report
`BLOCKED_BY_STORAGE_INTEGRATION`; do not emit a false durable ACK.

Two separate preparations remain before product flashing: enable/review only
the existing secure UART qualification controls (S3 CMake currently rejects
GS_HIL_CONTROL; keep insecure GS_HIL_BUILD disabled), and isolate product NVS
from original user NVS. The current development table maps default nvs to
0x9000, so ordinary product startup/provisioning could modify preserved data.
A backup alone is not permission to overwrite it. Future ota_1 writes also
overlap original VFS; no such write occurred here. A preservation-safe
development layout/write plan must be reviewed before product boot/FOTA.

PCB/module markings and actual camera pinout remain unavailable. Use only the
already demonstrated CH343 UART43/44 until board evidence is available; no
sensor/camera/LED/button GPIO was assigned or driven. Keep Octal PSRAM35–37
reserved. No camera firmware, Node changes or BAT-C8 changes were introduced.

## Focused host validation

From the product directory, existing targets all exited0:

- `make commissioning-crypto-host-test`: identity/signature/ECDH/HKDF/AEAD;
  exact identity/Home/Hub/window/replay; fragmented wire; uplink/ACK tamper and replay.
- `make association-host-test`: reboot/write failure/reset/corruption.
- `make rejoin-host-test`: mutual proof/session/Home/replay.
- `make node-recovery-persistence-host-test`: encrypted bounded recovery.

Host PASS is not physical pair qualification. No historical capacity suites,
FOTA attempts or additional firmware optimizations were run. Existing physical
lost-ACK evidence for the former Hub remains historical evidence only.
No newly observed regression; pairing, physical invalid-frame rejection,
disconnect recovery, durable ACK and S3 cross-reboot dedupe remain untested.
See [measurement log](R1_S3_C3_FIRST_PAIR_20261009.log).

## Single next action

Resolve the C3 ownership handoff: reconnect this Node to its original authenticated
Hub and durably deliver/retire its seven pending records before reviewing an
explicit re-enrollment to the S3. Do not factory-reset or discard them. If that
Hub is unavailable, preserve this Node and use a genuinely unpaired C3 instead.
Stop this run; no production storage/FOTA/AI work or new requirements.
