CREATE TABLE IF NOT EXISTS lite_schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS lite_homes (
  home_id TEXT PRIMARY KEY,
  test_only BOOLEAN NOT NULL,
  ownership_epoch INTEGER NOT NULL CHECK (ownership_epoch > 0),
  simulation_generation INTEGER NOT NULL DEFAULT 1 CHECK (simulation_generation > 0)
);
CREATE TABLE IF NOT EXISTS lite_accounts (
  account_id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  active BOOLEAN NOT NULL
);
CREATE TABLE IF NOT EXISTS lite_memberships (
  account_id TEXT NOT NULL REFERENCES lite_accounts(account_id),
  home_id TEXT NOT NULL REFERENCES lite_homes(home_id),
  role TEXT NOT NULL CHECK (role IN ('ADMIN','CAREGIVER')),
  active BOOLEAN NOT NULL,
  ownership_epoch INTEGER NOT NULL,
  PRIMARY KEY(account_id,home_id)
);
CREATE TABLE IF NOT EXISTS lite_sessions (
  session_id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES lite_accounts(account_id),
  token_hash TEXT NOT NULL UNIQUE,
  issued_at BIGINT NOT NULL,
  expires_at BIGINT NOT NULL,
  revoked_at BIGINT
);
CREATE TABLE IF NOT EXISTS lite_login_limits (
  key_hash TEXT PRIMARY KEY,
  failures INTEGER NOT NULL,
  blocked_until BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS lite_api_limits (
  account_id TEXT PRIMARY KEY REFERENCES lite_accounts(account_id),
  window_start BIGINT NOT NULL,
  request_count INTEGER NOT NULL CHECK (request_count > 0)
);
CREATE TABLE IF NOT EXISTS lite_runs (
  run_id TEXT PRIMARY KEY,
  home_id TEXT NOT NULL REFERENCES lite_homes(home_id),
  account_id TEXT NOT NULL REFERENCES lite_accounts(account_id),
  scenario_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('PASS','FAIL','BLOCKED','NOT_RUN')),
  simulation_generation INTEGER NOT NULL,
  created_at BIGINT NOT NULL,
  result_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS lite_runs_home_time ON lite_runs(home_id,created_at);
