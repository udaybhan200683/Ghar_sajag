-- Hub-owned rule decisions have their own durable identity. They are never
-- assigned a Node EventKey or inserted as a Node event.
CREATE TABLE IF NOT EXISTS hub_rule_decisions (
    home_id TEXT NOT NULL REFERENCES households(home_id) ON DELETE CASCADE,
    hub_device_id TEXT NOT NULL,
    installation_epoch INTEGER NOT NULL CHECK(installation_epoch > 0),
    decision_id TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    kind TEXT NOT NULL,
    tone TEXT NOT NULL CHECK(tone IN ('EXPECTED','CONCERN')),
    reason TEXT NOT NULL,
    decided_at INTEGER NOT NULL,
    duration_seconds INTEGER NOT NULL CHECK(duration_seconds >= 0),
    source_event_id TEXT REFERENCES events(event_id) ON DELETE RESTRICT,
    resolves_prior_id TEXT,
    committed_at INTEGER NOT NULL,
    PRIMARY KEY(home_id, hub_device_id, installation_epoch, decision_id)
);
CREATE INDEX IF NOT EXISTS idx_hub_rule_decisions_home_time
    ON hub_rule_decisions(home_id, decided_at DESC, decision_id DESC);
