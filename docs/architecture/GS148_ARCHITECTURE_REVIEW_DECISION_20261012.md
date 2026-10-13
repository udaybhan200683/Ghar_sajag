# GS-148 approved architecture direction — 2026-10-12

Classification: **APPROVED ARCHITECTURE**, subordinate to LOCKED decisions and
the release/domain contracts. This records [GS-148 comment 10513](https://udaybhan200683.atlassian.net/browse/GS-148?focusedCommentId=10513)
and the A–O review in comments 10514–10522. The immutable
[original source audit](GS148_ARCHITECTURE_REVIEW_20261012.md) used historical
`e31e8ef6314abcc777eb5979c3d33939cdb7b296`. Its old source paths and status are
provenance, not instructions to resume an old worktree.

The user subsequently authorized only the software P0 reconciliation and bounded
P1/P2 correctness package after GS-152 Done. The implementation and current
gap dispositions belong in the [dated evidence/handoff](../exec-plans/evidence/R1_GS148_P0_P1_P2_20261012.md).

- Finish the existing S3 encrypted segmented LittleFS outbox, exact identity and
  reducer checkpoint stores, bounded NVS control state and replay fences. Reuse
  the existing stack; preserve durable-before-ACK, original EventKey/payload/
  admission context, authenticated ownership, Node retirement and fail-closed
  authority checks.
- Reproduce local prepared-identity, recovery-bank and witness-floor defects
  against current source before correction. Preserve already qualified logic
  and RPF00–RPF08 diagnostics. Production deletion stays disabled.
- Finish trusted CloudSync, production credentials and domain/request-bound
  durable backend receipts only after the owning security decisions. Backend
  owns long-term history; Internet availability triggers continuous sync.
- Six-Node HIGH is a qualification candidate, not a 72-hour commercial promise.
  STRESS measures honest saturation. Workload, field lengths, reserve, overflow,
  retention, latency, memory and endurance budgets need explicit decisions and
  measurements.
- Retain the dual 4-MiB OTA, 4-MiB LittleFS and 256-KiB state candidate. Measure
  whole-filesystem allocation and current-format recovery before lifecycle
  activation. This decision does not change flash partitions or authorize any
  device operation.
- Preserve current-format R1 durability and supported rollback. Keep historical
  migration failure visible under its separate owner and framework applicability
  decision. GS-145 acceptance does not close GS-148 lifecycle scope.
- Physical qualification remains separately authorized, fixture/image matched,
  and independent of host/target-build PASS. GS-114's physical NO-GO remains.

**PROPOSED PRODUCT POLICY:** D-A through D-M remain OPEN: commercial workload /
offline envelope and exact-summary policy; local retention; protected reserve /
overflow; abandoned or revoked pending data; commercial geometry; installation
incarnation/key/transfer policy; production credential and possession proof;
trusted receipt mechanism; transfer/revocation disposition; supported format /
rollback matrix; historical migration gate applicability; latency/heap/wear
budgets; transfer UX scope. No new LOCKED decision or CONTEXT_VERSION increment
is introduced by this implementation record.

The [archived acceptance matrix](../exec-plans/evidence/gs148_architecture_20261012/ACCEPTANCE_MATRIX.csv),
capacity, wear and source inventories remain historical proposals. Their 72
cases are not blanket implemented/executed acceptance. New scoped assertions
use permanent IDs in MASTER_TRACEABILITY; the dated package evidence states
which portions actually ran and which remain blocked or unimplemented.
