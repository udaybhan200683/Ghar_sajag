Ghar Sajag functional suite 1.5.4-routine-battery
PASS 92/92
PASS motion-room1-visible: Room 1 motion is preserved as exact positive activity
PASS motion-kitchen-visible: Kitchen motion is preserved as exact positive activity
PASS motion-pooja-visible: Pooja motion is preserved as exact positive activity
PASS door-open-daytime: Normal daytime door opening is green and explicit
PASS door-open-close-order: Door open and close remain chronological and explicit
PASS resident-ok-green: I am OK remains a distinct green self-check-in
PASS call-family-opens-workflow: Call Family opens exactly one incident and two routes
PASS call-then-ok-keeps-call: I am OK after Call Family is newer but does not resolve the request
PASS post-missing-activity-visible: Later activities remain visible after missing-morning alert
PASS morning-missing-covered: Covered morning with no evidence creates one concern
PASS morning-kitchen-qualifies: Kitchen motion satisfies morning routine
PASS morning-pooja-qualifies: Pooja motion satisfies morning routine
PASS morning-room1-not-qualifying: Room 1 motion does not silently satisfy kitchen/pooja morning policy
PASS morning-door-not-qualifying: Main-door activity does not silently satisfy kitchen/pooja morning policy
PASS morning-ok-qualifies: Explicit I am OK satisfies morning check-in independently of PIR
PASS morning-coverage-gap-suppresses: Missing sensor coverage suppresses inactivity interpretation
PASS morning-untrusted-clock-suppresses: Untrusted clock suppresses time-based morning concern
PASS morning-wan-offline-replay: Morning concern detected offline replays with original detection time
PASS morning-repeat-deadline-idempotent: Repeated deadline evaluation does not create duplicate missing incident
PASS door-late-night-red: Door opening in configured quiet hours is unexpected/red
PASS door-quiet-rule-disabled: Quiet-hour door opening is normal when the household disables that rule
PASS door-late-night-away-suppressed: Late-night door concern is suppressed in AWAY mode
PASS door-late-night-paused-suppressed: Late-night door concern is suppressed in PAUSED mode
PASS door-late-night-visitor-suppressed: Late-night door concern is suppressed in VISITOR mode
PASS door-left-open-before-threshold: Door left open before threshold does not warn
PASS door-left-open-at-threshold: Door left open at threshold creates one red warning
PASS door-close-before-threshold: Door closed before threshold remains normal
PASS door-close-after-warning: Closing a left-open door clears current condition and preserves duration
PASS door-close-without-open: Standalone close state does not invent a left-open warning
PASS door-configurable-threshold: Door-left-open threshold follows household configuration
PASS inactivity-before-threshold: No activity before configured threshold does not alert
PASS inactivity-at-threshold: No activity at configured threshold opens check-in workflow
PASS inactivity-motion-rearms: Activity resets daytime inactivity timer
PASS inactivity-disabled: Disabled daytime inactivity policy produces no concern
PASS inactivity-away-suppressed: Daytime inactivity is suppressed in AWAY mode
PASS inactivity-paused-suppressed: Daytime inactivity is suppressed in PAUSED mode
PASS inactivity-visitor-suppressed: Daytime inactivity is suppressed in VISITOR mode
PASS inactivity-coverage-gap-suppressed: Daytime inactivity is suppressed when observation coverage is unavailable
PASS inactivity-clock-untrusted-suppressed: Daytime inactivity is suppressed when time is untrusted
PASS inactivity-outside-daytime-window: Daytime inactivity does not fire outside configured daytime window
PASS wan-loss-local-progress: WAN loss keeps local evidence while backend view is stale
PASS wan-reconnect-replays: WAN reconnect replays pending event exactly once
PASS node-link-replay: Node link recovery replays retained event exactly once
PASS duplicate-event-backend-idempotent: Duplicate radio replay is stored once by backend
PASS call-family-offline-replay: Call Family survives WAN outage and opens one incident on reconnect
PASS provider-acceptance-not-human-ack: Notification provider acceptance does not acknowledge incident
PASS caregiver-lifecycle: Claim acknowledge resolve closes incident and cancels pending routes
PASS settings-version-increments: Changing household policy creates a new config version
PASS invalid-privacy-event-rejected: User-facing privacy event is not accepted by simulator controls
PASS invalid-kitchen-door-event-rejected: Sensor capability mismatch is rejected
PASS invalid-entry-ok-event-rejected: Resident button event cannot be injected through door sensor
PASS invalid-advance-rejected: Negative simulated time advance is rejected
PASS invalid-local-time-rejected: Invalid local minute is rejected
PASS invalid-mode-rejected: Unsupported mode is rejected
PASS invalid-door-timeout-rejected: Unsafe door timeout setting is rejected
PASS invalid-inactivity-threshold-rejected: Unsafe inactivity threshold is rejected
PASS unknown-node-rejected: Unknown node cannot inject sensor data
PASS node-fault-low_battery: Node fault LOW_BATTERY maps to stable diagnostics
PASS node-fault-battery_depleted: Node fault BATTERY_DEPLETED maps to stable diagnostics
PASS node-fault-link_loss: Node fault LINK_LOSS maps to stable diagnostics and reboot recovery
PASS node-fault-sensor_fault: Node fault SENSOR_FAULT maps to stable diagnostics
PASS node-fault-over_temp: Node fault OVER_TEMP maps to stable diagnostics
PASS node-fault-watchdog: Node fault WATCHDOG maps to stable diagnostics and reboot recovery
PASS hub-fault-power_loss: Hub fault POWER_LOSS maps to stable diagnostics
PASS hub-fault-node_radio_failure: Hub fault NODE_RADIO_FAILURE maps to stable diagnostics and reboot recovery
PASS hub-fault-internet_loss: Hub fault INTERNET_LOSS maps to stable diagnostics
PASS hub-fault-over_temp: Hub fault OVER_TEMP maps to stable diagnostics
PASS hub-fault-watchdog: Hub fault WATCHDOG maps to stable diagnostics and reboot recovery
PASS morning-sequence-bedroom-bathroom-kitchen-completes: Configured bedroom → bathroom + kitchen completes morning routine
PASS morning-sequence-bathroom-before-bedroom-does-not-complete: Bathroom before bedroom does not satisfy configured morning sequence
PASS morning-sequence-configurable-locations: Morning sequence uses configured locations rather than code constants
PASS morning-sequence-window-configurable: Morning sequence completion window is configurable
PASS night-bathroom-at-configured-limit-no-alert: Bathroom visits equal to configured limit do not alert
PASS night-bathroom-over-limit-alerts: Bathroom visits greater than configured limit raise concern
PASS night-bathroom-threshold-configurable: Bathroom visit threshold from household settings changes the alert point
PASS night-common-over-limit-alerts: Common-room visits greater than configured limit raise concern
PASS night-common-threshold-configurable: Common-room threshold is household-configurable
PASS night-visit-merge-prevents-pir-burst-overcount: Repeated PIR events inside configured merge interval count as one visit
PASS night-motion-outside-window-not-counted: Bathroom motion outside configured night window is not a night visit
PASS door-left-open-two-hour-config-default: Door-open concern uses configured two-hour default
PASS door-left-open-configured-boundary: Door-left-open concern fires at configured threshold
PASS post-door-inactivity-before-threshold-no-alert: Door closed with no motion before configured threshold stays normal
PASS post-door-inactivity-at-threshold-alerts: Door closed with no indoor motion reaches configured red-flag threshold
PASS post-door-indoor-motion-cancels-alert: Indoor motion after door close cancels post-door inactivity concern
PASS household-routine-settings-versioned: Household routine settings are versioned and visible after apply
PASS battery-prediction-baseline: Battery analytics predicts remaining days from voltage plus calibrated usage history
PASS battery-high-drain-detected: Sustained high wake/radio usage is detected and shortens battery-life prediction
PASS battery-low-voltage-reserve: Low battery voltage respects reserve and does not over-promise runtime
PASS battery-counter-reset-safe: Battery analytics tolerates device counter reset without negative energy
PASS battery-profile-capacity-configurable: Device battery capacity calibration changes runtime prediction without code change
PASS battery-alert-threshold-configurable: Household low-battery alert threshold is configuration, not a hardcoded value
PASS battery-invalid-usage-rejected: Invalid battery-usage telemetry controls are rejected safely
