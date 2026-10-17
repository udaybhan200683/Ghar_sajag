# GS-172 First S3 Fixture Readiness Checklist — v1.0

**State:** NOT READY / NO physical operation authorized
**Use:** Complete and sign for one fixture before requesting a separate
fixture-specific action approval. Blank or `UNKNOWN` means NO-GO.
**Do not use:** This checklist is not an authorization to connect, power,
enumerate, read, flash, reset, provision, or test a device.

## A. Fixture identity and custody

| Check | Required record | Current state |
|---|---|---|
| Unique fixture ID, owner, storage location, non-customer disposition | Inventory ID, custodian, access record | **UNKNOWN / BLOCKED; template remains GS68-SPARE-UNASSIGNED** |
| ESP32-S3 Hub board identity and revision | Board label, PCB revision, SoC marking, N16R8 flash/PSRAM provenance, manufacturer documentation | **UNKNOWN / BLOCKED** |
| C3 pairing fixture(s), if used | Unique Node IDs/revisions; TC05 requires at least two independently enrolled Nodes or approved qualified profile fixture | **NOT IDENTIFIED** |
| Exclusion of GS-114/C8 | Compare fixture/serial/MAC/port/cable/power IDs with protected evidence inventory; no reuse | **NOT VERIFIED; historical BUSID/COM10/ttyACM0 is not current identity evidence** |
| Isolated bench | Diagram of exact connector, cable, adapter, power supply/current limit, VBUS/back-power and LAN segmentation | **NOT VERIFIED** |
| Recovery and quarantine owner | Named person, stop conditions, evidence-preserving interruption and replacement route | **PLAN ONLY** |

## B. Image, firmware and environment

| Check | Required record | Current state |
|---|---|---|
| Source baseline | Commit SHA, clean tracked source fingerprint, change list | **Candidate source a5d2806; current HEAD c4bc525; exact runner binding mismatch, NO-GO** |
| ESP-IDF/toolchain | Exact ESP-IDF 6.0.3 build/container/tool versions and component lock | **v6.0.3 non-flashing candidate build verified; physical image/toolchain qualification NOT_RUN** |
| Build profile/config | Production vs test-only profile name; sdkconfig, partition and feature hashes; assert no production endpoint | **TEST_ONLY candidate identified; image c0fb82c69fe030f8b4358b7783e7c537156dfdb361b4df1a620831210d1bef65; partition compatibility unverified** |
| Installed image identity | On-device running-image proof bound to expected boot slot and source/image SHA; build output alone is insufficient | **NOT VERIFIED** |
| Provisioning/recovery images | Signed image digest, signing key custody, boot/update/recovery proof and rollback policy | **NOT READY; no independently verified restore image found for reported baseline c905af73419c84af7a1d986dada3724da7e654b4d7eaa0235bd06e515902f8ef** |
| TEST_ONLY backend | Isolated test hostname, root/fingerprint inventory, issuer/time signer identities, network ACL and data reset policy | **SOFTWARE FIXTURES ONLY; endpoint not prepared** |
| Production separation | Confirm production roots/URLs/credentials cannot be selected by test build, fixture, environment or registry | **NOT VERIFIED** |

## C. Identity, credential and registry fixtures

| Check | Required record | Current state |
|---|---|---|
| Permanent Hub ID | Uniqueness reservation and public opaque lookup value; no Home claim in QR/label | **NOT RESERVED** |
| TEST_ONLY Hub client certificate | Exact isolated test issuer, leaf/chain/fingerprint, client-auth purpose, RSA-3072 and proof-of-possession result | **Synthetic host fixture only; no device credential** |
| DS key path | Security-approved generation, D12 HMAC/eFuse input handling, DS context write/load path, zeroization and disabled unauthorized debug | **NOT IMPLEMENTED / NOT APPROVED** |
| Registry mapping | Test row joining fingerprint, Hub ID, enrollment/source association, current Home/epoch, generation/status | **Host test only; no fixture row** |
| Negative authority fixtures | Unknown Hub, wrong Hub, stale epoch, transfer, revoked, quarantined, expired, replaced and unavailable registry | **Host tests exist; device/backend fixture not staged** |
| Credential lifecycle | Renewal/overlap, expiry, emergency revocation, replacement, issuer loss and CA compromise response | **OPEN / SECURITY REVIEW** |

## D. D06 time fixtures

| Check | Required record | Current state |
|---|---|---|
| TEST_ONLY time authority | Isolated signer, private key custody, pinned test anchor, endpoint/audience and no production trust | **Host test signer only** |
| Target proof path | PSA CSPRNG challenge; GSTP v1 verifier; exact nonce/boot-generation binding; successful target adapter and CloudSync gate | **TEST_ONLY target diagnostic compiled; silicon execution NOT_RUN; valid proof writes NVS namespace gs68time** |
| Cold-boot behavior | No time/no WAN means CloudSync unavailable, local safety active; no SNTP-only readiness | **TEST_ONLY state-machine coverage; no device** |
| Floor/rollback | Missing/corrupt store, old floor, wall-clock rollback, restored flash, reboot, max-age and checkpoint/wear tests | **Host tests exist; production anti-rollback floor absent** |
| Rotation and thresholds | Approved authority/anchor overlap, freshness, validity, allowed error, outage and recovery policy | **OPEN / SECURITY REVIEW** |
| Epoch changes during recovery | Old Home epoch rejected before publisher resumes | **Host behavior covered; physical/backend fixture not staged** |

## E. Safe observation and authorization

| Check | Required record | Current state |
|---|---|---|
| Non-resetting observer | Exact stable by-id path, adapter model/serial, no DTR/RTS/reset behavior, read-only command list and tested bounded capture | **UNKNOWN / BLOCKED; current fixture has no stable by-id path; runner source/case binding not suitable for auxiliary command smoke** |
| Installed-image method | Approved method that verifies running image without reset; any installation/flash separately authorized | **NOT VERIFIED** |
| Evidence location | New unique directory, access controls, timestamp source, hash manifest and retention owner | **NOT ASSIGNED** |
| Approval record | Named fixture IDs, image/plan hashes, case IDs, operation classes, interface, operator, start/expiry, recovery, separate Security signoff for credential/eFuse | **NOT GRANTED** |
| Stop conditions | Identity/image mismatch, unexpected reset, power anomaly, invalid time/registry, missing evidence, endpoint mismatch | **Must be incorporated in signed plan** |

## F. GO decision

**Current result: NO-GO.** The candidate image and USB configuration are
identified and hash-verified, but the spare's present identity, installed
image, matching partition table, compatible recovery image, stable observer,
formal runner source/case binding, and fixture-specific authorization are not
verified. The TEST_ONLY target proof path is compiled but has no silicon
evidence; DS signer and physical TEST_ONLY trust setup are absent. Production
D05/D12/D06 authorities and Secure Boot/Flash Encryption/recovery decisions
remain open. See the [dated install preflight](GS68_SPARE_S3_INSTALL_PREFLIGHT_20261017.md).

GO for an initial identity-only observation requires every applicable row in A,
B and E to be complete plus a separate approval for the named observation.
GO for GS68-PHY-001..005 additionally requires target DS signing, TLS 1.2
TEST_ONLY mTLS, the signed-time verifier path, approved registry and negative
fixtures, current image proof, and security/fixture approval. GO for any
Secure Boot, Flash Encryption, eFuse or ROM/debug change additionally requires
resolved P4 in the decision matrix and a separate exact operation authorization.

GS-40 PHY-01..06 require the matched current S3/C3 images, Node enrollment and
session identities, effective profiles, safe observers, Home/epoch authority,
trusted time, backend/PWA test account, and separate per-case approvals. TC05
is NO-GO until a second independently enrolled Node or a qualified approved
profile fixture is available. See the [GS-40 current readiness record](GS40_REAL_TARGET_READINESS_20261016.md).

Related: [SOP](GS172_FIRST_DEVICE_PROVISIONING_SOP_v1.0_20261017.md),
[decision matrix](GS172_SECURITY_DECISION_APPROVAL_MATRIX_v1.0_20261017.md),
[physical plan](GS172_PHYSICAL_ACCEPTANCE_PLAN_v1.0_20261017.md),
[GS-68 first physical plan](GS68_S3_FIRST_PHYSICAL_QUALIFICATION_PLAN_20261016.md).
