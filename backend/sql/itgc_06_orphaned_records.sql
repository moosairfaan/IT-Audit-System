-- ITGC-06 Orphaned accounts and unknown users
--
-- Objective: Every application account and every change is tied to a person
-- on the HR roster.
-- Risk: An account or a change that names someone the roster does not list
-- cannot be attributed, reviewed, or removed when that person leaves.
-- Suggested action: Add the person to the HR roster, or remove the account
-- and hold the change until that person is recorded.
--
-- Population: accounts with no matching HR record, and changes made by
-- people not on the roster.
-- A null employee id is a shared or generic account (ITGC-05), not this test.
-- A blank approver is an unapproved change (ITGC-03), not an unknown person.
-- Exception: the account's employee id, or the change's requester, approver,
-- or deployer, is not on the HR roster.

SELECT
    (
        SELECT COUNT(*)
        FROM iam_accounts AS account
        WHERE account.employee_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM hr_roster AS employee
              WHERE employee.employee_id = account.employee_id
          )
    )
    +
    (
        SELECT COUNT(*)
        FROM change_tickets AS ticket
        WHERE NOT EXISTS (
                SELECT 1
                FROM hr_roster AS employee
                WHERE employee.employee_id = ticket.requested_by
              )
           OR (
                ticket.approved_by IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1
                    FROM hr_roster AS employee
                    WHERE employee.employee_id = ticket.approved_by
                )
              )
           OR NOT EXISTS (
                SELECT 1
                FROM hr_roster AS employee
                WHERE employee.employee_id = ticket.deployed_by
              )
    ) AS population_count;

SELECT
    account.account_id AS exception_id,
    'account' AS record_type,
    account.employee_id AS person_id,
    account.system,
    account.role,
    'employee is not on the HR roster' AS reason
FROM iam_accounts AS account
WHERE account.employee_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM hr_roster AS employee
      WHERE employee.employee_id = account.employee_id
  )
UNION ALL
SELECT
    ticket.ticket_id AS exception_id,
    'change' AS record_type,
    concat_ws(
        ', ',
        CASE
            WHEN NOT EXISTS (
                SELECT 1 FROM hr_roster AS employee
                WHERE employee.employee_id = ticket.requested_by
            ) THEN ticket.requested_by
        END,
        CASE
            WHEN ticket.approved_by IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM hr_roster AS employee
                WHERE employee.employee_id = ticket.approved_by
            ) THEN ticket.approved_by
        END,
        CASE
            WHEN NOT EXISTS (
                SELECT 1 FROM hr_roster AS employee
                WHERE employee.employee_id = ticket.deployed_by
            ) THEN ticket.deployed_by
        END
    ) AS person_id,
    ticket.system,
    NULL AS role,
    concat_ws(
        '; ',
        CASE
            WHEN NOT EXISTS (
                SELECT 1 FROM hr_roster AS employee
                WHERE employee.employee_id = ticket.requested_by
            ) THEN 'requester is not on the HR roster'
        END,
        CASE
            WHEN ticket.approved_by IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM hr_roster AS employee
                WHERE employee.employee_id = ticket.approved_by
            ) THEN 'approver is not on the HR roster'
        END,
        CASE
            WHEN NOT EXISTS (
                SELECT 1 FROM hr_roster AS employee
                WHERE employee.employee_id = ticket.deployed_by
            ) THEN 'deployer is not on the HR roster'
        END
    ) AS reason
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
ORDER BY exception_id;
