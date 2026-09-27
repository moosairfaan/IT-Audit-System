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
    if not isinstance(sample, dict):
        return f"The population count is {population}. No sample was selected."
    return (
        f"The population count is {population}. "
        f"A {sample['method']} sample of {sample['sample_size']} was selected "
        f"from a sampling population of {sample['population_size']} "
        f"with seed {sample['seed']}."
    )


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
