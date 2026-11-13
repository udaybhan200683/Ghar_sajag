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
