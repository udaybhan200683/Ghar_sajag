-- Phase 2B local notification preferences and delivery records.
CREATE TABLE IF NOT EXISTS notification_preferences (
    home_id TEXT PRIMARY KEY REFERENCES households(home_id) ON DELETE CASCADE,
    preferences_json TEXT NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS notification_records (
    record_id TEXT PRIMARY KEY,
    home_id TEXT NOT NULL REFERENCES households(home_id) ON DELETE CASCADE,
    source_event_id TEXT,
    category TEXT NOT NULL CHECK (category IN ('SAFETY','ROUTINE','CHECK_IN','MONITORING','DEVICE_MAINTENANCE')),
    severity TEXT NOT NULL CHECK (severity IN ('INFO','CONCERN','URGENT')),
    state TEXT NOT NULL CHECK (state IN ('DELIVERED','FAILED','SUPPRESSED','RESOLVED')),
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    correlation_key TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    delivered_at INTEGER,
    failed_at INTEGER,
    resolved_at INTEGER,
    suppressed_reason TEXT,
    UNIQUE(home_id, correlation_key)
);

CREATE INDEX IF NOT EXISTS idx_notification_records_home_time ON notification_records(home_id, created_at DESC);
