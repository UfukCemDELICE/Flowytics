from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import Column
from sqlmodel import SQLModel, Field, JSON

class AgentRun(SQLModel, table=True):
    __tablename__ = "agent_runs"
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    trigger_type: str  # CHECK: scheduled, slack_message, webhook, manual
    trigger_payload: dict | None = Field(default=None, sa_column=Column(JSON))
    status: str = Field(default="running")  # CHECK: running, completed, failed
    tools_called: list = Field(default=[], sa_column=Column(JSON))
    model_used: str | None = Field(default=None)
    tokens_input: int = Field(default=0)
    tokens_output: int = Field(default=0)
    cost_usd: Decimal = Field(default=Decimal("0"))
    duration_ms: int | None = Field(default=None)
    output_result: dict | None = Field(default=None, sa_column=Column(JSON))
    error: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
