"""Active dataset and the rules the controls read.

Demo data is the synthetic broker-dealer. Company data is an imported file set.
The tables the control SQL reads always hold the active dataset. The other one
is kept in dataset_snapshots so a switch can put it back.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import Engine, delete, insert, text
from sqlalchemy.exc import IntegrityError

from app.datasets import Column, columns_for
from app.models import Base
from app.sampling.priority import CRITICAL_SYSTEMS, PRIVILEGED_ROLES

DEMO = "demo"
COMPANY = "company"
DATASETS_CHOICE = (DEMO, COMPANY)

IMPORT_TABLES: tuple[str, ...] = (
    "hr_roster",
    "iam_accounts",
    "role_permissions",
    "change_tickets",
)


class RealDataDisabled(PermissionError):
    """This deployment does not accept company data."""


class DatasetError(ValueError):
    """The requested dataset cannot be activated."""


def allow_real_data() -> bool:
    raw = os.environ.get("ALLOW_REAL_DATA", "true").strip().lower()
    return raw not in {"0", "false", "no"}


def dataset_label(dataset: str) -> str:
    if dataset == COMPANY:
        return "Company data"
    return "Demo data"


def ensure_audit_context(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS audit_context (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    active_dataset TEXT NOT NULL DEFAULT 'demo',
                    dormant_days INTEGER NOT NULL DEFAULT 90,
                    privileged_roles JSONB NOT NULL,
                    critical_systems JSONB NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    CHECK (active_dataset IN ('demo', 'company')),
                    CHECK (dormant_days >= 1)
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS column_mappings (
                    dataset TEXT PRIMARY KEY,
                    mapping JSONB NOT NULL,
                    status_map JSONB NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS dataset_snapshots (
                    dataset TEXT NOT NULL,
                    table_name TEXT NOT NULL,
                    payload JSONB NOT NULL,
                    saved_at TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (dataset, table_name),
                    CHECK (dataset IN ('demo', 'company'))
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO audit_context (
                    id, active_dataset, dormant_days, privileged_roles, critical_systems, updated_at
                )
                VALUES (
                    1, 'demo', 90, CAST(:roles AS jsonb), CAST(:systems AS jsonb), :updated_at
                )
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "roles": json.dumps(sorted(PRIVILEGED_ROLES)),
                "systems": json.dumps(sorted(CRITICAL_SYSTEMS)),
                "updated_at": datetime.now(timezone.utc),
            },
        )


def active_dataset(engine: Engine) -> str:
    ensure_audit_context(engine)
    with engine.connect() as connection:
        value = connection.execute(text("SELECT active_dataset FROM audit_context WHERE id = 1")).scalar_one()
    return str(value)


def data_source(engine: Engine) -> dict[str, object]:
    dataset = active_dataset(engine)
    return {
        "dataset": dataset,
        "label": dataset_label(dataset),
        "allow_real_data": allow_real_data(),
    }


def load_rules(engine: Engine) -> dict[str, Any]:
    ensure_audit_context(engine)
    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT dormant_days, privileged_roles, critical_systems
                FROM audit_context
                WHERE id = 1
                """
            )
        ).mappings().one()
        pairs = connection.execute(
            text(
                """
                SELECT permission_a, permission_b, description
                FROM sod_conflict_rules
                ORDER BY permission_a, permission_b
                """
            )
        ).mappings().all()
    return {
        "dormant_days": int(row["dormant_days"]),
        "privileged_roles": [str(item) for item in row["privileged_roles"]],
        "critical_systems": [str(item) for item in row["critical_systems"]],
        "sod_pairs": [dict(pair) for pair in pairs],
    }


def save_rules(engine: Engine, body: dict[str, Any]) -> dict[str, Any]:
    dormant_days = body.get("dormant_days")
    if not isinstance(dormant_days, int) or isinstance(dormant_days, bool) or dormant_days < 1:
        raise DatasetError("Dormancy threshold must be a whole number of at least 1 day.")
    roles = _names(body.get("privileged_roles"), "Privileged role")
    systems = _names(body.get("critical_systems"), "Critical system")
    pairs = _pairs(body.get("sod_pairs"))
    ensure_audit_context(engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE audit_context
                SET dormant_days = :dormant_days,
                    privileged_roles = CAST(:roles AS jsonb),
                    critical_systems = CAST(:systems AS jsonb),
                    updated_at = :updated_at
                WHERE id = 1
                """
            ),
            {
                "dormant_days": dormant_days,
                "roles": json.dumps(roles),
                "systems": json.dumps(systems),
                "updated_at": datetime.now(timezone.utc),
            },
        )
        connection.execute(text("DELETE FROM sod_conflict_rules"))
        if pairs:
            connection.execute(
                text(
                    """
                    INSERT INTO sod_conflict_rules (permission_a, permission_b, description)
                    VALUES (:permission_a, :permission_b, :description)
                    """
                ),
                pairs,
            )
    return load_rules(engine)


def activate(engine: Engine, dataset: str) -> dict[str, object]:
    if dataset not in DATASETS_CHOICE:
        raise DatasetError("Dataset must be demo or company.")
    if dataset == COMPANY and not allow_real_data():
        raise RealDataDisabled("Company data is turned off for this deployment.")
    ensure_audit_context(engine)
    current = active_dataset(engine)
    if dataset == current:
        return data_source(engine)
    if not _has_snapshot(engine, dataset):
        if dataset == COMPANY:
            raise DatasetError("Import company data before switching to it.")
        raise DatasetError("Demo data has no saved copy to restore.")
    with engine.begin() as connection:
        _write_snapshot(connection, current)
        _restore_snapshot(connection, dataset)
        connection.execute(
            text(
                """
                UPDATE audit_context
                SET active_dataset = :dataset, updated_at = :updated_at
                WHERE id = 1
                """
            ),
            {"dataset": dataset, "updated_at": datetime.now(timezone.utc)},
        )
    return data_source(engine)


def remember_demo_snapshot(engine: Engine) -> None:
    """Keep the synthetic tables before company rows replace them."""
    ensure_audit_context(engine)
    if active_dataset(engine) != DEMO:
        return
    with engine.begin() as connection:
        _write_snapshot(connection, DEMO)


def remember_company_snapshot(engine: Engine) -> None:
    ensure_audit_context(engine)
    with engine.begin() as connection:
        _write_snapshot(connection, COMPANY)
        connection.execute(
            text(
                """
                UPDATE audit_context
                SET active_dataset = 'company', updated_at = :updated_at
                WHERE id = 1
                """
            ),
            {"updated_at": datetime.now(timezone.utc)},
        )


def saved_mapping(engine: Engine, dataset: str) -> dict[str, Any] | None:
    ensure_audit_context(engine)
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT mapping, status_map FROM column_mappings WHERE dataset = :dataset"),
            {"dataset": dataset},
        ).mappings().first()
    if row is None:
        return None
    return {"mapping": dict(row["mapping"]), "status_map": dict(row["status_map"])}


def save_mapping(engine: Engine, dataset: str, mapping: dict[str, str], status_map: dict[str, str]) -> None:
    ensure_audit_context(engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO column_mappings (dataset, mapping, status_map, updated_at)
                VALUES (:dataset, CAST(:mapping AS jsonb), CAST(:status_map AS jsonb), :updated_at)
                ON CONFLICT (dataset) DO UPDATE
                SET mapping = EXCLUDED.mapping,
                    status_map = EXCLUDED.status_map,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "dataset": dataset,
                "mapping": json.dumps(mapping),
                "status_map": json.dumps(status_map),
                "updated_at": datetime.now(timezone.utc),
            },
        )


def replace_import_tables(engine: Engine, tables: dict[str, list[dict[str, Any]]]) -> None:
    """Replace the four company tables. Child rows go before parent rows."""
    from app.load import LoadError

    ordered_delete = ("change_tickets", "iam_accounts", "role_permissions", "hr_roster")
    ordered_insert = ("hr_roster", "role_permissions", "iam_accounts", "change_tickets")
    try:
        with engine.begin() as connection:
            for name in ordered_delete:
                connection.execute(delete(Base.metadata.tables[name]))
            for name in ordered_insert:
                rows = tables.get(name) or []
                if rows:
                    connection.execute(insert(Base.metadata.tables[name]), rows)
    except IntegrityError as exc:
        raise LoadError("The company files refer to an employee or account that was not imported.") from exc


def _names(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise DatasetError(f"Add at least one {label.lower()}.")
    names: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise DatasetError(f"{label} cannot be blank.")
        cleaned = item.strip()
        key = cleaned.casefold()
        if key in seen:
            raise DatasetError(f"{label} {cleaned} is listed twice.")
        seen.add(key)
        names.append(cleaned)
    return names


def _pairs(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise DatasetError("Segregation-of-duties pairs must be a list.")
    pairs: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in value:
        if not isinstance(item, dict):
            raise DatasetError("Each segregation-of-duties pair needs two permissions.")
        left = str(item.get("permission_a") or "").strip()
        right = str(item.get("permission_b") or "").strip()
        description = str(item.get("description") or "").strip()
        if not left or not right or not description:
            raise DatasetError("Each segregation-of-duties pair needs two permissions and a description.")
        if left == right:
            raise DatasetError("A segregation-of-duties pair cannot list the same permission twice.")
        key = tuple(sorted((left, right)))
        if key in seen:
            raise DatasetError(f"{left} and {right} are already a pair.")
        seen.add(key)
        pairs.append({"permission_a": left, "permission_b": right, "description": description})
    return pairs


def _has_snapshot(engine: Engine, dataset: str) -> bool:
    with engine.connect() as connection:
        count = connection.execute(
            text("SELECT COUNT(*) FROM dataset_snapshots WHERE dataset = :dataset"),
            {"dataset": dataset},
        ).scalar_one()
    return int(count) == len(IMPORT_TABLES)


def _write_snapshot(connection: Any, dataset: str) -> None:
    saved_at = datetime.now(timezone.utc)
    for name in IMPORT_TABLES:
        columns = columns_for(name)
        listed = ", ".join(column.name for column in columns)
        rows = connection.execute(text(f"SELECT {listed} FROM {name} ORDER BY 1")).mappings().all()
        payload = [_jsonable(dict(row), columns) for row in rows]
        connection.execute(
            text(
                """
                INSERT INTO dataset_snapshots (dataset, table_name, payload, saved_at)
                VALUES (:dataset, :table_name, CAST(:payload AS jsonb), :saved_at)
                ON CONFLICT (dataset, table_name) DO UPDATE
                SET payload = EXCLUDED.payload, saved_at = EXCLUDED.saved_at
                """
            ),
            {
                "dataset": dataset,
                "table_name": name,
                "payload": json.dumps(payload),
                "saved_at": saved_at,
            },
        )


def _restore_snapshot(connection: Any, dataset: str) -> None:
    for name in ("change_tickets", "iam_accounts", "role_permissions", "hr_roster"):
        connection.execute(delete(Base.metadata.tables[name]))
    for name in ("hr_roster", "role_permissions", "iam_accounts", "change_tickets"):
        raw = connection.execute(
            text(
                """
                SELECT payload FROM dataset_snapshots
                WHERE dataset = :dataset AND table_name = :table_name
                """
            ),
            {"dataset": dataset, "table_name": name},
        ).scalar_one()
        columns = columns_for(name)
        rows = [_typed(dict(item), columns) for item in raw]
        if rows:
            connection.execute(insert(Base.metadata.tables[name]), rows)


def _jsonable(row: dict[str, Any], columns: tuple[Column, ...]) -> dict[str, Any]:
    encoded: dict[str, Any] = {}
    for column in columns:
        value = row.get(column.name)
        if isinstance(value, datetime):
            encoded[column.name] = value.isoformat()
        elif isinstance(value, date):
            encoded[column.name] = value.isoformat()
        else:
            encoded[column.name] = value
    return encoded


def _typed(row: dict[str, Any], columns: tuple[Column, ...]) -> dict[str, Any]:
    typed: dict[str, Any] = {}
    for column in columns:
        value = row.get(column.name)
        if value is None or value == "":
            typed[column.name] = None
            continue
        if column.kind == "date" and isinstance(value, str):
            typed[column.name] = date.fromisoformat(value[:10])
        elif column.kind == "datetime" and isinstance(value, str):
            typed[column.name] = datetime.fromisoformat(value)
        else:
            typed[column.name] = value
    return typed

