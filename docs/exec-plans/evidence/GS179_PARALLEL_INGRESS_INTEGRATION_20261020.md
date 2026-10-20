# GS-179 / GS-59 parallel ingress integration decision — 2026-10-20

## Outcome

`EXACTLY_NEW_CAPABILITY=NONE`

`ALREADY_IMPLEMENTED=GS-148 durable Hub event API/PostgreSQL COMMITTED path; GS-168 verified TLS credential and current Home/epoch authorization; GS-179 bounded TEST_ONLY application-terminated mTLS listener; authenticated caregiver projection; GS-178 source-linked HOST_SIM Node-to-caregiver E2E.`

`SECURE_RENDER_HUB_INGRESS=UNSUPPORTED_BY_CURRENT_WEB_SERVICE_BOUNDARY`

No new implementation was added. The requested secure composition cannot be
activated without an approved Hub credential/issuer lifecycle, trusted-time
provider, and deployment/network approval. Adding a second identity route,
forwarded-certificate header, or listener with a fabricated clock would weaken
the existing security contract. This is the bounded decision package requested
after the duplication audit; it does not claim a new monitoring capability.

## Scope and checkpoint

- Canonical source: `/home/udaybhan/projects/Ghar_sajag_r1`,
  `feature/r1-commercial-baseline`, fetched HEAD
  `7e41eb8a606ce5e48534b0114e2d902c26523c28`.
- Parallel source: `/home/udaybhan/projects/Ghar_sajag_gs179_parallel`,
  `feature/gs179-ingress-parallel-20261020`, based on that same fetched HEAD.
- Context preflight: PASS on the parallel worktree; context version
  `2026-10-13.001`.
- The canonical checkout's pre-existing untracked files were preserved. No
  Android, onboarding, shared decision, requirements, or validation-registry
  files were changed.
- Jira checked: GS-179 latest comment 11481; GS-59 latest comment 11480.
  Both remain In Progress. GS-59 acceptance is real Hub-to-backend persistence
  with application-level commit/ack behavior.

## Existing implementation reused

The current source already contains the authenticated and durable path:

1. `cloud_client_identity.py` promotes only a verified TLS 1.2 peer with a
   current, active client credential into a typed Hub context, and binds that
   Hub to its current Home and installation epoch.
2. `test_only_mtls_listener.py` terminates TLS in the application, requires a
   client certificate, rejects caller-supplied identity, restricts TEST_ONLY
   identities/Home prefixes, requires startup and per-request backend/time
   readiness, bounds workers/timeouts, and has bounded shutdown.
3. `durable_api.py`, `durable_commit.py`, and `postgres_database.py` reuse the
   GS-148 domain path, current ownership/enrollment checks, EventKey
   idempotency/conflict handling, durable PostgreSQL commit, and exact
   application-level `COMMITTED` response.
4. `connected_lite.py` can project those committed records through the
   authenticated caregiver session and current Home roster. Existing browser
   behavior keeps `HOST_SIM` provenance and stale/unknown monitoring distinct
   from physical Hub health.
5. `gs179-postgres-e2e` and GS-178 tests exercise the existing source-linked
   Node/Hub/backend/caregiver path with TEST_ONLY identities and isolated
   PostgreSQL schemas. GS-137's historical durable-backend work remains owned
   by GS-148; no parallel API/store was introduced.

The latest source-matched evidence is the canonical GS-179 recovery checkpoint
at ancestor commit `7990fc0e6ef4f5b98a3b1a80d7263f6323dc0a66`. It records the
registered isolated PostgreSQL E2E at 46/46, affected browser cases 3/3,
GS-179 lifecycle/security 14/14, validation framework 51/51, and traceability
mapping 22/22 (221 features, 263 source modules, 26 physical cases). The earlier
source-matched GS-179 ingress checkpoint records 40/40 PostgreSQL E2E and the
same framework/mapping PASS. The evidence is reused; it was not rerun here.

One redundant E2E invocation had started before the scope correction arrived.
It was interrupted during the production host build, before tests ran:
`make -C code gs179-postgres-e2e` exit 130. Its temporary PostgreSQL 18.6
cluster used `/tmp/gs179_parallel_runtime`, TLS `verify-full`, and durable
settings; it was cleanly stopped. It did not connect to or mutate the existing
laptop PostgreSQL. No test result is claimed from this interrupted invocation.

## Current hosting compatibility

Read-only Render MCP inspection on 2026-10-20 found:

- `parivar-saathi-lite-staging` is a public Render `web_service`, Free plan,
  Oregon, one instance, `autoDeploy=off`, public ingress `0.0.0.0/0`, and
  Gunicorn starts WSGI on `0.0.0.0:$PORT`.
- Its latest live deploy is `dep-dbb42sjl550s73c9lg80`, commit
  `3c0fec898d5cb2caae662f3dcc6324faaabf6b30`. The service still deploys the
  canonical branch, not this parallel branch.
- `parivar-saathi-lite-db` is an available Free PostgreSQL 18 primary in
  Oregon, currently has an empty external IP allowlist, and is configured to
  expire on 2026-11-16. No database allowlist or service setting was changed.
- Source `wsgi.py` mounts the connected Lite caregiver app; it does not mount
  the GS-148 Hub API or terminate Hub mTLS.

Render's current Web Services documentation states that its load balancer
terminates inbound HTTPS and forwards requests to the web service over HTTP.
Render Private Services expose an internal hostname to Render services, not an
internet-reachable Hub endpoint. Thus the current public WSGI boundary cannot
give `authorize_cloud_tls_context` the verified Hub TLS peer socket. The Free
service's `0.0.0.0/0` access rule is also not a client identity mechanism.
Source: [Render Web Services](https://render.com/docs/web-services),
[Render Private Network](https://render.com/docs/private-network), and
[Render inbound IP rules](https://render.com/docs/inbound-ip-rules).

The current Render arrangement therefore cannot securely host this Hub ingress
by mounting the API into WSGI. A private service alone also cannot accept
direct Hub traffic over the public internet. A separate approved app-controlled
TLS terminator or cryptographically authenticated proxy identity contract
would be required for that platform. Neither is currently configured or
approved.

## Remaining deployment and identity blockers

- GS-D032 locks identity, ownership, epoch, revocation, EventKey and durable
  COMMITTED behavior; it does not approve an issuer, certificate/key custody,
  proof freshness, trusted proxy assertion, or deployment composition.
- `GS40T/1` remains proposed. The available `TestOnlyIssuer` is deliberately
  TEST_ONLY and keeps CA signing authority in memory; it is not a persistent
  deployment issuer. There is no approved physical Hub client credential or
  durable production issuer/registry adapter.
- The listener requires a genuine trusted-time provider. The existing test
  harness clock is a TEST_ONLY fixture; system wall time or an HTTP field is
  not promoted to trusted time by this package.
- The local laptop caregiver/PostgreSQL recovery is not Hub ingress readiness.
  Its network evidence still has Wi-Fi `192.168.1.3`, configured address and
  certificate identity `192.168.1.6`, no Windows TCP 443 listener, and no
  authoritative reservation/lease for `.6`. Existing firewall inspection was
  permission-limited. No Windows networking change is authorized here.
- The Render database's empty external allowlist and Nov 16 expiration do not
  supply an authorized stable database path for a new host.
- Commercial activation, paid hosting, secret installation, service edits,
  deployment, physical Hub credentials, and hardware acceptance remain out of
  scope and NOT_RUN.

## Economical recommendation and owner decision

Keep the existing **₹0 incremental-cost laptop deployment** as the only
near-term TEST_ONLY path; do not purchase a host or change Render. First have
the network owner confirm/reserve `192.168.1.6` for the laptop. Then obtain
separate owner authorization for the exact private Windows forwarding/firewall
change and validate the phone-facing HTTPS route without disabling certificate
validation. In parallel, GS-109/GS-68/GS-148 owners must approve the TEST_ONLY
Hub credential/registry and trusted-time lifecycle needed by the existing
listener. Only after those prerequisites can that existing application-owned
TLS listener be composed with the existing PostgreSQL and caregiver read model
on the same controlled host.

This recommendation is for isolated software/testing only, not a commercially
available or always-on R1 service. If owner wants Render to remain the shared
live backend, the separate secure ingress host and stable, verified database
network path require a later hosting/security approval. No paid option is
proposed or provisioned in this checkpoint.

## Qualification and integration handoff

- `EXACTLY_NEW_CAPABILITY`: none.
- `ALREADY_IMPLEMENTED`: GS-178 HOST_SIM vertical and GS-148 durable/event and
  caregiver contracts, with GS-179 TEST_ONLY listener as above.
- `INGRESS_SECURITY_STATUS`: secure only in the application-terminated
  TEST_ONLY listener; current Render ingress cannot supply authenticated peer
  identity.
- `DURABLE_COMMIT_STATUS`: source-matched TEST_ONLY PostgreSQL `COMMITTED`
  evidence PASS; no new live Render or laptop Hub commit occurred.
- `CAREGIVER_PROJECTION_STATUS`: source-matched authenticated Home projection
  evidence PASS for existing HOST_SIM data; no physical Hub freshness is
  claimed.
- `PHYSICAL_STATUS`: NOT_RUN. Phone real-data and physical C3/S3 qualification
  remain NOT_RUN.
- `FILES_CHANGED`: this evidence file only.
- `CONFLICTS_EXPECTED`: no source conflict; canonical owner must make any later
  deployment/security decision and integrate changes sequentially.
- `CANONICAL_OWNER_REVIEW`: review Render topology and the required external
  owner approvals; do not merge a second ingress/authentication model.
- `RECOMMENDED_INTEGRATION_SEQUENCE`: (1) approve identity/credential and
  trusted-time lifecycle; (2) confirm/reserve `.6` and authorize the narrowly
  scoped local route, or choose a separately approved app-terminated host;
  (3) compose existing listener with existing GS-148 database and caregiver
  projection; (4) execute source-bound TEST_ONLY E2E; (5) pursue physical
  qualification separately.
- `MERGE_READINESS`: evidence-only, safe for review; no source capability is
  proposed for merge.
- `NEXT_ACTION`: owner decision on the existing-laptop route and the
  GS-109/GS-68/GS-148 TEST_ONLY credential/time prerequisites.
