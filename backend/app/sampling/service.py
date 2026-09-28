"""Load a control population, draw a sample, and store it."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, text

from app.controls.catalog import CONTROLS, UnknownControl
from app.controls.store import ensure_test_runs
from app.load import sql_statements
from app.sampling.priority import is_priority
from app.sampling.select import METHODS, PopulationItem, SamplingError, choose, new_seed

SQL_DIR = Path(__file__).resolve().parents[2] / "sql"
POPULATION_FILES = {
    "ITGC-01": "itgc_01_population.sql",
    "ITGC-02": "itgc_02_population.sql",
    "ITGC-03": "itgc_03_population.sql",
    "ITGC-04": "itgc_04_population.sql",
    "ITGC-05": "itgc_05_population.sql",
}

_CREATE_SAMPLES = """
CREATE TABLE IF NOT EXISTS samples (
    sample_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    control_id TEXT NOT NULL,
    run_id INTEGER NOT NULL REFERENCES test_runs (run_id),
    method TEXT NOT NULL,
    seed BIGINT NOT NULL,
    population_size INTEGER NOT NULL,
    sample_size INTEGER NOT NULL,
    selected_ids JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CHECK (method IN ('random', 'risk_based')),
    CHECK (sample_size > 0)
)
"""


class RunRequired(LookupError):
    """Sampling needs a stored test run for the control."""


class SampleNotFound(LookupError):
    """No sample has that id."""


def create_sample(
    engine: Engine,
    control_id: str,
    method: str,
    sample_size: int,
    seed: int | None = None,
) -> dict[str, Any]:
    if method not in METHODS:
        raise SamplingError("method must be random or risk_based")
    _known_control(control_id)
    items = load_population(engine, control_id)
    chosen_seed = new_seed() if seed is None else seed
    selected = choose(items, method, sample_size, chosen_seed)
    run_id = _latest_run_id(engine, control_id)
    if run_id is None:
        raise RunRequired(f"Run {control_id} before selecting a sample")
    created_at = datetime.now(timezone.utc)
    sample_id = _insert(
        engine,
        {
            "control_id": control_id,
            "run_id": run_id,
            "method": method,
            "seed": chosen_seed,
            "population_size": len(items),
            "sample_size": sample_size,
            "selected_ids": selected,
            "created_at": created_at,
        },
    )
    return _row(sample_id, control_id, run_id, method, chosen_seed, len(items), sample_size, selected, created_at)


def latest_sample(engine: Engine, control_id: str) -> dict[str, Any]:
    _known_control(control_id)
    ensure_samples(engine)
    statement = text(
        """
        SELECT sample_id, control_id, run_id, method, seed, population_size,
               sample_size, selected_ids, created_at
        FROM samples
        WHERE control_id = :control_id
        ORDER BY sample_id DESC
        LIMIT 1
        """
    )
    with engine.connect() as connection:
        row = connection.execute(statement, {"control_id": control_id}).mappings().first()
    if row is None:
        raise SampleNotFound(f"No sample has been drawn for {control_id}")
    body = dict(row)
    body["created_at"] = body["created_at"].isoformat()
    body["selected_ids"] = list(body["selected_ids"])
    return body


def get_sample(engine: Engine, sample_id: int) -> dict[str, Any]:
    ensure_samples(engine)
    statement = text(
        """
        SELECT sample_id, control_id, run_id, method, seed, population_size,
               sample_size, selected_ids, created_at
        FROM samples
        WHERE sample_id = :sample_id
        """
    )
    with engine.connect() as connection:
        row = connection.execute(statement, {"sample_id": sample_id}).mappings().first()
    if row is None:
        raise SampleNotFound(f"Unknown sample {sample_id}")
    body = dict(row)
    body["created_at"] = body["created_at"].isoformat()
    body["selected_ids"] = list(body["selected_ids"])
    return body


def load_population(engine: Engine, control_id: str) -> list[PopulationItem]:
    _known_control(control_id)
    sql = (SQL_DIR / POPULATION_FILES[control_id]).read_text(encoding="utf-8")
    statements = sql_statements(sql)
    if len(statements) != 1:
        raise RuntimeError(f"{control_id} population file must contain one query")
    with engine.connect() as connection:
        rows = connection.execute(text(statements[0])).mappings().all()
    priority_by_id: dict[str, bool] = {}
    order: list[str] = []
    for row in rows:
        item_id = str(row["item_id"])
        if item_id not in priority_by_id:
            priority_by_id[item_id] = False
            order.append(item_id)
        if is_priority(row["role"], row["system"]):
            priority_by_id[item_id] = True
    return [PopulationItem(item_id, priority_by_id[item_id]) for item_id in order]


def ensure_samples(engine: Engine) -> None:
    ensure_test_runs(engine)
    with engine.begin() as connection:
        connection.execute(text(_CREATE_SAMPLES))


def _latest_run_id(engine: Engine, control_id: str) -> int | None:
    ensure_test_runs(engine)
    statement = text(
        """
        SELECT run_id
        FROM test_runs
        WHERE control_id = :control_id
        ORDER BY run_id DESC
        LIMIT 1
        """
    )
    with engine.connect() as connection:
        run_id = connection.execute(statement, {"control_id": control_id}).scalar()
    if run_id is None:
        return None
    return int(run_id)


def _insert(engine: Engine, row: dict[str, Any]) -> int:
    ensure_samples(engine)
    statement = text(
        """
        INSERT INTO samples (
            control_id, run_id, method, seed, population_size,
            sample_size, selected_ids, created_at
        )
        VALUES (
            :control_id, :run_id, :method, :seed, :population_size,
            :sample_size, CAST(:selected_ids AS jsonb), :created_at
        )
        RETURNING sample_id
        """
    )
    parameters = dict(row)
    parameters["selected_ids"] = json.dumps(row["selected_ids"])
    with engine.begin() as connection:
        sample_id = connection.execute(statement, parameters).scalar_one()
    return int(sample_id)


def _known_control(control_id: str) -> None:
    if control_id not in CONTROLS:
        known = ", ".join(CONTROLS)
        raise UnknownControl(f"Unknown control {control_id}. Expected one of: {known}")


def _row(
    sample_id: int,
    control_id: str,
    run_id: int,
    method: str,
    seed: int,
    population_size: int,
    sample_size: int,
    selected_ids: list[str],
    created_at: datetime,
) -> dict[str, Any]:
    return {
        "sample_id": sample_id,
        "control_id": control_id,
        "run_id": run_id,
        "method": method,
        "seed": seed,
        "population_size": population_size,
        "sample_size": sample_size,
        "selected_ids": selected_ids,
        "created_at": created_at.isoformat(),
    }
