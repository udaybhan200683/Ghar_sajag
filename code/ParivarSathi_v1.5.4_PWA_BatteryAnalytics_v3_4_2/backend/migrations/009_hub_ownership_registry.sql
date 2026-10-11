-- Authoritative backend Hub identity/ownership and Node enrollment history.
-- `hubs` remains the operational status projection; this registry is the
-- ownership authority and deliberately survives Home deletion attempts.
CREATE TABLE IF NOT EXISTS hub_ownership_registry (
    hub_device_id TEXT PRIMARY KEY CHECK(length(hub_device_id) BETWEEN 1 AND 128),
    identity_key_fingerprint TEXT NOT NULL UNIQUE
        CHECK(length(identity_key_fingerprint) = 64),
    state TEXT NOT NULL CHECK(state IN
        ('UNCLAIMED','ACTIVE','TRANSFER_PENDING','REVOKED','RECOVERY_REQUIRED')),
    home_id TEXT REFERENCES households(home_id) ON DELETE RESTRICT,
    pending_home_id TEXT REFERENCES households(home_id) ON DELETE RESTRICT,
    installation_epoch INTEGER NOT NULL DEFAULT 0 CHECK(installation_epoch >= 0),
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    CHECK (
        (state='UNCLAIMED' AND home_id IS NULL AND pending_home_id IS NULL) OR
        (state='ACTIVE' AND home_id IS NOT NULL AND pending_home_id IS NULL AND installation_epoch > 0) OR
        (state='TRANSFER_PENDING' AND home_id IS NOT NULL AND pending_home_id IS NOT NULL
            AND pending_home_id <> home_id AND installation_epoch > 0) OR
        (state IN ('REVOKED','RECOVERY_REQUIRED') AND pending_home_id IS NULL)
    )
);

CREATE TABLE IF NOT EXISTS hub_ownership_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    hub_device_id TEXT NOT NULL REFERENCES hub_ownership_registry(hub_device_id) ON DELETE RESTRICT,
    transition TEXT NOT NULL CHECK(transition IN
        ('IDENTITY_REGISTERED','CLAIMED','TRANSFER_PENDING','REVOKED','RECOVERY_REQUIRED')),
    from_home_id TEXT REFERENCES households(home_id) ON DELETE RESTRICT,
    to_home_id TEXT REFERENCES households(home_id) ON DELETE RESTRICT,
    prior_epoch INTEGER NOT NULL CHECK(prior_epoch >= 0),
    new_epoch INTEGER NOT NULL CHECK(new_epoch >= 0),
    actor_id TEXT NOT NULL,
    authorization_reference TEXT NOT NULL,
    possession_proof_reference TEXT NOT NULL,
    occurred_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hub_ownership_history_device
    ON hub_ownership_history(hub_device_id, history_id);

CREATE TABLE IF NOT EXISTS node_enrollment_history (
    hub_device_id TEXT NOT NULL REFERENCES hub_ownership_registry(hub_device_id) ON DELETE RESTRICT,
    home_id TEXT NOT NULL REFERENCES households(home_id) ON DELETE RESTRICT,
    physical_node_id TEXT NOT NULL CHECK(length(physical_node_id) BETWEEN 1 AND 64),
    logical_node_id TEXT NOT NULL CHECK(length(logical_node_id) BETWEEN 1 AND 24),
    enrollment_generation INTEGER NOT NULL CHECK(enrollment_generation > 0),
    identity_key_fingerprint TEXT NOT NULL CHECK(length(identity_key_fingerprint) = 64),
    state TEXT NOT NULL CHECK(state IN ('ACTIVE','REPLACED','REVOKED')),
    authorization_reference TEXT NOT NULL,
    proof_reference TEXT NOT NULL,
    enrolled_at INTEGER NOT NULL,
    ended_at INTEGER,
    PRIMARY KEY(hub_device_id, physical_node_id, enrollment_generation),
    CHECK((state='ACTIVE' AND ended_at IS NULL) OR (state<>'ACTIVE' AND ended_at IS NOT NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_node_enrollment_one_active
    ON node_enrollment_history(hub_device_id, physical_node_id) WHERE state='ACTIVE';
-- A permanent Node identity is bound to only one active Hub/Home at a time.
CREATE UNIQUE INDEX IF NOT EXISTS idx_node_enrollment_identity_one_active
    ON node_enrollment_history(physical_node_id) WHERE state='ACTIVE';
CREATE INDEX IF NOT EXISTS idx_node_enrollment_lookup
    ON node_enrollment_history(hub_device_id, home_id, physical_node_id,
                               logical_node_id, enrollment_generation, state);
