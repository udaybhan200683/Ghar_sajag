# Phase 0 current-baseline reconciliation

Effective baseline: **Parivar Saathi v1.5.4 / PWA-BatteryAnalytics v3.4.3**.
The active physical directory remains `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2`.
The v3.4.3 legacy-browser assertion alignment is already checked in; this review neither
renamed the directory nor reapplied that patch.

## Checked-in host validation evidence

The current source and suites provide 24/24 P0 validation mappings, four schema/contract
checks, 94 C++ checks, 31 Python tests, 11 JavaScript tests, Base and AI product profiles,
four feature variants, five dummy streams, 92 canonical functional scenarios, 16 HTTP
integration tests, PWA bridge/API/frontend checks, sanitizer and trace checks. The final
gate also runs Playwright preflight and Chromium PWA validation for desktop and Pixel 7
viewport profiles. These are host/simulator results; they do not certify physical hardware.

## Status corrections made

- G16 is **VALIDATED**: browser automation is mandatory in `make release-gate-final`, not
  manual-only. The manual plan remains useful supplementary exploratory evidence.
- G01–G12 and G15 remain partial/open where persistence, target integration, transport,
  provider delivery, authorization, resource evidence or recovery is still incomplete.
- G13–G14 remain future AI scope; G17 remains **OPEN / HIL**.
- G18–G19 identify Phase 1 authoritative persistence, household/family and device-management
  work. Existing simulator PWA controls do not close those requirements.
- G20 identifies Phase 2 reports/notification completion. G21 identifies Phase 3 stress,
  endurance and recovery qualification.

## Evidence limits and classifications

**HOST_SIMULATED:** PWA state, battery telemetry, rule decisions, transport replay, device
diagnostics, notification provider states and all browser evidence use the connected host lab.

**HW_REQUIRED:** PIR/reed/button behaviour, ESP-NOW cryptography/RSSI/channel recovery,
battery current/ADC/capacity calibration, UPS/brownout/watchdog, flash durability, signed OTA,
real provider/phone delivery and installed-home pilot coverage.

## Final validation checkpoint

**PASS — `make release-gate-final`**, manually executed in the normal WSL environment after
this Phase 0 reconciliation. The earlier Codex-sandbox attempt is classified
**ENVIRONMENT_BLOCKED**, not a product failure: that sandbox denied the local loopback socket
creation needed by the HTTP/PWA/browser stages. No source change was made in response.
