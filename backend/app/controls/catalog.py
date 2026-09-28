"""Control metadata. The detection logic lives in backend/sql."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SQL_DIR = Path(__file__).resolve().parents[2] / "sql"


@dataclass(frozen=True, slots=True)
class Control:
    control_id: str
    name: str
    objective: str
    risk_addressed: str
    population: str
    suggested_action: str
    sql_path: Path
    uses_as_of: bool


def _control(
    control_id: str,
    name: str,
    objective: str,
    risk_addressed: str,
    population: str,
    suggested_action: str,
    filename: str,
    uses_as_of: bool,
) -> Control:
    return Control(
        control_id,
        name,
        objective,
        risk_addressed,
        population,
        suggested_action,
        SQL_DIR / filename,
        uses_as_of,
    )


CONTROLS: dict[str, Control] = {
    control.control_id: control
    for control in (
        _control(
            "ITGC-01",
            "Terminated user access",
            "Active application accounts are removed when employment ends.",
            "A former employee can still sign in and use a production system after the termination date.",
            "accounts belonging to terminated employees",
            "Disable the account and record the date access was removed.",
            "itgc_01_terminated_access.sql",
            True,
        ),
        _control(
            "ITGC-02",
            "Segregation of duties",
            "No one person holds both permissions in a conflicting pair.",
            "A user who can both create and approve the same action can bypass a second-person check.",
            "employees who have at least one application account",
            "Remove one permission from the conflicting pair so one person cannot both prepare and approve.",
            "itgc_02_segregation_of_duties.sql",
            False,
        ),
        _control(
            "ITGC-03",
            "Change management",
            "A deployed change is approved by someone other than the requester and the deployer, before deployment.",
            "An unapproved or self-approved change can put unreviewed code or configuration into production.",
            "change tickets that have been deployed",
            "Obtain approval from someone other than the requester and the deployer before deployment.",
            "itgc_03_change_management.sql",
            False,
        ),
        _control(
            "ITGC-04",
            "Dormant accounts",
            "An active account has been used within the last 90 days, or it is disabled.",
            "A credential nobody is watching can be reused without the owner noticing.",
            "active accounts that are not shared",
            "Disable the account, or confirm a login inside the dormancy window.",
            "itgc_04_dormant_accounts.sql",
            True,
        ),
        _control(
            "ITGC-05",
            "Shared or generic accounts",
            "Each active account belongs to one identifiable person.",
            "A shared or generic login cannot be tied to one employee, so activity cannot be attributed.",
            "active accounts",
            "Replace the shared login with an account assigned to one employee.",
            "itgc_05_shared_accounts.sql",
            False,
        ),
        _control(
            "ITGC-06",
            "Orphaned accounts and unknown users",
            "Every application account and every change is tied to a person on the HR roster.",
            "An account or a change that names someone the roster does not list cannot be attributed, reviewed, or removed when that person leaves.",
            "accounts with no matching HR record, and changes made by people not on the roster",
            "Add the person to the HR roster, or remove the account and hold the change until that person is recorded.",
            "itgc_06_orphaned_records.sql",
            False,
        ),
    )
}


def describe_controls() -> list[dict[str, str]]:
    return [
        {
            "control_id": control.control_id,
            "name": control.name,
            "objective": control.objective,
            "risk_addressed": control.risk_addressed,
            "population": control.population,
            "suggested_action": control.suggested_action,
        }
        for control in CONTROLS.values()
    ]


class UnknownControl(KeyError):
    """The control id is not one of the ITGC tests."""
