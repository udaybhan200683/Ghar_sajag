# Parivar Sathi v3.4.1 — Playwright battery locator fix

## Symptom

The battery-negative browser test failed on desktop and mobile even though the
PWA rendered the correct state.

Playwright strict mode found two valid elements matching the page-wide text:

1. Device Health card: `Low battery: Kitchen Node 5%`
2. Recent Important Events: `Kitchen sensor battery low: 5%`

## Fix

The browser test now scopes the primary battery assertions to:

`[data-care-card="device-health"]`

It separately verifies the red Recent Important Event.

This is a test-locator correction only. Battery analytics, care-banner behavior,
backend logic, thresholds, and the 92 canonical functional scenarios are unchanged.

Expected Playwright result: 22/22 PASS.
