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

## Canonical GS-179 Wi-Fi and GS-177 UX integration — 2026-10-22

The owner requested that the completed router-independent TEST_ONLY Wi-Fi work be checkpointed before UX integration. That ordering was preserved: Wi-Fi implementation was committed first as `fd6437eee69ca6cfabd78ab3fc3b9f38801444db`; the approved UX implementation and evidence commits were then integrated on the canonical branch as `608c5ba40453f3eead9b5e831fe22dbbe68efed5` and `794b355364471c89bf0ec30006e77e5e64e15735`. Shared Settings and source/traceability conflicts were resolved by retaining the approved UX and reconnect/reset functionality together.

The combined regression exposed stale browser-test assumptions from before the approved UX change: an active urgent incident changes the Home heading, the authenticated watermark changed, and incident state is represented by a semantic `data-incident-state` attribute rather than visible label text. Existing source-linked assertions now derive the heading from authorized active incidents, check the current watermark, and assert semantic incident state. The focused browser case and full GS-179 run pass after this correction; no production assertion was weakened.

Combined validation on the integrated source:

- `make -C code gs179-postgres-e2e` — PASS, 55 tests; source-linked HOST_SIM event delivery, durable PostgreSQL and caregiver projection. Physical sensor remains NOT_RUN.
- `make -C code pwa-68-browser-test` — PASS, 4/4 browser tests and 92/92 rendered catalog assertions, including Home severity/freshness, all four tabs and responsive UX.
- Connected caregiver API — PASS, 22/22; JavaScript runtime — PASS, 10/10.
- GS-179 PostgreSQL security — PASS, 18/18; GS-116 validation framework — PASS, 51/51; GS-130 feature coverage/traceability — PASS, 225 features / 278 modules / 26 physical cases and 22/22 framework cases.
- JavaScript/Python syntax and `git diff --check` — PASS. Local Android Gradle build is unavailable because this host lacks Gradle/Android SDK; the authorized CI workflow is the APK build path.

The live laptop route is not ready for a phone test: current Agrim address is `192.168.1.8/24`, while existing portproxy still targets historical `192.168.1.6`. No elevated Windows forwarding/firewall change was made. Yogi → Agrim → Yogi on the physical phone, APK installation/signature comparison, real Hub authentication, and a genuine PIR event remain NOT_RUN. A combined APK workflow is required from the final pushed source; that build will not establish phone acceptance.

## Combined local-LAN APK follow-up — 2026-10-22

The established workflow completed the integrated local-LAN TEST_ONLY APK build on source `ed99dbe1d73286110670c0128e2476415e387d2a`:
[workflow run 39797650882](https://github.com/udaybhan200683/Ghar_sajag/actions/runs/39797650882), artifact `parivar-saathi-caregiver-debug-ed99dbe1d73286110670c0128e2476415e387d2a` (artifact ID `12434502262`, expires after 14 days). The artifact contains APK, build metadata and SHA256SUMS. APK SHA-256 is `5aaea3c6f71e1d60b401436d987fb50633c4766ba4e7318384e077ad7f0bd02f`; package `in.gharsajag.caregiver`, versionName `0.4.0-connected-lite-staging`, source versionCode 3, backend `https://desktop-3qqu64b.local`, local-LAN TEST_ONLY enabled, and trusted LAN CA SHA-256 `7152366fdcf6d64d2df6ad2eca86ec6a8a8d60dad43cc7a8738e353fe86eddd5`. Build used JDK 17, Gradle 8.9 and Android compile SDK 35. CI verified APK v2 signature. Signer certificate SHA-256 is `141f15cdaec4645094cb0657956f8b82110f2f4eccfda61a9b5260052e111392`; this runner-generated debug signer differs from the previously recorded local-LAN signer (`58f9d580…`) and staging signer (`d2429959…`). The installed phone signer was not inspected, and the APK was not installed. In-place update compatibility is therefore not established; with a different installed signer, Android requires uninstall/reinstall, which was not authorized.

The Android workflow's browser suite passed 4/4 and 92/92 rendered checks; the registered caregiver/API and Android stages passed (22 API checks, 12 Android dashboard checks, 28 voice-prototype checks), signature verification passed, and artifact upload passed. The overall GitHub run status remained `in_progress` after its only job had completed successfully; job result is success. A separate automatic default-origin push run `39797636040` failed in the first all-catalog test because Chrome DevTools did not start; the remaining three browser tests passed in that attempt. The manually dispatched `.local` TEST_ONLY run passed the same complete browser stage.

The workflow artifact is build evidence only. It does not establish physical installation, phone server reachability, Yogi → Agrim → Yogi reconnection, live Home authorization, Hub authentication, or physical sensor acceptance. Current laptop portproxy state still targets the earlier `.6` address while Agrim readback was `.8`; the actual phone route must be refreshed and observed before installation validation.

Final workflow status refresh: GitHub run `39797650882` finalized `completed / success` at 2026-10-22 14:50:44 UTC. Its only Android job had already completed successfully; the prior in-progress aggregate observation was delayed status propagation.

## Incremental five-reference visual correction — 2026-10-22

This work is on the explicitly authorized GS-75 feature worktree only. Starting feature HEAD was `ce663f071d5e6e535cc0898d1389608e2edec6de`; remote matched and the tracked worktree was clean. The latest committed canonical R1 HEAD was `8ca19768ea3da392d2badbb8b9e9077702bc54dc`. Context preflight passed (`2026-10-13.001`). A non-rewriting merge produced `266172237ec55ea17ede9f96ecd399d0898af9ef`. Its four conflicts were inspected: the canonical side already contained the earlier GS-177 UI plus the newer GS-179 reconnect implementation and corresponding traceability/evidence. Those four resolved files retain that combined committed version. No canonical worktree file, live service, database, certificate, network route or phone APK was changed.

### Reference inspection and visible comparison

All five owner images were opened from the canonical Android directory read-only. The original reference values are illustrative, so the live UI retains only authenticated backend values and explicit UNKNOWN/STALE/TEST_ONLY provenance. The old feature screenshots in this evidence directory provide the browser baseline. New 390×844 mock-authenticated Chromium viewport and full-page captures are in [`screenshots/visual-correction-20261022`](GS177_ANDROID_UX_IMPLEMENTATION_20261022/screenshots/visual-correction-20261022/). Full-page captures show the fixed bottom bar at the viewport position; they are browser composites, not Android phone images. Owner-installed screenshots `1000238617.png` and `1000238619.png` were not available as local files; the owner observations in the task request were used for comparison.

| Approved reference | Previous authenticated browser appearance | Incremental correction | Remaining difference |
|---|---|---|---|
| `Pastel Smart Home Dashboard UI.png` (normal Home) | Large status/hero stack, cramped three-column summaries, tight two-column cards and uneven recent events | Shorter hero and status stack, two-column mobile summaries with a full-width connectivity row, stable door/battery SVGs, clearer timeline, balanced card spacing; [before](GS177_ANDROID_UX_IMPLEMENTATION_20261022/screenshots/home-normal-after.png), [after](GS177_ANDROID_UX_IMPLEMENTATION_20261022/screenshots/visual-correction-20261022/home-normal-after-full.png) | Authenticated fixture lacks an OK press and night decision, so UNKNOWN remains visible. Real battery estimate/room statistics in the reference have no authorized source. |
| `home_negative_reference.png` | Red concern was already qualified but hero/cards were tall and crowded | Preserved `CONCERN` semantics and red presentation; compact event emphasis and card layout; [before](GS177_ANDROID_UX_IMPLEMENTATION_20261022/screenshots/home-negative-after.png), [after](GS177_ANDROID_UX_IMPLEMENTATION_20261022/screenshots/visual-correction-20261022/home-negative-after-full.png) | Fixture has one covered missed-morning rule, not the illustrated door/battery/night alerts. No emergency call is inferred from red styling. |
| `devices_reference.png` | Three narrow metrics and a dense NodeHealth row | Better status/icon alignment, source-backed Node identity and coverage grouping; [before](GS177_ANDROID_UX_IMPLEMENTATION_20261022/screenshots/devices-after.png), [after](GS177_ANDROID_UX_IMPLEMENTATION_20261022/screenshots/visual-correction-20261022/devices-after.png) | Battery percentage, life estimate, RSSI, room, and Hub-device list in the reference are unsupported by the current authorized projection. |
| `reports_reference.png` | Flat count, event history and drilldown buttons | Stronger count hierarchy, section heading, compact source-backed event timeline; [before](GS177_ANDROID_UX_IMPLEMENTATION_20261022/screenshots/reports-after.png), [after](GS177_ANDROID_UX_IMPLEMENTATION_20261022/screenshots/visual-correction-20261022/reports-after.png) | Weekly/monthly metrics, activity chart, insights and PDF export have no approved backend contract or committed data; GS-104 learning remains on hold. |
| `settings_reference.png` | Plain large text cards, uneven account/connection information | Grouped account/Home/session, Hub setup and app/connection rows with consistent icon wells and supported action styling; [before](GS177_ANDROID_UX_IMPLEMENTATION_20261022/screenshots/settings-after.png), [after](GS177_ANDROID_UX_IMPLEMENTATION_20261022/screenshots/visual-correction-20261022/settings-after-full.png) | Family, device, notification, scheduling, security and support controls in the image lack implemented authorization/capability. GS-179 reconnect/reset links remain capability-gated and need phone acceptance. |

The existing four fixed text-only tabs remain unchanged. Tests use the existing GS-116 browser case and its GS-130 `GS177-CONNECTED-LITE-HOME-01` mapping; no second renderer, simulator API, backend route, notification logic or validation framework was added. The CSS and markup changes are limited to authenticated presentation. GS-179 endpoint, TLS, WebView and server code were taken from the committed canonical merge and not edited afterward.

### Validation and delivery checkpoint

The browser evidence uses local mock transport, Chrome for Testing 153.0.8010.12, and source-backed fixtures in `tests/pwa_68_browser_test.py`. Added deterministic measurements at 320, 360, 390, 412 and 768 CSS px for horizontal overflow, header/hero bounds, summary/card containment, fixed 56 px bottom ribbon, and long English/Hindi text with 125% font scaling. Device, report and settings bounds use the same existing case. Browser screenshots are visual review evidence and do not establish Android WebView acceptance. Physical Android and real Hub/Node qualification remain NOT_RUN.

Test commands and final results are recorded below when the isolated regression completes. The entire `validation-pwa` target is deferred because its registered `gs179-postgres-e2e` stage can touch the parallel GS-179 environment; only independently isolated GS-177 stages are authorized here. Complete release and physical gates are NOT_RUN for this developer UI correction.

Executed isolated results on the visual-correction working tree:

- `GS177_SCREENSHOT_DIR=... PATH=<isolated Chrome for Testing 153> <isolated Python with websocket-client/cryptography> -m unittest discover -s code/tests -p pwa_68_browser_test.py -v` — PASS, 4/4 browser methods and 92/92 rendered catalog cases. The prior attempt's catalog DevTools read timed out locally; the subsequent isolated rerun completed 92/92. A further rerun after the Settings overview correction passed 4/4 and 92/92. The final extra assertion that Settings retains `COVERED / CURRENT` passed in a focused authenticated browser rerun, 1/1.
- `PYTHONPATH=code/backend:code <isolated Python> code/validation/run_gs177_connected_lite.py` — PASS, 22 connected caregiver API tests, 3 deterministic scenarios, 10 JavaScript runtime tests; physical NOT_RUN. It built only local host simulation outputs.
- `node --test code/tests/js/caregiver_runtime.test.mjs` — PASS, 10/10 after Settings action assertions.
- `PYTHONPATH=code python3 -m unittest discover -s code/tests/python -p test_component_gate.py -q` — PASS, 51/51.
- `make -C code feature-coverage-test` — PASS, 225 feature rows, 280 source modules, 26 physical cases; traceability framework 22/22. This proves mapping consistency, not phone or physical coverage.
- JavaScript syntax, Python syntax and `git diff --check` — PASS.

No new validation stage or test framework was added. Existing registered stage `gs177-caregiver-offline-browser` executes the expanded authenticated browser case. The source change that makes Settings use its authorized Home overview is read-only and preserves GS-179's capability-gated reconnect/reset handlers. Local Gradle/Android SDK and ADB are unavailable; APK packaging and installed-phone tests are NOT_RUN here. A combined feature-branch CI APK build, if dispatched after push, must be reported separately with exact source SHA and signer.

### Feature-branch checkpoint and Android package

- UI commit `8e34f86662bd2e9366d51eeffae0e3de420b9b91` followed merge commit `266172237ec55ea17ede9f96ecd399d0898af9ef`. The feature branch was pushed normally and exact remote HEAD matched `8e34f86662bd2e9366d51eeffae0e3de420b9b91`. The canonical worktree was not edited.
- The existing [Android workflow run 39823937174](https://github.com/udaybhan200683/Ghar_sajag/actions/runs/39823937174) checked out `8e34f86662bd2e9366d51eeffae0e3de420b9b91` from the GS-75 feature branch, using TEST_ONLY `https://desktop-3qqu64b.local`. Its sole `android-caregiver-apk` job completed **success** at 17:38:33 UTC. The GitHub aggregate run API still reported `in_progress` during this evidence write, so the job result is recorded precisely without claiming a final aggregate result.
- Job stages: browser 4/4 and catalog 92/92 PASS; registered caregiver API 22 checks PASS; Android dashboard 17 checks PASS; voice prototype 28 checks PASS; APK build, v2 signature verification and artifact upload PASS. `SOFTWARE PASS PHYSICAL NOT_RUN` is the registry classification. This does not validate handset rendering or voice calling.
- Artifact ID `12446445648`, name `parivar-saathi-caregiver-debug-8e34f86662bd2e9366d51eeffae0e3de420b9b91`, expires 2026-11-05. Downloaded APK size 2,955,956 bytes and SHA-256 `6db78ec63aa536d48628e1578f743d306e370eb01f2625e8d150d43f10e591a6`, matching artifact SHA256SUMS. Package `in.gharsajag.caregiver`; version `0.4.0-connected-lite-staging`; JDK 17, Gradle 8.9, compile SDK 35; pinned TEST_ONLY CA SHA-256 `7152366fdcf6d64d2df6ad2eca86ec6a8a8d60dad43cc7a8738e353fe86eddd5`; push notifications and voice calling remain disabled in this testing build.
- The downloaded APK's `assets/index.html`, `boot.mjs`, `connected_lite.mjs` and `caregiver.css` match the committed source byte for byte. `apksigner` verified v2; runner-generated debug signer certificate SHA-256 is `e7c04d1e151f5512813d4fbae02794f67225f28e2fbea98356e0a6748f100554`. This differs from the previous recorded local-LAN build signer `141f15cd...`; installed signer and in-place update compatibility are **unverified**. No phone installation/replacement/uninstall was performed.
- Existing GS-130 rows `GS177-CONNECTED-LITE-HOME-01` and `GS177-ANDROID-01` were updated in this feature worktree with the source, test, layout and package evidence. `make -C code feature-coverage-test` passed again: 225 rows, 280 modules, 26 physical cases; framework 22/22. This update does not promote physical acceptance.

### Integration handoff

The canonical committed branch advanced from `8ca19768ea3da392d2badbb8b9e9077702bc54dc` to `6754a2d9829960c1ddb81c958a7a3ead1de0e773` while this UI branch was being validated. That new commit records GS-179 evidence. The other session still owns GS-179 and has uncommitted canonical documentation/traceability work, so **do not merge this branch into canonical yet**. After exclusive integration ownership is handed off: read the latest canonical HEAD, GS-179 handoff and comments; compare UI/code/test/traceability differences; reconcile any newer committed GS-179 work into this feature branch without replaying the earlier integrated UX; then integrate only reviewed incremental GS-177 changes. Run the combined affected suites, build the final canonical APK, compare signer/package/source and obtain separate physical Android visual and connection acceptance. The current owner-phone successful `https://192.168.1.8` reconnect observation belongs to the earlier installed TEST_ONLY build; this new APK was not installed or used on a phone. Unsupported reference-only battery, analytics, PDF and Settings controls remain absent pending their owning backend/product requirements.

Final workflow status refresh: GitHub run `39823937174` is `completed / success`; its only Android job is `completed / success`. The CI APK was built from UI source commit `8e34f86662bd2e9366d51eeffae0e3de420b9b91`; subsequent commits change evidence and traceability only.

## Canonical GS-177 + GS-179 integration checkpoint — 2026-10-23

The canonical worktree is `/home/udaybhan/projects/Ghar_sajag_r1` on `feature/r1-commercial-baseline`. Starting canonical HEAD was `b4eaa05f999680d3dfe0f8c3d9e553a19941c032`; the UI branch was `a0f49c5bb855a716647521ad3bd1f7a487394816`. Since the original GS-177 implementation was already present on canonical under different SHAs, integration cherry-picked the incremental approved UI correction and its two follow-up commits, preserving both histories. The resulting canonical source HEAD is `563691589e72b09f7b5ef2564e6c4464cd2512b4`; it is three commits ahead of `origin/feature/r1-commercial-baseline`, whose last observed HEAD remains `b4eaa05f999680d3dfe0f8c3d9e553a19941c032`.

The three commits add the approved five-reference responsive visual correction, its focused browser/runtime assertions, GS-130 traceability/evidence, and the screenshot set linked below. The GS-179 Android discovery, TLS validation, endpoint continuity, reconnect, Windows advertisement/guard, backend, PostgreSQL and authentication source files are unchanged from the canonical baseline. Four fixed text-only tabs remain in place. No simulator measurements were added. Concern styling remains visual and does not change event classification.

### Validation on integrated source

- Full isolated GS-179 PostgreSQL/security regression: **55/55 PASS**, 491.530 seconds. Both registered GS-179 LAN lifecycle cases passed. The test used a unique temporary PostgreSQL/TLS environment and database `gs179_monitoring`; the owner's running HTTPS/PostgreSQL services remained running. Physical status is `NOT_RUN`.
- `node --test code/tests/js/caregiver_runtime.test.mjs`: **10/10 PASS**.
- `PYTHONPATH=code/backend:code python3 code/validation/run_gs177_connected_lite.py`: **22 API tests + 10 runtime tests + 3 scenarios PASS**; physical status `NOT_RUN`.
- `make -C code feature-coverage-test`: **225 feature rows, 280 modules, 26 physical cases; framework 22/22 PASS**.
- Registered caregiver-app component gate with the explicit TEST_ONLY origin: API 22/22 and voice prototype 28/28 passed. Android dashboard source, branding and runtime assertions passed, but APK build was **BLOCKED** because local Gradle is unavailable. The first gate attempt without `GS177_BACKEND_ORIGIN` also correctly stopped at the missing approved-origin prerequisite.
- `make -C code pwa-68-browser-test`: browser class was **skipped before executing tests** because Chromium/Chrome is not installed (0 tests executed). The connected-lite browser helper teardown race was fixed narrowly in `code/tests/support/gs178_browser.cjs` by unroute-before-close with Playwright's `ignoreErrors` behavior; the focused 1/1 test passed before this final full suite. The hosted workflow remains the required full browser and Android APK gate.
- No physical phone test was performed. Chromium images are not handset/WebView acceptance.

The available 390×844 mock-authenticated after screenshots from the completed UI branch remain the visual evidence for all five approved references: [normal Home](GS177_ANDROID_UX_IMPLEMENTATION_20261022/screenshots/visual-correction-20261022/home-normal-after-full.png), [negative Home](GS177_ANDROID_UX_IMPLEMENTATION_20261022/screenshots/visual-correction-20261022/home-negative-after-full.png), [Devices](GS177_ANDROID_UX_IMPLEMENTATION_20261022/screenshots/visual-correction-20261022/devices-after-full.png), [Reports](GS177_ANDROID_UX_IMPLEMENTATION_20261022/screenshots/visual-correction-20261022/reports-after-full.png), and [Settings](GS177_ANDROID_UX_IMPLEMENTATION_20261022/screenshots/visual-correction-20261022/settings-after-full.png). They are browser captures of the authenticated shared PWA using isolated mock transport, not installed-APK images. Owner screenshots `1000238617.png` and `1000238619.png` were not present locally, so direct comparison against those installed-phone captures remains unavailable.

The changed Playwright helper is test-only. Existing untracked reference images, configuration, credential and hardware evidence files were preserved. The combined canonical APK workflow, package/source parity, signer fingerprint and artifact SHA have not yet been produced for integrated HEAD `563691589e72b09f7b5ef2564e6c4464cd2512b4`; APK build and phone update compatibility remain pending. The old standalone/feature-branch APK evidence above must not be represented as the final combined artifact.
