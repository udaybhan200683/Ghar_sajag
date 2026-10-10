# R1 Cross-Worktree Requirements, Code, Documentation and Jira Audit

**Date:** 2026-10-10
**Status:** Proposed audit; awaiting user review. No code, Jira workflow/ranking, branch, or hardware changes were made.
**Canonical line:** `/home/udaybhan/projects/Ghar_sajag_r1`, `feature/r1-commercial-baseline`, local `9cda6ad4227bf54b8cb0ddc4279d72e20d6aafd7`; GitHub ref `f27d6ab0944bf3c1871d6185a7cd4ebef357a149` is its direct parent. Normal push of this audit will publish the already-approved GS-D030 commit and this report.

## Executive assessment

R1 canonical authority is the R1 branch’s LOCKED decision log, release contract, indexed domain documents and work-state. GS-D030 selects S3 N16R8 Hub with C3 Nodes. The S3 feature branch contains substantial S3 implementation, P2-A/B/C host/SDK evidence and the 10 October pause handoff, but it is not in the canonical R1 baseline. P2-D remains partial. The battery branch contains material C3 runtime/persistence changes and battery physical evidence absent from R1. No branch is a complete release baseline by itself.

Jira comments 10307–10310 / 10308 approve pausing S3 execution and making BAT-C8 physical qualification active. R1 Work State / Project Context / storage ExecPlan still name S3 as the next engineering priority. This is a current-state documentation mismatch, not a product requirement conflict. GS-148 remains In Progress in Jira although its description/comments say workstream paused; GS-131 is OnHold. No Jira transition was made.

Jira inventory indexed all 142 issues by key, title, status and issue type. Detailed descriptions/links were fetched for GS-41/42/43/44/46/51/69, GS-95/96/108, GS-110/114/115/117/118/119/121 and GS-131–139/140/141/144–148. Newest comments were inspected for GS-110/114/115/119 and GS-131–139/144/146/147/148, including the 132–139 crosswalk. This did not read every description/comment/field on all 142 issues. PWA/backend and the remaining backlog need a second full acceptance/link/rank pass before this becomes a complete commercial R1 execution plan. No tests were rerun; all PASS statements below are historical and scoped to their recorded commit/hardware.

## Worktrees, refs and reconciliation

Actual remote refs were queried with `git ls-remote`. No worktree was synchronized or modified.

| Path | Branch; local HEAD / actual remote HEAD | Status and latest commit | Scope / R1 relevance | AGENTS and docs | Work absent from R1; consolidation assessment |
|---|---|---|---|---|---|
| `/home/udaybhan/projects/Ghar_sajag` | `feature/battery-power-policy`; `808080e94b6958153952ce16eb56c1ad37a9ad01` / same | 3 untracked HIL probe scripts preserved; 2026-09-28 “Recover Node session after Hub restart” | BAT-C8+ C3 implementation and physical evidence; R1-relevant | No repo AGENTS; `docs/`, `docs/hw/evidence/` | C3 runtime/persistence/security differences are on this branch only. Preserve and reconcile before claiming canonical BAT-C8 source. No wholesale merge. |
| `/home/udaybhan/projects/Ghar_sajag_durable_storage_impl` | `feature/hub-durable-storage-primitives`; `e1ef65e3f647bffa0cef75695e1af6d135c0df4a` / same | Tracked clean; 2026-10-04 “WIP: checkpoint deferred durability migration” | Historical durability primitives, useful comparator | No repo AGENTS; docs/design/validation | Separate native transaction/ownership work. Preserve as historical; no merge absent scoped proof. |
| `/home/udaybhan/projects/Ghar_sajag_phase2` | `feature/hw-m1-4-hil-phase2`; `8f053b45b1c6b8ec772565336582c7e63a68a6a6` / same | Untracked generated test build dirs preserved; 2026-09-27 “Record Hub journal restart recovery qualification” | Secure multi-node HIL, FOTA, restart evidence on tested target only | No repo AGENTS; docs/hw/evidence, docs/validation | S3 implementation absent; preserve, never treat historical target as S3 evidence. |
| `/home/udaybhan/projects/Ghar_sajag_r1` | `feature/r1-commercial-baseline`; `9cda6ad4227bf54b8cb0ddc4279d72e20d6aafd7` / `f27d6ab0944bf3c1871d6185a7cd4ebef357a149` | Tracked clean; one approved local commit ahead; 2026-10-09 “Record approved ESP32-S3 N16R8 Hub development direction” | Designated canonical R1 governance/integration line | Root AGENTS; docs/product and indexed domains/evidence | Does not contain S3 P2 implementation or battery-branch C3 diffs. Keep canonical; no force/sync. |
| `/home/udaybhan/projects/Ghar_sajag_r1_s3` | `feature/r1-s3-hub-bringup`; `5b8b1485f80b5989db0fbbd77588c91986fc6ca9` / same | Untracked SDK `sdkconfig`, `managed_components/` preserved; 2026-10-10 “Document S3 pause and BAT-C8 handoff” | S3 P2-A/B/C host/SDK complete, P2-D partial, paused | Root AGENTS; branch-local docs/evidence | S3 code/status absent in R1. Keep isolated pending explicit resume/review. |
| `/home/udaybhan/projects/Ghar_sajag_r1_storage` | `feature/r1-hub-storage-lifecycle`; `389ffd3048cd44afdbb9ef074ed2a96020a3641e` / actual `2b3c6730f8c490ba88a13ba2c23d6674c4c30fa8` | 11 commits ahead of its cached upstream and actual remote tip; untracked `prompt.txt` preserved; 2026-10-09 “Record 128 KiB short-outage capacity failures” | Storage analysis/capacity experiments | Root AGENTS; storage design/ExecPlan/evidence | Local work is ahead of actual GitHub. Preserve; do not sync. |

R1 and S3 share ancestor `cd8d126ab44689cc9c6ebbbe74e6dce058d4323b`, with 5 R1 commits and 45 S3 commits after it. R1 and storage share it, with 26 storage commits after it. These are independent lines, not merge readiness.

## Markdown and AGENTS conflict matrix

| Sources | Finding | Status / treatment |
|---|---|---|
| `~/.codex/AGENTS.md`, R1 and S3 root `AGENTS.md` | Context preflight, safety and no-destructive-sync rules align. R1 AGENTS names R1 worktree/branch canonical and document precedence. No nested AGENTS found. | Shared policy sufficient; no AGENTS changed. |
| R1 LOCKED decisions / Release Contract / Index | GS-D005/D016: fixed 128-event lifetime unacceptable. GS-D024: density first. GS-D025: 72-hour outage design target, not capacity guarantee. GS-D026 aggregation boundaries; GS-D027 battery-first C3; GS-D029 storage security/application rollback; GS-D030 S3 N16R8 Hub. | Current authority. Classic 4 MiB facts remain historical, not current Hub requirement. |
| R1 Work State, Project Context, active storage ExecPlan vs Jira 10308 and S3 pause docs | R1 says S3 is next; 10/10 approved priority is BAT-C8 physical. | Current-state mismatch; dated work-state sync added. No requirement/context-version change. |
| BAT-C8 plan vs later battery branch evidence/Jira GS-114/119 comments | R1 plan’s P1–P10 NOT_RUN accurately describes prepared checkpoint. Later evidence proves some real AM312/GPIO4/ACK cases; soak/power/C8 closure still pending. | Preserve both with exact image/source provenance; reuse valid cases only when setup matches. |
| S3 P2-D evidence vs production claims | HTTP/HTTPS adapter, strict receipt parser, bounded CloudSync/fixture, host sanitizers and S3 build PASS; live auth/provisioning, generation-bound receipt, active worker/reconnect and canonical 72h traces not passed. | PARTIAL, branch-local evidence only. Do not call production E2E. |

GS-D029/D030 and context `2026-10-09.001` are present on both canonical and S3 docs. No unresolved current product requirement conflict was identified in reviewed authority. Preserve historical sections and GS-132–139 crosswalk.

## R1 requirements and open decisions

**Mandatory R1 scope evidenced by the release contract:** commercially installable fresh-install system; authenticated ownership/device lifecycle; PIR/event chronology; local safety during cloud loss; durable-before-ACK, retry/dedupe/reboot recovery; caregiver freshness/coverage; backend-backed history; required BAT-C8 production sleep/wake reliability (GS-D020); signed FOTA/application rollback; bounded operation across six C3 Nodes and S3 Hub.

**Conditional/post-R1:** GS-115 C9–C12 measurement-driven; no automatic deep sleep/adaptive TX/QoS. GS-147 is design proposed, not production approved. Bed sensing, fall detection, 24/7 response and engineering dashboards are not mandatory absent new decision.

**Unresolved decisions/gates:** GS-144 numeric battery target/workload/uncertainty and real measurement path; exact retention/offline volume/rate/reserve/saturation/wear policy; production backend credential/provisioning/endpoint/trust and owner/enrollment-generation-bound durable COMMITTED contract; canonical outage traces and summary policy (NORMAL 728 exact + 197 candidate summaries; HIGH 3,278 + 298; STRESS 42,679 + 1,682; separate 6,556 engineering stress trace); physical S3 flash/PSRAM/pinout/partition, GC/wear/heap/OTA and power-cut qualification; post-sync local history and incarnation/migration product policies.

## Source-code audit

Read-only inspection used S3 HEAD `5b8b148`, battery HEAD `808080e`, canonical R1 HEAD `9cda6ad`. Source paths are relative to `code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2/`.

### C3 and cross-component behavior

- `firmware/node/runtime/node_runtime.cpp:52-104,110-139`: record path preflights TX capacity, persists before enqueue, retains EventKey/original timestamps, and applies defined ACK retirement. Exact event identity/content comparison exists.
- Battery vs R1 source differs in `firmware/node/components/storage/node_recovery_persistence.cpp`, `firmware/node/runtime/node_runtime.cpp/.hpp`, target `app_main.cpp`, `node_runtime_adapter.cpp`, `node_security_link.cpp/.hpp`, and zero-length-AEAD qualification files. These changes are not in canonical R1.
- `firmware/node/components/radio/node_radio.cpp:46-149`: outage path prioritizes unsent non-motion/critical work, permits a prompt first motion opportunity, then applies global bounded retry/backoff. This is source behavior, not measured current/endurance or physical sleep-first qualification.
- PowerPolicy and light sleep decision live in `firmware/node/components/power/power.cpp/.hpp`; target GPIO/timer wiring is C3 adapter. Existing cap/diagnostics do not prove 32/72-hour Hub-off retention.
- Node pending record capacity is bounded at 32; near-full rejection is not solved by increasing a constant. No persistent format/queue expansion under GS-147 without approved contract, retirement interoperability and capacity proof.
- C3 exact EventKey, timestamp, authenticated durable Hub ACK, retirement report capacity, owner/session/generation/replay-fence, no-new-PIR recovery and OTA schema compatibility form a cross-component gate before any queue change.
- Battery telemetry counters are not a calibrated battery SOC/endurance measurement. GS-115 C9 requires GS-144 and hardware evidence.

### S3, cloud and backend

- `firmware/hub/target/esp32/hub_runtime_adapter.cpp:601-630`: S3 target mounts LittleFS segmented outbox and closes admission on unavailable partition/recovery failure; target staging uses 128 KiB segments. Commercial layout and long-run capacity remain unqualified.
- `firmware/hub/components/storage/durable_event_outbox.cpp` plus mixed-body tests implement mixed-segment reclaim, ordinal/completion remap, replay fence and crash-consistent publication on S3. Deletion gates remain disabled for production.
- `hub_runtime_adapter.cpp:1030-1047`: replay fence joins retirement snapshot/checkpoint before admission; failure closes admission. Host fault checks do not exhaust physical power-loss points.
- `firmware/hub/components/cloud/cloud_sync.cpp:108-169,183-243`: bounded batch scans durable pending events, verifies request content against journal, records local completion only on authenticated matching COMMITTED, and uses bounded backoff. A network send is not completion.
- `firmware/hub/target/esp32s3/https_backend_channel.cpp`: configured HTTPS origin/CA, bounded framing and redirect refusal. No live endpoint/trust/credential provisioning or active production connectivity owner is configured.
- S3 P2-D evidence (branch `5b8b148`, prior code checkpoint `e1941d7`) reports SQLite 300-event bridge, 3 duplicate submissions/no duplicate business effect, ASan/UBSan and S3 build PASS; 300 peak pending, 90,112 peak POSIX allocated bytes, 138,863 ms catch-up under host test conditions. Fixture is not live backend or 72-hour endurance; no payload/identity deletion.
- PWA contract remains backend-first/near-real-time. GS-117/121 hardware-to-PWA E2E open. Signed FOTA evidence is target-specific; S3 storage/FOTA compatibility/rollback not established.

## Validation and evidence matrix

| Claim | Historical source and result | Fresh audit result / limit |
|---|---|---|
| R1 durable admission, rejoin, ACK, lost-ACK/retry/dedupe | R1 `docs/hw/evidence/R1_LOST_ACK_FINAL/`, prior physical PASS on stated hardware | Not rerun; does not qualify S3/current battery image. |
| BAT-C8 host/build | GS-114 and `docs/hw/evidence/BAT_C8_R1_QUALIFICATION/TEST_PLAN.md`; focused host/build PASS | Not rerun; P1–P10 closure pending, reuse only traceable physical evidence. |
| C1–C4 physical | GS-119 comments: real optical PIR/GPIO4 and repeated events complete on battery branch | PARTIAL; soak/power remain. |
| Signed C3 FOTA | GS-118 and Phase2 evidence | Core positive/negative path historically qualified; rollback/interruption extension open; not rerun. |
| S3 P2-A/B/C | S3 evidence through `17c5cfd` | Host/SDK PASS; physical pending; not rerun. |
| S3 P2-D | S3 evidence at `e1941d7`, pause docs at `5b8b148` | PARTIAL; live auth/caller/reconnect/canonical 72h not run; baseline-reproducible Node assertion failure remains. |
| Storage branch capacity | `389ffd3` dated reports | Historical model/workspace boundary; not S3 guarantee. |
| Context | Preflight R1 and S3 | PASS at `2026-10-09.001`; no builds/tests run. |

## Jira status and disposition (proposal only)

All current statuses below were read 2026-10-10. No rank/status/links changed.

| Issues | Current Jira state | Proposed classification |
|---|---|---|
| GS-110 | In Progress | Valid parent epic, not executable as a single task. |
| GS-111–113 | Done | BAT-C1–C7 implementation; evidence provenance retained. |
| GS-114 | In Progress | Current active BAT-C8 physical task; software/host/build done; physical closure not done. |
| GS-115 | To Do | Conditional measurement-based C9–C12 decision; no automatic implementation. |
| GS-119 | To Do | Partial: reuse optical PIR/GPIO4 evidence; soak/power gaps remain. GS-38 historical resolved; GS-39 conditional. |
| GS-140/41/42/141/43/44/51 | To Do | Ordered measurement setup, B0–B4, frozen comparison, matched AFTER. |
| GS-46 / GS-69 | To Do | First-event latency and 12h soak/end-of-soak real PIR→ACK remain. |
| GS-144 | To Do | Required target/workload decision before endurance claim. |
| GS-146 | To Do | Valid evidence-consuming C1–C8 closure gate, not a new campaign. |
| GS-147 | To Do | Research/design only, not implementation-approved; needs measured Hub-off target and ACK/capacity contract. |
| GS-131 | OnHold | Paused parent epic; do not close. |
| GS-132/134/136 | OnHold | Residual incarnation/migration, recovery-root, anti-ABA/reclamation obligations under GS-148. |
| GS-133/135 | Done | Administrative supersession/coverage by GS-148, not physical release qualification. Preserve crosswalk. |
| GS-137/138/139 | OnHold | Production backend; capacity/offline; physical durability obligations remain under GS-148. |
| GS-148 | In Progress | Description/comments say paused; Jira workflow mismatch for user review. Single S3 release owner; retain GS-132–139 crosswalk. |
| GS-117/121 | To Do | Live C3→Hub→backend→PWA E2E open; after real production contract. |
| GS-145 | To Do | Current-format fresh-install/reboot gate; prior evidence target-specific. |
| GS-118 | To Do | FOTA rollback/interruption extension; after final S3 storage/schema. |
| GS-95/96/108 | To Do | Older broad HIL/integration scopes need R1/S3 rescope and evidence reuse. |
| GS-38 | Done | Historical PIR stall resolved; reopen only on current reproduction. |
| GS-39 | OnHold | Conditional diagnostic if current soak has unexplained failure. |
| GS-45/52/53/56/66/70–72/78–82/92/102–107/120/122/124–129 | Mixed OnHold/Future/To Do | Mostly optional, historical, research or post-R1; require source before ranking. |
| GS-40, 54–68, 73–77, 83–94, 104, 109, 116, 130, 142–145 | Mixed To Do | Potential R1 health, provisioning/security, PWA roles, sensors, learning, notification, FOTA/HIL; full AC/link review remains. |

## Single proposed execution queue (awaiting approval)

Exact active row first. This is a proposal, not Jira re-ranking. Rows 14–15 are gated and not ready until decisions/contracts land. A wider PWA/backend backlog review remains necessary before calling this the entire commercial release queue.

| Rank | Jira | Work / prerequisites / completion | Environment, blocker, rough effort | Next |
|---:|---|---|---|---|
| 1 | GS-114 | Finish remaining physical C8 P1–P10; correct firmware/image provenance; reuse valid PIR/ACK evidence; disposition all cases. | Physical; preserve boards/state; 1–3 bench days assuming equipment. | GS-144 |
| 2 | GS-144 | Approve numeric battery target, workload, measurement path and uncertainty. | Product decision; 0.5–2 days after owner response. | GS-140 |
| 3 | GS-140 | Repeatable B0 instrument/setup boundary and calibration. | Hardware; 0.5–1 day. | GS-41 |
| 4 | GS-41 | B1 idle baseline with correlated firmware/logs. | Hardware; 0.5 day. | GS-42 |
| 5 | GS-42 | B2 NodeHealth baseline. | Hardware; 0.5 day. | GS-141 |
| 6 | GS-141 | B3 controlled real PIR baseline. | Hardware; 0.5 day. | GS-43 |
| 7 | GS-43 | B4 Hub offline/recovery baseline. | Hardware; 0.5–1 day. | GS-44 |
| 8 | GS-44 | Freeze comparable metrics/uncertainty from B0–B4. | Analysis; 0.5 day. | GS-46 |
| 9 | GS-46 | First meaningful motion latency after wake and retry against approved bound. | Physical; bound may need product input; 0.5–1 day. | GS-119 |
| 10 | GS-119 + GS-69 | Complete residual C1–C4 and 12h soak; end-of-soak real PIR→authenticated Hub ACK. | Hardware, 12h elapsed + setup; reuse prior accepted cases. | GS-51 |
| 11 | GS-51 | Matched AFTER B1–B4, quantify changes and correctness regressions. | Hardware; frozen baseline required; 1–2 days. | GS-146 |
| 12 | GS-146 | Close C1–C8 from reconciled evidence without duplicate tests. | Review + hardware evidence; 0.5–1 day. | GS-115 |
| 13 | GS-115 | Measurement-based go/no-go per C9–C12 only. | Decision; no auto-code; 0.5–2 days. | GS-148 |
| 14 | GS-148 | Resume P2-D production identity/provisioning, owner-generation COMMITTED, active network worker, canonical workload contract, tests. | Host + live backend; currently blocked, estimate after inputs. | GS-145 |
| 15 | GS-145 + GS-118 + GS-117/121 | Requalify S3 fresh-install/reboot/dedupe, FOTA/storage rollback and real hardware→backend→PWA vertical. | Host + physical/live; depends on P2-D and approved preservation procedure. | GS-139 / release gate |

## Blocked, conditional and post-R1

- **Blocked:** P2-D production authentication/provisioning, receipt ownership binding, endpoint/trust and active connectivity caller; canonical NORMAL/HIGH/STRESS trace and aggregation rules.
- **Blocked:** S3 physical flash/partition, GC/wear, power-cut, heap/PSRAM, OTA rollback and 72h six-node evidence. Host/SDK does not satisfy these.
- **Needs product decision:** GS-144 battery target; exact retention/offline capacity/reserve/saturation; local post-sync history; GS-147 Hub-off retention and whether larger C3 journal is R1.
- **Conditional:** GS-115 C9–C12, GS-39 if fault recurs; C3 journal increase only with S3 ACK/report/capacity proof.
- **Post-R1 absent measurement:** 24/72h soak beyond R1 12h, deep sleep, adaptive TX, optional sensor/research features and broad campaigns not tied to R1 gates.
- **Not a blocker:** GS-38 resolved historical PIR stall absent recurrence. Classic hardware evidence remains target-specific.

## Worktree and documentation policy proposal

**WORKTREE_KEEP:** canonical R1; paused S3; battery source/evidence until reconciled; phase2 and durable-storage trees read-only while evidence needed.
**WORKTREE_ARCHIVE_CANDIDATE:** phase2 and durable-storage implementation, only after separate approval and evidence inventory; never delete in this audit.
**WORKTREE_UNMERGED_FEATURES:** battery C3, S3 storage/cloud/partition, storage-lifecycle experiments, phase2 HIL/FOTA.
**CANONICAL_R1_WORKTREE:** `/home/udaybhan/projects/Ghar_sajag_r1`. **CANONICAL_R1_BRANCH:** `feature/r1-commercial-baseline`.
**CANONICAL_DOCUMENTATION_ROOT:** R1 `docs/product/`, indexed domain docs and dated `docs/exec-plans/evidence/`.
**AGENTS_RECONCILIATION_REQUIRED:** none immediate; global universal policy, root shared rules, nested instructions only module-specific. Do not overwrite global instructions.
**BRANCH_INTEGRATION_PLAN:** after user approval, integrate only reviewed commits by explicit PR/normal fast-forward; record source/destination refs, preflight, impacted tests, intended files and resulting remote hash. No hidden copies or whole-branch cherry-pick.

This gives every session one source-controlled work-state/index and preserves dated evidence without erasing independent history.

## Risks and decisions awaiting user review

Risks: C3 code/evidence provenance differs across branches; S3 is not in canonical; P2-D contracts/workload block release; 32 C3 entries and retirement reporting constrain any scale-up; production deletion disabled; no physical S3 commercial storage/72h/power-cut/wear/heap/OTA proof; GS-148 status mismatch; PWA/account/commissioning acceptance needs full audit.

Review/approve or revise queue; identify C8 image/source and code-reconciliation route; decide GS-144 target/workload; provide/approve backend security and canonical trace contract; decide GS-147 scope; review GS-148 Jira status; approve any consolidation/archive separately. No Phase 2/3, GS-131 or GS-148 closure is recommended.

## Provenance and checks

Inventory used `git worktree list --porcelain`, each worktree status/HEAD/log, actual `git ls-remote`, ancestry/diff and targeted source/document searches. Jira search returned 142 issues; targeted descriptions/links/comments as stated above. Context preflight PASS in canonical R1 and S3 at `2026-10-09.001`. No build, test, flash, hardware, Jira mutation, merge, rebase, reset or cleanup was run.
