"""Runtime settings. Defaults match .env.example."""

from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_DATABASE_URL = "postgresql+psycopg://itaudit:itaudit@localhost:5433/itaudit"
DEFAULT_CORS_ORIGINS = "http://localhost:5173"


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    cors_origins: tuple[str, ...]


def load_settings() -> Settings:
    origins = os.environ.get("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
    return Settings(
        database_url=os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL),
        cors_origins=tuple(part.strip() for part in origins.split(",") if part.strip()),
    )
