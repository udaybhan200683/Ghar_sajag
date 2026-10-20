# GS-177 / GS-179 connected Home event visibility — 2026-10-20

## Result

The authenticated Connected Lite Home now follows the established Parivar
Saathi PWA home composition (overview hero, summary cards and activity timeline)
while reading only the current session's authorized GS-148 caregiver
projection. Devices, Reports, Settings and the other existing tabs remain in
the application. The navigation strip is docked directly below the header and
spans the viewport; it no longer uses the floating-pill treatment.

The live laptop fixture currently contains one committed GS-178 event from the
`test-c3-bedroom` HOST_SIM source. The Home displayed that existing event with
its EventKey, original room/time and `HOST_SIM · TEST_ONLY` provenance. The
observation did not insert or replay an event. The source was stale, so Home
reported monitoring and Node state as UNKNOWN even though the stored device
response included ONLINE/COVERED. The caregiver account was correctly denied
the Engineering endpoint (HTTP 403), and the Engineering tab remained hidden.

This is a software/browser integration result, not evidence of physical Node
motion, current physical Hub health, or Android phone behavior.

## Implementation

- `code/tools/sim/pwa/connected_lite.mjs` renders the authenticated Home from
  the session-bound overview, device, routine and incident APIs; it rejects
  mismatched Home/test-only projections and unrecognized source provenance.
- `code/tools/sim/pwa/caregiver.css` docks the accessible full-width tab strip
  below the app header, preserving safe-area padding, horizontal overflow,
  scrolling and selected-tab indication.
- `code/tests/pwa_68_browser_test.py` covers the Home projection, stale-source
  downgrade, source provenance, reload/idempotency, tab behavior and rejection
  of simulator fallback.
- `code/tests/js/caregiver_runtime.test.mjs` checks runtime markup/API wiring.
- `code/tools/local/gs179_laptop_browser.py` and
  `code/tools/local/gs179_laptop_caregiver_browser.cjs` exercise the live
  laptop API and confirm actual account permissions without changing them.
- `code/validation/suites.json`,
  `docs/validation/MASTER_TRACEABILITY.csv` and
  `docs/validation/SOURCE_FEATURE_INVENTORY.csv` register the focused case.

The account's effective role is CAREGIVER. The server requires ADMIN plus the
TEST_ONLY flag for the existing Engineering screen and returns 403 for this
account. No account role, permission or backend policy was changed. A separate
owner decision is required before granting the existing account the
TEST_ONLY Engineering permission.

## Validation

- `node --check code/tools/sim/pwa/connected_lite.mjs` — PASS.
- `node --check code/tools/local/gs179_laptop_caregiver_browser.cjs` — PASS.
- `python3 -m py_compile code/tools/local/gs179_laptop_browser.py code/tests/pwa_68_browser_test.py` — PASS.
- `node --test code/tests/js/caregiver_runtime.test.mjs` — PASS, 8/8.
- `make -C code pwa-68-frontend-test` — PASS, 1/1.
- `make -C code pwa-68-browser-test` — PASS, 4/4 tests; 92/92 catalogue
  assertions, including the new authenticated Home case. The command used the
  already-installed cached Chromium and an isolated temporary
  `websocket-client` dependency; no repository dependency or lockfile changed.
- Registered `gs177-caregiver-offline-browser` component adjudication — PASS;
  all four required-success markers were present.
- `code/tools/local/gs179-laptop-server.sh browser` — PASS as
  `HOST_SIM_PASS`; live authenticated PostgreSQL-backed projection showed the
  existing single HOST_SIM row, stale/UNKNOWN status and HTTP 403 for
  Engineering. The browser logged out at completion.
- `make -C code feature-coverage-test` — PASS; 217 features, 257 source
  modules, 25 physical cases and 22/22 mapping tests.
- Local Android assembly was attempted with the existing TEST_ONLY LAN profile.
  PWA runtime checks passed 8/8; APK assembly stopped with exit 127 because
  Gradle is not installed in this WSL environment. The existing Android Actions
  workflow then succeeded as run 39371372388 on evidence commit
  `5a7a10965e8734bfff567d362e7254845a1633f1`. It produced a 2,914,926-byte
  debug APK with SHA-256
  `d36eab8982a655fbb6678eb7124c46c3e289b8681beb4b0452ead1809c14eab1`
  (artifact 12241890946). Its metadata shows
  `GS177_LOCAL_LAN_TEST_ONLY=0` and the default Render origin, so this artifact
  is not suitable for reading the owner's laptop PostgreSQL event and should
  not be installed for this task. It is build/signature evidence only. The
  WSL-bound HTTPS listener passed its
  certificate-verified `/readyz` check, but the existing Windows Wi-Fi HTTPS
  forwarding endpoint on port 443 refused the connection. Thus the configured
  laptop LAN APK origin is not presently reachable from a phone. A refreshed
  local-LAN APK can be built by the existing Android Actions workflow after
  restoring the pinned endpoint or completing an approved TLS/origin rotation.
  No forwarding or firewall rule was changed in this task. Owner-phone
  installation and acceptance remain NOT_RUN.
- `git diff --check` — PASS.

The backend record and physical evidence were read only; no synthetic event
was added for this test. The test's mocked browser case validates projection
semantics; the separate live laptop check validates only the pre-existing
HOST_SIM database row.

## Remaining source-to-caregiver gaps

- **GS-40:** No real C3 authenticated contact/NodeHealth or S3 product-runtime
  publication was observed in this run. Actual target image, current trusted
  time/Hub authority and a physical run remain required.
- **GS-58:** Current evidence does not show a physical Hub's test-only Wi-Fi
  provisioning/recovery as an end-to-end input to the laptop service.
- **GS-68 / GS-109:** Real Hub credential, current ownership/Home epoch,
  signed-time trust and Node enrollment/session must be valid for any target
  publication. Commercial issuance and DS/eFuse approvals are separate and
  remain outside this software change.
- **GS-148 / GS-59:** The durable caregiver read model and existing HOST_SIM
  mTLS path are usable. No persistent application-terminated mTLS listener
  carrying a physical Hub's commits is currently connected to this laptop
  service.
- **GS-117:** Physical C3 sensor → S3 Hub → backend COMMITTED → caregiver case
  remains NOT_RUN. It requires explicitly authorized, image-verified C3/S3
  fixtures with current enrollment and the approved authentication ingress.
- **Engineering:** The existing route works for ADMIN+TEST_ONLY only. The
  current caregiver account is least privilege; no elevation was made.

The installed phone, C3, S3 and C8 were not accessed. No serial port, reset,
firmware flash, database write, account change or production service was used.
The Windows port-forwarding path is a separate GS-179 laptop-host availability
issue; the evidence does not claim that the current Home UI was exercised on
the physical phone during this task.
