# GS-179 / GS-117 source-pin decoupling — 2026-11-13

## Finding

Jira GS-179 #12039 and GS-117 #12040 require routine GS-117 application-source
edits not to disable the independent bounded Windows ingress executor. The
installed task was registered and its protected files matched its manifest,
but its isolated `gs179_engineering_validator.py` rejected the current
`gs117_hil_authorization.py` checkout with `reviewed_project_source_changed`.

The mismatch was caused by commit `a870860`, which updated only the reviewed
S3 bootstrap script/hash selection in `gs117_hil_authorization.py` (v22 to
v24). The installed network executor already loads and executes its
administrator-protected GS-117 snapshot; it does not execute the mutable
checkout copy. Requiring the checkout bytes to match the installed GS-117
snapshot therefore coupled ingress availability to unrelated application
source updates.

## Correction

The existing validator now continues to validate manifest schema, the exact
four allowed snapshot names, hash syntax, the canonical source paths, and the
current hashes of the three fixed GS-179 executor files. It rejects a
GS-117 source-path symlink, but no longer requires the mutable GS-117 checkout
bytes to match the installed authorization snapshot. The installed GS-117 and
GS-179 endpoint snapshots are still verified against the protected manifest
before either is executed. The Windows launcher continues to verify all four
installed snapshot hashes, owner/ACL, fixed task action and principal.

The GS-117 snapshot remains the executor's reviewed network-authority
implementation. This change does not run caller-controlled source, add an
action or path, grant hardware authority, change an authorization record, or
alter lease, identity, Home, TLS/mTLS, cleanup, firewall, or port scope.
GS-117's separate hardware admission remains responsible for physical-device
operations.

`code/tests/python/test_gs179_verified_endpoint.py` retains the existing
`GS179-UNATTENDED-002` test ID and now proves that changed/malicious current
GS-117 bytes are neither executed nor an admission dependency; GS-117 path
substitution, changed privileged GS-179 source, changed protected GS-117
snapshot, and invalid manifest paths still fail closed. Two existing Windows
mock cases now explicitly model the no-installed-executor branch so their
results are independent of this machine's actual `ProgramData` and task
registration.

## Validation

- `python3 code/tests/python/test_gs179_verified_endpoint.py` — 27/27 PASS.
- `python3 code/tests/windows/gs179_physical_session_test.py` — 21/21 PASS.
- Python compilation of the changed validator and test modules — PASS.
- `git diff --check` — PASS.
- No broad release, firmware, Android, or unrelated backend suite was run.

The first Windows mock invocation was 19/21 because two tests inherited an
unset `ProgramData` while the actual Windows installation existed. Their
explicit test-only no-install fixture correction was followed by the 21/21
PASS above; no production behavior was changed for that test issue.

## Deployment and physical status

The installed task remains `GharSajag-Engineering-Ingress`, state `Ready`,
principal `DELL`, S4U, Highest, with its fixed `RunEngineeringExecutor`
PowerShell action. Its protected directory is owned by Administrators;
SYSTEM and Administrators have FullControl and DELL has ReadAndExecute. Its
four installed file hashes still match the protected manifest:

| File | Installed/protected SHA-256 | Current source SHA-256 |
|---|---|---|
| `gs179-windows-lan-proxy.ps1` | `8c3f3ecd83e5bf854a5188028fa87fe8cc823b49d0638e1b806d7307c5ff9056` | same |
| `gs179_engineering_validator.py` | `b0725a9c9786f7c52f16765791cd206052e082a9f8813ce363084e1ff56de5db` | `eb00866c200935651b73b988894803700c98b56f8b6edadf0d0340507691abd9` |
| `gs179_verified_endpoint.py` | `c9b3cb79895d19ef6854aa55084d59b50e014804e43422fb73d84c1f3ceb8c7c` | same |
| `gs117_hil_authorization.py` | `1d321595cbe590d6ca983c23878eafdf2e0841631b8ea0c230873ef28baa21bf` | `cacc9cc747c3e74c6bb90b6ef46f7a639616c4e198694a255cf57d892697486f` |

Because the corrected validator is itself protected privileged code, the
existing installation cannot consume it in place: the reviewed one-time
installer refuses to overwrite an existing installation, and no supported
update action exists. A one-time administrator-authorized deployment of the
reviewed validator and its updated protected manifest is therefore still
required. No protected file, manifest, task, ACL, firewall rule, portproxy, or
authority record was modified here. Do not bypass that boundary or use the
old task as if the source correction were deployed.

At the last live status check, Windows TCP 8445 and UDP 4468 were absent,
caregiver TCP 443 remained listening, and WSL backend 8444 plus PostgreSQL
55432 were listening. No physical S3 authentication/rejoin, USB injection, or
fresh EventKey was produced. GS-117 #11983 S3 reboot remains UNUSED; C3
cold-start work remains ON HOLD. GS-179 remains PARTIAL, including its
previously recorded independent-cleanup attribution/timing gaps.

`BUG_CLASSIFICATION=TEST_INFRA_ONLY`
`REQUIREMENT_SOURCE=GS-179 #12039; GS-117 #12040; existing GS-D034`
`TASK_SCOPE=remove mutable GS-117 checkout-byte admission from the fixed GS-179 executor while preserving protected snapshot verification`
`OUT_OF_SCOPE=task replacement, executor update framework, hardware access, S3 reboot, and physical TC-001 execution before protected deployment`

Next action: deploy the reviewed validator once through an administrator-
authorized update to the existing protected installation, verify the new
manifest/hash and actual Start/Close path, restore bounded ingress and signed
time, then resume GS-117 physical readiness and one-event execution. Do not
ask for handset availability until backend delivery of a fresh event is
verified.

## Owner-approved one-time deployment handoff

The local Codex Windows process is non-elevated (`IsInRole(Administrator)` =
False), so it did not modify the protected installation. The owner-approved
one-time operation is prepared as
[`GS179_DEPLOY_VALIDATOR_ONCE_20261113.ps1`](GS179_DEPLOY_VALIDATOR_ONCE_20261113.ps1),
SHA-256 `100679f56a25bd4db7cefa436ca9dcd7ab748d1a232bef857afed8aa6e6716ab`.
It is fixed to the verified prior four hashes and the one reviewed new
validator hash. It refuses a different task, identity, ACL, manifest, active
8445 listener or source. It updates only `gs179_engineering_validator.py` and
that one manifest hash, retains protected validator/manifest rollback copies,
and checks the installed runner with `--help` before reporting success. It
preserves the existing task action/principal/ACL, all other protected
snapshots, TCP 443 and UDP 4468 state. It is an evidence-scoped one-time action,
not an updater service or general installation interface.

The command for the owner's already elevated PowerShell session is:

```powershell
$scriptPath = '\\wsl.localhost\Ubuntu\home\udaybhan\projects\Ghar_sajag_r1\docs\exec-plans\evidence\GS179_DEPLOY_VALIDATOR_ONCE_20261113.ps1'
if ((Get-FileHash -LiteralPath $scriptPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne '100679f56a25bd4db7cefa436ca9dcd7ab748d1a232bef857afed8aa6e6716ab') { throw 'Deployment script hash mismatch' }
& "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $scriptPath
```

`-ExecutionPolicy Bypass` is scoped to this PowerShell process and does not
alter UAC or machine policy. The script itself requires an actual Administrator
token. Expected success result is `VALIDATOR_UPDATED_AND_VERIFIED`, with the
rollback directory and installed hash printed. On failure it reports either
`VALIDATOR_UPDATE_FAILED_ROLLED_BACK` or
`VALIDATOR_UPDATE_FAILED_ROLLBACK_INCOMPLETE`; retain the printed backup path
and do not retry after either failure. Before deployment, its PowerShell
parser and pinned installation/task ACL checks passed, and its non-elevated
guard rejected execution without changing files or ports. The script has not
been run elevated; the installed validator remains at the previous hash and
8445 remains closed.

### Live pre-deployment recheck — 2026-11-13

From the current non-elevated DELL session, the task was observed `Ready`,
principal `DELL`, logon type `S4U`, run level `Highest`, with the expected fixed
`RunEngineeringExecutor -EndpointKind PhysicalHubIngress` action. The protected
validator and manifest still both contain the old
`b0725a9c9786f7c52f16765791cd206052e082a9f8813ce363084e1ff56de5db` hash.
The live root, manifest, validator and task security descriptors matched the
script's exact reviewed SDDL pins. The one-time script parsed successfully and
its direct non-elevated invocation failed closed with
`administrator_token_required` (exit 1). Post-check showed TCP 8445 = 0,
UDP 4468 = 0, caregiver TCP 443 = 1. No protected file, task, port, device or
authority state was changed by the check. Elevated deployment and actual
post-deployment executor behavior are still NOT_RUN.

### UAC launch result — 2026-11-13

The first `Start-Process -Verb RunAs` wrapper did not launch because Windows
PowerShell rejects combining `-Verb RunAs` with standard-output/error
redirection; it failed before creating a UAC child. The corrected standard
`RunAs` invocation then created `consent.exe` in interactive Console session 1
and waited. Windows subsequently returned `The operation was canceled by the
user`; no elevated child or installation receipt was produced. This records the
OS result and does not establish that the owner deliberately refused consent.
No retry was made. A fresh read-only check confirmed that the task remained
Ready, the protected validator and manifest still matched the old
`b0725a9c9786f7c52f16765791cd206052e082a9f8813ce363084e1ff56de5db` hash,
8445=0, UDP4468=0, and caregiver443=1. No protected or network state changed.

The exact hash-pinned operation above remains the next action in the owner's
already elevated Administrator PowerShell. The deployment itself is already
owner-approved; this is the remaining local Windows-token boundary, not a new
project/Jira approval. Once its success receipt is available, re-read the
installed manifest and validator hash before using the fixed Start action.

## 2026-11-13 live continuation — deployment verified; C3 command response blocks injection

The earlier pending-deployment statements above are superseded by the actual
owner receipt and independent live readback below.

### GS-179 deployment and bounded session

Owner-provided deployment result: `VALIDATOR_UPDATED_AND_VERIFIED`, installed
validator SHA-256
`eb00866c200935651b73b988894803700c98b56f8b6edadf0d0340507691abd9`.
Independent Windows readback confirmed the protected manifest contains the same
hash. The existing task `GharSajag-Engineering-Ingress` remains registered,
Ready, principal DELL/S4U/Highest, with its fixed
`RunEngineeringExecutor -EndpointKind PhysicalHubIngress` action; the protected
root/task ACL remained intact. No reinstall, task replacement or UAC prompt
was used.

The existing bounded session and signed-time path were started. WSL TCP 8445
was reachable through the registered Windows route; signed-time UDP 4468 was
active. Physical S3 UART evidence recorded authenticated TLS/configuration
activity, Hub owner startup, Home/Hub identity and an authenticated C3 rejoin
at C3 session 141. One `/v1/homes/gs177-test-product/node-health` exchange
returned HTTP 503; the physical ingress status receipt did not establish a
fresh `real_hub_authenticated` status. S3 CloudSync logged state 3 with
`submitted=0 completed=0` before any motion event. These are distinct pieces of
evidence; they do not prove that a motion event reached CloudSync or the
backend.

The bounded Windows session deadline was 2026-11-13 06:40:45 UTC. After the
deadline, read-only Windows checks found TCP 8445=0, UDP 4468=0, caregiver TCP
443=1 and no per-session PhysicalIngress tasks. WSL TCP 8445 was absent; the
registered Engineering task remained installed. Backend TCP 8444 and
PostgreSQL 55432 remained available. The portal listener was loopback-only on
127.0.0.1:18791. This verifies expiry cleanup for this session only; it does
not close the previously recorded SYSTEM attribution/strict inactivity timing
qualification gaps. GS-179 remains PARTIAL.

### GS-117 physical status and first failed boundary

The already approved S3 reboot #11983 was USED exactly once in the earlier
COM10-only bootstrap. No intentional C3 reset, firmware update, flash, erase,
commissioning, pairing, enrollment, key or protected-state change occurred in
this continuation. COM4-open incidental reset risk remains; no reset marker was
captured in the bounded C3 observations, which does not prove that no reset
occurred.

At 06:20 UTC the exact registered C3 COM4 returned `HIL_STATE` and
`HIL_OK command=GET_STATE`, session 141, runtime/sensing counters 88515 and
pending/retained/in-flight queues all zero. This was a successful point-in-time
readiness observation. The subsequent existing web run
`TC001-USB-ONE-EVENT-20261113T062606Z-1e08d435` passed its initial environment
and exact C3/S3 identity checks, opened COM4, then received zero serial bytes
and no `HIL_STATE`/GET_STATE ACK after three host-accepted writes of 10/10
bytes over its 30-second bound. The unchanged readiness guard stopped before
`INJECT_MOTION`. The one additional read-only COM4 observation at 06:37 UTC
(`c3-readonly-20261113T063801Z-resume.json`) recorded one host-accepted 10/10
byte `GET_STATE` write, `bytes_read=0`, no ACK and no response line. S3 UART
was not opened for these C3 checks.

Earlier same-day captured output contains `HIL_ERROR command_too_long` followed
by `HIL_ERROR unknown_command=STATE`; another observation contains
`unknown_command=!`. The C3 command parser source does not discard the remainder
of an overlong input line after clearing its buffer, so a suffix can be parsed
as a separate bogus command. This is a confirmed parser recovery defect and a
plausible contributor to the observed malformed commands, but current evidence
does not identify where those extra input bytes originated or prove this is
the exclusive cause of missing GET_STATE replies. The helper's hardcoded
command is `GET_STATE\n`; its 10/10 host write receipt proves host API
acceptance only, not C3 receipt. Current running C3 image identity and console
mapping are UNKNOWN / NOT_VERIFIED. No source change or firmware operation was
made because the root cause is not isolated and no C3 image deployment was
authorized.

Historical C3 session 126/sequence 1 demonstrates the existing USB-injected
path has worked: the captured report has C3 `HIL_OK command=INJECT_MOTION`,
NodeRuntime event generation, authenticated class-0 application ACK, exactly
one PostgreSQL row, caregiver API result and later supplemental exact-key APK
evidence. It remains historical and cannot substitute for this run.

Current new-run stages: exact C3/S3 fixture identity and S3 authenticated rejoin
have evidence; C3 GET_STATE readiness is intermittent/BLOCKED. No
`INJECT_MOTION`, EventKey, motion event, S3 motion ACK, CloudSync event,
PostgreSQL event, caregiver API event or Android presentation was generated.
The first failed event-flow boundary is the C3 USB command-response/readiness
gate; all downstream motion-event stages are NOT_RUN. Android was not needed
for this diagnosis. USB-triggered E2E is NOT_ACCEPTED, formal optical TC-001 is
0/5 and the five-run campaign is 0/5. C3 cold-start work stays ON HOLD.

### Validation, worktree and next action

No validation suite was run, per the current execution direction. Historical
endpoint27/27 and Windows mock21/21 receipts were reused as unchanged evidence;
they do not validate this physical run. Current local and remote HEAD are
`3afdcd1b798a64e9f02d65fe264c7f552aaaf0f8`. The working tree retains the
pre-existing uncommitted `code/tools/local/gs117_tc001_serial_windows.py`
change (10-second query interval and bounded startup-drain logic) and unrelated
untracked assets; none were staged or changed in this continuation.

Next action: establish the running C3 image's actual USB console input mapping
and isolate the source of the malformed/absent GET_STATE command response
using an already supported non-destructive evidence path. Do not reopen COM4
or issue another motion command without a concrete hypothesis and a fresh
genuinely passing readiness guard. Do not weaken the guard or attribute the
failure solely to the overlong-line defect until the input source is proven.
Jira checkpoint comments: GS-117 #12057 and GS-179 #12058.
