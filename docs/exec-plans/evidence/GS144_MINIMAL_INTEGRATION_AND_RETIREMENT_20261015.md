# GS-144 Minimal Integration and Retirement — 2026-10-15

## Executive result

The historical GS-144 branch contained a useful proposed workload dataset, a
production-component host harness, an optional current-based endurance model,
and two checkpoint commits. Canonical already owns the tested Node power,
health, sleep, radio retry, ACK retirement, persistence, and recovery behavior.
Those algorithms and their regression tests were not copied.

Canonical now contains one machine-readable GS-144 specification and a small
registered test that checks its provenance, structure, consistency, and
unapproved status. Seven candidate profiles are explicitly proposals; the
approved acceptance profile, actual cell and capacity, reserve, measurement
boundary, RF/outage schedule, service limits, and endurance thresholds remain
empty pending the owner decision. The workload is therefore **not yet an
approved reproducible acceptance workload**. GS-144 remains In Progress.

The historical battery estimator was not integrated: GS-144/GS-149 currently
need accepted workload and measurement inputs first, and the reviewed estimator
understates flash-write energy by a factor of 1,000. Its source, complete clone,
ignored build outputs, and local Git provenance are scheduled for a verified
external backup before the approved temporary clone/branch retirement.

No product firmware/runtime code, physical evidence, device, or Jira workflow
state was changed. Host results do not constitute a battery-life or commercial
qualification result.

## Verified refs and worktree state

| Ref | Verified state |
|---|---|
| Canonical branch before work | `feature/r1-commercial-baseline` at `12eae946db1ce8c810c9cc7df8e2c17d27d30889`; actual GitHub ref matched |
| Historical local branch | `gs144-workload-qualification` at `9af8c4f97c3db2314075ce62be5b95cb34fab923`; one commit behind remote, no local-only commit |
| Historical GitHub branch | `gs144-workload-qualification` at `ad7b9b7434246dd567ea0d800adccec65d724f00`; actual ref matched |
| Historical implementation | `9af8c4f97c3db2314075ce62be5b95cb34fab923` |
| Historical delivery checkpoint | `ad7b9b7434246dd567ea0d800adccec65d724f00` |
| Common boundary | `9272cc7efe171f6fc5f6ceb7fac4ad1c4924fd33` |
| Historical temp directory | `/tmp/gs144_battery_workload`; standalone Git clone, not a registered linked worktree; at remote branch tip `ad7b9b7434246dd567ea0d800adccec65d724f00` |

The temporary clone's `github` remote points to the expected GitHub repository.
Its `origin` points to the historical canonical checkpoint `9272cc7`; it is
not the current canonical remote. Its tracked and untracked status was clean;
it contains ignored build, log, cache, configuration, and evidence artifacts
(about 58 MiB at inventory). The repository's local branch ref is stale at
`9af8c4f`; the clone's checked-out branch and GitHub ref agree at `ad7b9b7`.
The clone had no unpublished commit relative to its GitHub branch. The later
checkpoint commit changes only the old evidence report and historical work
state.

Canonical had no tracked changes at task start. Existing untracked user PWA,
managed-component, and physical GS-114 evidence remained untouched. Four
registered worktrees were present at preflight: the primary repository, FOTA
phase2, canonical R1, and the integration worktree. A Codex/local-lab process
was confined to the integration worktree; the canonical writer observed was
this session. No process had the historical directory as its working directory
or open Git lock. No HIL, IDF, serial, or flashing process was present.

## Authority and acceptance mapping

Jira descriptions, acceptance criteria, dependencies, and latest relevant
comments were read for GS-144, GS-110, GS-149, GS-140, GS-41, GS-42, GS-141,
GS-43, GS-44, GS-51, GS-40, GS-114, GS-150, GS-116, GS-130, and GS-115.
Latest GS-144 comment 11047 asks for one owner decision and explicitly keeps
the following open:

| Requirement/use case | Current authority and status | How the specification represents it |
|---|---|---|
| Daily PIR/motion episodes and aggregation | GS-144 / GS-110; candidate counts in historical commit 9af8c4f are not approved household behavior | Candidate episode, observation, first-event, aggregate-summary and business-event counts; timing distribution remains null |
| NodeHealth and piggyback | Locked GS-D031; effective 300-second heartbeat, event piggyback, derived 910-second offline threshold | Recorded separately as approved policy facts and cross-checked against `code/config/node_health.json` |
| TX/RX, retries, rejoin, sleep/wake residency | GS-150 existing policy and GS-D020/027; no new latency or service guarantee | Candidate opportunity counts/durations and proposed awake/sleep estimates; not measurements and not a second policy implementation |
| Hub outage/recovery and installation/RF | GS-144/GS-110; frequency, duration, recovery phase and RF distribution remain open | Scenario labels and proposed retry/rejoin counts are retained; exact outage/recovery intervals and numeric RF assumptions remain null |
| Battery, reserve and measurement boundary | GS-144 open; GS-140 owns B0 instrument/boundary; GS-41/42/141/43 own BEFORE; GS-44 freezes comparison; GS-51 owns matched AFTER | Battery, usable capacity, reserve, instrument, boundary and uncertainty fields remain null until approved/measured |
| P10 comparison | GS-149 owns C8 quantitative acceptance after GS-114, GS-144, GS-140/B0–B4 and GS-51 | Spec requests matched raw current/voltage, firmware/fixture provenance, event traces, repeatability and uncertainty; this software change does not satisfy P10 |
| Physical function and liveness | GS-114 owns non-power BAT-C8 P1–P9; GS-40 owns real-target 300/910-second heartbeat/liveness acceptance | Reuse existing physical and software suites; do not relabel host coverage as hardware acceptance |
| Validation governance | GS-116 component/fast/release registration; GS-130 traceability and physical catalogue | New host spec contract is registered in the canonical Node stage and traceability ledger; no new HIL framework or physical test case |
| Later optimization | GS-115 is measurement-led; C11 is post-R1 by default and C12 is deferred | No C9–C12 implementation or commercial battery claim |

GS-144 comment 11047 identifies 150–180 days as aspiration and the proposed
150-day minimum as **not approved**. It also says nominal 2,900 mAh and the
DMEGC candidate are not approved battery values. No selected commercial cell,
usable capacity, reserve, aging/temperature basis, first-event service limit,
reliability bound, or target uncertainty policy was inferred here. GS-144
blocks GS-149; GS-149 also depends on GS-114 and the measurement/baseline work.
GS-144 remains In Progress.

## Historical commit and file disposition

| Historical commit / file | Change and canonical counterpart | Disposition and reason |
|---|---|---|
| `9af8c4f97c3db2314075ce62be5b95cb34fab923` — `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/tests/data/gs144_workloads.json` | Nine illustrative profiles, candidate capacity/current values and model assumptions. Canonical counterpart is `code/tests/data/gs144_workload_spec.json`. | **Partially integrated:** retained seven profile families as explicitly unapproved proposals; excluded duplicate `battery_low_unknown_calibration_24h` and OTA-only `ota_control_readiness_24h`. Added missing approval, timing, RF/outage, physical boundary, uncertainty and provenance fields as unresolved nulls. None is a mandatory acceptance workload. |
| `9af8c4f...` — `tests/cpp/gs144_workload_validation.cpp` | Five grouped checks exercise ActivityEpisode, NodeHealthCadence, sleep policy, NodeRadio retry, and Durable ACK. The test hard-codes profile counts and does not load the JSON workload file. | **Excluded as redundant:** equivalent behavior is covered by current `battery_c8_validation.cpp`, `gs40_node_health_validation.cpp`, `gs150_offline_sleep_validation.cpp`, `node_runtime_recovery_validation.cpp`, `node_recovery_persistence_validation.cpp`, `node_retirement_protocol_validation.cpp`, and board-stack coverage. A second hard-coded harness would duplicate those algorithms and would not make the JSON executable. |
| `9af8c4f...` — `tools/power/gs144_battery_model.py` | Optional analytic capacity/current model and per-profile endurance estimates. | **Deferred/excluded:** actual GS-144 workflow currently needs a product-approved workload and measured inputs. The model is not required to define those inputs or perform GS-149's measured comparison. Its arithmetic/assumptions fail review below. |
| `9af8c4f...` — `tests/python/test_gs144_battery_model.py` | Four tests for capacity envelope, proposed labels, invalid capacity and overlap handling. | **Excluded with model:** tests do not catch the flash-write unit error and would preserve an unapproved model as if it were part of acceptance. New tests guard input provenance and explicit decision gaps instead. |
| `9af8c4f...` — versioned-wrapper `Makefile` | Registers `gs144-workload-host-test` under the former source wrapper. | **Superseded by current layout:** canonical adds `gs144-workload-spec-test` in the root `code/Makefile`. |
| `9af8c4f...` — versioned-wrapper `tools/validation/suites.json` | Registers a Node workload/model stage in the historical registry. | **Superseded by current layout:** equivalent current Node stage `gs144-workload-spec` is added to `code/validation/suites.json` and exercised by framework/meta checks. |
| `9af8c4f...` — `docs/exec-plans/evidence/R1_GS144_BATTERY_WORKLOAD_20261012.md` | 291-line historical source review, proposals, calculations, test receipts and measurement plan. | **Reference preserved:** findings, commit provenance, accepted vs proposed boundary, validation evidence and arithmetic issue are reconciled here; the entire stale checkpoint is retained in the verified temporary-clone backup rather than copied as a competing/current report. |
| `9af8c4f...` — `docs/product/R1_WORK_STATE.md` | Adds an isolated-branch progress section with old canonical/source checkpoint and proposed acceptance. | **Superseded:** not copied verbatim. Current work-state receives a new canonical checkpoint tied to present HEAD and open approvals. |
| `9af8c4f...` — `docs/validation/MASTER_TRACEABILITY.csv` | Adds a validation-capability row under old source paths and the old GS-116 registry. | **Adapted:** canonical trace row `GS144-WL-SPEC-01` references the current spec/test/Node stage and records partial status until product approval. |
| `ad7b9b7434246dd567ea0d800adccec65d724f00` — historical evidence report and work state | Adds the delivery result and progress checkpoint to the prior isolated report; no production source/test change. | **Historical provenance only:** exact SHA retained here and in the external clone backup. Old branch progress/HEAD claims are not current canonical status. |

## Battery-model arithmetic and assumptions review

The proposed average-current envelope formula is arithmetically valid when
capacity, usable fraction, reserve definition and days are supplied and
approved: `capacity_mAh * usable_fraction * (1 - reserve_fraction) /
(days * 24)`. That does not make the candidate 2,900 mAh, 80% usable, 10%
reserve, or 150/180-day values approved or measured.

The historical model treats `flash_write_mas` as milliamp-seconds but divides
by `3,600,000` to produce mAh. For mA·s to mAh the conversion is `/ 3,600`.
The current formula therefore understates each flash-write energy contribution
by **1,000×**. No correction was integrated because the optional estimator is
deferred; the complete historical source remains in the backup.

Other model limitations also prevent acceptance use: TX/RX durations are
summed as separate awake increments without evidence that the windows do not
overlap; TX/RX current increments and continuous PIR/leakage additions require
a precisely defined battery-side baseline to avoid double counting; awake and
sleep residency are assumed rather than sampled; the model has no measured
current/voltage trace or uncertainty; and outage/RF timing, event schedule,
actual battery cutoff and power path are not established by candidate profile
labels. These are not resolved by the model's sensitivity output.

## Canonical integration

Files changed for the integration:

| Canonical file | Change |
|---|---|
| `code/tests/data/gs144_workload_spec.json` | One versioned input contract with approved fields kept empty and seven candidate profiles marked `PROPOSED_NOT_APPROVED`; includes motion/event, health/piggyback, TX/RX/retry/rejoin, outage/RF, residency, pending/flash-write and physical measurement/uncertainty fields. |
| `code/tests/python/test_gs144_workload_spec.py` | Four focused tests validate that open values stay empty, the 300/910 GS-D031 facts match canonical config, candidate event/residency arithmetic is consistent, and missing outage/RF/physical data remains explicit. |
| `code/Makefile` | Adds `gs144-workload-spec-test`. |
| `code/validation/suites.json` | Registers the stage for the Node component and full fast/release composition. |
| `docs/validation/MASTER_TRACEABILITY.csv` | Adds `GS144-WL-SPEC-01`, classified PARTIAL pending the GS-144 owner decision. |
| `docs/product/R1_WORK_STATE.md` | Records delivered canonical input specification, tests, open decisions and next action. |
| `docs/product/CANONICAL_REQUIREMENTS_INDEX.md` | Indexes this execution evidence and the machine-readable test input without assigning either requirements authority. |
| `docs/exec-plans/evidence/GS144_MINIMAL_INTEGRATION_AND_RETIREMENT_20261015.md` | This semantic reconciliation, model audit, validation and retirement handoff. |

At the test source snapshot, SHA-256 was `e25c4f1e62f0dff185662d03a0ddfe7911944cab96329bed64e6f22c73a5587c` for the workload JSON and `1e7c0478d2e95a196b9d5594570da9b2144fd886e505dc996a48128c71a1b287` for the Python test. The registered suite JSON SHA-256 was `72c76bb6afa330deba91c53109b02b3ecb86d5fed80df8357571ac41f72db72c`.

No file under `code/firmware/` changed. No PowerPolicy, ActivityEpisode,
NodeHealth, NodeRadio, retry, ACK, recovery, sleep or production algorithm was
added or modified.

## Focused validation evidence

All commands below ran on the canonical source after integration edits. Host
tests only; no full release gate, target build, physical HIL, firmware flash,
USB operation, reset, erase, commissioning or measurement was performed.

| Command | Result |
|---|---|
| `make -C code gs144-workload-spec-test` | PASS, 4 tests |
| `make -C code battery-c8-host-test` | PASS, 72 C++ checks and 11 Python invariants |
| `make -C code gs40-host-test` | PASS, 1,320 checks |
| `make -C code gs150-host-test` | PASS, 1,500 checks |
| `make -C code node-recovery-host-test` | PASS, retained/in-flight/retry/session-isolation host suite |
| `make -C code node-recovery-persistence-host-test` | PASS, encrypted bounded recovery host suite |
| `make -C code node-retirement-protocol-host-test` | PASS, authenticated report and heartbeat-retirement host suite |
| `python3 code/validation/component_gate.py --suite node --list` | PASS; `gs144-workload-spec` appears in the Node component selection |
| `make -C code feature-coverage-test` | PASS; 199 feature rows, 210 source modules, 15 physical cases; 22/22 mapping tests |
| `make -C code validation-framework-test` | PASS, 46/46; confirms registry selection, release inclusion and failure propagation |
| `git diff --check` | PASS after final documentation edits |

Board-stack E2E was not rerun because production source and shared runtime
contracts did not change; current committed board-stack receipts remain
available in canonical validation evidence. No physical result or endurance
claim is inferred from any host result.

## Open decisions and next plan

1. GS-144/product owner approves a representative scenario and event timing,
   motion aggregation assumptions, Hub outage/recovery/RF profile, actual cell
   and usable-capacity/aging/temperature basis, reserve, power path and
   battery-side measurement boundary.
2. Product owner approves first-important-event latency/reliability limits and
   minimum/preferred endurance target/uncertainty. Do not treat 150–180 days or
   the proposed 150-day minimum as accepted.
3. GS-140 freezes instrument/range, safe boundary, sampling, burden and
   uncertainty. Then GS-41/42/141/43 collect comparable BEFORE evidence and
   GS-44 freezes metrics; GS-51 collects matched AFTER evidence.
4. GS-114 P1–P9 and GS-40 real-target liveness remain their own acceptance
   tracks. After their prerequisites and approved GS-144 inputs, GS-149 makes
   the measured P10 comparison; GS-146 owns final C1–C8 physical release
   closure. GS-115 stays measurement-led; BAT-C12 remains deferred.

The canonical validation work is software-complete for this small spec contract,
but GS-144 product acceptance remains open. Retirement of the old branch and
temporary clone is allowed only after the whole clone, including ignored
build/log/cache/evidence files and `.git`, is copied and content/inventory
checksums pass. Final cleanup state and backup location are to be appended after
that gate.
