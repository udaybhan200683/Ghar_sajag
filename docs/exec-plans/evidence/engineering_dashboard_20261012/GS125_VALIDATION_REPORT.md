# GS-125 validation report — 2026-10-12

**Scope: inactive review preparation plus focused existing baseline readiness.**
Production dashboard qualification remains BLOCKED_DESIGN_APPROVAL. A test below
marked PASS proves only its stated executed scope. No full software, commercial
authentication, target image, physical or release qualification is claimed.

## Independent delivery states

| Track | Campaign result | Executed evidence and limit |
|---|---|---|
| Design | PROPOSED / approval pending | Complete GS-120 proposal; no explicit acceptance |
| Production implementation | BLOCKED_DESIGN_APPROVAL | Inactive preparation is PARTIAL; no product activation |
| Unit testing | BLOCKED for production; preparation PASS | 37 draft model tests; production diagnostic model absent |
| Deterministic simulation | BLOCKED for dashboard; host baseline PASS | Actual Node/Hub/crypto/storage/CloudSync host fixture; 8 groups, 325 checks |
| Backend integration | BLOCKED for deployment; local preparation PASS | 8 actual file-SQLite API/query tests; local trusted-context adapter only |
| Playwright | BLOCKED for product; review artifact PASS | 20 desktop/mobile checks; static saved evidence, no live/authenticated PWA route |
| Relevant existing regression | PASS for executed focused readiness | 29 API/commit/ownership/health tests; board stack above; aggregate suites NOT_RUN |
| Validation-registry integration | BLOCKED_DESIGN_APPROVAL | Draft mappings only; existing 39 framework tests PASS |
| Board HIL | BLOCKED_GS114_NO_GO / NOT_RUN | Existing runner safeguards tested without ports; no identified approved safe fixture |
| Motion HIL | BLOCKED_GS114_NO_GO / NOT_RUN | No optical stimulus or current-image evidence |
| Actual physical product E2E | BLOCKED / NOT_RUN | Live S3→backend and technician access also incomplete |
| Full release gate | NOT_RUN | Ordinary development preparation; no release candidate or separate authorization |

## Exact executions and logs

Commands below ran with working directory `code/` in the isolated worktree.
Preparation uses `TMPDIR=$PWD/build/dashboard_review_tmp`; it never cleans `/tmp`.
The final host compile command and flags appear verbatim in the owned-temp log.

| Command | Exit / count | Evidence |
|---|---|---|
| `python3 tests/support/engineering_dashboard_review/prepare_host_event.py` | 0; emitted event + 8 groups / 325 checks | production_host_fixture_owned_tmp_final.log |
| `PYTHONPATH=backend:.:tests/support/engineering_dashboard_review python3 -m unittest discover -s tests/support/engineering_dashboard_review -p 'test_review_*.py' -v` | 0; 45 tests (37 model + 8 API) | review_tests_attempt03.log |
| `node tests/support/engineering_dashboard_review/review_browser.mjs` | 0; 20 checks | review_browser_attempt02.log; review_browser_results.json; two screenshots |
| `make validation-framework-test gs130-hil-runner-test` | 0; 39 + 17 tests | framework_hil_readiness.log |
| `make -j2 lab-build` | 0; prerequisite host application build | lab_build_readiness.log |
| `PYTHONPATH=backend:. python3 -m unittest tests.python.test_durable_api tests.python.test_durable_event_commit tests.python.test_hub_ownership_registry tests.python.test_node_health_config -v` | 0; 29 tests | existing_api_policy_readiness_attempt02.log |

Initial 37 model tests also passed, but are included in the final 45 and must not
be added a second time. The framework/HIL tests execute controlled fixtures and
mocked adapters, including expected BLOCKED paths; they do not operate boards.
No complete Node/Hub/contract/backend/PWA gate was required or executed for
unactivated test-support preparation. Production activation will require all
prior affected-component regressions, shared contracts, production simulation,
focused trigger-to-outcome E2E and browser permissions tests. No receipt is used
to convert a focused result into an aggregate PASS.

## Assertions actually exercised

Model tests cover strict diagnostic version/enum/identity input; positive signed
backend identity bounds; exact decimal display beyond JavaScript safe integers;
original versus transport identity; independent unavailable/conflicting stages;
fixture grant expiry, scope and caregiver denial; trusted contact lease equality,
expiry and reboot-domain uncertainty; MAC versus application ACK; count/byte
window overflow; exact-node/room/generation/kind installation matching; stale
backlog, wrong observer domain, timeout, retry, duplicate, incomplete and multiple
devices; unsupported capability. These are draft policy examples, not approved
product acceptance. There is no deployed grant issuer or installation route.

API tests run production `DurableEventApi`, `DurableEventCommit`, `SQLiteEventMap`
and caregiver query logic. They assert original key/room/time, reopen and one-row
duplicate commit, 409 same-key payload conflict, missing/spoofed trusted context,
cross-Home/wrong-node denial, existing caregiver query denial, closed storage
without COMMITTED, and separation from generic caregiver read. Actual local
transaction/query PASS does not prove commercial credentials or a running S3
worker. The saved trace exposes only the observation that was captured.

Browser tests assert seven panes at both widths, exact key, 10 independent stages
(nine UNKNOWN / one backend PASS), matching/nonmatching kind filters, saved-data
refresh and reload, disabled installation/advanced controls, no document overflow,
no page errors and no mutation request. Live stream, service-worker behavior,
technician auth and caregiver denial in a production browser remain BLOCKED.

## Preserved failed attempts and causes

| Attempt / log | Actual outcome | Resolution or disposition |
|---|---|---|
| production_host_fixture_build.log | Exit 2; initial file-backed Node recovery FAIL | Hardcoded `/tmp` fixture root on full filesystem; owned adapter only, no cleanup or production edit |
| production_host_fixture_owned_tmp.log | Exit 1; missing profiled object | Build-generated header changed make object fingerprint; reproducible script builds selected objects before link |
| review_integration_tests.log | Exit 1; 8 missing-input errors | Integration started before host fixture existed; generated actual fixture first |
| review_tests_final.log | Exit 1; 8 fixture-timezone errors | Fixture Home used unsupported UTC; corrected fixture to Asia/Kolkata |
| review_tests_attempt02.log | Exit 1; 1 identity assertion failure / 45 tests | Node-local versus physical-qualified key mapping made explicit; original field checks retained |
| review_browser.log | Exit 1; missing REVIEW_FIXTURE.json | Exported only after successful real API fixture; reran browser |
| existing_api_policy_readiness.log | Exit 1; 4 missing simulator errors / 29 tests | Built existing lab prerequisite; reran exact focused command |

The initial staged whitespace check detected CRLF in two generated CSV files
and line-end spaces in captured output. CSV files were normalized to LF; raw
logs remain byte-exact using a scoped log-only .gitattributes rule. The final
staged check passes. staged_whitespace_review_attempt01.log preserves the finding.

No failed log is replaced by the successful attempt. These were preparation
environment/fixture issues, not qualified production regressions. Historical
`clean migration commits` FAIL and full P0 `product_status=PARTIAL` gate FAIL are
preserved by reference to current work state/Jira; unchanged broad suites were
not rerun to hide them. The host event fixture is a subset of P0, not its full gate.

## Registry, source and physical evidence limits

Existing GS-116 39 meta-tests pass: nonzero failure propagation, zero/missing
tests, selected-stage composition, fingerprint/profile/receipt checks and release
composition are structurally tested. New dashboard IDs are not installed in
`suites.json` or `MASTER_TRACEABILITY.csv`; activation is deliberately blocked
pending design. FEATURE_TO_TEST_MATRIX.csv documents ownership/layers/physical
classes; source anchors/hashes establish inventory consistency only.
No new fixture framework or physical catalogue entry was activated.

SOURCE_INVENTORY.csv fingerprints existing provenance sources. PREPARATION_SOURCE_SHA256.csv
fingerprints the exact preparation source and review input used by final checks.
TEST_EXECUTION_RECEIPT.json records commands/counts/exits/scope and log hashes;
MANIFEST_SHA256.csv checks the shipped review files. Final delivery Git/remote
verification is in DELIVERY_CHECKPOINT.json in the ZIP. The preparation is Python,
Node/Chromium and base/O2/trace0 C++ host simulation, not an ESP-IDF target image.

HIL_ACCEPTANCE_MATRIX.csv preserves catalogue semantics and includes two explicitly
proposed future cases. HIL_OPERATOR_PLAN.md reconciles runner capabilities,
required exact fixture/image evidence and absent automatic motion/ACK proof.
GS-114's observer-reset and replay-fence failures remain NO-GO. No physical case
received PASS; no UART/USB interface, flash, reset, erase, enrollment or power-cycle
operation occurred. Software delivery, physical qualification and release
approval remain separate. This evidence does not satisfy GS-125 production Done.
