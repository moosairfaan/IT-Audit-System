"""Postgres loaded with the synthetic broker-dealer for control and sample tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from app.config import load_settings
from app.datasets import DATASETS
from app.load import apply_schema, replace_dataset, rows_to_csv
from data_gen.generate import generate

SCHEMA = Path(__file__).resolve().parents[1] / "sql" / "schema.sql"


@pytest.fixture(scope="session")
def database() -> Engine:
    engine = create_engine(load_settings().database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError as exc:
        pytest.fail(f"Postgres is not available. Start it with: docker compose up -d ({exc})")
    tables, _truth = generate()
    apply_schema(engine, SCHEMA.read_text(encoding="utf-8"))
    for dataset in DATASETS:
        replace_dataset(engine, dataset, rows_to_csv(dataset, tables[dataset]))
    return engine
