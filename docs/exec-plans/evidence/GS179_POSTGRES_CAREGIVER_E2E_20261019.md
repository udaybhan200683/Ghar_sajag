# GS-179 PostgreSQL and caregiver E2E checkpoint — 2026-10-19

## Result

The isolated host software path now runs the real GS-178 Node event-processing
binary through the existing verified Hub TLS identity and GS-148 API, commits
the exact Node EventKey to a local PostgreSQL database, and reads that committed
record through the caregiver API and shared browser app. The validation stage is
registered as `gs179-postgres-e2e`; its final registered execution passed 34/34
tests.

This is `HOST_SIM_PASS`. It is not evidence of a deployed service, an Android
handset, an ESP32 target, real PIR sensing, commercial credentials, or physical
qualification. The current Render deployment was not changed or redeployed.
`LIVE_STAGING_SOFTWARE_E2E_PASS=NO`.

## Implemented path

The application-controlled listener in
`code/backend/ghar_sajag/test_only_mtls_listener.py` terminates TLS 1.2 in the
application process, requires a verified client certificate, and passes only
the verified TLS peer connection to the existing GS-68 credential and current
ownership checks. The Hub identity and Home are taken from that verified
certificate/registry context; a caller-supplied certificate header cannot
create the identity. It scopes this adapter to explicit `GS179_TEST_ONLY`
configuration and the `test-hub-` / `gs177-test-` namespaces.

`code/backend/ghar_sajag/postgres_database.py` adapts the existing GS-148 durable
event, ownership, NodeHealth, incident, and Hub-decision domain stores to
PostgreSQL. The remote connection path requires `sslmode=verify-full`; plaintext
is accepted only when the caller explicitly selects local test mode. Durable
commit readiness is gated by PostgreSQL `fsync` and `synchronous_commit`.
`open_postgres_durable_event_api()` reuses the existing authenticated API,
ownership registry and EventKey/COMMITTED semantics rather than defining a
parallel ingestion contract.

The opt-in `GS179_TEST_ONLY_MONITORING=1` composition in
`code/parivar_saathi_android_app/server/connected_lite.py` reads this durable
projection for an already authenticated, current TEST_ONLY caregiver session.
Events and Hub decisions render through the existing Home, Activity, Devices,
Incidents, Routines and Reports views. Synthetic scenario runs remain separate
and retain their simulation provenance. Missing, stale or uncovered source data
does not imply that the Home is connected or that the resident is inactive.

## Validation evidence

The registered gate was run against a local PostgreSQL 18.6 instance bound to a
private Unix socket. Each product-stack test received a random schema; both the
caregiver session/account database and the GS-148 durable monitoring database
used PostgreSQL in the final run. The fixture rejects non-local database hosts
and drops only its own schema. Ephemeral TEST_ONLY certificates and credentials
were used. No staging, production, board, USB, serial, phone, eFuse, or customer
identity was accessed.

Command:

```sh
GS179_TEST_POSTGRES_DSN='host=/tmp/gs179-postgres-socket port=55432 dbname=postgres user=udaybhan' \
LD_LIBRARY_PATH=/tmp/gs179-pg-packages/root/usr/lib/x86_64-linux-gnu \
PYTHONPATH=/tmp/gs179-python-deps \
python3 code/validation/component_gate.py --suite postgres-integration
```

Final source-bound rerun: `PASS gs179-postgres-e2e exit=0 count=34`; stage
runtime 202.324 seconds (202.999 seconds total gate runtime); physical status
`NOT_RUN`; release approval `false`. Its ignored local report is
`code/evidence/validation_framework/postgres-integration-1792435470522033688/report.json`;
the stage log SHA-256 is
`27af77200aa8fc841660aff65853ae27a83472c6ac368ed97226175083cec299`, the host
Node/Hub executable SHA-256 is
`3acef9fb780b39c5c86b9f1ca1cef4ab3bbe7fcfd73a7894211f2f08b32bf595`, and the
source fingerprint is
`366a503df78677b4ce3d6ff13981cfce822afce705f59c444b81ae8d1d54413e`. The
report binds the run to base commit `4fbb8afbfb95a128fa942ac260939601af817411`
plus the declared tracked inputs and records `source_unchanged=true` during
execution. The exact Home browser scenario passed 17 assertions, including
authenticated NodeHealth projecting Home `COVERED` / source `CURRENT`, retained
Node-origin EventKeys before and after reload, and the explicit
`NODE_ORIGIN_HOST_SIM` provenance label. Generated reports remain in the local
ignored evidence directory; this redacted summary is committed.

The current-caregiver authorization bridge also requires the authenticated
Lite account ID to be an active entry in the durable `household_caregivers`
roster. Effective product role is the least privilege of the Lite session and
durable roster: a TEST_ONLY `ADMIN` account whose durable role is `PRIMARY`
remains a product `CAREGIVER`; an unrostered account is rejected. The final
34-test run includes this negative assertion.

The affected baseline SQLite stack was also re-run after moving the Hub transport
behind the listener adapter:

```sh
make -C code gs178-software-e2e
```

Result: PASS, all 29 GS-178 Node/Hub security, outage/retry, Home ownership,
NodeHealth, rules and caregiver-browser tests.

The 29 cases cover signed/encrypted configuration and signed-time rejection,
credential generation/revocation and authority lease checks; verified mTLS
peer identity, spoofed-header rejection, Home/epoch and enrollment fencing;
Node event processing, exact EventKey and durable `COMMITTED` correlation;
duplicate/lost receipt, backend restart/retry and delayed chronology; NodeHealth
ONLINE, silent OFFLINE, source-stale UNKNOWN and authenticated recovery; morning
and night decisions, Hub-decision idempotency/revocation/transfer; caregiver
Home isolation, event/routine rendering, actions and reload; and explicit
simulation-versus-product provenance.

The 34 cases cover the existing 29 Node/Hub/security/caregiver cases plus five
PostgreSQL transport and durability boundary negatives: remote databases reject
unverified TLS modes, local plaintext requires explicit test mode, the local
override cannot relax a remote connection, unsafe server durability settings
reject migration before SQL executes, and the isolated test database refuses
non-local hosts.

The exact EventKey regression additionally verifies equality among the
Node-originated EventKey, HTTP `COMMITTED` receipt, PostgreSQL durable commit and
stored event, caregiver API projection, and the browser's rendered `data-event-key`
before and after reload. A conflicting same-key payload is rejected; the
original event remains exactly-once across Hub/backend restart. The retry after
lost receipt and ownership/revocation negatives are included in the registered
34-test execution.

Focused caregiver browser command:

```sh
make -C code pwa-68-browser-test
```

Prior focused browser suite result: PASS, 3 tests / 92 registered assertions.
The final PostgreSQL E2E browser run separately passed 17 assertions in the
source-linked caregiver scenario. The Playwright browser came from the installed
local test browser; the repository and device firmware were not changed for
this.

Traceability mapping command:

```sh
make -C code feature-coverage-test
```

Result: PASS, 22 mapping assertions; current master trace maps 216 features,
257 source modules and 25 physical cases. New feature `GS179-PG-01` is registered
as partial and `SOFTWARE_ONLY` for this local test adapter; live ingress and
physical acceptance remain unqualified.

Additional source checks passed:

```sh
PYTHONPATH=code python3 code/tests/engineering_dashboard/test_registration.py
python3 -m py_compile code/backend/ghar_sajag/postgres_database.py code/backend/ghar_sajag/test_only_mtls_listener.py code/backend/ghar_sajag/durable_api.py code/backend/ghar_sajag/durable_commit.py code/backend/ghar_sajag/caregiver_product.py code/parivar_saathi_android_app/server/connected_lite.py code/tests/integration/run_gs179_postgres_e2e.py code/tests/support/gs179_postgres_test_db.py
node --check code/tools/sim/pwa/connected_lite.mjs
node --check code/tests/support/gs178_browser.cjs
git diff --check
```

The registry unit test ran 6/6. Python compilation, both JavaScript syntax
checks, and whitespace validation exited 0.

The earlier aggregate `make validation-backend` and `make validation-pwa` runs
remain FAIL and are not overridden by the focused PASS results. Recorded causes:
the P0 aggregate scenario asserts correctly but required `product_status=PARTIAL`
keeps the gate failed; the legacy diagnostic runner integrity stage timed out;
and the old offline-browser stage could not locate system Chrome on its first
environment. The new focused browser and registered PostgreSQL stage passed
with an explicit test-browser path. These broader existing gates need their
own source-scoped triage; no threshold or product status was changed.

## Deployment boundary and minimum option

The current Render staging ingress still terminates public TLS before WSGI, so
the app cannot obtain the authenticated Hub client certificate. The app does
not accept forwarded certificate headers, and none were added. The prior
Render/database inspection is documented in
[`GS179_RENDER_INGRESS_BLOCKER_20261019.md`](GS179_RENDER_INGRESS_BLOCKER_20261019.md);
its live finding is unchanged. No Render service, database allowlist, deployment,
auto-deploy policy, or billing was modified.

The smallest evaluated topology that preserves the existing authentication
contract is one app-controlled Linux VM: terminate device mTLS in the same
process that creates `VerifiedHubContext`; serve the isolated caregiver API/PWA
there (or connect an already-authorized caregiver service over an authenticated
private channel); and connect to the existing PostgreSQL using TLS with hostname
verification. If the existing Render PostgreSQL is retained, the VM needs a
stable egress IPv4 explicitly added to the database allowlist. The current
`verify-full` requirement also needs validated CA/hostname material for the
actual database endpoint. Neither change has been authorized or performed.

Indicative, not purchased, infrastructure pricing checked 2026-10-19: Hetzner
CPX22 provides 2 vCPU, 4 GB RAM and 80 GB NVMe. The 15 June 2026 price table
lists €19.49/month in Germany/Finland or $22.99/month in the US, excluding
IPv4; the static IPv4 adds €0.50/month or $0.60/month, respectively (all before
VAT). That yields €19.99/month EU or $23.59/month US before VAT and optional
backup/domain/monitoring costs. Hetzner's current product page marked CPX22
unavailable in the displayed EU locations when checked, so these figures are
not an orderable quote; availability and region suitability must be checked
before any purchase. See the [official price table](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/),
[primary IPv4 pricing](https://docs.hetzner.com/cloud/servers/primary-ips/overview/),
and [CPX22 specifications and availability](https://www.hetzner.com/cloud/regular-performance/).

A single VM is a small pilot topology, not a high-availability service. It needs
a named operator for patching, backups, monitoring, firewall rules, certificate
rotation and recovery. Creating the VM, assigning DNS/certificates, changing the
Render database allowlist, injecting secrets or deploying the app requires
separate infrastructure/account authorization. No alternative signed-request
scheme is implemented or proposed as approved.

## Status and next action

- Local authenticated PostgreSQL host integration: **PASS**.
- Actual current Render mTLS ingestion and live database commit: **BLOCKED** by
  the already documented TLS termination / absent trusted peer identity and
  database network path.
- Live staging software E2E: **NOT PASS**.
- Android CI APK source/signing verification and owner-phone real-data behavior:
  **NOT RUN in this checkpoint**.
- Physical C3/S3 and real sensor qualification: **NOT RUN**.
- GS-179 remains **In Progress**; GS-148 and GS-177 remain in their existing
  statuses. Product status remains `PARTIAL`.

Next: authorize a suitable account/region and a small mTLS-capable host, then
authorize the specific endpoint DNS/TLS material, fixed-egress database
allowlist addition, isolated TEST_ONLY secret provisioning and deployment. Keep
the existing Render staging service untouched until a safe end-to-end route and
recovery plan are approved.
