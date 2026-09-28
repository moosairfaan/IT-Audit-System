"""How many records each control tested, and why the rest were left out.

The counts are separate from the exception query. records_tested is the
population the control SQL already counted.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Engine, text

from app.controls.catalog import CONTROLS


def completeness_for(engine: Engine, control_id: str, tested: int) -> dict[str, Any]:
    loaded, exclusions = _breakdown(engine, control_id)
    explained = sum(int(item["count"]) for item in exclusions)
    excluded = loaded - tested
    if excluded > explained:
        exclusions.append({"reason": "another population rule", "count": excluded - explained})
    return {
        "records_loaded": loaded,
        "records_tested": tested,
        "records_excluded": excluded,
        "exclusions": [item for item in exclusions if int(item["count"]) > 0],
    }


def completeness_report(engine: Engine) -> list[dict[str, Any]]:
    """Population coverage for the tables loaded now, before or after a run."""
    from app.controls.runner import _queries

    report: list[dict[str, Any]] = []
    with engine.connect() as connection:
        for control in CONTROLS.values():
            population_sql, _exception_sql = _queries(control.sql_path.read_text(encoding="utf-8"))
            params: dict[str, object] = {}
            if ":dormant_days" in population_sql:
                params["dormant_days"] = _dormant_days(connection)
            tested = int(connection.execute(text(population_sql), params).scalar_one())
            item = completeness_for(engine, control.control_id, tested)
            item["control_id"] = control.control_id
            item["name"] = control.name
            report.append(item)
    return report


def _breakdown(engine: Engine, control_id: str) -> tuple[int, list[dict[str, Any]]]:
    statement, columns = _SQL[control_id]
    with engine.connect() as connection:
        row = connection.execute(text(statement)).mappings().one()
    loaded = int(row["loaded"])
    exclusions = [{"reason": reason, "count": int(row[column])} for reason, column in columns]
    return loaded, exclusions


def _dormant_days(connection: Any) -> int:
    value = connection.execute(text("SELECT dormant_days FROM audit_context WHERE id = 1")).scalar()
    if value is None:
        return 90
    return int(value)


_SQL: dict[str, tuple[str, tuple[tuple[str, str], ...]]] = {
    "ITGC-01": (
        """
        SELECT
            COUNT(*) AS loaded,
            COUNT(*) FILTER (WHERE account.employee_id IS NULL) AS unlinked,
            COUNT(*) FILTER (
                WHERE account.employee_id IS NOT NULL AND employee.termination_date IS NULL
            ) AS employed
        FROM iam_accounts AS account
        LEFT JOIN hr_roster AS employee ON employee.employee_id = account.employee_id
        """,
        (
            ("the account is not linked to an employee", "unlinked"),
            ("the employee has no termination date", "employed"),
        ),
    ),
    "ITGC-02": (
        """
        SELECT
            (SELECT COUNT(*) FROM hr_roster) AS loaded,
            (
                SELECT COUNT(*)
                FROM hr_roster AS employee
                WHERE NOT EXISTS (
                    SELECT 1 FROM iam_accounts AS account
                    WHERE account.employee_id = employee.employee_id
                )
            ) AS no_account
        """,
        (("the employee has no application account", "no_account"),),
    ),
    "ITGC-03": (
        """
        SELECT
            COUNT(*) AS loaded,
            COUNT(*) FILTER (WHERE deployed_at IS NULL) AS not_deployed
        FROM change_tickets
        """,
        (("the ticket has not been deployed", "not_deployed"),),
    ),
    "ITGC-04": (
        """
        SELECT
            COUNT(*) AS loaded,
            COUNT(*) FILTER (WHERE status = 'disabled') AS disabled,
            COUNT(*) FILTER (WHERE status = 'active' AND is_shared) AS shared
        FROM iam_accounts
        """,
        (
            ("the account is disabled", "disabled"),
            ("the account is shared", "shared"),
        ),
    ),
    "ITGC-05": (
        """
        SELECT
            COUNT(*) AS loaded,
            COUNT(*) FILTER (WHERE status = 'disabled') AS disabled
        FROM iam_accounts
        """,
        (("the account is disabled", "disabled"),),
    ),
    "ITGC-06": (
        """
        SELECT
            (SELECT COUNT(*) FROM iam_accounts) + (SELECT COUNT(*) FROM change_tickets) AS loaded,
            (
                SELECT COUNT(*)
                FROM iam_accounts AS account
                WHERE account.employee_id IS NOT NULL
                  AND EXISTS (
                      SELECT 1 FROM hr_roster AS employee
                      WHERE employee.employee_id = account.employee_id
                  )
            ) AS on_roster,
            (SELECT COUNT(*) FROM iam_accounts WHERE employee_id IS NULL) AS no_employee,
            (
                SELECT COUNT(*)
                FROM change_tickets AS ticket
                WHERE EXISTS (
                        SELECT 1 FROM hr_roster AS employee
                        WHERE employee.employee_id = ticket.requested_by
                      )
                  AND (
                        ticket.approved_by IS NULL
                        OR EXISTS (
                            SELECT 1 FROM hr_roster AS employee
                            WHERE employee.employee_id = ticket.approved_by
                        )
                      )
                  AND EXISTS (
                        SELECT 1 FROM hr_roster AS employee
                        WHERE employee.employee_id = ticket.deployed_by
                      )
            ) AS known_change
        """,
        (
            ("the employee is on the HR roster", "on_roster"),
            ("the account has no employee id", "no_employee"),
            ("the change names only people on the HR roster", "known_change"),
        ),
    ),
}
