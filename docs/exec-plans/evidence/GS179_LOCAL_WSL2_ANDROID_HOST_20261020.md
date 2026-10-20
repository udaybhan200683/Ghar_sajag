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
