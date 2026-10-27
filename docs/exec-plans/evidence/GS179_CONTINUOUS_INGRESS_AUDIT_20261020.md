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

## Canonical fast-forward and resumed GS-179 checkpoint — 2026-10-21

The user-authorized fast-forward was performed in the canonical worktree only.
The verified starting commit was `2b8dee5dc0494a06bcc34210cd08bdc63e6339b0`;
`origin/feature/r1-commercial-baseline` was exactly
`ef352611528ea8ddd302229ef8371bd7528a8c61` and the starting commit was its
ancestor. The incoming 25 changed paths were checked against existing
untracked and ignored paths, including path ancestry and filesystem types;
there were no collisions. The tracked worktree was clean. `git merge --ff-only
origin/feature/r1-commercial-baseline` advanced the branch to the approved
commit. Before and after counts remained 301 untracked and 174,433 ignored
paths; no cleanup or other worktree operation was performed. Context preflight
passed before and after the fast-forward (`2026-10-13.001`).

The fast-forward changed no GS-179 runtime implementation. Current-source
inspection reconfirmed this reuse/gap matrix:

| Component | Classification | Evidence and minimum change |
|---|---|---|
| Application-terminated TEST_ONLY TLS 1.2/mTLS listener | `ALREADY_IMPLEMENTED / REUSE` | `test_only_mtls_listener.py` already enforces verified TLS peer identity, certificate purpose/validity, registry and ownership checks, trusted-time/backend readiness, bounded request handling, and bounded shutdown. |
| GS-148 durable PostgreSQL event API | `ALREADY_IMPLEMENTED / REUSE` | `durable_api.py` and its PostgreSQL commit path already perform ownership-checked durable event and NodeHealth processing and expose the caregiver query projection. COMMITTED and exact-body retry contracts remain unchanged. |
| GS-179 caregiver projection and Android-facing API | `ALREADY_IMPLEMENTED / REUSE` | `connected_lite.py` already composes the durable API with the Home-authorized caregiver view. No duplicate store, API, or UI was introduced. |
| Laptop TEST_ONLY Hub ingress runtime composition | `GENUINE_GAP / BLOCKED` | `gs179-laptop-server.sh` still starts caregiver Gunicorn/WSGI and reports `HUB_INGRESS_READY=NOT_CONFIGURED`; it does not compose the listener. It also lacks approved Hub credential-registry/artifact, trusted-time, current Hub/Home/epoch authority, and authorized route configuration. |
| Runtime code/configuration change | `MINIMUM_REQUIRED_CHANGE: none safely implementable with current approved inputs` | Do not invent a persistent issuer, client identity, trusted clock, authority binding, or network route. Keep ingress default-disabled and report the exact configuration/trust gate. No source code or runtime configuration changed in this checkpoint. |

### Focused validation on `ef352611528ea8ddd302229ef8371bd7528a8c61`

The existing GS-179 test was first attempted without the laptop's existing
private Python dependency paths: it exited 2 with 34 collection/import errors
(`psycopg` unavailable). A second attempt with the Python package path but
without its existing libpq loader path also exited 2 with 34 import errors.
No database schemas were created in either attempt. With the existing private
dependency paths supplied, the registered suite passed:

```text
source /home/udaybhan/.config/ghar-sajag/gs179-laptop/server.env
export GS179_TEST_POSTGRES_DSN="$GS179_LOCAL_SERVER_DSN"
export PYTHONPATH="/home/udaybhan/.local/share/ghar-sajag/gs179-laptop/python-deps${PYTHONPATH:+:$PYTHONPATH}"
export LD_LIBRARY_PATH="/home/udaybhan/.local/share/ghar-sajag/gs179-laptop/postgres-root/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
make -C code gs179-postgres-e2e
```

Result: exit 0, 47/47 tests passed (`15 test_gs178_security`, 18
`test_gs178_vertical`, 14 `test_gs179_postgres_security`); the suite built and
ran the production Node/Hub host-simulation path. A read-only post-run query
found zero leftover `GS179_TEST_*` schemas. Additional checks:

- `make -C code validation-framework-test`: exit 0, 51/51.
- `make -C code feature-coverage-test`: exit 0; 223 features, 277 modules,
  26 physical cases; mapping tests 22/22.
- `bash -n code/tools/local/gs179-laptop-server.sh`: exit 0.
- `git diff --check`: exit 0 at validation time.

The existing scenario's original source `EventKey` is
`{physical_device_id: "test-c3-bedroom", logical_node_id: "bedroom",
origin_session_id: 10, event_sequence: 1}` with `occurred_at=1792605498`,
motion type and bedroom room. The GS-178 host simulation produced and retained
that Node event; the existing Hub processing/CloudSync path submitted it via
the verified TEST_ONLY mTLS fixture. The durable API returned 201
`COMMITTED`/`duplicate=false`; the exact retry returned 200
`COMMITTED`/`duplicate=true`. The test asserts exactly one PostgreSQL logical
row for that EventKey and the caregiver projection returned the same source
event in the authorized TEST_ONLY Home. The browser/shared-UI scenario recorded
17 assertions and `HOST_SIM_PASS`. This is source-linked host simulation plus
isolated TEST_ONLY host services; it is not C3/S3 target execution, physical
PIR evidence, a real Hub certificate, or Android handset evidence.

The same registered cases exercise exact retry across restart, conflicting
EventKey/body rejection, wrong/revoked/expired certificate or identity,
wrong-Home isolation, forged identity headers, missing/untrusted time,
backend-readiness loss, stale/revoked ownership, NodeHealth freshness and
UNKNOWN transition, authenticated health refresh, bounds and shutdown. They
pass for the isolated software fixture only. No physical/target test was run.

### Current operational readiness and gate

The existing read-only laptop health command reported:

```text
POSTGRES_READY=PASS tls=verify-full durability=fsync,synchronous_commit,full_page_writes
CAREGIVER_HTTPS_READY=PASS tls=ca_and_ip_san_verified
LOCAL_BACKEND_READY=PASS
PHONE_LAN_REACHABLE=BLOCKED_CONFIG_MISMATCH
HUB_INGRESS_READY=NOT_CONFIGURED
```

Caregiver HTTPS/PostgreSQL readiness does not imply Hub ingress or physical
monitoring availability. The phone's configured LAN endpoint does not match
the currently observed laptop address; no network or forwarding setting was
changed. Persistent Hub ingress remains blocked until the owner-approved
TEST_ONLY credential/issuer registry and artifacts, trusted-time provider,
current Hub/Home/epoch binding and authorized route are supplied and verified.
Production credential custody and production TLS remain separate approval
gates. The next product milestone is the separately authorized GS-117 physical
qualification: identify and verify the actual C3/S3 images and authority,
trusted session/time and pending journal state, approve the secure endpoint and
route, then observe real PIR → C3 → S3 → backend → Android APK behavior under a
written stop/recovery plan. No such physical operation is authorized here.

## Default-disabled runtime composition implementation — 2026-10-22

The 2026-10-21 statement that the runtime change was not safely implementable
without live credential and route inputs is superseded for software work by the
owner's implementation instruction. The safe code-level composition has now
been implemented and exercised with disposable TEST_ONLY dependencies. No live
credential, route, network listener or customer data was enabled.

### Reuse and minimum change

| Component | Classification | Delivery |
|---|---|---|
| Application-terminated TLS 1.2/mTLS listener | `ALREADY_IMPLEMENTED / REUSE` | `test_only_mtls_listener.py` remains the socket, TLS, peer identity, request-bound and shutdown owner. The runtime passes it the existing API, credential registry, current ownership database, trusted-time callback and GS-40 authority-refresh callback. |
| GS-148 PostgreSQL durable API | `ALREADY_IMPLEMENTED / REUSE` | `open_postgres_durable_event_api` remains the event, NodeHealth, Hub-decision and caregiver projection store. The runtime opens one durable API connection and checks durable settings plus `SELECT 1` before constructing the listener. |
| GS-168 TEST_ONLY credential registry and GS-40 authority refresh | `ALREADY_IMPLEMENTED / REUSE` | Runtime trust is injected and bound to the client CA fingerprint. Authority refresh uses the existing `AuthorityService`; test subprocesses read issuer metadata read-only and use only the stack's disposable authority signer fixture. |
| Hub-ingress process composition | `GENUINE_GAP / MINIMUM_REQUIRED_CHANGE` | Added `gs179_hub_ingress_runtime.py`, a default-disabled lifecycle that requires explicit `GS179_TEST_ONLY` config, loopback PostgreSQL over `verify-full`, server key/cert and client CA, a matching TEST_ONLY credential registry, an explicit trusted-time source, authority refresh, and a current Hub/Home/epoch with active Node enrollment. It scopes the registry to that configured Hub and binds only to loopback. It never starts in WSGI/Gunicorn. |
| Laptop operational status | `REUSE / MINIMUM_REQUIRED_CHANGE` | The caregiver service still does not activate Hub ingress. Health output now reports runtime available, autostart disabled, no authenticated real Hub, freshness UNKNOWN, persistent ingress not configured, and preserves `HUB_INGRESS_READY=NOT_CONFIGURED`. |
| Caregiver projection, API and Android shared UI | `ALREADY_IMPLEMENTED / REUSE` | The same committed PostgreSQL event remains readable through the current Home-authorized projection. No caregiver data model, API, Home UI or Android feature was duplicated or changed. |

### Runtime behavior and failure closure

`start_gs179_test_only_hub_ingress` is the runtime entry point. Unset enable
configuration returns disabled without contacting PostgreSQL or opening a
socket. Enabled startup rejects missing/unsafe TLS paths, non-loopback or
non-`verify-full` PostgreSQL, a non-TEST_ONLY or CA-mismatched registry,
missing/untrusted time, absent authority refresh, invalid Home/Hub namespace,
stale epoch, missing active enrollment, unhealthy PostgreSQL or unsafe durable
settings before the listener is opened. Request processing and shutdown remain
bounded by the existing listener. Runtime status can report listener, database
and trusted-time readiness but always reports real Hub authentication `NO`,
Hub connected `NO`, and monitoring freshness `UNKNOWN`.

The persistent laptop operation is unchanged and remains disabled. This code
does not provide a TEST_ONLY CA as a commercial credential lifecycle, add a
second worker/store, start a listener from Gunicorn, or make firewall, portproxy,
router, cloud or hardware changes.

### Runtime-owned source-linked E2E

The new registered test launches the production runtime entry point in a
separate process, then starts the existing GS-178 production-code HOST_SIM Node
and performs CloudSync over an actual loopback TLS socket. The event identity is
`{physical_device_id: "test-c3-bedroom", logical_node_id: "bedroom",
origin_session_id: 10, event_sequence: 1}`. The C++ Node's original EventKey
string is checked against the key sent by CloudSync. Its occurrence time,
`MOTION` type, bedroom location, Hub ID, current Home and ownership epoch are
checked against the single durable PostgreSQL record.

The runtime's first HTTP response was intentionally dropped after PostgreSQL
commit. The listener process was shut down and restarted on the same loopback
port. The Node retried the same retained event; the second receipt was
`COMMITTED` with `duplicate=true`, and PostgreSQL still contained one logical
row. The authenticated caregiver API read the same EventKey from
`gs177-test-product` before and after listener and caregiver API connection
restart. Initial monitoring was `UNKNOWN`; runtime status did not infer a Hub
connection from service readiness. The scenario is HOST_SIM plus disposable
TEST_ONLY software; it is not target execution or physical sensor evidence.

### Validation on the runtime implementation

- Registered `make -C code gs179-postgres-e2e`: **50/50 PASS**, exit 0. This
  comprises 15 existing GS-178 security cases, 18 existing Node-origin vertical
  cases, 14 PostgreSQL/security cases and 3 runtime-composition cases. The
  production HOST_SIM target was built; all database schemas were isolated.
- Focused new runtime module after adding the exact EventKey assertion:
  **3/3 PASS**, exit 0. This includes disabled/missing configuration, missing
  authority, untrusted time, missing server certificate/key/client CA,
  CA-registry mismatch, stale epoch, PostgreSQL unavailable, wrong-Home peer,
  listener process restart, lost receipt and caregiver readback.
- `make -C code validation-framework-test`: **51/51 PASS**, exit 0.
- `make -C code feature-coverage-test`: **223 features, 278 modules, 26
  physical cases; mapping 22/22 PASS**, exit 0. A first mapping attempt exposed
  that fixture/tool files were outside the source inventory's configured source
  roots; the inventory was narrowed to the new backend runtime while the test
  and fixture paths remain registered as suite and traceability inputs.
- Physical C3/S3, real PIR, real Hub TLS authentication, real Android APK
  handset, network routing and commercial release tests were not run.

One early process-test attempt failed because the separate runtime had not yet
been given the existing GS-40 authority-refresh callback; the production
HOST_SIM Hub correctly refused bootstrap. The composition was corrected to
require that callback and the subprocess now uses the existing TEST_ONLY
`AuthorityService` with the same ephemeral fixture signer as the Node. The
subsequent focused and registered runs passed. An initial test command without
the established Python/libpq paths also failed at import; the registered run
used the already configured local test environment and passed. These setup
failures did not change product behavior or weaken test assertions.

### Current readiness and next action

```text
GS179_RUNTIME_COMPOSITION_IMPLEMENTED=PASS
GS179_RUNTIME_INTEGRATION_TESTED=PASS
GS179_ISOLATED_SOFTWARE_E2E=PASS
PERSISTENT_LAPTOP_HUB_INGRESS_ACTIVE=NOT_CONFIGURED
REAL_S3_AUTHENTICATED=NOT_RUN
REAL_PIR_EVENT_RECEIVED=NOT_RUN
ANDROID_REAL_EVENT_VISIBLE=NOT_RUN
GS117_PHYSICAL_E2E=NOT_RUN
COMMERCIAL_RELEASE=NOT_RUN
```

To activate a persistent real-S3 ingress later, the owner must approve the
specific Hub credential/registry artifact, current Home/epoch and Node
enrollment, trusted-time source, server endpoint identity, and private network
route plus service activation. Production credentials require the separate
approved security lifecycle; the TEST_ONLY issuer and listener are not that
lifecycle. GS-117 then requires the fixture/image/authority, journal,
reset-safe observation, endpoint and recovery checks before authorized real PIR
qualification and a verified Android APK read. Keep GS-179 In Progress and
GS-117 open. The default-disabled runtime source and software evidence were
committed and pushed as `acde2183c74351db403b49b441deea67a3474142`; local and
remote matched at delivery. Jira comment 11526 records the implementation and
validation. Remaining GS-179 work is separately approved persistent/runtime
configuration and the broader live staging/phone acceptance. No physical pass
is claimed.

### 2026-10-27 — bounded physical-ingress readiness recheck

At canonical source `cac55b92a00fe6fe807787ce9faa55ba42df5305`, the existing
GS-179 TEST_ONLY mTLS ingress and signed-time endpoint were restored from
protected, hash-matched operator scripts for a bounded one-hour session. No
autostart or persistent service was enabled. On verified Private
`Airtel_Agrim` Wi-Fi at dynamically observed `192.168.1.10`, the already-owned
Windows forwarding targets remained 443→8444 and 8445→8445; the live Windows
8445 TCP probe passed. PostgreSQL durability/TLS and caregiver HTTPS health
passed. A host-generated challenge received a valid nonce/generation-bound
RSA-3072 signed-time proof with a current validity interval.

These endpoint checks do not prove S3 traffic. The current listener reported
listener/PostgreSQL/trusted-time readiness, but `real_hub_authenticated=NO`,
`hub_connected=NO`, and zero Hub/event receipt rows were recorded since its
start. Signed-time request counters lack authenticated source attribution.
The last verified S3 mTLS/CloudSync events remain historical, so
`REAL_S3_AUTHENTICATED=NOT_VERIFIED`, not PASS. The laptop caregiver and
PostgreSQL components are ready; persistent ingress remains default-disabled.

The physical Android device is ADB-authorized. Current installed APK bytes
match the protected preservation SHA and its embedded signer-certificate
fingerprint matches preserved trusted signer digests. In the existing app,
Settings showed Home `gs177-test-product`, origin `https://192.168.1.10/` and
`Backend API · CONNECTED`; Reports showed `Latest recorded events`. The
production exact-key observer also matched a historical physical event through
Event details; this validates observer readiness only and is not new event
acceptance. `UNKNOWN`/`STALE` NodeHealth remains a separate known projection
conflict; no enrollment or database state was changed.

No physical serial port or board was accessed. No C3 event was injected. Since
the earlier S3 configuration is RAM-only and its last authenticated evidence
is outside the bounded session, current S3 config/runtime cannot be confirmed
without the explicitly excluded reset-aware COM10 bootstrap. If required,
reuse the existing protected
`gs117-protected-bootstrap-current-network.py`: opening COM10 can cause
`USB_UART_CHIP_RESET`, reboot S3 and clear RAM-only Wi-Fi/GS40 config; the
existing procedure sends a fresh challenge-bound encrypted config and does not
flash or overwrite NVS/partition/outbox/state. Its previously recorded
one-attempt approval is consumed. TC-001 remains BLOCKED/NOT_RUN and needs
fresh live S3 mTLS evidence plus the exact owner-only console fixture. The
five-run physical approval was not created. Sanitized observation is stored
mode 0600 outside Git at
`~/.local/state/ghar-sajag/gs117-tc001/services-20261027T0230Z/readiness-observation-20261027T0255Z.json`.

### 2026-10-27 — resumed bounded ingress recheck (04:30Z)

Canonical source at recheck entry was `cac55b92a00fe6fe807787ce9faa55ba42df5305`;
context preflight passed. Private Wi-Fi `Airtel_Agrim` remained Private at
`192.168.1.10/24`, with WSL at `172.17.152.10/20` and existing 443→8444 and
8445→8445 forwarding. Windows TCP 8445 passed. A no-client-certificate TLS
probe reached the listener certificate subject and then failed the handshake;
it verifies routing to the endpoint but no mTLS client identity.

The current laptop health check passed PostgreSQL durability/TLS, caregiver
HTTPS and endpoint CA/DNS-SAN checks. The one-hour TEST_ONLY listener reported
listener/PostgreSQL/trusted-time ready, while authentication and Hub connection
remained NO; no current CloudSync receipt or event trace row was produced.
Persistent ingress is still NOT_CONFIGURED and autostart DISABLED. UDP 4468
was bound; the host-generated nonce/generation-bound RSA-3072/SHA-256 proof
passed at 04:22:20Z and was valid through 04:24:20Z. It is host-service
evidence, not S3 authentication, and was expired by this later recheck.

The 02:59:52Z Android receipt records the existing APK connected to
`gs177-test-product`, Reports available and a historical EventKey observer
match only. It records no fresh TC-001 event. Installed APK bytes match the
preserved hash; the embedded v2 signer-certificate fingerprint matches
preserved digest files, but `apksigner verify` was not run, so package signature
verification remains incomplete. The current-source GS-117 console/ADB
regression passed **43/43**; the loopback status endpoint itself responded
HTTP 200 from an older process and is not evidence of current-source readiness.

The owner-only TC-001 fixture and separate five-run approval remain absent. No
physical port or board was accessed, and no injection or lifecycle mutation was
performed. TC-001 remains BLOCKED/NOT_RUN; fresh running-image/fixture identity
and authenticated S3 ingress evidence are still missing. Any reset-aware COM10
recovery requires new explicit owner approval because opening COM10 may reboot
S3 and clear its RAM-only configuration. Private sanitized evidence remains at
`~/.local/state/ghar-sajag/gs117-tc001/fixture-session-20261027T041925Z/readiness-observation-20261027T0430Z.json`.

### 2026-10-27 — audit-first current readiness recheck (05:07Z)

At canonical source `77b1927dc4043308078f0b3d2afa496aeead4555`, the current
host health check passed PostgreSQL TLS/durability, caregiver HTTPS and local
backend checks. Private Wi-Fi `Airtel_Agrim` was `192.168.1.10`; existing
Windows forwarding and TCP 8445 reachability passed. UDP 4468 returned a
fresh nonce/generation-bound RSA-3072/SHA-256 host proof at 05:01:54Z, valid
through 05:03:54Z. This TEST_ONLY host proof expired by the later observation
and is not S3 authentication.

The bounded ingress listener and its backend/time dependencies were ready, but
no current authenticated Hub event trace or physical CloudSync receipt was
observed. Its status fields `real_hub_authenticated` and `hub_connected` are
conservative constants, not live Hub measurements. Persistent ingress remains
disabled. A stale idle loopback console was replaced with the existing current-
source launcher; the guarded console reports backend readiness but fixture
BLOCKED and Android NOT_VERIFIED. USB enumeration identified the expected C3
COM4 and S3 COM10 without opening either port.

The Android evidence remains the historical 02:59Z session112/sequence2
observer match. Installed bytes match the preserved APK SHA and the embedded
v2 certificate digest matches preserved trust digests; formal `apksigner
verify` remains incomplete. No fresh TC-001 event was observed. The owner-only
fixture and separate five-run authorization are absent. TC-001 is 0/5
BLOCKED/NOT_RUN; real PIR is NOT_RUN.

The previous one-hour RAM-only configuration/authority envelope expired. The
existing protected recovery procedure has a current-session helper hash pin
updated only in its mode-0600 session copy; its owner-only template is
unchanged. Its no-approval guard stopped before network or serial access.
Fresh scoped owner approval is required for the one-attempt COM10/COM4
configuration recovery described in the GS-117 handoff. That recovery approval
is separate from any five-run injection approval. Persistent GS-179 service
configuration and broader live staging acceptance remain open; GS-179 stays
In Progress.

### 2026-10-27 — bounded physical recovery ingress, fresh mTLS receipt and backend projection (05:57Z)

Following the separately scoped owner approval for one S3 recovery, the
existing protected recovery procedure was executed once. The S3 returned to
the exact TEST_ONLY Hub `hub-e072a1d38d34`, Home `gs177-test-product`, epoch 1,
enrollment 1 and accepted the existing encrypted configuration. The procedure
observed current app version `9bbc6d0-dirty` and ELF SHA prefix `c77483102`,
not a full current-image digest. The consumed attempt was not repeated.

Existing bounded GS-179 mTLS ingress and signed-time services were restored
from hash-matched operator scripts for a one-hour session. On Private
`Airtel_Agrim` Wi-Fi at `192.168.1.10`, current Windows-to-WSL TCP 8445
forwarding succeeded; UDP 4468 was bound. Current PostgreSQL TLS/durability,
caregiver HTTPS and local backend health passed. A host RSA-3072/SHA-256
signed-time proof matched its fresh nonce and generation and was valid from
05:38:38Z to 05:40:38Z; it had expired at this 05:57Z observation. This is
host-generated TEST_ONLY proof, not physical Hub authentication.

Unlike the earlier readiness checkpoint, the current listener trace now
contains repeated physical Hub mTLS authority-refresh responses (latest HTTP
200 at 05:57:02Z) and physical CloudSync event receipts. Sixteen unique C3
EventKeys from `c3-146393c5d158`, Bedroom, session 118 sequences 1–16 received
HTTP 201 `COMMITTED`, `duplicate=false`; repeated retries received 18 HTTP 200
`COMMITTED`, `duplicate=true`. The saved read-only PostgreSQL/caregiver API
correlation reports exactly one durable record and one caregiver projection
for each of these keys with the correct Hub, Home, epoch and enrollment. These
are physical Node-originated/replayed events, not controlled TC-001 stimuli;
they do not establish a five-run campaign, per-run C3 durable ACK evidence, or
actual phone display. A later Node-observed sequence 122 was not present in
the exact-key backend query and is not counted as delivered.

`gs179-laptop-server.sh health` continues to report persistent Hub ingress
`NOT_CONFIGURED` and autostart disabled. The loopback GS-117 console's
`hub_ingress.status=PASS` only describes the active bounded listener, while
its `running=false` and current fixture/campaign/Android gates are
BLOCKED/NOT_VERIFIED. Preserve those distinctions: the live mTLS trace proves
current S3 authentication for this bounded session, but it does not enable a
persistent staging service or close GS-179. GS-179 remains **In Progress**.

The existing Android `AndroidReady` check passed installed device/package/path
identity. The exact-key event observer remained NOT_VERIFIED because the
approved phone was locked and did not foreground the app. The signer digest
was echoed from its owner-only install receipt and formal APK signature
verification remains incomplete. Full current C3/S3 image and partition
receipts and a fresh exact-key APK observation are still missing; no fixture
was created and the five-run campaign approval remains absent. Private
mode-0600 source trace and sanitized backend correlation are under
`~/.local/state/ghar-sajag/gs117-tc001/recovery-services-20261027T053803Z/`.

### 2026-10-27 11:11 UTC — current endpoint and listener recheck

PostgreSQL TLS/durability, caregiver HTTPS and the local backend still pass.
The external TLS health probe to the phone-facing endpoint times out. Windows
Wi-Fi is now `192.168.1.6`, while the Android app and last verified encrypted
Hub configuration target `192.168.1.10`; existing portproxy mappings still
bind `.10` to WSL `172.17.152.10`. The `.10` neighbor is a different MAC from
the laptop Wi-Fi adapter, so the old endpoint is not currently owned by this
host. No credentials
were sent to it and no network configuration was changed.

The bounded physical mTLS ingress on TCP 8445 and signed-time service on UDP
4468 are no longer listening. Historical authenticated S3 authority-refresh
receipts and CloudSync commits through 06:37Z remain valid for that bounded
session only; they do not establish current S3 authentication. Persistent
ingress remains `NOT_CONFIGURED` and autostart remains disabled. A fresh S3
receipt requires the owner-approved lab endpoint and bounded services to be
restored; the prior one-attempt Hub recovery approval is consumed.

GS-179 remains **In Progress**. Current state is
`GS179_FRESH_REAL_S3_AUTHENTICATION=NOT_VERIFIED`. Do not repoint the proxy to
`.6` while the app and Hub still use `.10`; first restore the approved endpoint
or obtain an approved coordinated endpoint change.

### 2026-10-27 12:16 UTC — router-reserved `.6` endpoint restored; physical Hub still unauthenticated

The owner confirmed the router reserves `192.168.1.6` for laptop Wi-Fi MAC
`C0:18:85:B9:4F:C3`; Windows DHCP remains enabled. The existing GS-179 recovery
has removed the stale `.10` routes and now forwards only `.6:443` to WSL
`172.17.152.10:8444` and `.6:8445` to `172.17.152.10:8445`. The Wi-Fi profile
is Private, the current TLS identity covers `desktop-3qqu64b.local` and `.6`,
and existing PostgreSQL TLS/durability, caregiver HTTPS, local backend and
endpoint TLS checks pass. No credentials were sent to `.10`.

The actual installed Android app reports Backend API CONNECTED, Home
`gs177-test-product`, origin `https://192.168.1.6/`, and accessible Reports.
Its Event Details screen was observed through the existing ADB helper for
historical physical session 118 / sequence 16, with the exact original EventKey
and Bedroom/Motion/time fields. This is not a new TC-001 input. The observation
is preserved at
`~/.local/state/ghar-sajag/gs117-tc001/android-session118-seq16-exact-20261027T120515Z/`.

The existing bounded TCP 8445 ingress and UDP 4468 signed-time processes are
active at this checkpoint. Host forwarding and listener readiness pass. The
12:11:28Z RSA-3072 challenge verifies nonce/generation/signature binding but is
host-generated and expired after its 120-second validity window. Current
ingress status at 12:16:32Z remains `real_hub_authenticated=NO`,
`hub_connected=NO`, monitoring freshness `UNKNOWN`; persistent ingress is
`NOT_CONFIGURED`. Therefore no fresh authenticated physical S3 receipt is
established. Last-known encrypted S3 configuration still targets `.10`; its
update to `.6` requires another explicitly scoped COM10 operation because the
prior one-attempt recovery authorization was consumed. COM10 reset can lose
RAM-only Wi-Fi/GS40 state.

Current-image fixture evidence remains incomplete. The S3 image receipt has
aged past 24 hours; C3 has no complete current installed-image/partition-table
receipt. Use targeted read-only app-slot and partition-table readback through
the existing esptool procedure, avoiding NVS/outbox/state. Opening COM4/COM10
may reset the boards, so this evidence collection and one encrypted S3 endpoint
recovery attempt require fresh scoped owner approval. The fixture and separate
five-run approval remain absent. No port was opened or board operation run in
this checkpoint. GS-179 stays **In Progress**; bounded readiness and actual
phone connectivity do not close fresh physical S3 authentication or persistent
staging acceptance.
