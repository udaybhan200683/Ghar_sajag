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

- [Event Delivery, Retry and Recovery](EVENT_DELIVERY_RETRY_AND_RECOVERY.md)
  — event identity, bounded retry, durable Hub ACK, dedupe, and restart recovery.
- [Hub Persistence and Recovery](HUB_PERSISTENCE_AND_RECOVERY.md)
  — Hub identity, registry and journal storage, restore sequence, and durability limits.
- [Device Health, Liveness and Offline Detection](DEVICE_HEALTH_LIVENESS_AND_OFFLINE_DETECTION.md)
  — authenticated health, per-Node recent contact, offline threshold, and recovery.
- [Device Identity, Registration and Lifecycle](DEVICE_IDENTITY_REGISTRATION_AND_LIFECYCLE.md)
  — physical identity, exact-device commissioning, persisted association,
  authenticated rejoin, replacement, and recovery boundaries.
- [Hub-Node Secure Communication](HUB_NODE_SECURE_COMMUNICATION.md)
  — per-Node runtime sessions, authenticated traffic, replay protection,
  event/health/ACK routing, and qualification boundaries.
- [Battery, Low-Power and Power Management](BATTERY_LOW_POWER_AND_POWER_MANAGEMENT.md)
  — current Node sensing and event-delivery power costs, portable energy policy,
  battery analytics boundaries, and sleep roadmap.
- [Routine, Activity and Incident Rules](ROUTINE_ACTIVITY_AND_INCIDENT_RULES.md)
  — deterministic morning, inactivity, quiet-hours, door and night activity
  behavior, including clock and coverage limits.
- [Caregiver Actions and Notifications](CAREGIVER_ACTIONS_AND_NOTIFICATIONS.md)
  — resident actions, incident timelines, caregiver acknowledgement, and
  notification delivery boundaries.
- [FOTA Engineering, Flashing, Security, and Recovery Guide](FOTA_ENGINEERING_FLASHING_SECURITY_AND_RECOVERY_GUIDE.md)
  — C3 FOTA architecture, signed image workflow, operational boundaries, and
  recovery guidance.

## Planned

The entries below are planned documentation topics. They are not claims about
implementation or feature completeness.

- Multi-Node Operation
- Installation and Service Workflow
- Node-Hub-Backend-PWA Data Flow
