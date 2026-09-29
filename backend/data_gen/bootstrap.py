"""Load the synthetic population only when the database is empty.

The start command on a host runs this before uvicorn. A later deploy leaves
existing demo or company rows in place.
"""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import load_settings


def main() -> None:
    engine = create_engine(load_settings().database_url, pool_pre_ping=True)
    if _has_roster_rows(engine):
        print("HR roster already has rows. Leaving the database as it is.")
        return
    from data_gen.seed import main as seed_main

    seed_main()


def _has_roster_rows(engine: Engine) -> bool:
    try:
        with engine.connect() as connection:
            count = connection.execute(text("SELECT COUNT(*) FROM hr_roster")).scalar_one()
    except SQLAlchemyError:
        return False
    return int(count) > 0


if __name__ == "__main__":
    main()
