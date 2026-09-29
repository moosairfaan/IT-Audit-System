"""Hosted Postgres URLs are rewritten to the psycopg driver name."""

from __future__ import annotations

import pytest

from app.config import load_settings
from data_gen.bootstrap import _has_roster_rows


def test_postgres_scheme_becomes_psycopg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgres://user:secret@db.example/itaudit?sslmode=require")
    assert (
        load_settings().database_url
        == "postgresql+psycopg://user:secret@db.example/itaudit?sslmode=require"
    )


def test_postgresql_scheme_becomes_psycopg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@db.example/itaudit")
    assert load_settings().database_url == "postgresql+psycopg://user:secret@db.example/itaudit"


def test_psycopg_url_is_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "postgresql+psycopg://itaudit:itaudit@localhost:5433/itaudit"
    monkeypatch.setenv("DATABASE_URL", url)
    assert load_settings().database_url == url


def test_bootstrap_leaves_a_loaded_roster_alone(database) -> None:
    assert _has_roster_rows(database) is True
