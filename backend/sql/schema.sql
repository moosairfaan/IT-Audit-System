-- Initial schema for The ITAudit System.
-- The seed command drops and recreates these tables, then loads the CSVs.
-- Control-test queries will live in their own files in this directory.

DROP TABLE IF EXISTS workpapers;
DROP TABLE IF EXISTS samples;
DROP TABLE IF EXISTS test_runs;
DROP TABLE IF EXISTS column_mappings;
DROP TABLE IF EXISTS dataset_snapshots;
DROP TABLE IF EXISTS audit_context;
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
-- A value that is not on the HR roster is kept and reported by ITGC-06.
CREATE TABLE iam_accounts (
    account_id TEXT PRIMARY KEY,
    employee_id TEXT,
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
-- when a change was deployed with no approval. A person id that is not on the
-- HR roster is kept and reported by ITGC-06.
CREATE TABLE change_tickets (
    ticket_id TEXT PRIMARY KEY,
    system TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    approved_by TEXT,
    deployed_by TEXT NOT NULL,
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
    run_at TIMESTAMPTZ NOT NULL,
    dataset TEXT NOT NULL DEFAULT 'demo',
    completeness JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (dataset IN ('demo', 'company'))
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
    dataset TEXT NOT NULL DEFAULT 'demo',
    CHECK (dataset IN ('demo', 'company')),
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
    dataset TEXT NOT NULL DEFAULT 'demo',
    CHECK (dataset IN ('demo', 'company')),
    CHECK (status IN ('draft', 'reviewed', 'approved'))
);

-- Which population the controls read, and the editable test rules.
-- privileged_roles and critical_systems are JSON arrays of strings.
CREATE TABLE audit_context (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    active_dataset TEXT NOT NULL DEFAULT 'demo',
    dormant_days INTEGER NOT NULL DEFAULT 90,
    privileged_roles JSONB NOT NULL,
    critical_systems JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CHECK (active_dataset IN ('demo', 'company')),
    CHECK (dormant_days >= 1)
);

INSERT INTO audit_context (
    id, active_dataset, dormant_days, privileged_roles, critical_systems, updated_at
) VALUES (
    1,
    'demo',
    90,
    '["trade_supervisor", "journal_approver", "payment_approver", "access_approver", "release_manager"]',
    '["payments", "general ledger"]',
    CURRENT_TIMESTAMP
);

-- Column mapping remembered for the next company-data upload.
CREATE TABLE column_mappings (
    dataset TEXT PRIMARY KEY,
    mapping JSONB NOT NULL,
    status_map JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

-- The population that is not currently loaded into the control tables.
CREATE TABLE dataset_snapshots (
    dataset TEXT NOT NULL,
    table_name TEXT NOT NULL,
    payload JSONB NOT NULL,
    saved_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (dataset, table_name),
    CHECK (dataset IN ('demo', 'company'))
);
