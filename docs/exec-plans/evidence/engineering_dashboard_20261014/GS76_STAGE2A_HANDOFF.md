# GS-76 Stage 2A identity boundary and pause/resume handoff — 2026-10-14

Owner: GS-76. Related: GS-143, GS-122/124/125, GS-116/130. Dashboard branch
`feature/gs124-125-engineering-dashboard`; starting local and GitHub remote HEAD
`193b641d8ae49e50675716317ad2ad2bc564d9e9`, clean. Context preflight
PASS at `2026-10-13.001`. The separate canonical GS-148 worktree was inspected
read-only and had ongoing uncommitted source/evidence; no file there was changed.

## Scope and current result

Classification: `R1_BLOCKER`; requirement source GS-76, GS-143/10706,
GS-122/10705, GS-DIAG-01; no new product decision. Affected component: backend
human identity boundary; shared interfaces are Stage 1 `ServiceAuthority`,
`TrustedDiagnosticAuthority`, current Home membership and ownership registry,
and future PWA/API sessions. Positive, negative, expiry, outage, logout and
offboarding cases are registered in GS-116 `diagnostic-foundation` and GS-130
`DASH-HUMAN-AUTH-BOUNDARY`. This is SOFTWARE_ONLY; physical and release gates
remain separate. No hardware, firmware or canonical worktree operation occurred.

The reusable, inactive `human_authentication.py` boundary requires an injected
cryptographic verifier and an authoritative live session directory. It checks a
configured HTTPS issuer, intended audience, normalized credential use, subject,
issued/not-before/expiry times, session identity and current account/session
state, then maps issuer+subject to a server-owned actor ID. It accepts no
role, Home, company, `verified` flag or email claim as authorization. Missing
dependencies, malformed assertions, revoked sessions and directory/verifier
outages deny. Its verifier and directory in tests are fixtures; **no production
OIDC signature verification, identity issuer, session store, route or PWA login
has been implemented**. `JsonApi` remains development-only with `X-Actor-Id`;
service and diagnostic routes remain absent.

The existing `IdentityService` checks in-memory Home membership but does not
authenticate a human. `ServiceDesk` persists host SQLite tickets and grants,
using an injected `ServiceAuthority` fixture; its transactional Home/Hub/Node/
ownership-epoch checks remain unchanged. `HubOwnershipRegistry` owns device
association, not human login. `DiagnosticAuthorizer` enforces explicit current
grant policy but accepts only a future trusted snapshot provider. The modular
PWA `ApiClient` accepts an injected bearer token provider. The shipped static
`frontend/public/app.mjs` reads a configured Home ID and fetches a snapshot
with same-origin credentials; no production login, refresh, staff view or
caregiver approval route is composed. PostgreSQL is described as a future
backend adapter and migration 011 is SQLite-only.

## Managed OIDC recommendation for owner review

**Recommend evaluating Amazon Cognito User Pools in ap-south-1 (Mumbai) first**,
subject to product-owner approval of provider, residency, projected MAU/feature
cost, recovery/MFA method, staff onboarding/offboarding and operations. This is
an engineering recommendation, not a vendor selection or deployment. AWS lists
Cognito in Mumbai, managed login with sign-up/sign-in/password reset, OIDC
discovery/JWKS, authorization-code PKCE, user disable and server-side global
sign-out. Pricing is MAU/feature dependent; federation, advanced security and
other options can change cost. Verify a dated quote against the intended mix.

| Option | Caregiver and staff fit | Cost and operations to review |
|---|---|---|
| [Cognito](https://aws.amazon.com/cognito/pricing/) | [Managed login](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-authentication-approach.html), [OIDC discovery](https://docs.aws.amazon.com/cognito/latest/developerguide/federation-endpoints.html), [Mumbai endpoint](https://docs.aws.amazon.com/general/latest/gr/cognito.html); separate server staff roster still required | MAU tiers and add-ons; AWS IAM, pool/client/JWKS and recovery operations |
| [Google Identity Platform](https://cloud.google.com/identity-platform/pricing) | Email/social and OIDC federation; [tenant separation](https://docs.cloud.google.com/identity-platform/docs/multi-tenancy) available | MAU method tiers, SMS/MFA charges; Google project/tenant and blocking-function operations |
| [Auth0](https://auth0.com/pricing) | Hosted CIAM, flexible [PKCE and refresh rotation](https://auth0.com/docs/secure/tokens/refresh-tokens/use-refresh-token-rotation) | Plan/add-on cost and tenant operations; [public-cloud localities](https://auth0.com/docs/get-started/auth0-overview/create-tenants) do not list India |
| [Microsoft Entra External ID](https://learn.microsoft.com/en-us/entra/external-id/external-identities-pricing) | Consumer external tenant plus possible staff ecosystem fit | MAU and premium add-ons; [Go-Local is currently listed only for Australia/Japan](https://learn.microsoft.com/en-us/entra/external-id/external-identities-pricing), so India residency requires review |

The table is based on provider documents read 2026-10-14. It does not assert a
legal India residency mandate or a stable price. The vendor choice must follow
a current quote, data-flow/residency review and actual hosting decision.

## Production interface and security responsibilities

1. **Ingress:** a selected OIDC/BFF adapter must perform actual signature and
   pinned-algorithm/JWKS validation, issuer/audience/use/time verification,
   key rotation and issuer-constrained discovery before returning a
   `VerifiedAssertion`. No unverified JWT decode, arbitrary `kid` URL, ID-token
   substitution, client role or `X-Actor-Id` header is trust. The server maps
   `(issuer, subject)` to a stable local actor and checks revocable session state
   on every protected request. The exact provider claim mapping, session type
   and clock-skew policy need source-backed review.
2. **Authorization:** GS-143 supplies current server-owned Home membership and
   approved caregiver role. A separate company directory supplies ACTIVE admin/
   technician status, company association and offboarding. Stage 1
   `ServiceAuthority` must join these to exact ticket and current ownership
   registry state under an agreed transaction/version fence. No staff or Home
   role in a token grants diagnostics. Real-Home admin details need the same
   caregiver approval; only isolated synthetic/test Homes permit the approved
   authenticated dev-admin exception. No service OTP is used.
3. **Browser session:** choose BFF cookie or bearer-token PWA architecture before
   production wiring. For a BFF, keep refresh tokens server-side, use Secure,
   HttpOnly, SameSite cookies and server-validated CSRF for mutations; for a
   bearer PWA, establish safe token storage/refresh and origin controls. Both
   need OIDC authorization-code PKCE, state/nonce, account recovery, logout,
   refresh rotation/replay handling, session revocation and offboarding. On
   logout/Home switch/revoke/expiry, abort polling and clear Home diagnostics
   cache; backend rechecks every request and before returning data. Cookie,
   CSRF, TTL and recovery policy values are not chosen here.
4. **Persistence:** current `InMemoryStore` Home roles and host SQLite migration
   011 need PostgreSQL schema/adapter compatibility, foreign keys, unique live
   request, row locks/serialization, revision fencing, audit, retention and
   multi-worker restart review. IdP session revocation and staff/Home changes
   must invalidate ticket grants immediately. No production PostgreSQL schema
   is claimed by this Stage 2A boundary.

## Executed qualification

New stable tests `GS76-AUTH-H01..H14` exercise the inactive boundary with
injected fixtures. They do **not** prove cryptographic verification, deployed
sessions or end-to-end caregiver/browser behavior. Registering the tests does
not make GS-76, GS-143 or GS-124 Done. Source fingerprint
`3dff695c90b79bed22e74f761a85b40074408f2d76f1338a41e55ea1375ca149`
matched both aggregates; each reports `source_unchanged=true`. Source was
uncommitted during execution (`tracked_dirty=true`), then reviewed for commit.
The native reports and all stage logs were copied byte-for-byte to
[`validation/`](validation/); `validation/SHA256SUMS` verifies the copy.

Validated source, registration, documentation and native evidence were committed
and pushed as `8e1c11472c28b9d2bd3706d5c3b350be70e95db3`. Actual GitHub
remote HEAD equaled local HEAD; the tracked dashboard worktree was clean after
that push. Validation ran on the same source bytes before commit, with
`tracked_dirty=true` truthfully retained in the native receipts. The only
following change is this delivery-checkpoint documentation update. Ignored
local build/report artifacts remain preserved; no canonical GS-148 file moved.

| Command | Result | Exact evidence |
|---|---|---|
| `PYTHONPATH=backend:. python3 -m unittest discover -s tests/engineering_dashboard -p 'test_*.py' -v` from `code/` | PASS, exit 0, 98/98 (84 prior + 14 new) | `validation/dashboard_98.log` |
| `make validation-framework-test` | PASS, exit 0, 39/39 | `validation/framework_39.log`; composed registry also ran the new stage |
| `make feature-coverage-test` | PASS, exit 0, 158 feature rows, 209 modules, 14 physical catalogue entries; 20/20 meta-tests | `validation/feature_coverage.log` |
| `make validation-backend` | **FAIL, exit 2**, 14/15 stages PASS; Python 449 PASS with one allowed historical skip; diagnostic-foundation 98/98 PASS | `validation/backend-1791993307048834831/report.json` and stage logs |
| `make validation-pwa VALIDATION_REUSE_REPORTS=evidence/validation_framework/backend-1791993307048834831/report.json` from `code/` | **FAIL, exit 2**, 11/12 stages PASS; 10 eligible same-source/profile backend PASS receipts reused; JavaScript 23/23 PASS fresh | `validation/pwa-1791993447465767670/report.json` and stage logs |

Both aggregates fail only the mandatory `p0-full-product-e2e` completeness
adjudication. Its command exits 0 and executes 26/26 scenarios plus one Chromium
test, including initial file-backed Node recovery, but the actual P0 report says
`product_vertical_status=PARTIAL`. It names the missing production Hub TLS/
credential authenticator and enrollment-generation registry binding under
GS-148; the local test credential does not qualify it. The stage therefore
correctly remains FAIL. `/tmp` remained about 1.1 GiB free and no ENOSPC
occurred. Physical HIL, OTA and full release gate were NOT_RUN.

## Next action

Next action after product-owner approval: select provider and session model;
implement a vetted signature verifier and durable session directory; qualify
actual current Home/staff authority and PostgreSQL transaction fence; then
compose authenticated caregiver/Admin/Technician PWA and API flows and real
browser/API security tests. Keep production routes disabled until that vertical
path passes. GS-148 P0 credential/enrollment completeness and physical release
qualification remain independent blockers.
