# Parivar Sathi v3.3.1 browser/routine validation correction

Focused correction on top of v3.3. No user-facing household thresholds were re-hardcoded.

## Fixes

1. **Device Schedules editing is stable** — background 2 s PWA polling is paused while the schedule editor is open, so the form is not detached while a family member is typing. Saving still refreshes from the backend response.
2. **Browser tests are isolated** — direct post-door/night tests reset to a known PASS baseline before injecting events.
3. **Door chronology assertion follows the new configured rule** — the PWA door-negative toggle intentionally advances to the configured left-open threshold, so the newest visible event is `Main door left open`, not merely `Main door opened`.
4. **Night-only canonical scenarios suppress unrelated morning-rule alarms** — night routine cases disable the morning-sequence rule for that test case only, so the expected night concern is the visible main-banner reason. The household product default remains configurable and unchanged.
5. **Door-left-open browser boundary scenario is isolated from the morning rule** for the same reason.

## Re-test

```bash
make playwright-gate
```

Expected: all 16 browser checks pass (8 logical checks × desktop/mobile).

Then run:

```bash
make release-gate-final
```
