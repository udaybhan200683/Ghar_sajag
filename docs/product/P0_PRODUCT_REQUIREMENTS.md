# P0 Product Requirements — Current Baseline

**Authority:** canonical P0/R1 product requirements. This document states product behavior supported by current repository decisions. Implementation guides and test plans explain/code or verify details; they do not promote unqualified lab behavior into a physical product claim.

**Status key:** `LOCKED` is an approved product rule; `OPEN` means the repository does not settle the behavior. “Implemented” and “qualified” describe evidence boundaries, not product authority.

## Household and caregiver

- A household has a resident/home, an authorized Hub, assigned Nodes, and caregiver-facing access. Household configuration is the policy input for deterministic rules. **LOCKED; R1.** Full production invitation, enrollment and consent operations are not established by the local-lab UI. **Implementation boundary:** see [device identity lifecycle](../features/DEVICE_IDENTITY_REGISTRATION_AND_LIFECYCLE.md) and [caregiver actions](../features/CAREGIVER_ACTIONS_AND_NOTIFICATIONS.md).
- Caregiver incident actions distinguish taking responsibility, acknowledgement and resolution. A resident action or notification-provider acceptance is not caregiver acknowledgement; history remains chronological. **LOCKED behavior in the application model; production account/provider deployment is not proven.**
- The current PWA/backend model shows household activity, event history, concerns, device status and routine policy. It must not claim emergency dispatch, clinical monitoring, or a live human response service. **LOCKED boundary;** actual deployed service coverage is **OPEN**.

## Hub and Node responsibilities

- The Hub authenticates enrolled Nodes, accepts their events, applies local product rules, commits required event state before application ACK, and buffers/synchronizes caregiver-relevant data. Cloud outage must not stop local sensing, safety behavior or routine processing. **LOCKED; R1.** See [release contract](R1_RELEASE_CONTRACT.md) and [storage/sync contract](../architecture/STORAGE_SYNC_ROUTINE_LEARNING.md).
- Sensor Nodes use ESP32-C3 for the R1 baseline. The Node samples its configured sensor, creates identified events, retains/retries them, and retires them only on a valid application ACK or explicit discard-policy result. **LOCKED; R1.** Physical fresh-install, retry, ACK retirement and lost-ACK gates are closed per [R1 work state](R1_WORK_STATE.md).
- The physically established current Node input is PIR motion on GPIO4. The production target is PIR-focused. Other event types in the shared domain model do not by themselves prove that a corresponding physical sensor/button is installed or qualified.

## Sensor and event categories

The shared event model names motion, door-open/closed, resident OK, Call Family, heartbeat, privacy, gap and motion-summary events; sensor types include PIR, Reed, Button, Heartbeat and System. This is the **software/domain vocabulary**, not a claim that every sensor or event source is present in the qualified physical build.

| Category | Current product meaning | Boundary/status |
|---|---|---|
| PIR motion | A room activity observation associated with a Node/location and event time | P0. ESP32-C3 GPIO4 PIR path is physically exercised. Time-dependent Hub rule outcomes on secure target are not fully qualified. |
| Reed/door transition | Main-door open/closed chronology; do not collapse it into generic motion | P0 application/domain behavior. Physical Reed installation and end-to-end production qualification are **OPEN**. |
| Heartbeat/NodeHealth | Device contact/health evidence, separate from resident activity and event ACK | P0 device-health concept. It does not prove battery voltage; NodeHealth currently has no battery ADC field. |
| `OK_PRESSED` | Explicit resident check-in evidence, separate from motion | P0 application event/routine input. Production physical button input is **not established**; host/simulator entry exists. |
| `CALL_FAMILY` | Explicit assistance request, creates a distinct caregiver-facing concern in the application model | P0 feature flag is enabled by default. Physical resident control and live notification-provider delivery are **not established**. It is not emergency dispatch. |
| Privacy events/mode | Internal consent/privacy enforcement and rule suppression | See the locked privacy rule below. A privacy event enum does not authorize a public toggle or imply physical input. |
| Gap/motion summary | Transport/storage diagnostics or coalesced motion representation | Product use and caregiver visibility beyond existing application semantics are **OPEN**; preserve loss/correctness meaning. |

## Main door, room activity, bathroom and kitchen

- Where door-transition events are available, show main-door opened/closed chronology and duration/cleared information when available. Configured quiet-hours opening or a door left open may produce a caregiver concern. A close does not erase prior event history. **P0 application behavior.** Physical Reed sensing and secure-target rule qualification remain **OPEN**.
- Room PIR observations are shown with location, such as “Motion detected — kitchen.” Ordinary activity is positive evidence, not proof of wellbeing or a medical conclusion. **P0.**
- Bathroom and kitchen activity can participate in configured morning-sequence and night-visit rules; the application/rule guide describes bedroom, bathroom and kitchen evidence. Such interpretation depends on configured locations, trusted time, mode and sensor coverage. **P0 application/rule behavior;** exact current product defaults and physically qualified target behavior are **OPEN**. Do not treat a missing event as inactivity when coverage/time is unknown.
- Routine windows, thresholds, uncertainty handling and incident identity are configuration/rule details. Read [routine/activity rules](../features/ROUTINE_ACTIVITY_AND_INCIDENT_RULES.md); do not copy historical or simulator defaults into a product requirement.

## Resident interactions, caregiver concerns and notifications

- `I Am OK` is a distinct chronological event and can be evidence for a matching morning check-in independently of PIR in the application model. It does not erase an earlier concern or resolve an unrelated Call Family incident. Current physical resident button support is **OPEN/not established**.
- `Call Family` creates a distinct assistance concern in the local application model. Caregiver claim/acknowledge/resolve operations are separate. The repository does not establish production SMS, phone call, always-running push delivery, care center or emergency dispatch. Provider acceptance is not proof a caregiver received/read a notification.
- PWA event/timeline presentation retains event meaning and chronology. Main-door events, room motion, I Am OK, Call Family and rule concerns have distinct text/meaning where those application paths exist. Exact production PWA availability and physical event-to-cloud integration must be verified against current release evidence; simulator support is not physical qualification.

## Device offline and battery health

- No motion is not evidence that a Node is offline. Device liveness/coverage derives from authenticated health/event contact separately from resident activity. Unknown coverage suppresses time-based “no activity” conclusions. **LOCKED safety rule;** exact target clock/coverage integration has limitations documented in the [device health guide](../features/DEVICE_HEALTH_LIVENESS_AND_OFFLINE_DETECTION.md).
- During Hub/backend outage, local sensing and Node retry/retention continue; PWA/backend freshness must be shown as stale/offline where connectivity is unavailable. **LOCKED architecture behavior.** Exact supported outage duration/backlog guarantee is **OPEN**.
- Node health diagnostics expose runtime/contact and queue information, not a qualified battery gauge. Battery voltage/SOC, remaining-life claims and a commercial battery-life number are **OPEN/unqualified** unless supported by calibrated hardware evidence. See [battery/power guide](../features/BATTERY_LOW_POWER_AND_POWER_MANAGEMENT.md).
- Production-critical BAT-C8 power behavior is an **R1-required feature with physical qualification pending** (GS-D020). Qualification must prove intended production sleep entry, required GPIO/timer wake, bounded wake/resume, sensing/runtime restoration, required radio restoration, safe fail-awake behavior, and no required event-processing regression. Final battery-life optimization and long-duration endurance are not R1 blockers without an explicit R1 battery-life claim. Test details are in the BAT-C8 plan; P1–P10 are test-case identifiers.

## Routine learning and data visibility

- Safety-relevant routine/baseline/trend logic is intended to run locally with bounded state/aggregates; backend may provide richer long-term analytics. **LOCKED direction;** learning formulas, sufficiency/coverage criteria, persistence representation and current target maturity are **OPEN/partially implemented**. The current deterministic rules must not be described as a learned personalized baseline.
- Caregiver-relevant events are synchronized to backend continuously/near-real-time when connected; dashboard open is not the trigger for primary sync. PWA is backend-first and should display stale/offline status. **LOCKED direction;** exact deployed transport/service behavior is not physically qualified here. See [storage/sync contract](../architecture/STORAGE_SYNC_ROUTINE_LEARNING.md).

## Privacy — locked current behavior

- Do not expose a generic ordinary household Privacy ON/OFF selector as if it were a notification preference. The ordinary PWA mode selector omits that toggle.
- Consent withdrawal may enforce an internal privacy state. Routine rules suppress passive evidence in Privacy, as they also suppress/limit rules in applicable Away/Paused states. Household modes and notification preferences remain separate concepts.
- This is supported by later release notes removing the user-facing simulation toggle, the manual PWA validation checklist, and the caregiver/routine guides. **LOCKED; GS-D018.** This records existing approved behavior; it does not redesign consent, data deletion, access control or privacy UX beyond these statements.

## Explicitly deferred or not established

- P1 experiments: temperature context and external camera remain disabled; do not present temperature as fire/cooking detection. Fall detection and professional response require separate validation/service/liability decisions.
- Emergency dispatch, clinical claims, production SMS/telephone/push provider, and production resident buttons are not established.
- Deep sleep, calibrated battery-life promises, exact guaranteed offline duration, exact event/history retention, and a complete learned longitudinal baseline are not current verified behavior. Their product scope is governed by the decision log and future approved decisions.
- Final battery-life optimization, long-duration endurance, deep sleep/RTC retention, and calibrated battery telemetry remain distinct from the required BAT-C8 production behavior; do not silently expand the R1 gate into those claims.

## Detailed sources

See the [canonical index](CANONICAL_REQUIREMENTS_INDEX.md) for the authority map, requirement register and domain links. Implementation facts are documented in the feature guides and firmware notes; test plans and evidence establish only the exact validated build/configuration/workload.

## Storage-first, failure-aware routine requirements — GS-D021/022/023

**LOCKED:** Optimize qualifying designs for retained useful information/flash byte, deterministic retrieval, bounded RAM and flash lifetime before CPU cycles. Preserve correctness, authentication, crash safety, stability, scalability and caregiver UX.

**LOCKED:** Current and daily routine conclusions, coverage/confidence and recovery must remain correct through Node/Hub failures and reboot/rejoin, radio/internet/backend outages, lost ACK, backlog/multi-day recovery, rollover, delayed events, partial coverage and pressure. Distinguish NO_ACTIVITY from NO_OBSERVATION / SENSOR_UNAVAILABLE / HUB_UNAVAILABLE. Missing observation is never evidence of resident inactivity. These are requirements, not claims that the current secure target implements full coverage/day recovery. Exact formulas, time/lateness policy, offline guarantee and backend daily-effect contract remain OPEN.
