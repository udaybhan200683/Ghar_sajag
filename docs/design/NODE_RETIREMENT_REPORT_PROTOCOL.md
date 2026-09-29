# Node retirement report protocol and bounded Hub dedupe state

Status: architecture contract for the next implementation task. Production
firmware and the durable storage codec do not yet implement this protocol.

## Source invariants and scope

`NodeRuntime::record` allocates `(logical node, origin session, sequence)`
before queue or store admission. A refusal therefore creates a sequence gap.
`NodeRadio` holds at most 32 pending messages, chooses eligible messages by
round-robin, and prioritizes unsent critical messages during outages. ACK
retirement is by exact key; `Rejected` and a volatile ACK for a business event
leave it pending. The target saves the recovery snapshot before transmitting a
new event and after ACK retirement; a failed save stops its owner. A boot
creates a new `NodeRuntime` origin session, restores old pending identities,
and uses a fresh authenticated transport session. An in-place rejoin can
advance the **transport** session while the existing `NodeRuntime` continues
to allocate under its unchanged **origin** session. Authenticated Hub ingest
permits `origin_session <= transport_session`.

The recovery snapshot includes every pending `NodeMessage`, including
nonbusiness messages. It rejects duplicate pending keys and checks retained
business payloads against pending copies. Normal `record` allocation cannot
create two copies of the same key. `NodeStore::append` currently accepts an
already present key without comparing payloads; the new implementation must
reject a conflicting same-key payload and fail closed.

The proof below covers **all pending NodeMessage keys**, avoiding a separate
exception for nonbusiness retries. A `RetirementReport` is valid only for an
authenticated enrolled physical device and its bound logical source.

## Chosen proof: complete pending-key set

A durable Node snapshot contains the complete set `P` of at most 32 pending
keys. Its `current_origin_session` is the session in which `NodeRuntime` can
still allocate. Its `durable_admission_highwater` is the highest sequence of
an event successfully admitted and saved in that origin session. Failed
admissions need no durable allocation entry: they were never transmissible.
The existing sparse sequence allocator is retained.
Sequence, session, report-generation and enrollment-generation overflow
must stop admission; wrapping any of them would invalidate the proof.

For a key `(S,Q)` in this physical device's binding:

* If `S < current_origin_session`, the Node cannot allocate another event in
  `S`. If the key is absent from `P`, it cannot legitimately be retransmitted.
* If `S == current_origin_session` and `Q <= durable_admission_highwater`, an
  absent key likewise cannot be retransmitted. It was either never admitted
  (a gap) or was individually retired and durably removed.
* A current-session key above the reported highwater may be admitted later.
  A listed key is outstanding regardless of its sequence or age.
* A key from a future origin session is impossible under this report and the
  authenticated transport session.

This is a complete-set certificate, not a greatest-sequence certificate.
The derived retirement floor for a session with listed keys is one less than
its smallest listed sequence. For the current session without listed keys it
is the admission highwater. For an older session without listed keys it is
closed. The complement of `P` also retires individual keys **above** a blocked
floor, so one indefinitely pending low sequence cannot leak unbounded Hub
dedupe records as later events are ACKed.

Alternatives: a contiguous floor alone would pin later ACKed keys behind one
old pending key. A floor with sparse retired gaps becomes an unbounded list
over a long-lived blocked floor. Persisting every failed allocation adds
writes without proof value. A new dense business sequence would change wire
identity, recovery and migration but still would not solve out-of-order ACKs
or cross-session retention. The complete pending set is already bounded by
the production queue cap and needs no separate gap ledger.

## Wire encoding: `NodeRetirementReportV1`

All integers are unsigned, big endian. A logical report is sorted by
`(origin_session, sequence)` and rejects duplicate/zero keys. It contains:

| Field | Bytes | Rule |
| --- | ---: | --- |
| Protocol version | 1 | Exactly 1 |
| Hub retirement/storage epoch | 4 | Nonzero; equals negotiated Hub epoch |
| Retirement report generation | 8 | Nonzero, persisted and monotonic within epoch |
| Current origin session | 8 | Nonzero, no greater than authenticated transport session |
| Durable admission highwater | 8 | Zero is allowed for a fresh origin session |
| Pending count | 1 | 0–32 |
| Pending `(origin_session, sequence)` | 16 each | Session at most current; current sequence at most highwater |

Logical size is **30 + 16N bytes**: 30 B with no pending keys, 542 B at 32.
Physical and logical IDs are omitted because `RuntimeFrameSecurity` already
authenticates the enrolled binding and direction. The receiver must resolve
that binding before assembling the report. The epoch prevents an old report
from being reused after a Hub storage migration.

Add a data-plane frame type `NodeRetirementFragment` to the authenticated
runtime envelope. Its fragment header after the existing 8-byte data-plane
header is: report generation `u64`, report HMAC-SHA256 `32`, fragment index
`u8`, fragment count `u8`, and logical length `u16`: **44 bytes**. A key
derived from the installation binding using the label
`GS-RETIRE-REPORT-v1` authenticates the complete canonical logical report;
the existing runtime AEAD authenticates each fragment. The extra HMAC binds
fragments together and is not a second device identity. The secure frame
allows 222 plaintext bytes, leaving 170 bytes of report data per fragment.
A maximal 542-byte report takes four fragments; a typical report is one
82-byte plaintext / 110-byte secure frame. No fragment exceeds 250 secure
bytes. Assemble at most 542 bytes for one binding/generation/HMAC, verify
the HMAC and canonical encoding, then apply atomically. Fragment timeout,
duplicates and a second digest at the same generation never alter state.

The response is an authenticated `NodeRetirementAckV1` containing epoch `u32`,
generation `u64`, and report HMAC `32`; the Node clears its pending-report
send flag only after the exact response. It may skip superseded reports:
every newer report is a complete snapshot. On lost response, resend the
same report or a newer complete report.

## Node durable ordering

Extend the **same** encrypted `NodeRecoveryRepository` snapshot (version 3)
with retirement epoch `u32`, durable admission highwater `u64`, and retirement
report generation `u64`: **20 new plaintext bytes per Node**. The current
origin session and the full pending set are already present. The report
generation increments only when the report projection changes: admitted key,
durable ACK removal, origin-session change, or epoch change. The outer
repository generation remains the storage-write generation. The epoch and
report generation are never stored independently of the pending set.

An admitted event is saved with its key, payload, new highwater and report
generation **before** radio send. If save or readback is ambiguous, stop
transmission and resolve by reloading the snapshot. A failed admission does
not enter the pending set; a later successful save may jump the highwater
over its gap. A received durable/policy ACK removes exactly its key and saves
the new pending set/generation before any report may claim its absence. A
failed save stops the owner: reboot restores either the old pending key or
the new absent key. Retry timing changes may be persisted without advancing
report generation. On boot, restore the old snapshot, authenticate a strictly
newer transport session, create a fresh origin session, set its highwater to
zero, and save that baseline before reporting or admitting a new event.
An in-place rejoin changes only the transport session; it does not close the
origin session. A previous origin session closes when its last pending key
is absent from a saved snapshot whose current origin is newer. A further
reboot preserves every still-pending older key. At most **32 prior origin
sessions** can each have a pending key, plus one current origin session.
No separate closed-session ledger is required on the Node.

Send a report on the next authenticated NodeHealth opportunity when the
report projection changes; coalesce multiple ACKs. Send immediately after
the saved reboot baseline or successful rejoin, before a planned sleep if
dirty, and periodically with NodeHealth until the exact report ACK. Do not
write a snapshot or send a four-fragment report for every retry. A report
made from RAM before durable snapshot verification is forbidden.

## Hub admission, replay and conflict rules

For each enrolled physical binding, the Hub keeps the latest durable report
generation, its 32-byte HMAC, current origin session, highwater, and pending
set. Newer reports may only increase current origin session, and may only
increase highwater while that origin is unchanged. A key that was in the
previously covered universe and absent from its pending set cannot reappear
in a newer set. An older generation is ignored; same generation/same HMAC
is an idempotent duplicate; same generation/different HMAC is a conflict
and fails closed. On Hub restart, the selected checkpoint restores these
values before event admission. Report epoch mismatch fails closed.

The Hub keeps an exact `(enrollment slot generation, origin session,
sequence, HMAC-SHA256 payload digest)` for each committed EventKey that may
still be retransmitted. HMAC-SHA256 uses a derived Hub dedupe key and a
versioned canonical encoding of the **immutable Node-origin fields**:
physical/logical binding, origin session, sequence, event kind, location,
Node monotonic/occurred times, uncertainty, battery, test/sensor fields,
Node event RSSI, and motion aggregate or other business payload. Exclude
Hub receive time, transport RSSI and mutable power telemetry. Persist the
digest with the committed transition, before a durable Node ACK. Same key
and digest is an exact duplicate and receives a durable ACK without effects.
Same key with different digest is a conflict and fails closed. A full event
payload is retained only while another business/effect owner needs it;
otherwise compact its evidence chunk item to the 53-byte key/digest form.

With no report, legacy exact records remain dedupe-relevant. With a report,
an absent key inside its covered universe is stale/impossible and cannot
produce effects, even if an old radio frame arrives after the report. A
listed committed key remains an exact duplicate. A listed uncommitted key
may be committed normally. A current-origin key above the reported highwater
may be a newly admitted event and is recorded exactly. An older-origin key
not listed is closed. Report application prunes committed-key records only
after its snapshot and the resulting ledger index are durably selected;
evidence chunks required by either checkpoint remain until both cover the
retirement. A crash before selection keeps old dedupe records; a crash after
selection uses the new report to reject any late retired frame. A verified
persisted-but-reported-failed write is resolved by readback; unresolved
corruption stops admission.

The enrolled physical binding, logical source, and enrollment generation
determine a 32-byte binding digest in the snapshot. Ledger entries use a
one-byte enrolled slot plus a four-byte slot generation, preventing a
replacement Node from inheriting old keys. A revoked device's dedupe state
may be dropped only after revocation durably prevents its authentication;
its pending backend effects have their separate stable identities.

## Encoded Hub state and partition budget

The report-state snapshot is one authenticated blob. Header: magic `4`,
format `1`, storage epoch `4`, snapshot generation `8`, Node count `1`
= **18 bytes**. Each of at most ten Node records is: binding digest `32`,
enrollment generation `4`, report generation `8`, report HMAC `32`, current
origin session `8`, highwater `8`, pending count `1`, and up to 32 key pairs
`16` each = **605 bytes/Node**. AES-GCM nonce/tag add `28` bytes. Maximum
blob: **18 + 10×605 + 28 = 6,096 bytes**. Keep at most three physical
snapshot generations (the two checkpoint references and one new write).
The logical report state is at most 6,096 B; the physical reservation is
18,288 B. Each exact committed digest record is `slot 1 + slot generation 4
+ session 8 + sequence 8 + digest 32 = 53 bytes`, at most 32 per Node and
128 across the Hub. Digest bytes alone are at most 4,096 B globally. The
logical Hub dedupe data bound is 605 + 32×53 = 2,301 B for one Node, and
6,096 + 128×53 = **12,880 B globally**, subject to the global 128-event
admission cap. These exact entries share the existing 32 four-item event
evidence chunks; completed items are compacted to digests. One additional
1,004-byte scratch chunk is reserved for copy-on-write replacement. The
Node-side retirement extension is 20 B/Node, 200 B across ten separate
Node devices; the existing protected recovery blob remains capped at 8,192
bytes per Node. Hub ordinary NVS gets no new retirement keys.

The existing checkpoint's ten unsafe frontier identities occupy
`10×(1+64+1+24+8+8) = 1,060` worst-case bytes. Replace them with 32 event
evidence chunk references (`u64 chunk ID + 32-byte digest`, 1,280 B) and one
report-snapshot reference (`u8 bank + u64 generation + 32-byte digest`, 41 B).
Net checkpoint increase: **261 B**, from 4,253 to **4,514 B**. All lists
have explicit limits; codec decoding must reject excess counts and unknown
generations. The report snapshot is selected through the same A/B checkpoint
transaction; no independent selector may publish it early.

| Component | Migration maximum | Normal maximum |
| --- | ---: | ---: |
| Four transition records | 5,328 | 5,328 |
| A/B checkpoints, 2×4,514 | 9,028 | 9,028 |
| Event evidence chunks | 16,064 | 32,128 |
| Four effect chunks | 5,040 | 5,040 |
| Two completion bitmaps | 768 | 768 |
| Selector/epoch/migration metadata | 512 | 512 |
| Extra checkpoint + bitmap + metadata + event scratch chunk | 6,030 | 6,030 |
| Legacy events/receipts still present | 40,448 | 0 |
| Three 6,096-byte retirement snapshot banks | 0 | 18,288 |
| **Total** | **83,218** | **77,122** |

`gs_journal` is 131,072 B. Peak modeled free space is **47,854 B (36.51%)**.
The prior modeled migration entry peak was 3,160 of 4,032 entries. Enlarging
three checkpoint copies costs 9 entries each; one scratch event chunk costs
34 entries. The migration peak is **3,221 used / 811 free (20.11%)**.
After legacy physical slots are retired, the normal entry estimate is
`(3160 - 1792 - 544 + 1088) + 27 + 3×(2+ceil(6096/32)) + 34`
= **2,552 used**, so it is below the migration peak. The ordinary Hub NVS
raw estimate remains **15,520 B**. These are bounded codec/NVS-entry models;
target allocator fragmentation and power-cut behavior still require later
qualification.

Migration must be staged. First transfer authenticated legacy EventKeys,
payloads, completion receipts, and still-pending backend work into new-epoch
evidence/effect chunks and checkpoints. Unknown timer, coverage, rule-input
and config history remains UNKNOWN; do not invent it. Use the scratch event
chunk to transfer a bounded batch, select **both** checkpoint generations
that reference and verify it, bar rollback, then retire only the corresponding
legacy physical slots. Repeat without admitting new events until all legacy
slots have been transferred. No legacy EventKey is declared retired by this
physical transfer: its exact key/digest stays in new evidence storage. Only
after legacy physical slots are gone may the three retirement snapshot banks
be allocated and the new report capability enabled. Existing Node recovery
v1/v2 is decoded, pending identities are preserved, a v3 snapshot with the
new epoch and fresh current origin is saved, then its first report is sent.
Old Nodes without the negotiated report capability keep exact dedupe records
and may be backpressured; no historical retirement floor is fabricated.

## Host proof and implementation boundary

`tests/python/test_node_retirement_protocol_model.py` contains 22
deterministic cases: lost ACK, out-of-order delivery, gap, Node/Hub reboot,
in-place rejoin, late old-origin event, 32 simultaneous previous sessions,
session closure, report replay/conflict/resurrection, payload conflict,
crashes before/after Node durable removal, lost report/response, full queue,
wire bounds, and the storage calculation. It is an architecture model, not a
test of future firmware. The next implementation task must implement the
versioned snapshot/wire codecs and A/B report-state ownership, then rerun
equivalent tests against production code and target NVS fault injection.
Production log-slot reclamation and HubRuntime integration remain separate.
