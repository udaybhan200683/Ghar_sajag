# Phase 2 Architecture and Gap Analysis

**Document status:** ARCHITECTURE BASELINE with incremental Phase-2 implementation notes
**Analysis baseline:** `ae9b7dc` — *Add unattended WSL-first Phase-1 HIL qualification*
**Phase-1 status:** CLOSED / QUALIFIED
**Phase-2 implementation status:** P2.1/P2.2 host foundation and P2.3 host registry/commissioning foundations; production target commissioning remains absent

## 1. PURPOSE / SCOPE

This document records the repository and target-firmware analysis that starts
Phase 2 of Ghar Sajag / Parivar Saathi HIL qualification. It is based on the
Phase-1 qualified baseline `ae9b7dc`. It describes current facts, proposed
architecture, product gaps, test-infrastructure gaps and qualification order.

No Phase-2 product or runtime behavior has been implemented by this baseline.
No Phase-2 real-hardware PASS is claimed. The 71 Phase-1 real-HW cases remain
mandatory regression coverage and must continue to run through the existing
WSL-first supervisor.

Status labels used below are explicit:

- `CONFIRMED_REQUIREMENT` — required product or qualification behavior.
- `CURRENT_IMPLEMENTATION_FACT` — observed in the repository or built target.
- `PROPOSED_ARCHITECTURE` — recommended direction, not implemented.
- `OPEN_DECISION` — requires an explicit product or security decision.
- `PRODUCT_GAP` — product behavior is absent or insufficient.
- `TEST_INFRA_GAP` — qualification support is absent.

## 2. CURRENT IMPLEMENTATION

`NodeRuntime` owns one logical node ID, one boot session, a local sequence,
bounded retained business events and a retry queue. The C3 allocates a
monotonically increasing boot session in NVS. The target composition still
uses compile-time Node ID, room, Hub MAC and Node MAC values.

`HubRuntime` has a source-ID to session map, a bounded ingest queue and an
in-memory journal. The target Hub adapter accepts one qualified C3 MAC and one
logical Node identity, authorizes a higher session from that source, and then
processes the frame through the normal codec, ingest, journal and rules path.
This is session filtering and routing; it is not a cryptographic commissioning
protocol.

The target queue boundaries are currently:

| Target structure | Current capacity | Status |
|---|---:|---|
| Hub data callback queue | 16 frames | `CURRENT_IMPLEMENTATION_FACT` |
| Hub FOTA/control queue | 8 frames | `CURRENT_IMPLEMENTATION_FACT` |
| Hub health queue | 1 latest snapshot | `CURRENT_IMPLEMENTATION_FACT` |
| HubRuntime ingest queue | 32 events | `CURRENT_IMPLEMENTATION_FACT` |
| HubRuntime journal | 1,024 records | volatile in-memory target composition |
| C3 ACK queue | 8 frames | `CURRENT_IMPLEMENTATION_FACT` |
| C3 FOTA/control queue | 8 frames | `CURRENT_IMPLEMENTATION_FACT` |
| C3 send-result queue | 4 results | `CURRENT_IMPLEMENTATION_FACT` |
| NodeRuntime retained store | 32 events by default | volatile in-memory runtime object |
| NodeRuntime retry queue | 32 events by default | volatile in-memory runtime object |

The host interactive lab constructs six independent `NodeRuntime` objects and
one `HubRuntime`, but delivery is direct, sequential and host-only. It does
not model ten physical peers, target callback scheduling, RF contention,
commissioning, target persistence or per-node target resource accounting.
Backend stress profiles containing `extra_devices` are backend records only;
they are not evidence of ten-node NodeRuntime / transport / HubRuntime /
ESP-NOW behavior.

### Persistence and acknowledgements

The C3 boot-session counter is persisted in NVS. Node retained business events,
in-flight state, Hub authorization, Hub dedupe state and Hub journal records are
not persisted across a power loss or target restart. The Hub journal does not
compact records after cloud acknowledgement.

The current “durable Hub ACK” means that the event was committed to the
volatile in-memory Hub journal. It does not mean power-loss durability.

### Security and target peer state

The current target adds one product ESP-NOW peer and sets `encrypt=false`.
There is no factory credential, Home identity, pairing transaction, credential
rotation or authenticated Hub/Node handshake. MAC filtering and logical ID
filtering are routing/admission checks, not proof of possession of a device
credential.

## 3. NODE COMMISSIONING CURRENT STATE

| Capability | Classification | Current finding |
|---|---|---|
| Immutable physical identity | `PARTIALLY_IMPLEMENTED` | Target MAC is checked; no protected product identity record. |
| Factory identity / manufacturing credential | `MISSING_PRODUCT_FEATURE` | No per-device credential provisioning. |
| Hub identity | `PARTIALLY_IMPLEMENTED` | Hub MAC is compiled into the C3; no authenticated Hub credential. |
| Home / installation identity | `MISSING_PRODUCT_FEATURE` | No Home binding in target association. |
| Discovery | `MISSING_PRODUCT_FEATURE` | Only the known qualified peer is accepted. |
| Bounded pairing window | `MISSING_PRODUCT_FEATURE` | No commissioning state or timeout. |
| Authentication / authorization | `PARTIALLY_IMPLEMENTED` | MAC, logical ID and session checks exist; cryptographic authorization does not. |
| ESP-NOW peer creation | `PARTIALLY_IMPLEMENTED` | One startup peer is created; no enrollment lifecycle. |
| Session establishment | `PARTIALLY_IMPLEMENTED` | NVS boot session and higher-session admission exist; no authenticated handshake. |
| Persistent association | `MISSING_PRODUCT_FEATURE` | Hub and Node association is not stored as a product record. |
| Logical Node ID assignment | `MISSING_PRODUCT_FEATURE` | Logical ID is compiled in. |
| Room/function assignment | `MISSING_PRODUCT_FEATURE` | Room is compiled in. |
| Reboot/rejoin without pairing | `PARTIALLY_IMPLEMENTED` | Fixed pair resumes with a new session; enrolled-node rejoin is absent. |
| Duplicate Node handling | `PARTIALLY_IMPLEMENTED` | Fixed MAC/ID filters exist; clone and registry-conflict policy is absent. |
| Node from another Home | `MISSING_PRODUCT_FEATURE` | No Home credential or association check. |
| Hub from another Home | `MISSING_PRODUCT_FEATURE` | No authenticated Hub/Home binding. |
| Copied or stolen identity | `MISSING_PRODUCT_FEATURE` | No credential anti-cloning or quarantine policy. |
| Pairing timeout/interruption | `MISSING_PRODUCT_FEATURE` | No pairing transaction exists to recover. |
| Hub or Node reboot during pairing | `MISSING_PRODUCT_FEATURE` | No resumable commissioning state. |
| Node removal | `MISSING_PRODUCT_FEATURE` | No revoke, peer removal or tombstone workflow. |
| Node replacement | `MISSING_PRODUCT_FEATURE` | No replacement and logical-room reassignment workflow. |
| Factory reset | `MISSING_PRODUCT_FEATURE` | No target reset semantics for credentials and association. |
| Hub replacement | `MISSING_PRODUCT_FEATURE` | No key-transfer or re-pairing workflow. |
| Credential rotation | `MISSING_PRODUCT_FEATURE` | Host credential reference types exist; target rotation does not. |
| Pairing audit evidence | `MISSING_PRODUCT_FEATURE` | No commissioning event ledger. |
| Commissioning test orchestration | `TEST_INFRA_GAP` | No commissioning campaign or evidence schema exists. |

No requested production commissioning capability is currently classified
`IMPLEMENTED`; the existing implementation is limited to the partial routing,
session and fixed-peer behaviors listed above.

## 4. PROPOSED COMMISSIONING ARCHITECTURE

The following is `PROPOSED_ARCHITECTURE` and is not current behavior:

```text
Add Device
    -> bounded Hub pairing window
    -> exact Node candidate discovery
    -> device-specific cryptographic authentication
    -> Hub/Home binding
    -> logical Node and room/function assignment
    -> ESP-NOW peer and authenticated session setup
    -> persistent association on Hub and Node
    -> normal runtime
```

The production rules should be:

- An ordinary reboot performs an authenticated rejoin without user pairing.
- A nearby unknown Node is rejected or ignored and may increment a bounded
  diagnostic counter; it never becomes trusted because it has a product MAC or
  common product signature.
- A MAC address is useful for routing, but is not sufficient authentication.
- Immutable physical identity and user-facing logical room/function identity
  remain separate.
- Replacement hardware receives a new physical identity and may inherit the
  logical room/function assignment only through an authorized replacement flow.
- Association writes are transactional. A Hub reboot, Node reboot or lost
  final response must resolve to either the old association or a clearly
  recoverable pending transaction.

The exact credential, key derivation, anti-replay and secure-storage design is
`OPEN_DECISION` pending threat modelling and target capacity measurements.

### P2.3 implementation note (2026-09-23)

The approved credential direction is unique asymmetric Node identity. A
bounded, host-tested commissioning state machine now uses an exact QR-pinned
Device ID/public key, a separate one-time installer authorization code,
fresh Hub/Node challenges, P-256 signatures and ephemeral ECDH, HKDF-SHA-256,
and HMAC confirmations. The authenticated transcript includes Home ID, Hub
ID, logical Node ID, room and function. Host tests reject altered assignments,
wrong keys, transcript tampering, expired windows and replay. The test crypto
provider uses OpenSSL and generates test-only private keys in memory.

This is `PARTIALLY_IMPLEMENTED`: no production target credential provider,
commissioning radio/wire adapter, protected association persistence,
authenticated rejoin or target runtime AEAD is connected yet. The installer code
authorizes enrollment intent; knowing it alone cannot forge the Node's
private-key proof. Its disclosure can permit a competing Hub to race to
enroll an uncommissioned Node, so recovery needs explicit product
qualification. No current physical board has passed production-security
qualification.

The scheduled host harness subsequently enrolled each of its 1, 4, 10 and
25 independent NodeRuntime contexts through this protocol before registry
admission. Its uplink and ACK path now wraps the production data-plane codec
with AES-256-GCM, direction-separated session keys, an authenticated counter
and a 64-packet replay window. Host checks include wrong-node ACK delivery,
tampering, stale-session ACK rejection and retry recovery. These are
`HOST/SIMULATED` results. The protected envelope uses 28 bytes, leaving at
most 222 payload bytes under the conservative 250-byte ESP-NOW v1 limit;
the existing codec permits 224-byte frames, so those largest frames are
rejected until the target transport size policy is resolved. Fresh session
salt authentication, persisted anti-replay state or mandatory fresh rejoin,
target crypto/peer wiring and RF capacity remain `PRODUCT_GAP`.

An ESP-IDF 6.0.3 PSA crypto provider for P-256 verification, ephemeral ECDH,
HKDF-SHA-256, HMAC-SHA-256 and AES-256-GCM now compiles in both Hub and C3
projects. Its identity signing operation delegates to an `IdentitySigner`
interface; there is no factory private-key store or target commissioning
caller yet. Both target images build with the shared commissioning protocol
and runtime envelope, but the new code is not in the active target packet
path. This is compile evidence, not physical or production-security evidence.

A separate authenticated rejoin state machine now uses the installation key
to prove possession with fresh Node/Hub challenges, validates the bound
physical/logical/Home/Hub IDs, rejects stale sessions and derives a fresh
runtime session salt. The host harness uses it before registry session
progression, including one-of-ten Node restart with the other nine active.
This is `HOST/SIMULATED` only. The Hub and Node still need persistent
association/session state and an interrupted-final-ACK recovery rule; the
target packet path has not enabled rejoin.

An encrypted single-blob association repository now has host tests for
reopen/reboot, write failure, wrong wrapping key, corrupted data,
generation progression and an explicit factory-reset tombstone. An ESP-IDF
NVS adapter for the wrapped blob compiles in both targets and verifies a
completed write by rereading it. This is `PARTIALLY_IMPLEMENTED`: no
production protected wrapping-key source exists, no target startup loads the
record, Hub multi-node registry/session state is not persisted, and NVS
power-cut behavior has not been physically qualified. A restored old valid
flash image can roll back an association without a separate protected
monotonic counter; service policy for that threat remains open. Corruption
fails closed and needs explicit service recovery.

## 5. MANDATORY MULTI-NODE REQUIREMENTS

The following are `CONFIRMED_REQUIREMENT` product qualification targets:

- One Hub plus 4 logical Nodes.
- One Hub plus 10 logical Nodes — **mandatory product qualification**.
- One Hub plus 25 simulated Nodes for architectural boundary and stress work.
- An explicitly documented architecture-defined maximum and boundary behavior.

Backend/API device registration does not satisfy the ten-node requirement. The
ten-node case must exercise ten independent NodeRuntime contexts and the real
NodeRuntime → transport/session → Hub ingest → HubRuntime → journal/state path
as far as technically possible.

## 6. 10-NODE ACCEPTANCE CRITERIA

The ten-node gate requires individual and aggregate evidence for:

- ten distinct physical/logical identities, sessions, sequence spaces and room
  or function attributions;
- independent health and liveness state;
- simultaneous event generation and correct event attribution;
- no node-to-node state, ACK or session leakage;
- bounded Hub ingress queues, journal occupancy and deterministic full behavior;
- retry correctness, ACK correctness and ACK latency distributions;
- noisy-node fairness and quiet-node starvation protection;
- simultaneous bursts, all-node outage/recovery storms and reconnects;
- individual Node restart without disturbing the other nine;
- Hub restart and recovery of all ten;
- remove, re-add and authenticated rejoin;
- duplicate identity and unknown Node rejection;
- CPU, heap, minimum heap, queue depth, journal occupancy and unexplained
  memory-growth checks;
- dropped and rejected event accounting.

Per-node results are mandatory. One aggregate PASS is insufficient.

## 7. ESP-NOW CAPACITY FINDINGS

The repository builds with ESP-IDF 6.0.3. The installed IDF header defines 20
total ESP-NOW peers and 6 encrypted peers. The repository-generated target
configuration sets `CONFIG_ESP_WIFI_ESPNOW_MAX_ENCRYPT_NUM=7`; the IDF Kconfig
allows a configurable value up to 17 on these targets. The effective encrypted
capacity therefore requires target verification and is below the ten-node goal
under the current known limits.

The current product code adds one unencrypted peer. No multi-peer registry,
peer-key allocation, enrollment persistence or per-peer memory measurement is
implemented. Twenty-five simulated Nodes must never be described as 25
physical ESP-NOW peers. The final product maximum is `OPEN_DECISION`.

This document intentionally does not change either sdkconfig or peer behavior.

## 8. SECURITY / PAIRING OPTIONS

The evaluated mechanisms are:

| Option | Assessment |
|---|---|
| QR-assisted authorization | Recommended for exact-device selection and room assignment; requires manufacturing credential binding. |
| Hub pairing-window control | Required operator authorization and bounded exposure. |
| Node first-boot or physical button | Useful intent/proximity signal; not authentication by itself. |
| ESP-NOW discovery | Suitable offline discovery transport; unsafe as trust decision alone. |
| BLE-assisted commissioning | Possible without new hardware, but adds app, firmware and coexistence complexity. |
| Wi-Fi-assisted commissioning | Adds network dependency and is not currently justified. |

Approved direction: ESP-NOW discovery plus explicit installer authorization,
unique asymmetric Node identity and QR-represented public identity. The Node
must authenticate the intended Hub/Home. Commissioning derives symmetric
runtime keys; application-layer authenticated encryption is required if
native ESP-NOW encrypted-peer capacity cannot support ten. Protocol details,
protected storage and production eFuse policy remain open for implementation
and qualification.

## 9. PRODUCT GAPS

The following are `PRODUCT_GAP` unless a later implementation record changes
their status:

- secure commissioning and persistent Hub/Node association;
- persistent per-node authorization and session state;
- retained and in-flight event persistence across Node restart;
- persistent Hub dedupe and journal with a defined retention/compaction policy;
- target-to-backend bridge;
- Hub self-FOTA;
- signed FOTA manifest, board/version authorization and secure update policy;
- scalable Node registry, peer registry and removal behavior;
- Hub replacement and Node replacement workflows;
- factory reset and credential rotation.

The existing host security reference validates a supplied verifier, but this is
not target provisioning or target boot authenticity.

## 10. FOTA FINDINGS

Hub-initiated C3 FOTA exists. The Hub embeds a C3 image, transfers 200-byte
CRC-checked chunks, retries each packet and supports abort. The receiver handles
bad magic/version, bad session, duplicate and out-of-order sequence, bad chunk
CRC/size, write/finalize/boot-partition failures and inactivity timeout.

Bootloader A/B rollback support is enabled in the target configuration. The C3
currently marks a pending image valid after a fixed five-second task delay;
that is not a complete runtime-health gate. Signed manifests, SHA-256 image
authorization, board/version policy, secure boot enforcement and a measured
post-restart health decision remain gaps. Target FOTA happy-path, negative,
interrupted, restart, boot-failure, rollback and repeated A/B qualification are
Phase-2 work; host receiver tests do not claim those physical outcomes.

## 11. TARGET-TO-APPLICATION GAP

`MISSING_PRODUCT_FEATURE_TARGET_VERTICAL_BRIDGE` is the current status. The
target composition has ESP-NOW Node/Hub runtime and FOTA, but no production
Hub-to-backend transport. `CloudSync` and the local lab are host/reference
components.

The project must not claim physical Node → Hub → backend → PWA qualification
until a production target bridge exists and is separately qualified.

## 12. REAL-HARDWARE EVIDENCE REPLAY

Phase 2 must add a host replay layer built from representative real Phase-1
captures. Required fixtures include:

- ESP32 `rst:0xc (SW_CPU_RESET)`;
- ESP32-C3 `rst:0xc (RTC_SW_CPU_RST)`;
- normalized `SOFTWARE_RESET`;
- UART truncation at reset boundaries and interleaved UART;
- C3 native USB disappearance/re-enumeration;
- explicit C3 PIR sensing-ready delay after boot;
- observed esptool 5.x identity output;
- stale reset and stale `HIL_READY` lines;
- changed and unchanged tty behavior;
- USB disappearance/reappearance where captured.

Fixtures must preserve provenance and fresh-cursor semantics. A new physical
behavior follows: real observation → fix → real evidence fixture → host
regression. Mocks alone are insufficient for observed hardware behavior.

## 13. ACTIVE DISCOVERY HARDENING

The current campaign performs repeated authoritative esptool probing during
preflight, flash verification, capture startup and recovery rediscovery. This
is a `CURRENT_IMPLEMENTATION_FACT` and a Phase-2 hardening target.

The desired future architecture (`PROPOSED_ARCHITECTURE`) is:

```text
initial authoritative identity verification
    -> campaign-cached identity
    -> non-intrusive tty/USB metadata checks
    -> esptool only for explicit re-verification or recovery
```

The qualified Phase-1 implementation is not changed by this document. Any
future hardening must first pass replay and host tests and preserve its bounded
probe, dynamic re-enumeration, fresh evidence and fail-closed behavior.

## 14. PHYSICAL VS SIMULATED QUALIFICATION

| Stage | Scope | Claim boundary |
|---|---|---|
| Stage A | One target Hub architecture plus 4 and 10 logical NodeRuntime Nodes | Runtime isolation, transport/session, queues, journal, recovery and scaling; not ten-node physical RF. |
| Stage B | One Hub plus 25 simulated Nodes | Architectural boundary/stress only; not 25 ESP-NOW peers. |
| Stage C | One Hub plus initially 2–4 physical C3 Nodes | Real contention, retries, ACK timing, RF fairness, bursts and reconnects. |

Stage C must not be described as ten-node physical RF qualification unless ten
physical C3 Nodes were actually tested.

Power interruption, brownout, current/battery endurance, PIR optics,
house-range RF, obstruction/interference and thermal/environmental behavior
remain physical-fixture areas.

## 15. PROPOSED TC FAMILIES

The following Phase-2 families are `PROPOSED_ARCHITECTURE` for qualification:

`P2-COM`, `P2-MN04`, `P2-MN10`, `P2-MN25`, `P2-FOTA`, `P2-FOTA-NEG`,
`P2-FAULT`, `P2-REC`, `P2-PERF`, `P2-SOAK`, and `P2-VERT`.

The existing 71 Phase-1 real-HW cases remain a separate mandatory regression
set. Phase-2 cases must report physical, target-HIL, host/simulated and
extra-fixture status distinctly.

## 16. COMMAND ARCHITECTURE

The following hierarchy is `PROPOSED_ARCHITECTURE`; commands are not added by
this baseline:

```text
make hil-regression  -> Phase-1 71 cases only
make hil-phase2      -> Phase-2 target/multi-node/FOTA/fault cases
make hil-full        -> Phase-1 plus Phase-2, with no duplicate campaign work
make release-qualify -> future complete qualification with shared artifacts
```

Ownership remains with the existing WSL supervisor. PowerShell remains only the
minimal USB helper defined by the Phase-1 architecture.

## 17. IMPLEMENTATION ORDER

The analyzed order is:

1. P2.0 architecture and decision freeze.
2. P2.1 real-evidence replay and scalable multi-instance host transport harness.
3. P2.2 commissioning, registry, authenticated session and persistence.
4. P2.3 4-node qualification.
5. P2.4 mandatory 10-node qualification.
6. P2.5 25-node simulated stress.
7. P2.6 FOTA happy path.
8. P2.7 FOTA negative, rollback and recovery.
9. P2.8 compile-gated deterministic fault injection.
10. P2.9 multi-node recovery storms.
11. P2.10 performance and resource qualification.
12. P2.11 representative 2–4 physical-C3 HIL.
13. P2.12 configurable soak and full qualification.

Before any physical Phase-2 checkpoint, host tests, real-evidence replay,
relevant simulation and code review must pass.

## 18. OPEN ARCHITECTURE DECISIONS

These decisions remain `OPEN_DECISION`:

- final product Node maximum above mandatory ten;
- application-layer versus ESP-NOW encryption strategy;
- factory asymmetric-key generation and manufacturing provisioning process;
- secure credential storage and rotation;
- exact commissioning cryptographic protocol and anti-replay policy;
- offline installer and app-to-Hub control path;
- Hub replacement recovery and key-transfer workflow;
- persistent journal medium, retention and compaction;
- OTA health-validity and rollback criteria;
- target-to-backend transport;
- physical multi-C3 scale required before commercial release.

## 19. TRACEABILITY

The Phase-2 baseline extends the repository’s existing E02 (reliable transport
and duplicate handling), E05 (Node storage), E08/E09 (update/security), E10
(validation), NFR-03 (persistence), NFR-04 (bounded runtime behavior), NFR-05
(target resilience) and NFR-06 (security/update) conventions. The following
planned obligations are recorded in the existing master traceability file and
must not be treated as implemented until their status changes:

| Obligation | Planned coverage |
|---|---|
| At least 10 logical Nodes with real runtime-path exercise | `P2-MN10` |
| Secure commissioning and exact-device authorization | `P2-COM` |
| Unknown Node rejection and foreign-Home rejection | `P2-COM`, `P2-FAULT` |
| Authenticated automatic rejoin | `P2-COM`, `P2-REC` |
| Node remove/replace/re-add | `P2-COM`, `P2-MN10` |
| Per-node isolation and attribution | `P2-MN04`, `P2-MN10`, `P2-MN25` |
| Bounded queues/journal and deterministic full behavior | `P2-MN10`, `P2-PERF` |
| FOTA happy path, negative paths and rollback evidence | `P2-FOTA`, `P2-FOTA-NEG` |
| Preservation of all Phase-1 regression cases | `HIL-PHASE1-01` and `make hil-regression` |

## 20. RECOMMENDED FIRST IMPLEMENTATION STEP

Freeze the security/capacity decisions and acceptance/report contracts in P2.0.
Then implement the real-evidence replay layer and scalable multi-instance host
transport harness while keeping the Phase-1 campaign unchanged. Do not claim
ten-node product support until the registry, authenticated association,
effective encrypted-peer capacity and per-node evidence are implemented and
qualified.

## 21. IMPLEMENTATION CHECKPOINT: P2.1/P2.2 HOST FOUNDATION

The Phase-1 hardware run from 2026-09-23 supplies five `REAL_HARDWARE`
replay fixtures. They cover ESP32/C3 software reset forms, fresh versus stale
readiness, C3 PIR readiness after `HIL_READY`, reset-boundary UART truncation
and interleaving, and esptool 5.4 chip/MAC output. A sixth reconnect fixture
is labelled `SYNTHETIC_NO_RAW_CAPTURE`; the repository does not contain a
portable raw USB disconnect/re-enumeration trace from that run. Replay tests
exercise the existing reboot parser and fresh-cursor state machine. No new
physical test has been executed for this checkpoint.

The existing HIL supervisor now uses cached chip/MAC identity plus stable USB
metadata when starting capture and before flashing. It still performs a bounded
authoritative probe after flash or runtime disappearance/reappearance. The
Phase-1 71-case campaign and assertions retain their ownership and manifest.
This discovery change has host test coverage but still awaits physical
regression before Phase-2 closure.

The host-only scheduled transport harness creates independent `NodeRuntime`
instances, serializes with the production data-plane codec, schedules delivery
to `HubRuntime`, and returns encoded ACKs to the matching runtime. Focused
host cases exercise 1, 4, 10 and 25 simulated contexts, a lost ACK, and a
ten-context logical outage/recovery. Authorization is a test setup shortcut;
commissioning, target ESP-NOW admission, RF behavior, persistent association,
health/liveness and the full ten-node acceptance matrix remain open. These
results are `HOST/SIMULATED` evidence only and do not qualify target ten-node
product behavior or 25 physical peers.

The product owner subsequently approved unique asymmetric Node credentials,
QR-represented public identity and derived symmetric runtime protection.
This resolves the credential-direction decision, while manufacturing/eFuse
layout and effective target peer capacity still require qualification.

## 22. CONNECTED CHECKPOINT AND HIL SETUP RECOVERY

The connected Hub+C3 smoke run at
`evidence/hil/runs/20260923T111615.076642Z` passed 17/17 Phase-1 smoke cases
on commit `fc0776b`, with zero failures, unexpected resets, retained events
or in-flight events. Both targets reported `fc0776b-hil-e3b0c44`; the
standalone and Hub-embedded C3 image hashes matched. This is a physical
single-C3 smoke result, not Phase-1 71-case regression or Phase-2 multi-node
qualification.

The first bare smoke invocation was blocked before any hardware test because
the saved setup belonged to a previous branch. The existing fail-closed
preflight rule remains intact. A focused profile of the existing WSL
supervisor, `make hil-checkpoint-smoke`, now runs USB fixture readiness,
fresh `hil-setup`, `hil-preflight`, then `hil-smoke` in one command. Setup is
refreshed before every focused checkpoint, including after branch, commit or
source changes. The campaign continues to own paired build, conditional
flash, target version/identity checks and report generation. The new profile
has host orchestration tests; its first connected execution remains pending.

## 23. P2.3 REGISTRY FOUNDATION

`NodeRegistry` is now a bounded production C++ component compiled into the
Hub image. It stores distinct physical Device ID/public-key identity, radio
address, Home/Hub binding, logical ID, room and function. It provides explicit
enrollment, monotonic-session rejoin, removal, replacement, bounded revocation
tombstones and quarantine on conflicting physical identity. Capacity is a
constructor policy: host tests prove max−1/max/max+1 at ten installed Nodes;
the commercial maximum above ten remains `OPEN_DECISION`. Replacement retains
the logical slot while changing the physical identity.

Revocation tombstones are never evicted on capacity pressure. At max−1 and max,
removal records the revoked physical identity. At max+1, removal or replacement
returns `RevocationCapacityFull`, retains all prior revocations, and
quarantines the active identity requested for removal. Rejoin then rejects it;
the installer must resolve the exhausted revocation store through an explicit
service workflow. Host regression covers this behavior. Hub persistence and
service recovery remain incomplete, so this is not target restart proof.

A bounded registry snapshot/restore operation now validates Home/Hub identity,
installed capacity, tombstone capacity, active identity conflicts, prior
sessions and quarantine before restoring a fresh registry. Host tests prove
stale-session and revoked-identity rejection after restore. The snapshot is
an in-memory state transfer only: it has no encrypted durable Hub store,
installation-key recovery, target startup path or power-cut proof.

The scheduled host transport harness now uses registry admission before
`HubRuntime`, including removal of one context while the other nine continue.
Its test setup supplies preauthenticated records directly. This does not
constitute cryptographic commissioning, persistent association, target peer
management or physical ten-node qualification. `P2-COM` remains a product gap.

The approved security direction is a unique asymmetric keypair per production
C3, a QR-represented public identity, authenticated Hub/Home binding and
derived symmetric application-layer protection for runtime traffic. The QR
must not expose a private credential that alone permits Node impersonation.
The exact protocol, credential storage, target wiring and production eFuse
policy are not yet implemented.
