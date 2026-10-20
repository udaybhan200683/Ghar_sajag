# GS-165 Pilot Provisioning Station v1 — implementation evidence

Date: 2026-10-19 UTC
Owning Jira: GS-165; implementation slices GS-167/169/170/171; reuses GS-168
Branch: `feature/gs-165-pilot-station`
Source baseline: `4fbb8afbfb95a128fa942ac260939601af817411` from fetched
`origin/feature/r1-commercial-baseline`
Preflight: PASS, context `2026-10-13.001`

## Scope and dependencies

This is a local Python/SQLite, software-only tool change. Affected code is
`code/tools/factory/` and its Python tests/validation registrations. Node, Hub,
backend, PWA and shared firmware/security interfaces are unchanged. It adds no
production identity semantics or Home ownership behavior.

Implementation follows the current GS-165 owner-approved single-operator
50–100-unit pilot scope, the GS-166 simulated states and identity boundaries,
and the existing GS-168 TEST_ONLY issuer. GS-166 remains In Progress. The
issuer's CA key remains ephemeral in process memory, as GS-166 requires. This
allows retry/recovery while the same authority is available; after real process
loss, public report/verify commands remain available and clearly state that
certificate-chain verification was not repeated, but incomplete issuance fails
closed. Do not persist or substitute a new issuer key to bypass that gate.

No hardware, USB/serial, flash, eFuse, real credential, production service or
activation was used. Physical QA is `NOT_RUN`; no simulated result is delivery
qualification.

## Delivered

- `code/tools/factory/pilot_station.py`: local CLI for `simulate-one`,
  `simulate-batch` (1–100, sequential), `verify`, `resume`, `quarantine`,
  `recover`, and `export-public`.
- `code/tools/factory/pilot_test_issuer.py`: narrowly exposes the active public
  TEST_ONLY certificate for interrupted idempotent retry; no private key or CSR
  material is returned or stored.
- `code/tools/factory/GS165_PILOT_STATION_README.md`: command examples, state
  flow, backup, quarantine/recovery and issuer-loss limits.
- `code/tests/python/test_gs165_pilot_station.py`: permanent focused station
  suite. It runs alongside all existing GS-168 issuer tests.
- `code/validation/suites.json`: `pilot-factory` tooling stage, selected by fast
  and release compositions.
- `docs/validation/MASTER_TRACEABILITY.csv`: `GS165-PILOT-01` and test anchor
  `GS165-PILOT-001`. The general source inventory intentionally does not scan
  `tools/factory/` or `tests/python/`; no broad scanner/root change was made.

The local transactional registry holds the permanent synthetic Hub ID, unique
public certificate fingerprint, issuer reference, source and firmware
versions/hashes, QA result, provisioning state, public QR lookup handle,
quarantine reason and timestamps. Its unique constraints protect Hub ID,
certificate fingerprint and QR handle. It contains no Home, installation epoch,
Node credential or private key field. QR is an opaque public lookup reference.

Allowed states are `NEW -> RESERVED -> TEST_CREDENTIAL_ISSUED ->
SIMULATED_QA_PASS`; invalid/error paths enter `QUARANTINED`. Identity/provenance
conflicts require a different Hub ID. Retryable quarantine requires exact
operator confirmation. No `READY` or `DELIVERY_READY` state exists. Reports are
labelled `SIMULATED`, keep physical QA `NOT_RUN`, and say
`NOT_READY_SIMULATION_ONLY`.

## Executed validation

| Command | Result |
|---|---|
| `python3 -m py_compile tools/factory/pilot_station.py tools/factory/pilot_test_issuer.py tests/python/test_gs165_pilot_station.py` | PASS |
| Registered stage command: `python3 -m unittest discover -s tests/python -p 'test_gs16*_pilot*.py' -v` | PASS, 24 tests in 76.790 s; includes 14 GS-165 tests and existing 10 GS-168 tests. GS-165 includes sequential 100-device simulation. |
| `make feature-coverage-test` | PASS: traceability consistency, 216 features / 255 modules / 25 physical cases; Python traceability suite 22/22. Consistency only, not semantic or physical qualification. |
| `make validation-framework-test` | PASS, 51/51 GS-116 framework tests. |
| `python3 validation/component_gate.py --suite tooling --list` | PASS: `pilot-factory` is selected in tooling, fast and release membership. This listed the composition; it did not run unrelated tooling stages. |
| CLI smoke: `simulate-one`, then separate-process `verify` and `resume` on the completed matching record | PASS. All report `SIMULATED_QA_PASS`; read-only commands mark `NOT_REPEATED_AUTHORITY_KEY_EPHEMERAL`. |
| `git diff --check` | PASS before final commit (recheck immediately before staging/commit). |

Negative/recovery checks cover duplicate Hub ID with conflicting provenance,
duplicate fingerprint/QR, revoked or mismatched issuer credentials, corrupted
registry authority metadata, interrupted SQLite transaction rollback,
same-authority registry/issuer restart and retry, issuer outage/retry, explicit
quarantine recovery and immutable reasons, production-mode rejection, invalid
transitions, safe provenance, report secret exclusion and false-READY prevention.

Full Node/Hub/backend/PWA regressions and full release gates were not run:
this task changes only host factory tooling and registered Python tests. No
target build is applicable. Board E2E and all physical qualification remain
NOT_RUN.

## Pause/integration boundary

The change stays on the isolated branch. Do not merge, cherry-pick or rebase
while GS-179 is active. The canonical branch was at the fetched baseline when
this branch was created; the pre-existing GS-177 branch remains untouched at
`0120f6f2f57a2568700b5933bcab8eb4ddf18edc` with zero unique commits relative to
that fetched canonical tip. The canonical worktree's unrelated untracked PWA,
IDF and physical evidence remains preserved.

Before later integration, compare current canonical ancestry and file-level
changes, rerun canonical context preflight, and reconcile `pilot_test_issuer.py`,
the validation stage and traceability row. Run the affected registered tooling
tests and feature coverage on the integration commit. Do not overwrite any
GS-179 changes. Actual process-loss continuation remains limited by GS-168's
ephemeral test authority; changing that boundary requires the owning security
decision, not a key-storage workaround in this station branch.

## Delivery checkpoint

- Implementation commit: `e40058af55eb76385fc4e5ce64bc877c0c97cba6`.
- Pushed only to `origin/feature/gs-165-pilot-station`; `git ls-remote` matched
  this commit immediately after push.
- The fetched canonical remote remained
  `4fbb8afbfb95a128fa942ac260939601af817411`; the GS-177 fallback branch
  remained `0120f6f2f57a2568700b5933bcab8eb4ddf18edc`.
- No merge, cherry-pick or rebase was performed. No canonical or GS-179 worktree
  files were changed by this implementation.
- GS-165 remains In Progress. GS-166 remains In Progress. GS-167 remains open
  because process-loss continuation cannot bypass the GS-168 ephemeral-authority
  rule. GS-169, GS-170 and GS-171 deliverables are implemented and registered;
  their Jira workflow statuses are updated separately after validation.
- `R1_WORK_STATE.md` is intentionally not changed on this isolated source branch
  while the canonical GS-179/R1 state writer is active. Integrate a concise status
  note only during canonical review.

Next action: after GS-179 is complete and a canonical integration window is
explicitly opened, re-read the latest GS-165/166/179 comments and current
canonical state, inspect commit/file-level conflicts, rerun preflight, reconcile
the TEST_ONLY issuer boundary and run the registered pilot-factory plus
feature-traceability checks on the integration commit.
