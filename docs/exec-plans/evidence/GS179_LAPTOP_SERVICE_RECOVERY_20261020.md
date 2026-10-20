# GS-179 laptop service recovery and Windows diagnostics — 2026-10-20

## Result

`LOCAL_BACKEND_READY=PASS`. The recovered local service serves the existing
caregiver HTTPS API from WSL and PostgreSQL is reachable over verified TLS with
durability settings enabled. `PHONE_LAN_REACHABLE` remains blocked by the
Windows Wi-Fi/certificate/origin mismatch. `HUB_INGRESS_READY=NOT_CONFIGURED`;
this local caregiver service is not a persistent authenticated physical-Hub
ingress.

No Windows network setting, certificate, caregiver account, hardware, or
production resource was changed. No synthetic event was inserted. Existing
PostgreSQL records were checked only with read-only queries. All physical and
phone acceptance remains `NOT_RUN`.

## Root cause and correction

The installed user unit had an `ExecStartPost` that ran the Windows
`proxy-start` action. The Windows script correctly required an administrator
token for portproxy/firewall mutation, which the current process did not have.
That post-start failure caused systemd to fail the whole unit and send TERM to
the caregiver Gunicorn process. The unit's `ExecStopPost` then stopped
PostgreSQL, so later Gunicorn worker database/TLS errors were consequences of
the service teardown, not evidence of bad database credentials. Repeated
automatic restarts reached systemd's start limit.

The Linux lifecycle now keeps Windows forwarding out of systemd startup and
shutdown. A failed caregiver process leaves PostgreSQL running for recovery;
an intentional clean service stop shuts down only PostgreSQL. `start` and
`restart` now load the private config, perform the local systemd action, wait
for up to 30 seconds for PostgreSQL and local caregiver HTTPS readiness, then
report phone-LAN and Hub readiness separately. This bounded wait fixes the
observed race where systemd's `Type=simple` job returned before the local
health probes were ready.

The previous user unit was saved outside the repository with mode `0600` before
replacement. The corrected unit was installed and verified to contain no
`ExecStartPost`, `proxy-start`, or automatic Windows networking hook. It is
enabled and running. The service binds Gunicorn only to the current private WSL
NAT address on TCP 8444. PostgreSQL listens on WSL loopback TCP 55432 and its
private socket, with `sslmode=verify-full`, SCRAM authentication,
`fsync=on`, `synchronous_commit=on`, and `full_page_writes=on`.

## Read-only Windows findings

- Windows 10 build 19045; PowerShell 5.1.
- Wi-Fi is up at `192.168.1.3/24`; network category is Public. The configured
  expected address is `192.168.1.6`. The current Wi-Fi profile identity matches
  the private server configuration; its name is intentionally omitted here.
- Current WSL NAT address: `172.17.152.10`.
- IP Helper is running.
- Existing portproxy row: `192.168.1.6:443` → `172.17.152.10:8444`. The target
  WSL address matches the current WSL NAT address, but the listen address does
  not match the current Wi-Fi address. Windows `netstat` showed no TCP 443
  listener.
- The read-only firewall query returned
  `BLOCKED_ADMIN_READ_PERMISSION`; current rule presence/scope is therefore
  unknown. No administrator prompt or elevation was attempted.
- A host-to-WSL TCP check to `172.17.152.10:8444` succeeded. WSL's
  certificate-verified `/readyz` succeeded. A Windows-native curl request to
  the WSL address with the existing CA and expected `.6` certificate identity
  failed with Schannel `CERT_TRUST_REVOCATION_STATUS_UNKNOWN` (curl exit 60).
  Certificate checks were not bypassed. This host diagnostic is not phone
  acceptance.
- The Android/local server certificate contains `IP:192.168.1.6` SAN and is
  valid for the existing expected origin. It does not match `.3`.
- No router DHCP reservation or authoritative lease data was available. No
  cached neighbor entry was observed for `.6`; that does not prove that `.6` is
  unused. Availability of `.6` is **UNCONFIRMED**.

The read-only `proxy-audit` action was moved before the administrator gate so
it can report available adapter/portproxy information without elevation. Its
firewall query reports a permission-limited status instead of claiming that a
rule is absent. Start and Stop retain the administrator-token check and their
mutation validation.

## Local data and readiness evidence

The private PostgreSQL cluster was cleanly shut down before recovery. The
service started it without provisioning or erasing it. After the recovery and
isolated E2E run, a read-only TLS transaction reported:

| Public table | Current rows |
|---|---:|
| `households` | 6 |
| `caregivers` | 7 |
| `events` | 1 |
| `durable_event_commits` | 1 |
| `hub_rule_decisions` | 0 |
| `node_health_latest` | 1 |
| `gs_schema_migrations` | 13 |

The E2E runner used new random `gs179_e2e_*` schemas in the local database and
dropped each schema on teardown. It did not target the public monitoring
tables. No live account, session, event, Home, or credential was changed by the
recovery. Existing caregiver/event data was not printed.

Final local health output:

```text
POSTGRES_READY=PASS tls=verify-full durability=fsync,synchronous_commit,full_page_writes
CAREGIVER_HTTPS_READY=PASS tls=ca_and_ip_san_verified
LOCAL_BACKEND_READY=PASS
PHONE_LAN_REACHABLE=BLOCKED_CONFIG_MISMATCH expected_address=192.168.1.6 observed_address=192.168.1.3
HUB_INGRESS_READY=NOT_CONFIGURED
```

`start` passed after recovery, `restart` passed, and a repeated `start` passed.
There was one transient initial health invocation before service readiness;
the bounded wait was added and the subsequent real start/restart checks passed.

## Source changes and test evidence

Classification for the browser test path correction:

```text
BUG_CLASSIFICATION=TEST_INFRA_ONLY
REQUIREMENT_SOURCE=GS-116 registered GS-179/GS-178 regression execution
DECISION_IDS=NONE
TASK_SCOPE=GS-179 local service recovery and focused regressions
OUT_OF_SCOPE=product event semantics, Windows network mutation, physical qualification
```

Files changed:

- `code/tools/local/gs179-laptop-server.sh` — local-only service lifecycle,
  failure-safe PostgreSQL handling, bounded start readiness, verified separate
  health states, and read-only `proxy-audit`.
- `code/tools/local/gs179-windows-lan-proxy.ps1` — read-only Audit before the
  admin gate; all mutation actions remain admin-gated.
- `code/tests/integration/test_gs179_postgres_security.py` — lifecycle, health
  classification, Windows boundary, and bounded readiness regression tests.
- `code/tests/integration/test_gs178_vertical.py` — browser support script now
  resolves from the source file, independent of the runner's working directory.

Executed results:

- GS-179 PostgreSQL E2E runner with local private DSN and per-test isolated
  schemas: **46/46 PASS**, `physical=NOT_RUN`.
- Three browser scenarios affected by the path fix: **3/3 PASS**.
- GS-179 lifecycle/security component suite: **14/14 PASS**.
- `make validation-framework-test`: **51/51 PASS**.
- `make feature-coverage-test`: **PASS**, 221 features, 263 modules, 26
  physical cases; mapping tests **22/22 PASS**.
- `bash -n code/tools/local/gs179-laptop-server.sh`: **PASS**.
- Python byte-compilation of the changed integration tests: **PASS**.
- Windows PowerShell AST parse for the proxy script: **PASS**.
- `git diff --check`: **PASS**.
- `validation-fast` and `release-gate-final`: **NOT_RUN**.

Representative command forms (private DSN/password values are loaded from the
existing mode-0600 file and are not printed):

```bash
bash code/tools/local/gs179-laptop-server.sh start
bash code/tools/local/gs179-laptop-server.sh restart
bash code/tools/local/gs179-laptop-server.sh health
bash code/tools/local/gs179-laptop-server.sh proxy-audit
make -C code validation-framework-test
make -C code feature-coverage-test
```

The 46-case run was invoked as
`GS179_TEST_POSTGRES_ONLY=1 GS179_TEST_POSTGRES_DSN="$GS179_LOCAL_SERVER_DSN"`
with the private `server.env` sourced only in the current shell and the
isolated local Python/PostgreSQL runtime paths. It used
`python3 code/tests/integration/run_gs179_postgres_e2e.py`; the fixture created
and dropped per-test random schemas in the local database.

The prior first attempt at the PostgreSQL E2E reported 43/46 because three
browser cases used a working-directory-relative script path. After correcting
the test harness and rerunning the complete suite, all 46 passed. The laptop
unit's actual startup and restart health checks are separate live local
service evidence; they do not imply LAN phone access or physical Hub ingestion.

## Address decision and next action

Restoring `192.168.1.6` is **not yet established as safe**: current Wi-Fi is
`.3`, the router reservation/lease is unavailable, and absence from the local
neighbor cache is not proof of availability. The existing certificate and
LAN APK profile are aligned to `.6`, so retaining `.6` is the preferred route
if the network owner confirms it is reserved for this laptop. If it is not
available, a separately authorized origin/certificate/Windows forwarding and
LAN APK change would be required; none was performed.

The next action is for the network owner to verify or reserve `.6` for this
laptop, then separately authorize the exact Windows address/forwarding update.
After that, rerun read-only audit, verify the scoped firewall rule and TCP 443
listener, then test the pinned HTTPS origin from the phone. Do not attempt
phone acceptance before those checks. Actual C3/S3 NodeHealth/Hub ingress,
GS-117 physical E2E, and commercial credentials remain separate blockers.
