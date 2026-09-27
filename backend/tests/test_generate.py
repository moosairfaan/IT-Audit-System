"""The seeded population is reproducible and the exception lists are exact."""

from data_gen.catalog import (
    AS_OF,
    BAD_CHANGE_COUNT,
    DORMANT_COUNT,
    EMPLOYEE_COUNT,
    GOOD_CHANGE_COUNT,
    SHARED_COUNT,
    SOD_RULES,
    TERMINATED_ACTIVE_COUNT,
    TERMINATED_COUNT,
)
from data_gen.checks import detect
from data_gen.generate import generate


def test_generate_is_reproducible() -> None:
    first_tables, first_truth = generate()
    second_tables, second_truth = generate()
    assert first_tables == second_tables
    assert first_truth == second_truth


def test_population_shape_and_exception_counts() -> None:
    tables, truth = generate()
    roster = tables["hr_roster"]
    accounts = tables["iam_accounts"]
    assert len(roster) == EMPLOYEE_COUNT
    assert len(tables["role_permissions"]) == 15
    assert len(tables["sod_conflict_rules"]) == len(SOD_RULES)
    assert len(tables["change_tickets"]) == BAD_CHANGE_COUNT + GOOD_CHANGE_COUNT
    assert sum(1 for row in roster if row["termination_date"] is not None) == TERMINATED_COUNT
    assert len(accounts) == EMPLOYEE_COUNT * 2 + 6 + SHARED_COUNT
    assert [len(ids) for ids in truth.values()] == [
        TERMINATED_ACTIVE_COUNT,
        6,
        BAD_CHANGE_COUNT,
        DORMANT_COUNT,
        SHARED_COUNT,
    ]
    assert detect(tables, AS_OF) == truth


def test_systems_are_the_broker_dealer_stack() -> None:
    tables, _truth = generate()
    systems = {row["system"] for row in tables["iam_accounts"]}
    assert systems == {
        "trading platform",
        "general ledger",
        "payments",
        "HR system",
        "core database",
    }
