-- ITGC-02 Segregation of duties
--
-- Objective: No one person holds both permissions in a conflicting pair.
-- Risk: A user who can both create and approve the same transaction, trade,
-- access request, or change can bypass a second-person check.
--
-- Population: employees who have at least one application account.
-- Permissions come from the account role joined to role_permissions.
-- Exception: the employee holds both permission_a and permission_b from any
-- row in sod_conflict_rules. One employee is one exception, even if several
-- pairs match. conflicting_pairs lists each pair.

SELECT COUNT(DISTINCT account.employee_id) AS population_count
FROM iam_accounts AS account
WHERE account.employee_id IS NOT NULL;

WITH employee_permission AS (
    SELECT DISTINCT account.employee_id, permission.permission
    FROM iam_accounts AS account
    JOIN role_permissions AS permission ON permission.role = account.role
    WHERE account.employee_id IS NOT NULL
)
SELECT
    held.employee_id AS exception_id,
    employee.name,
    string_agg(
        DISTINCT rule.permission_a || ' + ' || rule.permission_b,
        ', '
        ORDER BY rule.permission_a || ' + ' || rule.permission_b
    ) AS conflicting_pairs
FROM employee_permission AS held
JOIN sod_conflict_rules AS rule
    ON EXISTS (
        SELECT 1
        FROM employee_permission AS other
        WHERE other.employee_id = held.employee_id
          AND other.permission = rule.permission_a
    )
   AND EXISTS (
        SELECT 1
        FROM employee_permission AS other
        WHERE other.employee_id = held.employee_id
          AND other.permission = rule.permission_b
    )
JOIN hr_roster AS employee ON employee.employee_id = held.employee_id
GROUP BY held.employee_id, employee.name
ORDER BY held.employee_id;
