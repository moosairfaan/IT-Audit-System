"""Workpapers stay inside the test result, and an approved paper is read-only."""

from __future__ import annotations

import json
import re

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.controls.runner import run_control
from app.sampling.service import create_sample
from app.workpapers.grounding import GroundingError, check_grounding
from app.workpapers.render import render_sections
from app.workpapers.sections import DEFICIENCY
from app.workpapers.service import (
    PROMPT_PATH,
    WorkpaperError,
    WorkpaperLocked,
    ensure_workpapers,
    export_markdown,
    generate_workpaper,
    update_workpaper,
)


class RecordingClient:
    def __init__(self, invented: str | None = None) -> None:
        self.source_json = ""
        self.instructions = ""
        self.invented = invented

    def complete(self, instructions: str, source_json: str) -> str:
        self.instructions = instructions
        self.source_json = source_json
        sections = render_sections(json.loads(source_json))
        if self.invented is not None:
            sections["results"] = f"{sections['results']} {self.invented}"
        return json.dumps(sections)


def test_terminated_employee_population_is_not_called_active(database: Engine) -> None:
    run = run_control(database, "ITGC-01")
    assert "terminated" in run["population"].lower()
    assert not re.search(r"\bactive\b", run["population"], re.IGNORECASE)
    client = RecordingClient()
    paper = generate_workpaper(database, client, "ITGC-01", run["run_id"])
    source = json.loads(client.source_json)
    assert source["population"] == "accounts belonging to terminated employees"
    section = paper["sections"]["population_and_sample"]
    assert not re.search(r"\bactive\b", section, re.IGNORECASE)


def test_population_section_states_completeness_counts(database: Engine) -> None:
    run = run_control(database, "ITGC-01")
    client = RecordingClient()
    paper = generate_workpaper(database, client, "ITGC-01", run["run_id"])
    source = json.loads(client.source_json)
    completeness = source["completeness"]
    assert completeness["records_loaded"] == run["completeness"]["records_loaded"]
    assert completeness["records_tested"] == run["completeness"]["records_tested"]
    assert completeness["records_excluded"] == run["completeness"]["records_excluded"]
    section = paper["sections"]["population_and_sample"]
    assert f"Records loaded: {completeness['records_loaded']}." in section
    assert f"Records tested: {completeness['records_tested']}." in section
    assert f"Records excluded: {completeness['records_excluded']}." in section
    for item in completeness["exclusions"]:
        assert f"{item['count']} excluded because {item['reason']}." in section
    check_grounding(paper["markdown"], source)
    instructions = client.instructions
    assert "records_loaded" in instructions
    assert "records_tested" in instructions
    assert "records_excluded" in instructions


def test_omitted_completeness_is_added_and_stays_grounded(database: Engine) -> None:
    run = run_control(database, "ITGC-01")

    class OmitCompleteness(RecordingClient):
        def complete(self, instructions: str, source_json: str) -> str:
            self.instructions = instructions
            self.source_json = source_json
            sections = render_sections(json.loads(source_json))
            text = sections["population_and_sample"]
            sections["population_and_sample"] = text.split(" Records loaded:")[0]
            return json.dumps(sections)

    client = OmitCompleteness()
    paper = generate_workpaper(database, client, "ITGC-01", run["run_id"])
    source = json.loads(client.source_json)
    section = paper["sections"]["population_and_sample"]
    assert f"Records loaded: {source['completeness']['records_loaded']}." in section
    check_grounding(paper["markdown"], source)


def test_prompt_separates_results_from_the_exception_narrative() -> None:
    text = PROMPT_PATH.read_text(encoding="utf-8")
    assert "do not list every exception row" in text.lower()
    assert "exception rate" in text.lower()
    assert "do not copy any figure" in text.lower()


def test_grounding_rejects_a_number_that_is_not_in_the_source() -> None:
    source = {"control_id": "ITGC-01", "population_count": 80, "exception_count": 8}
    check_grounding("Control ITGC-01. The population count is 80. The exception count is 8.", source)
    with pytest.raises(GroundingError, match="99999"):
        check_grounding("The population count is 99999.", source)


def test_generated_workpaper_uses_only_source_numbers(database: Engine) -> None:
    run = run_control(database, "ITGC-01")
    client = RecordingClient()
    paper = generate_workpaper(database, client, "ITGC-01", run["run_id"])
    source = json.loads(client.source_json)
    assert source["exception_count"] == run["exception_count"]
    assert source["summary"]["exception_rate_percent"] == "10.00"
    assert "sample" not in source
    check_grounding(paper["markdown"], source)
    assert paper["status"] == "draft"
    assert DEFICIENCY in paper["sections"]["conclusion"]
    exported = export_markdown(database, paper["id"])
    assert exported == paper["markdown"]
    assert "ITGC-01" in exported
    assert "## Conclusion" in exported


def test_sample_metadata_is_included_and_stays_grounded(database: Engine) -> None:
    run = run_control(database, "ITGC-01")
    sample = create_sample(database, "ITGC-01", "random", 5, seed=3)
    client = RecordingClient()
    paper = generate_workpaper(database, client, "ITGC-01", run["run_id"], sample["sample_id"])
    source = json.loads(client.source_json)
    assert source["sample"]["seed"] == 3
    assert source["sample"]["sample_size"] == 5
    check_grounding(paper["markdown"], source)
    assert "seed 3" in paper["markdown"]


def test_invented_number_is_not_stored(database: Engine) -> None:
    run = run_control(database, "ITGC-01")
    before = _count(database)
    with pytest.raises(WorkpaperError, match="99999"):
        generate_workpaper(database, RecordingClient("Unsupported total 99999."), "ITGC-01", run["run_id"])
    assert _count(database) == before


def test_approved_workpaper_rejects_later_edits(database: Engine) -> None:
    run = run_control(database, "ITGC-01")
    paper = generate_workpaper(database, RecordingClient(), "ITGC-01", run["run_id"])
    reviewed = update_workpaper(
        database,
        paper["id"],
        sections={
            "procedure_performed": (
                "The procedure used the exception rows in the test result and no other source."
            )
        },
        status="reviewed",
        reviewer_notes="Prepared for review.",
    )
    assert reviewed["status"] == "reviewed"
    assert reviewed["reviewer_notes"] == "Prepared for review."
    approved = update_workpaper(database, paper["id"], status="approved")
    assert approved["status"] == "approved"
    with pytest.raises(WorkpaperLocked):
        update_workpaper(database, paper["id"], reviewer_notes="Change after approval.")
    assert export_markdown(database, paper["id"]) == approved["markdown"]


def _count(engine: Engine) -> int:
    ensure_workpapers(engine)
    with engine.connect() as connection:
        count = connection.execute(text("SELECT COUNT(*) FROM workpapers")).scalar_one()
    return int(count)
