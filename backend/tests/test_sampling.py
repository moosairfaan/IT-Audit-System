"""A sample is reproducible, and risk-based selection puts higher-risk items first."""

from __future__ import annotations

from sqlalchemy.engine import Engine

from app.controls.runner import run_control
from app.sampling.service import create_sample, get_sample, load_population
from data_gen.generate import generate


def test_populations_match_the_control_definitions(database: Engine) -> None:
    tables, _truth = generate()
    terminated = {
        row["employee_id"] for row in tables["hr_roster"] if row["termination_date"] is not None
    }
    accounts = tables["iam_accounts"]
    active = [row for row in accounts if row["status"] == "active"]
    assert len(load_population(database, "ITGC-01")) == sum(
        1 for row in accounts if row["employee_id"] in terminated
    )
    assert len(load_population(database, "ITGC-02")) == len(tables["hr_roster"])
    assert len(load_population(database, "ITGC-03")) == len(tables["change_tickets"])
    assert len(load_population(database, "ITGC-04")) == len(active)
    assert len(load_population(database, "ITGC-05")) == len(active)


def test_same_seed_reproduces_the_sample_and_a_new_seed_does_not(database: Engine) -> None:
    run_control(database, "ITGC-04")
    first = create_sample(database, "ITGC-04", "random", 25, seed=11)
    second = create_sample(database, "ITGC-04", "random", 25, seed=11)
    other = create_sample(database, "ITGC-04", "random", 25, seed=99)
    assert first["selected_ids"] == second["selected_ids"]
    assert first["seed"] == second["seed"] == 11
    assert first["sample_id"] != second["sample_id"]
    assert other["selected_ids"] != first["selected_ids"]
    stored = get_sample(database, first["sample_id"])
    assert stored["selected_ids"] == first["selected_ids"]
    assert stored["run_id"] == first["run_id"]


def test_risk_based_sample_puts_privileged_and_critical_items_first(database: Engine) -> None:
    run_control(database, "ITGC-04")
    items = load_population(database, "ITGC-04")
    priority = {item.item_id for item in items if item.priority}
    assert priority
    sample_size = len(priority) + 5
    assert sample_size < len(items)
    selected = create_sample(database, "ITGC-04", "risk_based", sample_size, seed=5)["selected_ids"]
    assert set(selected[: len(priority)]) == priority
    assert set(selected[len(priority) :]).isdisjoint(priority)
