# Phase 2 Architecture and Gap Analysis

**Document status:** ARCHITECTURE BASELINE with incremental Phase-2 implementation notes; current snapshot is maintained in [CURRENT_STATUS_AND_ROADMAP.md](progress/CURRENT_STATUS_AND_ROADMAP.md)
**Analysis baseline:** `ae9b7dc` — *Add unattended WSL-first Phase-1 HIL qualification*
**Phase-1 status:** CLOSED / QUALIFIED
**Phase-2 implementation status:** host registry/commissioning/rejoin/persistence and 1/4/10/25 logical-Node foundations exist; one-Hub/one-C3 smoke and same-image OTA health-gate success are physically qualified; Phase 2 remains ACTIVE / NOT COMPLETE

## 1. PURPOSE / SCOPE

For present status, current evidence, release blockers and forward execution
order, see [CURRENT_STATUS_AND_ROADMAP.md](progress/CURRENT_STATUS_AND_ROADMAP.md).
Chronological implementation and HIL defect/fix history is in
[PROJECT_HISTORY.md](progress/PROJECT_HISTORY.md); requirement status is in
[MASTER_TRACEABILITY.csv](validation/MASTER_TRACEABILITY.csv).

This document records the repository and target-firmware analysis that starts
Phase 2 of Ghar Sajag / Parivar Saathi HIL qualification. It is based on the
Phase-1 qualified baseline `ae9b7dc`. It describes current facts, proposed
architecture, product gaps, test-infrastructure gaps and qualification order.

At the original `ae9b7dc` baseline, no Phase-2 product or runtime behavior had
been implemented. That sentence describes the historical analysis point, not
the current branch. The 71 Phase-1 real-HW cases remain
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

### Phase-2 Hub event-history storage decision (host repository implemented; target integration pending)

The 4 MiB Hub flash ends at `0x400000`. The second required OTA slot ends at
`0x3e0000`, leaving exactly `0x20000` (128 KiB) unpartitioned. The existing
default 1,024-entry journal is a RAM bound, not a flash retention promise. A
maximum-length event needs up to 181 bytes before framing, authentication and
NVS entry overhead, so 1,024 such events cannot fit in the free region. Phase
2 will use that region as a separate 128 KiB NVS journal partition without
moving either OTA slot or the existing 24 KiB NVS partition.

The product target will admit at most **128 locally durable event records**.
This is a bound on outstanding records whose safe reclamation is not yet
proven, not a time guarantee for internet outage. A new event receives a
durable ACK only after its authenticated record is committed and read back.
At 128 occupied slots or any write/read/corruption fault, it receives an
explicit rejected ACK; the Node retains its own business evidence. The Hub
must expose storage-full and rejected-event counters. No accepted event may
be silently overwritten.

Exact event identities remain in persistent dedupe state while their records
are retained. A record may be reclaimed only after backend application commit
and authenticated evidence that its source Node has retired that event. A
persisted per-Node/session retirement floor must be committed before record
deletion; older event keys then remain rejected across Hub restart. If that
evidence or floor commit is absent, the slot stays occupied. Target
reclamation, authenticated Node retirement evidence and target/backend
integration remain implementation work.

Use NVS append/commit behavior on the dedicated partition and encrypt each
record with a Hub installation-specific key from a protected production key
provider. Development/HIL keys are test-only. The storage owner must verify
readback before ACK and fail closed on ambiguous recovery. The design avoids
rewriting the entire journal on every event; target erase/write counts and
power-cut atomicity still require measurement. Worst-case sealed payloads are
under 256 bytes, so 128 records consume under 32 KiB of payload before NVS
metadata and reclamation headroom; actual NVS fit is a target qualification
gate. Target RAM journal capacity becomes 128 when this storage owner is
wired; host 1/4/10/25-context stress may continue using larger simulated
capacities with explicit classification.

Adding the partition does not change OTA slot offsets. Existing boards with
the old partition table require a controlled partition-table flash before the
new journal is used; an application-only OTA cannot create this partition.
Migration must fail closed when the expected partition is absent, and must
not report power-loss durability until physical interruption tests pass.

The current checkpoint adds the partition-table entry, a dedicated NVS slot
adapter, and a 128-record host journal that seals each immutable slot using
AES-256-GCM with the slot index as authenticated context. Commit requires NVS
write/readback and successful authenticated decode before an ACK is eligible.
Host tests cover exact capacity, Hub restart dedupe, physical-device
replacement identity, wrong key, corruption and an ambiguous write result.
The **active ESP32 target adapter still uses its qualified volatile journal**;
it does not yet supply a protected Hub key or attach the new store. Therefore
the current target `Durable` ACK still means RAM commitment. No power-loss
durability or flash endurance result is claimed. An append-only 128-record
store without authenticated retirement and backend application receipts will
eventually fill; reclamation and target integration remain release gaps.

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

As of 2026-09-24, the bounded commissioning wire codec is linked into both
targets and host-tested across ESP-NOW-sized fragments. Target key-source
adapters now exist: HIL keys are generated once per target and
stored in explicitly test-only NVS; the production identity adapter accepts
only a separately provisioned persistent PSA signing key. A separate random
wrapping key is committed and read back before use. Production initialization
rejects configurations without secure boot and flash encryption. These
adapters remain **unconnected to the live radio owners**, and the current
prototype configuration has both protections disabled. Their target builds
are compile evidence only; no credential provisioning, association recovery,
or production-security qualification is implied.
The HIL-only `GET_TEST_QR` / `GET_TEST_IDENTITY` commands expose public
identity and a test installation code for future exact-candidate fixture
provisioning; they never export the private signing key. The target crypto
provider now links when actually invoked by C3 HIL code, after correcting
ESP-IDF 6.0.3's C-only constant-time comparison declaration.

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

NodeRuntime now exposes a bounded recovery snapshot of retained business
events, pending transmissions, retry attempts and the storage gap marker.
Host restore requires the same logical Node and a strictly newer boot session,
preserves old event identities, and makes old monotonic retry deadlines due in
the new clock domain. A trusted HubRuntime ingest path accepts such old event
keys only inside the currently authenticated transport session and correct
logical Node mapping. Duplicate journal identities receive an ACK without
repeating reducer effects. A ten-Node host test restarts one Node with an
encrypted frame in flight and proves the other nine continue. This is
`HOST/SIMULATED`: no target flash store or startup restore exists, and the
target ESP-NOW adapter does not yet call the authenticated ingest path.

The Node recovery repository now seals a bounded 8,192-byte record under a
caller-supplied wrapping key and binds it to Home, Hub and logical Node IDs.
It stores pending events once, marks the retained subset, and preserves retry
attempts and the storage gap marker. Wrong identity/key, tampering, corrupt
state and read errors fail closed; failed writes leave the previous record.
It rejects a save from an older boot session. The scheduled host harness now
commits this record after recording, transport results and ACK retirement, and
reopens it for individual Node restart. These are host tests, not flash or
power-loss qualification. The NVS adapter has a dedicated bounded namespace,
but target startup and runtime do not yet use it. A protected key source,
write-frequency/wear policy, power-cut proof and rollback protection remain
open before any target durability claim.

The physical one-Hub/one-C3 checkpoint at commit `613dd45` passed on
2026-09-24: 17/17 smoke cases, zero failures or unexpected resets, and final
retained/in-flight both zero. Both targets reported
`613dd45-hil-e3b0c44`. This is Phase-1 physical regression evidence for
the host recovery foundation; it is not physical persisted-event recovery.

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

The host receiver now checks image metadata on repeated Begin, each Data
chunk and End, requires the expected End sequence, rejects malformed reserved
fields and zero sessions, and does not let rejected traffic extend its
inactivity window. These are protocol-correctness checks only. They do not
authenticate firmware source or image, establish board/version policy, prove
a physical OTA, or replace the fixed target boot-health decision. Lost final
ACK followed by immediate Node reboot remains a recovery case to qualify.
Before restart, a repeated valid End now returns the same Complete result
without writing or activating the image twice.

A Phase-2 same-image physical FOTA checkpoint is now prepared within the
existing WSL HIL supervisor: `make hil-checkpoint-fota` refreshes USB fixture
setup and preflight, builds/flashes the paired HIL images, runs the Phase-1
17-case smoke, then triggers C3 OTA through a compile-gated Hub UART command.
It requires fresh transfer completion, expected C3 software-reset evidence,
the alternate OTA slot, exact paired firmware provenance, PIR readiness,
post-update motion/ACK and empty retained/in-flight state. This same-image
checkpoint does not prove version upgrade,
signed-image authorization, rollback, or repeated A/B cycles.

The connected checkpoint at `evidence/hil/runs/20260924T085804.060488Z`
passed the 17 Phase-1 smoke cases and all three `P2-FOTA-SAME` cases. The
paired ESP-IDF v6.0.3 images both report `6ed7de7-hil-ae23023`: Hub SHA-256
`f2f619efead13239b245c86b5844f50136eb70f29bb0cc8876d3793b0e01388a`,
C3 and Hub-embedded C3 SHA-256
`1f4ee9844ca1bf79ecd0cf6f49da341cf10d0e51c8d5f1a50ae2c313e835d748`.
The C3 log shows `ota_0` to `ota_1`, a fresh `rst:0xc (RTC_SW_CPU_RST)`,
the new `HIL_READY`, subsequent PIR readiness, and a motion event retired by
application ACK. Final retained and in-flight counts are zero, with no
unexpected reset reported. This physical result qualifies same-image transfer,
reboot and functional recovery only. Version upgrade, image authenticity and
rollback remain unqualified.

The earlier physical log exposed an incomplete boot-health ordering: the old
five-second task marked the pending image valid before PIR stabilization.
`P2-REPLAY-FOTA-001` retains those raw lines as a permanent regression. The
replacement uses a bounded 90-second gate:
NodeRuntime owner active, PIR ready, at least two post-sensing runtime ticks,
a fresh post-sensing health frame accepted at the ESP-NOW MAC layer, no active
maintenance, and at least 8 KiB minimum free heap. Missing health evidence
requests ESP-IDF rollback instead of marking the image valid. `FOTA-HOST-028`
passes, and the paired HIL build passes. The gate then passed on physical
hardware at `evidence/hil/runs/20260924T094521.398370Z`. That run used commit
`7bc2a3302b2e8b7792aefe453f31e78a750fe929`, clean source fingerprint
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, Hub
SHA-256 `b713e7d983d5e343cea8b66581cac4dde56967b13a4b6a36e730b412446881ae`,
and matching standalone/embedded C3 SHA-256
`a439202c8e4231bc3c29a67ee2cc42ee90c4b5c6a33c7102f7859c1fba52d10b`.
Both report `7bc2a33-hil-e3b0c44` on ESP-IDF v6.0.3. The C3 changed from
`ota_0` to `ota_1`, produced fresh `RTC_SW_CPU_RST` evidence, reached PIR
readiness, then logged image validity. At that decision the gate had observed
post-sensing runtime ticks, accepted health transmission at the ESP-NOW MAC
layer and minimum free heap of 201,212 bytes. A post-OTA motion event was
application-ACKed; unexpected resets, retained events and in-flight events
were all zero. The physical campaign passed 17/17 smoke and 3/3 same-image
FOTA cases. MAC delivery does not prove authenticated Hub application
admission, and this run did not exercise the timeout/rollback branch. Version
upgrade, image authenticity, negative transfer cases, rollback and repeated
A/B cycles remain unqualified.

The same report lists six `BLOCKED_EXTRA_FIXTURE` rows: Hub power cut, C3
power cut, controlled brownout, current/battery measurement, optical PIR
stimulus, and house-range RF/thermal testing. They are explicitly outside this
focused software FOTA checkpoint and require specialized fixtures. It contains
no blocked radio, offline, Hub restart, C3 restart or both-target restart
suite rows; those cases were not run by this focused campaign. Host/logical
coverage exists for some of those paths, while physical multi-C3 RF and
target outage/restart-storm evidence remain Phase-2 qualification gaps.

### Deferred battery milestone after Phase 2

Battery optimization is the next milestone, outside Phase 2: HW-M1.4B
baseline current measurement; HW-M1.4C1 automatic light sleep and measurement;
HW-M1.4C2 GPIO4 PIR event wake, immediate first motion with 30–60 second
coalescing, adaptive health/offline retry backoff; HW-M1.4C3 deep sleep with
RTC retention; then overnight/endurance qualification. AM312 remains powered,
critical events stay immediate, and per-motion NVS writes are avoided. The
current roughly 20 ms polling and 60 second HIL health interval are not the
production battery policy.

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
stale-session and revoked-identity rejection after restore. The registry
snapshot method itself transfers in-memory state; the repository described
below adds authenticated serialization around it.

A separate bounded Hub registry repository now encrypts one snapshot containing
up to the configured installed-node capacity, associated installation keys,
session floors, quarantines and revoked Device IDs. Its host tests cover ten
Nodes, wrong wrapping/Hub identity, tampering, write failure, lost revocation
and session rollback. A 25-Node host-only snapshot passes its configured
boundary and max+1 is rejected. It refuses a replacement snapshot that
silently drops a revocation or an active Device ID. The ESP-IDF NVS adapter
has a separate 8,192-byte bounded registry namespace and compiles into the
Hub image. Status is `PARTIALLY_IMPLEMENTED`: target runtime does not call it,
no protected Hub wrapping-key provider exists, NVS fit/power-cut behavior has not been
measured, and a valid old flash image can still roll back state without a
protected monotonic counter. It is not target restart qualification.

The scheduled host transport harness now runs the asymmetric commissioning
protocol, authenticated rejoin and registry admission before `HubRuntime`,
including removal of one context while the other nine continue. It does not
constitute target commissioning, protected target credential storage, target
peer management or physical ten-node qualification. Target `P2-COM` remains a
product gap.

The host scheduler now separates authenticated Hub ingress from the Hub state
owner's processing budget. A ten-context pressure case fills the 32-entry
HubRuntime ingress queue, observes explicit rejections, resumes processing and
drains all ten retained events without wrong-node ACKs. A separate journal
case caps storage at eight entries and proves two Nodes keep their rejected
events. A noisy Node with 20 events does not starve nine quiet Nodes. These
cases and the 1/4/10/25-context cases produce
`build/multinode_host_summary.json` with one result and metrics row per Node;
the existing validation gate checks expected/executed/passed case and Node
counts. The artifact is `HOST/SIMULATED`, not target or physical RF proof.

The approved security direction is a unique asymmetric keypair per production
C3, a QR-represented public identity, authenticated Hub/Home binding and
derived symmetric application-layer protection for runtime traffic. The QR
must not expose a private credential that alone permits Node impersonation.
Host commissioning and runtime-authentication protocols now implement this
direction for test identities. Production credential storage, active target
commissioning/runtime wiring and production eFuse policy are not implemented
or physically qualified.

## 24. CURRENT STATUS UPDATE — 2026-09-24

Phase 2 remains **ACTIVE / NOT COMPLETE**. Host-side commissioning crypto,
authenticated runtime frames/rejoin, bounded registry and fail-closed
revocation, encrypted association/registry/Node-recovery records, and scheduled
1/4/10/25 logical-Node qualification have advanced beyond the original
architecture baseline. Ten-Node ingress/journal pressure, noisy-node fairness,
and per-Node evidence are host/simulated results. Target adapters/builds do
not establish active target commissioning, protected key sourcing, durable
target association restore, or ten-peer ESP-NOW/RF qualification.

The Hub event-history design is bounded to 128 locally durable records in the
128 KiB `gs_journal` partition while preserving both OTA slots. The
authenticated target owner now initializes the existing NVS slot store and
attaches the existing encrypted append/dedupe journal before processing
authenticated events. Its journal key is derived from the Hub wrapping key
with Home/Hub context. Each new event is persisted and read back before the
application ACK; restore failure prevents the secure owner from starting,
while a runtime write/readback fault rejects the event without an accepted
ACK and faults further journal commits. The 129th distinct event is rejected
rather than overwriting history. The
production-profile Hub build (`GS_HIL_BUILD=OFF`) and focused host journal
regression pass. This is target-build evidence only: physical restart/power-cut
recovery, production protected-key provisioning and flash endurance are not
qualified. The 128-slot append-only store has no reclamation; backend/cloud
acknowledgment state also remains volatile, so this does not provide a complete
cloud delivery/retention lifecycle.

The latest physical result is
[`evidence/hil/runs/20260924T094521.398370Z`](../evidence/hil/runs/20260924T094521.398370Z):
17/17 smoke plus 3/3 same-image OTA passed on firmware provenance
`7bc2a33-hil-e3b0c44`, with OTA slot change, fresh reset, PIR readiness,
post-boot health gate, and post-OTA application ACK. This is one Hub plus one
C3. It does not qualify version upgrades, image authenticity, rollback,
negative/interrupted OTA, physical multi-C3 contention, or the six extra
electrical/optical/RF fixtures. See
[CURRENT_STATUS_AND_ROADMAP.md](progress/CURRENT_STATUS_AND_ROADMAP.md) for
the exact PASS/BLOCKED interpretation and remaining blockers, and
[PROJECT_HISTORY.md](progress/PROJECT_HISTORY.md) for dated milestones.

The master traceability entries are the source of truth for requirement
status. Phase-1 remains closed with all 71 real-HW cases mandatory for
regression; its final evidence and detailed historical HIL fixes are recorded
in [PROJECT_HISTORY.md](progress/PROJECT_HISTORY.md).
