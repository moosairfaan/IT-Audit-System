"""Who is selected first in a risk-based sample.

Privileged roles can approve or deploy. Critical systems are payments and the
general ledger. An item is higher risk when its role is privileged or its
system is critical.
"""

from __future__ import annotations

PRIVILEGED_ROLES = frozenset(
    {
        "trade_supervisor",
        "journal_approver",
        "payment_approver",
        "access_approver",
        "release_manager",
    }
)
CRITICAL_SYSTEMS = frozenset({"payments", "general ledger"})


def is_priority(
    role: str | None,
    system: str | None,
    privileged: frozenset[str] | set[str] | None = None,
    critical: frozenset[str] | set[str] | None = None,
) -> bool:
    roles = PRIVILEGED_ROLES if privileged is None else privileged
    systems = CRITICAL_SYSTEMS if critical is None else critical
    return role in roles or system in systems
