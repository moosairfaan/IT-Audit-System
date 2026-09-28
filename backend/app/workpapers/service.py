"""Create, edit, and export a workpaper from one test run."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import Engine, text

from app.controls.store import ensure_test_runs, get_run
from app.sampling.service import SampleNotFound, ensure_samples, get_sample
from app.workpapers.grounding import GroundingError, check_grounding
from app.workpapers.sections import SECTION_KEYS, STATUSES, conclusion_is_consistent, render_markdown

PROMPT_PATH = Path(__file__).resolve().parent / "prompt.txt"
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)

_CREATE_WORKPAPERS = """
CREATE TABLE IF NOT EXISTS workpapers (
    workpaper_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    control_id TEXT NOT NULL,
    run_id INTEGER NOT NULL REFERENCES test_runs (run_id),
    sample_id INTEGER REFERENCES samples (sample_id),
    status TEXT NOT NULL,
    sections JSONB NOT NULL,
    markdown TEXT NOT NULL,
    source_json JSONB NOT NULL,
    reviewer_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    edited_at TIMESTAMPTZ NOT NULL,
    dataset TEXT NOT NULL DEFAULT 'demo',
    CHECK (status IN ('draft', 'reviewed', 'approved'))
)
"""


class WorkpaperClient(Protocol):
    def complete(self, instructions: str, source_json: str) -> str:
        """Return the model text for one workpaper."""


class WorkpaperError(ValueError):
    """The draft or the edit is not acceptable."""


class WorkpaperNotFound(LookupError):
    """No workpaper or test run has that id."""


class WorkpaperLocked(WorkpaperError):
    """An approved workpaper cannot be edited."""


def generate_workpaper(
    engine: Engine,
    client: WorkpaperClient,
    control_id: str,
    run_id: int,
    sample_id: int | None = None,
) -> dict[str, Any]:
    source = _source(engine, control_id, run_id, sample_id)
    source_json = json.dumps(source, ensure_ascii=False, default=str)
    instructions = PROMPT_PATH.read_text(encoding="utf-8")
    raw = client.complete(instructions, source_json)
    sections = parse_sections(raw)
    _accept(sections, source)
    markdown = render_markdown(sections, control_id)
    now = datetime.now(timezone.utc)
    dataset = str(source.get("dataset") or "demo")
    workpaper_id = _insert(
        engine,
        control_id=control_id,
        run_id=run_id,
        sample_id=sample_id,
        sections=sections,
        markdown=markdown,
        source=source,
        now=now,
        dataset=dataset,
    )
    return _present(
        workpaper_id, control_id, run_id, sample_id, "draft", sections, markdown, None, now, now, dataset
    )


def list_workpapers(engine: Engine) -> list[dict[str, Any]]:
    ensure_workpapers(engine)
    statement = text(
        """
        SELECT workpaper_id, control_id, run_id, sample_id, status, created_at, edited_at, dataset
        FROM workpapers
        ORDER BY workpaper_id DESC
        """
    )
    with engine.connect() as connection:
        rows = connection.execute(statement).mappings().all()
    listed: list[dict[str, Any]] = []
    for row in rows:
        body = dict(row)
        body["id"] = body.pop("workpaper_id")
        body["created_at"] = body["created_at"].isoformat()
        body["edited_at"] = body["edited_at"].isoformat()
        body["dataset"] = str(body.get("dataset") or "demo")
        body["dataset_label"] = "Company data" if body["dataset"] == "company" else "Demo data"
        listed.append(body)
    return listed


def get_workpaper(engine: Engine, workpaper_id: int) -> dict[str, Any]:
    row = _load(engine, workpaper_id)
    row.pop("source")
    return row


def update_workpaper(
    engine: Engine,
    workpaper_id: int,
    sections: dict[str, str] | None = None,
    status: str | None = None,
    reviewer_notes: str | None = None,
) -> dict[str, Any]:
    current = _load(engine, workpaper_id)
    if current["status"] == "approved":
        raise WorkpaperLocked("An approved workpaper is read-only")
    if sections is None and status is None and reviewer_notes is None:
        raise WorkpaperError("No changes were provided")
    updated = dict(current["sections"])
    if sections is not None:
        unknown = set(sections) - set(SECTION_KEYS)
        if unknown:
            raise WorkpaperError(f"Unknown workpaper section: {', '.join(sorted(unknown))}")
        for key, value in sections.items():
            if not isinstance(value, str) or not value.strip():
                raise WorkpaperError(f"{key} cannot be empty")
            updated[key] = value.strip()
        _accept(updated, current["source"])
    if status is not None and status not in STATUSES:
        raise WorkpaperError("status must be draft, reviewed, or approved")
    markdown = render_markdown(updated, str(current["control_id"]))
    new_status = status or current["status"]
    notes = current["reviewer_notes"] if reviewer_notes is None else reviewer_notes
    edited_at = datetime.now(timezone.utc)
    _save_edit(engine, workpaper_id, updated, markdown, new_status, notes, edited_at)
    current["sections"] = updated
    current["markdown"] = markdown
    current["status"] = new_status
    current["reviewer_notes"] = notes
    current["edited_at"] = edited_at.isoformat()
    current.pop("source")
    return current


def export_markdown(engine: Engine, workpaper_id: int) -> str:
    return str(get_workpaper(engine, workpaper_id)["markdown"])


def parse_sections(raw: str) -> dict[str, str]:
    text_value = raw.strip()
    text_value = _FENCE.sub("", text_value).strip()
    try:
        parsed = json.loads(text_value)
    except json.JSONDecodeError as exc:
        raise WorkpaperError("The draft was not valid section JSON") from exc
    if not isinstance(parsed, dict):
        raise WorkpaperError("The draft was not a JSON object")
    missing = [key for key in SECTION_KEYS if key not in parsed]
    if missing:
        raise WorkpaperError(f"The draft is missing {', '.join(missing)}")
    extra = [key for key in parsed if key not in SECTION_KEYS]
    if extra:
        raise WorkpaperError(f"The draft has unknown fields: {', '.join(extra)}")
    sections: dict[str, str] = {}
    for key in SECTION_KEYS:
        value = parsed[key]
        if not isinstance(value, str) or not value.strip():
            raise WorkpaperError(f"{key} must be a non-empty string")
        sections[key] = value.strip()
    return sections


def ensure_workpapers(engine: Engine) -> None:
    ensure_test_runs(engine)
    ensure_samples(engine)
    with engine.begin() as connection:
        connection.execute(text(_CREATE_WORKPAPERS))
        connection.execute(
            text("ALTER TABLE workpapers ADD COLUMN IF NOT EXISTS dataset TEXT NOT NULL DEFAULT 'demo'")
        )


def _source(engine: Engine, control_id: str, run_id: int, sample_id: int | None) -> dict[str, Any]:
    run = get_run(engine, control_id, run_id)
    if run is None:
        raise WorkpaperNotFound(f"Unknown run {run_id} for {control_id}")
    payload: dict[str, Any] = {
        "control_id": run["control_id"],
        "name": run["name"],
        "objective": run["objective"],
        "risk_addressed": run["risk_addressed"],
        "population": run["population"],
        "population_count": run["population_count"],
        "exception_count": run["exception_count"],
        "exceptions": run["exceptions"],
        "summary": _summary(run["exceptions"], int(run["population_count"]), int(run["exception_count"])),
        "run_id": run["run_id"],
        "run_at": run["run_at"],
        "dataset": run.get("dataset") or "demo",
        "dataset_label": run.get("dataset_label") or "Demo data",
        "completeness": run.get("completeness") or {},
    }
    if sample_id is None:
        return payload
    try:
        sample = get_sample(engine, sample_id)
    except SampleNotFound as exc:
        raise WorkpaperNotFound(f"Unknown sample {sample_id}") from exc
    if sample["control_id"] != control_id or sample["run_id"] != run_id:
        raise WorkpaperError("The sample does not belong to this test run")
    payload["sample"] = {
        "sample_id": sample["sample_id"],
        "method": sample["method"],
        "seed": sample["seed"],
        "population_size": sample["population_size"],
        "sample_size": sample["sample_size"],
        "selected_ids": sample["selected_ids"],
    }
    return payload


def _summary(rows: list[dict[str, Any]], population_count: int, exception_count: int) -> dict[str, Any]:
    """Aggregates the model may cite. Every figure is computed from the run."""
    summary: dict[str, Any] = {
        "exception_rate": _rate(exception_count, population_count),
        "exception_rate_percent": _percent(exception_count, population_count),
    }
    for key in ("system", "department", "role"):
        counts = Counter(str(row[key]) for row in rows if row.get(key) not in (None, ""))
        if counts:
            summary[f"count_by_{key}"] = dict(sorted(counts.items()))
    numeric: dict[str, list[tuple[Decimal, str | None]]] = {}
    for row in rows:
        exception_id = row.get("exception_id")
        label = str(exception_id) if exception_id is not None else None
        for key, value in row.items():
            if key == "exception_id" or key.endswith("_id") or isinstance(value, bool):
                continue
            if not isinstance(value, (int, float)):
                continue
            numeric.setdefault(key, []).append((Decimal(str(value)), label))
    for key, pairs in numeric.items():
        low = min(pairs, key=lambda pair: pair[0])
        high = max(pairs, key=lambda pair: pair[0])
        summary[f"{key}_min"] = _whole(low[0])
        summary[f"{key}_max"] = _whole(high[0])
        if low[1] is not None:
            summary[f"{key}_min_exception_id"] = low[1]
        if high[1] is not None:
            summary[f"{key}_max_exception_id"] = high[1]
    return summary


def _rate(exceptions: int, population: int) -> str:
    if population == 0:
        return "0.0000"
    return format((Decimal(exceptions) / Decimal(population)).quantize(Decimal("0.0001")), "f")


def _percent(exceptions: int, population: int) -> str:
    if population == 0:
        return "0.00"
    return format((Decimal(exceptions) / Decimal(population) * 100).quantize(Decimal("0.01")), "f")


def _whole(value: Decimal) -> int | str:
    if value == value.to_integral():
        return int(value)
    return format(value, "f")


def _accept(sections: dict[str, str], source: dict[str, Any]) -> None:
    try:
        check_grounding(render_markdown(sections, str(source.get("control_id") or "")), source)
    except GroundingError as exc:
        raise WorkpaperError(str(exc)) from exc
    if not conclusion_is_consistent(sections["conclusion"], int(source["exception_count"])):
        raise WorkpaperError(
            "The conclusion does not match the exception count in the test result"
        )


def _insert(
    engine: Engine,
    control_id: str,
    run_id: int,
    sample_id: int | None,
    sections: dict[str, str],
    markdown: str,
    source: dict[str, Any],
    now: datetime,
    dataset: str,
) -> int:
    ensure_workpapers(engine)
    statement = text(
        """
        INSERT INTO workpapers (
            control_id, run_id, sample_id, status, sections, markdown,
            source_json, reviewer_notes, created_at, edited_at, dataset
        )
        VALUES (
            :control_id, :run_id, :sample_id, 'draft',
            CAST(:sections AS jsonb), :markdown, CAST(:source_json AS jsonb),
            NULL, :created_at, :edited_at, :dataset
        )
        RETURNING workpaper_id
        """
    )
    with engine.begin() as connection:
        workpaper_id = connection.execute(
            statement,
            {
                "control_id": control_id,
                "run_id": run_id,
                "sample_id": sample_id,
                "sections": json.dumps(sections),
                "markdown": markdown,
                "source_json": json.dumps(source, default=str),
                "created_at": now,
                "edited_at": now,
                "dataset": dataset,
            },
        ).scalar_one()
    return int(workpaper_id)


def _save_edit(
    engine: Engine,
    workpaper_id: int,
    sections: dict[str, str],
    markdown: str,
    status: str,
    reviewer_notes: str | None,
    edited_at: datetime,
) -> None:
    statement = text(
        """
        UPDATE workpapers
        SET sections = CAST(:sections AS jsonb),
            markdown = :markdown,
            status = :status,
            reviewer_notes = :reviewer_notes,
            edited_at = :edited_at
        WHERE workpaper_id = :workpaper_id
        """
    )
    with engine.begin() as connection:
        connection.execute(
            statement,
            {
                "workpaper_id": workpaper_id,
                "sections": json.dumps(sections),
                "markdown": markdown,
                "status": status,
                "reviewer_notes": reviewer_notes,
                "edited_at": edited_at,
            },
        )


def _load(engine: Engine, workpaper_id: int) -> dict[str, Any]:
    ensure_workpapers(engine)
    row = _fetch(engine, workpaper_id)
    if row is None:
        raise WorkpaperNotFound(f"Unknown workpaper {workpaper_id}")
    return row


def _fetch(engine: Engine, workpaper_id: int) -> dict[str, Any] | None:
    statement = text(
        """
        SELECT workpaper_id, control_id, run_id, sample_id, status, sections,
               markdown, source_json, reviewer_notes, created_at, edited_at, dataset
        FROM workpapers
        WHERE workpaper_id = :workpaper_id
        """
    )
    with engine.connect() as connection:
        row = connection.execute(statement, {"workpaper_id": workpaper_id}).mappings().first()
    if row is None:
        return None
    body = dict(row)
    body["id"] = body.pop("workpaper_id")
    body["source"] = body.pop("source_json")
    body["created_at"] = body["created_at"].isoformat()
    body["edited_at"] = body["edited_at"].isoformat()
    body["dataset"] = str(body.get("dataset") or "demo")
    body["dataset_label"] = "Company data" if body["dataset"] == "company" else "Demo data"
    return body


def _present(
    workpaper_id: int,
    control_id: str,
    run_id: int,
    sample_id: int | None,
    status: str,
    sections: dict[str, str],
    markdown: str,
    reviewer_notes: str | None,
    created_at: datetime,
    edited_at: datetime,
    dataset: str,
) -> dict[str, Any]:
    return {
        "id": workpaper_id,
        "control_id": control_id,
        "run_id": run_id,
        "sample_id": sample_id,
        "status": status,
        "sections": sections,
        "markdown": markdown,
        "reviewer_notes": reviewer_notes,
        "created_at": created_at.isoformat(),
        "edited_at": edited_at.isoformat(),
        "dataset": dataset,
        "dataset_label": "Company data" if dataset == "company" else "Demo data",
    }
