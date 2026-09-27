-- ITGC-05 Shared or generic accounts
--
-- Objective: Each active account belongs to one identifiable person.
-- Risk: A shared or generic login cannot be tied to one employee, so
-- activity on that account cannot be attributed.
--
-- Population: active accounts.
-- Exception: is_shared is true. Disabled shared accounts are outside this
-- test because they cannot currently be used.

SELECT COUNT(*) AS population_count
FROM iam_accounts
WHERE status = 'active';

SELECT
    account.account_id AS exception_id,
    account.employee_id,
    account.system,
    account.role,
    account.last_login
FROM iam_accounts AS account
WHERE account.status = 'active'
  AND account.is_shared = TRUE
ORDER BY account.account_id;
