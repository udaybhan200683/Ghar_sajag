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

# Caregiver Actions and Notifications

## Product mental model

Resident actions, sensor events and rule outcomes are separate records. The
timeline keeps their order and meaning. An incident can be claimed,
acknowledged or resolved by an authorized dashboard actor; a notification
service accepting a delivery request is not the same thing as a person
acknowledging the incident.

```text
Resident action / sensor observation / rule result
       |
       v
Product event and, where applicable, incident state
       |
       v
Chronological timeline
       |
       v
Family/caregiver dashboard
       |
       v
Notification job or human response (only where implemented)
```

Current evidence is strongest for local simulator/backend/PWA flows. It does
not establish a production resident button, cloud notification provider, SMS,
telephone, or emergency-response service.

## I Am OK and Call Family

### I Am OK

The event vocabulary includes `OK_PRESSED`. In the current local application
this is a resident action injected through the simulator/action flow; it is
recorded with location and time and displayed as a separate “I am OK” timeline
entry, including freshness such as “12 min ago.” Routine logic may use an OK
whose occurrence interval overlaps the configured morning window as explicit
evidence independent of PIR motion. The target Node wiring inspected for this
guide is PIR-focused and does not establish a production resident button
input.

An OK action following a check-in/morning concern can update the relevant
simulated check-in state when it matches that concern. It remains a new
chronological event: the earlier warning is not deleted or rewritten. An OK
after Call Family is newer, but the Call Family request remains open until a
caregiver resolves it. This distinction is covered explicitly by the manual
functional scenarios.

### Call Family

`CALL_FAMILY` is a distinct event and incident request. In the local host flow
it creates one Call Family incident and routes primary and backup notification
jobs when those recipients are configured. It appears in the timeline as
“Call Family requested.” Repeated delivery of the same event identity is
deduplicated by the ingest path; a genuinely new Call Family event is a new
request.

Caregiver incident actions are claim (“I’ll check”), acknowledge, and resolve.
Authorization and lease checks are repeated by the server because a UI
snapshot can be stale. Acknowledge records that an actor has taken
responsibility; it does not erase the event history. Resolve is a later
terminal incident state. A resident OK is not the same operation as caregiver
acknowledgement or resolution.

## SOS and emergency boundary

The current shared event set has Call Family, but no production SOS dispatch
or emergency-services transport is established by the inspected code. A
button/event label that might be used in a future emergency UX would only
represent a product event unless a separately qualified dispatch integration
exists. Do not describe current Call Family as contacting emergency services,
an ambulance, or a professional response service.

## Timeline and activity presentation

The timeline is chronological because actions have independent historical
meaning. For example:

```text
10:05  Call Family requested
10:08  I am OK
```

Both stay visible. The newer OK does not overwrite the earlier request. A
delayed event can be labeled “received later” while retaining its occurrence
time. The app formats age from the event occurrence timestamp where provided.

The home view uses specific text and tones:

- “Motion detected — kitchen” for a room observation.
- “Main door opened” / “Main door closed,” with duration and warning-cleared
  detail when available.
- “Main door opened during quiet hours” or “Main door kept open” for
  concerning door cases.
- “Missing morning activity” and “No activity for longer than expected” for
  rule concerns.
- “Call Family requested” and “I am OK” for explicit actions.

Color is supplementary. Text, event kind, timing, and status communicate
meaning for users who cannot distinguish color or for assistive technology.

## Family, caregiver and authorization model

The backend notification scheduler has primary and backup caregiver IDs. It
can create a primary job immediately and a backup-stage job after its default
300-second delay. Incident operations check actor access and ownership leases.
The PWA foundation also models household membership/roles and settings.

This is not a complete production identity and consent system or a fully
separated resident/family/caregiver service model. Local-lab role names and
primary/backup routing demonstrate application behavior; they do not prove
account enrollment, secure invitation, clinical responsibility, or a live
caregiver service.

## Notification channels and what “delivered” means

There are two related host software paths:

1. `NotificationService` creates idempotent primary/backup jobs for incidents.
   A caller asks for due jobs and records a provider result. The code is a
   scheduler/state model; provider I/O is a separate worker responsibility.
   `PROVIDER_ACCEPTED` means the simulated/abstract provider accepted a job,
   not that a phone rang or a person read it. Failed-job retry is not
   implemented. A human acknowledgement updates accepted jobs to
   `HUMAN_ACKED` and cancels unsent jobs.
2. The PWA foundation stores notification preferences and bounded recent
   delivery records with DELIVERED, SUPPRESSED or FAILED style states in the
   local application path. The simulator can toggle delivery availability.
   Browser permission can be requested by the UI, but a web-push subscription
   is not evidence of notification delivery.

No inspected path implements real SMS, telephone calls, an always-running
push provider, caregiver call-center, or emergency dispatch. Notification
jobs and PWA delivery records should be read as application state unless a
separately configured provider integration is present and evidenced.

## Acknowledgement, resolution and incident history

The caregiver incident UI offers actions based on state. An OPEN incident can
be claimed or acknowledged; a CLAIMED incident can be acknowledged or
resolved; an ACKNOWLEDGED incident can be resolved. A live lease held by
another actor limits the view to read-only. Server-side authorization remains
authoritative.

Acknowledgement records a human response and stops pending escalation jobs;
it does not mean the underlying event never happened. Resolution changes the
incident state to RESOLVED, while the timeline/audit history remains. A
provider acceptance is separate from human acknowledgement. A resident I Am
OK updates resident evidence; it does not substitute for caregiver
acknowledgement of Call Family.

## Privacy and settings

The shared home modes include Home, Away, Paused, Visitor and Privacy. The
ordinary PWA mode selector does not expose a generic privacy ON/OFF switch as
if privacy were a notification preference. Consent withdrawal may enforce an
internal privacy state; routine rules also suppress evidence in privacy
mode. Household policy and notification preferences are separate settings.
Do not infer consent or access controls from a notification toggle.

## Offline and reconnect behavior

- **Node offline:** Hub liveness/coverage can become unknown; that is distinct
  from a resident action or activity rule. Admitted Node events are retained
  and retried by the bounded target path, but full production end-to-end
  notification delivery is not qualified.
- **Hub offline:** Node-to-Hub delivery recovery and caregiver backend
  availability are separate links. Local PWA/backend state cannot show an
  event it has not received.
- **Backend unreachable:** a PWA action that requires server confirmation
  cannot be treated as completed just because the user clicked it. The
  browser contract keeps the visible concern until a confirmed response.
- **Caregiver browser disconnected:** the browser cannot observe newly
  committed server state until it reconnects and refreshes/polls.
- **Action attempted offline:** local UI state is not proof of server-side
  event/incident creation. Reconnect and inspect the canonical timeline and
  response before presenting completion.
- **Backend reconnect:** event ingestion and dedupe can restore server-side
  state through the configured backend path; current local simulation is not
  proof of deployed WAN behavior.

## Failure and recovery matrix

| CONDITION | EXPECTED BEHAVIOR | IMPLEMENTATION STATUS | ENGINEER DIAGNOSTIC |
|---|---|---|---|
| Duplicate I Am OK | Same event identity is deduped; separate new action stays separate | Host ingest/UI behavior | Compare event ID/key, kind and timeline rows |
| Duplicate Call Family | Duplicate delivery should not open a second incident for the same event | Host ingest idempotency and manual scenario | Inspect event dedupe key, incident key and notification job keys |
| Call Family then I Am OK | Preserve both; OK does not close request | Explicit manual functional scenario | Compare event chronology and incident state |
| Browser refresh | Re-fetch backend/PWA snapshot; do not assume an unconfirmed click committed | Browser/PWA tests; store-dependent | Inspect API result, server incident and notification records |
| Delayed event | Keep occurrence chronology and identify later receipt | PWA display supports delayed marker | Compare occurred/received timestamps and event identity |
| Repeated alert | Stable incident/event keys avoid repeated creation for same cause where implemented | Rule/notification idempotency in host paths | Check stable key, event ID and job key |
| Backend reconnect | Refresh canonical state; dedupe replayed event identities | Host path; deployed service qualification incomplete | Review ingest result, event journal and current snapshot |
| Hub restart | Nodes rejoin; runtime sessions are fresh; backend history depends on composed path | Device recovery implemented/partial; notification path not physically qualified | Inspect Hub restore, rejoin, journal, backend event and incident |
| Action while offline | Do not show server action as confirmed until response; retain event locally only where that action has a durable producer | PWA contract behavior; resident target action path incomplete | Network/API response, pending command state, timeline after reconnect |

## Source map and verification boundaries

- `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/shared/include/gs/domain.hpp` — event and incident vocabulary.
- `.../backend/ghar_sajag/ingest.py`, `.../backend/ghar_sajag/incidents.py` — event admission, dedupe and incident lifecycle.
- `.../backend/ghar_sajag/notifications.py` — scheduler, due jobs, provider result and human acknowledgement semantics.
- `.../backend/ghar_sajag/foundation.py`, `.../backend/ghar_sajag/sqlite_events.py` — PWA foundation and notification record persistence.
- `.../app/src/features/home/index.mjs` — event, freshness, tone and timeline text.
- `.../app/src/features/incidents/index.mjs` — incident actions and delivery labels.
- `.../app/src/platform/index.mjs` — browser platform boundary, including push subscription versus delivery evidence.
- `.../tools/sim/local_lab.py`, `.../tests/MANUAL_FUNCTIONAL_VALIDATION.md` — simulator actions and documented scenarios M006–M008.
- `.../tests/python/test_phase1_application.py`, `.../tests/python/test_notifications.py`, `.../tests/playwright/phase1_ui_contract.spec.ts`, `.../tests/playwright/phase2b_notifications.spec.ts` — host/application/browser behavior.

| EVIDENCE CLASS | BOUNDARY |
|---|---|
| IMPLEMENTED | Host event/timeline model, incident claim/acknowledge/resolve, notification job and local delivery-record models |
| HOST_VERIFIED | Python application/notification tests, PWA unit and Playwright/browser contracts cover selected interaction and delivery-state behavior |
| TARGET_BUILD_VERIFIED | Target builds do not verify resident controls, backend notification routes or caregiver browser delivery |
| CURRENT_HEAD_PHYSICALLY_VERIFIED | No current-HEAD resident-to-caregiver physical qualification evidence is claimed |
| NOT_YET_PHYSICALLY_QUALIFIED | Complete Node/Hub/backend/PWA interaction and actual provider/human receipt |
| PLANNED / INCOMPLETE | Production resident action hardware/input, identity and authorization flows, provider worker/retry, SMS/calling and emergency response service |

## Known limitations and diagnostics

The host notification scheduler has no provider I/O worker or retry for failed
jobs. Provider acceptance is not human receipt. The local PWA foundation,
backend incident scheduler, secure Node/Hub and deployed caregiver channel do
not yet form a single physically qualified vertical product flow. No
professional emergency-response integration is implemented by the event
label.

When a caregiver says an action disappeared or a notification did not arrive,
inspect the event ID and dedupe result, incident stable key and state, actor
authorization/lease, notification preference and home recipients, job stage
and due time, provider result/attempt count, browser API result, delivery
record, and backend reachability. Keep resident event chronology, incident
state, provider state, and human acknowledgement as separate facts.
