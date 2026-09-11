# Parivar Sathi v1.5.4 PWA browser-gate stability correction — v3.2

Focused correction on top of the already-applied v3.1 chronology patch.

## What was fixed

1. The local WSGI server is now threaded. Chromium requests HTML, CSS, JS, manifest,
   service-worker assets and backend APIs concurrently; the previous single-threaded
   development server could intermittently delay desktop navigation.
2. `/index.html` is now a valid alias for the PWA root. The service worker precache
   explicitly requests `index.html`, so this also fixes PWA service-worker installation.
3. Playwright navigation now waits for HTTP navigation commit and then waits for the
   application-generated `#homeTab .hero`. This validates that the real PWA JavaScript
   and backend state have rendered, without depending on a flaky browser lifecycle event.

No C++ RulesCore behavior was changed.

## Re-test

```bash
make playwright-gate
```

Expected: `8 passed`.

Then:

```bash
make release-gate-final
```
