# GS-58 / GS-177 customer Hub Wi-Fi onboarding — software checkpoint

Date: 2026-10-20. Source baseline: `7990fc0e6ef4f5b98a3b1a80d7263f6323dc0a66`; implementation commit: `1043827858609a1212e403ddf4d4494e90c6165e` on `feature/r1-commercial-baseline`. Source `code/` tree OID: `19f705568942d7e1e800fb67cc3b5ee30dd2992e`. Owning Jira: GS-58; Android surface: GS-177. This is a source and host-software checkpoint, not a claim of customer-ready provisioning, installed firmware or physical BLE/Wi-Fi acceptance.

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
- `PYTHONPATH=code/build/gs58_browser_pydeps python3 code/tests/pwa_68_browser_test.py`: NOT_RUN, Chrome/Chromium is absent on this WSL host. The pinned Python `websocket-client` dependency is available in an ignored build directory; the existing Android CI browser stage will run after push.
- ESP-IDF 6.0.3 standard S3 profile: `GS40_TEST_ONLY_CLOUDSYNC=OFF`, `CONFIG_ESP_TLS_USE_DS_PERIPHERAL=y`; `sdkconfig.defaults` SHA-256 `be0624e0d4efb47d6e3868a42c7a5925c5be1dea8520df644271ad2e66a4c024`, effective sdkconfig SHA-256 `79aa5a0b45b155a97e60feb1f93bc7b653b10d745aea932d57eac9f6bc5da27b`. The paired C3 *build asset* is historical GS-114 P8 (`5256779c8c0b592cea219f3e3a3d0c7da72892a37207399bfce388e549c25659`); it is not evidence of a current deployed C3 image. Final S3 image result is pending.
- Android CI workflow run `39437956269` is in progress on exact source commit `1043827`; it includes browser and Android registered stages. Record final result and APK hash below when available.

Physical acceptance is **NOT_RUN** for BLE identity/phone, actual S3 Wi-Fi scan, protected storage, AP association/change, C3 rejoin, cloud Home claim and caregiver freshness. GS-58/177 remain In Progress. The next implementation step is the approved D1 device-specific Security 2 proof and D2 encrypted-store provider, followed by an authorized image-matched S3/Android fixture run; no password submission is enabled before those gates.

## Pause and resume handoff — 2026-10-20

The implementation checkpoint is `1043827858609a1212e403ddf4d4494e90c6165e` on `feature/r1-commercial-baseline`; local and remote HEAD matched after push. Only this evidence file was modified after that checkpoint while the final validations were in flight. The pre-existing untracked PWA, ESP-IDF managed components, Zone.Identifier files and hardware evidence were not staged or changed. Recheck Git state and active writers at resume rather than assuming this line remains current.

Completed: bounded Hub scan/policy integration port, fail-closed current-authority and protected-store checks, Android discovery-only Settings route, GS-116 registration and GS-130 mapping. Existing station reconnect, C3 channel rejoin, caregiver Home and protected credential-store port were reused. Host results: GS-58 reconnect 77/77, onboarding 30/30 normal and ASAN/UBSAN, caregiver runtime 9/9, app test 34/34, validation framework 51/51, feature mapping 22/22. Local browser cases were NOT_RUN because Chrome/Chromium is absent in WSL. Android workflow `39437956269` first attempt failed 1/4 browser tests because its first Chrome DevTools endpoint did not start; the other 3 browser tests passed. A single failed-job rerun was started and its result was pending at this checkpoint. The final ESP-IDF 6.0.3 S3 non-flashing rebuild was also pending after a Ninja build-log-version mismatch caused dependency recompilation. No firmware was flashed; no phone, board, Windows network, production credential or backend was operated.

Open gates: D1 approved device-specific Security 2 pairing/installer authority; D2 verified encrypted NVS with per-device key custody and atomic recovery; authenticated current Hub/Home/epoch claim; production cloud origin and physical fixture qualification. No password entry or credential-bearing BLE flow is enabled; first-time setup and change-Wi-Fi remain SECURITY_BLOCKED. Android APK/source check and S3 final image hash must be recorded from actual finished jobs. Do not count a compile, host test or advertisement as authenticated customer provisioning.

Resume sequence: verify canonical worktree, branch, local/remote HEAD, tracked/untracked state and writer ownership; run context preflight; read this handoff, current Jira GS-58/177 and source. Collect ESP-IDF build exit, image size/hash and configuration; collect workflow `39437956269` rerun outcome and APK SHA if it passed. If browser startup fails again, retain FAIL and diagnose the Chrome launch/port evidence without weakening browser assertions. Update this handoff and `R1_WORK_STATE.md`, run `git diff --check`, commit only redacted evidence, push, verify remote equality, and post factual GS-58/177 Jira comments. Continue D1/D2 implementation only after those approved authority/key contracts exist.

### Ready-to-copy resume prompt

> Resume GS-58/GS-177 customer Hub Wi-Fi onboarding from `/home/udaybhan/projects/Ghar_sajag_r1` on `feature/r1-commercial-baseline`. Read AGENTS.md, run `tools/context/ghar_sajag_context_preflight.sh`, inspect Git/writers and this evidence file. Preserve all untracked evidence. Do not redo the committed discovery/policy work at `1043827`. Collect the in-flight ESP-IDF S3 build and Android workflow `39437956269` rerun results, resolve only concrete failures, record image/APK hashes and tests, complete R1_WORK_STATE and Jira GS-58/177, commit/push evidence and verify remote HEAD. Keep customer password submission and commercial provisioning disabled until D1 device-specific Security 2 authority, D2 protected encrypted storage and Home/epoch claim are approved and implemented. No hardware or production operations.
