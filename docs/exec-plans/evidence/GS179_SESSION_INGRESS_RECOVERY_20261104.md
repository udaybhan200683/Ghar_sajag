# GS-179 session-scoped physical ingress recovery — decision boundary

Status: software IMPLEMENTED and offline validation recorded below; privileged deployment NOT_ENABLED / PENDING_APPROVAL; real Windows recovery qualification NOT_RUN.
Owning implementation: GS-179. Product dependency: GS-117 (Highest / In Progress).
Starting canonical HEAD: 57ea0b436ffffa21576109b9f1e6445df2033e2c.

## Verified findings

The preceding physical task stopped at normal Windows UAC cancellation (#11901); no elevated audit/repair, successor/session or hardware operation remains active. No parallel implementation was started.

- Actual Scheduled Task inspection on 2026-11-04 shows `Ghar Sajag GS-179 Trusted Wi-Fi Reconnect` invokes the canonical `gs179-windows-lan-proxy.ps1 -Action Watch -LinuxScriptPath /home/udaybhan/projects/Ghar_sajag_r1/code/tools/local/gs179-laptop-server.sh`, without `PhysicalHubIngress`. LastTaskResult is 0. It runs with HighestAvailable and InteractiveToken. This is an existing live privileged consumer of the source, not an unused script.
- Source explicitly rejects Watch/RegisterWatch for PhysicalHubIngress. Start already implements dormant-row delete/re-add, listener verification and rollback. Therefore the verified recovery defect is missing 8445 coverage, not absent portproxy repair code.
- Preserved ingress/time launchers stop at 3600 seconds. Recorded normal shutdown and task-owned cleanup explain later absent WSL/time services; they do not explain Windows portproxy listener disappearance.
- Correct Windows 8445 mapping without a listener was independently observed; IP Helper was running and 443 still listened (#11899). No firmware defect follows from these facts.
- NetworkProfile/Operational is enabled and contains connect/disconnect events. TaskScheduler/Operational is disabled and has no usable task execution history. No preserved timestamped portproxy/listener transition ties a particular event to disappearance. Exact initial Windows trigger: UNCONFIRMED. Wi-Fi rebind, WSL lifecycle and OS/IP Helper events remain hypotheses, not proven causes.
- #11900 authorizes one exact existing rule refresh only. #11897 authorizes one bounded hardware observation. Neither is permission to modify privileged scheduled-task behavior or grant recurring network repair authority.

## Original proposed integration (historical rationale; implementation below)

Reuse the existing GS-179 task/utility, bounded service launchers, exact-route guards and rollback. Do not add a second network daemon, issuer, hardware authorization controller or firmware tool.

An explicit opt-in physical-test session would supply its existing audited authorization reference and a nonextendable deadline no later than the existing service window (maximum 3600 seconds). Existing GS-117 authorization remains the authority; a network session must not grant hardware operations. Preserve `.6`, router reservation, APK origin, TLS and default caregiver Watch behavior.

Before enabling the physical branch, verify administrative firewall scope, exact service/route ownership and absence of stale unrelated rows. The physical branch must never create/widen firewall policy or modify unrelated mappings. Reuse existing Start only with those constraints enforced before mutation, including rollback. Do not simply enable permanent PhysicalHubIngress Watch/RegisterWatch: that would expose TEST_ONLY ingress outside its approved session.

During the bounded session, reconcile only `.6:8445` to the currently validated WSL NAT target when the existing authenticated-ingress service is available. A healthy listener must produce no mutation or service restart. Reconnect/NAT changes must revalidate trust, route ownership and the existing authorized session. Missing/expired ingress, untrusted Wi-Fi, wrong fixed IP, authorization loss or deadline expiry must stop exposure; do not renew service or authorization lifetimes automatically.

Normal closure and crash/timeout recovery must remove only the session-owned forwarding exposure, retaining unrelated 443 mappings/firewall/tasks. A foreground sleep loop with finally cleanup alone is insufficient because process termination can leave persistent portproxy rows behind. Reuse Task Scheduler expiry/recovery support; reject activation if guaranteed bounded cleanup cannot be established. Any changed task action or expiry trigger is a privileged deployment change requiring explicit approval. No task registration/privilege modification is authorized by this record.

## Software authorization versus deployment

The current owner instruction explicitly authorizes implementation and offline tests. It does not authorize privileged registration or activation. The earlier proposal-only implementation pause is superseded for software work; #11900 remains one-refresh authority and #11897 remains one bounded physical observation. Neither is used as standing recurring network authority. The exact pending deployment review follows below.

## Required qualification before enablement

Use existing GS-179 integration/security test registration. Exercise actual changed production functions with mocked Windows/network/task operations: healthy no-op; dormant recovery/rollback; trusted reconnect; WSL NAT change; expired service; repeated start/stop; Public/wrong `.6` IP; wrong owner/authorization; elevation failure; conflicting listener; unexpected firewall/stale row; expiry and abrupt controller termination. Verify unchanged 443/unrelated entries, no lifetime extension and no exposure outside session. Static source checks alone cannot establish those outcomes.

At the original proposal checkpoint no new implementation existed and no simulated PASS was claimed. That software status is superseded by the implementation and executed validation below; prior physical bootstrap evidence remains historical. Real Windows elevated firewall audit, repair, reconnect/NAT-failure qualification and actual session cleanup remain NOT_RUN. Hardware rejoin/TC-001 remain separate: receipts STALE, TC001_READY NO, TC-001 0/5. Event123/1 latency and existing release-gate failures remain unresolved.


## Implemented correction and deployment review — 2026-11-04

Owning Jira GS-179; dependent GS-117. Classification TEST_INFRA_ONLY supporting an R1 physical-validation blocker. Requirements: current owner instructions and existing trusted GS-179 networking/GS-117 identity and safety contracts. Affected components: local Windows development networking and a read-only projection in the existing verified-endpoint helper. No Node/Hub firmware, event protocol, HTTP API, caregiver UI, credentials or commercial FOTA changes.

### Exact source behavior

`gs179-windows-lan-proxy.ps1` adds explicitly selected `SessionStart`, `SessionTick` and `SessionClose` actions for PhysicalHubIngress only. The installed 443 Watch invocation and task are not changed. No session action runs for default Watch. Existing Start/Stop remain supported. A session-only restricted Start mode refuses missing/mismatched firewall rules, changes of firewall address/profile/edge policy, other 8445 rows, wrong fixed `.6`/24 or SSID, and conflicting listener ownership. It reuses the existing dormant-row/retarget/listener-verification/rollback body. Actual mocked native-command execution exposed the old saved-row argument-expansion defect; property expressions in rollback/owned-row arguments now use PowerShell subexpressions so addresses and ports, rather than literal property text, reach netsh. Healthy 443 and 8445 Start remain no-ops.

`gs179_verified_endpoint.physical_ingress_authority()` reads the EXISTING GS117_DEV_TEST_ONLY policy and audit validator; it never reserves/activates/renews a scope or writes its history. It requires the exact known fixture/images through the existing loader, one bootstrap-only scope, max_sessions=1, max_retries=0, 90-second observation, no motion permission, and the supplied approval reference. It pins the owning Linux process UID/PID/start time and the existing private bounded-ingress launcher receipt, live process/script hash and fresh runtime status. Revocation, exhausted scope, completed observation or crashed controller closes the network session. A pessimistically blocked live hardware reservation is accepted only while its existing lock is held, no failure/completion is recorded, and its child age is at most 150 seconds; a genuine latch is never reopened. Existing #11886 therefore remains unavailable.

The existing bounded-service preparation remains in its established launchers: restore only missing ingress/signed-time services once before SessionStart, preserving their 3600-second bounds and protected configuration, and pass their private run directory. The recovery worker does not duplicate service ownership, restart healthy processes or renew expired services. It verifies ingress receipt/profile/identity and connectivity, plus the signed-time executable/command/PID/start identity and expected UDP4468 bind. Expired or replaced services close exposure and return control to the existing setup/cleanup procedure. It does not infer target authenticated readiness or time acceptance.

### Session state, tasks and cleanup

An administrative SessionStart stores protected state/events and an exact hash-pinned proxy-script snapshot under `C:\ProgramData\GharSajag\PhysicalIngress`. The parent, directory and receipt ownership/ACL/reparse checks reject paths writable by principals other than Administrators/SYSTEM. No existing source script is edited by activation. The original deadline is at most 3600 seconds and is clamped to the earliest prior deadline for the same authorization scope/activation, even after closed/restarted cycles; no automatic extension or renewal exists.

Only after validating the existing authority/services does activation prepare two per-session tasks with unique names:

- `GharSajag-PhysicalIngress-<id>-Expiry`: SYSTEM/Highest, once at the absolute deadline plus AtStartup, StartWhenAvailable, independent of WSL or controller. Calls the protected snapshot with SessionClose. Three bounded one-minute restart attempts are configured for task failure. Cleanup cannot be omitted merely because WSL/controller exited.
- `GharSajag-PhysicalIngress-<id>-Tick`: current operator/Highest, once with one-minute repetition limited to the window. Calls SessionTick. It revalidates authority, controller/services, network, target, exact firewall/row ownership, script hash and the expiry task definition. A healthy route causes no mutation. A legitimate verified NAT-target change uses the existing exact retarget/rollback; replacement of the pinned ingress process instead fails closed and requires established service setup, not silent identity rebinding.

The expiry task definition is pinned; no exposure is claimed until both cleanup and reconciliation registration succeed. Registration failure closes the unowned receipt and removes only its task registrations without deleting a pre-existing route. Reconciliation and expiry use an exclusive receipt lock, re-read state under the lock and save targets before repair. Cleanup deletes only `.6:8445` rows to this session's recorded targets, leaves all firewall rules and 443/unrelated mappings untouched, marks closed and removes its own tasks. Failed mapping deletion retains tasks/state for bounded retry. Controller loss/revocation/service loss is detected by the next scheduled check (nominally within one minute); actual scheduler timing/lock contention must be measured during privileged qualification. Deadline handling and SYSTEM expiry need no fresh WSL query. No hard real-time/physical PASS is inferred from mocked scheduling.

### Proposed activation commands (NOT EXECUTED)

After explicit deployment approval, normal UAC, protected-scope audit and a valid unreserved successor through the existing GS-117 mechanism, use the existing bounded launchers and invoke the reviewed source:

```powershell
# Fill these with the current audited successor, live owning WSL PID, and
# existing verified private launcher run directory. Never invent a consent ref.
& '<canonical Windows path>\gs179-windows-lan-proxy.ps1' `
  -Action SessionStart -EndpointKind PhysicalHubIngress `
  -ApprovalRef 'GS-117#<approved-successor>' -ControllerPid <owning-WSL-PID> `
  -ServiceDirectory '/home/udaybhan/.local/state/ghar-sajag/gs117-tc001/<existing-run>' `
  -AuthorityHelperSha256 '<reviewed gs179_verified_endpoint.py SHA-256 below>' `
  -SessionSeconds 3600
```

The new source requires an independently valid, narrow successor before network-session activation, but consumes no hardware session. Full network/fixture guards still pass before physical reservation. That sequencing and the two new privileged tasks are part of the pending deployment approval, not an implicit expansion of #11900/#11897.

Normal early rollback: run `SessionClose -EndpointKind PhysicalHubIngress -SessionFile <generated-protected-json>` from the exact protected snapshot under administrator rights. It closes only its recorded forwarding exposure and tasks, retains evidence and firewall scope, and never clears GS-117 latches. Existing setup owns service shutdown; the original bounded service expiry also remains in force. Do not use general Stop to remove shared firewall state for session cleanup.

### Consolidated pending approval

Approve one controlled deployment/qualification of the reviewed opt-in session actions: create the named protected state/snapshot directory, register only the two temporary task types above (operator Highest and independent SYSTEM expiry/startup), and permit bounded exact 8445 recovery/retarget/cleanup during a valid GS-117 scope. Keep fixed `.6`, default 443 watcher/task, existing firewall rules, APK, router, certificates and unrelated routes unchanged. First audit firewall/row ownership and stop if other policy mutations are necessary. Qualify healthy/dormant recovery, an isolated short expiry/controller-exit test, authorization-end cleanup and rollback; simulate disruptive Wi-Fi/WSL failures unless separately approved. Supply task XML/action/hash and before/after networking evidence; verify task removal, unchanged 443 and no residual 8445 exposure. No firmware/hardware operations or TC-001 campaign are added by deployment approval. Do not enable recurring repair merely under #11900. This deployment has NOT been approved or performed.

### Validation evidence

The explicitly registered `gs179-physical-session-offline` stage runs through `make -C code gs179-physical-session-offline-test`. It requires PowerShell (Windows PowerShell via WSL or pwsh), fails if unavailable and is deliberately outside portable fast/release auto-discovery. Tests extract actual production functions via the PowerShell AST; all netsh, task and firewall mutations are mocked. Linux authority checks use temporary receipts/ordinary child processes and mocked existing authority; no real private policy is changed. Permanent IDs and sources are added to the existing GS179-LAN traceability row.

Initial failures retained: Windows command-length/execution-policy test-runner setup corrected to temporary process-scoped test scripts; a functional rollback assertion exposed the real native-argument bug and was preserved while source was fixed; traceability command spelling corrected to its registered command; one old integration assertion confused helper definition order with execution and was scoped to actual guarded dispatch. No product assertion was weakened.

Final counts and integration outcome are recorded in the execution handoff/work-state after command completion. Elevated deployment, live task cleanup, disruptive network qualification and C3/S3 physical readiness remain NOT_RUN. #11886 and every historical authorization ledger remain unchanged. TC001_READY remains NO; TC-001 0/5.


Reviewed source identities (before commit):

- `code/tools/local/gs179-windows-lan-proxy.ps1`: `fb09b256966aa2ee1be594589b8758e0045c03d891c1f274af7316ae30dc315f`
- `code/tools/local/gs179_verified_endpoint.py`: `a43465931bac1e94d475974edc289964b374b8bc8efd63a66f61dab7c3db93d3`
- `code/tests/windows/gs179_physical_session_test.py`: `9dff5d0dddc1f359e9427f5e5db681b6096178d127f6bd436525f4bd0b61d299`


Final executed validation (2026-11-04): explicit Windows production-function mocks 9/9 PASS (24 policy +9 native Start +8 worker scenarios, authority/lock, cleanup, expiry/registration failure and nonrenewable-window cases); endpoint8/8, GS117136/136, framework55/55, mapping22/22 PASS; full PostgreSQL final72/72 PASS. Initial integration71/72 source-order assertion failure, class15/15 correction rerun and original logs retained. Python/PowerShell syntax/diff PASS. Private detailed receipt/logs: `~/.local/state/ghar-sajag/gs179-session-recovery-20261104/validation-receipt-delivery.json`. Privileged deployment remains NOT_ENABLED; actual Windows/hardware qualification NOT_RUN. This is the concrete software artifact for the consolidated deployment approval above, not an activation record.


Final integrity hardening: SessionStart requires the reviewed authority-helper digest as an explicit input (read from the reviewed source receipt, not a second hardcoded constant). The protected session stores it; Windows checks the fixed canonical helper file before each WSL query and uses the OS WSL binary and `/usr/bin/python3`. A changed/missing helper pin fails before query/exposure. The additional production-function negative test passes; final Windows offline suite is **9/9 PASS**. The final legacy networking class rerun is **15/15 PASS** after this new-branch guard; the full 72/72 PostgreSQL rerun covers the unchanged application path and existing proxy branches. No additional privileged operation was executed.


### 2026-11-04 — deployment audit compatibility correction

Owner explicitly approved controlled deployment; recorded as GS-179#11907. Normal Windows UAC elevation succeeded for a read-only scope audit. Actual existing firewall remote scope is `192.168.1.0/255.255.255.0`, semantically identical to approved `/24`. Literal string comparisons would incorrectly reject it or request an unnecessary firewall update. Added strict IPv4 network/mask equivalence (single scope only; contiguous mask; rejects Any, broader/different networks and extra entries) to the existing scope comparisons, preserving actual policy without any firewall mutation. This is a scope-preserving verified compatibility defect correction under the deployment instruction, not a new network permission. New production-function tests cover the actual mask form and strict negatives; Windows mock suite10/10 and existing networking class15/15 PASS. Earlier full PostgreSQL72/72 and other unchanged software evidence are reused. Elevated audit/private logs: `~/.local/state/ghar-sajag/gs179-live-20261104T155650Z/windows-preaudit.json`. No network mutation, task registration or hardware operation has occurred at this checkpoint; continue approved guarded deployment using the corrected reviewed artifact.
