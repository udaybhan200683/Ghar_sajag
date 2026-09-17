-- Preserve the public (home_id,event_id) CloudEvent identity in SQLite.
-- `events.event_id` remains the internal relational key for compatibility with
-- existing foreign keys; canonical_event_id is the household-local API value.
ALTER TABLE events ADD COLUMN canonical_event_id TEXT;

UPDATE events
   SET canonical_event_id=event_id
 WHERE canonical_event_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_events_home_canonical_id
    ON events(home_id, canonical_event_id);

CREATE TRIGGER IF NOT EXISTS events_fill_canonical_id
AFTER INSERT ON events
WHEN NEW.canonical_event_id IS NULL
BEGIN
    UPDATE events
       SET canonical_event_id=NEW.event_id
     WHERE rowid=NEW.rowid;
END;

CREATE TRIGGER IF NOT EXISTS events_reject_null_canonical_id
BEFORE UPDATE OF canonical_event_id ON events
WHEN NEW.canonical_event_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'canonical_event_id_required');
END;

DROP INDEX IF EXISTS idx_events_home_time;
CREATE INDEX idx_events_home_time
    ON events(home_id, occurred_at DESC, canonical_event_id DESC);

DROP INDEX IF EXISTS idx_events_home_type_time;
CREATE INDEX idx_events_home_type_time
    ON events(home_id, event_type, occurred_at DESC, canonical_event_id DESC);

DROP INDEX IF EXISTS idx_events_home_type_received;
CREATE INDEX idx_events_home_type_received
    ON events(home_id, event_type, received_at DESC, canonical_event_id DESC);
