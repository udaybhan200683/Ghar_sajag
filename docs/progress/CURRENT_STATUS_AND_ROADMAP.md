# Current Status and Roadmap

**Status snapshot:** 2026-09-24, before the documentation-consolidation
commit. This document records repository/evidence facts and the execution
roadmap; it does not qualify work by itself.

## Documentation ownership

- `README.md`: project entry point and navigation.
- `docs/progress/PROJECT_HISTORY.md`: chronological history, including prior
  decisions, failures, and fixes.
- This document: present status and next work.
- `docs/PHASE2_ARCHITECTURE_AND_GAP_ANALYSIS.md`: detailed Phase-2 architecture,
  design decisions, and gap analysis.
- `docs/validation/MASTER_TRACEABILITY.csv`: requirement/test/evidence/status
  record.
- `docs/hw/HW_M1_4_POST_RESILIENCE_ROADMAP.md`: canonical power, battery,
  resilience, chronology, and later routine-learning roadmap.

Status labels: **COMPLETE** means the stated scope has evidence at its named
qualification level; **PARTIAL** means some layers or scenarios remain;
**OPEN** means work has not been completed; **BLOCKED_EXTRA_FIXTURE** means a
special fixture is required; **DEFERRED** means deliberately scheduled after
the current priority. Host, target-build, and physical evidence are identified
separately throughout.

## Repository and qualification checkpoint

| Field | Verified value |
|---|---|
| Current branch | `feature/hw-m1-4-hil-phase2` |
| Repository HEAD before this docs-only checkpoint | `6f49d2841e5385b60fc56adcc463d849f973d0d0` |
| Last validated product/code commit | `7bc2a3302b2e8b7792aefe453f31e78a750fe929` |
| Worktree before documentation edits | clean |
| Latest physical evidence | `evidence/hil/runs/20260924T094521.398370Z` |
| Target firmware from that evidence | `7bc2a33-hil-e3b0c44`, ESP-IDF `v6.0.3` |

The current repository HEAD is a documentation/evidence checkpoint after the
firmware commit exercised by the physical run. Documentation-only commits do
not change firmware provenance. This consolidation is a new commit on top of
published history; it does not replace or rewrite any existing commit.

## Phase 1 — CLOSED / qualified

Phase 1 remains closed and its 71 real-hardware cases remain mandatory
regression coverage. Its final qualification recorded validation-fast,
release-gate-final, USB fixture, setup, preflight, smoke, and regression as
passing; 71 real-HW cases passed with zero failures; six extra-fixture cases
were blocked as expected; unexpected resets were zero; final retained and
in-flight counts were zero; Playwright passed 86/86. The closure is recorded
in `PROJECT_HISTORY.md` and is anchored at `ae9b7dc`.

The physical scope was the qualified Hub/C3 fixture. Electrical power cuts,
controlled brownout, current/battery endurance, PIR optical stimulus, and
house-range RF required additional fixtures and were not silently counted as
software passes.

## Phase 2 — ACTIVE / NOT COMPLETE

### Complete at the stated evidence level

- **COMPLETE — host commissioning/security foundations:** unique asymmetric
  test identities, exact QR-public-identity pinning, mutual commissioning
  transcript, assignment binding, derived installation keys, runtime AEAD,
  replay rejection, and authenticated rejoin have host coverage. ESP-IDF PSA
  adapters compile for Hub and C3. This is not production credential-storage,
  target pairing, or target packet-path qualification.
- **COMPLETE — host registry/recovery foundations:** bounded registry,
  snapshot, encrypted association/registry/recovery records, explicit
  fail-closed revocation capacity, and host reopen/recovery behavior are
  covered. The target NVS adapters compile; protected key sourcing, target
  startup restore, power-cut atomicity, rollback resistance, and wear
  qualification remain open.
- **COMPLETE — target-build evidence only:** ESP-IDF PSA crypto and bounded
  NVS association, registry, Node-recovery and Hub-journal adapters have
  target-build coverage in their Hub/C3 projects. The paired Hub/C3 build
  provenance is recorded below. Compilation does not prove the commissioning,
  protected storage, durable journal, or multi-Node secure transport paths are
  active and qualified on target.
- **COMPLETE — logical multi-Node host qualification:** independent
  NodeRuntime contexts for 1, 4, 10, and 25 simulated Nodes use scheduled
  production-codec transport, authenticated host frames, Hub ingest/runtime,
  journal state, and matching ACKs. Ten-node pressure, bounded ingress and
  journal rejection, noisy-node fairness, recovery, and per-Node machine-
  readable evidence are covered. These are logical/host Nodes, not physical
  ESP-NOW peers.
- **COMPLETE — one-pair physical smoke and same-image OTA success path:** see
  evidence section below. This covers one Hub and one C3 only.

### Latest physical evidence and its limits

The run `evidence/hil/runs/20260924T094521.398370Z` records fixture, setup,
preflight, 17/17 smoke, and 3/3 same-image FOTA PASS: total 20 PASS, 0 FAIL,
and 6 `BLOCKED_EXTRA_FIXTURE`. Both target app versions were
`7bc2a33-hil-e3b0c44` on ESP-IDF v6.0.3. The Hub image SHA-256 was
`b713e7d983d5e343cea8b66581cac4dde56967b13a4b6a36e730b412446881ae`; the
standalone and Hub-embedded C3 image SHA-256 was
`a439202c8e4231bc3c29a67ee2cc42ee90c4b5c6a33c7102f7859c1fba52d10b`.

The C3 changed from `ota_0` to `ota_1`, produced fresh software-reset evidence,
reached PIR/sensing readiness, satisfied the runtime/radio/heap boot-health
gate before marking the image valid, then sent a motion event that received an
application ACK. Unexpected resets were zero; final retained and in-flight
counts were zero. The report classifies these six rows as
`BLOCKED_EXTRA_FIXTURE`: `PHYSICAL-HUB-POWER`, `PHYSICAL-C3-POWER`,
`PHYSICAL-BROWNOUT`, `PHYSICAL-CURRENT`, `PHYSICAL-PIR`, and `PHYSICAL-RF`.
They require electrical control, current instrumentation, optical stimulus, or
RF/environmental fixtures; they are not failures. The focused campaign did
not run radio-loss, offline, Hub-restart, C3-restart, or both-target-restart
campaigns; these must not be described as blocked or passed by this report.

This evidence qualifies only the same-image physical OTA and the successful
post-boot health/functional recovery path. It does **not** qualify a real
version upgrade, image authenticity/signature enforcement, rollback or
failed-boot recovery, all corruption/interruption cases, repeated A/B cycles,
physical multi-C3 RF, or electrical power/current behavior.

### Remaining Phase-2 release blockers

| Area | Status | Remaining work |
|---|---|---|
| Target commissioning and registry wiring | **OPEN** | Connect installer authorization, target asymmetric proof, target registry admission, logical assignment, and audit behavior. Host protocol tests do not establish this path. |
| Target runtime authentication / rejoin | **OPEN** | Wire AEAD, authenticated ACK/control/health, replay windows, session progression, and rejoin into actual ESP-NOW adapters. |
| Production credential and protected-key source | **OPEN** | Define manufacturing key provisioning and use supported protected storage. Development/HIL credentials are not production qualification. No irreversible eFuse operation is authorized here. |
| Association and Node recovery persistence | **PARTIAL** | Target NVS namespaces/adapters compile; connect protected key source and startup restore, then qualify corruption, interruption, rollback, and power loss. |
| Hub registry persistence | **PARTIAL** | Host encrypted snapshot and target adapter/build exist; target restore and protected key source remain open. |
| Hub event journal/dedupe | **PARTIAL** | Bounded 128-record design and host journal exist; active target path is still volatile. Integrate authenticated admission, durable commit/readback, safe reclamation, and restart dedupe. |
| Power-cut atomicity / monotonicity | **OPEN** | Qualify torn writes, corrupt state, old snapshot rollback, revocation/session floors, and safe recovery on target. |
| ESP-NOW secure peer scale | **OPEN** | Demonstrate target peer allocation/security and resource bounds at 10 Nodes; logical simulation is not peer-capacity proof. |
| 2–4 physical C3 HIL / RF fairness | **OPEN** | Test contention, collision/retry, ACK latency, fairness, reconnect, and concurrent activity with actual multiple C3 boards. |
| Deterministic fault injection | **OPEN** | Add compile-gated target-path faults and cases for loss, ACK, malformed traffic, queue/journal pressure, and FOTA faults. |
| Target recovery storms | **OPEN** | Qualify target Node/Hub restarts, outage, reconnect storms, join/leave, and cross-Node isolation using fresh evidence. |
| Performance/resource budgets | **OPEN** | Measure CPU/task load, heap/minimum heap, queues, journal occupancy, per-Node cost, latency, retries, drops, and recovery at target scales; set justified limits. |
| FOTA version/authenticity/negative paths | **PARTIAL** | Qualify real version upgrade; signed/authenticated image and board/version policy; corruption/interruption/timeout; rollback and failed boot; repeated A/B. |
| Target → backend → PWA | **OPEN / PRODUCT GAP** | `MISSING_PRODUCT_FEATURE_TARGET_VERTICAL_BRIDGE`; no production target bridge or physical end-to-end qualification exists. |
| Stress / soak | **OPEN** | Short deterministic stress, recovery and FOTA cycles, then configurable soak with resource/event accounting. |
| `hil-full` / `release-qualify` | **OPEN** | Implement non-duplicative orchestration after Phase-2 campaign ownership and gates are ready. |
| Final Phase-2 closure | **OPEN** | Close release-blocking traceability items, then repeat required Phase-1 physical regression and complete release gates. |

The full requirement status and evidence references are in
[`MASTER_TRACEABILITY.csv`](../validation/MASTER_TRACEABILITY.csv). Phase 2 is
not complete.

## Exact remaining Phase-2 sequence

1. **P2.3 target commissioning/security wiring:** complete target mutual
   authentication, registry admission, authenticated runtime, and rejoin.
   Development/HIL key sourcing may be used for qualification; production
   credential manufacturing remains a separately governed decision.
2. **P2.4 target persistence integration:** connect protected key sourcing,
   association/registry/recovery restore, and the bounded Hub event journal;
   define accurate durable-ACK behavior and qualify restart semantics.
3. **P2.5 target capacity and physical scale:** preserve host MN01/MN04/MN10/
   MN25 results; prove target single-Node compatibility, then target capacity
   and representative physical 2–4 C3 behavior. Ten logical Nodes remain
   mandatory; 25 Nodes remain simulated stress.
4. **P2.6–P2.7 FOTA:** run a real version upgrade, add image authorization and
   compatibility policy, negative/interruption tests, rollback/failed-boot
   evidence, and repeated A/B cycles.
5. **P2.8–P2.10 reliability/performance:** deterministic target-path fault
   injection, recovery storms, resource/latency budgets, and staged stress.
6. **P2.11 vertical path:** deliver a real target Hub/backend/PWA path if it
   remains in Phase-2 product scope; until then report the explicit product
   gap and do not claim vertical qualification.
7. **P2.12–P2.15 closure:** physical multi-C3 checkpoint, configurable soak,
   `hil-full`, `release-qualify`, final mandatory Phase-1 regression,
   documentation and traceability closure.

Dependencies may require interleaving target commissioning with persistence;
no host test substitutes for the relevant target proof.

## Battery and power — PLANNED next major track

Battery optimization is separate from Phase 2 and has not been implemented
here. The sensing evidence showed `sensing_live` increasing by roughly 3,000
over 60 seconds, about 50 loop iterations per second (roughly a 20 ms loop).
The previously discussed ~10-second spacing was HIL motion generation, not
the production sensing loop. The C3 is effectively awake continuously today.

The approved order is **HW-M1.4B** repeatable current baseline → **C1**
automatic light sleep → measure improvement → **C2** GPIO4 PIR event-driven
wake → first motion immediate and ordinary PIR aggregation over a measured
30–60 second window → adaptive NodeHealth and Hub-offline backoff → measure
dynamic ESP-NOW TX power → **C3** deep sleep/RTC-retained state → overnight and
endurance qualification. Keep the AM312 continuously powered; sleep the C3
CPU/radio while idle. Do not implement wake-every-10-seconds polling, batch
critical events, or write NVS for every PIR trigger. The 60-second NodeHealth
cadence is HIL/debug-oriented, not production policy. Full power architecture,
retained-state, battery telemetry, and acceptance details remain in the
[canonical HW-M1.4 roadmap](../hw/HW_M1_4_POST_RESILIENCE_ROADMAP.md) and
[baseline plan](../hw/HW_M1_4B_POWER_BASELINE_PLAN.md).

## After Phase 2: product and intelligence roadmap

### P0 product completion and real-home pilot

The P0 path is physical Node → Hub → production backend/cloud → caregiver/family
PWA. It still needs production transport/authentication and retry, absolute
time synchronization and Node-origin timestamps, household/device attribution,
event chronology, household state, offline/heartbeat visibility,
person-specific settings, caregiver dashboard completion, daily/morning
summary, door/reed integration, and real-home acceptance. Productization also
needs installer/onboarding, manufacturing and unique-device provisioning,
diagnostics, service/replacement, enclosure/BOM and power architecture,
deployment, field regression, and certification planning. See the
[P0 software gap audit](P0_SOFTWARE_GAP_AUDIT_HW_M1.md) and the
[product implementation plan](../plans/FULL_PWA_IMPLEMENTATION_TASK.md).

### P1 routine learning and longitudinal trends

Keep deterministic immediate P0 rules separate from the later
**Personalized Routine Learning, Longitudinal Baseline & Trend Detection**
workstream. P0 example: no activity by 10:00 AM triggers an immediate rule.
P1 example: morning activity gradually shifts later while room transitions
decrease and night bathroom visits increase, producing a multi-day routine
change insight rather than a single-anomaly alert.

Useful personal baselines include first morning activity, night bathroom
visits, kitchen visits/day, room transitions/day, longest daytime inactivity,
activity by time of day, and relevant room dwell/context. Likely work packages:
P1-RL1 person-specific learning; RL2 longitudinal baseline; RL3 daily
deviation; RL4 multi-day trends; RL5 multi-signal scoring; RL6 historical
trend storage/analytics; RL7 caregiver insights; RL8 synthetic 7/14/30-day
validation. Begin with explainable rules/statistics; ML is optional later.
The HW roadmap’s P0-SW-R0–R5 labels describe related chronology, baseline,
deviation, trend, and insight foundations and should be reconciled when this
work is scheduled.

### Sensors and deferred capabilities

- **P0:** PIR, door/reed, I Am OK/SOS, and deterministic routine/inactivity
  rules.
- **P1 candidate:** mmWave with PIR and routine context for richer
  rest/presence estimation.
- **Optional later:** under-mattress/bed-leg pressure sensing. Possible events
  include `BED_ENTER`, `BED_EXIT`, `TIME_IN_BED`, `NIGHT_BED_EXIT_COUNT`,
  `BED_EXIT_NO_RETURN`, and `UNUSUALLY_LONG_TIME_IN_BED`; it is not mandatory
  for P0 or routine-learning v1.
- **Deferred:** fall detection, medicine monitoring, environmental sensing,
  outdoor-camera linkage, emergency-response service, and Sarthi AI.
