# GS-124 authorization/privacy foundation — scoped approval and impact

2026-10-13. Owner GS-124/125; dependencies GS-76/143/65; coordination GS-122.
Approved by the user's bounded implementation request and GS-122/10677.
This is an IMPLEMENTATION_DESIGN and approval record for a non-active interface,
not a second requirements master or production authentication authority.

Approval sources: GS-120/10660 (ED-D01 read-only architecture), GS-143/10670
(ED-D02 Home diagnostic permission), GS-65/10671 (ED-D03-MIN privacy),
GS-122/10672 and 10677 (execution/ownership limits). Earlier pending-policy labels
are superseded; provider, grantor/self-grant, TTL, audit/grant storage, numerical
resource policy and production activation are NOT approved by these decisions.
No canonical files are edited. Canonical policy promotion/context versioning is
an ED-D09 owner boundary; context remains the preflight-matched 2026-10-11.001.

## Before-edit scope and interface contract

Affected component: backend identity/action enforcement and new non-composed
read-only modules. IdentityService.require("read"/"manage") keeps existing role
behavior; unknown actions become DENY before membership lookup. Diagnostic
permission never aliases generic read. No HTTP header, request dictionary,
verified flag, QR or role is promoted to a human principal.

A trusted injected source supplies an independently verified actor/session,
current Home membership, explicit grant, ownership epoch and versions. The
foundation enforces expiry/revoke/version/epoch but does not authenticate that
source or construct production credentials. Missing source denies. No grant
issuance, live JsonApi route, server composition or engineering browser route.
Grantor/self-grant decisions and durable atomic lifecycle stay GS-76/143-owned.

The projection requires explicit trusted bounds with no numerical defaults;
absent policy disables it. Class A reads only a scoped bounded technical source;
no live target exporter is invented. Class B queries a single original EventKey
from the existing SQLite event/durable-commit join, fenced by Home/current epoch,
original generation and configured recent window. No timeline, duplicate table,
new event owner or data writer. The SELECT excludes raw payload. Recheck trusted
authorization after source reads; changed session/member/grant/ownership versions
invalidate in-flight data and bounded-memory opaque cursors. UNKNOWN/STALE/
UNSUPPORTED replace absent evidence, not fictional PASS. Response allowlisting,
safe error codes and no-store apply to success/denial/failure. Controls and
installation certification stay disabled.

## Test/registration impact before implementation

New actual-source tests: unknown/write/issuance denial, forged/missing actor,
OWNER/CAREGIVER/INSTALLER without grant, cross-Home, expiry/revoke/member/epoch
changes, stale cursors/in-flight reads, original commit/key/time/zone and
generation, Class A/B redaction, missing-stage UNKNOWN, rows/bytes/cursor bounds,
invalid filters, sanitized storage faults and default-disabled ingress.
Injected test authority is explicitly NON-PRODUCTION; IdP, issuer and real
grant lifecycle qualification remain BLOCKED/NOT_RUN where source is absent.

Prior suites: registered backend and affected API/caregiver PWA regressions,
JavaScript caregiver tests, framework/meta and feature mapping. Reuse GS-116
selection/adjudication/fingerprints and GS-130 source/feature inventory. Append
isolated registry/matrix changes only; never overwrite GS-148's canonical file.
Record the newer canonical delta for owner review before merge. No Node/Hub
runtime/shared wire change; old 45/20 preview and 325 board campaign are not
repeated without actual affected source. No C++ sanitizer/target build required
for Python-only code. Full release NOT_RUN. SOFTWARE_ONLY foundation; existing
physical mappings BLOCKED_GS114_NO_GO, no ports or hardware operations.

## Ownership, triage and stopping point

Dashboard source/local/remote 31822b1a6bd1a7fc11e00fb63805eb5110e444b2 on existing
feature/gs124-125-engineering-dashboard. Canonical advanced to
371a560f04b99bce8fd86e58739a75184b555b55. Backend/frontend remain unchanged from
the shared baseline; GS-148 firmware/tests/registry/docs advanced. Those changes
are inspected read-only, neither merged nor copied. Canonical tracked tree clean
at intake; untracked managed components and physical evidence preserved.

BUG_CLASSIFICATION=R1_FIX for unknown-action fallback (approved ED-D02 security
denial); REQUIREMENT_SOURCE=GS143/10670; DECISION_IDS=ED-D02;
TASK_SCOPE=isolated non-active foundation; OUT_OF_SCOPE=issuer/provider,
grantor/self-grant/TTL, durable grant/audit, activation, target exporter,
GS148 persistence/CloudSync and hardware. No adjacent fixes.

Next separate prerequisites: qualified GS-76 identity/session/issuer; approved
GS-143 grantor/expiry and durable versioned revoke/member/epoch/audit; GS-65
trusted exporter; actual operational rate/row/byte/window policy; production
browser cancellation/cache proof; ED-D04–09. Historical journal migration FAIL
and full P0 PARTIAL remain mandatory. Stop after this bounded package.

## Delivery checkpoint — 2026-10-13

Source `bfcf293edaf538a68c61b654e8aee141429480ce`, isolated branch pushed and
actual remote HEAD verified. 54 distinct source cases PASS; existing framework
39 and mapping 19 PASS. Backend/PWA aggregates FAIL on existing CloudSync/P0
file-backed fixtures in the full-/tmp environment; no aggregate/release PASS.
[Report and exact receipts](../exec-plans/evidence/engineering_dashboard_20261013/README.md).
Canonical advanced externally to 19ec67c, documentation-only storage proposal;
current decisions/domain/status delta read, no requirements or source copied.
Issuer/grant lifecycle, activated HTTP/browser and target evidence remain absent.
