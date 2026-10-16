# Canonical Consolidation and Cleanup Manifest — 2026-10-16

## Scope and safety state

This manifest records the read-only audit and isolated factory integration preparation for GS-166/168 and the content reconciliation of the CloudSync feasibility branch. It does not implement GS-167 or GS-169.

Canonical is `/home/udaybhan/projects/Ghar_sajag_r1`, branch `feature/r1-commercial-baseline`. At audit start, local and origin were both `6ab7883d7edf0e56f60f80356f418824dd9a1721`; canonical context preflight passed. The tracked tree was clean. Existing canonical untracked PWA assets, S3 `managed_components/`, and C8/GS-40 physical evidence were present and left untouched.

At audit time a live Codex process had its working directory in canonical (PIDs 678231/678242, started 2026-10-16 05:35 UTC). A separate live Codex process had its working directory in the CloudSync feasibility worktree (PIDs 744572/744583, started 2026-10-16 10:10 UTC). Neither task was interrupted. Canonical commits, pushes, branch deletion and worktree removal are therefore deferred until those owners release their worktrees and refs are reverified.

The factory branch had no registered local worktree. The candidate remote tip was `4eab738e65fd393f8d866d0eeebdf9e060234df5`. A normal merge of that ref into a temporary branch based on canonical was prepared at `/tmp/ghar-sajag-canonical-consolidation-20261016`; see the exact tests below. It is not yet integrated into canonical or pushed.

## GS-166/168 factory integration

The factory branch differs from canonical by exactly these four added tracked files:

- `code/tools/factory/pilot_test_issuer.py`
- `code/tests/python/test_gs168_pilot_issuer.py`
- `code/tools/factory/GS168_TEST_ONLY_README.md`
- `docs/exec-plans/GS166_PILOT_PROVISIONING_CONTRACT.md`

The isolated normal merge applied without conflict and did not modify existing CloudSync, GS-40/GS-114 evidence, backend, PWA, or validation-policy files. Source Jira comments GS-166/168 11243/11244 describe the owner-approved scope and prior test evidence. The contract and README keep station CLI/registry work (GS-167/169) out of scope, and keep real issuance/physical qualification under GS-172.

Validation on the merged temporary tree:

- `python3 -m unittest discover -s code/tests/python -p 'test_gs168_pilot_issuer.py' -v`: **9/9 PASS**.
- `GS168_TEST_100=1 python3 -m unittest discover -s code/tests/python -p 'test_gs168_pilot_issuer.py' -v`: **9/9 PASS**, including the sequential 100-identity synthetic batch.
- Python syntax/import checks: PASS (`py_compile` for issuer/test and direct import of the issuer API).
- `git diff --check feature/r1-commercial-baseline...HEAD`: PASS.
- Production-boundary inspection: no issuer/test-helper import or call in backend, firmware, build scripts or the GS-68 HIL tools. Issuer module imports only Python standard libraries and `cryptography`; synthetic CA signing key is generated in process memory. No production credential, secret, network connection or device operation was used.
- No existing runtime dependencies changed, so no broader component regression was selected. GS-116/GS-130 permanent factory end-to-end registration remains owned by the future GS-171 scope; no gate policy was modified here.

## GS-68/109 feasibility branch content reconciliation

Current refs were fetched before comparison. Common base is `12eae946db1ce8c810c9cc7df8e2c17d27d30889`. The remote feasibility tip is `e740f99d094b4a0ef7397f0a506e8f089fb5d261`; the canonical tree is newer and the feasibility ref is not an ancestor of canonical. The feasibility branch has 16 source-only commits after the common base, but the tree comparison is decisive for cleanup:

- All **49** paths changed by the feasibility branch are present in canonical.
- **30/49** are byte-identical at the current refs, including the bounded GS-68 diagnostic protocol, S3 diagnostic target, C3 observer implementation/profile, build scripts, runner/backend tooling, runner tests and dated GS-68 physical-HIL evidence/plans.
- The remaining **19/49** overlap files differ. Source-side added lines are older fixture/build/gate/documentation fragments; current canonical retains later NodeHealth, BAT-C8, GS-40 qualification and validation-stage content. Canonical has newer content in each overlapping path. No source-only path is absent from canonical.
- The source branch tree lacks later canonical GS-40/GS-109/GS-148 NodeHealth implementation and evidence, so replacing canonical with this branch or merging its full tree would regress current functionality and erase canonical qualification records.
- Classification: identical GS-68 content = **Already integrated**; older source variants in the 19 overlapping files = **Superseded**; stale C8/GS-40/test-gate/work-state fragments = **Obsolete/test-only** where they describe branch-era context. **Still required additions: none identified. Undetermined items: none in the tracked-tree comparison.**

This is a content-level decision, not a `git branch --merged` decision. Although no further CloudSync code needs selective integration, its branch/worktree cannot be deleted while the live Codex process owns the worktree. Recheck the branch tip, untracked/ignored assets and ownership before any later removal. Preserve the shared untracked `managed_components/` tree; its tree hash matched canonical at audit time: `a2a9e24c420e3e633a9943e3e02564b8d8af1d29e33b6a8077fdd345b28574a7` (118 files, 2,117,834 bytes).

No CloudSync test suite was rerun because no CloudSync source was integrated or changed in this audit. Canonical NodeHealth, P0 PARTIAL, Hub migration FAIL, and physical NOT_RUN records remain unchanged.

## Archive audit

`/home/udaybhan/projects/_artifacts` was retained. Its relevant `Ghar_sajag` archive contains:

- `CloudSyncIntegration/ad6df017_20261016/`: **666 MiB**, 4,995 regular files plus inventory directories/records; contains the prior integration source snapshot, reports, binaries, test outputs, generated caches and `LOCAL_ASSET_MANIFEST.json`. All 4,996 file entries in the manifest were hash/size checked; **0 missing, 0 mismatched**.
- `GS68/20261016_M9cHfJ/`: five files, 564 KiB total; includes `gs_r1_s3_hub.bin`, build log, profile defaults and report. All four entries in `SHA256SUMS.json` were hash/size checked; **0 missing, 0 mismatched**.

Classification:

- GS-68 firmware image, profile, build report/log and checksum manifest: **Unique qualification/engineering evidence — RETAIN**.
- CloudSync integration source snapshot, test receipts, runner reports, image/test artifacts and source asset manifest: **Archived engineering material — RETAIN**.
- `code/build/`, Python `__pycache__/` and other generated binaries/caches inside the archived CloudSync snapshot: **possible reproducible-cache review candidates only**. They are included in a verified archive manifest and were not removed; exact repro equivalence and whether any reports share those paths have not been established.
- Unknown-origin, untracked or ignored data in any worktree: **RETAIN**.

**Files removed: none.** No exact duplicate was deleted. Any later archive pruning requires a separate path-level duplicate/reproducibility check and a new verified recovery manifest before removal.

## Cleanup disposition and next safe action

- Factory remote branch: **retain for now**; its changes are prepared and tested but not yet on canonical. After normal canonical integration and remote verification, recheck its tip and then consider ordinary remote deletion. There is no local factory worktree to remove.
- CloudSync local/remote branch and `/home/udaybhan/projects/Ghar_sajag_r1_cloudsync_mtls`: **retain** because a live Codex process owns that worktree, despite current content being integrated/superseded.
- Canonical worktree/branch: **retain**; currently owned by a live Codex process.
- Other registered worktrees (`/home/udaybhan/projects/Ghar_sajag` detached and `/tmp/ghar-sajag-gs40-qualification`): outside the two feature candidates, retained and untouched.
- No board/USB/serial access, flash/reset, eFuse/security operation, production credential action or commercial endpoint connection occurred.

Next action: when canonical and the CloudSync worktree are confirmed quiescent, re-fetch and verify all refs/statuses, merge the tested factory source normally into canonical, run the focused tests again on the integrated canonical tree, commit/push and verify exact remote SHA. Only then post factual GS-166/168 Jira comments. Reassess each candidate branch/worktree independently; retain anything whose process ownership or complete asset inventory is uncertain.
