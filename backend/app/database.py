"""SQLAlchemy engine."""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, create_engine, text

from app.config import load_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(load_settings().database_url, pool_pre_ping=True)


def database_status(engine: Engine) -> str:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        return "down"
    return "up"
