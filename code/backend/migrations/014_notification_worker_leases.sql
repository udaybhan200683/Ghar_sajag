-- Add restart-safe worker ownership and bounded retry metadata to the existing outbox.
-- Existing rows remain pending with their original identity, schedule and payload.
ALTER TABLE durable_notification_outbox ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE durable_notification_outbox ADD COLUMN lease_token TEXT;
ALTER TABLE durable_notification_outbox ADD COLUMN lease_generation INTEGER NOT NULL DEFAULT 0;
ALTER TABLE durable_notification_outbox ADD COLUMN lease_until INTEGER;
ALTER TABLE durable_notification_outbox ADD COLUMN last_attempt_at INTEGER;
ALTER TABLE durable_notification_outbox ADD COLUMN last_error_class TEXT;
ALTER TABLE durable_notification_outbox ADD COLUMN terminal_reason TEXT;
ALTER TABLE durable_notification_outbox ADD COLUMN provider_accepted_at INTEGER;
-- Legacy outbox rows predate explicit stage; NULL means infer from live role.
ALTER TABLE durable_notification_outbox ADD COLUMN stage INTEGER;
CREATE INDEX IF NOT EXISTS idx_durable_outbox_lease ON durable_notification_outbox(state, due_at, lease_until);
