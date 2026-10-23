# GS-179 local WSL2 caregiver validation host — 2026-10-20

> **Recovery update (2026-10-20):** The earlier forwarding description below
> records the setup at the time it was validated. The current Wi-Fi address is
> `192.168.1.3`, while the existing certificate, Android origin and Windows
> forwarding mapping use `192.168.1.6`. No Windows network setting was changed.
> The recovered WSL backend is locally ready, but the Windows-to-phone route is
> currently unavailable. The current service lifecycle and network findings
> are recorded in
> [`GS-179 laptop service recovery`](GS179_LAPTOP_SERVICE_RECOVERY_20261020.md).

## Result and scope

The owner selected the existing Windows 10 laptop and WSL2 for no-cost,
same-trusted-Wi-Fi R1 Android validation in GS-179 comment 11452. This checkpoint
configures the canonical GS-148 caregiver API/PWA and PostgreSQL on that laptop,
adds a narrowly scoped Windows-to-WSL HTTPS route, and prepares a debug-only
Android build profile for the current laptop origin. It does not change Render,
production services, router configuration, hardware, production credentials, or
commercial security policy.

The software path exercised is the existing GS-178 host Node/Hub code → the
existing TEST_ONLY application-terminated TLS 1.2/mTLS listener and GS-148
durable API → the local PostgreSQL commit store → authenticated caregiver API
and canonical PWA. It is **HOST_SIM_PASS** only. The persistent laptop service
is the caregiver HTTPS API plus PostgreSQL. It is not a continuously running
physical Hub mTLS endpoint: the source-linked host-simulation command runs the
existing TEST_ONLY Hub mTLS listener using ephemeral test credentials. No
physical Hub identity or client credential is installed on this laptop.

## Runtime and network boundary

- Current caregiver origin: `https://192.168.1.6` (RFC1918 Wi-Fi address; it
  may change with DHCP. The Android trust profile and server certificate are
  bound to this exact address and must be deliberately renewed together if it
  changes).
- The existing Windows mapping is `192.168.1.6:443` to the current WSL NAT
  address on TCP 8444. It is not usable while Wi-Fi is `192.168.1.3`; read-only
  inspection found no Windows TCP 443 listener. The firewall rule's current
  presence/scope could not be verified using the non-administrator account.
  No router port-forward or public listener is configured.
- The app binds to the WSL interface and serves TLS 1.2 or later. Windows can
  reach the WSL TCP listener, but Windows curl's Schannel validation returned
  `CERT_TRUST_REVOCATION_STATUS_UNKNOWN` when supplied the local CA. This was
  not bypassed. WSL's CA- and IP-SAN-verified `/readyz` check passes.
- The PostgreSQL listener is only `127.0.0.1:55432`. Its HBA rejects remote
  hosts; the application role uses SCRAM and `sslmode=verify-full` against the
  private local PostgreSQL test CA.
- PostgreSQL was checked with `fsync=on`, `synchronous_commit=on`, and
  `full_page_writes=on`. A service restart preserved the committed event.
  A separate machine-loss backup/restore rehearsal was not run.
- The observed Windows Wi-Fi profile is Public. The firewall rule was
  previously configured with an interface/address/subnet scope, but that scope
  could not be re-read without administrator permission. Re-run the read-only
  audit after a network or WSL address change; mismatched addresses fail
  closed.
- The laptop must remain awake, logged in to WSL and connected to the same
  trusted Wi-Fi while the phone test is running. Mobile-data access is not
  configured. Do not add a router port-forward; any off-LAN VPN/overlay remains
  a separate decision.

## TEST_ONLY HTTPS identity

The Android profile includes only the public local TEST_ONLY CA certificate;
its private key remains owner-only under the user's local data directory and
was not committed. The standards-shaped CA has `CA:TRUE,pathlen:0` and
`keyCertSign,cRLSign`; its file SHA-256 is
`7152366fdcf6d64d2df6ad2eca86ec6a8a8d60dad43cc7a8738e353fe86eddd5` and its
certificate fingerprint is
`124e28f34b8d73aa9fdd3f0f0fa2b7ff216e601c25162d1d6a224f1d63372b7c`.

During review, the original server leaf was found to have no IP SAN. Although
the current curl/OpenSSL environment accepted its legacy common-name identity,
that was insufficient evidence for Android's IP hostname check. The local
TEST_ONLY leaf was reissued under that CA with `IP:192.168.1.6`, `CA:FALSE`,
and `serverAuth`. Its file SHA-256 is
`390e1505b37a47f0dd08272a52fbd96a5a716828e7e6dc580a38abd2629b6119`.
`openssl verify -CAfile <private-ca.pem> -verify_ip 192.168.1.6 <server.pem>`
and a live CA-verified HTTPS `/readyz` request both passed after service restart.
The leaf and CA private keys remain mode 0600 outside the repository.

The local APK trust profile is conditional on the explicit
`gs179LocalLanTestOnly=true` Gradle property. It pins the exact LAN origin to a
single matching `network_security_config` domain and trusts the embedded local
test CA only for that domain. Release builds and ordinary debug builds retain
the public-DNS-only origin rule and do not include the local CA/profile. The
LAN build runner also verifies the manifest/resource binding, exact origin
match, and that the bundled certificate is a current self-signed CA with
critical CA constraints and certificate-signing usages. The
LAN APK always uses a runner-generated debug signing key, not a pilot or
production key. The build runner rejects an origin that differs from the
profile's pinned domain.

## Repeatable laptop commands

Run these from the canonical WSL worktree:

```bash
code/tools/local/gs179-laptop-server.sh start
code/tools/local/gs179-laptop-server.sh status
code/tools/local/gs179-laptop-server.sh health
code/tools/local/gs179-laptop-server.sh logs 100
code/tools/local/gs179-laptop-server.sh restart
code/tools/local/gs179-laptop-server.sh health-source
code/tools/local/gs179-laptop-server.sh browser
code/tools/local/gs179-laptop-server.sh stop
```

`provision` is a first-time operation and is idempotent only when the complete
private PostgreSQL/configuration state already exists. It refuses partial
state. The `event` command intentionally creates a source-linked event only
for an empty GS-179 persistent test Home; it refuses if an event already
exists. Do not run it to repeat the already committed event.

`start` and `restart` start the WSL user service and PostgreSQL only, wait up to
30 seconds for verified local PostgreSQL and caregiver HTTPS readiness, then
report phone-LAN and Hub-ingress states separately. They do not start or stop
Windows forwarding. `proxy-audit` is read-only. `proxy-start` and `proxy-stop`
remain explicit Windows network mutation commands and were not invoked during
this recovery. `status`/`logs` are for diagnosis. The service does not install
a Windows startup task; after a Windows/WSL restart, open the existing WSL
distro and run `start`.

## Validation evidence

Source state before delivery was canonical `feature/r1-commercial-baseline`
at `ef85e5b1ae0fe859fd666164976c0a293598c097`, equal to origin; context
preflight returned `GHAR_SAJAG_CONTEXT_PREFLIGHT=PASS`. No new branch or
worktree was created. The GS-58 worktree was left untouched.

Observed focused results:

- Existing GS-178 production-code host simulation generated one Node motion
  event, preserved its original EventKey, received the matching GS-148
  `COMMITTED` receipt and stored exactly one durable PostgreSQL row. Existing
  caregiver login/API returned that same event. The correlated EventKey is
  `{"physical_device_id":"test-c3-bedroom","logical_node_id":"bedroom","origin_session_id":10,"event_sequence":1}`.
  It is a TEST_ONLY fixture identifier, not a physical Node identity.
- After an application/PostgreSQL service restart, the same row and caregiver
  session remained available; no new event was inserted.
- After backend source freshness expired, the caregiver API reported source
  `STALE`, monitoring `UNKNOWN`, and Node `UNKNOWN`; it did not infer resident
  wellbeing from missing observations. A later authenticated host-simulator
  NodeHealth refresh restored source `CURRENT`, monitoring `COVERED`, and Node
  `ONLINE`.
- `code/tools/local/gs179-laptop-server.sh browser`: **HOST_SIM_PASS**. The
  canonical bundled PWA used the laptop HTTPS API, verified the committed
  event key/kind/room, showed current authenticated source freshness and
  `ONLINE`/`COVERED`, then reloaded with one event and no duplicate.
- `PYTHONPATH=/tmp/gs179-python-deps python3 -m unittest discover -s code/parivar_saathi_android_app/server/tests -p test_connected_lite.py -v`:
  **15/15 PASS**.
- `node --test code/tests/js/caregiver_runtime.test.mjs`: **8/8 PASS**.
- `GS177_BACKEND_ORIGIN=https://192.168.1.6 GS177_LOCAL_LAN_TEST_ONLY=1 python3 code/validation/run_gs177_android.py`:
  local profile/origin/CA-pinning checks, branding checks and 8 PWA runtime
  tests passed; the runner then returned **BLOCKED (127)** because Gradle and
  Android SDK are not installed in WSL. The negative profile check with
  `https://192.168.1.7` returned the expected **FAIL (1)** before invoking
  Gradle because it did not match the CA-pinned profile domain.
- The repository's `make -C code pwa-68-browser-test` reported **0 run, 1
  skipped** because system Chromium is not installed. The dedicated Playwright
  browser executable already present in the test cache was used by the local
  browser validation above, which passed against the live HTTPS API.
- GS-179 PostgreSQL/security focused tests: **7/7 PASS**; GS-178 host vertical
  focused cases: **3/3 PASS** in the preceding execution. These were not
  rerun after the Android-only pinned-domain guard change.
- TLS: `openssl verify ... -verify_ip 192.168.1.6` **PASS**; `curl --cacert
  <private-ca.pem> https://192.168.1.6/readyz` **HTTP 200**; OpenSSL live
  `s_client -verify_ip 192.168.1.6 -verify_return_error` returned **0 (ok)**.
- No phone APK build/install/foreground/background acceptance, physical C3/S3,
  phone data use, production service or hardware test was executed in this
  evidence checkpoint.

The source-matched local-LAN Android build completed in GitHub Actions run
[39326071201](https://github.com/udaybhan200683/Ghar_sajag/actions/runs/39326071201)
on commit `b8af8b37f3de4334a672588e5f5c8fad0dd855d4` with
`backend_origin=https://192.168.1.6` and
`gs179_local_lan_test_only=true`. The run passed the PWA browser/offline stage,
the registered caregiver app gates (Connected Lite API 15/15, Android dashboard
7/7, voice prototype 21/21), `:app:testDebugUnitTest`, `:app:assembleDebug`,
APK signature verification and artifact upload. The CI artifact is
`parivar-saathi-caregiver-debug-b8af8b37f3de4334a672588e5f5c8fad0dd855d4`
(artifact ID `12222706843`, archive SHA-256
`5e637ab363eb208c95f1f0217199175c3d696d7aef4e2992bff9d048ebbbd7ef`). Its
APK is 2,913,584 bytes, SHA-256
`6935f71d06c38087f09b2bf95c6a216e4dae30836449e367c773e7afa65eab42`; the
downloaded file passed `sha256sum --check` and APK archive integrity. CI
verified APK Signature Scheme v2. Build metadata binds it to the exact LAN
origin, local TEST_ONLY flag, and CA SHA-256
`7152366fdcf6d64d2df6ad2eca86ec6a8a8d60dad43cc7a8738e353fe86eddd5`.
Signing is runner-generated debug signing, not a pilot key. This proves APK
build and software gates only; it does not prove installation or behavior on
the owner's phone.

## Phone acceptance steps after artifact availability

1. Keep the Windows laptop awake, connected to the same trusted Wi-Fi, and WSL
   running. In canonical WSL, execute `code/tools/local/gs179-laptop-server.sh
   start`; require both `/readyz` probes to report ready. If the Wi-Fi address,
   subnet, certificate SAN, or CA-pinned profile changed, stop and reissue the
   local TEST_ONLY leaf/rebuild the APK; do not bypass certificate checks.
2. Install the `GS179_LOCAL_LAN_TEST_ONLY=true` debug APK artifact from the
   source-matched GitHub Actions run. It is signed with a runner-generated
   debug key. If Android reports a signature conflict with the previously
   installed pilot/debug package, remove that prior package only after
   preserving any desired local app state; server-side caregiver data remains
   in the laptop database.
3. On the phone, join the same trusted Wi-Fi (not mobile data/VPN), open
   Parivar Saathi and sign in using the already provisioned private
   GS-179 TEST_ONLY caregiver account. Confirm the bedroom motion appears once
   with its original event time and room; Devices shows `ONLINE`/`COVERED`;
   Home monitoring/source freshness shows current authenticated data.
4. Background and foreground the app, reload it, and verify the event remains
   once. Allow source freshness to expire without generating a new NodeHealth
   contact; refresh the caregiver view and require `UNKNOWN`/stale instead of
   false connected/wellbeing status. Run the existing `health-source` command,
   reload and require the authenticated source to recover to current and
   `ONLINE`/`COVERED`.
5. Record the phone model/Android version privately, APK artifact/source/hash,
   screenshots and timestamps. No credentials, private keys, or full
   identifiers go into public Git/Jira. Mark phone acceptance only after these
   observations are actually collected.

## Status

`LAPTOP_SERVICE`: PASS (local TEST_ONLY API/PostgreSQL running)
`HOST_SIM_NODE_EVENT_TO_POSTGRES_COMMITTED`: PASS
`CAREGIVER_BROWSER_PROJECTION`: PASS (host Playwright)
`ANDROID_LOCAL_LAN_APK_BUILD`: PASS (run 39326071201; source b8af8b37; APK
SHA-256 6935f71d06c38087f09b2bf95c6a216e4dae30836449e367c773e7afa65eab42)
`PHONE_FOREGROUND_BACKGROUND_ACCEPTANCE`: NOT_RUN
`C3_S3_PHYSICAL_TARGET_ACCEPTANCE`: NOT_RUN
`LIVE_STAGING_SOFTWARE_E2E_PASS`: NO (Render was not changed or accessed for
this local-host validation)
`PRODUCT_OR_RELEASE_PASS`: NO; broader P0 and physical release gates are not
reclassified by this local demonstration.

## 2026-10-22 — owner-approved Windows/WSL2 LAN configuration

Owner approval was recorded in GS-179 comment 11546 and GS-117 comment 11547.
This section supersedes the earlier statement in this file that no LAN
endpoint/forwarding/firewall changes were made; it does not change the physical
acceptance boundary.

### Current endpoint and trust

- Windows Wi-Fi is connected to SSID `Yogi`, IPv4 `192.168.1.6/24`,
  network category Public. The address is DHCP; the observed lease expires
  2026-10-23 15:36 local time. No router reservation was inspected or changed,
  so this is a verified current endpoint, not a guaranteed stable address.
- WSL2 address is `172.17.152.10`; caregiver HTTPS listens on that address at
  port 8444. PostgreSQL listens on WSL loopback port 55432.
- Existing TEST_ONLY server certificate already has the `192.168.1.6`
  address SAN and serverAuth purpose. Existing local CA SHA-256 is
  `7152366fdcf6d64d2df6ad2eca86ec6a8a8d60dad43cc7a8738e353fe86eddd5`,
  matching the Android local-LAN CA pin. The certificate verified for
  `192.168.1.6`; no CA, leaf certificate, key, or Android pin was changed.
- Caregiver HTTPS and Hub-ingress configuration use the same verified local
  PostgreSQL database: `gs179_monitoring`, role `gs179_app`, endpoint
  `127.0.0.1:55432`, PostgreSQL `verify-full`, with fsync,
  synchronous_commit, and full_page_writes enabled. Secret DSN contents are
  held only in the owner-private mode-600 configuration.

### Reversible LAN configuration

The existing portproxy row was `192.168.1.6:443 ->
172.17.152.10:8444`, but Windows had no active TCP 443 listener. The
owner-approved start helper now refreshes the same row when it is dormant and
fails closed unless the listener appears. It restores a replaced prior row and
removes only a newly created firewall rule if startup fails.

The Windows helper created rule `GS179-Local-LAN-HTTPS` for inbound TCP 443,
local address `192.168.1.6`, remote subnet `192.168.1.0/24`, Wi-Fi
interface, Public profile, and blocked edge traversal. It does not add a
router rule or Internet exposure. The current firewall query from WSL is
limited by Windows administrator-read permissions. The elevated Start
operation successfully created the rule with the exact parameters above;
post-change audit confirmed the listener and forwarding row, while firewall
rule readback remained blocked for the non-administrator WSL token.

Private rollback material is preserved at
`/home/udaybhan/.local/state/ghar-sajag/gs179-laptop/lan-rollback-20261022T103148Z`.
The saved private config is mode 600. To roll back: remove only firewall rule
`GS179-Local-LAN-HTTPS` from an elevated PowerShell prompt; restore
`server.env.before` to
`/home/udaybhan/.config/ghar-sajag/gs179-laptop/server.env` with mode 600;
and remove the newly created
`/home/udaybhan/.local/state/ghar-sajag/gs179-laptop/windows-wsl-target`
marker. The portproxy entry had the same target before this task; removing the
firewall rule restores the prior effective network access. If the forwarding
row itself is intentionally removed, first compare it to the saved
`windows-proxy-audit` snapshot and remove only that exact GS-179 row.
No certificate rollback is required.

### Live and isolated validation

After setup, `code/tools/local/gs179-laptop-server.sh health` reported
PostgreSQL durability PASS, caregiver HTTPS PASS, local backend PASS, and
`LAPTOP_LAN_ENDPOINT_TLS_READY=PASS` with a verified CA/IP-SAN HTTPS request
from WSL through the Windows endpoint. It correctly reported
`PHONE_LAN_REACHABLE=NOT_VERIFIED`. Hub ingress remains implemented but
default-disabled: `HUB_INGRESS_AUTOSTART=DISABLED`,
`HUB_IDENTITY_AUTHENTICATED=NO`, freshness UNKNOWN and
`PERSISTENT_HUB_INGRESS=NOT_CONFIGURED`.

`code/tools/local/gs179-laptop-server.sh browser` returned HOST_SIM_PASS
against the live laptop HTTPS caregiver API. It logged in, read the same
PostgreSQL-backed authorized Home, rendered the existing source-linked
TEST_ONLY event once after reload, and displayed stale source/UNKNOWN
monitoring. EventKey:
`{"physical_device_id":"test-c3-bedroom","logical_node_id":"bedroom","origin_session_id":10,"event_sequence":1}`.
Event kind/room were MOTION/bedroom; provenance was HOST_SIM TEST_ONLY.
This is not a real Node, Hub, phone, or PIR event.

The registered `make -C code gs179-postgres-e2e` run passed **52/52** with
the isolated local PostgreSQL database, including source-linked Node/Hub
HOST_SIM, durable commit/retry/restart/caregiver projection, listener and
authority negatives, runtime lifecycle, and the added dormant-portproxy
regression. The two previously stale browser-helper cases passed directly
(2/2) after updating selectors to the current four-tab navigation and
asserting its current fail-closed UNKNOWN state. The independent focused
`test_gs179_postgres_security.py` suite passed 15/15. Shell and Node syntax
checks and `git diff --check` passed. Initial direct focused invocations
without the repository's backend/support Python paths failed at import time;
the registered Make target supplied those paths and completed successfully.

No phone-side reachability probe, APK installation, S3 authentication,
persistent Hub-ingress activation, customer enrollment, physical board
operation, or PIR stimulus was performed. The current Windows DHCP lease is
short-lived; a stable router reservation or hostname would require separate
network-owner approval if the endpoint changes before phone validation.

### Source-matched local-LAN APK — 2026-10-22

The existing GS-177 Android workflow was manually dispatched with
`backend_origin=https://192.168.1.6` and
`gs179_local_lan_test_only=true` against source commit
`8c134487a4afdde0869aad0e0c5b9c9b19f1b544`.
[GitHub Actions run 39766494060](https://github.com/udaybhan200683/Ghar_sajag/actions/runs/39766494060)
completed SUCCESS. Artifact
[parivar-saathi-caregiver-debug-8c134487a4afdde0869aad0e0c5b9c9b19f1b544](https://github.com/udaybhan200683/Ghar_sajag/actions/runs/39766494060/artifacts/12420842385)
(ID 12420842385, 14-day retention) was downloaded and checked locally.

Artifact contents:

- APK: `parivar-saathi-caregiver-debug.apk`, 2,929,936 bytes,
  SHA-256 `ab61481bbdaf9b8d98b86b0c67ef8b7bdfb10be0605dc4a425f6343de03754f9`.
  `sha256sum --check` and APK ZIP integrity checks passed.
- Package `in.gharsajag.caregiver`, version name
  `0.4.0-connected-lite-staging`, version code 3, existing Parivar Saathi app.
- Origin `https://192.168.1.6`, local-LAN TEST_ONLY enabled, CA SHA-256
  `7152366fdcf6d64d2df6ad2eca86ec6a8a8d60dad43cc7a8738e353fe86eddd5`.
- CI `apksigner` verified one RSA-2048 debug signer. Certificate SHA-256
  `58f9d58042af12a1eca6b4fadd8bb836e3b04220995fb710ad3eac0d1b1972ac`.
  This is a runner-generated debug key, not the installed APK's verified
  signer or a production signing key; an update-signature conflict may require
  uninstall/reinstall and a new sign-in.
- Workflow gates passed: PWA browser/offline 4 tests and 92 rendered cases;
  registered caregiver API 20, Android dashboard 10, and voice prototype 26;
  Android debug unit/build/signature/artifact stages. Validation reported
  SOFTWARE PASS, PHYSICAL NOT_RUN.

The physical phone was not accessed and the APK was not installed. Current
Windows DHCP lease has no confirmed reservation and may change; if it changes,
recheck the certificate/SAN and rebuild against the new verified origin before
phone-side login. No PIN, TLS-validation bypass, or untrusted certificate was
introduced.

A separate live caregiver browser rerun initially got a transient
`route.fetch: socket hang up` on the Windows forwarded `/devices` request while
a read-only proxy audit was also running. The service health/TLS checks stayed
PASS; the browser rerun by itself passed with the same EventKey and no source
change. The transient was not reproduced.

## 2026-10-22 — router-independent TEST_ONLY reconnect implementation

This follow-up adds a reusable reconnect path for the existing laptop host and
Parivar Saathi app. It remains TEST_ONLY and leaves the commercial release
origin and trust configuration unchanged. The Android app can restore a
previously paired `https://<computer-name>.local` origin or use an explicit
private IPv4 fallback in the bundled reconnect flow. It persists the selected
origin, while WebView continues normal TLS hostname and certificate
verification. Address discovery is never treated as authentication. The
caregiver server permits the `.local` HTTPS origin only under its explicit
TEST_ONLY LAN setting.

The Windows helper now reads the active Wi-Fi IPv4 and current WSL2 address and
can retarget only its owned portproxy/firewall configuration. A bounded,
opt-in watcher is available for operator activation but was not registered:
the current Windows session is not elevated. No broad firewall rule, router
change, server restart, or phone operation was performed.

At final read-only inspection, Windows was connected to `Airtel_Agrim` at
`192.168.1.8/24` and WSL2 was `172.17.152.10`. PostgreSQL, caregiver HTTPS and
local service checks were healthy. The existing Windows portproxy still
targeted the previous `192.168.1.6`, so
`LAPTOP_LAN_ENDPOINT_TLS_READY=FAIL`; phone reachability remains NOT_VERIFIED.
The server certificate covers the stable computer-name `.local` origin. The
stale route was left unchanged to preserve the live network/server state. No
phone-side Yogi → Agrim → Yogi test has been performed.

Focused validation on this source passed: PWA runtime JS 10/10; caregiver API
22/22; GS-179 security 18/18; source-linked GS-179 PostgreSQL E2E 55/55;
GS-177 connected-lite runner (22 API tests, 10 JS tests, 3 source scenarios,
10 runtime checks); validation framework 51/51; feature coverage and
traceability; PWA browser 4/4 tests and 92/92 rendered checks; and GS-178
caregiver integration 33/33. Python, Node, shell and JSON syntax checks and
`git diff --check` passed. The broader backend/PWA aggregates retain the
existing mandatory P0 `product_status=PARTIAL`, diagnostic-foundation's
stale-stage registration assertion, and an initial offline-browser attempt
that lacked the Python `websocket` dependency; the isolated browser target
passed after that dependency was supplied outside the repository. These
results were not suppressed or altered. Local Gradle and ADB are unavailable,
so the updated combined APK was not built. Physical phone, Hub and PIR
validation remain NOT_RUN.

This is the Wi-Fi source checkpoint only. GS-177 UX commit integration is
deferred until this checkpoint is committed and pushed. Starting local and
remote HEAD was `aeb2ab52a4f1c0e286817b77026d4fe13f03580b`; pre-existing
untracked and ignored assets remain preserved.

## 2026-10-22 — owner-reported Android connectivity regression

The owner installed the combined TEST_ONLY APK from workflow 39797650882 and
reported caregiver login `Failed to fetch` on both Yogi and Agrim. The previous
IP-origin APK had connected on Yogi. This supersedes the earlier statement that
phone-side testing was NOT_RUN: an owner-operated phone login attempt was made
and failed. It does not establish a real Hub or sensor event.

### Current read-only state and isolation

- Canonical source is `feature/r1-commercial-baseline` at
  `7d352118e37681be036c0d410ea0e4df27be53bc`, equal to the remote at the start
  of this check. Context preflight passed. The tracked tree was clean; existing
  untracked/generated assets were left untouched.
- Windows reports Wi-Fi profile `Airtel_Agrim`, category `Public`,
  `192.168.1.8/24`. WSL2 is `172.17.152.10`. The existing portproxy row remains
  `192.168.1.6:443 -> 172.17.152.10:8444`. The WSL service and PostgreSQL are
  active. PostgreSQL is loopback-only on 55432 and its verified TLS/durability
  health check passes.
- `gs179-laptop-server.sh health` reports PostgreSQL and caregiver HTTPS
  ready locally, but its Windows-LAN TLS probe times out at the current `.8`
  address. It reports phone reachability NOT_VERIFIED and Hub ingress
  default-disabled. This is not a claim of physical monitoring availability.
- The current leaf certificate chains to the same TEST_ONLY CA embedded in the
  installed APK (CA file SHA-256
  `7152366fdcf6d64d2df6ad2eca86ec6a8a8d60dad43cc7a8738e353fe86eddd5`). The
  leaf has DNS SAN `desktop-3qqu64b.local` and IP SAN `192.168.1.6`; its DNS
  name verifies locally, but its IP SAN does not cover current Agrim address
  `192.168.1.8`. A wrong TLS hostname is rejected. No TLS verification was
  bypassed. Refreshing the leaf for `.8` was not performed because the Windows
  forwarding operation that makes the route usable requires an elevated
  Windows token.
- Windows `Resolve-DnsName desktop-3qqu64b.local` currently returns A records
  `172.17.144.1` (the WSL virtual-network gateway) and `192.168.1.8`, plus
  link-local IPv6 records. WSL `getent hosts desktop-3qqu64b.local` returned no
  result, and the existing browser helper failed at name resolution before
  login. The actual Android resolver-selected address was not captured, so
  these are concrete risks for the `.local` path, not proof of the phone's
  selected address.
- Android source inspection confirms `BackendOrigin` accepts the configured
  `.local` host and `TrustedPwaWebView` loads it as the WebView origin; the
  reconnect flow preserves normal TLS hostname validation. There is no app
  `NsdManager`/DNS-SD resolver in this path, so `.local` resolution is delegated
  to Android's platform/WebView resolver. This identifies a plausible boundary
  for the phone failure, but does not prove what address or resolver error the
  handset observed.
- A direct WSL TLS probe to the caregiver listener used the `.local` SNI and
  hostname verification with the pinned TEST_ONLY CA. Login through the
  existing caregiver API succeeded for the owner-only TEST_ONLY fixture; the
  same authorized Home overview returned the single pre-existing PostgreSQL
  EventKey exactly once, and a different Home was denied. The API reported
  source freshness `STALE` and monitoring `UNKNOWN`. The diagnostic logged out
  its temporary session. The event is existing HOST_SIM/TEST_ONLY data, not a
  real household or sensor event.
- `test_connected_lite.py` ran 22/22 PASS. Its fixtures are isolated. The
  direct WSL API probe above used the running local service and database, but
  did not traverse Windows portproxy or the phone.

### Operations not performed and exact remaining steps

The current Windows token is not an administrator. The helper audit could not
read the firewall rule, and no portproxy/firewall/certificate/service change
was made. The existing helper's network watcher also remains unregistered. Its
scheduled task runs with `HighestAvailable` at logon and every generic
NetworkProfile-connected event; the `Watch` path accepts any RFC1918 Wi-Fi
profile and has no allowlist for owner-trusted networks. It is not safe to
register as-is under the requirement to fail closed on untrusted networks.
Until a trusted-network policy is supplied and enforced, use an elevated
one-time refresh only while connected to an owner-approved Wi-Fi:

```bash
code/tools/local/gs179-laptop-server.sh network-refresh
```

Run it from the canonical WSL distro launched by an elevated Windows Terminal;
first verify that the helper's Windows PowerShell child reports an
administrator token. This refreshes the current TEST_ONLY certificate SAN and
private server origin, restarts the WSL service, and updates only the existing
GS-179 Wi-Fi/subnet-scoped forwarding/firewall rule. Require
`LAPTOP_LAN_ENDPOINT_TLS_READY=PASS` before testing the phone. Repeat the
one-time refresh after each Yogi/Agrim switch until a safe, explicitly approved
watcher exists.

After the route is ready, test from the phone's Chrome browser first at
`https://desktop-3qqu64b.local/readyz`; require the ready JSON without a
certificate warning. If name resolution fails, use the APK's **Reconnect to
laptop server** action and enter the current Windows Wi-Fi IPv4 as an HTTPS
private-IP origin only after the helper has placed that exact IP in the leaf
certificate SAN. Never bypass a certificate error. Then log in and confirm the
authorized Home loads. Repeat Yogi → Agrim → Yogi with the same installed APK;
run the elevated one-time helper refresh at each Wi-Fi transition, and record
the displayed endpoint and phone outcome. No phone OS/device logs or screenshots
were captured by this WSL session.

The installed artifact remains workflow 39797650882, APK SHA-256
`5aaea3c6f71e1d60b401436d987fb50633c4766ba4e7318384e077ad7f0bd02f`, package
`in.gharsajag.caregiver`, version `0.4.0-connected-lite-staging`, origin
`https://desktop-3qqu64b.local`. No APK rebuild or reinstall is presently
indicated; the reported failure needs route and resolver isolation first.

## 2026-10-22 — TEST_ONLY DNS-SD discovery and Android secure reconnect

The latest owner phone report (GS-177 comment 11583) corrects the prior phone
failure: on Agrim, the same installed TEST_ONLY APK logged in and loaded its
authorized Home after the owner selected `https://192.168.1.8` through the
existing reconnect control. This proves the current-IP HTTPS fallback and
caregiver API path on that phone. The `.local` route failed, and Android
automatic discovery plus Yogi → Agrim → Yogi remain unverified.

The source change adds a TEST_ONLY-only Windows DNS-SD advertisement for the
current HTTPS listener and foreground Android NSD discovery. Android accepts
DNS-SD only as a locator: it probes a private IPv4 endpoint using the platform
trust store, default IP-hostname verification, the exact configured
`desktop-3qqu64b.local` certificate SAN, a persisted SPKI continuity pin after
first success, no redirects, and the existing bounded `/readyz` response with
PostgreSQL reachable. It stores the IP endpoint only after those checks, then
reopens the same PWA/WebView origin. No identity headers, TLS override, new
backend, or production profile change is introduced. Discovery is foreground
and Wi-Fi only; each generation probes no more than four distinct private
addresses, keeps at most two DNS-SD resolves pending, uses 3.5-second connect
and read timeouts, and reads at most 4096 readiness bytes. A stale probe cannot
persist its IP after a Wi-Fi generation change.

The Windows advertiser is a non-privileged process started with the existing
explicit `GS179_LOCAL_LAN_TEST_ONLY=1` laptop-server command. It only registers
the existing service when active Wi-Fi is classified by Windows as `Private`
or `DomainAuthenticated`, has an RFC1918 address, and already has the HTTPS
listener. `Public` and unknown Windows profiles fail closed. The current
read-only Windows profile is `Airtel_Agrim / Public`, so the advertiser will
not publish until that owner-trusted Wi-Fi is classified as Private. The
existing elevated network watcher remains unregistered: route, forwarding,
firewall and current-IP certificate refresh still require its separately
approved trusted-network lifecycle. The stale owned `192.168.1.6:443` mapping
remains a separate cleanup issue; the current `192.168.1.8:443` mapping to
WSL `172.17.152.10:8444` and listener were present during read-only recheck.

Validation on source before delivery:

- GS177 Android runner source/policy marker: `GS177-LAN-NSD-001 SOURCE_PASS`.
- Existing PWA runtime: 10/10 PASS.
- Windows PowerShell DNS-SD construction and policy validation: 13/13 policy
  assertions PASS; DNS-SD record construction PASS; no socket or registration
  opened.
- `make -C code feature-coverage-test`: PASS, 225 feature rows, 280 source
  modules, 26 physical cases; 22/22 framework tests.
- Shell syntax, Python compilation, `suites.json` parse, and `git diff --check`:
  PASS.
- The full local Android runner exits 127 after source checks, branding, and
  PWA tests because Gradle/Android SDK are absent from WSL. The registered CI
  Android unit/build stage is required to compile the new Kotlin and produce
  the TEST_ONLY APK. No phone NSD test, Wi-Fi switch, forwarding/firewall
  mutation, or persistent watcher registration was performed.

Current laptop API/TLS health checks pass from WSL; Windows IP is
`192.168.1.8/24`, WSL is `172.17.152.10`, and Windows reports listeners on
`.8:443` and the historical `.6:443`. This does not prove the phone's mDNS
visibility. The real phone result remains IP-fallback PASS only. A new APK build
will be needed because the Android source changed, but CI signing compatibility
with the installed build must be checked before installation. If the server
address changes, caregiver login may be required again because HTTPS cookies
are origin-bound.

### Same-origin route recovery correction

The Android activity now observes `ConnectivityManager.NetworkCallback` link
properties as well as default-network changes. It restarts bounded NSD discovery
when the active Wi-Fi network or its address/route signature changes. After a
candidate passes HTTPS CA validation, the current IP SAN, the expected laptop
DNS SAN, the persisted SPKI continuity check and database readiness, it reloads
the caregiver WebView when either the endpoint or Wi-Fi route changed. This
handles a route transition that retains the same private IP; simply foregrounding
the app on an unchanged network does not force a reload. JUnit coverage was
added for this same-origin route transition. CI Android compilation and actual
phone DNS-SD/Yogi → Agrim → Yogi validation remain pending.

The follow-up validation on this source re-ran the PWA JS tests (10/10), the
GS-179 local Android source/policy checks, Windows DNS-SD policy/record
construction validation (13 policy cases; no registration or socket), the
feature traceability suite (22/22), shell/Python/JSON syntax checks and
`git diff --check`. The registered runner reaches its Android stage but exits
127 because Gradle and Android SDK are absent in WSL. No APK was built or
installed during that local run.


### CI/APK and owner-verification addendum — 2026-10-22

The source push at `8ca19768ea3da392d2badbb8b9e9077702bc54dc` triggered GS-177
workflow 39821567855, which passed its registered PWA and Android stages. The
separate local-LAN workflow 39822389037 was dispatched with
`backend_origin=https://desktop-3qqu64b.local` and
`gs179_local_lan_test_only=true`. Its first attempt failed before Android
build because Chromium DevTools did not start in two pre-existing browser cases;
the same run's failed job was retried, and attempt 2 passed:

- `make pwa-68-browser-test`: 4 browser tests; 92/92 rendered cases PASS.
- `python3 validation/component_gate.py --suite caregiver-app`: API 22,
  Android dashboard 17, voice prototype 28; all registered stages PASS.
- Android `:app:testDebugUnitTest :app:assembleDebug`: PASS.
- APK signature verification and uploaded SHA-256 evidence: PASS.

Artifact: [workflow 39822389037](https://github.com/udaybhan200683/Ghar_sajag/actions/runs/39822389037),
artifact `parivar-saathi-caregiver-debug-8ca19768ea3da392d2badbb8b9e9077702bc54dc`,
available through 2026-11-05. Build metadata says package
`in.gharsajag.caregiver`, version `0.4.0-connected-lite-staging`, TEST_ONLY
origin `https://desktop-3qqu64b.local`, CA SHA-256
`7152366fdcf6d64d2df6ad2eca86ec6a8a8d60dad43cc7a8738e353fe86eddd5`.
APK SHA-256 is
`b54d0ebd45653d2e085be1deaaf5686c5d73802f05fbaaeb7338e1315f8084c3`.
Signer certificate SHA-256 is
`8caa922ccf7efae2337ba8d63780d12a0d2935bba3f10872b0466f51330eed11`.
The prior installed workflow 39797650882 signer was
`141f15cdaec4645094cb0657956f8b82110f2f4eccfda61a9b5260052e111392`;
the signatures differ, so this artifact cannot update that installation in
place. It was not installed; do not uninstall/clear the owner's app without
approval.

A documentation synchronization check initially failed because the GS179-LAN-01 row command and assertion anchor diverged from the registered suite/source. The row was corrected to the three registered commands and the source test marker; `make -C code feature-coverage-test` then passed (225 features, 280 modules, 26 physical cases; 22/22 mapping tests). The failed first check was preserved here rather than hidden.

The owner separately reports that the already-installed APK connects on Agrim,
logs in and loads authorized Home using the manual IP fallback
`https://192.168.1.8`. This is phone PASS for IP fallback only. Automatic
DNS-SD, unchanged-APK Yogi → Agrim → Yogi switching, and phone use of this new
APK remain NOT_RUN. No IP, forwarding, firewall, Windows network profile,
certificate, or listener configuration was changed as part of source
validation/build. Current Windows Public profile and unregistered privileged
network watcher still prevent claiming operational automatic discovery.

### Watcher fail-closed guard and focused regression — 2026-10-22

Added a Windows profile check before registering the privileged reconnect
watcher and before its `Start`/`Watch` forwarding or firewall mutations. Only
`Private` or `DomainAuthenticated` profiles with bounded RFC1918 Wi-Fi
addresses are accepted. This prevents a persisted task or network changes on a
Public/Unknown Wi-Fi profile. No watcher was registered and no Windows network
state was changed.

Separated writing the current WSL target from starting the DNS-SD advertiser.
The watcher now starts the advertiser explicitly after it records the target;
this keeps the state-recording command independently testable and preserves
the runtime sequence. `LaptopServiceLifecycleBoundary` passed 11/11 after this
correction. `make -C code feature-coverage-test` passed 22/22 (225 feature rows,
280 modules, 26 physical cases); Bash parsing, Windows PowerShell parser, and
`git diff --check` passed.

The preceding `make -C code gs179-postgres-e2e` run executed 55 tests and had
one failure in `test_proxy_target_recorder_accepts_only_wsl_nat_addresses`:
the test fixture did not create the private server configuration newly
required when that command also launched DNS-SD. The command was then split as
described above, and the complete 11-test laptop lifecycle class passed. The
full 55-test suite was not repeated. The remaining test evidence is software
only; automatic phone DNS-SD and Yogi → Agrim → Yogi remain unverified.

### 2026-10-23 — DNS-SD result, combined APK and physical-test handoff

Latest owning Jira: GS-179 (In Progress). Canonical branch:
`feature/r1-commercial-baseline`; code source HEAD and verified origin HEAD at
the start of this handoff: `dce8a52e6a294c40d6f8fe949430418c54042a3c`.
Tracked source changes are committed; pre-existing unrelated untracked files
and evidence remain preserved. The documentation/artifact checkpoint is being
committed and pushed separately after this update.

Windows TEST_ONLY advertiser status was read without restarting the worker:
PID 4280, `REGISTERED`, `DnsServiceRegister` API return 9506
(`DNS_REQUEST_PENDING`), callback status 0, service
`GharSajag-GS179-desktop-3qqu64b._https._tcp.local` at `192.168.1.8:443`,
interface 18. This proves Windows DNS-SD registration completion, not
multicast delivery to Android. Wi-Fi remains Private. The persistent privileged
network watcher is not registered.

The combined Local-LAN TEST_ONLY workflow
[39887837848](https://github.com/udaybhan200683/Ghar_sajag/actions/runs/39887837848)
completed SUCCESS on source `dce8a52e`. Browser assertions passed 92/92;
registered API/Android-dashboard/voice gates passed 22/19/28; Android unit
tests and APK build passed; signature/upload passed. The verified APK is at
`docs/exec-plans/evidence/GS179_DNSSD_AUTODISCOVERY_20261023/apk/`, SHA-256
`0ae141221233ba39a997396bb496a818250668ccf1b4d354372dad5add630c80`, signer
SHA-256 `61710682d9c43052a1e1f07dbe6fef7ae7671391d82335d91b61bd0cf3a564cf`,
origin `https://desktop-3qqu64b.local`, CA SHA-256
`7152366fdcf6d64d2df6ad2eca86ec6a8a8d60dad43cc7a8738e353fe86eddd5`.
Artifact ID `12473876313`, 14-day Actions retention. The installed phone
package signer was not inspected, and the candidate uses a runner-generated
debug key, so update compatibility is unverified. No installation,
uninstallation, data clear or phone access occurred.

Physical acceptance remains NOT_RUN: Android discovery visibility, service
resolution/TXT acceptance, secure readiness, and Yogi → Agrim → Yogi have not
been observed on the handset. No ADB/device is available in this environment.
The latest app change preserves the working saved manual-IP origin and SPKI pin
when “Use paired laptop” is tapped; automatic discovery replaces the origin
only after the existing CA/IP-hostname, expected DNS SAN, SPKI continuity and
`/readyz` checks pass. TEST_ONLY logs now expose each discovery, validation,
storage and delivery failure stage. Preserve certificate verification and
manual-IP connectivity.

Next exact action: owner confirms a signer-compatible route for the delivered
APK without removing the working app or clearing data. Then run phone browse,
resolve and Yogi → Agrim → Yogi checks while capturing `ParivarSaathiLan` logs;
record the actual phone visibility result separately from the Windows callback
and hosted CI. Do not activate the privileged watcher, mutate firewall or
forwarding, or claim physical acceptance from software results.
