# GS-177 caregiver Android continuation — 2026-10-17

## Current disposition

`APK_BUILT_DASHBOARD_ONLY; LIVE_ACCEPTANCE_BLOCKED`. Hosted build run 39007792463 produced a debug-signed installable APK; the artifact and portable checksum sidecar both verify. The APK only opens an administrator-configured HTTPS origin and has push, calls, microphone and escalation disabled. No approved live endpoint is configured, and the phone, production identity/session issuer, Firebase project, or S3 Hub media path are not available in this execution environment. Keep GS-177 open.

This build is an installable test shell intended to load the existing Parivar Saathi PWA from an administrator-provided HTTPS origin. It is not yet a usable caregiver service until that origin serves the actual authenticated PWA/backend.

## Branch and ownership

| Item | Verified value |
|---|---|
| GS-177 worktree | `/home/udaybhan/projects/Ghar_sajag_gs177` |
| GS-177 branch | `feature/gs-177-caregiver-android` |
| APK build source revision | `da21a22487e9325530554de0a49897f14490e200` |
| GS-177 starting and remote ref at continuation start | `e92407139bc96a4fde91df39b6e38ebcc2dd6f56` |
| Existing GS-177 base | `71f7dc0518fc4705d2467bc70f772d861b02750e`; branch retained without rebase/merge |
| Canonical GS-40 worktree | `/home/udaybhan/projects/Ghar_sajag_r1` |
| Canonical local HEAD at continuation start | `072e94ee7185b3797cc83a4308331571cba17663` |
| `origin/feature/r1-commercial-baseline` read-only remote HEAD | `3075011dd1b0525a8dfa326131c6a435e515b02a` |
| Worktree safety | GS-40 directory and existing untracked hardware/PWA assets were read-only and untouched |
| Context preflight | `PASS`, version `2026-10-13.001`, run from this GS-177 worktree at `e92407139bc96a4fde91df39b6e38ebcc2dd6f56` |

The canonical local and remote R1 heads differ, and both are newer than the established GS-177 base. GS-40 is active in that worktree. This branch remains isolated for a later conflict-reviewed integration; no synchronization with the canonical branch was attempted.

## Owner-supplied source import

The read-only owner source exists at `/home/udaybhan/projects/Ghar_sajag_r1/code/parivar_saathi_android_app`. It directly contains `android/`, `server/`, `web/caregiver/`, tests, and starter documentation. It was copied (not moved) into `code/parivar_saathi_android_app/` in this GS-177 worktree. The import manifest `docs/exec-plans/evidence/GS177_SOURCE_IMPORT_20261017.tsv` records source and destination relative paths; its SHA-256 is `359b9503d8c29d9d081c3540e7d621daea1bc1b13e98d5107d9c9bedbb1c2bf3`. The three prototype Android call/FCM Kotlin files are retained under `code/parivar_saathi_android_app/prototype/android/`, outside the Android Gradle source tree.

At this continuation check, all 23 source files still matched their manifest hashes and sizes. GS-177 destination files have intentional, reviewed edits for dashboard-only behavior/build configuration; the protected source copies remain unchanged. Source `Zone.Identifier` streams were not imported. Python `__pycache__` entries seen after tests are generated ignored files, not imported source. No Firebase JSON, service key, keystore, APK, `.env`, or build output was copied.

## Implemented app and build scope

- The Android shell loads the existing PWA from a first-run configured public HTTPS origin. It rejects HTTP, local/reserved domains, credentials, paths, query/fragment, and nonstandard ports; normalizes the host and stores the selected endpoint in app-private preferences.
- WebView uses TLS only, denies SSL errors, mixed content, file/content access, third-party cookies, multiple windows, web permissions, and privileged JavaScript bridges. Top-level navigation is constrained to the configured HTTPS host. Back navigation works. The user can clear cookies and change the server.
- The app has no bundled demo data, synthetic account, `X-Actor-Id`, `example.invalid` runtime endpoint, or local mock dashboard. The APK will not create a caregiver session or grant Home access.
- The dashboard artifact excludes the prototype call Activity, FCM service, and token registration sources by keeping them outside `android/app/src/main`; it has no notification or microphone permission and no Firebase dependency. This follows the actual Gradle/Kotlin source behavior observed in the first CI build. The UI labels voice calls and notifications disabled. The included call/signaling sources remain an isolated prototype and are not qualified product behavior.
- `.github/workflows/gs177-android-dashboard-apk.yml` is pinned to immutable action SHAs, runs on hosted Ubuntu 24.04 with Temurin JDK 17, Gradle 8.9, Android SDK 35 / Build Tools 35.0.0, runs registered tests/build, verifies debug signing, writes SHA/build metadata, and uploads a 14-day test artifact. It uses only read permissions and no secrets. It triggers only for pushes to the GS-177 branch.
- App and voice prototype stages are separately registered in GS-116/130 traceability and are outside the generic fast/release suites. Physical qualification remains `NOT_RUN` and release-blocking.

## Build and validation evidence at this checkpoint

### APK artifact

| Field | Value |
|---|---|
| `ANDROID_APK_PATH` | `/home/udaybhan/projects/Ghar_sajag_gs177/code/parivar_saathi_android_app/android/app/build/ci-artifact-39007792463/parivar-saathi-caregiver-debug.apk` |
| SHA-256 | `a82b60b7d5b2ab498bd5e19eb91f802e7e36f9539c19c15caced0c2d856490c1` |
| Size | 2,455,020 bytes |
| Package / version | `in.gharsajag.caregiver` / `0.1.0-dashboard` |
| Build / source | GitHub Actions [run 39007792463](https://github.com/udaybhan200683/Ghar_sajag/actions/runs/39007792463), source revision `da21a22487e9325530554de0a49897f14490e200` |
| Build environment | Temurin JDK 17, Gradle 8.9, Android SDK 35, Build Tools 35.0.0; min API 26 |
| Signature / checksum | CI `apksigner verify` passed; downloaded artifact `sha256sum --check SHA256SUMS` passed |
| Signing | Runner-generated Android debug key, testing only; no keystore is stored or reused |

Install on an Android API 26+ device by downloading the APK, verifying it with the adjacent `SHA256SUMS`, and opening it with Android's package installer (allow this file source when prompted). On first launch it requests an approved HTTPS service origin. No production origin is currently available, and no phone install was performed here.

| Check | Result |
|---|---|
| Local JDK / Android SDK / Gradle / ADB / apksigner | Not installed |
| Local Android build | `NOT_BUILT` locally; JDK/SDK/Gradle absent |
| Hosted Android workflow | Run 39007792463 passed the registered Android and prototype stages, 4/4 Kotlin tests, `apksigner`, relative `SHA256SUMS` verification and artifact upload. Previous runs 39006792176, 39006969459 and 39007289252 exposed and resolved the build/gate issues; run 39007561093 exposed the absolute checksum-path issue. |
| Physical Android device / install | `NOT_RUN`; no phone is attached/observable |
| `bash code/parivar_saathi_android_app/verify.sh` | PASS, 6/6 prototype tests; Node syntax and Android XML parse pass |
| `make -C code feature-coverage-test` | PASS, 210 features / 234 modules / 25 physical cases; 22/22 mapping tests |
| `make -C code validation-framework-test` | PASS, 48/48 tests |
| `make -C code physical-hil-catalogue-test` | PASS, 109 catalogue cases; device access `NONE` (catalogue consistency only) |
| Source, endpoint and product E2E | Not run; no approved live endpoint/identity/phone |
| Full release gate | `NOT_RUN` (deferred) |

The prototype signaling tests are host-only contract tests and do not prove Android build, real FCM receipt, display/answer, production authorization, TURN media, or Hub connectivity.

## Deployment, trust and acceptance status

`LIVE_HTTPS_PWA_URL=NOT_DEPLOYED`. No approved hosting credentials/domain or deployed persistent backend + PWA were available. Do not expose the localhost WSGI demo or `X-Actor-Id: simulation-owner`. Production server-side login/session issuance, current Home/caregiver role and epoch authorization, revocation, and audit remain upstream GS-68/109/143/148 work. No APK backend URL is embedded.

| Use case | Status | Evidence boundary |
|---|---|---|
| HOME | `BLOCKED_UPSTREAM` | No deployed authenticated PWA/API or authorized current Home session |
| DEVICES | `BLOCKED_UPSTREAM` | No live authorized NodeHealth feed or mobile run |
| REPORTS | `BLOCKED_UPSTREAM` | No live authenticated report/history service |
| SETTINGS | `BLOCKED_UPSTREAM` | Production caregiver authority and writable API not qualified |
| INCIDENTS | `BLOCKED_UPSTREAM` | No production persistence/actor authorization endpoint |
| NOTIFICATIONS | `BLOCKED_UPSTREAM` | GS-25/Firebase setup deferred; no provider or handset evidence |
| MANUAL_INTERNET_CALL | `BLOCKED_UPSTREAM` | GS-154/157 call service, authenticated signaling, ICE/TURN and S3 audio absent |
| AUTO_ABNORMALITY_CALL | `BLOCKED_UPSTREAM` | Qualified Hub risk trigger and policy-owned CallManager absent |
| BACKUP_ESCALATION | `BLOCKED_UPSTREAM` | Durable ordered backup/call lifecycle absent |

FCM provider receipt, Android displayed/ringing/answered state, S3 WebRTC media, physical HIL, and independent mobile-data E2E are all `NOT_RUN`. Worst-case unattended reachability is unqualified. Internet/power outage is not represented as successful caregiver reachability. FCM acceptance alone cannot establish a displayed alert or answer.

## Exact next actions

1. Obtain the approved live HTTPS PWA/API origin, production caregiver issuer/session + current-Home/epoch/revocation contract, persistent hosting/database, and a real Android phone with mobile-data access. Install the exact APK above and capture actual device/backend evidence for each supported screen and denial/revocation case.
2. Keep GS-25 Firebase delivery and GS-154/157 plus GS-40/68/109/143/148 call/identity/Hub work as upstream gates. Do not claim FCM delivery, manual/automatic voice, backup escalation, or S3 HIL until performed with the real phone and hardware under separate approved test conditions.
3. Update Jira GS-177 and this handoff with later device/backend results. Submit a reviewed GS-177 PR/handoff; do not merge into or push to the GS-40 branch.

## GS-177 live-backend and startup continuation — 2026-10-17

### Verified starting state and ownership

This continuation started on GS-177 HEAD `9b0f697bcf178e10fc4a164cda542270d193644d` in `/home/udaybhan/projects/Ghar_sajag_gs177`, branch `feature/gs-177-caregiver-android`; local HEAD equaled the remote branch and the tracked/untracked status was clean. The GS-177 context preflight passed (`2026-10-13.001`). The canonical GS-40 checkout was read-only: local HEAD `072e94ee7185b3797cc83a4308331571cba17663`, remote HEAD `3075011dd1b0525a8dfa326131c6a435e515b02a`; its pre-existing untracked PWA, Android starter, managed components and hardware evidence were preserved. No synchronization or write was made to that checkout.

### Current backend boundary audit

The existing PWA in `code/tools/sim/pwa/` is the only four-tab Home / Devices / Reports / Settings UI inspected in this branch. It is a local simulator client, not a production caregiver app: `app.js` sends `X-Actor-Id: simulation-owner` and the Reports path names `simulation-home`; the PWA README explicitly calls device registration simulated. The Android wrapper currently opens a remotely configured origin and shows the manual server-address screen when no origin is stored.

The corresponding server is not safe to publish:

- `code/backend/ghar_sajag/http_api.py` describes `X-Actor-Id` as a development-only adapter, reads that header as the actor, and its demo `main()` binds to `127.0.0.1`.
- `code/backend/ghar_sajag/human_authentication.py` is an inactive verifier/session interface. It does not verify OIDC signatures, issue sessions or install API routes; its tests inject a fixture verifier.
- `GharSajagService` defaults to `InMemoryStore`. `database.py` only initializes SQLite and explicitly leaves PostgreSQL as a future adapter. The deployment compose file has PostgreSQL and Mosquitto only; it has no caregiver API, PWA host, identity provider or HTTPS reverse proxy.
- Current GS-143 remains To Do. GS-68/109 production trust/provider decisions remain unapproved. GS-148 remains In Progress with production durable/backend completion open, and GS-40 remains active. Do not invent Home membership, session revocation, event durability or production identity contracts on this app branch.

`LIVE_HTTPS_PWA_URL=NOT_DEPLOYED`. No cloud host/domain/OIDC tenant and app registration, managed application database, or approved caregiver-to-Home authority source was supplied. The local execution environment has no Docker/Podman/cloud CLI or ADB available. No public deployment or credential access was attempted. **Priority-1 disposition: `BLOCKED_AUTH_PROVIDER` / `BLOCKED_DEPLOYMENT`.** A PostgreSQL service container alone is insufficient because no PostgreSQL application store or authenticated production composition is present.

### Android startup/offline addendum

The owner reports installing the existing dashboard APK. That owner-reported install is not a phone log or a live backend test. The current app still asks for a server address on first use, as confirmed in `MainActivity.kt`; the wrapper has no bundled PWA assets and cannot present the familiar tabs offline.

Do not copy the PWA into Android as an independent implementation or bundle the simulator wiring unchanged. Doing either would create two UI authorities or show simulator identity/data. Keep this as the next bounded GS-177 app integration after the live API/runtime contract is approved:

1. Package the existing `code/tools/sim/pwa/` assets through the Android build as generated WebView assets from that single source tree; do not maintain a second dashboard copy.
2. Remove the server-address form from the normal caregiver launch. Supply the production HTTPS origin through an internally controlled build/runtime configuration and keep any endpoint override available only in a debug build.
3. Add a production PWA transport mode that never sends the simulator actor/header or uses `simulation-home`; retain local simulator mode only for the explicitly launched development lab.
4. On an unavailable backend, open the bundled familiar interface and show an explicit `Offline / Unable to connect` state. Every data panel must be empty/unavailable with freshness unknown; no demo household, device, event, notification, incident or call state may be shown.
5. Add Android startup/offline instrumentation and production-build checks proving offline launch, no simulator identity/data, and no release server override before producing the next APK.

This UI slice must not be represented as completion of live caregiver use cases. The backend currently exposes no approved authenticated production API to configure, and the local PWA's `/pwa/*` and `simulation-home` paths do not match a production caregiver contract.

### Focused local regressions executed

| Command | Result | Boundary |
|---|---|---|
| `PYTHONPATH=backend python3 -m unittest discover -s tests/engineering_dashboard -p 'test_human_authentication.py' -v` | PASS, 14/14 | Injected verifier/session fixtures only; not production OIDC |
| `make app-test` | PASS, 24/24 | Existing caregiver JS unit tests |
| `make pwa-68-api-test` | PASS, 1/1 | Local simulator-backed API test; target prerequisites built in GS-177 ignored build output |
| `make pwa-68-frontend-test` | PASS, 1/1 | Existing frontend unit test; no mobile backend |

No Android, backend, PWA, or deployment source was changed in this continuation; the existing APK and GitHub Actions build workflow remain intact. No new APK, Android build, physical install, live HTTPS test, issuer/session test, PostgreSQL test, notification receipt, voice test, Hub test or HIL was run. The already delivered APK remains the dashboard-only artifact at the path/hash recorded above; full release gate remains `NOT_RUN`.

### Current acceptance matrix

| Use case | Status | Evidence |
|---|---|---|
| HOME | `BLOCKED` | No deployed authenticated caregiver API/current Home membership; owner-reported APK install only |
| DEVICES | `BLOCKED` | No live NodeHealth source exposed to the caregiver PWA |
| REPORTS | `BLOCKED` | Existing PWA report path is simulator/Home-specific; no authorized backend route |
| SETTINGS | `BLOCKED` | No production caregiver role/epoch/revocation or writable API |
| INCIDENTS | `BLOCKED` | No production caregiver session and durable authorized API |
| NOTIFICATIONS | `BLOCKED` | GS-25 provider setup and real Android delivery evidence absent |
| MANUAL_INTERNET_CALL | `BLOCKED` | GS-154/157 call service, TURN and S3 media are unqualified |
| AUTO_ABNORMALITY_CALL | `BLOCKED` | Qualified risk trigger and GS-157 CallManager absent |
| BACKUP_ESCALATION | `BLOCKED` | Durable ordered fallback and actual caregiver receipts absent |
| Bundled PWA startup / manual-origin removal / offline state | `REAL_FAIL` | Current `MainActivity` requires a manually entered origin; no bundled offline PWA |

FCM provider acceptance, Android displayed/answered receipts, mobile-data end-to-end, real Hub↔phone audio and physical S3 HIL remain `NOT_RUN`. No life-safety reachability claim is qualified.

### Exact owner inputs for the next real deployment step

Provide through the authorized secret/configuration channel (never Jira, Git or chat secrets): (1) the organization-approved hosting account/provider, region, domain and DNS control; (2) the approved OIDC issuer/tenant, API audience, Android/PWA client registration and redirect URIs; (3) the authorized owner/team and current Home membership/role/epoch/revocation source that resolves a verified OIDC subject to an actual caregiver; (4) managed PostgreSQL and backup/restore ownership; and (5) one real test caregiver/Home plus an Android phone available for independent mobile-data testing. GS-25 Firebase project and GS-154/157 TURN/Hub-media qualification are separate later inputs. Until the identity and Home-authority dependencies are approved and implemented, do not create a public app endpoint or claim the APK is Internet-connected.

Next safe action: coordinate the production OIDC/Home authority and PostgreSQL API contract with GS-143/GS-68/GS-109/GS-148/GS-40 owners. Then implement the authenticated server composition and a real PWA runtime contract in GS-177, followed by the bundled startup/offline slice and live mobile-data test. Keep the Jira issue open and submit a conflict-reviewed PR/handoff; do not merge into GS-40.

## GS-177 bundled offline startup and approved logo — 2026-10-17

This continuation supersedes the earlier manual-origin startup status in this
handoff. Development remains isolated in `/home/udaybhan/projects/Ghar_sajag_gs177`
on `feature/gs-177-caregiver-android`. At start, HEAD was
`9b0f697bcf178e10fc4a164cda542270d193644d`, equal to the GS-177 remote branch.
The GS-177 context preflight passed (`2026-10-13.001`). The canonical GS-40
checkout was used only for read-only logo inspection and copy; no files there
were written, staged, or built.

### Logo provenance and implementation

The identified owner logo is
`/home/udaybhan/projects/Ghar_sajag_r1/code/parivar_saathi_android_app/android/Parivar_Saathi_Logo.png`
(1254×1254 PNG). It was copied first to
`code/parivar_saathi_android_app/branding/source/Parivar_Saathi_Logo.png` in
GS-177. Both the protected original and copied input had SHA-256
`d0ff244d61b5cb047c320fc3af1028fa8e780186189a481657b8fea14b679441` after
copy. The deterministic standard-library generator is
`code/parivar_saathi_android_app/branding/generate_parivar_saathi_assets.py`.

- Android density launcher icons, adaptive/round resources and Android 13
  monochrome layer use the family/home/shield mark only. The separate small
  notification icon is monochrome white and is only a resource; FCM is still
  disabled.
- Android splash combines the launcher mark with the supplied Parivar Saathi
  wordmark and tagline. The Android application label is `Parivar Saathi`.
- The shared PWA header, favicon, install manifest and notification icon now
  use the approved mark and `Parivar Saathi` spelling. Its 192px icon is part of
  offline startup; the 512px maskable icon is accounted as install-only payload.
- The app launches the existing bundled `tools/sim/pwa/` UI directly. It no
  longer asks the caregiver to type a server address. With no network/API, the
  UI renders Home, Devices, Reports and Settings with “Offline / Unable to
  connect,” unknown freshness and no simulated household data. Build-time debug
  origin configuration is separate from release; it does not enable a real
  caregiver API or authentication.

### Validation at this source checkpoint

| Check | Result | Evidence boundary |
|---|---|---|
| Logo source/copy identity | PASS | SHA-256 matched; GS-40 input remained read-only |
| Branding resource validation | PASS | `GS177-ANDROID-BRANDING-001`; Android XML references and PNG dimensions checked |
| `make -C code app-test` | PASS, 30/30 | JS/unit tests only |
| `make -C code pwa-e2e-test` | PASS, 14/14 | PWA bridge 12/12, API 1/1 and frontend 1/1; local simulator fixtures only |
| `make -C code performance-profile` | PASS | Startup payload 110,404 bytes; JS 67,920 bytes; install-only 512px icon 85,193 bytes; 9 cached startup assets |
| `make -C code feature-coverage-test` | PASS | 211 feature rows, 236 source modules, 25 physical cases; mapping tests 22/22 |
| `bash code/parivar_saathi_android_app/verify.sh` | PASS, 6/6 | Isolated call/push prototype tests and its XML check; not production voice/FCM |
| `python3 code/validation/run_gs177_android.py` | BLOCKED, exit 127 | Branding and runtime checks passed (runtime 6/6); local Gradle/JDK/Android SDK are absent |
| Caregiver Chromium browser E2E | NOT_RUN | Local run skipped because Chromium/Chrome is not installed. The hosted workflow now installs pinned `websocket-client` and runs the registered PWA browser regression. |
| Android Gradle APK build / install | NOT_RUN | Hosted run is required; physical phone is not available in this environment |

No live backend, auth issuer, Android phone, Firebase project, TURN service or
S3 media was configured or exercised. `LIVE_HTTPS_PWA_URL=NOT_DEPLOYED`; the
full release gate remains `NOT_RUN`.

| Caregiver use case | Status | Current evidence |
|---|---|---|
| HOME | BLOCKED | No deployed authenticated caregiver API or current-Home authorization |
| DEVICES | BLOCKED | No live authorized NodeHealth endpoint |
| REPORTS | BLOCKED | No authenticated production history service |
| SETTINGS | BLOCKED | No production caregiver role/epoch/revocation API |
| INCIDENTS | BLOCKED | No production session or durable incident API |
| NOTIFICATIONS | BLOCKED | FCM disabled; no provider or handset receipt |
| MANUAL_INTERNET_CALL | BLOCKED | GS-154/157 signaling, TURN and S3 audio not qualified |
| AUTO_ABNORMALITY_CALL | BLOCKED | Qualified risk trigger and CallManager are upstream |
| BACKUP_ESCALATION | BLOCKED | Durable ordered fallback and real caregiver receipts absent |

### Next action

Commit and push only `feature/gs-177-caregiver-android`, wait for its hosted
browser/Android resource and Gradle checks, then record the run ID and APK
SHA-256. Independently, obtain approved hosting/OIDC/Home authority and a real
Android phone for mobile-data E2E. Keep the previous dashboard APK identified
as historical; do not call an offline or build-only artifact a live caregiver
product. Do not modify or merge into GS-40.

## GS-177 approved logo and hosted APK receipt — 2026-10-17

This latest checkpoint completes the requested branding/build slice. The
verified input is the owner-provided
`/home/udaybhan/projects/Ghar_sajag_r1/code/parivar_saathi_android_app/android/Parivar_Saathi_Logo.png`.
It was copied into the GS-177-owned source directory before processing. The
canonical input and GS-177 copy both hash to
`d0ff244d61b5cb047c320fc3af1028fa8e780186189a481657b8fea14b679441`; the
original GS-40 tree remains read-only. Android launcher, adaptive and round
icons use only the family/home/shield mark. The Android label and shared PWA
branding say `Parivar Saathi`; the splash includes the wordmark/tagline, and a
monochrome notification icon resource is bundled. FCM remains disabled.

The shared PWA launches from the APK without a manual server-address screen.
It renders its familiar Home, Devices, Reports and Settings navigation with
explicit offline/unavailable status and no fabricated household data. This is
still an offline dashboard artifact: build metadata says
`backend_origin=not-configured`, `push_notifications=disabled`, and
`voice_calling=disabled`.

| Evidence | Result |
|---|---|
| Context preflight in GS-177 worktree | PASS, `2026-10-13.001` |
| Source logo provenance and generated Android/PWA resource checks | PASS, `GS177-ANDROID-BRANDING-001` |
| Hosted browser regression, Actions run `39013127801` | PASS, 2 browser tests; 92/92 rendered PWA catalog assertions; explicit offline UI with no simulator data/API calls |
| Android Gradle/unit/build gate, Actions run `39013127801` | PASS, 6/6 Android unit tests; `:app:testDebugUnitTest :app:assembleDebug`; origin/resource/bundle checks |
| Voice prototype contract stage | PASS, 6/6 host-only tests; not production voice evidence |
| APK verification | PASS, APK v2 signature verified; `sha256sum --check SHA256SUMS` passed |
| Local Android build | BLOCKED, local Gradle/JDK/Android SDK unavailable; hosted runner produced the artifact |
| Physical phone install/launch/offline recovery | NOT_RUN, no device evidence available to this execution |
| Live HTTPS/auth/Home authorization/data | BLOCKED, `LIVE_HTTPS_PWA_URL=NOT_DEPLOYED` |

The reproducible hosted build is [GitHub Actions run 39013127801](https://github.com/udaybhan200683/Ghar_sajag/actions/runs/39013127801), source revision
`da52b49fc05a5a7d8de48a855262e69ad147a37b`, branch
`feature/gs-177-caregiver-android`. APK package is
`in.gharsajag.caregiver`, version `0.3.0-branded-offline`, min API 26, built
with JDK 17, Gradle 8.9 and Android compile SDK 35. It uses a runner-generated
debug certificate for testing only; this key is ephemeral and cannot provide
stable upgrade signing.

- APK: `code/parivar_saathi_android_app/android/app/build/ci-artifact-39013127801/parivar-saathi-caregiver-debug-da52b49fc05a5a7d8de48a855262e69ad147a37b/parivar-saathi-caregiver-debug.apk`
- SHA-256: `74363def11cd84566c080be03ddf59cf9c3d0dd71040591bffbd3f18a0974d51`
- Download: [Actions artifact 12093656871](https://github.com/udaybhan200683/Ghar_sajag/actions/runs/39013127801/artifacts/12093656871)
- Build metadata and `SHA256SUMS` are beside the APK; extracted APK checksum reverified locally.

Current caregiver acceptance remains incomplete. HOME, DEVICES, REPORTS,
SETTINGS, INCIDENTS, NOTIFICATIONS, MANUAL_INTERNET_CALL,
AUTO_ABNORMALITY_CALL and BACKUP_ESCALATION are `BLOCKED_UPSTREAM` for real
use because there is no production caregiver issuer/session, current Home
membership/epoch/revocation API, persistent deployed backend or configured
HTTPS URL, FCM project, qualified CallManager/TURN/S3 media path. Android
phone installation, provider delivery, displayed/answered receipt, mobile-data
E2E and physical HIL are `NOT_RUN`. Full release gate remains `NOT_RUN`; GS-177
remains open.

The Jira handoff comment is GS-177 comment `11318`. GS-177 source changes are
committed only to the isolated worktree `/home/udaybhan/projects/Ghar_sajag_gs177`
on `feature/gs-177-caregiver-android`. Artifact source commit `da52b49` was
verified equal to origin before documentation receipts. No GS-40 branch,
index, source, untracked assets, or hardware was modified.

Next safe action: install this testing APK on the owner's phone and capture
the actual Android launch evidence; supply the approved hosting/OIDC/Home
authority inputs before configuring a live origin. Do not describe the
dashboard build as a connected caregiver product or claim FCM/voice safety.

## GS-177 Connected Lite continuation and GS-125 reuse — 2026-10-17

**Status: source integration in progress; not deployed or Android-qualified.**
GS-177 comment 11325 and GS-125 comment 11061 correct the Engineering scope:
the GS-120 seven-screen architecture and GS-122/124 service-ticket,
authorization and read-only projection foundation were merged into R1 on
15 October. The current GS-177 branch already contains `diagnostics.py`,
`diagnostic_authorization.py`, `service_access.py`, `human_authentication.py`,
migration 011 and registered tests. This change reuses the read service and
authorizer through a TEST_ONLY adapter; the production real-Home consent and
ticket route remains disabled until a qualified production identity/Home
authority is composed. There is no second Engineering domain implementation.

Starting checkpoint: authorized `/home/udaybhan/projects/Ghar_sajag_gs177`,
`feature/gs-177-caregiver-android`, local/remote HEAD
`6749b9e0cb5785a00cb87df88cb424b6107073bd`, clean before edits. Context
preflight PASS `2026-10-13.001`. No sync, reset, merge, rebase, branch switch,
GS-40 write or hardware operation occurred.

The staging implementation is `code/parivar_saathi_android_app/server/connected_lite.py`
and `connected_lite_schema.sql`, with WSGI entry `wsgi.py` and `render.yaml`.
It creates uniquely named TEST_ONLY Homes via a prompted operator bootstrap,
stores password hashes and revocable session-token digests, checks active
account/session, current Home membership/role/epoch on every route, checks
POST Origin, limits request bodies and login attempts, and never mounts the
development `X-Actor-Id` API. A PostgreSQL advisory transaction lock bounds
lab concurrency; 120 saved runs per Home per hour is the initial staging cap.
Each scenario invokes the existing `local_lab`/validation catalogue, stores
source-labelled JSON in PostgreSQL and leaves emergency delivery disabled.
The Android WebView serves the bundled shared PWA under the exact approved
HTTPS backend origin, giving its HttpOnly SameSite session cookie first-party
scope. The existing branded resources and package ID are preserved.

The PWA adds login, Home, Devices, Incidents, Reports, Routines, Settings,
admin-only Simulation Lab and Engineering navigation. The Engineering selector
uses the seven GS-120 areas and the GS-124 health projection; unavailable
physical signals show UNKNOWN/UNSUPPORTED/NOT_RUN. Saved synthetic event
timelines and expected-versus-observed checks are inspectable/exportable.
Selected and full-catalogue execution are supported; the backend rejects
unapproved seed/config inputs rather than pretending to run a configurable
clock. Routine summary currently reports `UNSUPPORTED_MULTI_DAY`; a synthetic
single scenario is not a trained resident baseline. Real Home operations,
caregiver Approve/Deny/Revoke route composition and actual long-term Hub
event ingest are still absent from this TEST_ONLY staging API.

### Validation receipt

| Area | Outcome |
|---|---|
| Connected Lite host gate | PASS: 9 API/auth/storage tests, 6 JS runtime tests, 3 real existing lab scenarios (`motion-room1-visible`, `door-open-close-order`, `morning-missing-covered`) |
| Shared PWA browser | PASS: 2 browser tests, 92/92 rendered catalogue cases; offline login gate shows no synthetic healthy data |
| GS-130 traceability | PASS: 212 features, 242 modules, 25 physical cases; consistency only |
| PostgreSQL hosted recovery | NOT_RUN: no provisioned database/service |
| Android connected APK/signature/hash | BLOCKED: no approved stable HTTPS backend origin; previous `0.3.0-branded-offline` APK is historical |
| Owner mobile-data/laptop-off acceptance A–E | NOT_RUN: no configured APK or independent phone evidence |
| Real device/voice/Firebase/HIL | NOT_RUN/BLOCKED on GS-40/68/109/143/148/154/157 and physical qualification |

### Deployment and credential procedure

1. In an authorized Render account, review the paid `render.yaml` web and
   PostgreSQL plans and approve provisioning. Import this repository's
   `feature/gs-177-caregiver-android` branch as a Blueprint. The service pins
   that branch and disables automatic deploys. Its `PUBLIC_ORIGIN` references
   Render's own HTTPS service URL; database connection comes from private
   managed PostgreSQL. No repository credential is required.
2. Verify `/healthz` and `/readyz` over the assigned HTTPS URL. In the service's
   private operator shell, run
   `cd code/parivar_saathi_android_app/server && python3 connected_lite.py bootstrap-admin --email <owner-email>`.
   Enter a unique password of at least 16 characters at the hidden prompt and
   deliver it to the owner through a private channel. Do not post it to Jira,
   source, CI or build metadata. Rotate with the same operator shell using
   `python3 connected_lite.py rotate-password --email <owner-email>`; this
   revokes existing sessions. A TEST_ONLY caregiver can be provisioned with
   `bootstrap-caregiver --email <email> --home-id <test-home-id>` and a hidden
   password prompt. This bootstrap has not yet been run on a hosted service.
3. Set GitHub Actions repository variable `GS177_BACKEND_ORIGIN` to the exact
   assigned HTTPS origin, then trigger the existing GS-177 Android workflow on
   this branch. For upgrade signing, create and retain an owner-controlled
   keystore outside Git; set `GS177_KEYSTORE_B64`,
   `GS177_KEYSTORE_PASSWORD`, `GS177_KEY_ALIAS`, `GS177_KEY_PASSWORD` as GitHub
   Actions secrets. Without them the runner signs with a temporary debug key;
   the previous APK may need uninstalling and future seamless updates are not
   guaranteed. Record the actual Actions URL, APK SHA-256 and `apksigner`
   certificate receipt before installation.
4. Configure managed PostgreSQL backup/snapshot retention in the Render
   account, record a recovery owner, and test restoration into an isolated
   database before relying on persistence. The service schema is versioned in
   `lite_schema_migrations`; all simulation records remain under unique Home
   and run IDs. No backup or restore has been executed here.
5. Run owner-phone acceptance A–E on mobile data with the laptop off. Capture
   login, Home freshness, scenario timeline/export/reopen, caregiver privileged
   endpoint denial, app/backend restart and reconnect receipts. Keep each step
   BLOCKED/NOT_RUN until independently observed.

Next exact prerequisite is an authorized Render account and approval of its
managed-service/database charges. Then the service can be provisioned, the
owner credential bootstrapped privately, an APK built against the actual URL,
and mobile-data acceptance executed. Do not mark GS-177 Done on host tests.

### Pause/resume checkpoint requested by owner — 2026-10-17

The owner requested a pause after a logical endpoint. No further feature work
is authorized in this turn. The implementation and focused host checks above
are preserved for resumption. Branch is
`feature/gs-177-caregiver-android` in the authorized GS-177 worktree; starting
HEAD and origin were `6749b9e0cb5785a00cb87df88cb424b6107073bd`. The
validated changes are to be committed and pushed on this branch, with the
actual final local/remote SHA recorded in the dated GS-177 Jira comment and
turn receipt. Canonical GS-40 remains read-only.

The affected backend component gate executed 22 stages. Its existing
CloudSync/Hub/contracts/functional/API stages and new
`gs177-connected-lite-api` stage passed, but the aggregate gate exited 2:
the Python stage failed under a temporary directory mistakenly placed inside
the repository and because `gs177-caregiver-offline-browser` was absent from
release composition; the existing GS-124 registry test assumed diagnostics
was the last suite after GS-177 stages were appended; and P0 full-product E2E
could not find `frontend/node_modules/.bin/playwright`. The first two
registration/environment issues were corrected without removing any test or
weakening assertions. The three affected registration/private-key tests then
passed 14/14 with an external temporary directory. The full backend gate has
**not** been rerun after the fixes; its aggregate status remains FAIL. The PWA
component gate and complete product release gate were not run. The separate
PWA browser regression passed 2/2 and 92/92 catalogue assertions. The focused
connected Lite gate passed 9/9 API tests, 6/6 JS tests and 3/3 lab scenarios.
The GS-130 feature mapping test passed 22/22. There is no PostgreSQL, Android
build or physical evidence in this checkpoint.

Acceptance A (cloud laptop-off), B (phone Simulation Lab), C (multi-day routine),
D (phone Engineering plus caregiver direct denial) and E (app/backend restart and
reconnect) are all BLOCKED/NOT_RUN as end-to-end phone tests. Host-only role
denial and saved-run reconstruction passed; they are not substitutes for the
cloud/phone steps. No new APK path, SHA-256, Actions run or hosted URL exists.

Exact resume sequence: verify worktree/branch/HEAD/remote/status and active
writers; run context preflight; reread this handoff, Jira 11319/11320/11325,
GS-125/11061 and current canonical decisions. Then run the backend gate with
`TMPDIR=/home/udaybhan/.cache/gs177_tmp` after installing the repository's
frontend Playwright dependencies, and run the affected PWA component gate.
Review the unimplemented multi-day routine and real-Home GS-124 consent
composition against canonical requirements before changing semantics. Obtain
authorized Render account/billing, deploy and verify PostgreSQL/HTTPS, privately
bootstrap the owner admin, set the GitHub backend-origin variable and pilot
signing secrets, build/verify the new APK, and execute owner-phone A–E. Keep
GS-177 open and physical/Firebase/WebRTC obligations separately blocked.

## GS-177 Connected Lite resume and Hub Wi-Fi / CloudSync audit — 2026-10-17

### Resume point and preservation

Resumed the interrupted implementation in
`/home/udaybhan/projects/Ghar_sajag_gs177`, branch
`feature/gs-177-caregiver-android`, at local/remote HEAD
`6749b9e0cb5785a00cb87df88cb424b6107073bd`. The pre-existing tracked edits
and untracked Connected Lite/API/PWA/Render files were preserved. No reset,
clean, stash, rebase, force push, branch replacement or worktree replacement
was performed. GS-177 was already In Progress. The GS-177 context preflight had
passed before resuming substantive changes. Jira comments 11319, 11320, 11325
and 11330 and GS-125 comment 11061 were reconciled. Comment 11330 establishes
two tracks: TEST_ONLY Connected Lite independent of Hub connectivity, and real
Hub CloudSync separately BLOCKED/NOT_RUN.

The canonical `/home/udaybhan/projects/Ghar_sajag_r1` checkout was only read.
It had pre-existing unrelated dirty/untracked activity; no file, build, branch
or hardware operation was performed there. No protected firmware/hardware
operation was authorized or executed.

### Changes completed in this continuation

- Reused the existing GS-120/122/124/125 diagnostics and authorization
  foundation. Connected Lite adds only thin authenticated navigation and API
  adaptation to the existing seven Engineering areas; no second dashboard or
  diagnostic domain engine was created.
- The connected service remains isolated on `/lite/v1` and accepts only
  authenticated `gs177-test-*` Homes. It does not mount legacy
  `http_api.py`/`X-Actor-Id` authentication or write simulated events into the
  GS-148 event store. A direct `/v1/homes/{home}/events` request to this service
  returns 404. The response identifies `GS-148_CLOUDSYNC` as the future real
  event contract.
- Home, Devices, Engineering and Settings display
  `Physical Home UNAVAILABLE / NO_HUB_CLOUDSYNC`. Physical monitoring freshness
  and sensor/NodeHealth measurements remain UNKNOWN; simulation results retain
  `HOST_SIMULATION_TEST_ONLY` provenance.
- Corrected the registered GS-177 browser-stage success patterns to account for
  unittest's test-name prefixes and added a validation-framework regression
  proving those evidence lines are accepted, while missing lines and nonzero
  exit remain failures.
- The connected Home and Settings text distinguishes a Cloud API fetch from
  physical Hub synchronization. Offline/unconfigured behavior and admin-only
  navigation are retained.

### Read-only Hub Wi-Fi, coexistence, buffering and CloudSync audit

Read-only source inspection in canonical R1 found:

1. `code/firmware/hub/target/esp32/hub_target_config.hpp` fixes the ESP-NOW
   channel at 1. `hub_runtime_adapter.cpp::initialize_wifi()` initializes
   netif/event loop, Wi-Fi, RAM storage and STA mode, starts the radio, disables
   power save and sets channel 1. The inspected target code has no Home Wi-Fi
   credential provisioning/configuration, `esp_netif_create_default_wifi_sta`,
   `esp_wifi_connect`, IP/STA event handler or reconnect policy. Therefore no
   Home association or IP route is established by this target path. ESP-NOW
   initialization follows this setup; the HIL peer uses channel 0 (current
   channel) and its fixture-only peer is unencrypted. AP/ESP-NOW channel
   coexistence has not been qualified.
2. `cloud_wan_ready()` checks an associated AP and a STA address/gateway, but
   the target startup does not establish the missing STA association/netif in
   this path. The S3 composition constructs `UnprovisionedS3CloudTrust`, an
   HTTPS channel with empty origin/CA configuration, and an authority provider
   that cannot return a binding. Permanent Hub/Home/ownership epoch,
   enrollment generation, client TLS identity, approved DS key custody and
   authenticated trusted time are not provisioned.
3. The target schedules a task every 5 seconds that calls
   `CloudSyncWorker::run_node_health_once`; it does not schedule the event
   `run_once`/durable event-batch path. The worker's event path itself checks
   current Home/Hub/epoch, original event ownership and GS-148 V2 enrollment
   generation before and after I/O, and only retires after an authenticated
   committed backend receipt. Its bounded retry delays are 1, 5, 30, 120 and
   300 seconds. Existing durable journal/outbox state and EventKeys provide
   the local buffering/replay basis, but live event catch-up through the target
   scheduler is not established.
4. Existing GS-148 backend code defines
   `/v1/homes/{home_id}/events` and durable commit behavior, but the Connected
   Lite deployment does not mount it. The public developer actor-header adapter
   is not suitable for this use. The production Hub credential verifier,
   active ownership/enrollment authority and authenticated caregiver read
   projections remain upstream dependencies.

Exact enablement prerequisites for real Hub → Home Wi-Fi → cloud → Android:

1. An approved protected Home Wi-Fi provisioning source and target STA/netif,
   association, IP and reconnect composition; define channel coexistence with
   ESP-NOW channel 1 and qualify loss/rejoin without weakening Node durability.
2. A scheduled GS-148 event CloudSync worker using trusted WAN-ready state,
   retaining the same original EventKey/body through offline replay and waiting
   for the exact authenticated durable COMMITTED receipt before clearing local
   obligations. Keep NodeHealth publication distinct from event commit.
3. Approved GS-68/GS-109 authority, credential and trusted-time providers:
   permanent Hub ID, current Home and ownership epoch/revocation, Node
   enrollment generation, approved CA/server identity, per-Hub TLS identity
   and protected DS key-custody proof. No device secret or Wi-Fi password was
   added to source or APK.
4. A production GS-148 backend composition that verifies that identity and
   current Home/epoch/enrollment before calling the existing durable commit
   transaction, then exposes authorized caregiver projections to the app.
   Do not accept `X-Actor-Id` as Hub or Internet identity.
5. Separate approved physical C3/S3/Home-Wi-Fi fixture qualification for
   coexistence, outage/reconnect, buffered catch-up, reboot/retry/duplicate
   safety, exact EventKey/commit receipt, NodeHealth freshness and caregiver
   mobile-data projection. This task performed no such operation.

### Validation at this checkpoint

| Command / stage | Result | Qualification boundary |
|---|---:|---|
| `python3 validation/run_gs177_connected_lite.py` | PASS: 10 API tests, 6 JS runtime tests, 3 production-lab scenarios | Local SQLite/host simulation only; physical `NOT_RUN` |
| Existing event/routine scenarios | PASS: motion timeline 9, door timeline 12, covered missing-morning timeline 33 | Deterministic TEST_ONLY; not resident training or real Home behavior |
| `make app-test` | PASS: 30/30 | Shared JS tests |
| `make pwa-68-browser-test` | PASS: 3/3; PWA catalogue 92/92 | Chromium with mocked Connected Lite transport; no backend network or Android WebView |
| `tests/engineering_dashboard` | PASS: 98/98 | Existing GS-124/service/access/auth tests, host only |
| Component-gate meta tests | PASS: 49/49 | Includes unittest-prefixed GS-177 browser evidence handling |
| Engineering registration tests | PASS: 6/6 | Preserves canonical stage membership and GS-177 stages |
| `make feature-coverage-test` | PASS: 213 features, 242 modules, 25 physical cases; 22/22 mapping tests | Registration consistency only |
| Latest `make validation-pwa` report | FAIL, exit 2 | Browser 86/86 PASS; P0 26/26 checks but `product_status=PARTIAL`; the old browser-stage marker regex was corrected and focused-tested afterward; aggregate not rerun |
| `python3 validation/run_gs177_android.py` without origin | BLOCKED, exit 127 | `approved_hosted_backend_origin` absent; no connected APK built |
| Render deploy / PostgreSQL restart and backup | NOT_RUN | No authorized connected Render account/service or billing approval |
| Admin bootstrap in cloud | NOT_RUN | No service/database to bootstrap; source provides interactive `bootstrap-admin` and `rotate-password` commands |
| Mobile-data laptop-off and physical Hub E2E | NOT_RUN / BLOCKED | No connected APK/hosted API or approved physical Hub qualification |
| Full product release gate | NOT_RUN | Not run as ordinary development validation |

P0's 26 assertions plus its browser check are software scenario evidence only;
`product_status=PARTIAL` remains a gate failure because production GS-148
identity/CloudSync composition is incomplete. Do not relabel it PASS. The current
routine API reports `UNSUPPORTED_MULTI_DAY`; the existing Hub `RoutineService`
has no longitudinal/calendar baseline learner. The Simulation Lab can run the
existing 92-entry scenario catalogue and the verified three scenarios, but
multi-day resident learning and a trained resident model are not delivered.

### Deployment, bootstrap and owner acceptance boundary

No Render MCP/deployment connection or approved hosting/billing authorization
was available. `render.yaml` remains a deployable blueprint with PostgreSQL,
but there is no real HTTPS URL, database backup/recovery receipt or hosted
source revision. `GS177_BACKEND_ORIGIN` is not configured in GitHub Actions;
the connected APK build gate therefore cannot run. The prior
`0.3.0-branded-offline` artifact remains the latest APK and is not connected.

After the owner authorizes a Render workspace/service and stable HTTPS URL:

1. Set repository Actions variable `GS177_BACKEND_ORIGIN` to the exact HTTPS
   service origin. Do not set an app password/token in Actions or the APK.
2. Deploy and verify `/healthz` and `/readyz`, PostgreSQL schema startup,
   restart recovery and provider-managed backup/restore configuration.
3. In a secure Render shell with `DATABASE_URL` supplied by the service, run
   `cd code/parivar_saathi_android_app/server` then
   `python connected_lite.py bootstrap-admin --email <owner-email>`; type a
   unique password of at least 16 characters at the hidden interactive prompt.
   The command prints only the account id. The account receives a random
   `gs177-test-*` Home on login. Use the same interactive
   `rotate-password --email <owner-email>` command to rotate and revoke all
   sessions. Deliver the password through the owner's private password manager
   if an operator performs bootstrap; never put it in Jira, Git, CI or chat.
4. Configure `GS177_KEYSTORE_B64`, `GS177_KEYSTORE_PASSWORD`, `GS177_KEY_ALIAS`
   and `GS177_KEY_PASSWORD` only as GitHub Actions secrets if the owner supplies
   an approved persistent pilot keystore. Without it, the hosted debug key is
   ephemeral and the old APK may need uninstalling before update.
5. Build and verify the connected APK, then perform owner-phone cloud/simulation/
   routine/Engineering/offline/reconnect acceptance with the laptop off. Phone
   evidence must be recorded separately from host and mock-browser PASS.

Current commit checkpoint at authoring: branch
`feature/gs-177-caregiver-android`, base HEAD
`6749b9e0cb5785a00cb87df88cb424b6107073bd`; the implementation changes remain
uncommitted until final review. Preserve every pre-existing modified and
untracked path. Keep GS-177 open. On resume, inspect current Git/remote state and
preflight again before writing; then complete authorized cloud setup and the
owner-phone acceptance. Do not modify canonical GS-40 or run firmware/HIL,
provisioning, serial, eFuse or protected-key operations.

### GS-177 resumed Connected Lite source and validation checkpoint — 2026-10-17

This checkpoint resumes the preserved uncommitted implementation in the
authorized GS-177 worktree; it is not a fresh implementation. Startup checks
confirmed workspace `/home/udaybhan/projects/Ghar_sajag_gs177`, branch
`feature/gs-177-caregiver-android`, local/remote starting HEAD
`6749b9e0cb5785a00cb87df88cb424b6107073bd`, GitHub origin unchanged, and no
active competing writer. The mandatory context preflight passed
(`2026-10-13.001`). GS-177 comments 11319, 11320, 11325 and 11330, GS-125
comment 11061, and the cited dependency/validation decisions were reconciled.
The canonical GS-40 worktree was only read for the requested Hub audit and was
not modified; no hardware, provisioning, serial, eFuse, or HIL operation ran.

The connected application source reuses the shared Parivar Saathi PWA, the
production local simulation lab/scenario catalogue, the GS-124
`DiagnosticReadService`/authorization boundary, and the GS-120 seven-area
engineering structure. It does not recreate the engineering domain service,
mount the development `http_api.py`, accept `X-Actor-Id`, or mount the GS-148
real Hub event route. The added `/lite/v1` API is restricted to isolated
synthetic `gs177-test-*` Homes. It has operator-only bootstrap/rotation,
scrypt password storage, opaque revocable 12-hour sessions, current account,
Home membership, role and ownership-epoch checks, same-origin POST protection,
request-size/auth/simulation limits, PostgreSQL schema migration support, and
durable synthetic run records. Caregivers see the shared caregiver screens;
Simulation Lab and Engineering tabs appear only for server-authorized TEST_ONLY
admins. The Android WebView uses a build-approved HTTPS origin and serves the
shared PWA bundle with origin/navigation restrictions. The app reports
`NO_HUB_CLOUDSYNC`, physical state/freshness `UNKNOWN`, and no physical
measurements. It does not claim real-home caregiver consent or Hub data support.

The seven Engineering areas are integrated as an Android/PWA adapter to the
existing GS-124 authorized read projection and saved synthetic runs. Hardware
identity, RSSI, battery, firmware, radio delivery, physical ACK and guided
installation evidence remain UNKNOWN/UNSUPPORTED/NOT_RUN where the approved
source is absent. Existing routine/activity rules can be run and inspected;
the current simulator has no multi-day resident baseline learner, so the API
and UI state `UNSUPPORTED_MULTI_DAY` and do not imply a trained resident model.
The existing catalogue contains 92 scenarios; validated deterministic cases
are motion, door open/close, and covered missing-morning activity. Run history
survives local API/application reconstruction in SQLite tests. PostgreSQL
restart recovery remains untested until deployment.

`render.yaml` configures one Gunicorn/Python web service and managed PostgreSQL;
the WSGI readiness path runs schema migrations. Gunicorn is pinned in server
requirements, and the WSGI entry point/requirements/blueprint are registered as
Connected Lite stage inputs. The Render plan identifiers were checked against
Render's current Blueprint reference. No Render account, service, PostgreSQL
instance, billing authorization, or deploy credential was available to
provision; therefore there is no hosted URL. A local Gunicorn smoke using
SQLite returned PASS for `/healthz` and database-backed `/readyz`. Psycopg
3.2.6's CPython 3.12 manylinux wheel resolved for the blueprint's Python 3.12
runtime; no PostgreSQL server or PostgreSQL migration/restart was available for
a live database test.

#### Validation receipt

| Command or stage | Result | Scope and limits |
|---|---:|---|
| `python3 validation/run_gs177_connected_lite.py` after final API test addition | PASS: 12 API/WSGI tests, 6 JavaScript runtime tests, 3 existing lab scenarios | SQLite/local host; motion timeline 9, door timeline 12, missing-morning timeline 33; physical NOT_RUN |
| Gunicorn WSGI smoke | PASS `/healthz` and SQLite-backed `/readyz` | Local host only; not a hosted PostgreSQL test |
| `make pwa-68-browser-test` with cached Chromium 153 and isolated dependency path | PASS 3/3; catalogue 92/92 | Connected browser transport is mocked; no live network, Android WebView, or owner phone |
| `make validation-framework-test` | PASS 50/50 | Includes inherited isolated `PYTHONPATH` regression and P0 fail-closed assertion |
| Engineering registration tests | PASS 6/6 | Existing GS-116 stage membership preserved |
| `make feature-coverage-test` | PASS: 213 features, 242 modules, 25 physical cases; mapping tests 22/22 | Mapping integrity only; not semantic/physical qualification |
| `make app-test` | PASS 30/30 | Shared application JS tests |
| Final `make validation-backend` report `code/evidence/validation_framework/backend-1792247859346014736/report.json` | **FAIL**, physical NOT_RUN | 527 Python, 92 functional, 98 diagnostic, 12 Connected Lite API, 9 CloudSync security, 18 CloudSync simulation, mTLS/worker/contract/health/HTTP/bridge stages PASS. Registered P0 stage has 26/26 software checks plus one Chromium test but `product_vertical_status=PARTIAL`; GS-148 production Hub credential/enrollment-generation binding is absent. The gate correctly returns FAIL. |
| Earlier `make validation-pwa` report `code/evidence/validation_framework/pwa-1792243150186487736/report.json` | **FAIL**, not a current PASS receipt | That run had 84 browser tests pass and two mobile browser tests time out; its Connected Lite browser stage also lacked `websocket-client` because the child environment replaced `PYTHONPATH`. The two timed-out tests passed in isolated reruns, the dependency was installed outside the repository, `base_environment()` now preserves inherited isolated paths, and the direct 3/3 browser stage passed. The full PWA aggregate was not rerun after that fix; P0 remains PARTIAL. |
| Full product release gate | NOT_RUN | Not an ordinary development gate and not authorized as a release candidate |

The backend P0 output separately reports the exact product gap:
`GS-148: production Hub TLS/credential authenticator and enrollment-generation
registry binding are not configured; local test credential only`. Individual
P0 host checks do not promote the product vertical to PASS. The Connected Lite
deployment does not accept real Hub events.

#### Cloud, Android and owner acceptance

No cloud admin was bootstrapped and no credentials were created. The secure
operator procedure remains `python connected_lite.py bootstrap-admin --email
<owner-email>` in the deployed service shell with hidden password confirmation
(minimum 16 characters); password rotation uses `rotate-password` and revokes
sessions. Credentials must be delivered privately and never placed in Git,
Jira, CI, or chat.

The Android source version is `0.4.0-connected-lite-staging`, package
`in.gharsajag.caregiver`, API 26+, preserving the approved logo and icons. The
workflow is gated on Actions variable `GS177_BACKEND_ORIGIN`, supports an
owner-supplied persistent pilot signing key through repository secrets, and
otherwise identifies the debug certificate as ephemeral. Since no hosted
origin is configured and the local Android SDK/JDK/Gradle build environment is
unavailable, the connected APK was **NOT_BUILT**. The previous
`0.3.0-branded-offline` APK is not this deliverable. No artifact URL, connected
APK checksum, or connected signing receipt exists.

Owner-phone tests A-E (mobile data with laptop off, live login/Home data,
cloud simulation/save/reopen/export, live Engineering authorization, app and
backend restart/reconnect) are **NOT_RUN/BLOCKED** because there is no deployed
service or connected APK. Physical Hub-to-Wi-Fi-to-CloudSync-to-Android remains
**BLOCKED/NOT_RUN**.

#### Read-only Hub Wi-Fi / CloudSync audit

The requested GS-177 comment 11330 audit found the current S3 target sets STA
mode/channel 1 and ESP-NOW channel 1 but does not compose Home Wi-Fi credential
provisioning, station connection, IP/gateway readiness, and reconnect into the
inspected target startup path. The cloud trust object has empty HTTPS origin/CA
and cannot provide an ownership binding; production Hub/Home/epoch,
enrollment-generation, TLS identity, and trusted-time providers are not
provisioned. The target recurring scheduler invokes NodeHealth; it does not
schedule the event `CloudSyncWorker::run_once` batch path. That worker already
contains the exact EventKey/retry/durable-COMMITTED-before-retirement logic,
but the inspected target does not enable it. The GS-148 authenticated durable
event route exists in backend source but is not mounted by Connected Lite.

Real Hub → Home Wi-Fi → Cloud → Android therefore still requires: (1) approved
protected Wi-Fi provisioning plus STA/IP/reconnect and ESP-NOW coexistence
qualification; (2) target scheduling of the existing event batch worker and
its exact authenticated durable receipt checks; (3) approved GS-68/GS-109
Hub/Home/epoch/enrollment identity, TLS/CA/key-custody, and trusted-time
providers; (4) production GS-148 identity middleware and caregiver projections
composed with the hosted service; and (5) separately authorized C3/S3/Home-Wi-Fi
physical outage/reconnect/replay/reboot and mobile-data end-to-end evidence.
This task changed no Hub firmware or canonical GS-40 files.

#### Git and next action

At the start of this continuation, local and remote branch HEAD were both
`6749b9e0cb5785a00cb87df88cb424b6107073bd`. The preserved implementation and
this updated handoff remain uncommitted until the source review is complete;
no reset, clean, stash, rebase, branch/worktree recreation, or force push was
used. The next operator action is to authorize a Render workspace and any
associated service/PostgreSQL charges (or provide an already-authorized
equivalent), then configure the resulting approved HTTPS origin for the APK
workflow. After hosted DB readiness, run the interactive admin bootstrap,
build/sign the connected APK, and execute owner-phone acceptance. Keep GS-177
open. The connected staging slice does not satisfy FULL_PRODUCT_HIL or physical
Hub CloudSync acceptance.

### GS-177 Render free-tier cost correction — 2026-10-17

The TEST_ONLY Render Blueprint now selects `plan: free` for both the single
Python web service and PostgreSQL. All other service/database settings remain
as previously configured. No Render service was created, synchronized or
deployed, and no charge or production credential was authorized.

Resource compatibility review: Render currently specifies the free web plan
as 0.1 CPU / 512 MB RAM and free PostgreSQL as 0.1 CPU / 256 MB, up to 100
connections. The API has bounded request/simulation inputs and intended
single-owner TEST_ONLY usage is low-volume. This is configuration-level
compatibility, **not a measured memory/latency or hosted load-test PASS**. The
Blueprint retains its two Gunicorn workers; actual worker memory and bounded
simulation behavior on the free instance must be observed after owner
authorization. Excess resource use, cold starts and transient free database
restarts can make the service slow or unavailable. APK builds run on a
GitHub-hosted Actions runner, not within the Render service allocation. The
Render `buildCommand` compiles the simulator during deploy and has not been
exercised on Render. Free web use is also subject to workspace instance-hour,
outbound bandwidth and build-pipeline quotas.

New Free Render PostgreSQL instances expire 30 days after creation; at expiry
they become inaccessible unless upgraded. The 14-day grace period is an
upgrade window, not a backup guarantee: Render deletes the database and all
data after that period. Free Postgres has 1 GB storage and no managed backups.
Before creating a database, record its creation/expiry date and set a reminder
well before day 30. Before expiry, use a trusted operator machine with
PostgreSQL client tools and the database's **external** connection URL (never
paste it into Git, Jira, chat, or a shell command recorded in history) to run:

Render Free web services do not provide SSH or dashboard shell access. This
supersedes the earlier handoff's Render-shell bootstrap wording: after owner-
authorized provisioning, bootstrap/rotate the admin from a trusted operator
machine with Python 3.12 and the pinned server requirements installed. Read
the external `DATABASE_URL` with a hidden prompt, export it only in that
process environment, and run `python connected_lite.py bootstrap-admin
--email <owner-email>` (or `rotate-password`) from
`code/parivar_saathi_android_app/server`; the script prompts for the password
without echo and revokes sessions on rotation. For example, from that
directory:

```sh
read -rsp 'External DATABASE_URL: ' DATABASE_URL
export DATABASE_URL
python connected_lite.py bootstrap-admin --email <owner-email>
unset DATABASE_URL
```

Do not put the DB URL/password in Jira, Git, CI, chat, or shell history.

```sh
umask 077
read -rsp 'Render external DATABASE_URL: ' DATABASE_URL
export DATABASE_URL
pg_dump --format=custom --no-owner --no-privileges \
  --file="gs177-test-only-$(date -u +%Y%m%dT%H%M%SZ).dump" "$DATABASE_URL"
unset DATABASE_URL
sha256sum gs177-test-only-*.dump
pg_restore --list gs177-test-only-*.dump >/dev/null
```

Move the dump and checksum to owner-controlled encrypted storage outside the
Render service and repository. Preserve the dump before expiry; do not rely on
the grace window. To restore after provisioning an authorized replacement
PostgreSQL database, read its external URL into `TARGET_URL` using the same
hidden-prompt pattern, export the variable, and restore **only into an empty
database** with `pg_restore --no-owner --no-privileges
--dbname="$TARGET_URL" gs177-test-only-<timestamp>.dump`; then unset the URL.
Keep the archive/checksum and a restore receipt. Do not upgrade to paid compute
or create a replacement service without owner authorization.

The Android Actions workflow now has a `workflow_dispatch` trigger in addition
to the existing filtered push trigger. Both paths retain the job condition
that requires repository variable `GS177_BACKEND_ORIGIN`; no manual input can
redirect the app to an arbitrary host. GitHub requires this workflow to exist
on the repository default branch for the Run workflow UI/API trigger. After
the file is present there, configure the variable to the approved HTTPS origin,
select `feature/gs-177-caregiver-android`, and dispatch the workflow. The
current branch change alone does not guarantee the button is visible while
the workflow file is absent from the default branch. No build was dispatched
because no approved backend origin exists.

Dependency review: server requirements pin `gunicorn==23.0.0` and
`psycopg[binary]==3.2.6`; the Blueprint selects Python 3.12.11, for which the
CPython 3.12 Linux x86_64 wheel-resolution check succeeded using isolated
`pip download --python-version 3.12 --implementation cp --abi cp312
--platform manylinux2014_x86_64 --only-binary=:all:`. `make -C code lab-build`
also passed locally, validating the Blueprint's simulator compile command.
PyYAML parsed both deployment/workflow files and explicit assertions confirmed
both resource plan IDs are `free`, the existing service/database settings are
unchanged, `workflow_dispatch` exists, and the origin-required job guard is
retained. `git diff --check` passed. These do not measure Render-side build
resource use or free-tier runtime performance; both remain NOT_RUN because
deployment is explicitly not authorized. The GitHub manual trigger is not
available from the GS-177-only branch until the workflow is present on `main`.

Checkpoint before this correction: `9b4bf94278f48fc7ae894c61cb30390749c718e6`
on `feature/gs-177-caregiver-android`, equal to the remote; worktree clean.
The implementation and focused checks are complete; commit/push is the next
delivery step. GS-177 remains In Progress; cloud deployment, connected APK,
phone acceptance, and physical Hub synchronization remain NOT_RUN/BLOCKED as
previously recorded.

## 2026-10-18 connected event/routine trace implementation update

This dated update supersedes the checkpoint above for GS-177 source, browser,
APK-build and cloud-readiness status. It does not change the canonical R1/GS-40
workspace or qualify the real Hub data path.

### Implemented and verified

- The connected caregiver Home now displays recent persisted TEST_ONLY event
  projections and routine decisions. Engineering Live Events uses the same
  projections. Run detail shows engine step results, expected-versus-observed
  checks, actual simulator decision reason, generated incident/notification
  counts, resulting simulated Home state and event occurrence/receipt fields.
- Projections are derived from the existing `lite_runs.result_json`; there is
  no second event database. A run has `sim:<run-id>` correlation and each
  displayed event has a run-local trace correlation. These are application
  trace IDs, not a product EventKey. Product EventKey remains explicitly
  unavailable for simulator events.
- Routine scenarios are selected from the existing catalogue category rather
  than scenario-name heuristics. Displayed reasons, steps and checks come from
  the existing scenario engine output. Multi-day resident baseline learning
  remains `UNSUPPORTED_MULTI_DAY`; synthetic incidents omit the local runner's
  internal `home_id` and `is_test` fixture values.
- Regression coverage was extended in the registered Connected Lite API and
  PWA browser stages. Commit `27baa615cb0b1db41a56ba12cacfbbc08de80c1a` is on
  `feature/gs-177-caregiver-android`, pushed, and matches the remote.
- Focused results: Connected Lite API 13/13; caregiver runtime 7/7; 3/3
  existing deterministic motion/door/morning scenarios; GS-124 authorization
  foundation 48/48; GS-124 service-access 30/30; validation framework meta
  tests 13/13; feature traceability mapping 22/22; registered PWA browser 3/3,
  including 92/92 catalogue render checks and connected admin/caregiver mock
  navigation, event/routine trace and direct caregiver-denial checks.
- GitHub Actions Android build run `39093929946` completed successfully at the
  source commit above. The branded APK uses package `in.gharsajag.caregiver`,
  version `0.4.0-connected-lite-staging`, API 26+ compatible configuration and
  the existing bundled PWA. The artifact was downloaded and its SHA-256 file
  validated. Build details and checksum are recorded in the GS-177 Jira update
  and final execution report. Signing is still a runner-generated debug key;
  this is not a persistent pilot update key.
- Public staging `/readyz` returned HTTP 200 with the database reachable.
  Unauthenticated `/lite/v1/me`, Home overview and Engineering calls returned
  403. This verifies the existing deployed revision's health and denial only;
  the event/routine API changes from this commit have not yet been deployed.

### Validation findings

- `make validation-pwa` remains FAIL. Its legacy PWA static budget reports
  117,011 total bytes versus 114,688 and 21,694 CSS bytes versus 18,432. The
  budgeted legacy assets/CSS were unchanged by this patch. Its full historical
  desktop/mobile Playwright stage had 59 passes, 3 legacy settings-selector
  timeouts and one interrupted case; it was stopped at the broad release-suite
  substage per development validation scope. The focused registered Connected
  Lite browser command was then run and passed 3/3.
- The first aggregate run's registered PWA browser stage failed because the
  system Python environment lacked `websocket-client`. It was installed with
  `cryptography` into `/home/udaybhan/.cache/gs177-pwa-venv`, outside the
  repository, and `make -C code pwa-68-browser-test` passed using that
  environment and the already-cached Chromium binary.
- The registered P0 vertical host scenario reported 26/26 checks PASS and
  `product_status=PARTIAL`. Physical hardware remains NOT_RUN; P0's partial
  product qualification is not a Connected Lite PASS.

### Remaining external acceptance

- Render deployment was not triggered: the current tools expose no Render
  control plane, credential or database URL. The existing Render service has
  `autoDeploy: false`. Deploy commit `27baa615…` to the already-approved Free
  staging service before claiming the updated cloud event/routine UI is live.
- The Free PostgreSQL export/restore rehearsal was NOT_RUN. The temporary
  external database allow-list is removed, no database URL is available here,
  and `pg_dump`/`pg_restore` are absent. Preserve/export the TEST_ONLY data
  before the recorded 16 November 2026 expiry; the expiry/grace policy and
  exact secure operator procedure remain in the preceding deployment-cost
  section.
- Actual owner-admin cloud login was NOT_RUN because the securely provisioned
  password is not available to this environment. Host login/session tests
  passed; do not reset the account merely to obtain a test credential.
- Mobile-data/laptop-off acceptance and physical Android installation remain
  NOT_RUN. No ADB-connected owner phone is exposed to this environment.
- Real C3/S3 Hub → Home Wi-Fi → authenticated GS-148 CloudSync → Android
  synchronization remains BLOCKED/NOT_RUN. The staging `/v1` event ingress is
  intentionally unmounted until trusted Hub identity, enrollment/ownership
  fencing, authenticated durable commit and caregiver projection are composed.
  Firmware/Wi-Fi/coexistence/reconnect/buffering and actual hardware operation
  were not changed.
- FCM, real incoming-call UI, TURN-qualified WebRTC, duplex S3 audio and
  unattended escalation remain NOT_RUN under GS-154/GS-157 and physical HIL
  dependencies. The APK still reports push and voice calling disabled.

### Git and workspace boundary

- GS-177 initial synchronized HEAD for this work: `f518e201af9d608042c56995a043d35c7e02bfee`.
- GS-177 committed/pushed HEAD: `27baa615cb0b1db41a56ba12cacfbbc08de80c1a`; remote equality verified.
- Canonical R1 remained read-only. At the final read-only check it was on
  `feature/r1-commercial-baseline`, HEAD `eef0152e5844eeb548a3b8d44d3cb8a05d06bf02`,
  with pre-existing modified/untracked files visible. None were changed from
  this GS-177 worktree.
- Keep GS-177 In Progress. The HTTPS backend redeploy, PostgreSQL backup/restore,
  owner admin login, owner-phone/mobile-data run, physical Hub sync and real
  calling remain outstanding acceptance gates.


### GS-177 authorized Render Free deployment receipt — 2026-10-18

- **Scope:** Deploy existing GS-177 connected TEST_ONLY event/routine projection to the previously authorized Render Free staging web service only. No new/paid resources, database settings, credentials, firmware, canonical GS-40 code or physical hardware were modified.
- **Existing service:** `parivar-saathi-lite-staging` (`srv-db9p25m1egvs7383iss0`), HTTPS `https://parivar-saathi-lite-staging.onrender.com`, `plan: free`, autoDeploy `no`. Existing PostgreSQL `parivar-saathi-lite-db`; free DB expiry recorded 2026-11-16 15:14:58 UTC (backup/restore not yet qualified).
- **Deployment:** `dep-dba3ut8m7kps73fclol0`, API-triggered for feature-branch HEAD `47e8faaff093184d0bcbf1bb95dc9e79aba03090` (contains implementation `27baa615cb0b1db41a56ba12cacfbbc08de80c1a`; last additional commit was documentation/traceability). Render reports `live`; finished **2026-10-18 03:40:52 UTC**. Logs show successful simulator build, Gunicorn gthread workers starting, Render service-live receipt and subsequent `GET /readyz` HTTP 200 from the new instance (e.g. 03:41:06 UTC).
- **APK:** existing GitHub Actions success `39093929946`, artifact `12123996919`, `in.gharsajag.caregiver`, version `0.4.0-connected-lite-staging`. APK checksum independently verified against zipped `SHA256SUMS`: `68f5ef1a6a4548803b5993a7b304576ebc05e299a3e62e5ad4bb0d50e65802b2`. Runner-generated TEST_ONLY debug key; earlier installed APK may need replacement/uninstall after local-data preservation.
- **Validation boundary:** Hosted deployment and internal readiness PASS; independent authenticated remote scenario execution, actual administrator login, PostgreSQL export/restore, owner Android install/mobile-data/laptop-off acceptance, real C3/S3 CloudSync, Android FCM, WebRTC/S3 audio and auto-call all remain **NOT_RUN/BLOCKED**. No signed-off product acceptance is implied. Historical broad PWA aggregate **FAIL** (legacy budgets/selector timeouts), P0 **PARTIAL**, full release gate **NOT_RUN**; focused GS-177 tests remain as documented in preceding checkpoint.
- **Worktree safeguard:** Changes made through authorized GitHub document update on the feature branch; the original Codex WSL worktree was not accessed. On resume inspect/fetch and reconcile remote documentation commit before additional edits; never reset/overwrite or assume local HEAD equals remote.
