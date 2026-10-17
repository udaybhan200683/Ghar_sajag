# GS-40 NodeHealth software integration checkpoint — 2026-10-16

## Follow-up — D05/D12/D06 integration seam — 2026-10-17

This dated continuation supersedes the earlier follow-up's description of
unimplemented provider *seams*. The S3 adapter now consumes shared typed
identity/current-authority/time interfaces; the app remains wired to the
explicit unprovisioned implementation and therefore still cannot send
commercial CloudSync. TEST_ONLY host coverage now joins current HubRuntime
contact through the existing bounded NodeHealth CloudSync publisher, exercises
ownership transfer/revocation, per-device RSA-3072 DS credential constraints,
TLS time readiness, authenticated-time recovery/rollback/floor persistence,
and rejects proof nonce reuse. Backend verifier code and durable event/ACK
semantics are unchanged.

The HTTPS adapter sets ESP system time only from a fresh authenticated time
snapshot before ESP-TLS certificate checks. It requires a Hub identity,
credential generation/fingerprint, cloud-client purpose, RSA-3072 DS context,
client certificate and TLS 1.2; no Authorization bearer fallback exists.
Missing provider, endpoint or trust root remains fail closed. The abstract D06
verifier, CSPRNG challenge source, durable target floor/boot-counter store and
approved freshness/checkpoint thresholds do not have production implementations.

Final-software-source focused results: `make cloudsync-security-ut` PASS
(mTLS 9/9, D05/D12/D06/GS-40 provider suites, backend security 14/14,
NodeHealth 5/5); `make cpp-test` PASS (1,509); P2D durable CloudSync/EventKey
contract PASS (invalid receipts 15, pending 200, batch 16, retry 64, persistence
cuts 2); local TLS worker/API bridge 1/1 PASS; validation framework 47/47;
feature traceability 208 features / 220 modules / 24 physical cases / 22
mapping tests PASS. The ESP-IDF 6.0.3 non-flashing S3 `GS_HIL_BUILD=OFF`
production-profile app passed at 2,168,128 bytes in its 4 MiB slot, image
SHA-256 `2052ba8d233b66bd753d5f6572c01acd4a4cd3daf6017dde70c27d628fde69b5`,
sdkconfig SHA-256
`79aa5a0b45b155a97e60feb1f93bc7b653b10d745aea932d57eac9f6bc5da27b`. It
embedded the unchanged C3 app at 937,536 bytes, SHA-256
`d94e011abd0e28b31cadb4dee2ff6451b0f5311c2783cdcbb2a631c03e86f765`. The
initial configure with the ESP-IDF component manager disabled failed to resolve
the pinned LittleFS dependency; rerun with the existing lockfile/manager enabled
passed. Managed-component file hashes and `dependencies.lock` stayed unchanged.
The build emitted one non-fatal `retirement_ack_sent` unused-variable warning
in the Hub adapter. Historical backend
and caregiver PWA results remain PASS; no browser/backend implementation was
changed in this increment.

Remaining owners: GS-68/GS-109 must supply approved production D05/D12 identity,
credential custody and current Home/revocation source plus D06 authenticated
bootstrap/verifier, durable target anti-rollback store and policy thresholds.
The software CloudSync path remains TEST_ONLY; GS-40 and GS-68 physical gates
remain BLOCKED/NOT_RUN pending those inputs and a separately identified,
owner-authorized fixture. No serial, USB, board, flash, reset, credential issue,
eFuse, production endpoint or physical operation was accessed. Implementation
commit `42f74034d5f1f5acd2c605ffee37f540da42ef7e` was pushed to the canonical
branch and matched GitHub. Jira comments were added without workflow changes:
GS-68 `11286`, GS-109 `11287`, GS-40 `11288`; GS-148 was not updated because
its backend/PWA code was unchanged.

## Follow-up — S3 runtime composition (2026-10-16)

This follow-up supersedes the earlier statement below that the S3 product
application had no CloudSync worker composition. The canonical S3 owner now
refreshes a bounded immutable NodeHealth snapshot every five seconds and a
separate five-second network worker publishes at most four current states per
pass over the existing HTTPS CloudSync status channel. The adapter maps the
configured 300/910 and trusted legacy 60/190 and 120/310 profiles from current
installed policy and HubRuntime lease state. WAN association/IP, bounded retry
and authority rechecks are integrated. Event transport and durable EventKey,
ACK, replay and retirement behavior are unchanged.

The current S3 `S3CloudTrustProvisioning` and TLS identity implementation are
explicit unprovisioned stubs that return unavailable. Thus runtime wiring is
software-complete, but commercial transmission stays disabled until D05/D12
permanent Hub identity, key custody, verifier and current ownership/revocation
source, plus D06 trusted Hub time, are approved and supplied through the
thread-safe authority-provider seam. The provider may not use untrusted SNTP,
MAC-derived identity or caller-supplied authority. No production credential,
service or physical board was used.

Latest validation on this change set: `make -C code cpp-test` 1,509 checks
PASS; CloudSync adapter 8/8, mTLS tests 13/13, NodeHealth API/model 5/5, P2D
EventKey/receipt contract PASS, app tests 24/24, backend Python 523 PASS,
caregiver browser 86/86 PASS. Hub validation retains the existing migration
assertion failure and P0 `PARTIAL`; contract/backend/PWA aggregates report the
required P0 `PARTIAL` despite 26/26 assertions and the Chromium scenario
passing. Final frozen-source Hub and contract reports are
`code/evidence/validation_framework/hub-1792177423393802158/report.json` and
`code/evidence/validation_framework/contract-1792177035924980667/report.json`;
both have `source_unchanged=true` and fingerprint
`478ca9b8d83835ebf5ebe4a9d3c500e1fc2cd54946573ba3bc770e9bccd9822c`. ESP-IDF
6.0.3 non-flashing S3 production-profile build passes at
2,166,688 bytes in a 4 MiB app slot, image SHA-256
`e39dc13190b8f23d95a82f972ce9a896ce5c9f87a1ea33565ab31ff07e88e1d5`. Feature
coverage integrity is 208 features, 218 modules, 24 physical cases and 22/22
mapping tests. Physical
cases remain NOT_RUN. Exact commit/push state and the dated Jira follow-up are
recorded at delivery.

## Scope and status

Owning issues: GS-109, GS-68, GS-148, GS-40. Jira inputs: GS-109 comment 11235, GS-68 comment 11236, GS-148 comment 11237, GS-40 comment 11238, and approved GS-68 architecture comment 11217. Canonical branch: `feature/r1-commercial-baseline`. Starting commit: `76516b963055977eab7cb2d2d084c69692d8690e`.

At this original checkpoint, the software implemented a typed TLS-verified Hub/Home/installation-epoch/time-readiness context, an additive bounded per-Node CloudSync status publication and HTTPS transport contract, SQLite latest-state backend ingest/read model, and caregiver PWA projection. The S3 runtime composition was still missing then and is described by the follow-up above. Existing EventKey durable event/ACK/retry behavior remains on its existing path. NodeHealth has no EventKey and does not retire event records.

Production acceptance remains partial. At that original checkpoint the S3 product
application did not instantiate the CloudSync worker with an approved permanent
Hub identity and trusted time/NodeHealth authority source. The follow-up above
composes the software worker, but D05/D12 identity and key custody and D06
trusted-time behavior must be approved and supplied before a real
source-to-caregiver feed can run. No production credentials or endpoints were
enabled. GS-40 physical acceptance remains blocked.

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
