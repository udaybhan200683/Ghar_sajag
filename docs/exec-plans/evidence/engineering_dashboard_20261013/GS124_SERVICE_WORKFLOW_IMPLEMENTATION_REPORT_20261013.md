# GS-122/124/125 service-workflow implementation checkpoint — 2026-10-13

## Delivery state

The approved service-desk behavior was inspected against the isolated dashboard
source and its latest reconciled context. Production implementation is
`BLOCKED_AT_PRODUCTION_IDENTITY_AND_STORAGE_BOUNDARY`; no ticket endpoint,
service-desk tables, role view, consent grant writer, or production route was
added. This preserves fail-closed behavior instead of trusting the local
`X-Actor-Id` adapter or introducing a second identity/device registry.

Dashboard branch `feature/gs124-125-engineering-dashboard`, local and GitHub
remote HEAD `ebdec41fde2389a03974a57d30a0118c6adafeeb`. The post-reconciliation
test-infrastructure change is committed and pushed. Dashboard worktree was
clean at inspection. Canonical GS-148 branch
`feature/r1-commercial-baseline` remained at local and remote HEAD
`774da5c2ee8073c535df2fe56ecdbf548c16ebf0`, with 35 staged, modified or
untracked paths. The canonical worktree and GS-114 evidence were inspected
read-only and left untouched. Context preflight returned PASS at the dashboard
HEAD; both context versions are `2026-10-13.001`.

## Source inventory and boundary

| Area | Existing Ghar Sajag source | Service-workflow finding |
|---|---|---|
| HTTP API and actor | `code/backend/ghar_sajag/http_api.py` | `JsonApi` is the local WSGI development adapter. Its `X-Actor-Id` is explicitly not production authentication. There are no ticket, admin, technician, consent or diagnostic routes. |
| Household roles | `code/backend/ghar_sajag/identity.py`, `code/backend/ghar_sajag/model.py` | Existing roles are OWNER/CAREGIVER/INSTALLER, with generic read/manage only. No verified session, staff role, admin directory or technician assignment authority exists. Unknown permissions deny. |
| Diagnostic authorization | `code/backend/ghar_sajag/diagnostic_authorization.py` | The trusted authority is an interface only. It requires current session, Home membership, grant and ownership epoch; there is no production issuer/session adapter or durable grant resolver. |
| Diagnostic projection | `code/backend/ghar_sajag/diagnostics.py` | Class A/B projections remain non-composed. No service consent grant writer or live route exists. |
| Device ownership | `code/backend/ghar_sajag/ownership_registry.py`; migrations `001`, `009`, `010` | Existing database owns Home, Hub and Node enrollment/ownership facts, including Hub installation epoch. This is reusable authority; it does not authenticate caregiver/staff actors or provide a production current-device service API. No competing device registry was added. |
| Persistence | `code/backend/ghar_sajag/database.py`, `code/backend/DATA_MODEL.md`, existing SQL migrations | Migrations are a host SQLite schema contract. The documented production PostgreSQL adapter is not present. Adding durable tickets and atomic grants now would establish a new persistence contract without the production storage adapter required by the task boundary. |
| Caregiver PWA | `code/frontend/public/app.mjs`, `code/frontend/public/index.html`, `code/frontend/public/service-worker.mjs` | The public app is caregiver-only and reads a runtime JSON config containing Home/API location. It has no sign-in/session provider, admin/technician views or in-app service-consent workflow. |
| Token transport | `code/frontend/src/platform/index.mjs` | `ApiClient` accepts an injected token provider, but the public PWA does not compose it and no production provider is available. |
| JSON configuration | `code/config/node_health.json`, `code/config/node_health.schema.json`; generated test `runtime-config.json` | Tracked JSON controls Node health policy only. No service-access configuration exists. The E2E runtime config is generated for a local test and is not a production identity/config authority. |
| Validation | `code/tests/engineering_dashboard`, `code/validation/suites.json`, `code/tests/playwright` | The 54-case registered diagnostic foundation covers nonactive authorization/privacy/trace behavior and GS-116 registry checks. Existing browser suites use the development test adapter; no service-desk role or consent Playwright path exists. |

The approved product flow remains: caregiver ticket creation/tracking; admin
queue, manual or atomic round-robin assignment; assigned-only technician view;
technician Start; caregiver in-app Approve/Deny/Revoke; exact ticket/Home/Hub/
current-Node/ownership-epoch scope; non-sliding 30-minute JSON-configured
default; fresh approval after expiry; no email/SMS OTP. Admin ticket management
does not imply real-Home diagnostic consent. Only an authenticated admin on an
isolated synthetic/test Home may use the consent bypass.

The blocking implementation interfaces are:

1. GS-76/GS-143 verified principal/session and active staff/admin authority,
   including how caregiver membership and staff assignment are resolved.
2. Durable, transactionally consistent ticket, assignment, caregiver decision,
   grant/revocation, ownership-epoch fence, and audit storage behind the actual
   production database adapter.
3. Production PWA session/token composition and server-side route middleware.
4. Trusted current Home/Hub/Node resolver composition and a qualified
   diagnostic exporter. `HubOwnershipRegistry` alone is not an actor authority.

The product decision already fixes the service-consent behavior and 30-minute
default; the blockers above are implementation authorities/adapters, not a
request to choose email/SMS or extend consent duration. Do not activate any
commercial route through `X-Actor-Id` while these interfaces are absent.

## Validation evidence

| Layer | Result | Evidence |
|---|---|---|
| Context preflight | PASS | `bash tools/context/ghar_sajag_context_preflight.sh`; local/canonical context `2026-10-13.001`; dashboard HEAD `ebdec41fde2389a03974a57d30a0118c6adafeeb`. |
| GS-116/GS-130 traceability | PASS | `make feature-coverage-test`; 155 features, 206 modules, 14 physical cases; 20 framework meta-tests. Exact output is in `CONTEXT_RECONCILIATION_VALIDATION_20261013.md`. |
| Registered diagnostic foundation | PASS | `PYTHONPATH=backend:. python3 -m unittest discover -s tests/engineering_dashboard -p 'test_*.py' -v`; 54 tests passed, 12.673 s, exit 0. Includes unknown-action denial, forged actor, cross-Home, expiry/revocation/epoch, original EventKey, privacy allowlists, no-store, bounded cursors, absent routes, selected-stage/failure-propagation/source-fingerprint checks. |
| New service-ticket backend tests | BLOCKED | No service-ticket production source or authenticated persistence boundary exists to test. No service ticket test was counted as PASS. |
| Backend/API and PWA regression | NOT_RUN | No backend route or PWA source was changed; existing `X-Actor-Id` paths cannot qualify the requested authenticated workflow. |
| Service-desk deterministic simulation/backend integration/Playwright | BLOCKED | No production or testable service-desk route/model was added. A UI-only or local-actor PASS would be misleading. |
| Board HIL, motion HIL, physical product E2E | BLOCKED / NOT_RUN | GS-114 NO-GO preserved. No ports, serial, boards, OTA, commissioning or physical operation accessed. |
| Full release gate | NOT_RUN | Not requested. |

GS-116 current source fingerprint for this dashboard source snapshot:
`b3d8ca992f3aef1e7f02245b99bb3addd426a7762c866d3e8686b7660af0521c`.

## Next implementation handoff

Resume when GS-76/GS-143 provide the verified identity/session and active
caregiver/admin/technician authority, and the production storage owner identifies
the durable transaction boundary compatible with the deployed database. Then
implement service tickets/grants against the existing Home/Hub/Node registries,
compose authenticated server routes and PWA sessions, and register production
source tests before running backend, PWA and Playwright regressions. Keep exact
30-minute policy, in-app consent, no OTP, real-Home consent, synthetic-only
admin bypass and all physical/release gates unchanged. GS-122/124/125 remain
open; this report does not authorize production activation or a Jira Done
transition.
