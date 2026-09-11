PRAGMA foreign_keys = ON;

-- P0 relational contract. SQLite is used for host validation; PostgreSQL should preserve the same
-- identities, foreign keys and uniqueness semantics while strengthening JSON/time types.

CREATE TABLE IF NOT EXISTS households (
    home_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    timezone TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'en-IN',
    mode TEXT NOT NULL DEFAULT 'HOME'
        CHECK (mode IN ('HOME','AWAY','PAUSED','VISITOR','PRIVACY')),
    consent_state TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK (consent_state IN ('ACTIVE','WITHDRAWN','PENDING')),
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS rooms (
    room_id TEXT PRIMARY KEY,
    home_id TEXT NOT NULL REFERENCES households(home_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    room_type TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1)),
    UNIQUE(home_id, name)
);

CREATE TABLE IF NOT EXISTS caregivers (
    caregiver_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    contact_ref TEXT,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS household_caregivers (
    home_id TEXT NOT NULL REFERENCES households(home_id) ON DELETE CASCADE,
    caregiver_id TEXT NOT NULL REFERENCES caregivers(caregiver_id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('OWNER','PRIMARY','BACKUP','FAMILY')),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1)),
    escalation_order INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(home_id, caregiver_id)
);

CREATE TABLE IF NOT EXISTS hubs (
    hub_id TEXT PRIMARY KEY,
    home_id TEXT NOT NULL REFERENCES households(home_id) ON DELETE CASCADE,
    location TEXT NOT NULL DEFAULT 'Home',
    board_profile TEXT NOT NULL,
    firmware_version TEXT NOT NULL,
    config_version INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'UNKNOWN'
        CHECK (status IN ('ACTIVE','DEGRADED','OFFLINE','UNKNOWN')),
    last_seen_at INTEGER,
    internet_state TEXT NOT NULL DEFAULT 'UNKNOWN'
        CHECK (internet_state IN ('ONLINE','OFFLINE','UNKNOWN')),
    error_code TEXT,
    boot_id TEXT,
    reset_reason TEXT
);

CREATE TABLE IF NOT EXISTS nodes (
    node_id TEXT PRIMARY KEY,
    home_id TEXT NOT NULL REFERENCES households(home_id) ON DELETE CASCADE,
    hub_id TEXT REFERENCES hubs(hub_id) ON DELETE SET NULL,
    room_id TEXT REFERENCES rooms(room_id) ON DELETE SET NULL,
    location TEXT NOT NULL,
    board_profile TEXT NOT NULL,
    capability_profile TEXT NOT NULL,
    firmware_version TEXT NOT NULL,
    config_version INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'UNKNOWN'
        CHECK (status IN ('ACTIVE','DEGRADED','OFFLINE','UNKNOWN')),
    last_seen_at INTEGER,
    last_rssi_dbm INTEGER CHECK (last_rssi_dbm IS NULL OR last_rssi_dbm BETWEEN -127 AND 20),
    last_battery_mv INTEGER CHECK (last_battery_mv IS NULL OR last_battery_mv BETWEEN 0 AND 6000),
    error_code TEXT,
    session_id INTEGER,
    last_sequence_number INTEGER,
    UNIQUE(home_id, node_id)
);

CREATE INDEX IF NOT EXISTS idx_nodes_home_status ON nodes(home_id, status);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    home_id TEXT NOT NULL REFERENCES households(home_id) ON DELETE CASCADE,
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL
        CHECK (source_type IN ('NODE','HUB','RESIDENT_CONTROL','SYSTEM')),
    node_id TEXT REFERENCES nodes(node_id) ON DELETE SET NULL,
    room_id TEXT REFERENCES rooms(room_id) ON DELETE SET NULL,
    session_id INTEGER NOT NULL,
    sequence_number INTEGER NOT NULL,
    sensor_type TEXT NOT NULL,
    event_type TEXT NOT NULL,
    location TEXT NOT NULL,
    occurred_at INTEGER,
    received_at INTEGER NOT NULL,
    uncertainty_ms INTEGER NOT NULL DEFAULT 0 CHECK (uncertainty_ms >= 0),
    battery_mv INTEGER CHECK (battery_mv IS NULL OR battery_mv BETWEEN 0 AND 6000),
    rssi_dbm INTEGER CHECK (rssi_dbm IS NULL OR rssi_dbm BETWEEN -127 AND 20),
    is_test INTEGER NOT NULL DEFAULT 0 CHECK (is_test IN (0,1)),
    payload_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(source_id, session_id, sequence_number)
);

CREATE INDEX IF NOT EXISTS idx_events_home_time ON events(home_id, occurred_at DESC, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_node_time ON events(node_id, received_at DESC);

CREATE TABLE IF NOT EXISTS routines (
    routine_id TEXT PRIMARY KEY,
    home_id TEXT NOT NULL REFERENCES households(home_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    routine_type TEXT NOT NULL
        CHECK (routine_type IN ('MORNING_ACTIVITY','DAYTIME_INACTIVITY','QUIET_HOURS','DOOR_OPEN_TIMEOUT','CUSTOM')),
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1)),
    window_start_minute INTEGER CHECK (window_start_minute IS NULL OR window_start_minute BETWEEN 0 AND 1439),
    window_end_minute INTEGER CHECK (window_end_minute IS NULL OR window_end_minute BETWEEN 0 AND 1439),
    grace_seconds INTEGER NOT NULL DEFAULT 0 CHECK (grace_seconds >= 0),
    threshold_seconds INTEGER CHECK (threshold_seconds IS NULL OR threshold_seconds >= 0),
    qualifying_locations_json TEXT NOT NULL DEFAULT '[]',
    policy_json TEXT NOT NULL DEFAULT '{}',
    config_version INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    UNIQUE(home_id, name, config_version)
);

CREATE TABLE IF NOT EXISTS routine_windows (
    window_id TEXT PRIMARY KEY,
    routine_id TEXT NOT NULL REFERENCES routines(routine_id) ON DELETE CASCADE,
    home_id TEXT NOT NULL REFERENCES households(home_id) ON DELETE CASCADE,
    start_at INTEGER NOT NULL,
    end_at INTEGER NOT NULL,
    grace_end_at INTEGER NOT NULL,
    state TEXT NOT NULL
        CHECK (state IN ('OPEN','SATISFIED','MISSING','UNKNOWN','SUPPRESSED','CLOSED')),
    coverage_state TEXT NOT NULL
        CHECK (coverage_state IN ('COVERED','UNKNOWN','FAULT')),
    evidence_json TEXT NOT NULL DEFAULT '[]',
    incident_stable_key TEXT,
    updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_routine_windows_home_time ON routine_windows(home_id, start_at DESC);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id TEXT PRIMARY KEY,
    home_id TEXT NOT NULL REFERENCES households(home_id) ON DELETE CASCADE,
    stable_key TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('INFO','EXPECTED','CONCERN','URGENT')),
    state TEXT NOT NULL CHECK (state IN ('OPEN','CLAIMED','ACKNOWLEDGED','RESOLVED','CANCELLED','ROUTE_EXHAUSTED')),
    source_event_id TEXT REFERENCES events(event_id) ON DELETE SET NULL,
    routine_window_id TEXT REFERENCES routine_windows(window_id) ON DELETE SET NULL,
    owner_caregiver_id TEXT REFERENCES caregivers(caregiver_id) ON DELETE SET NULL,
    owner_lease_until INTEGER,
    created_at INTEGER NOT NULL,
    acknowledged_at INTEGER,
    resolved_at INTEGER,
    is_test INTEGER NOT NULL DEFAULT 0 CHECK (is_test IN (0,1)),
    details_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(home_id, stable_key)
);

CREATE INDEX IF NOT EXISTS idx_alerts_home_state ON alerts(home_id, state, created_at DESC);

CREATE TABLE IF NOT EXISTS acknowledgements (
    acknowledgement_id TEXT PRIMARY KEY,
    alert_id TEXT NOT NULL REFERENCES alerts(alert_id) ON DELETE CASCADE,
    caregiver_id TEXT REFERENCES caregivers(caregiver_id) ON DELETE SET NULL,
    action TEXT NOT NULL
        CHECK (action IN ('CLAIM','ACKNOWLEDGE','CONTACTED','UNABLE_TO_REACH','RESOLVE','HANDOFF','AUTO_RESOLVE')),
    occurred_at INTEGER NOT NULL,
    note TEXT
);

CREATE INDEX IF NOT EXISTS idx_ack_alert_time ON acknowledgements(alert_id, occurred_at);

CREATE TABLE IF NOT EXISTS notification_jobs (
    job_id TEXT PRIMARY KEY,
    alert_id TEXT NOT NULL REFERENCES alerts(alert_id) ON DELETE CASCADE,
    home_id TEXT NOT NULL REFERENCES households(home_id) ON DELETE CASCADE,
    recipient_id TEXT NOT NULL REFERENCES caregivers(caregiver_id) ON DELETE CASCADE,
    stage INTEGER NOT NULL DEFAULT 0,
    due_at INTEGER NOT NULL,
    state TEXT NOT NULL
        CHECK (state IN ('CREATED','PROVIDER_ACCEPTED','HUMAN_ACKED','FAILED','CANCELLED')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    provider_reference TEXT,
    idempotency_key TEXT NOT NULL UNIQUE,
    last_attempt_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_notification_due ON notification_jobs(state, due_at);

CREATE TABLE IF NOT EXISTS battery_history (
    sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    sampled_at INTEGER NOT NULL,
    battery_mv INTEGER NOT NULL CHECK (battery_mv BETWEEN 0 AND 6000),
    percent_estimate INTEGER CHECK (percent_estimate IS NULL OR percent_estimate BETWEEN 0 AND 100),
    charging INTEGER CHECK (charging IS NULL OR charging IN (0,1)),
    source_event_id TEXT REFERENCES events(event_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_battery_node_time ON battery_history(node_id, sampled_at DESC);

CREATE TABLE IF NOT EXISTS device_health_history (
    sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_id TEXT NOT NULL REFERENCES households(home_id) ON DELETE CASCADE,
    device_type TEXT NOT NULL CHECK (device_type IN ('HUB','NODE')),
    device_id TEXT NOT NULL,
    sampled_at INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ACTIVE','DEGRADED','OFFLINE','UNKNOWN')),
    error_code TEXT,
    rssi_dbm INTEGER CHECK (rssi_dbm IS NULL OR rssi_dbm BETWEEN -127 AND 20),
    battery_mv INTEGER CHECK (battery_mv IS NULL OR battery_mv BETWEEN 0 AND 6000),
    temperature_c_x10 INTEGER,
    details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_health_device_time
    ON device_health_history(home_id, device_type, device_id, sampled_at DESC);

CREATE TABLE IF NOT EXISTS configurations (
    config_id TEXT PRIMARY KEY,
    home_id TEXT NOT NULL REFERENCES households(home_id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    schema_version INTEGER NOT NULL DEFAULT 1,
    config_json TEXT NOT NULL,
    desired_at INTEGER NOT NULL,
    applied_at INTEGER,
    status TEXT NOT NULL CHECK (status IN ('DESIRED','APPLIED','REJECTED','SUPERSEDED')),
    rejection_reason TEXT,
    UNIQUE(home_id, version)
);

CREATE INDEX IF NOT EXISTS idx_configs_home_version ON configurations(home_id, version DESC);

CREATE TABLE IF NOT EXISTS audit_log (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_id TEXT NOT NULL REFERENCES households(home_id) ON DELETE CASCADE,
    occurred_at INTEGER NOT NULL,
    actor_type TEXT NOT NULL CHECK (actor_type IN ('DEVICE','CAREGIVER','RESIDENT','SYSTEM','SUPPORT')),
    actor_id TEXT NOT NULL,
    action TEXT NOT NULL,
    subject_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_audit_home_time ON audit_log(home_id, occurred_at DESC);
