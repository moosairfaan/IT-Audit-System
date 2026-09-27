"""Build the broker-dealer population from a seeded random generator."""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone
from typing import Any

from data_gen.catalog import (
    AS_OF,
    BAD_CHANGE_COUNT,
    CHANGE_DESCRIPTIONS,
    DEPARTMENTS,
    DORMANT_COUNT,
    EMPLOYEE_COUNT,
    FIRST_NAMES,
    GOOD_CHANGE_COUNT,
    LAST_NAMES,
    ROLE_PERMISSIONS,
    SEED,
    SHARED_COUNT,
    SOD_ASSIGNMENTS,
    SOD_RULES,
    SYSTEMS,
    TERMINATED_ACTIVE_COUNT,
    TERMINATED_COUNT,
)
from data_gen.checks import detect

Row = dict[str, Any]


def generate(seed: int = SEED) -> tuple[dict[str, list[Row]], dict[str, list[str]]]:
    rng = random.Random(seed)
    roster = _roster(rng)
    accounts = _accounts(roster)
    terminated = {row["employee_id"] for row in roster if row["termination_date"] is not None}
    _add_sod_accounts(accounts, terminated)
    _mark_dormant(accounts, terminated)
    owner = next(row["employee_id"] for row in roster if row["termination_date"] is None)
    accounts.extend(_shared_accounts(len(accounts), owner))
    tables: dict[str, list[Row]] = {
        "hr_roster": roster,
        "role_permissions": _role_rows(),
        "sod_conflict_rules": _sod_rows(),
        "iam_accounts": accounts,
        "change_tickets": _changes(roster),
    }
    found = detect(tables, AS_OF)
    _require_exact(found)
    return tables, found


def _roster(rng: random.Random) -> list[Row]:
    names = [f"{first} {last}" for first in FIRST_NAMES for last in LAST_NAMES]
    if len(names) < EMPLOYEE_COUNT:
        raise RuntimeError("Not enough synthetic names for the roster")
    rng.shuffle(names)
    terminated = set(rng.sample(range(EMPLOYEE_COUNT), TERMINATED_COUNT))
    rows: list[Row] = []
    for index in range(EMPLOYEE_COUNT):
        department = DEPARTMENTS[index % len(DEPARTMENTS)]
        hire_date = date(2016, 1, 15) + timedelta(days=rng.randrange(0, 2800))
        termination = _termination(rng, hire_date) if index in terminated else None
        rows.append(
            {
                "employee_id": f"E{index + 1:04d}",
                "name": names[index],
                "department": department.name,
                "job_title": department.titles[index % 2],
                "hire_date": hire_date,
                "termination_date": termination,
            }
        )
    return rows


def _termination(rng: random.Random, hire_date: date) -> date:
    latest = date(2026, 8, 1)
    candidate = hire_date + timedelta(days=rng.randrange(200, 800))
    if candidate > latest:
        return latest
    return candidate


def _accounts(roster: list[Row]) -> list[Row]:
    terminated_active = {
        row["employee_id"]
        for row in roster
        if row["termination_date"] is not None
    }
    # The first accounts of the lowest-numbered terminated employees stay active.
    leave_active = set(sorted(terminated_active)[:TERMINATED_ACTIVE_COUNT])
    role_system = {role: system for role, system, _permission in ROLE_PERMISSIONS}
    rows: list[Row] = []
    for employee in roster:
        department = next(item for item in DEPARTMENTS if item.name == employee["department"])
        leaver = employee["termination_date"] is not None
        for role_index, role in enumerate(department.roles):
            keep_active = leaver and role_index == 0 and employee["employee_id"] in leave_active
            status = "disabled" if leaver and not keep_active else "active"
            rows.append(
                {
                    "account_id": f"A{len(rows) + 1:05d}",
                    "employee_id": employee["employee_id"],
                    "system": role_system[role],
                    "role": role,
                    "status": status,
                    "last_login": _login(employee, status),
                    "is_shared": False,
                }
            )
    return rows


def _login(employee: Row, status: str) -> datetime:
    if status == "disabled" and employee["termination_date"] is not None:
        day = employee["termination_date"] - timedelta(days=3)
    else:
        day = date(2026, 8, 1 + (int(employee["employee_id"][1:]) % 27))
    return datetime(day.year, day.month, day.day, 14, 0, tzinfo=timezone.utc)


def _add_sod_accounts(accounts: list[Row], terminated: set[str]) -> None:
    role_system = {role: system for role, system, _permission in ROLE_PERMISSIONS}
    for source_role, conflict_role, count in SOD_ASSIGNMENTS:
        chosen = _first_active_with_role(accounts, source_role, count, terminated)
        for account in chosen:
            accounts.append(
                {
                    "account_id": f"A{len(accounts) + 1:05d}",
                    "employee_id": account["employee_id"],
                    "system": role_system[conflict_role],
                    "role": conflict_role,
                    "status": "active",
                    "last_login": datetime(2026, 8, 20, 11, 0, tzinfo=timezone.utc),
                    "is_shared": False,
                }
            )


def _first_active_with_role(
    accounts: list[Row],
    role: str,
    count: int,
    terminated: set[str],
) -> list[Row]:
    chosen: list[Row] = []
    seen: set[str] = set()
    for account in accounts:
        employee_id = account["employee_id"]
        if account["role"] != role or account["status"] != "active" or not employee_id:
            continue
        if employee_id in terminated:
            continue
        if employee_id in seen:
            continue
        seen.add(employee_id)
        chosen.append(account)
        if len(chosen) == count:
            return chosen
    raise RuntimeError(f"Needed {count} active {role} accounts, found {len(chosen)}")


def _mark_dormant(accounts: list[Row], terminated: set[str]) -> None:
    conflicting = {added for _source, added, _count in SOD_ASSIGNMENTS}
    sod_holders = {
        account["employee_id"] for account in accounts if account["role"] in conflicting
    }
    eligible = [
        account
        for account in accounts
        if account["status"] == "active"
        and not account["is_shared"]
        and account["employee_id"] not in terminated
        and account["employee_id"] not in sod_holders
        and account["role"] not in conflicting
    ]
    if len(eligible) < DORMANT_COUNT:
        raise RuntimeError("Not enough accounts to mark dormant")
    stale = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
    for account in eligible[:DORMANT_COUNT]:
        account["last_login"] = stale


def _shared_accounts(existing: int, owner: str) -> list[Row]:
    templates = (
        ("trading platform", "trading_read"),
        ("general ledger", "gl_read"),
        ("payments", "payment_read"),
        ("core database", "dba_read"),
        ("HR system", "hr_viewer"),
    )
    rows: list[Row] = []
    for index, (system, role) in enumerate(templates[:SHARED_COUNT]):
        generic = index < 3
        rows.append(
            {
                "account_id": f"A{existing + index + 1:05d}",
                "employee_id": None if generic else owner,
                "system": system,
                "role": role,
                "status": "active",
                "last_login": datetime(2026, 8, 18, 8, 0, tzinfo=timezone.utc),
                "is_shared": True,
            }
        )
    return rows


def _role_rows() -> list[Row]:
    return [{"role": role, "permission": permission} for role, _system, permission in ROLE_PERMISSIONS]


def _sod_rows() -> list[Row]:
    return [
        {"permission_a": left, "permission_b": right, "description": description}
        for left, right, description in SOD_RULES
    ]


def _changes(roster: list[Row]) -> list[Row]:
    active = [row["employee_id"] for row in roster if row["termination_date"] is None]
    requesters = active[0:80]
    approvers = active[80:160]
    deployers = active[160:240]
    tickets = [_bad_ticket(index, requesters, approvers, deployers) for index in range(BAD_CHANGE_COUNT)]
    tickets.extend(_good_ticket(index, requesters, approvers, deployers) for index in range(GOOD_CHANGE_COUNT))
    if len({row["system"] for row in tickets} - set(SYSTEMS)) > 0:
        raise RuntimeError("A change ticket uses a system outside the catalog")
    return tickets


def _bad_ticket(
    index: int,
    requesters: list[str],
    approvers: list[str],
    deployers: list[str],
) -> Row:
    requested = requesters[index]
    approved = approvers[index]
    deployed = deployers[index]
    approved_at: datetime | None = datetime(2026, 8, 20, 15, 0, tzinfo=timezone.utc)
    deployed_at: datetime | None = datetime(2026, 8, 21, 15, 0, tzinfo=timezone.utc)
    approved_by: str | None = approved
    if index < 3:
        deployed_at = datetime(2026, 8, 18, 9, 0, tzinfo=timezone.utc)
    elif index < 6:
        approved_by = None
        approved_at = None
    elif index < 8:
        approved_by = requested
    else:
        approved_by = deployed
    return _ticket(index + 1, requested, approved_by, deployed, approved_at, deployed_at, index)


def _good_ticket(
    index: int,
    requesters: list[str],
    approvers: list[str],
    deployers: list[str],
) -> Row:
    approved_at = datetime(2026, 8, 4 + (index % 20), 10, 0, tzinfo=timezone.utc)
    return _ticket(
        BAD_CHANGE_COUNT + index + 1,
        requesters[20 + index],
        approvers[20 + index],
        deployers[20 + index],
        approved_at,
        approved_at + timedelta(hours=6),
        index,
    )


def _ticket(
    number: int,
    requested_by: str,
    approved_by: str | None,
    deployed_by: str,
    approved_at: datetime | None,
    deployed_at: datetime | None,
    description_index: int,
) -> Row:
    return {
        "ticket_id": f"CHG-{1000 + number}",
        "system": SYSTEMS[number % len(SYSTEMS)],
        "requested_by": requested_by,
        "approved_by": approved_by,
        "deployed_by": deployed_by,
        "approved_at": approved_at,
        "deployed_at": deployed_at,
        "description": CHANGE_DESCRIPTIONS[description_index % len(CHANGE_DESCRIPTIONS)],
    }


def _require_exact(found: dict[str, list[str]]) -> None:
    expected = {
        "ITGC-01": TERMINATED_ACTIVE_COUNT,
        "ITGC-02": sum(count for _source, _role, count in SOD_ASSIGNMENTS),
        "ITGC-03": BAD_CHANGE_COUNT,
        "ITGC-04": DORMANT_COUNT,
        "ITGC-05": SHARED_COUNT,
    }
    actual = {control: len(ids) for control, ids in found.items()}
    if actual != expected:
        raise RuntimeError(f"Exception counts {actual} did not match the injected counts {expected}")
