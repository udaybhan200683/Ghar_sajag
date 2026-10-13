# GS-124/125 inactive authorization and diagnostic foundation

2026-10-13 UTC. Scoped Package A/B/C implemented on the existing isolated
`feature/gs124-125-engineering-dashboard`; no production activation or canonical
integration. ED-D01, ED-D02 and ED-D03-MIN policy approval is recorded in
[the scope and impact record](../../../architecture/GS124_AUTHORIZATION_FOUNDATION_20261013.md).
Approvals: GS120/10660, GS143/10670, GS65/10671, GS122/10672 and 10677.
Commercial authentication and CloudSync remain unqualified.

## Implemented boundary

`identity.py` rejects every unknown permission before membership lookup. Known
read/manage role behavior is preserved. READ_DIAGNOSTICS never aliases read.
`diagnostic_authorization.py` defines a separate trusted-adapter seam and enforces
explicit per-Home grant, verified-session interface, membership, expiry,
revocation, versions and current ownership epoch. Missing or malformed authority
denies. OWNER/CAREGIVER/INSTALLER alone grant no diagnostic access. The module
does not verify cryptography or issue credentials: a production GS-76/143 adapter
is absent. Fixture object capabilities and issuer labels are test inputs only.

`diagnostics.py` is an in-process read-only service, outside JsonApi/main and
frontend routing. Class A accepts an already qualified, bounded Home/epoch
technical provider and projects fixed fields. No live provider is implemented.
Class B requires current trusted device/Home/original-generation binding before
an exact original-EventKey SQLite join. The join uses the existing durable commit
and events tables, selects no raw payload, and creates no event pipeline/storage.
Session/grant/membership/ownership and event eligibility are rechecked after reads.

Row, response-byte, ephemeral cursor-count, recentness and freshness bounds are
mandatory injected parameters; none has a production numeric default. Opaque
cursors are tied to the entire current access snapshot and source revision.
Invalid input, absent evidence, stale data and unavailable capabilities have
exact negative assertions. Only the SQLite commit observation can pass in the
trace; eleven other stages remain UNKNOWN. Deployment, producer fingerprint and
clock trust remain unknown where no evidence exists. Successful, denied, invalid
and fault responses carry no-store. Actual browser cancellation/cache behavior
is not implemented or qualified by these headers.

There is no grant-issuance API, live diagnostic route, durable grant/audit store,
persistent diagnostic journal, Node wakeup, radio packet, Hub/CloudSync authority
change, installation certification, restart, recommission or raw-log export.
Generic unsupported routes retain 404; in-process controls deny.

## Executed source evidence

54 distinct registered cases: GS125-AUTH-A01–A18, GS125-PRIVACY-P01–P16,
GS125-TRACE-T01–T14 and GS125-REGISTRY-R01–R06. Exact methods/assertions are in
[TEST_CASES.csv](TEST_CASES.csv). The final registered execution passes all 54.
The earlier 48-case attempt and first 54-case run remain preserved; they are not
additional distinct cases. Local integration uses the real ownership registry,
DurableEventCommit transaction, SQLite read-only connection, duplicate/reopen
logic and caregiver query. Test authority and technical adapters are explicit
fixtures. This proves the inactive policy/projection with supplied trusted state,
not commercial actor verification or an actual C3→S3→backend→PWA delivery.

| Qualification | Result and limit |
|---|---|
| Design | APPROVED bounded policies; deployment/lifecycle decisions OPEN |
| Implementation | COMPLETE scoped inactive foundation; overall GS124 PARTIAL |
| Unit/policy/privacy/registry cases | PASS, 54 distinct cases |
| Deterministic source simulation | PASS scoped state transitions, including T13; no RF/target qualification |
| Local backend foundation integration | PASS T01–T14, real production transaction/query adapters with fixture authority |
| Production issuer/grant lifecycle integration | BLOCKED; source absent |
| Full affected backend gate | FAIL; existing Python bridge and P0 file-backed fixture failures remain |
| Affected caregiver/API regressions | PASS functional 92, streams 5, HTTP 17, bridge 13, API 2, frontend 2, JavaScript 23 |
| Existing Python aggregate | FAIL, 448 executed, one failure and one explicitly allowed historical skip |
| PWA component gate | FAIL; verified eligible backend receipts reused, same Python/P0 failures |
| Production engineering Playwright | NOT_RUN/BLOCKED; no live route or issuer/grants |
| Validation registration | PASS six new meta-cases, existing framework 39, mapping integrity 19 |
| Board / motion / physical product E2E | BLOCKED GS114 NO-GO; no physical operation |
| Full release gate | NOT_RUN |

Initial backend run found a missing `p2d_cloud_contract_validation` prerequisite.
Building the existing host target passed its protocol/completion tests.
The initial mapping attempt rejected an incorrect requirement ID; it was
corrected to existing GS-VAL-01 and both later mapping runs pass all 19 checks. A rerun
replaced that missing-binary error with `bridge durable-before-ACK` failure.
The P0 stage fails `initial file-backed Node recovery` before assertions/browser.
Both fixtures use hard-coded `/tmp` paths; `/tmp` is full even when TMPDIR points
to the isolated ignored build directory. This environment is recorded; these
failures are not waived or converted to PASS. No shared storage or fixture source
was changed to hide them. Historical GS148 journal migration FAIL and GS130 P0
product PARTIAL/FAIL remain mandatory independent gaps.

## Registry and ownership

One `diagnostic-foundation` backend stage is appended to the existing GS116
registry, eligible for fast/release composition without executing those complete
gates. It has a non-production-authentication qualification label. Six meta-tests
exercise actual selection, nonzero subprocess failure despite OK, zero/missing
execution markers, missing registered input and source-fingerprint changes.
Four GS130 feature rows and two source-inventory entries map the foundation,
classified SOFTWARE_ONLY with explicit commercial/activation gaps.

Canonical GS148 source was read-only at intake
`371a560f04b99bce8fd86e58739a75184b555b55` and advanced externally to
`19ec67c365e1bdea8fce61fb46f481f407fa42b9` during this run. The newer first-event
storage proposal was read; backend/frontend code, registry and tracked cleanliness
remain unchanged. No canonical writes were made. Its registry separately adds
`storage-correctness` and `storage-correctness-sanitizers`; neither is copied,
removed or overwritten. No existing isolated registry stage is changed.
An eventual owner-reviewed integration must retain both canonical stages and
the new diagnostic stage, reconcile maps/docs, and rerun affected checks.

Test source checkpoint: `810209e9bbc469b003d1611a6d22c391365cf1c5` plus the
scoped working tree. Final native fingerprint and each changed source SHA256
are in [SOURCE_FINGERPRINTS.json](SOURCE_FINGERPRINTS.json). Native reports record
source unchanged during execution and tracked dirty truthfully. Their original
paths refer to ignored runtime evidence; verbatim copies are under `gs116_runs/`.
Source commit `bfcf293edaf538a68c61b654e8aee141429480ce` contains the same
tested bytes and was pushed normally; actual remote HEAD equality verified.
The later documentation commit is recorded in the delivery/Jira receipt. Exact changed-file
inventory and verified push checkpoint are supplied with the handoff.

## Stop and next implementation prerequisites

1. GS76 chooses and implements production IdP/issuer/session verification and
   logout, with actual negative identity tests.
2. GS143 approves grantor/self-grant policy, numeric TTL/renewal, durable atomic
   grant/revoke/member/epoch versions and sanitized audit lifecycle. No choices
   are invented by this foundation.
3. GS65 supplies qualified current device/Home/generation and technical exporter;
   approve operational row/byte/cursor/window/rate policy and audit retention.
4. After GS148 ownership checkpoint, ED-D09 reviews integration against the actual
   newer canonical HEAD. No merge is authorized by this delivery.
5. Only after these boundaries are qualified, separately authorize route/browser
   composition and prove no-store, logout/Home-switch cancellation and access
   denial in real application/Playwright tests.

Hardware mapping is preparation only: [HIL_MAPPING.csv](HIL_MAPPING.csv), reusing
the existing catalogue/prior campaign matrix. Real optical PIR, reset-safe C3
observation, S3 replay fence and source-matched disposable fixture approval remain
prerequisites. No Jira Done transition or production activation is claimed.
