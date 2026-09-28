"""Rank an exception for the dashboard.

High is a terminated employee who still has access, a segregation-of-duties
conflict on payments or the general ledger, or an orphaned account or unknown
user. Low is a dormant account or a shared account. Every other exception is medium.
"""

from __future__ import annotations

from typing import Any

SEVERITIES = ("high", "medium", "low")

_PAYMENTS_OR_GL = ("payment", "journal")


def severity_for(control_id: str, row: dict[str, Any]) -> str:
    if control_id == "ITGC-01":
        return "high"
    if control_id == "ITGC-06":
        return "high"
    if control_id == "ITGC-02":
        pairs = str(row.get("conflicting_pairs") or "")
        if any(token in pairs for token in _PAYMENTS_OR_GL):
            return "high"
        return "medium"
    if control_id in {"ITGC-04", "ITGC-05"}:
        return "low"
    return "medium"


def annotate_run(run: dict[str, Any]) -> dict[str, Any]:
    """Copy a run and mark each exception. The stored row is left unchanged."""
    annotated = dict(run)
    annotated["exceptions"] = [
        {**row, "severity": severity_for(str(run["control_id"]), row)} for row in run["exceptions"]
    ]
    return annotated
