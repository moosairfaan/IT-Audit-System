"""CSV contracts for each uploaded dataset."""

from __future__ import annotations

from dataclasses import dataclass


HR_ROSTER = "hr_roster"
IAM_ACCOUNTS = "iam_accounts"
ROLE_PERMISSIONS = "role_permissions"
CHANGE_TICKETS = "change_tickets"
SOD_CONFLICT_RULES = "sod_conflict_rules"

DATASETS: tuple[str, ...] = (
    HR_ROSTER,
    ROLE_PERMISSIONS,
    SOD_CONFLICT_RULES,
    IAM_ACCOUNTS,
    CHANGE_TICKETS,
)


@dataclass(frozen=True, slots=True)
class Column:
    name: str
    kind: str
    nullable: bool


def columns_for(dataset: str) -> tuple[Column, ...]:
    try:
        return _COLUMNS[dataset]
    except KeyError as exc:
        known = ", ".join(DATASETS)
        raise KeyError(f"Unknown dataset {dataset}. Expected one of: {known}") from exc


_COLUMNS: dict[str, tuple[Column, ...]] = {
    HR_ROSTER: (
        Column("employee_id", "str", False),
        Column("name", "str", False),
        Column("department", "str", False),
        Column("job_title", "str", False),
        Column("hire_date", "date", False),
        Column("termination_date", "date", True),
    ),
    IAM_ACCOUNTS: (
        Column("account_id", "str", False),
        Column("employee_id", "str", True),
        Column("system", "str", False),
        Column("role", "str", False),
        Column("status", "str", False),
        Column("last_login", "datetime", True),
        Column("is_shared", "bool", False),
    ),
    ROLE_PERMISSIONS: (
        Column("role", "str", False),
        Column("permission", "str", False),
    ),
    CHANGE_TICKETS: (
        Column("ticket_id", "str", False),
        Column("system", "str", False),
        Column("requested_by", "str", False),
        Column("approved_by", "str", True),
        Column("deployed_by", "str", False),
        Column("approved_at", "datetime", True),
        Column("deployed_at", "datetime", True),
        Column("description", "str", False),
    ),
    SOD_CONFLICT_RULES: (
        Column("permission_a", "str", False),
        Column("permission_b", "str", False),
        Column("description", "str", False),
    ),
}
