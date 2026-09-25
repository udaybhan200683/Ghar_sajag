# Feature Guides

`docs/features/` contains engineer-facing functional guides. A feature guide
explains what a feature does and why it exists, its user/product behavior,
architecture and ownership, normal flow, algorithms or state machines,
configuration, communication, persistence/state, failure and recovery,
security, source-code locations, diagnostics, test and qualification
boundaries, and known limitations.

Feature guides are **not** the current project-status authority. Use:

- [Current status and roadmap](../progress/CURRENT_STATUS_AND_ROADMAP.md) for
  current project status and future work.
- [Master traceability](../validation/MASTER_TRACEABILITY.csv) for
  implementation, requirements, tests, and evidence traceability.
- `docs/validation/` and `evidence/hil/runs/` for formal physical
  qualification plans and run evidence.

## Available

- [Device Identity, Registration and Lifecycle](DEVICE_IDENTITY_REGISTRATION_AND_LIFECYCLE.md)
  — physical identity, exact-device commissioning, persisted association,
  authenticated rejoin, replacement, and recovery boundaries.
- [Hub-Node Secure Communication](HUB_NODE_SECURE_COMMUNICATION.md)
  — per-Node runtime sessions, authenticated traffic, replay protection,
  event/health/ACK routing, and qualification boundaries.
- [FOTA Engineering, Flashing, Security, and Recovery Guide](FOTA_ENGINEERING_FLASHING_SECURITY_AND_RECOVERY_GUIDE.md)
  — C3 FOTA architecture, signed image workflow, operational boundaries, and
  recovery guidance.

## Planned

The entries below are planned documentation topics. They are not claims about
implementation or feature completeness.

- Event Delivery, Retry and Recovery
- Hub Persistence and Recovery
- Multi-Node Operation
- Device Health, Liveness and Offline Detection
- Battery, Low-Power and Power Management
- Routine, Activity and Incident Rules
- Caregiver Actions and Notifications
- Installation and Service Workflow
- Node-Hub-Backend-PWA Data Flow
