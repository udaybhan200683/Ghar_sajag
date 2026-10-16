CREATE TABLE IF NOT EXISTS node_health_latest (
    home_id TEXT NOT NULL,
    hub_device_id TEXT NOT NULL,
    ownership_fingerprint_sha256 TEXT NOT NULL CHECK(length(ownership_fingerprint_sha256)=64),
    installation_epoch INTEGER NOT NULL CHECK(installation_epoch > 0),
    physical_node_id TEXT NOT NULL,
    logical_node_id TEXT NOT NULL,
    node_enrollment_generation INTEGER NOT NULL CHECK(node_enrollment_generation > 0),
    session_id INTEGER NOT NULL CHECK(session_id > 0),
    boot_generation INTEGER NOT NULL CHECK(boot_generation > 0),
    source_revision INTEGER NOT NULL CHECK(source_revision > 0),
    contact_kind TEXT NOT NULL CHECK(contact_kind IN ('NODE_HEALTH','AUTHENTICATED_EVENT')),
    profile_id TEXT NOT NULL CHECK(profile_id IN ('configured','legacy_60','legacy_120')),
    heartbeat_seconds INTEGER NOT NULL CHECK(heartbeat_seconds BETWEEN 15 AND 3600),
    offline_seconds INTEGER NOT NULL CHECK(offline_seconds BETWEEN 55 AND 10900),
    hub_received_at INTEGER NOT NULL CHECK(hub_received_at > 0),
    hub_snapshot_at INTEGER NOT NULL CHECK(hub_snapshot_at > 0),
    backend_received_at INTEGER NOT NULL CHECK(backend_received_at > 0),
    updated_at INTEGER NOT NULL CHECK(updated_at > 0),
    PRIMARY KEY(home_id, physical_node_id),
    UNIQUE(home_id, logical_node_id)
);
CREATE INDEX IF NOT EXISTS node_health_latest_home_receive
    ON node_health_latest(home_id, backend_received_at DESC);
