"""Dashboard severity follows the control, not a label on the stored row."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.engine import Engine

from app.audit_context import ensure_audit_context
from app.controls.catalog import CONTROLS
from app.controls.runner import run_control
from app.controls.severity import severity_for
from app.controls.store import ensure_test_runs
from app.overview import build_overview, dataset_counts
from app.sampling.service import ensure_samples
from app.schema_guard import reset_for_tests
from app.workpapers.service import ensure_workpapers


def test_severity_counts_match_the_rules(database: Engine) -> None:
    for control_id in CONTROLS:
        run_control(database, control_id)
    summary = build_overview(database)
    assert summary["controls_tested"] == 6
    assert summary["control_count"] == 6
    assert summary["total_exceptions"] == 35
    assert summary["exceptions_by_severity"] == {"high": 11, "medium": 13, "low": 11}
    by_control = {row["control_id"]: row["exception_count"] for row in summary["exceptions_by_control"]}
    assert by_control == {
        "ITGC-01": 8,
        "ITGC-02": 6,
        "ITGC-03": 10,
        "ITGC-04": 6,
        "ITGC-05": 5,
        "ITGC-06": 0,
    }


def test_payments_and_ledger_conflicts_are_high() -> None:
    assert severity_for("ITGC-01", {}) == "high"
    assert severity_for("ITGC-02", {"conflicting_pairs": "create_payment + approve_payment"}) == "high"
    assert severity_for("ITGC-02", {"conflicting_pairs": "create_journal + approve_journal"}) == "high"
    assert severity_for("ITGC-02", {"conflicting_pairs": "submit_trade + approve_trade"}) == "medium"
    assert severity_for("ITGC-03", {"system": "payments"}) == "medium"
    assert severity_for("ITGC-04", {}) == "low"
    assert severity_for("ITGC-05", {}) == "low"
    assert severity_for("ITGC-06", {}) == "high"


def test_concurrent_page_loads_do_not_deadlock_on_schema_setup(database: Engine) -> None:
    reset_for_tests()

    def load_once(_: int) -> None:
        ensure_test_runs(database)
        ensure_samples(database)
        ensure_workpapers(database)
        ensure_audit_context(database)
        build_overview(database)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(load_once, range(8)))


def test_dataset_counts_match_the_seeded_population(database: Engine) -> None:
    counts = {row["dataset"]: row["rows"] for row in dataset_counts(database)}
    assert counts == {
        "hr_roster": 400,
        "role_permissions": 15,
        "sod_conflict_rules": 5,
        "iam_accounts": 811,
        "change_tickets": 50,
    }
