"""Deterministic draft used when tests stand in for the model.

Every numeral is copied from the source result. This module does not call the model.
"""

from __future__ import annotations

from typing import Any

from app.workpapers.sections import DEFICIENCY, EFFECTIVE, SECTION_KEYS


def render_sections(source: dict[str, Any]) -> dict[str, str]:
    population = source["population_count"]
    exceptions = source["exception_count"]
    sections = {
        "control_objective": f"Control {source['control_id']}. {source['objective']}",
        "risk_addressed": str(source["risk_addressed"]),
        "procedure_performed": (
            "The procedure compared the population for this run with the exception rows "
            "in the test result. The workpaper uses only those rows."
        ),
        "population_and_sample": _population(source, population),
        "results": (
            f"The population count is {population}. The exception count is {exceptions}."
        ),
        "exceptions_noted": _exceptions(source["exceptions"], exceptions),
        "conclusion": _conclusion(exceptions),
    }
    if set(sections) != set(SECTION_KEYS):
        raise RuntimeError("The draft is missing a workpaper section")
    return sections


def _population(source: dict[str, Any], population: int) -> str:
    sample = source.get("sample")
    described = f"The test covered a population of {population}{described_label(source)}. "
    if not isinstance(sample, dict):
        text = described + "The full population was tested and no sample was selected."
    else:
        text = (
            described
            + f"A {sample['method']} sample of {sample['sample_size']} was selected "
            + f"from a sampling population of {sample['population_size']} "
            + f"with seed {sample['seed']}."
        )
    return text + _completeness(source.get("completeness"))


def described_label(source: dict[str, Any]) -> str:
    label = source.get("population")
    if isinstance(label, str) and label.strip():
        return f" {label}"
    return ""


def _completeness(value: object) -> str:
    if not isinstance(value, dict) or "records_loaded" not in value:
        return ""
    sentences = [
        f" Records loaded: {value['records_loaded']}.",
        f" Records tested: {value['records_tested']}.",
        f" Records excluded: {value['records_excluded']}.",
    ]
    exclusions = value.get("exclusions")
    if isinstance(exclusions, list):
        for item in exclusions:
            if isinstance(item, dict):
                sentences.append(f" {item['count']} excluded because {item['reason']}.")
    return "".join(sentences)


def _exceptions(rows: list[dict[str, Any]], exception_count: int) -> str:
    if exception_count == 0:
        return "No exceptions were noted."
    lines: list[str] = []
    for row in rows:
        details = [
            f"{key} {value}"
            for key, value in row.items()
            if key != "exception_id" and value is not None
        ]
        suffix = f", {', '.join(details)}" if details else ""
        lines.append(f"- Exception {row['exception_id']}{suffix}.")
    return "\n".join(lines)


def _conclusion(exception_count: int) -> str:
    determination = EFFECTIVE if exception_count == 0 else DEFICIENCY
    return f"The exception count is {exception_count}. {determination}"
