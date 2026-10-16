# Gate C protected compact NVS publication — 2026-10-08

Outcome: **GATE_C_PASS_SDK**, restricted to the workspace certificate and bounded
safe-rejection contract below. **Production integration ready: NO.** This closes
the scoped next-operation preservation/rejection proof, not sustained allocator
replenishment, usable-volume qualification or the72-hour design target.

Start `7c424f6f817133b775b9aa4b9b85f1df51a9482b`, storage branch
`feature/r1-hub-storage-lifecycle`, context `2026-10-08.002`, preflight PASS.
Canonical remains clean at `f27d6ab0944bf3c1871d6185a7cd4ebef357a149`.
Verified origin is `https://github.com/udaybhan200683/Ghar_sajag.git`; fetch confirms
storage remote `2b3c6730f8c490ba88a13ba2c23d6674c4c30fa8`, two existing local
commits ahead, zero behind. This experiment is not pushed. `prompt.txt` was never
read, modified or staged. No production/partition/BAT-C8/backend/PWA/canonical/
context change, hardware use or broad storage simulation.

```text
BUG_CLASSIFICATION=R1_BLOCKER
REQUIREMENT_SOURCE=docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md
DECISION_IDS=GS-D025,GS-D026,GS-D027,GS-D028,GS-D029
TASK_SCOPE=host/SDK protected next-operation admission and recovery
OUT_OF_SCOPE=production integration, partition changes, Node work, volume guarantees
```

GS-D029 removes adversarial restoration of a valid older flash image from R1
data-freshness guarantees. The previous intact-image witness and stronger host
independent-authority regression remain valid; AES-GCM is not antirollback.
Ordinary crash consistency, corruption detection, no silently stale routine
state and automatic signed/validated APPLICATION FOTA rollback remain mandatory.
No stored-format bytes or version changed: GNT1/CNP1/GNP1 and object AEAD domains
are unchanged. Failed-upgrade format compatibility still needs integration tests.

## Executable correction

`host/storage/protected_nvs_space.hpp` defines a bounded publication plan,
workspace arithmetic and typed outcomes. The native transaction tells the
representation whether this is a new ordinary admission; duplicate EventKeys
return before this boundary and perform zero writes even at storage saturation.
Existing authenticated owner/report/credit validation remains the source of
admission authority, not a caller's priority or radio receipt.

A focused executable counterexample additionally found cached EventKey retries
returning Duplicate after the accepted body was deleted through NVS. The original
assertion failed (exit-6), preserved in the raw log. Event AND retirement-report
duplicate paths now revalidate the exact authenticated selected root/closure
before ACK eligibility. They still write nothing; missing evidence returns Fault,
invalidates current state and forbids older-bank fallback. The final SDK suite
includes both `dupmissing` and `reportmissing`. This adds bounded Hub read/crypto
work, not Node wake-ups; target latency/RAM remain unqualified.

`CompactRepresentation::pack` now parses the entire candidate and authenticates
every reused body/reducer before writing. Its complete write set comprises only
missing immutable objects, encrypted candidate manifest and86-byte publication
head. It also counts remaining bounded object slots. The real NVS adapter must
approve this plan before the first write. After an encode/preparation failure,
`Transaction::publish` revalidates the selected state; a damaged required object
cannot leave a supposedly valid current RAM state exposed.

SDK `Store::prepare_publication` certifies **wholly erased physical pages**, read
with `esp_partition_read_raw` after successful mount/recovery. It never uses
`nvs_get_stats()` free entries as a progress proof. One all-FF page is conservatively
subtracted because NVS may have activated a lazily initialized page without yet
writing its header. Corrupt pages, logical holes and erased entries in occupied
pages contribute nothing to the certificate.

For a blob of L bytes, bound page activations by `ceil(L/4000)+1`. Add these
bounds for the complete planned operation. For ordinary admission, also reserve
one maximum subsequent CONTROL operation: a4124-byte sealed reducer, worst
six-owner manifest at the candidate row count, and86-byte head. Add one further
free page for NVS itself. The manifest bound is `3977+33*rows`, maximum16649 B.
Controls include report/credit publication, owner phase changes, dependency
completion and checkpoint replacement; none introduces a new event row.

The guard additionally leaves one reducer-object slot for that control update.
At most385 event objects and3 reducer objects remain the original compact limits.
Failed publication orphans can exhaust the last reducer slot even while clean
pages remain: ordinary admission then rejects without a write. Tested authorized
collection authenticates the entire selected closure, removes only unselected
objects, and permits retry. The page/slot checks protect transaction workspace,
**not an approved critical-event storage reserve or saturation policy**.

Every guarded write must match the next planned blob length. There is one bounded
attempt; successful admission requires exact dependency/bank verification and
authenticated head-selected recovery. Space refusal precedes all writes/ACKs.
There is no retry/GC loop, automatic factory initialization, epoch reset or erase
of accepted evidence. Failed I/O may leave only bounded unselected candidates;
recovery/authorized collection determines what may be removed.

## Source-derived sufficient bound and limits

Primary source is installed ESP-IDF6.0.3, commit
`76f5dedd9950a3012fee8fb7d5586df21fc67802`:

- `components/nvs_flash/src/nvs_storage.cpp:273` splits blobs into at most4000-byte
  chunks, may skip an initial short tail, then publishes the index before removing
  the prior version. One extra page covers tail fragmentation/index placement.
- `nvs_pagemanager.cpp:135` activates directly with at least two free pages;
  only the last-free-page path performs GC. A certified complete operation leaves
  at least one free page, so it cannot need that GC path while executing.
- `nvs_pagemanager.cpp:17` completes interrupted FREEING recovery before mounting;
  `:206` activates pages. `nvs_page.cpp:1153` sets sequence in RAM without writing
  the UNINITIALIZED page, explaining the conservative one-page subtraction.
- `nvs_handle_simple.cpp:109` commit is not a multi-key transaction. The authenticated
  single-key head selects one complete bank/closure; no NVS atomic CAS is assumed.

Conditions: pinned SDK semantics; valid mounted128/192/256 KiB partition; healthy
flash for the enough-space completion argument; one serialized writer across ALL
namespaces for the entire operation; no concurrent consumer/reclamation. Changes
to SDK, page geometry, format, maximum sizes or writer ownership invalidate this
certificate. Hardware/encrypted-target behavior still needs qualification.

At the tested boundary, protected control+internal workspace is9 pages =36864 B;
an unchanged-reducer admission needs15 certified free pages total, versus18 when
writing a new4 KiB reducer. At384 rows, the conservative control+internal reserve
is12 pages =49152 B and a maximal event/reducer/manifest/head operation requires
25 certified free pages in total. The extra possible lazy page is excluded from
all these certified counts. These are sufficient physical page budgets, not
logical payload estimates or a promise that384 max bodies fit128 KiB.

**Practical limitation:** the guard does not replenish erased pages. Logical
dependency deletion alone does not restore its certificate. A healthy online
Hub could eventually remain safely rejected despite small live state. Autonomous
sustained GC/reclamation progress is NOT established; the allowed exit contract
here is bounded completion OR explicit safe rejection. Do not deploy this as a
qualified lifetime allocator or infer an unconditional Gate C progress guarantee.
Relaxing this conservative boundary requires a focused reserve-restoration proof
using SDK NVS, not optimistic byte counts or a custom raw-flash engine.

## Physical measurements

Each guarded fill starts with one owner and a4 KiB reducer; retained backend
bodies remain pinned. Reports every16 admissions free retry credits, not bodies.
Fixed reducer cases are representation fixtures; they do not imply real routine
state remains unchanged. `guardbusy` changes the entire reducer each admission.
These are six focused boundary fixtures, **not the72-hour workload matrix**.

|Fixture|Accepted events|Retained logical payload at rejection|Peak nonblank pages/bytes|Peak live entries|Control result|
|---|---:|---:|---:|---:|---|
|128 KiB,448 B body, fixed reducer|34|24955|19 /77824|1055|report + checkpoint committed|
|128 KiB,36 B body, fixed reducer|42|12427|19 /77824|681|report + checkpoint committed|
|128 KiB,448 B body, changing reducer|9|9970|16 /65536|499|report + checkpoint committed|
|128 KiB, already fragmented legacy storage|1 previously accepted|5194 compact objects; padding excluded|31 /126976|2010|zero-write safe rejection|
|192 KiB,448 B body, fixed reducer|57|38686|35 /143360|1568|report + checkpoint committed|
|256 KiB,448 B body, fixed reducer|76|50029|52 /212992|1987|report + checkpoint committed|

At first ordinary rejection the fixed-reducer cases have14 certified free pages
against15 required. Three harder next-event attempts (new reducer) require18,
produce zero writes and preserve generation, body count/bytes, credits and reducer.
After the two boundary controls, raw erased pages are13/13/16/1/13/12 respectively;
the raw count still includes any possible lazy page and is not certified free.
`nvs_get_stats` counts free/erased entries which are deliberately not usable proof.

Protected event/root publication with a new maximum body/reducer takes1369
four-byte/erase fault units in52 calls, no GC, peak3 nonblank pages and317 live
entries. Retirement replacement takes142 units/22 calls. The primed LEGACY GC
operation takes1425 units/66 calls, two erases, peak32 nonblank pages/131072 B
including padding and2151 live entries. Recovery with the guard enabled either
deduplicates the newly committed event or rejects the uncommitted retry with zero
writes; it does not pretend the fragmented partition has a protected reserve.

## Focused acceptance evidence

[Raw validation](R1_STORAGE_PROTECTED_NVS_GATE_C_20261008.log) records hashes,
SDK identity, fixture configuration, assertions and outputs. Commands run from
`code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2`:

- `make storage-native-transaction-host-test storage-compact-representation-host-test`:
  preserved Gate A/B max384, six-owner/retiring/credit/report/lost-ACK and stale-root
  regressions PASS in their defined host authority/Node-report scope. New actual
  max-report write plan refusal makes zero writes; corruption during preparation
  invalidates current state instead of exposing stale routine state.
- `python3 host/storage/nvs_runtime_probe/run_compact.py --suite protected --output ...`:
  **48 real-SDK cases PASS**. Includes near-full/control/credit/root replacements,
  six maximal pending reports/4000-byte manifest boundary, typed I/O refusal and
  orphan slot exhaustion/recovery, missing/corrupt head/manifest/reducer, duplicate
  retry, cached event/report duplicate with missing body, and unsupported64 KiB configuration.
- **33 interruption/no-cut fixtures**:15 guarded event/publication,6 retirement,
  7 real GC/restart and5 selected-dependency collection. Cuts before data, after
  immutable data, during bank/head/index writes and after publication recover
  exact old/new state. Cuts2/1087 in legacy GC actually interrupt sector erases.
  Children halt with `_exit(77)` immediately at the first injected failure; parent
  starts with deinitialized SDK RAM and mounts persisted bytes anew. No simulated
  writing continues after power cut. No-cut success requires the new state.
- ASan/UBSan host native+compact PASS. SDK **48 cases PASS** with probe/adapter,
  native transaction and compact codec instrumented; SDK/OpenSSL archives are
  uninstrumented, LeakSanitizer disabled. No hardware or full release gate.

The preserved native host summary still prints `gate_C=OPEN`: that provider-free
Gate A/B suite cannot qualify NVS. The separate SDK result above establishes only
the explicitly restricted Gate C completion/safe-rejection envelope.

Typed outcomes distinguish durable Committed, effect-free Duplicate, insufficient
protected space, metadata-publication failure, integrity/recovery failure,
restart-required interrupted/dependency I/O, unsupported configuration, admission
credit/owner limits and invalid requests. A power cut cannot return a C++ outcome;
restart and authoritative recovery establish eligibility. Only Committed/Duplicate
of an already committed EventKey qualify for durable ACK, never radio receipt.

Exactly one authority-selected root is recoverable in this candidate. Candidate
and previous bank bytes are not independent authorized fallback roots. Old/current
dependencies survive every prepublication interruption; collection authenticates
all selected dependencies before deleting anything. Additional authorized roots
would require a union of closures and a new proof; they are not claimed here.

## Capacity and implementation handoff

The actual4 MiB layout stays128 KiB gs_journal with two0x1E0000 OTA slots. Prior
qualified image1864624 B leaves101456 B; the previously observed but unrequalified
1865616-byte artifact leaves100464 B. Reviewed192/256 KiB layouts have a limiting
0x1D0000 slot,35920/34928 B respective margins. No build/CSV was changed or newly
qualified. These larger boundary fixtures do not establish adequate OTA margin.

Existing128 KiB72-hour workload failures remain. No supported volume, critical
reserve/saturation policy or guaranteed72-hour workload is approved/qualified;
192/256 KiB are not universal solutions. No speculative Node event reduction.
The conditional384 identity bound still depends on the documented production
Node-report/owner contract, separately from fitting all retained backend evidence.

First eventual production seam remains Hub NVS provider + durable admission owner,
then ingest/routine-state recovery and versioned FOTA compatibility. Do not copy
the RAM-heavy native reference wholesale. Prerequisites: supported volume/flash
and OTA engineering envelope decision, sustained reserve restoration if this
candidate continues, target RAM/image measurement and physical power-cut tests.
Flash-capacity increase is a separate decision from MCU upgrade; neither is
authorized here. Keep urgent delivery/BAT-C8/ESP-NOW energy/coverage qualification
separate. Stop after this local implementation/evidence commit.
