# Compact real-SDK NVS feasibility — 2026-10-08

**ENGINEERING_OUTCOME=BLOCKED_PUBLICATION_AUTHORITY.** The executable compact
representation reuses the proven host transaction. It is not a conforming target
publication authority or production-ready allocator. An intact older flash image
recovers stale authenticated state after a later admission; checkpoint progress
also fails at near-full NVS. Stop before production integration. Increasing flash
does not solve publication authority.

Start `2b3c6730f8c490ba88a13ba2c23d6674c4c30fa8`, context2026-10-08.001,
storage branch/worktree, context preflight PASS. Origin exactly
`https://github.com/udaybhan200683/Ghar_sajag.git`; fetch showed ahead1/behind0.
Reviewed2b3c673 was dry-run/pushed/fetched and verified equal remotely. This new
experimental work is not pushed. Canonical and governance remain untouched;
`prompt.txt` was not read, modified, staged or removed.

Read AGENTS, mandatory canonical orientation/release/work-state/index, LOCKED
decisions including GS-D025–028, storage contract, active ExecPlan sections31/32,
readiness/correction evidence, native implementation/tests and installed SDK.

```text
BUG_CLASSIFICATION=R1_BLOCKER
REQUIREMENT_SOURCE=docs/product/R1_RELEASE_CONTRACT.md; docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md
DECISION_IDS=GS-D005/016/021/022/023/024/025/026/027/028
TASK_SCOPE=compact host/SDK mapping and executable publication/capacity NO-GO gate
OUT_OF_SCOPE=production Hub/Node, partition/BAT-C8/backend/PWA, governance/context/canonical, Jira, hardware, experimental push
```

## Implemented compact representation

`P=code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2`.
`P/host/storage/compact_nvs_representation.{hpp,cpp}` implements an optional
representation hook in the existing `native_transaction.{hpp,cpp}`. The original
full-bank path and regressions are preserved. The core validates the full logical
state before serialization and after reconstruction. A representation/provider
failure returns Fault, rather than misclassifying failed persistence as invalid
input. No production module was changed.

- Each immutable event object contains slot, enrollment generation, origin/sequence,
  exact digest, length and body. Mutable retry/local/backend flags live in the manifest.
  Body is encrypted once; reports, credit changes and checkpoint publication reuse it.
- CNP1 manifest carries the native version/epoch/W/bank/generation/owner prefix,
  complete authenticated reports and persisted credit,33 bytes per row (flags plus
  full32-byte object reference), and one32-byte reducer reference. The existing
  bank AEAD and86-byte HMAC publication marker bind this entire dependency closure.
- Reducer bytes are separately encrypted and referenced, independently recoverable
  without an event tail. Missing required reducer/body/manifest fails closed.
- Immutable object ID is domain/epoch-separated HMAC of plaintext. NVS names use
  kind plus14 hex characters to respect15-character keys. Full256-bit references
  and AEAD are checked; a truncated-name collision rejects, never aliases evidence.
  Fresh random nonces retain the existing entropy contract; no generation nonce reuse.
- At most385 event objects and3 reducer objects can exist. Enumeration is bounded;
  excess or orphan pressure stops publication. Each normal admission writes at most
  one new body, one new reducer, one manifest and one marker. Report/credit changes
  reuse body/reducer objects and write manifest/marker. There is no application retry
  loop. No object is deleted to manufacture admission credit.

Collection is a trusted serialized-owner operation after successful selected-root
recovery/publication. It authenticates all required objects before deleting any
unreferenced object, with at most388 object iterations. Exactly the head-selected
root is authorized: older candidate banks have no fallback authority. Before new
publication old selected dependencies remain; after verified publication only the
new complete closure permits collection. Do not call collection with guessed
state, failed authority recovery or concurrent writers. SDK collection cuts retain
selected reducer/body/credit and duplicate safety. If multiple roots are authorized
by a future format, their union must be protected; this code does not authorize them.

This is a compact **persistence** experiment. Host core still materializes/copies
bounded native State and scans up to384 rows; target RAM, CPU and integrated image
are unqualified. No assertion that the host RAM implementation fits ESP32 is made.
No summary/backend protocol, Node batching, observation semantics or product bound
was introduced. Runtime observation availability remains false until re-established.

## Real SDK semantics and three failure models

Installed ESP-IDF6.0.3 commit `76f5dedd9950a3012fee8fb7d5586df21fc67802` is the
primary source, under `/home/udaybhan/.espressif/v6.0.3/esp-idf`:

| Source | Finding |
|---|---|
| `components/nvs_flash/src/nvs_handle_simple.cpp:109–114` | `commit()` checks handle and returns OK; writes occur during set operations in this implementation. No multi-key transaction boundary. Still invoke public commit API. |
| `nvs_storage.cpp:273–390,480–520` | Blob replacement alternates chunk version offsets, writes chunks then index, and subsequently retires older entries. Failed writes have cleanup paths. Application must publish separate dependencies before marker. |
| `nvs_page.cpp:151ff` | Entry/page CRC/state bitmap transitions provide SDK recovery machinery, not application AEAD, ownership or freshness. |
| `nvs_pagemanager.cpp:139–207` and load/recovery path | GC marks source FREEING, activates destination, copies live items and erases source; recovery resumes transitional pages. One free GC page is not protected application checkpoint space. |
| `components/esp_partition/partition_linux.c:683ff,729ff` | Emulator supports partial programming and sector erase cuts. Linux sector erasure is a model, not analog hardware power-loss qualification. |

**A — ordinary interrupted write/power failure:** one serialized writer can write
immutable dependencies, authenticate readback, replace one marker, then verify it.
No atomic multi-key compare-and-swap is assumed. In the focused SDK samples reboot
recovers exact old or new complete state. A completed admission always recovers new;
an interrupted one may recover old/new. Before publication there is no ACK. New
published state after lost notification yields duplicate retry without another effect.
These samples/source reasoning are not exhaustive target power-interruption proof.

**B — corruption/missing metadata:** damaged/missing selected manifest, missing
selected reducer or missing marker fail closed even with an older complete bank
present. This is a tested detectable-corruption subset. Arbitrary corruption that
leaves an intact older authenticated flash state is not distinguishable from that
state's legitimate earlier history without independent freshness authority.
Do not generalize the subset to all possible corruption/rollback outcomes.

**C — malicious intact-image rollback:** real SDK test saves old partition bytes,
commits an event/new reducer, restores the older whole partition and remounts.
Recovery accepts old generation, old reducer and zero events. Authentication is
valid, but the later accepted obligation is missing. AES-GCM/HMAC and a larger
sequence value inside the same rolled-back image cannot detect this. NVS provides
no independent trusted current-head/monotonic anchor here.

`OrdinaryFlashAuthority` in `main/compact_probe.hpp` is explicitly a **nonconforming
negative candidate** for native PublicationAuthority's stronger contract. Its
serialized read/replace/read proves neither CAS against concurrent writers nor
nonrollback authority. The positive host384 fixture uses an independent test
witness; the native freshness regression keeps that assumption explicit.

**Minimum missing primitive:** authenticated, crash-consistent current-publication
authority outside the rollbackable storage domain (including safe ordering of its
advance with durable dependencies). It must detect loss and valid older replay.
Existing onboard flash alone cannot distinguish two identical restored byte images
offline. Extra flash capacity or an MCU upgrade alone does not supply the primitive.
If this threat model is not an R1 requirement, its scope needs an explicit product/
security decision; this run neither silently relaxes it nor edits governance.

## Gates and focused executable results

[Raw log](R1_STORAGE_COMPACT_NVS_FEASIBILITY_20261008.log) includes source/executable
hashes, commands, SDK outputs, original regressions and sanitizer scope.

| Check | Result / limitation |
|---|---|
| Original native Gate A/B regressions | PASS unchanged, six Active/Retiring owners, W32 conditional384 identity bound, lost reports/ACK, authenticated reports, credits, dependency pins and freshness under independent host authority. |
| Original unsafe production/readiness cases | Preserved; still reproduce33 uncovered admits, stale reducer fallback and selected-only report ownership. No production fix claimed. |
| Compact384 host fixture | PASS: full native validation,384 maximal bodies, complete32-key reports, credit32 per owner,16649-byte selected manifest; dependency tamper fails closed. |
| SDK basic / corruption / rollback / pressure | Seven cases PASS as assertions, including explicitly expected rollback and capacity NO-GO witnesses. Lost ACK does not write/spend credit; sixth/seventh owner and revocation behavior match core. |
| SDK event/report power cuts |133 scoped cases across event, retirement and GC-primed operations, including no-cut controls. Old/new complete state and retry/report idempotence PASS. |
| Exact GC boundaries | Four added cuts1/2/1086/1087 PASS. Cuts2/1087 halt inside erase,1/1086 during page-state programming. No-cut GC candidate performs two actual SDK erases. |
| Reclamation cuts | Seven added cases (0/1/2/3/4/8/no-cut) PASS; selected dependencies survive and event retry remains Duplicate. |
| Sanitizers | ASan+UBSan PASS for fully instrumented host compact/core/dependencies and SDK probe/header, plus a new collection cut. SDK archives/linked host-core objects in SDK sanitizer binary remain uninstrumented; LeakSanitizer disabled. No SDK wear-counter qualification inferred from sanitizer outputs. |

Cuts use fork plus SDK shared flash. On first injected write/erase error the child
exits77 **immediately**; no SDK cleanup, application read/write, commit, collection
or notification continues after the cut. Parent deinitialized NVS before fork,
then initializes fresh RAM from persisted bytes. This avoids the previously found
one-shot-failure model defect. Only each emitted child scratch image is removed.
No million-event run, full72h matrix, production build, hardware or release gate.
ACK assertions refer to Committed/Duplicate eligibility at the durable transaction
boundary; the SDK/host tests emit no physical Node or backend ACK.

## Gate C — preserved rejection, protected progress still FAIL

The new near-full SDK case retains an accepted448-byte event and4096-byte reducer,
then fills ordinary diagnostic blobs. Three bounded admissions return Fault /
`ESP_ERR_NVS_NOT_ENOUGH_SPACE`, without ACK, credit reset or loss of selected data.
One orphan candidate body persists but remains unselected and bounded. A retirement
report/credit update happens to fit; the required reducer/checkpoint replacement
still fails NOT_ENOUGH_SPACE. Selected report/credit, event, reducer and root survive.
Final31 allocated pages /1 erased page,3865 live entries,167 stats-free entries
are **not** a checkpoint reservation. Passing report publication alone is insufficient.

**PROTECTED_RESERVE_BYTES=UNPROVEN / no enforced application reserve.** The prototype
has bounded rejection and recovery, but ordinary data can leave insufficient space
for the required checkpoint. It therefore does not pass Gate C or justify GO.
Do not infer a guard from `nvs_get_stats` or repeat retries hoping to create space.

Physical inspection after each successful primitive in the scoped GC-primed
candidate measures32 simultaneously nonblank pages /131072 B (including diagnostic
padding and temporary GC duplication), versus31 after recovery. This observed peak
is not a qualified whole-system operational footprint or usable-payload budget.

Exact next-operation logical new objects at the tested maximum representation:
report/credit publication16735 B (manifest16649 + marker86); reducer/checkpoint
20859 B (plus reducer4124); admission21390 B (plus event531). These exclude old
retained dependencies, NVS chunk/index/entry rounding, page fragmentation and GC.
Ideal-alignment NVS entry costs are at least17024 /21248 /21856 B respectively,
plus a4096-byte GC page; fragmentation and COW may require more. These are
reservation obligations, **not protected/qualified reserve sizes**. Gate C needs
an actual admission guard and interruption/recovery proof for the chosen layout.

## Executable capacity and OTA constraints

Reference maximum full bank201573 B, two banks+head403232 B, conservative old/
candidate COW604891 logical B before NVS/authority overhead remain prior proof.

Compact maximum event531 B, reducer4124 B, manifest16649 B, marker86 B.
Two maximum manifests plus384 bodies/reducer/head: **241412 logical B**.
The host384 fixture measures241379 B because the old manifest has one fewer
33-byte reference. With385 bodies,3 reducers,3 manifest versions for NVS COW and
old/new markers: **266926 logical B** before NVS entry/page overhead or an anchor.
This conservative coexistence envelope exceeds256 KiB by4782 logical B already.
It is not an approved workload/reserve requirement or a claim that every operation
must simultaneously reach all maxima.

Four real-SDK coexistence fixtures only; bodies remain locally/backend owned:

| NVS | Body bytes | Accepted before space rejection /384 | Retained payload at stop |
|---|---:|---:|---:|
|128 KiB|36|369|80515 B|
|128 KiB|448|151|102809 B|
|192 KiB|448|242|157136 B|
|256 KiB|448|332|210866 B|

All remounts retain exactly accepted rows/credits. The discrepancy between logical
payload and partition occupancy is real metadata/COW/chunk/GC cost. Counts are
fixture observations, **not safe admission limits**, final event encodings or
72-hour promises. Even the narrow36-byte128 KiB fixture stops before384; this does
not prove every smaller approved workload impossible. The conditional384 identity
bound never promised384 simultaneously required maximal bodies fit in flash.
These transaction fixtures also exclude the complete production certificate/config,
daily/summary/history and backend-protocol allocation. They cannot replace the
earlier whole-system budgets or establish production usable payload space.

Actual CSV remains128 KiB at0x3E0000, dual0x1E0000-byte slots, end4 MiB.
The prior qualified build1864624 B / margin101456 B is preserved. Read-only size
check of the currently available canonical build artifact finds **1865616 B**,
SHA256 `8a3a91baf00a2fb4480b5afae31e9cbc40bc253800d751abdb815d5046e787fe`.
Its source/build provenance was not requalified; do not relabel it as a new build
of this candidate. It implies100464 B current-slot arithmetic margin. Reviewed
192/256 KiB aligned dual-OTA layouts both have limiting0x1D0000-byte slots:
34928 B against that artifact, versus35920 B against the prior qualified image.
No CSV or canonical artifact changed. Integrated growth/engineering margin unknown.

72h target remains unqualified: supported volume/saturation, critical classes and
reserve, summary/backend/time/coverage policy remain open. Existing complete128 KiB
72h fixture failures and192/256 limitations remain prior evidence, not rerun or
replaced by these four transaction fixtures. No Node event reduction is assumed.
If the approved operational envelope plus reserve/OTA does not fit4 MiB, decide
flash capacity separately from MCU choice; no ESP32-S3 selection is implied.

## Bounded handoff and stop

Primary blocker is publication authority under the preserved nonrollback contract.
Secondary blockers are protected physical next-operation capacity, approved volume/
critical saturation/backend/time/coverage contracts and target RAM/image/hardware
qualification. Gate A/B host proofs stay conditional; Gate C FAIL for protected
progress. **PRODUCTION_IMPLEMENTATION_READY=NO.**

Next action is an explicit freshness/threat-model and trusted-anchor decision,
using the executable rollback witness, together with an approved operational
information envelope/flash-and-OTA budget. Do not implement another speculative
storage layer or optimize theoretical byte counts again before that decision.
First production module, only after those gates close: NVS provider publication/
space error boundary and `durable_transition` recovery/admission, keeping existing
authenticated owner and external Node ACK paths intact. No module is authorized
for production modification now. BAT-C8 physical sleep/wake, urgent delivery,
ESP-NOW retry energy and coverage freshness remain separate qualification work.

STOP after focused code/tests/evidence/ExecPlan commit. No new experimental push,
canonical promotion, production firmware, partition, backend, BAT-C8 or hardware.
