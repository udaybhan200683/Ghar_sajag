# GS-68 / GS-172 spare-S3 auxiliary diagnostic — 2026-10-17

## Disposition

**Software candidate: BUILD PASS. Physical installation: NO-GO.** Host-only USB/PnP observations are consistent with the owner's dedicated spare and differ from the protected C8 fixture inventory. A read-only security inspection produced no security data and its USB command blocked. Secure Boot, Flash Encryption, ROM/download restrictions, installed partitions, recovery capability, and running image remain UNKNOWN. No candidate installation or physical diagnostic was performed.

This is auxiliary TEST_ONLY readiness evidence. It does not satisfy GS68-PHY-001..010, DS signing, mTLS, GS-68 physical acceptance, or GS-40 physical acceptance.

## Repository and provenance

- Repository: /home/udaybhan/projects/Ghar_sajag_r1
- Branch: feature/r1-commercial-baseline
- Source implementation HEAD: cfc89a8e7bd6009eddde5790814e557357d8a032
- Source code-tree OID: e4c8fd938d394be5f1e595bd7d3036744a9888e3
- Context preflight: PASS; version 2026-10-13.001
- Implementation commits: dbaf834, 1fafdf7, ea76ce6, cfc89a8e7bd6009eddde5790814e557357d8a032. The last fixes a C++ namespace error found by the non-flashing build.
- Existing untracked PWA, Android, managed-component, GS-114/C8, GS-40 and other evidence paths were preserved and not staged. Separate GS-177 worktree/process was not changed or signaled.
- Source-binding runner accepts an immutable image source commit only when it is an ancestor of current HEAD and the committed code tree/build inputs remain identical. Later documentation-only commits do not impersonate the artifact source commit.

## Current build candidate

Artifact: code/build/validation_targets/gs68_cloudsync_diag_20261017_auxfix/build/gs_r1_s3_hub.bin (ignored local build output).

| Property | Verified value |
|---|---|
| Build source commit | cfc89a8e7bd6009eddde5790814e557357d8a032 |
| App image | 278,944 bytes; SHA-256 855b586d6e7a51ebad22eb45c81c170897bbb0dbfd291b921d60bca72ae15049 |
| ELF SHA-256 from image metadata | 67a0ba642bca413e4018c0102d2a4c4e1d3b646e2f3b5add94abd8cf90d20c46 |
| Profile SHA-256 | 7d13aa13684953744737b653c82ec7f8b95d0c6bfc715649bc99d501313d3c72 |
| Effective sdkconfig SHA-256 | ff3150eeeac79a4a80b5a718a20408386d90d5a491cb199d763e0b6190105a7a |
| Development partition CSV SHA-256 | 9da4b591a461c8b251e3ced8107d3ff3bc4a5fe4fd8844670ba4d90163d3ea29 |
| Partition table binary SHA-256 | 4828fb04f0569bcc5ffafaf887bb7f360e6ab858ec29df00297671f5f2a468fe |
| Build inputs SHA-256 | 0d92a028bacbca7663b001fac6bb6894d402118b36e40ca9ecbe8b202d26f39b |
| ESP-IDF / target / profile | v6.0.3 / ESP32-S3 / GS68_CLOUDSYNC_DS_MTLS_HIL TEST_ONLY |
| Effective console | USB Serial/JTAG primary; UART0 primary disabled; USB secondary disabled; USB driver-backed blocking stdin |
| Image format check | esptool v5.4.0 image-info: ESP32-S3, 16 MB image header, checksum and validation hash valid |

The successful build used no serial or hardware. Its image metadata reports
DS peripheral selected but not provisioned; this is not evidence of silicon DS
signing. The candidate contains no production credential or production time
anchor and does not enable a commercial endpoint. The former c0fb82c image
(473,312 bytes, SHA-256
c0fb82c69fe030f8a4358b7783e7c537156dfdb361b4df1a620831210d1bef65) is
**superseded** by this source-corrected build and must not be installed.
Earlier e8e0a623 and installed-baseline c905af734 artifacts are not substitutes.

## Software validation

- make -C code gs130-hil-runner-test: PASS; 1,738 C++ protocol assertions and 84 Python tests. Physical/default HIL cases remained NOT_RUN; no port opened.
- Focused auxiliary runner, source-binding, and signed-time helper tests: PASS, 13 tests.
- make -C code gs68-node-diag-protocol-host-test: PASS; 1,738 assertions.
- ESP-IDF 6.0.3 non-flashing S3 diagnostic build: PASS; hardware_actions=0; physical=NOT_RUN.
- First build attempt exposed a namespace compile error. It was fixed in cfc89a8 and the final source-bound build above passed. No stale image is used as the current candidate.

## Fixture and inspection results

Host-only USB enumeration positively distinguished the owner-designated spare
from the protected C8 inventory using available USB/PnP metadata. Public
evidence intentionally omits serial, MAC, full by-id path, Windows device
instance IDs, and private evidence paths; the private host receipt is stored
under /home/udaybhan/.local/share/ghar-sajag/GS68-20261017 with restrictive
permissions.

ESP-IDF v6.0.3 / esptool v5.4.0 was used for one attempted read-only security
inspection. The command included --before default-reset and --after hard-reset;
these are reset-capable transport options. It printed the tool and serial-path
header, then blocked without returning security information. The process was
not killed, retried, or detached; no further device I/O was attempted. No flash
readback or backup was made. No flash, erase, eFuse/security write, credential,
production endpoint, or C8 operation occurred.

| Physical result | State | Reason |
|---|---|---|
| Fixture identity | OBSERVED, consistent with designated spare | Host USB/PnP only; identifiers redacted publicly |
| Secure Boot / Flash Encryption / ROM restrictions | UNKNOWN | Security query returned no data |
| Installed partition map / active OTA slot | UNKNOWN | No flash inspection |
| Usable backup and recovery route | NOT ESTABLISHED | No baseline image/metadata readback or restore validation |
| Candidate installed / running image verified | NO / NO | Installation gates not met |
| USB delayed/fragmented/malformed/sequential commands | NOT_RUN | Candidate not installed |
| Silicon PSA RNG / RSA signed-time proof and negatives | NOT_RUN | Candidate not installed |
| DS signing / live mTLS | NOT_RUN | No provisioned DS context or client credential; outside scope |
| Official GS-68 and GS-40 physical acceptance | NOT_RUN | No official physical cases executed |

## Exact next action and stop conditions

The installation gate remains NO-GO until a stable USB connection permits a
successful documented read-only security inspection, the installed bootloader,
partition table, OTA metadata/slot and application are identified, Secure
Boot/Flash Encryption/download restrictions are understood, and a restorable
baseline recovery image plus metadata is obtained and verified offline. Then
re-evaluate app-only compatibility at the measured application offset. Do not
reuse historical offsets as observed facts, force security overrides, or
substitute an older image. After all gates pass, use the owner's conditional
authorization only for the exact current digest and a bounded application-only
TEST_ONLY installation; stop on any reset, identity, image or behavior mismatch.

If USB transport remains blocked or the protection/recovery state cannot be
established, installation stays NO-GO. The next safe action is to repair the
USB/IP connection and repeat only the read-only preflight, with no flash write.

Production D05/D12/D06 approvals remain open: pilot CA/issuer and trust
custody; S3 DS key/eFuse custody and lifecycle; authenticated-time authority,
anchor, freshness and rollback-resistant state; authoritative ownership and
credential registry/lifecycle; Secure Boot, Flash Encryption and recovery
policy. Existing P0 product_status=PARTIAL and the Hub migration assertion and
sanitizer timeout blockers remain open.
