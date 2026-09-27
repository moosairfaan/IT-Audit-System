"""Generate the synthetic population and load it into Postgres.

From the backend directory:

    python -m data_gen.seed
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError

from app.config import load_settings
from app.datasets import DATASETS
from app.load import apply_schema, count_rows, replace_dataset, rows_to_csv
from data_gen.generate import generate

GENERATED = Path(__file__).resolve().parent / "generated"
SCHEMA = Path(__file__).resolve().parents[1] / "sql" / "schema.sql"


def main() -> None:
    tables, ground_truth = generate()
    _write(tables, ground_truth)
    engine = create_engine(load_settings().database_url, pool_pre_ping=True)
    _wait(engine)
    apply_schema(engine, SCHEMA.read_text(encoding="utf-8"))
    print("Loaded the synthetic broker-dealer.")
    for dataset in DATASETS:
        csv_text = (GENERATED / f"{dataset}.csv").read_text(encoding="utf-8")
        replace_dataset(engine, dataset, csv_text)
        print(f"{dataset:24} {count_rows(engine, dataset)}")
    print(f"ground_truth             {GENERATED / 'ground_truth.json'}")


def _write(tables: dict[str, list[dict[str, object]]], ground_truth: dict[str, list[str]]) -> None:
    GENERATED.mkdir(exist_ok=True)
    for dataset, rows in tables.items():
        (GENERATED / f"{dataset}.csv").write_text(rows_to_csv(dataset, rows), encoding="utf-8")
    (GENERATED / "ground_truth.json").write_text(
        json.dumps(ground_truth, indent=2) + "\n",
        encoding="utf-8",
    )


def _wait(engine: Engine) -> None:
    last_error: Exception | None = None
    for _ in range(30):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return
        except OperationalError as exc:
            last_error = exc
            time.sleep(1)
    detail = f" ({last_error})" if last_error is not None else ""
    raise SystemExit(f"Postgres did not answer. Start it with: docker compose up -d{detail}")


if __name__ == "__main__":
    main()
