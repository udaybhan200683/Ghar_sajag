# Ghar Sajag reference code 1.5.4

Immediate product: Base Parivar Saathi P0. The active source package is
`code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2`; this remains a
host/simulator reference, not a flashable ESP-IDF application.

Phase 1 implementation, UX correction and Validation Hardening are complete.
Final qualification is **PASS** via the authoritative command:

```bash
make release-gate-final
```

`make release-gate-final` includes host validation plus mandatory Playwright.
Playwright runs all mandatory browser specs for `chromium-desktop` and
`chromium-mobile`. The host `browser-e2e` lab owns port `8765`; Playwright owns
port `8766`. Automated browser validation uses isolated in-memory application
databases where intended, so release qualification does not depend on interactive
lab state.

Start with the package README and the current progress files under
`docs/progress`. Phase 2 Reports and production notifications remain pending;
physical provisioning, Wi-Fi and sensor qualification remain hardware-required.
