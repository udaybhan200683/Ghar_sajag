# GS-177 caregiver Android continuation — 2026-10-17

## Current disposition

`ANDROID_CI_RETRY_PENDING`; the real phone + authenticated Internet backend acceptance is not met. A dashboard-only Android wrapper and a pinned hosted build workflow are implemented in the isolated GS-177 branch. No APK has been built yet, no live endpoint is configured, and the phone, production identity/session issuer, Firebase project, or S3 Hub media path are not available in this execution environment. Keep GS-177 open.

This build is an installable test shell intended to load the existing Parivar Saathi PWA from an administrator-provided HTTPS origin. It is not yet a usable caregiver service until that origin serves the actual authenticated PWA/backend.

## Branch and ownership

| Item | Verified value |
|---|---|
| GS-177 worktree | `/home/udaybhan/projects/Ghar_sajag_gs177` |
| GS-177 branch | `feature/gs-177-caregiver-android` |
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

| Check | Result |
|---|---|
| Local JDK / Android SDK / Gradle / ADB / apksigner | Not installed |
| Local Android build | `NOT_BUILT`; hosted workflow must produce first APK |
| Hosted Android workflow | Runs 39006792176 and 39006969459 both failed at Kotlin compilation. Run 39006969459 confirmed the unescaped `in` package segment and showed Android Java excludes did not exclude Kotlin files (prototype Firebase classes were compiled). The current GS-177 tree escapes `in` in Kotlin package declarations and relocates the three call/FCM classes to `prototype/android/`, outside the Gradle source tree; a third hosted build is pending. [Run 39006792176](https://github.com/udaybhan200683/Ghar_sajag/actions/runs/39006792176) · [run 39006969459](https://github.com/udaybhan200683/Ghar_sajag/actions/runs/39006969459) |
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

1. Commit and push the reviewed Kotlin package/source-layout fix only to `feature/gs-177-caregiver-android`. Verify the next hosted build; download an APK only after the job passes, then record run URL, commit, version, package, SHA-256 and signing certificate. If it fails, use the retained compiler diagnostics and repair only in this branch.
2. Obtain the approved live HTTPS PWA/API origin, production caregiver issuer/session + current-Home/epoch/revocation contract, persistent hosting/database, and a real Android phone with mobile-data access. Then install the artifact and capture actual device/backend evidence for each supported screen and denial/revocation case.
3. Keep GS-25 Firebase delivery and GS-154/157 plus GS-40/68/109/143/148 call/identity/Hub work as upstream gates. Do not claim FCM delivery, manual/automatic voice, backup escalation, or S3 HIL until performed with the real phone and hardware under separate approved test conditions.
4. Update Jira GS-177 and this handoff with the actual workflow and later device/backend results. Submit a reviewed GS-177 PR/handoff; do not merge into or push to the GS-40 branch.
