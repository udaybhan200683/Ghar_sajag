# Parivar Sathi v3.3.3 — Device Schedules editor stability

## Symptom
Settings → Device Schedules opened correctly, but closed roughly two seconds later,
making manual editing impossible.

## Root cause
The PWA polls `/pwa/state` every two seconds. A refresh that started just before the
editor opened could complete afterward and call the global `render()`, rebuilding the
Settings tab and detaching the editor form.

Checking for `#scheduleEditor` only before starting a poll was therefore not race-safe.

## Fix
- Added an explicit `scheduleEditorOpen` lifecycle state.
- Global renders no longer rebuild the Settings tab while the editor is open.
- Backend polling continues, so other dashboard state remains current.
- Save refreshes only the Device Schedules editor with backend-confirmed values.
- Cancel closes it explicitly.
- Playwright now keeps the editor open for 3.5 seconds (longer than one polling cycle)
  before editing, so this regression is automatically caught.

No household values were hardcoded by this fix.
