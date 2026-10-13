# Engineering Dashboard open decisions and blockers

Updated 2026-10-13 UTC; GS-122/120/124/125. ED-D01/02/03-MIN policies are
approved; remaining implementation/deployment decisions remain OPEN.
No new LOCKED GS-D decision or context version on this isolated branch.

| ID | Decision / prerequisite | Owner | Affected implementation |
|---|---|---|---|
| ED-D01 | APPROVED bounded read-only architecture, GS120/10660 | User / GS-120 | Isolated inactive foundation authorized; production activation remains gated |
| ED-D02 | APPROVED explicit Home READ_DIAGNOSTICS policy, GS143/10670. Production issuer, grantor/self-grant, TTL and durable atomic lifecycle OPEN | GS-76 / GS-143 | Fail-closed policy implemented in isolation; production trust infrastructure absent |
| ED-D03-MIN | APPROVED Class A and narrow exact-event Class B allowlist/no-store, GS65/10671. Numeric bounds, audit storage/retention and any expanded diagnostics OPEN | Product / GS-65 | Inactive ephemeral projection only; target source and browser qualification absent |
| ED-D04 | Installation deadline, required evidence stages/device manifest and fresh stimulus proof | Product / GS-120 | Production guided step PASS; no example timeout promoted to requirement |
| ED-D05 | Authenticated Node/Hub observation export and target ownership/budget | GS-65 / GS-148 | Live RX/ACK/counter/outbox projection; no existing active endpoint |
| ED-D06 | Exact physical fixture, source-matched running images, state preservation and reset-safe observation | User / GS-114 | Board/motion/physical product E2E BLOCKED; no hardware access |
| ED-D07 | Privileged commands and authenticated supported control path | GS-109 / GS-143 | Restart/recommission/test/identify disabled; not part of proposed MVP |
| ED-D08 | Production CloudSync credential/deployment and durable trusted backend composition | GS-148 / GS-109 | Live S3→backend delivery UNKNOWN; local SQLite proof is not deployment |
| ED-D09 | After GS-148 checkpoint, review shared registry/traceability/status files against actual newer canonical HEAD | GS-122 / GS-148 | No canonical merge or shared-file overwrite while writer active |

Previously observed unknown-action fallback is corrected under approved ED-D02
in the isolated foundation. IdentityService.require now denies unknown actions;
known read/manage behavior is regression-tested. Canonical GS-143 owner review
remains required before integration; canonical source is untouched.

Original identity range differs: C++ uint64 vs backend positive <2^63 and browser
safe integers <2^53. Classification INVESTIGATE_ONLY for out-of-range production
compatibility. Diagnostic rendering uses exact strings in the proposal, does not
change CloudSync. Original untrusted/zero target time remains UNKNOWN; query
fallback occurrence is not original sensor time. No GS-148 fix authorized here.

Historical mandatory GS-148 journal migration FAIL (`clean migration commits`)
and GS-130 complete-product PARTIAL/FAIL remain visible. They are not waived,
rerun as unchanged failures, or represented as qualified authentication.

Campaign authorization explicitly permits the existing isolated branch/worktree
and the named inactive foundation. It overrides single-worktree instructions
only for this campaign; named approvals do not authorize production activation.
Canonical storage/runtime/CloudSync changes and all untracked evidence are protected.

Next: qualified GS-76 identity, approved GS-143 lifecycle and GS-65 target source,
then ED-D09 canonical ownership review. ED-D04/06/07/08 remain separate gates.
See the updated CAMPAIGN_HANDOFF.md for exact implementation and test evidence.
