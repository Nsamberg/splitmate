from datetime import date, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Member(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    is_admin: bool = False
    active: bool = True
    # Payment routing preference: when this member owes money, the recap
    # page's preference-aware suggestions try to route it to this person
    # first (e.g. because of a shared bank/currency), before falling back
    # to the plain minimal-transfer algorithm. Both optional and editable
    # from /admin — not a hard rule, just a preference.
    preferred_creditor_id: Optional[int] = Field(default=None, foreign_key="member.id")
    preference_note: Optional[str] = None


class Expense(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    description: str
    amount_cents: int
    paid_by_id: int = Field(foreign_key="member.id")
    expense_date: date
    created_by_id: int = Field(foreign_key="member.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    # Soft-delete: kept for audit trail, excluded from balances/lists.
    deleted_at: Optional[datetime] = None
    deleted_by_id: Optional[int] = Field(default=None, foreign_key="member.id")


class ExpenseParticipant(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    expense_id: int = Field(foreign_key="expense.id", index=True)
    member_id: int = Field(foreign_key="member.id", index=True)
    share_cents: int


class Settlement(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    from_member_id: int = Field(foreign_key="member.id")
    to_member_id: int = Field(foreign_key="member.id")
    amount_cents: int
    settlement_date: date
    note: Optional[str] = None
    created_by_id: int = Field(foreign_key="member.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    # Soft-delete, same as Expense.
    deleted_at: Optional[datetime] = None
    deleted_by_id: Optional[int] = Field(default=None, foreign_key="member.id")


class AppSetting(SQLModel, table=True):
    """Small key/value store for runtime-editable config, e.g. the access code."""

    key: str = Field(primary_key=True)
    value: str
