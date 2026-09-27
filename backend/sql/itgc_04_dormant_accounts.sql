-- ITGC-04 Dormant accounts
--
-- Objective: An active account has been used within the last 90 days, or it
-- is disabled.
-- Risk: A credential nobody is watching can be reused without the owner
-- noticing.
--
-- Population: active accounts that are not shared. Shared and generic
-- accounts are tested by ITGC-05, so they are not also dormant exceptions.
-- Exception: last_login is missing, or the login is on or before the as-of
-- date minus 90 days. A login exactly 90 days earlier is included.

SELECT COUNT(*) AS population_count
FROM iam_accounts
WHERE status = 'active'
  AND is_shared = FALSE;

SELECT
    account.account_id AS exception_id,
    account.employee_id,
    account.system,
    account.role,
    account.last_login
FROM iam_accounts AS account
WHERE account.status = 'active'
  AND account.is_shared = FALSE
  AND (
        account.last_login IS NULL
        OR account.last_login <= (CAST(:as_of AS timestamp) AT TIME ZONE 'UTC') - INTERVAL '90 days'
      )
ORDER BY account.account_id;
