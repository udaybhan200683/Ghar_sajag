-- Host SQLite service desk state. Deployment requires a reviewed PostgreSQL adapter.
CREATE TABLE IF NOT EXISTS service_tickets (
    ticket_id TEXT PRIMARY KEY,
    home_id TEXT NOT NULL REFERENCES households(home_id) ON DELETE RESTRICT,
    hub_device_id TEXT NOT NULL REFERENCES hub_ownership_registry(hub_device_id) ON DELETE RESTRICT,
    ownership_epoch INTEGER NOT NULL CHECK(ownership_epoch > 0),
    company_id TEXT NOT NULL,
    created_by TEXT NOT NULL,
    reason TEXT NOT NULL CHECK(length(reason) BETWEEN 1 AND 500),
    status TEXT NOT NULL CHECK(status IN ('OPEN','IN_PROGRESS','CLOSED')),
    assignee_id TEXT,
    assignment_version INTEGER NOT NULL DEFAULT 0 CHECK(assignment_version >= 0),
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_service_tickets_queue
    ON service_tickets(company_id, status, assignee_id, created_at);
CREATE TABLE IF NOT EXISTS service_access_requests (
    request_id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL REFERENCES service_tickets(ticket_id) ON DELETE RESTRICT,
    employee_id TEXT NOT NULL,
    employee_role TEXT NOT NULL CHECK(employee_role IN ('ADMIN','TECHNICIAN')),
    assignment_version INTEGER NOT NULL,
    home_id TEXT NOT NULL,
    hub_device_id TEXT NOT NULL,
    ownership_epoch INTEGER NOT NULL,
    node_scope_json TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('PENDING','APPROVED','DENIED','REVOKED','EXPIRED','CANCELLED')),
    requested_at INTEGER NOT NULL,
    approved_by TEXT,
    decided_at INTEGER,
    expires_at INTEGER,
    grant_id TEXT UNIQUE,
    CHECK ((state='APPROVED' AND approved_by IS NOT NULL AND decided_at IS NOT NULL
            AND expires_at IS NOT NULL AND grant_id IS NOT NULL) OR state<>'APPROVED')
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_service_one_live_request
    ON service_access_requests(ticket_id) WHERE state IN ('PENDING','APPROVED');
CREATE INDEX IF NOT EXISTS idx_service_requests_ticket
    ON service_access_requests(ticket_id, requested_at);
CREATE TABLE IF NOT EXISTS service_assignment_cursor (
    company_id TEXT PRIMARY KEY,
    last_employee_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS service_access_audit (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id TEXT NOT NULL REFERENCES service_tickets(ticket_id) ON DELETE RESTRICT,
    request_id TEXT,
    actor_id TEXT NOT NULL,
    action TEXT NOT NULL,
    occurred_at INTEGER NOT NULL
);
