-- Initial schema for The ITAudit System.
-- The seed command drops and recreates these tables, then loads the CSVs.
-- Control-test queries will live in their own files in this directory.

DROP TABLE IF EXISTS workpapers;
DROP TABLE IF EXISTS samples;
DROP TABLE IF EXISTS test_runs;
DROP TABLE IF EXISTS change_tickets;
DROP TABLE IF EXISTS iam_accounts;
DROP TABLE IF EXISTS sod_conflict_rules;
DROP TABLE IF EXISTS role_permissions;
DROP TABLE IF EXISTS hr_roster;

-- Population of workers. termination_date is null while the worker is employed.
CREATE TABLE hr_roster (
    employee_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    job_title TEXT NOT NULL,
    hire_date DATE NOT NULL,
    termination_date DATE,
    CHECK (termination_date IS NULL OR termination_date >= hire_date)
);

-- One application role and the permission it grants. A role may grant several permissions.
CREATE TABLE role_permissions (
    role TEXT NOT NULL,
    permission TEXT NOT NULL,
    PRIMARY KEY (role, permission)
);

-- Segregation-of-duties pairs. Holding both permissions is a conflict.
-- The seed command loads the pairs. This table starts empty.
CREATE TABLE sod_conflict_rules (
    rule_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    permission_a TEXT NOT NULL,
    permission_b TEXT NOT NULL,
    description TEXT NOT NULL,
    CHECK (permission_a <> permission_b),
    UNIQUE (permission_a, permission_b)
);

-- Accounts on in-scope systems. employee_id is null for a generic account.
CREATE TABLE iam_accounts (
    account_id TEXT PRIMARY KEY,
    employee_id TEXT REFERENCES hr_roster (employee_id),
    system TEXT NOT NULL,
    role TEXT NOT NULL,
    status TEXT NOT NULL,
    last_login TIMESTAMPTZ,
    is_shared BOOLEAN NOT NULL,
    CHECK (status IN ('active', 'disabled'))
);

CREATE INDEX iam_accounts_employee_id_idx ON iam_accounts (employee_id);
CREATE INDEX iam_accounts_status_idx ON iam_accounts (status);

-- Changes that were requested, approved, and deployed. Approval columns are null
-- when a change was deployed with no approval.
CREATE TABLE change_tickets (
    ticket_id TEXT PRIMARY KEY,
    system TEXT NOT NULL,
    requested_by TEXT NOT NULL REFERENCES hr_roster (employee_id),
    approved_by TEXT REFERENCES hr_roster (employee_id),
    deployed_by TEXT NOT NULL REFERENCES hr_roster (employee_id),
    approved_at TIMESTAMPTZ,
    deployed_at TIMESTAMPTZ,
    description TEXT NOT NULL
);

-- One row each time a control test is executed. exceptions is the result set.
CREATE TABLE test_runs (
    run_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    control_id TEXT NOT NULL,
    name TEXT NOT NULL,
    objective TEXT NOT NULL,
    risk_addressed TEXT NOT NULL,
    population_count INTEGER NOT NULL,
    exception_count INTEGER NOT NULL,
    exceptions JSONB NOT NULL,
    run_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX test_runs_control_id_idx ON test_runs (control_id, run_id DESC);

-- One sample drawn from a control population. selected_ids keeps selection order.
-- The same control, method, sample size, and seed reproduce the same ids.
CREATE TABLE samples (
    sample_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    control_id TEXT NOT NULL,
    run_id INTEGER NOT NULL REFERENCES test_runs (run_id),
    method TEXT NOT NULL,
    seed BIGINT NOT NULL,
    population_size INTEGER NOT NULL,
    sample_size INTEGER NOT NULL,
    selected_ids JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CHECK (method IN ('random', 'risk_based')),
    CHECK (sample_size > 0)
);

-- Draft, reviewed, or approved workpaper for one test run.
-- source_json is the only fact set the draft is allowed to use.
-- An approved row is read-only.
CREATE TABLE workpapers (
    workpaper_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    control_id TEXT NOT NULL,
    run_id INTEGER NOT NULL REFERENCES test_runs (run_id),
    sample_id INTEGER REFERENCES samples (sample_id),
    status TEXT NOT NULL,
    sections JSONB NOT NULL,
    markdown TEXT NOT NULL,
    source_json JSONB NOT NULL,
    reviewer_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    edited_at TIMESTAMPTZ NOT NULL,
    CHECK (status IN ('draft', 'reviewed', 'approved'))
);
