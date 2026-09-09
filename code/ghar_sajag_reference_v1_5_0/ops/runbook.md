# Pilot operations runbook (T03)

## Service principles

- Preserve local hub behavior during backend failure; never describe cloud recovery as proof of resident safety.
- Treat node↔hub, hub↔backend, notification-provider and phone↔backend health as separate links.
- Production events and TEST drills use separate metrics and routing policy.

## Ingest backlog

1. Confirm broker, API and database independently.
2. Stop destructive maintenance; retain hub outboxes and original occurrence times.
3. Restore database capacity before acknowledging application commits.
4. Verify replay is idempotent by event ID and notification intent key.

## Notification failure

1. Compare job state, provider acceptance and human acknowledgement; do not collapse them into “notified”.
2. Disable invalid subscriptions and keep the delivery failure visible.
3. Preserve backup timing from incident creation even if the primary provider call fails.

## Restore drill

Quarterly in pilot: restore an encrypted backup to an isolated environment, validate tenant isolation and event/incident/outbox counts, rotate test credentials, and record evidence. Never point a restore drill at production push recipients.

## Secrets

Do not commit passwords, device keys, VAPID private keys, OIDC secrets or provisioning plans. Use a managed secret store before a live pilot.
