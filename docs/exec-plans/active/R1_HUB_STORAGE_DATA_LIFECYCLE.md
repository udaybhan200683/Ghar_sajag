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

## 21. Storage-first refinement and failure-aware routine recovery — 2026-10-07

### 21.1 Authority, evidence and limits

GS-D021/022/023 lock the new engineering order and failure-aware current/daily routine behavior. They do **not** close GS-D013/014/015/017. Sections 8/9/10/20 remain useful historical proposals; the alternatives below supersede their numerical recommendations only for this sizing comparison. No proposed codec, retention threshold, critical quota, coverage formula or backend revision API is approved by being described here.

Qualified isolated core is committed as `45f6b00`. Its unchanged million-event fixture passed again: 192 records, 17,088-byte record pool, 12,452-byte exact index, zero hot C++ new calls. Production remains the current 128-event journal. No new failure simulator has been implemented in this refinement checkpoint. Model tests described below are required future work, not PASS evidence.

### 21.2 Field audit and one-body lifecycle

| Existing field | Classification | Treatment |
|---|---|---|
| Physical/logical source strings | MANDATORY_CORRECTNESS / SECURITY / BACKEND | Authenticated immutable dictionary, numeric slot + enrollment generation; retain dictionary until every reference dies |
| Location string | MANDATORY_BACKEND / ROUTINE | Assignment generation maps historical room; never use current renamed room on retry |
| Origin/session + sequence | MANDATORY_CORRECTNESS / BACKEND | Full u64 each; transport session is different and not substituted |
| Kind, sensor, test/privacy exclusions | MANDATORY_CORRECTNESS / ROUTINE / BACKEND | Bounded enums/flags; reject unsupported versions |
| Node monotonic, occurred, uncertainty | MANDATORY_ROUTINE / BACKEND | Preserve full widths; uncertain/untrusted time does not become absolute truth |
| Original Hub received time | MANDATORY_BACKEND | Preserve once, because current backend fingerprint includes it |
| Battery, Node-origin RSSI | MANDATORY_BACKEND / DIAGNOSTIC | Current canonical backend payload includes them; cannot discard solely as diagnostic |
| Motion count, first/last monotonic | MANDATORY_ROUTINE / BACKEND | Rare 20-byte summary extension; does not prove continuous occupancy |
| Payload digest in multiple objects | DERIVABLE | Full canonical bytes can be compared after authentication; do not require repeated digest if immutable body remains |
| Installation/security domain, schema strings | MANDATORY_SECURITY; repeated strings REDUNDANT | Bind authenticated segment/dictionary, numeric schema per record |
| Transport RSSI, latest retry receive time | DIAGNOSTIC_ONLY | Separate from immutable Node payload; RAM/latest bounded diagnostic state |
| Archive copy/outbox copy/history copy | REDUNDANT payload duplication | One immutable body, independent ownership bits/references |

An ordinary body is 64 bytes of canonical numeric content. Physical proposed record is 84 bytes after tag/commit, summary 104. For summary events use 84-byte content plus tag/commit. Body remains immutable through RX/authentication, durable commit, reducer/learner application, backend pending, backend accepted, optional recent history and reclaim. Initial active/pending/history state is implicit in record kind plus selected root; no three payload writes.

| Lifecycle stage | Persistent body | Active metadata | Outbox metadata | History metadata | Checkpoint effect | Duplicate body bytes | RAM index |
|---|---:|---|---|---|---|---:|---:|
| RX/authentication, before commit | 0 | 0 | 0 | 0 | 0 | 0 | temporary bounded buffer |
| LOCAL_DURABLE, before Node ACK | 84 /104 | implicit key; credit delta transaction | implicit pending | implicit optional | ordered replay ordinal; state not yet checkpointed | 0 | 25-byte row + amortized buckets |
| LOCAL_EFFECT_APPLIED | same | unchanged | unchanged | unchanged | materialized once, dirty state covered by retained input | 0 | same |
| BACKEND_ACCEPTED | same if other owners live | until complete report proves retirement | authenticated completion bitmap batch | optional | bounded state child | 0 | same until A ends |
| Node retired, state checkpoint-covered | same only if C/D live | certificate replaces exact membership | pending or accepted bit | optional | checkpoint owns effect | 0 | release A row |
| RECLAIMABLE | 0 after safe erase | 0 | 0 | 0 | survives in state/aggregate | 0 | 0 |

During COW/GC there may temporarily be TWO physical authenticated copies of a live body. Both refer to the same logical event; selected root chooses one. Charge the GC reserve, never call this zero peak duplication. Independent lifecycle metadata batch below is 44 bytes for up to32 records, 1.375 bytes/record when full; sparse batches cost44 bytes. Receipt authenticity/identity verification occurs before that batch is committed. History needs no durable per-item index when bounded segment scans answer it. Checkpoint effect is not a second raw payload: fixed-size aggregate state, amortization depends on actual update cadence.

### 21.3 Byte-level proposed formats (not final production codecs)

All integers little endian, checked arithmetic, four-byte record alignment, no JSON/heap strings. A segment has a 64-byte authenticated header; usable sector bytes =4,032. Nonce is DERIVABLE as `(never-reused segment serial u64, physical byte offset u32)` under an installation/epoch/type-separated key. Record identity for relocation and backend is the logical EventKey/effect identity, not the physical pointer. Relocation authenticates old content then re-encrypts under the destination nonce. A per-segment nonce base alone is unsafe without a unique per-record offset.

**Ordinary semantic event — 84 bytes; ActivitySummary — 104 bytes.** The first64 bytes match the prior prototype fields except its CRC is replaced with AEAD, and a summary adds20 bytes.

| Offset | Field | Bytes | Rationale |
|---:|---|---:|---|
| 0 | schema | 1 | per-record decoder; new experimental schema distinct from deployed format |
| 1 | kind | 1 | semantic enum |
| 2 | sensor | 1 | preserve producer meaning |
| 3 | flags | 1 | test/exclusion/data-quality bits |
| 4 | Node slot | 1 | six-node dictionary binding |
| 5 | reserved | 1 | must be zero |
| 6 | record length | 2 | bounded parsing, authenticated AAD |
| 8 | enrollment generation | 4 | physical replacement/ownership binding |
| 12 | assignment generation | 4 | historical location identity |
| 16 | origin session | 8 | exact EventKey |
| 24 | sequence | 8 | exact EventKey, no gap floor shortcut |
| 32 | monotonic ms | 8 | original signed domain width |
| 40 | occurred seconds | 8 | original immutable value |
| 48 | original received seconds | 8 | backend retry fingerprint |
| 56 | uncertainty seconds | 4 | trusted-time eligibility |
| 60 | battery mV | 2 | preserve current upload |
| 62 | Node-origin RSSI | 2 | preserve current upload |
| 64 ordinary /84 summary | AEAD tag | 16 | mandatory per-record authentication |
| 80 ordinary /100 summary | commit pattern | 4 | programmed last; valid tag/header/length also required |
| 64 summary only | additional motion count | 4 | lossless summary |
| 68 summary only | first monotonic ms | 8 | lossless summary |
| 76 summary only | last monotonic ms | 8 | lossless summary |

Nonce12 is not stored; CRC4 is omitted because mandatory AEAD verifies every recovered/read record. Prototype CRC codec stays unchanged and unauthenticated. No security claim is made until nonce reservation and actual AEAD tests prove this format. Flags/length/schema are authenticated; parsing checks bounds before accessing ciphertext. Offset-derived nonce forbids overwriting a record, even with the same source key. Abandoned reservations burn offsets/serials.

**Critical alert — candidate128 bytes.** Source CallFamily uses ordinary84 bytes; a distinct Hub-derived incident uses its own identity/codec:

| Offset | Field | Bytes | Rationale |
|---:|---|---:|---|
| 0 | schema/type/length | 4 | bounded framing |
| 4 | stable rule-instance identity | 16 | dictionary-backed installation + rule/window/generation mapping; full exact identity retained in dictionary |
| 20 | revision | 4 | immutable effect revision |
| 24 | cause source key | 24 | slot/enrollment/session/sequence plus padding; exact provenance |
| 48 | occurred and received | 16 | chronology |
| 64 | config/assignment versions | 8 | reproducible rule/room |
| 72 | kind/severity/flags/reason code | 8 | no repeated reason strings |
| 80 | bounded cause/decision extension | 28 | lengths/uncertainty/state; longer content requires charged extension record |
| 108 | tag | 16 | authenticated |
| 124 | commit | 4 | final write |

128 is a sizing ceiling for this candidate, not proof every current incident fits. Truncated hashes alone must not define uniqueness; dictionaries store/compare full identity tuples and immutable versions. Critical payload exceeding28-byte extension reopens capacity gate.

**Daily aggregate — candidate320 bytes.**

| Offset | Field | Bytes | Rationale |
|---:|---|---:|---|
| 0 | schema/type/length | 4 | framing |
| 4 | local calendar day | 4 | explicit date, not fixed86400 seconds |
| 8 | revision | 4 | immutable retry identity |
| 12 | timezone/config generation | 4 | interpretation version |
| 16 | clock mapping generation | 4 | time provenance |
| 20 | finalization generation | 8 | exactly-once baseline selection |
| 28 | rule/config generation | 4 | model inputs |
| 32 | installation/household dictionary binding | 4 | exact full domain outside repeated body |
| 36 | model schema + day flags | 4 | complete/partial/untrusted/excluded |
| 40 | covered input ordinal | 8 | replay boundary |
| 48 | anomaly/data-quality masks | 4 | bounded conclusions |
| 52 | household first/last activity seconds within day | 8 | positive evidence; invalid sentinel |
| 60 | six zone blocks | 240 | each40 bytes below |
| 300 | tag | 16 | authenticated |
| 316 | commit | 4 | final write |

Each zone block: first4, last4, sessioncount4, observed-duration proxy4, expected-observation seconds4, available seconds4, doorcount2, explicit-checkin count2, missing-reason mask2, flags2, deviation fixed-point2, confidence2, reserved4. Counts saturate with overflow/data-quality flag; duration is an observation proxy, not proof of continuous resident activity. Expected duration comes from actual local-day boundaries/config and may differ across DST. Unsupported bathroom/kitchen interpretation is omitted/flagged, never fabricated.

**Backend outbox / active durability metadata — shared44-byte transition batch.** Offset0 schema/type/length4; offset4 source segment serial8; offset12 base offset4; offset16 record-selection bitmap4; offset20 accepted/retired/applied masks or action4; offset24 AEAD tag16; offset40 commit4. References apply only to at most32 records of a known immutable segment directory, not arbitrary offsets; root selects directory and report/receipt generation. The action is one authenticated state transition, not an untrusted bit. Separate report objects preserve exact pending sets/credit; this batch cannot replace full certificates. More than one action requires another batch. Sparse changes and GC relocation must be budgeted.

**Segment header —64 bytes.** Offset0 magic4;4 format/minreader2+2;8 serial8;16 epoch8;24 installation/domain digest16;40 segment role/flags2+2;44 reserved4;48 tag16. Header authentication uses a separate key/nonce domain. Sector erase generation is never sufficient nonce uniqueness without reserved serial progress. Header contains no mutable per-event count: parse committed records until bounded end; directory reconstructed at boot.

**Checkpoint root —240 bytes, plus4-byte page-level activation marker.** Offset0 magic/schema/length8;8 rootgeneration8;16 epoch8;24 installationdigest16;40 coveredordinal8;48 config/dictionary references16;64 three child references and full hashes144 (each16-byte locator +32-byte hash);208 minimumreader/writer4+4;216 nonce-allocation highwater8;224 tag16. Root page framing/activation is additional at page level; a complete authenticated root is valid only when all children/covered tails are reachable. Bounds include three root sectors. Generation/serial overflow refuses admission, never wraps.

### 21.4 Coverage and bounded routine model

Propose routine serialized2,560 B / RAM2,848 B: six zones each384 serialized (two day-class48×u16 buckets96; twelve20-byte moments240; trend32; confidence/model flags16), plus256 household/model parameters. No raw-history scans. Current-day state is separate512 B: six40-byte daily metric blocks240 + coverage208 + day/finalization/time header64. **Coverage208 B** = six32-byte zone coverage records +16-byte Hub/time anchor. Each zone: expected seconds4, available seconds4, missingreason2, stateflags2, monotoniclastchange8, clockgeneration4, trustedleaseendpoint8. Model histograms and confidence criteria are versioned; saturation is explicit. Daily confidence occupies2 bytes/zone plus day-level flags in header; at least12 bytes, not a claim of an approved probability model.

Combined checkpoint budget becomes **6,144 B**, replacing preliminary5,120 only for this comparison: reducer2,048 + routine2,560 + currentday512 +1,024 authentication/schema/dictionary-root/effect-boundary allowance. Three COW images need18,432 B, provisioned in five sectors20,480 B. This is not a proven whole-state codec or an approved change to current4,549-byte limit. RAM model + currentday =3,360 B candidate; current secure owner/task memory is additional.

Incremental update: validate source/assignment/time/exclusions, dedupe and coveredordinal, then update one zone first/last/count, one bucket and session accumulator; at most a bounded handful of moment/EWMA operations. Bounded tens of integer operations per semantic event; no new target-cycle estimate. Day boundaries perform six fixed-zone updates, not history replay. Current routine state remains recoverable by selected checkpoint + retained tail. Baseline receives only coverage-eligible finalized inputs; absent observation is not zero activity.

Coverage intervals use monotonic elapsed time while running, trusted mapping for day clipping, and configured eligibility. Fresh contact allows a future bounded lease; it does not prove an earlier offline interval was observed. Sensor fault/runtime-stall/gap/privacy/maintenance reasons remain distinct. A Hub reboot resets liveness to UNKNOWN: downtime from last durable time anchor to fresh trusted contact is missing observation. Unknown-duration downtime is marked unknown, not assigned zero seconds. Day totals are a compact summary, not enough to prove a specific morning window was continuously covered: persist bounded per-current-rule window coverage/gap flags in reducer state. Exact positive-evidence attribution does not fill unknown coverage.

For overlapping sensors, use configured required-zone eligibility/union semantics; do not sum availability beyond expected seconds. Arbitrarily flapping contact cannot require unbounded interval lists: maintain totals, current interval and bounded rule-window gap bits; exact historical availability curves belong backend. Confidence sufficiency, correlation of sources, lease tuning and overflow behavior remain product decisions. Internet/backend unavailability alone does not reduce local sensor coverage; Hub/radio failure can.

### 21.5 Finite active invariant and retrieval

Current implementation provides no finite accumulated-evidence bound beyond128. Conditional invariant remains: each enrolled Node has at most32 entries in selected authenticated complete pending certificate plus at most32 new distinct commitments since it. Persist credit basis with every acceptance/certificate selection. Reject new-key admission at exhausted credit while duplicates and report/control remain serviceable. Exact set complement with session/highwater proof retires covered absent keys; a greatest-sequence watermark does not.

Proof by induction: certificate selection leaves <=32 listed keys; each distinct new commitment consumes one of32 credits; retry consumes zero; reboot restores same credit basis, never replenishes; fresh certificate removes only proven absent covered keys and resets credits transactionally. Six Nodes therefore <=384 exact keys. +32 bounded COW/in-flight copies =416 physical entry capacity. Engineering margin is32, not new semantic admissions. If arbitrary report loss prevents progress, the invariant bounds memory but cannot guarantee continued new-event ACKs. Thus **RETIREMENT_BOUND_PROVEN=NO for production**, MAX_EXACT_KEYS_REQUIRED unconditionally unbounded, conditionally384. Node pending maximum192 alone is insufficient. Six admission limit, progress negotiation and source/digest conflict checks remain STOP.

Keep current ExactIndex416 (12,452 RAM) until storage settles; host faster/slower alternatives do not justify larger flash. Match exact enrollment/session/sequence and immutable authenticated dictionary, then compare original Node payload before Duplicate ACK. Fixed hash collision behavior is deterministic O(capacity); fingerprint is never sole proof. Backend scheduling uses per-segment pending/critical masks and cursor, not duplicate payload queues. Recent history scans bounded selected segment directories; currentday/model read fixed state children; victim lookup uses per-segment live-byte/owner counters; retirement uses six fixed certificate descriptors. Boot scans at most partition sectors and fixed metadata; no runtime full-partition scan per event. Reconstruct RAM index from authenticated selected roots and committed tail; ignore unselected COW debris. No extra flash index charged.

### 21.6 Exact conditional128 KiB comparison budget

This is an exact sum of a **candidate reservation**, not exact proven allocator occupancy. A 64-byte header leaves4,032 usable bytes/sector. Reserve worst104-byte Node records,38/sector, 80-byte remainder; larger critical records use31/sector. Root sectors and metadata reserves include their headers; no RAM index bytes are counted as flash.

| Category | Reserved bytes | Reason | Reclaimable |
|---|---:|---|---|
| Active shared bodies / correctness | 45,056 (11 sectors) | 418 worst104-byte slots >=416; same bodies serve pending outbox/history | only after all owners clear |
| State / routine / daily / COW | 20,480 (5 sectors) | three6,144-byte checkpoint images +2,048 framing slack; routine2,560/currentday512 are INCLUDED | older images only with root proof |
| Roots / nonce generations | 12,288 (3 sectors) | rotating root log, preserve old/new valid references | safe obsolete generations |
| Exact retirement certificates | 12,288 (3 sectors) | three <=3,676-byte six-Node snapshots | after durable newer selection |
| Lifecycle/dictionary deltas | 8,192 (2 sectors) | bounded completion/credit/mapping transitions; churn fit unproven | after checkpoint/certificate ownership transfer |
| GC reserve | 12,288 (3 sectors) | destination victim copy + publication/partial-erase headroom | reserved, never ordinary admission |
| Critical operational reserve | 8,192 (2 sectors) | at least one32-event transaction burst at128 B needs2 sectors (31/sector); candidate ONLY | critical work after ownership transfer |
| Ordinary outbox/history incremental pool | 8,192 (2 sectors) | 76 worst104-byte records | according to backend/summary/history ownership |
| Free unassigned reserve | 4,096 (1 sector) | extra bad/abandoned tail/COW headroom; faults still fail closed | not ordinary quota |
| **TOTAL** | **131,072 (32 sectors)** | exactly current partition | |

ACTIVE_DURABILITY_BYTES45,056 excludes certificate metadata separately charged12,288. OUTBOX_BYTES8,192 is incremental ordinary pool, **not a second active payload copy**. ROUTINE_STATE_BYTES2,560 and DAILY_STATE_BYTES512 are suballocations of state reserve, not additions. CHECKPOINT_BYTES6,144 is each image. ROOT_METADATA_BYTES12,288; CRITICAL_RESERVE_BYTES8,192; GC_RESERVE_BYTES12,288. Segment headers total32×64=2,048 INCLUDED across rows. AVAILABLE_EVENT_BYTES: ordinary pool payload capacity76×104=7,904, headers128/tail160 included; active bodies capacity418×104=43,472; critical62×128=7,936. Active tail/COW headroom cannot be advertised as ordinary history. Roots/state packing, dictionary pins, variable effects and report churn still need executable allocator proof.

Critical reserve derivation protects one bounded32-record ingestion burst during cleanup, not an indefinite outage. All192 Node pending keys could be critical and already fit shared active capacity; ordinary admissions must leave critical credits physically available. Emergency intervals/incident rate and post-retirement backlog are unbounded in requirements, so8,192 is **not a final critical-retention guarantee**. If critical traffic can permanently fill all pinned capacity, finite flash cannot preserve every incident indefinitely while continuing all ACKs. Required bounded incident/effect overflow semantics are a REQUIREMENT_GAP, not solved by this reserve.

### 21.7 Retention, aging and72-hour comparison

Retain previous actual episode scenarios384 /1,776 /23,232 records/day. No qualified Reed/button maximum exists. For guaranteed source record sizing use104 B even for ordinary84-byte events; this fixed-cell comparison avoids pretending an unspecified mix/order has an exact packing ratio. NORMAL actual scenario has264 ordinary and120 summaries =34,656 body bytes/day before sector/lifecycle effects; HIGH1,056 ordinary720 summaries =163,584; STRESS11,712 ordinary11,520 summaries =2,181,888. Those byte sums are not standalone retention guarantees.

Only incremental ordinary pool counted below; active payloads may already carry additional backlog, but are pinned correctness reserve and are not promised retention space.

| Detail representation | Capacity | NORMAL hours /days | HIGH hours /days | STRESS hours /days |
|---|---:|---|---|---|
| Full semantic detail,104-byte bound | 76 source records | 4.75 /0.197917 | 1.027027 /0.042793 | 0.078512 /0.003271 |
| Daily320-byte aggregates in same2 sectors | 24 daily records (12/sector) | 576 /24 | 576 /24 | 576 /24 |

The second row preserves daily aggregate information, **not all source events**:24 days correspond to9,216 /42,624 /557,568 source-record equivalents under scenarios, without their individual identities/chronology. It is conditional on approved backend summary/revision/completion contracts and on full active/report/reducer constraints clearing. Fixed routine model persists indefinitely by replacement, but this does not promise infinite unsynced daily history. Beyond24 aggregate days needs approved cross-day sufficient-statistic merging plus explicit coverage/gap boundaries; cannot silently drop days required for backfill. Baseline alone cannot reconstruct daily conclusions.

Critical-only protected pool:62 maximum128-byte records, plus whatever active credit reservation permits; hours =62/rate_per_day×24, days=62/rate_per_day. No finite critical arrival rate is approved, so an unconditional number of days is **NOT DERIVABLE**. For an explicitly illustrative6 critical records/day:248 h /10.333 days; this is not a requirement or measured rate.

Aging proposal: A recent immutable source detail; B lossless existing activity-summary records (already produced by Node, not arbitrary new five-minute suppression); C authenticated daily aggregates with coverage/reasons and stable identity; D critical incident/effect records independently pinned. Synced optional history and diagnostics go first. An unsynced source record may be transformed only after local correctness transfers, and backend explicitly accepts a new aggregate/substitution manifest; current Node EventKey API forbids changing its canonical payload. Distinct door/OK/CallFamily chronology cannot be collapsed without product approval. NO_OBSERVATION remains visible through every tier.

**72h NORMAL is comparison only.** 3×384=1,152 source records. Worst104-byte slots need ceil(1,152/38)=31 sectors=126,976 B (119,808 body,1,984 headers,5,184 padding/unused slots). Fixed other reservation excluding ordinary pool is122,880 B, already including active, state/daily/routine, roots, critical and GC. Required total **249,856 B (244 KiB)**; existing128 KiB deficit **118,784 B (116 KiB)**. Thus72H_NORMAL_FITS_128K=NO under this conservative independent-backlog reservation. Sharing current active occupants may reduce peak but cannot be promised before allocator/credit/COW proof. A precise mixed variable-record implementation could use less; do not promote this upper-bound allocation to a mathematically minimal requirement.

| Partition | Incremental normal sectors after fixed120 KiB | Full-detail records | NORMAL /HIGH /STRESS hours |
|---|---:|---:|---|
| 128 KiB | 2 | 76 | 4.75 /1.027 /0.079 |
| 192 KiB | 18 | 684 | 42.75 /9.243 /0.707 |
| 256 KiB | 34 | 1,292 | 80.75 /17.459 /1.335 |
| 384 KiB | 66 | 2,508 | 156.75 /33.892 /2.591 |

No locked offline horizon proves resizing necessary. Minimum for the above72-hour bound is244 KiB raw, rounded to256 KiB among compared layouts; not a production recommendation. 256 KiB would permit two0x1D0000 slots at0x020000/0x1F0000 and lifecycle0x3C0000/0x040000. 192 KiB can retain current first slot and shrink second to0x1D0000, lifecycle0x3D0000/0x030000; asymmetric OTA capacities must be respected. 384 KiB stays the earlier conditional layout. **Recommendation: keep128 KiB and existing CSV until policy, allocator proof and image evidence show a necessary resize.** 128K_FITS_LOCKED_R1_REQUIREMENTS=CONDITIONAL, not YES; maximum critical/backfill obligations remain undefined.

### 21.8 Failure matrices and recovery expectations

All rows describe required/proposed behavior, **NOT_TESTED as a new integrated engine**. PWA effects require future backend contract/vertical validation. No Node/Hub failure may manufacture inactivity from missing coverage.

| Node case | Local durability / recovery | Routine / coverage | Backend / PWA |
|---|---|---|---|
| Power before retained transmit | No Hub ACK; restore only durably retained input; unsaved repeats may be lost | no fabricated activity; sensing reset/gap means uncertain coverage | explicit quality/gap where supported, no complete-day claim |
| Power after retain before ACK | Retry same origin key after rejoin | apply once after commit; downtime unavailable | stable source identity |
| ACK loss then reboot | exact authenticated duplicate ACK; saved retirement/report then progress | no second learner update | no second caregiver effect |
| Offline minutes /hours | keep exact pending and report credits | unavailable interval, positive evidence elsewhere remains usable | connectivity/partial confidence, not resident inactive |
| Offline across day | retain supported source input; complete-day claim withheld | separate each day's missing duration/reason | stable partial daily conclusions |
| Rejoin retained | old origin survives newer transport session | delayed occurrence if time trusted; no retroactive blanket coverage | backfill original immutable payload |
| Duplicate on rejoin | exact key + payload verification | zero new contribution | idempotent retry |
| Out-of-order | certificate membership and sparse gaps preserved | commutative daily counts/min/max; order-sensitive rules need explicit bounded chronology policy | occurrence + receive order preserved |
| Six simultaneous rejoin | fixed per-source quotas, fair bounded drain | independent coverage recovery | fair backfill, critical live service |
| One Node unavailable | other five continue | affected required-zone/windows partial; do not suppress positive evidence globally | explicit missing source/zone |

| Hub case | Durable recovery | Routine / coverage | Backend / PWA |
|---|---|---|---|
| Before event commit | torn/uncommitted record ignored; no durable ACK | no application | Node retries |
| After commit before ACK | reconstruct exact key and replay covered tail once | same canonical input | same identity |
| After reducer RAM update | root/tail ordinal selects state | redo only not-covered inputs; RAM updates not authority | durable intent remains pending |
| During routine update | old selected snapshot + input, or new valid child/root | never double baseline/event | no invented conclusion |
| During checkpoint | child hashes/root validation chooses complete state | old root retains necessary tail | no missing acknowledged work |
| While backend pending | pending owner recovered | learning independent of cloud | automatic identical retry |
| Backend accepted, response lost | leave pending until authenticated receipt durably selected | no local repeat | backend conflict/dedupe prevents duplication |
| During reclaim | state machine below | selected reachable state survives | live pending payload survives |
| Repeated reboot | preserve credit, nonce reservation and ordinals | leases UNKNOWN until fresh contact; boot count not activity | no identity renewal per boot |
| Across midnight | trusted date gaps synthesized only as unavailable | bounded day closing; unknown time quarantined | one logical day/revision, no false inactivity |
| Return with many retained Nodes | six independent exact/certificate paths | correct delayed evidence with partial coverage | fair bounded backfill |

| Internet/backend case | Local effect | Retry / caregiver effect |
|---|---|---|
| Internet unavailable /backend unavailable | sensing/alerts/learning and source ACK unchanged within independent reserve | pending backlog; stale backend status, no PWA-open trigger |
| Timeout /durable acceptance response lost | completion not inferred | identical request/identity, retry accepted once |
| Partial upload then outage | persist only verified accepted completion bits | resume remaining stable pending identities |
| Hours /multiple days | detail ages only under approved substitution | retain daily conclusions independently, bounded pressure flagged |
| Large reconnect backlog | bounded oldest-first normal + critical/fresh service | no starvation; explicit backend rate/backoff budget needed |
| New live event during drain | normal local durable commit | near-real-time scheduling remains enabled |
| Retry after Hub reboot | selected outbox and exact canonical body recovered | no new receive timestamp, no duplicate timeline |

Example Day1/Day2 backend outage: local coverage-aware daily aggregates remain pending; on Day3 submit both stable daily identities/revisions, retained meaningful detail and current Day3 state automatically. Backend acknowledgements are separate per immutable object. Unknown/missing detail is flagged; aggregates do not claim a reconstructed full timeline.

### 21.9 Time, daily finalization and identity contracts

Boot without trusted time keeps monotonic activity in a bounded unassigned-time bucket; no dated no-activity daily conclusion. NTP restoration creates a versioned mapping with uncertainty; only records whose interval falls unambiguously in a day may be assigned. Cannot reconstruct time across reboot from Node monotonic alone. Unresolvable positive activity remains undated evidence, not an inactive day. Bounded overflow/retention of unassigned items needs policy.

Clock forward jump closes only trusted contiguous days; skipped intervals are unavailable. Backward jump never reopens a finalized day as a new day; monotonic processing and versioned clock mapping prevent negative durations. Timezone change becomes effective at an explicit config boundary; do not relabel old finalized days. Local-day lengths use actual UTC start/end, including DST; sentinel first/last is not midnight zero. Event uncertainty straddling midnight is ambiguous rather than counted twice.

Proposed bounded lateness mechanism: current-day state plus one retained previous-day revision workspace, with a product-approved grace horizon (NOT selected). Within it, late input makes a new immutable revision; outside it preserve delayed positive detail/quality, do not silently rewrite local baseline. Arbitrary multi-day delayed corrections cannot all reside in512-byte current state. Exact late-window/historical rule retraction and sample correction policy remains OPEN. Order-sensitive door/morning sequence cannot be made correct by blindly replaying receive order; bounded reorder/correction semantics must be specified separately from commutative daily counters.

Daily transaction: OPEN -> PREPARED aggregate child -> committed authenticated aggregate -> updated model child with `(DayKey, applied_revision)` -> selected root referencing aggregate, model, backend intent and new OPEN day -> RAM activation. Aggregate preparation is unreachable until root; baseline update is COW, never in-place before selection. One root publication selects all changes. Before publication failure selects old day/model; afterward selects new complete day/model. The old root retains inputs needed to finish again. Backend dispatch only selected intents. Repeated finalization uses the same DayKey/revision and skips an already applied revision. For late correction, replace the prior day's contribution exactly or rebuild a bounded sufficient-statistic correction; EWMA subtraction is not generally reversible. Do not claim correction safety without a specific model contract.

Stable logical identities (full tuples, no fingerprint-only equality):

| Object | Proposed identity | Existing production status |
|---|---|---|
| SOURCE_EVENT_ID | household/installation + physical/logical source + enrollment + origin + sequence | existing backend subset key and canonical conflict semantics implemented; installation/enrollment API extensions need review |
| CAREGIVER_EFFECT_ID | installation + rule schema/config + full source/window cause tuple + effect kind | derived-effect ACK/API incomplete |
| ACTIVITY_SUMMARY_ID | source EventKey for existing Node summary; new compaction object uses installation + exact source-range manifest + compaction generation | Node summary canonical event supported; substitution manifest contract OPEN |
| DAILY_AGGREGATE_ID | installation + household + local date + day-schema; revision separate immutable upload identity | OPEN backend API |
| DEVICE_STATE_TRANSITION_ID | installation + bound device/enrollment + durable transition generation + state kind | OPEN backend API |

Node application ACK = locally committed correctness obligation only. BACKEND_DURABLE_ACK = authenticated matching application acceptance of exact object ID/revision/payload, not HTTP transport success/PUBACK/provider acceptance. Backend day table should upsert logicalDayKey with monotonic accepted revisions while preserving immutable revision fingerprints; same revision/different payload conflicts. Atomic receipt selection makes completion durable. Current event COMMITTED contract is source-backed; proposed summary/daily/effect contracts are not approved or deployed.

### 21.10 Pressure, reclaim and formal proof obligations

P0 correctness/dedupe; P1 unsynced critical effects; P2 meaningful unsynced detail; P3 daily/routine aggregates; P4 synced recent history; P5 diagnostics. This is a proposed class map, not a newly locked total priority order: P3 necessary for current recovery is P0, and unsynced critical aggregates may be P1. Ownership beats labels. Thresholds should be free-sector/next-admission-cost based, not guessed percentage constants.

NORMAL: all admitted committed objects retained, sync immediately. HIGH: required admission+worst victim-copy+root reserve approaching available free sectors; reclaim P4/P5, batch routine checkpoints within proven replay bound. CRITICAL: protect P0/P1 and aggregate recovery; compact P2 only under backend substitution/approved product semantics; drain control/report to release exact evidence. SATURATED: no unsafe durable ACK, no silent critical loss; sensing/local rules continue using their independent reserve, expose storage/backlog quality. An indefinitely pinned P1/P0 workload can exhaust any finite reserve; the continuing-locally-safe critical effect saturation policy is still REQUIREMENT_GAP. Refusing every local safety event permanently would violate GS-D009/012.

Reclaim state machine: SEGMENT_ACTIVE -> SEGMENT_CANDIDATE (all current owners catalogued) -> LIVE_COPY_STARTED (source pinned; destination reserved) -> LIVE_COPY_COMMITTED (all live bodies authenticated/re-encrypted, logical identity unchanged) -> ROOT_UPDATED (all child refs/completions/certificates verified) -> RETIREMENT_COMMITTED (both surviving recovery roots or their replay mappings no longer require victim) -> ERASE_ALLOWED -> ERASED. Physical address references never survive reuse without matching serial. One reserve destination must fit worst live victim; additional roots/COW/report space charged separately.

Before record commit failure ignores tail; after commit replay recovers it; before state application recover tail; after RAM application without checkpoint redo from old root exactly once; before checkpoint activation preserve old children/tail. During live-copy failure keep source and ignore unselected destination. After root update but before retirement keep source and destination; older root cannot point to erased victim. After retirement before erase source unnecessary; during erase recover from selected destinations and quarantine/finish erased sector. After erase before allocator metadata commit, reserved unique serial is burned and sector reused only after complete erase/verified header. Backend receipt loss before selection causes duplicate idempotent upload, not local loss. Every ACKed event must be reachable from each permitted recovery root or its retained replay tail; every backend pending identity has reachable canonical content.

This is an invariant argument, **not an executable crash proof**. Need inject failure after every flash program/erase byte boundary, AEAD/length/tag/root faults, report/completion publication, nonce reservation, sector reuse and double reboot. Arbitrary malicious rollback of valid flash is not solved by AEAD alone; domain epoch/counter/security threat model must match existing authenticated storage. Fail closed on contradictory valid roots or missing pinned children; older snapshot fallback is forbidden if it loses acknowledged work.

### 21.11 Wear, rollback and build status

Do not checkpoint full6,144 B per ordinary event. Candidate cadence32 dirty events or bounded tail pressure and six-hour dirty timeout; root rotation/report batching and dirty-child updates require actual proof. At conservative twice6,144 writes per32 events, snapshot pairs/day12 /56 /726; daily aggregate320 B/day plus committed revision changes. Node bodies/day34,656 /163,584 /2,181,888. At full32 completion batches,44 B×12/56/726=528 /2,464 /31,944. Logical total excluding report/credit/dictionary/root/GC traffic:182,960 /854,496 /11,135,240 B/day. Sparse receipts/report deltas can cost more; aggregate aging reduces history footprint, not necessarily ingest/checkpoint wear.

Root publication at least one per selected checkpoint (12/56/726) plus report/COW/day/receipt transactions, not every poll. Roots rotate across three reserved sectors; peak pins may prevent perfectly equal wear. Divide baseline writes by4,032 usable bytes gives lower-bound45.38 /211.93 /2,761.72 sector fills/day. Uniform32-sector distribution would be1.42 /6.62 /86.30 cycles/sector/day before GC and excluded metadata. This is a workload warning, not endurance qualification. GC write amplification approximates1/(1-live_fraction) for repeated relocation; at50% live2×, at90%10×, no universal2× bound. Need admission selectability proof limiting maximum live victim, measured actual physical writes/erases and flash-chip rated endurance. Stress cannot yet be called indefinitely supported.

New sector format cannot be enabled as an irreversible OTA side effect. Existing firmware expects current NVS/native checkpoint <=4,549 B and cannot read this log. Fresh-install native format and legacy dev-format scope stay distinct (legacy migration remains HISTORICAL_LEGACY /optional DEFER_POST_R1). For current supported deployed format, require backward-readable transition or staged migration with old firmware rollback barred only after new image marked valid and compatible roots verified; preserve rollback-readable source until then. Never silently erase old state or reset epoch to free capacity. FOTA minimum-compatible reader/writer must be enforced by boot/install path, not merely stored in a new root old firmware ignores. Partition resizing needs a separate service/deployment decision; dual OTA app update alone does not relocate partitions safely.

Hub production build attempted with installed ESP-IDF6.0.3, no HIL flags, /tmp build directory. CMake stops at main/CMakeLists.txt:11: missing embedded node_firmware.bin. Initial Node build defaulted to esp32 and was stopped; explicit C3 rebuild uses isolated SDKCONFIG and must be assessed separately. No wrong-target binary is accepted. Explicit C3 build succeeded and supplied the generated embedded image. Current Hub build then PASS: app1,864,624 B (actual .bin), existing OTA slot1,966,080 B, margin101,456 B. Static DRAM45,783 B (134,953 remaining in reported linker region), IRAM87,359 B (43,713 remaining). These static section figures exclude runtime task stacks/heap and are not runtime headroom. Build/size provenance is preserved in the refinement evidence. Historical image sizes are no longer needed for this baseline comparison.

### 21.12 Validation and production gate

Future safe host/model tests must parameterize unresolved lease/lateness/retention values rather than choose product policy. Extend existing fixed primitive fixture with: certificate/credit induction across six sources, report loss and reboot (no credit reset), repeated exact retry with changed payload rejection, all old/new-root crash boundaries, active reference relocation, unique nonce reservation/reboot, backend accepted-response-lost and stable daily revisions, Day1/Day2 outage backfill, midnight finalization crashes/repeat, late previous-day correction, trusted/untrusted time, one missing zone vs healthy quiet zone, DST/clock changes, partial-window coverage, saturation/critical admission and million-event bounded metadata. Assert NO_ACTIVITY only in fully eligible observed windows; NO_OBSERVATION must not increment inactive baseline samples. Assert each DayKey/revision contributes once and each ACK-required input stays reachable. Cryptographic flash integration and target power failures are later qualification, not covered by symbolic old/new selection.

| Gate | Status | Closure needed |
|---|---|---|
| OFFLINE_POLICY | OPEN | approved detail/aggregate horizon and prolonged-outage behavior |
| STORAGE_PRIORITY_POLICY | OPEN | compaction substitutions and saturated critical behavior |
| RETIREMENT_BOUND | CONDITIONAL, production OPEN | credit/report protocol progress and six-source enforcement |
| BACKEND_IDENTITY | source-event existing; derived OPEN | daily/effect/substitution full identity/revision API |
| BACKEND_COMPLETION | source COMMITTED verified; derived OPEN | production caller + durable aggregate/effect acceptance |
| ROUTINE_MODEL_BOUND | candidate bounded; proof OPEN | complete codec/config/overflow/correction limits |
| COVERAGE_MODEL | requirement LOCKED; implementation OPEN | window coverage/time/reboot proof and eligibility criteria |
| DAILY_CONCLUSION | candidate transaction; OPEN | backend revisions and baseline correction/finalization tests |
| TIME_RECOVERY | OPEN | trusted clock mapping, lateness/timezone boundaries |
| ROLLBACK_SAFETY | OPEN | compatible transition and enforced minimum-reader gate |
| CRASH_RECLAIM_PROOF | OPEN | real authenticated flash fault model and allocator invariant proof |
| FLASH_WEAR | OPEN | chip rating, physical amplification and supported load |
| IMAGE_FIT | CLOSED current baseline; future engine OPEN | current app fits existing slots; new code/growth and signing reserve unproven |
| PARTITION_DECISION | UNDECIDED | prove128 KiB first; resize only approved need/current image |

ARCHITECTURE_READY_FOR_PRODUCTION_INTEGRATION=NO. Even after all gates close, this run does not authorize production integration. Next action is context promotion/reconciliation by explicit authorized workflow, then isolated failure-model tests and authenticated allocator proof, then product/backend decisions, target size/wear measurement and relevant physical qualification. No firmware/ACK/backend/PWA/partition behavior changed.

Refinement verification: unchanged storage-efficiency million-event test, existing Hub backend COMMITTED and journal/reboot/tamper/full129 regressions PASS. ASan/UBSan re-run uses leak detection disabled for the environment restriction; no LeakSanitizer claim. Static reservation sums, slot packing,72-hour calculation, workload/write arithmetic and relative Markdown document paths checked. These checks do not prove allocator, flash wear, time/coverage recovery or authenticated reclamation.

Nonce proof obligation: reserve a monotonic serial range durably in all recovery roots permitted after a crash before using any serial from that range. A single latest-root counter with fallback to a lower old counter is unsafe. Recovery skips/burns all potentially used reservations; destination erase/reuse must allocate a new serial. Sector erase/program alignment must be confirmed against ESP32 driver and any platform flash-encryption alignment before accepting84/104-byte physical sizes; additional alignment can invalidate retention arithmetic.

Daily-history requirement interpretation requiring product closure: correct daily conclusions during multi-day outage does not establish an unlimited duration promise. If it is intended to require every distinct day retained through arbitrarily long backend outage, finite4 MB flash cannot meet it. Preserve bounded current state/model and explicit quality; do not silently merge/drop daily backlog until approved sufficient-statistic/revision semantics define which distinctions may be retired. This is an OPEN retention/overflow question, not authority to weaken GS-D023.

RAM retrieval refinement: ordinary variable-size bodies may pack densely;104-byte cells are only conservative capacity accounting. The exact index's4-byte handle can be a RAM-only physical sector/offset cache under exclusive owner control; it is not a durable reference or complete generation. Read/authenticate the full segment serial before resolving it, and never reuse a sector while any selected reference remains. Stable persisted references contain full serial/offset/length. Pending bitmaps/directories reconstructed from at most38 Node records per candidate sector allow bounded scans without persisting a second full EventKey list for outbox/history. Additional directory/coverage RAM must be included in a complete target budget before integration.

Current image invalidates the earlier384 KiB recommendation: its0x1C0000 OTA slots are29,616 bytes smaller than the current1,864,624-byte image. Both256 KiB layout slots0x1D0000 leave35,920 bytes each, only1.89% of slot;192 KiB asymmetric layout has the same limiting margin. Neither resize is approved without future-engine code growth and required signing/FOTA reserve. Existing slots leave101,456 bytes (5.16%). Bootloader26,304 B leaves2,368 B before partition-table offset; table binary3,072 B stays within its4,096-byte sector. Generated table confirms current end0x400000 exactly. See [refinement evidence](../evidence/R1_STORAGE_FIRST_REFINEMENT_20261007.md).


## 22. INFORMATION DENSITY / BOUNDED CONTEXT COMPRESSION — 2026-10-07

**Status: PROTOTYPED / PROPOSED; production integration STOP.** This section replaces earlier candidate per-event size, current native retirement-size and 128 KiB retention calculations where they differ. It does not replace locked requirements, prior physical evidence or the failure/coverage/time contracts in section21. Initial context preflight PASS at `2026-10-07.002`, starting HEAD `b833b3a1f9bfb951efc25c7d9e245ca42de94b82`. All analysis/tests below precede the separately committed canonical principle/context update. Evidence: [density measurements](../evidence/R1_STORAGE_ENCODING_DENSITY_20261007.md), [raw output](../evidence/R1_STORAGE_ENCODING_DENSITY_20261007.log), [81-field inventory](../evidence/R1_STORAGE_PERSISTENT_FIELD_INVENTORY_20261007.csv).

### 22.1 Current persistent-field and lifecycle audit

**CURRENT_IMPLEMENTATION_FACT**, not a product retention requirement. Inspected the code project's `firmware/hub/components/storage/{journal,durable_journal_slot_store,durable_transition,node_retirement_snapshot}.{hpp,cpp}`, target `nvs_durable_blob_store`, `nvs_durable_key_codec`, runtime/ingest, `cloud/cloud_sync`, shared DomainEvent, and existing persistence/backend tests. The CSV inventories each serialized field/container with bytes, copies, writer/reader, reboot/dedupe/backend/routine/diagnostic need and lifetime. Registry/security audit additionally covers gs_home/id16, gs_security/wrap_key32, GSRG2 shared snapshot fields and protected PSA identity; these live in the existing24 KiB nvs partition, not the128 KiB gs_journal budget. Registry codec cap5,077 B (NVS wrapper cap8,192) is not measured current usage. Existing target installed-capacity10 is broader than the six-Node R1 design: future storage admission/dictionary/report budgeting must enforce six or rederive every bound for10; no constant changed here. Copies describe logical native owners; stale NVS page copies and physical entry/erase overhead are not measurable from application encoders alone.

Production native path is NOT three independent full journal/outbox/history bodies. HubJournal creates an encrypted legacy-shaped slot as an adapter input; the native adapter opens it and writes a Transition. That transient129-byte sample blob is not a third native persisted body. Native archive Effect.payload serves local journal, backend pending and current historical reads. Temporary Transition plus archive payload copies exist while checkpoint/replay roots pin both. Keys/session/sequence recur in transition identity, causal payload and exact-key evidence; effect ID additionally repeats a truncated payload HMAC. Completion receipt stores no second payload. Event129 still fails because immutable historical slots/archive admission are not safely recycled.

| Current native object | Actual serialized size / sample | Duplication and lifetime |
|---|---|---|
| DomainEvent payload v2 | ordinary101 B for physical32/logical6/location7; summary121 B; encoded bounds208/228 B at maximum strings | full body in Transition causal input, later archive payload; source/time fields themselves repeat within Transition identity |
| Transition | sample298 B ordinary;455/475 B at maximum strings with empty decision/effects; generic defensive cap1,332 B | event/config/ordinal/HMAC repeated per transition; tail still required until selected snapshot covers it |
| Archive chunk |64 plaintext header +4×(ID32+kind2+length2+payload101)+AEAD28 =640 B | one full payload per event; chunk owner refs, not three bodies |
| Evidence chunk | actual18 plaintext header +4×(key21+digest32)+AEAD28 =258 B | defensive cap320 and declared padding constants are not actual encoded bytes |
| Checkpoint | empty base130 B +48 B per archive/evidence reference pair;41 B extra report ref if present; opaque reducer adds variable bytes | two banks; cap4,549 B; references grow with immutable archives |
| Selector |13 plaintext+nonce12+tag16=41 B, two writes per checkpoint transaction in measured ledger | selects complete generation, not EventKey body |
| Backend completion |32 B keyed receipt per event | durable matching backend COMMITTED; archive remains unreclaimed |
| Native retirement snapshot |19 +6×(4+8+32+8+8+1+32×16)+28 =3,485 B | six fully populated32-key reports, up to three banks; cap5,777 for10 nodes. Legacy inspection bound6,096 differs |
| Migration manifests |218 B/bank,436 B for two | optional dev-era migration; not fresh R1 per-event obligation |

Current per-event physical flash bytes cannot honestly be a single constant. Using ACTUAL production codecs, the first four-event checkpoint/completion cycle writes2,656 logical blob bytes =664 B/event: body contributions202 B/event (transition+archive101 each), transition metadata197, archive metadata59, evidence64.5, checkpoint89, selectors20.5, completion32. At batch32 it writes5,632 =1,408 B/event due growing checkpoint references; across128 events132,608 B =1,036 B/event average. Empty reducer/no report updates; excludes NVS physical overhead, configuration writes, page GC and other effects. Retirement updates add a whole selected snapshot transaction, not a fixed per-event size. There is no standalone extra outbox/history body. These are measured write bytes, not simultaneously occupied partition bytes.

A sample logical event: RX authenticates Node/enrollment; native Transition commit makes it ACK-eligible; reducer applies the selected causal input; routine gets exactly that semantic input (full persistent coverage/model remains proposed); archive body + refs remain backend pending; matching application COMMITTED produces receipt; body becomes optional history only once every local/replay/dedupe owner transfers. Selected Node report may retire exact keys; current implementation does not then reclaim archive slots. Proposed lifecycle uses one immutable canonical body, RAM-derived A/O/H ownership bits and committed lifecycle transactions. Stable logical RecordId and full segment serial/offset/length survive relocation via selected roots. Never persist three payload copies for A/O/H; GC temporarily permits old+new full copies, never erases source before all permitted recovery roots stop needing it.

| Proposed lifecycle stage | Event body | Active / outbox / history metadata | Checkpoint effect / extra full-body bytes |
|---|---|---|---|
| durable HOT, before ACK | NORMAL median raw12 B +HOT framing22 B, aligned36 B; range28..124 physical | A bit/cache +selected committed extent; no repeated key list while body exists | old snapshot +canonical replay input;0 extra steady full-body bytes |
| reducer/routine applied, backend pending | same logical body; HOT remains until safe COW sealing | A/O owner bits, root-covered ordinal; outbox needs no extra full payload | bounded state deltas folded into checkpoint; field-level effect size varies, no per-event full model snapshot |
| WARM sealed pending | NORMAL median entry14 B, mean15.53125 B including entry length, excluding shared header/pad | selected block identity +pending bitmap; same body serves all owners |0 steady duplicated payload; temporary HOT/WARM copy until root/recovery pins release |
| backend accepted / recent history | same immutable body if desired history or A still needs it | authenticated receipt/bitmap transaction removes O only | backend identity derived from exact canonical body;0 duplicate history body |
| body obligations clear, exact retry evidence still needed | choose smaller safe full body or witness, not mandatory full body | witness65 B conservatively, or compressed equivalent, until selected retirement proof | no routine raw-history dependency |
| all owners clear |0 | compact report/floor/gap state independently committed | reclaim permitted only after roots/certificates updated |

Nominal eliminated independent outbox+history copies would save2×101 =202 sample payload bytes/event, but **current native code already shares those owners**, so do not claim202 B as an improvement over current native steady state. Actual removed redundancy includes current repeated physical/logical identity, per-transition config header/padding, archive IDs/HMAC duplication when full body remains, per-chunk framing and cumulative root refs. The measured steady full-body count is1 current and1 proposed;2 transient copies during checkpoint/GC are allowed. Multiple snapshots of small state are intentional crash reserve, not redundant historical event bodies.

### 22.2 Lossless bounded context and byte-level grammar

**PROTOTYPED:** `host/storage/context_codec.hpp` implements numeric source-event fixed/varint/delta/context/presence/exact-relation codecs. Enrollment Node IDs are dictionary slots with exact authenticated mapping, never truncated fingerprints. Immutable zone/physical/logical mapping must be stored/recovered in a bounded authenticated dictionary; host Event stores assignment-generation ID, not actual strings. Domain hash16 is a selector for a full authenticated registry/domain, never sole equality evidence. This mapping, target key lifecycle and segment writer remain **OPEN**.

Comparative raw codecs take Mode as an external host input; context fixture version2 does not dispatch all six modes. The mock sector always uses Relations. A production format version must bind exactly one grammar (recommended Relations), and any future mode needs a new explicit version/capability; this is not a finalized mixed-mode store. The measured numeric-only candidate uses one4,096-byte sector, max6 context rows, max497 minimum-size numeric entries. Full source reconstruction additionally needs exact string/config context; recommended independent form and corrected sizing are in22.10. No previous-record/segment delta dependency. Each record independently uses the immutable context and its own fields, not a prior decoded record. Dictionary overflow uses full absolute identity within the bounded numeric codec; physical/string mapping still has to exist in the selected dictionary. Enrollment/session changes restart context or escape. Worst arithmetic values retain full64-bit sequence/session/timestamps; zero/invalid identity rejects; numeric wrap is never interpreted as continuation under the same identity. No delta-of-delta chain, mutable dictionary append or run-length chain is recommended.

| Header offset | Field | Bytes | Why |
|---|---|---|---|
|0 | magic |4 | discover format |
|4 | explicit codec/schema version |1 | mixed format and rejection |
|5 | context count |1 |0..6 bounded |
|6 | header length |2 | bound recovery reads |
|8 | unique segment serial |8 | identity / nonce-generation binding |
|16 | storage epoch |4 | current domain; never reset for capacity |
|20 | authenticated installation/domain selector |16 | selected full registry binds ownership |
|36+58n | each immutable context row |58 | node1,sensor1,enrollment4,assignment4,origin8,base-sequence8,base-monotonic8,base-occurrence8,base-receive8,uncertainty4,battery2,RSSI2 |
|36+58count | authentication tag |16 proposed | HOT header authentication; WARM complete block authentication before any decode |
|52+58count | commit marker |4 proposed | complete header selection; not authentication by itself |

The table places tag/commit immediately after context for a HOT context header. For a sealed WARM block, only the36-byte discovery prefix may be clear AAD; the348-byte numeric context rows, full identity/config context when present, and event bodies are encrypted as one selected block; its single16-byte tag +4-byte commit are at the final selected block footer after entries. There is no separately committed header tag plus a second uncounted footer. Authenticate the complete selected block before exposing context or entries. Removed derivable max-record-count2, reserved2, unused test-default1 and padding1 per row:16 B/segment. Count/extent is selected by authenticated block/root ownership; maximum497 is schema-derived from114 B one-context overhead and8 B entry. Six-row candidate authenticated header/footer overhead404 B; one row114 B. The host context fixture v2 instead has CRC4 and totals388 B for six rows. It is not a production security format. WARM requires final block authentication over exact count/used extent/content, with tag and final commit position determined by selected extent; the404 B budget charges that tag/commit once, not a second tag per entry. Header context is reachable only through authenticated selected roots, and no item is accepted before whole-block tag verification. Candidate compact block with no per-source context uses64 B (36 B prefix+20 auth/commit+8 extent/count/mode framing).

| Body offset/order | Field | Bytes | Behavior |
|---|---|---|---|
|0 | kind4 bits +context selector3 bits +test1 bit |1 | selectors0..5,7 escape;6 invalid |
|1 | canonical presence/absolute/relation mask |1..2 |13 defined bits; overlong/unknown mask rejects |
|next, if escaped/explicit | node/enrollment/assignment/session |1 +1..5 +1..5 +1..10 | exact binding; context can omit unchanged identity |
|next | sequence delta or absolute |1..10 | bounded unsigned canonical varint |
|next | monotonic delta / absolute |1..10 | ZigZag signed; exact seconds only when divisible1,000 |
|next | occurrence delta / absolute |1..10 | signed64 preserved, overflow escape |
|next, unless exactly derivable | original receive delta / absolute |1..10 | omit ONLY if receive-minus-occurrence exactly matches immutable base offset |
|optional | changed sensor/uncertainty/battery/RSSI |1 /1..5 /1..3 /1..3 | compare immutable defaults, not previous event; preserve current canonical payload |
|summary only | additional count, first/last monotonic |1..5 +1..10 +1..10 | source-generated immutable episode summary |

Maximum ordinary raw body76 B; maximum summary raw101 B. Fixed buffer128 B includes explicit headroom, not record padding. Recommended HOT `length2 +body +tag16 +commit4`, align4: max100 ordinary /124 summary; NORMAL median36, summary-inclusive p9544. WARM `length2+body`, byte-packed under shared authentication: max78 ordinary /103 summary; NORMAL median14,p9521. Max total format span bounded4 KiB; decoder accepts only canonical exact forms and checks bounds before output publication. Actual ESP32 programming/encryption alignment may increase physical sizes: **OPEN until driver/build proof**.

Critical source kinds already represented by current DomainEvent use the same source codec. A separate derived critical caregiver effect is NOT automatically this event, and has no finalized codec/API; conservative128 B transaction allowance stays **PROPOSED**. Daily aggregate uses existing candidate300 B plaintext fields (section21; coverage208 is current-day state, not an extra daily blob). Standalone authenticated day320 B; WARM under shared block302 B including length. No daily identity schema/API is silently implemented here.

### 22.3 Encoding comparisons and measured density

The current physical Hub adapter sets hub_received_at=0 (no trusted clock); this fixture deliberately exercises a future trusted-time scenario while retaining full zero/untrusted support. It does not prove NTP/day assignment on current firmware. Fixed-codec timing includes computing the prior experimental CRC before stripping it; other decoder timings include canonical re-encode validation, so these are prototype implementation timings, not optimized production comparisons. Synthetic rates retained unchanged:384 /1,776 /23,232 source semantic records/day, not guarantees. Node already coalesces motion episodes (first motion +immutable repeat summary; quiet~45 s/bounded online~5 min). Not every electrical PIR edge is an event. [Three-day scenario annotations](../evidence/R1_STORAGE_ENCODING_DENSITY_SCENARIO_20261007.csv) describe Node/Hub/backend availability, daily/critical/late/backfill conditions; they are not encoded extra records or executed failure-model proof. Fixture NORMAL120 summaries+24 other source events; HIGH720+96; STRESS11,520+192; remaining records are first-motion events. Thus stress includes conservative dense opening/summary traffic, not a qualified continuous-motion claim. Real timing/room distributions, offline episode behavior and supported configuration maxima still need trace capture. Six interleaved sources, kitchen/bathroom/room assignment dictionary, domain Reed/button/control examples, reboot-origin changes, delayed receive/uncertainty and health-like sequenced source events are included. Periodic unsequenced NodeHealth excluded. Hub connectivity/device transitions and derived critical/daily effects need their separate codec/contracts: source distributions alone do not establish complete caregiver-outbox rate. Daily capacity simulations add one300 B aggregate/day. Critical allowance is separately reserved; additional ancillary normal transitions consume the remaining pool, not free bytes.

NORMAL measurements (raw body, excludes auth/framing; complete HOT/WARM comparisons in raw output):

| Model | Raw min /median /p95 /max /mean B | encode/decode ns | Authenticated candidate HOT median /mean B | WARM entry median /mean B |
|---|---|---|---|---|
| A current production | sample101 /summary121; max208/228 payload;298 sample Transition |168.76 encode payload; AEAD/flash excluded |not equivalent; current native ledger664..1,408 logical B/event |native archive4-source chunk640 B |
| B fixed binary |64/64/84/84/70.25 |364.33 /514.81 |84 /90.25 |66 /72.25 |
| C unsigned varint |27/27/36/36/29.8125 |123.73 /363.50 |52 /54.5 |29 /31.8125 |
| D timestamp/sequence delta |15/22/31/31/23.2135 |150.37 /360.51 |44 /46.6042 |24 /25.8490 |
| E immutable context +delta |11/18/27/27/19.2161 |119.51 /329.06 |40 /42.6875 |20 /21.8490 |
| F/G context +presence +bounded dictionary |6/15/24/24/16.0026 |121.60 /298.36 |40 /39.625 |17 /18.8750 |
| recommended: exact context relations |6/12/19/19/12.5938 |135.17 /294.96 |36 /36.1354 |14 /15.53125 |
| H optional immutable cold zlib probe |12 independently restartable 32-record blocks:9,570 plain ->4,233 compressed;4,473 with20 B/block auth allowance |123,430.99 /7,517.80 per block Python |NOT HOT; not selected |workspace/code target unknown; Python encode traced peak300,905 B |

WARM means include length, use actual per-sector restart contexts and may differ from HOT raw means because boundaries differ. Sector headers and unused tails are charged separately in capacity calculations. Worst global fallback103 B WARM /124 B HOT exceeds every trace's measured max; the trace p95/max is NOT a guaranteed bound. Source Summary adds only its variable extension; do not allocate a fixed20 B extension to every ordinary event.

All raw codecs workspace128 B +context568 B (host ABI). Fixed format repeats all fields; varint alone remains individually addressable. Delta/context have one bounded immutable dependency; indexed random access decodes one record after context/authentication, no chain scan. Common boot work is O(partition bytes +records), bounded131,072 B; no full scan during normal lookup. Dictionary/presence/exact relations increase version rules and context binding tests; numeric context corruption blast radius at most one sector. A shared external dictionary could affect every bounded live segment referring to it; do not claim a one-sector full-identity blast radius without self-contained identity restart or independently replicated dictionary roots (22.10). HOT per-record authentication can fail one record but corruption/missing context makes its sector unavailable; root reachability detects missing pinned data and fails closed. WARM requires sector authentication before any item is exposed; do not interpret partially valid entries after a bad tag. No compressor library is added to firmware; general compression rejected pending target code/workspace/benefit measurements. RLE/state-change-only and semantic aggregation need product/backend sufficiency contracts before discarding distinctions. ZigZag, varints, enums, exact-unit deltas and immutable defaults are lossless; no floating-point history encoding is needed.

### 22.4 Security overhead and failure boundaries

Prior estimated108 B =compact prototype68 +nonce12 +tag16 +length2 +RecordId4 +generation2 +commit4. The68 includes CRC4. Candidate fixed lossless body64 can omit CRC ONLY inside a verified authenticated envelope. Stable identity comes from full segment serial +offset; not a separate4-byte per-record ID. Per-event generation/schema/security-domain repeat moves to independently authenticated context. A unique12-byte nonce can derive from durably reserved64-bit segment serial +32-bit position/type-domain; it cannot simply derive from a counter that resets on reboot. Tag16 remains per HOT event; commit4 and length2 remain. Fixed ordinary84 B is this derivation, not weakening AEAD. Segmented raw variable HOT22 B envelope +0..3 pad; WARM2 B entry framing with amortized20 B tag/commit per sector; context itself404 B six rows.

For the same compact fixed payload, removing repeated nonce12+RecordId4+generation2+CRC4 saves22 B before padding; this is a PROPOSED envelope comparison, not current native improvement proof. For recommended NORMAL WARM,404 B/roughly230 source records per sector ~=1.76 B total context/header per entry;20 B authentication/commit alone ~=0.087 B/entry. Sparse traffic pays full header/tail. Do not claim universal per-event security savings: HOT retains16-byte tag, WARM saves per-record tags only after sealing/COW selection. No reduced key/tag strength or CRC substitution for authentication.

Authentication must bind format/domain/epoch/serial/full immutable context, physical position/length or complete ordered block contents, count/used extent, and logical root ownership. This detects context swaps, reordering/insertion, wrong generation and torn writes. **AEAD alone cannot detect deletion/truncation of an entire valid tail/segment or replay of an old valid inventory.** An independently authenticated authoritative root/committed-extent ledger must anchor every ACKed append before ACK; the root/ledger anti-rollback model must match current threat requirements. Candidate extent transaction44 B (serial8,extent2,count2,covered/cursor8,tag16,commit4,pad4), max32-item tail1,408 B, is an allowance, not an implemented durable algorithm. If per-event authenticated inventory publication cannot fit its reserve/wear/atomicity bounds, this budget fails. Raw decoder under wrong context can decode a plausible different event; only authenticated context binding makes that illegal.

| Failure point | Required recovery / present host coverage |
|---|---|
| segment/context creation | no record uses uncommitted context; CRC fixture header truncation/corruption tested; real encrypted header publish OPEN |
| append before marker/extent selection | old authoritative extent valid; no ACK; byte-tear fixture tests old/new selection |
| append after durable commit before ACK | root-anchored tail recovers exact event; Node retry Duplicate; target extent selection OPEN |
| dictionary change | immutable rows never patched; new independent header/absolute escape; dictionary boundaries tested; external mapping COW OPEN |
| checkpoint | old state +covered-tail, or complete new child/root; covered ordinal prevents double apply; existing native tests retained; new engine roots OPEN |
| HOT->WARM / WARM->COLD | copy canonical identities unchanged; authenticate whole destination before any ownership moves; source pinned while any old root may recover |
| live copy / root update | fixture tests every destination byte cut with externally selected old/new roots; authenticated root transaction/erase not implemented |
| erase / allocator metadata loss | only after every permitted root releases source; erased physical sector gets never-reused serial; target erase/nonce proof OPEN |

Million-event model explicitly releases owners at reuse, maintains at most192 keys, periodically rebuilds exact index; it **does not prove product retirement, indefinite outage safety or authenticated GC**. Tests use CRC for mock sector tears and host AES-GCM separately to test AAD/nonce/position binding. They do not combine into a production encrypted flash store. Wrong domain/generation, context bytes, canonical varints/lengths, extrema, random decode fuzz and truncation all reject. Preserving old source during all COW cuts is proven only under the model's externally supplied root.

### 22.5 Active bodies, certificates and finite retirement invariant

Six×32 Node retained pending =192 currently pending keys, NOT a finite bound on all historical Hub evidence without report progress. Lost report, radio outage, reboot/rejoin can leave prior acknowledged keys unknown indefinitely. A highest-sequence floor is unsafe with gaps/multiple origins. Body count also includes uncovered reducer inputs and unsynced backend content independently of Node retention. Need to distinguish full source bodies from exact certificates and per-origin/report/gap state.

Conditional existing proposal: each Node starts with at most32 exact keys listed in a durably selected authenticated complete report; allow at most32 new distinct admissions before a newer selected report releases/replenishes credits. Reports/reboot/rejoin never create free credit; retransmission of an existing exact key consumes no new credit; generation transition cannot discard old listed origins; retirement validates complete pending set and safe exclusion. Induction: at most64 evidence obligations/Node =>384 total;32 aggregate COW/in-flight margin =>416. Production does not enforce this admission/progress contract, and saturated safety behavior remains OPEN. A host fixture with192 live keys does not prove this384 bound.

Dedupe alone needs **0 full payload bodies** after an authenticated safe exact witness can verify identical retry and all other body owners clear. Recovery needs up to32 proposed uncovered canonical inputs between checkpoints; they may already be the shared backend bodies, not32 duplicated bodies. Backend pending has independent bounded pool; there is no safe universal192-body total guarantee. Minimum exact witness count varies0..384 under the conditional credit invariant; without it no finite historical maximum is proven. Conservative witness row65 B =key21 +current payload HMAC32 +assignment-generation4 +original receive-time8; current digest includes canonical Hub receive/location inputs, so retaining merely key+truncated digest is unsafe. Recompute retry with original canonical context or exactly compare surviving full body. Optimizing which fields Node retransmits vs Hub annotates requires existing ingest/digest contract review. Keep compressed full body when it is cheaper than65 B and safely supplies all witness inputs.

Seven independently authenticated witness sectors with64 B header and65 B rows give7×floor(4,032/65)=434 certificates >=416 at28,672 B; selection/count/context integrity still required. This replaces arbitrary416×104 full-body reserve, but does not invent retirement progress. Six-node report banks at3,485 each fit within12 KiB separately. Their absent listed keys allow retirement only under authenticated generation/report rules; no unsafe watermark replaces exceptions.

### 22.6 Retrieval and RAM budget

PROTOTYPED exact index:416 packed rows(key21+RAM handle4)=10,400 B +1,024×uint16 hash slots=2,048 B +4 control =12,452 B. Hash only accelerates lookup; equality compares all21 bytes. Backshift deletion avoids tombstone-age growth. Expected O(1), deterministic worst1,024 probes, deletion/insertion bounded likewise; adversarial hash collision remains bounded, never false Duplicate. A handle is only RAM sector/offset cache: verify full selected serial before read; never persist/reuse bare offset as identity.

Candidate source directory for7 sectors:7×497×offset2 =6,958 B. Three A/O/H bitmaps:7×3×ceil(497/8)=1,323 B. Critical two sectors of31 reserved128-byte effects:124 B offsets +24 B bitmaps. Segment descriptors32×32=1,024 B; queue cursors256 B. **INDEX_RAM=22,161 B candidate**, includes exact12,452 index; not a measured target allocation. Direct RecordId is full serial/offset mapped to selected descriptor. Backend queue selection scans at most32 descriptor entries then fixed bitmaps; O(32+ceil497/word_bits), critical service has separate bitmap; random/recent reads use offset directories, O(1) slot access plus one authenticated sector (<=4 KiB) and one decode. Current-day/model are direct selected state, retirement direct six reports, reclaim candidate O(32) descriptors +bounded live-owner bitmaps. Boot scans<=131,072 B, reconstructs directories/ownership and exact entries; contradictory roots/missing live children fail closed, not best-effort skipped data.

| Candidate RAM allocation | Bytes |
|---|---:|
| bounded indexes/directories/cursors above |22,161 |
| routine model2,848 +current-day512 |3,360 |
| RX buffer |512 |
| raw encode buffer |128 |
| sector reclaim/authenticate work buffer |4,096 |
| checkpoint encode/COW workspace |6,144 |
| one decoded context workspace |568 |
| **static/owner workspace total** |**36,969** |
| separate maximum stack allowance (unproven target call graph) |2,048 |
| **candidate total** |**39,017** |

Correctness hot codec/index C++ heap0 in host million-event path. Host fixture itself allocates six in-memory mocked sectors34,080 B +12,452 index =46,532 B, placed on host stack only; do not copy that layout to target stacks. OpenSSL host test/Python compressor/internal production strings and vectors allocate outside portable hot measurement. Proposed sector workspace is reused for verification/GC under single owner; concurrent operations need another allocation or scheduling. Current target linker DRAM45,783 B does not establish free runtime RAM for this new engine: task/Wi-Fi/crypto heaps and new code require later measurement. New RAM and root/driver workspace remain gate inputs, not target-qualified claims.

Host retrieval54.30 ns exact lookup;317.42 ns random mock-sector read;23,586.71 ns32-record reboot reconstruction scanning1,096 B. Median9 timed runs after warmup. Sourcecodec recommended135.17 ns encode/294.96 decode; excludesAEAD/flash. No ESP32 cycle/latency claim. Stress mean23,232/day=.269 events/s, but radio rejoin creates bursts; target measurements must bound those bursts. Representation chosen for density and independent retrieval, not host speed. No CPU micro-optimization added.

### 22.7 Routine/daily state and information aging

Prior failure-aware bounded model remains PROPOSED:2,560 flash /2,848 RAM,512 current-day,coverage208 INCLUDED in current-day; combined current model RAM3,360. Checkpoint candidate6,144 B includes model2,560 +day512 +reducer2,048 +header/refs1,024, not separate additional copies of every field. Incremental fixed-point counters, first/last, six-zone sessions/duration/time histograms, weekday/weekend running count/mean/M2 and trend/confidence update only affected zone/bucket; O(1) except bounded six-zone/day-close work. No raw flash history replay in normal learning. Overflow/eligibility/time/lateness/revision policy remains OPEN. NO_ACTIVITY requires observed eligible intervals; failed sensors/Hub or untrusted time produce NO_OBSERVATION/quality, never fabricated inactivity. New codec preserves uncertainty/timing; it does not implement coverage leases/daily conclusions or remedy their outstanding proofs.

Daily candidate300 B plaintext /320 independently authenticated; WARM302 with length under shared block. Stable installation/household/local-day/schema ID plus immutable revision remains required. Day finalization atomic old/new root selects aggregate, model applied-revision, backend intent and next day; absent backend revision API no unsynced-detail substitution is authorized. Daily-only30/90/365 raw bodies9,000/27,000/109,500 B; warm entries9,060/27,180/110,230 B. With64 B independent block header and13 daily entries per4 KiB sector, allocated12,288/28,672/118,784 B (does not include separate fixed engine reserve). Long-term365-day local history is not a requirement; backend stores it.

HOT->WARM is lossless physical packing and can transfer all original canonical fields. WARM->COLD may discard already-backend-accepted optional detail after safe state materialization. Unacknowledged semantic detail may be replaced with compact sessions/daily aggregates ONLY after approved backend substitution/idempotency and product information-priority rules. Current Node summary already coalesces raw motion; Hub must not count it as a new independent session or sum episode start+summary twice. One daily aggregate/day is not automatically equivalent to a timeline, button/door/critical event, nor proof of complete coverage. Infinite critical/day backlog cannot fit finite flash; continued safety requires explicit saturation/retention behavior. Diagnostics (routine polling RSSI/latest NodeHealth/debug strings) should remain RAM/bounded stream unless their transition/quality matters. Current RSSI/battery in canonical source payload cannot simply be stripped; dictionary defaults preserve them losslessly.

Compaction-only capacity in7 source pool sectors is91 daily aggregates =2,184 h /91 days at one/day, same duration for all activity scenarios; plus protected critical reserve, model and current state. This is a **candidate daily-information ceiling**, NOT full-detail/offline guarantee and not implementable for pending source replacement under current backend contract. Critical-only reserve:62 candidate128-byte effect cells in two64-header sectors; hours/days are `62 / approved critical-events-per-day`, currently unknown. The32-record burst allowance remains conditional, not arbitrary product guarantee. Normal source traffic never spends critical/engineering reserve.

### 22.8 Exact 128 KiB rebudget and retention comparison

**PROPOSED conditional reservation**, no partition table change. Categories do not count RAM indexes as flash, do not double-count checkpoint/model or source body/outbox/history. Auth headers/padding/unused tails are charged inside their sector reservations. Old native simultaneous transition/migration storage is not assumed compatible with this candidate; rollback/source-format coexistence needs separate sizing.

| Category | Reserved bytes | Purpose / reclaimability |
|---|---:|---|
| ACTIVE |28,672 |7 sectors,434 conservative65-byte witnesses; share source body when available; reclaim only exact retirement/owner release |
| RETIREMENT |12,288 |three six-node native snapshot banks, actual3,485 B each; report/live generation protected |
| ROUTINE +CURRENT_DAY +REDUCER checkpoint/COW |20,480 |three6,144-byte candidate images packed with framing; includes2,560 model +512 day; 3-copy packing/proof OPEN |
| ROOTS |8,192 |two rotating authenticated root sectors; GC scratch supplies rotation staging; this replaces prior3-sector root proposal and requires proof |
| SEGMENT /LIFECYCLE /DICTIONARY |8,192 |bounded selected descriptors, exact physical string mapping, completion/extent deltas; peak churn/append selection still OPEN |
| GC_COW |12,288 |live destination, victim/root scratch and commit reserve; old source never invalidated prematurely |
| CRITICAL |8,192 |candidate32-effect transaction burst,62 cells at128 B; prolonged saturation OPEN |
| ENGINEERING |4,096 |kept outside normal admission |
| **FIXED_OVERHEAD** |**102,400** |100 KiB; includes model/day/checkpoint/critical/GC etc |
| **VARIABLE_EVENT_POOL /BACKEND/HISTORY** |**28,672** |7 sectors share canonical body and logical owners; daily objects consume this pool |
| **TOTAL** |**131,072** |exact existing128 KiB |

No separate large backend payload reserve, history reserve or per-event duplicate EventKey directory is persisted. Native report reserve is conservative; full-source-body per-event HOT->WARM staging, dictionaries, append-extent/root pins may consume more than currently reserved. The arithmetic fits; **allocator simultaneous-peak/crash proof does not yet exist**. Optimizing active witness ownership and roots is what releases room compared with section21's76-record conservative independent-reserve case; codec improvements alone do not prove that policy-neutral candidate can integrate.

Measured whole-sector capacity under this SAME fixed100 KiB allocation, including one300-byte daily body +length2 at every elapsed synthetic day; seven variable sectors:

| Scenario | Fixed binary pool: records /hours /days | Recommended context pool: source records /hours /days | Full3-day source+day allocation incl fixed |
|---|---|---|---:|
| NORMAL384/day |383 /23.9375 /0.997396 |**1,595 /99.6875 /4.153646** |126,976 B (6 sectors detail +fixed) |
| HIGH1,776/day |377 /5.094595 /0.212275 |**1,476 /19.945946 /0.831081** |208,896 B (26 sectors +fixed) |
| STRESS23,232/day |365 /0.377066 /0.015711 |**1,619 /1.672521 /0.069688** |1,339,392 B (302 sectors +fixed) |

72 h NORMAL comparison:1,152 source events +3 daily entries, independent sector context/framing/tag/padding charged,6×4,096 +102,400 =**126,976 B**, **4,096 B spare** within128 KiB. `72H_FITS_128K=YES_FOR_THIS_TRACE_AND_CONDITIONAL_RESERVATION`; this neither locks72 h nor proves all approved failures/rates fit. Current-generation dictionaries/live-source reconstruction/nonce/root/COW/critical/ancillary peaks remain proof gates. Worst source escape103 B WARM yields only35 entries per404-header sector,245 in7 sectors, before daily/extra events; thus this trace result is not a guaranteed minimum horizon. Safe source-only worst72 h normal1152 records needs33 sectors +3 daily entries potentially another sector; actual mix/layout required, not trace median multiplication.

Information-density scorecard uses explicit denominators to avoid comparing logical writes with occupancy: Fixed vs recommended NORMAL raw meaningful numeric-field body70.25 vs12.5938 mean; fixed WARM actual full-day allocated28,672 vs8,192 B =>3.5× one-day sector occupancy improvement. Same seven-sector pool retention1595/383=**4.16449×** with daily entries. Current production101 B sample payload vs12 B raw median is encoding comparison only, not backend-field equivalence proof until full dictionary strings are selected. Recommended WARM median14 vs fixed66 saves52 B entry, before shared header; recommended contextual vs noncontext varint raw mean29.8125->12.5938 saves17.21875 B/event losslessly in NORMAL fixture. Useful-information ratio has no defined product weighting. Compare retained complete canonical numeric source information under the same bounded pool:4.16449× source-record capacity vs fixed encoding, not a literal percentage of physical bytes. Current archive literal-payload fraction404/640=63.125% for the measured ordinary four-event chunk includes redundant context. Optimized literal-payload fraction is not a valid useful-information comparison because compression changes its numerator; no scalar semantic usefulness percentage is claimed. Current fixed overhead depends installed NVS objects, not a stable measured number; proposed fixed overhead100 KiB is a worst-reservation ledger, not current usage measured from flash.

`CAN_128K_SATISFY_LOCKED_R1_REQUIREMENTS=CONDITIONAL`. Offline/full-detail guarantee, product substitution/saturation policy, retirement credit invariant, exact digest projection, daily/backend API, trusted time/coverage/late correction, rollback, authenticated append/root/GC/nonce allocation, peak dictionary/state/COW and target runtime RAM/wear remain OPEN. No partition enlargement is proven necessary by this trace; no unconditional128 KiB acceptance. Compare physical options only if those gates define a larger approved need:128/192/256/384 KiB keep dual OTA, current app1,864,624 B; current0x1E0000 slots1,966,080 margin101,456;192 KiB asymmetric/256 KiB0x1D0000 limiting slot1,900,544 margin35,920;384 KiB0x1C0000 slot1,835,008 fails by29,616. Future code/signing/growth reserve remains open. Recommend KEEP EXISTING LAYOUT during proof work; partition decision UNDECIDED, no hardware migration.

### 22.9 Write amplification, FOTA and next STOP gates

Wear cannot be derived from occupancy alone. Source durability HOT at measured average36.1354 /37.9459 /36.9384 B writes/day13,876 /67,392 /858,152; sealed WARM allocated source-only one-day8,192 /36,864 /413,696 includescontext/tail, source-recordcount and header writes2/9/101 perday. HOT source sectors4/19/234 perday beforestate/metadata/GC. Sealing once writes a second denser encoding, not a third permanent payload; baseline sourceencodingwrite/day upper allocation24,576 /114,688 /1,372,160 if full sectors programmed; program actual committed bytes instead where permitted. Raw committed HOT+WARM lower source traffic roughly20,648 /101,707 /1,269,381 including WARMheader and excluding unused tails. Per-event inventory/extent44 B adds16,896 /78,144 /1,022,208 if needed every ACK; cannot batch ACK authority away for performance. Completion metadata may batch after backend receipts, but Node durable commit may not wait on cloud.

Checkpoint cadence candidate32 dirty events or bounded dirty-time/replay pressure:ceil(rate/32)=12/56/726 groups perday; two6,144-byte selected/recovery images cost147,456 /688,128 /8,921,088 B/day. This is intentionally conservative; actual dirty-child copy budget/rotating roots must be measured, not rewritten per event. Daily conclusion300 B +sharedframing perday; finalization revisions add writes. Checkpointroot updates at least12/56/726 plus append/report/completion/day/GC transactions. Root/dictionary/completion journals need rotation before overwrite; two root sectors require scratch and old-root-release proof. Dividing HOT+WARM+per-event44+two-state-image baseline by4,096 gives approximate lower physical-sector-fill equivalents45.2397 /211.9827 /2,737.5437 perday before reports/root/witness/GC; not actual erased sectors nor chip lifetime. At evenly spread32 sectors these are1.4137 /6.6245 /85.5482 per-sector/day. Hot roots and current state can wear faster. Sector relocation WA≈1/(1-live_fraction),50%=>2×,90%=>10×; no asserted2× maximum. Flash chip endurance/program alignment unknown; no invented cycle rating. Need measured target programmed/erased bytes, victim-live bound, state batching/cadence and rated chip before wear gate closes. Density improves offline capacity; it does not alone guarantee long life under stress.

Format strategy: explicit version on every independently restartable sector; capability/minimum-reader bound in boot/install policy, not a root old firmware ignores. New firmware dual-reads current native NVS and new format while migration/rollback protection is evaluated. Existing old firmware cannot read new log; ROLLBACK_SAFE=OPEN, dual-read REQUIRED for deployed-format transition, rollback barrier may be REQUIRED only with validated image and enforced compatibility. Preserve old rollback-readable source until safe activation; no automatic epoch reset or irreversible OTA side effect. Mixed-format selected children require version-dispatched authenticated validation. Partial migration selects old complete state or full compatible new state; development-format migration remains HISTORICAL_LEGACY/optional under GS-D001. No production format activated or partition relocation.

PROVEN: current codec size/ledger facts, lossless canonical host roundtrips/bounds, fixed-buffer memory, exact-index prior collision coverage, independent restart/position-auth binding experiments, model old/new COW byte cuts, million-event explicitly released-owner bounded fixture, unchanged current source/backend durability regressions. PROTOTYPED: six numeric source encodings, CRC mock sectors, host AES binding, trace packing, Python cold probe. PROPOSED: target AEAD envelope/shared-block authentication, root/extent ledger, string dictionary lifetime, conditional witness/credit reserve,100+28 KiB budget,32-event materialized cadence. OPEN: actual durable allocator/reclaim/security proof, saturated safety, backend derived identities/substitution, routine/time/day corrections and complete target RAM/wear/FOTA growth.

No production integration is authorized. Next engineering task after authorized canonical context promotion: define and prove authenticated append-inventory/root/nonce/COW allocator with allbyte/program/erase failure cuts; prove selected string/context dictionaries and65-byte witness canonical retry; close persisted retirement credits/progress without stopping safety; decide backend daily/substitution/saturation/retention/time policies. Re-run relevant host/million/failure tests, build/measure future firmware size/RAM, then only separately authorized target qualification. Do not repeat physical fresh-install qualification until an integration change invalidates it. This host run never flashes, generates PIR/HIL, changes BAT-C8/Jira/backend/PWA/ACK or partition CSV.


### 22.10 Full identity/configuration context and jitter correction

**This subsection qualifies earlier source-numeric sizes/retention in22.2/22.3/22.8.** A numeric dictionary selector is not a complete physical/logical/zone identity. The production Transition also carries config-version4 +config-hash32, which recovery must preserve. These bytes may share context but cannot vanish. Two safe directions: pin bounded authenticated immutable dictionary/config snapshots by exact selected reference (peak count/proof OPEN), or carry exact source dictionary and config binding at each independent sector restart. Recommend the latter for the first full-source format until a smaller shared-dictionary lifetime/recovery proof exists. Lossless numeric host codec is implemented; full string/config serializer/reader and real AEAD/root integration are NOT implemented or qualified.

Self-contained source header addition: per context, physical ID length1+bytes<=64, logical ID length1+bytes<=24, location/zone length1+bytes<=64. Numeric row already supplies node/enrollment/assignment/origin/sequence/time defaults. Whole header also carries immutable config-version4 and config-hash32. For the actual production-code sample used in the benchmark (32/6/7-byte names), addition36 +6×(3+32+6+7)=324 B; numeric authenticated overhead404 ->**728 B**. Maximum permitted strings addition36+6×155=966 ->**1,370 B**. Generic fixed numerical record needs explicit dictionary binding tuple9 per row too:64 B envelope +36 config +6×(9+48)=**442 B**. No repeated per-event strings or config hash. Header positions: prefix0..35 as22.2; config-version at36..39, hash40..71; six rows follow, each58 numeric bytes then three length-prefixed strings; final authentication/footer. Variable string lengths must be bounds checked; reserved namespaces/ownership must be exact, not fingerprint matching. Schema must explicitly dispatch this future grammar rather than silently reuse experimental numeric-only v2.

All context rows/identity strings/source body and any other data encrypted by the current format remain encrypted. For HOT, encrypted context has its own16-byte tag/4-byte complete marker, and each event AEAD binds that authenticated context/position/length. For WARM, encrypted context+ordered entries use one whole-block16-byte tag/4-byte commit, with discovery prefix and selected count/extent bound as AAD. The raw host context and synthetic AAD experiment are plaintext test fixtures; they are **not authority to deploy plaintext sensitive headers**. Derive nonce only after unique serial reservation; HOT->WARM uses a new serial/key domain, never reseals with an already used nonce. After reboot/torn append burn unproven offsets or the open segment unless a durable offset-reservation proof exists. Full-block dictionary/config corruption makes only that sector undecodable; selected roots detect missing pinned data and fail closed. Selected full config objects/keys are bounded root dependencies, not a prior context chain.

Minimum full-identity single-context header36+36+58+5(minimum three string lengths+nonempty physical/logical bytes)+20=155 B gives<=492 eight-byte entries; six-context sample header728 gives<=421, max-string1,370 gives<=340. RAM directories retain497 as conservative numeric prototype upper bound, so no underallocation. Full identity views can borrow the authenticated4 KiB buffer; if using owned strings instead, budget up to930 additional bytes plus36 config. Candidate39,017-byte RAM allowance becomes up to**39,985 B** with a separately owned,8-byte-aligned1,536-byte context workspace replacing568. This is host-layout sizing, not target RAM proof. Outbox/history still share the same canonical source body; dictionary/config binds source reconstruction, not a second body.

A binding absent from a self-contained segment dictionary must start a new independent restart or carry an explicitly bounded full identity extension. Numeric absolute escape alone is insufficient to reconstruct new physical/location strings. Such churn is not in the fixed six-label trace. Origin-only change may use absolute session/sequence escape under the same exact node/enrollment/assignment binding. Config/time/assignment changes need selected immutable binding and a checkpoint/control barrier or equivalent bounded ordered replay: do not replay an old input with a new rule/time mapping. Stable EventKey/backend identity remains unchanged by relocation/sealing. Rule config blobs/late/time semantics and peak pins remain STOP gates.

Density sensitivity now includes exact string-length cost and native configuration binding, at the same original384/1,776/23,232 rates. Additional deterministic fixture uses20 ms polling jitter `(i*23 mod50)*20` in source monotonic time and a receive-offset change from1 to2 s on every seventh record (sparse multi-hour delay retained). No integer-second rounding: this tests when the exact-second shortcut is unavailable. Jittered raw codec roundtrips added and sanitized. These are scenarios, not sensor measurements. Independent source dictionary/config bytes are **layout-cost/proposed-envelope sizing**, not a new string codec or crypto implementation.

| Full self-contained variant /rate | source records in7 sectors | hours /days |3-day bytes incl fixed100 KiB +daily |
|---|---:|---|---:|
| sample names, uniform NORMAL |1,469 |91.8125 /3.825521 |126,976 |
| max names, uniform NORMAL |1,193 |74.5625 /3.106771 |131,072 |
| sample names, jitter NORMAL |**1,281** |**80.0625 /3.335938** |**131,072** |
| max names, jitter NORMAL |**1,056** |**66 /2.75** |**135,168** |
| sample names, jitter HIGH |**1,347** |**18.202703 /0.758446** |217,088 |
| max names, jitter HIGH |1,103 |14.905405 /0.621059 |241,664 |
| sample names, jitter STRESS |**1,457** |**1.505165 /0.062715** |1,466,368 |
| max names, jitter STRESS |1,181 |1.220041 /0.050835 |1,789,952 |

Fair self-contained fixed baseline at same sample strings/config:350 /343 /336 records in same pool; NORMAL jittered context gains1281/350=**3.66×**, HIGH1347/343=3.9271×, STRESS1457/336=4.3363×. Numeric-only4.16449× remains correctly labeled a narrower source codec result. Preferred source entry remains variable lossless binary (numeric entry min8,max103), plus728-byte sample/1,370-byte maximum independent context. Median14 from uniform numeric trace is not a universal production typical size; jitter/backend/time/config churn can increase it. Daily standalone320/plain300 and91-day daily-only ceiling remain proposed, with approved identity/revision and substitution prerequisites unchanged.

**Corrected72-hour interpretation:** sample names+jitter need131,072 B, margin0; maximum names+jitter need135,168 B, deficit4,096. The earlier126,976 B/4 KiB margin remains ONLY uniform numeric/source-sample comparison. `72H_FITS_128K=CONDITIONAL_BY_CONTEXT_AND_TRAFFIC`, not a locked promise. Because72 h is not required, this is not proof that R1 needs a larger partition. If product later locks this full-detail/max-name scenario, source pool needs8 sectors and lifecycle minimum132 KiB under the same unproven fixed ledger, before any additional simultaneous-peak/alignment margin. Review192 KiB versus unused-flash/OTA alternatives only after that actual requirement and image/FOTA proof; no table or hardware change approved now.

Wear numbers22.9 apply to numeric-only source envelopes; they are lower than a complete self-contained engine. Every source HOT/WARM segment additionally writes324 B sample identity/config or966 B max; jitter changes bodies/restart frequency too. Physical erase/WARM header counts cannot be inferred by simply adding averages. Full-source append-extent/root, directory, witness projection and GC copying must be instrumented. No complete flash endurance claim. Extra record details/derived effects, mapping churn, repeated reset, metadata/COW peaks, format alignment and config barrier costs still make current128 KiB feasibility **CONDITIONAL**, production ready **NO**.

Critical reserve correction for full-source headers: the earlier62 generic
128-byte cells assume a64-byte header. A1,370-byte full-source context instead
permits21 such cells per sector,42 across the two reserved sectors, before
additional lifecycle metadata. This still exceeds the candidate32-effect
transaction burst, but neither that burst nor a final critical-effect codec is
product-approved; indefinite critical saturation remains OPEN.

### 22.11 Interrupted-run closeout

Final host/regression/sanitizer PASS output was recovered and preserved; no
expensive passed run repeated. The sanitizer session handle was lost, but the
terminal million-event PASS matches the evidence byte-for-byte. See the
[evidence closeout](../evidence/R1_STORAGE_ENCODING_DENSITY_20261007.md) for
provenance and all uniform/name/timing results. Only the missing one-day entry
size calculation was completed, with the existing codec and independent HOT
and WARM restart packing. Numeric body median13 B, HOT median36 B, WARM
median15–16 B under timing variation; full-source mean WARM17.5052 sample /
17.2760 maximum-name B. Shared context728/1370 B and padding are charged
separately. Use16 B only for typical-entry comparison, never worst-case
retention; global maxima raw101/HOT124/WARM103 remain.

Recommend the independently restarted lossless context/change/delta format
for further proof, keeping the existing128 KiB partition. Full-source jitter
retention is1281 sample /1056 max-name NORMAL records (80.0625/66 hours).
72h source+daily comparison costs131072/135168 B under the conditional100 KiB
fixed ledger; zero margin/4096 deficit. No production72h promise, partition
requirement or proof that every locked R1 requirement fits. Source/config/name
serialization, authenticated allocator/root/nonce/COW, retirement credits,
backend derived completion, overflow/retention, coverage/time/day recovery,
rollback and target RAM/wear remain STOP gates.


## 23. Active/retirement bound and reclamation proof checkpoint

See [focused lifecycle evidence](../evidence/R1_STORAGE_RETIREMENT_RECLAIM_PROOF_20261007.md)
for source trace, per-transition lifecycle table, proof/counterexample, exact
certificate format, COW cut matrix, ESP-IDF NVS physical accounting, raw byte
ledger and frozen-codec retention sensitivity. **Codec frozen; host-only.**

PROVEN: six production Node queues/recovery permit32 sequenced pending keys
each (192), including sequenced Heartbeat, excluding unsequenced NodeHealth.
A complete selected pending set retires its covered complement without losing
sequence holes. Current event ACKs do not guarantee report progress: one-slot
Node plus successful ACKs/lost reports produces arbitrarily growing Hub
unreported evidence. **192 is not a historical Hub evidence/body bound.**
Current128 archive limit remains unchanged; event129 still Full.

HOST-MODELED conditional finite invariant: per owner at most32 reported pending
keys plus32 new uncovered admissions, persisted with report/evidence state;
reboot/new transport/report generation alone never refills credit. Six owners
=>384 live exact witnesses, not416 full bodies. Thirty-two COW witness copies
belong to GC reserve. Stalled reports then stop uncovered admission: report
fairness/critical admission and local-safety saturation semantics are OPEN.
No production credit rule was implemented or silently approved.

Proposed dedupe-only witness53 B = exact owner slot1 +enrollment4 +origin8
+sequence8 +full source HMAC32, within authenticated page/root. It may replace
body only after backend/replay/history owners finish and canonical immutable
retry projection is proven. Compared with frozen36-byte typical HOT entry,
55-byte framed witness is19 B larger; do not force certificate conversion when
the complete encoded body/context is smaller. Existing native digest includes
Hub received_at; journal outer duplicate is key-only while durable component
compares digests. End-to-end conflict/retry projection remains INVESTIGATE_ONLY,
not an implemented fix. No finite current historical exact-key or backend-body
bound is established.

Abstract COW state: prepare/verify destination or certificate ->select/readback
new root ->release ALL old recovery references ->erase victim ->verify blank
before reuse. Five transitions,865 cut points each (4,325 total) recover old or
new complete state. Selected corrupt child fails closed rather than using an
older root that may lose ACKed responsibility. CRC mock pages/roots, atomic
ledger snapshots and selected retirement flags are model assumptions; AEAD,
nonce reservation, real sector root rotation, interrupted recovery/resume,
rollback and simultaneous live allocator proof remain OPEN. Million-event
randomized six-owner run peak89, fixed384 ledger26,368 model RAM. Existing
million-event density, source-backend, journal recovery, Node retirement and
Hub snapshot regressions PASS; ASan/UBSan PASS, LeakSanitizer not claimed.

This subsection adds a **conditional raw-partition sensitivity**, replacing
section22's old witness reserve only if the53-byte projection/credit/allocator
assumptions close: certificates24,576; report banks12,288; routine/day/stateCOW
20,480; roots8,192; lifecycle metadata8,192; GC12,288; critical placeholder8,192;
engineering4,096 =fixed98,304. Shared bodies/outbox/history/daily32,768; total
131,072. No separate full-body or backend payload copy; zero separate body
reserve does not mean zero bodies required. Gap exceptions already in reports.
Worst192 maximal HOT124-byte events +1370 header require10 sectors40,960,
exceeding the8-sector pool before older outbox/day data. Thus arithmetic alone
is not guaranteed active-body admission.

Frozen jittered full-source sample/max-name eight-sector retention:
NORMAL1472/1197 events (92/74.8125h), HIGH1539/1261 (20.797297/17.040541h),
STRESS1667/1351 (1.722107/1.395661h). Synthetic72h NORMAL sample126,976 B,
4096 margin; max131,072 B,zero margin. **No production72-hour guarantee.**
NVS4096-byte segment blob instead needs at least13132-byte entries; seven/eight
whole blobs require optimistic9/10-sector windows with namespace/free page.
Holding raw fixed ledger constant only for sensitivity: sample135,168 B
(deficit4096), max139,264 (deficit8192). Shared scratch/fixed-object NVS mapping
needs proof; these are estimates, not complete target allocation measurements.
Existing dedicated8-sector NVS window fits at most6whole blobs in ideal packing.
Do not equate entry occupancy with physical write amplification or wear.

CURRENT_128K_FEASIBILITY=CONDITIONAL; PARTITION_CHANGE_PROVEN_NECESSARY=NO;
MINIMUM_REQUIRED_PARTITION=UNDETERMINED. Offline/critical/substitution policy,
report-bound admission/progress, full retry/conflict digest projection,
backend-derived completion, authenticated allocator/root/nonce/rollback,
materialized routine/day/config recovery and target physical peak/wear/RAM remain
STOP gates. No new locked requirement/context version, partition, production
integration or hardware operation. Next work is the bounded authenticated
allocator/progress proof plus requested product/backend decisions, not another
codec optimization or larger journal constant.

## 24. Admission progress and whole-partition NVS/raw proof

[Focused admission/physical evidence](../evidence/R1_STORAGE_ADMISSION_RAWFLASH_PROOF_20261007.md)
contains source maps, alternatives, conditional induction, pressure behavior,
per-object physical accounting, whole-partition ledgers, fresh SDK-generator
images and full-sector host failure models. Context remains.003; codec frozen.
No production/ACK/backend/partition/hardware change or new LOCKED decision.

### Conditional finite rule, not a product-policy choice

Persist a selected complete gap-aware report P_i (<=32 keys) and bound distinct
uncovered admissions U_i by W. New covered keys must be listed; covered absent
keys are Stale. New uncovered commit spends one credit; retries spend none.
Recompute remaining credits from surviving uncovered evidence on real selected
report progress, never report-generation increment, event ACK count, reboot,
rejoin/new transport or epoch reset. Reports/control have independent reserved
selection/COW workspace and cannot be blocked by normal event exhaustion.
Then E_i subset P_i union U_i; total exact live keys<=6*(32+W). Gap exceptions
are the listed32/Node, with zero additional retired-gap ledger. Current production
still lacks this admission rule; its historical exact evidence is unbounded.

Recommended conceptual minimum is fixed persisted Hub admission plus mandatory
complete report to replenish, optionally piggybacking report progress. W=32
permits one full retained32-key flight; W=1 would yield198 exact keys but tighter
report latency; W=2 is the minimum allowing separate one normal/one critical
new credit. No final W is approved. Origin/session ledger alone cannot bound
continued ACKed events in one origin; an ACK credit token is not needed for the
safety proof. Event/report scheduling, full six-owner enforcement, ownership/
epoch revocation and durable credit recovery remain integration obligations.

Reserve C within W, not unlimited extra critical admissions. Normal uncovered
charges<=W-C, total<=W. Critical body bytes and Node admission reservations must
also be protected. Existing Node four-slot reserve protects all nonmotion
traffic, not critical only. C=4 in the model is a test parameter; C=1/2/16/32
and W=1/8/32 are also exercised. Final critical classes/C/rate, offline/full-detail
horizon, saturation behavior and backend summary substitution remain
REQUIREMENT_GAP; stop that policy branch. A finite reserve cannot promise
unlimited unsynced critical history. Credits and body capacity are independent:
report retirement may free dedupe credit while a backend-pending body remains.

Do not force body->certificate: typical frozen HOT36/WARM15–16 are smaller than
55 framed exact certificates. Use the smallest lossless context-pinned form
until all replay/backend/history obligations finish, then exact key+full HMAC
or selected report complement. Class association must remain authenticated
when body removed (candidate48-byte384-row bitmap inside lifecycle metadata);
53-byte dedupe certificate alone is not a class-credit or backend payload.
No unsafe key-only conflict check, simple highest-sequence floor, or backend
send/timeout completion. Original source retry binding remains a technical gate.

### Corrected raw physical map and efficient whole NVS comparison

Section23 raw fixed98,304 assumed three6144-byte state images in20,480 B. For
**independent erase-sector banks**, charge3*8192=24,576, increasing fixed to
102,400 and leaving28,672 (seven sectors). Shared five-sector arena remains an
unproved allocator alternative; do not claim sector independence for it.

Raw bytes: exact certificates24,576; report banks12,288; state/current-day/
checkpoint banks24,576; roots8192; lifecycle metadata8192; GC/COW12,288; critical
placeholder8192; engineering4096 =fixed102,400. Shared active/backlog/history/
daily28,672; free0; total131,072. Six-row source contexts728/1370 within each
variable sector, framing/tag/padding included. No triple body copy or RAM index
counted as flash. Critical placeholder is not an approved derived rate guarantee.

NVS uses real6.0.3 constants: page4096, header+bitmap64,126 entries32, chunk
maximum4000. Blob minimumceil(B/32)+ceil(B/4000)+1 entries. **Remap every fixed
object**, rather than retaining raw fixed-sector padding and taxing only events:
six4079-byte witness blocks786 entries; three3485 reports333; three6144 state
images585; two512 roots36; two4096 lifecycle metadata262; two4096 critical
placeholders262; namespace1 =2265 entries. These include current-day/routine
and candidate class/completion state, not duplicate separate payloads.

Fixed minimum18 occupied pages +four reserve pages =90,112 B. Four reserve
pages comprise one NVS internal free page, two application GC/COW pages and one
engineering page. Nine logical4096 event segments add1179 entries; globally
ceil(3444/126)+4=32 sectors. Incremental variable physical allocation40,960,
logical event segments36,864; free0; total131072. Ten segments require33 sectors.
The official installed V2 generator measures3447 actual entries for the nine
segments, still28 occupied pages plus one free plus three application/engineering
pages=131072. Seven/eight-segment images also match total sector minima despite
three extra entries from actual fresh chunk splits.

**FRESH-IMAGE TESTED only:** no runtime NVS GC/fragmentation/torn HOT tails/
replacement coexistence or application scratch guarantee. Efficient NVS could
pack fixed objects better than this conservative raw map; raw is not selected
just for entry density. RECOMMENDED_STORAGE_BACKEND=UNDECIDED; next evaluate
actual IDF runtime on emulated flash with committed HOT tails, sealed promotion
and peak owner/COW/recovery churn. Never acknowledge an event waiting in an
uncommitted batch. Never rewrite whole4096 NVS blob per event without addressing
its>=4192-byte entry write amplification. Full raw engine remains much more
custom security/recovery/rollback work than the fixture.

### Retention and validation boundary

Frozen source traces384/1776/23232/day, full sample/max names,20ms timing variation
and302-byte daily entries:

| Scenario | Raw seven sectors: sample /max records;hours | Optimistic NVS nine segments: sample /max records;hours |
|---|---|---|
|NORMAL|1281 /1056;80.0625 /66|1649 /1353;103.0625 /84.5625|
|HIGH|1347 /1103;18.202703 /14.905405|1740 /1419;23.513514 /19.175676|
|STRESS|1457 /1181;1.505165 /1.220041|1877 /1520;1.939050 /1.570248|

72h1152 NORMAL sources+three daily entries: sample7 event sectors, max8.
NVS whole fresh physical totals122,880/126,976, margins8192/4096; RAW totals
131,072/135,168, margin0/deficit4096. **72h not a product guarantee**. NVS
nine-segment retention assumes sealed values; transient HOT coexistence can
reduce it.192 maximal HOT124 with1370 context still require10 event sectors,
not guaranteed by either conservative pool. Borrowing unoccupied witness banks
or earlier complete owner release requires an actual peak allocator proof.
Neither this adverse trace nor raw72h miss proves partition enlargement necessary.

New fixed admission model million-event run peak139, RAM37,384, plus six Nodes
at384 simultaneously; replay/out-of-order reports, gaps, origin/generation change,
critical reserve under normal-credit saturation, copied-snapshot reboot and
nonresetting credit all PASS. Raw numeric fixture uses actual4 KiB sectors and
host AES-GCM context/offset/root binding:17,018 exhaustive append/root/GC/erase
byte-cut cases,144 sampled interrupted-cleanup second crashes,64 GC lifetimes,
selected corruption/wrong serial fail-closed PASS. External nonce reservation,
root freshness fence, complete-source strings, arbitrary brownout erase pattern,
full32-sector multi-owner allocator and target implementation remain OPEN.
Root fixture erases one sector per append to prove ordering: **not** production
wear design. Production needs bounded journal/append-inventory amortization.

Existing lifecycle/density million regressions, backend completion and journal
recovery PASS; new admission/raw ASan+UBSan PASS (LeakSanitizer disabled). Logs and
commands in focused evidence. No new target measurements; prior app1,864,624,
OTA margin101,456 remain evidence, not new storage integration size/RAM/wear.

CURRENT_128K_FEASIBILITY=CONDITIONAL; PARTITION_CHANGE_PROVEN_NECESSARY=NO;
MINIMUM_REQUIRED_PARTITION=UNDETERMINED.4 MB storage viability conditional;
current image OTA fits. Hardware upgrade is not proven required. Production
integration remains NO pending product saturation/substitution/critical decisions,
persisted report/admission fairness and source binding, physical peak allocator,
authenticated root/nonce/freshness/FOTA and target RAM/code/wear. No context bump.

## 25. Installed-IDF NVS runtime/saturation checkpoint — 2026-10-08

[Focused host evidence and raw logs](../evidence/R1_STORAGE_NVS_RUNTIME_PROOF_20261008.md)
use the actual installed ESP-IDF6.0.3 NVS allocator on a Linux emulated128 KiB
partition. The length-matched dummy objects are the section24 whole-object
map; no production codec, ACK, partition, BAT-C8 or hardware change.

Nine sealed4096-byte segments plus fixed objects take28 nonblank NVS pages
fresh. After10,000 deliberately heavy tail/segment/report/state/meta/root
replacement cycles,31 pages are nonblank and one erased page remains at call
boundaries;69,755 page erases and297,789,032 bytes programmed are measured.
The three pages previously called two application COW plus one engineering
reserve become NVS churn space, so that reserve ledger is invalid at runtime.
The NVS free page is internal GC workspace, not report/root headroom. At12
live segments, retirement-report replacement fails; deleting an old segment
allows an append, but report-driven retirement cannot rely on that order.
At11 segments the report/root update succeeds in one measured state, not as a
proven admission threshold. An allocator guard must reserve a complete next
report/root/GC operation under worst allowed live/fragmented layout.

With192 old exact keys retained as certificates and192 maximum HOT bodies
attempted as separate blobs, only138 new bodies admit at nine segments. The
384 exact-key lemma does not imply all six Node pending flights can become
independent NVS HOT blobs while retaining the proposed history. Limit hot-tail
coexistence through bounded authenticated promotion and credit/physical
admission; never ACK on failed write. The32-HOT promotion fixture succeeds at
nine segments, but this is only one page-layout witness.

Sampled NVS report-blob failure cuts recover old or new at most points; cut1072
returns `ESP_ERR_NVS_NOT_FOUND` after successful remount, reproducibly. Do not
overwrite a selected report key in place. Authenticated old/selected/candidate
bank selection and root release ordering need explicit crash tests. The host
admission model still copies atomic state; durable class/credit bytes beyond a
48-byte candidate bitmap and report/root association are not fixed. A three-
bank report candidate costs10455 logical bytes and at least10656 NVS entry
bytes before page/GC overhead.

The heavy cycle programs29,767.64 bytes and erases6.9755 pages on average
after setup, against18,457 changed-value bytes/cycle (ratio1.613). It is not
an approved per-event schedule. Actual NORMAL/HIGH/STRESS write amplification,
flash lifetime/hot pages, NVS-specific engine RAM and firmware OTA growth are
still OPEN. Existing39,017-byte raw-sector candidate RAM is not a measured NVS
budget. Current image OTA margin101,456 bytes is prior evidence only.

`READY_TO_START_PRODUCTION_STORAGE_IMPLEMENTATION=NO`.
`CURRENT_128K_FEASIBILITY=CONDITIONAL` overall; section24's unrestricted
nine-segment reserve map fails. No partition change or hardware migration is
proven necessary. NVS stays preferred candidate; raw stays fallback. Next
technical proof needs persisted authenticated credit/report/root recovery,
physical admission with protected report/GC/COW space, final bounded tail/
checkpoint/report schedule and wear/RAM/rollback measurements. Product critical,
offline, overflow and backend substitution decisions remain separate STOP gates.
Context stays.003 and no LOCKED decision is added.

## 26. NVS blocker diagnosis and bounded next decision — 2026-10-08

[Focused diagnosis](../evidence/R1_STORAGE_NVS_BLOCKER_DIAGNOSIS_20261008.md)
corrects section25's cut1072 inference: the installed Linux emulator resumes
writes after one failure. New-index publication succeeds physically, cleanup
then removes a new chunk, and remount removes both incomplete/duplicate indexes.
Latching all writes/erases off until remount recovers generation127. Classification
is FAULT_INJECTION_MODEL_DEFECT, not a demonstrated SDK power-loss bug. The
independent report/new-selector/old-retirement prototype passes2702 supported
cut/recovery checks. Full authenticated credit/class/root persistence remains OPEN.

Report replacement needs at least4128 entry bytes of candidate report+root,
plus4096 internal GC and sector/fragmentation allowance; three free/reserved
physical pages (12288 B) are a lower reservation obligation, not a guaranteed
allocator threshold. Nine-segment192 maximum-HOT coexistence with independent
next report/checkpoint/roots needs a modeled155648 B (24576 deficit at128 KiB),
and first passes in the tested38-page fixture. Three history segments also pass
at128 KiB without discarding required report/state copies. Thus128 KiB R1 is
UNPROVEN, not categorically impossible; choosing fewer pending/history owners
requires the open offline/information contract.192/256 KiB review layouts pass
the generator/current image, but their limiting OTA margin is only35920 B.

Checkpoint-every32 sensitivity measures90/461/6089 erases for NORMAL/HIGH/STRESS,
with programmed/value ratios1.641702/1.728766/1.745295. These connected dummy
schedules are not outage/rejoin production wear evidence.49648 B application
RAM planning allowance plus NVS internals is not target RAM/headroom measurement.
NVS remains the recommended technical candidate, raw fallback; retain4 MB Hub.
No further broad backend exploration is warranted by these findings. Production
implementation is a separate task after product policy, authenticated persisted
admission/root, guarded peak allocation, target wear/RAM/OTA and rollback gates.
READY_TO_START_PRODUCTION_STORAGE_IMPLEMENTATION=NO. No context/partition,
production firmware, ACK, backend/PWA, BAT-C8 or hardware change.

## 27. 72-hour offline direction and loss-aware aggregation analysis — 2026-10-08

[Focused evidence](../evidence/R1_STORAGE_72H_AGGREGATION_CAPACITY_20261008.md)
refines the user-approved72h internet-offline target and ordinary-motion aggregation
under all existing safety/authentication/coverage invariants. This section is
IMPLEMENTATION_DESIGN/PROPOSED, not a partition/critical quota/backend guarantee.
Product-decision/context governance recording is deferred by the user-directed
checkpoint; bounds remain OPEN. No new LOCKED decision/context version has been
committed. Prior codec and production code are unchanged. Work is paused; see the
[checkpoint handoff](../evidence/R1_STORAGE_72H_CHECKPOINT_HANDOFF_20261008.md).

Candidate B uses immutable bounded containers of separate ordinary Motion points
with source membership, original monotonic/receive timing, coverage/context and
selected processed-state dependency. Keep Call Family/I Am OK, important door/
alert/fault/window dependencies exactly. **Keep native Node MotionSummary exact**;
its millisecond endpoints/count cannot become a seconds-only history summary.
Unknown/delayed/unclosed/inflight exact sources remain exact. A public history
summary is not fed to the existing MotionSummary rule enum. Four calendar dates,
coverage and day/clock revisions remain explicit. Full routine-learning/time/
finalization semantics are not newly invented or qualified.

Worst-size NORMAL mostly ordinary430 exact originals (candidate essential53,
native aggregates374 with overlapping anchor subset),288 new summaries needs
237568 B protected modeled peak. It passes256 KiB SDK update/reclaim/remount.
Mixed NORMAL728 exact/197 summaries needs282624 B and fails256 KiB. Typical NORMAL
passes192; all final128 fixtures fail. HIGH mostly ordinary worst536576 B and
STRESS5132288 B fail all reviewed sizes. Earlier narrower128/optimistic HIGH
observations remain scoped evidence, not a guarantee. Physical passing churn
uses all but one erased page; admission must reserve actual next operations,
not assume that page is application headroom.

Six384-key witness banks and all old report/state owners remain charged; serial32
HOT admission, two max source extents/32 arrivals, eight source-stage extents/128
checkpoint inputs, separate next report/checkpoint/selectors, four day states and
critical32/64/128 alternatives are included. Those credits/reserves are conditional,
not deployed policy.192 pending Nodes can be drained serially in the host model;
192 standalone Hub HOT is a different and larger allocator obligation. No source
body disappears before selected summary+checkpoint, and Node retirement cannot
stand for cloud completion. Exact first-send must be durably fenced against later
compaction; backend exclusive source claims and manifest receipts need a new API.

NORMAL full72h dummy schedule:1176 source+local inputs,970944 programmed B,
WA1.189578 versus all changed values (6.658328 versus124-byte input bodies),185
erases, max7/sector. HIGH/STRESS full-day/outage wear UNPROVEN after capacity stops.
Application RAM42749 B plus NVS internals is a bound proposal; target heap/image/
endurance/brownout/rollback remain UNPROVEN. Fourteen semantic tests, actual rules,
60 sampled GC-primed fault cases, relevant regressions and scoped ASan/UBSan pass.

256 KiB is a safer candidate than192 at the same35920 B limiting current-image
OTA margin; neither guarantees the declared max mixed workload. Retain4 MB ESP32
and NVS candidate/raw fallback. Final partition UNDECIDED. Stop additional backend/
compression exploration; resolve supported volume/critical/late/coverage/API/OTA
policy, authenticated persisted root/admission and target qualification before
freezing or phased production implementation. No partition/firmware/backend/PWA,
BAT-C8, hardware or canonical-branch change occurs in this run.

## 28. Node-local PIR consolidation investigation — 2026-10-08

[Focused source audit, proposal and host evidence](../evidence/R1_NODE_MOTION_CONSOLIDATION_20261008.md)
resume checkpoint `dc4eb0c61419cdf0e0e64074638fc1f43289cfa1` with preflight
PASS at context `2026-10-07.003`. This is INVESTIGATE_ONLY / PROPOSED; no canonical
decision promotion, production integration, partition, backend/PWA, BAT-C8,
Jira or hardware change. User-owned `prompt.txt` is preserved untracked.

Existing production ActivityEpisode already retains a durable first Motion,
coalesces repeats in RAM, and emits a separate durable MotionSummary after
connected quiet45s or max300s closure. Radio-outage idle1800s is different from
internet-only outage. Qualified input uses150ms debounce/1000ms retrigger and
fresh rising transitions; raw edges were never all permanent event records.
At40s repeated observations can merge;60–120s typically become separate Motion
events. Native summaries contain repeat first/last/count, can span separate
closed episodes while pending, and have no first-Motion episode linkage. They
cannot establish continuous presence or occupancy duration.

Actual Hub RulesCore ignores native MotionSummary. First/last/count cannot
preserve all morning-window interior points, night visit spacing, last-motion
anchors or motion after another Node's door close. Current Node recovery saves
immutable pending events/report state but not ActivityEpisode: uncommitted
repeat/last-motion information can disappear on reboot. Secure target has no
trusted absolute event clock/local-minute timer integration; source events
have occurred_at0/uncertainty86400s. Host trusted-time results are conditional.

Propose IDLE -> ACTIVE -> IDLE with durable linked START, bounded recoverable
observations, timely immutable PROGRESS and validated quiet END. ACTIVE never
means continuous presence. Keep required intermediate points and original
times/identity; timer health is not motion. Hub owns eligibility, household
routine learning, cross-sensor rules and history grouping. New protocol remains
unimplemented. Fixed quiet gap and progress delay are UNDETERMINED pending
sensor/meaning, applied rule deadlines, coverage/time and alert-latency contract.
Use exact current semantic inputs when safe eligibility/delay cannot be proved.
Future bed VACANT/OCCUPIED sessions need availability/uncertainty and interrupted
recovery; bed hardware/identity/sleep inference are outside R1 and this task.

Source-derived host replay realizes NORMAL/HIGH's original40/160 sessions per
Node/day with1152/5328 total Node source events in72h (native summaries360/2160,
other source events72/288). Four repeats in the repeated episodes are explicit
synthetic inputs, not measured household pulses. The literal STRESS paired45s
attempt schedule coalesces to10452 source events, whereas paired46s sensitivity
produces68196. This qualifies only section6's literal45s two-record-per-episode
attribution; the prior69696 abstract semantic stress fixture and its capacity
results remain valid for their declared inputs. Do not use10452 as a safe
commercial worst-case bound or claim a newly implemented reduction.

Working8h/day at40/80/120s for six Nodes produces3240/6480/4320 current semantic
records in72h. No universal reduction factor is derived. Proposed Node protocol
reduced counts remain UNDETERMINED; its exact fallback retains current counts.
Each current source event implies two logical recovery save operations under
prompt durable ACK, not two measured flash program/erase operations. New durable
repeat state/progress can add writes and energy compared with today's RAM repeats.

Unchanged72h ledger fed source-derived records: ordinary NORMAL retains462 exact
originals (360 native) plus442 point summaries, modeled protected peak249856 B;
mixed NORMAL278528 B, HIGH ordinary638976 B and literal STRESS ordinary1204224 B.
New SDK fixtures:15 cases,1 passing256 KiB NORMAL ordinary witness and14 expected
capacity stops.128/192 KiB fail these new worst-size cases;256 KiB still fails
mixed NORMAL/HIGH/STRESS. Passing physical peak258048 B leaves only internal GC
page. No general72h guarantee or partition decision follows. Prior narrower
typical results, OTA margins and fault evidence are preserved; no broad old
qualification or wear campaign was repeated. NVS remains candidate/raw fallback.

Host compile/behavioral counterexamples, seven deterministic replays, inherited
capacity ledgers and scoped ASan+UBSan PASS. Complete Node progress/root/cursor,
Hub coverage/time/reducer recovery, backend exclusive representation/revision
completion, protected NVS admission and target RAM/OTA/wear/BAT-C8 remain OPEN.
Planning only: Node workspaces1772 B before pending payloads/platform overhead;
Hub proposed episode/decode additions800 B beyond prior42749 B+NVS internals.
Neither is measured target RAM or a final allocation. BAT-C8 is unchanged;
later sensing/deadline/sleep integration requires relevant requalification.

Required next governance action is an explicitly authorized review/promotion on
the designated canonical source: record already approved72h internet-only and
eligible loss-aware ordinary-motion direction as LOCKED, partially supersede
only approved GS-D013/017 scope, keep remaining volume/critical/saturation/
coverage/time/backend/partition details OPEN, update canonical documents/index,
increment CONTEXT_VERSION and commit before dependent implementation. This run
does none of that. Node proposal needs separate semantic approval/proof. After
the coherent host-only investigation commit, STOP; production integration NO.

## 29. Approved product governance preparation — 2026-10-08

Documentation-only follow-up locks GS-D025–028: 72-hour internet-only outage
design target; loss-aware eligible ordinary-motion aggregation; battery-first
intelligent ESP32-C3 Nodes; safe PIR, identifiable door and future-bed boundaries.
GS-D013/017 are partially superseded for direction only. These decisions do not
approve an unconditional capacity guarantee, Node protocol or partition change.

Section28's START/PROGRESS/END model remains proposed. Quiet gap, progress
frequency, final summary/backend encoding, critical classes/reserve/saturation
and guaranteed workload bounds remain OPEN. Do not introduce 40–120-second
periodic Node wake-ups for consolidation. Preserve BAT-C8 requirements and
prove any new protocol's battery and correctness impact before implementation.
Hub retains household/cross-sensor learning; future bed sensing is excluded
from R1 and occupancy establishes neither sleep nor identity.

Progress: minimum canonical governance documents updated; context advances
from `2026-10-07.003` to `2026-10-08.001`. Earlier evidence and proposals remain
intact under the partial-supersession notes in the canonical index. No storage
simulations, host-model tests, hardware or release gates repeated; production,
partition and BAT-C8 changes NO.

STOP after this coherent documentation commit. Canonical remains `.003`, so
preflight STALE is expected until explicitly authorized review/apply/commit of
the eight governance files listed in R1_WORK_STATE on the canonical branch.
Review this implementation-design status section separately from canonical
governance promotion. Do not weaken preflight, auto-promote, begin the Node
semantic proof or integrate storage in this run.

## 30. Bounded battery-first delivery finding — 2026-10-08

[Focused delivery evidence](../evidence/R1_NODE_DELIVERY_PRIORITY_STORAGE_IMPACT_20261008.md)
recommends **RETAIN_CURRENT_DELIVERY** for Hub storage. Existing ESP-NOW single-event
frames, PIR coalescing, authenticated-contact health suppression and ACK-driven
pending drain already supply reusable mechanisms. No AP association per Motion;
light-sleep returns restore Wi-Fi/ESP-NOW even without an application frame.
Holding pending records presently inhibits sleep and suppresses health, so a
standalone defer-to-health optimization is not safe or a demonstrated battery win.

Batching original events leaves semantic identities, Hub durable admissions,
backend backlog and logical persistence work unchanged. Reuse source-derived72h
Node inputs1152/5328/10452 (literal45s STRESS, not a worst-case promise) and Hub
inputs1176/5352/10476 with24 local outcomes; adverse46s and earlier abstract stress
fixtures retain their stated limits. No changes to128/192/256 KiB capacity results,
retained-history summary counts, record sizes or write/wear estimates. No full
storage matrix or compression work rerun.

If future Node power work batches deferred releases, separately prove temporal
arrival/admission peaks:32 pending per Node,192 across six, callback16/ingest32,
per-event durable ACK and report/COW/GC interleaving. Unchanged A needs no new
burst experiment. Never reduce admission credits or claim fewer NVS writes from
shared RF sessions. Current quiet Node retries without new PIR; new holding must
also guarantee bounded expiry, urgent selection, sleep-safe persistence and health.

Ten focused unchanged-component host counterexample groups PASS: limited priority,
28+4 reserve, exact reboot/ACK drain, pending sleep/health inhibition, late morning
and inactivity, event-time night classification and reordered door/motion effects.
Deferred equivalence requires approved deadline/time/coverage/late-order contracts;
current secure target trusted time/timer and learned daily state remain unqualified.
Keep this in separate BAT-C8/Node work; no new Node protocol blocks Hub storage.

Canonical promotion3b72892 is complete; source/canonical context2026-10-08.001
preflight PASS. GS-D025–028 unchanged. No production/partition/BAT-C8/backend/PWA,
canonical governance, Jira or hardware changes; no push. Next bounded Hub work is
persisted authenticated admission/retirement credits/report/root and protected
next-operation COW/GC progress on the existing event stream, with policy closure
before production. STOP after the coherent supporting-investigation commit.

## 31. Bounded Hub implementation readiness — 2026-10-08

[Focused readiness evidence](../evidence/R1_HUB_STORAGE_IMPLEMENTATION_READINESS_20261008.md)
and its raw log retain NVS/the4 MiB Hub/current PIR and ESP-NOW delivery. The
starting reviewed3201886 checkpoint was explicitly pushed and verified; new
host proof changes are not pushed. Context2026-10-08.001 preflight PASS; canonical
governance and all production/partition/BAT-C8 files remain unchanged.

**Gates A/B/C FAIL for integration; conditional primitives PASS.** Finite tests
prove6*(32+W) exact identities only with complete selected reports, persisted
uncovered credits and at most six retained authenticated enrollment owners.
W32 gives384 identities, not bodies or physical admission rights. Current exact
ledger accepts33 uncovered keys for one owner without report progress; ten-owner
production enrollment capacity and old-enrollment revocation need bounded R1
enforcement. Lost reports stop new uncovered admission under the candidate gate;
retries retain identity and report generations/reboots do not refill credit.
No final W, reserve or critical saturation policy is approved.

Actual authenticated DurableStore counterexamples publish reducer generation2,
then corrupt/remove its checkpoint child: recovery silently selects generation1.
This is a root-freshness blocker for the new reclaiming/credit engine, not evidence
of observed physical ACK loss. The report adapter protects only the selected
bank; a torn candidate can overwrite an older recoverable root's child. Passing
the union of old/selected report references to the existing three-bank repository
preserves both in the focused test. Complete publication freshness, credit/class
serialization and all-authorized-root ownership remain unproved.

One new SDK NVS pressure/remount case preserves all30 existing dummy blobs but
fails three bounded next-report/root attempts with NOT_ENOUGH_SPACE. A free GC
page/entry total does not protect metadata progress. Prior supported-cut/GC
results are reused, with no full72h matrix or million-event rerun. Next work must
prove the native authenticated transaction and protected next-operation admission,
then integrate durable admission/recovery at the current Hub ACK boundary.

Current128 KiB does not fit the tested complete72h fixtures; no guaranteed volume
is approved. The narrower nine-segment/192-max-HOT peak remains152 KiB (24 KiB
gap). Latest source-derived conditional ordinary NORMAL is244 KiB (116 KiB gap),
mixed NORMAL272 KiB, HIGH624/728 KiB; no Node event reduction is assumed.256 KiB
passes only a scoped ordinary NORMAL witness, not mixed/HIGH/STRESS. Current OTA
margin101456 B and reviewed192/256 limiting margin35920 B are inherited image
facts; integrated code/RAM/wear/rollback remains unqualified. Raise a workload/
partition/hardware decision if the approved envelope cannot fit4 MiB; no automatic
partition or S3 choice. Urgent delivery, BAT-C8 physical wake/current, retransmission
energy and coverage freshness remain separate Node qualification.

Focused C++ and ASan+UBSan checks PASS, including explicitly expected blockers;
SDK preservation case PASS with progress BLOCKED. Production integration remains
NO. STOP after host-only validation/evidence commit; no new-proof push or canonical
promotion.

## 32. Host-native Gate A/B corrective transaction — 2026-10-08

[Corrective evidence](../evidence/R1_STORAGE_NATIVE_TRANSACTION_CORRECTION_20261008.md)
and [raw regressions/sanitizers](../evidence/R1_STORAGE_NATIVE_TRANSACTION_20261008.log)
record actual host implementation in `P/host/storage/native_transaction.{hpp,cpp}`.
The reviewed readiness3d63505 checkpoint was pushed and verified at origin;
new experimental changes are not pushed. Context2026-10-08.001 remains PASS;
canonical/production/partition/BAT-C8 files are unchanged.

**Gate A PASS in defined host scope:** six retained Active/Retiring owners,
globally nonreused generation, complete authenticated32-key reports and explicit
persisted W32 uncovered credit. Encoded authenticated bank recovery validates
charged counts against exact rows. Tested maximum384 exact identities; missing
reports stop new admission, duplicates spend nothing, generation/reboot/rejoin
never refill. Revocation keeps accepted rows/dependencies and consumes an owner
slot until a complete drained report plus no required rows permit release.
Seventh owner is Full. This is no product W/reserve/volume approval.

**Gate B host PASS with explicit trusted publication authority; target primitive
BLOCKED.** Inactive full bank is written/authenticated/read back before CAS
publication of a versioned exact-bank head. Recovery never scans/falls back to
an older bank; corrupt/missing latest data, false credit metadata or uncertain
authority fail closed without ACK. Eight event/report crash points, old-head
replay, report conflicts, exact reboot/rejoin retries and live dependency cases
PASS with ASan+UBSan. Original legacy regressions remain intact. BlobStore alone
does not supply durable non-rollback CAS authority; the fixed-size independent
host witness is an explicit test assumption, not an ESP32 implementation.

**Gate C OPEN.** No NVS matrix rerun or allocator progress claim. One candidate
bank write plus one authority publication per mutation, no internal retry/erase
loop. The conservative complete reference bank maximum201573 B is measured by
the maximal serialized fixture; head86 B. Two banks+head403232 logical B; a
three-blob COW plus old/new head allowance604891 B before provider/entry/page/GC
cost. This reference cannot be copied into current128 KiB production. Next map
its proven logical invariants onto existing compact NVS objects, bound/protect
the complete next-operation reservation and all recovery dependencies, and
separately provide the trusted publication primitive. Supported-volume/saturation,
target RAM/OTA/rollback and remaining product/Node qualification are still open.
STOP after host code/tests/evidence commit; production integration remains NO.

## 33. Compact real-SDK transaction feasibility — 2026-10-08

[Focused executable evidence](../evidence/R1_STORAGE_COMPACT_NVS_FEASIBILITY_20261008.md)
and [raw tests](../evidence/R1_STORAGE_COMPACT_NVS_FEASIBILITY_20261008.log)
reuse native admission/report/credit validation with immutable encrypted bodies,
independent reducer objects and smaller authenticated manifests. Reviewed2b3c673
was pushed/fetched/verified; the new experiment is not pushed. Context.001 PASS;
canonical, production, partitions and BAT-C8 unchanged.

**Outcome BLOCKED_PUBLICATION_AUTHORITY; production integration NO.** Real NVS
single-key publication is not atomic multi-key CAS or independent monotonic
authority. Restoring an intact old flash image after successful admission recovers
stale authenticated state. Detected selected dependency/head damage fails closed;
do not generalize those cases to valid older-state replay. An explicit trusted
publication primitive or product/security threat-model decision is required;
larger flash/MCU alone cannot solve it. Native Gate A/B remain PASS only in their
declared owner/report/independent-authority host scope.

**Gate C protected progress FAIL.** Near-full NVS preserves an accepted body,
credit/root and reducer through three no-ACK admission failures, but required
checkpoint replacement still fails NOT_ENOUGH_SPACE. No protected application
reserve/guard is qualified. Scoped event/report/GC/reclamation cuts pass old/new
recovery and exact retries; child execution stops immediately on injected cut.
Host compact384 maximum manifest16649 B, retained payload241379 B; conservative
max logical COW coexistence266926 B excludes NVS overhead/anchor. Real SDK384-body
fixtures stop at369(128 KiB/36 B),151(128/448),242(192/448),332(256/448), safely
preserving accepted rows. These exclude full production allocations and are not
72h guarantees or admission thresholds. No broad capacity matrix was repeated.

Existing qualified image1864624 B remains prior evidence; available canonical
artifact now measures1865616 B without requalified build provenance. Arithmetic
OTA margin100464 B current /34928 B limiting reviewed192/256 layouts; integrated
growth/RAM unknown. Supported-volume/saturation/backend/time/coverage and Node
qualification stay open. Stop after the host/SDK/evidence commit. Next obtain the
freshness/anchor and operational flash/OTA envelope decisions before further
allocator optimization or any production admission/recovery integration.

## 34. Protected compact NVS admission boundary — 2026-10-08

[Executable Gate C evidence](../evidence/R1_STORAGE_PROTECTED_NVS_GATE_C_20261008.md)
and [raw validation](../evidence/R1_STORAGE_PROTECTED_NVS_GATE_C_20261008.log).
Start7c424f6, context.002 PASS; GS-D029 now excludes adversarial intact-image
restoration from R1 freshness guarantees while preserving ordinary crash/
corruption recovery and mandatory application FOTA rollback. The stronger native
independent-authority regressions remain unchanged; no new governance or format.

**GATE_C_PASS_SDK only for certified workspace or bounded safe rejection;
production integration NO.** Compact preparation authenticates reused objects
and presents a complete write plan before any write. The SDK adapter certifies
erased physical pages (subtracting one possible lazy active page), bounds blob
page activations, and protects a maximum next control publication plus NVS's free
page and a reducer-object slot. Event/report duplicate ACK eligibility now
revalidates the selected durable closure without writing. Three rejected attempts
are effect-free; controls/recovery preserve accepted bodies and credits.
48 focused SDK cases and33 interruption/no-cut fixtures PASS; scoped host native/
compact regressions and ASan/UBSan PASS. Actual GC interruption resumes into exact
selected recovery followed by duplicate or space rejection, not optimistic ACK.

128 KiB fixtures reject at34(max body/fixed reducer),42(small body),9(changing
reducer) events, then publish retirement/checkpoint controls. Protected workspace
is9 pages/36864 B at these boundaries; max384-row conservative control reserve
is12 pages/49152 B. Reviewed192/256 fixtures reject at57/76 max-body records.
These are deliberately conservative transaction fixtures, NOT product thresholds
or72-hour qualification. Guarded publication avoids GC; automatic replenishment
of erased workspace remains unqualified and could leave a healthy online Hub
safely rejected despite logically reclaimed entries. Do not infer sustained
allocator progress, critical-event fit, target RAM/OTA sufficiency or readiness.

No full capacity matrix, production/partition/Node/BAT-C8/backend/canonical/context
change or experimental push. Existing4 MiB/128 KiB workload and OTA limitations
remain. Next decide supported workload and feasible flash/OTA engineering envelope
before production integration; any relaxed/replenished workspace boundary needs
its own focused SDK proof. No automatic new investigation or MCU selection.

## 35. Flash/OTA capacity decision — 2026-10-08

[Focused decision and SDK evidence](../evidence/R1_FLASH_OTA_CAPACITY_DECISION_20261008.md):
**EVALUATE_8MB_FOR_R1**, classic ESP32 with proposed2 MiB journal and two2.5 MiB
OTA slots. Not product approval, a partition change or production readiness.
Available Hub artifact1865616 B leaves755824 B per proposed slot; current4 MiB
margin100464 B. A4 MiB/512 KiB journal layout cannot fit that image. Five temporary
layouts validate SDK alignment/flash limits. Frozen512 KiB NORMAL mixed,
1 MiB HIGH door/user and2 MiB literal STRESS mixed capacity fixtures pass load,
32 updates and remount; conditional histories/critical placeholders remain unapproved.
384 unretired identities are not1176/5352/10476+ offline records; the candidate's
384 pinned-body cap still needs durable history/outbox separation.

New authenticated SDK counterexample:26 fully retired/consumer-complete bodies,
one backend-pinned body remaining,5320 logical bytes; admission rejects because
only14 erased pages certify against15 required. Logical collection does not
replenish the guard's workspace. Three rejects/remount preserve current root/body
without writes; lost-ACK effects remain deduplicated. Gate C safe rejection proof
stands; **sustained progress remains unimplemented**. Next bounded SDK correction
is reserve restoration with dependency protection and interruption proof, alongside
explicit workload/critical/saturation and flash/growth approval. No raw-flash erase,
Node redesign, new timestamp compression, purchase, production integration or push.
Target RAM, integrated/signed image, real flash endurance and storage-compatible
failed-update rollback remain qualification gates. GS-D025–029/context.002 unchanged.

## 36. Bounded 256 KiB / NORMAL48h workspace qualification — 2026-10-09

[Focused SDK counterexample](../evidence/R1_256K_48H_WORKSPACE_QUALIFICATION_20261009.md):
**FAIL_CAPACITY for the frozen retained map plus existing certificate**, not a
universal lower bound for future formats. Removing four unselected temporary
metadata objects preserves85 pinned objects but leaves6569 live entries and
only7 certified pages against at least15 needed for an ordinary publication.
Even ideal packing requires69 pages/282624 B,20480 B above256 KiB. Public SDK
purge zeros deleted data, restores no erased pages, and is not a lifecycle fix.
Five negative workspace/interruption cases, five authenticated subset checks,
host Gate A/B/compact and scoped ASan/UBSan pass preservation/refusal; no repeated
post-load admission succeeds. Authenticated48h history transfer and sustained
reclamation remain unimplemented. Stop; resolve additional journal/OTA envelope
before integration rather than weaken the guard. No production/partition/Node/
BAT-C8/governance/context change, hardware test, HIGH/72h comparison or push.
