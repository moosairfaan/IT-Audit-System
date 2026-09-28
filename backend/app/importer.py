"""Map, normalize, and validate a company CSV before it replaces the tables.

The four import files are the HR roster, application accounts, role permissions,
and change tickets. Segregation-of-duties pairs are rules, not an uploaded file.
"""

from __future__ import annotations

import io
import re
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from typing import Any

import pandas as pd

from app.datasets import (
    CHANGE_TICKETS,
    HR_ROSTER,
    IAM_ACCOUNTS,
    ROLE_PERMISSIONS,
    Column,
    columns_for,
)
from app.load import LoadError

IMPORT_DATASETS: tuple[str, ...] = (HR_ROSTER, IAM_ACCOUNTS, ROLE_PERMISSIONS, CHANGE_TICKETS)

LABELS = {
    HR_ROSTER: "HR roster",
    IAM_ACCOUNTS: "IAM accounts",
    ROLE_PERMISSIONS: "Role permissions",
    CHANGE_TICKETS: "Change tickets",
}

_ACTIVE = {"active", "a", "enabled", "1"}
_DISABLED = {"disabled", "d", "inactive", "0"}
_TRUE = {"true", "t", "1", "yes"}
_FALSE = {"false", "f", "0", "no"}

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%m-%d-%Y",
    "%d-%b-%Y",
    "%d-%b-%y",
    "%d %b %Y",
    "%b %d, %Y",
    "%d-%b-%Y",
)

_ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
    HR_ROSTER: {
        "employee_id": ("employee id", "emp id", "employee number", "worker id", "staff id"),
        "name": ("full name", "employee name", "worker name", "name"),
        "department": ("dept", "department name", "department"),
        "job_title": ("job title", "title", "position"),
        "hire_date": ("hire date", "start date", "date of hire", "hire dt"),
        "termination_date": ("termination date", "termination", "term date", "end date"),
    },
    IAM_ACCOUNTS: {
        "account_id": ("account id", "account number", "user id"),
        "employee_id": ("employee id", "employee", "emp id", "owner"),
        "system": ("system", "application", "system name", "app"),
        "role": ("role", "access role", "role name"),
        "status": ("status", "account status"),
        "last_login": ("last login", "last sign in", "last login date"),
        "is_shared": ("is shared", "shared", "generic"),
    },
    ROLE_PERMISSIONS: {
        "role": ("role", "role name"),
        "permission": ("permission", "privilege", "access right"),
    },
    CHANGE_TICKETS: {
        "ticket_id": ("ticket id", "change id", "ticket", "change number"),
        "system": ("system", "application"),
        "requested_by": ("requested by", "requester", "requestor"),
        "approved_by": ("approved by", "approver"),
        "deployed_by": ("deployed by", "deployer"),
        "approved_at": ("approved at", "approved on", "approval date"),
        "deployed_at": ("deployed at", "deployed on", "deployment date"),
        "description": ("description", "summary"),
    },
}

_KEYS = {
    HR_ROSTER: ("employee_id",),
    IAM_ACCOUNTS: ("account_id",),
    ROLE_PERMISSIONS: ("role", "permission"),
    CHANGE_TICKETS: ("ticket_id",),
}


def template_csv(dataset: str) -> str:
    _known(dataset)
    columns = columns_for(dataset)
    header = ",".join(column.name for column in columns)
    example = ",".join(_example(column) for column in columns)
    return f"{header}\n{example}\n"


def inspect_csv(dataset: str, csv_text: str, saved: dict[str, Any] | None = None) -> dict[str, Any]:
    _known(dataset)
    headers = read_headers(csv_text)
    columns = columns_for(dataset)
    suggested = suggest_mapping(dataset, headers)
    mapping = _reuse(saved, headers, suggested) if saved else suggested
    status_header = mapping.get("status") if dataset == IAM_ACCOUNTS else None
    values = status_values(csv_text, status_header) if status_header else []
    saved_status = dict(saved["status_map"]) if saved else {}
    return {
        "dataset": dataset,
        "label": LABELS[dataset],
        "headers": headers,
        "fields": [_field(column, mapping.get(column.name, "")) for column in columns],
        "mapping": mapping,
        "status_values": values,
        "status_map": {value: saved_status.get(value, suggest_status(value)) for value in values},
    }


def suggest_mapping(dataset: str, headers: list[str]) -> dict[str, str]:
    columns = columns_for(dataset)
    aliases = _ALIASES[dataset]
    candidates: list[tuple[float, str, str]] = []
    for column in columns:
        for header in headers:
            score = _score(column.name, header, aliases.get(column.name, ()))
            if score >= 0.72:
                candidates.append((score, column.name, header))
    candidates.sort(key=lambda item: item[0], reverse=True)
    mapping = {column.name: "" for column in columns}
    used_headers: set[str] = set()
    used_fields: set[str] = set()
    for _score_value, field, header in candidates:
        if field in used_fields or header in used_headers:
            continue
        mapping[field] = header
        used_fields.add(field)
        used_headers.add(header)
    return mapping


def suggest_status(raw: str) -> str:
    token = raw.strip().casefold()
    if token in _ACTIVE:
        return "active"
    if token in _DISABLED:
        return "disabled"
    return ""


def status_values(csv_text: str, header: str | None) -> list[str]:
    if not header:
        return []
    frame = _frame(csv_text)
    if header not in frame.columns:
        return []
    seen: list[str] = []
    for value in frame[header].tolist():
        text = str(value).strip()
        if text and text not in seen:
            seen.append(text)
    return seen


def read_headers(csv_text: str) -> list[str]:
    frame = _frame(csv_text)
    headers = [str(name).strip().lstrip("\ufeff") for name in frame.columns]
    if any(not header for header in headers):
        raise LoadError("The CSV has a blank column name.")
    if len(headers) != len(set(headers)):
        raise LoadError("The CSV repeats a column name.")
    return headers


def validate_dataset(
    dataset: str,
    csv_text: str,
    mapping: dict[str, str],
    status_map: dict[str, str] | None = None,
    roster_ids: set[str] | None = None,
) -> dict[str, Any]:
    _known(dataset)
    columns = columns_for(dataset)
    headers = read_headers(csv_text)
    clean_mapping = _clean_mapping(mapping, headers, columns)
    coverage = [_field(column, clean_mapping.get(column.name, "")) for column in columns]
    blocked = any(item["required"] and not item["mapped"] for item in coverage)
    report: dict[str, Any] = {
        "dataset": dataset,
        "label": LABELS[dataset],
        "rows_seen": 0,
        "rows_loaded": 0,
        "rows_skipped": 0,
        "skipped": [],
        "coverage": coverage,
        "blocked": blocked,
        "rows": [],
    }
    if blocked:
        frame = _frame(csv_text)
        report["rows_seen"] = int(len(frame))
        report["rows_skipped"] = report["rows_seen"]
        report["skipped"].append({"line": 1, "reason": "a required field is not mapped"})
        return report
    frame = _frame(csv_text)
    seen_keys: set[tuple[str, ...]] = set()
    accepted_ids: set[str] = set()
    for offset, record in enumerate(frame.to_dict(orient="records"), start=2):
        report["rows_seen"] += 1
        parsed, reason = _parse_record(dataset, offset, record, columns, clean_mapping, status_map or {})
        if parsed is None:
            report["rows_skipped"] += 1
            report["skipped"].append({"line": offset, "reason": reason})
            continue
        foreign = _foreign_reason(dataset, parsed, roster_ids)
        if foreign:
            report["rows_skipped"] += 1
            report["skipped"].append({"line": offset, "reason": foreign})
            continue
        key = tuple(str(parsed[name]) for name in _KEYS[dataset])
        if key in seen_keys:
            report["rows_skipped"] += 1
            report["skipped"].append({"line": offset, "reason": f"duplicate {_KEYS[dataset][0]}"})
            continue
        seen_keys.add(key)
        if dataset == HR_ROSTER:
            accepted_ids.add(str(parsed["employee_id"]))
        report["rows_loaded"] += 1
        report["rows"].append(parsed)
    report["accepted_ids"] = sorted(accepted_ids)
    return report


def validate_bundle(files: dict[str, dict[str, Any]]) -> dict[str, Any]:
    missing = [dataset for dataset in IMPORT_DATASETS if dataset not in files]
    if missing:
        raise LoadError(f"Upload all four files. Missing {', '.join(missing)}.")
    roster = validate_dataset(
        HR_ROSTER,
        str(files[HR_ROSTER]["csv"]),
        dict(files[HR_ROSTER].get("mapping") or {}),
        None,
    )
    roster_ids = set(roster.get("accepted_ids") or [])
    reports = [roster]
    for dataset in (IAM_ACCOUNTS, ROLE_PERMISSIONS, CHANGE_TICKETS):
        reports.append(
            validate_dataset(
                dataset,
                str(files[dataset]["csv"]),
                dict(files[dataset].get("mapping") or {}),
                dict(files[dataset].get("status_map") or {}) if dataset == IAM_ACCOUNTS else None,
                roster_ids if dataset in {IAM_ACCOUNTS, CHANGE_TICKETS} else None,
            )
        )
    public = [_public_report(report) for report in reports]
    return {
        "datasets": public,
        "can_import": all(not item["blocked"] for item in public),
        "rows": {report["dataset"]: report["rows"] for report in reports},
    }


def commit_import(engine: Any, files: dict[str, dict[str, Any]]) -> dict[str, Any]:
    from app.audit_context import (
        RealDataDisabled,
        allow_real_data,
        remember_company_snapshot,
        remember_demo_snapshot,
        replace_import_tables,
        save_mapping,
    )
    from app.completeness import completeness_report

    if not allow_real_data():
        raise RealDataDisabled("Company data is turned off for this deployment.")
    bundle = validate_bundle(files)
    if not bundle["can_import"]:
        raise LoadError("Import is blocked until every required field is mapped.")
    for dataset in IMPORT_DATASETS:
        payload = files[dataset]
        save_mapping(
            engine,
            dataset,
            {str(key): str(value) for key, value in dict(payload.get("mapping") or {}).items()},
            {str(key): str(value) for key, value in dict(payload.get("status_map") or {}).items()},
        )
    remember_demo_snapshot(engine)
    replace_import_tables(engine, bundle["rows"])
    remember_company_snapshot(engine)
    return {
        "dataset": "company",
        "label": "Company data",
        "validation": {"datasets": bundle["datasets"], "can_import": True},
        "completeness": completeness_report(engine),
    }


def _public_report(report: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in report.items() if key not in {"rows", "accepted_ids"}}


def _known(dataset: str) -> None:
    if dataset not in IMPORT_DATASETS:
        raise LoadError(f"Unknown import {dataset}. Expected one of: {', '.join(IMPORT_DATASETS)}")


def _frame(csv_text: str) -> pd.DataFrame:
    if not csv_text.strip():
        raise LoadError("CSV body is empty")
    try:
        return pd.read_csv(io.StringIO(csv_text), dtype=str, keep_default_na=False)
    except pd.errors.ParserError as exc:
        raise LoadError(f"CSV could not be parsed: {exc}") from exc


def _reuse(saved: dict[str, Any], headers: list[str], suggested: dict[str, str]) -> dict[str, str]:
    mapping = dict(suggested)
    header_set = set(headers)
    for field, header in dict(saved.get("mapping") or {}).items():
        if field in mapping and isinstance(header, str) and header in header_set:
            mapping[field] = header
    used: set[str] = set()
    for field, header in list(mapping.items()):
        if not header:
            continue
        if header in used:
            mapping[field] = ""
            continue
        used.add(header)
    return mapping


def _clean_mapping(mapping: dict[str, str], headers: list[str], columns: tuple[Column, ...]) -> dict[str, str]:
    header_set = set(headers)
    clean = {column.name: "" for column in columns}
    used: set[str] = set()
    for column in columns:
        header = str(mapping.get(column.name) or "").strip()
        if not header:
            continue
        if header not in header_set:
            raise LoadError(f"{column.name} is mapped to {header}, which is not a column in the file.")
        if header in used:
            raise LoadError(f"{header} is mapped to more than one field.")
        used.add(header)
        clean[column.name] = header
    return clean


def _field(column: Column, header: str) -> dict[str, Any]:
    return {
        "field": column.name,
        "header": header,
        "required": not column.nullable,
        "mapped": bool(header),
    }


def _parse_record(
    dataset: str,
    line_number: int,
    record: dict[str, Any],
    columns: tuple[Column, ...],
    mapping: dict[str, str],
    status_map: dict[str, str],
) -> tuple[dict[str, Any] | None, str]:
    parsed: dict[str, Any] = {}
    for column in columns:
        header = mapping.get(column.name) or ""
        raw = str(record.get(header, "")).strip() if header else ""
        if raw == "":
            if not column.nullable:
                return None, f"missing {column.name}"
            parsed[column.name] = None
            continue
        try:
            parsed[column.name] = _parse_value(column, raw, status_map)
        except ValueError:
            if column.kind in {"date", "datetime"}:
                return None, f"bad date in {column.name}"
            if column.name == "status":
                return None, "status value has no mapping"
            return None, f"{column.name} could not be read"
    return parsed, ""


def _parse_value(column: Column, raw: str, status_map: dict[str, str]) -> Any:
    if column.kind == "date":
        return _parse_date(raw)
    if column.kind == "datetime":
        return _parse_datetime(raw)
    if column.kind == "bool":
        return _parse_bool(raw)
    if column.name == "status":
        mapped = status_map.get(raw, suggest_status(raw))
        if mapped not in {"active", "disabled"}:
            raise ValueError(raw)
        return mapped
    return raw


def _parse_date(raw: str) -> date:
    text = raw.strip()
    named = _named_date(text)
    if named is not None:
        return named
    iso = text[:10]
    if len(text) >= 10 and iso[4] == "-" and iso[7] == "-":
        return date.fromisoformat(iso)
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(raw)


def _named_date(text: str) -> date | None:
    match = re.fullmatch(r"(\d{1,2})[- ]([A-Za-z]{3,9})[- ](\d{2,4})", text.strip())
    if match is None:
        return None
    months = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    month = months.get(match.group(2)[:3].casefold())
    if month is None:
        return None
    year = int(match.group(3))
    if year < 100:
        year += 2000
    return date(year, month, int(match.group(1)))


def _parse_datetime(raw: str) -> datetime:
    text = raw.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        parsed = datetime.combine(_parse_date(text), datetime.min.time())
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_bool(raw: str) -> bool:
    token = raw.strip().casefold()
    if token in _TRUE:
        return True
    if token in _FALSE:
        return False
    raise ValueError(raw)


def _foreign_reason(dataset: str, row: dict[str, Any], roster_ids: set[str] | None) -> str:
    if roster_ids is None:
        return ""
    if dataset == IAM_ACCOUNTS:
        employee_id = row.get("employee_id")
        if employee_id and str(employee_id) not in roster_ids:
            return "employee_id is not on the HR roster"
        return ""
    if dataset == CHANGE_TICKETS:
        for field in ("requested_by", "approved_by", "deployed_by"):
            value = row.get(field)
            if value and str(value) not in roster_ids:
                return f"{field} is not on the HR roster"
    return ""


def _score(field: str, header: str, aliases: tuple[str, ...]) -> float:
    compact_header = _compact(header)
    names = (field.replace("_", " "), *aliases)
    best = 0.0
    for name in names:
        if _compact(name) == compact_header or name.casefold() == header.strip().casefold():
            return 1.0
        best = max(best, SequenceMatcher(None, _compact(name), compact_header).ratio())
    return best


def _compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _example(column: Column) -> str:
    samples = {
        "employee_id": "E100",
        "name": "Ada Lovelace",
        "department": "Finance",
        "job_title": "Analyst",
        "hire_date": "2020-01-15",
        "termination_date": "",
        "account_id": "A100",
        "system": "payments",
        "role": "payment_read",
        "permission": "view_payments",
        "status": "active",
        "last_login": "2026-08-01T00:00:00+00:00",
        "is_shared": "false",
        "ticket_id": "CHG-1",
        "requested_by": "E100",
        "approved_by": "E101",
        "deployed_by": "E102",
        "approved_at": "2026-08-01T00:00:00+00:00",
        "deployed_at": "2026-08-02T00:00:00+00:00",
        "description": "Example change",
    }
    return samples.get(column.name, "")
