"""Detect the injected exceptions. The generator refuses to emit a population these rules do not explain."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from data_gen.catalog import (
    DORMANT_DAYS,
    ITGC_CHANGE,
    ITGC_DORMANT,
    ITGC_SHARED,
    ITGC_SOD,
    ITGC_TERMINATED_ACTIVE,
)


def detect(tables: dict[str, list[dict[str, Any]]], as_of: date) -> dict[str, list[str]]:
    permissions = _permissions_by_role(tables["role_permissions"])
    return {
        ITGC_TERMINATED_ACTIVE: terminated_active_ids(tables["hr_roster"], tables["iam_accounts"]),
        ITGC_SOD: sod_employee_ids(tables["iam_accounts"], permissions, tables["sod_conflict_rules"]),
        ITGC_CHANGE: improper_change_ids(tables["change_tickets"]),
        ITGC_DORMANT: dormant_account_ids(tables["iam_accounts"], as_of),
        ITGC_SHARED: shared_account_ids(tables["iam_accounts"]),
    }


def terminated_active_ids(
    roster: list[dict[str, Any]],
    accounts: list[dict[str, Any]],
) -> list[str]:
    terminated = {
        row["employee_id"]
        for row in roster
        if row["termination_date"] is not None
    }
    return sorted(
        row["account_id"]
        for row in accounts
        if row["status"] == "active" and row["employee_id"] in terminated
    )


def sod_employee_ids(
    accounts: list[dict[str, Any]],
    permissions_by_role: dict[str, set[str]],
    rules: list[dict[str, Any]],
) -> list[str]:
    held: dict[str, set[str]] = {}
    for account in accounts:
        employee_id = account["employee_id"]
        if not employee_id:
            continue
        held.setdefault(employee_id, set()).update(permissions_by_role.get(account["role"], set()))
    found: list[str] = []
    for employee_id, permissions in held.items():
        if _holds_conflict(permissions, rules):
            found.append(employee_id)
    return sorted(found)


def improper_change_ids(tickets: list[dict[str, Any]]) -> list[str]:
    return sorted(row["ticket_id"] for row in tickets if improper_change(row))


def improper_change(ticket: dict[str, Any]) -> bool:
    """A deployed change is an exception when approval is missing, late, or not independent."""
    if ticket["deployed_at"] is None:
        return False
    if ticket["approved_at"] is None or ticket["approved_by"] is None:
        return True
    if ticket["deployed_at"] < ticket["approved_at"]:
        return True
    if ticket["approved_by"] == ticket["requested_by"]:
        return True
    return ticket["approved_by"] == ticket["deployed_by"]


def dormant_account_ids(accounts: list[dict[str, Any]], as_of: date) -> list[str]:
    cutoff = datetime(as_of.year, as_of.month, as_of.day, tzinfo=timezone.utc) - timedelta(days=DORMANT_DAYS)
    found: list[str] = []
    for account in accounts:
        if account["status"] != "active" or account["is_shared"]:
            continue
        last_login = account["last_login"]
        if last_login is None or last_login <= cutoff:
            found.append(account["account_id"])
    return sorted(found)


def shared_account_ids(accounts: list[dict[str, Any]]) -> list[str]:
    return sorted(row["account_id"] for row in accounts if row["is_shared"])


def _permissions_by_role(rows: list[dict[str, Any]]) -> dict[str, set[str]]:
    grouped: dict[str, set[str]] = {}
    for row in rows:
        grouped.setdefault(row["role"], set()).add(row["permission"])
    return grouped


def _holds_conflict(permissions: set[str], rules: list[dict[str, Any]]) -> bool:
    return any(
        rule["permission_a"] in permissions and rule["permission_b"] in permissions for rule in rules
    )
