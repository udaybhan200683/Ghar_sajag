# Ghar Sajag v1.5.1 — P0 simulation closure

This patch implements the ten requested simulation/dashboard behaviors without changing the core safety boundary: activity is evidence, not proof of wellbeing.

## User-visible behavior

1. **I am OK** is a distinct green event with age (for example, “2 min ago”).
2. Recent household events are **newest first**. `Call Family → I am OK` shows both; I am OK never resolves the Call Family incident.
3. The same authorised dashboard supports a family member or caregiver. A separate page is not required solely because professional caregiver service is absent.
4. The simulator no longer exposes a **Privacy ON/OFF** user action. Internal consent/privacy enforcement is intentionally retained.
5. Door events are shown explicitly as **Main door opened / Main door closed**, not generic “activity observed”.
6. Quiet-hours/late-night door opening is **unexpected/red**; normal door activity is positive/green.
7. After a **Missing morning activity** incident, later room/kitchen/pooja/door activity continues to appear chronologically while the missing-morning incident remains visible.
8. Hub and nodes show a non-clickable status indicator, active/degraded/offline state and configured location.
9. Simulated Troubleshoot/Reboot maps injected faults to stable error codes. Reboot only clears faults where restart is a valid remedy.
10. A door open for 5 minutes produces a red **Main door kept open** event. Later close clears the current warning and reports how long the door was open, while retaining the warning in history.

## Simulated diagnostic codes

| Code | Meaning |
|---|---|
| GS-OK000 | No active simulated fault / successful recovery |
| GS-N001 | Node low battery |
| GS-N002 | Node battery depleted / power unavailable |
| GS-N003 | Node-to-hub link lost |
| GS-N004 | Sensor input fault |
| GS-N005 | Node over-temperature |
| GS-N006 | Node watchdog/reset fault |
| GS-H001 | Hub power unavailable |
| GS-H002 | Hub node-radio path fault |
| GS-H003 | Hub internet/WAN path unavailable |
| GS-H004 | Hub over-temperature |
| GS-H005 | Hub watchdog/reset fault |

These are simulation/service codes, not yet hardware-derived diagnoses. Real error classification must be validated after battery, thermal, reset-reason and RF telemetry are integrated.
