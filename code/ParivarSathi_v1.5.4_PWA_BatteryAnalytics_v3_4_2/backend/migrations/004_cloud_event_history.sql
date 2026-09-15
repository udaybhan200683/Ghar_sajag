-- Phase 2A: preserve the canonical CloudEvent hub timestamp used by the backend event contract.
ALTER TABLE events ADD COLUMN hub_received_at INTEGER;
