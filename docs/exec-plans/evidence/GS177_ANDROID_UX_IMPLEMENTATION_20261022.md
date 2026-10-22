# GS-177 authenticated Android UX implementation — 2026-10-22

## Scope and preflight

- Owning Jira: GS-177. Validation ownership: GS-116 and GS-130.
- Authorized worktree: `/home/udaybhan/projects/Ghar_sajag_gs75_notifications`.
- Branch: `feature/gs75-autonomous-notifications-20261020`.
- Starting local and remote HEAD: `aeb2ab52a4f1c0e286817b77026d4fe13f03580b`.
- Canonical branch at inspection: same HEAD; branch divergence 0/0.
- Context preflight: PASS, local and canonical context `2026-10-13.001`.
- The selected feature worktree was clean before this evidence file was added. The active GS-179 worktree has unrelated `code/Makefile`, `docs/product/R1_WORK_STATE.md`, and untracked managed-component changes. No overlapping caregiver UI or validation-test changes were present in that worktree.
- The GS-179 server, database, worktree, credentials, network configuration, and `docs/product/R1_WORK_STATE.md` are excluded from this task. The shared R1 work-state update is deferred until GS-179 ownership is coordinated.

## Change triage

```text
BUG_CLASSIFICATION=R1_FIX
REQUIREMENT_SOURCE=GS-177 approved five-screen Android UX and current authenticated caregiver API projection
DECISION_IDS=NONE; owner-approved GS-177 UX decision for qualified MISSING_MORNING_ACTIVITY concern styling
TASK_SCOPE=Focused presentation and existing-suite regression assertions for authenticated Home, Devices, Reports, and Settings
OUT_OF_SCOPE=Backend/API changes; simulator renderer; routine-learning; notification scheduling/delivery; call escalation; Hub/Node behavior; physical/HIL operations; release gate
```

## Components and shared interfaces

- Application component: authenticated caregiver UI shared by the Android WebView: `code/tools/sim/pwa/connected_lite.mjs`, `code/tools/sim/pwa/caregiver.css`, and existing browser test `code/tests/pwa_68_browser_test.py`.
- Validation component: existing GS-116 registered stage `gs177-caregiver-offline-browser`; existing JS runtime checks and GS-130 traceability row `GS177-CONNECTED-LITE-HOME-01`.
- Shared API contracts are read-only inputs: authenticated `/lite/v1/homes/<home>/overview`, `devices`, `routines`, `incidents`, `reports`, and incident `claim`/`acknowledge`/`resolve` actions. No API or backend mutation is in scope.
- Existing PWA and Android wrapper behavior to preserve: immediate login form, async session restore/cancellation, server authorization, default Home after login, session expiry, source/freshness truth, and fixed text-only Home/Devices/Reports/Settings tabs.

## Prior suites and planned checks

- Reuse `make pwa-68-browser-test` and extend its existing authenticated GS-148 mock-transport browser case for current/concern/stale/unknown/offline states, incident acknowledgement/resolution, navigation, narrow layouts, long text, and reference-visible controls.
- Reuse `node --test code/tests/js/caregiver_runtime.test.mjs` for login/session, origin, navigation and Android inset contracts.
- Inspect and run the existing GS-177 connected Lite API runner only if its fixtures are isolated from the active GS-179 service and data.
- Reuse the existing Android registered workflow/runner for package and bundle validation after relevant tests pass. No emulator/phone/HIL command is authorized or available in this task unless separately confirmed safe and present.
- Physical phone, genuine Hub/Node event provenance, notification delivery and physical HIL acceptance remain separate from browser and APK-build evidence.

## Reference and implementation decisions

- The five owner-provided reference PNGs are untracked assets in the canonical worktree. They remain unchanged and will not be staged or copied into this branch.
- Reuse the authenticated `connected_lite.mjs` projection and `caregiver.css`; do not import `app.js` or simulator state, API routes, actor headers, or sample defaults.
- A current, authorized, covered `MISSING_MORNING_ACTIVITY` with source-backed concern qualification may use the approved red attention appearance while retaining semantic severity `CONCERN`. Unknown, stale, offline, acknowledged, and resolved data must not receive active-emergency styling. No escalation policy or severity algorithm is changed.
- The current authenticated reports API provides durable event counts/history and existing incident/routine drilldowns; no unsupported charts, period metrics, PDF controls, or synthetic statistics will be added.
- Current Settings support is account/session/logout, backend/build status, and guarded Hub setup messaging. Unsupported household, Wi-Fi credential, device provisioning, or notification controls will not be activated.

## Execution record

Implementation source commit: `93f3ea4ecec46ff59182446a02e6d0591d6876f4` on `feature/gs75-autonomous-notifications-20261020`; pushed to the matching origin branch. Canonical remains at `aeb2ab52a4f1c0e286817b77026d4fe13f03580b`.

### Implemented scope

- Updated the authenticated `connected_lite.mjs` caregiver renderer, `caregiver.css`, and the shared PWA title/tagline in `index.html`; no legacy renderer, backend, Hub, Node, scheduler, escalation rule, or API contract was added.
- Corrected connected Home branding/tagline layout, mobile header and status spacing, summary chips, four information cards, door icon, recent-event layout, warning treatment, and mobile text wrapping. Preserved the four text-only bottom tabs at 56 px and at least 48 px per tab target.
- Added presentation-only severity qualification. Current authenticated, covered missed-morning decisions may display red attention while retaining source severity `CONCERN`. Unknown routine coverage, stale source, unresolved-but-acknowledged, resolved, and offline Node states cannot be promoted to a resident-emergency claim.
- Reused durable event history, NodeHealth, incident lifecycle and existing Settings/session/Hub-setup projections. Reports contain source-backed event history only. Unsupported family, Wi-Fi, provisioning, fake battery and chart/period controls remain inactive/absent.
- Unknown source data now fails closed in the connected Devices, Reports and Routine views rather than falling through to simulator presentation. The separate simulator mode remains opt-in in `boot.mjs`.
- Expanded the existing registered GS-177 browser assertion and GS-116 registry success marker; updated its existing GS-116 adjudication unit-test fixture. The existing GS-177 Android runner now checks that the packaged `index.html`, `boot.mjs`, `connected_lite.mjs`, and `caregiver.css` match source bytes, and its existing suite inputs track those files. Updated the existing GS-130 source inventory entry. No validation suite or test framework was added.

### Local validation

Executed against the selected feature worktree based on starting commit `aeb2ab52a4f1c0e286817b77026d4fe13f03580b`; local test inputs contained the uncommitted GS-177 changes recorded above.

- `node --check code/tools/sim/pwa/connected_lite.mjs` — PASS.
- `node --test code/tests/js/caregiver_runtime.test.mjs` — PASS, 9/9.
- Existing `Pwa68BrowserTest` class — PASS, 4/4 tests; its catalog assertion rendered 92/92 PASS. Executed in Chrome for Testing 153.0.8010.12 with an in-memory DevTools WebSocket adapter because `websocket-client` is not installed in the local Python environment. The simulator test server and logs were isolated under a unique `/tmp/gs177-isolated-browser-*` root. The caregiver API was mocked; no GS-179 service or database was contacted.
- `PYTHONPATH=code python3 -m unittest discover -s code/tests/python -p test_component_gate.py -v` — PASS, 51/51. This verifies the updated registered browser success marker, Android source-parity registration, and existing gate adjudication behavior.
- `make -C code feature-coverage-test` — PASS; traceability consistency reports 224 features, 278 source modules and 26 physical cases; its existing framework suite passes 22/22. Updated the existing GS-130 Home/Android traceability rows to record commit `93f3ea4`, the registered assertions, workflow `39781674209`, APK metadata and remaining phone/backend gaps. This consistency check does not establish semantic or physical coverage.
- `python3 -m py_compile code/tests/pwa_68_browser_test.py code/tests/python/test_component_gate.py` — PASS.
- `git diff --check` — PASS.
- The first framework-unit run found its old expected browser success marker; the existing test fixture was updated to the new precise success message and rerun PASS. No production/runtime behavior was altered to satisfy the gate. A final framework-unit rerun after adding Android source-parity assertions also passed 51/51.

### Refreshed Jira and existing APK evidence

- Refreshed GS-177: status remains **In Progress**. Comments 11557 and 11559 add a separate TEST_ONLY requirement to survive Yogi/Agrim Wi-Fi changes without rebuilding around a fixed `192.168.1.6`, while preserving authenticated server identity and TLS validation. This UX package does not change Android endpoint selection, certificate, discovery, or GS-179 server/network code; that requirement remains for a separately coordinated GS-177/GS-179 implementation.
- The latest successful matching LAN TEST_ONLY workflow artifact inspected was run `39766494060`, source `8c134487a4afdde0869aad0e0c5b9c9b19f1b544`, package `in.gharsajag.caregiver`, origin `https://192.168.1.6`, and `gs179_local_lan_test_only=1`. It records `runner-generated-debug-key; local-lan-test-only`; its certificate SHA-256 was `58f9d58042af12a1eca6b4fadd8bb836e3b04220995fb710ad3eac0d1b1972ac`. The artifact's source Gradle configuration used versionCode 3 and versionName `0.4.0-connected-lite-staging`.
- A separate successful staging workflow artifact from the same source commit also used a runner-generated debug key. The current source still has the same package, versionCode 3 and versionName. Exact update eligibility will be decided by comparing the new artifact signing certificate with the LAN artifact certificate; the installed phone package itself cannot be inspected here.
- No ADB executable or local Android SDK configuration is available. No APK has been installed, replaced, or uninstalled.

### Before/after screenshots

The baseline image is the original Home view captured with the same TEST_ONLY mock profile, before UI changes. All post-change captures are 390×844 Chrome views using mock authenticated GS-148 data and visibly labeled TEST_ONLY; they are not installed-APK or resident data evidence.

- Before Home: [home-before.png](GS177_ANDROID_UX_IMPLEMENTATION_20261022/screenshots/home-before.png)
- Normal Home: [home-normal-after.png](GS177_ANDROID_UX_IMPLEMENTATION_20261022/screenshots/home-normal-after.png)
- Qualified missed-morning concern: [home-negative-after.png](GS177_ANDROID_UX_IMPLEMENTATION_20261022/screenshots/home-negative-after.png)
- Offline NodeHealth: [devices-after.png](GS177_ANDROID_UX_IMPLEMENTATION_20261022/screenshots/devices-after.png)
- Durable history: [reports-after.png](GS177_ANDROID_UX_IMPLEMENTATION_20261022/screenshots/reports-after.png)
- Supported account/session settings: [settings-after.png](GS177_ANDROID_UX_IMPLEMENTATION_20261022/screenshots/settings-after.png)

### APK workflow outcome and remaining acceptance

- Existing workflow [run 39781674209](https://github.com/udaybhan200683/Ghar_sajag/actions/runs/39781674209) completed successfully on source `93f3ea4ecec46ff59182446a02e6d0591d6876f4` from `feature/gs75-autonomous-notifications-20261020`. The HTTPS staging origin was explicitly supplied as `https://parivar-saathi-lite-staging.onrender.com`; `gs179_local_lan_test_only=0`.
- Workflow results: browser 4/4 tests and 92/92 catalog scenarios; authenticated Home regression PASS; existing registered API stage 20 checks PASS; Android dashboard stage 10 checks, 0 skipped, PASS; existing voice prototype stage 26 checks PASS. The Android runner performed its existing unit/build/source-bundle checks, including `testDebugUnitTest`, `assembleDebug`, and source-to-APK asset parity. No GS-179 server or data was used.
- Artifact `parivar-saathi-caregiver-debug-93f3ea4ecec46ff59182446a02e6d0591d6876f4` is available from the linked workflow run through 2026-11-05. APK: package `in.gharsajag.caregiver`, versionName `0.4.0-connected-lite-staging`, source versionCode `3`, JDK 17, Gradle 8.9, Android compile SDK 35, 2,932,390 bytes, SHA-256 `71054f7876a00517c1d44bf72e07a2c973667429e3748e0be7053a199ac80e70`. Artifact build-info confirms the HTTPS staging origin, the existing bundled PWA source, push notifications disabled, and voice calling disabled.
- APK v2 signature verification passed. Signing used the runner-generated Android debug key because owner-controlled pilot signing secrets were not supplied. Certificate SHA-256 is `d24299590a0701cd4dc7d9346c67af3139f3f6f72200921c37720e4348c77a40`. The previously inspected GS-179 LAN APK used certificate SHA-256 `58f9d58042af12a1eca6b4fadd8bb836e3b04220995fb710ad3eac0d1b1972ac`; the signatures differ, so this artifact cannot update that APK in place. The installed phone package/signature cannot be queried in the current environment. No uninstall/install was attempted.
- Android emulator and owner-phone execution remain NOT_RUN; local ADB/Android SDK configuration is unavailable. Physical HIL remains outside scope. The workflow validates packaging and source parity, not actual WebView rendering, touch/keyboard/insets, lifecycle restoration or live caregiver authorization on a device.
- GS-177 Jira comments 11557 and 11559 also require TEST_ONLY server-origin behavior that survives Yogi/Agrim Wi-Fi changes without pinning the APK to `192.168.1.6`, while retaining server authentication and TLS validation. This UX package did not change endpoint selection, certificate handling, discovery, or GS-179 networking; that requirement remains an explicit GS-177/GS-179 coordination item.
- Do not change `docs/product/R1_WORK_STATE.md` until GS-179 writer ownership is coordinated. Updating that shared state remains a pending integration action.

No GS-179 source/worktree/server/database/network/credential changes were made. No canonical merge or shared R1 work-state edit is authorized in this execution.
