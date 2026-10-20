+# GS-58 Hub Wi-Fi audit and decision gate — 2026-10-19

## Checkpoint

Owning Jira: GS-58. Scope: S3 Hub Wi-Fi onboarding/reconnect and recovery across the existing Hub/Node/CloudSync interfaces. Affected components: S3 Hub target Wi-Fi/ESP-NOW startup, C3 Node channel/session recovery, existing Hub CloudSync/status path. No code or product behavior has been changed.

Canonical baseline fetched: `4fbb8afbfb95a128fa942ac260939601af817411`. New isolated worktree: `/home/udaybhan/projects/Ghar_sajag_gs58`, branch `feature/gs-58-hub-wifi`. Context preflight from that worktree: PASS, local/canonical context `2026-10-13.001`. The canonical GS-179 worktree has active uncommitted changes; it was not modified. GS-165 worktree/branch was preserved. Jira GS-58 is being moved to In Progress for this analysis checkpoint.

No tests or target build were run because implementation is stopped at unresolved product/security decisions. No hardware, USB/serial, credentials, production service, flash, reset or eFuse was accessed. Canonical `R1_WORK_STATE.md` is not edited in this branch checkpoint because the active GS-179 writer has uncommitted edits to that shared file; reconcile this handoff during a reviewed integration window.

## Source findings

- GS-58 Jira description accepts “Hub reconnects predictably and state/replay remain correct across outages.” Its only comment says the item is required for R1. It does not select a provisioning UX, credential-at-rest method, or shared-radio channel policy.
- The normal ESP32-S3 product profile starts Wi-Fi STA but has no Wi-Fi credential source or association configured. The diagnostic profile starts STA only and explicitly has no persistent Wi-Fi configuration.
- `code/firmware/hub/target/esp32s3/gs40_test_only_runtime.cpp` is guarded TEST_ONLY code. It accepts Wi-Fi material from the TEST_ONLY envelope, places it in RAM-configured ESP-IDF Wi-Fi storage, clears its input copy, and currently rejects a connected AP whose primary channel is not 1. This is not a customer provisioning path.
- Existing Hub and C3 target adapters set `kEspNowChannel = 1`; the C3 restores that channel after light sleep. This is also asserted by validation. Wi-Fi STA association normally follows the AP's channel, so supporting arbitrary home-router channels needs an approved coexistence/recovery policy. Channel migration also affects authenticated session rejoin; event identity, durable-before-ACK, retry, replay and retirement semantics must remain unchanged.
- S3 defaults do not establish a commercial credential-protection/eFuse profile. GS-D032 and the GS-172 security matrix leave trust/key custody and security provisioning decisions open; GS-172 P4 explicitly treats Secure Boot/Flash Encryption and irreversible setup as separately reviewed, unqualified work.
- The S3 CloudSync worker and existing NodeHealth/status path are present, but production trust remains fail-closed on `UnprovisionedS3CloudTrust`. Current status consumers distinguish authenticated backend freshness from local Node liveness. `cloud_wan_ready()` checks AP association, IP and gateway; this alone does not prove WAN reachability or authenticated CloudSync. GS-D032 / D05-D12-D06 production authority, credentials and authenticated-time mechanisms remain unresolved.

## Decision requests

### GS58-D1 — Authorized Wi-Fi onboarding channel and installer authorization

**Decision required:** Select the customer/installer method for entering or selecting home Wi-Fi credentials and the proof that the operator is authorized to configure this Hub.

**Why:** GS-58 requires authorized onboarding, but no approved R1 customer interaction or installer authorization contract is present. Existing USB/Serial-JTAG configuration is explicitly TEST_ONLY and cannot be promoted to the customer path by reuse.

**Options:**
1. Integrate with an already approved authenticated installation flow, if its owner confirms it supplies this authorization and a local target transport.
2. Approve a new local BLE or device-hosted setup flow, including its installer proof, pairing, failure and recovery semantics.
3. Restrict pilot installation to a separately defined attended service procedure; this increases operator friction and still needs an approved trust channel.

**Recommendation:** Reuse an existing authenticated installation boundary if one is approved; otherwise explicitly approve a small local setup flow before coding. Do not accept an unauthenticated open setup AP or treat network possession alone as Home/installer authority.

**Impact if deferred:** Customer onboarding implementation remains blocked; only read-only analysis can continue.

**Approval needed from:** Product owner and Security/GS-109 owner.

### GS58-D2 — Protection and lifecycle of stored Wi-Fi credentials

**Decision required:** Select where credentials persist, the cryptographic protection/key source, and the authorized replace/delete behavior.

**Why:** Restart reconnection requires persistent credentials, while plaintext or test-profile NVS would expose household network secrets. The S3 security boot/key-storage profile is not approved or qualified.

**Options:**
1. Persist through ESP-IDF encrypted NVS backed by the approved per-device Flash Encryption/boot-security provisioning path.
2. Store an application-encrypted credential object under a separately approved per-device protected key provider.
3. Keep credentials volatile and require reconfiguration after every reboot; this fails the requested reconnect behavior and is not a viable R1 completion.

**Recommendation:** Option 1, but only after Security approves the exact per-device key/boot provisioning, storage partition and erase/replace semantics under GS-172/GS-68. Do not persist credentials until that prerequisite is approved.

**Impact if deferred:** Restart recovery cannot be delivered safely; protected hardware/security provisioning remains outside this software task and no fuse action is authorized here.

**Approval needed from:** Product owner and Security/firmware security owner.

### GS58-D3 — Wi-Fi STA and ESP-NOW channel coexistence

**Decision required:** Select the pilot channel policy when a home AP is not on channel 1, including how C3 Nodes discover/accept the channel and how fresh authenticated sessions are recovered.

**Why:** The current C3 and Hub adapters use channel 1; the only S3 Wi-Fi connection example rejects any AP on another channel. Generic home Wi-Fi and current fixed-channel radio behavior cannot both be promised without a policy.

**Options:**
1. Require the installer's router/AP to use channel 1. Low firmware change, poor customer compatibility and fragile if the router auto-selects another channel.
2. Coordinate a versioned, authenticated Hub-to-Node channel change to the AP channel, with bounded scan/rejoin and fresh session establishment. Better customer behavior; changes a shared radio/session contract and requires compatibility tests.
3. Add a second radio or approved time-sliced radio architecture. Hardware/cost/complexity impact and no current authorization.

**Recommendation:** Option 2 for the commercial product, preserving the existing event/session invariants and defining mixed-version behavior before implementation. Do not change the protocol or Node firmware until this is approved.

**Impact if deferred:** Generic home-router support and secure C3/S3 coexistence remain blocked. Restricting channel 1 would make onboarding unreliable for pilot homes.

**Approval needed from:** Product owner and Hub/Node protocol/security owner.

### GS58-D4 — Cloud recovery boundary and status claim

**Decision required:** Confirm that GS-58 will use the existing CloudSync authority/provider seam and must report Wi-Fi association, WAN reachability, cloud authentication and end-to-end monitoring as distinct states; commercial cloud delivery remains fail-closed until GS-68/GS-109/GS-148 approve and provide production trust inputs.

**Why:** The user request requires CloudSync to resume after network and authenticated authority recover, but current S3 production trust is intentionally unprovisioned. AP/IP/gateway is not evidence of internet or authenticated cloud availability.

**Options:**
1. Keep GS-58 bounded to Wi-Fi/reconnect and truthful network status; use the existing provider seam and leave cloud status unavailable until approved trust is supplied by the owning security/cloud work.
2. Expand GS-58 to also choose and implement production credential/time/authority mechanisms. This overlaps GS-68/GS-109/GS-148 and contradicts their open decision boundary without separate approval.

**Recommendation:** Option 1. GS-58 should not invent or replace production CloudSync trust. Integration must show “monitoring unavailable/stale” until the existing authority and authenticated CloudSync path are ready, then retry automatically through existing workers.

**Impact if deferred:** The complete cloud-resume criterion cannot be represented as commercially ready; network-only software work can resume after D1–D3 are approved, but production monitoring remains blocked on the named security/cloud dependencies.

**Approval needed from:** Product owner; GS-68/GS-109/GS-148 owners for the provider dependency.

## Validation plan once decisions are recorded

Register permanent tests using GS-116/GS-130. Affected scope is S3 Hub, C3 Node, Hub/Node/shared contracts, and CloudSync status contracts if modified. Add positive, wrong-credential, AP/WAN loss, DHCP change, router restart, reboot/recovery, channel mismatch/change, session refresh, concurrent durable events, no-false-ACK, exact retry/dedupe, and credential redaction cases. Run new tests, all affected component/contract regressions and a non-flashing ESP-IDF 6.0.3 S3 build (plus C3 build if Node source changes). No physical acceptance is implied; any fixture/HIL work needs separate explicit authorization.

## Next action

Wait for explicit answers to GS58-D1 through GS58-D4. After approval, reconcile those choices with the canonical decision log and applicable GS-68/GS-109/GS-148 contracts, then implement only the approved scope. Re-run preflight and inspect the current branch and writer state before resuming.
