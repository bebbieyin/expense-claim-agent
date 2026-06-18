"""SQLAlchemy models for persisted expense claims."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base for application database models."""


class Employee(Base):
    """An employee available for expense claim submission."""

    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    employee_name: Mapped[str] = mapped_column(String(120), index=True)


class Claim(Base):
    """A submitted claim and its review result."""

    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    employee_id: Mapped[str] = mapped_column(String(64), index=True)
    employee_name: Mapped[str] = mapped_column(String(120))
    department: Mapped[str] = mapped_column(String(120))
    claim_date: Mapped[date] = mapped_column(Date)
    expense_category: Mapped[str] = mapped_column(String(64))
    expense_purpose: Mapped[str] = mapped_column(Text)
    claimed_amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8))
    receipt_file_path: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="processing")
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    review_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_agent_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    langfuse_trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
