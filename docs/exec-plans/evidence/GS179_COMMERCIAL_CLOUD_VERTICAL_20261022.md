# GS-179 commercial cloud vertical checkpoint — 2026-10-22

## Scope and result

This checkpoint follows GS-179 owner comment 11532 and GS-117 owner comment
11533. Both select a customer-style outbound Hub-to-cloud path; the physical
acceptance path must not depend on Windows/WSL2, a static customer IP, router
forwarding, or a developer-started listener.

The canonical source already has a source-linked isolated TEST_ONLY event
vertical. The commercial cloud path does not. No safe production listener or
caregiver read path can be enabled from the current contracts: GS-D032 leaves
production credential/proof, deployment middleware and database composition
open and explicitly says not to invent those mechanisms. GS-68/109/172 still
own device trust/authority and GS-76/143 still own production caregiver
authentication/membership. TEST_ONLY source, identity and Home fixtures cannot
be promoted to production.

No source, cloud resource, live configuration, network, credential, customer
data or physical device was changed. This is not live-cloud, hardware or
commercial acceptance.

## Jira and source checkpoint

- Jira inventory: 173 issues, refreshed in Rank order. GS-114 Rank 31 remains
  In Progress; GS-117 Rank 52 remains In Progress; GS-60 Rank 60 remains To Do;
  GS-179 Rank 173 remains In Progress. No Rank changed.
- Related owners remain open: GS-40 (32), GS-177 (34), GS-148 (35), GS-109
  (57), GS-58 (58), GS-59 (59), GS-68 (81), GS-76 (82), GS-143 (63), GS-172
  (167), GS-178 (172), GS-116 (87), GS-130 (89), GS-121 (53). GS-114's
  higher-ranked qualification is not displaced.
- Worktree: `/home/udaybhan/projects/Ghar_sajag_r1`, branch
  `feature/r1-commercial-baseline`, starting HEAD
  `1f6b72b3fac0a4ddf5b58a78d42ed430ffb124e4`; live origin matched. Tracked
  files were clean. The existing 301 untracked entries and 174,520 ignored
  paths were preserved.
- Context preflight: PASS at `2026-10-13.001`; no nested `code/AGENTS.md`
  files were present. No additional writer or worktree was used.

## Reuse matrix

| EXISTING | REUSE | GENUINE GAP | MINIMUM REQUIRED CHANGE | JIRA_OWNER |
|---|---|---|---|---|
| C3 PIR/EventKey and authenticated Node transport; S3 admission, durable journal and CloudSync serializer/worker exist. The production S3 composition uses `UnprovisionedS3CloudTrust` and fails closed. | Existing C3/S3 runtime and CloudSync; no protocol replacement. | Current production Hub identity/time/endpoint is not provisioned or authorized. | Keep production CloudSync fail-closed until GS-68/109/172 approve and supply the authority, identity, trusted-time and endpoint inputs. | GS-40, GS-58, GS-68, GS-109, GS-148, GS-172 |
| GS-179 `start_gs179_test_only_hub_ingress`, application-terminated TLS 1.2 listener, verified peer identity, registry/authority checks, readiness and bounded lifecycle. | Reuse this only for isolated TEST_ONLY software validation. | There is no commercial listener profile or approved production identity/registry adapter. The existing listener expressly requires `GS179_TEST_ONLY`. | Do not remove its profile checks. GS-68/109/172 must approve the production identity/verifier contract before a separate commercial runtime is implemented. | GS-59, GS-68, GS-109, GS-172, GS-179 |
| GS-148 PostgreSQL transactional EventKey/NodeHealth/decision APIs and COMMITTED semantics. | One authoritative PostgreSQL database; exact retries and caregiver projection remain unchanged. | The live hosted app does not mount the durable API or a same-DB authorized commercial caregiver read path. | After identity and human-auth contracts are approved, compose existing APIs against one authorized database; no second store. | GS-148, GS-179 |
| Render caregiver WSGI/Connected Lite app, existing Home UI/API and current PostgreSQL resource. | Keep the existing shared caregiver UI and API contract where production authorization permits. | Live Render deployment is a Free caregiver-only service, TLS terminates before WSGI, and its current WSGI app does not expose verified Hub TLS peer identity or mount commercial durable monitoring. The Render database is also Free in `render.yaml`. | Keep it as staging only; do not infer mTLS from TLS or accept certificate/Hub headers. | GS-76, GS-143, GS-177, GS-179 |
| Existing GS-177 APK workflow, current Render origin and shared Android Home/Activity UI. | Reuse the app and workflow after the approved production origin and caregiver auth exist. | Current APK is staging-origin testing build; there is no source EventKey from a real Hub to display and no authorized production Home session. | Build with the approved cloud origin and owner-controlled signer after domain/auth approval; verify installation and same-event visibility on the phone. | GS-76, GS-117, GS-143, GS-177, GS-60 |
| GS-179 isolated runtime process E2E and GS-178 Node-origin HOST_SIM path. | Reuse existing PostgreSQL fixtures and event provenance evidence; do not rerun without source changes. | These tests are explicitly TEST_ONLY/HOST_SIM and do not qualify public cloud ingress or physical devices. | Keep them as software regression evidence; add commercial runtime E2E only after its approved identity boundary exists. | GS-116, GS-130, GS-178, GS-179 |

## Cloud service inspection and topology recommendation

Render service `parivar-saathi-lite-staging` (`srv-db9p25m1egvs7383iss0`) is
still live on deployment `dep-dbb42sjl550s73c9lg80`, commit
`3c0fec898d5cb2caae662f3dcc6324faaabf6b30`, on the Free plan with auto-deploy
off. Its current public HTTPS edge terminates TLS and forwards HTTP to WSGI;
the application cannot receive the Hub's verified TLS peer socket. Render's
documentation also says Free services/databases are for preview/testing, not
production. This option therefore cannot be made into the Hub identity boundary
by changing WSGI headers. A proxy/gateway identity assertion would be a new
security contract and is not approved.

**Selected engineering topology recommendation (not yet provisioned or
approved for spend):** Option B, one small Linux cloud host in AWS Lightsail
Mumbai for the existing caregiver WSGI process and a separate app-owned Hub
TLS ingress process, plus one private managed PostgreSQL database in the same
region. A small HAProxy TCP/SNI frontend would pass the original TLS bytes to
the correct application TLS endpoint (`hub.<approved-domain>` for client
mTLS; `app.<approved-domain>` for caregiver HTTPS); it would not terminate or
assert Hub identity. Both processes use the same database. Hub and phone both
use outbound/inbound standard port 443; the database has no public listener.
The caregiver app and Hub ingress remain separate OS processes with normal
service supervision, bounded startup/shutdown and no extra event worker.

This topology reuses the current application-terminated identity seam and
avoids a proxy-supplied identity header or new backend. It is the simplest
path identified that can keep Hub peer-certificate verification inside the
application while serving ordinary caregiver HTTPS under another hostname.
It remains a topology recommendation only: the present GS-179 listener is
TEST_ONLY and cannot be deployed as this commercial ingress. Production
credential/authority contracts, caregiver authentication, domain, paid
resources and live deployment still require their owners' approval.

Indicative current AWS list-price baseline (USD, before taxes/domain/manual
snapshots/overage): Lightsail Linux 2-vCPU/2-GB/60-GB host at $12/month plus
Lightsail PostgreSQL 2-GB Standard at $30/month, approximately **$42/month**.
The 2-GB database plan is encrypted; Lightsail documents PostgreSQL 16 support,
automatic backups with a 7-day point-in-time restore window, and same-region
database connectivity. A 2-GB High Availability database is $60/month, taking
this baseline to about $72/month; it does not make the single app host highly
available. Mumbai's bundled instance transfer allowance is lower than many
other Lightsail regions. These are budget estimates, not a capacity or uptime
qualification. The single app host remains a cloud-availability failure point;
the Hub's local durable journal/retry continues to protect events during a
cloud outage. Any stronger cloud uptime commitment requires a later scoped
availability and cost decision.

Provider references checked 2026-10-22:

- [Render public web-service TLS boundary](https://render.com/docs/web-services#connecting-from-the-public-internet)
- [Render Free service/database limitations](https://render.com/docs/free)
- [Lightsail instance bundles and monthly pricing](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-bundles.html)
- [Lightsail managed database pricing](https://aws.amazon.com/lightsail/pricing/)
- [Lightsail supported PostgreSQL versions](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-choosing-a-database.html)
- [Lightsail managed database backups and same-region behavior](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-faq-databases.html)

No provider account, resource, domain, DNS record, certificate, allowlist,
network route, deployment or data migration was created or changed.

## Runtime / APK status

The same original EventKey can be demonstrated only in the existing isolated
GS-178 HOST_SIM → GS-179 TEST_ONLY runtime → PostgreSQL COMMITTED → authorized
TEST_ONLY caregiver API scenario. The last registered GS-179 suite result is
51/51 PASS at the runtime source checkpoint; the runtime/validation evidence
also records framework 51/51 and feature mapping 22/22. That evidence remains
reusable because this checkpoint changed no source or tests. It is not a
commercial or physical result.

Render's latest observed deploy remains `3c0fec898d5cb2caae662f3dcc6324faaabf6b30`.
The latest identified successful Android workflow is `39721322469` (source
`2a1b5ffa9a52d4ad81726d8d99ba95773ff03085`), package
`in.gharsajag.caregiver`, version `0.4.0-connected-lite-staging`, origin
`https://parivar-saathi-lite-staging.onrender.com`, APK SHA-256
`c42fd1817f85eae52f9e7df3cb016a173ff0275b20307a2274b48a07042bab64`.
The owner reports the APK installed; this workspace did not verify the
installed package/signer or observe a real event. No original physical EventKey,
production COMMITTED receipt or same-event phone read exists.

## Exact blockers and next action

1. GS-68/109/172 must approve and provide the production Hub credential and
   proof/verifier lifecycle, current Hub/Home/epoch and Node-enrollment source,
   revocation/rotation behavior, trusted-time source and cloud endpoint trust.
   This is required by the unresolved mechanisms recorded under GS-D032; do not
   turn the TEST_ONLY issuer or listener into production.
2. GS-76/143 must qualify production caregiver identity, session/revocation and
   Home membership/role authorization so Android reads only its authorized
   Home.
3. The owner must approve the exact paid Lightsail host/database plan and
   approved domain/DNS target before resource creation, DNS or deployment.
4. After those gates, implement the smallest commercial listener/runtime and
   same-PostgreSQL caregiver composition using the approved providers; run a
   commercial-configured source-linked E2E, then build the existing APK against
   that origin with the approved signer.
5. GS-117/GS-60 physical operation remains separately gated on current C3/S3
   image/identity, safe observer, Home/epoch/enrollment/trusted time, and
   explicit fixture/operator approval. No hardware access is authorized here.

Immediate next Jira action: **GS-172 / GS-68 / GS-109 owner decision on the
production Hub identity/credential and authority contract**, while GS-76/143
complete the caregiver authorization seam. Until then GS-179 remains In
Progress; persistent cloud ingress is NOT_CONFIGURED; GS-117 and GS-60 remain
open. No source or test was changed or rerun in this checkpoint.
