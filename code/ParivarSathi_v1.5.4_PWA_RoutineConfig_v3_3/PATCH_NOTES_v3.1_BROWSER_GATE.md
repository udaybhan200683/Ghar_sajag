# Parivar Sathi v1.5.4 PWA browser-gate correction — v3.1

This is a focused correction on top of the v3 package. No C++ RulesCore/product behavior changed.

## Fixes

1. Playwright navigation waits for `domcontentloaded` instead of the full `load` event, then validates the rendered DOM. This removes the observed one-off 120 s desktop navigation timeout without weakening the visible-page assertions.
2. PWA manual-scenario audit timestamps are monotonic across deterministic simulator rebuilds. Therefore the latest user-triggered scenario transition is the newest visible Recent Important Event even when the simulator internally returns to its baseline clock.

## Re-test

```bash
make playwright-gate
```

If it passes:

```bash
make release-gate-final
```
