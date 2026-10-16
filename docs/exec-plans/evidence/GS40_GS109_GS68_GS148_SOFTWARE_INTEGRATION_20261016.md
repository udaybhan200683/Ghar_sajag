# GS-40 NodeHealth software integration checkpoint — 2026-10-16

## Scope and status

Owning issues: GS-109, GS-68, GS-148, GS-40. Jira inputs: GS-109 comment 11235, GS-68 comment 11236, GS-148 comment 11237, GS-40 comment 11238, and approved GS-68 architecture comment 11217. Canonical branch: `feature/r1-commercial-baseline`. Starting commit: `76516b963055977eab7cb2d2d084c69692d8690e`.

This checkpoint implements a typed TLS-verified Hub/Home/installation-epoch/time-readiness context, an additive bounded per-Node CloudSync status publication and HTTPS transport contract, SQLite latest-state backend ingest/read model, and caregiver PWA projection. Existing EventKey durable event/ACK/retry behavior remains on its existing path. NodeHealth has no EventKey and does not retire event records.

The software work is partial for production acceptance. The S3 product application still does not instantiate the CloudSync worker with an approved permanent Hub identity and trusted time/NodeHealth authority source. D05/D12 identity and key custody, D06 trusted-time behavior, and production S3 worker composition must be resolved before a real source-to-caregiver feed can run. No production credentials or endpoints were enabled. GS-40 software remains blocked from resuming physical acceptance.

## Implementation evidence

- Cloud mTLS authorization returns an immutable context only after TLS peer-chain verification, the current permanent-Hub certificate/fingerprint lookup, active Home/installation epoch check and explicit trusted-time readiness. Tests use temporary synthetic credentials.
- The existing CloudSync worker has a separate bounded status submission path. The HTTPS response must echo the exact logical Node, boot generation and source revision. Existing event journal, EventKey, ACK and retry behavior was not changed.
- Status ingest requires the typed authenticated Hub context, active Hub/Home/epoch and Node enrollment, an existing trusted profile, exact contact kind and monotonic source revision. SQLite keeps one current row per enrolled Node. Reads recheck current ownership/enrollment and derive ONLINE only through the inclusive lease, OFFLINE after strict expiry, and UNKNOWN when Hub/cloud source freshness is absent or stale.
- The backend response preserves Hub contact, backend reception and PWA snapshot timestamps independently. The caregiver view keeps Node communication/coverage separate from resident inactivity; unavailable/stale source renders UNKNOWN.
- Traceability registers `GS40-NODEHEALTH-CLOUD-001` to GS-116 stages `cloudsync-security-unit`, `cloud-contract`, `cpp`, `python` and `javascript`; the relevant stage inputs are updated without changing the parent `cloud-contract` fast/release policy. GS-130 source inventory and feature matrix consistency pass. Physical `PHY-GS40` remains BLOCKED / NOT_RUN.

## Executed validation

- `make cloudsync-security-ut`: TLS adapter 8/8, mTLS certificate tests 13/13, NodeHealth SQLite/API tests 5/5 — PASS.
- `make cpp-test`: 1,488 checks — PASS.
- `make p2d-cloud-contract-host-test`: transport and existing durable EventKey/receipt contract — PASS (`invalid_receipt_modes=15`, `pending=200`, `batch_peak=16`, `retry_peak=64`; persistence cuts PASS).
- `make app-test`: 24/24 — PASS, including stale Hub/cloud source renders caregiver NodeHealth UNKNOWN.
- `make validation-framework-test`: 47/47 — PASS.
- `make feature-coverage-test`: GS-130 traceability 208 features, 218 source modules, 24 physical cases; 22/22 mapping regressions — PASS. This is registration consistency only.
- `make gs130-hil-runner-test`: 70/70 — PASS; safe no-run/dry-run behavior retained.
- `test_gs40_qualification.py`: 17/17 — PASS.
- `make validation-backend`: backend receipts, ownership, CloudSync mTLS/simulation/integration, contracts, bridge, API/frontend, Python 514/514 and GS-130 runner 70/70 all PASS. Required P0 full-product stage ran 26/26 assertions and one Chromium test PASS but reports `product_status=PARTIAL`; aggregate therefore correctly FAILs. This pre-existing product status is preserved.
- `make validation-pwa`: 86/86 browser tests and all preceding stages PASS. P0 stage again reports 26/26 assertions and `product_status=PARTIAL`; aggregate correctly FAILs.
- `make validation-hub`: selected Hub regressions pass except existing journal migration gate (`clean migration commits`) and required P0 `product_status=PARTIAL`; aggregate FAIL. A concurrent host build initially produced `Text file busy` for feature-boundaries, which passed on a sequential rerun (133/133 checks).
- `make validation-contract`: CloudSync/security, contract, bridge and GS-130 runner stages PASS. Concurrent builds initially produced `Text file busy` for board-stack and sanitizer outputs; sequential reruns passed board-stack (10 cases / 398 checks) and `hub-storage-correctness-sanitize` (PASS). P0 `product_status=PARTIAL` remains the aggregate FAIL.
- `make feature-boundary-host-test`, `make board-stack-e2e-host-test`, `make hub-storage-correctness-sanitize` rerun sequentially — PASS.
- `python3 code/scripts/check_feature_traceability.py`: GS130 TRACEABILITY PASS, 208 features / 218 modules / 24 physical cases. No physical proof inferred.
- ESP-IDF 6.0.3 `python3 code/scripts/build_validation_targets.py`: C3 PASS, 937,536 bytes, image SHA-256 `d94e011abd0e28b31cadb4dee2ff6451b0f5311c2783cdcbb2a631c03e86f765`; S3 PASS, 1,887,200 bytes, image SHA-256 `507df1e2a26707bc7c5267b98c369dd00e5141a29c6ccf687b5a06908d4480ed`. Both fit their configured 1,966,080-byte and 4,194,304-byte application slots. Build source head `76516b963055977eab7cb2d2d084c69692d8690e`, working-tree/source fingerprint `ba043ee9da757a1cf0285223b94e145a4ed4478b06d07e74ad03bff2708ae913`, production profiles with `GS_HIL_BUILD=OFF`, IDF 6.0.3. Target compilation is not physical, TLS-operation or signing qualification.

No board, serial port or USB interface was accessed. No flash, reset, eFuse, Secure Boot/Flash Encryption, credential provisioning, live production CloudSync, OTA, or physical HIL operation occurred. `PHY-GS40` and `PHY-GS68-CLOUD-MTLS` remain NOT_RUN; P0 remains PARTIAL; the Hub migration FAIL is unchanged.

## Remaining production and physical gates

1. Approve/define D05/D12 production permanent Hub certificate/key custody and verifier, D06 trusted Hub time, and composition contract for the S3 Hub owner/runtime to supply current authenticated Node session/enrollment/contact to the existing CloudSync worker. Keep fail-closed until approved.
2. Re-run the applicable component/integration gates after production source composition; then validate real authenticated Hub-to-backend-to-caregiver behavior in software with deployment identity mapping.
3. Keep GS-40 physical cases NOT_RUN until exact fixture/image/config/session prerequisites and case-specific approval are met. Existing GS-40 P0 PARTIAL and Hub journal migration FAIL are not waived by this software checkpoint.
4. Physical approval, live credentials and production deployment remain separate. No physical operation is authorized by this report.

Commit/push/Jira evidence is recorded in the follow-up section of `docs/product/R1_WORK_STATE.md` and the linked GS-109/GS-68/GS-148/GS-40 Jira comments.
