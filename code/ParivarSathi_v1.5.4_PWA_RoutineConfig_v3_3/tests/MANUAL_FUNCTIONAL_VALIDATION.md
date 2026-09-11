# Ghar Sajag v1.5.4-routine-config Manual Functional Validation Plan

Use this checklist before a release when reviewing the browser/PWA manually. It is generated from the same scenario catalog used by automation, so manual and automated coverage cannot silently drift.

## Common setup

1. Run `make lab`.
2. Open `http://127.0.0.1:8765`.
3. Before each case press **Reset scenario** unless the case says otherwise.
4. Use only synthetic/demo data.
5. Record PASS/FAIL, screenshot failures, and attach `logs/e2e_report.json`.

## Expected scenarios

### M001 — Room 1 motion is preserved as exact positive activity
Scenario ID: `motion-room1-visible`  
Requirements: F05, F11

**Steps**
1. Inject MOTION from room1

**Expected**
- `home.latest_activity.kind` eq `MOTION`
- `home.latest_activity.location` eq `room1`
- `home.latest_activity.tone` eq `positive`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M002 — Kitchen motion is preserved as exact positive activity
Scenario ID: `motion-kitchen-visible`  
Requirements: F05, F11

**Steps**
1. Inject MOTION from kitchen

**Expected**
- `home.latest_activity.location` eq `kitchen`
- `home.latest_activity.tone` eq `positive`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M003 — Pooja motion is preserved as exact positive activity
Scenario ID: `motion-pooja-visible`  
Requirements: F05, F11

**Steps**
1. Inject MOTION from pooja

**Expected**
- `home.latest_activity.location` eq `pooja`
- `home.latest_activity.tone` eq `positive`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M004 — Normal daytime door opening is green and explicit
Scenario ID: `door-open-daytime`  
Requirements: F09, F11

**Steps**
1. Inject DOOR_OPEN from entry

**Expected**
- `home.latest_activity.kind` eq `DOOR_OPEN`
- `home.latest_activity.tone` eq `positive`
- `home.latest_activity.details.unexpected` eq `False`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M005 — Door open and close remain chronological and explicit
Scenario ID: `door-open-close-order`  
Requirements: F09, F11

**Steps**
1. Inject DOOR_OPEN from entry
2. Advance simulated clock by 60 seconds
3. Inject DOOR_CLOSED from entry

**Expected**
- `home.recent_events` begins in order `['DOOR_CLOSED', 'DOOR_OPEN']`
- `home.door_status.state` eq `CLOSED`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M006 — I am OK remains a distinct green self-check-in
Scenario ID: `resident-ok-green`  
Requirements: F06, F11

**Steps**
1. Inject OK_PRESSED from room1

**Expected**
- `home.latest_activity.kind` eq `OK_PRESSED`
- `home.latest_activity.tone` eq `positive`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M007 — Call Family opens exactly one incident and two routes
Scenario ID: `call-family-opens-workflow`  
Requirements: F07, F13

**Steps**
1. Inject CALL_FAMILY from room1

**Expected**
- `incidents` contains 1 item(s) matching `{"kind": "CALL_FAMILY", "state": "OPEN"}`
- `notifications` contains 2 item(s) matching `{}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M008 — I am OK after Call Family is newer but does not resolve the request
Scenario ID: `call-then-ok-keeps-call`  
Requirements: F06, F07, F11

**Steps**
1. Inject CALL_FAMILY from room1
2. Advance simulated clock by 60 seconds
3. Inject OK_PRESSED from room1

**Expected**
- `home.recent_events` begins in order `['OK_PRESSED', 'CALL_FAMILY']`
- `incidents` contains 1 item(s) matching `{"kind": "CALL_FAMILY", "state": "OPEN"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M009 — Later activities remain visible after missing-morning alert
Scenario ID: `post-missing-activity-visible`  
Requirements: F08, F11

**Steps**
1. Advance simulated clock by 1300 seconds
2. Inject MOTION from room1
3. Advance simulated clock by 60 seconds
4. Inject MOTION from kitchen
5. Inject DOOR_OPEN from entry

**Expected**
- `incidents` contains 1 item(s) matching `{"kind": "MISSING_MORNING_ACTIVITY"}`
- `home.recent_events` contains >=2 item(s) matching `{"kind": "MOTION"}`
- `home.recent_events` contains 1 item(s) matching `{"kind": "DOOR_OPEN"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

## Morning scenarios

### M010 — Covered morning with no evidence creates one concern
Scenario ID: `morning-missing-covered`  
Requirements: F08

**Steps**
1. Advance simulated clock by 1300 seconds

**Expected**
- `simulation.reason` eq `no_qualifying_evidence`
- `incidents` contains 1 item(s) matching `{"kind": "MISSING_MORNING_ACTIVITY"}`
- `notifications` contains 2 item(s) matching `{}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M011 — Kitchen motion satisfies morning routine
Scenario ID: `morning-kitchen-qualifies`  
Requirements: F05, F08

**Steps**
1. Inject MOTION from kitchen
2. Advance simulated clock by 1300 seconds

**Expected**
- `simulation.reason` eq `evidence_present`
- `incidents` contains 0 item(s) matching `{"kind": "MISSING_MORNING_ACTIVITY"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M012 — Pooja motion satisfies morning routine
Scenario ID: `morning-pooja-qualifies`  
Requirements: F05, F08

**Steps**
1. Inject MOTION from pooja
2. Advance simulated clock by 1300 seconds

**Expected**
- `simulation.reason` eq `evidence_present`
- `incidents` contains 0 item(s) matching `{"kind": "MISSING_MORNING_ACTIVITY"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M013 — Room 1 motion does not silently satisfy kitchen/pooja morning policy
Scenario ID: `morning-room1-not-qualifying`  
Requirements: F04, F08

**Steps**
1. Inject MOTION from room1
2. Advance simulated clock by 1300 seconds

**Expected**
- `incidents` contains 1 item(s) matching `{"kind": "MISSING_MORNING_ACTIVITY"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M014 — Main-door activity does not silently satisfy kitchen/pooja morning policy
Scenario ID: `morning-door-not-qualifying`  
Requirements: F04, F08

**Steps**
1. Inject DOOR_OPEN from entry
2. Advance simulated clock by 1300 seconds

**Expected**
- `incidents` contains 1 item(s) matching `{"kind": "MISSING_MORNING_ACTIVITY"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M015 — Explicit I am OK satisfies morning check-in independently of PIR
Scenario ID: `morning-ok-qualifies`  
Requirements: F06, F08

**Steps**
1. Inject OK_PRESSED from room1
2. Advance simulated clock by 1300 seconds

**Expected**
- `simulation.explicit_ok` is true/non-empty
- `incidents` contains 0 item(s) matching `{"kind": "MISSING_MORNING_ACTIVITY"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M016 — Missing sensor coverage suppresses inactivity interpretation
Scenario ID: `morning-coverage-gap-suppresses`  
Requirements: E01, F08

**Steps**
1. Set node kitchen link unavailable
2. Advance simulated clock by 1300 seconds

**Expected**
- `simulation.reason` eq `coverage_unknown`
- `incidents` contains 0 item(s) matching `{"kind": "MISSING_MORNING_ACTIVITY"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M017 — Untrusted clock suppresses time-based morning concern
Scenario ID: `morning-untrusted-clock-suppresses`  
Requirements: E06, F08

**Steps**
1. Set clock untrusted
2. Advance simulated clock by 1300 seconds

**Expected**
- `simulation.reason` eq `time_untrusted`
- `incidents` contains 0 item(s) matching `{"kind": "MISSING_MORNING_ACTIVITY"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M018 — Morning concern detected offline replays with original detection time
Scenario ID: `morning-wan-offline-replay`  
Requirements: E03, F08

**Steps**
1. Set internet disconnected
2. Advance simulated clock by 1300 seconds
3. Advance simulated clock by 60 seconds
4. Set internet connected

**Expected**
- `incidents` contains 1 item(s) matching `{"kind": "MISSING_MORNING_ACTIVITY"}`
- `timeline` contains 1 item(s) matching `{"kind": "MISSING_MORNING_ACTIVITY", "occurred_at": 2300}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M019 — Repeated deadline evaluation does not create duplicate missing incident
Scenario ID: `morning-repeat-deadline-idempotent`  
Requirements: E02, F08

**Steps**
1. Advance simulated clock by 1300 seconds
2. Evaluate routine deadline again.
3. Evaluate routine deadline again.

**Expected**
- `incidents` contains 1 item(s) matching `{"kind": "MISSING_MORNING_ACTIVITY"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

## Door scenarios

### M020 — Door opening in configured quiet hours is unexpected/red
Scenario ID: `door-late-night-red`  
Requirements: F09

**Steps**
1. Inject DOOR_OPEN from entry using the late-night control

**Expected**
- `home.latest_activity.details.unexpected` eq `True`
- `home.latest_activity.tone` eq `danger`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M021 — Quiet-hour door opening is normal when the household disables that rule
Scenario ID: `door-quiet-rule-disabled`  
Requirements: F09, E07

**Steps**
1. Change household setting(s): {"quiet_hours_enabled": false}
2. Inject DOOR_OPEN from entry using the late-night control

**Expected**
- `home.latest_activity.details.unexpected` eq `False`
- `home.latest_activity.tone` eq `positive`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M022 — Late-night door concern is suppressed in AWAY mode
Scenario ID: `door-late-night-away-suppressed`  
Requirements: F09, F10

**Steps**
1. Set home mode to AWAY
2. Inject DOOR_OPEN from entry using the late-night control

**Expected**
- `home.latest_activity.details.unexpected` eq `False`
- `home.mode` eq `AWAY`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M023 — Late-night door concern is suppressed in PAUSED mode
Scenario ID: `door-late-night-paused-suppressed`  
Requirements: F09, F10

**Steps**
1. Set home mode to PAUSED
2. Inject DOOR_OPEN from entry using the late-night control

**Expected**
- `home.latest_activity.details.unexpected` eq `False`
- `home.mode` eq `PAUSED`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M024 — Late-night door concern is suppressed in VISITOR mode
Scenario ID: `door-late-night-visitor-suppressed`  
Requirements: F09, F10

**Steps**
1. Set home mode to VISITOR
2. Inject DOOR_OPEN from entry using the late-night control

**Expected**
- `home.latest_activity.details.unexpected` eq `False`
- `home.mode` eq `VISITOR`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M025 — Door left open before threshold does not warn
Scenario ID: `door-left-open-before-threshold`  
Requirements: F09

**Steps**
1. Inject DOOR_OPEN from entry
2. Advance simulated clock by 299 seconds

**Expected**
- `timeline` contains 0 item(s) matching `{"kind": "DOOR_LEFT_OPEN"}`
- `home.door_status.left_open` eq `False`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M026 — Door left open at threshold creates one red warning
Scenario ID: `door-left-open-at-threshold`  
Requirements: F09

**Steps**
1. Change household setting(s): {"door_open_timeout_seconds": 300}
2. Inject DOOR_OPEN from entry
3. Advance simulated clock by 300 seconds

**Expected**
- `timeline` contains 1 item(s) matching `{"kind": "DOOR_LEFT_OPEN", "tone": "danger"}`
- `home.door_status.left_open` eq `True`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M027 — Door closed before threshold remains normal
Scenario ID: `door-close-before-threshold`  
Requirements: F09

**Steps**
1. Inject DOOR_OPEN from entry
2. Advance simulated clock by 240 seconds
3. Inject DOOR_CLOSED from entry

**Expected**
- `timeline` contains 0 item(s) matching `{"kind": "DOOR_LEFT_OPEN"}`
- `home.latest_activity.kind` eq `DOOR_CLOSED`
- `home.latest_activity.tone` eq `positive`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M028 — Closing a left-open door clears current condition and preserves duration
Scenario ID: `door-close-after-warning`  
Requirements: F09

**Steps**
1. Change household setting(s): {"door_open_timeout_seconds": 300}
2. Inject DOOR_OPEN from entry
3. Advance simulated clock by 360 seconds
4. Inject DOOR_CLOSED from entry

**Expected**
- `timeline` contains 1 item(s) matching `{"kind": "DOOR_LEFT_OPEN"}`
- `home.latest_activity.details.resolved_left_open` eq `True`
- `home.latest_activity.details.open_duration_s` ge `360`
- `home.door_status.state` eq `CLOSED`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M029 — Standalone close state does not invent a left-open warning
Scenario ID: `door-close-without-open`  
Requirements: F09

**Steps**
1. Inject DOOR_CLOSED from entry

**Expected**
- `timeline` contains 0 item(s) matching `{"kind": "DOOR_LEFT_OPEN"}`
- `home.door_status.state` eq `CLOSED`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M030 — Door-left-open threshold follows household configuration
Scenario ID: `door-configurable-threshold`  
Requirements: F09, E07

**Steps**
1. Change household setting(s): {"door_open_timeout_seconds": 120}
2. Inject DOOR_OPEN from entry
3. Advance simulated clock by 119 seconds
4. Advance simulated clock by 1 seconds

**Expected**
- `timeline` contains 1 item(s) matching `{"kind": "DOOR_LEFT_OPEN"}`
- `home.door_status.left_open` eq `True`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

## Inactivity scenarios

### M031 — No activity before configured threshold does not alert
Scenario ID: `inactivity-before-threshold`  
Requirements: F11

**Steps**
1. Change household setting(s): {"daytime_inactivity_seconds": 300}
2. Set simulated local minute to 600
3. Advance simulated clock by 299 seconds

**Expected**
- `timeline` contains 0 item(s) matching `{"kind": "DAYTIME_INACTIVITY"}`
- `incidents` contains 0 item(s) matching `{"kind": "DAYTIME_INACTIVITY"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M032 — No activity at configured threshold opens check-in workflow
Scenario ID: `inactivity-at-threshold`  
Requirements: F11, F12

**Steps**
1. Change household setting(s): {"daytime_inactivity_seconds": 300}
2. Set simulated local minute to 600
3. Advance simulated clock by 300 seconds

**Expected**
- `timeline` contains 1 item(s) matching `{"kind": "DAYTIME_INACTIVITY", "tone": "danger"}`
- `incidents` contains 1 item(s) matching `{"kind": "DAYTIME_INACTIVITY", "state": "OPEN"}`
- `notifications` contains 2 item(s) matching `{}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M033 — Activity resets daytime inactivity timer
Scenario ID: `inactivity-motion-rearms`  
Requirements: F05

**Steps**
1. Change household setting(s): {"daytime_inactivity_seconds": 300}
2. Set simulated local minute to 600
3. Advance simulated clock by 240 seconds
4. Inject MOTION from room1
5. Advance simulated clock by 240 seconds

**Expected**
- `timeline` contains 0 item(s) matching `{"kind": "DAYTIME_INACTIVITY"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M034 — Disabled daytime inactivity policy produces no concern
Scenario ID: `inactivity-disabled`  
Requirements: E07

**Steps**
1. Change household setting(s): {"daytime_inactivity_enabled": false, "daytime_inactivity_seconds": 300}
2. Set simulated local minute to 600
3. Advance simulated clock by 600 seconds

**Expected**
- `timeline` contains 0 item(s) matching `{"kind": "DAYTIME_INACTIVITY"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M035 — Daytime inactivity is suppressed in AWAY mode
Scenario ID: `inactivity-away-suppressed`  
Requirements: F10

**Steps**
1. Change household setting(s): {"daytime_inactivity_seconds": 300}
2. Set simulated local minute to 600
3. Set home mode to AWAY
4. Advance simulated clock by 300 seconds

**Expected**
- `timeline` contains 0 item(s) matching `{"kind": "DAYTIME_INACTIVITY"}`
- `home.mode` eq `AWAY`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M036 — Daytime inactivity is suppressed in PAUSED mode
Scenario ID: `inactivity-paused-suppressed`  
Requirements: F10

**Steps**
1. Change household setting(s): {"daytime_inactivity_seconds": 300}
2. Set simulated local minute to 600
3. Set home mode to PAUSED
4. Advance simulated clock by 300 seconds

**Expected**
- `timeline` contains 0 item(s) matching `{"kind": "DAYTIME_INACTIVITY"}`
- `home.mode` eq `PAUSED`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M037 — Daytime inactivity is suppressed in VISITOR mode
Scenario ID: `inactivity-visitor-suppressed`  
Requirements: F10

**Steps**
1. Change household setting(s): {"daytime_inactivity_seconds": 300}
2. Set simulated local minute to 600
3. Set home mode to VISITOR
4. Advance simulated clock by 300 seconds

**Expected**
- `timeline` contains 0 item(s) matching `{"kind": "DAYTIME_INACTIVITY"}`
- `home.mode` eq `VISITOR`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M038 — Daytime inactivity is suppressed when observation coverage is unavailable
Scenario ID: `inactivity-coverage-gap-suppressed`  
Requirements: E01

**Steps**
1. Change household setting(s): {"daytime_inactivity_seconds": 300}
2. Set simulated local minute to 600
3. Set node kitchen link unavailable
4. Advance simulated clock by 300 seconds

**Expected**
- `timeline` contains 0 item(s) matching `{"kind": "DAYTIME_INACTIVITY"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M039 — Daytime inactivity is suppressed when time is untrusted
Scenario ID: `inactivity-clock-untrusted-suppressed`  
Requirements: E06

**Steps**
1. Change household setting(s): {"daytime_inactivity_seconds": 300}
2. Set simulated local minute to 600
3. Set clock untrusted
4. Advance simulated clock by 300 seconds

**Expected**
- `timeline` contains 0 item(s) matching `{"kind": "DAYTIME_INACTIVITY"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M040 — Daytime inactivity does not fire outside configured daytime window
Scenario ID: `inactivity-outside-daytime-window`  
Requirements: E06

**Steps**
1. Change household setting(s): {"daytime_inactivity_seconds": 300}
2. Set simulated local minute to 1380
3. Advance simulated clock by 300 seconds

**Expected**
- `timeline` contains 0 item(s) matching `{"kind": "DAYTIME_INACTIVITY"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

## Transport scenarios

### M041 — WAN loss keeps local evidence while backend view is stale
Scenario ID: `wan-loss-local-progress`  
Requirements: E03, E04

**Steps**
1. Set internet disconnected
2. Inject MOTION from kitchen
3. Advance simulated clock by 240 seconds

**Expected**
- `simulation.activity_seen` is true/non-empty
- `simulation.pending_cloud` gt `0`
- `home.hub_reachable` eq `False`
- `timeline` contains 0 item(s) matching `{"kind": "MOTION"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M042 — WAN reconnect replays pending event exactly once
Scenario ID: `wan-reconnect-replays`  
Requirements: E02, E03

**Steps**
1. Set internet disconnected
2. Inject MOTION from kitchen
3. Set internet connected

**Expected**
- `simulation.pending_cloud` eq `0`
- `timeline` contains 1 item(s) matching `{"kind": "MOTION"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M043 — Node link recovery replays retained event exactly once
Scenario ID: `node-link-replay`  
Requirements: E02

**Steps**
1. Set node kitchen link unavailable
2. Inject MOTION from kitchen
3. Set node kitchen link available

**Expected**
- `timeline` contains 1 item(s) matching `{"kind": "MOTION"}`
- `simulation.nodes.1.retained` eq `0`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M044 — Duplicate radio replay is stored once by backend
Scenario ID: `duplicate-event-backend-idempotent`  
Requirements: E02

**Steps**
1. Inject MOTION from kitchen
2. Replay the last node business event.

**Expected**
- `timeline` contains 1 item(s) matching `{"kind": "MOTION"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M045 — Call Family survives WAN outage and opens one incident on reconnect
Scenario ID: `call-family-offline-replay`  
Requirements: E03, F07

**Steps**
1. Set internet disconnected
2. Inject CALL_FAMILY from room1
3. Set internet connected

**Expected**
- `incidents` contains 1 item(s) matching `{"kind": "CALL_FAMILY"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

## Caregiver scenarios

### M046 — Notification provider acceptance does not acknowledge incident
Scenario ID: `provider-acceptance-not-human-ack`  
Requirements: F12, F13

**Steps**
1. Advance simulated clock by 1300 seconds
2. Run fake notification-provider delivery.

**Expected**
- `incidents` contains 1 item(s) matching `{"kind": "MISSING_MORNING_ACTIVITY", "state": "OPEN"}`
- `notifications` contains >=1 item(s) matching `{"state": "PROVIDER_ACCEPTED"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M047 — Claim acknowledge resolve closes incident and cancels pending routes
Scenario ID: `caregiver-lifecycle`  
Requirements: F12, F13

**Steps**
1. Advance simulated clock by 1300 seconds
2. Record the first incident ID shown by the simulator.
3. As primary caregiver, claim the captured incident
4. As primary caregiver, acknowledge the captured incident
5. As primary caregiver, resolve the captured incident

**Expected**
- `incidents` contains 1 item(s) matching `{"state": "RESOLVED"}`
- `notifications` contains 2 item(s) matching `{"state": "CANCELLED"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

## Configuration scenarios

### M048 — Changing household policy creates a new config version
Scenario ID: `settings-version-increments`  
Requirements: E07

**Steps**
1. Change household setting(s): {"door_open_timeout_seconds": 180}

**Expected**
- `settings.config_version` ge `2`
- `settings.door_open_timeout_seconds` eq `180`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

## Negative scenarios

### M049 — User-facing privacy event is not accepted by simulator controls
Scenario ID: `invalid-privacy-event-rejected`  
Requirements: F02

**Steps**
1. Inject PRIVACY_ON from room1 (expect rejection: invalid node or event)

**Expected**
- The requested invalid operation is rejected and the simulator remains usable.

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M050 — Sensor capability mismatch is rejected
Scenario ID: `invalid-kitchen-door-event-rejected`  
Requirements: E07

**Steps**
1. Inject DOOR_OPEN from kitchen (expect rejection: not supported)

**Expected**
- The requested invalid operation is rejected and the simulator remains usable.

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M051 — Resident button event cannot be injected through door sensor
Scenario ID: `invalid-entry-ok-event-rejected`  
Requirements: E07

**Steps**
1. Inject OK_PRESSED from entry (expect rejection: not supported)

**Expected**
- The requested invalid operation is rejected and the simulator remains usable.

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M052 — Negative simulated time advance is rejected
Scenario ID: `invalid-advance-rejected`  
Requirements: NFR-08

**Steps**
1. Advance simulated clock by -1 seconds (expect rejection: seconds must)

**Expected**
- The requested invalid operation is rejected and the simulator remains usable.

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M053 — Invalid local minute is rejected
Scenario ID: `invalid-local-time-rejected`  
Requirements: E06

**Steps**
1. Set simulated local minute to 1440

**Expected**
- The requested invalid operation is rejected and the simulator remains usable.

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M054 — Unsupported mode is rejected
Scenario ID: `invalid-mode-rejected`  
Requirements: F10

**Steps**
1. Set home mode to PRIVACY (expect rejection: invalid mode)

**Expected**
- The requested invalid operation is rejected and the simulator remains usable.

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M055 — Unsafe door timeout setting is rejected
Scenario ID: `invalid-door-timeout-rejected`  
Requirements: E07

**Steps**
1. Change household setting(s): {"door_open_timeout_seconds": 20} (expect rejection: door_open_timeout_seconds)

**Expected**
- The requested invalid operation is rejected and the simulator remains usable.

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M056 — Unsafe inactivity threshold is rejected
Scenario ID: `invalid-inactivity-threshold-rejected`  
Requirements: E07

**Steps**
1. Change household setting(s): {"daytime_inactivity_seconds": 200} (expect rejection: daytime_inactivity_seconds)

**Expected**
- The requested invalid operation is rejected and the simulator remains usable.

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M057 — Unknown node cannot inject sensor data
Scenario ID: `unknown-node-rejected`  
Requirements: E07

**Steps**
1. Inject MOTION from garage (expect rejection: invalid node or event)

**Expected**
- The requested invalid operation is rejected and the simulator remains usable.

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

## Diagnostics scenarios

### M058 — Node fault LOW_BATTERY maps to stable diagnostics
Scenario ID: `node-fault-low_battery`  
Requirements: E01, E10

**Steps**
1. Inject LOW_BATTERY on kitchen
2. Run Troubleshoot on kitchen

**Expected**
- `devices` contains 1 item(s) matching `{"active": true, "code": "GS-N001", "health": "DEGRADED", "id": "kitchen"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M059 — Node fault BATTERY_DEPLETED maps to stable diagnostics
Scenario ID: `node-fault-battery_depleted`  
Requirements: E01, E10

**Steps**
1. Inject BATTERY_DEPLETED on kitchen
2. Run Troubleshoot on kitchen

**Expected**
- `devices` contains 1 item(s) matching `{"active": false, "code": "GS-N002", "health": "OFFLINE", "id": "kitchen"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M060 — Node fault LINK_LOSS maps to stable diagnostics and reboot recovery
Scenario ID: `node-fault-link_loss`  
Requirements: E01, E10

**Steps**
1. Inject LINK_LOSS on kitchen
2. Run Troubleshoot on kitchen
3. Run Reboot on kitchen

**Expected**
- `devices` contains 1 item(s) matching `{"active": true, "code": "GS-OK000", "health": "ACTIVE", "id": "kitchen"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M061 — Node fault SENSOR_FAULT maps to stable diagnostics
Scenario ID: `node-fault-sensor_fault`  
Requirements: E01, E10

**Steps**
1. Inject SENSOR_FAULT on kitchen
2. Run Troubleshoot on kitchen

**Expected**
- `devices` contains 1 item(s) matching `{"active": true, "code": "GS-N004", "health": "DEGRADED", "id": "kitchen"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M062 — Node fault OVER_TEMP maps to stable diagnostics
Scenario ID: `node-fault-over_temp`  
Requirements: E01, E10

**Steps**
1. Inject OVER_TEMP on kitchen
2. Run Troubleshoot on kitchen

**Expected**
- `devices` contains 1 item(s) matching `{"active": false, "code": "GS-N005", "health": "OFFLINE", "id": "kitchen"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M063 — Node fault WATCHDOG maps to stable diagnostics and reboot recovery
Scenario ID: `node-fault-watchdog`  
Requirements: E01, E10

**Steps**
1. Inject WATCHDOG on kitchen
2. Run Troubleshoot on kitchen
3. Run Reboot on kitchen

**Expected**
- `devices` contains 1 item(s) matching `{"active": true, "code": "GS-OK000", "health": "ACTIVE", "id": "kitchen"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M064 — Hub fault POWER_LOSS maps to stable diagnostics
Scenario ID: `hub-fault-power_loss`  
Requirements: E04, E10

**Steps**
1. Inject POWER_LOSS on hub
2. Run Troubleshoot on hub

**Expected**
- `devices` contains 1 item(s) matching `{"active": false, "code": "GS-H001", "health": "OFFLINE", "id": "hub"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M065 — Hub fault NODE_RADIO_FAILURE maps to stable diagnostics and reboot recovery
Scenario ID: `hub-fault-node_radio_failure`  
Requirements: E04, E10

**Steps**
1. Inject NODE_RADIO_FAILURE on hub
2. Run Troubleshoot on hub
3. Run Reboot on hub

**Expected**
- `devices` contains 1 item(s) matching `{"active": true, "code": "GS-OK000", "health": "ACTIVE", "id": "hub"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M066 — Hub fault INTERNET_LOSS maps to stable diagnostics
Scenario ID: `hub-fault-internet_loss`  
Requirements: E04, E10

**Steps**
1. Inject INTERNET_LOSS on hub
2. Run Troubleshoot on hub

**Expected**
- `devices` contains 1 item(s) matching `{"active": true, "code": "GS-H003", "health": "DEGRADED", "id": "hub"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M067 — Hub fault OVER_TEMP maps to stable diagnostics
Scenario ID: `hub-fault-over_temp`  
Requirements: E04, E10

**Steps**
1. Inject OVER_TEMP on hub
2. Run Troubleshoot on hub

**Expected**
- `devices` contains 1 item(s) matching `{"active": false, "code": "GS-H004", "health": "OFFLINE", "id": "hub"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M068 — Hub fault WATCHDOG maps to stable diagnostics and reboot recovery
Scenario ID: `hub-fault-watchdog`  
Requirements: E04, E10

**Steps**
1. Inject WATCHDOG on hub
2. Run Troubleshoot on hub
3. Run Reboot on hub

**Expected**
- `devices` contains 1 item(s) matching `{"active": true, "code": "GS-OK000", "health": "ACTIVE", "id": "hub"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

## Routine scenarios

### M069 — Configured bedroom → bathroom + kitchen completes morning routine
Scenario ID: `morning-sequence-bedroom-bathroom-kitchen-completes`  
Requirements: F04, F05, F09, F10, F11

**Steps**
1. Set simulated local minute to 420
2. Inject MOTION from room1
3. Advance simulated clock by 600 seconds
4. Inject MOTION from bathroom
5. Advance simulated clock by 600 seconds
6. Inject MOTION from kitchen

**Expected**
- `simulation.morning_sequence_completed` eq `True`
- `timeline` contains 1 item(s) matching `{"kind": "MORNING_ROUTINE_COMPLETED"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M070 — Bathroom before bedroom does not satisfy configured morning sequence
Scenario ID: `morning-sequence-bathroom-before-bedroom-does-not-complete`  
Requirements: F04, F05, F09, F10, F11

**Steps**
1. Set simulated local minute to 420
2. Inject MOTION from bathroom
3. Inject MOTION from room1
4. Inject MOTION from kitchen

**Expected**
- `simulation.morning_sequence_completed` eq `False`
- `timeline` contains 0 item(s) matching `{"kind": "MORNING_ROUTINE_COMPLETED"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

## Configuration scenarios

### M071 — Morning sequence uses configured locations rather than code constants
Scenario ID: `morning-sequence-configurable-locations`  
Requirements: F04, F05, F09, F10, F11

**Steps**
1. Change household setting(s): {"morning_bathroom_location": "common", "morning_bedroom_location": "pooja", "morning_kitchen_location": "kitchen"}
2. Set simulated local minute to 420
3. Inject MOTION from pooja
4. Inject MOTION from common
5. Inject MOTION from kitchen

**Expected**
- `simulation.morning_sequence_completed` eq `True`
- `settings.morning_bedroom_location` eq `pooja`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

## Boundary scenarios

### M072 — Morning sequence completion window is configurable
Scenario ID: `morning-sequence-window-configurable`  
Requirements: F04, F05, F09, F10, F11

**Steps**
1. Change household setting(s): {"morning_sequence_window_seconds": 600}
2. Set simulated local minute to 420
3. Inject MOTION from room1
4. Advance simulated clock by 601 seconds
5. Inject MOTION from bathroom
6. Inject MOTION from kitchen

**Expected**
- `simulation.morning_sequence_completed` eq `False`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M073 — Bathroom visits equal to configured limit do not alert
Scenario ID: `night-bathroom-at-configured-limit-no-alert`  
Requirements: F04, F05, F09, F10, F11

**Steps**
1. Change household setting(s): {"morning_sequence_enabled": false}
2. Set simulated local minute to 1380
3. Inject MOTION from bathroom
4. Advance simulated clock by 301 seconds
5. Inject MOTION from bathroom
6. Advance simulated clock by 301 seconds
7. Inject MOTION from bathroom
8. Advance simulated clock by 301 seconds
9. Inject MOTION from bathroom
10. Advance simulated clock by 301 seconds

**Expected**
- `simulation.night_bathroom_visits` eq `4`
- `timeline` contains 0 item(s) matching `{"kind": "UNUSUAL_NIGHT_BATHROOM_ACTIVITY"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

## Routine scenarios

### M074 — Bathroom visits greater than configured limit raise concern
Scenario ID: `night-bathroom-over-limit-alerts`  
Requirements: F04, F05, F09, F10, F11

**Steps**
1. Change household setting(s): {"morning_sequence_enabled": false}
2. Set simulated local minute to 1380
3. Inject MOTION from bathroom
4. Advance simulated clock by 301 seconds
5. Inject MOTION from bathroom
6. Advance simulated clock by 301 seconds
7. Inject MOTION from bathroom
8. Advance simulated clock by 301 seconds
9. Inject MOTION from bathroom
10. Advance simulated clock by 301 seconds
11. Inject MOTION from bathroom
12. Advance simulated clock by 301 seconds

**Expected**
- `simulation.night_bathroom_visits` eq `5`
- `timeline` contains 1 item(s) matching `{"kind": "UNUSUAL_NIGHT_BATHROOM_ACTIVITY"}`
- `incidents` contains 1 item(s) matching `{"kind": "UNUSUAL_NIGHT_BATHROOM_ACTIVITY"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

## Configuration scenarios

### M075 — Bathroom visit threshold from household settings changes the alert point
Scenario ID: `night-bathroom-threshold-configurable`  
Requirements: F04, F05, F09, F10, F11

**Steps**
1. Change household setting(s): {"morning_sequence_enabled": false, "night_bathroom_visit_threshold": 2}
2. Set simulated local minute to 1380
3. Inject MOTION from bathroom
4. Advance simulated clock by 301 seconds
5. Inject MOTION from bathroom
6. Advance simulated clock by 301 seconds
7. Inject MOTION from bathroom
8. Advance simulated clock by 301 seconds

**Expected**
- `settings.night_bathroom_visit_threshold` eq `2`
- `timeline` contains 1 item(s) matching `{"kind": "UNUSUAL_NIGHT_BATHROOM_ACTIVITY"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

## Routine scenarios

### M076 — Common-room visits greater than configured limit raise concern
Scenario ID: `night-common-over-limit-alerts`  
Requirements: F04, F05, F09, F10, F11

**Steps**
1. Change household setting(s): {"morning_sequence_enabled": false}
2. Set simulated local minute to 1380
3. Inject MOTION from common
4. Advance simulated clock by 301 seconds
5. Inject MOTION from common
6. Advance simulated clock by 301 seconds
7. Inject MOTION from common
8. Advance simulated clock by 301 seconds
9. Inject MOTION from common
10. Advance simulated clock by 301 seconds
11. Inject MOTION from common
12. Advance simulated clock by 301 seconds

**Expected**
- `simulation.night_common_visits` eq `5`
- `timeline` contains 1 item(s) matching `{"kind": "UNUSUAL_NIGHT_COMMON_ACTIVITY"}`
- `incidents` contains 1 item(s) matching `{"kind": "UNUSUAL_NIGHT_COMMON_ACTIVITY"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

## Configuration scenarios

### M077 — Common-room threshold is household-configurable
Scenario ID: `night-common-threshold-configurable`  
Requirements: F04, F05, F09, F10, F11

**Steps**
1. Change household setting(s): {"morning_sequence_enabled": false, "night_common_visit_threshold": 1}
2. Set simulated local minute to 1380
3. Inject MOTION from common
4. Advance simulated clock by 301 seconds
5. Inject MOTION from common
6. Advance simulated clock by 301 seconds

**Expected**
- `settings.night_common_visit_threshold` eq `1`
- `timeline` contains 1 item(s) matching `{"kind": "UNUSUAL_NIGHT_COMMON_ACTIVITY"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

## Boundary scenarios

### M078 — Repeated PIR events inside configured merge interval count as one visit
Scenario ID: `night-visit-merge-prevents-pir-burst-overcount`  
Requirements: F04, F05, F09, F10, F11

**Steps**
1. Change household setting(s): {"morning_sequence_enabled": false, "night_bathroom_visit_threshold": 1, "night_visit_merge_seconds": 600}
2. Set simulated local minute to 1380
3. Inject MOTION from bathroom
4. Advance simulated clock by 60 seconds
5. Inject MOTION from bathroom

**Expected**
- `simulation.night_bathroom_visits` eq `1`
- `timeline` contains 0 item(s) matching `{"kind": "UNUSUAL_NIGHT_BATHROOM_ACTIVITY"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M079 — Bathroom motion outside configured night window is not a night visit
Scenario ID: `night-motion-outside-window-not-counted`  
Requirements: F04, F05, F09, F10, F11

**Steps**
1. Change household setting(s): {"morning_sequence_enabled": false}
2. Set simulated local minute to 720
3. Inject MOTION from bathroom

**Expected**
- `simulation.night_bathroom_visits` eq `0`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

## Routine scenarios

### M080 — Door-open concern uses configured two-hour default
Scenario ID: `door-left-open-two-hour-config-default`  
Requirements: F04, F05, F09, F10, F11

**Steps**
1. Set simulated local minute to 720
2. Inject DOOR_OPEN from entry
3. Advance simulated clock by 7199 seconds

**Expected**
- `timeline` contains 0 item(s) matching `{"kind": "DOOR_LEFT_OPEN"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

## Boundary scenarios

### M081 — Door-left-open concern fires at configured threshold
Scenario ID: `door-left-open-configured-boundary`  
Requirements: F04, F05, F09, F10, F11

**Steps**
1. Change household setting(s): {"door_open_timeout_seconds": 7200, "morning_sequence_enabled": false}
2. Set simulated local minute to 720
3. Inject DOOR_OPEN from entry
4. Advance simulated clock by 7200 seconds

**Expected**
- `timeline` contains 1 item(s) matching `{"kind": "DOOR_LEFT_OPEN"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

### M082 — Door closed with no motion before configured threshold stays normal
Scenario ID: `post-door-inactivity-before-threshold-no-alert`  
Requirements: F04, F05, F09, F10, F11

**Steps**
1. Change household setting(s): {"post_door_inactivity_seconds": 7200}
2. Set simulated local minute to 720
3. Inject DOOR_OPEN from entry
4. Inject DOOR_CLOSED from entry
5. Advance simulated clock by 7199 seconds

**Expected**
- `simulation.post_door_inactivity_alerted` eq `False`
- `timeline` contains 0 item(s) matching `{"kind": "POST_DOOR_INACTIVITY"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

## Routine scenarios

### M083 — Door closed with no indoor motion reaches configured red-flag threshold
Scenario ID: `post-door-inactivity-at-threshold-alerts`  
Requirements: F04, F05, F09, F10, F11

**Steps**
1. Change household setting(s): {"post_door_inactivity_seconds": 7200}
2. Set simulated local minute to 720
3. Inject DOOR_OPEN from entry
4. Inject DOOR_CLOSED from entry
5. Advance simulated clock by 7200 seconds

**Expected**
- `simulation.post_door_inactivity_alerted` eq `True`
- `timeline` contains 1 item(s) matching `{"kind": "POST_DOOR_INACTIVITY"}`
- `incidents` contains 1 item(s) matching `{"kind": "POST_DOOR_INACTIVITY"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

## Recovery scenarios

### M084 — Indoor motion after door close cancels post-door inactivity concern
Scenario ID: `post-door-indoor-motion-cancels-alert`  
Requirements: F04, F05, F09, F10, F11

**Steps**
1. Change household setting(s): {"post_door_inactivity_seconds": 7200}
2. Set simulated local minute to 720
3. Inject DOOR_OPEN from entry
4. Inject DOOR_CLOSED from entry
5. Advance simulated clock by 3600 seconds
6. Inject MOTION from room1
7. Advance simulated clock by 3600 seconds

**Expected**
- `simulation.post_door_inactivity_alerted` eq `False`
- `timeline` contains 0 item(s) matching `{"kind": "POST_DOOR_INACTIVITY"}`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

## Configuration scenarios

### M085 — Household routine settings are versioned and visible after apply
Scenario ID: `household-routine-settings-versioned`  
Requirements: F04, F05, F09, F10, F11

**Steps**
1. Change household setting(s): {"door_open_timeout_seconds": 5400, "night_bathroom_visit_threshold": 3, "night_common_visit_threshold": 2, "post_door_inactivity_seconds": 9000}

**Expected**
- `settings.night_bathroom_visit_threshold` eq `3`
- `settings.night_common_visit_threshold` eq `2`
- `settings.door_open_timeout_seconds` eq `5400`
- `settings.post_door_inactivity_seconds` eq `9000`
- `settings.config_version` ge `2`

Result: ☐ PASS ☐ FAIL   Notes: ______________________________

## Additional visual/accessibility checks

- ☐ I am OK is visually positive/green and includes elapsed time.
- ☐ Unexpected/concern events are visually distinct in red and are not communicated by color alone.
- ☐ Active/degraded/offline device states have text labels as well as colored status circles.
- ☐ 390 px mobile viewport has no horizontal overflow and primary controls remain usable.
- ☐ Family/caregiver timeline is newest-first and missing-morning/call incidents are not hidden by later activity.
- ☐ Settings values reload after Save and display the new configuration version.
- ☐ No Privacy ON/OFF control is present in normal household Settings.

## Physical-hardware acceptance (cannot be completed in host simulation)

These are mandatory before an unattended pilot but are intentionally not marked automated PASS: real PIR/reed/button debounce, ESP-NOW RF/link loss, RSSI, battery calibration/runtime, brown-out, charging/UPS, actual reboot/reset reason, temperature telemetry, flash persistence/wear, OTA signature/rollback, real push delivery, and installed-home coverage.

