# GS-179 / GS-59 continuous Hub ingress audit — 2026-10-20

## Baseline

- Canonical branch: `feature/r1-commercial-baseline`
- Source checkpoint: `29cdc43f569a9a512e68e073cb85aa3ebc0eebbd`
- Remote: `origin/feature/r1-commercial-baseline`, equal at audit start.
- Context preflight: PASS (`2026-10-13.001`).
- No tracked modifications at audit start; pre-existing untracked Android/PWA,
  ESP-IDF and hardware evidence was preserved.
- No second active canonical writer was observed.
- Filesystem is read-write with available space; connectivity-only `git fsck`
  reported dangling objects but no missing/corrupt objects and exit 0.

## Existing-versus-missing matrix

| Boundary | Existing implementation/evidence | Remaining gap | Safe execution in this task |
|---|---|---|---|
| Hub mTLS identity | `TestOnlyMtlsListener` terminates TLS 1.2 in-process; `authorize_cloud_tls_context` derives identity only from the verified peer and checks certificate purpose, current GS-168 registry state, trusted time, and active ownership. Existing GS-178 security tests cover spoofed headers, stale Home/enrollment and conflicting EventKey content. | Listener is an injectable TEST_ONLY component; it is not composed into the laptop caregiver unit. | Keep it disabled unless an explicitly configured TEST_ONLY composition supplies TLS material, current identity/ownership, trusted time and backend readiness. No new issuer or identity source is introduced. |
| Durable ingestion | `open_postgres_durable_event_api` reuses GS-148 durable commits, Hub ownership, NodeHealth, Hub-decision persistence and caregiver query model. The adapter requires verified TLS for remote PostgreSQL, bounded connect, `fsync` and synchronous commit. | No distinct long-running Hub ingress is composed into the laptop user service. | Do not alter the live laptop service/database. Preserve the listener as an injectable, long-running TEST_ONLY component and validate lifecycle in isolated PostgreSQL schemas. |
| Credential registry | GS-168 `TestOnlyIssuer` stores public credential metadata in its existing SQLite registry; the CA signing key is deliberately ephemeral/in-memory. | No physical Hub credential, durable CA custody, or current registered enrollment is configured for the laptop service. | Do not create persistent issuer authority or seed the laptop database. Real target activation remains blocked. |
| Trusted time | Listener accepts an injected trusted-time provider and rechecks certificate validity against its returned aware UTC value per request. GS-178 host harness provides a TEST_ONLY clock. | The laptop caregiver service does not configure a Hub-ingress trusted-time provider. | Fail closed if readiness or trusted time is absent; do not infer a Hub identity or configure production time. |
| Caregiver read model | GS-148 caregiver projection reads the same durable PostgreSQL records. GS-179 local evidence already demonstrates one HOST_SIM EventKey through COMMITTED and caregiver API, restart retention, stale UNKNOWN and authenticated refresh. | No real C3/S3 source event has been received. | Reuse prior source-linked evidence; run affected listener/PostgreSQL tests only. Do not add rows to the live laptop DB or claim physical behavior. |
| Laptop exposure | Existing local caregiver service and LAN forwarding are separately configured; latest evidence says Windows forwarding refuses TCP 443. | No authorized working Hub-facing network route or client credential is active. | No listener start, port-forward/firewall/IP/certificate changes in this task. |

## Scope and test boundary

The listener hardening is a code-level robustness/fail-closed correction to the
already registered `gs179-postgres-e2e` validation inputs. It does not create a
new protocol, issuer, event store, caregiver UI, production profile, or service
deployment. All new runtime tests use the existing GS-168/GS-178 TEST_ONLY
fixtures and isolated database resources. Existing laptop accounts, committed
events, credentials, Windows networking, physical fixtures and production
services remain untouched.

## Implemented correction and validation — 2026-10-20

`TestOnlyMtlsListener` now requires an explicit backend-readiness callback and
checks it, together with an aware trusted-time value, before creating its
socket. It repeats backend and time readiness checks for every request. The
listener defaults to loopback; a private IPv4 address requires an explicit
TEST_ONLY caller opt-in, while wildcard, public, reserved and IPv6 binds are
rejected. Accepted connections are capped (default 8, maximum 32), and TLS
handshakes run in those bounded workers with the configured socket timeout;
the accept loop remains available to reject excess peers. Shutdown waits a
bounded time for workers to drain. Closed instances cannot be restarted. TLS
peer certificate, ownership/epoch, GS-168 registry and existing GS-148
transaction checks are unchanged.

Permanent tests were added to the already registered `gs179-postgres-e2e`
suite. They exercise incomplete TLS handshake timeout and saturation before
HTTP dispatch, worker recovery, graceful drain, closed restart refusal,
mandatory startup readiness, bind and port bounds, and request-time backend/time
loss. They use the existing GS-178 ephemeral TEST_ONLY identity/time fixtures
and isolated PostgreSQL; no fixture uses a persistent laptop account, the live
laptop database, a physical Hub, or production trust.

Results on the changed source:

- `make -C code gs179-postgres-e2e`: PASS, 40/40 tests; output ended
  `GS179 POSTGRES E2E PASS tests=40 physical=NOT_RUN`.
- `make -C code validation-framework-test`: PASS, 51/51.
- `make -C code feature-coverage-test`: PASS, 221 features, 263 modules,
  26 physical cases; mapping tests 22/22.
- `python3 -m py_compile code/backend/ghar_sajag/test_only_mtls_listener.py
  code/tests/integration/test_gs178_security.py`: PASS.
- `git diff --check`: PASS.

The PostgreSQL test used an isolated TLS-enabled temporary cluster and isolated
test schema. Its server was stopped after the test. Temporary task-created
artifacts were under a private mode-0700 `/tmp/gs179-isolated-pg.*` directory;
they contain test-only material and are not committed. No broad cleanup was
run.

The persistent laptop caregiver service was inspected but not restarted. Its
user unit was stopped/failed: `ExecStartPost`'s Windows port-forward startup
returned 1, after which the unit's `ExecStopPost` stopped PostgreSQL. No
Windows networking, IP, forwarding, firewall, caregiver data, private account,
credentials or persistent database was changed. Therefore the newly hardened
listener itself has source-linked host/PostgreSQL evidence, but continuous
laptop ingress is not operationally deployed or live-tested.

Physical C3/S3 acceptance, physical Hub identity/enrollment, production CA/key
custody, live persistent mTLS ingress and official GS-40/GS-59/GS-117/GS-121
acceptance remain NOT_RUN/BLOCKED. The existing aggregate validation failures
for Hub migration `clean migration commits` and required P0
`product_status=PARTIAL` remain unchanged.

## Outcome

`CONTINUOUS_INGRESS_READINESS=PARTIAL`: the existing application-terminated
TEST_ONLY mTLS and durable event path is hardened and source-linked host/Postgres
validated. A persistent, enrolled Hub-facing service is not deployed; laptop
network forwarding, server/client trust material, current Hub enrollment and
trusted-time configuration are not active. The next required qualification
step is to provide existing approved TEST_ONLY artifacts and an authorized
route, then start only on an approved private interface and validate real
S3-originated HTTPS/mTLS ingestion. Physical and production paths remain
blocked separately.
