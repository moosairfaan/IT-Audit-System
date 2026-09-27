# The ITAudit System

A tool for an IT audit team at a financial services firm. Auditors upload client-style data, the system runs IT general controls (ITGC) tests, and it drafts an audit workpaper for each test.

Phase 4 drafts an audit workpaper from a stored test run. The model receives only that result. A draft is stored only when every number in it already appears in the result.

The population is fictional. It is practice data for control testing, not a record of a real firm.

## Stack

Python, FastAPI, PostgreSQL, SQLAlchemy, pandas, and pytest. React, TypeScript, and Vite, with Recharts. The Anthropic API is reserved for workpaper drafting. Uvicorn serves the API, and psycopg is the PostgreSQL driver.

Postgres runs from `docker-compose.yml` on port **5433**.

## Phase 1 data

`python -m data_gen.seed` builds about 400 employees with a fixed random seed, writes CSVs, and loads every table. Known exceptions are listed in `backend/data_gen/generated/ground_truth.json`. The detection rules and control identifiers are in [docs/data.md](docs/data.md).

| Table | Rows |
| --- | ---: |
| hr_roster | 400 |
| role_permissions | 15 |
| sod_conflict_rules | 5 |
| iam_accounts | 811 |
| change_tickets | 50 |

## Setup

From the repository root, with Docker, Python 3.13, and Node:

```bash
docker compose up -d
python3.13 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt && npm --prefix frontend install
cd backend && .venv/bin/python -m data_gen.seed
```

The API and the dashboard each need a terminal:

```bash
backend/.venv/bin/uvicorn app.main:app --app-dir backend --port 8000
npm --prefix frontend run dev
```

Open http://127.0.0.1:5173. If `docker compose` is not installed, use `docker-compose up -d`.

`POST /api/upload/{dataset}` accepts the raw CSV and replaces that table. Datasets: `hr_roster`, `role_permissions`, `sod_conflict_rules`, `iam_accounts`, `change_tickets`. Load `hr_roster` before the tables that reference it.

`POST /api/tests/{control_id}/run` executes one control and stores the run. `GET /api/tests` returns the latest run of each control. `GET /api/tests/{control_id}/runs/{run_id}` returns one stored run. The dormant and termination day counts use the population as-of date, 1 September 2026.

`POST /api/tests/{control_id}/sample` draws a sample from that control's population after a run exists. The body is `method` (`random` or `risk_based`), `sample_size`, and an optional `seed`. When `seed` is omitted, the API generates one and returns it. The same method, sample size, and seed reproduce the same selected ids. Risk-based sampling takes privileged roles and the critical systems (payments and the general ledger) first, then fills the rest at random. `GET /api/samples/{sample_id}` returns the stored sample.

`POST /api/workpapers/generate` drafts a workpaper for a `control_id` and `run_id`, with an optional `sample_id`. The prompt template is `backend/app/workpapers/prompt.txt`. Set `ANTHROPIC_API_KEY` before generating a live draft. `GET /api/workpapers/{id}` returns the draft. `PATCH /api/workpapers/{id}` edits sections, sets `reviewer_notes`, or moves status among `draft`, `reviewed`, and `approved`. An approved workpaper is read-only. `GET /api/workpapers/{id}/export` returns the markdown.

```bash
backend/.venv/bin/pytest -q
```

The control tests need Postgres. The generator tests do not.

## Layout

- `backend/app/` API and table loading
- `backend/sql/` database init now; one commented file per control test later
- `backend/tests/`
- `backend/data_gen/` seeded generator and `python -m data_gen.seed`
- `frontend/`
- `docs/`

## Working rules

Build one phase at a time and stop for review. Use audit terms: control, exception, deficiency, population, sample, completeness and accuracy. Ask before adding a dependency that is not in the stack above.
