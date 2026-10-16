# Hub Persistence and Recovery

Feature documentation type:
ENGINEERING FUNCTIONAL GUIDE

This guide explains stable feature functionality and implementation.

It is NOT the current project-status authority.

For current status: `docs/progress/CURRENT_STATUS_AND_ROADMAP.md`
For implementation/evidence traceability: `docs/validation/MASTER_TRACEABILITY.csv`
For physical qualification: `docs/validation/` and `evidence/hil/runs/`

## 1. Easy mental model

Hub state has different lifetimes. Identity and enrolled authorization are
needed after reboot. Accepted event history supports dedupe and reducer
reconstruction. A live runtime session and recent Node contact are temporary
and must be recreated. Persisted does not automatically mean
power-cut-qualified.

```text
identity/security state     survives via NVS records (with key caveats)
registry/authorization      survives via encrypted registry snapshot
event/journal state         survives via encrypted append-only event slots
runtime session/liveness    RAM only; Nodes rejoin and report/contact again
FOTA transaction            volatile; a restarted transfer is abandoned
```

## 2. State ownership

| STATE | OWNER | RAM / NVS / OTHER | ENCRYPTED? | SURVIVES RESTART? | RESTORE PATH | PURPOSE |
|---|---|---|---|---|---|---|
| Home identity | `HubSecurityLink` | RAM plus `gs_home` NVS blob | No separate AEAD shown for ID; integrity checked by length/nonzero | Yes, if NVS is readable | `load_or_create_home_id` during security initialization | Binds installation |
| Hub identity | `TargetIdentitySigner` and target adapter | signer/provider plus Hub MAC-derived Hub ID in current target | Private key secret in development NVS source; protection not production-qualified | Intended to survive; exact provisioned key source matters | signer initialize/public key lookup; Hub ID derived from current MAC | Proves Hub and scopes association |
| Node registry | `NodeRegistry` + `HubRegistryRepository` | RAM + NVS wrapped blob | AES-GCM under supplied wrapping key | Yes if valid blob/key and same installation identity | `HubSecurityLink::initialize` loads repository and restores registry | Enrolled identity, logical/room/function and session floor |
| Associations/installation keys | Registry repository bindings | RAM + encrypted registry blob | AES-GCM | Yes if valid snapshot/key | Loaded with registry into HubSecurityLink | Authenticate Node rejoin and derive runtime session |
| Revocation/tombstones | `NodeRegistry` snapshot | RAM + encrypted registry blob | AES-GCM | Yes within stored bounded snapshot | Restored with registry | Prevent removed Device ID admission |
| Event journal/dedupe | `HubJournal` | RAM index + dedicated `gs_journal` NVS slots | Event blob AES-GCM; key supplied by security owner | Yes for the 128 committed slots if restore succeeds | Attach persistence, scan slots, rebuild IDs, then `restore_from_journal` | Durable event ACK boundary, dedupe and state replay |
| Runtime session | `HubSecurityLink` | RAM per active MAC/Node | Session keys are cryptographic material in RAM | No | Authenticated rejoin creates fresh session | Frame AEAD and replay counters |
| Per-Node liveness/health | `HubRuntime` maps | RAM only | Health arrives authenticated; snapshot itself not persisted | No; clears/rebuilds after restart | New health/event traffic after rejoin | Recent contact, diagnostics and online query |
| FOTA transaction | Hub sender/owner guard | RAM queues and worker state | Individual messages use runtime AEAD | No; restart requires a new transfer | New authorized request/session | Bound transfer progress and ACK matching |
| Rule/coverage runtime state | `HubRuntime`, `CoverageTracker`, rule services | RAM | No | Not generally | Journal replay restores only basic event-derived reducer/coverage effects | Current operation state; full policy/timer checkpoint is not restored |

The encryption rows describe software AES-GCM wrapping. They do not establish
hardware-protected production key custody or flash encryption.

## 3. Registry persistence

The target Hub registry capacity is 10 active Nodes and 10 revocation
tombstones. One bounded `GSRG` version-1 snapshot stores Home/Hub identity,
physical Device ID and P-256 public key, radio MAC, logical ID, room/function,
last accepted session, quarantine flag, Hub public key, each installation
key, and tombstone IDs. The repository authenticates metadata as GCM
associated data and encrypts the serialized snapshot under a supplied Hub
wrapping key. Maximum blob size is 8192 bytes; generation increments on
successful save. Restore validates the whole snapshot into a candidate before
replacing active registry state.

Startup `HubSecurityLink::initialize` loads or creates Home ID, initializes
the identity and wrapping-key provider, constructs the repository, and loads
the registry. Corrupt or IO-error state faults the security link; no empty
registry is silently substituted. A missing snapshot means a new/empty
registry. Security-state progression rules preserve old revocations, prevent
session rollback, and prevent unquarantine or identity/assignment mutation
outside supported replacement semantics.

Removal commits a candidate tombstone snapshot before active access is
stopped. If tombstone capacity is full, removal fails closed by quarantining
the active record and refusing session admission; it does not drop prior
tombstones. Repeated tombstone reclamation or registry reset is not provided
as an automatic space-making policy. Generation detects state progression in
the repository model but not rollback to an older valid physical flash image.

## 4. Event journal

The production secure Hub owner initializes dedicated NVS partition
`gs_journal`, creates `HubRuntime(32, 128)`, attaches a `HubJournal` to the
slot store, and restores it before admitting authenticated events. There are
128 append-only slots. Each event record is encoded with physical/logical
identity, session and sequence, timestamps, event/sensor type, uncertainty,
battery value, test flag and RSSI, then AES-GCM wrapped with a random nonce
and slot-bound associated data. The caller supplies a journal key derived
from the Hub/Home wrapping key context; the key is not stored in the journal
partition.

Restore scans slots in order, rejects a populated slot after an empty slot,
authenticates/decrypts every blob and rejects duplicate identities. Any
ambiguous read or invalid slot faults the journal. `HubRuntime::restore_from_journal`
replays records through basic event-derived coverage/routine/activity state
once, before new event processing; it does not emit rule signals. Volatile
runtime sessions, liveness maps, full routine schedule/config transitions,
timers, cloud ACK status and complete policy state are not restored from this
event log.

## 5. Durable ACK semantics

In the current target secure event path, a new normal event gets a `Durable`
ACK only after `HubJournal::commit` returns `Stored`. For persistent mode,
`Stored` means the slot was written, committed, read back byte-for-byte,
authenticated/decrypted again and checked against the event identity before
the in-memory journal index is updated. An exact known journal key returns
`Duplicate`; Hub sends a `Durable` ACK without applying reducer effects
again. A full journal or storage fault returns rejection, so the Hub does not
emit a durable ACK. The NVS API commit/readback is a software durability
boundary, not proof of every sudden-power-loss timing case.

Privacy policy is a distinct case: passive activity may be ACKed
`DiscardedPolicy` without being journaled. This says the Hub deliberately
discarded the activity under policy, not that event evidence was durably
retained. A Node's durable ACK is also not a backend application commit ACK
or caregiver notification. Cloud publishing does not reclaim local slots;
cloud application ACK state is currently RAM-only and journal reclamation is
not implemented.

## 6. Restart flow

```text
Hub boot
   ↓
initialize NVS / load Hub signer and wrapping-key source
   ↓
load Home ID; derive Hub ID; load and restore encrypted Node registry
   ↓
restore ESP-NOW peers for enrolled Nodes
   ↓
initialize gs_journal and attach encrypted journal
   ↓
scan/validate journal and replay basic event-derived state
   ↓
start secure owner event admission
   ↓
Nodes authenticate rejoin and get fresh RAM sessions
   ↓
health/event traffic rebuilds volatile contact and health state
```

The order is intentional: journal/registry faults refuse secure event
admission rather than lose the durable ACK contract. Active runtime sessions
and liveness are not resumed from flash. FOTA work is not resumed from a
persisted transaction record.

## 7. Write strategy, failure and atomicity

Registry saves are versioned, bounded, encrypted snapshots in the association
blob store. Repository validates prior state and next state, increments
generation, creates a fresh nonce and asks the blob store to write/read back
the wrapped blob. Journal records use individual immutable append-only slots;
target `NvsJournalSlotStore::write` refuses an already populated slot, calls
NVS set/commit and verifies readback. A failure turns into StorageFault and
closes event admission; code deliberately does not erase/reformat an NVS
partition after initialization errors.

These checks detect corruption and ambiguous writes, and candidate state
objects avoid partial in-memory mutation. They do not establish physical
power-cut atomicity, eFuse anti-rollback or recovery from a valid older flash
image. Those claims need explicit target qualification. Journal ACKed slots
are still occupied because there is no safe retirement floor, cloud commit
durability scheme and compactor.

## 8. Capacity behavior

- **Registry:** 10 active records. New enrollment is rejected at capacity.
- **Revocation:** 10 bounded tombstones. At full tombstone capacity, a
  requested removal cannot erase prior revocations; active record is
  quarantined and admission is rejected pending service recovery.
- **Journal:** 128 append-only event slots. Slot 129 is rejected; existing
  slots are not silently overwritten even after backend ACK.
- **Ingest queue:** target secure Hub owner configures 32 event entries.
  Queue-full input is dropped without a durable ACK; Node retries.
- **Runtime/session/health queues:** bounded target queues have independent
  overflow behavior; runtime session is rebuilt via rejoin.

Unbounded event history would consume finite flash and NVS metadata. Capacity
is currently an explicit refusal boundary, not an implemented archival or
automated cleanup policy.

## 9. Recovery matrix

| Condition | Expected behavior | Engineer action |
|---|---|---|
| Clean restart | Restore valid registry and journal; rejoin Nodes; rebuild volatile state | Check startup loaded counts, journal replay, then new session IDs |
| Unexpected restart | Same software restore path; in-flight RAM work is gone | Compare durable records and Node pending retry IDs |
| Corrupted registry | Hub security owner faults closed; do not admit Nodes as new | Preserve NVS blob/key provenance; use approved recovery, currently incomplete |
| Corrupted journal | Journal attach or replay fails; secure event admission does not start | Preserve partition and logs; do not erase evidence to force boot |
| Failed registry write | Candidate update does not replace live state; critical owner failure closes access | Inspect NVS write/readback and generation; verify old snapshot remains |
| Failed journal write | Return StorageFault; no durable ACK; event admission closes in target path | Check NVS partition/storage health; Node should retain/retry |
| Journal full | Reject new event and no durable ACK; Node retains it | Inspect slot count and archival/reclamation plan; no automatic free path |
| Revocation persistence | Snapshot commit precedes access removal; full tombstones quarantine/fail closed | Verify `access_stopped`, registry result and persisted tombstone |
| Node returns after Hub restart | Rejoin with newer authenticated session; old keys are not restored | Check registry session floor and rejoin transcript |
| Stale session after restore | Registry rejects non-increasing session | Inspect session allocator and saved `last_session`; do not lower floor |

## 10. Resource and flash considerations

All state is bounded: registry, tombstones, journal slots and wrapped blob
sizes have fixed limits. Journal writes occur once per newly accepted event;
duplicate retransmission does not write another slot. Registry writes occur
on enrollment, replacement, removal and accepted rejoin/session-floor update.
Liveness and health samples are RAM-only to avoid frequent flash writes.
Future reclamation, compaction and endurance analysis must account for event
retention and dedupe guarantees; deleting a slot too early could turn a late
retry into a second event.

## 11. Source files/classes

Paths are relative to `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/`.

- `firmware/hub/target/esp32/hub_security_link.*` — `HubSecurityLink::initialize`, registry restore, Home ID and journal-key derivation.
- `firmware/hub/components/registry/node_registry.*` — active/tombstone bounds, admission, rejoin, revoke and replacement.
- `firmware/hub/components/registry/registry_persistence.*` — `HubRegistryRepository` encrypted `GSRG` record and generation.
- `firmware/common/security/nvs_association_blob_store.*` — target NVS wrapped-blob adapter.
- `firmware/hub/components/storage/journal.*` — `HubJournal` slots, dedupe, commit status and cloud pending state.
- `firmware/hub/target/esp32/nvs_journal_slot_store.*` — `gs_journal` append-only NVS slot implementation.
- `firmware/hub/runtime/hub_runtime.*` — durable commit, reducer replay and volatile health/liveness maps.
- `firmware/hub/target/esp32/hub_runtime_adapter.cpp` — startup ordering, fail-closed admission and per-Node rejoin.
- `firmware/common/security/target_wrapping_key.*` — development target wrapping key source; production provider is separate work.

## 12. Verification boundaries

**IMPLEMENTED:** Bounded encrypted Node registry snapshot and event journal,
Hub startup restore paths, registry session/revocation checks, event dedupe,
and fail-closed behavior on invalid stored state.

**HOST_VERIFIED:** `tests/cpp/registry_persistence_validation.cpp`,
`node_registry_validation.cpp`, and `hub_journal_persistence_validation.cpp`
cover encrypted restore, conflict/capacity, revocation/session preservation,
duplicate, full, corruption and write-failure behavior. Hub host reducer
replay and exact duplicate handling are represented in validation evidence.

**TARGET_BUILD_VERIFIED:** ESP-IDF Hub build includes registry/NVS and
journal startup integration. This is not physical flash recovery evidence.

**PHYSICALLY_VERIFIED:** Historical HIL exercises its recorded firmware and
profile only; it does not establish current-HEAD persistent
registry/journal restart behavior. Treat only commit-matched evidence under
`evidence/hil/runs/` as physical verification.

**NOT_YET_PHYSICALLY_QUALIFIED:** Current-HEAD registry/journal restart,
corruption, NVS failure, revocation persistence, and sudden-power-loss
behavior.

**POWER-CUT QUALIFICATION:** Not established for registry snapshots, event
slots, generation progression or flash endurance.

**PLANNED / INCOMPLETE:** Safe journal reclamation/compaction, durable cloud
application ACK state, complete routine/config/timer checkpointing,
production protected key provisioning, anti-rollback and physical power-cut
qualification.

## 13. Engineer diagnostics

At boot, inspect Home ID load, Hub signer/key initialization, registry
repository status/generation and active/tombstone counts; the source currently
logs bootstrap failures and enrollment count, while additional generation
telemetry may need debugger/instrumentation. For the journal, inspect NVS
partition init, attach/restore result, `HubJournal::size()`, `persistent()`,
`storage_fault()`, slot index and commit result. For Node recovery, inspect
per-Node security `ready_node`, authenticated session and registry
`last_session`. Health/liveness are RAM-only: they begin unknown/offline until
current-session health or event traffic updates contact.

## 14. Known limitations

- Journal is finite, append-only and not reclaimed; full storage blocks new
  durable event admission.
- Cloud ACK state is not durably persisted and does not reclaim journal slots.
- Basic event-derived state is replayed; complete routine windows, settings,
  timers, full coverage history and per-Node liveness are not reconstructed.
- Production wrapping-key protection and Hub replacement/recovery procedures
  remain incomplete.
- Software write/readback is not a physical power-cut or rollback guarantee.
