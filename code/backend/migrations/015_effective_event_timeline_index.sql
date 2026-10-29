-- Keep the bounded caregiver timeline ordered by the same fallback timestamp
-- exposed by _row_to_event when historical occurred_at is zero.
CREATE INDEX IF NOT EXISTS idx_events_home_effective_time
    ON events(home_id, (COALESCE(NULLIF(occurred_at, 0), received_at)) DESC,
              canonical_event_id DESC);
