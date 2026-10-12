# Engineering Dashboard open decisions and blockers

2026-10-12 UTC; GS-122/120/124/125. All entries OPEN unless stated otherwise.
No new LOCKED decision or context version. The architecture is proposed v1.

| ID | Decision / prerequisite | Owner | Affected implementation |
|---|---|---|---|
| ED-D01 | Explicit acceptance of GS120_ENGINEERING_DASHBOARD_ARCHITECTURE.md, selected subset and source ownership | User / GS-120 | GS-124 production BLOCKED_DESIGN_APPROVAL |
| ED-D02 | Verified technician grant issuer, explicit Home READ_DIAGNOSTICS, expiry/revocation/epoch and deployment principal | GS-109 / GS-143 | All production diagnostic routes and technician browser access; existing generic read is insufficient |
| ED-D03 | Authorized diagnostic privacy fields, export, RAM window and retention; installation result lifetime/store | Product / GS-65 / GS-109 | Durable history, export and installation certificate; no new storage policy selected |
| ED-D04 | Installation deadline, required evidence stages/device manifest and fresh stimulus proof | Product / GS-120 | Production guided step PASS; no example timeout promoted to requirement |
| ED-D05 | Authenticated Node/Hub observation export and target ownership/budget | GS-65 / GS-148 | Live RX/ACK/counter/outbox projection; no existing active endpoint |
| ED-D06 | Exact physical fixture, source-matched running images, state preservation and reset-safe observation | User / GS-114 | Board/motion/physical product E2E BLOCKED; no hardware access |
| ED-D07 | Privileged commands and authenticated supported control path | GS-109 / GS-143 | Restart/recommission/test/identify disabled; not part of proposed MVP |
| ED-D08 | Production CloudSync credential/deployment and durable trusted backend composition | GS-148 / GS-109 | Live S3→backend delivery UNKNOWN; local SQLite proof is not deployment |
| ED-D09 | After GS-148 checkpoint, review shared registry/traceability/status files against actual newer canonical HEAD | GS-122 / GS-148 | No canonical merge or shared-file overwrite while writer active |

Observed source issue: IdentityService.require selects read roles for every
permission other than `manage`. Calling it with `READ_DIAGNOSTICS` would grant
generic read users access. Classification INVESTIGATE_ONLY / REQUIREMENT_GAP
for the new diagnostic permission; requested dashboard scope, no adjacent
identity-policy fix performed. A new exact diagnostic gate needs approved D02.

Original identity range differs: C++ uint64 vs backend positive <2^63 and browser
safe integers <2^53. Classification INVESTIGATE_ONLY for out-of-range production
compatibility. Diagnostic rendering uses exact strings in the proposal, does not
change CloudSync. Original untrusted/zero target time remains UNKNOWN; query
fallback occurrence is not original sensor time. No GS-148 fix authorized here.

Historical mandatory GS-148 journal migration FAIL (`clean migration commits`)
and GS-130 complete-product PARTIAL/FAIL remain visible. They are not waived,
rerun as unchanged failures, or represented as qualified authentication.

Campaign authorization explicitly permits one isolated branch/worktree and saved
review/test preparation. It overrides old single-worktree/no-artifact GS-120
instructions only for this campaign. It does not approve the design itself.
Canonical storage/runtime/CloudSync changes and all untracked evidence are protected.

Safe next action: review ED-D01 and accept a named subset; provide D02/D03/D04
before activating corresponding production behavior. Inactive host preparation
may continue while review is pending. Physical approval is a later separate gate.
