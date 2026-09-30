# The ITAudit System

A tool for an IT audit team at a financial services firm. Auditors load a population, run IT general controls (ITGC) tests, select a sample, and draft an audit workpaper for each test.

The live dashboard is [https://it-audit-system-thuk.vercel.app](https://it-audit-system-thuk.vercel.app).

The population is fictional. It is practice data for control testing, not a record of a real firm.

## Stack

Python, FastAPI, PostgreSQL, SQLAlchemy, pandas, and pytest. React, TypeScript, and Vite, with Recharts. The Anthropic API drafts workpapers. Uvicorn serves the API, and psycopg is the PostgreSQL driver.

Local Postgres runs from `docker-compose.yml` on port **5433**.

## Controls

The synthetic population is about 400 employees, loaded by `python -m data_gen.seed`. Known exceptions for ITGC-01 through ITGC-05 are in `backend/data_gen/generated/ground_truth.json`. Detection rules are in [docs/data.md](docs/data.md). The as-of date is 1 September 2026.

| Table | Rows |
| --- | ---: |
| hr_roster | 400 |
| role_permissions | 15 |
| sod_conflict_rules | 5 |
| iam_accounts | 811 |
| change_tickets | 50 |

| Control | What it tests | Demo exceptions |
| --- | --- | ---: |
| ITGC-01 | Terminated user access | 8 |
| ITGC-02 | Segregation of duties | 6 |
| ITGC-03 | Change management | 10 |
| ITGC-04 | Dormant accounts | 6 |
| ITGC-05 | Shared or generic accounts | 5 |
| ITGC-06 | Orphaned accounts and unknown users | 0 |

On the demo population the total is 35 exceptions: 11 high, 13 medium, and 11 low. High severity is a terminated employee who still has access, a segregation-of-duties conflict on payments or the general ledger, or an orphaned account or unknown user. Medium is every other exception, including change-management defects. Low is a dormant account or a shared account.

ITGC-06 is zero on the demo data because every generated account and change names someone on the HR roster. An uploaded account or change that names a person who is not on the roster is loaded and reported as an ITGC-06 exception.

## Company data

The active dataset is either **Demo data** or **Company data**. Control tests always read the active tables. Switching back to demo data restores the synthetic population from a snapshot.

The import wizard takes four files: HR roster, application accounts, role permissions, and change tickets. It maps columns, normalizes status values, and shows a validation report before anything is written. Rows with a missing id, a bad date, a duplicate key, or a status that does not map are skipped. A row that names a person who is not on the HR roster is loaded and listed under “Loaded, flagged for review.”

The settings page stores privileged roles, critical systems, the dormancy window, and segregation-of-duties pairs. Each control page shows records loaded, records tested, and records excluded, with a reason for each exclusion. The workpaper Population and sample section states those same counts.

Set `ALLOW_REAL_DATA=false` to hide company data and reject import requests. The live site currently allows company data.

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

Open http://127.0.0.1:5173. If `docker compose` is not installed, use `docker-compose up -d`. Leave `VITE_API_URL` empty locally so Vite proxies `/api` to port 8000.

```bash
backend/.venv/bin/pytest -q
npm --prefix frontend run test:e2e
```

The control tests need Postgres. Reseed before the Playwright suite so the dashboard starts from an empty run list. The generator tests do not need Postgres.

## API

`POST /api/upload/{dataset}` accepts a raw CSV and replaces that table. Datasets: `hr_roster`, `role_permissions`, `sod_conflict_rules`, `iam_accounts`, `change_tickets`. Load `hr_roster` before the tables that reference it.

`POST /api/tests/{control_id}/run` executes one control and stores the run. `GET /api/tests` returns the latest run of each control. `POST /api/tests/run-all` runs all six controls. `GET /api/overview` returns controls tested, total exceptions, workpapers by status, exceptions by control, and exceptions by severity.

`POST /api/tests/{control_id}/sample` draws a sample after a run exists. The body is `method` (`random` or `risk_based`), `sample_size`, and an optional `seed`. The same method, sample size, and seed reproduce the same selected ids. Risk-based sampling takes privileged roles and the critical systems first.

`POST /api/workpapers/generate` drafts a workpaper for a `control_id` and `run_id`, with an optional `sample_id`. The prompt is `backend/app/workpapers/prompt.txt`. Set `ANTHROPIC_API_KEY` before generating a live draft. `PATCH /api/workpapers/{id}` edits sections or moves status among `draft`, `reviewed`, and `approved`. An approved workpaper is read-only. `GET /api/workpapers/{id}/export` returns the markdown.

`GET /api/data-source` and `POST /api/data-source` read and switch the active dataset. `GET /api/completeness` returns loaded, tested, and excluded counts. `GET /api/settings` and `PUT /api/settings` read and save the audit rules. Import routes live under `/api/import/`.

## Deployment

Vercel serves the React app. Railway runs the API and Postgres. Workpaper generation waits on the model for up to 60 seconds, so the API stays a long-running process.

- Vercel project root: `frontend`. Set `VITE_API_URL` to the Railway origin with no trailing slash, then redeploy. `frontend/vercel.json` sends client routes back to `index.html`.
- Railway builds this repo with `railpack.json`. The start command loads the synthetic population only when the HR roster is empty. Set `DATABASE_URL` to `${{Postgres.DATABASE_URL}}`. A `postgres://` or `postgresql://` URL is rewritten to `postgresql+psycopg://` on startup. Set `CORS_ORIGINS` to the Vercel origin, `https://it-audit-system-thuk.vercel.app`, with no trailing slash.

## Layout

- `backend/app/` API, control tests, import, and workpapers
- `backend/sql/` schema and one query file per control
- `backend/tests/`
- `backend/data_gen/` seeded generator and `python -m data_gen.seed`
- `frontend/` dashboard
- `docs/`
