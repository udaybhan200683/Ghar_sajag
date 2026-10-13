# GS-125 post-ENOSPC backend/PWA validation — 2026-10-13

## Environment and source

- Dashboard branch: `feature/gs124-125-engineering-dashboard`
- Source HEAD: `aa7b19b13cef2d9c75096ab410c635e967671e90`; local and remote were equal before validation.
- Source fingerprint: `195c3a82e7ceaf075d9edc4f8b087bc69f0be6c508476babc7f2130522d97965`; backend and PWA match, `source_unchanged=true`, `tracked_dirty=false`.
- Build profile is identical in both reports: host compiler `d3c02c2eb999e2ce`, Python `3.14.4 (main, Aug 20 2026, 10:41:58) [GCC 15.2.0]`, portable crypto fingerprint `ad5008d86e3a337d12bed44ce4e8d983db842db83ef0f245d6db69fb8b74bbd0`.
- `/tmp` began with 1,080,057,856 bytes free (47% used); sampled during both runs and remained about 1.08 GB free. No ENOSPC occurred.
- GS-152 archives, worktrees, symlinks, and untracked `managed_components` were preserved. GS-148 canonical worktree was not modified.

## Aggregate results

| Command | Aggregate | Make exit | Stages |
|---|---|---:|---|
| `make validation-backend` | **FAIL** | 2 | 14 PASS, 1 FAIL |
| `make validation-pwa VALIDATION_REUSE_REPORTS=evidence/validation_framework/backend-1791907554777890475/report.json` | **FAIL** | 2 | 11 PASS, 1 FAIL; 10 backend PASS receipts reused, JS and P0 freshly executed |

Backend ran all stages fresh. Its full Python stage passed **449 tests, 1 allowed historical skip**; the durable-before-ACK CloudSync test passed. The `diagnostic-foundation` stage passed **84/84**. PWA ran JavaScript fresh: **23 passed**, and reused only same-source/profile backend PASS receipts whose commands, logs and artifacts were verified by `component_gate.py`.

Both aggregates fail only at `p0-full-product-e2e`. All **26/26 scenarios** and **1 Chromium browser test** passed, including initial file-backed Node recovery and the production-shaped CloudSync-to-durable-API flow. The stage command exited 0, but the registered `require_complete_product` adjudication correctly marks it FAIL because the report says `product_status=PARTIAL`. The exact product gap in the native P0 report is: “GS-148: production Hub TLS/credential authenticator and enrollment-generation registry binding are not configured; local test credential only.” This is a remaining production integration/qualification gap, not an ENOSPC or Node-recovery assertion failure. No assertion or source was changed.

Other limits: physical qualification `NOT_RUN`; release approval false. This does not qualify GS-76/143 identity, production PostgreSQL, authenticated service PWA routes, trusted diagnostic source, or hardware.

## Native receipts and logs

- Backend native report: [`backend-report.json`](backend-report.json); byte-exact stage logs: [`backend-stage-logs.tar.gz`](backend-stage-logs.tar.gz).
- PWA native report: [`pwa-report.json`](pwa-report.json); byte-exact stage logs: [`pwa-stage-logs.tar.gz`](pwa-stage-logs.tar.gz).
- Aggregate console outputs: [`backend-console.log.gz`](backend-console.log.gz), [`pwa-console.log.gz`](pwa-console.log.gz).
- Full P0 scenario report: [`p0_product_e2e_report.json`](p0_product_e2e_report.json).
- `SHA256SUMS` covers all receipt files. Each raw stage log inside the tarballs was independently checked against its native `report.json` `log_sha256`.

Native report JSON records each stage's command, status, exit, count, duration, log hash, reuse source, source fingerprint and build profile. Console outputs record aggregate runner/make exits.
