# Host-native durable transaction correction — 2026-10-08

**Executable correction implemented. Host Gate A PASS under the defined owner/
report/publication contracts. Host Gate B PASS with the explicit trusted
publication authority; without it recovery fails closed. The ESP32/NVS
publication primitive is not implemented or qualified. Gate C remains OPEN.**
Production integration is not ready. No production source or canonical governance
changed; this is a bounded correctness reference, not a deployed encoding.

Start `3d63505067024be92b719f89fc4195c2f90544c8`, storage branch/worktree,
context `2026-10-08.001`, preflight PASS. Origin verified as
`https://github.com/udaybhan200683/Ghar_sajag.git`; the reviewed readiness commit
was ahead1/behind0, explicitly dry-run/pushed, fetched and verified equal remotely.
Canonical remains clean at `3b72892`; no canonical or context change. Existing
untracked `prompt.txt` was never opened, changed or staged. This new experimental
commit is not pushed.

Read AGENTS, mandatory canonical context/release/work-state/index, decisions,
storage contract, active ExecPlan, readiness evidence/log and relevant admission/
retirement/root evidence/source. Original regressions are unchanged and reproduced
in the [new raw log](R1_STORAGE_NATIVE_TRANSACTION_20261008.log). Their legacy
production components still demonstrate missing credits and stale-root fallback;
this run corrects the **host-native** transaction, not production integration.

```text
BUG_CLASSIFICATION=R1_BLOCKER (existing storage durability/lifetime failures)
REQUIREMENT_SOURCE=docs/product/R1_RELEASE_CONTRACT.md; docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md
DECISION_IDS=GS-D005/016/021/022/023/024/025/026/027/028
TASK_SCOPE=host-native owner/credit/report/root corrective implementation and focused validation
OUT_OF_SCOPE=production Hub/Node integration, Gate C allocator, partitions, backend/PWA, BAT-C8, canonical governance/context, Jira, hardware, new-commit push
```

## Implemented code and trust boundaries

`P=code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/`.
`P/host/storage/native_transaction.{hpp,cpp}` implements the serialized transaction;
`P/tests/cpp/storage_native_transaction_validation.cpp` exercises it via real
`MemoryBlobStore`, OpenSSL CommissioningCrypto, canonical Node report encoding
and `RetirementSnapshotRepository::apply_authenticated_report`. The new Make
target is `storage-native-transaction-host-test`, excluded from firmware lists.
No disconnected copy of the admission ledger serves as durable recovery.

The protocol has six owner slots including Active and Retiring, nonwrapping
global owner generations, a configured W in1..32, at most384 retained body rows,
Node reports with at most32 keys, and at most4096 opaque reducer bytes. W32 is the
tested host parameter, not a new product reserve or workload promise. Recovery
requires the exact epoch/window/version. Row bodies use the existing448-byte
causal-input ceiling. Bodies/reducer are opaque complete caller inputs; this
protocol does not implement routine algorithms, summaries or cloud acceptance.

The authenticated registry/transport boundary must supply the verified physical/
logical/home/Hub enrollment binding and transport context. `Proof` is downstream
of that existing boundary, not a commissioning bypass. Each registered owner
has a distinct report key. The host input certificate verifies HMAC over epoch,
slot, owner generation, binding, origin, sequence, body and transport session.
This is a host attestation of already-authenticated input, **not a new Node wire
protocol**. The stored exact digest excludes mutable transport session, so a
rejoin retry remains the same immutable input. Digest comparisons use the existing
constant-time crypto interface. Enrollment/revocation, reducer checkpoints and
dependency completion are trusted Hub-owner management APIs; Node frames cannot
invoke them without the existing authorization layer. Backend completion may be
asserted only after an authenticated matching durable backend receipt.

Node report truthfulness means the existing complete **durably saved** pending
NodeMessage snapshot, including sequenced heartbeat keys and sparse gaps, with
old origins retained and ACK removal saved before absence is reported. This is
the existing `NODE_RETIREMENT_REPORT_PROTOCOL.md` contract, not inferred from
HMAC alone. A malicious/incorrect authenticated producer can lie about absence;
cryptography cannot prove snapshot completeness. Producer adherence/qualification
is a prerequisite. Missing, delayed, forged, incomplete or conflicting reports
do not create credit; the Hub stops new uncovered admission safely.

## Gate A — persisted bound and retirement

Let P_i be the selected complete report's pending set and U_i the accepted,
unretired keys not covered by that report. The encoded image stores exact rows,
report bytes/HMAC, owner phase/generation, and charged count together. Recovery
authenticates them and independently recomputes/checks that count from surviving
rows. A falsely reset count is rejected even with valid image authentication.

New covered keys must be listed; absent covered keys are Retired. A new uncovered
key consumes one of W credits in the same selected image as its immutable body
and reducer update. Exact retry returns Duplicate with no publication, credit or
reducer effect; same-key changed body returns Conflict. Real report progress
returns uncovered credit while listed keys remain retryable. Generation-only
reports, ACK count, rejoin and reboot never refill credit.

Inductively `E_i subset P_i union U_i`, `|P_i|<=32`, `|U_i|<=W`; at most six
retained owners yields `|E|<=6*(32+W)`. The test durably reaches384 identities
with six complete32-key reports plus32 uncovered admissions per owner, reopens
the encoded state, verifies every charge, and rejects the next key. The one-owner
lost-report regression now stops at32 rather than admitting33. Historical
backend/local rows can outlive retry identity; their separate global384-row cap
may reject new work earlier. That cap is a reference bound, not a qualified
offline capacity or a critical-saturation policy.

Revocation selects Retiring and preserves every accepted row, charge and consumer
dependency. New events are rejected; identical accepted retransmissions remain
effect-free duplicates. Retiring still occupies a slot, so a seventh owner is
Full. Release requires a selected complete drained report and **no** remaining
rows. Clearing local/backend owners alone cannot remove a retry-required row;
Node retirement alone cannot remove a backend/local-required body. Missing report
or consumer progress can block replacement indefinitely while preserving evidence.
Released slots receive a strictly newer global generation. Old-enrollment delayed
frames cannot acquire replacement identity or credit. No reset/epoch trick or
automatic revocation of accepted obligations exists.

Retiring is a storage state, not permission to authenticate a security-revoked
peer again. If security removal or permanent Node loss prevents further complete
reports, the conservative implementation keeps that owner slot and its required
rows; replacement availability is not guaranteed. A future stronger authenticated
revocation/closure contract must be proved before relaxing that behavior.

## Gate B — publication authority and recovery

An independently authenticated, versioned86-byte publication head names one
generation, bank, epoch, W and exact encrypted-bank HMAC. Bank images use the
existing AES-GCM provider with fresh random nonces, version/domain-separated
authentication, and exact serialized context. Required nonce entropy remains the
existing crypto-provider contract; generation-derived nonces are not reused on
uncommitted retries.

Every mutation follows the same sequence:

1. Construct/validate bounded next state, including body, credit, complete reports,
   owner phases and reducer; write only the inactive bank.
2. Read back exact bytes, authenticate/decode and check invariants; construct the
   authenticated head binding those bytes.
3. Compare/publish against the exact current authority head. Read authority and
   selected bank again before returning Committed. An API error after persistence
   resolves only through exact authority/readback, never an optimistic ACK.

At most one candidate-bank write and one authority publication are attempted;
there is no retry loop or erase. Duplicate/invalid/full input uses no publication.
Single serialized Hub writer is required; CAS does not make concurrent candidate
bank overwrites safe. Before successful publication the old selected bank remains
authoritative. After publication the new bank contains every retained dependency;
the old bank has no independent recovery authority. The next transaction can
overwrite that inactive bank, but cannot erase data still required in selected
state. Inline complete dependencies avoid report-bank ownership ambiguity in this
reference; a compact production mapping must prove the same closure explicitly.

Recovery reads **only** the trusted head and its named exact authenticated bank.
No highest-valid-bank scan or fallback exists. Missing/corrupt head, missing/
damaged selected child, wrong epoch/W/version, inconsistent credit metadata,
unavailable authority or contradictory generation makes state unavailable and
disables admission/ACK. Old bank presence cannot turn failure into success.
Explicit fresh provisioning refuses existing banks and never runs automatically
after metadata loss. Runtime observation coverage must be re-established;
`observation_available()` is false after recovery. Persisted silence cannot become
NO_ACTIVITY merely because the reducer image decoded.

**Precise missing target primitive:** BlobStore supplies read/write/replace, not
durable linearizable non-rollback compare/publish authority. Authenticated bytes
or a larger generation alone cannot establish that an older complete head was
not replayed. `PublicationAuthority` therefore requires trusted persistent
current-head semantics, with fail-closed loss/rollback detection. The fixture's
fixed-size `TrustedHostAuthority` uses real MemoryBlobStore head bytes plus an
independent persistent host witness surviving Transaction destruction; it models
that primitive, it does not implement it on ESP32 NVS or physical flash. Intact
old-head replay against the witness and authority unavailability both fail closed.
No software checksum is advertised as hardware antirollback protection.

Thus host Gate B's crash/corruption regression passes under a declared authority
contract; production Gate B freshness remains BLOCKED until a real provider and
its failure/threat model are demonstrated. With no trustworthy provider the
implemented engine safely rejects recovery. Gate C alone cannot close this gap.

## Focused failure-injection results

Crashes throw immediately from the fixture, preventing post-power-cut writes.
Recovery uses decoded persistent bytes, including a newly constructed Transaction
in event-crash cases. No copied RAM credit ledger is accepted as evidence.

| Required case | Tested result |
|---|---|
| Before event persistence | Old reducer/empty row/zero credit; no notification; retry newly commits |
| During candidate persistence | Torn inactive bank ignored; old selected state; no ACK |
| After event persistence, before publication/ACK | Complete unselected body does not spend credit or change reducer; retry commits |
| Immediately before root publication | Old complete state survives; no ACK |
| During publication | Torn authority fails closed despite old bank; admission disabled |
| After publication, before notification | Latest reducer/body/credit recover; retry Duplicate, no repeated effect |
| Damaged latest child, older bank present | Fail closed; never return old0x11 after published0x22 |
| Missing latest child | Same stale-root regression fails closed |
| Missing authority / old authentic head replay | No automatic genesis; independent witness rejects rollback |
| Lost report | Charged32 persists; next uncovered key Full; accepted retry still Duplicate |
| Repeated authenticated report | Duplicate, no refill or new publication |
| Forged/conflicting/resurrecting report | Invalid/Conflict; selected report and identities remain |
| Duplicate after reboot / rejoin | Identical immutable input is effect-free; changed body conflicts |
| Six owners plus seventh | Seventh Full; Retiring counts toward six |
| Revocation and delayed retransmission | Accepted key duplicate allowed; new key Retired; released old generation Invalid |
| Journal/recovery dependency still in use | Body remains until retry, local and backend owners all release |
| Partially written credit image | Not selected; old committed root remains valid |
| Authenticated falsely reset credit count | Decoder detects row/count contradiction and fails closed |
| Report crash after bank / after publication | Old charge1 or selected charge0 atomically; body preserved; lost-report ACK replay idempotent |
| Candidate/publication persist-then-API-error | Exact authenticated readback resolves success; no duplicate effect |
| Insufficient-space-like pre-write failure | Fault/no ACK; old generation remains recoverable; no deletion or loop |

Normal strict C++ build/test and ASan+UBSan PASS. Sanitizers ran outside sandbox
because LeakSanitizer cannot inspect threads under its ptrace. Raw log records
source/executable hashes, commands, exits and original/corrected assertions.
No broad SDK matrix, million-event loop, hardware, release gates or motion/power
investigation was run. Existing SDK metadata-space exhaustion remains untouched.

## Exact Gate C handoff and remaining limits

This intentionally complete snapshot makes correctness executable; it is not
the compact deployed format. Tested maximum bank size is **201,573 B**: header33,
six maximal646-byte owner/report records, row count2,384 maximal504-byte rows,
reducer length2+4096, and AES-GCM overhead28. Maximum head86 B. Two retained banks
plus head occupy up to403,232 logical bytes. A conservative NVS replacement
mapping must additionally charge one candidate blob's COW coexistence and an
old/new head: **604,891 logical bytes**, plus the actual authority/witness provider,
NVS entry/chunk/page overhead and GC workspace. One4 KiB GC page alone yields
608,987 B before those other costs; this is arithmetic, not an allocator proof.
It does not fit current128 KiB as-is. No partition or72-hour calculation changes.

Existing NVS provider rejects these new logical keys and oversized blobs; no
adapter claims they fit. A target mapping must reuse the prior compact immutable
body/context formats and bounded manifests while preserving exactly this encoded
owner/credit/report/publication dependency closure. Do not blindly copy full
snapshots into production or infer that384 identities imply384 feasible HOT blobs.
No new volume, reserve, critical classification or storage allocation is approved.

The existing BlobStore boolean write interface also conflates insufficient
space with I/O failure. This transaction surfaces Fault with no ACK and preserves
the selected root; it does not invent a space-error diagnosis from false. Gate C
must expose the provider's actual insufficient-space status and apply protected
admission/backpressure rather than retrying an indistinguishable failure forever.

**Next Gate C step:** map the corrected logical transaction onto bounded NVS
objects and account for its complete next-operation bank/report/credit/root/
authority update, old/candidate dependency coexistence and GC/COW overhead;
implement protected admission/backpressure and bounded reclamation only after
that mapping is proved. Separately close the real publication authority primitive.
Use targeted space/cut/remount tests for the changed mapping, not another full
capacity matrix. Target RAM/image/rollback, product supported-volume/saturation,
time/coverage/summary/backend policy and BAT-C8 physical qualification remain
separate unresolved requirements. No unconditional72h guarantee or production
integration readiness is asserted.

STOP after the coherent host implementation/test/evidence commit. Do not push
the new experimental commit or change production/canonical worktrees.
