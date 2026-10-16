# R1 72-hour storage checkpoint handoff — 2026-10-08

**PAUSED at the user's request.** Stop analysis, simulations, optimization and
feature development after this checkpoint. Resume only in a separately authorized
task. No analysis/build/test command was running when checkpointing began.

Branch: `feature/r1-hub-storage-lifecycle`. Context: `2026-10-07.003`.
Pre-checkpoint HEAD: `29fca17f9407706d901ebbeaecf7f70773f8eb1c`.
Context preflight: **PASS**, matching canonical
`/home/udaybhan/projects/Ghar_sajag_r1@feature/r1-commercial-baseline`.
The checkpoint commit is the commit containing this handoff; obtain its hash with
`git log -1 --format=%H -- docs/exec-plans/evidence/R1_STORAGE_72H_CHECKPOINT_HANDOFF_20261008.md`.

## Findings and limits

Keep NVS as the preferred technical candidate, raw as fallback, and the current
4 MiB ESP32 Hub as the baseline. Final partition remains **UNDECIDED**; architecture
freeze and production integration remain **NO**. User-approved direction is a
72-hour internet-only outage target, loss-aware eligible ordinary-motion
aggregation, exact important evidence, local monitoring/coverage continuity,
backend catch-up and durable-before-ACK. This is not an unlimited event guarantee.

Candidate summaries retain separate ordinary Motion points, source membership and
timing; a 60-minute container does not imply continuous presence. Native Node
MotionSummary bodies remain exact because their millisecond endpoints/counts
cannot safely become the candidate point summary. Safety-dependent, uncertain,
unprocessed or already submitted exact observations are excluded. Actual rule
processing must not substitute a history summary for the existing MotionSummary
enum. A rolling 72-hour interval can intersect four local calendar dates.

The host model preserves retry witnesses after body compaction and requires
selected summary plus processed-state checkpoint before retirement. Backend
completion is independent of Node retirement. The proposed exclusive source-claim,
immutable summary receipt, coverage and revision API does **not** exist in the
current backend. Host atomic-store/server assumptions are not production proofs.

| Capacity | Final SDK-emulated capacity results | Physical churn peak / limiting OTA margin |
|---|---|---|
| 128 KiB | All final tested full fixtures stop, including typical NORMAL; earlier narrower proofs remain scoped | Failure can occupy 131,072 B / 101,456 B |
| 192 KiB | Typical NORMAL profiles pass; worst-size NORMAL and HIGH fail | Passing peak 192,512 B, one erased page / 35,920 B |
| 256 KiB | Worst-size NORMAL ordinary/simultaneous and typical HIGH pass; worst-size mixed/door-heavy NORMAL and HIGH fail | Passing peak 258,048 B, one erased page / 35,920 B |

One erased page is internal GC space, not guaranteed application headroom. Passing
fixture operations demonstrate selected forward progress, not a universal allocator
guard. No general 72-hour guarantee is established at any reviewed capacity.

Modeled protected peaks (worst-supported 103-byte exact fallback, conditional
32-event critical alternative): NORMAL ordinary **237,568 B** (430 exact originals,
288 new summaries; essential and native-summary subsets overlap); NORMAL mixed
**282,624 B**; HIGH ordinary **536,576 B**; STRESS ordinary **5,132,288 B**.
Typical ordinary NORMAL/HIGH peaks are 151,552/221,184 B and cannot establish
worst-case admission. Source rates are engineering scenarios, not arrival bounds.

Legal temporary partition layouts were validated with the SDK generator; no CSV
was changed. 192 KiB has no limiting dual-OTA image-margin advantage over 256 KiB
because of app alignment. Current image 1,864,624 B; storage integration growth is
unmeasured. Proposed RAM is **42,749 B plus NVS internals**; target heap is UNPROVEN.
NORMAL 72-hour dummy schedule: 970,944 programmed B, 185 erases, max 7/sector;
amplification 1.189578 against all changed values, 6.658328 against source HOT
bodies. HIGH/STRESS complete schedules stop at capacity and remain UNPROVEN.
No flash lifetime or target hardware qualification is claimed.

## Preserved validation

- HOST PROVEN: 14 semantic model tests pass; focused actual RulesCore test and
  relevant existing lifecycle/density/admission/backend-completion regressions pass.
- SDK NVS EMULATED: capacity suite 54 cases, 15 passes and 39 expected capacity
  stops. Capacity stops are limitations, not successful retention guarantees.
- SDK NVS EMULATED: 60 sampled GC-primed interruption cases pass, including cuts
  1071/1072/1073; old or new complete child bytes survive. Prior cut1072 diagnosis
  remains FAULT_INJECTION_MODEL_DEFECT. Arbitrary brownout/partial erase is untested.
- Scoped ASan/UBSan: focused rules and 60 NVS fault cases pass. NVS probe translation
  unit is instrumented; SDK archives are not, leak detection is disabled.
- HIGH/STRESS full 72-hour wear and worst-size retention fail to complete;
  production authentication/root/admission, actual summary serialization/reducer,
  physical reserve use and target RAM/image/wear/recovery remain UNPROVEN.

All commands, fixture parameters, exits and raw logs are linked from
[the focused evidence](R1_STORAGE_72H_AGGREGATION_CAPACITY_20261008.md).
`R1_STORAGE_72H_PRE_STAGE_AUDIT_20261008.log` preserves explicitly superseded
development measurements; use the final logs for capacity/wear conclusions.

## Pending decisions and next-task direction

Final critical/safety classification, exact-volume envelope, reserve sizes,
saturation/backpressure/degraded-status semantics, late/clock/day revisions,
summary backend contract and partition change require separate approval. No new
LOCKED decision or context version was committed: the user's checkpoint direction
defers governance recording. Follow GS-D024 and promote canonical documentation
explicitly before implementation depending on a newly locked requirement. Canonical
worktree and context remain unchanged; do not silently promote this branch.

**Additional user direction for the NEXT task:** investigate Node-side consolidation
of repeated ordinary PIR motion; consider activity START/END and last-motion
tracking. Preserve exact door and safety events. Future bed sensors may track
occupancy sessions locally. Keep cross-sensor routine learning at the Hub. Do not
change production Node firmware now. Inspect/reuse existing ActivityEpisode
behavior before proposing changes; internet outage is separate from radio outage.

Technical blockers: bounded authenticated admission/report/selected-root state,
crash-safe summary/backend ownership implementation, guaranteed next-operation/GC
allocation at saturation, routine-learning coverage/revision semantics, realistic
target RAM/OTA growth/wear and physical power-failure qualification. Node-side
consolidation may change volume assumptions; it is not yet a proven capacity fix.

## Resume commands (do not run during this pause)

Read this handoff and the focused evidence first; reuse passed evidence and rerun
only suites invalidated by the next task's changed assumptions.

```bash
cd /home/udaybhan/projects/Ghar_sajag_r1_storage
tools/context/ghar_sajag_context_preflight.sh
git status --short
git branch --show-current
git rev-parse HEAD
cat docs/product/CONTEXT_VERSION
base=code/ParivarSathi_v1.5.4_PWA_BatteryAnalytics_v3_4_2
probe=$base/host/storage/nvs_runtime_probe
python3 "$base/host/storage/offline_72h_model.py" --output /tmp/gs-72h-cases.json
python3 "$base/host/storage/test_offline_72h_model.py"
export IDF_PATH=/home/udaybhan/.espressif/v6.0.3/esp-idf
export PATH=/tmp/gs-diag-bin:$PATH
export RUBYLIB=/tmp/gs-ruby/usr/lib/ruby/3.3.0:/tmp/gs-ruby/usr/lib/x86_64-linux-gnu/ruby/3.3.0
export LD_LIBRARY_PATH=/tmp/gs-ruby/usr/lib/x86_64-linux-gnu:/tmp/gs-libbsd-dev/usr/lib/x86_64-linux-gnu
cmake --build "$probe/build"
python3 "$probe/run_offline.py" --cases /tmp/gs-72h-cases.json --suite capacity
python3 "$probe/run_offline.py" --cases /tmp/gs-72h-cases.json --suite schedule
python3 "$probe/run_offline.py" --cases /tmp/gs-72h-cases.json --suite fault
```

The `/tmp` helper paths belong to the current prepared host environment; if absent
on resume, use the existing NVS probe README/environment instructions. Actual
rules, sanitizer and temporary partition-generator commands are in the evidence.

Checkpoint scope: host-only model/tests/probe, evidence logs, ExecPlan and this
handoff. Quick checkpoint checks only: preflight, Git whitespace/staged-scope,
Python AST syntax and preserved-log summaries. No new simulation/test campaign.
User-owned `prompt.txt` remains unchanged and uncommitted; expected final status
is `?? prompt.txt`. Production firmware, frozen codec, partitions, backend/PWA,
canonical context, BAT-C8, Jira and hardware remain untouched.
