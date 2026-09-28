"""Workpaper section contract."""

from __future__ import annotations

SECTIONS: tuple[tuple[str, str], ...] = (
    ("control_objective", "Control objective"),
    ("risk_addressed", "Risk addressed"),
    ("procedure_performed", "Procedure performed"),
    ("population_and_sample", "Population and sample"),
    ("results", "Results"),
    ("exceptions_noted", "Exceptions noted"),
    ("conclusion", "Conclusion"),
)

SECTION_KEYS: tuple[str, ...] = tuple(key for key, _title in SECTIONS)

EFFECTIVE = "The control operated effectively."
DEFICIENCY = "A deficiency was identified."
STATUSES = ("draft", "reviewed", "approved")


def render_markdown(sections: dict[str, str], control_id: str | None = None) -> str:
    parts = [f"## {title}\n\n{sections[key].strip()}" for key, title in SECTIONS]
    body = "\n\n".join(parts) + "\n"
    if not control_id:
        return body
    return f"# {control_id}\n\n{body}"


def conclusion_is_consistent(conclusion: str, exception_count: int) -> bool:
    if exception_count == 0:
        return EFFECTIVE in conclusion and DEFICIENCY not in conclusion
    return DEFICIENCY in conclusion and EFFECTIVE not in conclusion
