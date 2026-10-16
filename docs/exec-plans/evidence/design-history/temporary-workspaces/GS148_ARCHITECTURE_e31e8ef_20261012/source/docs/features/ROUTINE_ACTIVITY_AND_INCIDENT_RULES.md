Feature documentation type:
ENGINEERING FUNCTIONAL GUIDE

This guide explains stable feature functionality and implementation.

It is NOT the current project-status authority.

For current project status:
docs/progress/CURRENT_STATUS_AND_ROADMAP.md

For implementation/evidence traceability:
docs/validation/MASTER_TRACEABILITY.csv

For formal qualification:
docs/validation/ and evidence/hil/runs/

# Routine, Activity and Incident Rules

## Product behavior

Ghar Sajag turns sensor events into evidence about household activity. A
motion or door event is an observation; a deterministic rule may interpret it
against the home's configured schedule and mode. A missing observation is
only meaningful when the clock and sensor coverage are trusted. The resulting
concern is shown as a caregiver-facing timeline item or incident.

```text
Sensor event
     |
     v
Activity observation with Node identity and event time
     |
     v
Home policy + mode + coverage + trusted time
     |
     v
Expected activity / unexpected activity / no evidence by deadline
     |
     v
Timeline and, for selected concerns, an incident
```

This guide describes implemented deterministic rules and the current host/PWA
path. It does not claim learned personal routines or complete physical
Hub-to-cloud behavior.

## Terms that are easy to conflate

- **Sensor event:** a specific input such as PIR motion, a door transition, or
  an explicit I am OK action. It has an event identity and timestamps.
- **Activity:** an interpretation of one or more observations, such as motion
  in the kitchen or the door being open.
- **Routine:** an expected pattern/window, for example the morning period.
- **Expectation:** a policy statement such as “covered morning activity is
  expected by the grace deadline.”
- **Rule:** deterministic code that evaluates configured policy against event
  evidence, time, mode and coverage.
- **Violation/concern:** a rule result that needs attention, such as missing
  morning evidence or a door left open.
- **Incident:** a stable, reviewable concern with lifecycle/acknowledgement
  where the backend incident model applies.
- **Alert/notification:** presentation or delivery work associated with a
  concern; a displayed alert does not itself prove a caregiver saw it.

## Policy ownership and configuration

Routine and activity policy is household/home configuration. The C++
`ActivityRuleConfig` describes quiet hours, daytime inactivity, morning
sequence, night visits, door-open and post-door thresholds. The PWA settings
flow serializes applied/desired home policy and the backend validates and
persists household settings in its current application path. These are not
per-person learned profiles. Some limits, including coverage requirements,
event test suppression, and stable incident identity, are fixed rule
semantics.

There are multiple implementation defaults: C++ `ActivityRuleConfig` seeds
quiet 01:00–05:00, daytime 08:00–21:00 with a 3-hour inactivity interval,
morning 06:00–11:00 and a 4-hour sequence, 2-hour door/post-door thresholds,
and night 22:00–06:00 with 5-minute visit merging and a threshold of four.
The PWA/local simulator has its own seeded configuration (including
quiet-hours defaults that differ). Deployed/apply configuration is the input
to decisions; do not assume C++ defaults and PWA defaults are interchangeable.
Review the current configuration payload when diagnosing a result.

Home modes also affect rule eligibility. Routine evidence is suppressed in
Privacy, Away and Paused. Timer-driven activity concerns require Home mode,
Covered sensor coverage and a trusted clock. There is no separate
person-specific policy model in these rules. Settings UI availability should
be checked in the current PWA build; requirements/design documents alone do
not prove a control is shipped.

## Morning check and morning sequence

Two related behaviors exist in source:

1. The `RulesCore` routine-window check accepts a qualifying activity event or
   explicit I am OK when its occurrence-time uncertainty interval overlaps
   the configured window. At/after `grace_end_at`, a missing-morning concern
   is created only if the rule is enabled, time is trusted, mode is Home,
   coverage is Covered, and no qualifying activity or explicit OK exists.
   A stable `missing-morning:<window_id>` key prevents repeat creation for
   that window. Unknown coverage or untrusted time suppresses the concern.
2. `HubRuntime` activity rules can recognize a motion sequence during the
   configured local morning window: bedroom motion starts/restarts a sequence;
   bathroom and kitchen evidence within the configured sequence window
   completes it. Bathroom and kitchen may arrive in either order. Completion
   emits an expected-tone signal once for the sequence.

   **CURRENT IMPLEMENTATION LIMITATION:** the sequence check currently tests
   only `event.occurred_at - morning_started_at <= window`; it does not enforce
   `event.occurred_at >= morning_started_at`. A late-arriving event whose
   `occurred_at` predates the bedroom event may therefore satisfy the check.

The routine-window check uses `RoutineConfig.qualifying_locations`: when this
set is populated, locations outside it do not satisfy the check; when it is
empty, the current implementation allows any location. This mechanism is
separate from the morning activity-sequence rule, which uses its configured
bedroom, bathroom and kitchen locations. A door transition does not satisfy
the routine-window check because that check accepts activity events or
explicit I Am OK. The PWA displays “Missing morning activity” as a concern
and preserves it in the timeline. Later events remain later evidence; they do
not rewrite the earlier chronology. The current simulated application
resolves its check-in concern on a matching explicit OK path; an OK arriving
after a morning window can satisfy a routine only if its occurrence interval
overlaps that window. It must not be treated as retroactive proof for an
earlier interval.

## Inactivity, night and door rules

```text
Valid activity
   |
   v
Set last-activity anchor and clear daytime inactivity latch
   |
   v
Home + Covered + trusted time + daytime window?
   | yes
   v
Configured interval elapsed -> one concern
   |
   v
New activity clears latch and starts a new interval
```

The C++ default daytime window is 08:00–21:00 and the default threshold is
three hours. The anchor is the last activity event, or the configured
monitoring-start time if there has been no activity. A daytime event resets
the alert latch; the next threshold can create a new concern. Timer rules are
suppressed unless Home, coverage Covered and clock trusted all hold.

Quiet-hours door interpretation is separate from inactivity. With the
default C++ policy, quiet hours are 01:00–05:00. A door-open event during that
window can immediately emit an unexpected-door concern if Home and time are
trusted. A door left open emits once after the configured two-hour timeout
when timer-rule eligibility holds. A subsequent close emits a resolution-like
expected signal if the door had crossed the timeout or had already alerted,
then clears open tracking. After a close, a separate default two-hour
post-door inactivity timer can emit if no motion follows.

Night activity counts distinct motion visits at the configured bathroom and
common zones during the night window. Repeated observations in one zone are
merged unless separated by at least five minutes. The default threshold is
four; the concern is emitted when the count becomes greater than four and
only once in that night window. A daytime event resets visit counts and
alert latches.

Door-open and door-close chronology remains explicit. UI text says “Main door
opened,” “Main door closed,” or “Main door kept open,” and a close can state
how long the door was open and that the warning cleared. This is more useful
than collapsing a door transition into generic motion.

## Expected and unexpected activity

The rule core assigns expected or concern tone to signals; event presentation
uses specific text and tone, not color alone. Normal motion/door activity is
positive, quiet-hours opening and a long-open door are danger, missing morning
and prolonged inactivity are concerns, and a Call Family request is a
warning. Modes suppress some rules rather than labeling suppressed evidence
unexpected. A color treatment is a visual aid; readable labels and event
details carry the actual meaning.

The core does not run a learned baseline or multi-day anomaly detector. A
single deterministic threshold/window rule is not “routine learning.”
Personalized baselines, deviation analysis and longitudinal trends remain
planned concepts in the roadmap.

## Time and coverage semantics

`DomainEvent` distinguishes `occurred_at` (Node-origin event time),
`received_at` (Hub receive/order time), monotonic milliseconds, uncertainty,
and event identity. Rules use occurrence time and local minute/window
configuration. Receive order is useful transport evidence but is not a
substitute for event chronology. The current secure target adapter does not
provide a trusted wall-clock local minute to the runtime rule-timer path, and
target events currently lack a trusted absolute Node clock. Time-based rules
must therefore not be claimed as physically operating on the secure target
path merely because the shared rules compile and host tests pass.

Sensor `CoverageState` is distinct from resident activity. The 190-second
Hub-side authenticated-contact policy marks a Node offline/coverage unknown;
no resident motion by itself does not. Missing morning/inactivity logic
requires coverage to be Covered so a disconnected sensor is not misread as a
quiet household.

## Recovery, reset and persistence

`ActivityRuleState` and routine state are runtime reducer state; the shared
rule structs do not themselves persist a complete rule checkpoint. The Hub
event journal restore reconstructs basic event-derived state, but current
status calls full timer/policy state restoration incomplete. A frontend reload
re-fetches backend/PWA household state and timeline from its configured store;
simulator volatile rule state may be recreated from simulator state. Backend
restart durability depends on which repository/store path is in use: local
foundation settings use SQLite, while the connected local lab explicitly uses
some in-memory event/incident models. Hub and Node restart do not create a
trusted wall clock or guarantee complete routine-state replay on target.

I Am OK is an explicit action/evidence event. In the morning window it can
satisfy the check-in independently of PIR. It does not automatically cancel
an unrelated Call Family request; that request remains a separate
chronological event and incident until caregiver workflow resolves it.

## Important rule interactions

- **Call Family + I Am OK:** both remain distinct events. A later OK does not
  erase a Call Family incident.
- **Inactivity + Node offline:** coverage becomes unavailable, so the
  activity concern is suppressed; connectivity is a separate system state.
- **Morning missing + later motion:** later motion may restore current
  activity state, but historical warning/event chronology remains visible.
- **Late-night door + normal movement:** the configured quiet-hours door rule
  can create a concern immediately; ordinary movement remains its own
  positive event. No general “normal movement cancels every concern” rule
  exists.
- **Privacy/Away/Paused:** suppress routine interpretation in the shared
  routine core; timer rules additionally require Home and Covered state.

## Failure and recovery matrix

| CONDITION | EXPECTED BEHAVIOR | IMPLEMENTATION STATUS | ENGINEER ACTION |
|---|---|---|---|
| Delayed event | Preserve event occurrence and mark/describe later receipt | PWA timeline supports delayed annotation; end-to-end target chronology is incomplete | Compare event key, occurred time, received time and uncertainty |
| Duplicate event | Stable identity/dedupe prevents duplicate logical event processing where ingest path applies | Host/backend dedupe implemented; validate path in use | Compare full EventKey and event journal/backend dedupe record |
| Missing event | No activity conclusion without adequate coverage/evidence | Rule checks coverage; target-to-PWA path incomplete | Check Node queue, ACK, Hub journal and coverage status |
| Node offline | Show connectivity/coverage concern, not resident inactivity | Hub liveness implemented; physical current-head qualification boundary applies | Check last authenticated contact and 190-second policy |
| Hub offline | Node delivery/recovery and PWA connectivity states differ | Node retention path implemented; vertical user-flow incomplete | Check Hub restart/radio state and backend reachability separately |
| Wrong clock/time | Suppress time-based conclusions when clock untrusted | Shared rule context supports this; target trusted clock not integrated | Inspect timezone, clock trust, event uncertainty and local minute |
| Browser refresh | Re-fetch stored PWA/backend state; in-memory simulation state may reset | Host/browser coverage exists; store path matters | Check API response and local-lab process/store identity |
| Morning activity late | Do not rewrite past event order; create later evidence according to its timestamp | Host rule/UI tests cover chronology | Compare occurred/received timestamps, window and grace end |
| Repeated PIR motion | Current implementation sees separate observations/events; it does not aggregate episodes | Implemented active path; aggregation planned | Inspect retrigger/debounce, queue limits and duplicate keys |
| Late-night door event | Quiet-hours door opening may immediately produce concern | Host rule/UI behavior; physical target rules not qualified | Inspect local time, applied quiet hours, mode and clock trust |

## Code, tests and qualification

Main locations:

- `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/shared/include/gs/domain.hpp` — event, routine, mode, coverage and household rule contracts/defaults.
- `.../shared/include/gs/rules.hpp` and `.../shared/src/rules.cpp` — deterministic routine/activity state and timer logic.
- `.../firmware/hub/runtime/hub_runtime.cpp` — event application and rule invocation boundary.
- `.../backend/ghar_sajag/foundation.py`, `.../backend/ghar_sajag/sqlite_events.py` — PWA household policy, event and persisted foundation paths.
- `.../app/src/features/home/index.mjs` — readable event/timeline semantics and presentation tones.
- `.../tools/sim/local_lab.py` — simulator events, derived concern and dashboard mapping.
- `.../tests/cpp/test_main.cpp`, `.../tests/python/test_phase1_application.py`, `.../tests/playwright/phase1_ui_contract.spec.ts`, `.../tests/MANUAL_FUNCTIONAL_VALIDATION.md` — deterministic rule, application and browser contract coverage.

| EVIDENCE CLASS | BOUNDARY |
|---|---|
| IMPLEMENTED | Shared deterministic morning/activity/door/night rules; PWA/simulator timeline and configured policy handling |
| HOST_VERIFIED | C++ rule tests, Python simulator/application tests and browser contract tests cover selected rule and presentation cases |
| TARGET_BUILD_VERIFIED | Shared rule code builds as part of host/firmware targets; build evidence does not prove the secure target has a usable trusted clock or invokes all timers |
| CURRENT_HEAD_PHYSICALLY_VERIFIED | No current-HEAD physical qualification evidence is claimed |
| NOT_YET_PHYSICALLY_QUALIFIED | Secure target rule timing, chronology, reconnect behavior and caregiver-facing vertical flow |
| PLANNED / INCOMPLETE | Trusted target time integration, complete Hub rule/timer persistence, event episode chronology, learned routines and longitudinal anomaly detection |

## Known limitations and diagnostics

The PWA, local lab, backend, shared C++ rules and secure target are not one
fully qualified production data path. Defaults are not identical across every
adapter, complete timer/routine state is not durably checkpointed on target,
and no trusted absolute time source is currently integrated into the secure
target rule-timer path.

When a rule result looks wrong, inspect event identity and kind, physical and
logical source, occurrence/receive times, uncertainty, applied configuration
version, timezone/local minute, clock trust, Home mode, sensor coverage,
incident stable key and rule-state latch. For “offline” versus “quiet,” inspect
last authenticated Hub contact independently from the last resident activity
event. For a rule that differs between simulator and target, confirm which
adapter actually invoked `RulesCore`; identical policy source does not imply
identical runtime integration.
