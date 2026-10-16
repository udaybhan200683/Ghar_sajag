# Ghar Sajag v1.5.4 Release Gate

**Host/software result: PASS**

| Stage | Result | Seconds |
|---|---:|---:|
| validation-coverage | PASS | 0.04 |
| contracts | PASS | 0.04 |
| cpp-unit | PASS | 6.71 |
| master-production-runtime | PASS | 5.87 |
| fota-host-state-machine | PASS | 4.46 |
| javascript-app | PASS | 0.29 |
| product-base | PASS | 0.88 |
| product-ai | PASS | 0.93 |
| lab-build | PASS | 3.73 |
| python-backend-db-logging | PASS | 22.95 |
| dummy-sensor-streams | PASS | 0.75 |
| functional-catalog | PASS | 12.16 |
| http-integration | PASS | 13.31 |
| pwa-bridge | PASS | 6.21 |
| pwa-68-api | PASS | 12.75 |
| pwa-68-frontend | PASS | 13.66 |
| browser-e2e | MANUAL_REQUIRED | 0 |

## Boundary

A PASS means the hardware-independent host/software release gate passed. It does **not** certify physical ESP32/RF/power behaviour. Those gates remain pending until hardware is available.

Manual browser/PWA cases are in `tests/MANUAL_FUNCTIONAL_VALIDATION.md`. Use `--require-browser` when Playwright is installed so the browser test becomes mandatory.

