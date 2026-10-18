# Parivar Saathi caregiver Android + voice integration package

**Engineering checkpoint:** 2026-10-17. **Status: INDEPENDENT PROTOTYPE / NOT PRODUCTION / NOT MERGED.**

This is a self-contained, non-destructive parallel work package prepared by inspection of the `Ghar_sajag` canonical branch at `29890b36a753ffdc46d7be9399a4a6cbed97d727`. It does not edit `feature/r1-commercial-baseline`, GS-40, any existing physical C3/S3 board, or the user's WSL tree. Current canonical HEAD may move independently.

## What is actually implemented

- **Existing UI reuse:** Android Kotlin WebView shell loads the existing backend-driven Parivar Saathi PWA from a configured HTTPS origin, including the same Home, Devices, Reports, Settings and navigation. It does not fork PWA UI, fake local data or ship a second dashboard.
- **Native Android FCM invitation handling:** foreground/background Firebase data-message callback posts high-importance, user-visible incoming call invitation; clicking opens an Android `CallActivity` with a dedicated same-origin WebRTC call page. Incoming-call ID and origin are validated. Android microphone permission and WebView-origin scope are required. This is a notification-first prototype, NOT qualified Telecom/CallStyle integration or guaranteed locked-screen delivery.
- **Backend call signaling:** SQLite transactional incident-dedupe ledger with current Home/Hub/ownership epoch, current primary caregiver gate, bounded call TTL, role checking, single active incident request, durable push outbox, caregiver accept/decline, Hub offer, caregiver answer, bidirectional ICE candidates, two-sided media-ready signaling, end/revocation and failure states. WSGI adapter *requires* verified middleware injection: no HTTP caller-provided `X-Actor-Id`, owner claim or `policy_approved` flag grants call rights.
- **FCM provider seam:** optional `firebase_admin` worker module; requires separately provisioned backend service credentials, registration tokens from real authenticated users, a trusted dispatcher and worker-recovery/retry policy. Provider message accepted is NOT phone displayed or caregiver answered.
- **Browser WebRTC answer page:** same HTTPS origin and brand stylesheet as PWA; explicit Accept gesture; local microphone; remote audio; encrypted WebRTC peer connection; server-mediated signaling/ICE. Requires a real short-lived ICE/TURN provider, authenticated browser session, and Hub WebRTC *offerer* implementation not supplied here.
- **Automated verification:** six Python unit tests cover call creation, idempotent restart persistence, reject unauthorized/stale/revoked identities and policy spoof, SDP/ICE handshake states, media readiness, token registration, dispatch and revocation. JavaScript syntax and Android XML static parsing also checked.

## Cannot truthfully call this production end-to-end

The current canonical PWA test adapter (`code/tools/sim/pwa/app.js`) sends the local simulator actor header `X-Actor-Id: simulation-owner`; this is **not a production human login**. Canonical `code/backend/ghar_sajag/human_authentication.py` explicitly describes an **inactive** verifier and session boundary. GS-143 caregiver Home authority and commercial credentials are pending. GS-68/109 trusted identity/time providers and final GS-40 integration are also in progress.

Therefore the provided `CallApi` is **NOT activated as a public route**, and no fake authentication, test-only account, public URL, bundled API key, or static TURN password is installed. The Android app is source code, not a signed APK; it requires an actual HTTPS PWA deployment and FCM Android config. The S3 Hub WebRTC transport is NOT implemented by this package, and no real S3↔Android audio or locked-screen push HIL has passed.

These are missing upstream integrations, NOT passing tests:

1. Verify repository `AGENTS.md`, canonical locked requirements, latest Jira GS-143/153/154/157/40/68/109/148, and `tools/context/ghar_sajag_context_preflight.sh` in an **independent approved worktree** before merging or editing canonical product source. Do not compete with the active GS-40 writer or reset/clean/rebase the canonical worktree.
2. Configure HTTPS production PWA origin; serve existing PWA unchanged, plus `web/caregiver/call.html` and `call.mjs` under `/caregiver/`. Add a same-origin Content Security Policy suitable for WebRTC and a backend CSRF protection scheme; ensure login is verified before serving private data.
3. Mount `CallApi` behind production verified caregiver session, current Home/role/ownership epoch authorization and verified Hub identity. The `Principal` object and `gs.verified_incident_call_approval` must be produced **only by the server's trusted middleware/canonical risk engine** after the configured AUTO_CALL policy and verification timer. A remote client must not create that approval, pick a recipient or impersonate a Hub.
4. Integrate the call ledger and outbox into canonical transactional persistence and incident/notification resolution. Add strict retries, outbox-claim expiry/recovery, authenticated mobile-device ownership/revocation, audit, backup caregiver escalation, token invalidation, stale callback fencing, push/timeout convergence and confirmed-answer semantics. The sample SQLite ledger is a useful isolated contract but is NOT the canonical production durable store.
5. Provide an actual production short-lived ICE/STUN/TURN credential allocator via `CallApi(voice, ice_config_provider=...)`; no internet peer-to-peer media works reliably without appropriate NAT traversal. Use server-generated ephemeral credentials, never static public credentials.
6. Implement the **Hub-side** WebRTC/VoIP audio endpoint, session control, acoustic echo control, and coexistence with S3 ESP-NOW, durable ACK, CloudSync, security/FOTA and memory/PSRAM. Do not claim that ESP-WebRTC examples already run on the Ghar Sajag firmware.
7. Configure a dedicated Firebase Android app: put `google-services.json` in `android/app/` locally (do NOT commit it), configure least-privilege server-only Firebase Admin credentials, and test native notification permission, background/Doze/OEM battery savers, real caregiver answer and failed delivery. Complete Android Core-Telecom/phone-call foreground-service integration if a robust OS-style incoming-call experience is required; present source implements only a high-priority invitation notification. Android signed-release build requires Android SDK, Gradle and device tests.
8. Register production tests with GS-116/130 and run all prior affected backend/PWA/Hub regressions plus focused security/negative/WSGI/Android/browser and E2E tests. A full release gate and physical HIL remain NOT_RUN.

**Safety/compliance:** Google states FCM is not intended for life-critical or high-risk emergency alert systems. Do not position this push service or a WebRTC PWA/Android call as guaranteed emergency dispatch. Require independently qualified escalation/contact channels or restrict the feature to non-emergency caregiver communications until product/legal/reliability requirements are satisfied. With no Internet/power, remote calling cannot proceed; display and log that truthfully. No recording or always-open microphone by default.

## How to inspect and validate the package (no canonical repo changes)

```sh
python3 -m unittest discover -s server/tests -v
node --check web/caregiver/call.mjs
```

The Android project is `android/`. Import it in Android Studio with a supported Android SDK/Java 17, create `android/app/google-services.json` from a Firebase project, and set the HTTPS PWA URL with the Gradle project property:

```sh
# From android/; requires local Android SDK, Google services config & Gradle
./gradlew assembleDebug -PpwaBaseUrl=https://YOUR-APP-HOST.example/
```

The Gradle wrapper binary/JAR and Android SDK are not bundled by this package. Use Android Studio's Gradle sync or generate the wrapper with an installed Gradle distribution before CLI building. The dummy `https://example.invalid/` default refuses to operate as a real backend endpoint and must be overridden.

## Source-to-product integration mapping

| Package source | Intended canonical owner | Contract |
|---|---|---|
| `android/` | New independent caregiver Android app module | WebView reuse existing PWA, FCM invitation and WebRTC call page |
| `web/caregiver/` | `code/tools/sim/pwa/caregiver/` after approval | Same-origin call UI with verified cookie session |
| `server/call_signaling.py` | Backend call signaling, GS-157 | Verified Hub/caregiver/incident trust boundary, SQL and WebRTC state |
| `server/push_adapter.py` | Backend push dispatcher, GS-157 | FCM provider seam and no delivery exaggeration |
| `server/tests/` | GS-116/130 focused backend/contract suite | Register and run in canonical validation framework after approved integration |

## Validated versus outstanding evidence

- Python signaling / push unit tests: **PASS 6/6** in this isolated environment, no target/network required.
- `node --check` call browser module: **PASS**, syntax only.
- Android XML parser: **PASS**, XML structure only.
- Android Gradle build: **NOT_RUN** (Android Gradle and SDK/FCM credentials unavailable here).
- Android emulator / physical Android, FCM delivery, Doze, real WebRTC over TURN, production auth, Hub audio, full system E2E: **NOT_RUN**.
- Canonical context preflight and GS-116/130 full required component regressions: **NOT_RUN**; no canonical source modified.
- Jira and main branch changes: separate delivery records may exist; this package itself does not merge into the canonical repository.
