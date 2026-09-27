"""Tables created by backend/sql/schema.sql."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Identity, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class HrRoster(Base):
    __tablename__ = "hr_roster"

    employee_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    department: Mapped[str] = mapped_column(Text)
    job_title: Mapped[str] = mapped_column(Text)
    hire_date: Mapped[date] = mapped_column(Date)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role: Mapped[str] = mapped_column(Text, primary_key=True)
    permission: Mapped[str] = mapped_column(Text, primary_key=True)


class SodConflictRule(Base):
    __tablename__ = "sod_conflict_rules"

    rule_id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    permission_a: Mapped[str] = mapped_column(Text)
    permission_b: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)


class IamAccount(Base):
    __tablename__ = "iam_accounts"

    account_id: Mapped[str] = mapped_column(Text, primary_key=True)
    employee_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("hr_roster.employee_id"), nullable=True
    )
    system: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_shared: Mapped[bool] = mapped_column(Boolean)


class ChangeTicket(Base):
    __tablename__ = "change_tickets"

    ticket_id: Mapped[str] = mapped_column(Text, primary_key=True)
    system: Mapped[str] = mapped_column(Text)
    requested_by: Mapped[str] = mapped_column(Text, ForeignKey("hr_roster.employee_id"))
    approved_by: Mapped[str | None] = mapped_column(
        Text, ForeignKey("hr_roster.employee_id"), nullable=True
    )
    deployed_by: Mapped[str] = mapped_column(Text, ForeignKey("hr_roster.employee_id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deployed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[str] = mapped_column(Text)
