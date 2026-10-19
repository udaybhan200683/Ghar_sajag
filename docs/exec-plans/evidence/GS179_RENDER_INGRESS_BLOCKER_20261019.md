# GS-179 Render ingress and live monitoring boundary — 2026-10-19

## Disposition

`LIVE_STAGING_SOFTWARE_E2E_PASS=NO`

`SECURE_HUB_INGRESS=BLOCKED_ON_CURRENT_RENDER_WEB_SERVICE`

`CAREGIVER_LIVE_HUB_READ_MODEL=NOT_MOUNTED`
`PHONE_REAL_DATA_ACCEPTANCE=NOT_RUN`

This checkpoint verified the actual Render staging route and the canonical
security seam. It made no source, database, service configuration, deployment,
credential, or physical-device changes. GS-179 remains In Progress.

## Canonical source and writer state

- Repository: `/home/udaybhan/projects/Ghar_sajag_r1`
- Branch: `feature/r1-commercial-baseline`
- HEAD and `origin/feature/r1-commercial-baseline`:
  `3c0fec898d5cb2caae662f3dcc6324faaabf6b30`
- Ahead/behind: `0/0`
- Context preflight: PASS, `2026-10-13.001`
- Existing untracked PWA assets, ESP-IDF managed components/configuration,
  Android Zone.Identifier files, and GS-114/C8/GS-40 physical evidence were
  preserved.
- A second Codex console had initially been visible in the same worktree. The
  owner confirmed it was closed; a subsequent process check showed no other
  active command/build writer before documentation changes.

## Render service and ingress evidence

Render inspection identified the existing public Free web service
`parivar-saathi-lite-staging`, linked to the canonical branch with auto-deploy
disabled. Its latest observed live deploy is `dep-dbb42sjl550s73c9lg80` at
`3c0fec898d5cb2caae662f3dcc6324faaabf6b30`. It runs Gunicorn with the WSGI app
bound to `0.0.0.0:$PORT`.

Render documents that its load balancer terminates inbound HTTPS and forwards
requests to a web service over HTTP. The WSGI application therefore cannot
obtain the originating Hub `ssl.SSLSocket` or independently validate that
connection's client certificate. See [Render Web Services — connecting from
the public internet](https://render.com/docs/web-services#connecting-from-the-public-internet).
No trusted, signed client-certificate assertion from an ingress proxy is
configured for this service. A caller-supplied `X-Client-Cert`,
`X-Verified-Hub`, or similar header cannot establish identity.

Read-only observations against the deployed service:

| Request | Result | Meaning |
|---|---|---|
| `GET /v1/homes/gs179-test-probe/snapshot` | HTTP 404, `route_not_found` | The deployed WSGI process does not mount the GS-148 `/v1` API. |
| `GET /lite/v1/me` without a session | HTTP 403, `not_authorized` | Existing Lite session boundary remains active. |
| `GET /readyz` | The first client request timed out; subsequent Render application logs show HTTP 200 with 16–330 ms duration | The initial timeout is inconclusive and is not classified as a database failure. |

Render reports the existing PostgreSQL service as available. A read-only SQL
inspection through the Render connector was refused because the database's
external IP allowlist is empty. No allowlist or database setting was changed,
and no database schema/data claim is made from that attempted query.

## Source boundary

- `code/parivar_saathi_android_app/server/connected_lite.py` explicitly mounts
  only the synthetic `/lite/v1` service. Its persisted `lite_runs` are scenario
  records and cannot be repurposed as Hub events.
- `code/parivar_saathi_android_app/server/wsgi.py` constructs `connected_lite`;
  it does not mount `ghar_sajag.http_api.JsonApi` or a Hub TLS middleware.
- `code/backend/ghar_sajag/durable_api.py` requires a trusted server-side
  authorizer and says it does not authenticate Hub requests.
- `code/backend/ghar_sajag/cloud_client_identity.py` requires a server-side,
  certificate-required TLS 1.2 `SSLSocket`, a verified RSA-3072 ClientAuth
  certificate, trusted time, active credential registry state, and current
  ownership registry state before constructing Hub context.
- `code/backend/ghar_sajag/http_api.py` accepts durable event/NodeHealth/rule
  updates only with the corresponding verified Hub context. No HTTP request
  header creates this typed context.

These seams preserve the intended GS-D032 behavior, but the live Render process
cannot currently supply the required transport-authenticated context. Mounting
the API behind its current public web ingress or deriving Hub identity from a
request header would bypass that trust boundary. No such change was made.

## Smallest safe deployment path

Recommended to preserve the existing trust contract: use one isolated,
internet-reachable TEST_ONLY backend endpoint where the application-owned TLS
listener (or an explicitly trusted TLS-passthrough ingress) requires and
validates the Hub client certificate. The handler then calls the existing
`authorize_cloud_tls_context`, current GS-168/ownership/enrollment checks, and
the existing durable commit API before returning the exact COMMITTED receipt.
The caregiver API may remain on Render only after it reads the same committed
backend records through a separately authenticated, access-controlled
backend connection. The endpoint must use TEST_ONLY roots and Homes, retain
server certificate/hostname verification, and keep revocation and current
Home/epoch checks inside the backend transaction.

This endpoint/host and database connection path do not currently exist in the
verified deployment. No new paid resource, DNS name, network allowlist, trust
root, or service was created. An application-level signed-request protocol
could avoid dependence on a forwarded TLS peer, but it would be a new
authentication/proof contract; it remains unapproved and must not be silently
substituted for the present TLS identity seam.

## Validation and remaining work

- Context preflight: PASS.
- Canonical Git state and remote equality: PASS.
- Read-only Render service/deploy inspection: PASS.
- Render public-route check: observed 404 for GS-148 route and 403 for
  unauthenticated Lite session.
- Render request logs: health checks returned HTTP 200 after a worker restart;
  the client-side first timeout remains inconclusive.
- Render SQL connector: BLOCKED by the database's empty external IP allowlist;
  no setting was changed.
- Source tests, builds, Android workflow, database writes, staging deployment,
  physical cases: NOT_RUN in this checkpoint because no code/configuration
  changed and the authenticated ingress prerequisite is absent.

The already recorded GS-178 host E2E (27/27) and GS-177 Android CI success are
not repeated or promoted to live staging evidence. No source-linked Node
EventKey, Hub COMMITTED receipt, PostgreSQL row, or Android-visible monitoring
record was created. Existing Home monitoring must remain disconnected/unknown.

### Exact next prerequisite

Provide an already-authorized direct mTLS-capable isolated backend ingress/host
with a network path to the intended PostgreSQL instance, or approve a new
cryptographic request-authentication contract for security review. After that
prerequisite, mount the existing durable API behind that verified identity
boundary, connect the caregiver read model to the same committed records, run
the source-linked Node→Hub→backend→caregiver software scenario, then build the
current Android APK and manually deploy only after the secure integration gate
passes. Hardware remains excluded.
