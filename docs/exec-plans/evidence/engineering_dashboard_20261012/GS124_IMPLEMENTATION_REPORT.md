# GS-124 implementation report — 2026-10-12

**Production implementation: BLOCKED_DESIGN_APPROVAL. Inactive preparation: PARTIAL,
executed and reviewable.** GS-124/10622 requires explicit acceptance of GS-120;
none has been received. The campaign explicitly authorizes inactive preparation.
No product route, production dashboard, verified technician grant, firmware
observation export, persistent schema or privileged command was activated.

## Delivered preparation

`docs/architecture/GS120_ENGINEERING_DASHBOARD_ARCHITECTURE.md` is the complete
proposed design. Its versioned contracts, original identity/provenance, seven
screens, installation transitions, security/retention gates, resource budgets,
fault classifications, reuse plan and sequence are ready for a named review.
The interface inventory distinguishes production source, logs, host evidence and
missing capabilities. There are 20 proposed feature/test mappings, 29 simulation
cases and 14 physical mappings. These are proposals, not executed product acceptance.

`code/tests/support/engineering_dashboard_review/` contains isolated draft models,
37 model tests and 8 real API integration tests. Nothing imports these modules
from production. Identity validation and contact-lease calculation reuse existing
backend implementations. The draft model preserves exact counters, independent
stage evidence, count/byte limits, fixture-scoped grants and exact-device
installation candidates with explicit test policy. Fixture grants are input to
tests, never a production authenticator. Draft timeout values do not establish
product requirements. The preparation keeps no installation certificate or
diagnostic history in production storage.

`prepare_host_event.py` builds the existing production C3/S3 host stack and
CloudSync serializer. Its sole C++ test adapter relocates a fixture's hardcoded
temporary-directory prefix into owned build output because `/tmp` is full.
Production objects, shared file-flash fixture, encoding and runtime logic are
unchanged. All 8 existing board groups / 325 checks pass with that adapter.

The integration uses a real file-backed SQLite transaction through the existing
`DurableEventApi`, reopens the database, queries the existing caregiver service,
and verifies one-row dedupe, payload conflict and authorization-seam rejection.
It exports `REVIEW_FIXTURE.json`; this is saved actual local API evidence, not a
live target connection. Original Node-local `room:10:1` maps to the authenticated
Hub-qualified `p6:devicen4:rooms10q1`, preserving physical/logical identity and
original session 10 / sequence 1. The record's room and occurrence are checked
through the actual query. Original zero/untrusted time remains uncertain; the
backend's projection fallback cannot be called the sensor timestamp.

`review.html` renders all seven proposed screens. The trace deliberately has one
observed local backend-commit PASS and nine UNKNOWN stages. Independent host
assertions do not become target trace receipts. Filtering, saved-record refresh,
disabled controls and desktop/mobile layouts are executable. Twenty Playwright
checks validate this static review artifact; technician/caregiver browser
authorization and live updates remain unimplemented. There is no UI-only claim
of deployed backend delivery or optical PIR qualification.

## Isolation and impact

Owning Jira for preparation: GS-125; coordination GS-122; design GS-120.
Changed components: test support and proposed documentation/review artifact only.
Affected shared production interfaces: none. Existing production Node, Hub,
backend and caregiver frontend are byte-identical to committed baseline
`77e29d44c57f0851f78358049c288323c985d2e7`.
No firmware, persistence, CloudSync authority, reclaim policy, shared registry,
source-feature inventory or physical catalogue changes were made. Target builds
and sanitizers are deferred because no target code changed. Focused existing
API, board-stack, framework and no-port HIL checks were actually executed.

The explicit campaign exception permits only
`/home/udaybhan/projects/Ghar_sajag_r1_dashboard` on
`feature/gs124-125-engineering-dashboard`. The canonical GS-148 worktree has not
been edited, synchronized or merged. Canonical status documentation updates are
proposed on this isolated branch; reconcile them after GS-148's checkpoint.
Existing staged/unstaged changes, managed components and historical evidence
remain protected. No serial interfaces or hardware operations were used.

## Remaining production work

1. Accept the named design subset (ED-D01); define a verified technician grant,
   explicit Home permission and revocation semantics (ED-D02).
2. Approve privacy/retention and installation policy where applicable
   (ED-D03/04). Implement the read-only backend projection and dedicated PWA
   screens with actual authorization; run complete affected suites.
3. Agree target observation ownership/export with GS-65/GS-148 (ED-D05), then
   collect live evidence through the existing product path. Do not add a second
   event pipeline or change ACK/durability.
4. Activate permanent GS-116 stages and GS-130 feature mapping against approved
   production source. Until then all proposed IDs are DRAFT_NOT_REGISTERED;
   existing infrastructure PASS does not mean new registry integration PASS.
5. Qualify deployed CloudSync/authentication separately (ED-D08). Resolve GS-114
   NO-GO and obtain exact fixture approval before physical work (ED-D06).

GS-148's historical journal migration failure and GS-130 product PARTIAL/FAIL
remain open. Neither is suppressed or declared qualified. Commands, counts,
failed attempts, fingerprints and reproduction are in GS125_VALIDATION_REPORT.md
and README.md. This report does not meet GS-124's production Done criteria.
