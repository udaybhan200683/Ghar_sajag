## GS-172 / GS-68 spare-S3 install preflight — 2026-10-17 (evidence only)

Read-only preflight rehashed the USB-primary TEST_ONLY candidate
`c0fb82c69fe030f8b4358b7783e7c537156dfdb361b4df1a620831210d1bef65` and
verified the recorded profile/sdkconfig hashes. Installation remains NO-GO:
fixture identity is unassigned, no independently verified restore image or
installed partition match is available, the formal runner binds to current
full HEAD while the candidate records an earlier source commit, and the
registered runner does not adjudicate the diagnostic console/time commands.
No product or security requirement changes. See
[`GS-68 spare-S3 install preflight`](../exec-plans/evidence/GS68_SPARE_S3_INSTALL_PREFLIGHT_20261017.md).

# Ghar Sajag Product / Architecture Decision Log

## GS-178 / GS-40 India local-time adapter — 2026-10-19 (bounded TEST_ONLY implementation evidence)

The explicit GS-40 TEST_ONLY S3 configuration now accepts authenticated
household timezone `Asia/Kolkata` in addition to `Etc/UTC`, converting from
already trusted UTC with the fixed India UTC+05:30 offset. The adapter rejects
unknown zones, invalid time, and overflow and does not set process-global TZ or
accept an unauthenticated clock. This is a bounded test-profile implementation
detail; it does not lock worldwide timezone/DST policy, commercial configuration
semantics, or physical qualification. Existing deterministic morning/night
rules remain unchanged, and GS-104 R01–R09 remain on hold. The change is
source/test evidence only and does not increment the canonical context version.

## GS-178 isolated Hub rule receipt — 2026-10-19 (implementation evidence only)

The TEST_ONLY host vertical now uses a Hub-owned decision identity and separate
backend table/receipt to carry existing deterministic morning/night rule output
to the caregiver. Node EventKeys remain exclusive to Node events. The backend
requires verified TLS Hub identity, current Home/epoch and a committed source
event for event-derived decisions. This does not lock a target storage format,
resolve GS-D023 crash atomicity or authorize commercial credentials. The S3
source now has a bounded TEST_ONLY trusted-UTC-to-local-minute adapter; its
target behavior is not physically qualified. The composed durable Hub
rule-decision outbox is source-integrated and host-tested, with target flash
behavior still unqualified. Product P0 remains PARTIAL. See the
[GS-178 execution evidence](../exec-plans/evidence/GS178_SOFTWARE_VERTICAL_20261018.md).

## GS-68 isolated diagnostic USB console — 2026-10-17 (evidence only)

Following GS-172 comment 11323, the GS-68 TEST_ONLY S3 diagnostic now selects
USB Serial/JTAG as its primary console and uses the ESP-IDF 6.0.3
driver-backed blocking VFS for stdin. The bounded command framer preserves
partial input and rejects invalid/oversized lines without exiting the command
loop. The TEST_ONLY profile and build guards verify UART0 is not primary and
USB is not a secondary output-only console. Product defaults and production
composition are unchanged. This is software/build evidence only: the new
473,312-byte image (`c0fb82c69fe030f8a4358b7783e7c537156dfdb361b4df1a620831210d1bef65`)
supersedes the earlier build-only candidate for any future install but was not
installed. No product/security decision or context-version change is made;
silicon console, PSA RNG/RSA verification, DS signing, mTLS, GS-68 PHY and
GS-40 PHY remain NOT_RUN. See
[`GS68_USB_COMMAND_CONSOLE_20261017.md`](../exec-plans/evidence/GS68_USB_COMMAND_CONSOLE_20261017.md).

## GS-40 isolated TEST_ONLY software-key transport — 2026-10-18 (evidence only)

The existing S3 trust-provider/HTTPS seam now supports an RSA-3072 software
client key only under the explicit `GS40_TEST_ONLY_CLOUDSYNC_BUILD` macro. The
TEST_ONLY provider validates that the key matches the registered ClientAuth
certificate and still requires trusted time/current authority. Commercial
builds remain DS-only and reject TEST_ONLY identity material. Local mTLS,
issuer, NodeHealth and caregiver tests pass. A source-bound ESP-IDF 6.0.3
full-product profile build also passes with the TEST_ONLY transport option;
that image still composes `UnprovisionedS3CloudTrust` and contains no test
identity, binding or endpoint, so it proves compilation only. The target
GS-168/ownership/time material source and runtime provisioning remain absent;
no integrated source-to-caregiver or physical GS-40 result is claimed. No
product or security decision changed; context version remains
`2026-10-13.001`. See
[`GS40_TEST_ONLY_TLS_PROVIDER_20261018.md`](../exec-plans/evidence/GS40_TEST_ONLY_TLS_PROVIDER_20261018.md).

## GS-172 first-device provisioning and qualification package — 2026-10-17 (proposal/evidence only)

GS-172 comment 11296 is addressed by a versioned, non-executable first-device
SOP, a security approval matrix, a fixture-readiness checklist, and a linked
GS-68/GS-40 physical acceptance plan. The bounded recommendation is one
non-customer S3 fixture, isolated TEST_ONLY trust, one station/operator and an
independent evidence reviewer for a 50–100 Hub pilot. It reuses GS-165–GS-171
scope/contracts, the implemented GS-168 TEST_ONLY issuer, GS-109 and the
existing GS-68/GS-40 source seams; it adds no PKI, ownership model, CloudSync
transport or HIL framework. GS-167/GS-169–GS-171 remain planned/integration
scope and are not represented as completed station software.

This is a proposal, not a new LOCKED security/product decision. It does not
select an issuer vendor/custodian, key-generation or DS/eFuse procedure,
authenticated-time authority/threshold, protected rollback counter, registry
service, Secure Boot/Flash Encryption fuse order, or recovery policy. The
production app remains `UnprovisionedS3CloudTrust`; real DS/TLS/time target
provisioning is not established. No board, USB/serial, certificate, eFuse,
flash, production service or physical test was accessed or activated.
Physical readiness remains NO-GO / NOT_RUN; P0 `product_status=PARTIAL` and
the existing Hub journal-migration failure are unchanged. `CONTEXT_VERSION`
remains `2026-10-13.001`. See
[`GS172_FIRST_DEVICE_PROVISIONING_SOP_v1.0_20261017.md`](../exec-plans/evidence/GS172_FIRST_DEVICE_PROVISIONING_SOP_v1.0_20261017.md),
[`GS172_SECURITY_DECISION_APPROVAL_MATRIX_v1.0_20261017.md`](../exec-plans/evidence/GS172_SECURITY_DECISION_APPROVAL_MATRIX_v1.0_20261017.md),
[`GS172_FIRST_FIXTURE_READINESS_CHECKLIST_v1.0_20261017.md`](../exec-plans/evidence/GS172_FIRST_FIXTURE_READINESS_CHECKLIST_v1.0_20261017.md),
and [`GS172_PHYSICAL_ACCEPTANCE_PLAN_v1.0_20261017.md`](../exec-plans/evidence/GS172_PHYSICAL_ACCEPTANCE_PLAN_v1.0_20261017.md).

## GS-68 D05/D12/D06 provider-seam continuation — 2026-10-17 (evidence only)

The canonical S3 application now consumes one shared fail-closed cloud-trust
provider interface for current Hub/Home/ownership epoch, TLS identity and
authenticated Hub time. Host tests exercise TEST_ONLY credential and ownership
snapshots, concurrent revocation reads, D06 nonce-bound proof/freshness/floor
recovery, rollback detection, durable floor checkpointing, and the existing
bounded GS-40 NodeHealth-to-CloudSync publication path. The existing backend
verifier continues to enforce certificate chain/client-auth purpose, permanent
Hub identity, active Home/epoch, credential status and trusted time. ESP-TLS
system time is set only from a provider-authenticated UTC snapshot.

This is a software seam, not a production provider. No CA/issuer, factory or
eFuse/DS custody, current ownership source, signed-time verifier, durable target
floor/boot counter, approved freshness/checkpoint thresholds, or live credential
was selected or activated. The S3 product composition remains unprovisioned
and CloudSync remains fail closed. Physical qualification remains NOT_RUN;
`product_status=PARTIAL` and the existing Hub journal migration FAIL are
unchanged. No product decision or context version change is made. See the dated
GS-68/GS-40 handoff and qualification addenda for commands, image hashes and
exact owner prerequisites.

## GS-68 CloudSync physical-HIL software readiness — 2026-10-16 (evidence only)

GS-68 comment 11174 authorized completion of isolated software readiness work
on `feature/r1-gs68-gs109-mtls-feasibility`. Paired C3 diagnostic observation,
TEST_ONLY backend checks, runner-integrity registration, and S3/C3 build-only
reports are recorded in the [dated report](../exec-plans/evidence/GS68_CLOUDSYNC_PHYSICAL_HIL_AUTOMATION_20261016.md)
and [S3-first plan](../exec-plans/evidence/GS68_S3_FIRST_PHYSICAL_QUALIFICATION_PLAN_20261016.md).
This is validation evidence only; it approves no production security behavior,
fixture connection, protected identity, credential, or physical operation.
D05/D12/D06/D16 remain open and D15 remains separate for OTA. The required P0
`PARTIAL` and existing Hub migration FAIL remain gate failures;
`PHY-GS68-CLOUD-MTLS` remains release-blocking and NOT_RUN. No product decision
or context version change is made.

## GS-130 bounded regression and stale-health repair — 2026-10-14

GS-130 comment 10932 authorizes a focused implemented-feature regression pass.
An actual backend defect was reproduced: a duplicate cached received-contact
timestamp could turn an expired OFFLINE Node back ONLINE, and older telemetry
could clear a newer DEGRADED state. The existing Foundation consumer now ignores
duplicate/older explicit online observations and observations already outside
the selected Node/Hub lease. New still-fresh contact remains eligible for
recovery. This implements GS-D022/031 and the canonical truthful-health rule;
no new requirement, timeout, authentication policy or context version is added.

Six production-source scenarios cover health replay/rejoin, combined WAN/Node
outage recovery, stale backend reports, durable backlog/delivery/restart/privacy,
JSON rejection and rule toggle boundaries. They extend existing GS-116/GS-130
stages. Evidence and exact component results are recorded in
[the focused report](../exec-plans/evidence/GS130_RISK_REGRESSION_20261014.md).
Mandatory discovery also exposed six legacy rows with coverage class or
implementation state in the coverage-status field. Those statuses are corrected
to PARTIAL, and the mapping checker now rejects that metadata mix-up. Physical
acceptance and independent product gaps are unchanged.
GS-104/GS-89/GS-148 trust boundaries, Hub migration FAIL and product P0 PARTIAL
remain open. No hardware/release operation or GS-148 implementation is included.

## GS-76 Stage 2A status — 2026-10-14 (no new decision)

The isolated dashboard branch now includes a provider-neutral, nonactive human
credential/session verification boundary with injected tests. This records no
vendor choice, deployed issuer, production session, staff/Home authority,
PostgreSQL integration or route activation. The approved in-app caregiver
Approve/Deny/Revoke workflow and no-service-OTP policy below are unchanged.
See the [GS-76 Stage 2A handoff](../exec-plans/evidence/engineering_dashboard_20261014/GS76_STAGE2A_HANDOFF.md).

## GS-122/124/125 Stage 1 status — 2026-10-13 (no new decision)

The approved GS-122/10705 service workflow now has a bounded host SQLite
ticket, dispatch and in-app consent domain on the isolated dashboard branch.
The JSON default is 1800 seconds and the existing ED-D02 diagnostic policy is
composed in-process. The injected tests do not supply verified production
sessions, staff authority, PostgreSQL transactions or PWA composition. No
commercial route or synthetic-Home bypass was activated. The decisions below
and their open production/physical gates remain unchanged; see the
[Stage 1 boundary](../architecture/GS124_STAGE1_SERVICE_ACCESS_BOUNDARY_20261013.md).

## Dashboard approvals and reconciled R1 context — 2026-10-13

ED-D01 APPROVED read-only design (GS120/10660), ED-D02 APPROVED explicit Home
diagnostic permission policy (GS143/10670), and ED-D03-MIN APPROVED privacy-minimal
policy (GS65/10671). GS122/10672/10677/10705 authorize the scoped dashboard
foundation and service-access workflow in this isolated branch. A signed-in
caregiver creates and tracks a ticket for the server-derived authoritative Home,
Hub and current Nodes. Authenticated admins see the queue and may assign manually
or by atomic round-robin among active staff; an unassigned ticket is ADMIN ONLY.
Technicians see assigned-only tickets. An assigned technician's Start creates a
pending request; the caregiver reviews who/reason/ticket/Home/Hub/devices and
approves, denies or revokes in-app. There is no email/SMS OTP. Approval creates
an actor-bound, revocable READ_DIAGNOSTICS grant scoped to the exact ticket, Home,
Hub, current Nodes and ownership epoch, with a fixed, non-sliding 30-minute
default from product JSON configuration; expiry requires fresh approval. Closure,
reassignment, employee offboarding, ownership transfer, revoke and expiry deny
subsequent access and clear active diagnostic caches/polling. Admins can manage
tickets without consent. Detailed diagnostics for a real Home still require
caregiver approval; only authenticated admins on isolated synthetic/test Homes
may use the approved bypass. See [dashboard approval and scope record](../architecture/GS124_AUTHORIZATION_FOUNDATION_20261013.md).

These product decisions do not supply a production identity/session provider,
staff credential lifecycle, atomic grant persistence/revocation implementation,
trusted production Hub diagnostic source, or activated commercial routes. Those
remain implementation boundaries; the development `X-Actor-Id` adapter cannot
activate commercial diagnostics. Numerical privacy/query bounds and ED-D04–09
remain unresolved where not covered by the approved policy.

### Canonical GS-148 context — committed source `774da5c`

The canonical committed Decision Log authorizes bounded GS-148 Option A
implementation for native epoch-1 authenticated pending recovery and proven-empty
checkpoint completion using existing v1 formats, keys and durable-before-ACK.
Implementation and software evidence are pending at that committed source; D-A–D-M
remain OPEN except for the explicitly approved Option A scope.

### GS-D033 — Corrected v1 recovery in both supported commercial S3 images

**Status: LOCKED.** Both supported commercial R1 S3 application images require
corrected v1 first-event recovery before support designation, unless a later
explicit decision removes an image. No signed image pair is selected or qualified;
no self-OTA, signing/installing, slot write, physical rollback or hardware action
is authorized. The earlier design-review text requesting approval is historical
to that review; the later Option A authorization is current at the committed
canonical source. This isolated reconciliation imports no GS-148 implementation
or validation-registry change. The canonical worktree's uncommitted state is
preserved and is not represented by this committed-source summary.

Bounded implementation checkpoint: `bfcf293edaf538a68c61b654e8aee141429480ce`,
pushed with actual remote equality; 54 new cases PASS. Framework39/mapping19 and
caregiver JS23 PASS; full affected backend/PWA FAIL on existing file-backed
CloudSync/P0 fixtures in the full-/tmp environment. No production activation.
See [focused evidence](../exec-plans/evidence/engineering_dashboard_20261013/README.md).
Canonical documentation was compared at local and remote commit
`774da5c2ee8073c535df2fe56ecdbf548c16ebf0`; the dashboard context marker is
updated only after this documentation reconciliation and a passing real preflight.

Use:
- LOCKED = approved; changing requires explicit approval.
- PROVISIONAL = working direction.
- OPEN = unresolved.
- SUPERSEDED = replaced but retained for history.

## GS-114 disposable R&D fixture disposition — 2026-10-13

**APPROVED fixture disposition, not a new product requirement:** GS-114 10732
and the user's actual-execution instruction permit deliberate clean erase,
reinstallation and recommissioning of the existing C3 `14:63:93:c5:d1:58` /
S3 `7c:4f:ad:b7:2a:20` R&D pair. Earlier preservation-first instructions in
10730/10731 and corresponding dated handoffs are superseded for their temporary
experimental flash/enrollment/pending state. Preserve existing failure reports
and redacted logs. Exact connected targets/ports, safe power/wiring and each
operation still require supervising-operator confirmation. No production device,
eFuse, authentication, durability or physical acceptance rule changes. A clean
PASS would establish fresh installation only; earlier USB-reset/replay-fence
failures remain unresolved historical regressions. CONTEXT_VERSION is unchanged.
Current execution: [GS-114 report](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/EXECUTION_REPORT.md).

## GS-114 C8 physical sleep observer — 2026-10-14

**TEST_INFRA_ONLY; no product decision or requirement change.** Because the C3
native USB Serial/JTAG is silent during light sleep, a bounded optional schema-3
trace was added to authenticated non-business NodeHealth in the existing
`GS_BAT_C8_PHYSICAL_WAKE` qualification profile. The Hub prints it only in its
commissioning fixture profile. Normal C3 builds omit the recorder object and
owner-resume instrumentation. No EventKey, ACK, authentication, persistence or
sleep-policy behavior changes. Host validation is complete; source-matched
target build and physical P3 retest remain pending. `CONTEXT_VERSION` is
unchanged. See [P3 evidence](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run03_20261014/C8_P3.md).

## GS-148 Option A authorization — 2026-10-13

**APPROVED ARCHITECTURE / BOUNDED SOFTWARE IMPLEMENTED:** GS-148 comments
10688/10690 authorize only design E1/E2 native epoch-1 authenticated pending
recovery and proven-empty checkpoint completion, preserving all v1 formats,
keys and normal durable-before-ACK. The [Option A implementation evidence](../exec-plans/evidence/R1_GS148_OPTION_A_20261013.md)
records scoped host/sanitizer/target PASS and remaining aggregate failures.
This supersedes the earlier approval gates, not historical test results.
D-A–D-M remain OPEN; physical, signed-image and release qualification stay pending.

### GS-D033 — Corrected readers in both supported commercial R1 S3 images

**Status: LOCKED.** Product-owner approval: GS-145 comment 10689.
Both supported commercial R1 S3 application images SHALL contain corrected v1
first-event recovery logic. Backport before designating an older reader supported,
or obtain a later explicit decision removing it from the supported image set.
Old engineering readers' fail-closed pending-first-event limitation does not
satisfy commercial rollback availability. No concrete signed image pair is
selected or qualified; this decision authorizes no self-OTA, signing/installation,
slot writes, actual rollback or physical operations. GS-D029/032 remain in force.
Canonical context advances to `2026-10-13.001` before dependent implementation.

## GS-148 / GS-145 first-event recovery review — 2026-10-13

**HISTORICAL PREIMPLEMENTATION REVIEW:** the owner prioritizes reliability,
simplicity, affordability, maintainability and essential existing security
(GS-148 10681; GS-145 10682). The proposal below was later approved and
implemented within the bounded scope recorded above:
[the focused review](../architecture/GS148_FIRST_EVENT_RECOVERY_DESIGN_20261013.md)
recommends joining the existing authenticated checkpoint at boundary 0,
selected identity 1, exact first body and current native owner/fence state to
recover a pending transaction. Exact authenticated retry uses the existing v1
publication/checkpoint/ACK sequence. No new genesis record, key or schema is
needed for this bounded native-epoch-1 case. Standalone missing-head and
populated/corrupt authority failures remain required.

The earlier 116-byte genesis candidate is unapproved and is superseded as the
preferred solution for this specific first-event problem. Approval is still
needed for the bounded implementation and supported corrected S3 reader/image
pair. An old reader retains its existing pending-first-event fail-closed
limitation; v1 bytes alone do not prove rollback availability. S3 self-OTA and
signed-image boot health are not integrated/qualified by this design.
GS-D029/032 remain LOCKED and unchanged; D-A–D-M stay OPEN. No new LOCKED
requirement or CONTEXT_VERSION change. Physical/release acceptance remains pending.

## GS-148 architecture disposition and bounded implementation — 2026-10-12

**APPROVED ARCHITECTURE, not a new LOCKED product decision:** integrate Jira
10513–10523 through the [approval record](../architecture/GS148_ARCHITECTURE_REVIEW_DECISION_20261012.md)
and historical A–O audit. GS-152 is Done; current-source reconciliation starts at
`77e29d44c57f0851f78358049c288323c985d2e7` in the canonical R1 worktree.
The user's later authorization covers software-only P0 and bounded P1/P2:
before-identity capacity/bound checks, recovery-eligible report bank protection
and fail-closed witness/root consistency, using existing persistent formats.
See [implementation and validation evidence](../exec-plans/evidence/R1_GS148_P0_P1_P2_20261012.md).

D-A–D-M remain OPEN. Production deletion, numerical retention/overflow,
CloudSync credentials/receipt contract, partitions, new schemas, hardware and
P3–P9 execution remain excluded. Missing first v1 event publication authority
was referred for an initial-authority/rollback decision (see the 2026-10-13
design review above); retain fail-closed
recovery until that approved correction exists. Historical migration FAIL and
product P0 PARTIAL stay visible. CONTEXT_VERSION is unchanged because no new
LOCKED requirement is created here.

### GS-D001 — R1 fresh-install scope
**Status:** LOCKED  
R1 is a commercially installable fresh baseline. Arbitrary dev-era persistence migration is post-R1 unless it blocks the fresh-install path.

### GS-D002 — R1 quality rule
**Status:** LOCKED  
Reduce scope, not correctness/security/durability standards.

### GS-D003 — Hub hardware baseline
**Status:** SUPERSEDED for the Hub baseline by GS-D030; retained for history
Design R1 for the existing 4 MB Hub first. ESP32-S3-N16R8 remains future/optional unless explicitly approved.

### GS-D004 — Six Nodes share Hub storage
**Status:** LOCKED  
Storage is shared across Nodes; it is not a full independent journal per Node.

### GS-D005 — 128-event lifetime is unacceptable
**Status:** LOCKED  
Product lifetime must not be capped by a finite event count. Increasing 128 alone is not a correct fix.

### GS-D006 — Hub is not long-term caregiver database
**Status:** LOCKED  
Long-term history/analytics are backend responsibilities. Hub local storage is durability, outage buffering, current learned state, and short-term cache/history.

### GS-D007 — Connected sync is near-real-time
**Status:** LOCKED  
When connected, caregiver-relevant information is synchronized continuously/near-real-time. Do not wait for storage pressure or PWA open.

### GS-D008 — PWA is backend-first
**Status:** LOCKED  
Caregiver opens already-synchronized backend data; dashboard-open sync with Hub is not the main freshness mechanism.

### GS-D009 — Cloud outage does not disable local safety
**Status:** LOCKED  
Local sensing, alerts, durability, and routine learning continue during backend outage. PWA shows stale/offline state.

### GS-D010 — Basic AI is local + bounded
**Status:** LOCKED  
Current safety-relevant routine/baseline/trend logic runs locally using bounded state/aggregates. Backend may add richer analytics.

### GS-D011 — Raw sensor chatter is not permanent history
**Status:** LOCKED  
Repeated low-value raw transitions may be coalesced when correctness allows.

### GS-D012 — Storage pressure degrades history, not safety
**Status:** LOCKED  
Prefer reclaim/compress lower-value history while preserving correctness-critical state and continuing operation.

### GS-D013 — Exact retention values
**Status:** OPEN; partially superseded by GS-D025 for the internet-only outage design target

GS-D025 locks the 72-hour design target, not a guaranteed capacity or exact local
retention policy. Other durations/counts (including 90 d / 5k / 50k / 100k),
supported event volumes and per-class retention remain OPEN. Derive them from
the actual 4 MB budget, six-Node workload, OTA needs and crash-safety reserve.

### GS-D014 — Backend outbox policy
**Status:** OPEN  
Define bounded offline backlog and behavior for extremely long backend outages without permanent local safety failure.

### GS-D015 — Partition-layout change
**Status:** OPEN  
Do not alter partitions until byte budget and OTA impact are reviewed.

### GS-D016 — Storage/data-lifecycle design is the next R1 product blocker
**Status:** LOCKED (priority); policy details OPEN  
The shared 128-event lifetime ceiling is commercially unacceptable. The next design must derive active correctness/dedupe state, materialized reducer state, backend outbox, short history/cache, safe reclamation, offline capacity, flash wear, and OTA fit for the existing 4 MB Hub and six shared Nodes. Do not increase the event constant as the fix or repeat the already-passed fresh-install/lost-ACK physical qualification absent an invalidating change.

### GS-D017 — Storage retention and outage limits remain undecided
**Status:** OPEN; partially superseded by GS-D025/026 for approved direction

The 72-hour internet-only outage design target and eligible loss-aware ordinary
motion aggregation are now LOCKED by GS-D025/026. An unconditional offline
capacity guarantee, exact retention duration, supported event-volume envelope,
critical classification/reserve/saturation behavior, per-class byte budget,
outbox overflow policy and history-pressure threshold remain OPEN. Derive these
from the actual six-Node workload and 4 MB partition/OTA budget and record the
decision before implementing policy. Summary encoding/interval/backend contract,
motion quiet gap and progress-update frequency are not approved.

### GS-D018 — Ordinary PWA privacy toggle is not supported
**Status:** LOCKED  
The ordinary household PWA mode selector does not expose a generic Privacy ON/OFF control. Consent withdrawal may enforce an internal privacy state, and routine rules suppress passive evidence while that state applies. Privacy enforcement and notification preferences remain separate. Sources: current [P0 product requirements](P0_PRODUCT_REQUIREMENTS.md), [caregiver guide](../features/CAREGIVER_ACTIONS_AND_NOTIFICATIONS.md), and [routine rules](../features/ROUTINE_ACTIVITY_AND_INCIDENT_RULES.md); later application release notes and validation checklist record removal of the ordinary control.

### GS-D019 — BAT-C8 R1 release classification
**Status:** SUPERSEDED by GS-D020  
This prior open classification is closed by the explicit production requirement in GS-D020. It must not be treated as an outstanding scope conflict.

### GS-D020 — BAT-C8 production-critical power behavior is R1-required
**Status:** LOCKED  
BAT-C8 is an `R1_REQUIRED_FEATURE_WITH_PENDING_QUALIFICATION`. Before R1 production release, physical qualification must prove the intended production sleep entry; required GPIO/timer wake; bounded wake/resume; sensing/runtime restoration; required radio restoration; fail-awake/safe failure behavior; and no regression of required event processing. This requirement does not make final battery-life optimization or long-duration endurance characterization an R1 blocker unless R1 makes an explicit battery-life claim. BAT-C8 test cases P1–P10 remain NOT_RUN until separately authorized; those labels are test IDs, not priority levels.

**Jira traceability:** GS-114 covers implementation/focused qualification; GS-146 covers final R1 battery closure. These links do not assert either issue or the physical qualification is complete.

### GS-D021 — Storage and retrieval take priority over CPU optimization
**Status:** LOCKED

First satisfy correctness, durability, security/authentication, crash recovery, product stability, scalability and caregiver/user experience. Among qualifying designs prioritize useful information retained per flash byte, efficient deterministic retrieval, bounded RAM, and low flash write amplification/long flash lifetime, in that order. CPU-cycle efficiency is secondary. A faster host benchmark alone does not justify larger persistent records, less offline retention, weaker retrieval, durability, recovery, routine learning or caregiver behavior, or added complexity. A larger/faster representation needs strong justification and measurements showing the smaller design cannot meet realtime requirements. No product behavior, stability, scalability or UX degradation is authorized.

### GS-D022 — Missing observation is not resident inactivity
**Status:** LOCKED

The Hub routine learner and caregiver PWA must distinguish NO_ACTIVITY during adequately observed intervals from NO_OBSERVATION / SENSOR_UNAVAILABLE / HUB_UNAVAILABLE. Failed/offline sensors must not cause an inactivity conclusion. Coverage, confidence, time trust and data quality are part of current and daily routine state; positive delayed activity does not prove continuous sensor availability. Existing privacy/mode exclusions remain in force. Coverage thresholds/formulas and exact encodings remain OPEN.

### GS-D023 — Routine and daily-state failure recovery
**Status:** LOCKED

Bounded local routine learning must maintain correct current state, daily conclusions, coverage/confidence and recovery through Node power failure/reboot/rejoin, Hub power failure/reboot, radio interruption, internet/backend outages, lost backend ACK, backlog re-sync, multi-day outage, local-day rollover, delayed events, partial coverage and storage pressure. Recovery must not double-apply a logical event/baseline contribution, fabricate activity, duplicate caregiver history/daily conclusions, or lose ACK-required input. Backend retries use stable logical identities; exactly-once transport is not assumed. Daily time assignment must not fabricate trusted time. Exact retention, lateness, critical-overflow, backend effect/revision and rollback contracts remain OPEN; these decisions do not approve a partition change or production integration.

### GS-D024 — Eliminate persistent redundancy before increasing Hub storage
**Status:** LOCKED

Before increasing Hub storage allocation, storage design shall eliminate redundant persistent information and evaluate compact binary representation, shared bounded context, delta/change encoding, dictionary/reference encoding and safe semantic aggregation. Common context should be stored once where safe rather than repeated per record. Context-dependent formats must use bounded independently recoverable restart points. Storage optimization shall not weaken correctness, security, crash recovery, scalability, retrieval, routine learning or caregiver behavior.

This locks the approved design principle, not a record format, partition size,
retention horizon or backend substitution policy. GS-D021's mandatory quality
gate and CPU-secondary priority remain in force. Source strings, config/time
bindings, exact dedupe evidence and security metadata may be shared only when
their bounded lifetime and authenticated recovery are proven. The host-only
checkpoint `74c4b99` provides evidence for numeric codec/restart behavior and
conditional density; full-source serialization, target crypto/allocator,
retirement progress, derived backend effects, rollback and wear remain OPEN.
No production integration or partition change is authorized by this decision.

### GS-D025 — 72-hour internet-only outage design target
**Status:** LOCKED (design target); capacity guarantee and volume policy OPEN

**Approved:** 2026-10-08

R1 targets 72 elapsed hours of internet-only outage resilience with Hub and Nodes
powered and locally connected for the baseline scenario. Local monitoring and
routine learning continue without internet; essential safety evidence and
observation coverage remain durable. Pending information is synchronized when
the backend becomes available. This is a design target, not yet an unconditional
capacity guarantee. Supported event volume and critical saturation behavior
remain OPEN. It does not promise monitoring through power/sensor/local-radio
failure or approve a partition change. GS-D003/004/007/009/022/023 remain in force.
Only the previously undecided outage-target scope of GS-D013/017 is superseded.

### GS-D026 — Loss-aware ordinary motion aggregation
**Status:** LOCKED (product direction); representation and protocol OPEN

**Approved:** 2026-10-08

Eligible ordinary motion observations may be grouped or summarized; do not store
unnecessary repeated ordinary PIR history. Preserve information required for
routine learning, inactivity monitoring and timely safety decisions. Preserve
exact important door transitions, user actions (including Call Family and I Am
OK) and safety events. Never confuse NO_ACTIVITY with NO_OBSERVATION. Maintain
authenticated ownership, durable-before-ACK, retry, deduplication and recovery
correctness. Do not claim successful backend synchronization for data not
durably accepted by the backend. Specific summary encoding, interval, eligibility
details and backend contract remain unapproved. This refines GS-D011/024 without
approving endpoint-only substitution or weakening GS-D021/022/023.

### GS-D027 — Battery-first intelligent ESP32-C3 Nodes
**Status:** LOCKED (design requirement); new protocol and measured impact OPEN

**Approved:** 2026-10-08

R1 ESP32-C3 Nodes are battery-operated. Avoid unnecessary wake-ups, Wi-Fi
transmissions and flash writes; prefer processing triggered by meaningful sensor
observations. Do not introduce 40–120-second periodic wake-ups for activity
consolidation. Nodes may perform sensor-specific interpretation and episode
tracking; the Hub remains responsible for cross-sensor routine learning and
household decisions. Preserve GS-D020 BAT-C8 sleep/wake requirements and all
correctness/durability invariants. Any new Node protocol must prove its battery
and correctness impact before implementation. Required GPIO/timer wake,
health/retry/recovery work remains required; no new fixed progress frequency,
quiet gap, battery-life claim or qualified energy saving is established here.
Battery-first Node processing does not override GS-D021's mandatory quality gate
or authorize a competing routine-learning engine at every Node.

### GS-D028 — Sensor-specific motion, door and future bed semantics
**Status:** LOCKED (semantic boundaries); bed sensing excluded from R1

**Approved:** 2026-10-08

Ordinary PIR motion may be consolidated where safe under GS-D026. Door OPEN/CLOSE
transitions remain individually identifiable. Future bed sensors may support
occupancy START/END and duration tracking at the Node. Bed sensing is NOT being
added to R1; occupancy is not automatically equivalent to sleep or occupant
identity. This does not add bed hardware/protocol or claim that currently
unqualified door/button hardware has been installed or qualified. R1 retains
the existing 4 MB ESP32 Hub and ESP32-C3 Nodes; ESP32-S3 upgrade, final NVS size
and any hardware-scope change remain unapproved.

### GS-D029 — R1 durable-storage security scope and mandatory application rollback
**Status:** LOCKED

**Approved:** 2026-10-08, explicitly by the product owner

R1 must provide crash-consistent durable storage through ordinary power failures
and interrupted flash operations. Detect corrupted, missing or inconsistent durable
state and fail closed when trustworthy recovery is impossible. The Hub must never
silently present stale or uncertain routine state as current. Preserve authenticated
Node ownership/domain checks, durable-before-ACK, lost-ACK retry and exact deduplication,
retirement-credit correctness and every protected recovery dependency.

Deliberate restoration of an older, otherwise valid flash image is outside the R1
stored-data freshness detection guarantee. Document this limitation explicitly;
AES-GCM authenticates data but must not be represented as malicious full-flash
rollback protection. This exclusion does not permit stale fallback after ordinary
power interruption or detected corruption, or bypass uncertainty handling.

Automatic FOTA APPLICATION rollback remains MANDATORY: a failed firmware update
must normally return to the previous valid firmware through ESP-IDF OTA rollback.
Preserve signed FOTA, firmware validation and compatibility with durable storage
created by an unsuccessful upgrade. Previous valid firmware must be able to recover
that supported state correctly or fail closed; silent erase/reset or stale state
is not a compatibility solution. Application rollback and stored-data rollback
are separate concepts; the data-freshness exclusion does not waive firmware rollback.

No new security hardware, ESP32-S3 migration or flash partition change is authorized.
The existing 4 MB ESP32 Hub and ESP32-C3 Node baseline, BAT-C8 requirements and
qualification status remain unchanged. Gate C protected NVS capacity/progress,
supported event volumes and the 72-hour capacity guarantee remain unresolved.
This locks product/security scope, not a storage format, reserve, implementation
readiness or new qualification result. It resolves the previously OPEN security/
rollback scope in GS-D023/024 only to this extent; remaining technical recovery,
storage-format/FOTA compatibility, capacity and qualification gates stay open.

### GS-D030 — Approved ESP32-S3 N16R8 Hub development platform
**Status:** LOCKED (hardware direction); implementation and physical qualification pending

**Approved:** 2026-10-09, explicitly by the product owner

The R1 Hub development platform is ESP32-S3 N16R8: 16 MiB flash and 8 MiB
PSRAM. New Hub target development takes place on `feature/r1-s3-hub-bringup`
in `/home/udaybhan/projects/Ghar_sajag_r1_s3`. Retire the classic 4 MiB ESP32
as an active Hub development target; preserve its code, tests, evidence and Git
history. ESP32-C3 sensor Nodes, the six-Node model, ESP-NOW protocol, PIR
coalescing, ACK/retry/retirement and BAT-C8 requirements remain unchanged.

This explicitly supersedes GS-D003's former Hub baseline and only the 4 MiB
hardware-budget restrictions in GS-D013/016/017 and the unchanged-Hub-baseline
statements in GS-D028/029. All other locked functionality, routine/coverage,
ownership, durability, deduplication, security and FOTA contracts remain in force.
The 72-hour internet-only outage target remains LOCKED, not a capacity guarantee.
More flash/PSRAM does not qualify storage progress, runtime memory, signed FOTA,
automatic application rollback, schema compatibility or end-to-end R1 behavior.

Bring up the existing camera development board without adding camera/AI/ML or
bed features to R1. Verify chip, flash, PSRAM initialization and actual board
pinout; do not assume another board has the same GPIO mapping. Do not assign
Octal PSRAM pins GPIO35–37 to sensors. Preserve existing device firmware/data
before any flash writes; do not erase the whole flash or burn security eFuses.

An isolated S3 development partition layout with two OTA slots is authorized for
bring-up. Final commercial partitions, retention volumes, critical reserve and
saturation policy remain OPEN under GS-D015/025. Preserve signed firmware
validation and automatic application rollback; unsigned diagnostics are only
development artifacts and do not establish production FOTA qualification.
No hardware purchase, Node changes or production storage integration is implied.

## Reconciliation status — 2026-10-07

The already-qualified native fresh-install and empty-AEAD/recovery changes are
committed; no new product decision was made. The legacy journal migration host
gate also fails on the untouched starting commit and remains DEFER_POST_R1 under
GS-D001. See `docs/progress/R1_WORKTREE_RECONCILIATION_20261007.md` for attribution,
validation limits and preserved files. GS-D016's storage blocker and GS-D020's
pending physical qualification remain open work; CONTEXT_VERSION is unchanged.

## Storage architecture analysis — 2026-10-07

The proposed [R1 Hub storage/data-lifecycle ExecPlan](../exec-plans/active/R1_HUB_STORAGE_DATA_LIFECYCLE.md)
audits baseline `cd8d126ab44689cc9c6ebbbe74e6dce058d4323b` and proposes
a conditional 4 MB dual-OTA layout. **No new LOCKED decision is made.**
GS-D013/014/015/017 remain OPEN: outage/full-detail guarantees, critical overflow
and summary priorities, partition acceptability and exact numerical policy need
review. Retirement report progress/admission bounds, complete reducer limits,
new backend effect/summary completion semantics, rollback compatibility,
current signed image fit and crash/wear proofs also block implementation.
The candidate figures are analysis, not product requirements; context version
is unchanged. No firmware, partition, backend/PWA or hardware action occurred.

## Storage efficiency host core — 2026-10-07

User-authorized policy-neutral primitives are implemented outside production:
compact lossless experimental Node-event frames, bounded exact-key index,
integer statistics, record cursor and host tests/benchmarks. Documentation-only
architecture checkpoint: `94fe1a8`. The ExecPlan efficiency section challenges
the earlier budgets and prioritizes proving the existing 128 KiB partition.
Candidate108/128-byte authenticated envelopes,25 KiB engine RAM and smaller
routine/state models remain proposals. No new LOCKED policy, format activation,
partition approval or context-version change occurs. Million-event bounded host
fixtures and sanitizer/regression checks do not close production retirement,
backend, critical-overflow, crash/reclaim, image-size, wear or rollback gates.

## Maintenance

Append a new GS-Dxxx entry when a new product/architecture decision must survive future sessions. Never silently rewrite a LOCKED decision; supersede it explicitly.

## Storage-first refinement status — 2026-10-07

GS-D021/022/023 are the only new LOCKED decisions in this checkpoint. Proposed84/104-byte authenticated records and128 KiB budgets remain gated; no72-hour guarantee, critical overflow policy or partition change is approved. Current reproduced Hub image1,864,624 B fits existing slots with101,456 B margin; the old384 KiB candidate does not fit. Retirement credit/progress, coverage/time/day finalization, derived backend completion, authenticated GC and rollback remain open. Existing host regressions pass; new failure models are specified but not implemented.


## GS-150 implementation interpretation — 2026-10-10

User-approved Option A was clarified to permit bounded best-effort ACK
reception and existing exact-EventKey missed-ACK recovery, or conservative
confirmed-outage sleep. This records an implementation choice under GS-D020/027
and the existing durability/authentication requirements, not a new LOCKED
product decision. CONTEXT_VERSION remains 2026-10-09.001.

The [battery design](../features/BATTERY_LOW_POWER_AND_POWER_MANAGEMENT.md)
selects confirmed-outage-only retained sleep after the source-derived 10 s
active-contact receive budget, keeps continuous reception after successful
application MAC delivery, and preserves existing retry/rejoin/deadline rules.
No Hub ACK-arrival guarantee is introduced. The earlier ff0f6f1 requirement for
such a guarantee is superseded as an implementation blocker; its source finding
that no guaranteed application ACK latency exists remains accurate. A missed
ACK retains the event and uses authenticated same-key replay/dedupe. No wire,
persistent schema, queue size, retention guarantee or security change.

Physical BAT-C8 qualification remains required. Evidence and software limits:
[GS-150 validation](../exec-plans/evidence/R1_GS150_SOFTWARE_VALIDATION_20261010.md).


### GS-D031 — GS-40 configurable authenticated NodeHealth policy

**Status:** LOCKED — user approval in GS-40 description/comment 10359 and
10 October 2026 task. **Scope:** narrow GS-40 firmware configuration; GS-128
remains OnHold.

Default heartbeat is 300 seconds, identical day/night. Authenticated application
contact defers standalone health; local MAC success does not prove contact.
Piggyback health using existing authenticated event capabilities where supported.
One independently adjustable timing input: `heartbeat_interval_seconds`.
Node-offline detection is internally derived as `3 * interval + 10` seconds;
multiplier/grace/offline timeout are not configuration knobs. Invalid input must
not disable health. Firmware must consume validated versioned configuration at
startup; no new partition, persistence migration or runtime delivery protocol.

Mixed installations require an explicit effective per-Node profile based on
trusted identity/deployment information. Do not infer a new heartbeat from the
existing health schema. Preserve resident inactivity versus absent observation,
Hub cloud freshness versus local Node contact, and all GS-150 event/ACK/retry,
security, FOTA and sleep contracts. Physical acceptance remains outstanding.

GS-D031 implementation evidence (software scope):
[GS-40 validation](../exec-plans/evidence/R1_GS40_SOFTWARE_VALIDATION_20261010.md)
records JSON startup policy, trusted mixed-deployment profiles and the remaining
real-target acceptance/extended historical migration gate limitation. LOCKED
policy text above remains unchanged.

**Production-path audit — 2026-10-16:** The source-level authenticated
NodeHealth ingress and local HubRuntime lease exist, but no production S3
NodeHealth publication is connected through CloudSync to a backend read model
or caregiver PWA projection. Existing Foundation/backend/PWA freshness
behavior is host/simulator behavior. The backend event adapter explicitly
requires a production-provided Hub verifier and does not itself authenticate
Hub requests. Do not create a parallel Hub credential or trust contract under
GS-40: GS-109 D05/D12 identity/verifier decisions and GS-148's production
CloudSync/backend integration remain owners of that boundary. This finding
does not change GS-D031 product semantics or the 300/910 policy; it keeps the
real-target visibility criterion open until the authorized trust path is
implemented and source-to-PWA contract tests pass.

**Evidence-adapter follow-up — 2026-10-16:** GS-40's host observation validator
now requires correlated Hub/Home/ownership-epoch authority, a trusted Hub-owned
Node profile, authenticated application contact kind, and separately preserved
Hub/backend receive timestamps in observation-bundle schema v2. Focused tooling
tests cover those checks and stale-source fail-closed behavior. This is
`TEST_INFRA_ONLY`; it does not add a product endpoint, trust decision, timestamp
authority, or liveness policy. GS-109 D05/D12 and D06 plus GS-148 production
publication/read-model/PWA work remain open. No LOCKED decision or
`CONTEXT_VERSION` change is introduced.


## GS-116 engineering policy implementation note — 2026-10-11

The approved GS-116/130 permanent Definition of Done is implemented in AGENTS.md,
MASTER_VALIDATION.md and the component registry/runner. This is an engineering
process implementation, not a new product requirement or LOCKED decision;
context remains 2026-10-10.001. Software, physical qualification and release
approval remain distinct. Migration baseline evidence under GS-D001/029 is in
[R1 GS-116 evidence](../exec-plans/evidence/R1_GS116_VALIDATION_FRAMEWORK_20261010.md).
No security/storage contract, partition format or hardware authorization changes.
GS-11610405 explicitly limits development to affected components/contracts and
framework/build/sanitizer checks; full release execution is deferred to a genuine
release candidate. Lightweight composition proof never establishes release PASS.

## GS-130 regression and board-stack evidence note — 2026-10-11

Comment10409 requires independent feature/category coverage and portable C3/S3
application-stack E2E assessment. The existing registry now owns both, with
production runtime/security/durable-storage logic and host hardware boundaries.
The matrix, source inventory and physical catalogue are linked from
[MASTER_VALIDATION](../validation/MASTER_VALIDATION.md); current outcomes and
explicit gaps are in [GS-130 evidence](../exec-plans/evidence/R1_GS130_FEATURE_COVERAGE_20261011.md).
This records engineering implementation only. No LOCKED decision, product
contract, context version, wire/schema/partition or physical authorization changes.
GS-D001 deferred legacy migration remains distinct from GS-D029 current-format
ownership safety; its mandatory failing test is preserved under GS-148.

The 2026-10-11 P0 software and HIL-runner implementation records a validation
checkpoint only. Its local product stack remains PARTIAL at the existing
GS-148 authenticated durable-commit seam; the registered complete-product stage
fails closed on that status. Physical runners are opt-in and no hardware was
operated. See [dated GS-130 P0 evidence](../exec-plans/evidence/R1_GS130_P0_E2E_HIL_20261011.md).
No new product decision or GS-D identifier is introduced.

## GS-148 P2-D implementation note — 2026-10-11

The P0 host harness now composes the existing file-backed SQLite
`DurableEventCommit` and `SQLiteEventMap` for the exact CloudSync EventKey
request. This closes the harness's unconfigured-store 503 in its isolated
fixture and verifies the real commit/retry/query path. Production trust is not
decided or implemented: Hub credential verification, trusted Home/Node
enrollment-generation source/revocation, and deployment database composition
remain open. The test-only principal is ephemeral and local. No request/receipt
wire fields, ownership rules, persistence schema, or product semantics changed;
the locked requirements and context version remain unchanged. Full P0 status
remains PARTIAL and the complete-product gate remains FAIL until the production
trust/deployment contract is defined and implemented. See the P2-D evidence
section in [the existing CloudSync validation record](../exec-plans/evidence/R1_S3_P2D_CLOUD_VALIDATION_20261010.md).

### GS-148 P2-D production credential, registry and receipt mechanisms — OPEN, 2026-10-11

The product lifecycle behavior in this entry was approved and is now recorded
as GS-D032 below. This entry remains open for the unresolved technical security
mechanisms; it does not select a credential or receipt contract. Source audit found no approved production
Hub principal issuer/registration authority, Home↔Hub registry, backend
Node-enrollment-generation/revocation registry, deployable trusted middleware
or production database composition. The local commissioning registry's
generation is not present in the current CloudSync request. The existing Hub
HTTPS adapter takes an opaque deployment-supplied Authorization value and
validates the server TLS identity; neither operation defines issuance or
production principal verification. Current `COMMITTED` parsing checks the
verified TLS response and exact EventKey but does not validate an independent
signed Home/Hub/generation/payload-bound receipt.

**Proposed direction for product/security review (not authorization to
implement):** register the existing protected Hub P256 identity public key to a
Home and Hub installation through the authorized GS-109 onboarding authority;
prove possession on a canonical CloudSync request; have trusted backend
middleware resolve current Hub/Home and Node generation/revocation state before
the existing durable EventKey transaction. Approve how valid retained events
from a replaced/revoked Node are treated. Keep the current exact EventKey
receipt over verified TLS unless a separate signed receipt is explicitly
required; if required, define signer custody, key rotation and receipt fields.

Other candidate: issuer-managed short-lived device tokens, which require
approved issuer, claims, audience, storage, rotation, replay and revocation
rules and do not by themselves authorize a Node. Mutual TLS could use the
protected identity only after a certificate issuer/enrollment/revocation
lifecycle is specified. No option is selected. No bearer-token convention,
wire field, receipt signature, enrollment policy, or production credential was
invented. GS-109 owns the full Add Device workflow; this P2-D record requests
only its authoritative identity/ownership interface. See the 2026-10-11
[P2-D trust-contract evidence](../exec-plans/evidence/R1_S3_P2D_CLOUD_VALIDATION_20261010.md).

**Implementation checkpoint, 2026-10-11:** GS-148 has now added a persistent
SQLite ownership-policy registry, single active Home/Hub and Node bindings,
ownership-epoch fencing, globally monotonic Node enrollment generations, and
durable CloudSync provenance checks inside the event transaction. The S3
host serializer can include the original generation from persisted owner
evidence. These are policy/storage seams, not authenticators: verified identity
and authorized-operation inputs are supplied by the caller, the production
caller/credential issuer is absent, and the v2 serializer is not connected to
an active S3 CloudSync worker. Transfer completion remains blocked until old
Home pending-event disposition and secure local rebind are approved. This
implementation does not close any of the open mechanism choices above or
change the GS-D032 product behavior/context version.

### GS-D032 — Permanent Hub identity and household ownership lifecycle

**LOCKED product behavior, 2026-10-11 (GS-148 comment 10449; GS-109 comment
10450; GS-130 comment 10451):** each Hub has one permanent unique physical
identity and device-specific cryptographic identity, separate from its current
Home ownership. A Hub has at most one active Home binding. Initial registration,
ownership reset, transfer and re-registration require authenticated and
authorized control plus proof of possession of the exact Hub identity. A factory
reset, MAC address, serial number or QR scan alone never authorizes a claim or
transfer. Ownership/installation epochs fence stale credentials and sessions;
registration, revocation, replacement and transfer retain an audit history.

Cloud event authorization binds the authenticated Hub to its registered Home
and current ownership epoch, and each Node event to the Node's original identity
and enrollment generation. Revoked/replaced identities cannot be authorized
from current identity alone or from a client-supplied timestamp. EventKey and
occurrence time remain immutable; backend persistence precedes COMMITTED; exact
retries are idempotent and conflicting payloads fail closed.

Transfer never changes permanent Hub identity or moves old-Home events into a
new Home. Pending old-Home records remain protected. Transfer remains blocked
while pending data lacks an approved disposition or the Hub cannot safely revoke
old Home-scoped authorization and establish the new local ownership binding.
Offline status or local factory reset is not transfer authorization.

This decision locks product behavior, **not** a credential technology or
commercial issuance lifecycle. Certificate/mTLS, token issuance, reuse of the
local P256 key, proof freshness/challenge format, recovery authority, exact
COMMITTED receipt authentication, production database/middleware deployment,
and old-generation pending-event disposition remain OPEN until their secure
interfaces and authorities are defined. Do not invent these mechanisms or
credentials. GS-109 owns the full Add Device workflow; GS-148 P2-D implements
the approved CloudSync/authorization integration at available trusted seams.
Context version: `2026-10-11.001`.

## GS-114 Part 2B root-cause status — 2026-10-12 (no new locked decision)

Saved physical logs and current source were inspected without device access.
The C3 reset reason identifies a USB-UART reset class; observer-open causation
is likely but not proven. The S3 replay-fence path failed closed while handling
an authenticated retirement report, but the single runtime error message
does not identify the failing prerequisite or persistence operation. A C3
rejoin may have triggered that report; the saved trace does not prove it. Keep
the original C3/S3 state intact and do not resume physical qualification until
the S3 selected retirement snapshot/fence state is understood and the
observation path is separately assessed. No product requirement, security
contract, retry schedule, or storage format changed. This is a status/evidence
record, not a new GS-D decision; context remains `2026-10-11.001`. See
[`GS114_PART2B_ROOT_CAUSE_20261012.md`](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_PART2B_ROOT_CAUSE_20261012.md).

## GS-148 replay-fence diagnostic status — 2026-10-12 (evidence; no new locked decision)

Under GS-148 authorization comment 10499, the authenticated Node-retirement
replay-fence path gained stable sanitized failure-stage diagnostics and
production-code host fault injection. Failures still close admission and
withhold the retirement-report ACK. No ordering, persistent encoding,
ownership, event-retirement or recovery semantics changed. The diagnostics can
identify the failed interface-level stage; storage providers expose booleans,
so they cannot report an underlying physical filesystem errno. The original
S3 fixture failure remains unlocalized without a separately authorized,
state-preserving observation/deployment plan. This is an evidence update, not a
new product/storage decision; context version remains `2026-10-11.001`. See
[`GS-148 diagnostic evidence`](../exec-plans/evidence/R1_GS148_REPLAY_FENCE_DIAGNOSTIC_20261012.md).

## GS-114 C8 physical evidence update — 2026-10-14 (no new product decision)

The active run03 campaign physically passed P1 timer sleep/wake, P2 real AM312
wake and durable retirement, and P6 Hub-only reboot recovery after the RPF07
repair retest. P3 remains blocked on direct GPIO4 held-HIGH observability; P4
failed its single-stimulus criterion after three distinct qualified event keys;
P5 remains inconclusive because the first outage-recovery event was not captured
by the S3 reader. No source behavior was changed and no product/security
semantics are altered by this status update. The detailed case evidence and
limitations are in the [GS-114 execution report](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/EXECUTION_REPORT.md).
Context version remains `2026-10-13.001`; GS-114 remains In Progress.

The current installed S3 commissioning image has broad `GS_HIL_CONTROL=OFF`; the
target build rejects enabling it, so the existing broad postcommit reboot fault
cannot be used as a directional ACK-loss fixture. A distinct build-only,
default-off one-shot ACK suppression hook is now implemented in the working
tree. It is guarded to the isolated S3 commissioning profile and suppresses only
after an authenticated durable new effect, OPEN admission and positive exact-key
outbox lookup. Its 16-check host gate passes under AddressSanitizer,
UndefinedBehaviorSanitizer and ThreadSanitizer; the test image is not yet built
or installed, and physical P8 remains NOT_RUN until P7 is completed. This is
bounded HIL instrumentation, not a protocol/product decision. P9 still lacks
a longer controlled ACK hold, matched signed test and recovery images, a
supported trigger, and a known recovery procedure; no FOTA operation was
authorized or attempted. See the linked run03 P8/P9 evidence.

Since the initial host-test note, the paired C3/S3 P8 target images have built
successfully offline with ESP-IDF 6.0.3; the registered 16-check host target,
12-test S3 fixture-profile suite, and 19 feature-traceability tests pass after
correcting test-source/mapping assertions; the 99-case physical catalogue check
and expected S3 partitions/profile were verified. No image was
flashed and physical P8 remains NOT_RUN pending P7 and distinct operator
confirmation for image installation. The installed diagnostic pair and active
P7 capture are unchanged. This is a qualification/evidence update with no new
product/security decision or context-version change. See the linked run03
P8/P9 evidence and current `R1_WORK_STATE.md` checkpoint.

## GS-114 observer image installation and run04 status — 2026-10-14 (evidence; no new product decision)

The source-matched c699 C3 diagnostic application was installed app-only to
verified active `ota_0` at `0x20000`; the write hash verified and read-only
partition/otadata inspection confirmed the selected slot. Authenticated
NodeHealth schema 3 and the physical GPIO/sleep trace were subsequently
received and decoded by the Hub. The trace records one 6.793-second GPIO4 HIGH
episode, GPIO-high sleep inhibition, no sleep entry while HIGH, GPIO wake,
successful radio restoration and owner resume. These setup events were not
associated with a controlled operator stimulus and do not change P3 status.
The Hub later recorded Node session 15 offline; a controlled P3 stimulus is
still needed after the Node returns to a verified authenticated test state.
P8 remains physically NOT_RUN: the c699 S3 profile has `GS_HIL_C8_ACK_DROP=OFF`
and the available ACK-drop binary is from an earlier source checkpoint. P9
ACK/FOTA prerequisites remain blocked. No security, product, protocol,
storage or sleep-policy decision changed; context version remains
`2026-10-13.001`. See the [run04 evidence](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/run04_20261014/C8_C3_DIAGNOSTIC_INSTALL_AND_TRACE.md).

### P3 readiness recheck — 2026-10-14 07:55 UTC (evidence; no new product decision)

The operator confirmed no motion occurred during the previously requested
window. The active S3 capture produced no newer UART line after its
`FIXTURE_STATUS state=idle` response at 06:58:28.214244408 UTC. The newest
authenticated C3 health remains session 15 / health_seq 1 at
06:37:24.484466352 UTC; the Hub marked the Node offline at
06:52:38.225783443 UTC. The configured 300-second heartbeat and 910-second
offline lease establish that the fixture is not currently ready for P3. Both
USB identities remain enumerated, but this does not establish Node application
liveness. No hardware operation or new motion request was performed. P3
remains BLOCKED / NOT RUN pending safe restoration of authenticated liveness;
see run04 evidence and `R1_WORK_STATE.md`. `CONTEXT_VERSION` is unchanged.

### GS-114 P3 readiness observation — 2026-10-14 08:59 UTC (evidence only)

The operator was available for the controlled movement action, but authenticated
C3 liveness was stale. The last health was session 16 / health_seq 4 at
`08:35:48.443225859Z`; no subsequent 300 s heartbeat or decoded sleep trace
appeared. The configured 910 s lease elapsed at `08:50:58.443225859Z`. The S3
capture process remained the sole serial owner, but its log received no bytes
after `08:35:48.465006359Z`. No explicit `online=0` transition was captured,
so the Node, Hub/runtime and observer failure modes remain indistinguishable.
No motion, reset, port command, flash or storage operation occurred; the one
previously authorized C3 reset was already used. P3 remains BLOCKED / NOT RUN
pending fresh authenticated liveness, schema-3 trace and OPEN replay admission.
This records test status only; GS-D031 timing and product behavior are
unchanged and context version remains `2026-10-13.001`. See the run04 P3
handoff and consolidated report.

## GS-148 P4/P5-B1 host caller integration — 2026-10-14 (evidence; no decision)

The production CloudSync worker and HTTP transport were exercised against the
local durable backend API/ownership path by a registered host scenario. Exact
EventKey retry after committed-response loss, backend reopen, one durable
effect, and caregiver projection passed; wrong-Home and stale-epoch requests
were denied. Hub/contract/backend registered worker stages passed after fixing
a test-only historical-reader compile coupling and the stage-output matcher.
The Hub storage sanitizer and offline ESP-IDF 6.0.3 S3 diagnostic build passed.
Aggregate Hub remains FAIL for the existing migration assertion and P0
`PARTIAL`; aggregate contract/backend remain FAIL for P0 `PARTIAL`. Target
sending stays disabled pending GS-109 credential, trusted-owner and concurrency
contracts. This is validation evidence only: no product/security decision or
context version changed. Details: [GS-148 resumed execution record](../exec-plans/evidence/R1_GS148_P4P5_B1_20261014.md).

## GS-114 battery-first P1–P9 evidence reconciliation — 2026-10-15 (evidence; no new product decision)

GS-114 comment 11029 and GS-110 comment 11030 restore GS-114 non-power
P1–P9 physical evidence as the primary engineering focus. The consolidated
[execution handoff](../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/EXECUTION_REPORT.md)
records the case-by-case disposition against the current physical test plan.
P1/P2/P4/P5/P6/P7/P8 retain PASS evidence; P3's measured behavior passes but
the exact running S3 application hash is unavailable, so its catalogue remains
PARTIAL; P9 ACK-hold and signed-FOTA physical cases remain BLOCKED / NOT_RUN.
P4's initial q10–q12 extra-event trial and P5's missing per-attempt retry-key
log remain visible. P10 remains with GS-149.

The handoff also prepares separate, unexecuted P9-A authenticated ACK-hold and
P9-B signed-FOTA procedures with exact fixture, signing, slot, rollback,
observation and operation-authorization prerequisites. GS-40 actual 300-second
heartbeat / derived 910-second offline visibility remains open. GS-144's
representative workload, selected battery/reserve, measurement boundary,
reliability/latency and endurance inputs remain product-PENDING. No hardware or
software tests were run for this evidence reconciliation. No product, security,
storage, protocol or power-policy decision changed; context version remains
`2026-10-13.001`.

## GS-122 dashboard proposal checkpoint — 2026-10-12 (no new locked decision)

The campaign's explicit isolated-worktree exception permits proposed design and
inactive preparation on `feature/gs124-125-engineering-dashboard`; it does not
accept GS-120 or authorize new product/security/storage/device-control contracts.
The completed [GS-120 architecture](../architecture/GS120_ENGINEERING_DASHBOARD_ARCHITECTURE.md)
and [decision/blocker register](../exec-plans/evidence/engineering_dashboard_20261012/OPEN_DECISIONS_AND_BLOCKERS.md)
remain proposed. GS-124 production is BLOCKED_DESIGN_APPROVAL. Technician grants,
diagnostic privacy/retention, installation acceptance and target export require
their respective explicit decisions. No GS-D identifier or context-version
increment is appropriate: no new LOCKED requirement was approved. Canonical
GS-148 source is untouched; this status entry exists only on the isolated branch.


## GS-125 port-coexistence qualification — 2026-10-15 (evidence; no product decision)

The registered PWA gate now scopes `PLAYWRIGHT_PORT` and `PWA_BASE_URL` to its browser stage and automatically selects an OS-assigned loopback port when the preferred 8766 port is occupied. A per-user startup lock serializes selection/startup across worktrees. Explicit port overrides retain strict ownership checks. The Python default-port contract, alternate-port URL/command match, lock serialization and environment scoping have regression coverage.

At source `63cf8d605db08ff5c9cec8e62729a437e234fd4d`, `make validation-pwa` ran all 15 registered stages fresh: 14 PASS, one expected required P0 completeness FAIL (`product_status=PARTIAL`), physical NOT_RUN. Caregiver browser 86, Engineering `PREVIEW_ONLY` 20, Engineering host 98, Python 470 (one approved historical skip), and the six canonical C8/storage/CloudSync stages passed. The old-reader rollback limitation and fail-closed storage admission gap remain explicit; historical migration remains FAIL. No product, security, storage, protocol or authentication behavior changed; context version remains `2026-10-13.001`. Details and preserved receipts are in the [GS-125 integration qualification report](../exec-plans/evidence/integration_gs125_20261015/CONFLICT_RESOLUTION_AND_VALIDATION.md).

## 2026-10-15 — GS-125 source merge execution record

Owner authorization: GS-125 Jira comment 11058. Canonical R1 was fast-forwarded to integration commit `5f58333548739a31c388a359f4a122dad20d2ed7`; no product-semantic decision or commercial release state changed. The authorized source integration, exact validation scope, native evidence archive and remaining product blockers are recorded in `docs/product/R1_WORK_STATE.md` under “GS-125 Dashboard source integration completed — 2026-10-15”. P0 remains PARTIAL, historical migration FAIL, old-reader rollback limitation remains known, production CloudSync remains PENDING, Engineering production UI/authentication remains BLOCKED, and physical qualification remains NOT_RUN. Context version unchanged.


## GS-114 P9-A ACK-wait observer implementation — 2026-10-16 (evidence only)

Following GS-114 comment 11149, a test-profile-only bounded Node ACK-wait trace
was implemented and host-validated. It observes the existing MAC result,
exact-key authenticated Durable ACK retirement, sleep decisions and sleep/wake
path; it does not change ACK, retry, persistence, radio or sleep policy. The
trace uses the existing authenticated NodeHealth cadence, remains RAM-only, and
cannot establish reset continuity or continuous state during the 12-second
hold. The source-matched C3/S3 candidates were built but not installed. No
physical operation or P9 acceptance occurred. P9-A/P9-B remain BLOCKED / NOT_RUN
and GS-114 remains In Progress.

The focused ACK-wait test passes 36 checks normally and under ASan/UBSan.
BAT-C8, GS-150 and S3 fixture regressions pass. The registered Node/Hub/contract
stages and their separate P0 product_status=PARTIAL outcomes, plus the Hub
journal migration failure, are detailed in the GS-114 execution report
(../hw/evidence/BAT_C8_R1_QUALIFICATION/GS114_C8_EXECUTION_20261013T111655Z/EXECUTION_REPORT.md).
This is implementation and validation evidence only: no product, protocol,
security, storage or power-policy decision changed. CONTEXT_VERSION remains
2026-10-13.001.

## GS-114 P9 profile/artifact readiness — 2026-10-16 (evidence only)

The P9 C3 qualification candidate was narrowed from generic
`GS_HIL_CONTROL=ON` to a test-only profile with generic HIL controls OFF while
retaining physical GPIO4/timer light sleep, bounded authenticated ACK trace and
read-only R&D identity loading. Host-built signed C3 A/B/N/R and matched S3
P9-A ACK-hold and P9-B signed-FOTA N/B/R images now have exact source, profile,
signature, embedding and partition evidence in the GS-114 execution report and
P9 manifest. No image was installed and no physical P9 test was performed.
P9-A/P9-B remain BLOCKED / NOT_RUN pending exact Stage 2 authorization, current
board/slot/session/EventKey state, a reset-safe S3 command path, qualified
independent continuous observation and a verified recovery route. No product,
security, protocol, storage or power-policy decision changed; CONTEXT_VERSION
remains `2026-10-13.001`.

## 2026-10-16 GS-40 / GS-109 / GS-68 / GS-148 NodeHealth integration evidence (no new decision)

The additive software implementation provides a typed mTLS-derived permanent Hub/Home/installation-epoch/time-readiness context, an existing-CloudSync status publication/transport interface, an authenticated bounded latest-state backend model, and caregiver PWA projection. It preserves existing durable EventKey and ACK semantics. ESP-IDF 6.0.3 C3/S3 production-profile builds pass; host/backend/PWA and runner-integrity tests pass as recorded in [the integration evidence](../exec-plans/evidence/GS40_GS109_GS68_GS148_SOFTWARE_INTEGRATION_20261016.md).

At that checkpoint the S3 product runtime did not instantiate the status publisher. D05/D12 identity/key custody and D06 time decisions remain open. No live credentials, production endpoint, board, serial/USB or physical HIL operation was used. GS-40 physical acceptance stays NOT_RUN; the required P0 product result remains PARTIAL and the existing Hub migration gate remains FAIL. This is implementation evidence only; no locked behavior or CONTEXT_VERSION changed.

### GS-40 S3 runtime composition follow-up — 2026-10-16 (no new decision)

The canonical S3 owner now schedules bounded HubRuntime NodeHealth snapshots and a
separate network worker using the existing CloudSync authority and HTTPS transport.
Configured 300/910 and trusted legacy 60/190 and 120/310 profiles are mapped from
the installed Node policy. Current S3 authority, trusted-time and TLS identity
providers deliberately return unavailable, so commercial status transmission
remains disabled. EventKey, durable ACK, replay and retirement behavior is
unchanged. Host integration and an ESP-IDF 6.0.3 non-flashing S3 build pass; the
Hub gate still has its existing journal migration failure and the required P0
stage remains PARTIAL. See the current work-state entry and follow-up in the
GS-40 handoff and integration evidence. This records implementation status only;
D05/D12/D06 and CONTEXT_VERSION are unchanged.


## 2026-10-17 — GS-68 provider and signed-time implementation evidence (no new decision)

The GS-168 TEST_ONLY pilot issuer now adapts its active/revoked/unknown registry
state to backend CloudSync certificate lookup. The S3 trust adapter verifies
RSA-3072 ClientAuth certificate material/fingerprint and atomically revalidates
the current Home/epoch/credential generation. D06 includes a fixed-format
RSA-3072/SHA-256 signed proof verifier, CSPRNG one-use nonce, boot-generation
binding and floor/reboot/rollback checks. The TEST_ONLY time key is injected;
no trust anchor is compiled into the product. The ESP-IDF NVS store adapter
provides ordinary persistence only and is not rollback resistant or used by
product composition. `app_main` remains on `UnprovisionedS3CloudTrust`; commercial
activation stays disabled. The exact proof format, tests, production approvals
and physical NO-GO checklist are in
`docs/exec-plans/evidence/GS68_D05_D12_D06_PROVIDER_E2E_20261017.md`.

This section records implementation and TEST_ONLY evidence only. It does not
approve a CA/issuer, HSM/KMS or S3 DS key custody, production trust bundle,
authenticated-time signer/anchor/freshness policy, rollback-resistant counter,
production registry/certificate lifecycle, production endpoints or physical
operation. CONTEXT_VERSION remains `2026-10-13.001`; no locked requirement was
added or changed.

## 2026-10-17 — GS-172 / GS-68 isolated S3 signed-time diagnostic milestone (evidence only)

The existing S3 cloud-trust provider is linked into the isolated diagnostic
target only. It exposes TEST_ONLY public-key loading, PSA RNG challenge
generation, and RSA-3072/SHA-256 signed-time verification for the isolated
fixture; the host fake-verifier compatibility macro is forbidden in target
firmware. Production `UnprovisionedS3CloudTrust` composition is unchanged.
Focused host security and CloudSync tests pass, and the non-flashing ESP-IDF
6.0.3 target build passes. The candidate image was not installed. Silicon PSA
RNG, RSA verification, DS signing and mTLS have not been observed; physical
acceptance is NOT_RUN. See the dated provider evidence for exact commands,
artifact hashes and approvals still required.

This adds implementation/test evidence only. It does not approve production
trust anchors, CA/issuer custody, S3 DS/eFuse key handling, authenticated-time
authority, rollback protection, Secure Boot/Flash Encryption, production
registry, or physical operation. `CONTEXT_VERSION` remains
`2026-10-13.001`.

## 2026-10-17 — GS-172 / GS-68 spare-S3 diagnostic execution evidence (no decision)

The current TEST_ONLY S3 candidate is source-bound to cfc89a8 and passed the
non-flashing ESP-IDF 6.0.3 build. Its image SHA-256 is
`855b586d6e7a51ebad22eb45c81c170897bbb0dbfd291b921d60bca72ae15049`; the
previous c0fb82c build-only image is superseded. Host-only device enumeration
is consistent with the owner-designated spare and excluded the protected C8
inventory. A reset-capable read-only security query returned no security data
and blocked, so protection, installed partitions, and recovery remain unknown.
Installation was stopped at NO-GO. No product/security decision or
`CONTEXT_VERSION` changed. See
`docs/exec-plans/evidence/GS68_SPARE_S3_AUX_DIAGNOSTIC_20261017.md`.

## 2026-10-18 — GS-40 TEST_ONLY S3 runtime composition boundary (evidence; no new decision)

Focused host suites reconfirmed the existing TEST_ONLY provider, GS-168 issuer,
localhost mTLS NodeHealth ingest, and caregiver ONLINE/OFFLINE/UNKNOWN path.
The full product startup still selects `UnprovisionedS3CloudTrust`; there is no
target adapter for GS-168 credential/current Home-epoch refresh, no product
signed-time bootstrap transport/key configuration, and no TEST_ONLY Wi-Fi
configuration source. GS-D032 leaves these authentication/delivery mechanisms
open. The current signed-time proof verifier and CloudSync TLS client remain
fail closed until supplied through an approved boundary. No new wire protocol,
authority claim, or production mechanism is selected here. Exact findings and
validation are in
[`GS40_TEST_ONLY_RUNTIME_COMPOSITION_20261018.md`](../exec-plans/evidence/GS40_TEST_ONLY_RUNTIME_COMPOSITION_20261018.md).
No locked requirement changed; CONTEXT_VERSION remains `2026-10-13.001`.

## 2026-10-18 — GS-40 `GS40T/1` TEST_ONLY bootstrap contract (PROPOSED)

**Status: PROPOSED; no user/security approval; not LOCKED.** The existing
GS-168 issuer/registry, GS-109 ownership behavior, D06 verifier/provider and
GS-40 CloudSync interfaces do not define target material delivery, pre-TLS
signed-time transport/key supply, or isolated network configuration. Do not
implement a target trust source by choosing these mechanisms implicitly.

The recommended minimal isolated contract uses a signed, bounded,
single-session encrypted TEST_ONLY fixture envelope; the existing
`AuthenticatedHubTimeProvider` obtains its nonce/boot-generation-bound signed
proof over an untrusted UDP carrier before any certificate-time-dependent TLS;
and an authenticated TLS/mTLS refresh adapter obtains the current GS-168
credential state and current Home/ownership epoch from the existing registries.
The target fails closed on expiry, transfer, revocation, bad time, stale
authority, network/config failure and test/commercial profile crossover. A
controlled USB/PnP fixture is the TEST_ONLY config-delivery trust point; the
proposal does not claim device attestation, hardware key custody or malicious
flash rollback protection. Proposed TEST_ONLY time proof response age is 30 s,
maximum statement lifetime 300 s, floor checkpoint 60 s, authority lease 60 s
and refresh interval 15 s. These values and interfaces require approval as one
bounded TEST_ONLY contract. They do not change GS-D032 or authorize physical or
production operations.

Full contract, wire fields, trust boundaries, alternatives, threats, failure
behavior and acceptance tests:
[`GS40_TEST_ONLY_BOOTSTRAP_DECISION_PROPOSAL_20261018.md`](../exec-plans/evidence/GS40_TEST_ONLY_BOOTSTRAP_DECISION_PROPOSAL_20261018.md).
Until approved, S3 product startup remains `UnprovisionedS3CloudTrust`,
commercial profile remains fail-closed, and no runtime code or build artifact
is claimed integrated. `CONTEXT_VERSION` remains `2026-10-13.001` because no
locked decision changed.

### Bounded implementation note — 2026-10-18

Under a later task-specific delegation for isolated TEST_ONLY engineering, a
guarded implementation of the proposed envelope, authenticated-time bootstrap,
current-authority lease verifier, and S3 startup composition was added and
compiled. This does not convert `GS40T/1` from PROPOSED to approved or LOCKED,
does not approve any commercial trust mechanism, and does not establish a
working backend authority/time fixture or a complete S3-to-caregiver E2E. The
commercial composition continues to use `UnprovisionedS3CloudTrust`. See the
dated execution evidence for exact code and limits. `CONTEXT_VERSION` remains
unchanged.


### GS-178 TEST_ONLY implementation continuation — 2026-10-18

The later delegated software scope now supplies the G40E sender, signed-time
service and certificate-authenticated current-authority handler in an isolated
local environment. Actual shared S3 trust/HTTPS composition is exercised by a
production-component host vertical to durable backend and caregiver UI. The
engineering refinements (receipt-time lease validation, conservative whole-second
lease interval, isolated destinations, immutable retry receipt metadata and
non-regressing live chronology) are recorded in
[GS178 software evidence](../exec-plans/evidence/GS178_SOFTWARE_VERTICAL_20261018.md).
These are bounded TEST_ONLY/implementation corrections; GS40T/1 remains PROPOSED
for commercial approval, GS-D031/D032 remain LOCKED and unchanged, and GS-104
R01–R09 remain on hold. No physical or release acceptance is inferred.
