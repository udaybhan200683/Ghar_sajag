# GS-179 session-scoped physical ingress recovery — decision boundary

Status: PROPOSED; not implemented, enabled, registered or physically qualified.
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

## Minimum proposed integration (not an approved contract)

Reuse the existing GS-179 task/utility, bounded service launchers, exact-route guards and rollback. Do not add a second network daemon, issuer, hardware authorization controller or firmware tool.

An explicit opt-in physical-test session would supply its existing audited authorization reference and a nonextendable deadline no later than the existing service window (maximum 3600 seconds). Existing GS-117 authorization remains the authority; a network session must not grant hardware operations. Preserve `.6`, router reservation, APK origin, TLS and default caregiver Watch behavior.

Before enabling the physical branch, verify administrative firewall scope, exact service/route ownership and absence of stale unrelated rows. The physical branch must never create/widen firewall policy or modify unrelated mappings. Reuse existing Start only with those constraints enforced before mutation, including rollback. Do not simply enable permanent PhysicalHubIngress Watch/RegisterWatch: that would expose TEST_ONLY ingress outside its approved session.

During the bounded session, reconcile only `.6:8445` to the currently validated WSL NAT target when the existing authenticated-ingress service is available. A healthy listener must produce no mutation or service restart. Reconnect/NAT changes must revalidate trust, route ownership and the existing authorized session. Missing/expired ingress, untrusted Wi-Fi, wrong fixed IP, authorization loss or deadline expiry must stop exposure; do not renew service or authorization lifetimes automatically.

Normal closure and crash/timeout recovery must remove only the session-owned forwarding exposure, retaining unrelated 443 mappings/firewall/tasks. A foreground sleep loop with finally cleanup alone is insufficient because process termination can leave persistent portproxy rows behind. Reuse Task Scheduler expiry/recovery support; reject activation if guaranteed bounded cleanup cannot be established. Any changed task action or expiry trigger is a privileged deployment change requiring explicit approval. No task registration/privilege modification is authorized by this record.

## Exact outstanding owner decision

Approve or reject extending the EXISTING GS-179 elevated recovery task with an opt-in, revocable GS-117 physical-session branch and expiry/crash cleanup, limited to the named physical ingress rule, current verified WSL target and a maximum 3600-second authorized window. Preserve the default 443 action, fixed `.6` IP/APK endpoint, existing firewall scope and all other routes. No permanent physical-ingress autostart or network exposure. Existing audited GS-117 references must bind the session; #11900's single-refresh permission must not become standing authority. Offline implementation/negative tests and a concrete reviewed task-action/configuration diff must be supplied BEFORE any separate enablement/registration approval is exercised. No source or live task changes have been made here.

## Required qualification before enablement

Use existing GS-179 integration/security test registration. Exercise actual changed production functions with mocked Windows/network/task operations: healthy no-op; dormant recovery/rollback; trusted reconnect; WSL NAT change; expired service; repeated start/stop; Public/wrong `.6` IP; wrong owner/authorization; elevation failure; conflicting listener; unexpected firewall/stale row; expiry and abrupt controller termination. Verify unchanged 443/unrelated entries, no lifetime extension and no exposure outside session. Static source checks alone cannot establish those outcomes.

No new implementation exists, so no new functional suite or simulated PASS is claimed. Existing dormant-row tests and prior physical bootstrap evidence remain historical. Real Windows elevated firewall audit, repair, reconnect/NAT-failure qualification and actual session cleanup remain NOT_RUN. Hardware rejoin/TC-001 remain separate: receipts STALE, TC001_READY NO, TC-001 0/5. Event123/1 latency and existing release-gate failures remain unresolved.
