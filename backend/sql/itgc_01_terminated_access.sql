-- ITGC-01 Terminated user access
--
-- Objective: Active application accounts are removed when employment ends.
-- Risk: A former employee can still sign in and use a production system after
-- the termination date. That is unauthorized access.
--
-- Population: every account linked to an employee who has a termination_date.
-- Those accounts should be disabled.
-- Exception: the account status is still active.
-- days_after_termination is the number of days from the termination date
-- through the as-of date, which is how long the account stayed available.

SELECT COUNT(*) AS population_count
FROM iam_accounts AS account
JOIN hr_roster AS employee ON employee.employee_id = account.employee_id
WHERE employee.termination_date IS NOT NULL;

SELECT
    account.account_id AS exception_id,
    account.employee_id,
    employee.name,
    employee.department,
    account.system,
    account.role,
    employee.termination_date,
    account.last_login,
    (CAST(:as_of AS date) - employee.termination_date) AS days_after_termination
FROM iam_accounts AS account
JOIN hr_roster AS employee ON employee.employee_id = account.employee_id
WHERE employee.termination_date IS NOT NULL
  AND account.status = 'active'
ORDER BY account.account_id;
