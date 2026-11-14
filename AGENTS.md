# Ghar Sajag / Parivar Saathi — AGENTS.md

## 1. Primary Engineering Objective

**Deliver commercially usable Ghar Sajag / Parivar Saathi functionality with minimum necessary complexity, maximum reuse of validated components, and no compromise to essential product quality or safety.**

Ghar Sajag is a real commercial elder-care product under development, not a demonstration project.

Our immediate development priority is completing **TC-001: physical end-to-end event delivery**, from the existing Web Simulation Portal through the physical C3 and S3 devices to the installed Parivar Saathi Android application.

Prioritize working product use cases and functional validation over infrastructure expansion, enterprise-scale frameworks, repetitive readiness audits or documentation-only progress.

Implement commercially appropriate solutions that are reliable, maintainable, extensible and usable.

The system is intended for continuous 24/7 elder monitoring while powered. Ordinary configuration expiry, network interruptions or session renewal must not repeatedly interrupt legitimate monitoring or CloudSync operation.

Do not introduce temporary workarounds, placeholders, demo-only implementations or unnecessary architectural complexity.

For additional governing requirements, follow:

`docs/product/ENGINEERING_PRINCIPLES.md`

---

## 2. Mandatory Execution Priority

1. Finish the highest-priority approved Jira task before beginning another implementation.
2. Reprioritize only with explicit owner approval or a verified critical blocker.
3. Implement sequentially in the existing canonical worktree and branch.
4. Maintain only one active Codex implementation unless explicitly authorized otherwise.
5. Do not silently change approved requirements, scope, priority or acceptance criteria.
6. Record significant new feature ideas in the backlog without interrupting active work.
7. Include minor related improvements only when low-risk and non-disruptive.

### Implementation continuity — critical

**An incomplete implementation, missing integration, failing test or ordinary software defect is engineering work to perform, not automatically a reason to stop.**

When encountering such a problem:

1. Identify the precise failing component.
2. Inspect existing implementation and prior attempts.
3. Implement the smallest complete, maintainable correction.
4. Run relevant affected tests.
5. Continue the same approved task toward its acceptance criteria.

Do not repeatedly report an already-known implementation gap without attempting the necessary code changes.

Do not replace implementation with repeated analysis, documentation updates or Jira comments.

Do not stop merely because an implementation is incomplete, a recoverable software defect exists, or legitimate source-review fingerprints require updating after validated source changes.

A genuine blocker must be supported by specific evidence, such as an unavailable essential resource, an unresolved authoritative requirement conflict, a hardware-safety concern, a failed technical authorization check or another condition that actually prevents safe execution.

Never bypass a genuine safety or security failure to continue work.

---

## 3. Permanent Single-Worktree Development Policy

Ghar Sajag has one developer working sequentially.

Canonical repository:

`/home/udaybhan/projects/Ghar_sajag_r1`

Active branch:

`feature/r1-commercial-baseline`

Rules:

- Use only this canonical worktree and branch for R1 development.
- Do not create another branch, worktree, clone or feature-development directory without explicit owner approval.
- Do not switch worktrees or branches merely because Jira ownership changes.
- Never assume another branch contains all prior work.
- Preserve existing uncommitted modifications, untracked files, evidence and unrelated changes.
- Before any proposed worktree or branch change, explain the necessity and obtain approval.

### Documentation location

Store task-specific execution plans, evidence, design notes, decisions and pause/resume handoffs under:

`docs/exec-plans/evidence/`

Maintain existing canonical product requirements, architecture and work-state documents in their established locations. Do not relocate existing canonical documents merely to satisfy the evidence directory convention.

---

## 4. Mandatory Context and Task Startup

Before planning, designing, coding, reviewing or resuming substantial work:

1. Verify the current repository, worktree and branch.
2. Verify local HEAD, remote HEAD and working-tree status.
3. Read this `AGENTS.md` and applicable nested repository instructions.
4. Read relevant canonical requirements, architecture, decisions, release contracts and engineering principles.
5. Read `docs/product/R1_WORK_STATE.md`.
6. Read the owning Jira description, latest comments, dependencies and acceptance criteria.
7. Read the latest feature pause/resume handoff.
8. Inspect the actual relevant source code, Git history, tests and existing implementation evidence.
9. Reconcile any contradictions between Jira, documentation, code and actual validation results.

Prefer verified source and test evidence over outdated status statements.

Run the repository's existing context preflight when applicable.

**Keep context review focused on the active task. Do not repeatedly perform the same full investigation when existing evidence remains valid.**

Do not restart from an old task prompt without reconciling the current project state.

---

## 5. Jira Workflow and Ownership

Identify the owning Jira issue before beginning implementation.

Search existing Jira issues before creating new ones. Avoid duplicates.

New Jira issues must include:

- Scope and objective
- Requirements and design considerations
- Priority
- Dependencies
- Acceptance criteria

Use Jira statuses consistently:

| Status | Meaning |
|---|---|
| To Do | Approved or planned but not started |
| In Progress | Implementation has actually begun |
| OnHold | Genuine pause or verified blocker |
| Future_Features | Explicitly deferred future work |
| Done | Full acceptance criteria verified |

Move a ticket to **In Progress** when execution actually starts, not merely when a prompt is submitted.

Do not move a ticket to OnHold merely because code remains unfinished or a recoverable defect requires correction.

Do not move a ticket to Done until its complete Definition of Done is satisfied.

Update Jira with meaningful verified progress, decisions, results and genuine blockers.

Avoid repetitive comments that merely restate the same known implementation gap.

Respect explicit instructions not to update Jira.

---

## 6. Mandatory Execution, Validation and Closure

Follow this workflow:

**Check priority → Read Jira/docs/Git/source → Reconcile → Design/document as necessary → Confirm start → Implement → Validate → Update documentation → Commit → Push/verify remote → Update Jira → Close if fully accepted → Report next priority.**

### Implementation rules

- Check what has already been assigned, attempted, implemented and tested.
- Reuse existing validated components.
- Do not duplicate or unnecessarily replace working functionality.
- Prefer straightforward, durable solutions over temporary workarounds.
- Avoid introducing frameworks, services or infrastructure unrelated to the active product requirement.
- Preserve every approved requirement, security invariant, acceptance criterion and test obligation.
- Implement the actual maintained execution path, not isolated helpers that remain disconnected from the product.
- Do not change product behavior silently.

### Milestone completion

After each implementation milestone, check the relevant Definition of Done.

A milestone is complete only when its functional requirements and relevant tests are verified.

If the milestone is incomplete, identify the exact remaining executable work and continue unless a genuine blocker prevents it.

Do not declare PASS based only on code inspection, mocks, simulations or historical evidence when actual integration or physical acceptance is required.

---

## 7. Validation Policy

**Validate affected functionality, not the entire repository by default.**

For code changes:

1. Run relevant new tests.
2. Run existing tests for directly affected components.
3. Run relevant integration, regression, security, sanitizer or build checks where the change creates corresponding risk.
4. Run broad release gates at release milestones or when explicitly required by the release contract.
5. Execute physical hardware-in-the-loop tests when required for the active acceptance criteria.

Do not rerun unrelated module tests without an identified dependency or impact.

If no source or behavior change occurred, do not repeat previously verified tests unless environmental conditions, test validity or acceptance requirements justify it.

Distinguish clearly between:

- Source review
- Unit and component tests
- Simulation
- Target firmware build
- Integration testing
- Physical hardware validation
- Full product acceptance

Never invent PASS, suppress failures or substitute one validation level for another.

A failed test is a reason to diagnose and correct affected code, not automatically a reason to end the implementation session.

---

## 8. Engineering Authorization and Product Security

Ghar Sajag is currently in the Engineering development phase, preparing for Release R1.

### Standing Engineering authorization

The owner has granted standing authorization for routine registered TEST_ONLY Engineering operations within the existing approved scope, including supported application-only firmware updates.

Do not repeatedly request owner approval for routine authorized Engineering operations.

However, standing approval does not override required operating-system permissions, device identity checks, protected-flash safeguards, authentication, hardware-safety conditions or established recovery contracts.

Reuse the existing authorization mechanisms. Do not introduce additional authorization frameworks or recurring manual approval workflows without a verified requirement.

### Security expectations

Apply basic, appropriate commercial-product security—not unnecessary enterprise-scale security infrastructure.

Preserve:

- Authenticated device communications
- Household/Home isolation
- Device identity and registration
- Credentials and sensitive configuration
- Firmware and partition compatibility
- Event durability and deduplication
- Reliable recovery from interruption
- Reasonable protection of caregiver and resident information

Do not weaken authentic security controls merely to obtain a PASS or accelerate deployment.

Do not treat normal Engineering development, source changes or legitimate configuration renewal as a reason to create recurring manual approval obstacles.

### Continuous operation

Registered devices should recover automatically from ordinary network interruptions and configuration renewal.

A normal configuration timer must not permanently disable legitimate monitoring or CloudSync.

Design authenticated renewal, retry and recovery behavior to support dependable 24/7 operation.

Avoid introducing unnecessary recurring approvals, short-lived operational permissions or redundant safety frameworks.

---

## 9. S3 Firmware Build and Deployment Contract

**Always use the canonical S3 outbox build procedure.**

Canonical build script:

`code/firmware/hub/target/esp32s3/idf/build-outbox.sh`

When operating from its directory:

```bash
./build-outbox.sh
```

When operating from the repository root, invoke the script using its repository-relative path, ensuring the script's documented working-directory requirements are respected.

### Required partition contract

The physical Hub uses:

- `gs_outbox`: 4 MiB
- `gs_state`: 256 KiB
- Two 4 MiB OTA application slots

Never build deployable S3 firmware using the default `gs_journal` partition layout.

For Engineering Builds, include the established GS-40 TEST_ONLY and native-USB/UART configuration required for the registered physical Hub.

Keep Engineering and Release build profiles distinct.

Verify the generated partition table and application compatibility before declaring an image deployable.

### Firmware flashing

Use the existing validated official ESP-IDF application-only update procedure.

Never substitute generic full-device flashing for an authorized app-only update.

Preserve:

- Bootloader
- Partition table
- NVS
- Outbox and state partitions
- Device registration
- Credentials
- Existing OTA selector and recovery guarantees

Do not rewrite or erase protected regions.

The firmware writer must verify the current authorized session and compatible target before initiating a write.

A session ID alone must not be treated as proof of live lock ownership.

Maintain the existing trusted hardware lock, audit and authorized update-session contracts.

If updater integration is incomplete, implement and validate it rather than repeatedly documenting the same missing connection.

---

## 10. TC-001 — Immediate Product Priority

The current highest-priority functional objective is a **fresh physical end-to-end motion event**, delivered from the existing portal to the installed caregiver application.

Required real execution path:

1. Existing Web Simulation Portal
2. Select Motion Scenario → Run
3. TEST_ONLY USB `INJECT_MOTION` to physical ESP32-C3
4. Real C3 NodeRuntime creates a fresh original EventKey
5. Authenticated ESP-NOW transport
6. Physical ESP32-S3 HubRuntime
7. Real rules, journal/outbox durability and ACK
8. Real CloudSync
9. PostgreSQL durable event commit
10. Caregiver API retrieves the same original event
11. Installed Parivar Saathi Android APK visibly displays that event

### Acceptance expectations

Verify original EventKey continuity across every component.

Verify no duplicate durable event is created.

Use actual physical C3 and S3 devices for hardware acceptance.

Do not fabricate backend records or treat simulation as a substitute for real device operation.

When the event fails:

1. Trace fresh event-correlated evidence.
2. Find the first failing boundary.
3. Correct the underlying defect in the maintained product implementation.
4. Run affected tests.
5. Repeat the physical event.
6. Confirm complete downstream delivery.

Do not block functional testing on broad environment audits, repeated historical-log investigations or unrelated infrastructure checks.

Perform only the minimum prerequisites necessary for safe, authorized execution.

Preserve outstanding recovery obligations and original failure evidence.

Do not expand an isolated functional defect into an unnecessary system redesign.

---

## 11. Commercial Engineering Design Principles

Ghar Sajag is intended to become a commercially deployable elder-care product.

Implementation decisions must consider:

- Real resident and caregiver use cases
- Continuous monitoring reliability
- Useful, understandable user interactions
- Maintainability
- Appropriate security
- Power and battery considerations
- Recovery from normal operational interruptions
- Compatibility and future extensibility
- Commercially proven design practices

Prioritize functional product value, not engineering sophistication for its own sake.

Do not introduce enterprise-scale observability, operational frameworks, elaborate authorization systems, generalized test harnesses or unrelated infrastructure unless required for actual product acceptance.

Future infrastructure improvements may be planned and recorded separately without interrupting the highest-priority task.

No temporary solutions should be presented as finished commercial implementation.

---

## 12. Requirements Conflicts and Decision-Making

Follow the canonical document precedence defined in the repository.

Never invent missing product requirements or backend security contracts.

Do not create competing master requirement documents.

**Stop only when authoritative product requirements genuinely conflict and resolving the conflict would change approved product behavior.**

Do not classify these as requirement conflicts:

- An unfinished integration
- Missing implementation code
- A failing unit or integration test
- A known software defect
- Normal configuration expiry
- Stale source-review evidence that can legitimately be refreshed
- Routine implementation uncertainty resolvable through source inspection or testing

Resolve ordinary engineering problems through implementation and validation.

Record significant new requirements, architectural decisions, risks and limitations in dated Jira comments and canonical Markdown.

Distinguish approved decisions from proposals.

Seek owner approval when an actual product-scope, priority or acceptance-criteria change is required.

---

## 13. Git, Commit and Delivery Policy

- Implement sequential Jira tasks in the canonical worktree and branch.
- Preserve all existing uncommitted and unrelated work.
- Review staged files before committing.
- Commit validated task-owned code, tests and documentation.
- Push to the correct remote branch.
- Verify actual remote HEAD equals local HEAD.
- Report commit hashes and push verification.
- Never force-push, reset, rebase, discard changes or destructively clean files without explicit approval.
- Never overwrite or remove historical evidence without authorization.
- Do not claim remote delivery merely because a local commit succeeded.

If Git or an external connector fails, preserve the work and report the precise blocker. Avoid repeated futile retries.

Do not create extra branches or worktrees merely to handle an incomplete integration.

---

## 14. Mandatory Execution Continuity and Pause/Resume Handoff

The highest-priority approved task remains active until it is accepted, explicitly reprioritized or genuinely blocked.

**Do not treat incomplete software implementation as an automatic pause condition.**

When an engineering issue is recoverable:

- Diagnose it.
- Implement the correction.
- Run focused tests.
- Continue toward the existing acceptance criteria.

Do not repeatedly end sessions after reporting the same known issue without attempting the implementation.

### When a genuine pause occurs

If a task is actually paused, externally blocked, interrupted or reprioritized:

1. Update the existing canonical feature handoff Markdown.
2. Update `docs/product/R1_WORK_STATE.md`.
3. Record actual completed work, remaining work, genuine blockers, decisions and verified test results.
4. Record current branch, local/remote HEAD and uncommitted changes.
5. Identify the exact next executable action and required prerequisites.
6. Add a dated comment to the owning Jira issue.
7. Commit and push validated task-owned changes where possible.
8. Preserve unrelated work and historical evidence.

Do not repeatedly create identical handoff updates when no meaningful progress or new blocker has occurred.

When resuming, always reconcile the latest handoff, code, requirements, Jira and current Git state.

---

## 15. Documentation and Progress Reporting

Record significant requirements, approved designs, decisions, technical limitations, dependencies, corrections and risks in canonical Markdown and dated Jira comments.

Synchronize meaningful progress, verified test evidence, commits, failures, blockers and next priorities.

Do not use documentation-only progress as a substitute for required implementation.

Keep operational logs and reports concise.

Avoid repetitive advice and replacement prompts when an implementation task has already been assigned.

Every substantial task report must identify:

1. Verified implementation progress.
2. Actual test results and limitations.
3. Jira status and updates.
4. Canonical documentation updates.
5. Commit and push results.
6. Remote HEAD verification.
7. Genuine unresolved blockers.
8. Next highest-priority approved work.
9. Exact worktree, branch and HEAD.

Never claim unverified completion.

---

## 16. Codex Execution and Prompt Continuity

For new or resumed Codex sessions:

- Read and reconcile the latest approved task scope, prior work and current repository state.
- Continue existing partial implementation rather than restarting from scratch.
- Preserve all original requirements, designs, safety invariants, relevant tests and acceptance criteria.
- Do not silently narrow the task.
- Do not create unnecessary duplicate prompts, code paths or infrastructure.
- Prefer direct changes to the actual maintained execution path.

### Avoid repeated no-progress loops

If a task has already been analyzed and the missing implementation is known, proceed to source modification and focused validation.

Do not repeatedly produce the same explanation as a substitute for implementation.

If tools cannot edit files or execute commands, or if an external resource genuinely prevents progress, identify that precise restriction.

Do not claim a generic blocker when no actual blocking condition has been established.

### Prompt updates

When revising a previously provided Codex/AI implementation prompt, provide the **entire updated standalone prompt**, retaining all existing approved scope, security requirements, tests and deliverables unless explicitly changed.

Never require the owner to combine partial replacement prompts manually.

---

## 17. Governing Principle

**Finish, validate and close the highest-priority approved task.**

Reuse existing validated components.

Preserve product reliability, reasonable security, hardware safety and approved requirements.

Eliminate unnecessary approval loops and infrastructure expansion.

Prioritize actual implementation and physical end-to-end acceptance over repeated analysis or status reporting.

**The objective is a commercially reliable Ghar Sajag product that continuously monitors residents and delivers genuine events to caregivers—not a collection of disconnected helpers, readiness frameworks or documentation-only milestones.**