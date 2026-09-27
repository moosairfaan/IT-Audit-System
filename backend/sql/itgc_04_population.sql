-- Sampling population for ITGC-04.
-- Every active account, including shared accounts.
-- role and system let risk-based sampling put privileged roles and critical
-- systems (payments, general ledger) first.

SELECT
    account.account_id AS item_id,
    account.role,
    account.system
FROM iam_accounts AS account
WHERE account.status = 'active'
ORDER BY account.account_id;
