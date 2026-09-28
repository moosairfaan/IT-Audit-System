"""Dashboard totals. Severity is counted from the latest run of each control."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Engine, text

from app.controls.catalog import CONTROLS
from app.controls.runner import list_latest
from app.datasets import DATASETS
from app.workpapers.sections import STATUSES
from app.workpapers.service import list_workpapers


def build_overview(engine: Engine) -> dict[str, Any]:
    runs = {str(run["control_id"]): run for run in list_latest(engine)}
    by_control: list[dict[str, Any]] = []
    by_severity = {severity: 0 for severity in ("high", "medium", "low")}
    total = 0
    for control in CONTROLS.values():
        run = runs.get(control.control_id)
        count = int(run["exception_count"]) if run else 0
        total += count
        by_control.append(
            {
                "control_id": control.control_id,
                "name": control.name,
                "exception_count": count,
                "run_id": None if run is None else run["run_id"],
                "dataset": None if run is None else run.get("dataset"),
                "dataset_label": None if run is None else run.get("dataset_label"),
            }
        )
        if run is None:
            continue
        for row in run["exceptions"]:
            by_severity[str(row["severity"])] += 1
    papers = list_workpapers(engine)
    by_status = {status: 0 for status in STATUSES}
    for paper in papers:
        by_status[str(paper["status"])] += 1
    return {
        "controls_tested": len(runs),
        "control_count": len(CONTROLS),
        "total_exceptions": total,
        "workpapers_by_status": by_status,
        "exceptions_by_control": by_control,
        "exceptions_by_severity": by_severity,
        "workpapers": papers,
    }


def dataset_counts(engine: Engine) -> list[dict[str, Any]]:
    counts: list[dict[str, Any]] = []
    with engine.connect() as connection:
        for dataset in DATASETS:
            rows = connection.execute(text(f"SELECT COUNT(*) FROM {dataset}")).scalar_one()
            counts.append({"dataset": dataset, "rows": int(rows)})
    return counts
