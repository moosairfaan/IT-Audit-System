"""Persist and reload control-test runs."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import Engine, text

_CREATE_TEST_RUNS = """
CREATE TABLE IF NOT EXISTS test_runs (
    run_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    control_id TEXT NOT NULL,
    name TEXT NOT NULL,
    objective TEXT NOT NULL,
    risk_addressed TEXT NOT NULL,
    population_count INTEGER NOT NULL,
    exception_count INTEGER NOT NULL,
    exceptions JSONB NOT NULL,
    run_at TIMESTAMPTZ NOT NULL
)
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS test_runs_control_id_idx ON test_runs (control_id, run_id DESC)
"""


def ensure_test_runs(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text(_CREATE_TEST_RUNS))
        connection.execute(text(_CREATE_INDEX))


def save_run(engine: Engine, result: dict[str, Any]) -> int:
    statement = text(
        """
        INSERT INTO test_runs (
            control_id, name, objective, risk_addressed,
            population_count, exception_count, exceptions, run_at
        )
        VALUES (
            :control_id, :name, :objective, :risk_addressed,
            :population_count, :exception_count, CAST(:exceptions AS jsonb), :run_at
        )
        RETURNING run_id
        """
    )
    with engine.begin() as connection:
        run_id = connection.execute(
            statement,
            {
                "control_id": result["control_id"],
                "name": result["name"],
                "objective": result["objective"],
                "risk_addressed": result["risk_addressed"],
                "population_count": result["population_count"],
                "exception_count": result["exception_count"],
                "exceptions": _json(result["exceptions"]),
                "run_at": result["run_at"],
            },
        ).scalar_one()
    return int(run_id)


def latest_runs(engine: Engine) -> list[dict[str, Any]]:
    statement = text(
        """
        SELECT DISTINCT ON (control_id)
            run_id, control_id, name, objective, risk_addressed,
            population_count, exception_count, exceptions, run_at
        FROM test_runs
        ORDER BY control_id, run_id DESC
        """
    )
    with engine.connect() as connection:
        rows = connection.execute(statement).mappings().all()
    return [_present(row) for row in rows]


def get_run(engine: Engine, control_id: str, run_id: int) -> dict[str, Any] | None:
    statement = text(
        """
        SELECT
            run_id, control_id, name, objective, risk_addressed,
            population_count, exception_count, exceptions, run_at
        FROM test_runs
        WHERE control_id = :control_id AND run_id = :run_id
        """
    )
    with engine.connect() as connection:
        row = connection.execute(
            statement, {"control_id": control_id, "run_id": run_id}
        ).mappings().first()
    if row is None:
        return None
    return _present(row)


def _present(row: Any) -> dict[str, Any]:
    body = dict(row)
    body["run_at"] = _iso(body["run_at"])
    body["exceptions"] = body["exceptions"] or []
    return body


def _iso(value: datetime) -> str:
    return value.isoformat()


def _json(exceptions: list[dict[str, Any]]) -> str:
    return json.dumps(exceptions)
