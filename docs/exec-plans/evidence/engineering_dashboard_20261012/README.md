# GS-122 dashboard campaign review package

2026-10-12 UTC. Delivery branch `feature/gs124-125-engineering-dashboard`;
isolated worktree `/home/udaybhan/projects/Ghar_sajag_r1_dashboard`.
Committed production baseline `77e29d44c57f0851f78358049c288323c985d2e7`.
Final pushed commit/actual remote verification is recorded in the ZIP's
DELIVERY_CHECKPOINT.json. No merge into canonical GS-148 has occurred.

**Design PROPOSED. Production implementation/qualification BLOCKED_DESIGN_APPROVAL.**
The completed architecture and inactive preparation are available for review.
Explicit GS-120 acceptance is still required by GS-124/10622. A design approval
alone cannot invent technician grants, retention, installation PASS policy or
authenticated target export. OPEN_DECISIONS_AND_BLOCKERS.md lists all gates.

## Contents and review order

1. `docs/architecture/GS120_ENGINEERING_DASHBOARD_ARCHITECTURE.md`: full proposed
   architecture, seven screens, ordinary additions and approval-sensitive contracts.
2. GS124_IMPLEMENTATION_REPORT.md and GS125_VALIDATION_REPORT.md: delivered scope,
   independently reported qualification states, exact tests and failed attempts.
3. DIAGNOSTIC_INTERFACE_MATRIX.csv and SOURCE_INVENTORY.csv: production provenance,
   missing interfaces and source anchors/hashes.
4. FEATURE_TO_TEST_MATRIX.csv, SIMULATION_ACCEPTANCE_MATRIX.csv,
   HIL_ACCEPTANCE_MATRIX.csv and HIL_OPERATOR_PLAN.md: proposed acceptance,
   current blocked execution/registry status, actual runner limitations.
5. `review.html`, REVIEW_FIXTURE.json and desktop/mobile screenshots: inactive
   seven-screen review. Saved fixture came from actual production host serializer,
   durable local API and caregiver query. Nine trace stages remain UNKNOWN.
6. Preparation source under `code/tests/support/engineering_dashboard_review/`;
   logs, TEST_EXECUTION_RECEIPT.json, source fingerprints and package manifest.
7. CAMPAIGN_HANDOFF.md, sanitized Jira intake and Git snapshots for exact resume.

The ZIP preserves repo-relative paths. It excludes SQLite databases, node_modules,
credentials, raw physical logs, managed components and compiler output. Failed
attempt logs are retained alongside final successful logs. Source/log hashes
verify shipped evidence; they do not prove physical or semantic coverage.

## Actual outcomes

| Scope | Outcome |
|---|---|
| Inactive model/API preparation | PASS: 45 tests (37 model + 8 real API tests) |
| Existing production board-stack host simulation | PASS: 8 groups / 325 checks; physical NOT_RUN |
| Inactive browser review | PASS: 20 desktop/mobile checks |
| Existing framework / no-port HIL safeguards | PASS: 39 + 17 tests |
| Focused existing API/ownership/health readiness | PASS: 29 tests after lab prerequisite |
| Activated product dashboard / technician authentication | BLOCKED_DESIGN_APPROVAL / missing verified grant contract |
| New permanent registry integration | BLOCKED; all proposed IDs DRAFT_NOT_REGISTERED |
| Board / motion / physical product E2E | BLOCKED_GS114_NO_GO; NOT_RUN |
| Full release gate and complete component gates | NOT_RUN; no release or production activation |

Preserved product gaps: GS-148 historical `clean migration commits` FAIL,
GS-130 full P0 PARTIAL/gate FAIL, commercial trust/deployment and live target
observation export. Successful local SQLite tests do not qualify these.

## Reproduce inactive preparation

Use the isolated worktree, not canonical GS-148. These steps compile host code and
use local test databases/loopback only; they do not open serial interfaces. They
are preparation commands, not product qualification targets. Do not use legacy
HIL smoke/regression commands, which flash boards.

```bash
cd /home/udaybhan/projects/Ghar_sajag_r1_dashboard/code
mkdir -p build/dashboard_review_tmp
export TMPDIR="$PWD/build/dashboard_review_tmp"
python3 tests/support/engineering_dashboard_review/prepare_host_event.py
PYTHONPATH=backend:.:tests/support/engineering_dashboard_review python3 -m unittest discover -s tests/support/engineering_dashboard_review -p 'test_review_*.py' -v
PYTHONPATH=backend:.:tests/support/engineering_dashboard_review python3 - <<'PY'
import json
from pathlib import Path
from test_review_integration import ActualApiFixture
fixture = ActualApiFixture()
try:
    result = fixture.review()
finally:
    fixture.close()
Path('../docs/exec-plans/evidence/engineering_dashboard_20261012/REVIEW_FIXTURE.json').write_text(json.dumps(result, indent=2) + '\n')
PY
npm --prefix frontend ci --ignore-scripts --no-audit --no-fund
node tests/support/engineering_dashboard_review/review_browser.mjs
```

The browser command requires the frontend's existing Playwright dependency and
matching cached Chromium. Install the matching browser only if absent, using the
repository's usual setup. Existing dependency lockfiles were not changed here.
To view the saved preview, serve this evidence directory with a local static
server and open review.html; it is not a deployed or authenticated application.

Focused existing readiness commands:

```bash
make validation-framework-test gs130-hil-runner-test
make -j2 lab-build
PYTHONPATH=backend:. python3 -m unittest tests.python.test_durable_api tests.python.test_durable_event_commit tests.python.test_hub_ownership_registry tests.python.test_node_health_config -v
```

Before resuming production, read CAMPAIGN_HANDOFF.md, current GS-120/122/124/125
comments, canonical GS-148 checkpoint and work-state, reconcile the newer shared
files and rerun context preflight. Obtain named design acceptance and missing
contracts before dependent work. Do not restart completed stages or merge while
GS-148 is actively writing. Jira statuses remain unchanged.
