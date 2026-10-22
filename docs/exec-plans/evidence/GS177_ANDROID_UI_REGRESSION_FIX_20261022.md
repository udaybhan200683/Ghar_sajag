# GS-177 Android UI regression correction — 2026-10-22

## Scope and owner direction

Owning issue: GS-177 (In Progress, Rank 34). Integration dependency: GS-179
(In Progress, Rank 173). Rank and issue acceptance were not changed. The binding
visual specification is GS-177 comment 11534, with defect history in comment
11530. It approves the existing shared caregiver PWA Home after authorization
and a thin, flat, bottom-aligned text ribbon: Home | Devices | Reports | Settings.
The illustrated positive monitoring values in the reference are not data.

## Root causes and correction

- **Slow sign-in:** `connected_lite.mjs` previously waited for `/lite/v1/me`
  before rendering the credential form. The form now renders first; session
  restore runs asynchronously and single-flight. Focus/input cancels the restore,
  and a generation check ignores late responses. Login verifies the server session
  with `/me` before exposing Home, prevents duplicate submits, and opens Home by
  default. A `GS177_STARTUP login_form_visible_ms` diagnostic records UI timing
  only, without credentials or tokens.
- **Navigation position:** `dockNavigationUnderHeader()` moved the navigation
  element under the header and sticky CSS kept it above the content. The
  reparenting logic and sticky/header positioning were removed. The connected
  caregiver nav is now four text-only labels in a flat fixed 56 px full-width
  ribbon at the bottom of the WebView viewport. Content reserves scroll space;
  active state is a subtle background/text highlight; minimum targets are 48 px.
- **Home mismatch:** the authenticated connected Home path already had access to
  authorized product projections but rendered a separate legacy hero/tiles and
  surfaced its tool-oriented UI as a primary view. It now uses that same
  authorized projection in the approved Home hierarchy: branded header with
  tagline/date/Away, monitoring hero, routine/activity/connectivity summary,
  four information cards and recent-event timeline. Existing Devices, Reports
  and Settings views remain reachable; role-gated Engineering/Simulation remain
  under Settings. No second UI/data engine or API was added.

Home values come from the authenticated session Home's existing caregiver
projection. Unrecognized source data fails closed. Stale/unknown status cannot
become a positive health claim; HOST_SIM/TEST_ONLY data remains labelled as
such and does not imply physical evidence. The existing Away control remains
unchanged (disabled in this projection because no authorized Away action is
provided by its current API).

## Native Android viewport

`MainActivity` enables edge-to-edge layout, reserves status/navigation-bar and
cutout insets outside the WebView, and uses the greater of system-bar or IME
bottom insets. The manifest sets `adjustResize`. The PWA ribbon stays at the
bottom of the available WebView viewport, immediately above Android's system
navigation region, without an extra PWA safe-area gap. This is source-level
implementation; phone/emulator behavior remains unverified.

## Reuse and validation registration

Reused the single shared caregiver PWA, existing login/session API, GS-148
Home/NodeHealth/event projections, existing brand asset, existing four page
flows and the maintained Android WebView wrapper. No simulator API, new auth
path, new monitoring store or live deployment was introduced.

`docs/validation/MASTER_TRACEABILITY.csv` now registers
`GS177-CONNECTED-LITE-LOGIN-01` / `GS177-CONNECTED-LITE-LOGIN-001` against the
existing browser stage. The existing connected Home trace row covers the
approved design/fixed ribbon, the Android origin row covers viewport handling,
and `PHY-GS177-ANDROID-01` now explicitly retains phone timing, keyboard,
system-inset and live-authorized-data checks as NOT_RUN. Feature mapping remains
owned by GS-130.

## Local validation

At base source `6d807e4f9823c5ce281697aae6edbc48bf8a0234`, after the described
working-tree changes:

- `node --test code/tests/js/caregiver_runtime.test.mjs` — PASS, 9/9.
- `PATH=/tmp/ghar_sajag_ui_validation_venv/bin:$PATH python3 code/validation/run_gs177_connected_lite.py` — PASS: caregiver API 20 tests, JS runtime 9 tests, 3 deterministic HOST_SIM scenarios; physical NOT_RUN.
- `PATH=/tmp/ghar_sajag_ui_validation_venv/bin:$PATH make -C code validation-framework-test` — PASS, 51/51.
- `make -C code feature-coverage-test` — PASS after registration: 224 features / 278 modules / 26 physical cases, mapping tests 22/22.
- `node --check code/tools/sim/pwa/connected_lite.mjs` — PASS.
- `python3 -m py_compile code/tests/pwa_68_browser_test.py` — PASS.
- `python3 -m json.tool code/validation/suites.json` — PASS.
- `make -C code pwa-68-browser-test` — command exited 0 but skipped the browser cases because this host has no Chrome/Chromium. This is NOT browser PASS; the provisioned GitHub Actions workflow must run the browser assertions.
- `adb devices -l` — NOT_RUN; `adb` is not installed. No physical phone interaction occurred.
- GitHub Actions run [39721322469](https://github.com/udaybhan200683/Ghar_sajag/actions/runs/39721322469) — SUCCESS on source `2a1b5ffa9a52d4ad81726d8d99ba95773ff03085`: PWA browser 4/4 with 92/92 catalogue assertions; registered caregiver API stage 20 checks; Android dashboard stage 10 checks including `testDebugUnitTest` and `assembleDebug`; voice-prototype stage 26 checks; APK v2 signature verification and upload passed.

## APK artifact

Artifact ID `12401098317`, name `parivar-saathi-caregiver-debug-2a1b5ffa9a52d4ad81726d8d99ba95773ff03085`, uploaded artifact SHA-256 `9c624301a13c07e5ee22d05c7eca4fe61b80872d8356ccb978e8d41a6d8720cd`. Downloaded APK size: 2,927,482 bytes. APK SHA-256: `c42fd1817f85eae52f9e7df3cb016a173ff0275b20307a2274b48a07042bab64` (downloaded file matched the artifact SHA256SUMS). Package `in.gharsajag.caregiver`; version `0.4.0-connected-lite-staging`; source revision `2a1b5ffa9a52d4ad81726d8d99ba95773ff03085`; backend origin `https://parivar-saathi-lite-staging.onrender.com`; `GS177_LOCAL_LAN_TEST_ONLY=0`; signing is runner-generated Android Debug key, certificate SHA-256 `1a7d691b550351607b336250b6c0a9b41a35e1d390b2fd81a8b059eaa3747fb5`. This testing signature may require uninstalling the previously installed debug APK before installation. It is not owner-controlled pilot signing. The APK was not installed on a phone and is not aligned to the WSL2 PostgreSQL/Hub HOST_SIM route.

The temporary Python environment used pinned test dependencies only; no repository
runtime dependency was added. The initial Actions run 39721098614 is preserved as a
failure: the new login-race and Home/navigation browser cases passed, but the
existing offline-startup case asserted old login copy and stopped before Android
build. The assertion was corrected. Follow-up run 39721322469 passed browser, GS-116
stages, Android build/signature and artifact upload, as recorded above.

## Remaining acceptance boundaries

The successful APK workflow uses its configured Render staging origin and does
not redeploy Render. It therefore does not connect the APK to the WSL2 PostgreSQL
used by the existing HOST_SIM fixture. No real S3 mTLS
identity, physical Node event, production caregiver authority or same-event
backend route is established by this UI change. The local prior screenshot file
is an older design and is not used as the binding reference; browser structural
assertions check the approved elements, but pixel-by-pixel screenshot matching
and font scale/system-navigation behavior await CI/device evidence.

GS-177 remains In Progress. Next executable step is to run the registered
Android/PWA workflow, collect APK source SHA, version, origin, signing identity
and artifact digest, then have the owner install it on the identified phone for
cold/warm login, keyboard, system navigation and authorized Home observation.
Actual Hub, Node and physical PIR testing remains under GS-117/GS-179 and its
separate fixture, credential and network approvals.
