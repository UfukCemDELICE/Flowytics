from datetime import datetime, date, timezone
from uuid import uuid4
from sqlalchemy import Column
from sqlmodel import SQLModel, Field, JSON

class FinancialSnapshot(SQLModel, table=True):
    __tablename__ = "financial_snapshots"
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    snapshot_date: date
    source: str  # CHECK: codat, plaid
    data_type: str  # CHECK: profit_loss, balance_sheet, cash_flow, transactions, accounts, invoices, bills
    raw_data: dict = Field(sa_column=Column(JSON))
    period_start: date | None = Field(default=None)
    period_end: date | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
