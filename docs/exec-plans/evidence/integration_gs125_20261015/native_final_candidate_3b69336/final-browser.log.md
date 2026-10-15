make[1]: Entering directory '/home/udaybhan/projects/Ghar_sajag_r1_integration/code'
python3 scripts/playwright_preflight.py
PASS: Playwright preflight
# The runner executes every tests/playwright spec for desktop and mobile projects.
python3 scripts/run_playwright_gate.py
Preparing Playwright lab build...
make[2]: Entering directory '/home/udaybhan/projects/Ghar_sajag_r1_integration/code'
g++ -B/usr/bin -std=c++17 -O2 -Wall -Wextra -Werror -pedantic -DGS_PRODUCT_AI=0 -DGS_ENABLE_TRACE=0 -Ibuild/gs40_generated -I. -Ifirmware/common/shared/include -Ifirmware/node -Ifirmware/hub -Ifirmware/common/security build/obj/base/17d9719a5f53dde7/firmware/common/shared/src/rules.o build/obj/base/17d9719a5f53dde7/firmware/common/shared/src/logging.o build/obj/base/17d9719a5f53dde7/tests/support/host/logging/file_log_sink.o build/obj/base/17d9719a5f53dde7/firmware/common/transport/data_plane_codec.o build/obj/base/17d9719a5f53dde7/firmware/common/transport/node_retirement_protocol.o build/obj/base/17d9719a5f53dde7/firmware/common/transport/session_id.o build/obj/base/17d9719a5f53dde7/firmware/node/sensing/sensing.o build/obj/base/17d9719a5f53dde7/firmware/node/communication/radio/node_radio.o build/obj/base/17d9719a5f53dde7/firmware/node/power/power.o build/obj/base/17d9719a5f53dde7/firmware/node/lifecycle/lifecycle.o build/obj/base/17d9719a5f53dde7/firmware/node/storage/node_store.o build/obj/base/17d9719a5f53dde7/firmware/node/lifecycle/fota/fota_receiver.o build/obj/base/17d9719a5f53dde7/firmware/node/runtime/node_runtime.o build/obj/base/17d9719a5f53dde7/firmware/hub/event_processing/ingest/ingest.o build/obj/base/17d9719a5f53dde7/firmware/hub/commissioning/registry/node_registry.o build/obj/base/17d9719a5f53dde7/firmware/hub/storage/journal.o build/obj/base/17d9719a5f53dde7/firmware/hub/storage/durable_transition.o build/obj/base/17d9719a5f53dde7/firmware/hub/storage/node_retirement_snapshot.o build/obj/base/17d9719a5f53dde7/firmware/hub/storage/hub_durability_owner.o build/obj/base/17d9719a5f53dde7/firmware/hub/storage/durable_journal_slot_store.o build/obj/base/17d9719a5f53dde7/firmware/hub/runtime/time/clock.o build/obj/base/17d9719a5f53dde7/firmware/hub/event_processing/coverage/coverage.o build/obj/base/17d9719a5f53dde7/firmware/hub/routines/routine_service.o build/obj/base/17d9719a5f53dde7/firmware/hub/runtime/ui/resident_ui.o build/obj/base/17d9719a5f53dde7/firmware/hub/lifecycle/configuration/config_service.o build/obj/base/17d9719a5f53dde7/firmware/hub/cloud_sync/cloud_sync.o build/obj/base/17d9719a5f53dde7/firmware/hub/runtime/hub_runtime.o build/obj/base/17d9719a5f53dde7/firmware/hub/runtime/hub_checkpoint_codec.o build/obj/base/17d9719a5f53dde7/firmware/hub/storage/runtime_state_store.o build/obj/base/17d9719a5f53dde7/firmware/common/security/security.o build/obj/base/17d9719a5f53dde7/firmware/hub/storage/durable_event_outbox.o build/obj/base/17d9719a5f53dde7/tests/support/host/simulator/interactive.o -o build/ghar_sajag_interactive
make[2]: Leaving directory '/home/udaybhan/projects/Ghar_sajag_r1_integration/code'
Preferred Playwright port 8766 is occupied; selected 38633.
Starting Parivar Saathi / Ghar Sajag local lab...
Lab ready: http://127.0.0.1:38633

Running 86 tests using 1 worker

  ✓   1 [chromium-desktop] › ../tests/playwright/phase1_foundation.spec.ts:24:7 › Phase 1 authoritative application flows › Home Details load, save, reload, cancel and backend rejection (6.2s)
  ✓   2 [chromium-desktop] › ../tests/playwright/phase1_foundation.spec.ts:54:7 › Phase 1 authoritative application flows › Family Members add, edit, deactivate and reject last admin removal (5.4s)
  ✓   3 [chromium-desktop] › ../tests/playwright/phase1_foundation.spec.ts:81:7 › Phase 1 authoritative application flows › Devices and Manage Devices share registration, details, edit and removal (6.8s)
  ✓   4 [chromium-desktop] › ../tests/playwright/phase1_foundation.spec.ts:122:7 › Phase 1 authoritative application flows › Battery policy and schedules persist and reject invalid threshold relationship (6.0s)
  ✓   5 [chromium-desktop] › ../tests/playwright/phase1_foundation.spec.ts:171:9 › Phase 1 authoritative application flows › deterministic failed-save routing › failed Home Details save stays open and never claims success (2.0s)
  ✓   6 [chromium-desktop] › ../tests/playwright/phase1_foundation.spec.ts:200:7 › Phase 1 authoritative application flows › simulated online/offline transition updates backend-driven device health (5.7s)
  ✓   7 [chromium-desktop] › ../tests/playwright/phase1_foundation.spec.ts:223:7 › Phase 1 authoritative application flows › Network dialog reports host state and hardware boundary without pairing claim (1.9s)
  ✓   8 [chromium-desktop] › ../tests/playwright/phase1_foundation.spec.ts:235:7 › Phase 1 authoritative application flows › Family, Manage Devices and Schedules reject invalid saves and discard canceled drafts (6.3s)
  ✓   9 [chromium-desktop] › ../tests/playwright/phase1_ui_contract.spec.ts:115:7 › Phase 1 visible contract and contamination matrix › single-feature state axes and exact presentation (25.8s)
  ✓  10 [chromium-desktop] › ../tests/playwright/phase1_ui_contract.spec.ts:148:7 › Phase 1 visible contract and contamination matrix › deterministic pairwise and high-risk three-way concern interactions (22.2s)
  ✓  11 [chromium-desktop] › ../tests/playwright/phase1_ui_contract.spec.ts:171:7 › Phase 1 visible contract and contamination matrix › all exposed caregiver toggles recover without cross-card residue (17.4s)
  ✓  12 [chromium-desktop] › ../tests/playwright/phase1_ui_contract.spec.ts:191:7 › Phase 1 visible contract and contamination matrix › required-node lease expiry is real coverage loss with scoped Home concern and care event (5.2s)
  ✓  13 [chromium-desktop] › ../tests/playwright/phase1_ui_contract.spec.ts:240:7 › Phase 1 visible contract and contamination matrix › I am OK overdue concern clears on real acknowledgement with chronological events (5.4s)
  ✓  14 [chromium-desktop] › ../tests/playwright/phase1_ui_contract.spec.ts:273:7 › Phase 1 visible contract and contamination matrix › offline I am OK press waits for backend acceptance before clearing caregiver concern (4.3s)
  ✓  15 [chromium-desktop] › ../tests/playwright/phase2a_reports.spec.ts:60:7 › Phase 2A backend-derived Reports › renders Today, Week, and Month from the reports API (2.5s)
  ✓  16 [chromium-desktop] › ../tests/playwright/phase2a_reports.spec.ts:85:7 › Phase 2A backend-derived Reports › shows no-data without treating it as an error (1.7s)
  ✓  17 [chromium-desktop] › ../tests/playwright/phase2a_reports.spec.ts:93:7 › Phase 2A backend-derived Reports › refreshes after new backend activity (5.8s)
  ✓  18 [chromium-desktop] › ../tests/playwright/phase2a_reports.spec.ts:102:7 › Phase 2A backend-derived Reports › shows backend and malformed response errors explicitly (1.5s)
  ✓  19 [chromium-desktop] › ../tests/playwright/phase2a_reports.spec.ts:110:7 › Phase 2A backend-derived Reports › shows malformed report responses as errors (1.4s)
  ✓  20 [chromium-desktop] › ../tests/playwright/phase2b_notifications.spec.ts:25:7 › Phase 2B Notifications settings and status › loads, saves, reloads and cancels caregiver preferences (4.2s)
  ✓  21 [chromium-desktop] › ../tests/playwright/phase2b_notifications.spec.ts:52:7 › Phase 2B Notifications settings and status › records delivered, suppressed, failed and resolved notification states without technical leakage (4.5s)
  ✓  22 [chromium-desktop] › ../tests/playwright/phase2b_notifications.spec.ts:95:7 › Phase 2B Notifications settings and status › duplicates and maintenance activity do not create caregiver notification spam (2.0s)
  ✓  23 [chromium-desktop] › ../tests/playwright/phase2c_integration.spec.ts:17:7 › Phase 2C PWA integration › shows caregiver-facing routine settings name with stable behavior (1.7s)
  ✓  24 [chromium-desktop] › ../tests/playwright/phase2c_integration.spec.ts:27:7 › Phase 2C PWA integration › reflects backend-owned I-am-OK overdue and acknowledgement timing (3.3s)
  ✓  25 [chromium-desktop] › ../tests/playwright/phase2c_integration.spec.ts:52:7 › Phase 2C PWA integration › keeps optional device maintenance notifications separate from care activity (1.8s)
  ✓  26 [chromium-desktop] › ../tests/playwright/phase3a_performance.spec.ts:11:7 › Phase 3A lightweight runtime contracts › keeps initial Home minimal and navigation does not multiply timers, listeners, or DOM rows (5.2s)
  ✓  27 [chromium-desktop] › ../tests/playwright/phase3a_performance.spec.ts:50:7 › Phase 3A lightweight runtime contracts › loads Reports on demand, prevents overlapping refreshes, and Settings avoids full state (5.8s)
  ✓  28 [chromium-desktop] › ../tests/playwright/phase3a_performance.spec.ts:76:7 › Phase 3A lightweight runtime contracts › keeps the service-worker cache static-only and bounded (1.3s)
  ✓  29 [chromium-desktop] › ../tests/playwright/phase3a_performance.spec.ts:89:7 › Phase 3A lightweight runtime contracts › recovers after a temporary compact-state failure without losing the last safe presentation (5.5s)
  ✓  30 [chromium-desktop] › ../tests/playwright/pwa_release_gate.spec.ts:17:7 › Parivar Sathi mandatory browser release gate › PWA loads and primary tabs are visible (1.3s)
  ✓  31 [chromium-desktop] › ../tests/playwright/pwa_release_gate.spec.ts:25:7 › Parivar Sathi mandatory browser release gate › routine cards are below the overall banner with Morning before I am OK (1.4s)
  ✓  32 [chromium-desktop] › ../tests/playwright/pwa_release_gate.spec.ts:33:7 › Parivar Sathi mandatory browser release gate › battery health negative scenario changes only device health and not top banner (2.7s)
  ✓  33 [chromium-desktop] › ../tests/playwright/pwa_release_gate.spec.ts:64:7 › Parivar Sathi mandatory browser release gate › low battery with sufficient history renders the backend runtime prediction (4.1s)
  ✓  34 [chromium-desktop] › ../tests/playwright/pwa_release_gate.spec.ts:88:7 › Parivar Sathi mandatory browser release gate › high battery drain shortens prediction, flags device health, and does not change care banner (4.1s)
  ✓  35 [chromium-desktop] › ../tests/playwright/pwa_release_gate.spec.ts:105:7 › Parivar Sathi mandatory browser release gate › recent important events are newest-first after scenario toggles (2.5s)
  ✓  36 [chromium-desktop] › ../tests/playwright/pwa_release_gate.spec.ts:129:7 › Parivar Sathi mandatory browser release gate › night card stays domain-specific and door card shows elapsed open time (2.0s)
  ✓  37 [chromium-desktop] › ../tests/playwright/pwa_release_gate.spec.ts:143:7 › Parivar Sathi mandatory browser release gate › morning in progress is amber without an attention banner (4.4s)
  ✓  38 [chromium-desktop] › ../tests/playwright/pwa_release_gate.spec.ts:156:7 › Parivar Sathi mandatory browser release gate › Device Schedules exposes and saves family-specific routine thresholds (6.1s)
  ✓  39 [chromium-desktop] › ../tests/playwright/pwa_release_gate.spec.ts:180:7 › Parivar Sathi mandatory browser release gate › missing morning concern uses generic red banner and highlights Morning Routine card (2.8s)
  ✓  40 [chromium-desktop] › ../tests/playwright/pwa_release_gate.spec.ts:202:7 › Parivar Sathi mandatory browser release gate › post-door inactivity makes overall banner red and shows problem in Main Door card (4.9s)
  ✓  41 [chromium-desktop] › ../tests/playwright/pwa_release_gate.spec.ts:218:7 › Parivar Sathi mandatory browser release gate › night bathroom concern makes overall banner red and shows problem in Night Activity card (4.2s)
  ✓  42 [chromium-desktop] › ../tests/playwright/pwa_release_gate.spec.ts:233:7 › Parivar Sathi mandatory browser release gate › door-left-open and common-room concerns use generic red banner plus affected routine card (3.3s)
  ✓  43 [chromium-desktop] › ../tests/playwright/pwa_release_gate.spec.ts:260:7 › Parivar Sathi mandatory browser release gate › run all canonical scenarios through PWA and verify visible PASS summary (18.3s)
  ✓  44 [chromium-mobile] › ../tests/playwright/phase1_foundation.spec.ts:24:7 › Phase 1 authoritative application flows › Home Details load, save, reload, cancel and backend rejection (5.0s)
  ✓  45 [chromium-mobile] › ../tests/playwright/phase1_foundation.spec.ts:54:7 › Phase 1 authoritative application flows › Family Members add, edit, deactivate and reject last admin removal (4.4s)
  ✓  46 [chromium-mobile] › ../tests/playwright/phase1_foundation.spec.ts:81:7 › Phase 1 authoritative application flows › Devices and Manage Devices share registration, details, edit and removal (6.7s)
  ✓  47 [chromium-mobile] › ../tests/playwright/phase1_foundation.spec.ts:122:7 › Phase 1 authoritative application flows › Battery policy and schedules persist and reject invalid threshold relationship (4.9s)
  ✓  48 [chromium-mobile] › ../tests/playwright/phase1_foundation.spec.ts:171:9 › Phase 1 authoritative application flows › deterministic failed-save routing › failed Home Details save stays open and never claims success (2.0s)
  ✓  49 [chromium-mobile] › ../tests/playwright/phase1_foundation.spec.ts:200:7 › Phase 1 authoritative application flows › simulated online/offline transition updates backend-driven device health (5.6s)
  ✓  50 [chromium-mobile] › ../tests/playwright/phase1_foundation.spec.ts:223:7 › Phase 1 authoritative application flows › Network dialog reports host state and hardware boundary without pairing claim (1.6s)
  ✓  51 [chromium-mobile] › ../tests/playwright/phase1_foundation.spec.ts:235:7 › Phase 1 authoritative application flows › Family, Manage Devices and Schedules reject invalid saves and discard canceled drafts (4.9s)
  ✓  52 [chromium-mobile] › ../tests/playwright/phase1_ui_contract.spec.ts:115:7 › Phase 1 visible contract and contamination matrix › single-feature state axes and exact presentation (16.5s)
  ✓  53 [chromium-mobile] › ../tests/playwright/phase1_ui_contract.spec.ts:148:7 › Phase 1 visible contract and contamination matrix › deterministic pairwise and high-risk three-way concern interactions (14.9s)
  ✓  54 [chromium-mobile] › ../tests/playwright/phase1_ui_contract.spec.ts:171:7 › Phase 1 visible contract and contamination matrix › all exposed caregiver toggles recover without cross-card residue (10.7s)
  ✓  55 [chromium-mobile] › ../tests/playwright/phase1_ui_contract.spec.ts:191:7 › Phase 1 visible contract and contamination matrix › required-node lease expiry is real coverage loss with scoped Home concern and care event (4.0s)
  ✓  56 [chromium-mobile] › ../tests/playwright/phase1_ui_contract.spec.ts:240:7 › Phase 1 visible contract and contamination matrix › I am OK overdue concern clears on real acknowledgement with chronological events (3.6s)
  ✓  57 [chromium-mobile] › ../tests/playwright/phase1_ui_contract.spec.ts:273:7 › Phase 1 visible contract and contamination matrix › offline I am OK press waits for backend acceptance before clearing caregiver concern (4.1s)
  ✓  58 [chromium-mobile] › ../tests/playwright/phase2a_reports.spec.ts:60:7 › Phase 2A backend-derived Reports › renders Today, Week, and Month from the reports API (3.4s)
  ✓  59 [chromium-mobile] › ../tests/playwright/phase2a_reports.spec.ts:85:7 › Phase 2A backend-derived Reports › shows no-data without treating it as an error (2.4s)
  ✓  60 [chromium-mobile] › ../tests/playwright/phase2a_reports.spec.ts:93:7 › Phase 2A backend-derived Reports › refreshes after new backend activity (5.8s)
  ✓  61 [chromium-mobile] › ../tests/playwright/phase2a_reports.spec.ts:102:7 › Phase 2A backend-derived Reports › shows backend and malformed response errors explicitly (1.5s)
  ✓  62 [chromium-mobile] › ../tests/playwright/phase2a_reports.spec.ts:110:7 › Phase 2A backend-derived Reports › shows malformed report responses as errors (1.4s)
  ✓  63 [chromium-mobile] › ../tests/playwright/phase2b_notifications.spec.ts:25:7 › Phase 2B Notifications settings and status › loads, saves, reloads and cancels caregiver preferences (2.8s)
  ✓  64 [chromium-mobile] › ../tests/playwright/phase2b_notifications.spec.ts:52:7 › Phase 2B Notifications settings and status › records delivered, suppressed, failed and resolved notification states without technical leakage (3.5s)
  ✓  65 [chromium-mobile] › ../tests/playwright/phase2b_notifications.spec.ts:95:7 › Phase 2B Notifications settings and status › duplicates and maintenance activity do not create caregiver notification spam (2.0s)
  ✓  66 [chromium-mobile] › ../tests/playwright/phase2c_integration.spec.ts:17:7 › Phase 2C PWA integration › shows caregiver-facing routine settings name with stable behavior (1.8s)
  ✓  67 [chromium-mobile] › ../tests/playwright/phase2c_integration.spec.ts:27:7 › Phase 2C PWA integration › reflects backend-owned I-am-OK overdue and acknowledgement timing (1.9s)
  ✓  68 [chromium-mobile] › ../tests/playwright/phase2c_integration.spec.ts:52:7 › Phase 2C PWA integration › keeps optional device maintenance notifications separate from care activity (1.7s)
  ✓  69 [chromium-mobile] › ../tests/playwright/phase3a_performance.spec.ts:11:7 › Phase 3A lightweight runtime contracts › keeps initial Home minimal and navigation does not multiply timers, listeners, or DOM rows (3.9s)
  ✓  70 [chromium-mobile] › ../tests/playwright/phase3a_performance.spec.ts:50:7 › Phase 3A lightweight runtime contracts › loads Reports on demand, prevents overlapping refreshes, and Settings avoids full state (5.1s)
  ✓  71 [chromium-mobile] › ../tests/playwright/phase3a_performance.spec.ts:76:7 › Phase 3A lightweight runtime contracts › keeps the service-worker cache static-only and bounded (1.3s)
  ✓  72 [chromium-mobile] › ../tests/playwright/phase3a_performance.spec.ts:89:7 › Phase 3A lightweight runtime contracts › recovers after a temporary compact-state failure without losing the last safe presentation (5.9s)
  ✓  73 [chromium-mobile] › ../tests/playwright/pwa_release_gate.spec.ts:17:7 › Parivar Sathi mandatory browser release gate › PWA loads and primary tabs are visible (1.8s)
  ✓  74 [chromium-mobile] › ../tests/playwright/pwa_release_gate.spec.ts:25:7 › Parivar Sathi mandatory browser release gate › routine cards are below the overall banner with Morning before I am OK (1.7s)
  ✓  75 [chromium-mobile] › ../tests/playwright/pwa_release_gate.spec.ts:33:7 › Parivar Sathi mandatory browser release gate › battery health negative scenario changes only device health and not top banner (2.4s)
  ✓  76 [chromium-mobile] › ../tests/playwright/pwa_release_gate.spec.ts:64:7 › Parivar Sathi mandatory browser release gate › low battery with sufficient history renders the backend runtime prediction (4.6s)
  ✓  77 [chromium-mobile] › ../tests/playwright/pwa_release_gate.spec.ts:88:7 › Parivar Sathi mandatory browser release gate › high battery drain shortens prediction, flags device health, and does not change care banner (4.6s)
  ✓  78 [chromium-mobile] › ../tests/playwright/pwa_release_gate.spec.ts:105:7 › Parivar Sathi mandatory browser release gate › recent important events are newest-first after scenario toggles (2.8s)
  ✓  79 [chromium-mobile] › ../tests/playwright/pwa_release_gate.spec.ts:129:7 › Parivar Sathi mandatory browser release gate › night card stays domain-specific and door card shows elapsed open time (4.8s)
  ✓  80 [chromium-mobile] › ../tests/playwright/pwa_release_gate.spec.ts:143:7 › Parivar Sathi mandatory browser release gate › morning in progress is amber without an attention banner (10.5s)
  ✓  81 [chromium-mobile] › ../tests/playwright/pwa_release_gate.spec.ts:156:7 › Parivar Sathi mandatory browser release gate › Device Schedules exposes and saves family-specific routine thresholds (14.4s)
  ✓  82 [chromium-mobile] › ../tests/playwright/pwa_release_gate.spec.ts:180:7 › Parivar Sathi mandatory browser release gate › missing morning concern uses generic red banner and highlights Morning Routine card (12.2s)
  ✓  83 [chromium-mobile] › ../tests/playwright/pwa_release_gate.spec.ts:202:7 › Parivar Sathi mandatory browser release gate › post-door inactivity makes overall banner red and shows problem in Main Door card (12.3s)
  ✓  84 [chromium-mobile] › ../tests/playwright/pwa_release_gate.spec.ts:218:7 › Parivar Sathi mandatory browser release gate › night bathroom concern makes overall banner red and shows problem in Night Activity card (11.2s)
  ✓  85 [chromium-mobile] › ../tests/playwright/pwa_release_gate.spec.ts:233:7 › Parivar Sathi mandatory browser release gate › door-left-open and common-room concerns use generic red banner plus affected routine card (17.8s)
  ✓  86 [chromium-mobile] › ../tests/playwright/pwa_release_gate.spec.ts:260:7 › Parivar Sathi mandatory browser release gate › run all canonical scenarios through PWA and verify visible PASS summary (56.9s)

  86 passed (9.0m)
Running Engineering Dashboard PREVIEW_ONLY review suite...
CASE ED-PREVIEW-OVERVIEW-DESKTOP-001 PASS
CASE ED-PREVIEW-LIVE-DESKTOP-001 PASS
CASE ED-PREVIEW-TRACE-DESKTOP-001 PASS
CASE ED-PREVIEW-DEVICE-DESKTOP-001 PASS
CASE ED-PREVIEW-COMMUNICATION-DESKTOP-001 PASS
CASE ED-PREVIEW-INSTALLATION-DESKTOP-001 PASS
CASE ED-PREVIEW-ADVANCED-DESKTOP-001 PASS
CASE ED-PREVIEW-TRACE-UNKNOWN-DESKTOP-001 PASS
CASE ED-PREVIEW-LIVE-FILTER-DESKTOP-001 PASS
CASE ED-PREVIEW-STATE-DISABLED-LAYOUT-DESKTOP-001 PASS
CASE ED-PREVIEW-OVERVIEW-MOBILE-001 PASS
CASE ED-PREVIEW-LIVE-MOBILE-001 PASS
CASE ED-PREVIEW-TRACE-MOBILE-001 PASS
CASE ED-PREVIEW-DEVICE-MOBILE-001 PASS
CASE ED-PREVIEW-COMMUNICATION-MOBILE-001 PASS
CASE ED-PREVIEW-INSTALLATION-MOBILE-001 PASS
CASE ED-PREVIEW-ADVANCED-MOBILE-001 PASS
CASE ED-PREVIEW-TRACE-UNKNOWN-MOBILE-001 PASS
CASE ED-PREVIEW-LIVE-FILTER-MOBILE-001 PASS
CASE ED-PREVIEW-STATE-DISABLED-LAYOUT-MOBILE-001 PASS
ENGINEERING DASHBOARD PREVIEW PASS screens=7 viewports=2 cases=20 scope=PREVIEW_ONLY production_qualification=BLOCKED physical=NOT_RUN output=code/build/engineering_dashboard_preview
make[1]: Leaving directory '/home/udaybhan/projects/Ghar_sajag_r1_integration/code'
