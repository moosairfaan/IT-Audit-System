"""Parse a dataset CSV and replace the rows in its table."""

from __future__ import annotations

import io
from datetime import date, datetime
from typing import Any

import pandas as pd
from sqlalchemy import Engine, Table, delete, insert, text
from sqlalchemy.exc import IntegrityError

from app.datasets import Column, columns_for
from app.models import Base

_TRUE = {"true", "t", "1", "yes"}
_FALSE = {"false", "f", "0", "no"}


class LoadError(ValueError):
    """The CSV does not match the dataset contract."""


def rows_to_csv(dataset: str, rows: list[dict[str, Any]]) -> str:
    columns = columns_for(dataset)
    frame = pd.DataFrame(
        [{column.name: _format(row.get(column.name), column) for column in columns} for row in rows],
        columns=[column.name for column in columns],
    )
    return frame.to_csv(index=False, lineterminator="\n")


def parse_csv(dataset: str, csv_text: str) -> list[dict[str, Any]]:
    expected = columns_for(dataset)
    frame = _read_frame(csv_text)
    _check_header(dataset, frame, expected)
    parsed: list[dict[str, Any]] = []
    for offset, record in enumerate(frame.to_dict(orient="records"), start=2):
        parsed.append(_parse_row(dataset, offset, record, expected))
    return parsed


def replace_dataset(engine: Engine, dataset: str, csv_text: str) -> int:
    rows = parse_csv(dataset, csv_text)
    table = _table(dataset)
    try:
        with engine.begin() as connection:
            connection.execute(delete(table))
            if rows:
                connection.execute(insert(table), rows)
    except IntegrityError as exc:
        raise LoadError(
            f"Could not load {dataset}. Load parent tables first, or reload the database."
        ) from exc
    return len(rows)


def apply_schema(engine: Engine, sql: str) -> None:
    with engine.begin() as connection:
        for statement in sql_statements(sql):
            connection.execute(text(statement))


def count_rows(engine: Engine, dataset: str) -> int:
    table = _table(dataset)
    with engine.connect() as connection:
        count = connection.execute(text(f"SELECT COUNT(*) FROM {table.name}")).scalar_one()
    return int(count)


def _table(dataset: str) -> Table:
    columns_for(dataset)
    return Base.metadata.tables[dataset]


def _read_frame(csv_text: str) -> pd.DataFrame:
    if not csv_text.strip():
        raise LoadError("CSV body is empty")
    try:
        return pd.read_csv(io.StringIO(csv_text), dtype=str, keep_default_na=False)
    except pd.errors.ParserError as exc:
        raise LoadError(f"CSV could not be parsed: {exc}") from exc


def _check_header(dataset: str, frame: pd.DataFrame, expected: tuple[Column, ...]) -> None:
    actual = [str(name) for name in frame.columns]
    names = [column.name for column in expected]
    if actual != names:
        raise LoadError(f"{dataset} columns must be {', '.join(names)}")


def _parse_row(
    dataset: str,
    line_number: int,
    record: dict[str, Any],
    expected: tuple[Column, ...],
) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for column in expected:
        raw = str(record[column.name]).strip()
        if raw == "":
            if not column.nullable:
                raise LoadError(f"{dataset} line {line_number}: {column.name} is required")
            parsed[column.name] = None
            continue
        parsed[column.name] = _parse_value(dataset, line_number, column, raw)
    return parsed


def _parse_value(dataset: str, line_number: int, column: Column, raw: str) -> Any:
    try:
        if column.kind == "date":
            return date.fromisoformat(raw)
        if column.kind == "datetime":
            return datetime.fromisoformat(raw)
        if column.kind == "bool":
            return _parse_bool(raw)
    except ValueError as exc:
        raise LoadError(
            f"{dataset} line {line_number}: {column.name} has an invalid {column.kind}"
        ) from exc
    if column.name == "status" and raw not in {"active", "disabled"}:
        raise LoadError(f"{dataset} line {line_number}: status must be active or disabled")
    return raw


def _parse_bool(raw: str) -> bool:
    token = raw.lower()
    if token in _TRUE:
        return True
    if token in _FALSE:
        return False
    raise ValueError(raw)


def _format(value: Any, column: Column) -> str:
    if value is None:
        return ""
    if column.kind == "bool":
        return "true" if value else "false"
    if column.kind in {"date", "datetime"}:
        return value.isoformat()
    return str(value)


def sql_statements(sql: str) -> list[str]:
    code = "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))
    statements: list[str] = []
    current: list[str] = []
    in_string = False
    index = 0
    while index < len(code):
        char = code[index]
        if char == "'":
            if in_string and index + 1 < len(code) and code[index + 1] == "'":
                current.append("''")
                index += 2
                continue
            in_string = not in_string
            current.append(char)
        elif char == ";" and not in_string:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        else:
            current.append(char)
        index += 1
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements
