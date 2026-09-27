# Synthetic population

The generator builds a fictional broker-dealer of 400 employees. `python -m data_gen.seed` uses random seed `20260901` and an as-of date of 1 September 2026, writes CSVs under `backend/data_gen/generated/`, and loads Postgres.

`ground_truth.json` maps each control to the identifiers the SQL test must find. The queries are in `backend/sql/itgc_01_terminated_access.sql` through `itgc_05_shared_accounts.sql`. Day counts use the as-of date 1 September 2026.

| Control | What it is | Identifier |
| --- | --- | --- |
| ITGC-01 | Terminated employee whose account is still active | `account_id` |
| ITGC-02 | Employee who holds both permissions in a segregation-of-duties pair | `employee_id` |
| ITGC-03 | Change deployed before approval, with no approval, or approved by the requester or the deployer | `ticket_id` |
| ITGC-04 | Active account, not shared, with no login in the 90 days before the as-of date | `account_id` |
| ITGC-05 | Shared or generic account | `account_id` |

Injected counts: 8 terminated-but-active accounts, 6 segregation-of-duties users, 10 improper changes, 6 dormant accounts, and 5 shared accounts. The five shared accounts include three generic accounts with no employee and two shared accounts owned by an active employee.

Dormant detection ignores shared accounts, because those are ITGC-05. The synthetic rows are otherwise in separate populations, so one record is not listed under two controls.

Segregation-of-duties pairs in `sod_conflict_rules`:

- `create_payment` and `approve_payment`
- `create_journal` and `approve_journal`
- `submit_trade` and `approve_trade`
- `request_access` and `approve_access`
- `develop_change` and `deploy_change`

In-scope systems: trading platform, general ledger, payments, HR system, core database.

## Sampling populations

Samples are drawn from the full population, not only from the exceptions.

| Control | Population |
| --- | --- |
| ITGC-01 | Accounts belonging to employees with a termination date, active or disabled |
| ITGC-02 | Every user on the roster |
| ITGC-03 | Every change ticket |
| ITGC-04 | Every active account |
| ITGC-05 | Every active account |

Risk-based sampling selects higher-risk items first. A privileged role is one that can approve or deploy: `trade_supervisor`, `journal_approver`, `payment_approver`, `access_approver`, or `release_manager`. Payments and the general ledger are the critical systems. An account or ticket on one of those systems is higher risk, and a user is higher risk when any of their accounts is.
