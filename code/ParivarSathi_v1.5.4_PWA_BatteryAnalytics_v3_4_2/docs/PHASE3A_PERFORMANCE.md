# Phase 3A Performance Baseline and Regression Budgets

Document revision: **P3A-R1**
Product version: **Parivar Saathi v1.5.4**
Historical Phase 2D qualification anchor: **`9499381`**

The measurements below are deterministic raw UTF-8/file byte counts from the
socket-free profiler. Timing and RSS are diagnostics only; they are not host
correctness limits.

Run:

```bash
make performance-profile
make performance-test
```

## Before / after

| Metric | Phase 2D before | Phase 3A after | Interpretation |
|---|---:|---:|---|
| Unique first-load static files | 76,177 B | 79,144 B | +2,967 B for the tested polling/bounding helper and complete offline module allowlist; still below 90,112 B budget |
| JavaScript including service worker | 58,541 B | 61,508 B | Source remains unbundled/no-framework and below 65,536 B budget |
| CSS | 14,948 B | 14,948 B | unchanged |
| Service worker | 757 B | 832 B | imported modules are now explicitly cached; dynamic APIs remain excluded |
| Initial Home dynamic payload | 29,986 B | 1,216 B | validation catalog (28,770 B) moved off startup and is fetched only when validation is run |
| Static + initial dynamic bytes | 106,163 B | 80,360 B | 25,803 B (24.3%) less transferred before Home is usable |
| Compact Home state | 1,216 B | 1,216 B | unchanged, bounded at 6,144 B |
| Full PWA state | 7,587 B | 7,587 B | unchanged, on-demand only |
| Devices registry API | 3,057 B | 3,057 B | unchanged |
| Today / Week / Month report | 798 / 1,893 / 6,336 B | same | bounded backend projection; default deterministic no-data fixture |
| Notification preferences | 235 B | 235 B | unchanged |
| Bounded notification history | not populated in original baseline | 5,940 B for 20 of 24 records | endpoint remains capped at 20 by the PWA path |
| Home / members / policy / network | 138 / 162 / 963 / 71 B | same | domain Settings payloads remain small and on demand |

No wall-clock speed improvement is claimed. The evidence supports transfer,
query-shape, render-frequency and boundedness improvements.

Final qualification fixes added small runtime sequencing support after the
original before/after capture. The final post-fix profiler reported a static
total of **80,542 B**, still within the established structural budget. The table
above remains the deterministic pre-qualification Phase 3A comparison; no
wall-clock claim is inferred from the later byte-count change.

## Request and render behavior

| Flow | Before | After |
|---|---|---|
| Initial Home | compact Home + validation catalog | compact Home only; no Reports/full state/history |
| Normal Home | compact request every 2 s; requests could overlap | one compact poller, overlap guard, unchanged DOM is not rebuilt |
| Devices | full state on entry and every 2 s | same authoritative cadence, overlap guard, unchanged cards are retained |
| Reports | on entry plus every 2 s; overlapping requests possible | on entry/period change plus bounded 4 s active refresh; quiet refresh cannot overlap |
| Settings | full state fetched on entry | no full state; each selected domain fetches its own bounded API |
| Background tab | continued state/report work | state/report polling pauses; browser-notification polling remains available; visibility return triggers immediate authoritative refresh |
| Repeated navigation | one global timer but repeated inactive-tab DOM rebuilds | one global timer; same-tab clicks are no-ops; only changed active-domain DOM renders |

Playwright captures request paths, DOM counts, timer/listener counts and Chromium
performance metrics as diagnostic attachments in
`tests/playwright/phase3a_performance.spec.ts`. Exact heap/RSS values are not
pass/fail assertions.

## Structural budgets

The machine-readable budgets are in
`tests/validation/phase3a_performance_budget.json`.

- Static budgets allow modest maintenance growth but reject a large framework,
  bundle or accidental asset.
- Payload budgets include headroom for the configured 25-device MEDIUM profile.
- Home events (20), notification history (20), report highlights (6), room
  activity (5), Month buckets (31) and service-worker entries (9) are explicit
  correctness bounds.
- No wall-clock or exact-memory threshold is enforced.

## Diagnostic runs

The P3A-R1 socket-free run reported:

- deterministic profiler: PASS; about 0.09 s; 331,776 B isolated database;
- SMALL stress: PASS; 120 accepted, 12 duplicate, 6 rejected, zero unexpected
  request failures; 352,256 B isolated database; about 0.28 s;
- MEDIUM stress: PASS; 2,500 accepted, 250 duplicate, 50 rejected, zero
  unexpected request failures; 1,183,744 B isolated database; about 11.7 s on
  the recorded run;
- MEDIUM browser payload maxima from the host projection: Home 4,153 B, full
  17,694 B, report 7,555 B;
- simulator RSS stayed approximately 4.25 MB during the sampled MEDIUM run;
  Python max-RSS rose from approximately 30.8 MB to 40.2 MB. This is a trend
  observation, not a portable acceptance limit.

Generated JSON is printed to stdout or may be written to an explicit temporary
path with `--output`; it is not committed as build output.

## Qualification status

Phase 3A is **COMPLETE / QUALIFIED**.

Final qualification evidence:
- all socket-free/compiled release stages: PASS;
- Python regression discovery: `96/96` PASS;
- JavaScript test files: `3/3` PASS;
- performance profile: PASS;
- SMALL deterministic stress: PASS;
- MEDIUM deterministic stress: PASS;
- mandatory Chromium desktop browser suite: PASS;
- mandatory Chromium mobile browser suite: PASS;
- authoritative `make release-gate-final`: PASS.

Codex remained unable to bind loopback sockets because of sandbox `EPERM`, so
socket-bound browser/final-gate execution was performed in normal WSL. The WSL
result is the authoritative qualification result.

Browser qualification found and corrected three runtime sequencing issues
before the final PASS:
1. Reports refresh scheduling is now self-scheduled from the latest Reports
   request completion instead of relying on Home-poll timer alignment.
2. Older Home poll snapshots are rejected when a newer explicit action result
   has already been applied.
3. A simulator reset increments a reset epoch; stale-response ordering compares
   epoch first and `simulation_now` only within the same epoch, so legitimate
   post-reset states are not rejected when simulator time moves backward.
