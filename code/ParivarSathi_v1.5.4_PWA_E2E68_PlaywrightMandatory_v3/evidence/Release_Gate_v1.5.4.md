# Ghar Sajag v1.5.4 Release Gate

**Host/software result: PASS**

| Stage | Result | Seconds |
|---|---:|---:|
| validation-coverage | PASS | 0.23 |
| contracts | PASS | 0.28 |
| cpp-unit | PASS | 53.1 |
| python-backend-db-logging | PASS | 5.72 |
| javascript-app | PASS | 2.85 |
| product-base | PASS | 3.92 |
| product-ai | PASS | 2.91 |
| feature-p0-default-clean | PASS | 0.05 |
| feature-p0-default | PASS | 45.96 |
| feature-routine-disabled-clean | PASS | 0.05 |
| feature-routine-disabled | PASS | 53.64 |
| feature-call-disabled-clean | PASS | 0.04 |
| feature-call-disabled | PASS | 49.87 |
| feature-offline-disabled-clean | PASS | 0.04 |
| feature-offline-disabled | PASS | 49.19 |
| lab-build | PASS | 61.08 |
| dummy-sensor-streams | PASS | 8.32 |
| functional-catalog | PASS | 6.27 |
| http-integration | PASS | 13.9 |
| pwa-bridge | PASS | 5.36 |
| pwa-68-api | PASS | 6.53 |
| pwa-68-frontend | PASS | 7.43 |
| cpp-sanitizers | PASS | 78.35 |
| trace-build | PASS | 46.83 |
| browser-e2e | MANUAL_REQUIRED | 0 |

## Boundary

A PASS means the hardware-independent host/software release gate passed. It does **not** certify physical ESP32/RF/power behaviour. Those gates remain pending until hardware is available.

Manual browser/PWA cases are in `tests/MANUAL_FUNCTIONAL_VALIDATION.md`. Use `--require-browser` when Playwright is installed so the browser test becomes mandatory.

