-- Battery analytics calibration and telemetry history.
-- Calibration currents are measured per hardware profile/device; they are not household-routine policy.

CREATE TABLE IF NOT EXISTS battery_power_profiles (
    device_id TEXT PRIMARY KEY,
    usable_capacity_mah REAL NOT NULL CHECK (usable_capacity_mah > 0),
    reserve_percent REAL NOT NULL CHECK (reserve_percent >= 0 AND reserve_percent < 50),
    sleep_current_ma REAL NOT NULL CHECK (sleep_current_ma >= 0),
    awake_base_current_ma REAL NOT NULL CHECK (awake_base_current_ma >= 0),
    sensor_extra_current_ma REAL NOT NULL CHECK (sensor_extra_current_ma >= 0),
    radio_tx_extra_current_ma REAL NOT NULL CHECK (radio_tx_extra_current_ma >= 0),
    radio_rx_extra_current_ma REAL NOT NULL CHECK (radio_rx_extra_current_ma >= 0),
    high_drain_ratio REAL NOT NULL DEFAULT 1.75 CHECK (high_drain_ratio > 1.0),
    calibration_source TEXT NOT NULL DEFAULT 'UNVERIFIED'
        CHECK (calibration_source IN ('UNVERIFIED','BENCH_MEASURED','PRODUCTION_CALIBRATED')),
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS battery_usage_history (
    sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_id TEXT NOT NULL REFERENCES households(home_id) ON DELETE CASCADE,
    device_id TEXT NOT NULL,
    sampled_at INTEGER NOT NULL,
    battery_mv INTEGER NOT NULL CHECK (battery_mv BETWEEN 2500 AND 5000),
    charging INTEGER NOT NULL DEFAULT 0 CHECK (charging IN (0,1)),
    deep_sleep_ms INTEGER NOT NULL DEFAULT 0 CHECK (deep_sleep_ms >= 0),
    awake_ms INTEGER NOT NULL DEFAULT 0 CHECK (awake_ms >= 0),
    sensor_active_ms INTEGER NOT NULL DEFAULT 0 CHECK (sensor_active_ms >= 0),
    radio_tx_ms INTEGER NOT NULL DEFAULT 0 CHECK (radio_tx_ms >= 0),
    radio_rx_ms INTEGER NOT NULL DEFAULT 0 CHECK (radio_rx_ms >= 0),
    radio_tx_packets INTEGER NOT NULL DEFAULT 0 CHECK (radio_tx_packets >= 0),
    radio_retries INTEGER NOT NULL DEFAULT 0 CHECK (radio_retries >= 0),
    wake_count INTEGER NOT NULL DEFAULT 0 CHECK (wake_count >= 0),
    heartbeat_count INTEGER NOT NULL DEFAULT 0 CHECK (heartbeat_count >= 0),
    boot_count INTEGER NOT NULL DEFAULT 0 CHECK (boot_count >= 0),
    brownout_count INTEGER NOT NULL DEFAULT 0 CHECK (brownout_count >= 0),
    estimated_percent INTEGER CHECK (estimated_percent IS NULL OR estimated_percent BETWEEN 0 AND 100),
    estimated_daily_mah REAL CHECK (estimated_daily_mah IS NULL OR estimated_daily_mah >= 0),
    estimated_remaining_days REAL CHECK (estimated_remaining_days IS NULL OR estimated_remaining_days >= 0),
    confidence TEXT CHECK (confidence IS NULL OR confidence IN ('LOW','MEDIUM','HIGH')),
    drain_status TEXT CHECK (drain_status IS NULL OR drain_status IN ('LEARNING','NORMAL','HIGH')),
    UNIQUE(device_id, sampled_at)
);

CREATE INDEX IF NOT EXISTS idx_battery_usage_device_time
    ON battery_usage_history(device_id, sampled_at DESC);
