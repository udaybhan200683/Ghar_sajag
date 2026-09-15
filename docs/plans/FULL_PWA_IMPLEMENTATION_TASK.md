# Ghar Sajag / Parivar Saathi
# Full PWA End-to-End Implementation, Validation and Stress Qualification Specification

## Purpose

This document is the authoritative implementation specification for completing
the Ghar Sajag / Parivar Saathi PWA.

It defines the final required product behavior, backend integration,
persistence, simulation, validation, stress testing and definition of done.

Implementation will be executed in controlled phases.

Separate Phase 1, Phase 2 and Phase 3 prompts determine which portion of this
specification should be implemented during a particular Codex run.

Codex must read this document completely before starting every phase.

The phase prompt defines the immediate implementation scope.

This master specification defines the final product contract.

---

# 1. ROLE

Act as the lead:

- software architect
- senior full-stack engineer
- backend engineer
- PWA engineer
- validation engineer
- test automation engineer
- reliability/stress engineer

for the Ghar Sajag / Parivar Saathi project.

Work directly on the existing checked-out repository.

Do not create an unrelated prototype, separate demonstration project, or
parallel replacement implementation.

---

# 2. REPOSITORY

Repository root:

    ~/projects/Ghar_sajag

Active implementation directory:

    code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2

IMPORTANT:

The physical directory name still contains `v3_4_2`.

However, the v3.4.3 legacy-browser assertion alignment has already been
integrated into the checked-in source.

The implemented browser assertion is:

    /No (?:open )?incidents/i

Treat the current functional baseline as:

    Parivar Saathi v1.5.4
    PWA / BatteryAnalytics v3.4.3

Do NOT reapply the v3.4.3 patch.

Do NOT rename the active implementation directory merely for cosmetic version
alignment during this task.

Version-directory cleanup can be handled separately after implementation is
stable.

---

# 3. KNOWN-GOOD BASELINE

Before this implementation task began, the following command passed completely:

    make release-gate-final

The known-good release qualification included, among other checks:

- validation coverage
- contracts
- C++ unit tests
- Python/backend/database/logging tests
- JavaScript application tests
- base product build
- AI product build
- compile-time feature variants
- lab build
- dummy sensor streams
- functional catalog
- HTTP integration
- PWA bridge validation
- PWA API validation
- PWA frontend validation
- C++ sanitizers
- trace build
- browser E2E
- Playwright preflight
- mandatory Playwright/Chromium validation
- desktop browser scenarios
- mobile browser scenarios

The mandatory Playwright suite currently passes.

This is a valuable validated baseline.

Existing working behavior must not regress.

---

# 4. PRIMARY OBJECTIVE

Transform the current Parivar Saathi PWA into a complete, functional,
production-oriented family/caregiver application.

This is NOT:

- only a visual redesign
- only a frontend implementation
- only a mock-up
- only a prototype
- a collection of disconnected demo pages

Every implemented user-visible feature must work end-to-end through the
appropriate real application layers.

The expected architecture is conceptually:

    PWA UI
        ->
    frontend state/client
        ->
    API/backend
        ->
    domain/business logic
        ->
    persistent storage
        ->
    simulator/device abstraction/hub integration
        ->
    state/event response
        ->
    PWA update

Do not create buttons, switches, forms, menus or pages that merely look
functional.

Do not use hardcoded production-path example data to make the application
appear complete.

Simulator-backed development data is acceptable, but simulator events must
travel through the same production contracts and domain/backend paths wherever
practical.

---

# 5. PHASED EXECUTION

Implementation is intentionally divided into three controlled phases.

The separate phase prompt determines the active implementation scope.

The overall intent is:

## Phase 1

Establish the complete foundation:

- authoritative persistence
- household configuration
- family members
- device registry
- device registration/edit/remove
- device health
- battery settings
- schedules/routine configuration
- associated Settings and Devices functionality
- tests and Playwright coverage

## Phase 2

Complete user-facing product functionality:

- Reports
- Notifications
- remaining Settings
- full Home integration
- complete responsive UI
- all relevant positive/negative states
- report export
- notification behavior
- expanded simulator
- comprehensive Playwright coverage

## Phase 3

Hardening and qualification:

- stress
- load
- endurance
- resource/memory behavior
- failure injection
- long history
- event storms
- API load
- notification storms
- persistence failures
- restart/recovery
- coverage matrices
- full final qualification

Do not postpone ordinary testing until Phase 3.

Each phase must implement, test, fix and validate its own functionality.

Phase 3 is validation hardening, not the first validation pass.

---

# 6. SOURCE OF TRUTH

Use the following priority when requirements conflict:

1. current explicitly stated product requirements in this specification
2. current checked-in validated product behavior
3. current repository requirements/design documents
4. current automated tests where consistent with intended behavior
5. older UI/reference screenshots

Do not blindly restore behavior from an obsolete mock-up.

---

# 7. UI REFERENCE IMAGES

UI reference images are stored under:

    docs/ui_reference/

Inspect all available reference images before implementing major UI changes.

They are references for:

- overall design language
- navigation
- card structure
- status presentation
- typography hierarchy
- Devices page
- Reports page
- Settings page
- normal Home presentation
- negative/attention presentation

They are NOT automatically the behavioral source of truth.

## Critical Home rule

The CURRENT checked-in Home implementation is authoritative.

Morning Activity has already been removed from the primary/top overall Home
banner and moved lower in the current implementation.

DO NOT reintroduce Morning Activity into the main Home banner merely because an
older screenshot contains it.

Preserve the latest Home behavior.

---

# 8. FIRST ACTION BEFORE MODIFYING CODE

Before implementation, inspect the repository thoroughly.

Read at minimum:

- START_HERE.md
- progress.txt
- repository README
- active implementation README
- CHANGELOG
- IMPLEMENTATION_STATUS
- docs/requirements
- docs/design
- docs/progress
- current PWA source
- backend
- persistence/database implementation
- contracts
- simulator
- device abstractions
- battery analytics
- routine/schedule code
- notification-related code
- reporting-related code
- validation framework
- Makefile
- Playwright tests
- functional catalog
- existing API tests
- existing frontend tests

Build an internal gap inventory classified as:

A. fully implemented end-to-end

B. backend/domain implemented but PWA incomplete

C. PWA present but backend/persistence incomplete

D. partially implemented

E. documented requirement not yet implemented

F. hardware-dependent but host-simulatable at interface level

G. genuinely physical-HW-only qualification

H. future/out-of-scope

Do not ask the user to identify functionality that can be discovered from the
repository.

After analysis, proceed with the active implementation phase.

Do not stop merely to present a plan unless a genuinely blocking product
decision cannot be resolved from repository evidence or this specification.

---

# 9. MAIN PWA NAVIGATION

The complete PWA must contain four fully functional primary areas:

1. Home
2. Devices
3. Reports
4. Settings

All must be usable on:

- mobile
- tablet
- desktop

Navigation must remain consistent and intuitive.

---

# 10. HOME

Preserve and complete the latest checked-in Home experience.

Home must derive its state from real backend/domain state.

It must support applicable current product concepts including:

- overall household/care condition
- normal status
- attention status
- concern status
- I Am OK state
- elapsed time since I Am OK confirmation
- Call Family / assistance state where implemented
- main-door state
- door-open state
- door-close state
- time since door state
- post-door inactivity
- night activity
- abnormal night activity
- routine status
- morning routine in its current non-banner location
- device-health summary
- low battery
- critical battery
- offline device
- communication-health concern
- recent important events
- affected routine/card highlighting
- expected activity
- unexpected activity
- simulator-driven updates
- live backend state

Recent events must use human-readable descriptions.

Prefer:

    Main door opened

instead of:

    Activity observed

Prefer:

    Motion in Drawing Room

instead of generic motion.

Other examples:

    Main door closed
    Bathroom activity detected
    I am OK received
    Battery critically low
    Bathroom Node offline
    Morning routine completed

Recent event ordering must remain correct.

Status colors must carry semantic meaning and not merely decorate the UI.

---

# 11. DEVICES

The Devices tab must be a complete device-management and health interface.

Use the supplied Devices reference image as visual guidance while integrating
with real backend state.

For every Hub/Node expose appropriate data including:

- device display name
- unique device ID
- Hub/Node type
- sensor type
- assigned room/location
- online/offline state
- last-seen timestamp
- relative last-update time
- firmware version when available
- battery percentage
- charging/external-power state where applicable
- battery-health classification
- battery drain rate where available
- predicted remaining runtime
- warning/critical battery state
- communication status
- enabled/disabled status where supported
- registered capabilities

Device counts must derive from the actual registry.

---

# 12. DEVICE DETAILS

Selecting a device must show a real device-detail view.

It must use backend data rather than duplicated static examples.

Provide relevant:

- identity
- type
- capabilities
- room
- health
- communication state
- battery state
- recent device events
- configuration
- firmware/version metadata where available

---

# 13. DEVICE REGISTRATION

Implement real application-level device registration.

Required path:

    UI
      ->
    API
      ->
    validation
      ->
    unique device identity
      ->
    persistent record
      ->
    household association
      ->
    capability/type information
      ->
    room/location
      ->
    initial health/status
      ->
    simulator/device registry integration
      ->
    PWA refresh

Support simulator onboarding using the same application contracts.

Physical ESP32 provisioning may remain a hardware-specific adapter if no real
physical provisioning transport exists yet.

Do NOT fake successful physical pairing.

Design a clean seam for later physical ESP32 provisioning.

Validate:

- duplicate device ID
- malformed device ID
- unknown type
- unsupported capabilities
- missing room
- already registered device
- household mismatch
- invalid ownership
- backend failure

---

# 14. DEVICE EDITING

Support appropriate device changes such as:

- rename
- room/location assignment
- user-friendly label
- supported policy/configuration
- enabled state where valid

Changes must persist.

Reload must show saved values.

---

# 15. DEVICE REMOVAL

Implement safe removal/unregistration.

Require confirmation.

Removal must appropriately update:

- device registry
- persistence
- Devices page
- Home device-health summary
- active device count
- simulator/device association
- reporting semantics

Historical events should remain available where product semantics require
historical retention.

Prevent removal of architecturally mandatory components where applicable.

---

# 16. REPORTS

Implement fully functional reports for:

- Today / one day
- This Week / seven days
- This Month

Do not use static sample values.

All metrics must come from persisted events/domain data.

---

# 17. REPORT CONTENT

Reports should include appropriate:

- morning-routine completion
- I Am OK confirmations
- night activity
- unusual activity
- alerts
- concerns
- door activity
- room activity
- event volume
- device-offline events
- battery warnings
- critical battery events
- routine exceptions
- important events
- trends

Daily, weekly and monthly reporting should use the same authoritative reporting
domain model.

---

# 18. REPORT INSIGHTS

Insights must be rule/data derived.

Do not fabricate AI-style conclusions unsupported by data.

Examples:

    Morning routine completed 6 of 7 days.

    Night activity was higher than configured baseline.

    Main-door activity was lower than recent historical range.

    Bathroom Node generated repeated low-battery warnings.

If insufficient history exists, display that clearly.

---

# 19. REPORT DATA ARCHITECTURE

Reports must be reproducible from persistent data.

Do not rely solely on current in-memory state.

Use suitable:

- server-side filtering
- date-bound queries
- aggregation
- pagination
- indexes
- bounded detailed lists

Avoid unnecessary unbounded database growth.

---

# 20. REPORT EXPORT

If the Reports interface provides Download PDF/export, implement it
functionally.

Use the same report-domain data as the screen.

Do not maintain a separate duplicate report-calculation implementation.

Export must reflect the selected period.

Test export behavior.

---

# 21. SETTINGS

Every visible Settings destination must either:

- work end-to-end

or

- be explicitly identified as intentionally unavailable/future.

Do not leave dead menu items.

---

# 22. HOME DETAILS SETTINGS

Support applicable household information such as:

- display/home name
- timezone
- locale
- household preferences
- relevant location label
- existing required household policy information

Persist to backend storage.

Reload/backend restart should retain authoritative values where required.

Validate fields server-side.

Avoid collecting unnecessary sensitive data.

---

# 23. FAMILY MEMBERS

Implement full family-member management.

Support where applicable:

- list
- add
- edit
- deactivate/remove
- display name
- relationship/label
- role
- contact information required by notification/assistance workflows
- permissions/access

Use backend persistence.

Do not use browser localStorage as authoritative family-member storage.

Use repository requirements as source of truth for supported roles.

Likely concepts may include:

- household admin
- family member
- caregiver

but do not invent role semantics inconsistent with existing requirements.

Validate:

- duplicate identity/contact where applicable
- malformed data
- invalid permission changes
- deleting/deactivating last required admin
- unauthorized modifications

---

# 24. WI-FI & NETWORK

Implement only technically valid functionality.

The browser must not pretend to configure physical Wi-Fi if the Hub has no
physical provisioning API.

If provisioning exists, connect to it.

If it does not yet exist:

- implement configuration model
- API/interface boundary
- simulator behavior
- validation
- future hardware adapter seam

Show available real status such as:

- Hub online/offline
- network state
- last connectivity update

Never fake successful physical Wi-Fi provisioning.

---

# 25. MANAGE DEVICES SETTINGS

Manage Devices must reuse the same authoritative device domain as the Devices
tab.

Do not create a second device database.

Support applicable:

- list
- register
- edit
- rename
- room assignment
- remove
- health
- capabilities

---

# 26. NOTIFICATIONS

Implement a real notification architecture.

Preferences should support relevant product event classes such as:

- critical home concern
- I Am OK overdue
- abnormal night activity
- main-door concern
- device offline
- low battery
- critical battery
- assistance / Call Family
- other currently implemented alert classes

Required flow:

    preference UI
       ->
    persisted backend preference
       ->
    event/rule trigger
       ->
    notification service
       ->
    delivery adapter
       ->
    result/status where applicable

For PWA/browser notifications, implement appropriately where feasible:

- permission request/handling
- service-worker integration
- notification payload
- click/navigation behavior

If Web Push is appropriate, implement proper subscription/backend handling.

Do not claim SMS/email/WhatsApp delivery unless an actual provider exists.

Use delivery interfaces/adapters so future providers can be integrated cleanly.

Provide deterministic test adapters.

---

# 27. NOTIFICATION STORM PROTECTION

Implement appropriate:

- deduplication
- throttling/rate limiting
- repeated-state suppression
- escalation semantics

Do not flood family members because the same battery/offline state is reported
repeatedly.

Do not suppress genuinely distinct critical events.

---

# 28. BATTERY ALERT SETTINGS

Integrate settings with existing battery analytics.

Support applicable:

- low-battery threshold
- critical threshold
- abnormal drain alert preference
- notification behavior

Persistence must be authoritative.

Changing thresholds must actually influence backend/domain evaluation.

Do not merely change frontend colors.

Existing battery analytics behavior must not regress.

---

# 29. DEVICE SCHEDULES / ROUTINE SETTINGS

Preserve and complete existing Device Schedules behavior.

Support applicable configuration such as:

- morning routine window
- I Am OK expectation
- main-door/post-door thresholds
- night activity window
- inactivity thresholds
- routine parameters

Support household/person-level configuration where architecture allows.

Persistence must occur at backend level.

Changes must influence domain rule evaluation.

Do not implement safety/routine thresholds solely in JavaScript.

Existing validated Device Schedules Playwright behavior must continue to pass.

---

# 30. PRIVACY & SECURITY

DO NOT add a global user-visible Privacy ON/OFF switch.

That concept has explicitly been rejected.

Instead provide meaningful supported controls/information such as:

- access roles
- session/security status
- authorization
- retention information/settings where required
- logout/session management
- permissions

Do not weaken security.

---

# 31. HELP & SUPPORT

Implement a functional Help & Support experience.

At minimum consider:

- concise user guide
- explanation of statuses
- device troubleshooting
- battery troubleshooting
- network troubleshooting
- contact/support mechanism if defined
- safe diagnostic information

Do not expose secrets or unnecessarily sensitive debug information.

---

# 32. ABOUT

Display actual product/build information where practical:

- product name
- application version
- frontend version
- backend version where applicable
- build/release identifier
- terms/policy links where configured

Avoid stale manually duplicated version text.

---

# 33. AUTHORITATIVE PERSISTENCE

Backend persistence is authoritative for product state.

Do not rely solely on browser localStorage for:

- household details
- family members
- devices
- notification preferences
- battery policies
- routine schedules
- historical events
- report source data

Local browser storage may be used appropriately for:

- non-authoritative presentation preference
- session/cache
- safe offline shell metadata

Implement schema evolution/migration if required.

Existing persisted data should remain compatible where practical.

---

# 34. BACKEND / API REQUIREMENTS

Create or extend coherent APIs for applicable:

- household configuration
- family members
- devices
- device registration
- device editing
- device removal
- device health
- notification preferences
- battery policies
- routine policies
- report queries
- historical events
- application metadata

Use consistent:

- requests
- responses
- error handling
- validation

Validate server-side.

Do not trust frontend validation alone.

Keep domain rules out of thin endpoint handlers where they belong in domain
services.

---

# 35. LIVE STATE FLOW

The PWA must respond appropriately to:

- sensor activity
- main-door changes
- I Am OK
- battery changes
- device online/offline
- unusual activity
- routine completion
- routine failure
- policy changes
- newly registered device
- removed device

Use the existing polling/event/bridge mechanism unless architecture clearly
justifies changing it.

Do not introduce unnecessary infrastructure merely for novelty.

Manual page refresh should not normally be required to observe meaningful live
state changes.

---

# 36. PWA REQUIREMENTS

Maintain a real installable PWA.

Validate:

- manifest
- service worker
- responsive behavior
- mobile behavior
- desktop behavior
- offline shell
- update behavior
- cache safety

Safety/current-state information must not remain dangerously stale because of
service-worker caching.

Separate static-resource caching from live household state appropriately.

---

# 37. RESPONSIVE AND ACCESSIBLE UI

Implement quality behavior at:

- mobile widths
- tablet widths
- desktop widths

Do not simply stretch a mobile page across desktop.

Ensure:

- readable typography
- adequate touch targets
- keyboard access
- focus visibility
- semantic HTML
- ARIA where appropriate
- usable forms
- confirmation dialogs
- loading state
- empty state
- failure state
- offline state

---

# 38. COMPLETE UI FUNCTIONAL COVERAGE MATRIX

Every visible interactive element must be classified and validated.

Create and maintain a UI functionality/acceptance matrix containing:

- screen/tab
- subsection
- control/action
- backend/API involved
- persistence involved
- positive scenario
- negative scenario
- validation/error scenario
- backend-unavailable scenario where relevant
- offline scenario where relevant
- desktop Playwright coverage
- mobile Playwright coverage
- implementation status

No visible:

- button
- link
- switch
- form field
- card drill-down
- menu item
- navigation destination

may remain silently non-functional.

For every editable feature test:

1. initial backend-loaded value
2. valid edit
3. successful save
4. page reload
5. value remains
6. backend restart where persistence requires it
7. invalid input
8. backend rejection
9. backend unavailable
10. cancellation without saving
11. authorization failure where applicable
12. desktop behavior
13. mobile behavior

For destructive actions also test:

- confirmation
- cancellation
- success
- backend failure
- dependent-state update
- historical-data preservation where required

---

# 39. ERROR HANDLING

Handle gracefully:

- backend unavailable
- malformed request
- invalid form
- persistence failure
- duplicate device
- unauthorized operation
- notification permission denied
- device offline
- report unavailable
- insufficient historical data
- API timeout
- malformed simulator event

Do not silently swallow errors.

Do not show raw stack traces to ordinary users.

Failed persistence must never appear as a successful save.

---

# 40. SECURITY

Review new APIs and persistence for:

- authorization
- household isolation
- role checks
- server-side validation
- injection prevention
- safe rendering/output encoding
- secret management
- notification subscription security
- device registration trust
- session handling
- CSRF where relevant
- persistence security

Do not hardcode secrets.

---

# 41. SIMULATOR PHILOSOPHY

Everything that can reasonably be tested at software level should be simulatable
without physical ESP32 hardware.

The simulator must use the same application contracts/domain paths wherever
practical.

Do not create a special simplified behavior path solely to make tests pass.

The simulator should be capable of generating applicable:

- PIR motion
- room activity
- door open
- door close
- bathroom activity
- night activity
- I Am OK
- missed routine
- normal routine
- battery telemetry
- battery decline
- abnormal drain
- device online
- device offline
- reconnect
- device registration
- device removal
- malformed events
- duplicates
- delayed events
- out-of-order events
- communication failures

---

# 42. SOFTWARE-SIMULATABLE VS PHYSICAL-HARDWARE VALIDATION

The host simulator should validate higher-level product behavior for practically
all conditions.

Examples of HOST_SIMULATED qualification:

- door logic
- PIR event processing
- I Am OK
- routine logic
- night activity
- battery thresholds
- abnormal battery drain behavior
- offline behavior
- report aggregation
- notification triggering
- device registration
- database failures
- API failures
- event storms
- duplicate/out-of-order events
- large history
- UI state
- backend restart/recovery

However, do not falsely claim simulation proves physical behavior.

Mark genuinely physical qualification separately as HW_REQUIRED.

Examples include:

- actual ESP32 free heap
- ESP32 heap fragmentation
- FreeRTOS task-stack high-water marks
- actual ESP32 CPU timing
- real Wi-Fi interference/range
- real RF packet-loss characteristics
- real PIR false-positive/false-negative behavior
- reed-switch electrical characteristics/bounce
- physical battery discharge/runtime
- charger behavior
- brownout behavior
- actual flash wear
- hardware reboot timing

Software responses to these conditions should still be simulated where possible.

---

# 43. RESOURCE AND MEMORY ROBUSTNESS

Resource handling is a functional requirement.

Review:

- browser/PWA memory
- backend memory
- persistent storage
- reports
- event history
- notifications
- simulator
- queues
- device interfaces
- long-running sessions

Prevent:

- unbounded event lists
- unbounded queues
- unbounded logs
- unbounded report data
- duplicate event growth
- leaked event listeners
- leaked timers
- leaked subscriptions
- DOM/object leaks
- service-worker cache growth
- retained obsolete frontend data
- unlimited response buffering

Use:

- bounded collections
- pagination
- batching
- streaming where useful
- aggregation
- retention limits where defined

Changing tabs repeatedly must not create duplicate timers/listeners.

Opening/closing dialogs repeatedly must not leak resources.

---

# 44. LOW-RESOURCE BEHAVIOR

Where practical implement controlled fault-injection seams.

Do NOT deliberately consume all physical RAM of the development PC.

Simulate resource exhaustion safely.

Examples:

- queue full
- configured resource limit reached
- allocation/service failure
- worker unavailable
- maximum retained event count reached

On failure:

- do not corrupt state
- do not lose previously committed configuration
- do not infinitely retry
- do not continuously restart
- do not falsely report Home as normal
- provide diagnostic status
- allow safe recovery

Safety-related state should fail conservatively where appropriate.

---

# 45. LARGE HISTORY

Test:

- one-day history
- seven-day history
- 30-day history
- several months where practical
- extreme event density

The browser should not retrieve the entire historical database unnecessarily.

Home should retrieve only current/recent relevant information.

Reports should use bounded/aggregated server-side queries.

---

# 46. STORAGE EXHAUSTION AND DATABASE FAILURE

Do NOT fill the real developer SSD.

Use controlled:

- temporary databases
- write-failure seams
- quota simulation
- isolated test storage
- transaction failure injection

Simulate:

- database write failure
- transaction failure
- disk-full equivalent
- read failure
- corrupt record
- database unavailable
- report-export failure

Validate:

- failed save never displays success
- rollback works
- previous committed state remains valid
- user receives useful failure indication
- recovery works

---

# 47. STRESS TEST FRAMEWORK

Stress testing is mandatory.

Create deterministic synthetic/dummy workloads.

Stress framework must reuse production paths.

Do not create separate fake business logic.

---

# 48. SENSOR EVENT STORM

Support configurable load profiles such as:

SMALL:
- hundreds of events

MEDIUM:
- thousands

LARGE:
- tens/hundreds of thousands where practical

EXTENDED:
- large endurance workload outside ordinary fast validation

Generate combinations of:

- rapid PIR activity
- repeated door cycles
- simultaneous room events
- bathroom activity
- I Am OK
- battery telemetry
- online/offline transitions
- multiple devices
- duplicate events
- stale events
- delayed events
- out-of-order events
- malformed events

Verify:

- no crash
- no deadlock
- no corrupt state
- bounded memory/resource behavior
- correct event ordering semantics
- duplicate handling
- responsive API
- responsive UI
- correct Home state
- bounded recent-event display
- critical events are not silently lost

---

# 49. MULTI-DEVICE STRESS

Test at minimum applicable profiles such as:

- normal 1 Hub + 4 Nodes
- 1 Hub + 10 Nodes
- 1 Hub + 25 simulated Nodes
- architecture-defined maximum/boundary

Generate independent health/activity from all devices.

Verify no identity/state leakage across devices.

Exercise:

- registry
- health summary
- Home
- Reports
- Notifications
- persistence
- add/remove
- simultaneous updates

---

# 50. DATABASE / HISTORICAL STRESS

Create deterministic datasets representing:

- 1 day
- 7 days
- 30 days
- several months
- extended historical periods

Verify:

- Today report correctness
- Week report correctness
- Month report correctness
- query behavior
- pagination
- bounded responses
- indexes
- aggregation
- recent event bounds

Test both normal and extreme event densities.

---

# 51. MEMORY / ENDURANCE TESTING

Exercise repeated:

- Home refresh
- tab switching
- device details open/close
- Reports Today/Week/Month switching
- Settings navigation
- save/cancel
- Family Member CRUD
- Device CRUD
- simulator scenarios
- event refresh

Detect where practical:

- progressive RSS growth
- duplicate JavaScript listeners
- duplicate timers
- duplicate subscriptions
- unbounded caches
- unbounded queues
- stale retained frontend datasets

Do not use fragile exact-memory assertions.

Use reasonable trend/bound behavior.

---

# 52. API LOAD

Generate concurrent/repeated requests for applicable:

- Home state
- device lists
- device details
- device registration
- device update/removal
- event ingestion
- Settings
- report queries
- notification configuration

Validate:

- correctness
- consistency
- request limits
- bounded responses
- timeouts
- no cross-household leakage
- no state corruption

Performance numbers may be collected, but machine-dependent timing should not
become a fragile correctness criterion unless a formal requirement defines it.

---

# 53. NOTIFICATION STRESS

Simulate:

- repeated low battery
- repeated device disconnect/reconnect
- repeated unusual activity
- repeated door concerns
- multiple devices triggering same class

Verify:

- bounded notification queue
- deduplication
- appropriate throttling
- preference enforcement
- no alert storm
- critical distinct events remain deliverable

---

# 54. UI STRESS

Use Playwright where practical to exercise:

- repeated navigation
- card open/close
- report-range switching
- repeated Device CRUD
- repeated Settings editing
- events arriving while navigation occurs
- large event lists
- many devices
- backend temporary failure
- recovery/reconnect

Validate both desktop and mobile.

Ensure:

- no duplicated cards
- no duplicated events
- no stale state
- no infinite spinner
- no broken controls
- graceful error recovery

---

# 55. RESTART AND RECOVERY

Test applicable recovery after:

- backend restart
- simulator restart
- PWA reload
- interrupted settings update
- interrupted device registration
- interrupted report generation

Persistent authoritative state must remain correct.

Transient state must recover predictably.

---

# 56. BOUNDARY TESTING

For configurable values test:

- minimum
- below minimum invalid
- normal
- maximum
- above maximum invalid

Examples:

- inactivity timeout
- morning window
- night threshold
- battery thresholds
- report range
- device count
- family-member count
- string length
- API page size

Server-side validation is mandatory.

---

# 57. MALFORMED INPUT

Generate safe malformed inputs such as:

- missing field
- wrong type
- unknown enum
- excessive string length
- invalid date
- impossible battery value
- malformed device ID
- duplicate device ID
- extreme timestamp
- unknown event type
- invalid event ordering

Reject gracefully.

Never corrupt persistent state.

---

# 58. ACCELERATED SOAK TEST

Provide an automated accelerated household soak test.

Use controllable/fake logical time where architecture permits.

A 30-day household history should be simulatable in minutes rather than
requiring 30 real days.

Include combinations of:

- normal morning routine
- missed routine
- I Am OK
- door activity
- room motion
- bathroom/night activity
- battery decline
- low battery
- critical battery
- temporary offline devices
- reconnect
- unusual activity
- reports
- alerts

At completion validate:

- correct final household state
- report totals
- database consistency
- resource bounds
- notification behavior
- device health

---

# 59. STRESS METRICS

Capture useful diagnostic metrics where practical:

- events generated
- accepted
- rejected
- processing duration
- request failures
- database failures
- maximum queue depth
- memory before/after
- database size
- report generation duration
- notification count
- deduplicated notification count

Do not make hardware-dependent timing a strict host pass criterion without a
formal requirement.

---

# 60. TEST SUITE STRUCTURE

Preserve fast developer feedback.

The validation architecture should conceptually provide:

    make validation-fast

for development regression.

Maintain:

    make release-gate-final

as the normal complete release qualification.

The final release gate should include a bounded deterministic stress/resource
smoke subset.

Add an explicit substantial stress target, preferably:

    make stress-test

or a repository-appropriate equivalent.

Add a longer optional endurance target, preferably:

    make endurance-test

or equivalent.

The normal release gate must not become unnecessarily enormous.

---

# 61. FUNCTIONAL TESTING

Every new behavior must receive appropriate automated coverage.

Use the appropriate layers:

- C++ tests
- Python/backend tests
- persistence tests
- API tests
- HTTP integration
- JavaScript frontend tests
- simulator tests
- Playwright

Do not rely exclusively on browser tests for backend/domain correctness.

Do not rely exclusively on unit tests for end-to-end behavior.

---

# 62. PLAYWRIGHT COVERAGE

Add/update desktop and mobile Playwright scenarios for meaningful workflows.

At minimum eventually cover:

## Home

- normal state
- relevant negative states
- latest Home layout
- Morning Activity stays outside primary banner
- I Am OK
- Main Door
- Night Activity
- Device Health
- recent event ordering
- simulator state updates

## Devices

- device list
- detail
- register simulated device
- invalid registration
- duplicate registration
- edit/rename
- room assignment
- removal
- battery update
- offline device
- error handling

## Reports

- Today
- Week
- Month
- report-range switch
- aggregation
- no-data state
- important events
- heavy data
- report export where supported

## Settings

- Home Details save/reload
- Family Member CRUD
- device-management CRUD
- notification preferences
- battery settings
- schedule settings
- invalid inputs
- cancellation
- backend error
- authorization error where relevant

Do not weaken existing assertions simply to achieve PASS.

---

# 63. CANONICAL SCENARIOS

Existing canonical functional scenarios must remain valid.

Do not:

- delete them
- silently reduce coverage
- bypass them
- change expected semantics merely because new UI work conflicts

If a test is genuinely obsolete because a product requirement intentionally
changed, document why and replace it with equivalent or stronger validation.

---

# 64. IMPLEMENTATION STYLE

Work incrementally.

Prefer small coherent architectural changes.

Do not perform unrelated framework rewrites.

Do not migrate frontend/backend technologies merely because another framework
is fashionable.

Reuse existing architecture when sound.

Refactor when necessary for correctness/maintainability, but preserve behavior.

---

# 65. VALIDATION LOOP

During implementation:

    implement
       ->
    targeted tests
       ->
    fix
       ->
    next change

Periodically run:

    make validation-fast

At each phase checkpoint run:

    make release-gate-final

When the final release gate fails:

1. identify root cause
2. determine whether implementation or legitimately outdated test is wrong
3. fix correctly
4. rerun targeted validation
5. rerun final gate

Do not stop because a test failed.

Do not disable validation to obtain green output.

---

# 66. PRESERVATION RULES

DO NOT:

- reapply v3.4.3 patch
- remove existing working functionality
- replace backend behavior with mocks in production path
- reduce canonical coverage
- disable sanitizers
- disable browser tests
- remove simulator capability
- restore obsolete Home banner behavior
- move Morning Activity back into top overall banner
- add global Privacy ON/OFF
- create duplicate independent device databases
- create duplicate independent settings databases
- add dead UI controls
- hardcode report sample numbers
- fake successful physical ESP32 provisioning
- hardcode secrets
- commit node_modules
- commit normal build output
- commit unnecessary temporary logs
- commit transient Playwright artifacts unless repository evidence policy
  explicitly requires them

---

# 67. DOCUMENTATION

Update documentation along with implementation.

Update relevant:

- README
- CHANGELOG
- IMPLEMENTATION_STATUS
- architecture
- backend/API documentation
- persistence/data model
- simulator documentation
- PWA behavior
- validation documentation
- coverage/status documents
- open-work tracking

Clearly classify work as:

    IMPLEMENTED

    HOST_SIMULATED

    HW_REQUIRED

    FUTURE / OUT OF SCOPE

Do not mark hardware-only qualification as completed merely because host
simulation passes.

---

# 68. UI FUNCTIONAL MATRIX

Create/update a comprehensive machine-readable and human-readable matrix for
all visible application functionality.

The matrix should map:

    Requirement
      ->
    Screen
      ->
    UI action
      ->
    API
      ->
    backend/domain
      ->
    persistence
      ->
    simulator/HW interface
      ->
    test coverage

Include positive and negative cases.

---

# 69. STRESS COVERAGE MATRIX

Create a corresponding stress/failure matrix.

Include fields such as:

- Test ID
- requirement/category
- input/load profile
- positive/negative/failure mode
- expected behavior
- automated/manual
- HOST_SIMULATED/HW_REQUIRED
- component
- pass/fail

At minimum cover:

- sensor storm
- many devices
- long history
- month report under load
- notification storm
- repeated navigation
- repeated Device CRUD
- repeated Settings save
- repeated Family Member CRUD
- API load
- network failure/recovery
- database failure
- disk-full equivalent
- malformed input
- bounded queue
- low-resource injection
- backend restart
- accelerated 30-day soak

Everything reasonably testable in host simulation should be automated.

---

# 70. PHYSICAL HARDWARE QUALIFICATION

Maintain an explicit HW_REQUIRED checklist for later physical qualification.

Include applicable:

- ESP32 memory/heap
- FreeRTOS stack usage
- CPU utilization
- Wi-Fi/RF behavior
- actual sensor behavior
- battery runtime
- charger/power path
- brownout
- flash endurance
- physical reset/recovery

Host simulation should already validate higher-layer behavior for these failure
conditions before hardware testing starts.

---

# 71. PHASE COMPLETION REPORT

At the end of each implementation phase provide:

- features implemented
- files/modules substantially changed
- architecture changes
- API changes
- persistence/schema changes
- simulator changes
- tests added/updated
- Playwright coverage added
- unresolved dependencies for next phase
- HOST_SIMULATED items
- HW_REQUIRED items
- exact validation status

Do not declare a phase successful if its required release gate is failing.

---

# 72. FINAL COMPLETION REPORT

After all phases eventually provide:

1. Home functionality completed
2. Devices functionality completed
3. Reports functionality completed
4. Settings functionality completed
5. Notifications completed
6. persistence changes
7. API changes
8. simulator changes
9. functional validation coverage
10. positive/negative scenarios
11. stress testing
12. endurance testing
13. resource/memory qualification
14. Playwright desktop/mobile coverage
15. remaining HW_REQUIRED work
16. technical debt/future work
17. final validation status

Include exact results for:

    make release-gate-final

and where applicable:

    make stress-test

    make endurance-test

---

# 73. FINAL DEFINITION OF DONE

The overall project is not complete because pages merely look correct.

Completion ultimately requires:

- Home uses authoritative backend/domain state
- latest Home behavior is preserved
- Morning Activity remains outside the primary top banner
- Devices uses actual registry/health state
- device registration persists
- editing persists
- removal is safe and functional
- Home Details persists
- Family Member CRUD works
- notification settings persist
- notification settings influence real behavior
- battery policies influence backend evaluation
- schedules influence backend/domain evaluation
- Reports use actual persisted history
- Today report works
- Week report works
- Month report works
- report values are not hardcoded
- report insights are evidence-based
- report export works where required
- all Settings destinations are functional or explicitly unavailable
- backend restart does not lose required persistent configuration
- simulator supports comprehensive software scenarios
- positive cases pass
- negative cases pass
- boundary cases pass
- malformed input is handled
- backend failures are handled
- storage failures are handled
- event storms are bounded
- memory/resource growth is controlled
- notification storms are controlled
- long-history reporting works
- accelerated soak works
- desktop UX works
- mobile UX works
- accessibility is reasonable
- previous validated functionality has not regressed
- canonical scenarios remain valid
- mandatory Playwright validation passes
- final release qualification passes

The final implementation must not be declared complete while:

    make release-gate-final

is failing.

---

# 74. EXECUTION INSTRUCTION

When a phase prompt tells you to execute a phase:

1. Read this specification completely.
2. Inspect the current repository state.
3. Verify which work from earlier phases already exists.
4. Work only within the active phase scope except where dependencies require
   small prerequisite changes.
5. Implement actual code, not merely recommendations.
6. Add automated tests together with implementation.
7. Run targeted validation continuously.
8. Run the required phase release gate.
9. Fix failures.
10. Stop only at a coherent validated checkpoint.

Do not merely produce a design document.

Do not stop after gap analysis.

Implement the active phase.
