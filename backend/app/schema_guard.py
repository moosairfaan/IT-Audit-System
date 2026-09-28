"""Run schema setup once per process.

Page loads call these helpers together. Repeating ALTER TABLE on every request
takes an exclusive lock, and two of those locks deadlock.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from sqlalchemy import Connection, text

_lock = threading.RLock()
_done: set[str] = set()


def run_once(name: str, apply: Callable[[], None]) -> None:
    if name in _done:
        return
    with _lock:
        if name in _done:
            return
        apply()
        _done.add(name)


def add_column_if_missing(connection: Connection, table: str, column: str, definition: str) -> None:
    found = connection.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = :table
              AND column_name = :column
            """
        ),
        {"table": table, "column": column},
    ).first()
    if found is not None:
        return
    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))


def reset_for_tests() -> None:
    with _lock:
        _done.clear()
