"""Run one control SQL file and store the result."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import Engine, text

from app.controls.catalog import CONTROLS, UnknownControl
from app.controls.store import ensure_test_runs, get_run, latest_runs, save_run
from app.load import sql_statements
from data_gen.catalog import AS_OF


def run_control(engine: Engine, control_id: str, as_of: date = AS_OF) -> dict[str, Any]:
    control = _control(control_id)
    population_sql, exception_sql = _queries(control.sql_path.read_text(encoding="utf-8"))
    params = {"as_of": as_of} if control.uses_as_of else {}
    ensure_test_runs(engine)
    with engine.connect() as connection:
        population_count = int(connection.execute(text(population_sql), params).scalar_one())
        rows = connection.execute(text(exception_sql), params).mappings().all()
    exceptions = [_jsonable(dict(row)) for row in rows]
    result = {
        "control_id": control.control_id,
        "name": control.name,
        "objective": control.objective,
        "risk_addressed": control.risk_addressed,
        "population_count": population_count,
        "exception_count": len(exceptions),
        "exceptions": exceptions,
        "run_at": datetime.now(timezone.utc),
    }
    result["run_id"] = save_run(engine, result)
    result["run_at"] = result["run_at"].isoformat()
    return result


def list_latest(engine: Engine) -> list[dict[str, Any]]:
    ensure_test_runs(engine)
    return latest_runs(engine)


def fetch_run(engine: Engine, control_id: str, run_id: int) -> dict[str, Any]:
    _control(control_id)
    ensure_test_runs(engine)
    found = get_run(engine, control_id, run_id)
    if found is None:
        raise UnknownControl(f"Unknown run {run_id} for {control_id}")
    return found


def _control(control_id: str) -> Any:
    try:
        return CONTROLS[control_id]
    except KeyError as exc:
        known = ", ".join(CONTROLS)
        raise UnknownControl(f"Unknown control {control_id}. Expected one of: {known}") from exc


def _queries(sql: str) -> tuple[str, str]:
    statements = sql_statements(sql)
    if len(statements) != 2:
        raise RuntimeError("A control file must contain a population query and an exception query")
    return statements[0], statements[1]


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value
