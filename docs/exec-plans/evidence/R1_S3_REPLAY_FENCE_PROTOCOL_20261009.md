# S3 replay-fence publication protocol

The selected encrypted NVS retirement snapshot remains the data authority. Schema 3 persists each occupied node's enrollment binding digest; schema 1/2 remain readable, but a legacy row without the persisted binding digest cannot authorize identity eligibility until refreshed by an authenticated report. The LittleFS lifecycle-root reference is the snapshot's authenticated publication witness; it binds storage epoch, report generation, bank, and snapshot digest. A report is eligible to fence keys only after the NVS checkpoint selects the verified bank and the LittleFS root has been atomically replaced and read back.

For an update, close event admission, write and verify an unselected NVS bank, select it with the durable checkpoint, then atomically publish/read back the LittleFS fence reference. Reopen admission only after both references match. Any ambiguous write leaves admission closed. On boot, recover the selected NVS reference first; a missing or older LittleFS reference is advanced from that selected snapshot before admission opens, while a newer, conflicting, corrupt, or unresolvable reference fails closed. No identity rows are removed by this protocol.

The bounded Node snapshot carries the per-owner generation, session, high-water, and pending-key exceptions. A key is fenced only when its authenticated owner slot, generation, and binding digest match, its session/sequence is covered by the report's retirement predicate, and it is not listed pending. Node sequence numbers advance only after durable local admission, so the current-session high-water is a contiguous admitted prefix; failed admission does not create an unreported gap. Keys beyond the covered boundary remain admissible. New exact identity rows persist the authenticated owner tuple under the existing encrypted identity head; older rows without that tuple remain ineligible. The three-bank rotation remains bounded; the maximum owner-bound report blob is 6,097 bytes, and the lifecycle root stores one fixed-size reference, so advances do not create an unbounded key ledger. Identity eligibility additionally requires the exact retained identity, backend completion, reducer checkpoint coverage, and this matching authoritative witness.

## Validation evidence

Focused `hub-runtime-checkpoint-host-test`, `node-retirement-protocol-host-test`,
`hub-retirement-snapshot-host-test`, `s3-durable-outbox-host-test`, and
`hub-incremental-completion-host-test` pass. The identity gate has an eligible
case after completion, plus fail-closed coverage for missing report/completion,
wrong EventKey session, owner slot/generation/digest, pending exception, restart,
and before/after lifecycle publication cuts. Repeated three-bank fence advances
keep the lifecycle root size fixed. The prior 3,278-event lifecycle and 6,556
cumulative completion regressions still pass; completion storage is reclaimed
from 524,262 bytes to zero in the first reuse window. Focused ASan/UBSan runs pass.
The clean isolated ESP-IDF 6.0.3 S3 build passes with image size `0x1c4b60`
(1,854,304 bytes). No hardware was flashed or changed. This does not implement
identity deletion or qualify physical power-cut behavior.
