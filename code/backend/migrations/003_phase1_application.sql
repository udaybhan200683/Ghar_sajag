-- Application-owned Phase 1 state. Existing P0 hub/node/event tables retain their historical contract.
CREATE TABLE IF NOT EXISTS family_members (
    member_id TEXT PRIMARY KEY,
    home_id TEXT NOT NULL REFERENCES households(home_id) ON DELETE CASCADE,
    display_name TEXT NOT NULL,
    relationship TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL CHECK (role IN ('OWNER','FAMILY','CAREGIVER')),
    contact TEXT,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1)),
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_family_home_contact ON family_members(home_id, contact)
    WHERE contact IS NOT NULL AND active = 1;
CREATE INDEX IF NOT EXISTS idx_family_home_active ON family_members(home_id, active);

CREATE TABLE IF NOT EXISTS device_registry (
    device_id TEXT PRIMARY KEY,
    home_id TEXT NOT NULL REFERENCES households(home_id) ON DELETE CASCADE,
    display_name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('HUB','NODE')),
    capability TEXT NOT NULL CHECK (capability IN ('HUB','MOTION','DOOR','MOTION_BUTTON')),
    room TEXT NOT NULL,
    firmware_version TEXT,
    registration_source TEXT NOT NULL CHECK (registration_source IN ('SIMULATOR','PHYSICAL')),
    registered INTEGER NOT NULL DEFAULT 1 CHECK (registered IN (0,1)),
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1)),
    online INTEGER NOT NULL DEFAULT 0 CHECK (online IN (0,1)),
    health TEXT NOT NULL DEFAULT 'UNKNOWN' CHECK (health IN ('ACTIVE','DEGRADED','OFFLINE','UNKNOWN')),
    communication TEXT NOT NULL DEFAULT 'UNKNOWN' CHECK (communication IN ('ONLINE','OFFLINE','UNKNOWN')),
    last_seen_at INTEGER,
    battery_mv INTEGER CHECK (battery_mv IS NULL OR battery_mv BETWEEN 0 AND 6000),
    battery_percent INTEGER CHECK (battery_percent IS NULL OR battery_percent BETWEEN 0 AND 100),
    drain_status TEXT NOT NULL DEFAULT 'LEARNING' CHECK (drain_status IN ('NORMAL','HIGH','LEARNING')),
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_registry_home_registered ON device_registry(home_id, registered);

CREATE TABLE IF NOT EXISTS application_policy (
    home_id TEXT PRIMARY KEY REFERENCES households(home_id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1,
    policy_json TEXT NOT NULL,
    updated_at INTEGER NOT NULL
);
