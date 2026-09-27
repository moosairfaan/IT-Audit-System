-- Sampling population for ITGC-01.
-- Every account tied to an employee with a termination_date, whether the
-- account is still active or already disabled.
-- role and system let risk-based sampling put privileged roles and critical
-- systems (payments, general ledger) first.

SELECT
    account.account_id AS item_id,
    account.role,
    account.system
FROM iam_accounts AS account
JOIN hr_roster AS employee ON employee.employee_id = account.employee_id
WHERE employee.termination_date IS NOT NULL
ORDER BY account.account_id;
