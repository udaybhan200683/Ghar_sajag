# Local simulation adapter — low-level design v1.0

Applies to code 1.5.4. Companion to documentation edition 2.0, not a replacement for the SRD/LLD volumes.

## Participants and interfaces

| Participant | File / existing dependency | Interface and responsibility |
|---|---|---|
| Browser lab | `tools/sim/web/index.html`, `lab.mjs`, `lab.css` | Sends same-origin JSON controls; renders real state; calls incident API |
| App view helpers | `app/src/features/home/index.mjs`, `incidents/index.mjs` | Existing activity/freshness labels, ownership actions and command construction |
| WSGI lab | `tools/sim/local_lab.py::WebLab` | Loopback-only HTTP; fixed asset allowlist; small request bodies; serial ownership |
| Lab composition | `local_lab.py::Lab` | Child lifecycle, fixture home/caregivers, command mapping, cloud adapter, fake notification provider, reports |
| Interactive child | `host/simulator/interactive.cpp` | Four real NodeRuntime objects, one real HubRuntime and CloudSync; synthetic sensor events and clock |
| Existing domain components | N02/N05 node runtime/store; H01/H02/H04/H05/H08 hub components; S02 rules | Journal/queue/ACK policy, reducer, current coverage lease, cloud replay |
| Existing backend | JsonApi, GharSajagService and B01–B08 services | JSON route dispatch, ingestion, deduplication, incidents, jobs and caregiver state |

Browser → lab uses real HTTP. Python → C++ uses stdin/stdout command/JSON pipes. The Python cloud adapter calls the actual WSGI JsonApi in-process with serialized JSON; it does not open a cloud TCP connection or run MQTT. Browser caregiver operations call real `/v1/...` HTTP routes. This transport substitution is intentional and defines the integration boundary.

## C++ process ownership and state

One input line is processed at a time. The child owns four NodeRuntime objects and one HubRuntime. A synthetic input calls `NodeRuntime.record`, then `next_transmission`. When the link is available, the event enters `HubRuntime.radio_callback`, then `run_state_once`. The returned application ACK reaches `NodeRuntime.acknowledge`. The original node and hub containers are reused unchanged.

`advance` changes a synthetic epoch-seconds clock in steps of up to 60 seconds. Online nodes emit heartbeat records. At the end, `HubRuntime.deadline` invokes the real routine decision. The configured interval is [1000,2000], with grace ending at 2300. Required nodes are all four; qualifying locations are kitchen/pooja. These are test inputs and do not encode final placement policy.

Commands are `reset`, `state`, `event <node index> <kind index>`, `advance <0..3600>`, `node <index> <0|1>`, `wan <0|1>`, `clock <0|1>`, `deadline`, `duplicate`, `ack <event ID>` and `ack_missing`. Python builds these from validated fields. Returned JSON contains clock, state, pending records, node retention, decision reason and cloud event envelopes. IDs/locations come from fixed fixture names; no arbitrary strings enter the C++ JSON writer.

The Base lab requires the default morning/call/offline flags. It is not the general feature-flag matrix. The existing component simulator remains responsible for alternate compile configurations.

## Cloud replay and incident mapping

When WAN is down, CloudSync returns no batch; Python does not refresh the backend heartbeat. The simulated node/hub can still handle events. When WAN resumes, Python obtains pending events from CloudSync and posts each to the existing JSON adapter. Only an application `commit` response triggers `application_commit_ack` in the child. The API's historical string `DURABLE` is labelled **DURABLE_MODEL** in the lab because the backing container is memory.

The missing-morning decision is a separate adapter-held pending flag. Python converts it to one stable `MISSING_MORNING_ACTIVITY` envelope and clears the flag after backend acceptance. This demonstrates the mapping; the boolean is not a production transactional outbox. There is one synthetic window per reset. Repeated deadline checks use the original reducer's existing incident gate.

Backend home/caregiver creation uses the shipped API and services. The local simulation no longer exposes a user-facing Privacy ON/OFF event. Internal consent/privacy enforcement remains in the product state model and is validated separately; the lab focuses on resident/caregiver P0 behavior rather than presenting privacy as a casual dashboard toggle.

## Browser workflow

The initial GET retrieves `/sim/state`; no invented activity is displayed. Buttons POST `/sim/action`, then refresh state only after success. Caregiver buttons use the existing `actionCommand` to call `/v1/homes/{home}/incidents/{id}/{action}` with a synthetic actor header. The server checks reference membership/lease rules; the page shows the confirmed result, not optimistic success. The lab catches incident conflicts as HTTP 409.

The existing app helpers are imported unchanged. All variable display data is written with textContent. The page has no service worker, cloud credentials or external scripts. The static legacy app remains unchanged so its mockup is not mistaken for a finished customer application.

No real notification is sent: explicit lab buttons call `NotificationService.due` and `provider_result` using a fake reference. Caregiver acknowledgement remains independent. Failed-job retry and actual delivery workers are absent.

## Lifecycle, memory and failure boundaries

Python starts the C++ child with argument-array execution and no shell. It owns stdin/stdout and waits at most five seconds for a command response. A timeout kills the child and requires operator restart. Ctrl+C terminates the child. Constructor failure also closes resources. The single WSGI owner avoids concurrent mutation and pipe interleaving; this is a test architecture, not backend scaling design.

Node capacity is 128, hub journal capacity 4096 for the lab. The original journal retains cloud-acknowledged entries and will fill after enough events. Browser timeline shows at most 40 records. Logs rotate at 128 KiB with two backups. Backend model data/evidence vectors are not generally bounded, so a long-running soak cannot be signed off from this version. Reset releases scenario state; it is not simulated crash recovery.

The server binds only to 127.0.0.1, checks its Host and Origin and serves an exact asset list. These controls reduce accidental exposure of the synthetic lab. Existing X-Actor-Id, event intake and in-memory authorization are not production authentication/security. Do not publish this lab or use real household data.

## Test boundaries and exit criteria

1. All existing Base/AI component suites still pass after the source version change.
2. Thirteen adapter scenarios pass with the documented expected observations.
3. Nine real HTTP tests pass, including ownership conflict, unknown actor, origin rejection and source-file exclusion.
4. A human or real browser automation must verify the page controls and layout. The included Playwright script remains unverified in this release's authoring environment because Chromium download was unavailable.
5. Reports clearly distinguish a passed assertion from a known defect. Duplicate storage test deliberately observes existing duplicate reducer evidence; it does not close G02.

Further work: real persistence adapters with crash injection, serialized production envelopes/schema validation, coverage history, deterministic scenario-file parser, notification retry worker, profile-aware runtime integration, separate hub process/device transport adapters, multi-household backend tests and real browser CI.
