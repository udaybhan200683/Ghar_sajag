# Parivar Sathi v3.3.2

Fixes a validation-only state leak that could leave the live PWA showing a
synthetic final test state after `make playwright-gate` or "Run all".

It also separates:
- morning routine **pending/not completed yet**
from
- actual **MISSING_MORNING_ACTIVITY** care concern.

The main care banner now follows the backend/rule-engine `care.alert` only.
"Run all" and Playwright cleanup restore the dashboard to Reset/PASS.
