# R1 Hub storage and data lifecycle — architecture ExecPlan

Date: 2026-10-07. Source: `cd8d126ab44689cc9c6ebbbe74e6dce058d4323b`, branch `feature/r1-hub-storage-lifecycle`.
Context preflight: **PASS**, local/canonical context `2026-10-07.001`.
Status: **PROPOSED; production integration STOP; isolated policy-neutral host primitives implemented**.
The initial architecture checkpoint changed documentation only. The later efficiency phase adds host-only primitives/tests/benchmarks and Makefile targets; production firmware, partitions, backend, PWA and hardware remain unchanged.

## 1. Problem, authority and evidence boundaries

The six-Node household cannot operate commercially with a shared 128-event lifetime. Backend completion and Node retirement currently do not free event slots. Increasing that constant would move the failure without resolving recovery, dedupe, outage, wear or reclamation.

Authority is the LOCKED decision log, R1 release contract, canonical domain requirements, then work state; implementation documents describe mechanisms rather than product acceptance. This plan proposes numerical budgets and mechanisms, **not newly approved requirements**. No context-version increment or LOCKED decision is made. Values such as 72 hours, 90 days and 5,000 events are not adopted.

Canonical sources read: `AGENTS.md`, `docs/product/{GHAR_SAJAG_PROJECT_CONTEXT,R1_RELEASE_CONTRACT,R1_WORK_STATE,CANONICAL_REQUIREMENTS_INDEX,P0_PRODUCT_REQUIREMENTS,DECISION_LOG}.md`, and `docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md`. Relevant supporting sources: `docs/design/{NODE_RETIREMENT_REPORT_PROTOCOL,HUB_REDUCER_CHECKPOINT,HUB_DURABLE_STATE_TRANSITIONS}.md`, persistence, routine and FOTA feature guides, production source, backend completion contract, and reconciliation/build evidence. Older guides contain stale wiring/cloud-completion statements; the code and current completion contract below establish implementation facts. This is not a canonical requirement conflict.

Code paths below use prefix `P = code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/`. Byte budgets use KiB = 1,024 bytes. Proposed encodings are explicit serialization sizes, never `sizeof(C++ struct)`. Physical NVS utilization, current image size and flash endurance are **not measured in this run**.

## 2. Locked requirements

Preserve GS-D001–012, GS-D016 and GS-D018: fresh-install R1; quality/security/durability; existing 4 MiB ESP32 Hub and ESP32-C3 Nodes; six Nodes sharing resources; indefinite operation through recycling; Hub not long-term database; backend history; connected near-real-time sync independent of storage pressure/PWA opening; backend-first PWA; offline sensing, alerts, durability and bounded learning; correctness-preserving chatter coalescing; reduced low-value detail rather than stopped safety; privacy enforcement.

Preserve authenticated ownership/domain checks, durable-before-ACK, lost-ACK retry, exact dedupe where required, reboot recovery, retained-event retirement, fail-closed corruption, bounded execution and versioned FOTA. Do not erase storage or change epoch to disguise fullness. Keep both OTA slots and embedded Node-image needs. Do not reopen passed physical fresh-install/ACK gates without an invalidating change. Legacy abandoned-format migration is not automatically required. BAT-C8 remains separately pending; this plan does not alter GS-D020 or GS-114.

## 3. Actual 4 MiB flash audit

Source: `P/firmware/hub/target/esp32/idf/{partitions.csv,sdkconfig.defaults}`. Defaults select 4 MB flash, custom CSV and application rollback. Exact CSV end is `0x400000` = **4,194,304 bytes**; no overlap. There is no generated build/partition binary in this worktree, so the generated table and actual device flash identification cannot independently be verified here.

| Area | Offset | Size bytes | Purpose / occupancy evidence | Required reserve for proposed design |
|---|---:|---:|---|---|
| Pre-boot area | `0x000000` | 4,096 | ESP32 reserved boot region; no artifact | Preserve |
| Bootloader envelope | `0x001000` | 28,672 | Standard ESP32 envelope ending at table; actual bootloader bytes unavailable | Preserve envelope; signed-profile fit later |
| Partition table envelope | `0x008000` | 4,096 | Default table placement, not a measured generated binary | Preserve one sector |
| `nvs` | `0x009000` | 24,576 (`0x6000`) | Home ID, signer/wrapping source, registry/association, system Wi-Fi state; exact live use unknown | Preserve entire partition; verify allocator/GC headroom |
| `otadata` | `0x00F000` | 8,192 | OTA selection/rollback metadata; live contents unknown | Preserve both sectors |
| `phy_init` | `0x011000` | 4,096 | PHY initialization partition; live occupancy unknown | Preserve |
| Alignment gap | `0x012000` | 57,344 | CSV unallocated before app alignment | Keep for boot/layout flexibility; not assumed available storage |
| `ota_0` | `0x020000` | 1,966,080 (`0x1E0000`) | Hub application, including embedded C3 FOTA image | Candidate build must include signatures/alignment and growth reserve |
| `ota_1` | `0x200000` | 1,966,080 (`0x1E0000`) | Alternate Hub application | Same requirement as A |
| `gs_journal` | `0x3E0000` | 131,072 (`0x20000`) | NVS-formatted authenticated durability store | GC/COW space mandatory; not all bytes are payload |

No separate security partition appears in the production CSV. Software AEAD wrapping does not establish production flash encryption/key custody. Ordinary NVS supporting model: registry 8,192 + association 1,024 + identity 160 = 9,376 raw bytes; proposed prior config model adds 6,144 = 15,520. These are document ceilings, **not current measured use**; remaining raw 9,056 bytes does not establish allocator fit. Do not double-count model components as measured blobs.

Current durability completion-contract model: normal 81,218 raw bytes, migration peak 87,314 of 131,072; modeled NVS entries normal 2,936, migration 3,605 of 4,032. Migration model leaves only 427 entries (10.59%). These are model estimates, not physical occupancy or allocator qualification. Earlier 77,122/83,218 estimates omit the later independent receipts.

Image evidence:

* `docs/hw/evidence/HW_M1_3_TARGET_BUILD/README.md` and `HW_M1_3_FINAL_SMOKE/README.md`: physically used historical Hub image **1,592,848 bytes**, SHA-256 `f48a455658cf59d4f3e6a857bac36360ca045da2fd890d9b23ce7438e779a7f1`; slot margin **373,232 bytes** (18.98%).
* `docs/hw/evidence/HW_M1_4_NODE_OFFLINE_RESILIENCE/README.md`: later target-build image **1,599,312 bytes**, margin **366,768 bytes** (18.65%); this table labels that build's physical qualification pending.
* Current baseline's qualified app size and margin: **UNKNOWN**. `P/firmware/hub/target/esp32/idf/build` is absent. Reconciliation evidence describes an ELF/stack audit but gives no current image byte count. Neither historical figure is promoted to current-HEAD size. Build/sign/embedded-C3 growth is a STOP gate before shrinking slots.

## 4. Current implementation facts

**CURRENT_IMPLEMENTATION_FACT**:

* `shared/include/gs/domain.hpp`: EventKey comprises physical device ID, logical source ID, origin session `u64`, sequence `u64`; canonical length-delimited key string. Origin session is distinct from authenticated transport session. Supported string maxima in journal codec are physical 64, logical 24, location 64 bytes.
* `firmware/hub/components/storage/journal.cpp`: event codec v2 has version/string-length bytes (4), variable strings (up to 152), five `u64` values (session, sequence, monotonic, occurred, received = 40), and 12 bytes for kind/sensor/uncertainty/battery/test/RSSI/aggregate presence. Ordinary maximum **208 bytes**; MotionSummary adds count `u32` and first/last `u64` = 20, maximum **228 bytes**. Accepted codec cap is 256. AES-GCM nonce/tag add 28; actual maximum v2 slot 256 bytes, defensive provider cap 284. Slot AAD is `GSJ1` plus slot `u64`.
* Secure target `hub_runtime_adapter.cpp` constructs `HubDurabilityOwner`, recovers/authenticates registry-bound state, migrates recognized legacy sources if necessary, constructs **DurableJournalSlotStore**, binds the owner to `HubRuntime(32,128)`, attaches journal, then replays before admission. The raw/HIL alternate `HubRuntime(32,1024)` is not the secure commercial path.
* Durable slot adapter stores causal event bytes in authenticated transition, four-slot tail, then archives batches into pending-effect chunks. Slot number is persisted in transition decision and first four bytes of effect ID. Archive IDs are derived from checkpoint generation with a reserved prefix. `rows()` reconstructs retained slot identities from checkpoint archives plus uncovered tail and permitted legacy sources.
* `durable_transition.hpp`: transition cap 1,332, checkpoint **4,549**, pending chunk 1,260, dedupe chunk 320, bitmap 384 bytes; four events per chunk, 32 archive refs and 32 dedupe refs, 16 pending effects. Current checkpoint schema 3, native-fresh schema 4. Prior documents' 4,514 cap predates current registry-domain fields.
* Checkpoint stores epoch/generation/covered ordinal, config version/hash, opaque reducer bytes, bounded effect/chunk/evidence refs, report snapshot reference, registry digest and migration flags. A/B checkpoints/selectors and authenticated child digests recover a selected root plus uncovered tail. Report snapshot banks are separately authenticated but selected through checkpoint ownership. Unknown/corrupt inventory cannot bootstrap a new empty installation.
* Attach scans 128 logical slots; rejects holes followed by records, invalid/authentication failures and duplicate keys. `HubRuntime::restore_from_journal()` replays every retained event with `local_minute=nullopt`; it restores only event-derived state, not a complete timer/config/routine model. Opaque checkpoint capacity is not evidence that a complete product reducer is populated.
* `HubJournal::commit` checks key membership first and returns Duplicate without payload comparison at that layer. DurableStore compares digests for newly submitted transitions against tail/evidence. The current slot adapter HMACs the **entire encoded DomainEvent**, including Hub receive time/RSSI, rather than the proposed immutable Node-origin projection. **Later integration must define that projection and route duplicate retries through digest validation before ACK**; key-only fast path is insufficient as proof of conflicting same-key safety. Existing lost-ACK qualification proves duplicate growth/retirement for its recorded valid retry, not this adversarial conflict case.
* Node queue/recovery cap is 32, covering sequenced Heartbeat NodeMessages as well as business events. Node saves encrypted pending snapshot before transmission and after retirement. NodeHealth frames have no EventKey and do not occupy journal slots. Reports describe complete pending keys, current origin and durable highwater, bound to epoch and enrollment generation; target selects/verifies report bank before ACK. Report ACK does not mean backend completion.
* `HubJournal::acknowledge_cloud` persists a 32-byte HKDF/HMAC receipt tied to installation, exact EventKey and immutable slot. `c000..c127` survive reboot. Valid legacy archive completion markers can publish missing independent receipts. Current completion bitmap has only 16 bits and cannot serve as a recycled global receipt map.
* Cloud completion does not erase payload/archive/evidence/receipt. Retirement reports do not authorize the current slot adapter to reuse a slot. Logical retained rows and RAM journal membership remain.
* Epoch is recovered from selected authenticated storage, not incremented on reboot/FOTA. Empty-history epoch helper is not authorization for destructive capacity recovery. Registry/enrollment binding and authenticated ownership precede ingest; unknown domain/version/corruption faults closed.

**Why event 129 fails:** after 128 distinct retained records, `records_.size() >= capacity_` returns `Full` before a write. Both durable and legacy slot adapters independently reject slot >127. All 128 records may be backend-completed and Node-retired; neither reduces `records_.size()`. Four-slot tail recycling/archive batching is not event-history reclamation.

**CURRENT_PRODUCT_REQUIREMENT:** none of these 128/32-ref implementation ceilings defines commercial lifetime. GS-D005/016 requires replacing the coupled append-only lifecycle while preserving qualified durability.

## 5. Proposed logical ownership and commit boundary

One bounded storage owner serializes durable transitions. Five responsibilities may share a wear-levelled segment store, with quotas/reserves preventing one class from consuming another's safety capacity:

| Class | Retain until | Authoritative content |
|---|---|---|
| A active correctness | Node certificate excludes key, and reducer recovery no longer needs input | Enrollment-scoped exact key/digest, complete latest pending certificate, bounded uncheckpointed transition tail |
| B materialized household | Replaced by verified newer same-domain snapshot/root | Config/registry binding, routine/door/inactivity state, durable alert intents, coverage evidence and application boundary |
| C backend outbox | Matching authenticated durable application COMMITTED, or explicitly approved summary substitution | Immutable canonical upload and stable effect identity; independent of Node retirement |
| D recent history/cache | Rolling budget/pressure eviction after A/B/C dependencies clear | Optional synced recent context/diagnostics; no sole correctness evidence |
| E learned aggregates | Replaced by verified newer model state | Bounded sufficient statistics, coverage/sample confidence and model version |

Ingest transaction commits immutable input, dedupe evidence, reducer delta/decision and durable delivery intent **before Node durable ACK**. Apply to RAM after commit; recovery replays committed deltas without emitting external effects. This can use one transaction record with references into outbox storage: partially written children are unreachable until transaction commit. Outbox is immediately schedulable once committed. Neither cloud availability nor history space gates local correctness. Critical intent overflow remains a product STOP, not an invented discard policy.

Full raw payload can be freed after its delta is checkpoint-covered and cloud obligation is complete/substituted, even while an exact key/digest is retained for lost ACK. A retired Node key can release A while its payload remains in C. Synced history may remain in D without remaining in A/C. These independent lifetimes are the essential change.

## 6. Six-Node workload and semantic representation

Evidence: target config GPIO4, 20 ms polls, 150 ms debounce, 1,000 ms retrigger; `components/power/power.{hpp,cpp}` ActivityEpisode has online quiet 45 s, max 300 s, offline idle 1,800 s. First Motion is durably recorded; repeats are RAM coalesced; closing emits a separately identified immutable MotionSummary only if repeats exist. Pending summary is bounded and may merge same-room repeats. RAM repeats may disappear on reboot: do not claim exact continuous occupancy/activity duration. NodeProtocolPolicy production health interval is **120 s**, HIL 60 s; contact defers health and outage may suppress it. Node outage profile is Hub-contact outage, **not backend outage**; backend-only loss must be budgeted with online episode rate.

| Source | RAW_EVENT_RATE | SEMANTIC_EVENT_RATE | CAN_COALESCE / rule | Safety priority |
|---|---|---|---|---|
| PIR | Electrical edges unbounded without sensor electrical spec; accepted Motion <=1/s/Node (518,400/day household conservative limit) | First + optional summary per episode; continuous activity <=2/300 s/Node (~3,456/day); short repeated bursts just over 45 s apart can approach 2/45 s/Node (~23,040/day) | YES for repeats in same room/episode; preserve first and separate immutable summary; never alter already transmitted payload | Activity evidence; may trigger rules; not an emergency inference |
| Reed | No qualified target source/rate bound | Open and close individually | NO for chronology; bounce may be qualified before identity allocation | Door concern / safety relevance |
| OK / Call Family | No physical control/rate bound | One per deliberate accepted action | NO across distinct actions; exact-key retry only | Explicit check-in / high priority assistance |
| NodeHealth | Up to 4,320/day household at 120 s absent deferral | Latest authenticated contact; persisted status transitions/optional aggregate | YES periodic diagnostics; NO distinct offline/online transition history within approved guarantee | Coverage safety; not resident activity or battery gauge |
| Battery | No battery ADC production field | No qualified battery event rate | Candidate threshold/hysteresis transitions only after telemetry contract | Coverage/device condition |
| Offline/online | Derived from health/coverage, no input EventKey | One per genuine state change, not per poll | YES unchanged state; flap summary only with approved loss/visibility semantics | Required safety eligibility |
| Alerts/timers | Rule decision/latch, no specified global max | Stable incident identity per qualified trigger/window | Retry same identity only; distinct incidents cannot be collapsed arbitrarily | Critical/concern according to approved rule |
| Control/security/config | Authenticated enrollment, revocation, mode/config, FOTA boundaries | One durable semantic state transition | NO distinct security decisions; unchanged diagnostics may coalesce | Correctness/security |
| Gap / MotionSummary | Gap on queue-loss policy; summary as above | Explicit loss marker/summary | YES only preserving affected time/count uncertainty; never claim complete history | Transparency/coverage |

No evidence supports a finite worst-supported rate for unqualified buttons/Reed/security churn. The following **workload envelopes are engineering scenarios, not measured households or universal guarantees**. Additional classes use one 128-byte equivalent record; larger critical payloads reduce duration proportionally.

| Scenario | PIR sessions / Node / day | Mean records / session | Other semantic records / household / day | Total records/day |
|---|---:|---:|---:|---:|
| NORMAL | 40 (plausible distributed room visits) | 1.5 (half have repeats) | 24 (health state, rules, control, door/button allowance) | **384** |
| HIGH | 160 (frequent visits through six rooms) | 1.75 | 96 | **1,776** |
| DESIGN_STRESS | 1,920 (bursts every 45 s over 24 h) | 2 | 192 | **23,232** |

Stress is a conservative steady-state episode envelope; boundary effects and room/config changes require burst headroom and rate controls. It is not a workload the flash is already qualified to sustain indefinitely. Continuous six-room chatter produces fewer semantic records than repeatedly ending episodes. With coalescing disabled, 518,400/day accepted-motion ceiling is a separate fault/lab envelope, not the commercial supported workload; all layouts below last only minutes at that rate. Capacity must not depend on applying coalescing *after* discarding an unresolved EventKey.

Session data preserves first observation, last repeat, additional count, source/zone and uncertainty. It does not prove a resident was continuously active between endpoints. Existing 5-minute night-visit merge does not itself authorize 5-minute suppression of all safety evidence. Exact learning formula, summary treatment by each rule, trusted-time conversion, missing-deadline handling and room/config changes need approval/equivalence tests before adjusting current episodes.

## 7. Active durability bound and retirement proof

At one instant, six complete Node pending sets contain at most **6 × 32 = 192 distinct keys**, across at most 32 prior origin sessions plus current per Node. Retransmissions do not add keys. Sparse allocation gaps, out-of-order ACKs and Heartbeat keys make greatest-sequence-only watermarks unsafe. An absent covered key in a verified complete pending certificate is stale/impossible; listed keys require exact digests. Keep enrollment generation and physical binding; rejoin changes transport session without necessarily closing origin. Revoked identity evidence is releasable only after durable authentication revocation, independently of backend work.

**192 is not the unconditional current Hub evidence bound.** ACKed-but-unreported keys accumulate during lost/stale reports while the Node refills its queue. Current implementation contains no admission-credit proof bounding this gap; without the 128 ceiling, accumulated exact evidence has no finite theoretical limit. A time-based report interval alone is not a proof under arbitrary report loss.

Proposed protocol/admission invariant: per Node reserve its 32 listed possibly committed keys plus **32 new distinct commitments after the selected complete certificate**. At 32 new keys, request/process a fresh authenticated complete report before admitting another new key; duplicates and report/control traffic retain dedicated capacity. Persist credit basis atomically with report selection and reconstruct it after reboot. Refused sequence allocations do not consume committed-key credit. Never reclaim a listed digest on age or backend ACK. Persist updated certificates before pruning.

This produces **6 × (32 + 32) = 384** maximum live exact entries. Recommend physical room for **416 entries**: 384 plus one bounded 32-item Hub ingestion/transaction batch as COW engineering headroom, not permission to exceed the per-Node credit invariant. Serialized evidence item is current 53-byte key/digest padded to **64 bytes**; 416 × 64 = **26,624 bytes**. Report logical bound for six is 18 + 6×605 +28 = **3,676 bytes**, provisioned as 4,096 per snapshot, three versions = 12,288. If ten target registry slots remain accepted, snapshot max is 6,096 and protocol bound becomes 640 before batch reserve; commercial six-Node admission must be explicit, or budgets revised. Do not silently rely on six while accepting ten.

Additional active allowance: 32 ×256 =8,192-byte bounded transaction page set plus metadata/relocation space. Active 96 KiB quota leaves 51,200 bytes after these three allocations (26,624 +12,288 +8,192). That remaining space covers record authentication/page headers, two-root reachability and COW copies; it is not an advertised event capacity. Minimal 64 KiB leaves 18,432 bytes and is fragile.

Report-loss gating is necessary for proof but can eventually backpressure Node event admission. **REQUIREMENT_GAP:** approve report transport progress/retry priority and the supported failure envelope; arbitrary permanent retirement-protocol failure cannot give both finite exact-key retention and unlimited new commitments. Genuine hardware/storage faults still fail closed. A floor alone cannot replace exact evidence behind an old pending key; complete-set complement proof can retire later ACKed keys without closing that floor.

## 8. Compact materialized state and learning

Propose separately versioned state children referenced by a small root; do not enlarge today's 4,549-byte checkpoint implicitly. Snapshot envelope budget **8,192 bytes** = reducer 2,048 + learning 5,632 + schema/root/integrity allowance 512. Final codec must reject over-limit strings/lists and prove these sizes; this is a candidate ceiling, not a serialized implementation.

Reducer 2,048-byte candidate packing:

| Component | Bytes | Required fields |
|---|---:|---|
| Policy binding/mode/time | 192 | Config/registry hashes/generations, timezone/rule version, mode, window ID and clock uncertainty; clock starts untrusted after reboot |
| Six zone/coverage slots | 6×128 =768 | Assignment ID, last usable event/contact epoch, sensor fault/eligibility, session/last activity anchor, session accumulator; uptime online leases not restored |
| Activity reducer | 256 | All ActivityRuleState anchors, night counters, morning flags, inactivity/door latches; last activity and door cause IDs as full recoverable compact binding/session/sequence tuples |
| Routine window | 256 | Start/end/grace, qualifying-zone mask, activity/OK flags, decision/incident identity, bounded sufficient first/last evidence rather than unbounded evidence_ids |
| Current incident state | 384 | Eight 48-byte current rule-instance descriptors; external delivery payload lives in C, no unlimited alert history |
| Header/overflow reserve | 192 | Validity, schema, boundary, bounded overflow diagnostics |
| **Total** | **2,048** | Rule-instance count/string/config limits require approval |

Learning state is bounded; it does not store raw PIR history:

| Component | Calculation | Bytes |
|---|---|---:|
| Per-zone weekday/weekend hourly histogram | 2×24×u32 | 192/zone |
| Six metrics for two day classes | 2×6×24: mean 8, M2 8, count 4, trend 4 | 288/zone |
| Current day/session sufficient state | First/last epoch, counts, duration proxy, coverage and flags | 64/zone |
| Seven recent daily summaries | 7×24 | 168/zone |
| Six zones subtotal | 6×712 | 4,272 |
| Household 28-day summaries | 28×32 | 896 |
| Model/config/sufficiency parameters | Fixed block | 192 |
| Anomaly/confidence state | Fixed block | 128 |
| Coverage/exclusion counters | Fixed block | 128 |
| Model header | Version, sample epoch, flags | 16 |
| **Total** | | **5,632** |

Metrics candidates: first activity, last activity, session count, observed-duration proxy, night visits and explicit check-ins. Hourly counts and weekday/weekend statistics support local trends without interpreting missing coverage as inactivity. Use versioned fixed-point or specified finite IEEE encoding, saturating counters and explicit invalid/overflow state. Circular time-of-day handling is required for midnight; linear mean alone is wrong. Formula/decay/sample sufficiency/anomaly thresholds are **OPEN**, not hidden implementation choices. Seven/28-day summary windows here are memory-budget proposals, not history-retention promises. Longer cross-month raw timelines, caregiver reports, personalized longitudinal analysis and cross-household analytics belong in backend.

Persist learning updates as compact delta transactions with safety decisions; batch large snapshots. Checkpoint after **256 transitions or six hours**, and earlier for bounded-tail pressure/controlled shutdown, as an initial wear model. Retain up to 256 replayable transitions: worst reserved 256×256 =64 KiB must be available across active/history/outbox shared log, not merely the 8 KiB immediate transaction pages. If records exceed 256 bytes, use multi-record transactions and charge actual bytes. This maximum tail is included in live-space admission/GC checks, with history sacrificed first. Alert intents and config changes are durable immediately; batching snapshot writes cannot defer their durability.

Generation root includes installation digest, epoch, format, reducer/model versions, config/registry references, covered global ordinal, child hashes, segment mapping, minimum compatible reader/writer and length. CRC detects tears quickly; AEAD/HMAC under domain-separated installation keys authenticates header and payload. Segment ID/generation/record ordinal must prevent nonce reuse; checked counters refuse overflow rather than wrap. Two valid roots plus a staged third state image preserve recovery during publication. At most three 8 KiB state images plus roots consume <32 KiB; recommended 48 KiB state quota provides another 16 KiB for relocation and metadata. Fallback is permitted only when the root/commit protocol proves the older generation still covers all acknowledged work through replayable tail; never fall back to an older snapshot that loses acknowledged events.

## 9. Backend outbox and completion

Current `components/cloud/cloud_sync.cpp` provides priority (CallFamily first), per-key bounded-delay backoff 1/5/30/120/300 s, canonical request encoding and authenticated matching COMMITTED checks. It writes local completion only after backend application acceptance; PUBACK is insufficient. **No production caller/CloudBackendTransport binding was found in Hub runtime/target**. The portable component and host tests do not establish automatic deployed near-real-time upload.

`backend/ghar_sajag/durable_commit.py` and migration 008 use household+physical+logical+origin+sequence uniqueness and canonical payload SHA-256. File SQLite, foreign keys and FULL sync are prerequisites; event, incident and notification-outbox writes commit together before COMMITTED. Same key/different payload conflicts. Provider delivery is separate and not caregiver acknowledgement.

Outbox retry must preserve **exact normalized request**, including original hub_received_at, location and payload, because backend fingerprint includes these. Mutable telemetry/RSSI/time regeneration on retry is unsafe. Compact identity references may be used only while immutable assignment/installation dictionary versions remain durable until completion. Never resolve an old event against today's renamed room or replacement Node.

Candidate common compact Node outbox record **128 bytes**:

* 16-byte framing (type/schema/length/ordinal), 8-byte enrollment/assignment reference, 16-byte session/sequence, 24-byte monotonic/occurred/received times;
* 12-byte kind/sensor/flags/uncertainty/battery/RSSI block, 20-byte summary extension, 28-byte nonce/tag, 4-byte CRC = 128. Commit indication occupies the 16-byte framing block; the transaction commit record is separately charged to the transaction-log budget.

This reconstructs current bounded Node payload through an immutable dictionary. Variable rule/security payloads require 256-byte or multi-record entries; budget them as multiples of 128. Header AAD binds installation/epoch/record generation. A summary substitution is a **new immutable effect**, never mutation of an uploaded EventKey. It needs backend summary/gap identity/schema/ACK support not currently established. Current API cannot simply accept many-to-one activity sessions under an old constituent EventKey.

Connected: worker wakes on commit and connectivity, sends bounded batches without PWA/pressure dependency. Backfill automatically, with reserved service for fresh critical work and bounded fair service for oldest normal backlog. Persist completion deltas (candidate 32-byte compact records with stable generation-bound mapping) before making payload reclaimable; no completion evidence may refer only to a reused physical slot. Lost reply or power before completion yields identical retry; backend idempotency handles it. Authentication/authorization, request/reply matching, conflict quarantine/diagnostics and deployed production transport remain gates.

Outage: finite normal FIFO quota plus critical reserve. There is no finite exact-history guarantee for infinite outage. The proposed normal record capacity calculations below are **full-detail horizons**, after which approved summaries/loss markers must replace lower-value detail. Summary data allows bounded aggregate backfill, not reconstruction of every discarded transition. Extreme-outage critical incident saturation is unresolved: reserving flash delays it, does not prove indefinite critical chronology. Without approved bounded incident/summary semantics, architecture is not implementation-ready.

## 10. Candidate layouts and byte budget

Keep all addresses below `0x20000` and NVS/security unchanged. Balanced and maximum layouts require an approved fresh-install/service partition transition; ordinary app OTA cannot safely be presumed to relocate partitions. No CSV edited.

| Layout | OTA A offset / size | OTA B offset / size | Lifecycle offset / size |
|---|---|---|---|
| MINIMAL_CHANGE | `0x20000 / 0x1E0000` | `0x200000 / 0x1E0000` | `0x3E0000 / 0x20000` (128 KiB) |
| BALANCED_R1 | `0x20000 / 0x1C0000` | `0x1E0000 / 0x1C0000` | `0x3A0000 / 0x60000` (384 KiB) |
| MAX_OFFLINE_RESILIENCE | `0x20000 / 0x1B0000` | `0x1D0000 / 0x1B0000` | `0x380000 / 0x80000` (512 KiB) |

| Allocation KiB | Minimal | Balanced | Maximum |
|---|---:|---:|---:|
| OTA A | 1,920 | 1,792 | 1,728 |
| OTA B | 1,920 | 1,792 | 1,728 |
| NVS/security | 24 | 24 | 24 |
| Boot/table/OTA metadata/PHY/alignment envelope | 104 | 104 | 104 |
| Active correctness | 64 | 96 | 96 |
| State/checkpoint/routine | 32 | 48 | 48 |
| Backend outbox | 16 | 160 | 272 |
| Recent history | 0 | 48 | 64 |
| Cleanup scratch | 8 | 24 | 24 |
| Free operational reserve | 8 | 8 | 8 |
| **Total** | **4,096** | **4,096** | **4,096** |

These are **raw segment-store quotas**, not NVS payload capacities. Recommended low-level store is a bounded authenticated sector log with explicit GC, keeping NVS for identity/registry. Leaving lifecycle NVS-formatted requires a separate entry/GC budget and cannot use these capacities unchanged. Physical scratch has six sectors balanced/maximum: transaction relocation, victim copy and roots; algorithm must prove peak live set fits this reserve.

Sector model: 4,096 bytes, 64-byte header; 31×128-byte outbox records (3,968), 64 bytes additional packing margin. Reserve at least 20% outbox sectors, rounding up, for critical delivery: Minimal 4 sectors−1=3 normal; Balanced 40−8=32 normal; Maximum 68−14=54 normal. Completion metadata is separately charged to active/cleanup shared metadata reserve and GC live-space calculation. Capacities do not include oversized critical records, dictionary inflation or pathological fragmentation.

History candidate **96-byte record**: framing 16 + immutable binding ref 8 + EventKey session/sequence 16 + occurred/received 16 + semantic fields 8 + nonce/tag 28 + CRC4 =96. MotionSummary extension requires 128; raw replay inputs remain in correctness/recovery log until checkpoint, not lossy history. A sector fits 42 ordinary history records. Therefore ordinary history capacity balanced 504, maximum 672; all-summary capacity falls to 372/496. Optional history is never promised during pressure/outage.

| Derived property | Minimal | Balanced | Maximum |
|---|---:|---:|---:|
| Conditional active protocol bound / physical entries | 384 / 416 (tight) | 384 / 416 | 384 / 416 |
| Normal outbox equivalents | 93 | 992 | 1,674 |
| Full-detail offline NORMAL | 5.812 h | **62 h (2.583 d)** | 104.625 h |
| Full-detail offline HIGH | 1.257 h | **13.405 h** | 22.622 h |
| Full-detail offline STRESS | 5.76 min | **1.025 h** | 1.729 h |
| Ordinary local history NORMAL / HIGH / STRESS | None | 31.5 h /6.811 h /31.24 min | 42 h /9.081 h /41.65 min |
| Learning / checkpoint image | 5,632 /8,192 B, tight COW | 5,632 /8,192 B | 5,632 /8,192 B |
| Historical 1,599,312-byte image margin | 366,768 B | 235,696 B | 170,160 B |
| Current baseline image margin | UNKNOWN | UNKNOWN | UNKNOWN |

Horizons = normal record count / scenario rate ×24 hours. They start with empty outbox and are not approved duration guarantees. History depths are best-case ordinary-record capacities immediately after recovery-tail dependencies clear; live tail/COW may consume that shared space, reducing optional depth to zero. Minimal cannot hold the proposed 64 KiB maximum replay tail alongside live correctness/COW; it requires a smaller tail/earlier checkpoints and another wear proof, so is **not feasible under the complete recommended cadence**. Balanced/maximum can borrow recent-history space for the tail, but must prove peak coexistence of active evidence copies, 64 KiB tail, roots and full critical outbox in the allocator model. Backfill must drain faster than ongoing production; require measured service rate greater than supported event rate plus outage-recovery target. Critical reserve balanced is 8×31=248 common equivalents, fewer for 256-byte alerts; it is not a guaranteed number of incidents without the final effect schema.

**Recommendation: BALANCED_R1 as a conditional fresh-install candidate.** It preserves more historical OTA headroom than maximum and yields useful normal outage buffering; it does not support a universal multi-day six-Node high/stress guarantee. Minimal provides too little outage/recovery/GC headroom; maximum trades another 128 KiB of dual-slot growth margin for only 682 normal records. Do not choose maximum without measured signed Hub+embedded C3 fit. Proposed image reserve rule: at least **128 KiB after signed/padded candidate and embedded Node image**, subject to product review; current growth could invalidate every smaller-slot option.

4 MiB is **arithmetically plausible for bounded local safety and modest semantic buffering**, not proven sufficient for every unresolved requirement. Unlimited exact unsynced history is impossible on any finite flash. Final acceptance depends on outage/full-detail promise, summary priorities, reducer limits, reader compatibility, measured image/RAM fit and GC/wear proofs. Hardware migration is not proposed.

## 11. Storage-pressure proposal — approval required

Thresholds are proposed on usable normal outbox/live-space occupancy, with one-segment hysteresis; scratch/critical allocations are excluded from normal availability. Fragmentation/free-sector checks can escalate earlier than percentage thresholds.

| Tier | Candidate trigger | Allowed action / invariants |
|---|---|---|
| NORMAL | <70% normal quota, safe COW free space | Near-real-time upload; roll optional synced history; checkpoint on bounded cadence |
| HIGH | >=70% | Evict synced locally-unneeded history first, accelerate backfill/GC; omit repetitive diagnostic detail only under approved policy |
| CRITICAL | >=90% or insufficient normal transaction room | Convert eligible **unsynced low-value** motion detail to immutable approved summary + explicit gap/provenance; preserve local reducer/dedupe; reserve critical effects |
| EMERGENCY_RESERVE | Normal quota exhausted | Local sensing/rules/learning continue using bounded active/state storage; critical intents use protected reserve; maintain durable loss-range summaries; do not ACK a transaction lacking its required durable intent |

Unresolved key/digest, uncheckpointed reducer input, committed alert intent, unsynced critical alert and currently selected routine state are **not age-evictable**. Already synced optional history is reclaimable when no root/log consumer references it. Normal unsynced semantic records can be replaced only under GS-D014/017-approved meaning and backend ACK contract. Alert resolution does not erase earlier chronology. Privacy/consent may require different retention/redaction semantics; no invented deletion policy here.

**REQUIREMENT_GAP:** exact critical/normal priority, minimum explicit-action/door chronology, critical exhaustion, coverage-loss representation, ordinary outage guarantee, gap display and consent retention. Without those decisions, emergency behavior cannot be implemented faithfully. Infinite outages with infinitely many distinct critical incidents require either approved bounded representation or finite full-detail guarantees; flash reserve alone is insufficient.

## 12. Crash-safe reclamation and recovery model

Use 4 KiB sectors with installation/format/epoch, segment generation, role, first ordinal and authenticated header; records have length/type/ordinal, AEAD, CRC and a final commit indication. Append-only transaction commit binds all children/deltas/delivery intents. Completion/retirement are append-only deltas, not unsafe in-place bit flips. CRC is not authentication. Fresh generation prevents erased-slot aliasing; never wrap ID/nonce domains.

Root selection: write/readback children → write/readback alternate root → append authenticated activation/selector → verify recovery → advance second recoverable root to cover live changes. Every ACKed input has a reachable committed transaction, even before checkpoint. A committed tail cannot be dismissed as an orphan because a checkpoint is older. Never choose roots merely by largest unauthenticated number. Unknown committed records, contradictory roots or unrecoverable authenticated references fail closed.

Reclamation proof considers **both recoverable roots plus committed tail** and all five owners. Copy live victim records to scratch/fresh sectors; commit relocation mapping; publish/verify roots so neither recovery path depends on victim; persist retire intent; only then erase victim. The retire intent is authoritative before erase, not an after-erase bookkeeping prerequisite. Following erase, verify erased state and append free-generation record. Interrupted erase is quarantined and re-erased only when retired mapping proves it has no live references. Reclaiming a generation cannot reset storage epoch or event counters.

| Power loss point | Recovery obligation |
|---|---|
| Before record/transaction commit | Ignore provably uncommitted tail; no durable ACK; Node retries |
| After event transaction commit, before ACK | Replay delta once; retain exact digest; retry gets validated durable duplicate ACK |
| Before state application | Commit is authority; replay after checkpoint boundary |
| After RAM application, before checkpoint | Replay once from older checkpoint; no direct external emission; deliver persisted intent |
| Before checkpoint activation | Old selected root plus committed tail; staged valid children are pinned or safely orphan-classified |
| During root/selector write | Validate marker/authentication/readback; choose only provably recoverable committed generation |
| During copy/segment reclaim | Original victim remains live until both root dependency sets have moved; incomplete copies not authoritative |
| After retire commit, during erase | Victim is not needed; quarantine incomplete erase; complete cleanup from durable intent |
| After erase, before free metadata | Retire intent proves dead; treat as unavailable until erase verification/new generation commit |
| During backend completion | Partial/uncommitted completion keeps payload; committed matching receipt allows reclaim only after root/tail proof; identical retry resolves external/local gap |
| During report selection/pruning | Old report/digests retained until new certificate is durably selected and both root dependencies advance |

Boot scans bounded sector headers/commit chains, validates roots and children, reconstructs live tail/receipts/reports, resumes retirement intents and rebuilds bounded indexes. Yield between independent sectors; no unlimited whole-history replay. Rebuild RAM reducer without resending provider side effects. Reject clock/coverage trust until fresh authenticated contacts and trusted time. An invalid acknowledged transaction is corruption requiring fail-closed preservation, not silent rollback to an apparently empty root.

This is a proposed proof outline; no power-cut proof is claimed. Implementation must specify byte-level atomicity assumptions, maximum live victim copy, tail space and selector recovery before coding product admission/reclaim.

## 13. Flash wear and bounded runtime

No flash-chip endurance/data sheet is present as qualification evidence here. Use **10,000 erase cycles only as a sensitivity example**, not the device's rated life. A sector log avoids NVS blob write amplification and hot per-event checkpoints, but actual writes, GC copies and available wear pool must be instrumented.

Initial per semantic record model: transaction 256 + outbox128 + optional history96 + completion32 + compact evidence64 = **576 bytes**, excluding retirement reports, snapshot/dictionary changes and authentication padding beyond these envelopes. Evidence can share a transaction, so this deliberately double-charges rather than claiming a measured optimum. Retirement requires durable reports: batch at up to 32-key credit boundaries, and append compact report-change deltas rather than rewriting a 3,676-byte full snapshot per ACK. Extra tiny delta operations and low-rate control events remain unmeasured. Duplicates/retries write nothing unless retirement/completion projection changes.

Two 8 KiB snapshot publications per 256 transitions or six-hour limit: NORMAL 4/day, HIGH 7/day, STRESS 91/day (ceil envelope). The six-hour clock assumes trusted scheduling; tail byte pressure may force earlier snapshots. Logical demand before report/dictionary traffic:

| Scenario | Event bytes/day | Snapshot bytes/day | Total logical bytes/day | At 2× GC write amplification |
|---|---:|---:|---:|---:|
| NORMAL 384 | 221,184 | 65,536 | 286,720 | 573,440 |
| HIGH 1,776 | 1,022,976 | 114,688 | 1,137,664 | 2,275,328 |
| STRESS 23,232 | 13,381,632 | 1,490,944 | 14,872,576 | 29,745,152 |

If perfectly spread across the 384 KiB lifecycle store, these correspond to about **1.46 /5.79 /75.65 whole-pool erase cycles/day**. At the hypothetical 10k endurance: ~18.8 years /4.7 years /132 days. Real quotas restrict wear distribution: snapshot traffic alone over 48 KiB yields ~1.33/2.33/30.33 cycles/day before GC; fixed root sectors can be far worse. Rotate root/selector journals through wear-managed metadata sectors; avoid two permanently hot sectors. Cold long-lived correctness data can pin sectors; a measured wear-balancing policy is required. Wear amplification 2× is an assumed target, not an established upper bound under 90% live occupancy; GC amplification can be much larger.

Cloud outage eliminates receipt writes temporarily but pins outbox records and increases relocation pressure; fill duration alone is not lifetime qualification. Pressure summaries should bound long-outage writes, but only after policy approval. Do not rewrite giant report/snapshot blobs for every event/ACK. Sustained stress is not endurance-feasible as currently budgeted for a multi-year claim; approve sustained-rate envelope/compaction strategy and verify flash rating. “Indefinite lifetime” means no finite-event-count exhaustion, not infinite physical endurance.

Also verify RAM: current secure owner stack is 81,920 bytes and nested stack evidence is substantial. Do not copy snapshots/reports/sector sets onto nested stack frames. Bounded indexes, heap minimum, replay slices, ESP-NOW scheduling and backend worker contention require later measurements.

## 14. FOTA, rollback and migration

Current schema caps cannot hold the proposed combined 8 KiB state image. New child schema/root references are a storage-format transition; old firmware cannot be assumed to decode or safely ignore them. Current partition change also changes OTA B address. No app-only OTA repartition is authorized by this plan.

Preferred R1 rollout: approved **fresh-install** partition/image bundle, stable new format, both OTA images supporting its readers/writers. Existing physically qualified devices/evidence remain intact. Updating a current-format installation is a distinct supported-format preservation problem: either preserve a reversible old-format view until candidate health/rollback qualification completes, or ship a bridge release capable of reading/writing both representations before destructive reclaim. Partition relocation may require an approved service installation and backup/restore, not a bridge app alone.

Root advertises minimum compatible storage reader/writer and reducer/model version; enforce firmware eligibility before activation. Persisting a field ignored by old firmware does not enforce rollback safety. Signed-image/downgrade/version authorization and bootloader behavior must prevent selecting an incompatible reader **before any irreversible source deletion**. Do not disable rollback as an expedient or burn eFuses here. New snapshot schema activation and first old-format reclaim are separate commit points; prove every interruption and fallback path. Normal reclaim retains epoch; deliberate format/epoch migration transfers keys/receipts/pending state with authenticated domain continuity, never clears them.

Existing current-format ACKed events and Node pending identities must be preserved on any supported upgrade. Abandoned development formats remain optional. This does not reopen fresh-install durability without cause; reducer/reclaim/wire/FOTA changes specifically invalidate relevant recovery boundaries and will need focused regression qualification later.

## 15. Legacy migration test classification

`docs/progress/R1_WORKTREE_RECONCILIATION_20261007.md` records `hub-journal-migration-host-test` failing at **“clean migration commits”**, identically at untouched starting commit `4026e10`. Current decision log records it as deferred. No test rerun or modification was needed for this architecture analysis.

Classification: **HISTORICAL_LEGACY**, optional compatibility test; `BUG_CLASSIFICATION=DEFER_POST_R1`, sources GS-D001/release fresh-install contract. Recommend preserve it under an explicit optional compatibility gate, outside mandatory fresh-install R1 gate. Do not report a broad validation target green while it includes this known failure. If investigation shows that fixture is also required by a supported current-format transition/fresh install, reclassify that specific dependency as R1_REQUIRED; abandonment classification cannot waive loss of current-format ACKed state.

## 16. Implementation impact map — later work only

Paths relative to P unless explicitly repository-root. Tests listed are future requirements, not executed results.

| PATH | CURRENT_ROLE | PROPOSED_CHANGE | RISK | TESTS_REQUIRED |
|---|---|---|---|---|
| `firmware/hub/components/storage/journal.{hpp,cpp}` | Retained vector/key membership and slot-bound receipt | Replace lifetime vector with independent A/C/D ownership; exact digest validation before duplicate ACK | Lost ACK / conflicting key / RAM bounds | Dedupe conflict, six-Node lost ACK, reused-slot identity |
| `firmware/hub/components/storage/durable_journal_slot_store.*` | 0..127 transition/archive facade | Replace immutable slot mapping with generation/ordinal logical records; independent reclaim dependencies | Recovery/receipt aliasing | Many lifetimes, archive/reclaim interruption |
| `firmware/hub/components/storage/durable_transition.*` | Four-tail, A/B checkpoint, bounded refs | Versioned child state/root/segment transaction, bounded larger replay tail | Schema/atomicity/stack | Codec limits, roots, torn commits, every fault point |
| `firmware/hub/components/storage/{hub_durability_owner,node_retirement_snapshot}.*` | Epoch/ownership/report recovery | Persist credit basis, report-delta selection, pruning only with both-root proof | Dedupe retirement / stale certificates | Report loss/stale/same-gen conflict, reboot, old sessions |
| `firmware/hub/target/esp32/{nvs_durable_blob_store,nvs_store_inventory,nvs_durable_key_codec,nvs_journal_slot_store}.*` | NVS provider/inventory and legacy reader | New segment provider boundary; retain legacy reader only as approved transition requires | Flash driver/power cut | Inventory unknowns, partial erase, physical allocation |
| `firmware/hub/target/esp32/idf/partitions.csv`, sdkconfig/build metadata | Current dual slots | Approved fresh-install layout only, generated-table and signed-size checks | Unbootable/overlap/embedded image | Both slots, signatures, bootloader/table, build size |
| `firmware/hub/runtime/hub_runtime.*`, `shared/include/gs/rules.hpp`, `shared/src/rules.cpp` | RAM reducer/events/timers | Complete state serialization, durable config/timer/effect decisions, bounded evidence | Caregiver semantics/time | Checkpoint equivalence, late events, clock/privacy/coverage |
| `shared/include/gs/domain.hpp`, routine/coverage components | Domain/config/state | Bounded identities/evidence/model sufficient state with explicit policy limits | Requirement drift | All configured rule/state maxima and unknown coverage |
| `firmware/hub/components/cloud/cloud_sync.*`, Hub target adapter | Portable cloud driver; no live caller found | Dedicated production authenticated transport, independent outbox scheduler/completion | Lost cloud work, starvation | Near-real-time/outage/backfill/conflict/reboot |
| `backend/ghar_sajag/{durable_commit,ingest}.py`, migrations/API auth boundary | Exact-event transaction/idempotency | New Hub-effect/summary/gap identities and immutable completion contract if approved | Duplicate incidents/misleading history | Atomic backend commit, same-key conflict, summary replay |
| `firmware/common/transport/node_retirement_protocol.*`, Node runtime/recovery/target | Complete pending-set certificate | Admission/report credit negotiation and fair report progress if required; preserve 32-key recovery | Queue blocked/report loss | Six Nodes, sparse gaps, old origin, mixed Heartbeat keys |
| Node `components/power/power.*` | Existing activity episodes | Change only if approved equivalence/storage policy needs it | Missing activity/safety semantics | First-event durability, summaries, reboot/room/time boundaries |
| `firmware/hub/target/esp32/idf/main/fota_sender.*`, common FOTA/boot policy | Embedded C3 and secure transfer | Measure image growth; enforce compatible reader/writer release transition | Rollback data loss | Candidate rollback before/after storage commit |
| `tests/cpp/*durable*`, `*retirement*`, `*journal*`; Python models; `tools/sim/local_lab.py` | Existing host proofs / lab state | Deterministic bounded flash model, lifecycle fault injector, long-run six-Node replay | False confidence | Seeded power-fail matrix, conservation and bounds |
| `app/src/features/home/index.mjs`, backend/PWA status API | Backend timeline/state | Show approved summary/gap, freshness/backfill state from backend; no open-trigger upload | Misleading caregiver presentation | API/UI stale/summary chronology and incident preservation |

No adjacent feature repair is authorized. Newly identified gaps are triaged below, not silently implemented.

## 17. Validation strategy and later execution sequence

1. **Decision gate:** approve open policy/identity/rate/FOTA limits; record LOCKED decisions and update canonical context version/commit before dependent implementation. Define exact record codec and compatibility matrix first.
2. **Host storage model:** actual 4 MiB layout/quotas, page framing and flash 1→0 writes/partial erases, bounded indexes, allocator/GC, both-root liveness. Prove byte-level transaction and nonce rules. Fill/reclaim **at least 10,000 previous 128-event lifetimes**, then longer accelerated multi-year NORMAL/HIGH simulations; no count growth or epoch-reset workaround.
3. **Protocol host:** six interleaved Nodes with 32 pending each; lost ACK, exact/conflicting retry, sparse gaps, out-of-order delivery, multiple old origins, lost/stale reports, credit exhaustion/recovery, revocation/replacement, mixed Heartbeat and NodeHealth exclusion, persisted epoch transitions and overflow. No late retired frame may create effects.
4. **Reducer/learning host:** checkpoint+tail equals full bounded-reference replay for events/config/timers/modes/registry; crash before/after application; confidence/coverage/trusted-time exclusions; no unbounded evidence vectors; routine recovery and midnight/weekday boundaries. No external side effect directly emitted on replay.
5. **Cloud host:** production-like transport fixture with durable backend; outages exceeding every capacity, automatic recovery without new PIR/PWA open, exact immutable retry, lost completion replies, permanent conflict, fresh-critical/backlog fairness, byte-sized variable payloads, approved summary/gap semantics, critical reserve exhaustion and no local-safety coupling.
6. **Crash matrix:** inject failure before/within/after every write, commit, readback, checkpoint/selector, report prune, relocation and erase; failed API with exact persisted bytes; reboot fresh objects each time. Validate conservation: every ACKed key has dedupe/retirement proof, every required effect has durable pending/completion proof, every applied transition has recoverable state/tail. Corruption must not authorize empty bootstrap or false fallback.
7. **Static/target build later:** generated partition table, bootloader/signature fit, both Hub OTA slots including embedded signed Node image, minimum 128 KiB proposed image reserve, RAM/stack/heap/watcher budget, finite recovery/reclaim scheduling. No physical events before host qualification.
8. **Target storage qualification later:** allocator/page instrumentation, erase counts per sector, GC amplification, max live relocation, controlled power cuts and current-format rollback. Controlled physical events only after host/build gates and explicit campaign scope. Reuse existing qualified evidence; repeat only boundaries invalidated by the implemented change. BAT-C8 physical qualification remains separate.

Run for this analysis: context preflight, source/evidence reads/searches, arithmetic checks and `git diff --check` only. No builds, host mutation tests, HIL, flashing or synthetic PIR.

## 18. Open decisions, blockers and explicit STOP conditions

| Open decision / issue | Classification / authority | Needed closure |
|---|---|---|
| Full-detail outage promise and overflow summary/gap visibility | REQUIREMENT_GAP; GS-D013/014/017 | Approve scenario/byte-duration guarantee and permitted lost detail |
| Critical incidents/door/explicit action retention and reserve exhaustion | REQUIREMENT_GAP; GS-D009/012/014 | Bounded representation that preserves local safety and truthful chronology |
| Report progress and new-key credit limits, six versus ten admission | R1_BLOCKER design dependency; GS-D004 and durability invariants | Prove bound and supported protocol failure envelope |
| Complete reducer field/config/rule-instance limits, learning formulas/coverage/time behavior | REQUIREMENT_GAP; P0, GS-D010/018 | Product-equivalent sufficient state; no fabricated defaults |
| Summary/derived Hub-effect identity, payload/ACK schema and deployed auth transport | R1_BLOCKER integration; GS-D007/008, completion contract | Explicit backend transaction/idempotency/production caller contract |
| New root/state format, minimum-reader enforcement, partition deployment | R1_BLOCKER design dependency; release versioned-FOTA invariant, GS-D015 | Safe supported update/rollback proof before reclaim |
| Current signed image+embedded Node fit and RAM/wear | INVESTIGATE_ONLY now; becomes release gate | Actual artifacts, chip specification, allocator and sustained-rate evidence |
| Key-only duplicate fast path bypasses full immutable-payload check | INVESTIGATE_ONLY within requested dedupe audit | Host adversarial same-key test and exact digest routing design; no firmware fix here |
| Known abandoned-format migration failure | DEFER_POST_R1; GS-D001 | Preserve optional test; do not hide broad-suite failure |

Common triage: `TASK_SCOPE=architecture/static analysis/documentation`; `OUT_OF_SCOPE=firmware, partitions, backend/PWA changes, physical qualification, Jira/GS-114, BAT-C8, worktree synchronization`.

**Production-semantic implementation STOP if any remains:** unapproved product-semantic priority/exhaustion, unsafe rollback/format/partition transition, unmeasured insufficient 4 MiB safety margin, inability to preserve exact dedupe with bounded report credits, ambiguous new backend completion/summary contract, unproven crash recovery/reclaim peak space, canonical requirement conflict, or preflight no longer PASS. Current architecture is **NOT READY FOR PRODUCTION INTEGRATION** because these policy and proof gates remain. Section20 records the subsequently authorized isolated policy-neutral core; it does not bypass integration gates.

## 19. Execution status

- [x] Preflight PASS and requested base/branch verified; initial worktree clean.
- [x] Actual CSV/source audit, historical/current evidence distinction, protocol/rate/byte arithmetic, three candidate layouts.
- [x] Proposed lifecycle, recovery/learning/cloud/pressure/wear/FOTA design and impact/validation map.
- [x] Legacy failure classified from preserved reconciliation evidence; test unchanged.
- [ ] Product decisions and compatibility/crash proof closure.
- [x] Subsequent user-authorized efficiency phase: isolated host primitives and host validation; see section 20. No target build or physical qualification.

Recommended next action is product/engineering review of sections 7, 9–14 and 18, then approval of exact contracts before implementation. Do not replace missing decisions with the candidate numbers in this plan.

## 20. MEMORY / FLASH / CPU EFFICIENCY DESIGN

This section refines the earlier numerical proposal. The original documentation checkpoint is commit **94fe1a8**, reviewed and committed separately before code. Preflight passed again at context `2026-10-07.001`. User authorization permits isolated category-A primitives despite the production STOP gates; it does not approve any new product policy or format activation. Earlier 128/96-byte copies, 5,632/8,192-byte model/state, 256-transition cadence and conditional 384 KiB recommendation are comparison baselines, **not mandatory allocations**. The optimized design below makes the current 128 KiB partition worth considering first.

### 20.1 Field audit and lossless representation

Multiple classifications can apply; diagnostic-looking data cannot be removed from an existing backend retry whose canonical fingerprint includes it.

| Current field | Classification | Optimized treatment |
|---|---|---|
| Physical device ID | MANDATORY_FOR_CORRECTNESS/BACKEND; repeated text REDUNDANT | Authenticated immutable enrollment dictionary; one-byte slot plus full u32 generation |
| Logical source ID | MANDATORY_FOR_CORRECTNESS/BACKEND; text DERIVABLE | Same dictionary preserves original logical assignment; no lookup against renamed/replaced live assignment |
| Location | MANDATORY_FOR_BACKEND/LOCAL_AI; text DERIVABLE | Full u32 immutable assignment generation; six-zone routing from validated dictionary |
| Origin session | MANDATORY_FOR_CORRECTNESS/BACKEND | Keep full u64; transport-session advance cannot replace it |
| Sequence | MANDATORY_FOR_CORRECTNESS/BACKEND | Keep full u64; gaps/out-of-order keys preclude dense-sequence assumptions |
| Kind | MANDATORY_FOR_CORRECTNESS/BACKEND/LOCAL_AI | Versioned u8 enum; reject unknown values |
| Sensor type | MANDATORY_FOR_BACKEND; some LOCAL_AI context | u8; preserve current meaning |
| Node monotonic time | MANDATORY_FOR_BACKEND; summary/local ordering context | Signed 64-bit lossless representation, no truncation |
| Occurred time | MANDATORY_FOR_BACKEND/LOCAL_AI/correct rule timing | Signed 64-bit, preserve unknown/uncertainty semantics |
| Hub received time | MANDATORY_FOR_BACKEND/rule coverage; not Node-origin identity | Signed 64-bit; immutable across backend retries |
| Uncertainty | MANDATORY_FOR_BACKEND/LOCAL_AI/correct rule eligibility | Full u32, no assumed small default |
| Battery mV | DIAGNOSTIC_ONLY currently, MANDATORY_FOR_BACKEND fingerprint; possible coverage input | u16 retained; no new battery ADC claim |
| is_test | MANDATORY_FOR_CORRECTNESS/BACKEND | Bit 0 of flags; spare bits must be zero |
| Event RSSI | DIAGNOSTIC_ONLY, MANDATORY_FOR_BACKEND fingerprint | Signed 16-bit retained; Node-origin RSSI belongs to immutable input projection; separate RX transport RSSI does not |
| Motion count/first/last | MANDATORY_FOR_BACKEND/LOCAL_AI for summary | Rare 20-byte extension only for kind=MotionSummary |
| Per-event schema/ownership strings, JSON | REDUNDANT | Numeric version/dictionary references; JSON only on transmission |
| Full payload in A+C+D | REDUNDANT physical copies | One immutable event object with independent logical owners |

Reject varints/sequence deltas/timestamp deltas initially: they need extra state/anchors, complicate random retry lookup/corruption recovery, and give little benefit compared with removing repeated strings/copies. Keep simple network-endian fixed fields. New reader/writer compatibility remains gated. This format preserves current Node numeric fields; it is not an approved derived Hub-alert or summary-substitution API.

Implemented **experimental plaintext CRC frame**:

| OFFSET | FIELD | BYTES | Rationale |
|---:|---|---:|---|
| 0 | Codec version=1 | 1 | Explicit local prototype version, not existing storage schema |
| 1 | Event kind | 1 | 0–9 validated |
| 2 | Sensor | 1 | 0–5 validated |
| 3 | Test flags | 1 | Only bit 0 accepted |
| 4 | Node slot | 1 | Six supported slots |
| 5 | Reserved | 1 | Must be zero |
| 6 | Total plaintext-frame length | 2 | Exactly 68 or 88 |
| 8 | Enrollment generation | 4 | No truncated identity digest |
| 12 | Assignment generation | 4 | Immutable source/location mapping |
| 16 | Origin session | 8 | Full exact key |
| 24 | Sequence | 8 | Full exact key |
| 32 | Node monotonic time | 8 | Signed bits preserved |
| 40 | Occurred epoch | 8 | Signed bits preserved |
| 48 | Hub received epoch | 8 | Signed bits preserved |
| 56 | Uncertainty | 4 | Full range |
| 60 | Battery | 2 | Full range |
| 62 | Event RSSI | 2 | Signed bits preserved |
| 64 | Ordinary CRC32 OR summary additional count | 4 | Summary must have nonzero count |
| 68 | Summary first monotonic time | 8 | Only in summary |
| 76 | Summary last monotonic time | 8 | >=first>=0 |
| 84 | Summary CRC32 | 4 | Only in summary |

**68 B ordinary / 88 B summary** are implemented and statically bounded. CRC protects accidental corruption only. Prospective persistent envelope adds nonce12 + GCM tag16 + stable RecordId8 + commit marker4 = **108 /128 B**, before sector headers, transaction deltas, dictionaries and reclamation amplification. Header, installation/epoch, dictionary generations, RecordId and framing must be authenticated as AAD; the commit marker is not independently trusted without verified authentication/root reachability. No encrypted codec/flash writer is implemented here. Do not remove nonce bytes until uniqueness across ambiguous writes/reuse is formally proven.

`ACTIVE_EVENT_RECORD_BYTES=108 ordinary /128 summary` while full payload remains; `OUTBOX_MIN/TYPICAL/MAX=108/108/128` for current bounded Node vocabulary. Weighted NORMAL/HIGH/STRESS sizes are ~114.25/116.11/117.92 bytes using section 6's mix. `ACTIVITY_SUMMARY_BYTES=128` authenticated-envelope candidate. `CRITICAL_EVENT_BYTES=108` for existing CallFamily Node event; future derived incident/security payload sizes are **UNRESOLVED**, provision variable extensions/multi-record transactions only after their contracts. `ROUTINE_AGGREGATE_BYTES=20` numeric moment fields, or 28 in the standalone versioned CRC statistics frame. These are different representations, not missing authentication.

Once payload is no longer needed by outbox/history/replay, a key/digest witness can replace it: key21 + full HMAC32 + framing8 + RecordId8 + AEAD28 + CRC4 + commit4 =105, padded to **108 B**. A witness is retained only while a valid pending certificate permits retry. It cannot be deleted merely because backend completed. This footprint makes active-slot pressure explicit rather than hiding it behind a probabilistic fingerprint.

### 20.2 One immutable blob and low-copy path

Current audit sites: target ReceivedFrame queue copy/receive; RuntimeFrameSecurity cipher vector, opened vector and copy into EncodedFrame; NodeMessage string decoding; `domain_event_from_node_message`; ingest push and pop; HubJournal retained-vector copy; slot codec plaintext/cipher/readback/roundtrip and two comparison re-encodes; DurableJournalSlotStore rows/recovery/archive reconstructions; CloudSync pending batch, request DomainEvent copy and `ostringstream` serialization. Durable `rows()` reconstructs maps and decodes archive payloads repeatedly during reads/writes. Count grows with retained chunks and varies at four-event archive boundaries.

`CURRENT_COPIES_PER_EVENT` is **at least eight buffer/event materializations before cloud**, plus repeated data-dependent persistence/recovery copies; this is a static ownership count, not an exact byte-copy counter. The complete RX→cloud allocation count is not measured. The benchmark separately measures actual C++ `new` calls in the current volatile commit/duplicate slice. Never convert those into an exact production allocation count.

Planned path: one fixed received secure frame → fixed authenticated plaintext buffer → bounded scalar Event/view → canonical staging buffer → flash. Reducer and learner consume the same validated view; outbox queues RecordId/reference, not DomainEvent. **Two full payload transfers** (decrypt/encode and persist) are a target design, not established zero-copy target behavior. Readback/authentication adds mandatory bounded reads. Prototype encode uses an 88-byte candidate then assigns caller output; decode uses a scalar candidate then assignment so failure cannot partially mutate outputs. It is low-copy, not literally copy-free. No per-event heap is used by these primitives.

One object has A retry/dedupe, C delivery and D cache owners. Root/commit-selected reference metadata expresses completion, certificate retirement, checkpoint coverage and optional-history eviction. Physical record cannot disappear until all required owners release it. Reclaim relocation publishes a stable RecordId→new location mapping before removing old physical location; index handles are only a reconstructed RAM cache. Never reuse a physical offset as durable event/effect identity.

Previous separate transaction256 + outbox128 + history96 =480 bytes/new event before metadata. One 108-byte ordinary record saves **372 bytes (77.5%)** against that specific proposed triple-copy budget, not against measured physical NVS write traffic. Compared with outbox128+history96 alone, sharing108 saves116 bytes (51.8%). Section 13's former 576 B model additionally included evidence/completion; those do not all disappear. When an old root pins an old copy during GC, temporary duplication is required and counted as write amplification.

### 20.3 Bounded exact index alternatives

All lookup variants need verified full keys before declaring a key match; **payload equality still requires authenticated immutable bytes/full digest**. A key match by itself is not a Duplicate ACK. Corrupt persisted references fail closed on reconstruction; RAM index is never persistent authority.

| Candidate at 416 entries | Lookup / insertion / deletion | Approx RAM, excluding payload/digest | Tradeoff |
|---|---|---:|---|
| Linear packed array | <=416 exact comparisons; append O(1); locate+swap deletion O(N) | 416×25=10,400 B | Cheapest structure, high miss/duplicate CPU |
| Sorted packed array | <=9 search comparisons; insertion/delete shift <=415×25 bytes | ~10,404 B | Lower RAM, 10 KiB worst mutation move |
| Open-addressing + packed rows | Typical few probes; hard bound 1,024; backshift deletion bounded, no tombstones | **12,452 B** | Selected general primitive; no age-dependent cleanup |
| u16 fingerprint + exact rows | Scan <=416 fingerprints then full keys | ~11,236 B | Not probabilistic correctness, but measured scan remains costly |
| Per-Node sorted sessions/sequences | ~7 comparisons at ~64–96 entries/Node; bounded shifts | ~8.4 KiB for ideal shared 20-B rows; ~11.6 KiB for six fixed 96-row quotas | Fast lookup; allocation/quota/session-generation accounting not yet a selected production policy |

Chosen implementation stores **21-byte exact enrollment-scoped key + u32 opaque cache handle =25-byte row**, free list embedded in unused handle fields, and power-of-two u16 bucket references at load <=50%. Capacities 192/384/416 consume **5,828 /11,652 /12,452 B** respectively. No digest copies in RAM; full payload/witness authentication remains a storage-owner responsibility. Hash is FNV-1a over exact key bytes, solely for addressing. Forced constant-hash collisions and wraparound backshift chains are tested; no short fingerprint can produce a false key equality. Cryptographic hash/keyed hash for index addressing is unnecessary for correctness, but adversarial collision cost may justify a keyed mixer later; hard scan bounds remain.

Reboot reconstruction verifies each committed record/domain/root first, then inserts live exact keys. Expected O(live records); worst O(N×buckets), fixed independently of product age. Normal runtime performs no full-partition scan. Global sorted array remains a reasonable RAM alternative if target mutations dominate less than duplicates; host results alone do not settle ESP32 cache/flash-read cost.

### 20.4 Crypto/hashes and write ownership

Current chain performs radio GCM open; journal event GCM seal; adapter open of that generated slot; HMAC over full encoded DomainEvent; authenticated transition seal/readback; repeated checkpoint/selector/chunk authentication on `recover/rows`; adapter re-seals reconstructed slot; journal opens readback; archive flush recomputes event HMAC and builds evidence/child-reference MACs. Completion derives receipt key via HKDF and computes HMAC. Exact operation totals depend on archive count/root state and are **not a fixed hashes/event number**. The current key-only duplicate path may avoid all flash checks; it is not a valid performance baseline for future full-payload conflict checking.

Proposed ordinary ingest with already cached/verified installation keys: radio open1 + storage seal1 + readback open1 + radio ACK seal1 = **4 AEAD operations**, plus record CRC once at encode and once after readback. Required extra reducer/delivery transaction objects add their own authenticated commits; four is an event-envelope path budget, not the total product transaction cost. Readback cannot be elided for speed. Cache derived purpose keys per installation/session rather than HKDF each event.

`HASHES_PER_NEW_EVENT=0` immutable-payload HMACs if the full canonical authenticated event is retained and exact compared; compute/store full HMAC once on conversion to a compact witness. Alternative eager HMAC computes1 per new event, stores it once and reuses it at archive/checkpoint. Never recompute payload HMAC solely to rename an archive effect. This choice must be settled with the exact immutable Node-origin projection; the host codec does not implement digest semantics.

Full-payload retry: radio open1 + persisted-record open1 + ACK seal1 = **3 AEAD**, **0 payload HMAC**, exact field comparison. Witness retry: same 3 AEAD plus **1 canonical payload HMAC**, constant-time full digest compare. Reuse a verified cached record/digest only if its lifetime/immutability/root binding is proven; cache invalidates on relocation/domain changes. Neither CRC nor frame authentication alone proves stored immutable payload equality. Reboot authenticates all reachable durable records. Periodic checkpoint/report/GC authentication remains additional bounded work, not free.

### 20.5 Segmented log, writes and wear

Per-event NVS objects preserve existing qualified behavior but carry object/entry overhead and repeated blob GC; actual physical amplification is unmeasured. Fixed-slot ring offers cheap indexing but couples occupancy to longest-lived owner and variable payload sizing. Sector ring with only FIFO head can be pinned by one old pending key. **Selected future engine: sector-aligned append log + materialized checkpoint + RAM exact index**, with mixed-owner immutable records, dead/live accounting and bounded victim compaction. Existing NVS remains unchanged until an approved format/rollback transition. No flash driver/reclaim engine is implemented in category A.

One event-envelope write+commit/readback precedes ACK; marker may require a second flash program operation. Backend completion appends authenticated compact lifecycle metadata before payload becomes reclaimable. Combine up to 32 consecutive completions/retirement changes per metadata record; persistent mapping is generation/RecordId-bound, not a reused-slot bitmap. A crash before local completion persistence causes idempotent backend retry. Immediate local critical decisions/config changes commit transaction intent before RAM suppression/ACK, independently of analytics batching.

Candidate current 128 KiB design caps **uncheckpointed replay at32 retired events in addition to384 live exact evidence**, using the earlier 416 provision. This avoids a separate64 KiB full-payload tail; forcing a state checkpoint when that cap is reached is an engineering bound, not an invented retention policy. All still-required input/delta/effect bytes must fit; if multi-object rule transitions cannot meet it, budget changes and implementation remains STOP.

Current source model excluding report/initialization writes: event transition1; each four-event archive adds archive1 + evidence chunk1 + checkpoints2 + selectors2 =6/4; independent backend receipt1 per completed event: **~3.5 logical blob writes/event**. NVS may internally write/erase much more; not a measured physical amplification ratio.

Proposed event write1 + batched completion1/32 + two checkpoint-state writes1/32 = **1.09375 logical object writes/event**, plus root selectors, separate effect intents, report changes and GC. Flash program calls can be higher due commit markers/multi-sector snapshots. Epoch and registry saves occur only on their actual transitions. Unchanged health/contact diagnostics and retry counters remain RAM; persistent coverage/config changes retain required durability. Analytics numeric counters may checkpoint with state, but cannot omit enough input to make recovery incorrect. NodeHealth samples do not each become flash events.

With a conservative full 5,120-byte state written twice every32 state-changing events, snapshot pairs/day =**12/56/726** for NORMAL/HIGH/STRESS; minimum every six hours when dirty adds at most4 pairs/day in a nearly idle household. Event envelopes/day =384/1,776/23,232; completion batches/day =~12/56/726; actual report-generation changes are additional and can approach per-ACK frequency. Do not assume32-ACK batches during sparse traffic. High-rate report full snapshots must be replaced by authenticated bounded deltas selected by root, with periodic compaction; that implementation/proof is still pending.

For ordinary/summary mix and a provisional4 B/event amortized lifecycle metadata, full-state cadence yields roughly **164.3 KiB /768.3 KiB /9.79 MiB logical writes/day**, before report/dictionary/critical extensions. At assumed2× GC amplification, a128 KiB perfectly wear-spread pool sees roughly **2.57/12.0/156.7 cycles/day**. An illustrative10k endurance would be ~10.7 years/~2.3 years/~64 days; this is **not a chip rating or service-life claim**. The smaller partition may trade flash bytes for frequent state writes and insufficient high/stress endurance. Dirty-page/model-child snapshots and longer replay/low-value aggregation can lower load, but require proof and policy where detail is lost. Never claim 2× as an established bound at high live occupancy: relocation amplification scales with live fraction and can exceed it substantially. Track physical bytes/erase counts, roots/report hot sectors, maximum live victim and GC scheduling on target later.

### 20.6 Incremental routine state and checkpoint efficiency

Implemented `Moments`: count u32, sum u64, sum-of-squares u64 =**20 serialized numeric bytes**, <=24 RAM bytes on supported ABI (host24). At most UINT32_MAX u16 samples; exact sums/squares are bounded, count/sum/square overflow refuses update atomically. No floating point/division in update: one square multiply, two additions, counter increment and fixed overflow checks. Descriptive mean/population variance may be queried in double outside hot path. Tiny deviations around a large mean can suffer cancellation; a future anomaly policy must choose fixed-point/Welford or exact rational comparison with adequate intermediate widths rather than silently using noisy variance.

No window/decay/anomaly product formula is implemented. Propose six-zone, two day-class model: 48 u16 hourly buckets (96 B), 12 moment tuples (240 flash/288 RAM), current day/session32 B and coverage/confidence16 B =**384 flash /432 RAM per zone**; add256 household/config/model bytes: **ROUTINE_FLASH_BYTES=2,560**, **ROUTINE_RAM_BYTES<=2,848**. Histogram overflow is saturating with an explicit lost-detail flag, never wrapping; day rollover/normalization and sample sufficiency are decisions. u16 metric samples need domain bounds (e.g. minutes/day, not86,400 seconds/day); circular first/last-time profiles need specified encoding. No hidden narrower timestamp behavior is authorized. Remove optional seven/28-day raw-summary arrays unless a local-learning requirement justifies them; bounded counters/EWMA or approved short aggregates suffice. This is a proposed model, not implemented full routine learning.

Per semantic observation: route one zone, update one hourly bucket and session accumulator, at most a few moments/trend counters; **O(1), bounded tens of integer operations**, no flash-history scan/sort. Update daily first/last and finalized duration/count statistics at session/day boundaries, not duplicate retries. Coverage/privacy/test exclusions precede learning. EWMA step can use fixed-point multiply/shift with documented rounding; no formula is selected here. Long-range personalized analytics stay backend.

Candidate combined state **CHECKPOINT_BYTES=5,120** = reducer2,048 + routine2,560 + header/auth/root budget512. Stream through1 KiB workspace; do not place a5 KiB blob plus crypto copies on the secure owner's stack. These bounds require actual codec/config-limit/effect proof before replacing the current 4,549-byte cap. Prototype statistics encode/decode is tested; complete household/model checkpoint encoder is not implemented or benchmarked as such.

### 20.7 Proposed engine RAM budget

| Component | Bytes | Notes |
|---|---:|---|
| ACTIVE_INDEX | 12,452 | ExactIndex<416>, no full digest cache |
| RX_BUFFER | 512 | Two bounded buffers; existing driver queues are separate |
| ENCODE_BUFFER | 256 | Common/summary plus rare-extension staging |
| RECLAIM_BUFFER | 4,096 | One sector, static workspace |
| ROUTINE_MODEL | 2,848 | Proposed six-zone model, host conservative alignment |
| CHECKPOINT_WORKSPACE | 1,024 | Stream; whole snapshot not duplicated |
| OUTBOX_METADATA | 1,024 | Bounded scheduler cursors/pending completion masks, no payload queue |
| SEGMENT_METADATA | 768 | Up to96 segments at8 B; enough for conditional384 KiB option |
| OTHER_DICTIONARY/CONFIG | 2,048 | Candidate immutable mapping cache; exact config fit unproven |
| OTHER_OWNER_STATE | 128 | Cursors/counters/error state |
| **STATIC_RAM** | **25,156** | Proposed engine only |
| **MAX_STACK_TEMPORARY** | **256 budget** | Prototype event/encode candidates are bounded; target stack report required |
| **MAX_HEAP correctness hot path** | **0 target, 0 measured primitive C++ allocations** | Framework/network/OpenSSL allocations excluded |
| **TOTAL_WORST_CASE engine budget** | **25,412** | Not total Hub RAM or a target ABI measurement |

Existing81,920-byte secure-owner stack, radio queues, Wi-Fi/crypto/task state and embedded app sections are outside this incremental engine budget. Full target heap/stack/CPU margin is still unknown. Host fixtures place large arrays on host stack for tests; production placement must be static/owner-owned. Current benchmark retained volatile journal heap scales to160,180 B at416, excluding inputs/ingest/security/recovery; current physical journal is128, so that comparison is a lab capacity comparison, not a measured production 416-event heap. Proposed benchmark index+416 max-sized frames uses49,060 fixed bytes; target engine avoids caching all payloads in RAM, reading bounded immutable flash records as needed.

### 20.8 Current 128 KiB feasibility, before repartitioning

Provisional byte allocation **within existing partition**:

| Class | KiB | Derivation / limit |
|---|---:|---|
| State/root generations | 20 | Three5 KiB images packed across four sectors + root sector; actual fragment framing must fit |
| Retirement certificate banks | 12 | Three six-Node <=3,676 B blobs in three sectors |
| Active shared event/witness objects | 56 | Fourteen sectors×31 worst128 B frames =434 slots, >=416 |
| Cleanup scratch | 12 | Three sectors; victim/roots/partial erase space proof pending |
| Lifecycle/dictionary metadata | 4 | Bounded deltas and immutable dictionary generations; fit under churn unproven |
| Free emergency operational reserve | 4 | Kept out of ordinary admission |
| Additional outbox/history shared pool | 20 | Five sectors; one protected critical, four normal |
| **Total** | **128** | Raw sector model, not NVS payload capacity |

The active full event objects already serve the same keys' outbox/history/replay owners; they are **not copied** into20 KiB backlog pool. After Node retirement, payloads can occupy that extra pool. Conservative advertised NORMAL backlog equivalents count only the four extra normal sectors: **124 worst-size records**, with no optional-history guarantee. This is conservative about overlap but excludes larger derived effects and sustained dictionary/report delta growth; no guaranteed outage duration is locked.

Keep fixed 108 KiB safety/state/metadata allocation for comparison, use all remaining flash for the shared pool, and reserve >=20% of those pool sectors rounded up for critical work:

| Lifecycle size | Pool sectors | Critical sectors | Normal worst128 B records | NORMAL/HIGH/STRESS hours |
|---|---:|---:|---:|---|
| **128 KiB current** | 5 | 1 | **124** | **7.75 /1.676 /0.128** (~7.69 min stress) |
| 384 KiB conditional | 69 | 14 | **1,705** | **106.562 /23.041 /1.761** |
| 512 KiB conditional | 101 | 21 | **2,480** | **155 /33.514 /2.562** |

Sector header64 B gives31×128 B objects. If all ordinary108 B objects,37 fit/sector; 128 KiB normal pool148 objects gives9.25 h NORMAL, but do not use this as a mixed/critical guarantee. Synced recent history shares the pool and is first evicted; it consumes no duplicate payload. Reclamation/source-child copies, abandoned staged records, variable transaction intents and dictionary/history pins can shorten these horizons. Table is a sizing scenario, not an allocator proof. Earlier separate-class capacities are superseded **only as this proposed optimized comparison**, not as approved product promises.

`CAN_R1_STORAGE_WORK_WITH_CURRENT_128K_PARTITION=CONDITIONAL`. No locked duration currently mandates384 KiB. A modest full-detail outage promise plus approved bounded overflow could fit128 KiB **if** retirement credit/progress, complete-state/replay/critical byte bounds, peak COW/report metadata, wear and rollback prove out. A multi-day full-detail guarantee under HIGH activity would exceed this budget. Sustained stress/wear is also limiting. **PARTITION_CHANGE_NEEDED=UNDECIDED**; optimize/prove128 KiB first, retain existing dual1,966,080-byte OTA slots, and only request a layout decision if the approved guarantees demonstrably require more space. Replacing NVS with a sector log is still a format/rollback transition even when CSV addresses stay unchanged.

### 20.9 Phase classification, implementation and validation

| Category | Work | Status |
|---|---|---|
| A POLICY_NEUTRAL_STORAGE_CORE | Fixed exact-key index, lossless experimental codec/CRC/cursor, integer moments, host fixture/tests/benchmarks | **Implemented, host-only, excluded from production targets** |
| B PRODUCT_POLICY_DEPENDENT | Retention, overflow priority, six-node credits/report progress, histogram decay/anomalies, complete reducer limits | STOP |
| C BACKEND_CONTRACT_DEPENDENT | Derived-effect/summary/gap identity and canonical ACK mapping, production transport, routine delta API | STOP |
| D PARTITION_LAYOUT_DEPENDENT | Any OTA/storage resize or deployment relocation | STOP; unnecessary for category A |
| E ROLLBACK/FOTA_DEPENDENT | New persistent format, old-reader exclusion, source deletion/reclaim | STOP |

Implemented paths under P: `host/storage/efficient_core.hpp`, `host/storage/README.md`, `tests/cpp/storage_efficiency_validation.cpp`, `tests/cpp/storage_efficiency_benchmark.cpp`, and two isolated Makefile targets. No CPP_SOURCES/ESP-IDF production lists, firmware, partition CSV, backend/PWA or Node behavior changed. The core never sends ACKs, authenticates ownership, decides retention or erases storage. ExactIndex matching is deliberately a key-cache operation, not an alternative to full dedupe validation.

Validation: encode/decode ordinary and all enum kinds; minimum/maximum signed/unsigned values; truncated/bit-corrupted frames; malformed reserved/version/kind/slot fields with recomputed CRC; CRC golden vector; failed decode/encode leaves output unchanged; deterministic 50,000 fuzz inputs; forced constant-hash collisions including wraparound probe chains; capacity192/384/416, replacement generation separation and random 50,000-operation churn; statistic correct mean/variance, serialization, saturation/overflow; six-node interleaving and index reconstruction. Long fixture executes **1,000,000 semantic events**, retains exactly 192 records, periodically rebuilds verified CRC-frame index and asserts no new C++ allocations. Pool17,088 B +416-entry index 12,452 B remain constant; this proves simulated record count/primitive RAM independence from age, **not flash crash recovery or retirement protocol progress**. Fixture releases all three owners explicitly before reuse; no inferred policy authorizes retirement.

Address/undefined sanitizer validation passes with leak detection disabled because this environment's ptrace prevents LeakSanitizer operation; allocation instrumentation separately verifies zero hot-path C++ `new`. This is not a claim about libc/network/crypto allocations. Existing `hub-backend-commit-host-test` and `hub-journal-persistence-host-test` pass, preserving their receipt/reboot/dedupe/tamper/write-fault/reducer and128/full129 boundaries. Optional legacy migration remains unchanged and was not rerun. No HIL/physical event/target build.

Benchmark method: g++ 15.2.0, C++17 `-O2 -Wall -Wextra -Werror -pedantic`, trace disabled, Intel Core i5-3210M host. Warmup then median of 9 rounds; lookup/primitives200,000 operations/round, new insertion and retirement128 batches/round at 192/384/416; checkpoint/segment fixtures bounded. Timings are host wall-clock and can vary under contention; no ESP32 cycles inferred. Checksum/output observations prevent dead-code elimination. New-event baseline is actual **volatile HubJournal**, which can use lab capacities beyond 128; proposed pipeline is encode CRC+index+fixed record fixture, not authenticated durable ingestion. Duplicate comparison baseline checks key only; proposed timing is key lookup only, not full payload conflict proof. Checkpoint benchmark is256 standalone statistics frames (7,168 B), not the complete5,120 B reducer/model proposal. Segment-parser timing includes CRC/payload decode; GC root/erase-metadata processing is not implemented/benchmarked.

Final measured results and raw reproducible commands are recorded in [host evidence](../evidence/R1_STORAGE_EFFICIENCY_HOST_20261007.md). Performance acceptance is **primitive-level only**: avoid unbounded allocation and repeated retained-history reconstruction; lower fixed memory and lookup cost versus the current volatile reference. Full end-to-end flash/CPU/energy acceptance waits for authenticated storage/transactions and target measurement. The compact CRC codec may cost more CPU than the current unauthenticated payload encoder even after table optimization; do not describe that isolated comparison as a speedup.

All section 18 integration STOP gates remain. In particular, the million-event fixture is not a substitute for power-fail/AEAD/GC/rollback proof. No final128 KiB feasibility or durable write-amplification claim is approved by these host results.
