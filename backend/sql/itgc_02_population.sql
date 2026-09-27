-- Sampling population for ITGC-02.
-- Every user on the roster. A user with several accounts appears once per
-- account so the sampler can see each role and system. Users with no account
-- still appear, with a null role and system.
-- A user is higher risk when any account has a privileged role or sits on
-- payments or the general ledger.

SELECT
    employee.employee_id AS item_id,
    account.role,
    account.system
FROM hr_roster AS employee
LEFT JOIN iam_accounts AS account ON account.employee_id = employee.employee_id
ORDER BY employee.employee_id, account.account_id;
