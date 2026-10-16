# Device Identity, Registration and Lifecycle

Feature documentation type:
ENGINEERING FUNCTIONAL GUIDE

This guide explains stable feature functionality and implementation.

It is NOT the current project-status authority.

For current project status: `docs/progress/CURRENT_STATUS_AND_ROADMAP.md`
For implementation/evidence traceability: `docs/validation/MASTER_TRACEABILITY.csv`
For feature qualification: `docs/validation/` and `evidence/hil/runs/`

## 1. Purpose

Registration answers: “Is this exact physical Node authorized for this Home
and Hub, and what logical job should it perform?” The answer is based on a
cryptographic identity proof and a stored association. A radio address is
useful for delivery, but is not an identity credential.

Keep these concepts separate:

| Concept | Meaning |
|---|---|
| Physical device identity | Device ID plus that device's asymmetric public/private identity keypair. The private key proves possession; the public identity is carried in the expected-device record/QR. |
| Kit/Home authorization | The expected installation and exact Node are authorized to become associated. Home ID scopes the installation; installer authorization participates in commissioning. |
| Commissioning | A short, explicit first-enrollment or replacement protocol that authenticates both sides and creates a long-term installation binding. |
| Logical Node identity | Stable application slot, such as `node-01`. It can be assigned to replacement hardware without changing the replacement's physical identity. |
| Room/function assignment | Human/product meaning such as “bedroom / movement”. It is bound into commissioning so a proof for one assignment cannot be reused for another. |
| Persistent association | Node-side Home/Hub/Node/logical assignment and installation key saved in a versioned, AEAD-wrapped record. Hub-side registry and keys are saved in a separate encrypted snapshot. |
| Authenticated rejoin | A returning enrolled Node proves the existing association and establishes a fresh session. It is not first-time registration. |

## 2. Simple lifecycle

```text
Factory/service provisioning
  -> permanent Device ID and identity keypair
  -> public identity/QR record; private key remains on device

Starter-kit preparation
  -> expected Hub/Node relationship and intended logical assignment

Home installation
  -> authorized, bounded commissioning window
  -> exact expected Node identity
  -> Node proves private identity; Hub proves Home/Hub authority
  -> ephemeral ECDH, then HKDF derives installation material
  -> Node association and Hub registry persist
  -> room/function assignment is bound -> authenticated rejoin -> READY

Normal reboot or outage
  -> load association -> authenticated rejoin -> fresh session -> READY
  -> no registration again
```

Target owner state machines implement this shape. Product installer entry and
manufacturing supply processes remain incomplete; see limitations.

## 3. Factory/service provisioning

The identity protocol expects a unique Device ID and P-256 keypair for each
Node, plus a Hub installation identity. Public identity data can be printed in
a QR/manufacturing record. The QR may include a one-time installer code used
to authorize enrollment. That code is not the Node's identity proof and must
not enable impersonation without the private identity key.

The private identity key is secret. Public keys, Device ID, Hub/Home IDs,
logical assignment, and QR identity data are not secret, although they need
integrity protection. Installation keys, wrapping keys, private keys, and
installer codes are secret. Firmware image signing keys are a separate trust
domain from device identity keys.

Current target code has `TargetIdentitySigner` and `target_wrapping_key`;
development target provisioning can create/use test identity material in NVS
and the target PSA adapter supplies P-256/ECDH/HKDF/HMAC/AES-GCM operations.
This is development support, not a production manufacturing process. The
repository has no audited factory key-generation, QR binding, protected
production key custody, rework, or replacement workflow. Existing design
requires production private keys to remain protected on device and public
identity to leave the factory; the exact storage/eFuse policy is undecided.

## 4. Starter-kit pre-bonding intent

The intended standard kit is prepared with the Hub's expected Home identity
and the exact Node identities/assignment records before installation. This
lets installation authorize the supplied Nodes rather than ask the user to
manually pair every standard Node from scratch. The installed implementation
accepts an explicit `ExpectedNode` record containing the exact MAC, Device ID,
public key, installer code and logical/room/function values. A production
kit-preparation and secure distribution channel for those records is not
implemented. Do not treat the C++ record/API as a finished installer UX.

## 5. Add Device and commissioning

The Hub opens one expected-device exchange for 120 seconds. It binds the
offer to the exact expected Device ID/public key, Home/Hub, assignment and
installer code. The Node's own first-boot commissioning window is bounded to
10 minutes. Radio source MAC is an additional filter only: a MAC can be
copied, changed, or observed, so it cannot prove private-key possession.

```text
Hub (authorized request)                       exact Node
  Offer + Hub identity/challenge  ------------->
                                  <------------- Node proof/signature,
                                                identity and ephemeral key
  Hub proof/signature + ECDH transcript -------->
                                  <------------- final transcript confirmation
  authenticated commissioning ACK  ------------>
  Node saves association; then begins authenticated rejoin
```

The common protocol authenticates fresh challenges, both identities, Home ID,
logical ID, room/function, protocol version and ephemeral ECDH keys. Each side
checks the peer's signature/private-key proof; the Hub also checks the
installer authorization. ECDH creates shared secret material, and
HKDF-SHA-256 derives the installation key and confirmation values with
transcript/context binding. The resulting installation key supports later
rejoin and session derivation. It is not a permanent runtime traffic key.

On target, the Hub sends the final ACK only after committing the candidate
registry snapshot; the Node persists its own association after validating
that ACK. This ordering narrows inconsistency but does not solve all crash
windows. A lost final ACK can leave Hub and Node with different commit views;
full interrupted-commissioning recovery is not qualified.

## 6. Persistent association and registry

The Node association record contains the authenticated binding (physical
Device ID and public key, Home ID, Hub ID, logical ID, room/function, and
installation key). `AssociationRepository` serializes a bounded,
versioned record with a generation, random nonce and AES-256-GCM tag. The
header is authenticated as associated data. Factory reset writes an
authenticated unpaired tombstone, rather than relying on erasure alone.

The target blob adapter stores the wrapped record in NVS. The wrapping key is
supplied separately by `load_or_create_target_wrapping_key`. Current target
NVS is not a claim of production-protected storage: the development key
source is not the approved production key custody mechanism. The Hub uses a
separate bounded encrypted registry snapshot, including active physical and
logical assignments, installation keys, session floors, revoked IDs and
quarantine state. Hub/Home wrapping key derivation also scopes its journal
key.

Generations and authenticated records detect malformed, corrupt or
wrong-key data and the repositories reject unsafe rollback transitions in
their supported state model. They do not provide hardware anti-rollback
against restoration of an older valid flash image. Association IO/decryption
errors and Hub registry corruption fail closed: target owners enter fault or
keep event admission closed; they do not silently enroll a blank replacement.
The target NVS adapter writes and reads back a single blob, but power-cut
atomicity and flash rollback resistance require target qualification.

## 7. Authenticated rejoin

```text
Node boot
   |
   v
Load association and allocate a fresh monotonic boot session
   |
   v
Send authenticated rejoin hello (Device/Home/Hub/logical + challenge)
   |
   v
Hub verifies enrolled binding and session floor; returns fresh challenge
   |
   v
Node and Hub prove transcript, derive fresh session salt
   |
   v
Hub persists accepted session; both install new runtime AEAD session
   |
   v
READY
```

The Hub accepts only a strictly newer authenticated session for the exact
registry record, persists the updated registry before admitting application
traffic, and only then starts that Node's runtime frame context. The Node
loads its association and sends rejoin automatically. A reboot therefore
does not rescan a QR or create a new registry member. Stale/foreign rejoin
messages are rejected. See the communication guide for packet protection.

## 8. Remove and revoke

Removal is a locally authorized Hub owner operation. It first builds and
persists a candidate registry with the Node removed and its Device ID
tombstoned, then erases in-memory installation-key copies and active/rejoin
sessions. When tombstone capacity is full, the registry rejects admission and
retains the existing active state rather than forgetting revocation history.
If persistence fails, the security owner faults and clears active sessions;
it does not report successful access cut-off. Future data/rejoin from a
removed or revoked identity cannot be admitted. There is no completed
installer-facing Remove Device workflow documented by the target API alone.

## 9. Replace Node

Replacement is a new physical identity, not a reboot. The target Hub
replacement path checks the old and expected-new Device IDs, same logical
ID/room/function, distinct physical identity/MAC, and available tombstone
capacity. After successful commissioning it replaces the registry entry and
installation key as one persisted candidate update, then exposes the old
radio/logical slot for owner cleanup. The replacement has its own keypair and
proof; the old Node's identity is not copied. This C++ owner path is not a
complete service/product workflow.

## 10. Factory reset and ownership reset

A Node ownership reset should remove its Home/Hub association, installation
key, runtime session and retained ownership-bound state, while preserving the
factory Device ID and private identity key. The repository implements an
authenticated association tombstone. Node recovery persistence is separately
bound to Home/Hub/logical identity and should not be reused across ownership
change. A Hub ownership reset must clear Home identity, Hub associations,
registry/revocation state and derived journal state under a deliberate service
procedure. A production coordinated reset UX and audit workflow are not
implemented. Never infer it from deleting arbitrary NVS keys.

## 11. Hub replacement and recovery

Current architecture binds Node association to a specific Hub and Home. A
replacement Hub with a different identity cannot simply impersonate the old
Hub or inherit the Nodes' sessions. The provisioning design says baseline
recovery requires explicit recommissioning. Automated Hub-key migration,
escrow, restore authorization and registry transfer are not defined. A
Hub's NVS snapshot is encrypted under its wrapping key; a copied blob without
that key cannot restore enrollment. Physical recovery and production
ownership-transfer behavior remain incomplete.

## 12. State ownership

| STATE | OWNER | RAM/NVS | DURABILITY | PURPOSE |
|---|---|---|---|---|
| Factory identity/keypair | `TargetIdentitySigner` | signer/provider plus target NVS in development implementation | Intended permanent; production protection/provisioning unresolved | Proves physical Device ID identity |
| Home and Hub identity | Hub `HubSecurityLink` | Home ID in NVS; Hub ID derived from radio MAC in current target; active copy in RAM | Home ID persists; production identity lifecycle unresolved | Scopes installation and peer binding |
| Node association | Node `AssociationRepository` | RAM binding plus wrapped NVS blob | Survives reboot; AEAD corruption fails closed | Rejoin identity, assignment and installation key |
| Hub registry | `NodeRegistry` / `HubRegistryRepository` | RAM active records plus encrypted NVS snapshot | Survives reboot when key/record valid; target startup restore is wired | Admission, assignment, session floor, revocation |
| Runtime session | `RuntimeFrameSecurity` per Node | RAM only | Recreated by rejoin after reboot/outage | Fresh directional traffic keys, counters and replay windows |
| Logical assignment | Hub registry and Node association | RAM plus encrypted snapshots/blobs | Persists through reboot; replacement explicitly rebinds | Routes physical Node to product slot and room/function |
| Revocation/tombstone | `NodeRegistry` | RAM plus encrypted Hub snapshot | Durable subject to snapshot/key/rollback limits | Prevents removed identity from returning as active |
| Node retained/pending events | `NodeRecoveryRepository` and `NodeRuntime` | RAM plus encrypted recovery NVS blob | Host and target persistence wired; physical durability not qualified | Retry event identity across reboot |

## 13. Failure and recovery matrix

| Condition | Detection/expected behavior | Recovery guidance |
|---|---|---|
| Unknown Node | No matching enrolled Device ID; ordinary traffic/rejoin rejected | Verify exact QR/expected record and complete authorized commissioning |
| Wrong Home | Transcript/binding Home mismatch rejects proof or rejoin | Confirm intended Hub/Home; do not edit identity fields to force admission |
| Wrong Hub | Node pins authenticated Hub ID/MAC; signature and binding mismatch reject | Restore intended Hub or use approved recommissioning/replacement path |
| Stale session | Session must be strictly newer; old runtime session is not restored | Allocate fresh boot session and complete rejoin |
| Corrupted association | GCM/decode/version failure returns Corrupt and Node faults | Preserve blob/logs for diagnosis; authorized service reset/recommission after cause is understood |
| Missing association | First boot opens bounded commissioning, not runtime admission | Use authorized expected-device Add Device flow; avoid untrusted open enrollment |
| Revoked Node | Tombstone prevents re-enrollment/rejoin; traffic rejected | Use a new physical Node and explicit replacement procedure |
| Registry full | Capacity limit is 10 installed records; fail-closed admission; tombstone capacity also bounded | Remove/reconcile through service procedure; do not clear tombstones to make room |
| Hub restart | Restores registry, rejects bad/corrupt state; Node rejoin recreates session | Inspect NVS load result, wrapping-key availability, Hub/Home identity and session floor |
| C3 restart | Loads association, creates new boot session, rejoins | Inspect association load and rejoin proof; runtime keys are expected to change |
| Commissioning timeout | Hub offer expires after 120 s; Node initial window is 10 min; fragments also bounded | Start a new explicitly authorized window and capture both sides' state |

## 14. Important source files/classes

Paths below are relative to
`code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/`.

- `firmware/common/security/commissioning_protocol.*` — `HubCommissioning`,
  `NodeCommissioning`, transcript binding and derived binding.
- `firmware/common/security/commissioning_crypto.*` and
  `psa_commissioning_crypto.*` — crypto-provider API and target PSA backend.
- `firmware/common/security/commissioning_wire.*` — bounded fragmented
  commissioning/rejoin wire codec.
- `firmware/common/security/association_persistence.*`,
  `nvs_association_blob_store.*` — wrapped Node association record.
- `firmware/common/security/target_identity_signer.*`,
  `target_wrapping_key.*` — target identity and wrapping-key sources.
- `firmware/common/security/rejoin_protocol.*` — authenticated rejoin proof.
- `firmware/hub/components/registry/node_registry.*` and
  `registry_persistence.*` — capacity, assignment, session floor, revoke,
  replace, encrypted snapshot.
- `firmware/hub/target/esp32/hub_security_link.*` — target commissioning,
  rejoin, registry persistence and active sessions.
- `firmware/node/target/esp32c3/node_security_link.*` — Node boot state,
  association load, first commissioning or rejoin, READY transition.
- `firmware/node/components/storage/node_recovery_persistence.*` — retained
  event/retry recovery, distinct from ownership association.

## 15. Tests and qualification boundary

**Host verified:** Commissioning transcript/crypto, wrong identity/assignment,
expiry/replay, registry conflict/capacity/replacement, encrypted association
and registry persistence, corruption/wrong-key/write failures, and authenticated
rejoin have host validation sources including
`tests/cpp/commissioning_crypto_validation.cpp`,
`tests/cpp/node_registry_validation.cpp`,
`tests/cpp/registry_persistence_validation.cpp`, and
`tests/cpp/rejoin_host_validation.cpp`.

**Target-build verified:** PSA crypto adapter, target identity/wrapping-key
adapters, Hub/C3 commissioning/rejoin owner integration, and NVS storage
integration have ESP-IDF target-build evidence in traceability. Build
compilation does not prove provisioned credentials or runtime radio security.

**Physically qualified:** The default HIL/Phase-1 path does not qualify
Phase-2 physical commissioning, protected identity storage or authenticated
rejoin.

**Not yet physically qualified:** Current-HEAD end-to-end commissioning,
restart/outage rejoin, remove/revoke, replacement, storage corruption/power
cut, and production protected key behavior. Historical HIL PASS results are
not evidence for current-HEAD identity lifecycle behavior.

## 16. Known limitations

- Product/installer Add Device channel and authorization UX are incomplete.
- Standard-kit pre-bonding data generation/distribution is not a production
  workflow.
- Manufacturing credential provisioning and production key custody are not
  defined; target development keys are not production credentials.
- Current-HEAD physical commissioning and authenticated rejoin are unqualified.
- Interrupted commissioning after one side commits needs a fully qualified
  recovery protocol.
- Hub replacement/migration and ownership reset procedures are incomplete.
- Current target storage has no qualified anti-rollback or power-cut claim.

## 17. Engineer troubleshooting

For commissioning failure, compare the exact expected Device ID, QR public
key, source MAC, installer authorization, Home/Hub IDs and room/function on
both sides. Check the bounded offer/window and fragment assembler timeout.
Then inspect `HubSecurityLink::accept`, `NodeSecurityLink::accept`, PSA
operation results and registry result; changing the MAC cannot repair a key
or transcript mismatch.

For a Node that does not rejoin, inspect association status/generation, target
boot-session allocation, pinned Hub ID/MAC, rejoin hello/challenge/final/ACK
messages, and Hub persisted session floor. A new session must be strictly
higher. For an unknown Node or rejected admission, check `NodeRegistry::find`,
revoked/tombstone state, quarantine, Home/Hub/logical conflicts, installed
capacity, and registry load status. If association decryption fails, preserve
the blob and check format version, generation, nonce/tag, NVS readback and
wrapping-key source; do not silently erase it and treat the device as new.
