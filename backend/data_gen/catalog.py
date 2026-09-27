"""Reference lists for the fictional broker-dealer. The generator does not invent these."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

SEED = 20260901
AS_OF = date(2026, 9, 1)
EMPLOYEE_COUNT = 400
TERMINATED_COUNT = 40
TERMINATED_ACTIVE_COUNT = 8
SOD_USER_COUNT = 6
BAD_CHANGE_COUNT = 10
GOOD_CHANGE_COUNT = 40
DORMANT_COUNT = 6
SHARED_COUNT = 5
DORMANT_DAYS = 90

ITGC_TERMINATED_ACTIVE = "ITGC-01"
ITGC_SOD = "ITGC-02"
ITGC_CHANGE = "ITGC-03"
ITGC_DORMANT = "ITGC-04"
ITGC_SHARED = "ITGC-05"

SYSTEMS: tuple[str, ...] = (
    "trading platform",
    "general ledger",
    "payments",
    "HR system",
    "core database",
)

FIRST_NAMES: tuple[str, ...] = (
    "Avery",
    "Blake",
    "Cameron",
    "Dana",
    "Ellis",
    "Finley",
    "Gray",
    "Harper",
    "Indigo",
    "Jordan",
    "Kai",
    "Logan",
    "Morgan",
    "Noel",
    "Parker",
    "Quinn",
    "Reese",
    "Sawyer",
    "Taylor",
    "Winter",
)

LAST_NAMES: tuple[str, ...] = (
    "Adler",
    "Brooks",
    "Cho",
    "Dalton",
    "Estevez",
    "Farrell",
    "Gupta",
    "Hansen",
    "Ibarra",
    "Jensen",
    "Kapoor",
    "Larsen",
    "Morales",
    "Nguyen",
    "Okonkwo",
    "Patel",
    "Quintana",
    "Rahman",
    "Sato",
    "Tremblay",
)


@dataclass(frozen=True, slots=True)
class Department:
    name: str
    titles: tuple[str, str]
    roles: tuple[str, str]


DEPARTMENTS: tuple[Department, ...] = (
    Department("Trading", ("Trader", "Trading Analyst"), ("trader", "trading_read")),
    Department("Finance", ("Accountant", "Financial Analyst"), ("journal_preparer", "gl_read")),
    Department("Payments", ("Payments Specialist", "Payments Analyst"), ("payment_initiator", "payment_read")),
    Department("Human Resources", ("HR Generalist", "HR Analyst"), ("hr_viewer", "access_requester")),
    Department("Information Technology", ("Developer", "Database Analyst"), ("developer", "dba_read")),
    Department("Compliance", ("Compliance Analyst", "Compliance Officer"), ("trading_read", "gl_read")),
    Department("Operations", ("Operations Analyst", "Operations Specialist"), ("payment_read", "gl_read")),
    Department("Risk", ("Risk Analyst", "Market Risk Analyst"), ("trading_read", "payment_read")),
)

# One permission per role, so a conflict only appears when a person holds two roles.
ROLE_PERMISSIONS: tuple[tuple[str, str, str], ...] = (
    ("trader", "trading platform", "submit_trade"),
    ("trade_supervisor", "trading platform", "approve_trade"),
    ("trading_read", "trading platform", "view_positions"),
    ("journal_preparer", "general ledger", "create_journal"),
    ("journal_approver", "general ledger", "approve_journal"),
    ("gl_read", "general ledger", "view_ledger"),
    ("payment_initiator", "payments", "create_payment"),
    ("payment_approver", "payments", "approve_payment"),
    ("payment_read", "payments", "view_payments"),
    ("hr_viewer", "HR system", "view_employee"),
    ("access_requester", "HR system", "request_access"),
    ("access_approver", "HR system", "approve_access"),
    ("developer", "core database", "develop_change"),
    ("release_manager", "core database", "deploy_change"),
    ("dba_read", "core database", "view_schema"),
)

SOD_RULES: tuple[tuple[str, str, str], ...] = (
    (
        "create_payment",
        "approve_payment",
        "One person must not initiate and approve the same payment.",
    ),
    (
        "create_journal",
        "approve_journal",
        "One person must not prepare and approve the same journal entry.",
    ),
    (
        "submit_trade",
        "approve_trade",
        "One person must not submit and approve the same trade.",
    ),
    (
        "request_access",
        "approve_access",
        "One person must not request and approve the same access.",
    ),
    (
        "develop_change",
        "deploy_change",
        "One person must not develop and deploy the same change.",
    ),
)

# Existing role, conflicting role added for the injected users.
SOD_ASSIGNMENTS: tuple[tuple[str, str, int], ...] = (
    ("payment_initiator", "payment_approver", 2),
    ("journal_preparer", "journal_approver", 1),
    ("trader", "trade_supervisor", 1),
    ("access_requester", "access_approver", 1),
    ("developer", "release_manager", 1),
)

CHANGE_DESCRIPTIONS: tuple[str, ...] = (
    "Grant month-end read access to the general ledger",
    "Deploy the payments cutoff patch",
    "Add a settlement calendar to the trading platform",
    "Rotate the service credential on the core database",
    "Update the HR system new-hire workflow",
    "Correct the trade-date holiday table",
    "Enable dual control on the wire template",
    "Refresh the market-data entitlement file",
)
