from datetime import datetime
from uuid import uuid4, UUID
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import SQLModel, Field, JSON

from backend.app.utils import utc_now

class ComputedMetric(SQLModel, table=True):
    __tablename__ = "computed_metrics"
    id: UUID = Field(default_factory=uuid4, sa_column=Column(PG_UUID(as_uuid=True), primary_key=True))
    tenant_id: UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), nullable=False, index=True))
    metric_type: str  # CHECK: burn_rate, runway, cash_forecast, anomaly, scenario, fundraising, monthly_report
    computed_at: datetime = Field(default_factory=utc_now)
    period: str | None = Field(default=None)
    value: dict = Field(sa_column=Column(JSON))
    agent_run_id: UUID | None = Field(default=None, sa_column=Column(PG_UUID(as_uuid=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now)
