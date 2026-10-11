-- Preserve the trusted authorization decision with each committed CloudSync
-- event. Legacy local-fixture commits stay NULL and are not production proof.
ALTER TABLE durable_event_commits ADD COLUMN hub_device_id TEXT
    REFERENCES hub_ownership_registry(hub_device_id) ON DELETE RESTRICT;
ALTER TABLE durable_event_commits ADD COLUMN ownership_epoch INTEGER
    CHECK(ownership_epoch IS NULL OR ownership_epoch > 0);
ALTER TABLE durable_event_commits ADD COLUMN node_enrollment_generation INTEGER
    CHECK(node_enrollment_generation IS NULL OR node_enrollment_generation > 0);
