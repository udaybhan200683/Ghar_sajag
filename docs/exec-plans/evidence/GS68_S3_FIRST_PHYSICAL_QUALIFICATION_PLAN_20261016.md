# GS-68 S3-First Physical Qualification Plan — 2026-10-16

## Current disposition

**BLOCKED — `S3-FIRST-CONNECTION-APPROVAL-READY=NO`.** This document is a
non-destructive proposal for a later, separately authorized fixture checkpoint.
It is not authorization to connect, power, program, reset, or communicate with a
board. The current software phase did not access hardware. GS-68 comment 11174
is the task authority for software readiness; no fixture-specific physical
approval is present.

The source-bound S3 and C3 images are diagnostic build artifacts. Compilation
does not establish which boards or adapters are available, identify the spare
S3 serial interface, prove the image is running, or qualify its power path. The
fixture template is intentionally unassigned. Therefore the connection
procedure below cannot be verified against an exact board, connector, cable,
power source, adapter, USB serial identity, or stable `/dev/serial/by-id/` path.

## Qualification stages

| Stage | Scope | Minimum prerequisites | Status |
|---|---|---|---|
| S3-A | Passive spare S3 identity and interface inspection; no CloudSync, signer, or Node pairing | Exact spare S3 label/PCB revision; board documentation and pinout; identified connector and adapter; isolated bench and documented power path; exact stable USB identity; fixture-specific approval for the named observation | BLOCKED — fixture and connection details absent |
| S3-B | S3 RSA-3072 signing and TLS 1.2 mTLS qualification (GS68-PHY-001..005) | S3-A; approved D05 trust/issuer/verifier contract; D12 protected identity, key custody and test identity; D06 trusted-time contract; isolated TEST_ONLY backend and signed readiness; case-scoped approval | BLOCKED — D05/D12/D06 and protected test identity pending |
| PAIR-C | Later S3+C3 outage/rejoin, exact EventKey retry, authenticated durable ACK, duplicate-safe receipt, and resource observations (GS68-PHY-006..009) | S3-B prerequisites as applicable; identified C3 and its isolated observer image; separate C3 interface; an approved event/network stimulus and capture plan; D16 bounds; fixture-specific approval for both boards and each operation | BLOCKED — no identified C3 fixture or additional physical interfaces/stimulus plan |
| OTA-D | Signed image compatibility and failed-health rollback (GS68-PHY-010) | Separate GS-118/D15 decision and authorization; protected signing key custody; matched signed image pair; disposable fixture; explicit rollback and recovery procedure | BLOCKED — separate GS-118/D15 approval absent |

S3-A may only record device identity and basic boot observations. It does not
prove RSA signing, TLS, backend authorization, Node/Hub delivery, or rollback.
The diagnostic S3 profile selects the DS/TLS build path but has no provisioned
DS identity and does not send a network request when its protected identity
inputs are absent. The C3 observer is read-only: it can report its own link and
retained-event state and correlate authenticated ACKs; it cannot create motion,
reset the Node, or provide stimulus. A Node cannot observe the Hub's Internet
state, so paired outage evidence must include the Hub/backend side.

## Proposed S3 connection procedure

This procedure becomes executable only after each `TBD` is replaced by an
observed, owner-approved value and the exact plan is approved for that fixture.

1. **Identify the spare without borrowing C8 equipment.** Record the S3 PCB
   revision, board label, ESP32-S3 marking, flash/PSRAM part or documented
   configuration, and a photo of its disconnected connector area. Assign a new
   fixture ID. Compare the MAC, serial, and all stable port names with the
   protected GS-114 C8 identity/port registry; any match blocks the checkpoint.
   Current values: fixture ID `UNASSIGNED`; PCB/revision `UNKNOWN`; MAC
   `UNKNOWN`; USB serial `UNKNOWN`; port-by-id `UNKNOWN`.
2. **Verify the electrical path before attaching a cable.** Identify the exact
   connector, USB bridge/native USB function, cable, host adapter, power source,
   current limit, and whether USB VBUS back-powers the board. Use an isolated
   spare-only bench with no C8 harness, sensor, actuator, shared powered hub,
   production LAN, or production credential. Do not connect until the board
   documentation and observed wiring show that the proposed path cannot
   back-power another fixture or assert EN/reset. The hardware revision and
   approved power path are currently unknown, so this step is blocked.
3. **Enumerate only the named interface.** After fixture-specific approval,
   connect the approved cable to the isolated host. Capture the USB VID/PID,
   manufacturer/product/serial descriptor, stable by-id symlink, resolved tty,
   and fixture label in a new unique evidence directory. Do not scan candidate
   ports, select by tty numbering, or reuse a historical C8 path. A mismatch
   ends the run before opening a serial session.
4. **Prevent modem-line reset and writes during identity inspection.** Use the
   approved by-id port exclusively with DTR/RTS held low, `dsrdtr=False`,
   `rtscts=False`, `xonxoff=False`, and no reset/bootloader command. The GS-68
   serial transport is configured with these flags and exclusive access. For
   the initial USB identity-only pass, do not transmit a command. The target's
   actual diagnostic observation requires its source-matched image to be
   installed; any future image installation must have its own explicit,
   fixture-specific authorization and is not authorized here.
5. **Capture and bind evidence.** Create a new evidence directory with mode
   `0700` and files mode `0600`. Record UTC start/end, operator approval ID and
   expiry, fixture and board identity, exact adapter/port, cable/power path,
   source commit, S3/C3 profile hashes, sdkconfig hashes, image hashes, case
   plan digest, requested case IDs/nonces, raw bounded frames, reset reason,
   boot/session generation, and a hash-chained manifest. Keep keys and
   credentials in the approved secret store; do not put secrets in the evidence
   bundle, Git, logs, or Jira. Mark an absent frame, identity mismatch, changed
   image, incomplete capture, or unexpected reset `BLOCKED` and `NOT_RUN`.
6. **Close and recover without resetting.** Stop on any unexpected boot,
   panic, link state, identity mismatch, power anomaly, or evidence write error.
   Close the capture process, preserve the partial bundle as interrupted, and
   do not retry or clear it. Do not issue a reset to recover. Return power and
   cabling to the recorded safe state using only the approved isolation method;
   quarantine the fixture for owner review if its prior state is uncertain.
   Recovery may use only the separately approved procedure for the exact
   fixture.

## Explicitly prohibited for this plan

- Any connection, USB enumeration, UART/USB serial open, or power application
  before exact fixture-specific approval.
- Flash, erase, reset, bootloader entry, factory initialization, storage
  clearing, re-enrollment, or changing a device identity.
- eFuse/HMAC programming, protected key creation/export, Secure Boot or Flash
  Encryption changes, production credentials, production roots, or commercial
  CloudSync activation.
- Connecting to a production endpoint or using customer data.
- Operating or sharing the active GS-114 C8 fixture, adapter, cable, serial
  path, power supply, or evidence directory.
- Triggering motion, toggling network/power, or injecting events before a
  separately approved paired-board test plan exists.
- Signed OTA installation or rollback without separate GS-118/D15 authority.

## Readiness gaps and next owner action

Software has bounded S3/C3 diagnostic frames, source/profile/image bindings,
case IDs and nonces, authenticated Node ACK/EventKey correlation, a default-off
C3 observer, an isolated TEST_ONLY mTLS backend, and fail-closed dry-run and
evidence verification. Those controls have not been exercised on a board.

To make **S3-A** reviewable, provide the exact spare S3 identity and hardware
revision, board/pinout documentation, connector and adapter model, proposed
isolated power path, stable USB serial identity, and an approval naming the
allowed identity-only observation, allowed connection/power operations, expiry,
evidence location, and recovery steps. The approval must explicitly exclude
the protected C8 fixture. A separate approval must name any image installation
or target command.

Before **S3-B**, owners must resolve D05/D12 trust and protected test-identity
custody, D06 trusted time, the TEST_ONLY trust/ownership mapping and case plan.
Before **PAIR-C**, owners must approve D16 resource/outage limits and the
additional C3/interface/stimulus plan. **OTA-D** remains independently blocked
on GS-118/D15. Until then, `PHY-GS68-CLOUD-MTLS` remains release-blocking and
`NOT_RUN`.

## Dated software continuation — 2026-10-17

The S3 product now links the shared `cloud_trust_provider` seam, and the HTTPS
adapter uses only trusted provider time for ESP-TLS certificate validation.
TEST_ONLY provider/backend tests cover identity/authority, revocation, RSA-3072
DS credential shape, current ownership epoch, authenticated-time startup and
recovery, nonce replay, rollback, durable floor checkpointing and the GS-40
NodeHealth publisher. Commercial composition remains explicitly
`UnprovisionedS3CloudTrust`; no protected identity or authenticated time provider
is instantiated. The app's CloudSync URL/trust root and provider prerequisites
remain unconfigured, so the production request path still fails closed.

The latest software candidate is an ESP-IDF 6.0.3 non-flashing S3
production-profile build (`GS_HIL_BUILD=OFF`, project version
`gs68-provider-20261017`) with a 2,168,128-byte S3 app image, SHA-256
`2052ba8d233b66bd753d5f6572c01acd4a4cd3daf6017dde70c27d628fde69b5`, fitting
the 4 MiB app slot. Its sdkconfig SHA-256 is
`79aa5a0b45b155a97e60feb1f93bc7b653b10d745aea932d57eac9f6bc5da27b`. It embeds
the unchanged previously validated C3 app (937,536 bytes, SHA-256
`d94e011abd0e28b31cadb4dee2ff6451b0f5311c2783cdcbb2a631c03e86f765`). The
source commit `42f74034d5f1f5acd2c605ffee37f540da42ef7e` is pushed on the
canonical branch. Jira evidence: GS-68 comment `11286`, GS-109 `11287`, GS-40
`11288`. For a future installed-image check, an owner-approved
fixture operator must read back the booted application image through the
approved reset-safe observer and compare its device/image manifest to that
exact SHA; a source build or UART log alone is insufficient. C3 pairing reuses
the recorded validated C3 image until a Node source change invalidates it.
Expected-image verification does not authorize flashing or serial access.

This software result does not unblock S3-A/S3-B: the spare S3 fixture/revision,
flash/PSRAM/pinout and isolated power/connector path are still unknown; the
current D05 issuer/trust chain and active Hub/Home/revocation source, D12
factory/DS key custody and test identity, D06 authenticated bootstrap/verifier,
durable target counter/floor and approved freshness/checkpoint thresholds are
still absent. The case-specific fixture-owner approval remains required. No
physical, serial, USB, reset, flash, eFuse, credential or production-service
operation occurred during this continuation.
