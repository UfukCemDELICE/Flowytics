from datetime import datetime, date
from uuid import uuid4, UUID
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import SQLModel, Field, JSON

from backend.app.utils import utc_now

class FinancialSnapshot(SQLModel, table=True):
    __tablename__ = "financial_snapshots"
    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True)
    )
    tenant_id: UUID = Field(
        sa_column=Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    )
    snapshot_date: date
    source: str
    data_type: str
    raw_data: dict = Field(sa_column=Column(JSON))
    period_start: date | None = Field(default=None)
    period_end: date | None = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now)