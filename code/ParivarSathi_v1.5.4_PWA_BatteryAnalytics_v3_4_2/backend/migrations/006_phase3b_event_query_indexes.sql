-- Phase 3B: align durable-history indexes with the bounded snapshot/timeline query order.
DROP INDEX IF EXISTS idx_events_home_time;
CREATE INDEX idx_events_home_time
    ON events(home_id, occurred_at DESC, event_id DESC);

CREATE INDEX IF NOT EXISTS idx_events_home_type_time
    ON events(home_id, event_type, occurred_at DESC, event_id DESC);

CREATE INDEX IF NOT EXISTS idx_events_home_type_received
    ON events(home_id, event_type, received_at DESC, event_id DESC);
