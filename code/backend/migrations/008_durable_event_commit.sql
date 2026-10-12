-- One identity and payload fingerprint per committed business event.
CREATE TABLE IF NOT EXISTS durable_event_commits (
    home_id TEXT NOT NULL REFERENCES households(home_id) ON DELETE CASCADE,
    physical_device_id TEXT NOT NULL,
    logical_node_id TEXT NOT NULL,
    origin_session_id INTEGER NOT NULL CHECK(origin_session_id > 0),
    event_sequence INTEGER NOT NULL CHECK(event_sequence > 0),
    event_id TEXT NOT NULL UNIQUE REFERENCES events(event_id) ON DELETE CASCADE,
    payload_sha256 TEXT NOT NULL,
    committed_at INTEGER NOT NULL,
    PRIMARY KEY(home_id, physical_device_id, logical_node_id, origin_session_id, event_sequence)
);

-- Sender-owned state. External delivery happens only after the business commit.
CREATE TABLE IF NOT EXISTS durable_notification_outbox (
    outbox_id TEXT PRIMARY KEY,
    home_id TEXT NOT NULL REFERENCES households(home_id) ON DELETE CASCADE,
    event_id TEXT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    effect_key TEXT NOT NULL,
    recipient_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    due_at INTEGER NOT NULL,
    state TEXT NOT NULL DEFAULT 'PENDING' CHECK(state IN ('PENDING','DELIVERED','FAILED')),
    provider_reference TEXT,
    UNIQUE(home_id, effect_key, recipient_id)
);
CREATE INDEX IF NOT EXISTS idx_durable_outbox_pending ON durable_notification_outbox(state, due_at);
