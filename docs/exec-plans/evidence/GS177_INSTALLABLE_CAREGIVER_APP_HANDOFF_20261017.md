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
