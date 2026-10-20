# GS-58 / GS-177 customer Hub Wi-Fi onboarding — software checkpoint

Date: 2026-10-20. Source baseline: `7990fc0e6ef4f5b98a3b1a80d7263f6323dc0a66`; implementation commit: `1043827858609a1212e403ddf4d4494e90c6165e` on `feature/r1-commercial-baseline`. Evidence checkpoint: `ea94240c52a80d88709620a88248127bdb17250c`. Source `code/` tree OID: `19f705568942d7e1e800fb67cc3b5ee30dd2992e`. Owning Jira: GS-58; Android surface: GS-177. This is a source and host-software checkpoint, not a claim of customer-ready provisioning, installed firmware or physical BLE/Wi-Fi acceptance.

## Reuse and exact software boundary

| Part | Current result | Source |
|---|---|---|
| India radio profile and C3 channel rejoin | Existing; unchanged | `code/firmware/common/connectivity/india_wifi_profile.hpp`, GS-58 host test |
| Bounded S3 station reconnect | Existing; unchanged | `code/firmware/hub/connectivity/wifi_reconnect_policy.cpp` |
| Credential protection gate | Existing; protected atomic store interface only | `code/firmware/hub/connectivity/wifi_credential_store.hpp` |
| Hub-side network scan | New ESP-IDF 6.0.3 adapter; compiled, not exposed to a BLE client | `code/firmware/hub/target/esp32s3/esp_idf_wifi_setup_scanner.cpp` |
| Authorized setup policy | New host-tested gate: current authority generation, recent Hub scan, WPA2/WPA3 on IN channels 1–13, valid password, verified protected commit before reconnect | `code/firmware/hub/connectivity/wifi_onboarding.cpp` |
| Android Settings | New Add Hub entry; native bounded BLE discovery shows unverified setup-radio names, never requests or persists a password | `code/tools/sim/pwa/connected_lite.mjs`, `HubWifiSetupActivity.kt` |
| Credential-bearing BLE / Home claim | **SECURITY_BLOCKED**; no Security 2 session, device-specific proof, target encrypted store or claim provider is activated | GS-58 D1/D2; GS-109; GS-68/172 |

The Android native destination is an exact, parameter-free URL accepted only from the bundled first-party page. It is a discovery action, not a general JavaScript-to-native command bridge. Android 12+ requests Nearby Devices permissions and older supported versions request scan location permission; discovery stops after ten seconds or when the activity stops. Advertisement names are explicitly untrusted and are not used to authenticate or select an exact Hub. No BLE GATT credential transfer, password field or test credential fallback was added.

`WifiOnboarding` is a fail-closed integration port. It requires an approved implementation of `WifiSetupAuthority` that binds an exact physical Hub, device-specific installer proof, current Home/ownership epoch and a nonzero generation. A transfer, revocation or new session must change that generation. The existing production target supplies **no** such implementation; therefore its methods are not called from a live provisioning service. The guarded policy also requires a recent Hub-origin scan and the existing `WifiCredentialStore` protection result before a station-ready signal. It does not authorize a Home claim or CloudSync publication.

The ESP-IDF scanner is limited to twenty entries, 120 ms active dwell per channel, India 2.4 GHz channels 1–13, and no 5 GHz scan. It keeps SSID data in memory and logs none. Open, WEP, enterprise and unknown networks are excluded from the current password-based setup choices. Hidden SSIDs are not offered by this scan. Its RF coexistence and result behavior need physical qualification. The scanner is compiled into the S3 target but cannot be invoked by a customer without an approved BLE authority/session composition.

## Missing security contracts before a customer can enter a password

1. **D1 pairing and installer authority:** GS-165/172 and GS-109 must supply the exact per-device, non-public Security 2 username/verifier/proof lifecycle, authenticated Hub selection, initial claim and authorized change-network/recovery window. A MAC, advertisement or public QR lookup handle is insufficient. Use Espressif's managed `network_provisioning` component and compatible Android library only after that source is approved and pinned for ESP-IDF 6.0.3. [Espressif Security 2](https://docs.espressif.com/projects/esp-idf/en/v6.0.2/esp32/api-reference/provisioning/provisioning.html), [Espressif Android provisioning library](https://github.com/espressif/esp-idf-provisioning-android).
2. **D2 protected persistence:** GS-68/172 must approve the per-device encrypted-NVS key/partition provider and atomic replace/recovery semantics. No plaintext persistent or RAM-only fallback may claim restart recovery. A rejected or ambiguous commit must preserve the last verified credential and cannot trigger reconnect.
3. **Cloud/Home claim:** the existing GS-109/68/148 authority and TLS path must authenticate the Hub and current Home/epoch before Android presents authenticated monitoring readiness. Wi-Fi association, DHCP, Internet and cloud authentication are distinct observations. A stable commercial HTTPS origin is still separate from the laptop TEST_ONLY endpoint.

No commercial credential, eFuse, NVS partition or cloud endpoint was created or changed. No board or phone was accessed. Add C3 Node remains the separate GS-109 operation.

## Physical qualification prerequisites and proposed order

The next authorized fixture run needs an exact, image-verified S3 N16R8 Hub, a source-matched Android APK, an isolated 2.4 GHz WPA2/WPA3 access point on an IN channel, a distinct enrolled C3 for rejoin observation, and an isolated authenticated backend. Before entering any Wi-Fi password, the fixture must also have the approved D1 device-specific Security 2 pairing proof and installer/Home authority, the D2 verified per-device encrypted credential store with recovery evidence, and current GS-109 Hub/Home/epoch claim. The approved provider must implement an atomic current-binding generation and fence transfer/revocation during scan and commit.

After those gates, run first-time setup, wrong/expired proof, unsupported and hidden network behavior, wrong password, DHCP/Internet/cloud-auth distinctions, failed replacement retaining the prior working network, power interruption and reboot recovery, C3 authenticated channel rejoin with pending events retained, and caregiver freshness/UNKNOWN checks. Record the exact image and APK hashes, fixture identity privately, Home/epoch source, Wi-Fi channel and association state, backend receipt and caregiver projection separately. No software check in this document qualifies these physical outcomes.

## Validation and limits

- `make -C code gs58-wifi-host-test gs58-onboarding-host-test`: 77 existing + 28 new checks PASS at the preceding checkpoint; final `make -C code gs58-onboarding-host-test`: 30/30 PASS after adding scan invalidation checks.
- New onboarding test under ASAN/UBSAN: 30 checks PASS, including revocation during scan and during protected replacement, then refusal to reuse the invalidated scan.
- `node --test code/tests/js/caregiver_runtime.test.mjs`: 9/9 PASS.
- `make -C code app-test`: 34/34 PASS.
- `make -C code feature-coverage-test`: 222 features, 269 modules, 26 physical cases; 22/22 mapping tests PASS. Registration consistency is not semantic or physical proof.
- `make -C code validation-framework-test`: 51/51 PASS, including registered-stage failure propagation.
- `PYTHONPATH=code/build/gs58_browser_pydeps python3 code/tests/pwa_68_browser_test.py`: NOT_RUN, Chrome/Chromium is absent on this WSL host. The pinned Python `websocket-client` dependency is available in an ignored build directory. Existing Android CI browser stage completed 4/4 PASS with 92/92 catalogue assertions on the implementation commit; this does not replace local browser execution.
- ESP-IDF 6.0.3 standard S3 profile: `GS40_TEST_ONLY_CLOUDSYNC=OFF`, `CONFIG_ESP_TLS_USE_DS_PERIPHERAL=y`, 16 MiB flash, development partition table. `sdkconfig.defaults` SHA-256 `be0624e0d4efb47d6e3868a42c7a5925c5be1dea8520df644271ad2e66a4c024`; effective build sdkconfig SHA-256 `79aa5a0b45b155a97e60feb1f93bc7b653b10d745aea932d57eac9f6bc5da27b`. Final no-flash `idf.py build` verification exited 0; app-size check passed at 2,191,664 bytes (0x217130), leaving 2,002,640 bytes in the 4 MiB app partition. The app binary SHA-256 is `5416a715fc3862977aed9584534c53c3b6726fa888599ee973930df67dee75c3`; `esptool v5.4.0 image-info` validated the ESP32-S3 image checksum and validation digest `d47429105d7b2499ffbb00963372a8408d2c0adfdb546e299ce59ba54affc38f`. Embedded app version is `ea94240`; source code tree remains `19f705568942d7e1e800fb67cc3b5ee30dd2992e`, matching the implementation tree. This is build evidence only. The paired C3 *build asset* remains historical GS-114 P8 (`5256779c8c0b592cea219f3e3a3d0c7da72892a37207399bfce388e549c25659`); it is not evidence of a current deployed C3 image.
- Android CI workflow run `39437956269` completed SUCCESS on exact implementation source commit `1043827858609a1212e403ddf4d4494e90c6165e` after one failed-job rerun. Browser suite passed 4/4 and catalogue assertions passed 92/92; registered caregiver API 20, Android dashboard 9 and voice prototype 26 passed. The downloaded runner-signed debug APK is 2,923,446 bytes, SHA-256 `6c12a4439636b0ea9f9a762cdf4f99d41b16fc4dc8f4c9fbb6674d7a9c83a757`; it targets Render staging (`https://parivar-saathi-lite-staging.onrender.com`, laptop-LAN TEST_ONLY flag off), not the laptop server. It was not installed or observed on a physical phone. The first CI attempt had one browser startup failure (DevTools endpoint startup); the single rerun succeeded. Local browser tests remain NOT_RUN because Chrome/Chromium is unavailable in WSL.

Physical acceptance is **NOT_RUN** for BLE identity/phone, actual S3 Wi-Fi scan, protected storage, AP association/change, C3 rejoin, cloud Home claim and caregiver freshness. GS-58/177 remain In Progress. The next implementation step is the approved D1 device-specific Security 2 proof and D2 encrypted-store provider, followed by an authorized image-matched S3/Android fixture run; no password submission is enabled before those gates.

## Pause and resume handoff — 2026-10-20 (updated after validation)

The implementation commit `1043827858609a1212e403ddf4d4494e90c6165e` and evidence checkpoint `ea94240c52a80d88709620a88248127bdb17250c` are pushed. Local and fetched remote branch pointed to `ea94240` at resume. Tracked worktree was clean before this handoff update. Existing untracked PWA, ESP-IDF managed components, generated sdkconfig, Zone.Identifier files, historical C8/GS-114 evidence, and other hardware evidence remain untouched and unstaged. Filesystem is read-write with 892 GiB available; `git fsck --no-reflogs` exited 0 (reported pre-existing dangling objects, no integrity errors); context preflight PASS. No firmware build process remained active before final build verification.

Completed: bounded Hub scan/policy integration port, fail-closed current-authority and protected-store checks, Android discovery-only Settings route, GS-116 registration and GS-130 mapping. Existing station reconnect, C3 channel rejoin, caregiver Home and protected credential-store port were reused. Host results: GS-58 reconnect 77/77, onboarding 30/30 normal and ASAN/UBSAN, caregiver runtime 9/9, app test 34/34, validation framework 51/51, feature mapping 22/22. Android CI `39437956269` completed SUCCESS after one failed-job rerun: browser 4/4, browser catalogue 92/92, caregiver API 20, Android dashboard 9, voice prototype 26. Runner-signed debug APK: 2,923,446 bytes, SHA-256 `6c12a4439636b0ea9f9a762cdf4f99d41b16fc4dc8f4c9fbb6674d7a9c83a757`; it targets Render, not laptop LAN, and was not installed. Local browser remains NOT_RUN because Chrome/Chromium is absent. ESP-IDF 6.0.3 no-flash S3 build verification exited 0; image is 2,191,664 bytes, SHA-256 `5416a715fc3862977aed9584534c53c3b6726fa888599ee973930df67dee75c3`, image validation digest `d47429105d7b2499ffbb00963372a8408d2c0adfdb546e299ce59ba54affc38f`, app version `ea94240`, and effective sdkconfig hash `79aa5a0b45b155a97e60feb1f93bc7b653b10d745aea932d57eac9f6bc5da27b`. This did not compile/execute hardware in the current verification command; it validated the source-matched existing build tree and size targets. No firmware was flashed; no phone, board, Windows network, production credential or backend was operated.

Open gates: D1 approved device-specific Security 2 pairing/installer authority; D2 verified encrypted NVS with per-device key custody and atomic recovery; authenticated current Hub/Home/epoch claim; production cloud origin and physical fixture qualification. No password entry or credential-bearing BLE flow is enabled; first-time setup and change-Wi-Fi remain SECURITY_BLOCKED. APK and firmware results are software build evidence only; do not count them as installation, physical phone behavior, actual S3 execution or authenticated customer provisioning.

Resume sequence: the preceding documentation/work-state checkpoint is `82bdcafae17d7fd7376c55c530910f280c931034`; follow-up Jira comments 11487 (GS-58) and 11488 (GS-177) record the validation results. Do not re-run the successful build or CI. Any later D1/D2 work requires the device-specific Security 2 authority and encrypted credential-storage contract; no physical or network operation is currently authorized.

### Ready-to-copy resume prompt

> Resume GS-58/GS-177 from the latest canonical evidence commit. Read AGENTS.md, this handoff and R1_WORK_STATE; verify current branch/HEAD/remote and preserve all untracked evidence. Do not repeat the completed host tests, successful Android CI, or no-flash S3 build. The next action is documentation checkpoint delivery and factual Jira updates. Keep customer password submission and commercial provisioning disabled until D1 device-specific Security 2 authority, D2 protected encrypted storage and Home/epoch claim are approved and implemented. No hardware or production operations.

## GS-58 Phase 2 D1/D2 implementation decision packet — 2026-10-20

**Disposition: PROPOSED, not approved or LOCKED.** This section records a
minimum pilot design for 50–100 Hubs, based on the current interfaces and the
owner's GS-58 comments 11482/11485 and GS-177 comment 11486. It does not enable
credential-bearing provisioning, modify firmware configuration/partitions, or
change GS-D031/GS-D032. Production and physical status remain blocked/NOT_RUN.

### D1 — per-Hub BLE pairing plus current-owner authorization

**Recommendation.** Reuse Espressif's BLE `network_provisioning` component with
Protocomm Security 2 only. Security 2 uses SRP6a to establish an authenticated
session and AES-GCM to protect messages. The Hub stores the SRP salt/verifier;
the phone needs the corresponding per-Hub username/proof. Pin the device to
Security 2: reject absent/unknown security version and Security 0/1, with no
downgrade or fallback. This protects the local session and proves possession of
a Hub-specific setup secret; it does **not** authorize a user, Home, ownership
epoch, Hub transfer, or CloudSync.

ESP-IDF 6 moved provisioning out of ESP-IDF into the separately managed
`espressif/network_provisioning` component. Candidate version 1.2.4 declares
ESP-IDF >=5.1 and is a reasonable IDF 6.0.3 build candidate, not a verified
project dependency. Candidate Android library is
`espressif/esp-idf-provisioning-android` 2.4.4 (Android API 26+); both versions
still require source/security review, pinning and project CI before adoption.

**Factory and exact identity.** Keep the existing GS-168 registry as the source
of permanent Hub identity; do not add an issuer or identity registry. An
authorized station generates a fresh, CSPRNG-derived per-Hub setup secret with
at least 128 bits of entropy and the matching Security 2 salt/verifier. The
HubId is the Security 2 username/registry binding, not a secret. Load the
verifier and permanent HubId through the approved secure manufacturing path;
deliver the secret once on a sealed/scratch-off insert kept separate from a
public QR/serial label. A QR may contain only a public lookup/reference. Never
log, retain in an ordinary QA report, or commit the setup secret. Station
records contain HubId, verifier fingerprint/generation, operator/fixture
receipt and disposition only; zeroize working buffers and quarantine failed
units. Security 2 verifier storage depends on D2 and is not safely deployable
on the current unencrypted development profile.

**Owner/Home authority.** After login, only a Home Owner or explicitly
authorized Installer with Hub-setup permission may request a setup permit.
The phone may use mobile data while the Hub's prior router is offline. After
Security 2 establishes the exact local Hub session, the Hub supplies a fresh
random challenge, boot-generation value, permanent HubId and operation
(`INITIAL_CLAIM` or `CHANGE_WIFI`). The app sends that challenge and the
authenticated account session to the existing GS-109 ownership authority.
That authority verifies the GS-168 Hub registry state, current Home, owner,
ownership epoch, enrollment generation, revocation/transfer state and the
requesting user's role, then issues a one-use, purpose-bound permit containing
those bindings and the challenge. The Hub verifies the permit with the
GS-109-approved authority key and exact Hub identity, consumes the nonce once,
and enforces a local monotonic session deadline. Reboot invalidates outstanding
challenges. The current `WifiSetupAuthority` port can enforce an immutable
session generation but has no production provider, permit format, signer or
key pin; those must come from the existing GS-109 authority contract. Do not
reuse the GS-168 TLS issuer or FOTA signing key for setup permits. If GS-109
has no purpose-separated signing capability, approve the smallest dedicated
permit-signing key and trust anchor; do not create a second general PKI.

**Lease and race policy.** The target has no trusted wall clock before Wi-Fi,
so permit validity must not depend on SNTP or a phone timestamp. Bind issuance
to the fresh target challenge and boot generation, and bound the target's full
setup operation by monotonic time measured from challenge creation. The server
must serialize transfer/revocation against an outstanding short-lived permit;
otherwise an offline Hub cannot learn that ownership changed after issuance.
Recommend a maximum five-minute setup lease and block a competing transfer
until expiry/consumption. These are proposed limits, not approved policy. Once
network returns, the Hub must refresh current Home/epoch and revocation before
CloudSync or monitoring readiness. Wi-Fi association never implies
`INTERNET_REACHABLE`, `CLOUD_AUTHENTICATED`, `HOME_CLAIMED` or
`MONITORING_FRESH`.

**Recovery and threat boundary.** A neighboring phone with only the BLE name,
MAC, public QR or HubId cannot authenticate or obtain a permit. A phone with
the sealed proof but no authorized account cannot claim/configure a Home. A
logged-in authorized owner can use cellular data to change Wi-Fi while the old
router is unavailable. If both the old router and phone Internet are
unavailable, do not accept stale cached Home authority; require an approved
attended service/recovery flow. A lost phone is recovered by account login on
another phone. Lost setup proof or a transferred Hub requires current-owner
verification and attended proof rotation/reissue with registry epoch/revocation
update; factory reset, public QR or old-owner offline access is not recovery.

**Alternatives rejected.** Security 0, public QR/MAC/device-name authorization,
universal PoP, advertisement-only identity and custom GATT cryptography are
rejected. Security 1 is not selected because owner direction prefers Security 2
and there is no reviewed reason to add a second mode. SoftAP adds an unneeded
transport and does not solve owner/Home authorization.

### D2 — protected, recoverable Wi-Fi credential storage

**Recommendation.** Reuse ESP-IDF encrypted NVS with the Flash-Encryption-based
NVS key protection scheme, after GS-68/GS-172 approve and execute the existing
Secure Boot/Flash Encryption sequence. Allocate the documented 4 KiB `nvs_keys`
partition marked encrypted and a supported NVS data partition in the reviewed
commercial layout. Generate each device's NVS XTS keys only in an explicit,
authorized manufacturing/first-provisioning step after Flash Encryption is
confirmed active; keep them on-device, do not export them, and record only a
sanitized provisioning receipt. Normal application startup must load an
existing security configuration and call secure NVS initialization; it must
never auto-generate keys, auto-format NVS, or recover by erasing. A missing,
malformed or unreadable key partition leaves Wi-Fi setup disabled. Use
`WIFI_STORAGE_RAM` for the ESP-IDF station so it does not independently persist
a second credential copy in default NVS; the GS-58 store is the only credential
persistence path. Encrypt every NVS partition that may contain credentials or
pairing-verifier material. The current development partition table lacks
`nvs_keys`, its untracked effective `sdkconfig` has NVS encryption off, and
neither file is changed by this proposal.

**Atomic replacement model.** Keep a versioned credential record in two slots
and a separately committed active-slot/generation selector, all inside the
approved encrypted partition. Validate SSID/password bounds before writing;
write the inactive slot, commit, read back and validate it, then commit the
selector. Preserve the former active slot until the selector is verified. Only
an unambiguous successful selector commit returns `Ok` and triggers the
existing station reconnect. A rejected write leaves the old selector/record
active. An ambiguous commit returns `CommitOutcomeUnknown`, triggers no
reconnect, and is resolved only by reopening NVS and validating the committed
selector and both slots after restart; never guess the newest generation. A
corrupt selector, missing key, impossible generation, or invalid selected
record fails closed without falling back to stale credentials or reformatting.
The two-slot layout bounds retained history to current plus one previous
credential. Whether/when the previous slot is purged after the new network
associates needs product/security approval; no unbounded credential history is
permitted. Keep passwords only in bounded RAM buffers, clear them after use,
and redact all logs, crash output and diagnostic exports.

Encrypted NVS protects confidentiality and recognized read/modify/add against
an attacker without its key, but it does not prevent flash erase. It is not a
claim of malicious full-flash rollback protection; retain GS-D029's stated
rollback boundary. Do not choose the HMAC NVS scheme for this pilot: it consumes
an additional HMAC_UP eFuse key, and normal `nvs_flash_init()` may generate and
program that key when absent. A secure element or custom file-encryption
framework adds hardware/key infrastructure without a demonstrated need for
the first 50–100 units.

**Alternatives considered.** Plain/default NVS, Wi-Fi-driver persistence,
plaintext files and host-side firmware constants are rejected. HMAC-derived
NVS keys are rejected in favor of reusing the Flash Encryption trust boundary.
A custom encrypted file store is unnecessary while the existing
`WifiCredentialStore` and NVS API can implement the two-slot transaction.

### Approval matrix and qualification sequence

| Decision | Recommendation | Approval needed before enabling |
|---|---|---|
| D1 pairing scheme | ESP-IDF Security 2 only; unique >=128-bit per-Hub proof; verifier bound to permanent GS-168 HubId | GS-68 security + GS-172 manufacturing approve proof generation, storage, sealed delivery, rotation, retry/window limits and exact pinned component/client versions |
| D1 owner permit | GS-109 current-owner service issues one-use challenge/boot-generation/Home/epoch/operation permit; max five-minute lease proposed | GS-109/security approve claims, signer/trust key and purpose separation, transfer/revocation race lock, phone-online requirement, time/replay behavior and recovery authority |
| D2 storage/key lifecycle | ESP-IDF NVS encryption protected by the approved per-device Flash Encryption key; target-generated NVS XTS keys only in explicit controlled provisioning; secure read-only runtime init | GS-68/172 approve Secure Boot/FE sequence, exact eFuse/key custody and verification, `nvs_keys` and NVS partition map, first-boot authorization and recovery/rotation handling |
| D2 record recovery | Two encrypted credential slots + committed selector; no autoformat or stale fallback; one previous slot maximum | Product/security approve when old credentials are purged, failed-association retry UX and limits of erase/rollback recovery |
| Android transport | Espressif Android provisioning library candidate; native password/transport path only after permit | GS-177/security review pinned source/dependency, Security 2 downgrade behavior, permission, memory-zeroization/logging, lifecycle and accessibility tests |

**Acceptance tests before customer activation.** Host tests: permit
signature/HubId/Home/epoch/operation mismatch; unauthorized role; nonce replay;
wrong boot generation; expired monotonic session; duplicate sessions;
transfer/revocation races; lost/rotated proof; Security 0/1/missing-version
rejection; malformed/oversized scan and credentials. Store fault injection:
failure before data write, during slot write, after data commit, before selector,
selector commit unknown, restart at each boundary, corrupt/missing key/slot/
selector, rejected candidate preserving the former active record, no reconnect
before verified activation, and no plaintext output. Android: runtime permission
denial, exact Hub confirmation only after Security 2, Hub-scanned SSID list, no
password before permit, cancel/disconnect/app death, no password in
WebView/storage/logs, no downgrade, and correct distinct status rendering.
Target qualification: reviewed commercial image and partition, actual
per-device key status, flash-read confidentiality checks, power interruption/
reboot recovery, incorrect password/AP unavailable, old-credential recovery,
revocation/transfer, and C3 pending-event/rejoin retention. Physical cases need
separately authorized, identified fixtures; none ran in this task.

### Evidence and implementation disposition

The code at this checkpoint already has `WifiSetupAuthority`,
`WifiCredentialStoreBackend`, `WifiCredentialStore`, `WifiOnboarding`, the
bounded S3 scanner and Android discovery-only screen. The host policy requires
current authority generation, a fresh Hub scan and `EncryptedWithVerifiedDeviceKey`
before reconnect; no production provider, Security 2 session, permit verifier,
NVS key partition or credential-bearing Android transport exists. I made no
source, dependency, partition or effective configuration change because doing
so would pre-empt the unresolved D1/D2 trust/key decisions. This is not a claim
that design alone completes customer onboarding.

Focused current-source check: `make -C code gs58-onboarding-host-test` —
**30/30 PASS**, exit 0. Previously recorded, unchanged evidence remains:
reconnect 77/77, onboarding ASAN/UBSAN 30/30, app 34/34, framework 51/51,
traceability 22/22, S3 no-flash build PASS and Android Actions 39437956269
SUCCESS. These do not prove target credential storage, BLE provisioning,
physical phone operation or commercial acceptance. No Android CI, firmware
build, full validation campaign, physical device, production authority, key,
eFuse, router or network operation was run in this continuation.

Technical references: [ESP-IDF 6.0.3 NVS encryption guide](https://docs.espressif.com/projects/esp-idf/en/v6.0.3/esp32s3/api-reference/storage/nvs_encryption.html), [ESP-IDF 6.0.3 NVS API](https://docs.espressif.com/projects/esp-idf/en/v6.0.3/esp32s3/api-reference/storage/nvs_flash.html), [ESP-IDF 6.0 migration: provisioning moved to the managed `network_provisioning` component](https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/migration-guides/release-6.x/6.0/provisioning.html), [ESP-IDF Security 2 description](https://docs.espressif.com/projects/esp-idf/en/v6.0.2/esp32/api-reference/provisioning/provisioning.html#security-schemes), [network_provisioning v1.2.4 dependency metadata](https://components.espressif.com/components/espressif/network_provisioning/versions/1.2.4/dependencies?language=en), and [Espressif Android provisioning library](https://github.com/espressif/esp-idf-provisioning-android).

Canonical local/remote source was `e7f8a88631aab0f88686ee44bf9b5c4b2da67a1d`; context preflight PASS. The focused test is against unchanged production policy at that source. This proposal does not change `CONTEXT_VERSION`; all listed design decisions remain PROPOSED until approved.

## GS-58 Phase 3 secure software implementation checkpoint — 2026-10-20

This checkpoint implements host-testable portions of the existing D1/D2
proposal. It does **not** approve or activate D1, D2, commercial provisioning,
or an Android credential flow.

### Implemented source

- `wifi_credential_slots.*` adds a bounded two-slot/generation-selector
  transaction behind `WifiCredentialStoreBackend`. It writes the inactive
  slot, verifies exact readback, then changes the selector; faults do not
  retire a previously selected record. Ambiguous selector outcomes are
  accepted only when a reread proves the exact new generation. The fixed
  record/selector CRC detects accidental corruption only; it is not a MAC or a
  malicious rollback defense.
- `esp_idf_encrypted_wifi_credential_slots.*` adds an ESP-IDF 6.0.3 encrypted
  NVS storage adapter. Initialization requires Secure Boot and Flash
  Encryption already enabled, an encrypted NVS key partition, a dedicated
  writable NVS partition of at least three 4 KiB pages, and an injected
  device-key fingerprint verifier. It reads existing NVS security material
  and uses secure initialization; it does not generate keys, format/erase
  storage, or touch eFuses. The adapter was compiled only. It is not
  instantiated by the product startup, and the current development profile
  has no approved `nvs_keys`/credential partition or key custody.
- `wifi_setup_permit_gate.*` adapts the existing `WifiSetupAuthority` seam to
  an injected GS-109 one-use permit verifier. It binds the permit to the
  permanent Hub, Home, ownership epoch, operation, 32-byte nonce, boot
  generation and authenticated Security 2 session ID. The challenge age is
  bounded to 30 seconds; the test implementation caps the monotonic permit
  lifetime at 120 seconds from challenge creation. This is a stricter software
  test bound than the five-minute maximum in the earlier PROPOSED packet, not
  a newly approved product policy. The signature format, trust anchor, verifier
  implementation, transfer/revocation race policy and key lifecycle remain
  owned by GS-109/security and unimplemented here.
- `WifiOnboarding::commit` completes/closes a one-use authority session only
  after the protected credential store reports a verified commit and the
  current generation still matches; only then does it notify the existing
  reconnect path. No reconnect occurs on rejected or ambiguous store results.
- The existing Android discovery-only screen remains intact. A small native
  policy predicate and unit test describe the Security 2/identity/permit/store
  prerequisites, but no Protocomm Security 2 client, Hub Wi-Fi result display,
  password UI, or credential submission path is wired. The predicate is not
  authentication evidence; the Hub must independently enforce the permit.

No managed provisioning dependency or Android provisioning library was added.
The earlier investigation found the ESP-IDF 6.x managed provisioning boundary
and candidate libraries, but did not establish a reviewed end-to-end Security 2
integration compatible with the existing secret-handling constraints. The
current firmware/Android provisioning path therefore remains disabled rather
than adopting an unverified fallback. Existing India scan/reconnect policy is
reused; no parallel Wi-Fi manager, registry, issuer, or commissioning protocol
was introduced.

### Focused validation

Executed on the Phase 3 working source:

| Command | Result |
|---|---:|
| `make gs58-credential-slots-host-test` | 18/18 PASS |
| credential-slot host test with ASAN/UBSAN | 18/18 PASS |
| `make gs58-setup-permit-host-test` | 30/30 PASS |
| setup-permit host test with ASAN/UBSAN | 30/30 PASS |
| `make gs58-onboarding-host-test` | 30/30 PASS |
| onboarding host test with ASAN/UBSAN | 30/30 PASS |
| `make gs58-wifi-host-test` | 77/77 PASS |
| `make validation-framework-test` | 51/51 PASS after stage ownership correction |
| `make feature-coverage-test` | 22/22 mapping assertions PASS; traceability consistency reports 222 features, 275 modules, 26 physical cases |

The initial registration check caught an invalid `security` component label and
stage/command ordering mismatch; these metadata errors were corrected without
weakening test or traceability assertions. A missing malformed-verifier-id
length case was added to setup-permit coverage, raising it from 29 to 30
assertions; its normal and ASAN/UBSAN runs pass. The final framework and mapping
checks pass. Android Kotlin validation is delegated to the existing Android
GitHub Actions workflow because Java/Gradle are not installed in this WSL
environment. Physical BLE, encrypted-NVS, real phone, and commercial setup
tests are NOT_RUN.

### Target build and remaining gates

ESP-IDF 6.0.3 non-flashing C3 and S3 builds use separate `/var/tmp` build and
sdkconfig directories; the C3 image is the S3 project's paired Node asset. The
S3 profile is `GS40_TEST_ONLY_CLOUDSYNC=OFF`. Both builds completed successfully
and neither flashed nor accessed a board. Exact source/image/configuration
hashes and the remaining gates are recorded in the Phase 3 closeout below.

D1/D2 remain PROPOSED. Production pairing proof, GS-109 signing/trust
distribution, transfer/revocation serialization, Security 2 framework/client
pin review, Secure Boot/Flash Encryption and NVS key custody, commercial
partition geometry, old-credential recovery/purge policy, current Home claim,
real Hub scan and credential-bearing Android transport all remain gates.
Existing GS-58/GS-177 tickets remain In Progress; physical qualification stays
NOT_RUN. No context version or locked product decision changed.

### Phase 3 closeout — source commit `99142b8c3a939ff5a8875fe8c850d97eb7a66fa2`

The source/test/registry commit was pushed to the canonical branch. The
source-bound no-flash build used that code commit and the paired C3 image built
from the same source checkout. At build time the only tracked working-tree
change was this evidence document, so ESP-IDF's project version string carries
`99142b8-dirty`; no firmware source or build input was dirty. Full artifact
hashes and configuration fingerprints below are the authoritative provenance.

| Artifact / input | Result |
|---|---|
| ESP-IDF | v6.0.3 |
| S3 `gs_r1_s3_hub.bin` | 2,193,248 bytes; SHA-256 `79449e37837591c26ed1a05711a7b0c0fff24d5b24bf1236aff9b276dd19d138` |
| S3 ESP image validation digest | `67664f95c2f06de2cbac603c89b08bb304a8a4df977eaf25fd9bdcd691ee70f3` (valid) |
| Paired C3 `gs_hw_m1_node.bin` | 940,608 bytes; SHA-256 `2401c650fc58e517bfdbcbc91950a4bbde72a94444c92928dd590eb1f545e0ec` |
| C3 ESP image validation digest | `e180999cada060e8c62b812b391a5d55b70a2d89cad0501fbf9303439658816d` (valid) |
| S3 effective sdkconfig | SHA-256 `79aa5a0b45b155a97e60feb1f93bc7b653b10d745aea932d57eac9f6bc5da27b` |
| S3 CMake cache/profile | SHA-256 `52219cd12310b54fbd3213748693fab754c0945575892058ef8ef34c4d599d9d` |
| Generated GS-40 config fingerprint | `fdbf961f544afc16112ddf9a640248d6bf00adaa1acb25c0f4b41641829af862` |
| S3 partition table | SHA-256 `4828fb04f0569bcc5ffafaf887bb7f360e6ab858ec29df00297671f5f2a468fe` |
| Paired C3 embedded asset | byte-for-byte match with the C3 build artifact (verified with `cmp`) |

The S3 image is compatible with the development 4 MiB app slot (`0x400000`);
ESP-IDF reports 48% slot space free. The effective build selects 16 MiB flash
and `GS40_TEST_ONLY_CLOUDSYNC=OFF`. Secure Boot and Flash Encryption are not
enabled in this development profile. The new encrypted-NVS adapter therefore
cannot initialize in this profile: it requires both protections, the expected
encrypted NVS key partition, a dedicated data partition, and a separately
injected device-key fingerprint verifier. The target adapter compiles but is
not composed into startup. The image is not a provisioning-ready or physical
test candidate. No board, phone, eFuse, credential, router, production endpoint
or persistent device storage was accessed.

The final affected host results on commit `99142b8` are: credential slots
18/18 normal and ASAN/UBSAN; setup permit 30/30 normal and ASAN/UBSAN; onboarding
30/30 normal and ASAN/UBSAN; reconnect 77/77; validation framework 51/51;
feature traceability 222 features / 275 modules / 26 physical cases, with
22/22 mapping tests. All commands exited 0. `git diff --check` passed. The
Android workflow run `39479165553` completed SUCCESS on the exact source
commit. Its registered Android unit-test and `assembleDebug` steps passed; PWA
browser E2E was 92/92, including authenticated Home and offline regressions.
The runner-generated APK is 2,925,210 bytes, SHA-256
`a3dbd873a08936e120c388cce9a30f2e68f5810a09c641cf98fdaf62a91ac493`, package
`in.gharsajag.caregiver`, version `0.4.0-connected-lite-staging`, source
`99142b8`, Render staging origin, and `gs179_local_lan_test_only=0`; it was not
installed on a phone and is not the laptop-LAN APK. Full `validation-fast`,
`release-gate-final`, physical BLE, credential replacement on hardware,
Android phone acceptance and commercial qualification were not run.

D1/D2 remain PROPOSED: per-Hub proof creation/delivery/recovery and GS-109
permit signer/trust distribution, expiry and ownership-transfer race behavior
need security approval; Secure Boot/Flash Encryption/eNVS key custody,
partition geometry and credential rotation/recovery/purge semantics need
GS-68/GS-172 approval. The credential-bearing Android Security 2 flow and the
target session/authority composition remain disabled. GS-58 and GS-177 remain
In Progress. Android Actions run `39479165553` passed for the source commit;
this does not qualify an Android phone or enable provisioning. Physical case
`PHY-GS58-WIFI-01` remains NOT_RUN.
