# Parivar Sathi v3.4.2 — release-gate stability

This patch does not change product logic, battery analytics, dashboard behavior,
or the 92 canonical functional scenarios.

It fixes two release-gate infrastructure races seen on Windows/WSL paths:

1. `http-integration`
   - HTTP test server now uses the same threaded WSGI server as the local lab.
   - Per-request timeout is increased from 15 s to 45 s for slower `/mnt/*`
     filesystems and heavily loaded release-gate runs.

2. legacy `browser-e2e`
   - Replaces the fixed 1.2 s sleep with an actual HTTP readiness probe.
   - Waits up to 60 s for `/lab`.
   - Captures server startup output in `evidence/release_gate_v1.5.4/browser-e2e-server.log`.
   - Browser test timeout increased to 180 s.

The mandatory 22-test Playwright PWA gate remains unchanged.
