from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Column
from sqlmodel import SQLModel, Field, JSON

class ComputedMetric(SQLModel, table=True):
    __tablename__ = "computed_metrics"
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    metric_type: str  # CHECK: burn_rate, runway, cash_forecast, anomaly, scenario, fundraising, monthly_report
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    period: str | None = Field(default=None)
    value: dict = Field(sa_column=Column(JSON))
    agent_run_id: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
