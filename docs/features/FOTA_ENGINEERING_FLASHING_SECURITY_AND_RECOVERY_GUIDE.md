# Ghar Sajag FOTA Engineering, Flashing, Security, and Recovery Guide

## 1. Purpose and Audience

This guide is for engineers implementing, building, flashing, testing,
debugging, and recovering Hub/C3 firmware. It describes the current source
architecture and practical limits. It is not a qualification-results or
project-status document.

The detailed physical PASS/FAIL procedure for authenticated signed FOTA is in
[`docs/validation/PHASE2_SIGNED_FOTA_PHYSICAL_QUALIFICATION_PLAN.md`](../validation/PHASE2_SIGNED_FOTA_PHYSICAL_QUALIFICATION_PLAN.md).

## 2. FOTA at a Glance

```text
initial C3 installation
  -> authenticated Hub/Node association and runtime session
  -> authorized internal FOTA request for one enrolled Node
  -> Hub sender asks Hub security owner to seal each secure-v2 message
  -> ESP-NOW authenticated/encrypted session transport
  -> C3 security owner authenticates, decrypts, and checks replay state
  -> bounded FOTA receiver writes the inactive OTA partition
  -> streamed SHA-256 check
  -> ESP-IDF signed-image verification at OTA finalize (signed profile)
  -> select alternate boot slot
  -> restart
  -> pending-image health gate
  -> authenticated rejoin
  -> sensing and application event/ACK operation
```

The production C3 secure route requires signed-image verification to be
configured; otherwise it rejects secure FOTA `BEGIN` before starting the OTA
write. The regular HIL FOTA path is a separate legacy raw-packet route; see
[Development vs Production Profiles](#17-development-vs-production-profiles).

## 3. Components and Ownership

### Hub

| Responsibility | Owner |
|---|---|
| Product request boundary | `request_authenticated_fota(FotaStartRequest)` in `firmware/hub/target/esp32/idf/main/fota_sender.*`. It accepts a physical Device ID plus board and version claims. No external production caller is currently wired. |
| Image/chunk/retry state | FOTA sender worker in `firmware/hub/target/esp32/idf/main/fota_sender.cpp`. It reads the C3 image embedded as `node_firmware.bin`, constructs secure-v2 messages, and owns transfer progress and retries. |
| Session keys, sealing/opening, authorization | Hub owner and `HubSecurityLink` in `firmware/hub/target/esp32/hub_runtime_adapter.cpp` and `hub_security_link.cpp`. The sender passes typed commands through the owner queue; it does not own session keys. |
| Radio transport | ESP-NOW path in the Hub target adapter. Outbound secure messages and verified ACK results pass through the existing owner/radio route. |
| ACK acceptance | Sender consumes only verified FOTA ACK results returned by the Hub owner, matching the requested Node, transfer, and pinned session. |

### C3 Node

| Responsibility | Owner |
|---|---|
| Session authentication and replay state | Node security owner in `firmware/node/target/esp32c3/node_runtime_adapter.cpp` and `node_security_link.cpp`. It opens authenticated frames and submits accepted FOTA plaintext through a bounded control queue. |
| FOTA receiver state | Worker in `firmware/node/target/esp32c3/idf/main/fota_receiver.cpp`, using `firmware/node/fota/secure_fota_adapter.*` and the shared bounded receiver in `firmware/node/fota/fota_receiver.*`. |
| Flash writing and finalization | `EspIdfOtaWriter` in the target FOTA receiver. It uses `esp_ota_begin`, `esp_ota_write`, `esp_ota_end`, and `esp_ota_set_boot_partition`. |
| Image digest | Streaming SHA-256 adapter in the C3 target FOTA receiver; the secure adapter compares the computed digest with the authenticated `BEGIN` metadata before it finalizes the image. |
| Signature verification | ESP-IDF image verification reached by `esp_ota_end()` when the signed-app-on-update profile is enabled. |
| Pending-image health | `firmware/node/fota/boot_health_gate.*` plus the target health task in `firmware/node/target/esp32c3/idf/main/fota_receiver.cpp`. |

The secure sender API currently has no authorized cloud, app, or installer
caller. The in-firmware API is not itself a production user authorization
system.

## 4. FOTA Security Model

| Layer | What it does | What it does not prove |
|---|---|---|
| Authenticated Hub/C3 session | Binds messages to an enrolled physical Node and the current session. Session replacement invalidates a pinned transfer. | It does not establish that firmware came from the publisher. |
| Runtime AEAD | Protects secure FOTA data and control messages in transit; authenticates peer and frame contents. | It does not prove the image is approved firmware. An authorized Hub could send an arbitrary image. |
| Replay/freshness protection | Runtime security checks frame freshness/replay; ACKs and transfer data also bind to session, transfer ID, and index. | It does not prevent an authorized peer from requesting a new transfer or enforce downgrade policy. |
| SHA-256 image integrity | Streams the received image and requires it to match the digest in `BEGIN` before OTA finalization. | The digest is supplied by the Hub. A matching digest is not publisher authenticity. |
| Signed app image | With ESP-IDF signed-app-on-update enabled, `esp_ota_end()` verifies the candidate's RSA signature against the trusted public key in the currently running signed app. | It does not protect against physical rewriting of flash/bootloader without hardware Secure Boot. Current product key custody and image policy are incomplete. |
| Boot-health/rollback | Keeps a new OTA image pending until the configured target health gate succeeds; requests ESP-IDF rollback on gate timeout. | The existing physical result is the success path for historical same-image raw FOTA, not physical signed-A/B or failed-boot rollback proof. |
| Secure Boot/eFuse | Would anchor boot-time verification in hardware and protect the boot chain, subject to a production provisioning policy. | It is not enabled by the current development/signed profile and must not be inferred from signed-app-on-update. |

In signed-app-on-update mode, the first installed application must be signed
with the key that will sign future OTA images. ESP-IDF uses the signature in
the running app as the trust anchor for update verification. Without hardware
Secure Boot, an attacker with physical flash-write access may replace the app
and its trust anchor.

## 5. Wire Protocol

Secure FOTA v2 uses the existing runtime AEAD envelope and a bounded inner
codec in `firmware/common/transport/fota_secure_wire.*`:

- Fixed inner header: 14 bytes (`magic`, version, type, transfer ID, chunk/ACK
  index, body length).
- Maximum secure DATA body: 192 bytes.
- Current AEAD frame overhead: 28 bytes.
- DATA frame: `14 + 192 + 28 = 234` bytes, below the ESP-NOW application
  payload limit of 250 bytes.
- Integer fields are serialized explicitly in network byte order; C++ struct
  packing is not the wire format.
- `BEGIN` carries image size, CRC32, SHA-256, board claim, and version claim.
- `DATA` carries image bytes and a transfer index.
- `END` and `ABORT` carry transfer control.
- `ACK` reports status, next expected index, and bytes written. The secure ACK
  is protected and accepted through the Hub security owner.

The legacy raw Phase-1 HIL protocol uses the older fixed packet format and
must not be used as evidence for secure-v2 behavior.

## 6. Partition and Boot Model

The C3 partition table is
`firmware/node/target/esp32c3/idf/partitions.csv`:

| Partition | Offset | Size |
|---|---:|---:|
| `ota_0` | `0x20000` | `0x1e0000` (1,966,080 bytes) |
| `ota_1` | `0x200000` | `0x1e0000` (1,966,080 bytes) |

`esp_ota_get_next_update_partition()` selects the inactive update target. The
receiver writes and finalizes that candidate, then calls
`esp_ota_set_boot_partition()` only after receiver checks succeed. The next
boot is pending verification under the configured ESP-IDF rollback support.

The target health gate currently waits up to 90 seconds for all of:

- NodeRuntime owner started.
- PIR sensing ready.
- At least two post-sensing runtime ticks.
- Post-sensing radio send confirmation.
- No active FOTA maintenance.
- Minimum free heap at or above 8,192 bytes.

When those conditions pass, the target calls
`esp_ota_mark_app_valid_cancel_rollback()`. At the deadline it calls
`esp_ota_mark_app_invalid_rollback_and_reboot()`. Failure to request rollback
is logged; the image is not deliberately marked valid in that branch.

**Qualification boundary:** ESP-IDF rollback is configured and the health
gate has a physical success-path result in historical same-image HIL. Physical
signed A→B activation and the health-failure rollback branch remain unqualified.
The health gate's radio confirmation is not, by itself, proof of an
application-level authenticated Hub ACK.

## 7. Engineering Prerequisites

- Repository product directory:
  `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2`.
- ESP-IDF v6.0.3 and its activated Python/toolchain environment.
- Compatible ESP32 Hub and ESP32-C3 Node; the focused physical plan uses one
  of each.
- An exact enrolled Node identity and current authenticated Hub/Node session
  for secure FOTA.
- Matching Hub and C3 firmware/provenance. The Hub must contain the selected
  C3 update artifact.
- C3 OTA slot capacity of 1,966,080 bytes. Check the final signed artifact and
  final Hub image against their actual OTA partitions.
- For signed-app-on-update, a trusted signed initial C3 image and the same
  external key for authorized updates.
- USB/serial setup and preflight for physical fixture work. The focused
  qualification plan owns formal physical evidence requirements.

## 8. Initial C3 Flash / First Installation

### Unsigned development image

The ordinary development C3 configuration does not enable signed-app-on-update
or hardware Secure Boot. Secure production FOTA fails closed in this
configuration. The existing HIL fixture command can rebuild/flash its
test-specific pair:

```bash
make hil-checkpoint-smoke
```

Run it from the product directory. It owns fixture setup, preflight, build,
flash, and smoke evidence. It installs the HIL profile; that profile uses the
legacy raw FOTA route and is not an initial signed-image anchor.

`make hw-pair-build` builds a normal Hub/C3 pair but does not flash it. There
is no existing repository command that installs the signed-profile artifact
as a first-boot anchor while preserving the signed image. Do not treat the
unsigned output or generic build's `idf.py flash` suggestion as the signed
artifact.

### Signed initial image

For signed OTA, A must be signed before installation, and B must use the same
trusted key. Flashing unsigned A and later sending signed B does not establish
the software trust chain required by ESP-IDF. The existing signed build script
creates and verifies an artifact, but it does not flash the board. A safe,
repeatable signed first-install procedure is part of the remaining focused
fixture adaptation.

Record the installed image hash, app version, signed profile, key fingerprint,
and active OTA slot before testing updates.

## 9. Building a Signed C3 Image

The existing profile is
`firmware/node/target/esp32c3/idf/sdkconfig.signed.defaults`. It enables:

- `CONFIG_SECURE_SIGNED_APPS_NO_SECURE_BOOT=y`
- `CONFIG_SECURE_SIGNED_APPS_RSA_SCHEME=y`
- `CONFIG_SECURE_SIGNED_ON_UPDATE_NO_SECURE_BOOT=y`
- `CONFIG_SECURE_BOOT_BUILD_SIGNED_BINARIES=n` so the private key is not
  required inside the build configuration.

It does not enable hardware Secure Boot or flash encryption. From the product
directory, activate IDF and use the existing command:

```bash
source ~/.espressif/tools/activate_idf_v6.0.3.sh
python3 scripts/build_signed_c3.py --signing-key /absolute/path/outside/repo/test-key.pem
```

The script rejects a missing key and a key path inside the repository. It
builds the C3 signed profile, signs the app with ESP-IDF Secure Boot V2 RSA
signing, verifies the signature offline, checks the image against the C3 OTA
slot size, rejects known HIL control markers, and prints the signed artifact
path, size, and SHA-256.

The generated unsigned app is `build_signed/gs_hw_m1_node.bin`; the signed
artifact is `build_signed/gs_hw_m1_node.signed.bin`. Generated build output and
`sdkconfig.signed` are ignored by Git. Preserve the signed artifact and
provenance outside transient build cleanup if it is needed for qualification.
Never add the private key to Git or evidence. Offline verification confirms
the artifact matches the supplied key; it does not prove target OTA acceptance.

The current script builds one version per invocation and does not provide a
complete A/B campaign command or an A/B key-custody workflow.

## 10. Hub Image Preparation

The Hub target embeds `firmware/hub/target/esp32/idf/main/node_firmware.bin`
through `EMBED_FILES` in its CMake component. The existing pair builder copies
the normal C3 build output into that location before building the Hub.

The signed C3 builder does not currently synchronize its `.signed.bin` into
the Hub embed input, and no existing command creates Hub variants for valid
and wrong-signature candidates. For signed FOTA, the Hub must embed the exact
signed artifact whose hash is recorded for the run. Verify the embed byte for
byte before flashing. Do not claim a signed campaign using the existing raw
HIL image embedding workflow.

## 11. Normal FOTA A→B Operation

The intended operation is:

1. **Prerequisites:** A is running, signed, sensing-ready, enrolled to the
   intended Hub/Home, and has an authenticated runtime session. The Hub holds
   the compatible B image.
2. **Request:** An authorized internal product caller requests FOTA for the
   exact enrolled physical Node. Currently `request_authenticated_fota()` is
   an internal boundary without an external production caller.
3. **Pin session:** The Hub owner checks enrollment and current session and
   pins the transfer to that session. Removal, revocation, quarantine, or
   session change aborts it.
4. **Transfer:** The sender sends `BEGIN`, indexed `DATA`, then `END`. Each
   frame is sealed by the Hub owner. The C3 owner authenticates/decrypts and
   checks freshness before passing FOTA plaintext to the bounded worker.
5. **ACK/retry:** The receiver reports bounded status/sequence progress. The
   Hub accepts only authenticated ACKs matching Node, session, transfer, and
   index; the sender retries a bounded number of times.
6. **Integrity:** C3 computes SHA-256 over accepted image bytes and compares
   it to `BEGIN`. Mismatch aborts before finalization/boot selection.
7. **Signature:** With signed-on-update enabled, `esp_ota_end()` verifies the
   candidate signature against A's trusted key. A bad signature returns
   finalization failure; boot selection is not advanced by the receiver.
8. **Activation:** After successful finalization, the C3 selects the inactive
   slot and requests restart.
9. **Health:** The new app remains pending until the boot-health conditions in
   [Partition and Boot Model](#6-partition-and-boot-model) pass.
10. **Recovery:** The app re-establishes its authenticated association/session,
    reaches sensing-ready, and produces an application event acknowledged by
    the Hub. These last physical signed-update results remain to be qualified.

## 12. FOTA Failure and Recovery Matrix

“Host/target” means source tests or target builds exist; it does not mean the
behavior has passed on physical signed-FOTA hardware.

| Failure | Detected by | Expected behavior | Current implementation status | Engineer action |
|---|---|---|---|---|
| Unknown, revoked, or quarantined Node | Hub registry/FOTA guard | Reject request; do not start transfer | Host guard tests and target build; not physical FOTA qualified | Verify exact physical identity and registry state; do not retry with a different identity implicitly |
| No authenticated session | Hub owner | Reject request | Host guard coverage/target build; not physically qualified | Restore association and authenticated rejoin first |
| Wrong or replaced session | Hub owner and C3 session binding | Abort pinned transfer; old session cannot continue | Host coverage and target build; not physically qualified | Establish a fresh session and start a new transfer ID |
| Replay or stale frame | Runtime security freshness/replay checks | Reject without advancing transfer | Runtime security host coverage and target build; not physically FOTA qualified | Capture session/sequence logs; do not resend stale encrypted frames manually |
| Tampered secure packet | AEAD open | Reject before FOTA receiver | Host security coverage and target build; not physical secure-FOTA qualified | Check key/session mismatch or RF/data corruption; start a fresh session if needed |
| Oversized or malformed packet | Secure-v2 decoder | Reject frame | Codec host tests and target build | Capture frame length/type; do not change the packet manually |
| Missing/out-of-order chunk | Receiver sequence/index check | Reject expected-index mismatch; sender retries boundedly | Host receiver coverage and target build; physical secure path pending | Retry a fresh transfer if the sender reports failure |
| Duplicate chunk | Receiver sequence check | Return duplicate status without writing bytes twice; sender can accept duplicate ACK for current data | Host coverage and target build | Check ACK loss/retry; preserve transfer/session evidence |
| Hub restart | Sender task/session lifecycle | Sender transaction is not durable; old session/transfer must not resume | Restart correctness not physically qualified for secure FOTA | Verify active C3 slot/version; establish fresh session and start a new transfer |
| C3 restart mid-transfer | C3 worker and OTA state | Volatile transfer state is lost; boot selection should remain on prior slot until successful END/commit | Target logic/build; physical secure interruption pending | Check active slot/version and health; restart with a new session/transfer |
| Transfer timeout | C3 receiver inactivity timer and Hub bounded retries | Abort writer, leave maintenance, fail transfer | Host and target build; physical secure timeout pending | Confirm Node data plane resumed; start a new transfer only after authenticated session is healthy |
| Queue/request/ACK failure | Bounded owner/control queues | Reject, drop or time out; no unverified ACK advances sender | Host seam/target build; exact physical secure queue pressure pending | Capture queue and transfer logs; wait for abort/cleanup before a new request |
| SHA-256 mismatch | Secure FOTA adapter | Abort before `esp_ota_end()`/boot selection | Host digest tests and target build; not physical | Preserve A, capture claimed and calculated digest evidence, rebuild the exact artifact |
| Wrong firmware signature | ESP-IDF verification inside `esp_ota_end()` | Finalize fails; no boot-slot commit | Offline signing/tamper check and target build; physical rejection pending | Verify A trust key and that the test reached signature verification; preserve A |
| Flash write failure | `esp_ota_write()` | Return write error and reset/abort transfer; do not select candidate | Host writer seam and target build; not physically injected | Preserve logs and current slot; service reflash only if current app is not operational |
| Lost final ACK | Hub sender timeout vs. C3 completion/restart | Sender may report failure even though C3 selected the slot and reboots; result can be ambiguous | Duplicate-END handling before reboot exists; physical secure behavior pending | Inspect active slot, boot/version, and app event before deciding whether to retry |
| New image fails to boot | ESP-IDF bootloader rollback | Boot previous valid image when rollback state/configuration permits | Rollback configured; failure branch not physically qualified | Capture reset reason and active slot; use service recovery if automatic return fails |
| Boot-health failure | Target health gate | Request invalid-image rollback/reboot by deadline | Target build and health success path previously physical on a different same-image raw campaign; failure path pending | Preserve boot logs; verify prior slot boots and do not mark failed image valid manually |
| Authenticated rejoin fails | Node/Hub security runtime | Node must not send normal traffic as authenticated until rejoin succeeds | Host/target integration; signed-update physical rejoin pending | Verify association and fresh session; use service recovery if owner cannot rejoin |
| Corrupt/invalid candidate image | Digest/signature/image validation | Reject before boot activation | Digest host/target and offline signature checks; physical candidate rejection pending | Keep known-good slot; record exact artifact hash and verifier result |

## 13. Automatic Rollback and Recovery

**Implemented:** `CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE=y` is in the C3
development configuration. A successful OTA selects the candidate slot; after
boot it is pending verification. The health task marks it valid only after
runtime owner start, PIR readiness, post-sensing runtime/radio evidence, no
active maintenance, and the minimum heap requirement. A 90-second health
deadline requests ESP-IDF rollback.

**Host/target-build verified:** The health decision logic and target API path
build. The gate has a physically observed success path in the historical
same-image HIL campaign.

**Physically verified:** Historical same-image raw FOTA boot-health success at
`evidence/hil/runs/20260924T094521.398370Z`, on firmware provenance `7bc2a33`.
That run did not exercise secure signed A→B or rollback failure.

**Not yet qualified:** Physical signature rejection, signed version upgrade,
health-timeout rollback, failed-candidate recovery, and repeated signed A/B
cycles. Do not treat an ACK loss as proof that update activation failed; inspect
slot and boot/version evidence.

## 14. Manual / Service Recovery

When OTA behavior is uncertain or the candidate will not boot:

1. Stop additional FOTA requests. Do not repeatedly write the candidate slot.
2. Preserve Hub and C3 serial logs, current version, reset reason, Node
   identity/session evidence, and active OTA slot if readable.
3. Identify the exact physical board and its current port through the existing
   fixture discovery/setup process; do not guess a port or use stale setup.
4. Preserve the failing image and its hashes. Determine whether ESP-IDF
   rejected signature/digest, whether boot selection changed, or whether the
   health gate requested rollback.
5. Restore a known-good image compatible with the device's signed-app trust
   anchor and partition table using an approved service flashing procedure.
   The repository currently has no dedicated signed-image service-reflash
   command. The signed build script does not flash; its ordinary build output
   is unsigned.
6. After recovery, verify app version, boot/reset evidence, sensing readiness,
   radio/session rejoin, and an acknowledged application event.
7. Recommission only if association state is actually lost or invalid. An
   ordinary reboot should not require pairing again.

For restoring the qualified HIL fixture, the existing self-contained command
is `make hil-checkpoint-smoke` from the product directory. It rebuilds/flashes
the HIL pair and runs smoke; it does not restore a signed production image or
qualify secure FOTA. The legacy `hil-checkpoint-fota` command uses raw FOTA.
Do not issue a destructive erase as an improvised recovery step.

## 15. Common Engineer Recipes

These recipes describe current tool support; steps marked **not available**
need a focused implementation before they can be run as written.

### A. New C3 initial flash

- For the HIL fixture, from the product directory run `make
  hil-checkpoint-smoke`; this owns fixture setup, preflight, build, flash, and
  smoke.
- For a signed first-install image, use the signed profile builder below, then
  follow the approved signed service flashing workflow. **That flashing command
  is not currently provided.** Do not flash the unsigned `.bin` as signed A.

### B. Build a signed candidate

From the product directory, with ESP-IDF v6.0.3 activated:

```bash
python3 scripts/build_signed_c3.py --signing-key /absolute/path/outside/repo/test-key.pem
```

The script builds one version, signs it, verifies it offline, and prints its
hash and size. It does not make a Hub image or flash hardware.

### C. Normal signed A→B update

**Not yet available as an end-to-end repository recipe.** The runtime pieces
exist, but tooling for distinct signed A/B versions, signed-image Hub
embedding, secure HIL trigger, and physical installation/qualification is
incomplete. Use the physical plan after that focused adaptation exists.

### D. Verify wrong-signature rejection

Offline signature tamper rejection has been demonstrated for the signed
artifact. The repeatable physical recipe is in the
[signed-FOTA qualification plan](../validation/PHASE2_SIGNED_FOTA_PHYSICAL_QUALIFICATION_PLAN.md).
No current command drives a wrong-signature image through physical secure
FOTA.

### E. Retry after interrupted FOTA

Do not resume a stale transfer ID or session. Let the receiver timeout/abort
or reboot cleanly, confirm the active slot and normal application state, then
establish a current authenticated session and request a new transfer from the
beginning. Automatic byte-offset resume is not implemented.

### F. Recover after failed candidate boot

Allow ESP-IDF rollback to run and capture the reset/version/slot evidence.
Confirm the prior image boots and performs normal authenticated operation. If
rollback does not return a functioning image, use the approved service
procedure; no physical failed-boot recipe is qualified yet.

### G. Service reflash to known-good image

Select a known-good artifact with the correct signed-app trust key and board
profile. Use the approved service flashing path for that artifact. The
repository has no dedicated signed service-reflash command today; do not
substitute `make hil-checkpoint-fota` or flash the unsigned build output.

## 16. Diagnostics and Troubleshooting

Capture these states together so a transfer can be reconstructed:

- Hub/C3 app version, image SHA-256, build/profile provenance, and device
  identities.
- Home/Node association and authenticated session before and after restart.
- FOTA transfer ID, message/chunk index, ACK status, retry count, and sender
  result.
- C3 control queue/maintenance state, bytes written, expected index, digest
  outcome, and `esp_ota_end()` result.
- Current/next OTA slot, boot/reset reason, pending/valid image state, and
  health-gate decision.
- Sensing-ready, authenticated rejoin, application event/ACK, retained and
  in-flight state, and free/minimum heap.

Useful existing logs include `Authenticated FOTA sender result`, `FOTA
maintenance`, `FOTA COMPLETE; next boot partition=...`, `esp_ota_write failed`,
`esp_ota_end failed`, `OTA image pending health validation`, `OTA image marked
VALID after sensing/runtime/radio health`, and `OTA health deadline expired;
requesting rollback`. Log wording can evolve; interpret it with source and
fresh boot/partition evidence.

Common diagnoses:

- **Request rejected immediately:** verify exact Node enrollment, revocation
  state, authenticated session, and request queue availability.
- **Secure FOTA `BEGIN` rejected by policy:** running C3 is built without
  signed-on-update or hardware Secure Boot; ordinary unsigned configuration
  deliberately fails closed.
- **C3 rejects board/session/transfer:** verify `esp32c3` board claim, session
  continuity, transfer ID, and fresh frame sequence. The current version
  claim is not complete board/version authorization.
- **Sender fails near the last ACK:** inspect C3 slot/version; the C3 might
  have selected the new slot before reboot and the final ACK may have been
  lost.
- **Image finalization fails:** distinguish CRC/SHA failure from
  `esp_ota_end()` signature/image validation failure using target logs.
- **Candidate boots but is rolled back:** inspect the 90-second health
  observations: owner, sensing-ready, post-sensing radio/runtime ticks,
  maintenance state, and minimum heap.
- **No session after boot:** verify association restore and authenticated
  rejoin; do not force normal traffic under the previous session.

## 17. Development vs Production Profiles

| Profile | FOTA path | Signing/boot policy | Qualification meaning |
|---|---|---|---|
| Legacy Phase-1 HIL/raw | Fixed raw packet path selected by `GS_HIL_BUILD`; UART/button controls can start the legacy sender. | HIL controls are compile-gated; not a signed secure-FOTA profile. | Existing HIL smoke/FOTA evidence applies only to the tested raw path and recorded firmware. |
| Ordinary unsigned development | Secure production route is compiled, but C3 rejects `BEGIN` when signed-image verification is disabled. | No signed-app requirement and no Secure Boot. | Target build only; secure FOTA remains fail-closed. |
| Signed-app-on-update profile | Secure receiver route is used with ESP-IDF signature verification enabled at OTA update. | RSA-3072 app signatures; external test key; no hardware Secure Boot/eFuse. | Current evidence is target build plus offline valid/tampered signature checks, not physical OTA. |
| Future production Secure Boot profile | Secure authenticated FOTA plus hardware anchored boot verification. | Requires explicit manufacturing, key custody, flash protection, and eFuse policy. | Not implemented or qualified by the current profile. |

The existing HIL profile still selects raw FOTA. The signed profile currently
builds with `GS_HIL_BUILD=OFF`, and its script rejects known HIL markers. A
focused secure-HIL build profile is needed to combine repeatable fixture
control with the secure target path without weakening production isolation.

## 18. Security-Key Handling

- Use only disposable test keys for development/qualification workflows unless
  a production key process has been separately approved.
- Keep signing private keys outside the repository and outside captured logs
  or qualification evidence.
- Record only the public-key fingerprint with image provenance.
- The current script requires an external key path and refuses a path inside
  the repository; Git also ignores generated signed build output/config.
- Production signing-key custody, rotation/recovery, manufacturing PKI, and
  publisher authorization are future productization decisions.
- Do not enable Secure Boot, flash encryption, or burn eFuses on prototype
  units as part of this guide.

## 19. Physical Qualification

This guide explains architecture, build/sign flow, operation, and recovery.
The formal physical procedure and case-level PASS/FAIL conditions are owned by
[`docs/validation/PHASE2_SIGNED_FOTA_PHYSICAL_QUALIFICATION_PLAN.md`](../validation/PHASE2_SIGNED_FOTA_PHYSICAL_QUALIFICATION_PLAN.md).

The historical `hil-checkpoint-fota` campaign executes the raw Phase-1 path.
Its PASS cannot be reused as secure signed-FOTA evidence. The physical plan
requires secure FOTA HIL adaptation first.

## 20. Current Known Limitations

- Physical signed A→B OTA has not been qualified.
- Physical bad-signature rejection and preservation of A have not been
  qualified.
- Physical failed-boot and rollback behavior has not been demonstrated.
- Board/version authorization and downgrade policy are incomplete; the FOTA
  `BEGIN` claims are not fully checked against embedded image metadata.
- Production signing-key custody and manufacturing provisioning are pending.
- Hardware Secure Boot/eFuse protection is not enabled.
- No external trusted product FOTA request/control channel is integrated.
- Multi-C3 FOTA and RF contention are not qualified.
- Signed A/B build orchestration, Hub embedding, and signed initial/service
  flashing commands are incomplete.

## 21. Engineer Safety / Do-Not-Do List

- Do not use raw HIL FOTA as proof of secure FOTA.
- Do not commit private keys or include them in logs/evidence.
- Do not burn eFuses on prototype boards.
- Do not call SHA-256 a publisher-authenticity mechanism.
- Do not call target-build or offline signature evidence physical
  qualification.
- Do not continue a transfer under a changed authenticated session.
- Do not activate an unsigned or untrusted candidate.
- Do not assume the signed-profile `idf.py flash` suggestion points at the
  signed artifact; the builder's normal app output is unsigned.
- Do not erase flash or improvise destructive recovery commands.

## 22. Related Files and References

Paths below are relative to
`code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/` unless marked
repository-root.

- `firmware/common/transport/fota_secure_wire.hpp/.cpp` — secure-v2 framing
  and bounds.
- `firmware/common/security/runtime_frame_security.hpp/.cpp` — runtime
  authenticated-frame security and freshness.
- `firmware/hub/components/fota/hub_fota_guard.hpp/.cpp` — exact enrolled
  Node/session authorization and transfer guard.
- `firmware/hub/target/esp32/hub_runtime_adapter.cpp` and
  `hub_security_link.cpp` — Hub owner, secure session, and radio route.
- `firmware/hub/target/esp32/idf/main/fota_sender.cpp/.hpp` — Hub sender,
  retries, embedded image, and internal request API.
- `firmware/hub/target/esp32/idf/main/CMakeLists.txt` — C3 image embedding.
- `firmware/node/fota/fota_receiver.cpp` and
  `secure_fota_adapter.cpp` — chunk receiver, digest, and secure protocol
  adaptation.
- `firmware/node/target/esp32c3/node_runtime_adapter.cpp` and
  `node_security_link.cpp` — C3 security owner and authenticated runtime.
- `firmware/node/target/esp32c3/idf/main/fota_receiver.cpp` — ESP-IDF OTA
  writer, signed-image fail-closed gate, and boot-health task.
- `firmware/node/fota/boot_health_gate.hpp/.cpp` — boot-health conditions.
- `firmware/node/target/esp32c3/idf/partitions.csv` — C3 OTA layout.
- `firmware/node/target/esp32c3/idf/sdkconfig.defaults` — ordinary C3 and
  rollback configuration.
- `firmware/node/target/esp32c3/idf/sdkconfig.signed.defaults` — signed-app
  profile.
- `scripts/build_signed_c3.py` — external-key signed C3 build and offline
  verification.
- `scripts/build_hw_pair.py` — normal Hub/C3 pair build and unsigned C3 image
  synchronization; it does not flash hardware.
- `tools/hil/qualify.py`, `tools/hil/phase1.py`, and `Makefile` — existing
  fixture supervisor and legacy raw FOTA command ownership.
- Repository-root `docs/validation/MASTER_TRACEABILITY.csv` — FOTA requirement
  and qualification status.
- Repository-root `docs/PHASE2_ARCHITECTURE_AND_GAP_ANALYSIS.md` — broader
  Phase-2 architecture and gap analysis.
- Repository-root `docs/validation/PHASE2_SIGNED_FOTA_PHYSICAL_QUALIFICATION_PLAN.md`
  — formal focused physical qualification procedure.
- Repository-root `evidence/hil/runs/20260924T094521.398370Z` — historical
  same-image raw FOTA evidence, not secure signed-FOTA evidence.

Implementation lineage for source history: `2480da58` added the bounded
secure-v2 codec; `670b38d` routed Hub FOTA through authenticated Node sessions;
`d85a404` added C3 authenticated admission; `eae4dc0` added streamed SHA-256
verification; `f4ce5a8` added the fail-closed signed-image gate; and `51e99e1`
added the external-key signed C3 profile. These commits identify implementation
history and are not physical qualification claims.
