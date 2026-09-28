-- Sampling population for ITGC-06.
-- Orphaned accounts and change tickets that name a person who is not on
-- the HR roster. role and system let risk-based sampling put privileged
-- roles and critical systems first.

SELECT
    account.account_id AS item_id,
    account.role,
    account.system
FROM iam_accounts AS account
WHERE account.employee_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM hr_roster AS employee
      WHERE employee.employee_id = account.employee_id
  )
UNION ALL
SELECT
    ticket.ticket_id AS item_id,
    NULL AS role,
    ticket.system
FROM change_tickets AS ticket
WHERE NOT EXISTS (
        SELECT 1 FROM hr_roster AS employee
        WHERE employee.employee_id = ticket.requested_by
      )
   OR (
        ticket.approved_by IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM hr_roster AS employee
            WHERE employee.employee_id = ticket.approved_by
        )
      )
   OR NOT EXISTS (
        SELECT 1 FROM hr_roster AS employee
        WHERE employee.employee_id = ticket.deployed_by
      )
ORDER BY item_id;
