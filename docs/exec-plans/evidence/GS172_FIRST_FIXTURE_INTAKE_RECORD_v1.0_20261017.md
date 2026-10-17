# GS-172 First S3 Fixture Intake and Observation Authorization Record — v1.0

**Record date:** 2026-10-17  
**State:** INTAKE TEMPLATE / ALL PHYSICAL ACTIONS NO-GO / NOT_RUN  
**Purpose:** Turn design-level approval of GS-172 P0/P1/P10 (Jira comment #11307) into an exact first-fixture GO/NO-GO decision. This is **not** an authorization to connect, power, read, reset, flash, provision, observe, or manipulate any board.

**Source basis:** `feature/r1-commercial-baseline` at `072e94ee7185b3797cc83a4308331571cba17663` when this intake form was prepared. GS-172 SOP/matrix/fixture checklist/physical plan v1.0 (2026-10-17); GS-68 #11294; GS-40 #11293. Re-verify HEAD and current Jira decisions before any future use.

## 1. Decisions already approved — design direction only

| Decision | Recorded scope | Excluded |
|---|---|---|
| P0 | ONE disposable non-customer S3 qualification fixture in isolated TEST_ONLY trust/backend environment | No hardware action, physical-case GO, commercial roots/credentials/data/endpoints |
| P1 | Permanent HubId distinct from Home/Node; server-authoritative certificate-to-Hub/Home/epoch/revocation model | No production CA/issuer selection, credential generation, deployed ownership registry approval |
| P10 | One operator with independent evidence reviewer; quarantine failed units and do not reuse identity | No provisioning, rework or irreversible-action authorization |

P2–P8 remain under Security/technical review. P9 fixture- and operation-specific approval **NOT GRANTED**.

## 2. Pre-filled, source-verifiable baseline

| Field | Current value | Evidence limitation |
|---|---|---|
| Repository/branch | `udaybhan200683/Ghar_sajag`, `feature/r1-commercial-baseline` | Reverify at execution |
| Prior GS-172 design baseline | `072e94ee7185b3797cc83a4308331571cba17663` | Not an installed image |
| Hardware candidate class | ESP32-S3 N16R8, separate non-customer/disposable test Hub | **No individual board selected** |
| Prior C3 build candidate | SHA-256 `b4e2b1c1d370fd2da2a30aae52cfbc2f85e91d0ff3b39da41eef23816829fedb` | Historical build, not verified running |
| Prior S3 build candidate | SHA-256 `e09e9651160719673958fffdc5c06f7a1787eb31403384324fd421b8f15a3ea1` | Historical build, not verified running |
| SDK | ESP-IDF 6.0.3 reported in earlier non-flashing build | Qualifying image/config/component lock not selected |
| GS-68 D05/D12/D06 | TEST_ONLY provider/registry/signed-time software checks reported PASS | Target DS signer and trusted production composition absent |
| Current S3 production trust | `UnprovisionedS3CloudTrust` | Fail-closed; no commercial send |
| GS-40 | TEST_ONLY source-to-caregiver software checks reported PASS | PHY-GS40-01..06 remain NOT_RUN |
| GS-40 TC05 | Needs at least two independently enrolled Nodes or approved qualified profile fixture | Not available/identified |
| GS-114/C8 hardware/evidence | Existing protected historical assets | **Do not use, modify or relabel for this new fixture** |

**Public-repo privacy:** Record only a local non-sensitive fixture alias and redacted public metadata in Git/Jira. Keep exact serials, MAC addresses, physical location, private fixture contact details, unredacted security inventory and recovery credentials in a separately controlled private record, with only its reference/hash in this file. Never store private keys, raw eFuse key bytes, SSIDs/passwords or household data in source control.

## 3. Exact first-fixture intake — unresolved owner inputs

| Gate | Required source-bound record | Status |
|---|---|---|
| F01 fixture assignment | Unique **new** test fixture alias; explicit non-customer status; custodian; GS-114/C8 exclusion comparison | **BLOCKED — no fixture assigned** |
| F02 board provenance | S3 board maker/SKU and revision; N16R8 flash/PSRAM; protected hardware inventory reference | **BLOCKED — unknown** |
| F03 observer/power route | Exact approved adapter/cable/power path, reset/DTR/RTS effects, electrical and evidence-safety review | **BLOCKED — not established** |
| F04 recovery | Named operator, independent reviewer and recovery/quarantine owner; unexpected-reset recovery/stop policy | **BLOCKED — unassigned** |
| F05 source/image | Intended source SHA, test profile/config/partitions/SDK lock, non-flashing build and expected image digest | **BLOCKED — qualification image not selected** |
| F06 installed-state evidence | Non-resetting authorized method proving *running* firmware, slot, effective config and security state | **BLOCKED — no qualified observer or runtime receipt** |
| F07 trusted TEST_ONLY services | Isolated issuer, registry, time authority, backend/PWA, trust-root inventory and network separation | **BLOCKED — host simulation only** |
| F08 Node association | C3 fixture IDs, exact enrollment/session/generation/profile and pending EventKey baseline | **BLOCKED — no matched fixture** |
| F09 approval form | Signed fixture/action/case/image/plan-specific authorization, allowed interface, expiry, stop/recovery owner and evidence directory | **BLOCKED — not granted** |

No unknown field is auto-filled from MAC/USB guesses, simulated metadata, prior C8 fixtures, or image build hashes.

## 4. First possible physical action: identity-only, non-destructive observation

**GO requires F01–F06 and F09 to be complete and independently verified** (plus F07/F08 if requested observations involve trust, Node enrollment, or GS-40). For a first simple identity-only observation, explicitly approved operations must identify:

- Test-fixture alias + privately held exact hardware ID and board revision
- Source image/config digest expected for the *running* board, or a clearly scoped permitted baseline discovery method when unknown
- Exact observer/device interface, no-reset evidence, power/isolation plan and evidence path
- Approved **read-only** observations and prohibited operations
- Operator, independent reviewer, recovery/quarantine owner and stop conditions
- Expiry, approval record ID and case/plan hash

**No action is approved by the current P0/P1/P10 design sign-off.** USB/serial opens may reset this platform and cannot be assumed non-invasive. Do not supply or execute physical commands until a scoped observer procedure is reviewed and approved.

### Observation approval form (all pending)

| Authorization field | Value |
|---|---|
| Fixture alias / privately held hardware inventory ref | **PENDING** |
| Board revision and security-state provenance | **PENDING** |
| Operation: identity-only observation (specific list) | **PENDING** |
| Allowed adapter/power/interface and reset-safe proof | **PENDING** |
| Expected source/image/config/plan SHA-256 | **PENDING** |
| Evidence directory/manifest policy | **PENDING** |
| Named operator/reviewer/recovery owner | **PENDING** |
| Approval reference, approving authority, start/expiry | **PENDING — NOT GRANTED** |

## 5. Subsequent distinct gates — do not combine with intake approval

- **Wave T TEST_ONLY DS/mTLS/time:** qualified target DS signer and S3 trusted-time/provider composition, isolated issuer/registry/backend and test-only key-custody design, scoped Security and fixture authorization. GS68-PHY-001..005 only after these gates; never claim host-only signing is hardware DS proof.
- **GS-40 PHY-01..06:** real matched S3/C3 images, authoritative profiles/session and EventKey baseline, safe observers, isolated caregiver account/endpoints, and case-specific authorization. TC05 requires another independently enrolled Node or approved equivalent fixture.
- **Wave P commercial security:** P2–P8 Security approvals, real issuer/root and private-key custody, DS/eFuse/HMAC path, signed update/recovery GS-118/D15, Secure Boot/Flash Encryption/debug threat and recovery sign-off. Irreversible changes require their own exact, separately approved physical plan.

## 6. Next owner input and closeout

**The next missing factual input is identification of one distinct spare, non-customer ESP32-S3 N16R8 board for Wave T.** Once a fixture is named, produce its private inventory record, review its connection/observer/recovery design offline, and submit the exact identity-only observation permission for approval. If no spare fixture exists, keep physical NO-GO; do not repurpose GS-114/C8 boards.

**Current GO/NO-GO:** **NO-GO** for observation, DS/eFuse/key handling, firmware install, GS-68 PHY, GS-40 PHY, and production activation. No physical or production action was executed to prepare this record.

Related: [SOP](GS172_FIRST_DEVICE_PROVISIONING_SOP_v1.0_20261017.md), [decision matrix](GS172_SECURITY_DECISION_APPROVAL_MATRIX_v1.0_20261017.md), [fixture readiness](GS172_FIRST_FIXTURE_READINESS_CHECKLIST_v1.0_20261017.md), [physical acceptance](GS172_PHYSICAL_ACCEPTANCE_PLAN_v1.0_20261017.md).
