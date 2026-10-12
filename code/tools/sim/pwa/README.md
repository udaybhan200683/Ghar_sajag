# Parivar Saathi integrated PWA

This PWA is served by `make lab` at `http://localhost:8765/`. It is the current backend-driven verification UI; the historical standalone prototype is not its data source.

Home consumes `/pwa/state` and preserves the current care banner, I Am OK, door, night activity, lower Morning Activity placement, device-health summary and recent-event order. Home Details, Family Members, Devices, Device Details, Manage Devices, Battery Alerts and network status use `/pwa/foundation/` APIs. Device Schedules uses the existing `/pwa/action` settings bridge, which saves the same SQLite application policy and applies it to host rules. The browser does not keep authoritative household, family, registry or policy data in localStorage. The service worker caches static shell resources only; live state and APIs require the backend.

The Devices tab and Manage Devices share `FoundationService.device_registry`. Registering through this UI creates a **simulated** device using the application API; it does not pair an ESP32. Unregistration requires confirmation and retains historical rows. Physical Wi-Fi provisioning and real device telemetry remain HW_REQUIRED. The lab accepts a development `X-Actor-Id` and applies server-side OWNER checks; production login/session integration is pending.

Run `make lab` from the implementation root. Interactive application state
defaults to `logs/application.sqlite`; use `GS_APP_DB=:memory: make lab` for an
isolated disposable session. Browser release tests use an in-memory application
database. Phase 1 desktop/mobile flows are covered by
`tests/playwright/phase1_foundation.spec.ts` and are part of the mandatory
`make release-gate-final` validation path.
